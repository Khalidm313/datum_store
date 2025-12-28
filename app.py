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
    name = db.Column(db.String(100))
    currency = db.Column(db.String(10), default='USD')
    subscription_end = db.Column(db.DateTime)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'))
    shop = db.relationship('Shop')

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    barcode = db.Column(db.String(100))
    category = db.Column(db.String(50))
    buy_price = db.Column(db.Float, default=0)
    sell_price = db.Column(db.Float, default=0)
    stock = db.Column(db.Integer, default=0)
    tax = db.Column(db.Float, default=0)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'))

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    balance = db.Column(db.Float, default=0)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'))

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='unpaid')
    total_amount = db.Column(db.Float, default=0)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'))
    customer = db.relationship('Customer', backref='invoices')

class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer, default=1)
    product = db.relationship('Product')

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
    return redirect(url_for('dashboard')) if current_user.is_authenticated else redirect(url_for('login'))

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('بيانات الدخول غير صحيحة')
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

# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
@login_required
def dashboard():
    sales = db.session.query(db.func.sum(Invoice.total_amount))\
        .filter_by(shop_id=current_user.shop_id).scalar() or 0
    return render_template('dashboard.html', sales=sales)

# ---------------- POS ----------------
@app.route('/pos')
@login_required
def pos():
    return render_template('pos.html')

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
            tax=request.form.get('tax') or 0,
            shop_id=current_user.shop_id
        )
        db.session.add(product)
        db.session.commit()
        return redirect(url_for('products'))

    products = Product.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('products.html', products=products)

@app.route('/products/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    product = Product.query.filter_by(id=id, shop_id=current_user.shop_id).first_or_404()
    if request.method == 'POST':
        product.name = request.form['name']
        product.barcode = request.form.get('barcode')
        product.category = request.form.get('category')
        product.buy_price = request.form.get('buy_price') or 0
        product.sell_price = request.form.get('sell_price') or 0
        product.stock = request.form.get('stock') or 0
        product.tax = request.form.get('tax') or 0
        db.session.commit()
        return redirect(url_for('products'))
    return render_template('edit_product.html', product=product)

# ---------------- CUSTOMERS ----------------
@app.route('/customers', methods=['GET', 'POST'])
@login_required
def customers():
    if request.method == 'POST':
        customer = Customer(
            name=request.form['name'],
            phone=request.form.get('phone'),
            shop_id=current_user.shop_id
        )
        db.session.add(customer)
        db.session.commit()
        return redirect(url_for('customers'))

    customers = Customer.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('customers.html', customers=customers)

@app.route('/customers/<int:id>')
@login_required
def customer_details(id):
    customer = Customer.query.filter_by(id=id, shop_id=current_user.shop_id).first_or_404()
    invoices = Invoice.query.filter_by(customer_id=id, shop_id=current_user.shop_id).all()
    return render_template('customer_details.html', customer=customer, invoices=invoices)

# ---------------- PLACEHOLDER ROUTES (مهم جداً) ----------------
@app.route('/expenses')
@login_required
def expenses():
    return render_template('expenses.html') if os.path.exists('templates/expenses.html') else "صفحة المصروفات"

@app.route('/employees')
@login_required
def employees():
    return "صفحة الموظفين"

@app.route('/settings')
@login_required
def settings():
    return "الإعدادات"

@app.route('/support')
@login_required
def support():
    return "الدعم الفني"

# ======================================================
if __name__ == '__main__':
    app.run(debug=True)
