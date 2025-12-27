from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'datum-store-secret-key-2025')

# -------------------------
# DATABASE CONFIGURATION (Fixed for Render)
# -------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Fallback to SQLite if no online database is found
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# -------------------------
# MODELS
# -------------------------

class Shop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    tax_number = db.Column(db.String(50))
    footer_msg = db.Column(db.String(200))
    policy_text = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    rent_paid = db.Column(db.Boolean, default=True)
    subscription_end = db.Column(db.DateTime, nullable=True)
    
    users = db.relationship('User', backref='shop', lazy=True)
    products = db.relationship('Product', backref='shop', lazy=True)
    customers = db.relationship('Customer', backref='shop', lazy=True)
    invoices = db.relationship('Invoice', backref='shop', lazy=True)
    expenses = db.relationship('Expense', backref='shop', lazy=True)
    subscriptions = db.relationship('Subscription', backref='shop', lazy=True)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)
    plan_name = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='paid')
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
    date = db.Column(db.DateTime, default=datetime.utcnow)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)

# -------------------------
# DATABASE INITIALIZATION (Fixes 500 Error)
# -------------------------
with app.app_context():
    db.create_all()
    # Create default admin if not exists
    if not User.query.filter_by(username='admin').first():
        try:
            hashed = generate_password_hash('admin123', method='scrypt')
            # Create a dummy shop for admin to prevent errors
            admin_shop = Shop(name="System Admin", subscription_end=datetime.utcnow() + timedelta(days=3650))
            db.session.add(admin_shop)
            db.session.commit()
            
            admin = User(username='admin', password=hashed, role='admin', is_admin=True, shop_id=admin_shop.id)
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin User Created: admin / admin123")
        except Exception as e:
            print(f"⚠️ Error initializing admin: {e}")

