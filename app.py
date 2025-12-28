from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import csv
from io import StringIO
from flask import make_response

app = Flask(__name__)

# =========================
# ✅ SECRET KEY (عدل فقط)
# =========================
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')

# =========================
# ✅ UPLOADS (عدل فقط)
# =========================
UPLOAD_FOLDER = '/tmp/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# =========================
# ✅ DATABASE (عدل فقط)
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
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# -------------------------
# HELPERS
# -------------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# -------------------------
# MODELS (كما هي)
# -------------------------
class Shop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    tax_number = db.Column(db.String(50))
    footer_msg = db.Column(db.String(200))
    policy_text = db.Column(db.Text)
    currency = db.Column(db.String(10), default='LYD')
    low_stock_limit = db.Column(db.Integer, default=5)
    print_size = db.Column(db.String(20), default='80mm')
    auto_print = db.Column(db.Boolean, default=False)
    logo_file = db.Column(db.String(150))
    is_active = db.Column(db.Boolean, default=True)
    subscription_end = db.Column(db.DateTime, nullable=True)

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
    category = db.Column(db.String(50))
    stock = db.Column(db.Integer, default=0)
    buy_price = db.Column(db.Float, default=0.0)
    sell_price = db.Column(db.Float, default=0.0)
    tax = db.Column(db.Float, default=0.0)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    notes = db.Column(db.Text)
    balance = db.Column(db.Float, default=0.0)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='paid')
    payment_method = db.Column(db.String(20), default='cash')
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))
    customer_name = db.Column(db.String(100))
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)

class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)
    plan_name = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)

# -------------------------
# LOGIN (عدل فقط)
# -------------------------
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# -------------------------
# ROUTES
# -------------------------
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
                role='owner',
                shop_id=shop.id
            )
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('login'))
        except:
            db.session.rollback()
            flash('حدث خطأ أثناء التسجيل', 'error')
    return render_template('register.html')

# -------------------------
# DASHBOARD (عدل الشهر فقط)
# -------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    today = datetime.utcnow().date()
    shop_id = current_user.shop_id

    todays_sales = db.session.query(db.func.sum(Invoice.total_amount)).filter(
        Invoice.shop_id == shop_id,
        db.func.date(Invoice.date) == today,
        Invoice.status != 'refunded'
    ).scalar() or 0

    month_sales = db.session.query(db.func.sum(Invoice.total_amount)).filter(
        Invoice.shop_id == shop_id,
        db.func.date_trunc('month', Invoice.date) == db.func.date_trunc('month', db.func.now()),
        Invoice.status != 'refunded'
    ).scalar() or 0

    month_expenses = db.session.query(db.func.sum(Expense.amount)).filter(
        Expense.shop_id == shop_id,
        db.func.date_trunc('month', Expense.date) == db.func.date_trunc('month', db.func.now())
    ).scalar() or 0

    return render_template(
        'dashboard.html',
        todays_sales=todays_sales,
        month_sales=month_sales,
        month_expenses=month_expenses,
        net_profit=month_sales - month_expenses
    )

# -------------------------
# REFUND (عدل حماية فقط)
# -------------------------
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

# -------------------------
# RUN
# -------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
