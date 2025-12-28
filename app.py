from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required,
    logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

# =========================
# APP
# =========================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')

# =========================
# DATABASE
# =========================
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///local.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# =========================
# LOGIN
# =========================
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# =========================
# MODELS
# =========================
class Shop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    currency = db.Column(db.String(10), default='USD')
    subscription_end = db.Column(db.DateTime)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'))

    @property
    def shop(self):
        return Shop.query.get(self.shop_id)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    price = db.Column(db.Float, default=0)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'))

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    balance = db.Column(db.Float, default=0)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'))

# =========================
# CREATE TABLES
# =========================
with app.app_context():
    db.create_all()

# =========================
# AUTH
# =========================
@app.route('/')
def index():
    return redirect(url_for('dashboard')) if current_user.is_authenticated else redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('بيانات الدخول غير صحيحة', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        shop = Shop(
            name=request.form['shop_name'],
            subscription_end=datetime.utcnow() + timedelta(days=14)
        )
        db.session.add(shop)
        db.session.flush()

        user = User(
            username=request.form['username'],
            password=generate_password_hash(request.form['password']),
            shop_id=shop.id
        )
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# =========================
# MAIN PAGES
# =========================
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route("/pos")
@login_required
def pos():
    products = Product.query.filter_by(shop_id=current_user.shop_id).all()

    products_data = [
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "stock": p.stock
        }
        for p in products
    ]

    return render_template("pos.html", products=products_data)


@app.route('/products')
@login_required
def products():
    products = Product.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('products.html', products=products)

@app.route('/customers', methods=['GET', 'POST'])
@login_required
def customers():
    if request.method == 'POST':
        c = Customer(
            name=request.form['name'],
            phone=request.form.get('phone'),
            shop_id=current_user.shop_id
        )
        db.session.add(c)
        db.session.commit()
        return redirect(url_for('customers'))

    customers = Customer.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('customers.html', customers=customers)

@app.route('/expenses')
@login_required
def expenses():
    return render_template('expenses.html')

@app.route('/employees')
@login_required
def employees():
    return render_template('employees.html')

@app.route('/invoices')
@login_required
def invoices():
    return render_template('invoices.html')

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/support')
@login_required
def support():
    return render_template('support.html')

# =========================
# ADMIN (placeholders)
# =========================
@app.route('/admin')
@login_required
def admin_dashboard():
    return "Admin Dashboard"

@app.route('/admin/admins')
@login_required
def manage_admins():
    return "Manage Admins"

@app.route('/admin/profile')
@login_required
def admin_profile():
    return "Admin Profile"

