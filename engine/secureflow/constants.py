"""Word lists and thresholds for the rules that reduce false missing-login flags.

Kept in one place so they are easy to read, explain and change.
The public allowlist itself stays in public_routes.py.
Rules: docs/03-detection-rules.md, parts 6 and 7.
"""

# --- Public content rule (part 6) -----------------------------------------

# A public content route may only answer these HTTP methods (they only read).
PUBLIC_CONTENT_METHODS = {"GET", "HEAD", "OPTIONS"}

# Names that hold the visitor's request or identity. A handler that mentions
# any of them depends on who is asking, so it is not public content.
REQUEST_STATE_NAMES = {"request", "session", "g", "current_user"}
REQUEST_STATE_ATTRIBUTES = {"cookies", "headers"}

# Names and attribute names that mean "database, files, programs or network".
# A handler that mentions any of them is not public content. (Calls are also
# limited to ALLOWED_CALLS below, so these lists are a second safety net.)
DATA_ACCESS_NAMES = {"db", "cursor", "connection", "conn", "os", "subprocess", "open", "sqlite3", "requests", "urllib", "socket"}
DATA_ACCESS_ATTRIBUTES = {"execute", "executemany", "query", "commit"}

# The only functions a public content handler may call, with constant arguments.
ALLOWED_CALLS = {"render_template", "jsonify", "url_for", "make_response"}

# Jinja statements ({% ... %}) a public template may contain. Anything else,
# and any {{ ... }} expression, means the page can change, so it is not public content.
ALLOWED_TEMPLATE_STATEMENTS = {"extends", "block", "endblock", "include"}

# Words that must not appear in the returned text or template (lower case).
SENSITIVE_WORDS = ["password", "passwd", "secret", "token", "api_key", "apikey", "private", "admin", "credential"]

# --- Privileged words ------------------------------------------------------

# A route whose path or handler name contains one of these (lower case) is
# never public content. (Stage 3 will also use them to raise severity.)
PRIVILEGED_WORDS = [
    "admin", "export", "download", "dump", "backup", "delete", "remove",
    "debug", "config", "internal", "manage", "users",
]
