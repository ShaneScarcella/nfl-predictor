import re
from typing import Optional

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from nfl_app.extensions import db
from nfl_app.models import User

auth = Blueprint('auth', __name__, url_prefix='/auth')

_USERNAME_RE = re.compile(r'^[a-zA-Z0-9_-]{2,32}$')


def _validate_username(username: str) -> Optional[str]:
    u = (username or '').strip()
    if not _USERNAME_RE.match(u):
        return None
    return u


def _validate_password(password: str) -> Optional[str]:
    if not password or len(password) < 8:
        return None
    return password


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        username = _validate_username(request.form.get('username', ''))
        password = _validate_password(request.form.get('password', ''))
        password2 = request.form.get('password2', '')

        if not username:
            flash('Username must be 2–32 characters: letters, numbers, underscores, or hyphens.', 'error')
            return render_template('auth/register.html'), 400
        if not password:
            flash('Password must be at least 8 characters.', 'error')
            return render_template('auth/register.html'), 400
        if password != password2:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html'), 400

        if User.query.filter_by(username=username).first():
            flash('That username is already taken.', 'error')
            return render_template('auth/register.html'), 400

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('main.home'))

    return render_template('auth/register.html')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            flash('Invalid username or password.', 'error')
            return render_template('auth/login.html'), 401

        login_user(user, remember=bool(request.form.get('remember')))
        next_url = request.args.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect(url_for('main.home'))

    return render_template('auth/login.html')


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.home'))
