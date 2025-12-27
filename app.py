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
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "datum-secret-key-2025")

# -------------------------
# DATABASE CONFIG
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
# MODELS
# -------------------------
class Shop(db.Model):
    __tablename__ = "shops"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, default="متجري")
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    shop = db.relationship('Shop', backref='owner', uselist=False)

# -------------------------
# LOGIN MANAGER
# -------------------------
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------------
# INIT DATABASE
# -------------------------
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        admin_pass = generate_password_hash("admin123", method="scrypt")
        admin = User(username="admin", password=admin_pass, is_admin=True)
        db.session.add(admin)
        db.session.commit()
        
        admin_shop = Shop(name="Datum Admin Shop", user_id=admin.id)
        db.session.add(admin_shop)
        db.session.commit()

# -------------------------
# AUTH & DASHBOARD
# -------------------------
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('خطأ في اسم المستخدم أو كلمة المرور', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Pass empty lists to avoid the JSON chart error you saw earlier
    return render_template('dashboard.html', user=current_user, chart_labels=[], chart_data=[])

# -------------------------
# ADMIN ROUTES (Matching your files)
# -------------------------
@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    return render_template('admin.html', users=User.query.all())

@app.route('/manage_admins')
@login_required
def manage_admins():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    return render_template('admin_users.html')

@app.route('/admin_profile')
@login_required
def admin_profile():
    return render_template('admin_profile.html')

# -------------------------
# STORE ROUTES (Matching your files)
# -------------------------
@app.route('/pos')
@login_required
def pos(): return render_template('pos.html')

@app.route('/products')
@login_required
def products(): return render_template('products.html')

@app.route('/customers')
@login_required
def customers(): return render_template('customers.html')

@app.route('/expenses')
@login_required
def expenses(): return render_template('expenses.html')

@app.route('/employees')
@login_required
def employees(): return render_template('employees.html')

@app.route('/invoices')
@login_required
def invoices(): return render_template('invoices.html')

@app.route('/settings')
@login_required
def settings(): return render_template('settings.html')

@app.route('/support')
@login_required
def support(): return render_template('support.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)
