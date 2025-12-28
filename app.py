from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# ------------------
# App setup
# ------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key-change-me'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'


# ------------------
# Models
# ------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(50))
    balance = db.Column(db.Float, default=0)


class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='due')

    customer = db.relationship('Customer', backref='invoices')


# ------------------
# Login loader
# ------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ------------------
# Index
# ------------------
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


# ------------------
# Auth
# ------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not User.query.filter_by(username=request.form['username']).first():
            user = User(
                username=request.form['username'],
                password=generate_password_hash(request.form['password'])
            )
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ------------------
# Dashboard
# ------------------
@app.route('/dashboard')
@login_required
def dashboard():
    sales = Invoice.query.all()
    return render_template('dashboard.html', sales=sales)


# ------------------
# POS (dummy)
# ------------------
@app.route('/pos')
@login_required
def pos():
    return render_template('pos.html')


# ------------------
# Products (dummy)
# ------------------
@app.route('/products')
@login_required
def products():
    return render_template('products.html')


# ------------------
# Customers
# ------------------
@app.route('/customers', methods=['GET', 'POST'])
@login_required
def customers():
    if request.method == 'POST':
        c = Customer(
            name=request.form['name'],
            phone=request.form.get('phone')
        )
        db.session.add(c)
        db.session.commit()
        return redirect(url_for('customers'))

    customers = Customer.query.all()
    return render_template('customers.html', customers=customers)


@app.route('/customers/<int:id>')
@login_required
def customer_details(id):
    customer = Customer.query.get_or_404(id)
    invoices = Invoice.query.filter_by(customer_id=id).all()
    return render_template(
        'customer_details.html',
        customer=customer,
        invoices=invoices
    )


@app.route('/customers/<int:id>/delete')
@login_required
def delete_customer(id):
    customer = Customer.query.get_or_404(id)
    db.session.delete(customer)
    db.session.commit()
    return redirect(url_for('customers'))


@app.route('/customers/<int:id>/edit')
@login_required
def edit_customer(id):
    return redirect(url_for('customers'))


# ------------------
# Invoices
# ------------------
@app.route('/invoices')
@login_required
def invoices():
    invoices = Invoice.query.all()
    return render_template('invoices.html', invoices=invoices)


@app.route('/invoice/<int:id>/print')
@login_required
def print_invoice(id):
    invoice = Invoice.query.get_or_404(id)
    return f"Invoice #{invoice.id}"


# ------------------
# Expenses (ONE TIME ONLY)
# ------------------
@app.route('/expenses')
@login_required
def expenses():
    return render_template('expenses.html')


# ------------------
# DB init
# ------------------
with app.app_context():
    db.create_all()


# ------------------
# Run
# ------------------
if __name__ == '__main__':
    app.run(debug=True)
