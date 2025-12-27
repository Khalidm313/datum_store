from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required,
    logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

# -------------------------
# APP CONFIG
# -------------------------

app = Flask(__name__)
app.config['SECRET_KEY'] = 'CHANGE-THIS-SECRET-KEY'

# -------------------------
# DATABASE CONFIG (Render + Local)
# -------------------------

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# -------------------------
# LOGIN MANAGER
# -------------------------

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

# -------------------------
# MODELS
# -------------------------

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------------
# INIT DATABASE (Flask 3 SAFE)
# -------------------------

with app.app_context():
    db.create_all()

    if not User.query.filter_by(username="admin").first():
        admin_pass = generate_password_hash("admin123", method="scrypt")
        admin = User(
            username="admin",
            password=admin_pass,
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin user created")

# -------------------------
# ROUTES
# -------------------------

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))

        hashed = generate_password_hash(password, method='scrypt')
        user = User(username=username, password=hashed)

        db.session.add(user)
        db.session.commit()

        flash('Account created successfully', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))

        flash('Invalid credentials', 'danger')

    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))
