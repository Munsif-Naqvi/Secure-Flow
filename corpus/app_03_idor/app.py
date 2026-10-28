import sqlite3
from flask import Flask, render_template_string, request, session, redirect, url_for, g

app = Flask(__name__)
app.secret_key = 'super-secret-key-idor-demo'
DATABASE = 'idor_app.db'

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
        
        # Table: Users with private sensitive information
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT NOT NULL,
                credit_card TEXT NOT NULL,
                address TEXT NOT NULL
            )
        ''')
        
        # Seed Fake Users Data
        cursor.execute("INSERT OR IGNORE INTO users (id, username, password, email, credit_card, address) VALUES (1, 'alice', 'alice123', 'alice@example.com', '4532-xxxx-xxxx-8899', '123 Main Street, NY')")
        cursor.execute("INSERT OR IGNORE INTO users (id, username, password, email, credit_card, address) VALUES (2, 'bob', 'bob123', 'bob@example.com', '5412-xxxx-xxxx-1122', '456 Elm Street, CA')")
        
        db.commit()

# Basic Login Required Decorator
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
        <h2>User Identity Portal</h2>
        {% if session.get('username') %}
            <p>Logged in as: <b>{{ session['username'] }}</b> (Your User ID is: <b>{{ session['user_id'] }}</b>) | <a href="/logout">Logout</a></p>
            <ul>
                <li><a href="/user/profile?id={{ session['user_id'] }}">View My Own Profile (SAFE Intended Link)</a></li>
                <li><a href="/user/profile?id=2">View User 2 Profile (VULNERABLE IDOR - Try modifying ?id= parameter!)</a></li>
            </ul>
        {% else %}
            <p><a href="/login">Login First</a></p>
        {% endif %}
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
        <h3>Login</h3>
        <p><b>Test Accounts:</b><br>
        User 1: alice / alice123<br>
        User 2: bob / bob123</p>
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


# -------------------------------------------------------------
# VULNERABLE ROUTE: IDOR / Access Control Failure
# Target for Scanner: Feature B9 (ID in URL parameter with no ownership check)
# -------------------------------------------------------------
@app.route('/user/profile')
@login_required
def user_profile():
    # URL query parameter se user target ID li ja rahi hai (e.g., ?id=2)
    requested_id = request.args.get('id')
    
    # ❌ VULNERABILITY (IDOR):
    # Function query parameter 'id' ko direct database query me use karta hai.
    # MISSING CHECK:
    # if str(requested_id) != str(session['user_id']):
    #     return "Unauthorized Access: You cannot view another user's profile", 403

    if not requested_id:
        requested_id = session['user_id']

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (requested_id,)).fetchone()
    
    if not user:
        return "User Profile Not Found", 404
        
    return f'''
        <h3>Profile Details for User ID #{user['id']}</h3>
        <p style="color: blue;">Logged in User Session: <b>{session['username']} (ID: {session['user_id']})</b></p>
        <hr>
        <p><b>Username:</b> {user['username']}</p>
        <p><b>Email:</b> {user['email']}</p>
        <p><b>Credit Card on File:</b> {user['credit_card']}</p>
        <p><b>Address:</b> {user['address']}</p>
    '''


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)