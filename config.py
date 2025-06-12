import os
import json
import logging
from dotenv import load_dotenv
from typing import Dict, Any

logger = logging.getLogger(__name__)

def _validate_port(port_str):
    """Walidacja portu serwera"""
    try:
        port = int(port_str)
        if 1 <= port <= 65535:
            return port
        raise ValueError(f"Port musi być między 1 a 65535, otrzymano {port}")
    except (ValueError, TypeError):
        raise ValueError(f"Nieprawidłowy numer portu: {port_str}")

def get_config() -> Dict[str, Any]:
    """
    Ładuje konfigurację z pliku config.json i nadpisuje ją 
    zmiennymi środowiskowymi z pliku .env.
    """
    # Załaduj zmienne z .env do środowiska.
    # Tworzymy ścieżkę absolutną, aby uniknąć problemów z CWD.
    # Zakładamy, że config.py jest w głównym katalogu projektu.
    project_dir = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(project_dir, '.env')
    
    if os.path.exists(dotenv_path):
        # Użyj override=True, aby upewnić się, że .env ma priorytet nad zmiennymi systemowymi
        load_dotenv(dotenv_path=dotenv_path, override=True)
        logger.info(f"Wczytano i nadpisano zmienne z pliku .env: {dotenv_path}")
    else:
        logger.warning(f"Nie znaleziono pliku .env w {dotenv_path}. Używane będą tylko istniejące zmienne środowiskowe.")

    # Wczytaj bazową konfigurację z pliku JSON
    config_path = os.path.join(project_dir, 'config', 'config.json')
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Błąd parsowania pliku config.json: {e}")
            raise
    
    # === Od teraz sekrety MUSZĄ pochodzić ze środowiska ===
    config['DISCORD_TOKEN'] = os.getenv('DISCORD_TOKEN')
    config['GAME_SERVER_RCON_PASSWORD'] = os.getenv('GAME_SERVER_RCON_PASSWORD')
    
    # Walidacja i konwersja
    required_fields = [
        'DISCORD_TOKEN', 'GAME_SERVER_HOST', 'GAME_SERVER_PORT', 
        'GAME_SERVER_RCON_PASSWORD'
    ]
    missing_fields = [field for field in required_fields if not config.get(field)]
    if missing_fields:
        raise ValueError(f"Brakujące pola w konfiguracji: {', '.join(missing_fields)}")

    id_fields = [
        'DISCORD_CHANNEL_ID', 'DISCORD_PRIVATE_CHANNEL_ID', 'DISCORD_LOG_CHANNEL_ID',
        'DISCORD_ADMIN_ROLE_ID', 'DISCORD_MOD_ROLE_ID', 'DISCORD_STATUS_CHANNEL_ID'
    ]
    for field in id_fields:
        if field in config and config[field]:
            try:
                config[field] = int(config[field])
            except (ValueError, TypeError):
                logger.warning(f"Nieprawidłowa wartość dla {field}: {config[field]}. Ustawiono na 0.")
                config[field] = 0

    if 'GAME_SERVER_PORT' in config:
        config['GAME_SERVER_PORT'] = _validate_port(config['GAME_SERVER_PORT'])
        
    logger.info("Final configuration loaded.")
    # Log sensitive values partially
    token = config.get('DISCORD_TOKEN', '')
    rcon_pass = config.get('GAME_SERVER_RCON_PASSWORD', '')
    logger.info(f"Discord Token Loaded: {'Yes' if token else 'No'} (ends with ...{token[-4:] if token else 'N/A'})")
    logger.info(f"RCON Password Loaded: {'Yes' if rcon_pass else 'No'}")
    
    return config

# Inicjalizuj konfigurację raz przy starcie
try:
    CONFIG = get_config()
    logger.info("Konfiguracja wczytana pomyślnie")
except Exception as e:
    logger.critical(f"Krytyczny błąd wczytywania konfiguracji: {e}")
    # W przypadku błędu ładowania, utwórz pusty słownik, aby uniknąć dalszych błędów importu
    CONFIG = {} 