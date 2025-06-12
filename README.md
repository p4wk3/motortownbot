# MotorTownBot

System zarządzania serwerem gry MotorTown składający się z dwóch głównych komponentów: bota Discord oraz panelu administracyjnego.

## 🔧 Komponenty

### 1. Bot Discord (bot.py)
Bot Discord służący do zarządzania serwerem gry bezpośrednio z poziomu Discorda.

#### Główne funkcje:
- Monitorowanie statusu serwera
- Zarządzanie graczami (kick, ban, unban)
- Komunikacja z czatem w grze
- System komend moderacyjnych
- Śledzenie liczby graczy
- Automatyczne logowanie akcji administracyjnych

<details>
<summary>🔍 Szczegóły techniczne bota</summary>

#### Architektura bota
- Wykorzystuje bibliotekę `discord.py` z rozszerzonym systemem komend (`commands.Bot`)
- Implementuje własny system pomocy (`MyHelpCommand`)
- Asynchroniczne przetwarzanie żądań API (`aiohttp`)
- System rotacji logów z wykorzystaniem `RotatingFileHandler`

#### Kluczowe komponenty
```python
class MotorTownBot(commands.Bot):
    # Inicjalizacja z niestandardowymi intencjami Discord
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    
    # System cache'owania danych graczy
    player_history = [0] * 24  # Historia 24h
    player_data_file = "webpanel/player_data.json"
```

#### API Serwera
- Komunikacja przez REST API
- Endpointy:
  - `/player/count` - liczba graczy
  - `/player/list` - lista graczy
  - `/player/kick` - wyrzucanie graczy
  - `/player/ban` - banowanie graczy
  - `/player/unban` - odbanowywanie graczy

#### System uprawnień
- Weryfikacja ról Discord
- Hierarchiczny system komend
- Automatyczne logowanie akcji administracyjnych
</details>

#### Komendy:
##### Komendy publiczne:
- `!status` - Sprawdza status serwera i listę graczy online
- `!help` - Wyświetla listę dostępnych komend

##### Komendy dla moderatorów/adminów:
- `!playersmg` - Interaktywny panel zarządzania graczami
- `!players` - Wyświetla szczegółową listę graczy
- `!kick <id>` - Wyrzuca gracza z serwera
- `!ban <id>` - Banuje gracza
- `!unban <id>` - Odbanowuje gracza
- `!banlist` - Wyświetla listę zbanowanych graczy
- `!chat <wiadomość>` - Wysyła wiadomość na czat w grze

### 2. Panel Administracyjny (webpanel/)
Webowy panel administracyjny do zarządzania serwerem i botem.

<details>
<summary>🔍 Szczegóły techniczne panelu</summary>

#### Architektura aplikacji Flask
```python
# Struktura Blueprint
webpanel/
├── __init__.py      # Inicjalizacja aplikacji Flask
├── auth.py          # System autentykacji
├── models.py        # Modele danych
├── routes.py        # Endpointy aplikacji
├── playerlist.py    # Zarządzanie graczami
└── templates/       # Szablony Jinja2
```

#### System autentykacji
- Wykorzystuje `flask_login` dla zarządzania sesjami
- Implementacja `UserMixin` dla modelu użytkownika
- Bezpieczne hashowanie haseł
- System grup uprawnień z dziedziczeniem

#### Baza danych i przechowywanie
- Pliki JSON jako lekka baza danych
  - `users.json` - dane użytkowników
  - `user_groups.json` - grupy i uprawnienia
  - `playerslog.json` - historia graczy
  - `discord_cache.json` - cache danych z Discorda

#### Middleware i zabezpieczenia
```python
# Przykład dekoratora uprawnień
@login_required
@management_required
def protected_route():
    pass
```

#### System szablonów
- Jinja2 z własnym systemem makr
- Responsywny design z Bootstrap
- Dynamiczne ładowanie danych przez AJAX
</details>

#### Główne funkcje:
- Dashboard z statystykami serwera
- Zarządzanie konfiguracją bota i serwera
- System uprawnień (administratorzy, moderatorzy)
- Monitoring liczby graczy
- Przeglądanie logów
- Zarządzanie użytkownikami i grupami

