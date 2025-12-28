from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
# أضف هذه السطور في بداية الملف مع باقي الاستيرادات (Imports)
import csv
from io import StringIO
from flask import make_response

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'

# --- إعدادات رفع الصور ---
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -------------------------
# DATABASE CONFIGURATION (Fixed for Render)
# -------------------------
# سحب الرابط من إعدادات ريندر
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # ريندر يعطي الرابط يبدأ بـ postgres:// ويجب تحويله لـ postgresql:// ليعمل مع SQLAlchemy 2.0
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    # إذا لم يوجد رابط خارجي (مثل وقت التشغيل المحلي)، استخدم SQLite تلقائياً
    # تأكد من استخدام المسار المطلق للملف لضمان استقراره
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'database.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# -------------------------
# MODELS (الجداول)
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
    
    users = db.relationship('User', backref='shop', lazy=True)
    products = db.relationship('Product', backref='shop', lazy=True)
    customers = db.relationship('Customer', backref='shop', lazy=True)
    invoices = db.relationship('Invoice', backref='shop', lazy=True)
    expenses = db.relationship('Expense', backref='shop', lazy=True)
    subscriptions = db.relationship('Subscription', backref='shop', lazy=True)

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
    invoices = db.relationship('Invoice', backref='customer', lazy=True)

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.now)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='paid')
    payment_method = db.Column(db.String(20), default='cash') 
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True)
    customer_name = db.Column(db.String(100))
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)
    items = db.relationship('InvoiceItem', backref='invoice', lazy=True, cascade="all, delete-orphan")

class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.now)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)
    plan_name = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.DateTime, default=datetime.now)
    end_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

# -------------------------
# ROUTES (المسارات)
# -------------------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('بيانات خاطئة', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        shop = Shop(name=request.form.get('shop_name'), subscription_end=datetime.now()+timedelta(days=14))
        db.session.add(shop)
        db.session.commit()
        user = User(username=request.form.get('username'), password=generate_password_hash(request.form.get('password')), role='owner', shop_id=shop.id)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin: return redirect(url_for('admin_dashboard'))
    today = datetime.today().date()
    shop_id = current_user.shop_id
    
    todays_sales = db.session.query(db.func.sum(Invoice.total_amount)).filter(
        Invoice.shop_id==shop_id, 
        db.func.date(Invoice.date) == today, 
        Invoice.status != 'refunded'
    ).scalar() or 0
    
    month_sales = db.session.query(db.func.sum(Invoice.total_amount)).filter(
        Invoice.shop_id==shop_id, 
        db.func.extract('month', Invoice.date) == today.month, 
        Invoice.status != 'refunded'
    ).scalar() or 0
    
    month_expenses = db.session.query(db.func.sum(Expense.amount)).filter(
        Expense.shop_id==shop_id, 
        db.func.extract('month', Expense.date) == today.month
    ).scalar() or 0
    
    net_profit = month_sales - month_expenses
    limit = current_user.shop.low_stock_limit if current_user.shop.low_stock_limit else 5
    low_stock = Product.query.filter_by(shop_id=shop_id).filter(Product.stock <= limit).all()
    
    days_left = 0
    if current_user.shop.subscription_end:
        delta = current_user.shop.subscription_end - datetime.now()
        days_left = delta.days if delta.days > 0 else 0
    
    chart_labels = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]
    chart_data = [0, 0, 0, 0, 0, 0, 0] 

    return render_template('dashboard.html', 
                           today_date=today.strftime('%Y-%m-%d'),
                           todays_sales=round(todays_sales, 2),
                           month_sales=round(month_sales, 2),
                           month_expenses=round(month_expenses, 2),
                           net_profit=round(net_profit, 2),
                           low_stock_products=low_stock,
                           days_left=days_left,
                           chart_labels=chart_labels,
                           chart_data=chart_data)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    shop = Shop.query.get(current_user.shop_id)
    
    if request.method == 'POST':
        shop.name = request.form.get('name')
        shop.phone = request.form.get('phone')
        shop.address = request.form.get('address')
        shop.tax_number = request.form.get('tax_number')
        shop.footer_msg = request.form.get('footer_msg')
        shop.policy_text = request.form.get('policy_text')
        shop.print_size = request.form.get('print_size')
        shop.auto_print = 'auto_print' in request.form
        shop.low_stock_limit = request.form.get('low_stock_limit')
        shop.currency = request.form.get('currency')

        if 'logo' in request.files:
            file = request.files['logo']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"shop_{shop.id}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                shop.logo_file = filename

        if request.form.get('new_password'):
            current_user.password = generate_password_hash(request.form.get('new_password'), method='scrypt')
            
        db.session.commit()
        flash('تم حفظ الإعدادات بنجاح', 'success')
        return redirect(url_for('settings'))
        
    return render_template('settings.html', shop=shop)

