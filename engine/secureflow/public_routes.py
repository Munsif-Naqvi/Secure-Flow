"""The public allowlist (docs/03-detection-rules.md, part 3).

Routes that are meant to be open to everyone, such as the home page or the
login page, are not flagged even when they have no login check. The lists are
kept here, in one place, so they are easy to change.
"""

# Compared after lowercasing the path and removing a trailing slash.
PUBLIC_PATHS = {
    "/", "/index", "/home", "/login", "/signin", "/logout", "/register",
    "/signup", "/forgot-password", "/reset-password", "/health", "/healthz",
    "/ping", "/about", "/contact", "/favicon.ico",
}

# Any path under this folder is public too (Flask serves files from it).
PUBLIC_PATH_PREFIXES = ["/static/"]

# Handler function names that mean "public page", compared in lower case.
PUBLIC_FUNCTION_NAMES = {"index", "home", "login", "logout", "register", "signup", "health", "static"}
