from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import json, os

auth_bp = Blueprint('auth', __name__)

USERS_DB = "users.json"

def load_users():
    if not os.path.exists(USERS_DB):
        default_users = {"admin": {"password": generate_password_hash("admin123"), "job": "Developer"}}
        with open(USERS_DB, 'w') as f:
            json.dump(default_users, f, indent=4)
        return default_users
    with open(USERS_DB, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_DB, 'w') as f:
        json.dump(users, f, indent=4)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()
        if username in users and check_password_hash(users[username]['password'], password):
            session['user'] = {'id': username, 'job': users[username]['job']}
            return redirect(url_for('main.main'))
        flash('Invalid username or password!', 'error')
    return render_template('welcome.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()
        if username in users:
            flash('Username already exists!', 'error')
        elif not username or not password:
            flash('All fields are required!', 'error')
        else:
            users[username] = {"password": generate_password_hash(password), "job": "User"}
            save_users(users)
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('auth.login'))
@auth_bp.route('/')
def welcome():
    return render_template('welcome.html')