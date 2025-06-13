import os
import sys
import signal
import argparse
import subprocess
import psutil
import time
import logging
from webpanel import create_app
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
import json
from getpass import getpass

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def get_bot_pid():
    """Odczytuje PID bota z pliku"""
    try:
        with open('bot.pid', 'r') as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None

def save_bot_pid(pid):
    """Zapisuje PID bota do pliku"""
    with open('bot.pid', 'w') as f:
        f.write(str(pid))

def is_process_running(pid):
    """Sprawdza czy proces o danym PID jest uruchomiony"""
    try:
        process = psutil.Process(pid)
        return process.is_running()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False

def kill_process_tree(pid, timeout=3):
    """Zabija proces i wszystkie jego podprocesy"""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        
        # Najpierw próbujemy zakończyć proces normalnie
        parent.terminate()
        
        # Czekamy na zakończenie procesu
        gone, alive = psutil.wait_procs([parent] + children, timeout=timeout)
        
        # Jeśli proces nadal działa, zabijamy go
        if alive:
            for p in alive:
                try:
                    p.kill()
                except psutil.NoSuchProcess:
                    pass
                    
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False

def start_bot():
    """Uruchamia bota Discord"""
    # Sprawdź czy bot nie jest już uruchomiony
    pid = get_bot_pid()
    if pid and is_process_running(pid):
        return False, "Bot jest już uruchomiony"
    
    try:
        # Uruchom bota w tle
        process = subprocess.Popen(
            [sys.executable, 'bot.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        
        # Zapisz PID do pliku
        try:
            save_bot_pid(process.pid)
        except Exception as e:
            # Jeśli nie udało się zapisać PID, zabij proces
            process.kill()
            return False, f"Nie można zapisać PID: {str(e)}"
        
        # Poczekaj chwilę i sprawdź czy proces nadal działa
        time.sleep(2)
        if not is_process_running(process.pid):
            # Jeśli proces nie działa, usuń plik PID
            try:
                os.remove('bot.pid')
            except FileNotFoundError:
                pass
            return False, "Bot nie mógł się uruchomić - sprawdź logi"
            
        logging.info("Bot został uruchomiony")
        return True, "Bot został uruchomiony"
    except Exception as e:
        # W przypadku błędu upewnij się, że plik PID zostanie usunięty
        try:
            os.remove('bot.pid')
        except FileNotFoundError:
            pass
        return False, f"Błąd podczas uruchamiania bota: {str(e)}"

def stop_bot():
    """Zatrzymuje bota Discord"""
    pid = get_bot_pid()
    if not pid:
        return False, "Bot nie jest uruchomiony"
    
    try:
        if not is_process_running(pid):
            try:
                os.remove('bot.pid')
            except FileNotFoundError:
                pass
            return False, "Bot nie jest uruchomiony"
            
        # Wyślij sygnał SIGTERM do procesu
        os.kill(pid, signal.SIGTERM)
        
        # Poczekaj na zakończenie procesu
        time.sleep(2)
        
        if is_process_running(pid):
            # Jeśli proces nadal działa, wymuś zakończenie
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)
        
        try:
            os.remove('bot.pid')
        except FileNotFoundError:
            pass
            
        logging.info("Bot został zatrzymany")
        return True, "Bot został zatrzymany"
    except ProcessLookupError:
        # Proces już nie istnieje
        try:
            os.remove('bot.pid')
        except FileNotFoundError:
            pass
        return False, "Bot nie jest uruchomiony"
    except Exception as e:
        return False, f"Błąd podczas zatrzymywania bota: {str(e)}"

def signal_handler(sig, frame):
    """Obsługa sygnału przerwania"""
    print('\nZatrzymywanie aplikacji...')
    # Zatrzymaj bota przed wyjściem
    stop_bot()
    sys.exit(0)

def ensure_admin_account():
    users_path = os.path.join('webpanel', 'users.json')
    # Wczytaj użytkowników
    if os.path.exists(users_path):
        with open(users_path, 'r', encoding='utf-8') as f:
            users = json.load(f)
    else:
        users = {}
    # Sprawdź czy jest przynajmniej jeden admin
    has_admin = any(u.get('group_id') == 'admin' for u in users.values())
    if not has_admin:
        logging.warning('Brak konta administratora! Utwórz konto admina:')
        while True:
            username = input('Podaj login admina: ').strip()
            if not username:
                logging.warning('Login nie może być pusty!')
                continue
            if any(u.get('username') == username for u in users.values()):
                logging.warning('Taki login już istnieje!')
                continue
            break
        while True:
            password = getpass('Podaj hasło admina: ')
            password2 = getpass('Powtórz hasło: ')
            if password != password2:
                logging.warning('Hasła się nie zgadzają!')
                continue
            if not password:
                logging.warning('Hasło nie może być puste!')
                continue
            break
        import uuid
        user_id = str(uuid.uuid4())
        users[user_id] = {
            'username': username,
            'password_hash': generate_password_hash(password),
            'group_id': 'admin'
        }
        with open(users_path, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        logging.info(f'Konto administratora {username} zostało utworzone!')

def main():
    # Załaduj zmienne środowiskowe
    load_dotenv()
    # Dodaj sprawdzenie admina
    ensure_admin_account()
    
    # Parsowanie argumentów
    parser = argparse.ArgumentParser(description='Panel administracyjny bota')
    parser.add_argument('--host', default=os.getenv('WEBPANEL_HOST', '127.0.0.1'), help='Host na którym uruchomić panel')
    parser.add_argument('--port', type=int, default=os.getenv('WEBPANEL_PORT', 5000), help='Port na którym uruchomić panel')
    parser.add_argument('--debug', action='store_true', help='Uruchom w trybie debug')
    
    args = parser.parse_args()
    
    # Obsługa sygnału przerwania
    signal.signal(signal.SIGINT, signal_handler)
    
    # Utwórz i uruchom aplikację
    app = create_app()
    
    try:
        print(f"Panel administracyjny uruchomiony na http://{args.host}:{args.port}")
        app.run(host=args.host, port=args.port, debug=args.debug)
    except Exception as e:
        print(f"Błąd podczas uruchamiania panelu: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main() 