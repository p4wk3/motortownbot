import discord
from discord.ext import commands, tasks
import aiohttp
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus
import time
import datetime

load_dotenv()

class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.server_ip = os.getenv("SERVER_IP")
        self.web_port = int(os.getenv("WEB_PORT", 8080))
        self.game_slots = int(os.getenv("GAME_SLOTS", 50))
        self.password = quote_plus(os.getenv("WEB_API_PASSWORD"))
        self.base_url = f"http://{self.server_ip}:{self.web_port}"
        self.timeout = aiohttp.ClientTimeout(total=10)
        
        # Poprawione pobieranie wartości z .env
        self.public_channel = int(os.getenv("PUBLIC_CHANNEL")) if os.getenv("PUBLIC_CHANNEL") else None
        self.private_channel = int(os.getenv("PRIVATE_CHANNEL")) if os.getenv("PRIVATE_CHANNEL") else None
        
        self.last_status = None
        self.update_status.start()
        self.check_status.start()

    def cog_unload(self):
        self.update_status.cancel()
        self.check_status.cancel()

    async def api_request(self, method, endpoint, params=None):
        try:
            url = f"{self.base_url}{endpoint}"
            query_params = {"password": self.password}
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.request(
                    method=method,
                    url=url,
                    params=query_params,
                    raise_for_status=False  # Wyłączamy automatyczne rzucanie błędów
                ) as response:
                    data = await response.json(content_type=None) if response.content_type == 'application/json' else {}
                    
                    return {
                        "succeeded": 200 <= response.status < 300,
                        "data": data.get('data', {}),
                        "message": data.get('message', f"HTTP {response.status}")
                    }
                    
        except aiohttp.ClientError as e:
            return {"succeeded": False, "data": {}, "message": f"Błąd połączenia: {str(e)}"}
        except Exception as e:
            return {"succeeded": False, "data": {}, "message": f"Błąd krytyczny: {str(e)}"}

    @tasks.loop(seconds=5)
    async def check_status(self):
        try:
            if self.public_channel:
                channel = self.bot.get_channel(self.public_channel)
                previous_status = self.last_status
                
                # Aktualizuj status i pobierz nowy stan
                current_status = await self._update_presence()
                
                if previous_status != current_status:
                    status_msg = "🟢 **Serwer uruchomiony!**" if current_status else "🔴 **Serwer wyłączony!**"
                    embed = discord.Embed(
                        description=status_msg,
                        color=discord.Color.green() if current_status else discord.Color.red()
                    )
                    embed.set_footer(text=f"Status: {datetime.datetime.now().strftime('%H:%M:%S')}")
                    await channel.send(embed=embed)
                    self.last_status = current_status

        except Exception as e:
            print(f"Błąd sprawdzania statusu: {str(e)}")

    @tasks.loop(minutes=1)
    async def update_status(self):
        try:
            await self._update_presence()
        except Exception as e:
            print(f"Status update error: {str(e)}")

    async def _update_presence(self):
        try:
            # Sprawdź status serwera
            status_check = await self.api_request('GET', '/player/count')
            
            if status_check.get('succeeded'):
                count = status_check['data'].get('num_players', 0)
                status_text = f"{count}/{self.game_slots} 🚗"
                activity_type = discord.ActivityType.playing
            else:
                status_text = "Serwer OFFLINE 🔴"
                activity_type = discord.ActivityType.watching

            activity = discord.Activity(
                type=activity_type,
                name=status_text
            )
            await self.bot.change_presence(activity=activity)
            
            # Zwróć aktualny status dla powiadomień
            return status_check['succeeded']
            
        except Exception as e:
            print(f"Błąd aktualizacji statusu: {str(e)}")
            await self.bot.change_presence(activity=discord.Activity(
                name="Serwer OFFLINE 🔴",
                type=discord.ActivityType.watching
            ))
            return False

    def create_embed(self, ctx, success=True, **kwargs):
        embed = discord.Embed(
            color=discord.Color.green() if success else discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar)
        embed.set_footer(text="MotorTown.pl ©", icon_url=self.bot.user.display_avatar)
        
        for key, value in kwargs.items():
            if key == 'title':
                embed.title = value
            elif key == 'description':
                embed.description = value
            elif key == 'fields':
                for name, value, inline in value:
                    embed.add_field(name=name, value=value, inline=inline)
        return embed
    
    @commands.command(name='status')
    async def status_command(self, ctx):
        """Pokazuje status serwera i graczy"""
        start_time = time.monotonic()
        
        count_data = await self.api_request('GET', '/player/count')
        is_online = count_data.get('succeeded', False)
        
        # Jeśli serwer jest offline - krótki komunikat
        if not is_online:
            embed = self.create_embed(
                ctx,
                success=False,
                title="🔴 Serwer OFFLINE",
                description="```diff\n- Serwer jest aktualnie niedostępny\n- Spróbuj ponownie później\n```",
                fields=[
                    ("🌐 Adres", f"```{self.server_ip}```", True),
                    ("📡 Status", "```🔴 Brak połączenia```", True)
                ]
            )
            embed.color = discord.Color.dark_red()
            return await ctx.send(embed=embed)

        # Jeśli serwer online - pełne informacje
        ping = int((time.monotonic() - start_time) * 1000)
        list_data = await self.api_request('GET', '/player/list')
        
        count = count_data['data'].get('num_players', 0)
        players = list_data['data'].values() if list_data.get('succeeded') else []
        
        player_list = "\n".join([f"• {p['name']}" for p in players]) if players else "```diff\n- Brak aktywnych graczy\n```"
        
        embed = self.create_embed(
            ctx,
            title="📊 Status Serwera",
            description=f"**Gracze online ({count}):**\n{player_list}",
            fields=[
                ("🌐 Adres", f"```{self.server_ip}```", True),
                ("⏱ Ping", f"```{ping}ms```", True),
                ("📈 Status", f"```🟢 Online ({count})```", True)
            ]
        )
        embed.color = discord.Color.blurple()
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Status(bot))
    print("Status cog: loaded")