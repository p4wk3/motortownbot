from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
import os
import logging
from logging.handlers import RotatingFileHandler
import secrets
from datetime import datetime
import aiohttp
import asyncio
import json

login_manager = LoginManager()
csrf = CSRFProtect()

def load_config():
    """Ładuje i waliduje konfigurację"""
    config_path = os.path.join('config', 'config.json')
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Błąd wczytywania konfiguracji: {e}")
        return {}

def load_or_create_secret_key():
    """Wczytuje lub tworzy nowy klucz sekretny"""
    secret_key_file = os.path.join('config', 'secret_key')
    
    if os.path.exists(secret_key_file):
        with open(secret_key_file, 'rb') as f:
            return f.read()
    
    # Jeśli plik nie istnieje, wygeneruj nowy klucz
    if not os.path.exists('config'):
        os.makedirs('config')
        
    secret_key = secrets.token_bytes(32)
    with open(secret_key_file, 'wb') as f:
        f.write(secret_key)
    
    return secret_key

def create_app():
    app = Flask(__name__)
    
    # Ustaw stały klucz sekretny
    app.config['SECRET_KEY'] = load_or_create_secret_key()
    
    # Konfiguracja sesji
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 godziny
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Konfiguracja logowania dla Flask
    if not app.debug:
        # Wyłącz domyślne logowanie Werkzeug
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.disabled = True
        
        # Skonfiguruj własne logowanie do pliku
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        file_handler = RotatingFileHandler(
            'logs/webpanel.log',
            maxBytes=10240,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Webpanel startup')

    # Inicjalizacja rozszerzeń
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'  # type: ignore
    login_manager.session_protection = 'strong'
    
    # Rejestracja blueprintów
    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from .routes import bp as routes_bp
    app.register_blueprint(routes_bp)

    # Resetuj join_count wszystkich graczy przy starcie
    try:
        from .playerlist import PlayerTracker
        tracker = PlayerTracker()
        tracker.reset_join_counts()
    except Exception as e:
        app.logger.error(f'Błąd resetowania join_count: {e}')

    def format_datetime(value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except Exception:
                return value
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d %H:%M:%S')
        return value
    app.jinja_env.filters['format_datetime'] = format_datetime

    return app 

async def send_discord_error(error_message, error_type="ERROR"):
    """Wysyła błąd na kanał prywatny Discorda"""
    config = load_config()
    webhook_url = f"https://discord.com/api/webhooks/{config.get('DISCORD_PRIVATE_CHANNEL_ID')}"
    
    embed = {
        "title": f"❌ {error_type}",
        "description": f"```\n{error_message}\n```",
        "color": 0xFF0000,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            await session.post(webhook_url, json={"embeds": [embed]})
        except Exception as e:
            print(f"Failed to send Discord error: {e}")

def report_critical_error(error_message):
    """Wrapper dla asynchronicznego wysyłania błędów"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(send_discord_error(error_message))
    loop.close() 