# -------------------------
# ROUTES
# -------------------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            # Check shop status (if not admin)
            if not user.is_admin and user.shop:
                if not user.shop.is_active:
                    flash('عذراً، هذا المتجر موقف يدوياً من الإدارة.', 'error')
                    return redirect(url_for('login'))
                if user.shop.subscription_end and user.shop.subscription_end < datetime.utcnow():
                    flash('عذراً، انتهت صلاحية اشتراك هذا المتجر.', 'error')
                    return redirect(url_for('login'))
                
            login_user(user)
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        else:
            flash('بيانات الدخول غير صحيحة', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        shop_name = request.form.get('shop_name')
        username = request.form.get('username')
        password = request.form.get('password')
        
        if Shop.query.filter_by(name=shop_name).first():
            flash('عذراً، اسم المتجر هذا مستخدم مسبقاً.', 'error')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('اسم المستخدم موجود مسبقاً', 'error')
            return redirect(url_for('register'))
            
        trial_end = datetime.utcnow() + timedelta(days=14)
        new_shop = Shop(name=shop_name, subscription_end=trial_end)
        db.session.add(new_shop)
        db.session.flush()
        
        hashed_pw = generate_password_hash(password, method='scrypt')
        new_user = User(username=username, password=hashed_pw, role='owner', shop_id=new_shop.id)
        db.session.add(new_user)
        db.session.commit()
        
        flash('تم إنشاء الحساب بنجاح! لديك فترة تجريبية 14 يوم.', 'success')
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
    
    # Use explicit date checking for SQLite compatibility
    todays_sales = 0
    month_sales = 0
    
    # Fetch all invoices for this shop to process in Python (safer for SQLite)
    all_invoices = Invoice.query.filter_by(shop_id=shop_id).all()
    
    for inv in all_invoices:
        if inv.status == 'refunded': continue
        inv_date = inv.date.date()
        if inv_date == today:
            todays_sales += inv.total_amount
        if inv_date.month == today.month and inv_date.year == today.year:
            month_sales += inv.total_amount

    # Calculate expenses
    month_expenses = 0
    all_expenses = Expense.query.filter_by(shop_id=shop_id).all()
    for exp in all_expenses:
        if exp.date.date().month == today.month and exp.date.date().year == today.year:
            month_expenses += exp.amount
    
    net_profit = month_sales - month_expenses
    low_stock = Product.query.filter_by(shop_id=shop_id).filter(Product.stock <= 5).all()
    
    days_left = 0
    if current_user.shop.subscription_end:
        delta = current_user.shop.subscription_end - datetime.utcnow()
        days_left = max(0, delta.days)
    
    # Dummy data for chart (can be updated later)
    chart_labels = ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri"]
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

@app.route('/products', methods=['GET', 'POST'])
@login_required
def products():
    if request.method == 'POST':
        name = request.form.get('name')
        barcode = request.form.get('barcode')
        category = request.form.get('category')
        stock = request.form.get('stock')
        buy_price = request.form.get('buy_price')
        sell_price = request.form.get('sell_price')
        tax = request.form.get('tax') or 0
        
        new_prod = Product(
            name=name, barcode=barcode, category=category, 
            stock=stock, buy_price=buy_price, sell_price=sell_price, 
            tax=float(tax), shop_id=current_user.shop_id
        )
        db.session.add(new_prod)
        db.session.commit()
        flash('تم إضافة المنتج', 'success')
        return redirect(url_for('products'))
        
    all_products = Product.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('products.html', products=all_products)

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
        product.tax = request.form.get('tax') or 0
        db.session.commit()
        flash('تم التعديل', 'success')
        return redirect(url_for('products'))
    return render_template('edit_product.html', product=product)

@app.route('/product/delete/<int:id>')
@login_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    if product.shop_id != current_user.shop_id: return redirect(url_for('products'))
    db.session.delete(product)
    db.session.commit()
    flash('تم حذف المنتج', 'success')
    return redirect(url_for('products'))

@app.route('/customers', methods=['GET', 'POST'])
@login_required
def customers():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        new_cust = Customer(name=name, phone=phone, shop_id=current_user.shop_id)
        db.session.add(new_cust)
        db.session.commit()
        flash('تم إضافة العميل', 'success')
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
        flash('تم التعديل', 'success')
        return redirect(url_for('customers'))
    return render_template('edit_customer.html', customer=customer)

@app.route('/customer/delete/<int:id>')
@login_required
def delete_customer(id):
    customer = Customer.query.get_or_404(id)
    if customer.shop_id != current_user.shop_id: return redirect(url_for('customers'))
    db.session.delete(customer)
    db.session.commit()
    flash('تم الحذف', 'success')
    return redirect(url_for('customers'))

@app.route('/pos')
@login_required
def pos():
    products = Product.query.filter_by(shop_id=current_user.shop_id).all()
    customers = Customer.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('pos.html', products=products, customers=customers)

@app.route('/api/get_product_by_barcode/<barcode>')
@login_required
def get_product_by_barcode(barcode):
    product = Product.query.filter_by(shop_id=current_user.shop_id, barcode=barcode).first()
    if product:
        return jsonify({'success': True, 'id': product.id, 'name': product.name, 'price': product.sell_price, 'tax': product.tax})
    return jsonify({'success': False})

@app.route('/api/create_invoice', methods=['POST'])
@login_required
def create_invoice():
    data = request.json
    items = data.get('items', [])
    cust_id = data.get('customer_id')
    cust_name = data.get('customer_name')
    cust_phone = data.get('customer_phone')
    cust_email = data.get('customer_email')
    cust_notes = data.get('customer_notes')
    status = data.get('status', 'paid')
    
    if not items: return jsonify({'success': False, 'message': 'السلة فارغة'})
    
    customer = None
    if cust_id:
        customer = Customer.query.get(cust_id)
    elif cust_name:
        if cust_phone:
            customer = Customer.query.filter_by(phone=cust_phone, shop_id=current_user.shop_id).first()
        if not customer:
            customer = Customer(name=cust_name, phone=cust_phone, email=cust_email, notes=cust_notes, shop_id=current_user.shop_id, balance=0.0)
            db.session.add(customer)
            db.session.commit()
            
    total = 0
    invoice_items = []
    
    for item in items:
        prod = Product.query.get(item['id'])
        if prod and prod.shop_id == current_user.shop_id:
            if prod.stock < item['quantity']:
                return jsonify({'success': False, 'message': f'الكمية غير كافية: {prod.name}'})
            prod.stock -= item['quantity']
            line_total = (item['price'] * (1 + (prod.tax/100))) * item['quantity'] 
            total += line_total
            inv_item = InvoiceItem(product_id=prod.id, quantity=item['quantity'], price=item['price'])
            invoice_items.append(inv_item)
    
    new_inv = Invoice(total_amount=total, status=status, shop_id=current_user.shop_id, items=invoice_items)
    
    if customer:
        new_inv.customer_id = customer.id
        new_inv.customer_name = customer.name
        if status == 'pending':
            customer.balance += total

    db.session.add(new_inv)
    db.session.commit()
    return jsonify({'success': True, 'invoice_id': new_inv.id})

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
        if inv.customer:
            inv.customer.balance -= inv.total_amount
        db.session.commit()
        flash('تم التسديد', 'success')
    return redirect(url_for('invoices'))

@app.route('/invoice/refund/<int:id>')
@login_required
def refund_invoice(id):
    inv = Invoice.query.get_or_404(id)
    if inv.shop_id != current_user.shop_id: return redirect(url_for('invoices'))
    
    if inv.status != 'refunded':
        for item in inv.items:
            if item.product: item.product.stock += item.quantity
        if inv.status == 'pending' and inv.customer:
            inv.customer.balance -= inv.total_amount
        inv.status = 'refunded'
        db.session.commit()
        flash('تم الاسترجاع', 'success')
    return redirect(url_for('invoices'))

@app.route('/invoice/delete/<int:id>')
@login_required
def delete_invoice(id):
    inv = Invoice.query.get_or_404(id)
    if inv.shop_id != current_user.shop_id: return redirect(url_for('invoices'))
    db.session.delete(inv)
    db.session.commit()
    flash('تم الحذف', 'success')
    return redirect(url_for('invoices'))

@app.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    if request.method == 'POST':
        desc = request.form.get('description')
        amount = request.form.get('amount')
        new_exp = Expense(description=desc, amount=float(amount), shop_id=current_user.shop_id)
        db.session.add(new_exp)
        db.session.commit()
        return redirect(url_for('expenses'))
    all_exp = Expense.query.filter_by(shop_id=current_user.shop_id).order_by(Expense.date.desc()).all()
    total = sum(e.amount for e in all_exp)
    return render_template('expenses.html', expenses=all_exp, total=total)

@app.route('/expense/delete/<int:id>')
@login_required
def delete_expense(id):
    exp = Expense.query.get_or_404(id)
    if exp.shop_id != current_user.shop_id: return redirect(url_for('expenses'))
    db.session.delete(exp)
    db.session.commit()
    return redirect(url_for('expenses'))

@app.route('/employees', methods=['GET', 'POST'])
@login_required
def employees():
    if current_user.role != 'owner': return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        if User.query.filter_by(username=username).first():
            flash('المستخدم موجود', 'error')
        else:
            hashed = generate_password_hash(password, method='scrypt')
            new_emp = User(username=username, password=hashed, role=role, shop_id=current_user.shop_id)
            db.session.add(new_emp)
            db.session.commit()
            flash('تمت الإضافة', 'success')
            return redirect(url_for('employees'))
    emps = User.query.filter_by(shop_id=current_user.shop_id).all()
    return render_template('employees.html', employees=emps)

@app.route('/employee/delete/<int:id>')
@login_required
def delete_employee(id):
    if current_user.role != 'owner': return redirect(url_for('dashboard'))
    user = User.query.get_or_404(id)
    if user.shop_id != current_user.shop_id or user.id == current_user.id:
        return redirect(url_for('employees'))
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('employees'))

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
        db.session.commit()
        flash('تم الحفظ', 'success')
    return render_template('settings.html', shop=shop)

