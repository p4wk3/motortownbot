import os
import discord
import asyncio
from discord.ext import commands
from discord.ui import View, Button, Select
from discord import Interaction, ui
from typing import List, Dict
from dotenv import load_dotenv
from urllib.parse import quote_plus  # Dodano brakujący import
from urllib.parse import quote
from urllib.parse import urlencode
import aiohttp

# Ładowanie zmiennych środowiskowych
load_dotenv()

class PlayersMGMenu(View):
    def __init__(self, cog, players_data: List[Dict], banned_players: List[Dict] = None):
        super().__init__(timeout=30)
        self.cog = cog
        self.players = players_data
        self.banned_players = banned_players or []
        self.selected_player = None
        self.current_page = "main"
        
        # Dodaj początkowe komponenty
        self.update_components()

    def update_components(self):
        self.clear_items()
        
        if self.current_page == "main":
            self.add_item(PlayerSelect(self.players))
            self.add_item(BannedButton())
            self.add_item(CancelButton())
        elif self.current_page == "player_actions":
            self.add_item(ActionButton("Ban", discord.ButtonStyle.danger))
            self.add_item(ActionButton("Kick", discord.ButtonStyle.secondary))
            self.add_item(BackButton())
        elif self.current_page == "banned":
            self.add_item(BannedPlayersSelect(self.banned_players))
            self.add_item(BackButton())

    async def update_message(self, interaction: Interaction):
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    def create_embed(self):
        if self.current_page == "main":
            return self.create_main_embed()
        elif self.current_page == "player_actions":
            return self.create_player_embed()
        elif self.current_page == "banned":
            return self.create_banned_embed()
        return discord.Embed(title="Błąd", description="Nieznana strona")

    def create_main_embed(self):
        embed = discord.Embed(
            title="🎮 Zarządzanie Graczami",
            description="Wybierz gracza z listy:",
            color=discord.Color.blue()
        )
        if self.players:
            for player in self.players:
                embed.add_field(
                    name=f"👤 {player['name']}",
                    value=f"ID: `{player['unique_id']}`",
                    inline=False
                )
        else:
            embed.description = "Brak dostępnych graczy."
        return embed

    def create_player_embed(self):
        embed = discord.Embed(
            title=f"⚙️ Zarządzanie: {self.selected_player['name']}",
            color=discord.Color.orange()
        )
        embed.add_field(name="ID Gracza", value=f"`{self.selected_player['unique_id']}`")
        return embed

    def create_banned_embed(self):
        embed = discord.Embed(
            title="🚫 Zbanowani Gracze",
            color=discord.Color.red()
        )
        if self.banned_players:
            for player in self.banned_players:
                embed.add_field(
                    name=f"⛔ {player['name']}",
                    value=f"ID: `{player['unique_id']}`",
                    inline=False
                )
        else:
            embed.description = "Brak zbanowanych graczy."
        return embed

class PlayerSelect(Select):
    def __init__(self, players: List[Dict]):
        options = []
        
        # POPRAWKA: Sprawdź czy players nie jest None i czy ma elementy
        if players and isinstance(players, list):
            options = [
                discord.SelectOption(
                    label=player.get('name', 'Nieznany gracz'),  # Bezpieczne pobieranie nazwy
                    description=f"ID: {player.get('unique_id', 'N/A')}",
                    value=str(idx)
                ) for idx, player in enumerate(players)
                if isinstance(player, dict)  # Sprawdź czy element to słownik
            ]
        
        # Jeśli brak opcji, dodaj info
        if not options:
            options.append(discord.SelectOption(
                label="Brak graczy", 
                description="Brak dostępnych graczy", 
                value="none"
            ))
        
        super().__init__(placeholder="Wybierz gracza...", options=options)
        
        # Wyłącz select jeśli brak prawdziwych graczy
        if not players or options[0].value == "none":
            self.disabled = True

    async def callback(self, interaction: Interaction):
        if self.disabled or self.values[0] == "none":
            await interaction.response.send_message("Brak graczy do wybrania.", ephemeral=True)
            return

        view: PlayersMGMenu = self.view
        try:
            player_index = int(self.values[0])
            view.selected_player = view.players[player_index]
            view.current_page = "player_actions"
            view.update_components()
            await view.update_message(interaction)
        except (ValueError, IndexError) as e:
            await interaction.response.send_message("❌ Błąd wyboru gracza.", ephemeral=True)

