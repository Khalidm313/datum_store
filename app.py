from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required,
    logout_user, current_user
)
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import os

# ======================================================
# APP
# ======================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')

# ======================================================
# DATABASE
# ======================================================
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///local.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ======================================================
# LOGIN
# ======================================================
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ======================================================
# MODELS
# ======================================================
class Shop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    subscription_end = db.Column(db.DateTime)

    # ⭐ هذا السطر هو الحل للمشكلة
    users = db.relationship('User', backref='shop', lazy=True)
    products = db.relationship('Product', backref='shop', lazy=True)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'))


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    barcode = db.Column(db.String(100))
    category = db.Column(db.String(50))
    buy_price = db.Column(db.Float, default=0)
    sell_price = db.Column(db.Float, default=0)
    stock = db.Column(db.Integer, default=0)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'))


class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'))


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'))

# ======================================================
# CREATE TABLES
# ======================================================
with app.app_context():
    db.create_all()

# ======================================================
# ROUTES
# ======================================================
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('بيانات الدخول غير صحيحة', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            shop = Shop(
                name=request.form.get('shop_name'),
                subscription_end=datetime.utcnow() + timedelta(days=14)
            )
            db.session.add(shop)
            db.session.flush()

            user = User(
                username=request.form.get('username'),
                password=generate_password_hash(request.form.get('password')),
                shop_id=shop.id
            )
            db.session.add(user)
            db.session.commit()

            flash('تم إنشاء الحساب بنجاح', 'success')
            return redirect(url_for('login'))
        except Exception:
            db.session.rollback()
            flash('حدث خطأ أثناء التسجيل', 'error')

    return render_template('register.html')

# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
@login_required
def dashboard():
    sales = db.session.query(db.func.sum(Invoice.total_amount))\
        .filter_by(shop_id=current_user.shop_id).scalar() or 0

    expenses = db.session.query(db.func.sum(Expense.amount))\
        .filter_by(shop_id=current_user.shop_id).scalar() or 0

    return render_template(
        'dashboard.html',
        todays_sales=sales,
        expenses=expenses,
        net_profit=sales - expenses
    )

# ---------------- POS ----------------
@app.route('/pos')
@login_required
def pos():
    products = Product.query.filter_by(
        shop_id=current_user.shop_id
    ).all()

    products_data = [
        {
            "id": p.id,
            "name": p.name,
            "barcode": p.barcode,
            "price": p.sell_price,
            "stock": p.stock
        }
        for p in products
    ]

    return render_template(
        'pos.html',
        products=products_data
    )


# ---------------- PRODUCTS ----------------
@app.route('/products', methods=['GET', 'POST'])
@login_required
def products():
    if request.method == 'POST':
        product = Product(
            name=request.form['name'],
            barcode=request.form.get('barcode'),
            category=request.form.get('category'),
            buy_price=request.form.get('buy_price') or 0,
            sell_price=request.form.get('sell_price') or 0,
            stock=request.form.get('stock') or 0,
            shop_id=current_user.shop_id
        )
        db.session.add(product)
        db.session.commit()
        flash('تم إضافة المنتج بنجاح', 'success')
        return redirect(url_for('products'))

    products = Product.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('products.html', products=products)

# ---------------- INVOICES ----------------
@app.route('/invoices')
@login_required
def invoices():
    return render_template('invoices.html')

# ---------------- PLACEHOLDER ROUTES ----------------
@app.route('/customers')
@login_required
def customers():
    return "Customers page"

@app.route('/expenses')
@login_required
def expenses():
    return "Expenses page"

@app.route('/employees')
@login_required
def employees():
    return "Employees page"

@app.route('/settings')
@login_required
def settings():
    return "Settings page"

@app.route('/support')
@login_required
def support():
    return "Support page"