@app.route('/pos')
@login_required
def pos():
    raw_products = Product.query.filter_by(shop_id=current_user.shop_id).all()
    products_data = []
    for p in raw_products:
        products_data.append({
            'id': p.id,
            'name': p.name,
            'barcode': p.barcode,
            'category': p.category,
            'stock': p.stock,
            'sell_price': p.sell_price,
            'tax': p.tax if p.tax else 0
        })
    
    raw_customers = Customer.query.filter_by(shop_id=current_user.shop_id).all()
    customers_data = []
    for c in raw_customers:
        customers_data.append({
            'id': c.id,
            'name': c.name,
            'phone': c.phone,
            'email': c.email,
            'notes': c.notes,
            'balance': c.balance
        })

    return render_template('pos.html', products=products_data, customers=customers_data)

@app.route('/api/create_invoice', methods=['POST'])
@login_required
def create_invoice():
    data = request.json
    items = data.get('items', [])
    if not items: return jsonify({'success': False, 'message': 'السلة فارغة'})

    for item in items:
        prod = Product.query.get(item['id'])
        if not prod: continue
        if prod.stock < item['quantity']:
            return jsonify({'success': False, 'message': f'الكمية غير متوفرة للمنتج: {prod.name}'})

    customer = None
    if data.get('customer_id'):
        customer = Customer.query.get(data.get('customer_id'))
        if data.get('customer_phone'): customer.phone = data.get('customer_phone')
        if data.get('customer_email'): customer.email = data.get('customer_email')
        if data.get('customer_notes'): customer.notes = data.get('customer_notes')
    elif data.get('customer_name'):
        customer = Customer(
            name=data.get('customer_name'), 
            phone=data.get('customer_phone'),
            email=data.get('customer_email'),
            notes=data.get('customer_notes'),
            shop_id=current_user.shop_id
        )
        db.session.add(customer)
        db.session.flush()

    total = 0
    invoice_items = []
    for item in items:
        prod = Product.query.get(item['id'])
        if prod:
            prod.stock -= item['quantity']
            line_total = (item['price'] * (1 + (prod.tax/100))) * item['quantity']
            total += line_total
            invoice_items.append(InvoiceItem(product_id=prod.id, quantity=item['quantity'], price=item['price']))
    
    method = data.get('payment_method')
    status = 'paid'
    
    if method == 'debt':
        status = 'pending'
        if customer: customer.balance += total
        
    new_inv = Invoice(
        total_amount=total, 
        status=status, 
        payment_method=method,
        shop_id=current_user.shop_id, 
        items=invoice_items
    )
    if customer:
        new_inv.customer_id = customer.id
        new_inv.customer_name = customer.name
        
    db.session.add(new_inv)
    db.session.commit()
    
    return jsonify({'success': True, 'invoice_id': new_inv.id})

# --- الفواتير (Invoices) ---
@app.route('/invoices')
@login_required
def invoices():
    invs = Invoice.query.filter_by(shop_id=current_user.shop_id).order_by(Invoice.date.desc()).all()
    return render_template('invoices.html', invoices=invs)

@app.route('/invoice/print/<int:id>')
@login_required
def print_invoice(id):
    inv = Invoice.query.get_or_404(id)
    if inv.shop_id != current_user.shop_id: return redirect(url_for('invoices'))
    return render_template('print_invoice.html', invoice=inv, shop=inv.shop)

@app.route('/invoice/pay/<int:id>')
@login_required
def pay_invoice(id):
    inv = Invoice.query.get_or_404(id)
    if inv.shop_id != current_user.shop_id: return redirect(url_for('invoices'))
    if inv.status == 'pending':
        inv.status = 'paid'
        inv.payment_method = 'cash' 
        if inv.customer: inv.customer.balance -= inv.total_amount
        db.session.commit()
    return redirect(url_for('invoices'))

@app.route('/invoice/refund/<int:id>')
@login_required
def refund_invoice(id):
    inv = Invoice.query.get_or_404(id)
    if inv.shop_id != current_user.shop_id: return redirect(url_for('invoices'))
    if inv.status != 'refunded':
        for item in inv.items: item.product.stock += item.quantity
        if inv.status == 'pending' and inv.customer: inv.customer.balance -= inv.total_amount
        inv.status = 'refunded'
        db.session.commit()
    return redirect(url_for('invoices'))

