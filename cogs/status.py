import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import time
import datetime

load_dotenv()

class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_status = None
        
        # Startuj taski
        self.update_status.start()
        self.check_status.start()

    def cog_unload(self):
        self.update_status.cancel()
        self.check_status.cancel()

    @tasks.loop(seconds=5)
    async def check_status(self):
        """Sprawdza zmiany statusu serwera i wysyła powiadomienia"""
        try:
            if self.bot.public_channel:
                channel = self.bot.get_channel(self.bot.public_channel)
                if not channel:
                    return
                    
                previous_status = self.last_status
                
                # Aktualizuj status i pobierz nowy stan
                current_status = await self._update_presence()
                
                # Wyślij powiadomienie tylko przy zmianie statusu
                if previous_status is not None and previous_status != current_status:
                    status_msg = "🟢 **Serwer uruchomiony!**" if current_status else "🔴 **Serwer wyłączony!**"
                    embed = discord.Embed(
                        description=status_msg,
                        color=discord.Color.green() if current_status else discord.Color.red()
                    )
                    embed.set_footer(text=f"{datetime.datetime.now().strftime('%H:%M:%S')}")
                    await channel.send(embed=embed)
                
                self.last_status = current_status

        except Exception as e:
            print(f"Błąd sprawdzania statusu: {str(e)}")

    @tasks.loop(minutes=1)
    async def update_status(self):
        """Aktualizuje status bota co minutę"""
        try:
            await self._update_presence()
        except Exception as e:
            print(f"Status update error: {str(e)}")

    async def _update_presence(self):
        """Aktualizuje obecność bota i zwraca status serwera"""
        try:
            # Używaj API z głównego bota
            status_check = await self.bot.api_request('GET', '/player/count')
            
            if status_check.get('succeeded'):
                count = status_check['data'].get('num_players', 0)
                status_text = f"{count}/{self.bot.game_slots} 🚗"
                activity_type = discord.ActivityType.playing
                server_online = True
            else:
                status_text = "Serwer OFFLINE 🔴"
                activity_type = discord.ActivityType.watching
                server_online = False

            activity = discord.Activity(
                type=activity_type,
                name=status_text
            )
            await self.bot.change_presence(activity=activity)
            
            return server_online
            
        except Exception as e:
            print(f"Błąd aktualizacji statusu: {str(e)}")
            await self.bot.change_presence(activity=discord.Activity(
                name="Serwer OFFLINE 🔴",
                type=discord.ActivityType.watching
            ))
            return False
    
    @commands.command(name='status')
    async def status_command(self, ctx):
        """Pokazuje status serwera i graczy"""
        start_time = time.monotonic()
        
        # Używaj API z głównego bota
        count_data = await self.bot.api_request('GET', '/player/count')
        is_online = count_data.get('succeeded', False)
        
        # Jeśli serwer jest offline - krótki komunikat
        if not is_online:
            embed = self.bot.create_embed(
                ctx,
                success=False,
                title="🔴 Serwer OFFLINE",
                description="```diff\n- Serwer jest aktualnie niedostępny```",
                fields=[
                    ("🌐 Adres", f"```{self.bot.server_ip}```", True),
                    ("📡 Status", "```🔴 Brak połączenia```", True),
                    ("❌ Błąd", f"```{count_data.get('message', 'Nieznany błąd')}```", False)
                ]
            )
            embed.color = discord.Color.dark_red()
            return await ctx.send(embed=embed)

        # Jeśli serwer online - pełne informacje
        ping = int((time.monotonic() - start_time) * 1000)
        list_data = await self.bot.api_request('GET', '/player/list')
        
        count = count_data['data'].get('num_players', 0)
        
        # Przetwórz listę graczy
        players = []
        if list_data.get('succeeded'):
            players_raw = list_data.get('data', {})
            if isinstance(players_raw, dict):
                players = list(players_raw.values())
            elif isinstance(players_raw, list):
                players = players_raw
        
        # Utwórz listę graczy do wyświetlenia
        if players:
            player_list = "\n".join([f"• {p.get('name', 'Nieznany gracz')}" for p in players])
        else:
            player_list = "```diff\n- Brak aktywnych graczy\n```"
        
        embed = self.bot.create_embed(
            ctx,
            title="📊 Status Serwera",
            description=f"**Gracze online ({count}/{self.bot.game_slots}):**\n{player_list}",
            fields=[
                ("🌐 Adres", f"```{self.bot.server_ip}```", True),
                ("⏱ Ping", f"```{ping}ms```", True),
                ("📈 Status", f"```🟢 Online ({count})```", True)
            ]
        )
        embed.color = discord.Color.blurple()
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Status(bot))
    print("✅ Status cog: loaded")