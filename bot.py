import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import aiohttp
from urllib.parse import quote_plus

load_dotenv()

# Sprawdzenie wymaganych zmiennych środowiskowych
required_env_vars = ["DISCORD_TOKEN", "SERVER_IP", "WEB_PORT", "WEB_API_PASSWORD"]
for var in required_env_vars:
    if not os.getenv(var):
        raise ValueError(f"Brak wymaganej zmiennej środowiskowej: {var}")

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = '!'

# Konfiguracja intencji
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MotorTownBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=PREFIX, intents=intents)
        
        # Konfiguracja API (wspólna dla wszystkich cogów)
        self.server_ip = os.getenv("SERVER_IP")
        self.web_port = int(os.getenv("WEB_PORT"))
        self.game_slots = int(os.getenv("GAME_SLOTS", 50))  # Domyślnie 50 jeśli nie ustawione
        self.password = quote_plus(os.getenv("WEB_API_PASSWORD"))
        self.base_url = f"http://{self.server_ip}:{self.web_port}"
        self.timeout = aiohttp.ClientTimeout(total=10)
        
        # Konfiguracja kanałów
        self.public_channel = int(os.getenv("PUBLIC_CHANNEL")) if os.getenv("PUBLIC_CHANNEL") else None
        self.private_channel = int(os.getenv("PRIVATE_CHANNEL")) if os.getenv("PRIVATE_CHANNEL") else None
        
        # Konfiguracja ról z walidacją
        admin_role = os.getenv("ADMIN_ROLE")
        if not admin_role or not admin_role.strip():
            raise ValueError("ADMIN_ROLE nie został ustawiony w pliku .env")
        self.admin_role = int(admin_role)
        
        moderator_role = os.getenv("MODERATOR_ROLE")
        if not moderator_role or not moderator_role.strip():
            raise ValueError("MODERATOR_ROLE nie został ustawiony w pliku .env")
        self.moderator_role = int(moderator_role)

    async def api_request(self, method, endpoint, payload=None):
        """
        Wspólna funkcja do komunikacji z API serwera gry.
        Używana przez wszystkie cogi.
        """
        try:
            # Dodaj password do endpointu
            if '?' in endpoint:
                endpoint += f"&password={self.password}"
            else:
                endpoint += f"?password={self.password}"
                
            url = f"{self.base_url}{endpoint}"
            headers = {"Authorization": f"Bearer {self.password}"}
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                if method.upper() == 'GET':
                    async with session.get(url, headers=headers) as response:
                        data = await response.json() if response.content_type == 'application/json' else {}
                        return {
                            "succeeded": 200 <= response.status < 300,
                            "data": data.get('data', {}),
                            "message": data.get('message', f"HTTP {response.status}")
                        }
                elif method.upper() == 'POST':
                    async with session.post(url, json=payload, headers=headers) as response:
                        data = await response.json() if response.content_type == 'application/json' else {}
                        return {
                            "succeeded": 200 <= response.status < 300,
                            "data": data.get('data', {}),
                            "message": data.get('message', f"HTTP {response.status}")
                        }
                else:
                    raise ValueError(f"Nieobsługiwana metoda HTTP: {method}")
                    
        except aiohttp.ClientError as e:
            return {"succeeded": False, "data": {}, "message": f"Błąd połączenia: {str(e)}"}
        except Exception as e:
            return {"succeeded": False, "data": {}, "message": f"Błąd krytyczny: {str(e)}"}

    def has_role(self, member, role_id):
        """Sprawdza czy użytkownik ma określoną rolę"""
        return role_id in [role.id for role in member.roles]

    def create_embed(self, ctx, success=True, **kwargs):
        """Wspólna funkcja do tworzenia embedów"""
        embed = discord.Embed(
            color=discord.Color.green() if success else discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar)
        embed.set_footer(text="MotorTown.pl ©", icon_url=self.user.display_avatar)
        
        for key, value in kwargs.items():
            if key == 'title':
                embed.title = value
            elif key == 'description':
                embed.description = value
            elif key == 'fields':
                for name, value, inline in value:
                    embed.add_field(name=name, value=value, inline=inline)
        return embed

    async def setup_hook(self):
        """Ładowanie cogów przy starcie"""
        try:
            await self.load_extension('cogs.status')
            await self.load_extension('cogs.playersmg')
            print("✅ Wszystkie cogi załadowane pomyślnie")
        except Exception as e:
            print(f"❌ Błąd ładowania cogów: {e}")

    async def on_ready(self):
        print(f'✅ Zalogowano jako {self.user.name}')
        print(f'🔗 Połączono z API: {self.base_url}')

# Tworzenie i uruchamianie bota
bot = MotorTownBot()

if __name__ == '__main__':
    bot.run(TOKEN)