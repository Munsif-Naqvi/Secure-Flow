import sqlite3
from flask import Flask, render_template_string, request, session, redirect, url_for, g

app = Flask(__name__)
app.secret_key = 'super-secret-key-admin-demo'
DATABASE = 'admin_cms.db'

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
        
        # Table: Users (with role column)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
        ''')
        
        # Table: System Settings / Secrets
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_secrets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                secret_key_name TEXT NOT NULL,
                secret_value TEXT NOT NULL
            )
        ''')
        
        # Seed Fake Users: 1 Admin and 1 Normal User
        cursor.execute("INSERT OR IGNORE INTO users (id, username, password, role) VALUES (1, 'admin_user', 'admin123', 'admin')")
        cursor.execute("INSERT OR IGNORE INTO users (id, username, password, role) VALUES (2, 'john_doe', 'user123', 'user')")
        
        # Seed Sensitive Admin Data
        cursor.execute("INSERT OR IGNORE INTO system_secrets (id, secret_key_name, secret_value) VALUES (1, 'PAYMENT_GATEWAY_KEY', 'sk_live_998877665544')")
        cursor.execute("INSERT OR IGNORE INTO system_secrets (id, secret_key_name, secret_value) VALUES (2, 'DATABASE_BACKUP_PATH', '/var/backups/db_secure.sql')")
        
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
        <h2>Company Admin Portal</h2>
        {% if session.get('username') %}
            <p>Logged in as: <b>{{ session['username'] }}</b> (Role: {{ session['role'] }}) | <a href="/logout">Logout</a></p>
        {% else %}
            <p><a href="/login">Login</a></p>
        {% endif %}
        <ul>
            <li><a href="/user/dashboard">Normal User Dashboard (SAFE)</a></li>
            <li><a href="/admin/dashboard">Admin Panel (VULNERABLE - Missing Role Check)</a></li>
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
            session['role'] = user['role']
            return redirect(url_for('index'))
        return "Invalid Credentials", 401
    return '''
        <h3>Login</h3>
        <p><b>Test Accounts:</b><br>
        Admin: admin_user / admin123<br>
        Normal User: john_doe / user123</p>
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
# SAFE ROUTE: Normal User Dashboard
# -------------------------------------------------------------
@app.route('/user/dashboard')
@login_required
def user_dashboard():
    return f"<h3>User Dashboard</h3><p>Welcome, {session['username']}! This is your standard user area.</p>"


# -------------------------------------------------------------
# VULNERABLE ROUTE: Missing Role / Privilege Check
# Target for Scanner: Sensitive /admin URL missing role check logic!
# -------------------------------------------------------------
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    # VULNERABILITY:
    # @login_required verifies the user is logged in, but there is NO role check!
    # Missing: if session.get('role') != 'admin': return "Access Denied", 403
    
    db = get_db()
    secrets = db.execute('SELECT * FROM system_secrets').fetchall()
    
    secrets_html = "".join([f"<li><b>{s['secret_key_name']}:</b> {s['secret_value']}</li>" for s in secrets])
    
    return f'''
        <h2 style="color: red;">ADMIN CONTROL PANEL</h2>
        <p>Current Active Session: <b>{session['username']}</b> (Role: <b>{session['role']}</b>)</p>
        <h3>System Secrets & Admin Configurations:</h3>
        <ul>{secrets_html}</ul>
    '''


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)