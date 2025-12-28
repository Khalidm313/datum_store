from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'datum-store-secret-key-2025')

# إعدادات قاعدة البيانات (متوافق مع Render)
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- الموديلات (نفس الموديلات السابقة مع تحسينات طفيفة) ---
class Shop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    subscription_end = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    users = db.relationship('User', backref='shop', lazy=True)
    products = db.relationship('Product', backref='shop', lazy=True)
    customers = db.relationship('Customer', backref='shop', lazy=True)
    invoices = db.relationship('Invoice', backref='shop', lazy=True)
    expenses = db.relationship('Expense', backref='shop', lazy=True)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='owner') 
    is_admin = db.Column(db.Boolean, default=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    barcode = db.Column(db.String(100))
    stock = db.Column(db.Integer, default=0)
    sell_price = db.Column(db.Float, default=0.0)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='paid')
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)

# تهيئة قاعدة البيانات
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        hashed = generate_password_hash('admin123', method='scrypt')
        admin_shop = Shop(name="الإدارة", subscription_end=datetime.utcnow() + timedelta(days=3650))
        db.session.add(admin_shop)
        db.session.commit()
        admin = User(username='admin', password=hashed, role='admin', is_admin=True, shop_id=admin_shop.id)
        db.session.add(admin)
        db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- المسارات (Routes) ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard' if current_user.is_admin else 'dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    today = datetime.today().date()
    shop_id = current_user.shop_id
    # منطق حساب المبيعات والمصاريف...
    return render_template('dashboard.html', todays_sales=0, month_sales=0, month_expenses=0, net_profit=0, chart_labels=[], chart_data=[])

@app.route('/customers', methods=['GET', 'POST'])
@login_required
def customers():
    if request.method == 'POST':
        new_cust = Customer(name=request.form.get('name'), phone=request.form.get('phone'), shop_id=current_user.shop_id)
        db.session.add(new_cust)
        db.session.commit()
        flash('تم إضافة العميل', 'success')
    all_customers = Customer.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('customers.html', customers=all_customers)

@app.route('/employees', methods=['GET', 'POST'])
@login_required
def employees():
    if request.method == 'POST':
        hashed = generate_password_hash(request.form.get('password'), method='scrypt')
        new_emp = User(username=request.form.get('username'), password=hashed, role='worker', shop_id=current_user.shop_id)
        db.session.add(new_emp)
        db.session.commit()
        flash('تم إضافة الموظف', 'success')
    all_employees = User.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('employees.html', employees=all_employees)

@app.route('/support')
@login_required
def support():
    return render_template('support.html')

# أضف باقي المسارات (products, pos, invoices, settings, login, logout, register) كما في ملفك الأصلي

if __name__ == '__main__':
    app.run(debug=True)
