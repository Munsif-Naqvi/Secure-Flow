import sqlite3
from flask import Flask, render_template_string, request, session, redirect, url_for, g

app = Flask(__name__)
app.secret_key = 'super-secret-key-for-dev'
DATABASE = 'ecommerce.db'

# --- DATABASE SETUP ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Table: Users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        
        # Table: Orders
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL
            )
        ''')
        
        # Seed Fake Users & Data
        cursor.execute("INSERT OR IGNORE INTO users (id, username, password) VALUES (1, 'alice', 'password123')")
        cursor.execute("INSERT OR IGNORE INTO users (id, username, password) VALUES (2, 'bob', 'secret456')")
        
        cursor.execute("INSERT OR IGNORE INTO orders (id, user_id, item_name, amount, status) VALUES (101, 1, 'Laptop', 1200.00, 'Shipped')")
        cursor.execute("INSERT OR IGNORE INTO orders (id, user_id, item_name, amount, status) VALUES (102, 1, 'Mouse', 25.00, 'Delivered')")
        cursor.execute("INSERT OR IGNORE INTO orders (id, user_id, item_name, amount, status) VALUES (103, 2, 'Keyboard', 75.00, 'Processing')")
        
        db.commit()

# Dynamic decorator replacement for demonstration/custom check
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# --- ROUTES ---

@app.route('/')
def index():
    return render_template_string('''
        <h2>Welcome to SafeShop E-Commerce</h2>
        {% if session.get('username') %}
            <p>Logged in as: <b>{{ session['username'] }}</b> | <a href="/logout">Logout</a></p>
        {% else %}
            <p><a href="/login">Login</a></p>
        {% endif %}
        <ul>
            <li><a href="/products">View Products (Public)</a></li>
            <li><a href="/profile">My Account Profile (SAFE - Protected)</a></li>
            <li><a href="/checkout">Checkout Cart (VULNERABLE - Missing Login Check)</a></li>
            <li><a href="/orders">Order History (VULNERABLE - Missing Login Check)</a></li>
        </ul>
    ''')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        return "Invalid Credentials", 401
    return '''
        <form method="post">
            Username: <input type="text" name="username"><br>
            Password: <input type="password" name="password"><br>
            <input type="submit" value="Login">
        </form>
    '''

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/products')
def products():
    return "<h3>Public Product Catalog</h3><p>Item 1: Laptop - $1200</p><p>Item 2: Mouse - $25</p>"

# -------------------------------------------------------------
# SAFE ROUTE (Properly Protected)
# -------------------------------------------------------------
@app.route('/profile')
@login_required
def profile():
    return f"<h3>User Profile Page</h3><p>User ID: {session['user_id']}</p><p>Username: {session['username']}</p>"


# -------------------------------------------------------------
# VULNERABLE ROUTE 1: Missing @login_required decorator
# Target for Scanner: Flared missing auth on state/action route
# -------------------------------------------------------------
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    # VULNERABILITY: No @login_required decorator or session check!
    if request.method == 'POST':
        item = request.form.get('item', 'Generic Item')
        amount = request.form.get('amount', 50.0)
        
        # Uses session user_id if present, else defaults to anonymous user 1
        user_id = session.get('user_id', 1) 
        
        db = get_db()
        db.execute('INSERT INTO orders (user_id, item_name, amount, status) VALUES (?, ?, ?, ?)',
                   (user_id, item, amount, 'Pending'))
        db.commit()
        return f"<h3>Order Placed Successfully!</h3><p>Placed for User ID: {user_id}</p><a href='/orders'>View Orders</a>"
        
    return '''
        <h3>Checkout Page</h3>
        <form method="post">
            Item: <input type="text" name="item" value="Headphones"><br>
            Amount: <input type="text" name="amount" value="80.00"><br>
            <input type="submit" value="Confirm Purchase">
        </form>
    '''


# -------------------------------------------------------------
# VULNERABLE ROUTE 2: Missing @login_required decorator
# Target for Scanner: Flared missing auth exposing sensitive order data
# -------------------------------------------------------------
@app.route('/orders')
def orders():
    # VULNERABILITY: Unauthenticated request direct 200 OK access response!
    db = get_db()
    
    # If session exists shows session orders, else dumps all orders
    if 'user_id' in session:
        user_orders = db.execute('SELECT * FROM orders WHERE user_id = ?', (session['user_id'],)).fetchall()
    else:
        # Exposes sensitive customer purchase data to unauthenticated visitors
        user_orders = db.execute('SELECT * FROM orders').fetchall()
        
    orders_html = "".join([f"<li>Order #{o['id']}: {o['item_name']} - ${o['amount']} ({o['status']}) - User #{o['user_id']}</li>" for o in user_orders])
    return f"<h3>Order History</h3><ul>{orders_html}</ul>"


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)