class BannedPlayersSelect(Select):
    def __init__(self, banned_players: List[Dict]):
        options = [
            discord.SelectOption(
                label=player['name'],
                description=f"ID: {player['unique_id']}",
                value=str(idx)
            ) for idx, player in enumerate(banned_players)
        ]
        if not options:
            options.append(discord.SelectOption(label="Brak zbanowanych graczy", description="Brak dostępnych graczy", value="none"))
        super().__init__(placeholder="Wybierz zbanowanego gracza...", options=options)
        if not banned_players:
            self.disabled = True

    async def callback(self, interaction: Interaction):
        if self.disabled:
            await interaction.response.send_message("Brak zbanowanych graczy do wybrania.", ephemeral=True)
            return
        await interaction.response.send_message("Wybrano zbanowanego gracza", ephemeral=True)

class BannedButton(Button):
    def __init__(self):
        super().__init__(label="Zbanowani", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: Interaction):
        view: PlayersMGMenu = self.view
        view.current_page = "banned"
        view.update_components()
        await view.update_message(interaction)

class ActionButton(Button):
    def __init__(self, action: str, style: discord.ButtonStyle):
        super().__init__(label=action, style=style)
        self.action = action.lower()

    async def callback(self, interaction: Interaction):
        view: PlayersMGMenu = self.view
        player_id = view.selected_player['unique_id']
        
        try:
            if self.action == "ban":
                data = await view.cog.api_request('POST', '/player/ban', {'unique_id': player_id})
            elif self.action == "kick":
                data = await view.cog.api_request('POST', '/player/kick', {'unique_id': player_id})
            
            if data.get('succeeded'):
                confirmation = f"✅ Pomyślnie {self.action}owano gracza {view.selected_player['name']}!"
                await interaction.response.send_message(confirmation, ephemeral=True)
                await asyncio.sleep(1)
                await view.update_message(interaction)
            else:
                await interaction.response.send_message(f"❌ Błąd: {data.get('message', 'Unknown error')}", ephemeral=True)
                
        except Exception as e:
            await interaction.response.send_message(f"⚠️ Błąd systemowy: {str(e)}", ephemeral=True)

class BackButton(Button):
    def __init__(self):
        super().__init__(label="Powrót", style=discord.ButtonStyle.grey)

    async def callback(self, interaction: Interaction):
        view: PlayersMGMenu = self.view
        view.current_page = "main"
        view.update_components()
        await view.update_message(interaction)

class CancelButton(Button):
    def __init__(self):
        super().__init__(label="Anuluj", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: Interaction):
        await interaction.message.delete()

class Playersmg(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Konfiguracja z pliku .env
        self.server_ip = os.getenv("SERVER_IP")
        self.web_port = int(os.getenv("WEB_PORT"))
        self.game_slots = int(os.getenv("GAME_SLOTS"))
        self.password = quote_plus(os.getenv("WEB_API_PASSWORD"))
        self.base_url = f"http://{self.server_ip}:{self.web_port}"
        self.timeout = aiohttp.ClientTimeout(total=10)
        
        # ID kanałów z .env
        self.public_channel = int(os.getenv("PUBLIC_CHANNEL")) if os.getenv("PUBLIC_CHANNEL") else None
        self.private_channel = int(os.getenv("PRIVATE_CHANNEL")) if os.getenv("PRIVATE_CHANNEL") else None
        
        # Pobieranie roli administratora – oczekujemy ID roli
        admin_role = os.getenv("ADMIN_ROLE")
        if admin_role is None:
            raise ValueError("ADMIN_ROLE nie został ustawiony w pliku .env")
        self.admin_role = int(admin_role)

        MODERATOR_ROLE_ID = int(os.getenv("MODERATOR_ROLE"))
        if MODERATOR_ROLE_ID is None:
            raise ValueError("MODERATOR_ROLE nie został ustawiony w pliku .env")
        self.moderator_role = MODERATOR_ROLE_ID

    async def api_request(self, method, endpoint, payload=None):
        """
        Funkcja pomocnicza do komunikacji z API.
        Dołącza parametr password do każdego wywołania.
        """
        # Dodajemy parametr password do endpointu
        if '?' in endpoint:
            endpoint += f"&password={self.password}"
        else:
            endpoint += f"?password={self.password}"
            
        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.password}"}
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            if method.upper() == 'GET':
                async with session.get(url, headers=headers) as response:
                    return await response.json()
            elif method.upper() == 'POST':
                async with session.post(url, json=payload, headers=headers) as response:
                    return await response.json()
            else:
                raise ValueError("Metoda HTTP nieobsługiwana")

    @commands.command(name='chat')
    async def post_chat(self, ctx, *, message: str):
        author = ctx.author.display_name

        if ctx.channel.id != self.private_channel:
            await ctx.send("❌ Tej komendy można używać tylko na kanale prywatnym!", delete_after=10)
            return

        try:
            msg = quote(message)
            endpoint = f"/chat?message={msg}"
            data = await self.api_request('POST', endpoint)
            if data.get('succeeded'):
                await ctx.send(f"`{author}` :white_check_mark: \n```{message}```")
                await ctx.message.delete()
            else:
                await ctx.send(f":warning: Błąd API: {data.get('message', 'Nieznany błąd')}")
        except Exception as e:
            await ctx.send(f":rotating_light: Krytyczny błąd: {str(e)}")
            print(f"Błąd komendy chat: {str(e)}")
    
    @commands.command(name='kick')
    async def kick_player(self, ctx, player_id: int):
        query = urlencode({'unique_id': player_id})
        endpoint = f"/player/kick?{query}"
        data = await self.api_request('POST', endpoint)

        if data.get('succeeded'):
            await ctx.send(f"Gracz o ID {player_id} został wyrzucony")
            await ctx.message.delete()
        else:
            await ctx.send(f"Błąd: {data.get('message')}")

    @commands.command(name='ban')
    async def ban_player(self, ctx, player_id: int):
        query = urlencode({'unique_id': player_id})
        endpoint = f"/player/ban?{query}"
        data = await self.api_request('POST', endpoint)

        if data.get('succeeded'):
            await ctx.send(f"Gracz o ID {player_id} został zbanowany")
            await ctx.message.delete()
        else:
            await ctx.send(f"Błąd: {data.get('message')}")

    @commands.command(name='unban')
    async def unban_player(self, ctx, player_id: int):
        query = urlencode({'unique_id': player_id})
        endpoint = f"/player/unban?{query}"
        data = await self.api_request('POST', endpoint)

        if data.get('succeeded'):
            await ctx.send(f"Gracz o ID {player_id} został odbanowany")
            await ctx.message.delete()
        else:
            await ctx.send(f"Błąd: {data.get('message')}")

    @commands.command(name='banlist')
    async def banlist(self, ctx):
        try:
            data = await self.api_request('GET', '/player/banlist')
        except Exception as e:
            await ctx.send(f":rotating_light: Błąd podczas pobierania banlisty: {str(e)}")
            return

        banlist_data = data.get("data", {})
        if not banlist_data:
            await ctx.send("Brak zbanowanych graczy.")
            return

        embed = discord.Embed(title="Lista zbanowanych graczy", color=discord.Color.red())
        for key, player in banlist_data.items():
            name = player.get("name", "Brak nazwy")
            unique_id = player.get("unique_id", "Brak ID")
            embed.add_field(name=name, value=f"ID: {unique_id}", inline=False)

        await ctx.send(embed=embed)

