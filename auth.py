"""
auth.py
-------
Session-based authentication with real password hashing (werkzeug's
scrypt-based hasher — no plaintext or reversible storage) and role-based
access (farmer/admin).

Email (welcome message, password reset codes) is sent for real via SMTP
if SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD are set in .env — see
.env.example for Gmail App Password setup, and scripts/test_email.py to
verify your configuration independent of the web app. Without SMTP
configured, there is no way to actually deliver an email, so the reset
code is returned directly in the API response instead, clearly labeled
as the dev-mode fallback.
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

DB_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "krushi.db"))
RESET_TOKEN_TTL_MINUTES = 30


def email_config_status():
    """Safe to expose publicly — reports WHETHER SMTP is configured and
    which host, never the password. Lets the login page show a real,
    live status instead of the user having to guess whether their .env
    edits actually took effect (a common gotcha: env vars are only read
    once, at server startup — editing .env while the server is running
    does nothing until it's restarted)."""
    host = os.getenv("SMTP_HOST")
    user = os.getenv("SMTP_USER")
    configured = bool(host and os.getenv("SMTP_PORT") and user and os.getenv("SMTP_PASSWORD"))
    return {"configured": configured, "host": host if configured else None,
            "user": user if configured else None}


def send_email(to_email, subject, body):
    """Sends a real email via SMTP if credentials are configured in .env
    (SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD). Returns a dict:
      {"sent": True} on a real successful send
      {"sent": False, "reason": "not_configured"} if SMTP_* isn't set
      {"sent": False, "reason": "error", "detail": "..."} if SMTP is set
        but the send itself failed (bad credentials, blocked port, etc.)
    Callers use "reason" to decide what to tell the user — a real send
    failure is a different, more actionable message than "not configured"."""
    host = os.getenv("SMTP_HOST")
    port = os.getenv("SMTP_PORT")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    from_addr = os.getenv("SMTP_FROM") or user

    if not all([host, port, user, password]):
        return {"sent": False, "reason": "not_configured"}

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_email

        with smtplib.SMTP(host, int(port), timeout=15) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, [to_email], msg.as_string())
        return {"sent": True}
    except Exception as e:
        print(f"[auth] SMTP send failed: {e}")
        return {"sent": False, "reason": "error", "detail": str(e)}


def send_welcome_email(user):
    return send_email(
        user["email"], "Welcome to Krushi 🌱",
        f"Hi {user['name']},\n\n"
        f"Congratulations — your Krushi account has been created successfully!\n\n"
        f"You can now sign in and use the crop advisor, soil health check, market prices, "
        f"irrigation planner, and the rest of the tools.\n\n— Krushi",
    )


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


# Every table that stores a row per-user, deleted alongside the account so
# "delete account" actually removes the person's real data rather than
# leaving orphaned rows behind under a dangling user_id.
_USER_DATA_TABLES = [
    "expenses", "income", "soil_health_logs", "water_usage_logs", "yield_logs",
    "crop_plans", "disease_checks", "fertilizer_usage_logs", "password_resets",
]


def delete_user(user_id):
    """Permanently deletes the account and every real record tied to it.
    Recommendations logged to the shared `recommendations` table are kept
    but anonymized (user_id set to NULL) rather than deleted, since that
    table also backs aggregate app-wide stats (e.g. the admin dashboard's
    'recommendations generated' count) that shouldn't silently drop."""
    conn = get_db()
    for table in _USER_DATA_TABLES:
        conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
    conn.execute("UPDATE recommendations SET user_id = NULL WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def create_password_reset(email):
    """Returns (code, user) if the email exists, else (None, None). The
    raw 6-digit code is only ever returned here / to the caller — the DB
    stores only its hash, same principle as a password."""
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    if not row:
        conn.close()
        return None, None

    code = "".join(secrets.choice("0123456789") for _ in range(6))
    expires_at = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)
    conn.execute(
        "INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
        (row["id"], generate_password_hash(code), expires_at.isoformat()),
    )
    conn.commit()
    conn.close()
    return code, dict(row)


def _find_valid_reset(conn, user_id, code):
    """Shared lookup used by both verify (read-only) and reset (consuming).
    Returns the matching, unexpired, unused password_resets row, or None."""
    resets = conn.execute(
        "SELECT * FROM password_resets WHERE user_id = ? AND used = 0 ORDER BY id DESC",
        (user_id,),
    ).fetchall()
    for r in resets:
        if check_password_hash(r["token_hash"], code) and datetime.fromisoformat(r["expires_at"]) >= datetime.utcnow():
            return r
    return None


def verify_reset_code(email, code):
    """Checks whether a code is valid WITHOUT consuming it — lets the UI
    confirm the code before showing the new-password fields, matching a
    real OTP flow (verify first, only then allow setting a new password)."""
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    if not user:
        conn.close()
        return False, "No account with this email."
    matched = _find_valid_reset(conn, user["id"], code)
    conn.close()
    if not matched:
        return False, "Incorrect or expired code."
    return True, None


def reset_password(email, token, new_password):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    if not user:
        conn.close()
        return False, "No account with this email."

    matched = _find_valid_reset(conn, user["id"], token)
    if not matched:
        conn.close()
        return False, "Incorrect or expired code."

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