#### Struktura panelu:
- `/dashboard` - Główny panel z statystykami
- `/config` - Konfiguracja bota i serwera
- `/players` - Zarządzanie graczami
- `/management` - Zarządzanie użytkownikami i uprawnieniami

## 📦 Wymagania
- Python 3.8+
- Flask
- discord.py
- Pozostałe zależności w pliku `requirements.txt`

<details>
<summary>🔍 Szczegóły techniczne zależności</summary>

#### Główne zależności
```plaintext
# Discord
discord.py>=2.0.0
aiohttp>=3.8.0

# Web Panel
Flask>=2.0.0
Flask-Login>=0.6.0
Flask-WTF>=1.0.0
Werkzeug>=2.0.0

# Bezpieczeństwo
cryptography>=3.4.0
PyJWT>=2.0.0

# Narzędzia
python-dotenv>=0.19.0
psutil>=5.8.0
```

#### Wersjonowanie i kompatybilność
- Python 3.8+ wymagany ze względu na:
  - Typowanie (typing.TypedDict)
  - Asynchroniczne funkcje (async/await)
  - f-strings
  - Dataclasses

#### Opcjonalne zależności
- `uvicorn` lub `gunicorn` dla produkcyjnego serwera WSGI
- `redis` dla opcjonalnego cachowania
- `pytest` dla testów jednostkowych
</details>

## 🚀 Instalacja

1. Sklonuj repozytorium:
```bash
git clone https://github.com/p4wk3/motortownbot
```

2. Utwórz i aktywuj wirtualne środowisko:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# lub
.venv\Scripts\activate  # Windows
```

3. Zainstaluj zależności:
```bash
pip install -r requirements.txt
```

4. Skonfiguruj plik `config/config.json`:
```json
{
    "DISCORD_TOKEN": "",
    "DISCORD_CHANNEL_ID": "id_kanału_głównego",
    "DISCORD_PRIVATE_CHANNEL_ID": "id_kanału_prywatnego",
    "DISCORD_LOG_CHANNEL_ID": "id_kanału_logów",
    "DISCORD_ADMIN_ROLE_ID": "id_roli_admina",
    "DISCORD_MOD_ROLE_ID": "id_roli_moderatora",
    "GAME_SERVER_HOST": "adres_ip_serwera",
    "GAME_SERVER_PORT": "port_serwera",
    "GAME_SERVER_RCON_PASSWORD": ""
}
```

5. Utwórz plik `.env` w katalogu głównym projektu i dodaj do niego:
```env
DISCORD_TOKEN=twoj_token_bota
GAME_SERVER_RCON_PASSWORD=twoje_haslo_rcon
```

<details>
<summary>🔍 Szczegóły techniczne konfiguracji</summary>

#### Struktura konfiguracji
```plaintext
config/
├── config.json     # Główna konfiguracja
├── secret_key      # Klucz szyfrowania sesji
└── .env           # Zmienne środowiskowe (opcjonalne)
```

#### Walidacja konfiguracji
```python
def validate_config(config: dict) -> bool:
    required_fields = [
        'DISCORD_TOKEN',
        'GAME_SERVER_HOST',
        'GAME_SERVER_PORT',
        'GAME_SERVER_RCON_PASSWORD'
    ]
    return all(field in config for field in required_fields)
```

#### Zmienne środowiskowe
Alternatywnie można użyć zmiennych środowiskowych:
```bash
export DISCORD_TOKEN="token_bota"
export GAME_SERVER_HOST="adres_ip_serwera"
# itd.
```

#### Bezpieczeństwo konfiguracji
- Automatyczna generacja klucza sesji
- Walidacja typów i wartości
- Szyfrowanie wrażliwych danych
</details>

## 🎮 Uruchomienie

### Bot Discord:
```bash
python bot.py
```

### Panel Administracyjny:
```bash
python run_admin.py
```

<details>
<summary>🔍 Szczegóły techniczne uruchamiania</summary>

#### Tryby uruchomienia
```bash
# Tryb deweloperski
export FLASK_ENV=development
export FLASK_DEBUG=1
python run_admin.py

