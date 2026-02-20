from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy
import stripe
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask import request, jsonify
import cloudinary
import cloudinary.uploader
import cloudinary.api

app = Flask(__name__)

cloudinary.config(
    cloud_name=os.environ.get("dwtn2iuda"),
    api_key=os.environ.get("284485533773761"),
    api_secret=os.environ.get("VB2J3o_9KFcukeylXZTs8Da6rCI")
)
print(os.environ.get("CLOUDINARY_API_SECRET"))

UPLOAD_FOLDER = 'static/images'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
import os

database_url = os.environ.get("DATABASE_URL")

if database_url:
    # Fix Render postgres:// issue
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


app.config['SECRET_KEY'] = 'dev-secret-key' # IMPORTANT: Change this and keep it secret!
db = SQLAlchemy(app)
import os
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    price = db.Column(db.Integer)
    image = db.Column(db.String(200))


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(100))
    amount = db.Column(db.Integer)
    customer_email = db.Column(db.String(120))
    payment_status = db.Column(db.String(50))


@app.route('/buy/<int:product_id>', methods=['POST'])
def buy(product_id):

    product = Product.query.get(product_id)

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': product.name,
                },
                'unit_amount': int(product.price) * 100,
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=url_for('success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=url_for('cancel', _external=True),
    )

    return redirect(checkout_session.url)


@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)


@app.route('/admin')
def admin():
    products = Product.query.all()
    return render_template('admin.html', products=products)


@app.route('/add', methods=['GET', 'POST'])
def add_product():

    if not session.get('admin'):
        return redirect('/login')

    if request.method == 'POST':

        name = request.form['name']
        price = request.form['price']
        image_file = request.files['image']

        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(image_file)

        image_url = upload_result['secure_url']

        new_product = Product(
            name=name,
            price=price,
            image=image_url
        )

        db.session.add(new_product)
        db.session.commit()

        return redirect('/admin')

    return render_template('add_product.html')





from datetime import datetime

@app.route('/success')
def success():

    now = datetime.now()

    formatted_date = now.strftime("%A, %B %d, %Y at %I:%M %p")
    session.pop('cart', None)
    return render_template(
        'success.html',
        current_date=formatted_date
    )


@app.route('/cancel')
def cancel():
    return render_template('cancel.html')


@app.route('/orders')
def orders():

    if not session.get('admin'):
        return redirect('/login')

    orders = Order.query.all()
    return render_template('orders.html', orders=orders)


@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        admin = Admin.query.filter_by(username=username).first()

        if admin and check_password_hash(admin.password, password):
            session['admin'] = True
            return redirect('/admin')
        else:
            return "Invalid username or password"

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/login')

@app.route('/delete-product/<int:id>', methods=['POST'])
def delete_product(id):

    if not session.get('admin'):
        return redirect('/login')

    product = Product.query.get(id)

    if product:
        db.session.delete(product)
        db.session.commit()

    return redirect('/admin')


@app.route('/edit-product/<int:id>', methods=['GET', 'POST'])
def edit_product(id):

    if not session.get('admin'):
        return redirect('/login')

    product = Product.query.get(id)

    if request.method == 'POST':

        product.name = request.form['name']
        product.price = request.form['price']

        db.session.commit()

        return redirect('/admin')

    return render_template('edit_product.html', product=product)


@app.route('/add-to-cart/<int:id>', methods=['POST'])
def add_to_cart(id):

    quantity = int(request.form.get('quantity', 1))

    if 'cart' not in session:
        session['cart'] = {}

    cart = session['cart']

    if str(id) in cart:
        cart[str(id)] += quantity
    else:
        cart[str(id)] = quantity

    session['cart'] = cart
    session.modified = True

    return redirect('/')


@app.route('/cart')
def view_cart():

    cart = session.get('cart', {})

    products = []
    total = 0

    for product_id, quantity in cart.items():

        product = Product.query.get(int(product_id))

        if product:
            products.append({
                'product': product,
                'quantity': quantity,
                'subtotal': product.price * quantity
            })

            total += product.price * quantity

    return render_template('cart.html', products=products, total=total)


@app.route('/checkout', methods=['POST'])
def checkout():

    cart = session.get('cart', {})

    if not cart:
        return redirect('/cart')

    line_items = []

    for product_id, quantity in cart.items():

        product = Product.query.get(int(product_id))

        if product:
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': product.name,
                    },
                    'unit_amount': int(product.price) * 100,
                },
                'quantity': quantity,
            })

    session_stripe = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=line_items,
        mode='payment',
        success_url=url_for('success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=url_for('view_cart', _external=True),
    )

    return redirect(session_stripe.url)


@app.context_processor
def cart_count():

    cart = session.get('cart', {})

    total_quantity = sum(cart.values())

    return dict(cart_count=total_quantity)


@app.context_processor
def cart_data():

    cart = session.get('cart', {})
    products_data = []
    total = 0

    for product_id, quantity in cart.items():

        product = Product.query.get(int(product_id))

        if product:
            subtotal = product.price * quantity
            total += subtotal

            products_data.append({
                'product': product,
                'quantity': quantity,
                'subtotal': subtotal
            })

    return dict(cart_products=products_data, cart_total=total)


@app.route('/remove-from-cart/<int:id>', methods=['POST'])
def remove_from_cart(id):

    cart = session.get('cart', {})

    if str(id) in cart:
        del cart[str(id)]

    session['cart'] = cart
    session.modified = True

    total = 0

    for product_id, quantity in cart.items():
        product = Product.query.get(int(product_id))
        if product:
            total += product.price * quantity

    return jsonify({
        "cart_count": sum(cart.values()),
        "cart_total": total
    })



@app.route('/update-cart/<int:id>', methods=['POST'])
def update_cart(id):

    cart = session.get('cart', {})

    data = request.get_json()
    action = data.get("action")

    if str(id) in cart:

        if action == "increase":
            cart[str(id)] += 1

        elif action == "decrease":
            cart[str(id)] -= 1

            if cart[str(id)] <= 0:
                del cart[str(id)]

    session['cart'] = cart
    session.modified = True

    total = 0
    subtotals = {}
    quantities = {}

    for product_id, quantity in cart.items():
        product = Product.query.get(int(product_id))
        if product:
            item_total = product.price * quantity
            subtotals[str(product_id)] = item_total
            quantities[str(product_id)] = quantity
            total += item_total

    return jsonify({
        "cart_count": sum(cart.values()),
        "cart_total": total,
        "subtotals": subtotals,
        "quantities": quantities
    })


@app.route("/create-admin")
def create_admin():
    from werkzeug.security import generate_password_hash

    if not Admin.query.filter_by(username="admin").first():
        admin = Admin(
            username="admin",
            password=generate_password_hash("1234")
        )
        db.session.add(admin)
        db.session.commit()
        return "Admin created!"
    
    return "Admin already exists!"


# CREATE TABLES AFTER MODELS
with app.app_context():
    db.create_all()
