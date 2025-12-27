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

# -------------------------
# APP CONFIG
# -------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "datum-master-key-2025")

# Database Configuration
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# -------------------------
# MODELS
# -------------------------
class Shop(db.Model):
    __tablename__ = "shops"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    subscription_end = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(days=30))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
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
# CRITICAL FIX: INITIALIZE DATABASE IMMEDIATELY
# -------------------------
# This block runs automatically when Gunicorn starts the app
with app.app_context():
    db.create_all()
    
    # Create Admin if missing
    if not User.query.filter_by(username="admin").first():
        try:
            admin = User(username="admin", password=generate_password_hash("admin123", method="scrypt"), is_admin=True)
            db.session.add(admin)
            db.session.commit()
            
            admin_shop = Shop(name="Datum Admin", user_id=admin.id, phone="0000000000")
            db.session.add(admin_shop)
            db.session.commit()
            print("✅ Database & Admin Initialized Successfully")
        except Exception as e:
            print(f"❌ Error creating admin: {e}")

# -------------------------
# AUTH ROUTES
# -------------------------
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('بيانات الدخول غير صحيحة', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('المستخدم موجود مسبقاً', 'danger')
            return redirect(url_for('register'))
        
        hashed = generate_password_hash(password, method='scrypt')
        new_user = User(username=username, password=hashed)
        db.session.add(new_user)
        db.session.commit()
        
        new_shop = Shop(name=f"متجر {username}", user_id=new_user.id)
        db.session.add(new_shop)
        db.session.commit()
        flash('تم إنشاء الحساب بنجاح', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

# -------------------------
# DASHBOARD ROUTE
# -------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template(
        'dashboard.html', 
        user=current_user,
        todays_sales="0", 
        month_sales="0", 
        month_expenses="0", 
        net_profit="0", 
        chart_labels=[], 
        chart_data=[0,0,0,0,0,0,0]
    )

# -------------------------
# ADMIN PANEL ROUTES
# -------------------------
@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    
    shops_data = []
    for s in Shop.query.all():
        days = (s.subscription_end - datetime.utcnow()).days
        shops_data.append({
            'shop': s, 
            'owner_name': s.owner.username, 
            'products': 0, 
            'status': 'active' if days > 0 else 'expired', 
            'days_left': max(0, days)
        })
    return render_template('admin.html', shops=shops_data)

@app.route('/renew_subscription', methods=['POST'])
@login_required
def renew_subscription():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    shop = Shop.query.get(request.form.get('shop_id'))
    plan = request.form.get('plan_name')
    
    if plan == '1 Month': shop.subscription_end += timedelta(days=30)
    elif plan == '6 Months': shop.subscription_end += timedelta(days=180)
    elif plan == '1 Year': shop.subscription_end += timedelta(days=365)
    
    db.session.commit()
    flash(f"تم تجديد اشتراك {shop.name}", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/toggle_shop_status/<int:id>')
@login_required
def toggle_shop_status(id):
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    shop = Shop.query.get_or_404(id)
    shop.is_active = not shop.is_active
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/delete_shop/<int:id>')
@login_required
def delete_shop(id):
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    shop = Shop.query.get_or_404(id)
    db.session.delete(shop.owner)
    db.session.delete(shop)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

# -------------------------
# STORE ROUTES
# -------------------------
@app.route('/products', methods=['GET', 'POST'])
@login_required
def products(): 
    if request.method == 'POST': flash("سيتم تفعيل الإضافة قريباً", "info")
    return render_template('products.html')

@app.route('/employees', methods=['GET', 'POST'])
@login_required
def employees():
    if request.method == 'POST': flash("سيتم تفعيل الإضافة قريباً", "info")
    return render_template('employees.html')

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html', shop=current_user.shop)

# Placeholders
@app.route('/pos')
@login_required
def pos(): return render_template('pos.html')
@app.route('/customers')
@login_required
def customers(): return render_template('customers.html')
@app.route('/expenses')
@login_required
def expenses(): return render_template('expenses.html')
@app.route('/invoices')
@login_required
def invoices(): return render_template('invoices.html')
@app.route('/support')
@login_required
def support(): return render_template('support.html')
@app.route('/admin_profile')
@login_required
def admin_profile(): return render_template('admin_profile.html')
@app.route('/manage_admins')
@login_required
def manage_admins(): return render_template('admin_users.html')
@app.route('/admin_edit_shop/<int:id>')
@login_required
def admin_edit_shop(id): return render_template('admin_edit_shop.html', shop=Shop.query.get(id))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)