# Tryb produkcyjny
export FLASK_ENV=production
gunicorn -w 4 -b 0.0.0.0:5000 "webpanel:create_app()"
```

#### Monitorowanie procesów
```python
def is_bot_running():
    pid = get_bot_pid()
    return psutil.pid_exists(pid) if pid else False
```

#### Automatyczny restart
```bash
# Przykład użycia supervisord
[program:motortown_bot]
command=/path/to/venv/bin/python bot.py
directory=/path/to/project
autostart=true
autorestart=true
```

#### Logowanie zdarzeń
- Rotacja logów co 1MB
- Maksymalnie 5 plików backupu
- Osobne logi dla bota i panelu
</details>

## 🔐 Bezpieczeństwo
- Panel webowy wykorzystuje system logowania i autoryzacji
- Wszystkie hasła są hashowane
- Implementacja CSRF protection
- Bezpieczne sesje z odpowiednimi flagami (HTTPOnly, Secure, SameSite)
- Rotacja logów dla zachowania historii

<details>
<summary>🔍 Szczegóły techniczne bezpieczeństwa</summary>

#### Hashowanie haseł
```python
from werkzeug.security import generate_password_hash, check_password_hash

def set_password(self, password: str) -> None:
    self.password_hash = generate_password_hash(
        password,
        method='pbkdf2:sha256:260000'
    )
```

#### Zabezpieczenia sesji
```python
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=1)
)
```

#### CSRF Protection
```python
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect()
csrf.init_app(app)
```

#### Rate Limiting
```python
from flask_limiter import Limiter
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
```

#### Bezpieczne nagłówki
```python
from flask_talisman import Talisman
Talisman(app, 
    content_security_policy={
        'default-src': "'self'",
        'script-src': "'self' 'unsafe-inline'"
    }
)
```
</details>

## 📝 Logi
- Logi bota: `bot.log`
- Logi panelu: `logs/webpanel.log`
- Historia graczy: `webpanel/playerslog.json`

<details>
<summary>🔍 Szczegóły techniczne logowania</summary>

#### Konfiguracja logowania
```python
# Rotacja logów
log_handler = logging.handlers.RotatingFileHandler(
    'bot.log',
    maxBytes=1024 * 1024,  # 1MB
    backupCount=5,
    encoding='utf-8'
)

# Format logów
log_format = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s'
)
```

#### Struktura plików logów
```plaintext
logs/
├── bot.log
├── bot.log.1
├── webpanel.log
└── webpanel.log.1
```

#### Przykład wpisu w logu
```log
2024-03-14 12:34:56 [INFO] Bot started successfully
2024-03-14 12:35:01 [INFO] Player joined: PlayerID=123
2024-03-14 12:35:15 [WARNING] Failed login attempt from IP: 1.2.3.4
```

#### Analiza logów
- Automatyczne parsowanie logów
- Wykrywanie anomalii
- Statystyki użycia
</details>

## 👥 Role i uprawnienia
- Administrator: Pełny dostęp do wszystkich funkcji
- Moderator: Dostęp do podstawowych funkcji zarządzania serwerem
- Użytkownik: Podstawowy dostęp do panelu (tylko podgląd)

<details>
<summary>🔍 Szczegóły techniczne uprawnień</summary>

#### System uprawnień
```python
class UserGroup:
    def __init__(self, id: str, name: str, permissions: List[str]):
        self.id = id
        self.name = name
        self.permissions = permissions
    
    def has_permission(self, permission: str) -> bool:
        return "*" in self.permissions or permission in self.permissions
```

#### Dekoratory uprawnień
```python
def management_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.has_permission('management'):
            flash('Brak uprawnień', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function
```

#### Hierarchia uprawnień
```json
{
    "admin": {
        "name": "Administrator",
        "permissions": ["*"]
    },
    "moderator": {
        "name": "Moderator",
        "permissions": ["dashboard", "players", "logs"]
    },
    "user": {
        "name": "Użytkownik",
        "permissions": ["dashboard"]
    }
}
```

#### Dziedziczenie uprawnień
- System kaskadowych uprawnień
- Możliwość nadpisywania uprawnień
- Dynamiczne przydzielanie ról
</details> 