@app.route('/invoice/delete/<int:id>')
@login_required
def delete_invoice(id):
    inv = Invoice.query.get_or_404(id)
    if inv.shop_id != current_user.shop_id: return redirect(url_for('invoices'))
    db.session.delete(inv)
    db.session.commit()
    return redirect(url_for('invoices'))

# --- المنتجات (Products) ---
@app.route('/products', methods=['GET', 'POST'])
@login_required
def products():
    search_ref = request.args.get('search_ref')
    
    # إضافة منتج جديد
    if request.method == 'POST':
        name = request.form.get('name')
        barcode = request.form.get('barcode')
        # تحقق من تكرار الباركود
        if barcode and Product.query.filter_by(shop_id=current_user.shop_id, barcode=barcode).first():
            flash('الرقم الإشاري (الباركود) مستخدم مسبقاً!', 'error')
            return redirect(url_for('products'))

        new_prod = Product(
            name=name, 
            barcode=barcode, 
            category=request.form.get('category'), 
            stock=request.form.get('stock'), 
            buy_price=request.form.get('buy_price'), 
            sell_price=request.form.get('sell_price'), 
            tax=float(request.form.get('tax') or 0), 
            shop_id=current_user.shop_id
        )
        db.session.add(new_prod)
        db.session.commit()
        flash('تم إضافة المنتج بنجاح', 'success')
        return redirect(url_for('products'))
    
    # منطق البحث المتقدم
    query = Product.query.filter_by(shop_id=current_user.shop_id)
    search_results = [] # لتخزين سجلات المبيعات (الفواتير المرتبطة)
    
    if search_ref:
        # البحث عن المنتجات التي تطابق الباركود أو الاسم
        query = query.filter((Product.barcode.ilike(f'%{search_ref}%')) | (Product.name.ilike(f'%{search_ref}%')))
        all_products = query.all()
        
        if all_products:
            prod_ids = [p.id for p in all_products]
            # جلب تفاصيل المبيعات (المنتج داخل الفاتورة) لكي نعرض الكمية والسعر في تلك العملية
            search_results = db.session.query(InvoiceItem).join(Invoice).filter(
                InvoiceItem.product_id.in_(prod_ids), 
                Invoice.shop_id == current_user.shop_id
            ).order_by(Invoice.date.desc()).all()
    else:
        all_products = query.order_by(Product.id.desc()).limit(50).all()

    return render_template('products.html', products=all_products, search_history=search_results, search_term=search_ref)

@app.route('/product/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    if product.shop_id != current_user.shop_id: return redirect(url_for('products'))
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.barcode = request.form.get('barcode')
        product.category = request.form.get('category')
        product.stock = request.form.get('stock')
        product.buy_price = request.form.get('buy_price')
        product.sell_price = request.form.get('sell_price')
        product.tax = float(request.form.get('tax') or 0)
        db.session.commit()
        return redirect(url_for('products'))
    return render_template('edit_product.html', product=product)

@app.route('/product/delete/<int:id>')
@login_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    if product.shop_id != current_user.shop_id: return redirect(url_for('products'))
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('products'))

# --- العملاء (Customers) ---
@app.route('/customers', methods=['GET', 'POST'])
@login_required
def customers():
    if request.method == 'POST':
        new_cust = Customer(name=request.form.get('name'), phone=request.form.get('phone'), shop_id=current_user.shop_id)
        db.session.add(new_cust)
        db.session.commit()
        return redirect(url_for('customers'))
    all_customers = Customer.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('customers.html', customers=all_customers)

@app.route('/customer/details/<int:id>')
@login_required
def customer_details(id):
    customer = Customer.query.get_or_404(id)
    if customer.shop_id != current_user.shop_id: return redirect(url_for('customers'))
    invoices = Invoice.query.filter_by(customer_id=id).order_by(Invoice.date.desc()).all()
    return render_template('customer_details.html', customer=customer, invoices=invoices)

