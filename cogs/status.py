import discord
from discord.ext import commands, tasks
import time
from datetime import datetime
from webpanel.playerlist import PlayerTracker
import logging
import json
import os
import asyncio

logger = logging.getLogger(__name__)

class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_status = None
        self.last_players = set()  # Zbiór ID graczy z ostatniego sprawdzenia
        self.player_tracker = PlayerTracker()
        self.status_message = None  # Przechowuje ostatnią wiadomość statusu
        self.status_channel = None  # Przechowuje kanał statusu
        self.auto_update_enabled = True  # Flaga kontrolująca automatyczne aktualizacje
        
        # Startuj taski
        self.update_status.start()
        self.check_status.start()
        self.update_status_embed.start()

    def cog_unload(self):
        self.update_status.cancel()
        self.check_status.cancel()
        self.update_status_embed.cancel()

    @tasks.loop(seconds=30)
    async def check_status(self):
        """Sprawdza zmiany statusu serwera i wysyła powiadomienia"""
        try:
            if not self.bot.public_channel:
                return
                
            channel = self.bot.get_channel(self.bot.public_channel)
            if not channel:
                print(f"Nie znaleziono kanału {self.bot.public_channel}")
                return
                
            previous_status = self.last_status
            current_status = await self._update_presence()
            
            # Sprawdź nowych graczy
            if current_status:
                await self._check_new_players()
            
            # Wyślij powiadomienie tylko przy zmianie statusu
            if previous_status is not None and previous_status != current_status:
                await self._send_status_notification(channel, current_status)
                # Loguj zmianę statusu
                await self._log_status_change(current_status)
            
            self.last_status = current_status

        except Exception as e:
            logger.error(f"Błąd sprawdzania statusu: {str(e)}")

    async def _check_new_players(self):
        """Sprawdza i śledzi nowych graczy"""
        try:
            list_data = await self.bot.api_request('GET', '/player/list')
            if not list_data.get('succeeded'):
                return
                
            players_raw = list_data.get('data', {})
            
            # Konwertuj dane graczy do listy
            players = []
            if isinstance(players_raw, dict):
                players = list(players_raw.values())
            elif isinstance(players_raw, list):
                players = players_raw
            
            # Aktualizuj status online i czas gry
            self.player_tracker.update_online_status(players)
            
        except Exception as e:
            logger.error(f"Błąd sprawdzania nowych graczy: {str(e)}")

    async def _send_status_notification(self, channel, status):
        """Wysyła powiadomienie o zmianie statusu"""
        status_msg = "🟢 **Serwer uruchomiony!**" if status else "🔴 **Serwer wyłączony!**"
        embed = discord.Embed(
            description=status_msg,
            color=discord.Color.green() if status else discord.Color.red()
        )
        embed.set_footer(text=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        try:
            await channel.send(embed=embed)
        except discord.HTTPException as e:
            logger.error(f"Nie można wysłać powiadomienia: {str(e)}")

    async def _log_status_change(self, new_status):
        """Loguje zmianę statusu serwera"""
        try:
            status_text = "ONLINE" if new_status else "OFFLINE"
            await self.bot.log_admin_action(
                None,
                "Zmiana Statusu",
                f"Serwer {status_text}",
                success=True
            )
        except Exception as e:
            logger.error(f"Błąd logowania zmiany statusu: {str(e)}")

    @tasks.loop(minutes=1)
    async def update_status(self):
        """Aktualizuje status bota co minutę"""
        try:
            await self._update_presence()
        except Exception as e:
            logger.error(f"Status update error: {str(e)}")

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
            logger.error(f"Błąd aktualizacji statusu: {str(e)}")
            await self.bot.change_presence(activity=discord.Activity(
                name="Serwer OFFLINE 🔴",
                type=discord.ActivityType.watching
            ))
            return False
    
    @commands.command(name='status')
    async def status_command(self, ctx):
        """Aktualizuje status serwera"""
        try:
            # Usuń wiadomość użytkownika
            await ctx.message.delete()
            
            if not self.status_channel:
                config = self.bot.config
                channel_id = config.get('DISCORD_STATUS_CHANNEL_ID')
                if not channel_id:
                    return
                self.status_channel = self.bot.get_channel(int(channel_id))
                if not self.status_channel:
                    return
            
            # Usuń wszystkie wiadomości na kanale statusu
            try:
                messages = []
                async for message in self.status_channel.history(limit=None):
                    messages.append(message)
                if messages:
                    await self.status_channel.delete_messages(messages)
            except discord.errors.HTTPException:
                # Jeśli bulk delete się nie powiedzie, usuń pojedynczo
                for message in messages:
                    try:
                        await message.delete()
                    except discord.errors.NotFound:
                        continue
            
            # Wygeneruj i wyślij nowy embed
            embed = await self._generate_status_embed()
            if embed:
                await self.status_channel.send(embed=embed)
                
        except Exception as e:
            self.bot.logger.error(f"Błąd w komendzie status: {str(e)}")
            await ctx.send("❌ Wystąpił błąd podczas aktualizacji statusu.", delete_after=5)

    @commands.command(name='players')
    async def players_command(self, ctx):
        """Pokazuje listę wszystkich graczy, którzy kiedykolwiek dołączyli do serwera"""
        # Sprawdź uprawnienia
        if not any(role.id in [int(self.bot.config.get('DISCORD_ADMIN_ROLE_ID', 0)), 
                              int(self.bot.config.get('DISCORD_MOD_ROLE_ID', 0))] 
                  for role in ctx.author.roles):
            await ctx.send("❌ Nie masz uprawnień do użycia tej komendy!", delete_after=5)
            return

        players = self.player_tracker.get_all_players()
        
        if not players:
            await ctx.send("❌ Brak danych o graczach.")
            return
        
        # Sortuj graczy po statusie (online pierwsi) i dacie ostatniego widzenia
        players.sort(key=lambda x: (-x['is_online'], x['last_seen']), reverse=True)
        
        # Utwórz embed z paginacją
        pages = []
        items_per_page = 10
        
        for i in range(0, len(players), items_per_page):
            page_players = players[i:i + items_per_page]
            embed = discord.Embed(
                title="📋 Lista Wszystkich Graczy",
                description=f"Strona {len(pages) + 1}/{(len(players) + items_per_page - 1) // items_per_page}",
                color=discord.Color.blue()
            )
            
            for player in page_players:
                last_seen = datetime.fromisoformat(player['last_seen']).strftime('%Y-%m-%d %H:%M:%S')
                status = "🟢 Online" if player['is_online'] else "⚫ Offline"
                embed.add_field(
                    name=f"👤 {player['name']} ({status})",
                    value=f"ID: `{player['unique_id']}`\n"
                          f"Dołączeń: `{player['join_count']}`\n"
                          f"Czas gry: `{player['formatted_time']}`\n"
                          f"Ostatnio: `{last_seen}`",
                    inline=False
                )
            
            pages.append(embed)
        
        if pages:
            await ctx.send(embed=pages[0])  # Na razie wysyłamy tylko pierwszą stronę
            await ctx.send("Paginacja nie jest jeszcze zaimplementowana.")

    @tasks.loop(minutes=1)
    async def update_status_embed(self):
        """Aktualizuje embed statusu co minutę"""
        try:
            # Jeśli auto-update jest wyłączony, nie rób nic
            if not self.auto_update_enabled:
                return
                
            if not self.status_channel:
                config = self.bot.config
                channel_id = config.get('DISCORD_STATUS_CHANNEL_ID')
                if not channel_id:
                    return
                self.status_channel = self.bot.get_channel(int(channel_id))
                if not self.status_channel:
                    return

            # Usuń wszystkie wiadomości na kanale
            try:
                messages = []
                async for message in self.status_channel.history(limit=None):
                    messages.append(message)
                if messages:
                    await self.status_channel.delete_messages(messages)
            except discord.HTTPException as e:
                # Jeśli bulk delete się nie powiedzie, spróbuj usuwać pojedynczo
                try:
                    for message in messages:
                        try:
                            await message.delete()
                        except discord.HTTPException:
                            continue
                except Exception as e:
                    logger.error(f"Błąd podczas usuwania wiadomości: {str(e)}")

            # Wyślij nowy embed
            embed = await self._generate_status_embed()
            if embed:
                self.status_message = await self.status_channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Błąd aktualizacji embeda statusu: {str(e)}")

    @update_status_embed.before_loop
    async def before_update_status_embed(self):
        await self.bot.wait_until_ready()

    async def _generate_status_embed(self):
        """Generuje embed statusu"""
        try:
            start_time = time.monotonic()
            count_data = await self.bot.api_request('GET', '/player/count')
            is_online = count_data.get('succeeded', False)
            
            # Jeśli serwer jest offline
            if not is_online:
                embed = discord.Embed(
                    title="📊 Status Serwera",
                    description="```diff\n- Serwer jest aktualnie niedostępny```",
                    color=discord.Color.dark_red()
                )
                embed.set_footer(text=f"Ostatnia aktualizacja • {datetime.now().strftime('%d.%m.%Y, %H:%M:%S')}")
                return embed

            # Pobierz ping i listę graczy
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
            
            # Generuj listę graczy
            if players:
                player_list = "\n".join([f"• {p.get('name', 'Nieznany gracz')}" for p in sorted(players, key=lambda x: x.get('name', ''))])
            else:
                player_list = "Brak aktywnych graczy"

            # Ustal ikonę pingu
            ping_icon = "🟢" if ping < 100 else "🟡" if ping < 200 else "🔴"
            
            # Stwórz embed
            embed = discord.Embed(
                title="📊 Status Serwera",
                description=f"**Gracze online ({len(players)}):**\n{player_list}\n\n**Ping:**\n{ping_icon} {ping}ms\n\n**Status:**\n✅ Online ({len(players)})",
                color=discord.Color.blurple()
            )
            embed.set_footer(text=f"Ostatnia aktualizacja • {datetime.now().strftime('%d.%m.%Y, %H:%M:%S')}")
            
            return embed
            
        except Exception as e:
            logger.error(f"Błąd generowania embeda statusu: {str(e)}")
            return None

    @commands.command(name='toggle_status_update')
    async def toggle_status_update(self, ctx):
        """Włącza/wyłącza automatyczne aktualizacje statusu"""
        # Sprawdź uprawnienia
        if not any(role.id in [int(self.bot.config.get('DISCORD_ADMIN_ROLE_ID', 0)), 
                              int(self.bot.config.get('DISCORD_MOD_ROLE_ID', 0))] 
                  for role in ctx.author.roles):
            await ctx.send("❌ Nie masz uprawnień do użycia tej komendy!", delete_after=5)
            return
            
        self.auto_update_enabled = not self.auto_update_enabled
        status = "włączone" if self.auto_update_enabled else "wyłączone"
        
        embed = discord.Embed(
            description=f"✅ Automatyczne aktualizacje statusu zostały {status}!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Status(bot))
    print("✅ Status cog: loaded")