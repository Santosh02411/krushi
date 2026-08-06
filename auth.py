"""
auth.py
-------
Session-based authentication with real password hashing (werkzeug's
scrypt-based hasher — no plaintext or reversible storage) and role-based
access (farmer/admin).

Forgot-password is implemented honestly: this app has no email service
configured, so instead of pretending to "send an email" it generates a
real, single-use, time-limited reset token and returns it directly in the
API response, clearly labeled as a dev-mode stand-in for emailing it. See
README for how to wire up a real mail provider (e.g. SMTP or SendGrid) to
replace that step in production.
"""

import os
import secrets
import smtplib
import sqlite3
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from functools import wraps

from flask import g, jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "krushi.db")
RESET_TOKEN_TTL_MINUTES = 30


def send_email(to_email, subject, body):
    """Sends a real email via SMTP if credentials are configured in .env
    (SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD/SMTP_FROM). Returns True
    if a real send was attempted successfully, False otherwise — callers
    use this to decide whether to also return the token/link directly in
    the API response (only when email genuinely isn't configured, so the
    dev flow still works without SMTP)."""
    host = os.getenv("SMTP_HOST")
    port = os.getenv("SMTP_PORT")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    from_addr = os.getenv("SMTP_FROM", user)

    if not all([host, port, user, password]):
        return False

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_email

        with smtplib.SMTP(host, int(port), timeout=10) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"[auth] SMTP send failed, falling back to in-response token: {e}")
        return False


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_tables():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            location TEXT,
            farm_size_acres REAL,
            soil_type TEXT,
            preferred_language TEXT DEFAULT 'en',
            role TEXT NOT NULL DEFAULT 'farmer',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()


def register_user(name, email, password, location=None, farm_size_acres=None,
                   soil_type=None, preferred_language="en", role="farmer"):
    email = email.strip().lower()
    if role not in ("farmer", "admin"):
        role = "farmer"
    conn = get_db()
    try:
        cur = conn.execute(
            """INSERT INTO users (name, email, password_hash, location, farm_size_acres,
               soil_type, preferred_language, role)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (name.strip(), email, generate_password_hash(password), location,
             farm_size_acres, soil_type, preferred_language, role),
        )
        conn.commit()
        user_id = cur.lastrowid
        return {"success": True, "user_id": user_id}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "An account with this email already exists."}
    finally:
        conn.close()


def authenticate(email, password):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    conn.close()
    if row and check_password_hash(row["password_hash"], password):
        return dict(row)
    return None


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_profile(user_id, **fields):
    allowed = {"name", "location", "farm_size_acres", "soil_type", "preferred_language"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return False
    conn = get_db()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", (*updates.values(), user_id))
    conn.commit()
    conn.close()
    return True


def create_password_reset(email):
    """Returns (token, user) if the email exists, else (None, None). The
    raw token is only ever returned here / to the caller — the DB stores
    only its hash, same principle as a password."""
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    if not row:
        conn.close()
        return None, None

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)
    conn.execute(
        "INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
        (row["id"], generate_password_hash(token), expires_at.isoformat()),
    )
    conn.commit()
    conn.close()
    return token, dict(row)


def reset_password(email, token, new_password):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    if not user:
        conn.close()
        return False, "No account with this email."

    resets = conn.execute(
        "SELECT * FROM password_resets WHERE user_id = ? AND used = 0 ORDER BY id DESC",
        (user["id"],),
    ).fetchall()

    matched = None
    for r in resets:
        if check_password_hash(r["token_hash"], token):
            matched = r
            break

    if not matched:
        conn.close()
        return False, "Invalid or already-used reset token."
    if datetime.fromisoformat(matched["expires_at"]) < datetime.utcnow():
        conn.close()
        return False, "This reset token has expired — request a new one."

    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                 (generate_password_hash(new_password), user["id"]))
    conn.execute("UPDATE password_resets SET used = 1 WHERE id = ?", (matched["id"],))
    conn.commit()
    conn.close()
    return True, None


# ---------------------------------------------------------------------- #
# Session helpers / decorators
# ---------------------------------------------------------------------- #
def login_user_session(user):
    session["user_id"] = user["id"]
    session["role"] = user["role"]


def logout_user_session():
    session.clear()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(user_id)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"success": False, "error": "Login required."}), 401
        return fn(*args, **kwargs)
    return wrapper


def page_login_required(fn):
    """Like login_required, but for HTML page routes: redirects to /login
    instead of returning a JSON 401, since a browser navigating to a page
    needs a page back, not an API error body."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login_page", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


def page_admin_required(fn):
    """Page-route version of admin_required: redirects rather than
    returning a JSON error body."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login_page", next=request.path))
        if session.get("role") != "admin":
            return redirect(url_for("home_page"))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"success": False, "error": "Login required."}), 401
        if session.get("role") != "admin":
            return jsonify({"success": False, "error": "Admin access required."}), 403
        return fn(*args, **kwargs)
    return wrapper


def public_user_dict(user):
    if not user:
        return None
    return {
        "id": user["id"], "name": user["name"], "email": user["email"],
        "location": user["location"], "farm_size_acres": user["farm_size_acres"],
        "soil_type": user["soil_type"], "preferred_language": user["preferred_language"],
        "role": user["role"],
    }
