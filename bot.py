import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import aiohttp
from urllib.parse import quote_plus
import logging
import logging.handlers
import json
from typing import Union, Dict, Any, List
from discord import TextChannel, ForumChannel, CategoryChannel
from discord.abc import Messageable
import sys
import asyncio
from datetime import datetime
from config import CONFIG, get_config

# Konfiguracja logowania z rotacją
log_handler = logging.handlers.RotatingFileHandler(
    'bot.log',
    maxBytes=1024 * 1024,  # 1MB
    backupCount=5,
    encoding='utf-8'
)
log_handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s'
))
logging.basicConfig(
    level=logging.INFO,
    handlers=[log_handler, logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

def validate_port(port_str):
    """Walidacja portu serwera"""
    try:
        port = int(port_str)
        if 1 <= port <= 65535:
            return port
        raise ValueError(f"Port musi być między 1 a 65535, otrzymano {port}")
    except ValueError:
        raise ValueError(f"Nieprawidłowy numer portu: {port_str}")

def load_config() -> Dict[str, Any]:
    """Ładuje i waliduje konfigurację"""
    config_path = os.path.join('config', 'config.json')
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Plik konfiguracyjny nie istnieje: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Walidacja wymaganych pól (token i hasło mogą być w .env)
        load_dotenv()
        required_fields = [
            'GAME_SERVER_HOST',
            'GAME_SERVER_PORT'
        ]
        missing_fields = [field for field in required_fields if not config.get(field)]
        if missing_fields:
            raise ValueError(f"Brakujące wymagane pola w konfiguracji: {', '.join(missing_fields)}")
        # Token i hasło: sprawdź czy są w config.json LUB w .env
        if not (config.get('DISCORD_TOKEN') or os.getenv('DISCORD_TOKEN')):
            raise ValueError("Brakujący DISCORD_TOKEN w config.json lub .env")
        if not (config.get('GAME_SERVER_RCON_PASSWORD') or os.getenv('GAME_SERVER_RCON_PASSWORD')):
            raise ValueError("Brakujący GAME_SERVER_RCON_PASSWORD w config.json lub .env")
        # Konwersja ID na int
        id_fields = [
            'DISCORD_CHANNEL_ID',
            'DISCORD_PRIVATE_CHANNEL_ID',
            'DISCORD_LOG_CHANNEL_ID',
            'DISCORD_ADMIN_ROLE_ID',
            'DISCORD_MOD_ROLE_ID'
        ]
        for field in id_fields:
            if field in config and isinstance(config[field], str):
                try:
                    config[field] = int(config[field])
                except ValueError:
                    logger.warning(f"Nieprawidłowa wartość dla {field}: {config[field]}")
                    config[field] = 0
        # Konwersja portu na int
        try:
            config['GAME_SERVER_PORT'] = int(config['GAME_SERVER_PORT'])
        except ValueError:
            raise ValueError(f"Nieprawidłowy port serwera: {config['GAME_SERVER_PORT']}")
        return config
    except json.JSONDecodeError as e:
        raise ValueError(f"Błąd parsowania pliku konfiguracyjnego: {str(e)}")
    except Exception as e:
        raise Exception(f"Błąd wczytywania konfiguracji: {str(e)}")

# Wczytaj konfigurację
try:
    config = load_config()
    logger.info("Konfiguracja wczytana pomyślnie")
except Exception as e:
    logger.critical(f"Błąd wczytywania konfiguracji: {str(e)}")
    sys.exit(1)

# Konfiguracja została przeniesiona do config.py

# Ładuj zmienne środowiskowe - teraz obsługiwane przez config.py
TOKEN = CONFIG.get('DISCORD_TOKEN', '')
PREFIX = '!'

# Konfiguracja intencji
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MyHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        bot: "MotorTownBot" = self.context.bot # type: ignore
        embed = discord.Embed(
            title="📚 Lista Dostępnych Komend",
            description="Poniżej znajdziesz wszystkie dostępne komendy:",
            color=discord.Color.blue()
        )

        # Komendy dla wszystkich
        public_commands = [
            ("!status", "Sprawdź status serwera i listę graczy online"),
            ("!help", "Wyświetla tę listę komend")
        ]
        
        embed.add_field(
            name="🌐 Komendy Publiczne",
            value="\n".join([f"`{cmd}` - {desc}" for cmd, desc in public_commands]),
            inline=False
        )

        # Komendy dla moderatorów i adminów
        if isinstance(self.context.author, discord.Member) and (bot.has_role(self.context.author, bot.moderator_role) or bot.has_role(self.context.author, bot.admin_role)):
            mod_commands = [
                ("!playersmg", "Panel zarządzania graczami"),
                ("!kick <id>", "Wyrzuć gracza z serwera"),
                ("!chat <wiadomość>", "Wyślij wiadomość na czat w grze"),
                ("!ban <id>", "Zbanuj gracza"),
                ("!unban <id>", "Odbanuj gracza"),
                ("!banlist", "Lista zbanowanych graczy")
            ]
            
            embed.add_field(
                name="🛡️ Komendy Administracyjne",
                value="\n".join([f"`{cmd}` - {desc}" for cmd, desc in mod_commands]),
                inline=False
            )

        await self.get_destination().send(embed=embed)

class MotorTownBot(commands.Bot):
    def __init__(self, config):
        super().__init__(command_prefix=PREFIX, intents=intents, help_command=MyHelpCommand())
        self.config = config
        
        # Konfiguracja API
        self.server_ip = self.config.get("GAME_SERVER_HOST", "")
        self.web_port = validate_port(self.config.get("GAME_SERVER_PORT", "0"))
        self.game_slots = int(self.config.get("GAME_SLOTS", "50"))
        # Pobieraj hasło z .env jeśli istnieje
        self.password = quote_plus(os.getenv('GAME_SERVER_RCON_PASSWORD') or self.config.get("GAME_SERVER_RCON_PASSWORD", ""))
        self.base_url = f"http://{self.server_ip}:{self.web_port}"
        self.timeout = aiohttp.ClientTimeout(total=10)
        
        # Konfiguracja kanałów
        self.public_channel = int(self.config.get("DISCORD_CHANNEL_ID", "0"))
        self.private_channel = int(self.config.get("DISCORD_PRIVATE_CHANNEL_ID", "0"))
        self.log_channel = int(self.config.get("DISCORD_LOG_CHANNEL_ID", "0"))
        
        # Konfiguracja ról
        self.admin_role = int(self.config.get("DISCORD_ADMIN_ROLE_ID", "0"))
        self.moderator_role = int(self.config.get("DISCORD_MOD_ROLE_ID", "0"))
        
        # Inicjalizacja historii graczy
        self.player_history = [0] * 24
        self.last_player_count = 0
        self.player_data_file = "webpanel/player_data.json"
        self.load_player_history()

    def load_player_history(self):
        """Ładuje historię graczy z pliku"""
        try:
            if os.path.exists(self.player_data_file):
                with open(self.player_data_file, 'r') as f:
                    data = json.load(f)
                    self.player_history = data.get('history', [0] * 24)
                    self.last_player_count = data.get('current', 0)
        except Exception as e:
            logger.error(f"Błąd podczas ładowania historii graczy: {e}")
            self.player_history = [0] * 24
            self.last_player_count = 0

    def save_player_data(self):
        """Zapisuje dane o graczach do pliku"""
        try:
            os.makedirs(os.path.dirname(self.player_data_file), exist_ok=True)
            with open(self.player_data_file, 'w') as f:
                json.dump({
                    'history': self.player_history,
                    'current': self.last_player_count,
                    'last_update': datetime.now().isoformat()
                }, f)
        except Exception as e:
            logger.error(f"Błąd podczas zapisywania danych o graczach: {e}")

    async def update_player_count(self):
        """Aktualizuje liczbę graczy i historię"""
        while not self.is_closed():
            try:
                response = await self.api_request('GET', '/player/count')
                if response['succeeded']:
                    current_count = response['data'].get('num_players', 0)
                    
                    # Aktualizuj historię
                    current_hour = datetime.now().hour
                    self.player_history[current_hour] = current_count
                    self.last_player_count = current_count
                    
                    # Zapisz dane
                    self.save_player_data()
                    
                else:
                    logger.warning(f"Nie udało się pobrać liczby graczy: {response['message']}")
            except Exception as e:
                logger.error(f"Błąd podczas aktualizacji liczby graczy: {e}")
            
            await asyncio.sleep(60)  # Aktualizuj co minutę

    async def api_request(self, method, endpoint, payload=None):
        """
        Wspólna funkcja do komunikacji z API serwera gry.
        
        Args:
            method (str): Metoda HTTP ('GET' lub 'POST')
            endpoint (str): Endpoint API
            payload (dict, optional): Dane dla żądania POST
            
        Returns:
            dict: Odpowiedź z API zawierająca status i dane
        """
        try:
            if method.upper() not in ['GET', 'POST']:
                raise ValueError(f"Nieobsługiwana metoda HTTP: {method}")
                
            # Walidacja URL
            if not endpoint.startswith('/'):
                endpoint = f"/{endpoint}"
                
            # Dodaj password do endpointu
            endpoint = f"{endpoint}{'&' if '?' in endpoint else '?'}password={self.password}"
            url = f"{self.base_url}{endpoint}"
            headers = {"Authorization": f"Bearer {self.password}"}
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.request(method, url, json=payload, headers=headers) as response:
                    try:
                        data = await response.json()
                    except aiohttp.ContentTypeError:
                        data = {}
                        
                    return {
                        "succeeded": 200 <= response.status < 300,
                        "status_code": response.status,
                        "data": data.get('data', {}),
                        "message": data.get('message', f"HTTP {response.status}")
                    }
                    
        except aiohttp.ClientError as e:
            return {
                "succeeded": False,
                "status_code": None,
                "data": {},
                "message": f"Błąd połączenia: {str(e)}",
                "error_type": "connection"
            }
        except Exception as e:
            return {
                "succeeded": False,
                "status_code": None,
                "data": {},
                "message": f"Błąd krytyczny: {str(e)}",
                "error_type": "critical"
            }

    async def log_admin_action(self, ctx, action, target, reason=None, success=True):
        """Loguje akcję administracyjną na kanale logów"""
        try:
            channel = self.get_channel(self.log_channel)
            if not isinstance(channel, Messageable):
                print(f"Nie znaleziono kanału logów lub kanał nie jest tekstowy {self.log_channel}")
                return
                
            embed = discord.Embed(
                title=f"{'✅' if success else '❌'} Akcja Administracyjna: {action.title()}",
                color=discord.Color.green() if success else discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="Administrator", value=ctx.author.mention)
            embed.add_field(name="Cel", value=target)
            if reason:
                embed.add_field(name="Powód", value=reason, inline=False)
                
            await channel.send(embed=embed)
        except Exception as e:
            print(f"Błąd logowania akcji: {str(e)}")

    def has_role(self, member, role_id):
        """Sprawdza czy użytkownik ma określoną rolę"""
        return role_id in [role.id for role in member.roles]

    def create_embed(self, ctx: commands.Context, success=True, **kwargs):
        """Wspólna funkcja do tworzenia embedów"""
        embed = discord.Embed(
            color=discord.Color.green() if success else discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        if ctx.author and ctx.author.display_avatar:
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar)
        if self.user and self.user.display_avatar:
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
        """Uruchamia zadania w tle przy starcie bota"""
        try:
            # Ładowanie cogów
            await self.load_extension('cogs.status')
            await self.load_extension('cogs.playersmg')
            print("✅ Wszystkie cogi załadowane pomyślnie")
            
            # Uruchomienie zadania aktualizacji liczby graczy
            self.loop.create_task(self.update_player_count())
        except Exception as e:
            print(f"❌ Błąd ładowania cogów: {e}")

    async def on_ready(self):
        logger.info(f"--- BOT IS READY ---")
        if self.user:
            logger.info(f'Logged in as {self.user.name}')
            logger.info(f'User ID: {self.user.id}')
        else:
            logger.warning("Bot is ready but self.user is not available.")
        logger.info(f'Discord.py Version: {discord.__version__}')
        logger.info(f'Public Channel: {self.public_channel}')
        logger.info(f'Log Channel: {self.log_channel}')
        logger.info(f'Admin Role: {self.admin_role}')
        logger.info("--------------------")
        
        # Start background tasks
        self.update_player_count_task = self.loop.create_task(self.update_player_count())
        
        logger.info("Cogs loaded:")
        for cog in self.cogs:
            logger.info(f"- {cog}")

        logger.info("Attempting to sync commands...")
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands.")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")
            
        logger.info("Bot is fully operational.")

# Tworzenie i uruchamianie bota
bot = MotorTownBot(CONFIG)

if __name__ == '__main__':
    # Upewnij się, że token jest dostępny
    if not TOKEN:
        logger.critical("CRITICAL: DISCORD_TOKEN is not set. Bot cannot start.")
    else:
        logger.info(f"Starting bot with token ending in ...{TOKEN[-4:]}")
        try:
            bot.run(TOKEN)
        except discord.errors.LoginFailure:
            logger.critical("Login failed. The provided Discord token is invalid.")
        except Exception as e:
            logger.critical(f"An error occurred while running the bot: {e}")