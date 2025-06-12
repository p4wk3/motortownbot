from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField
from .models import User, UserGroup
import os
import psutil
import time
import json
import aiohttp
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
import sys
from urllib.parse import quote_plus
import requests
import re
import uuid
from functools import wraps
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from run_admin import start_bot as admin_start_bot, stop_bot as admin_stop_bot
from .auth import admin_required
from .playerlist import PlayerTracker
import threading
from . import report_critical_error, load_config

bp = Blueprint('routes', __name__)

# Zmienne globalne
START_TIME = datetime.now()
PLAYERS_LOG_FILE = 'webpanel/playerslog.json'

player_tracker = PlayerTracker()

REFRESH_INTERVAL = 60  # sekundy

def management_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.has_permission('management'):
            flash('Nie masz uprawnień do tej sekcji.', 'error')
            return redirect(url_for('routes.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

class ConfigForm(FlaskForm):
    """Formularz konfiguracji"""
    # Discord
    DISCORD_TOKEN = PasswordField('Token Bota')
    DISCORD_CHANNEL_ID = StringField('ID Kanału Głównego')
    DISCORD_PRIVATE_CHANNEL_ID = StringField('ID Kanału Prywatnego')
    DISCORD_LOG_CHANNEL_ID = StringField('ID Kanału Logów')
    DISCORD_ADMIN_ROLE_ID = StringField('ID Roli Administratora')
    DISCORD_MOD_ROLE_ID = StringField('ID Roli Moderatora')
    DISCORD_STATUS_CHANNEL_ID = StringField('ID Kanału Statusu')
    
    # Game Server
    GAME_SERVER_HOST = StringField('Host Serwera')
    GAME_SERVER_PORT = StringField('Port Serwera')
    GAME_SERVER_RCON_PASSWORD = PasswordField('Hasło RCON')
    
    # Debug
    LOG_LEVEL = SelectField('Poziom Logowania', choices=[
        ('', 'Bez zmian'),
        ('DEBUG', 'DEBUG'),
        ('INFO', 'INFO'),
        ('WARNING', 'WARNING'),
        ('ERROR', 'ERROR'),
        ('CRITICAL', 'CRITICAL')
    ])
    DEBUG = SelectField('Tryb Debug', choices=[
        ('', 'Bez zmian'),
        ('True', 'Włączony'),
        ('False', 'Wyłączony')
    ])

def load_config():
    """Ładuje i waliduje konfigurację"""
    config_path = os.path.join('config', 'config.json')
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        current_app.logger.error(f"Błąd wczytywania konfiguracji: {e}")
        return {}

def save_config(config):
    config_path = os.path.join('config', 'config.json')
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def load_discord_cache():
    """Ładuje cache danych z Discorda"""
    cache_file = os.path.join(os.path.dirname(__file__), 'discord_cache.json')
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"text_channels": [], "roles": [], "last_update": None}
    return {"text_channels": [], "roles": [], "last_update": None}

def save_discord_cache(data):
    """Zapisuje cache danych z Discorda"""
    cache_file = os.path.join(os.path.dirname(__file__), 'discord_cache.json')
    with open(cache_file, 'w') as f:
        json.dump(data, f, indent=4)

def is_bot_running():
    """Sprawdza czy bot jest uruchomiony"""
    from run_admin import get_bot_pid, is_process_running
    pid = get_bot_pid()
    if pid:
        return is_process_running(pid)
    return False

def get_bot_status():
    """Sprawdza status bota"""
    return 'online' if is_bot_running() else 'offline'

def get_memory_usage():
    """Pobiera użycie pamięci przez proces"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    return f"{memory_info.rss / 1024 / 1024:.1f} MB"

def get_uptime():
    """Pobiera czas działania bota"""
    uptime = datetime.now() - START_TIME
    days = uptime.days
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60
    return f"{days}d {hours}h {minutes}m"

def get_server_url():
    """Tworzy URL do API serwera gry"""
    config = load_config()
    host = config.get('GAME_SERVER_HOST', '')
    port = config.get('GAME_SERVER_PORT', '')
    password = quote_plus(config.get('GAME_SERVER_RCON_PASSWORD', ''))
    return f"http://{host}:{port}", password

def get_player_data():
    """Pobiera dane o graczach bezpośrednio z serwera gry"""
    try:
        base_url, password = get_server_url()
        if not base_url or not password:
            error_msg = "Brak konfiguracji serwera gry"
            report_critical_error(error_msg)
            return 0

        # Najpierw sprawdź liczbę graczy
        count_url = f"{base_url}/player/count?password={password}"
        try:
            count_response = requests.get(count_url, timeout=5)
            count_response.raise_for_status()
        except requests.RequestException as e:
            error_msg = f"Błąd połączenia z serwerem gry: {str(e)}"
            report_critical_error(error_msg)
            return 0
        
        count_data = count_response.json()
        if not count_data.get('succeeded', False):
            error_msg = f"Błąd API serwera: {count_data.get('message', 'Unknown error')}"
            report_critical_error(error_msg)
            return 0

        player_count = count_data.get('data', {}).get('num_players', 0)
        if player_count > 0:
            # Jeśli są gracze, pobierz pełną listę
            list_url = f"{base_url}/player/list?password={password}"
            try:
                list_response = requests.get(list_url, timeout=5)
                list_response.raise_for_status()
                list_data = list_response.json()
                
                if not list_data.get('succeeded', False):
                    error_msg = f"Błąd pobierania listy graczy: {list_data.get('message', 'Unknown error')}"
                    report_critical_error(error_msg)
                    return player_count
                
                players_raw = list_data.get('data', {})
                if isinstance(players_raw, dict):
                    return len(players_raw.values())
                elif isinstance(players_raw, list):
                    return len(players_raw)
                
            except requests.RequestException as e:
                error_msg = f"Błąd pobierania listy graczy: {str(e)}"
                report_critical_error(error_msg)
                return player_count
        
        return player_count
        
    except Exception as e:
        error_msg = f"Krytyczny błąd pobierania danych o graczach: {str(e)}"
        report_critical_error(error_msg)
        return 0

def load_players_history():
    """Ładuje historię graczy z pliku"""
    try:
        if os.path.exists(PLAYERS_LOG_FILE):
            with open(PLAYERS_LOG_FILE, 'r') as f:
                return json.load(f)
        return {'history': [0] * 24, 'last_update': None}
    except Exception as e:
        current_app.logger.error(f"Błąd wczytywania historii graczy: {e}")
        return {'history': [0] * 24, 'last_update': None}

def save_players_history(count):
    """Zapisuje aktualną liczbę graczy do historii"""
    try:
        data = load_players_history()
        current_hour = datetime.now().hour
        history = data['history']
        history[current_hour] = count
        
        with open(PLAYERS_LOG_FILE, 'w') as f:
            json.dump({
                'history': history,
                'last_update': datetime.now().isoformat(),
                'current': count
            }, f, indent=2)
    except Exception as e:
        current_app.logger.error(f"Błąd zapisywania historii graczy: {e}")

def get_player_count():
    """Pobiera liczbę aktywnych graczy"""
    count = get_player_data()
    save_players_history(count)
    return count

def get_player_history():
    """Pobiera historię liczby graczy z ostatnich 24 godzin"""
    data = load_players_history()
    return data.get('history', [0] * 24)

def read_bot_logs(log_path='bot.log', max_lines=500):
    """Czyta logi bota z pliku, pokazując tylko logi z aktualnej sesji"""
    logs = []
    if not os.path.exists(log_path):
        return logs
        
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # Znajdź początek ostatniej sesji (ostatnie uruchomienie bota)
        session_start = -1
        session_markers = ["Zalogowano jako", "Połączono z API", "Bot is ready"]
        for i, line in enumerate(reversed(lines)):
            if any(marker in line for marker in session_markers):
                session_start = len(lines) - i - 1
                break
        
        # Jeśli znaleziono początek sesji, weź tylko logi od tego momentu
        if session_start >= 0:
            lines = lines[session_start:]
        
        # Ogranicz do max_lines ostatnich linii
        lines = lines[-max_lines:]
            
        for line in lines:
            # Przykładowy format: 2024-06-08 12:34:56,789 [INFO] Wiadomość
            match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) \[(\w+)\] (.*)$', line)
            if match:
                timestamp, log_type, message = match.groups()
                type_color = {
                    'INFO': 'success',
                    'WARNING': 'warning',
                    'ERROR': 'danger',
                    'CRITICAL': 'danger',
                    'DEBUG': 'secondary'
                }.get(log_type, 'info')
                logs.append({
                    'timestamp': timestamp,
                    'type': log_type,
                    'type_color': type_color,
                    'message': message.strip()  # Remove any trailing whitespace
                })
            else:
                # Handle non-standard log lines
                logs.append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3],
                    'type': 'INFO',
                    'type_color': 'info',
                    'message': line.strip()
                })
    except Exception as e:
        logs.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3],
            'type': 'ERROR',
            'type_color': 'danger',
            'message': f'Błąd czytania logów: {str(e)}'
        })
    return logs

def fetch_and_update_players():
    try:
        config = load_config()
        host = config.get('GAME_SERVER_HOST', '')
        port = config.get('GAME_SERVER_PORT', '')
        password = quote_plus(config.get('GAME_SERVER_RCON_PASSWORD', ''))
        base_url = f"http://{host}:{port}"
        # Pobierz graczy
        list_url = f"{base_url}/player/list?password={password}"
        banlist_url = f"{base_url}/player/banlist?password={password}"
        players_response = requests.get(list_url, timeout=5)
        banned_response = requests.get(banlist_url, timeout=5)
        players = []
        banned_players = []
        if players_response.ok:
            data = players_response.json().get('data', {})
            if isinstance(data, dict):
                players = list(data.values())
            elif isinstance(data, list):
                players = data
        if banned_response.ok:
            banned_players = banned_response.json().get('data', [])
        player_tracker.update_online_status(players)
        player_tracker.update_banned_players(banned_players)
    except Exception as e:
        print(f"Błąd pobierania danych graczy: {e}")
    finally:
        # Zaplanuj kolejne odświeżenie
        threading.Timer(REFRESH_INTERVAL, fetch_and_update_players).start()

# Start background taska przy starcie aplikacji
fetch_and_update_players()

@bp.route('/api/stats')
@login_required
def get_stats():
    """Endpoint API zwracający aktualne statystyki"""
    return jsonify({
        'bot_status': get_bot_status(),
        'memory_usage': get_memory_usage(),
        'uptime': get_uptime(),
        'player_count': get_player_count(),
        'player_history': get_player_history()
    })

@bp.route('/')
@login_required
def index():
    return redirect(url_for('routes.dashboard'))

@bp.route('/dashboard')
@login_required
def dashboard():
    bot_status = get_bot_status()
    memory_usage = get_memory_usage()
    uptime = get_uptime()
    player_count = get_player_count()
    player_history = get_player_history()
    logs = read_bot_logs()
    return render_template('dashboard.html',
                         bot_status=bot_status,
                         memory_usage=memory_usage,
                         uptime=uptime,
                         player_count=player_count,
                         player_history=player_history,
                         logs=logs)

@bp.route('/config', methods=['GET', 'POST'])
@login_required
def config():
    if not current_user.has_permission('bot config'):
        flash('Brak uprawnień do konfiguracji bota.', 'error')
        return redirect(url_for('routes.dashboard'))
    """Strona konfiguracji"""
    form = ConfigForm()
    
    if form.validate_on_submit():
        # Zbierz dane z formularza
        config_data = {}
        for field in form:
            if field.name != 'csrf_token' and field.data:
                config_data[field.name] = field.data
        
        try:
            save_config(config_data)
            flash('Konfiguracja została zapisana', 'success')
            return redirect(url_for('routes.config'))
        except Exception as e:
            flash(f'Błąd podczas zapisywania konfiguracji: {str(e)}', 'error')
    
    # Wczytaj aktualną konfigurację
    config = load_config()
    discord_cache = load_discord_cache()
    
    return render_template('config.html',
                         form=form,
                         config=config,
                         text_channels=discord_cache.get('text_channels', []),
                         roles=discord_cache.get('roles', []))

@bp.route('/api/bot/start')
@login_required
def api_bot_start():
    """Endpoint API do uruchamiania bota"""
    success, message = admin_start_bot()
    current_app.logger.info(f"Bot start attempt: {message}")
    return jsonify({'success': success, 'message': message})

@bp.route('/api/bot/stop')
@login_required
def api_bot_stop():
    """Endpoint API do zatrzymywania bota"""
    success, message = admin_stop_bot()
    current_app.logger.info(f"Bot stop attempt: {message}")
    return jsonify({'success': success, 'message': message})

@bp.route('/api/bot/restart')
@login_required
def api_bot_restart():
    """Endpoint API do restartowania bota"""
    success, message = admin_stop_bot()
    if success:
        time.sleep(2)  # Poczekaj na zatrzymanie bota
        success, message = admin_start_bot()
    current_app.logger.info(f"Bot restart attempt: {message}")
    return jsonify({'success': success, 'message': message})

@bp.route('/api/logs')
@login_required
def get_logs():
    """Endpoint API zwracający logi bota"""
    logs = read_bot_logs()
    return jsonify(logs)

@bp.route('/api/logs/clear', methods=['POST'])
@login_required
def clear_logs():
    log_path = 'bot.log'
    try:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.truncate(0)
        return jsonify({'success': True, 'message': 'Logi zostały wyczyszczone.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Błąd czyszczenia logów: {str(e)}'}), 500

@bp.route('/players/refresh', methods=['POST'])
@login_required
def refresh_players():
    if not current_user.has_permission('players'):
        return jsonify({'error': 'Brak uprawnień'}), 403
    try:
        fetch_and_update_players()
        return jsonify({'message': 'Odświeżono listę graczy'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/players')
@login_required
def players():
    if not current_user.has_permission('players'):
        flash('Nie masz uprawnień do tej sekcji.', 'error')
        return redirect(url_for('routes.dashboard'))
    
    players = player_tracker.get_all_players()
    stats = player_tracker.get_stats()
    banned_players = player_tracker.get_banned_players()
    banned_ids = {p.get('unique_id') for p in banned_players}
    for p in players:
        p['is_banned'] = p['unique_id'] in banned_ids
    players.sort(key=lambda x: (-x['is_online'], x['last_seen']))
    return render_template(
        'players.html',
        players=players,
        stats=stats,
        banned_players=banned_players,
        active_page='players'
    )

@bp.route('/management')
@login_required
@management_required
def management():
    groups = UserGroup.get_all_groups().values()
    users = User.get_all_users()
    return render_template('management.html', groups=groups, users=users)

@bp.route('/management/group', methods=['POST'])
@login_required
@management_required
def add_group():
    group_id = request.form.get('group_id')
    name = request.form.get('name')
    permissions = request.form.getlist('permissions')
    
    if not all([group_id, name]) or not permissions:
        flash('Wszystkie pola są wymagane.', 'error')
        return redirect(url_for('routes.management'))
    
    if not isinstance(group_id, str) or not isinstance(name, str):
        flash('Nieprawidłowe dane.', 'error')
        return redirect(url_for('routes.management'))
    
    groups = UserGroup.get_all_groups()
    if group_id in groups:
        flash('Grupa o takim ID już istnieje.', 'error')
        return redirect(url_for('routes.management'))
    
    new_group = UserGroup(
        id=group_id,
        name=name,
        permissions=permissions
    )
    groups[group_id] = new_group
    
    # Konwertuj obiekty UserGroup na słowniki przed zapisem
    groups_dict = {
        gid: {'name': g.name, 'permissions': g.permissions}
        for gid, g in groups.items()
    }
    UserGroup.save_groups(groups_dict)
    flash('Grupa została dodana.', 'success')
    return redirect(url_for('routes.management'))

@bp.route('/management/group/<group_id>', methods=['DELETE'])
@login_required
@management_required
def delete_group(group_id):
    if group_id == 'admin':
        return jsonify({'error': 'Nie można usunąć grupy systemowej'}), 400
    
    groups = UserGroup.get_all_groups()
    if group_id not in groups:
        return jsonify({'error': 'Grupa nie istnieje'}), 404
    
    # Sprawdź czy są użytkownicy w tej grupie
    users = User.load_users()
    for user_data in users.values():
        if user_data.get('group_id') == group_id:
            return jsonify({'error': 'Nie można usunąć grupy, która ma przypisanych użytkowników'}), 400
    
    del groups[group_id]
    # Konwertuj obiekty UserGroup na słowniki przed zapisem
    groups_dict = {
        gid: {'name': g.name, 'permissions': g.permissions}
        for gid, g in groups.items()
    }
    UserGroup.save_groups(groups_dict)
    return jsonify({'message': 'Grupa została usunięta'}), 200

@bp.route('/management/user', methods=['POST'])
@login_required
@management_required
def add_user():
    username = request.form.get('username')
    password = request.form.get('password')
    group_id = request.form.get('group_id')
    
    if not all([username, password, group_id]):
        flash('Wszystkie pola są wymagane.', 'error')
        return redirect(url_for('routes.management'))
    
    users = User.load_users()
    for user_data in users.values():
        if user_data['username'] == username:
            flash('Użytkownik o takim loginie już istnieje.', 'error')
            return redirect(url_for('routes.management'))
    
    # Sprawdź czy grupa istnieje
    groups = UserGroup.get_all_groups()
    if group_id not in groups:
        flash('Wybrana grupa nie istnieje.', 'error')
        return redirect(url_for('routes.management'))
    
    # Upewnij się, że password nie jest None przed użyciem generate_password_hash
    if not isinstance(password, str):
        flash('Nieprawidłowe hasło.', 'error')
        return redirect(url_for('routes.management'))
    
    user_id = str(uuid.uuid4())
    users[user_id] = {
        'username': username,
        'password_hash': generate_password_hash(password),
        'group_id': group_id
    }
    
    User.save_users(users)
    flash('Użytkownik został dodany.', 'success')
    return redirect(url_for('routes.management'))

@bp.route('/management/user/<user_id>', methods=['DELETE'])
@login_required
@management_required
def delete_user(user_id):
    if user_id == 'admin':
        return jsonify({'error': 'Nie można usunąć użytkownika systemowego'}), 400
    
    users = User.load_users()
    if user_id not in users:
        return jsonify({'error': 'Użytkownik nie istnieje'}), 404
    
    del users[user_id]
    User.save_users(users)
    return jsonify({'message': 'Użytkownik został usunięty'}), 200

@bp.route('/management/group/<group_id>/permission', methods=['POST'])
@login_required
@management_required
def add_permission(group_id):
    """Dodaje uprawnienie do grupy"""
    if group_id == 'admin':
        return jsonify({'error': 'Nie można modyfikować grupy systemowej'}), 400
    
    if not request.is_json:
        return jsonify({'error': 'Oczekiwano JSON'}), 400
    
    data = request.get_json()
    permission = data.get('permission') if data else None
    if not permission:
        return jsonify({'error': 'Nie podano uprawnienia'}), 400
    
    groups = UserGroup.get_all_groups()
    if group_id not in groups:
        return jsonify({'error': 'Grupa nie istnieje'}), 404
    
    group = groups[group_id]
    if permission in group.permissions:
        return jsonify({'error': 'Grupa już ma to uprawnienie'}), 400
    
    group.permissions.append(permission)
    
    # Konwertuj obiekty UserGroup na słowniki przed zapisem
    groups_dict = {
        gid: {'name': g.name, 'permissions': g.permissions}
        for gid, g in groups.items()
    }
    UserGroup.save_groups(groups_dict)
    return jsonify({'message': 'Uprawnienie zostało dodane'}), 200

@bp.route('/management/group/<group_id>/permission/<permission>', methods=['DELETE'])
@login_required
@management_required
def remove_permission(group_id, permission):
    """Usuwa uprawnienie z grupy"""
    if group_id == 'admin':
        return jsonify({'error': 'Nie można modyfikować grupy systemowej'}), 400
    
    groups = UserGroup.get_all_groups()
    if group_id not in groups:
        return jsonify({'error': 'Grupa nie istnieje'}), 404
    
    group = groups[group_id]
    if permission not in group.permissions:
        return jsonify({'error': 'Grupa nie ma tego uprawnienia'}), 400
    
    group.permissions.remove(permission)
    
    # Konwertuj obiekty UserGroup na słowniki przed zapisem
    groups_dict = {
        gid: {'name': g.name, 'permissions': g.permissions}
        for gid, g in groups.items()
    }
    UserGroup.save_groups(groups_dict)
    return jsonify({'message': 'Uprawnienie zostało usunięte'}), 200

@bp.route('/management/user/<user_id>/group', methods=['POST'])
@login_required
@management_required
def set_user_group(user_id):
    """Ustawia grupę użytkownika"""
    if user_id == 'admin':
        return jsonify({'error': 'Nie można modyfikować użytkownika systemowego'}), 400
    
    if not request.is_json:
        return jsonify({'error': 'Oczekiwano JSON'}), 400
    
    data = request.get_json()
    group_id = data.get('group_id') if data else None
    if not group_id:
        return jsonify({'error': 'Nie podano ID grupy'}), 400
    
    users = User.load_users()
    if user_id not in users:
        return jsonify({'error': 'Użytkownik nie istnieje'}), 404
    
    groups = UserGroup.get_all_groups()
    if group_id not in groups:
        return jsonify({'error': 'Grupa nie istnieje'}), 404
    
    users[user_id]['group_id'] = group_id
    User.save_users(users)
    return jsonify({'message': 'Grupa została przypisana'}), 200

@bp.route('/management/user/<user_id>/group', methods=['DELETE'])
@login_required
@management_required
def remove_user_group(user_id):
    """Usuwa grupę użytkownika"""
    if user_id == 'admin':
        return jsonify({'error': 'Nie można modyfikować użytkownika systemowego'}), 400
    
    users = User.load_users()
    if user_id not in users:
        return jsonify({'error': 'Użytkownik nie istnieje'}), 404
    
    if 'group_id' not in users[user_id]:
        return jsonify({'error': 'Użytkownik nie ma przypisanej grupy'}), 400
    
    del users[user_id]['group_id']
    User.save_users(users)
    return jsonify({'message': 'Grupa została usunięta'}), 200

@bp.route('/players/reset_joins', methods=['POST'])
@login_required
def reset_joins():
    if not (hasattr(current_user, 'group') and getattr(current_user.group, 'id', None) == 'admin'):
        return jsonify({'error': 'Brak uprawnień'}), 403
    player_tracker.reset_join_counts()
    return jsonify({'message': 'join_count wszystkich graczy został zresetowany!'}), 200

@bp.route('/dc_status')
@login_required
def dc_status():
    if not current_user.has_permission('dc_status'):
        flash('Brak uprawnień do tej sekcji.', 'error')
        return redirect(url_for('routes.dashboard'))
    
    # Sprawdź czy bot jest uruchomiony
    if not is_bot_running():
        flash('Aby uzyskać dostęp do DC Status, najpierw uruchom bota.', 'warning')
        return redirect(url_for('routes.dashboard'))
    
    # Wczytaj aktualny embed z pliku konfiguracyjnego
    embed_path = os.path.join(os.path.dirname(__file__), 'dc_status.json')
    
    # Pobierz dane o graczach
    config = load_config()
    base_url, password = get_server_url()
    count = get_player_count()
    players = player_tracker.get_all_players()
    online_players = [p for p in players if p['is_online']]
    
    # Sprawdź ping serwera
    try:
        start_time = time.time()
        requests.get(f"{base_url}/player/count?password={password}", timeout=5)
        ping = int((time.time() - start_time) * 1000)  # Konwersja na ms
        ping_icon = "🟢" if ping < 100 else "🟡" if ping < 200 else "🔴"
    except:
        ping = 0
        ping_icon = "⚫"
    
    # Generuj listę graczy
    if online_players:
        player_list = "\n".join([f"• {p['name']}" for p in sorted(online_players, key=lambda x: x['name'])])
    else:
        player_list = "Brak aktywnych graczy"
    
    # Stwórz embed
    embed_data = {
        "title": "📊 Status Serwera",
        "description": f"**Gracze online ({len(online_players)}):**\n{player_list}\n\n**Ping:**\n{ping_icon} {ping}ms\n\n**Status:**\n✅ Online ({len(online_players)})",
        "color": "#5865F2",
        "footer": f"Ostatnia aktualizacja • {datetime.now().strftime('%d.%m.%Y, %H:%M:%S')}"
    }
    
    # Wczytaj poprzednie message_id jeśli istnieje
    try:
        with open(embed_path, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
            embed_data['message_id'] = old_data.get('message_id')
    except:
        pass
    
    # Zapisz embed
    with open(embed_path, 'w', encoding='utf-8') as f:
        json.dump(embed_data, f, indent=2, ensure_ascii=False)
    
    # Pobierz datę ostatniej aktualizacji
    last_update = datetime.fromtimestamp(os.path.getmtime(embed_path)).strftime('%d.%m.%Y, %H:%M:%S')
    
    return render_template('dc_status.html', embed=embed_data, last_update=last_update, active_page='dc_status')

@bp.route('/motortown.png')
def serve_favicon():
    """Serwuje plik favicon.ico z katalogu głównego"""
    return send_from_directory(os.path.dirname(os.path.dirname(__file__)), 'motortown.png')

@bp.route('/api/dc_status/toggle', methods=['POST'])
@login_required
def toggle_dc_status():
    if not current_user.has_permission('dc_status'):
        return jsonify({'error': 'Brak uprawnień'}), 403
    
    try:
        # Wywołaj komendę bota przez API
        base_url, password = get_server_url()
        response = requests.post(f"{base_url}/bot/command", json={
            'command': 'toggle_status_update',
            'password': password
        }, timeout=5)
        
        if response.ok:
            data = response.json()
            return jsonify({
                'enabled': data.get('enabled', True),
                'message': 'Status auto-update został zaktualizowany!'
            })
        return jsonify({'error': 'Nie udało się zmienić statusu auto-update'}), 500
        
    except Exception as e:
        current_app.logger.error(f"Błąd podczas przełączania auto-update: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/dc_status/refresh', methods=['POST'])
@login_required
def refresh_dc_status():
    if not current_user.has_permission('dc_status'):
        return jsonify({'error': 'Brak uprawnień'}), 403
    
    try:
        # Wywołaj komendę bota przez API
        base_url, password = get_server_url()
        response = requests.post(f"{base_url}/bot/command", json={
            'command': 'status',
            'password': password
        }, timeout=5)
        
        if response.ok:
            return jsonify({'message': 'Status został odświeżony!'})
        return jsonify({'error': 'Nie udało się odświeżyć statusu'}), 500
        
    except Exception as e:
        current_app.logger.error(f"Błąd podczas odświeżania statusu: {str(e)}")
        return jsonify({'error': str(e)}), 500 