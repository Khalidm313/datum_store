from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'datum-store-secret-key-2025')

# --- إعدادات قاعدة البيانات لـ Render ---
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- الموديلات (Models) ---
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
    buy_price = db.Column(db.Float, default=0.0)
    tax = db.Column(db.Float, default=0.0)
    category = db.Column(db.String(50))
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

# --- تهيئة قاعدة البيانات تلقائياً ---
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        hashed = generate_password_hash('admin123', method='scrypt')
        admin_shop = Shop(name="المركز الرئيسي", subscription_end=datetime.utcnow() + timedelta(days=3650))
        db.session.add(admin_shop)
        db.session.commit()
        admin = User(username='admin', password=hashed, role='admin', is_admin=True, shop_id=admin_shop.id)
        db.session.add(admin)
        db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- مسارات المصادقة ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard' if current_user.is_admin else 'dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('admin_dashboard' if user.is_admin else 'dashboard'))
        flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        shop_name = request.form.get('shop_name')
        username = request.form.get('username')
        password = request.form.get('password')
        if Shop.query.filter_by(name=shop_name).first():
            flash('اسم المتجر مستخدم بالفعل', 'error')
            return redirect(url_for('register'))
        new_shop = Shop(name=shop_name, subscription_end=datetime.utcnow() + timedelta(days=14))
        db.session.add(new_shop)
        db.session.flush()
        new_user = User(username=username, password=generate_password_hash(password, method='scrypt'), shop_id=new_shop.id)
        db.session.add(new_user)
        db.session.commit()
        flash('تم التسجيل بنجاح! فترة تجريبية 14 يوم.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- مسارات المتجر الأساسية ---
@app.route('/dashboard')
@login_required
def dashboard():
    # حسابات لوحة التحكم
    return render_template('dashboard.html', todays_sales=0, month_sales=0, month_expenses=0, net_profit=0, chart_labels=[], chart_data=[])

@app.route('/pos')
@login_required
def pos():
    products = Product.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('pos.html', products=products)

@app.route('/products', methods=['GET', 'POST'])
@login_required
def products():
    if request.method == 'POST':
        new_prod = Product(
            name=request.form.get('name'),
            barcode=request.form.get('barcode'),
            stock=int(request.form.get('stock') or 0),
            sell_price=float(request.form.get('sell_price') or 0),
            shop_id=current_user.shop_id
        )
        db.session.add(new_prod)
        db.session.commit()
        flash('تم إضافة المنتج', 'success')
    prods = Product.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('products.html', products=prods)

@app.route('/invoices')
@login_required
def invoices():
    invs = Invoice.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('invoices.html', invoices=invs)

@app.route('/invoice/print/<int:id>')
@login_required
def print_invoice(id):
    inv = Invoice.query.get_or_404(id)
    return render_template('print_invoice.html', invoice=inv, shop=current_user.shop)

@app.route('/customers', methods=['GET', 'POST'])
@login_required
def customers():
    if request.method == 'POST':
        new_cust = Customer(name=request.form.get('name'), phone=request.form.get('phone'), shop_id=current_user.shop_id)
        db.session.add(new_cust)
        db.session.commit()
        flash('تم إضافة العميل', 'success')
    custs = Customer.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('customers.html', customers=custs)

@app.route('/employees', methods=['GET', 'POST'])
@login_required
def employees():
    if request.method == 'POST':
        hashed = generate_password_hash(request.form.get('password'), method='scrypt')
        new_emp = User(username=request.form.get('username'), password=hashed, role='worker', shop_id=current_user.shop_id)
        db.session.add(new_emp)
        db.session.commit()
        flash('تم إضافة الموظف', 'success')
    emps = User.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('employees.html', employees=emps)

@app.route('/employee/delete/<int:id>')
@login_required
def delete_employee(id):
    emp = User.query.get_or_404(id)
    if emp.shop_id == current_user.shop_id:
        db.session.delete(emp)
        db.session.commit()
        flash('تم الحذف', 'success')
    return redirect(url_for('employees'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    shop = Shop.query.get(current_user.shop_id)
    if request.method == 'POST':
        shop.name = request.form.get('name')
        shop.phone = request.form.get('phone')
        db.session.commit()
        flash('تم الحفظ', 'success')
    return render_template('settings.html', shop=shop)

@app.route('/support')
@login_required
def support():
    return render_template('support.html')

# --- مسارات الإدارة ---
@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    shops = Shop.query.all()
    return render_template('admin.html', shops=shops)

if __name__ == '__main__':
    app.run(debug=True)