@app.route('/customer/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_customer(id):
    customer = Customer.query.get_or_404(id)
    if customer.shop_id != current_user.shop_id: return redirect(url_for('customers'))
    if request.method == 'POST':
        customer.name = request.form.get('name')
        customer.phone = request.form.get('phone')
        db.session.commit()
        return redirect(url_for('customers'))
    return render_template('edit_customer.html', customer=customer)

@app.route('/customer/delete/<int:id>')
@login_required
def delete_customer(id):
    customer = Customer.query.get_or_404(id)
    if customer.shop_id != current_user.shop_id: return redirect(url_for('customers'))
    db.session.delete(customer)
    db.session.commit()
    return redirect(url_for('customers'))

# --- المصروفات (Expenses) ---
@app.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    if request.method == 'POST':
        db.session.add(Expense(description=request.form.get('description'), amount=request.form.get('amount'), shop_id=current_user.shop_id))
        db.session.commit()
        return redirect(url_for('expenses'))
    all_exp = Expense.query.filter_by(shop_id=current_user.shop_id).order_by(Expense.date.desc()).all()
    return render_template('expenses.html', expenses=all_exp, total=sum(e.amount for e in all_exp))

@app.route('/expense/delete/<int:id>')
@login_required
def delete_expense(id):
    exp = Expense.query.get_or_404(id)
    if exp.shop_id != current_user.shop_id: return redirect(url_for('expenses'))
    db.session.delete(exp)
    db.session.commit()
    return redirect(url_for('expenses'))

# --- الموظفين (Employees) ---
@app.route('/employees', methods=['GET', 'POST'])
@login_required
def employees():
    if current_user.role != 'owner': return redirect(url_for('dashboard'))
    if request.method == 'POST':
        hashed = generate_password_hash(request.form.get('password'), method='scrypt')
        db.session.add(User(username=request.form.get('username'), password=hashed, role=request.form.get('role'), shop_id=current_user.shop_id))
        db.session.commit()
        return redirect(url_for('employees'))
    return render_template('employees.html', employees=User.query.filter_by(shop_id=current_user.shop_id).all())

@app.route('/employee/delete/<int:id>')
@login_required
def delete_employee(id):
    if current_user.role != 'owner': return redirect(url_for('dashboard'))
    user = User.query.get_or_404(id)
    if user.shop_id == current_user.shop_id:
        db.session.delete(user)
        db.session.commit()
    return redirect(url_for('employees'))

# --- الدعم وكشف الحساب والمسؤول ---
@app.route('/support')
@login_required
def support():
    return render_template('support.html')

@app.route('/account_statement')
@login_required
def account_statement():
    return render_template('account_statement.html', transactions=[])

# --- ضع هذا الكود الجديد مكان القديم ---
# ==========================================
# تحديثات الأدمن (الخصوصية + PDF)
# ==========================================

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    
    shops = Shop.query.all()
    
    # الإحصائيات (تم إزالة إحصائية المنتجات)
    total_shops = len(shops)
    active_shops = sum(1 for s in shops if s.is_active and s.subscription_end and s.subscription_end > datetime.now())
    total_revenue = db.session.query(db.func.sum(Subscription.amount)).scalar() or 0
    
    shop_list = []
    for s in shops:
        owner = User.query.filter_by(shop_id=s.id, role='owner').first()
        
        # تحديد الحالة
        status = "expired"
        if s.subscription_end and s.subscription_end > datetime.now():
            status = "active"
        if not s.is_active:
            status = "stopped"
            
        days_left = (s.subscription_end - datetime.now()).days if status == "active" else 0
        
        shop_list.append({
            'shop': s, 
            'owner_name': owner.username if owner else 'غير محدد',
            'status': status, 
            'days_left': days_left
        })
        
    return render_template('admin.html', 
                           shops=shop_list, 
                           stats={
                               'total_shops': total_shops,
                               'active_shops': active_shops,
                               'total_revenue': total_revenue
                           })

@app.route('/admin/report/pdf')
@login_required
def admin_export_pdf():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    
    shops = Shop.query.all()
    shop_data = []
    
    for s in shops:
        owner = User.query.filter_by(shop_id=s.id, role='owner').first()
        status = 'نشط' if s.is_active and s.subscription_end > datetime.now() else 'متوقف/منتهي'
        
        shop_data.append({
            'name': s.name,
            'owner': owner.username if owner else '-',
            'phone': s.phone,
            'sub_end': s.subscription_end.strftime('%Y-%m-%d') if s.subscription_end else '-',
            'status': status
        })
        
    return render_template('admin_report.html', shops=shop_data, date=datetime.now())
# ==========================================
# مسارات الأدمن (Admin Routes) - أضفها في نهاية app.py
# ==========================================

@app.route('/admin/toggle_status/<int:id>')
@login_required
def toggle_shop_status(id):
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    shop = Shop.query.get_or_404(id)
    shop.is_active = not shop.is_active
    db.session.commit()
    flash('تم تغيير حالة المتجر', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_shop/<int:id>')
@login_required
def delete_shop(id):
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    shop = Shop.query.get_or_404(id)
    # حذف المتجر وكل ما يتعلق به (سيتم الحذف بالتتابع إذا كانت العلاقات مضبوطة، أو يدوياً)
    try:
        # حذف البيانات المرتبطة يدوياً للأمان
        InvoiceItem.query.filter(InvoiceItem.product.has(shop_id=shop.id)).delete(synchronize_session=False)
        Invoice.query.filter_by(shop_id=shop.id).delete()
        Product.query.filter_by(shop_id=shop.id).delete()
        Customer.query.filter_by(shop_id=shop.id).delete()
        User.query.filter_by(shop_id=shop.id).delete()
        Expense.query.filter_by(shop_id=shop.id).delete()
        Subscription.query.filter_by(shop_id=shop.id).delete()
        
        db.session.delete(shop)
        db.session.commit()
        flash('تم حذف المتجر وبياناته بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء الحذف: {str(e)}', 'error')
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/renew_subscription', methods=['POST'])
@login_required
def renew_subscription():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    
    shop_id = request.form.get('shop_id')
    plan_name = request.form.get('plan_name')
    price = request.form.get('price')
    
    shop = Shop.query.get_or_404(shop_id)
    
    # تحديد عدد الأيام بناءً على الخطة
    days = 30
    if 'Year' in plan_name: days = 365
    elif '6 Months' in plan_name: days = 180
    
    # تمديد التاريخ
    if shop.subscription_end and shop.subscription_end > datetime.now():
        shop.subscription_end += timedelta(days=days)
    else:
        shop.subscription_end = datetime.now() + timedelta(days=days)
        
    # تسجيل الاشتراك في السجل
    new_sub = Subscription(
        shop_id=shop.id,
        plan_name=plan_name,
        amount=float(price),
        duration_days=days,
        end_date=shop.subscription_end
    )
    
    shop.is_active = True # إعادة التفعيل تلقائياً عند التجديد
    db.session.add(new_sub)
    db.session.commit()
    
    flash(f'تم تجديد الاشتراك لـ {shop.name} بنجاح', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_shop/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_edit_shop(id):
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    shop = Shop.query.get_or_404(id)
    owner = User.query.filter_by(shop_id=shop.id, role='owner').first()
    
    if request.method == 'POST':
        shop.name = request.form.get('shop_name')
        
        new_password = request.form.get('new_password')
        if new_password and owner:
            owner.password = generate_password_hash(new_password, method='scrypt')
            flash('تم تحديث كلمة مرور المالك', 'success')
            
        db.session.commit()
        flash('تم حفظ التغييرات', 'success')
        return redirect(url_for('admin_dashboard'))
        
    return render_template('admin_edit_shop.html', shop=shop, owner=owner)

@app.route('/admin/admins', methods=['GET', 'POST'])
@login_required
def manage_admins():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('اسم المستخدم موجود مسبقاً', 'error')
        else:
            hashed = generate_password_hash(password, method='scrypt')
            # المسؤول لا يتبع أي متجر (shop_id=None)
            new_admin = User(username=username, password=hashed, role='admin', is_admin=True)
            db.session.add(new_admin)
            db.session.commit()
            flash('تم إضافة المشرف بنجاح', 'success')
            
    admins = User.query.filter_by(is_admin=True).all()
    return render_template('admin_users.html', admins=admins)

@app.route('/admin/delete_admin/<int:id>')
@login_required
def delete_admin(id):
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    user = User.query.get_or_404(id)
    
    if user.id == current_user.id:
        flash('لا يمكنك حذف حسابك الحالي!', 'error')
    else:
        db.session.delete(user)
        db.session.commit()
        flash('تم حذف المشرف', 'success')
        
    return redirect(url_for('manage_admins'))

@app.route('/admin/profile', methods=['GET', 'POST'])
@login_required
def admin_profile():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        current_user.username = request.form.get('username')
        new_password = request.form.get('password')
        
        if new_password:
            current_user.password = generate_password_hash(new_password, method='scrypt')
            
        try:
            db.session.commit()
            flash('تم تحديث البيانات', 'success')
        except:
            flash('اسم المستخدم مستخدم بالفعل', 'error')
            
    return render_template('admin_profile.html')

# --- أضف هذه الدالة الجديدة (لم تكن موجودة سابقاً) ---
@app.route('/admin/export_csv')
@login_required
def admin_export_csv():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Shop ID', 'Shop Name', 'Phone', 'Address', 'Tax Number', 'Subscription End', 'Status'])
    
    shops = Shop.query.all()
    for s in shops:
        status = 'Active' if s.is_active else 'Stopped'
        cw.writerow([s.id, s.name, s.phone, s.address, s.tax_number, s.subscription_end, status])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=shops_export.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8-sig"
    return output

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(debug=True)