@app.route('/support')
@login_required
def support():
    return render_template('support.html')

# ----------------------------------------------------
# ADMIN ROUTES (Safe Logic)
# ----------------------------------------------------

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    # Corrected endpoint name: was /admin in original, changed to /admin_dashboard to match redirect
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    shops = Shop.query.all()
    shop_list = []
    for s in shops:
        owner = User.query.filter_by(shop_id=s.id, role='owner').first()
        prod_count = Product.query.filter_by(shop_id=s.id).count()
        
        sub_status = "inactive"
        days_left = 0
        
        # FIX: Handle None subscription_end safely
        if s.subscription_end:
            if s.subscription_end > datetime.utcnow():
                sub_status = "active"
                days_left = (s.subscription_end - datetime.utcnow()).days
            else:
                sub_status = "expired"

        shop_list.append({
            'shop': s, 
            'owner_name': owner.username if owner else 'Unknown', 
            'products': prod_count,
            'status': sub_status,
            'days_left': days_left
        })
    return render_template('admin.html', shops=shop_list, total_shops=len(shops))

@app.route('/admin/renew_subscription', methods=['POST'])
@login_required
def renew_subscription():
    if not current_user.is_admin: return redirect(url_for('login'))
    
    shop_id = request.form.get('shop_id')
    plan_name = request.form.get('plan_name')
    price = float(request.form.get('price'))
    
    shop = Shop.query.get_or_404(shop_id)
    
    duration_days = 30
    if plan_name == "6 Months": duration_days = 180
    elif plan_name == "1 Year": duration_days = 365
    
    start_date = datetime.utcnow()
    # FIX: Handle None type for comparison
    if shop.subscription_end and shop.subscription_end > datetime.utcnow():
        start_date = shop.subscription_end
    
    end_date = start_date + timedelta(days=duration_days)
    
    shop.subscription_end = end_date
    shop.is_active = True
    
    new_sub = Subscription(
        shop_id=shop.id,
        plan_name=plan_name,
        amount=price,
        duration_days=duration_days,
        start_date=start_date,
        end_date=end_date
    )
    db.session.add(new_sub)
    db.session.commit()
    
    flash(f'تم تجديد الاشتراك للمتجر {shop.name} بنجاح!', 'success')
    # FIX: Using admin_dashboard redirect to be safe
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/shop/toggle_status/<int:id>')
@login_required
def toggle_shop_status(id):
    if not current_user.is_admin: return redirect(url_for('login'))
    shop = Shop.query.get_or_404(id)
    shop.is_active = not shop.is_active
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/shop/delete/<int:id>')
@login_required
def delete_shop(id):
    if not current_user.is_admin: return redirect(url_for('login'))
    shop = Shop.query.get_or_404(id)
    User.query.filter_by(shop_id=id).delete()
    Product.query.filter_by(shop_id=id).delete()
    Customer.query.filter_by(shop_id=id).delete()
    Invoice.query.filter_by(shop_id=id).delete()
    db.session.delete(shop)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/manage_admins', methods=['GET', 'POST'])
