import sqlite3
from functools import wraps
from flask import Flask, render_template_string, request, session, redirect, url_for, g, abort

app = Flask(__name__)
app.secret_key = 'super-secure-key-safe-control-app'
DATABASE = 'safe_app.db'

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
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
        ''')
        
        # Table: User Records (IDOR safe testing)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS private_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                note_content TEXT NOT NULL
            )
        ''')
        
        # Seed Fake Users
        cursor.execute("INSERT OR IGNORE INTO users (id, username, password, role) VALUES (1, 'admin_safe', 'pass123', 'admin')")
        cursor.execute("INSERT OR IGNORE INTO users (id, username, password, role) VALUES (2, 'user_safe', 'pass456', 'user')")
        
        cursor.execute("INSERT OR IGNORE INTO private_notes (id, user_id, note_content) VALUES (1, 1, 'Admin confidential strategy note')")
        cursor.execute("INSERT OR IGNORE INTO private_notes (id, user_id, note_content) VALUES (2, 2, 'User 2 personal note content')")
        
        db.commit()

# --- AUTHENTICATION DECORATOR ---
def login_required(f):
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
        <h2>Fully Secure Control Application</h2>
        {% if session.get('username') %}
            <p>Logged in as: <b>{{ session['username'] }}</b> (Role: {{ session['role'] }}) | <a href="/logout">Logout</a></p>
        {% else %}
            <p><a href="/login">Login</a> (Public Area)</p>
        {% endif %}
        <ul>
            <li><a href="/public/info">Public Information Page</a></li>
            <li><a href="/user/profile">My Profile (Protected)</a></li>
            <li><a href="/admin/dashboard">Admin Dashboard (Role Protected)</a></li>
            <li><a href="/notes/view?id=2">View Note #2 (Ownership Verified)</a></li>
        </ul>
    ''')

@app.route('/public/info')
def public_info():
    # Intentionally public route - Should be ignored by scanner (Feature B8)
    return "<h3>Public Announcement</h3><p>This page is intentionally public and safe for anyone to view.</p>"

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
        <p>Admin: admin_safe / pass123 | User: user_safe / pass456</p>
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
# SAFE ROUTE 1: Profile Protected with Decorator
# -------------------------------------------------------------
@app.route('/user/profile')
@login_required
def profile():
    return f"<h3>Profile Page</h3><p>Username: {session['username']}</p>"


# -------------------------------------------------------------
# SAFE ROUTE 2: Admin Panel Protected with Role Check
# -------------------------------------------------------------
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    # SAFE: Explicit role check present
    if session.get('role') != 'admin':
        abort(403)
        
    return "<h3>Admin Dashboard</h3><p>Protected Admin Settings Area.</p>"


# -------------------------------------------------------------
# SAFE ROUTE 3: Parameter Route Protected with Identity Ownership Check
# -------------------------------------------------------------
@app.route('/notes/view')
@login_required
def view_note():
    note_id = request.args.get('id')
    db = get_db()
    note = db.execute('SELECT * FROM private_notes WHERE id = ?', (note_id,)).fetchone()
    
    if not note:
        return "Note not found", 404
        
    # SAFE: Cross-checks note owner with current logged-in user session ID
    if note['user_id'] != session['user_id']:
        abort(403)
        
    return f"<h3>Private Note #{note['id']}</h3><p>{note['note_content']}</p>"


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)