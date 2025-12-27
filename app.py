from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required,
    logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

# -------------------------
# APP CONFIG
# -------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "CHANGE-THIS-SECRET-KEY")

# -------------------------
# DATABASE CONFIG
# -------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# -------------------------
# MODELS (Fixes the "No attribute shop" error)
# -------------------------
class Shop(db.Model):
    __tablename__ = "shops"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, default="متجري")
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to Shop
    shop = db.relationship('Shop', backref='owner', uselist=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

# -------------------------
# INIT DATABASE
# -------------------------
with app.app_context():
    db.create_all()
    # Create default admin and shop if they don't exist
    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user:
        admin_pass = generate_password_hash("admin123", method="scrypt")
        admin_user = User(username="admin", password=admin_pass, is_admin=True)
        db.session.add(admin_user)
        db.session.commit()
        
        admin_shop = Shop(name="Datum Store Admin", user_id=admin_user.id)
        db.session.add(admin_shop)
        db.session.commit()
        print("✅ Admin user and Shop created")

# -------------------------
# AUTH ROUTES
# -------------------------
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
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
            flash('اسم المستخدم موجود مسبقاً', 'danger')
            return redirect(url_for('register'))
        
        hashed = generate_password_hash(password, method='scrypt')
        new_user = User(username=username, password=hashed)
        db.session.add(new_user)
        db.session.commit()
        
        # Create a default shop for new user
        new_shop = Shop(name=f"متجر {username}", user_id=new_user.id)
        db.session.add(new_shop)
        db.session.commit()

        flash('تم إنشاء الحساب بنجاح', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# -------------------------
# APPLICATION ROUTES (Placeholders for base.html)
# -------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    return render_template('admin_dashboard.html', users=User.query.all())

@app.route('/manage_admins')
@login_required
def manage_admins():
    if not current_user.is_admin: return redirect(url_for('dashboard'))
    return "<h1>إدارة المشرفين</h1>"

@app.route('/admin_profile')
@login_required
def admin_profile():
    return "<h1>ملفي الشخصي</h1>"

@app.route('/pos')
@login_required
def pos(): return "<h1>نقطة البيع</h1>"

@app.route('/products')
@login_required
def products(): return "<h1>المنتجات</h1>"

@app.route('/customers')
@login_required
def customers(): return "<h1>العملاء</h1>"

@app.route('/expenses')
@login_required
def expenses(): return "<h1>المصروفات</h1>"

@app.route('/employees')
@login_required
def employees(): return "<h1>الموظفين</h1>"

@app.route('/invoices')
@login_required
def invoices(): return "<h1>الفواتير</h1>"

@app.route('/settings')
@login_required
def settings(): return "<h1>الإعدادات</h1>"

@app.route('/support')
@login_required
def support(): return "<h1>الدعم الفني</h1>"

if __name__ == "__main__":
    app.run(debug=True)