@login_required
def manage_admins():
    if not current_user.is_admin: return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('اسم المستخدم هذا موجود بالفعل.', 'error')
        else:
            hashed = generate_password_hash(password, method='scrypt')
            # Create a dummy shop for the new admin to prevent errors
            admin_shop = Shop(name=f"Admin {username}", subscription_end=datetime.utcnow() + timedelta(days=3650))
            db.session.add(admin_shop)
            db.session.commit()
            
            new_admin = User(username=username, password=hashed, role='admin', is_admin=True, shop_id=admin_shop.id)
            db.session.add(new_admin)
            db.session.commit()
            flash('تم إضافة المشرف بنجاح', 'success')
        return redirect(url_for('manage_admins'))
        
    admins = User.query.filter_by(is_admin=True).filter(User.id != current_user.id).all()
    return render_template('admin_users.html', admins=admins)

@app.route('/admin_profile', methods=['GET', 'POST'])
@login_required
def admin_profile():
    if not current_user.is_admin: return redirect(url_for('login'))
    
    if request.method == 'POST':
        new_username = request.form.get('username')
        pw = request.form.get('password')
        
        existing_user = User.query.filter_by(username=new_username).first()
        if existing_user and existing_user.id != current_user.id:
            flash('اسم المستخدم هذا موجود بالفعل، يرجى اختيار اسم آخر.', 'error')
        else:
            current_user.username = new_username
            if pw: current_user.password = generate_password_hash(pw, method='scrypt')
            db.session.commit()
            flash('تم التحديث بنجاح', 'success')
            
    return render_template('admin_profile.html')

@app.route('/admin_edit_shop/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_edit_shop(id):
    if not current_user.is_admin: return redirect(url_for('login'))
    shop = Shop.query.get_or_404(id)
    owner = User.query.filter_by(shop_id=shop.id, role='owner').first()
    if request.method == 'POST':
        shop.name = request.form.get('shop_name')
        new_pass = request.form.get('new_password')
        if new_pass and owner:
            owner.password = generate_password_hash(new_pass, method='scrypt')
        db.session.commit()
        flash('تم التحديث', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_edit_shop.html', shop=shop, owner=owner)

if __name__ == '__main__':
    app.run(debug=True)
