from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
from . import login_manager
from functools import wraps
import bcrypt
from .models import User as DBUser, UserGroup

load_dotenv()

bp = Blueprint('auth', __name__)

@login_manager.user_loader
def load_user(user_id):
    return DBUser.get(user_id)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username') or ''
        password = request.form.get('password') or ''
        user = DBUser.get_by_username(username)
        if user and user.password_hash and check_password_hash(user.password_hash, password):
            if not user.group:
                flash('Twoja grupa nie istnieje. Skontaktuj się z administratorem.', 'error')
                current_app.logger.warning(f'Logowanie nieudane: brak grupy dla użytkownika {username}')
                return render_template('login.html')
            login_user(user)
            current_app.logger.info(f'Logowanie udane: {username}')
            return redirect(url_for('routes.dashboard'))
        flash('Nieprawidłowa nazwa użytkownika lub hasło')
        current_app.logger.warning(f'Logowanie nieudane: {username}')
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

def admin_required(f):
    """Dekorator sprawdzający czy użytkownik jest adminem"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.id != 'admin':
            flash('Nie masz uprawnień do tej strony.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function 