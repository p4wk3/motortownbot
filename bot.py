import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")  # Token bota Discord
if not TOKEN:
    raise ValueError("Brak wymaganego tokena bota Discord w zmiennych środowiskowych")
PREFIX = '!'

# Konfiguracja intencji
intents = discord.Intents.default()
intents.message_content = True  # Wymaga włączenia Message Content Intent
intents.members = True          # Wymaga włączenia Server Members Intent (opcjonalnie)

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

@bot.event
async def on_ready():
    print(f'Zalogowano jako {bot.user.name}')
    await bot.load_extension('cogs.status')  # Wczytanie cogs/status.py
    await bot.load_extension('cogs.playersmg') # Wczytanie cogs/playersmg.py

if __name__ == '__main__':
    bot.run(TOKEN)




