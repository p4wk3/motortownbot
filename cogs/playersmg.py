import discord
import asyncio
from discord.ext import commands
from discord.ui import View, Button, Select
from discord import Interaction, ui
from typing import List, Dict, Optional, Union, TYPE_CHECKING
from urllib.parse import quote
from urllib.parse import urlencode
import logging

if TYPE_CHECKING:
    from .playersmg import Playersmg

class PlayersMGMenu(View):
    def __init__(self, cog, players_data: List[Dict], banned_players: Optional[List[Dict]] = None):
        super().__init__(timeout=180)
        self.cog = cog
        self.players = players_data or []
        self.banned_players = banned_players or []
        self.selected_player: Optional[Dict] = None
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
            if self.selected_player:  # Dodaj przyciski tylko jeśli gracz jest wybrany
                self.add_item(ActionButton("Ban", self.cog))
                self.add_item(ActionButton("Kick", self.cog))
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
                    name=f"👤 {player.get('name', 'Nieznany')}",
                    value=f"ID: `{player.get('unique_id', 'N/A')}`",
                    inline=False
                )
        else:
            embed.description = "Brak dostępnych graczy."
        return embed

    def create_player_embed(self):
        if not self.selected_player:
            return discord.Embed(
                title="⚠️ Błąd",
                description="Nie wybrano gracza",
                color=discord.Color.red()
            )
            
        embed = discord.Embed(
            title=f"⚙️ Zarządzanie: {self.selected_player.get('name', 'Nieznany')}",
            color=discord.Color.orange()
        )
        embed.add_field(name="ID Gracza", value=f"`{self.selected_player.get('unique_id', 'N/A')}`")
        return embed

    def create_banned_embed(self):
        embed = discord.Embed(
            title="🚫 Zbanowani Gracze",
            color=discord.Color.red()
        )
        if self.banned_players:
            for player in self.banned_players:
                embed.add_field(
                    name=f"⛔ {player.get('name', 'Nieznany')}",
                    value=f"ID: `{player.get('unique_id', 'N/A')}`",
                    inline=False
                )
        else:
            embed.description = "Brak zbanowanych graczy."
        return embed

