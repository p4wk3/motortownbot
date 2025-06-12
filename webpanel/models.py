from flask_login import UserMixin
import json
import os
from typing import List, Dict, Optional
import shutil
from datetime import datetime

class UserGroup:
    """Model grupy użytkowników"""
    GROUPS_FILE = os.path.join(os.path.dirname(__file__), "user_groups.json")
    # Przenieś plik z katalogu głównego jeśli istnieje
    if os.path.exists("user_groups.json") and not os.path.exists(GROUPS_FILE):
        shutil.move("user_groups.json", GROUPS_FILE)
    
    def __init__(self, id: str, name: str, permissions: List[str]):
        self.id = id
        self.name = name
        self.permissions = permissions
    
    @staticmethod
    def get_all_groups() -> Dict[str, 'UserGroup']:
        """Pobiera wszystkie grupy"""
        if not os.path.exists(UserGroup.GROUPS_FILE):
            # Stwórz domyślną grupę admin
            default_groups = {
                "admin": {
                    "name": "Administrator",
                    "permissions": ["*", "dc_status"]  # Wszystkie uprawnienia + DC Status
                },
                "moderator": {
                    "name": "Moderator",
                    "permissions": ["dashboard", "players", "logs"]
                }
            }
            with open(UserGroup.GROUPS_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_groups, f, indent=4, ensure_ascii=False)
        
        with open(UserGroup.GROUPS_FILE, 'r', encoding='utf-8') as f:
            groups_data = json.load(f)
            
        return {
            group_id: UserGroup(
                id=group_id,
                name=data['name'],
                permissions=data['permissions']
            )
            for group_id, data in groups_data.items()
        }
    
    @staticmethod
    def get_group(group_id: str) -> Optional['UserGroup']:
        """Pobiera grupę po ID"""
        groups = UserGroup.get_all_groups()
        return groups.get(group_id)
    
    @staticmethod
    def save_groups(groups: Dict[str, Dict]) -> None:
        """Zapisuje grupy do pliku"""
        with open(UserGroup.GROUPS_FILE, 'w', encoding='utf-8') as f:
            json.dump(groups, f, indent=4, ensure_ascii=False)
    
    def has_permission(self, permission: str) -> bool:
        """Sprawdza czy grupa ma dane uprawnienie"""
        return "*" in self.permissions or permission in self.permissions

class User(UserMixin):
    """Model użytkownika dla Flask-Login"""
    USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")
    # Przenieś plik z katalogu głównego jeśli istnieje
    if os.path.exists("users.json") and not os.path.exists(USERS_FILE):
        shutil.move("users.json", USERS_FILE)
    
    def __init__(self, id: str, username: str, password_hash: str, group_id: str = "admin"):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.group_id = group_id
        self._group = None
    
    @property
    def group(self) -> Optional[UserGroup]:
        """Pobiera grupę użytkownika"""
        if self._group is None:
            self._group = UserGroup.get_group(self.group_id)
        return self._group
    
    def has_permission(self, permission: str) -> bool:
        """Sprawdza czy użytkownik ma dane uprawnienie"""
        if not self.group:
            return False
        return self.group.has_permission(permission)
    
    @staticmethod
    def get(user_id: str) -> Optional['User']:
        """Pobiera użytkownika na podstawie ID"""
        users = User.load_users()
        user_data = users.get(user_id)
        if user_data:
            return User(
                id=user_id,
                username=user_data['username'],
                password_hash=user_data['password_hash'],
                group_id=user_data.get('group_id', 'admin')
            )
        return None
    
    @staticmethod
    def get_by_username(username: str) -> Optional['User']:
        """Pobiera użytkownika na podstawie nazwy użytkownika"""
        users = User.load_users()
        for user_id, user_data in users.items():
            if user_data['username'] == username:
                return User(
                    id=user_id,
                    username=username,
                    password_hash=user_data['password_hash'],
                    group_id=user_data.get('group_id', 'admin')
                )
        return None
    
    @staticmethod
    def load_users() -> Dict:
        """Ładuje użytkowników z pliku"""
        if not os.path.exists(User.USERS_FILE):
            return {}
        try:
            with open(User.USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    @staticmethod
    def save_users(users: Dict) -> None:
        """Zapisuje użytkowników do pliku"""
        with open(User.USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
    
    @staticmethod
    def get_all_users() -> List['User']:
        """Pobiera wszystkich użytkowników"""
        users = User.load_users()
        return [
            User(
                id=user_id,
                username=data['username'],
                password_hash=data['password_hash'],
                group_id=data.get('group_id', 'admin')
            )
            for user_id, data in users.items()
        ]

class PlayerTracker:
    def __init__(self, file_path: Optional[str] = None):
        if file_path is None:
            file_path = os.path.join(os.path.dirname(__file__), "playerlist.json")
        self.file_path = file_path
        self.players: Dict[str, Dict] = {}
        self.online_players: Dict[str, datetime] = {}  # Śledzi czas ostatniego sprawdzenia online
        self.load_players()
    
    def load_players(self):
        # Implementacja metody load_players
        pass

    def save_players(self):
        # Implementacja metody save_players
        pass 