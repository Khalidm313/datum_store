from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required,
    logout_user, current_user
)
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import csv
from io import StringIO

# ======================================================
# APP
# ======================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')

# ======================================================
# UPLOADS
# ======================================================
UPLOAD_FOLDER = '/tmp/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
# HELPERS
# ======================================================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ======================================================
# MODELS
# ======================================================
class Shop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    subscription_end = db.Column(db.DateTime)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='owner')
    is_admin = db.Column(db.Boolean, default=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'))

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    stock = db.Column(db.Integer, default=0)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'))

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    balance = db.Column(db.Float, default=0)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'))

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='paid')
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'))

    items = db.relationship(
        'InvoiceItem',
        backref='invoice',
        cascade='all, delete-orphan',
        lazy=True
    )

class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer, nullable=False)
    product = db.relationship('Product')

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'))

# ======================================================
# ✅ CREATE TABLES (FIX — AFTER MODELS)
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
        flash('Invalid credentials', 'error')
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
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('Registration failed', 'error')
    return render_template('register.html')

# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
@login_required
def dashboard():
    shop_id = current_user.shop_id
    today = datetime.utcnow().date()

    sales_today = db.session.query(db.func.sum(Invoice.total_amount)).filter(
        Invoice.shop_id == shop_id,
        db.func.date(Invoice.date) == today
    ).scalar() or 0

    expenses = db.session.query(db.func.sum(Expense.amount)).filter(
        Expense.shop_id == shop_id
    ).scalar() or 0

    return render_template(
        'dashboard.html',
        todays_sales=sales_today,
        expenses=expenses,
        net_profit=sales_today - expenses
    )

# ---------------- INVOICES ----------------
@app.route('/pos')
@login_required
def pos():
    return render_template('pos.html')
# ------------------------------


@app.route('/invoices')
@login_required
def invoices():
    invs = Invoice.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('invoices.html', invoices=invs)

@app.route('/invoice/refund/<int:id>')
@login_required
def refund_invoice(id):
    inv = Invoice.query.get_or_404(id)
    if inv.shop_id != current_user.shop_id:
        return redirect(url_for('invoices'))

    if inv.status != 'refunded':
        for item in inv.items:
            if item.product:
                item.product.stock += item.quantity
        inv.status = 'refunded'
        db.session.commit()

    return redirect(url_for('invoices'))

    
    @app.route('/products')
@login_required
def products():
    products = Product.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('products.html', products=products)




