import sqlite3
from flask import Flask, render_template_string, request, session, redirect, url_for, g

app = Flask(__name__)
app.secret_key = 'super-secret-key-blog-demo'
DATABASE = 'blog_app.db'

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
        
        # Table: Blog Posts
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                author_id INTEGER NOT NULL
            )
        ''')
        
        # Seed Fake Users & Blog Posts
        cursor.execute("INSERT OR IGNORE INTO users (id, username, password) VALUES (1, 'author_john', 'pass123')")
        cursor.execute("INSERT OR IGNORE INTO users (id, username, password) VALUES (2, 'reader_sam', 'pass456')")
        
        cursor.execute("INSERT OR IGNORE INTO posts (id, title, content, author_id) VALUES (1, 'First Blog Post', 'This is a public blog post content.', 1)")
        cursor.execute("INSERT OR IGNORE INTO posts (id, title, content, author_id) VALUES (2, 'Important Announcement', 'Company critical update details.', 1)")
        
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
    db = get_db()
    posts = db.execute('SELECT posts.id, posts.title, posts.content, users.username FROM posts JOIN users ON posts.author_id = users.id').fetchall()
    
    posts_html = "".join([
        f"<li><b>{p['title']}</b> by {p['username']}: {p['content']} "
        f"[<a href='/post/delete/{p['id']}'>Delete Post</a>]</li>" 
        for p in posts
    ])
    
    return render_template_string(f'''
        <h2>Public Tech Blog</h2>
        {{% if session.get('username') %}}
            <p>Logged in as: <b>{{{{ session['username'] }}}}</b> | <a href="/logout">Logout</a></p>
        {{% else %}}
            <p><a href="/login">Login</a> (Not logged in)</p>
        {{% endif %}}
        <h3>Articles:</h3>
        <ul>{posts_html if posts_html else "<li>No posts remaining!</li>"}</ul>
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
        <h3>Blog Login</h3>
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
# SAFE ROUTE: Create Post (Protected)
# -------------------------------------------------------------
@app.route('/post/create', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        db = get_db()
        db.execute('INSERT INTO posts (title, content, author_id) VALUES (?, ?, ?)',
                   (title, content, session['user_id']))
        db.commit()
        return redirect(url_for('index'))
    return '''
        <h3>Create New Post</h3>
        <form method="post">
            Title: <input type="text" name="title"><br>
            Content: <textarea name="content"></textarea><br>
            <input type="submit" value="Publish">
        </form>
    '''


# -------------------------------------------------------------
# VULNERABLE ROUTE: Missing Authentication on Sensitive Action (Delete)
# Target for Scanner: State-changing action route without @login_required
# -------------------------------------------------------------
@app.route('/post/delete/<int:post_id>', methods=['GET', 'POST'])
def delete_post(post_id):
    # ❌ VULNERABILITY:
    # Action route missing `@login_required` decorator and session check.
    # Anyone can send a GET/POST request to /post/delete/1 and purge database content.
    
    db = get_db()
    db.execute('DELETE FROM posts WHERE id = ?', (post_id,))
    db.commit()
    
    return f"<h3>Post #{post_id} Deleted Successfully!</h3><a href='/'>Back to Blog</a>"


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)