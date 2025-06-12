import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class PlayerTracker:
    def __init__(self, file_path: Optional[str] = None, banned_file_path: Optional[str] = None, online_file_path: Optional[str] = None):
        if file_path is None:
            file_path = os.path.join(os.path.dirname(__file__), "playerlist.json")
        if banned_file_path is None:
            banned_file_path = os.path.join(os.path.dirname(__file__), "banned_players.json")
        if online_file_path is None:
            online_file_path = os.path.join(os.path.dirname(__file__), "online_players.json")
        self.file_path = file_path
        self.banned_file_path = banned_file_path
        self.online_file_path = online_file_path
        self.players: Dict[str, Dict] = {}
        self.banned_players: List[Dict] = []
        self.online_players: Dict[str, datetime] = {}
        self.load_players()
        self.load_banned_players()
        self.load_online_players()
    
    def load_players(self) -> None:
        """Ładuje listę graczy z pliku"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.players = json.load(f)
            except json.JSONDecodeError:
                self.players = {}
        else:
            self.players = {}
    
    def save_players(self) -> None:
        """Zapisuje listę graczy do pliku"""
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.players, f, indent=4, ensure_ascii=False)
    
    def load_banned_players(self) -> None:
        if os.path.exists(self.banned_file_path):
            try:
                with open(self.banned_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.banned_players = list(data.values())
                    elif isinstance(data, list):
                        self.banned_players = data
                    else:
                        self.banned_players = []
            except json.JSONDecodeError:
                self.banned_players = []
        else:
            self.banned_players = []
    
    def save_banned_players(self) -> None:
        # Zawsze zapisuj jako listę
        with open(self.banned_file_path, 'w', encoding='utf-8') as f:
            json.dump(self.banned_players, f, indent=4, ensure_ascii=False)
    
    def update_banned_players(self, banned_players_data: List[Dict] | Dict) -> None:
        if isinstance(banned_players_data, dict):
            self.banned_players = list(banned_players_data.values())
        elif isinstance(banned_players_data, list):
            self.banned_players = banned_players_data
        else:
            self.banned_players = []
        self.save_banned_players()
    
    def get_banned_players(self) -> List[Dict]:
        # Zawsze zwracaj listę
        if isinstance(self.banned_players, dict):
            return list(self.banned_players.values())
        return self.banned_players
    
    def load_online_players(self) -> None:
        if os.path.exists(self.online_file_path):
            try:
                with open(self.online_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.online_players = {k: datetime.fromisoformat(v) for k, v in data.items()}
            except Exception:
                self.online_players = {}
        else:
            self.online_players = {}

    def save_online_players(self) -> None:
        with open(self.online_file_path, 'w', encoding='utf-8') as f:
            json.dump({k: v.isoformat() for k, v in self.online_players.items()}, f, indent=4, ensure_ascii=False)
    
    def update_online_status(self, online_players_data: List[Dict]) -> None:
        """Aktualizuje status online graczy i ich czas gry"""
        current_time = datetime.now()
        current_online_ids = set()
        # Zapamiętaj poprzednich online
        previous_online = set(self.online_players.keys())
        for player_data in online_players_data:
            player_id = str(player_data.get('unique_id'))
            if not player_id:
                continue
            current_online_ids.add(player_id)
            player_name = player_data.get('name', 'Nieznany')
            # Jeśli gracz nie był wcześniej online (czyli dołącza)
            joined_now = player_id not in previous_online
            if player_id not in self.online_players:
                self.online_players[player_id] = current_time
                self.add_player(player_id, player_name, joined_now=joined_now)
            else:
                time_diff = (current_time - self.online_players[player_id]).total_seconds()
                if player_id in self.players:
                    self.players[player_id]["total_time"] += time_diff
                    self.players[player_id]["last_seen"] = current_time.isoformat()
                    self.players[player_id]["is_online"] = True
                self.online_players[player_id] = current_time
        # Sprawdź graczy którzy wyszli z serwera
        offline_players = set(self.online_players.keys()) - current_online_ids
        for player_id in offline_players:
            if player_id in self.players:
                last_time = (current_time - self.online_players[player_id]).total_seconds()
                self.players[player_id]["total_time"] += last_time
                self.players[player_id]["is_online"] = False
                self.players[player_id]["last_seen"] = current_time.isoformat()
            del self.online_players[player_id]
        self.save_players()
        self.save_online_players()
    
    def add_player(self, unique_id: str, name: str, joined_now: bool = False) -> None:
        """Dodaje lub aktualizuje gracza w bazie"""
        current_time = datetime.now()
        if str(unique_id) not in self.players:
            self.players[str(unique_id)] = {
                "name": name,
                "first_seen": current_time.isoformat(),
                "last_seen": current_time.isoformat(),
                "join_count": 1 if joined_now else 0,
                "total_time": 0.0,  # Czas w sekundach
                "is_online": True
            }
        else:
            self.players[str(unique_id)]["last_seen"] = current_time.isoformat()
            if joined_now:
                self.players[str(unique_id)]["join_count"] += 1
            self.players[str(unique_id)]["is_online"] = True
            if self.players[str(unique_id)]["name"] != name:
                self.players[str(unique_id)]["name"] = name
        
        self.save_players()
    
    def get_player(self, unique_id: str) -> Optional[Dict]:
        """Pobiera informacje o graczu"""
        player = self.players.get(str(unique_id))
        if player:
            # Konwertuj czas na czytelny format
            total_time = timedelta(seconds=int(player["total_time"]))
            days = total_time.days
            hours, remainder = divmod(total_time.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            player["formatted_time"] = f"{days}d {hours}h {minutes}m {seconds}s"
            
            # Dodaj informację czy jest online
            player["is_online"] = str(unique_id) in self.online_players
            
        return player
    
    def get_all_players(self) -> List[Dict]:
        """Zwraca listę wszystkich graczy"""
        players = []
        for unique_id, player_data in self.players.items():
            # Konwertuj czas na czytelny format
            total_time = timedelta(seconds=int(player_data["total_time"]))
            days = total_time.days
            hours, remainder = divmod(total_time.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            players.append({
                "unique_id": unique_id,
                "name": player_data["name"],
                "first_seen": player_data["first_seen"],
                "last_seen": player_data["last_seen"],
                "join_count": player_data["join_count"],
                "total_time": player_data["total_time"],
                "formatted_time": f"{days}d {hours}h {minutes}m {seconds}s",
                "is_online": str(unique_id) in self.online_players
            })
        return players
    
    def get_stats(self) -> Dict:
        """Zwraca statystyki graczy"""
        total_time = sum(p["total_time"] for p in self.players.values())
        total_time_delta = timedelta(seconds=int(total_time))
        days = total_time_delta.days
        hours, remainder = divmod(total_time_delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        return {
            "total_players": len(self.players),
            "total_joins": sum(p["join_count"] for p in self.players.values()),
            "players_online": len(self.online_players),
            "total_time": total_time,
            "formatted_total_time": f"{days}d {hours}h {minutes}m {seconds}s"
        }
    
    def reset_join_counts(self):
        for player in self.players.values():
            player['join_count'] = 0
        self.save_players() 