@commands.command(name='playersmg')
async def players_management(self, ctx):
    """Interaktywne menu zarządzania graczami"""
    
    # Sprawdź uprawnienia
    if ctx.channel.id != self.bot.private_channel:
        await ctx.send("❌ Tej komendy można używać tylko na kanale prywatnym!", delete_after=10)
        return
    
    if not self.bot.has_role(ctx.author, self.bot.admin_role):
        await ctx.send("❌ Nie masz uprawnień do użycia tej komendy!", delete_after=10)
        return

    try:
        # Pobierz dane z API
        players_response = await self.bot.api_request('GET', '/player/list')
        banned_response = await self.bot.api_request('GET', '/player/banlist')
        
        # POPRAWKA: Prawidłowe przetwarzanie danych
        players_data = []
        banned_data = []
        
        # Przetwórz dane graczy
        if players_response.get('succeeded'):
            players_raw = players_response.get('data', {})
            if isinstance(players_raw, dict):
                players_data = list(players_raw.values())
            elif isinstance(players_raw, list):
                players_data = players_raw
        
        # Przetwórz dane zbanowanych
        if banned_response.get('succeeded'):
            banned_raw = banned_response.get('data', {})
            if isinstance(banned_raw, dict):
                banned_data = list(banned_raw.values())
            elif isinstance(banned_raw, list):
                banned_data = banned_raw

        # Debug - pokaż co otrzymaliśmy
        print(f"Players data: {players_data}")
        print(f"Banned data: {banned_data}")

        # POPRAWKA: Sprawdź czy API w ogóle odpowiada
        if not players_response.get('succeeded'):
            await ctx.send(f"❌ Błąd pobierania listy graczy: {players_response.get('message')}")
            return

        # Stwórz menu (nawet jeśli lista jest pusta - menu pokaże "brak graczy")
        view = PlayersMGMenu(
            cog=self,
            players_data=players_data,  # Teraz na pewno jest lista (może pusta)
            banned_players=banned_data  # Teraz na pewno jest lista (może pusta)
        )
        
        embed = view.create_embed()
        await ctx.send(embed=embed, view=view)
        
    except Exception as e:
        print(f"Błąd w players_management: {str(e)}")
        await ctx.send(f"⚠️ Błąd inicjalizacji menu: {str(e)}")

async def setup(bot):
    await bot.add_cog(Playersmg(bot))
    print("Playersmg cog: loaded")