class PlayerSelect(Select):
    def __init__(self, players: List[Dict]):
        options = []
        
        # Sprawdź czy players nie jest None i czy ma elementy
        if players and isinstance(players, list):
            options = [
                discord.SelectOption(
                    label=player.get('name', 'Nieznany gracz'),
                    description=f"ID: {player.get('unique_id', 'N/A')}",
                    value=str(idx)
                ) for idx, player in enumerate(players)
                if isinstance(player, dict)
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
        options = []
        if banned_players:
            options = [
                discord.SelectOption(
                    label=player.get('name', 'Nieznany gracz'),
                    description=f"ID: {player.get('unique_id', 'N/A')}",
                    value=str(idx)
                ) for idx, player in enumerate(banned_players)
                if isinstance(player, dict)
            ]
        
        if not options:
            options.append(discord.SelectOption(
                label="Brak zbanowanych graczy", 
                description="Brak dostępnych graczy", 
                value="none"
            ))
        
        super().__init__(placeholder="Wybierz zbanowanego gracza...", options=options)
        if not banned_players:
            self.disabled = True

    async def callback(self, interaction: Interaction):
        if self.disabled or self.values[0] == "none":
            await interaction.response.send_message("Brak zbanowanych graczy do wybrania.", ephemeral=True)
            return
        
        view: PlayersMGMenu = self.view
        try:
            player_index = int(self.values[0])
            view.selected_player = view.banned_players[player_index]
            
            # Dodaj przycisk unban
            view.clear_items()
            view.add_item(ActionButton("Unban", view.cog))
            view.add_item(BackButton())
            
            await view.update_message(interaction)
            
        except (ValueError, IndexError):
            await interaction.response.send_message("❌ Błąd wyboru gracza.", ephemeral=True)

class BannedButton(Button):
    def __init__(self):
        super().__init__(label="Zbanowani", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: Interaction):
        view: PlayersMGMenu = self.view
        view.current_page = "banned"
        view.update_components()
        await view.update_message(interaction)

class ActionButton(Button):
    def __init__(self, action: str, cog: 'Playersmg', **kwargs):
        style = discord.ButtonStyle.danger if action.lower() == 'ban' else discord.ButtonStyle.secondary
        super().__init__(label=action, style=style, **kwargs)
        self.action = action.lower()
        self.cog = cog
        
    async def callback(self, interaction: Interaction):
        """Obsługa kliknięcia przycisku"""
        view: PlayersMGMenu = self.view
        if not view.selected_player:
            await interaction.response.send_message("❌ Nie wybrano gracza.", ephemeral=True)
            return
            
        try:
            player_id = view.selected_player.get('unique_id')
            player_name = view.selected_player.get('name', 'Nieznany')
            
            if not player_id:
                await interaction.response.send_message("❌ Błąd: Brak ID gracza.", ephemeral=True)
                return
            
            # Wykonaj akcję
            if self.action == 'kick':
                data = await self.cog.bot.api_request('POST', '/player/kick', {'unique_id': player_id})
            elif self.action == 'ban':
                data = await self.cog.bot.api_request('POST', '/player/ban', {'unique_id': player_id})
            elif self.action == 'unban':
                data = await self.cog.bot.api_request('POST', '/player/unban', {'unique_id': player_id})
            else:
                raise ValueError(f"Nieznana akcja: {self.action}")
                
            # Przygotuj wiadomość o wyniku
            if data.get('succeeded'):
                success_msg = f"✅ Pomyślnie wykonano akcję {self.action} na graczu {player_name} (ID: {player_id})"
                try:
                    await interaction.response.send_message(success_msg, ephemeral=True)
                except discord.errors.InteractionResponded:
                    await interaction.followup.send(success_msg, ephemeral=True)
                
                # Loguj akcję
                await self.cog.bot.log_admin_action(
                    interaction,
                    self.action.title(),
                    f"Gracz: {player_name} (ID: {player_id})",
                    success=True
                )
                
                # Odśwież listę graczy po akcji
                if self.action in ['kick', 'ban']:
                    players_data = await self.cog.bot.api_request('GET', '/player/list')
                    if players_data.get('succeeded'):
                        players_raw = players_data.get('data', {})
                        if isinstance(players_raw, dict):
                            view.players = list(players_raw.values())
                        elif isinstance(players_raw, list):
                            view.players = players_raw
                            
                # Odśwież listę zbanowanych po akcji
                if self.action in ['ban', 'unban']:
                    banned_data = await self.cog.bot.api_request('GET', '/player/banlist')
                    if banned_data.get('succeeded'):
                        view.banned_players = banned_data.get('data', [])
                
                # Wróć do głównego menu
                view.current_page = "main"
                view.selected_player = None
                view.update_components()
                await view.update_message(interaction)
                
            else:
                error_msg = f"❌ Błąd: {data.get('message', 'Unknown error')}"
                try:
                    await interaction.response.send_message(error_msg, ephemeral=True)
                except discord.errors.InteractionResponded:
                    await interaction.followup.send(error_msg, ephemeral=True)
                
                # Loguj błąd
                await self.cog.bot.log_admin_action(
                    interaction,
                    self.action.title(),
                    f"Gracz: {player_name} (ID: {player_id})",
                    reason=data.get('message', 'Unknown error'),
                    success=False
                )
                
        except Exception as e:
            error_msg = f"⚠️ Błąd systemowy: {str(e)}"
            try:
                await interaction.response.send_message(error_msg, ephemeral=True)
            except discord.errors.InteractionResponded:
                await interaction.followup.send(error_msg, ephemeral=True)
            
            # Loguj błąd
            await self.cog.bot.log_admin_action(
                interaction,
                self.action.title(),
                f"Gracz: {player_name} (ID: {player_id})",
                reason=str(e),
                success=False
            )
            
        # Aktualizuj widok
        if isinstance(self.view, PlayersMGMenu):
            try:
                await self.view.update_message(interaction)
            except Exception as e:
                logging.error(f"Błąd aktualizacji widoku: {str(e)}")
        else:
            logging.error("Nie można zaktualizować widoku - nieprawidłowy typ widoku")

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
        try:
            if interaction.message:
                await interaction.message.delete()
            else:
                await interaction.response.send_message(
                    "❌ Nie można znaleźć wiadomości do usunięcia.",
                    ephemeral=True
                )
        except discord.errors.NotFound:
            # Wiadomość już została usunięta
            pass
        except discord.errors.Forbidden:
            # Bot nie ma uprawnień do usunięcia wiadomości
            await interaction.response.send_message(
                "❌ Nie mam uprawnień do usunięcia tej wiadomości.",
                ephemeral=True
            )
        except Exception as e:
            # Inny błąd
            await interaction.response.send_message(
                f"❌ Nie można usunąć wiadomości: {str(e)}",
                ephemeral=True
            )

class Playersmg(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Używamy konfiguracji z głównego bota
        # Usuwamy duplikację kodu API

    @commands.command(name='chat')
    async def post_chat(self, ctx, *, message: str):
        """Wysyła wiadomość na czat w grze"""
        author = ctx.author.display_name

        if ctx.channel.id != self.bot.private_channel:
            await ctx.send("❌ Tej komendy można używać tylko na kanale prywatnym!", delete_after=10)
            return

        try:
            data = await self.bot.api_request(
                'POST',
                '/chat/send',
                {'message': f"[Discord] {author}: {message}"}
            )
            
            if data.get('succeeded'):
                await ctx.message.add_reaction('✅')
                # Loguj wysłanie wiadomości
                await self.bot.log_admin_action(
                    ctx,
                    "Chat",
                    f"Wysłano wiadomość: {message}",
                    success=True
                )
            else:
                await ctx.message.add_reaction('❌')
                await ctx.send(f"Błąd: {data.get('message', 'Unknown error')}", delete_after=10)
                # Loguj błąd
                await self.bot.log_admin_action(
                    ctx,
                    "Chat",
                    f"Błąd wysyłania wiadomości: {message}",
                    reason=data.get('message', 'Unknown error'),
                    success=False
                )
                
        except Exception as e:
            await ctx.message.add_reaction('❌')
            await ctx.send(f"Błąd: {str(e)}", delete_after=10)
            # Loguj błąd
            await self.bot.log_admin_action(
                ctx,
                "Chat",
                f"Błąd wysyłania wiadomości: {message}",
                reason=str(e),
                success=False
            )
    
    @commands.command(name='kick')
    async def kick_player(self, ctx, player_id: int):
        """Wyrzuca gracza z serwera"""
        if not self.bot.has_role(ctx.author, self.bot.moderator_role) and not self.bot.has_role(ctx.author, self.bot.admin_role):
            await ctx.send("❌ Nie masz uprawnień do tej komendy!", delete_after=10)
            return
            
        try:
            data = await self.bot.api_request('POST', '/player/kick', {'unique_id': player_id})
            
            if data.get('succeeded'):
                await ctx.send(f"✅ Pomyślnie wyrzucono gracza o ID: {player_id}")
                # Loguj akcję
                await self.bot.log_admin_action(
                    ctx,
                    "Kick",
                    f"Gracz ID: {player_id}",
                    success=True
                )
            else:
                await ctx.send(f"❌ Błąd: {data.get('message', 'Unknown error')}")
                # Loguj błąd
                await self.bot.log_admin_action(
                    ctx,
                    "Kick",
                    f"Gracz ID: {player_id}",
                    reason=data.get('message', 'Unknown error'),
                    success=False
                )
                
        except Exception as e:
            await ctx.send(f"⚠️ Błąd: {str(e)}")
            # Loguj błąd
            await self.bot.log_admin_action(
                ctx,
                "Kick",
                f"Gracz ID: {player_id}",
                reason=str(e),
                success=False
            )

    @commands.command(name='ban')
    async def ban_player(self, ctx, player_id: int):
        """Banuje gracza na serwerze"""
        if not self.bot.has_role(ctx.author, self.bot.moderator_role) and not self.bot.has_role(ctx.author, self.bot.admin_role):
            await ctx.send("❌ Nie masz uprawnień do tej komendy!", delete_after=10)
            return
            
        try:
            data = await self.bot.api_request('POST', '/player/ban', {'unique_id': player_id})
            
            if data.get('succeeded'):
                await ctx.send(f"✅ Pomyślnie zbanowano gracza o ID: {player_id}")
                # Loguj akcję
                await self.bot.log_admin_action(
                    ctx,
                    "Ban",
                    f"Gracz ID: {player_id}",
                    success=True
                )
            else:
                await ctx.send(f"❌ Błąd: {data.get('message', 'Unknown error')}")
                # Loguj błąd
                await self.bot.log_admin_action(
                    ctx,
                    "Ban",
                    f"Gracz ID: {player_id}",
                    reason=data.get('message', 'Unknown error'),
                    success=False
                )
                
        except Exception as e:
            await ctx.send(f"⚠️ Błąd: {str(e)}")
            # Loguj błąd
            await self.bot.log_admin_action(
                ctx,
                "Ban",
                f"Gracz ID: {player_id}",
                reason=str(e),
                success=False
            )

    @commands.command(name='unban')
    async def unban_player(self, ctx, player_id: int):
        """Odbanowuje gracza na serwerze"""
        if not self.bot.has_role(ctx.author, self.bot.moderator_role) and not self.bot.has_role(ctx.author, self.bot.admin_role):
            await ctx.send("❌ Nie masz uprawnień do tej komendy!", delete_after=10)
            return
            
        try:
            data = await self.bot.api_request('POST', '/player/unban', {'unique_id': player_id})
            
            if data.get('succeeded'):
                await ctx.send(f"✅ Pomyślnie odbanowano gracza o ID: {player_id}")
                # Loguj akcję
                await self.bot.log_admin_action(
                    ctx,
                    "Unban",
                    f"Gracz ID: {player_id}",
                    success=True
                )
            else:
                await ctx.send(f"❌ Błąd: {data.get('message', 'Unknown error')}")
                # Loguj błąd
                await self.bot.log_admin_action(
                    ctx,
                    "Unban",
                    f"Gracz ID: {player_id}",
                    reason=data.get('message', 'Unknown error'),
                    success=False
                )
                
        except Exception as e:
            await ctx.send(f"⚠️ Błąd: {str(e)}")
            # Loguj błąd
            await self.bot.log_admin_action(
                ctx,
                "Unban",
                f"Gracz ID: {player_id}",
                reason=str(e),
                success=False
            )

    @commands.command(name='banlist')
    async def banlist(self, ctx):
        """Wyświetla listę zbanowanych graczy"""
        if not self.bot.has_role(ctx.author, self.bot.moderator_role) and not self.bot.has_role(ctx.author, self.bot.admin_role):
            await ctx.send("❌ Nie masz uprawnień do tej komendy!", delete_after=10)
            return
            
        try:
            data = await self.bot.api_request('GET', '/player/banlist')
            
            if not data.get('succeeded'):
                await ctx.send(f"❌ Błąd: {data.get('message', 'Unknown error')}")
                return
                
            banned_players = data.get('data', [])
            
            if not banned_players:
                embed = self.bot.create_embed(
                    ctx,
                    title="📋 Lista Zbanowanych Graczy",
                    description="```diff\n- Brak zbanowanych graczy\n```"
                )
                await ctx.send(embed=embed)
                return
                
            # Utwórz embed z listą zbanowanych graczy
            embed = self.bot.create_embed(
                ctx,
                title="📋 Lista Zbanowanych Graczy",
                description=f"Liczba zbanowanych graczy: {len(banned_players)}"
            )
            
            for player in banned_players:
                embed.add_field(
                    name=f"🚫 {player.get('name', 'Nieznany')}",
                    value=f"ID: `{player.get('unique_id', 'N/A')}`",
                    inline=False
                )
                
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"⚠️ Błąd: {str(e)}")

    @commands.command(name='playersmg')
    async def players_management(self, ctx):
        """Panel zarządzania graczami"""
        if not self.bot.has_role(ctx.author, self.bot.moderator_role) and not self.bot.has_role(ctx.author, self.bot.admin_role):
            await ctx.send("❌ Nie masz uprawnień do tej komendy!", delete_after=10)
            return
            
        try:
            # Pobierz listę graczy
            players_data = await self.bot.api_request('GET', '/player/list')
            banned_data = await self.bot.api_request('GET', '/player/banlist')
            
            if not players_data.get('succeeded'):
                await ctx.send(f"❌ Błąd pobierania listy graczy: {players_data.get('message', 'Unknown error')}")
                return
                
            players = []
            players_raw = players_data.get('data', {})
            
            if isinstance(players_raw, dict):
                players = list(players_raw.values())
            elif isinstance(players_raw, list):
                players = players_raw
                
            banned_players = banned_data.get('data', []) if banned_data.get('succeeded') else []
            
            view = PlayersMGMenu(self, players, banned_players)
            embed = view.create_embed()
            
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            await ctx.send(f"⚠️ Błąd: {str(e)}")

async def setup(bot):
    await bot.add_cog(Playersmg(bot))
    print("✅ Playersmg cog: loaded")