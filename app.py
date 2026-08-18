import json
import os
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

import auth
import db_compat
import farm_records
from admin_tools import (add_custom_disease, add_news, delete_custom_disease, delete_news,
                          get_admin_stats, get_custom_diseases, get_news)
from chat_service import ChatService
from crop_calendar import get_crop_calendar
from disease_reference import DISEASE_REFERENCE, list_symptoms_for_crop, match_disease
from fertilizer_recommendation import get_fertilizer_plan
from knowledge_base import check_eligibility, get_knowledge_base
from location_service import LocationService
from market_service import MarketService
from ml_models import CropRecommendationModel, WaterManagementAdvisor
from notifications import build_notifications
from profit_estimation import estimate_profit
from regional_crops import get_common_crops, is_grown_in_state
from soil_health import analyze_soil
from weather_service import WeatherService
from yield_model import YieldModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(BASE_DIR, ".env")
# Explicit path (not just load_dotenv()'s auto-discovery) so there's no
# ambiguity about which .env gets read regardless of the working directory
# the app happens to be launched from.
load_dotenv(_env_path)

# Startup diagnostic: prints exactly what got picked up from .env, without
# ever printing the password itself. If this doesn't match what you put in
# .env, the file either isn't at BASE_DIR/.env, has a parsing problem
# (stray characters, e.g. an accidentally-pasted markdown code-fence line),
# or you're looking at output from before your last edit — env vars are
# only read once, at process startup, so an edit needs a restart to apply.
if os.path.exists(_env_path):
    _smtp_status = {k: bool(os.getenv(k)) for k in
                     ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD")}
    print(f"[app] Loaded .env from {_env_path}")
    print(f"[app] SMTP env vars detected (True = present, value not shown): {_smtp_status}")
    if not all(_smtp_status.values()):
        _missing = [k for k, present in _smtp_status.items() if not present]
        print(f"[app] SMTP not fully configured — missing/empty: {', '.join(_missing)}. "
              f"Password-reset codes will be shown on-screen instead of emailed until this is fixed. "
              f"Run: python scripts/test_email.py you@example.com for a detailed diagnosis.")
else:
    print(f"[app] No .env file found at {_env_path} — the app will run with defaults "
          f"(no SMTP, no Gemini chat, no live market API). Copy .env.example to .env to configure these.")

app = Flask(__name__)

# Every static asset (CSS/JS) is served with a cache-busting ?v=<mtime>
# query string via the asset_url() Jinja helper below — see there for why.
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


@app.template_global()
def asset_url(path):
    """url_for('static', filename=path) plus a ?v=<mtime> query string, so
    a browser that already cached an old copy of style.css/script.js is
    forced to fetch the new one the moment the file actually changes —
    instead of silently keeping the stale version until a hard refresh.
    Static files don't re-render like Jinja templates do on every request;
    without this, "I applied your fix but the page still looks old" is a
    real, recurring failure mode, not a one-off."""
    full_path = os.path.join(BASE_DIR, "static", path)
    try:
        version = int(os.path.getmtime(full_path))
    except OSError:
        version = 0
    return f"{url_for('static', filename=path)}?v={version}"


# SECRET_KEY: use the env var if set (required for production — without a
# stable key, sessions break on every restart/redeploy and, worse, on a
# multi-process deploy each worker would sign with a different key). If it
# isn't set, generate a random one for this process rather than falling
# back to a fixed, publicly-known default — a hardcoded secret in an
# open-source repo is a real session-forgery hole the moment anyone
# deploys without configuring their own.
_secret_key = os.getenv("SECRET_KEY")
if not _secret_key:
    _secret_key = secrets.token_hex(32)
    print(
        "[app] WARNING: SECRET_KEY not set in .env — using a random key for this process. "
        "Sessions will NOT survive a restart, and this is unsafe for any multi-worker/production "
        "deployment. Set SECRET_KEY in .env (any long random string) before deploying."
    )
app.secret_key = _secret_key

# Session cookie hardening. SESSION_COOKIE_SECURE is opt-in via env rather
# than always-on, because always-on would silently break login on a local
# plain-http dev server; set COOKIE_SECURE=1 once this runs behind HTTPS.
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "0") == "1",
)

# CORS: only allow the configured origin(s) to make credentialed requests,
# rather than reflecting any origin (the effective behavior of enabling
# supports_credentials with no allowlist) — that combination lets any
# website read authenticated responses from a logged-in user's browser.
# Defaults to common local dev origins; set ALLOWED_ORIGINS in .env
# (comma-separated) for anything else, including your real deployed domain.
_allowed_origins = [o.strip() for o in os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:5000,http://127.0.0.1:5000"
).split(",") if o.strip()]
CORS(app, supports_credentials=True, origins=_allowed_origins)

# Rate limiting: protects login/register from brute-force and credential
# stuffing, and protects /api/chat from one user burning through the whole
# app's (usually free-tier, shared) Gemini quota. In-memory storage is
# fine for a single-process dev/small deployment; point REDIS_URL at a
# real store for multi-worker production so limits are shared correctly.
limiter = Limiter(
    get_remote_address, app=app, storage_uri=os.getenv("REDIS_URL", "memory://"),
    default_limits=[], strategy="fixed-window",
)

DB_PATH = os.getenv("DATABASE_PATH", os.path.join(BASE_DIR, "krushi.db"))

# Services -- initialised once at startup. All three ML models train on
# their real bundled datasets the first time the app boots (a few seconds).
crop_model = CropRecommendationModel()
yield_model = YieldModel()
water_advisor = WaterManagementAdvisor()
weather_service = WeatherService(os.getenv("OPENWEATHER_API_KEY"))
market_service = MarketService(os.getenv("MARKET_API_KEY"))
location_service = LocationService()
chat_service = ChatService(os.getenv("GEMINI_API_KEY"), os.getenv("CHAT_MODEL"))

with open(os.path.join(BASE_DIR, "data", "states_districts.json"), encoding="utf-8") as f:
    STATES_DISTRICTS = json.load(f)

SOIL_TYPES = ["Alluvial", "Black (Regur)", "Red", "Laterite", "Arid / Desert",
              "Mountain / Forest", "Saline / Alkaline", "Peaty / Marshy"]
SEASONS = ["Kharif", "Rabi", "Summer", "Whole Year", "Winter", "Autumn"]

UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp"}


@app.context_processor
def inject_user():
    # Every template can reference `user` directly (e.g. base.html's nav),
    # without each view function having to pass it in explicitly.
    return {"user": auth.current_user()}


def init_db():
    # If DATABASE_PATH points at a mounted volume directory that doesn't
    # exist yet on first boot (e.g. a fresh Railway volume), create it
    # rather than fail with a cryptic sqlite3 "unable to open database" —
    # only relevant for SQLite; Postgres (DATABASE_URL) ignores DB_PATH
    # entirely.
    if not db_compat.USING_POSTGRES:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = db_compat.get_connection(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            location TEXT, state TEXT, district TEXT, season TEXT,
            n REAL, p REAL, k REAL, ph REAL,
            temperature REAL, humidity REAL, rainfall REAL,
            top_crop TEXT, confidence REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    auth.init_auth_tables()
    farm_records.init_farm_tables()


def log_recommendation(payload, top_result, user_id=None):
    try:
        conn = db_compat.get_connection(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO recommendations
               (user_id, location, state, district, season, n, p, k, ph,
                temperature, humidity, rainfall, top_crop, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id, payload.get("location"), payload.get("state"), payload.get("district"),
                payload.get("season"), payload.get("n"), payload.get("p"), payload.get("k"),
                payload.get("ph"), payload.get("temperature"), payload.get("humidity"),
                payload.get("rainfall"), top_result.get("crop"), top_result.get("confidence"),
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[app] could not log recommendation: {e}")


# Runs at import time, not just inside `if __name__ == "__main__"` —
# gunicorn (used in production, see Procfile) imports this module and
# calls the `app` object directly, so it never executes that block.
# Without this being here, unconditionally, the database tables are
# never created in production and every query 500s with "relation does
# not exist" — found exactly that way deploying this to Render.
init_db()


# ========================================================================= #
# Pages — every feature lives on its own route now, and every page except
# /login requires a signed-in session (auth.page_login_required redirects
# to /login instead of the app.py silently rendering nothing).
# ========================================================================= #
@app.route("/")
def root():
    return redirect(url_for("home_page") if session.get("user_id") else url_for("login_page"))


@app.route("/login")
def login_page():
    if session.get("user_id"):
        return redirect(url_for("home_page"))
    return render_template("login.html")


@app.route("/home")
@auth.page_login_required
def home_page():
    return render_template("home.html")


@app.route("/profile")
@auth.page_login_required
def profile_page():
    return render_template("profile.html")


@app.route("/recommend")
@auth.page_login_required
def recommend_page():
    return render_template("recommend.html")


@app.route("/soil")
@auth.page_login_required
def soil_page():
    return render_template("soil.html")


@app.route("/yield")
@auth.page_login_required
def yield_page():
    return render_template("yield.html")


@app.route("/market")
@auth.page_login_required
def market_page():
    return render_template("market.html")


@app.route("/fertilizer")
@auth.page_login_required
def fertilizer_page():
    return render_template("fertilizer.html")


@app.route("/profit")
@auth.page_login_required
def profit_page():
    return render_template("profit.html")


@app.route("/disease")
@auth.page_login_required
def disease_page():
    return render_template("disease.html")


@app.route("/water")
@auth.page_login_required
def water_page():
    return render_template("water.html")


@app.route("/calendar")
@auth.page_login_required
def calendar_page():
    return render_template("calendar.html")


@app.route("/dashboard")
@auth.page_login_required
def dashboard_page():
    return render_template("dashboard.html")


@app.route("/map")
@auth.page_login_required
def map_page():
    return render_template("map.html")


@app.route("/knowledge")
@auth.page_login_required
def knowledge_page():
    return render_template("knowledge.html")


@app.route("/about")
@auth.page_login_required
def about_page():
    return render_template("about.html")


@app.route("/chat")
@auth.page_login_required
def chat_page():
    return render_template("chat.html")


@app.route("/records")
@auth.page_login_required
def records_page():
    return render_template("records.html")


@app.route("/analytics")
@auth.page_login_required
def analytics_page():
    return render_template("analytics.html")


@app.route("/admin")
@auth.page_admin_required
def admin_page():
    return render_template("admin.html")


# ========================================================================= #
# Core data endpoints (still require login — see note above)
# ========================================================================= #
@app.route("/api/model-info")
@auth.login_required
def model_info():
    return jsonify({
        "success": True,
        "crop_model": crop_model.get_model_info(),
        "yield_model": yield_model.get_model_info(),
        "market_model": market_service.get_model_info(),
    })


@app.route("/api/reference-data")
def reference_data():
    return jsonify({
        "success": True,
        "states": sorted(STATES_DISTRICTS.keys()),
        "districts_by_state": STATES_DISTRICTS,
        "soil_types": SOIL_TYPES,
        "seasons": SEASONS,
        "languages": [
            {"code": "en", "label": "English"}, {"code": "hi", "label": "Hindi"},
            {"code": "kn", "label": "Kannada"}, {"code": "mr", "label": "Marathi"},
            {"code": "ta", "label": "Tamil"}, {"code": "te", "label": "Telugu"},
        ],
    })


@app.route("/api/regional-crops")
@auth.login_required
def regional_crops_route():
    """Real crops grown in a given state, from government production
    records — covers 49 real crops (sugarcane, tobacco, jowar, bajra,
    ragi, groundnut, wheat, onion, and more), not just the 22 the
    N/P/K soil-based model knows. See regional_crops.py for why this is
    a real ranked list, not a trained confidence score."""
    state = request.args.get("state", "")
    return jsonify({"success": True, "result": get_common_crops(state, top_n=int(request.args.get("top_n", 15)))})


# ========================================================================= #
# Auth (these stay public — they're how you get a session in the first place)
# ========================================================================= #
@app.route("/api/auth/register", methods=["POST"])
@limiter.limit("8 per hour")
def register():
    data = request.json or {}
    name, email, password = data.get("name", "").strip(), data.get("email", "").strip(), data.get("password", "")
    if not name or not email or not password:
        return jsonify({"success": False, "error": "name, email and password are required."}), 400
    if len(password) < 8:
        return jsonify({"success": False, "error": "Password must be at least 8 characters."}), 400

    result = auth.register_user(
        name=name, email=email, password=password,
        location=data.get("location"), farm_size_acres=data.get("farm_size_acres"),
        soil_type=data.get("soil_type"), preferred_language=data.get("preferred_language", "en"),
        role="farmer",  # public registration can NEVER self-assign a role — admin accounts are
                        # created only via scripts/create_admin.py (see README), run by whoever
                        # controls the server, not by anyone who can hit this API.
    )
    if not result["success"]:
        return jsonify(result), 409

    user = auth.get_user_by_id(result["user_id"])
    auth.login_user_session(user)
    email_result = auth.send_welcome_email(user)
    return jsonify({
        "success": True, "user": auth.public_user_dict(user),
        "welcome_email_sent": email_result["sent"],
    })


@app.route("/api/auth/login", methods=["POST"])
@limiter.limit("15 per minute")
def login():
    data = request.json or {}
    user = auth.authenticate(data.get("email", ""), data.get("password", ""))
    if not user:
        return jsonify({"success": False, "error": "Invalid email or password."}), 401
    auth.login_user_session(user)
    return jsonify({"success": True, "user": auth.public_user_dict(user)})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    auth.logout_user_session()
    return jsonify({"success": True})


@app.route("/api/auth/me")
def me():
    user = auth.current_user()
    return jsonify({"success": True, "user": auth.public_user_dict(user)})


@app.route("/api/auth/profile", methods=["PUT"])
@auth.login_required
def update_profile():
    data = request.json or {}
    auth.update_profile(
        session["user_id"], name=data.get("name"), location=data.get("location"),
        farm_size_acres=data.get("farm_size_acres"), soil_type=data.get("soil_type"),
        preferred_language=data.get("preferred_language"),
    )
    user = auth.get_user_by_id(session["user_id"])
    return jsonify({"success": True, "user": auth.public_user_dict(user)})


@app.route("/api/auth/delete-account", methods=["POST"])
@auth.login_required
def delete_account():
    data = request.json or {}
    user = auth.get_user_by_id(session["user_id"])
    if not check_password_hash(user["password_hash"], data.get("password", "")):
        return jsonify({"success": False, "error": "Incorrect password."}), 401

    auth.delete_user(user["id"])
    auth.logout_user_session()
    return jsonify({"success": True})


@app.route("/api/auth/email-status")
def email_status():
    return jsonify({"success": True, **auth.email_config_status()})


@app.route("/api/auth/forgot-password", methods=["POST"])
@limiter.limit("5 per hour")
def forgot_password():
    data = request.json or {}
    email = data.get("email", "")
    code, user = auth.create_password_reset(email)
    if not code:
        # Don't reveal whether the email exists -- standard practice.
        return jsonify({"success": True, "message": "If that email has an account, a code has been sent to it."})

    result = auth.send_email(
        user["email"], "Your Krushi password reset code",
        f"Hi {user['name']},\n\nYour Krushi password reset code is: {code}\n\n"
        f"This code expires in {auth.RESET_TOKEN_TTL_MINUTES} minutes and can only be used once.\n\n"
        f"If you didn't request this, you can ignore this email — your password won't change.",
    )

    if result["sent"]:
        return jsonify({"success": True, "email_sent": True,
                         "message": f"A 6-digit code has been sent to {user['email']}. Enter it below."})

    if result["reason"] == "error":
        # SMTP IS configured but the send itself failed — tell the truth
        # about that instead of pretending it worked, and still hand back
        # the code so the person isn't stuck.
        return jsonify({
            "success": True, "email_sent": False,
            "message": f"Email sending failed ({result['detail']}) — here is the code directly instead.",
            "reset_token": code, "expires_in_minutes": auth.RESET_TOKEN_TTL_MINUTES,
        })

    return jsonify({
        "success": True, "email_sent": False,
        "message": "No email service is configured (SMTP_* vars empty in .env), so here is the code "
                    "directly instead of emailing it. Set up SMTP in .env to send it for real.",
        "reset_token": code,
        "expires_in_minutes": auth.RESET_TOKEN_TTL_MINUTES,
    })


@app.route("/api/auth/verify-reset-code", methods=["POST"])
@limiter.limit("10 per hour")
def verify_reset_code():
    data = request.json or {}
    ok, error = auth.verify_reset_code(data.get("email", ""), data.get("token", ""))
    if not ok:
        return jsonify({"success": False, "error": error}), 400
    return jsonify({"success": True})


@app.route("/api/auth/reset-password", methods=["POST"])
@limiter.limit("10 per hour")
def reset_password_route():
    data = request.json or {}
    ok, error = auth.reset_password(data.get("email", ""), data.get("token", ""), data.get("new_password", ""))
    if not ok:
        return jsonify({"success": False, "error": error}), 400
    return jsonify({"success": True})


@app.route("/api/admin/users")
@auth.admin_required
def admin_users():
    conn = auth.get_db()
    rows = conn.execute("SELECT id, name, email, location, role, created_at FROM users").fetchall()
    conn.close()
    conn2 = db_compat.get_connection(DB_PATH)
    total_recs = conn2.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]
    conn2.close()
    return jsonify({
        "success": True,
        "users": [dict(r) for r in rows],
        "stats": {"total_users": len(rows), "total_recommendations_generated": total_recs},
    })


@app.route("/api/admin/stats")
@auth.admin_required
def admin_stats():
    return jsonify({"success": True, "stats": get_admin_stats()})


@app.route("/api/admin/crops")
@auth.admin_required
def admin_crops():
    """Read-only view of the crop model's training coverage — 'managing
    crops' here means seeing what the model actually knows, not editing
    live ML training data through a form."""
    return jsonify({
        "success": True,
        "crop_model": crop_model.get_model_info(),
        "yield_model_crops": yield_model.get_model_info()["covered_crops"],
        "market_model_crops": market_service.get_model_info()["covered_crops"],
    })


@app.route("/api/admin/weather-status")
@auth.admin_required
def admin_weather_status():
    """A live diagnostic call so the admin can see the weather pipeline is
    actually working, not a static status flag."""
    try:
        sample = weather_service.get_current_weather("Delhi")
        return jsonify({"success": True, "sample": sample,
                         "openweather_key_configured": bool(os.getenv("OPENWEATHER_API_KEY"))})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/news", methods=["GET", "POST"])
@auth.admin_required
def admin_news():
    if request.method == "POST":
        data = request.json or {}
        add_news(session["user_id"], data.get("title", ""), data.get("body", ""))
        return jsonify({"success": True})
    return jsonify({"success": True, "news": get_news()})


@app.route("/api/admin/news/<int:news_id>", methods=["DELETE"])
@auth.admin_required
def admin_delete_news(news_id):
    delete_news(news_id)
    return jsonify({"success": True})


@app.route("/api/news")
@auth.login_required
def public_news():
    """Same announcements, read-only, for the farmer-facing home page."""
    return jsonify({"success": True, "news": get_news(limit=5)})


@app.route("/api/admin/disease-database", methods=["GET", "POST"])
@auth.admin_required
def admin_disease_database():
    if request.method == "POST":
        data = request.json or {}
        add_custom_disease(
            session["user_id"], data.get("crop", ""), data.get("disease", ""),
            data.get("symptoms", []), data.get("cause", ""), data.get("treatment", ""),
            data.get("recommended_fungicide", ""),
        )
        return jsonify({"success": True})
    return jsonify({"success": True, "static_reference": DISEASE_REFERENCE,
                     "custom_entries": get_custom_diseases()})


@app.route("/api/admin/disease-database/<int:entry_id>", methods=["DELETE"])
@auth.admin_required
def admin_delete_disease(entry_id):
    delete_custom_disease(entry_id)
    return jsonify({"success": True})


# ========================================================================= #
# Location
# ========================================================================= #
@app.route("/api/reverse-geocode")
@auth.login_required
def reverse_geocode():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "lat and lon query params are required"}), 400

    result = location_service.reverse_geocode(lat, lon)
    notes = location_service.get_region_notes(result["location_string"])
    return jsonify({"success": True, **result, "region_notes": notes})


@app.route("/api/detect-location")
@auth.login_required
def detect_location():
    try:
        loc = location_service.get_location_from_ip()
        if loc:
            notes = location_service.get_region_notes(loc["location_string"])
            return jsonify({"success": True, "location": loc["location_string"],
                             "lat": loc["lat"], "lon": loc["lon"], "region_notes": notes,
                             "accuracy_warning": "Estimated from your network address — this can be "
                                                  "off by a large distance, especially on mobile data. "
                                                  "Allow location access for an accurate GPS-based result."})
        return jsonify({"success": False, "error": "Could not detect location automatically. "
                                                     "Please enter it manually."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ========================================================================= #
# Weather
# ========================================================================= #
def _weather_payload(current, forecast):
    return {"success": True, "current": current, "forecast": forecast,
            "alerts": weather_service.get_alerts(forecast)}


@app.route("/api/weather/<location>")
@auth.login_required
def get_weather(location):
    try:
        current = weather_service.get_current_weather(location)
        forecast = weather_service.get_forecast(location)
        return jsonify(_weather_payload(current, forecast))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/weather-by-coords")
@auth.login_required
def get_weather_by_coords():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
        label = request.args.get("label")
        current = weather_service.get_current_weather_by_coords(lat, lon, label)
        forecast = weather_service.get_forecast_by_coords(lat, lon)
        return jsonify(_weather_payload(current, forecast))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "lat and lon query params are required"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ========================================================================= #
# Crop recommendation
# ========================================================================= #
@app.route("/api/recommend-crops", methods=["POST"])
@auth.login_required
def recommend_crops():
    try:
        data = request.json or {}
        location = data.get("location", "")
        state = data.get("state")
        district = data.get("district")
        season = data.get("season")
        lat, lon = data.get("lat"), data.get("lon")

        n = float(data.get("n", 50))
        p = float(data.get("p", 50))
        k = float(data.get("k", 50))
        ph = float(data.get("ph", 6.5))

        temperature = data.get("temperature")
        humidity = data.get("humidity")
        rainfall = data.get("rainfall")

        weather_data = None
        if temperature is None or humidity is None or rainfall is None:
            if lat is not None and lon is not None:
                weather_data = weather_service.get_current_weather_by_coords(
                    float(lat), float(lon), label=location or None
                )
            else:
                weather_data = weather_service.get_current_weather(location or state or "Delhi")
            temperature = temperature if temperature is not None else weather_data.get("temperature", 25)
            humidity = humidity if humidity is not None else weather_data.get("humidity", 60)
            rainfall = rainfall if rainfall is not None else weather_data.get("rainfall", 100)

        rainfall_mm = float(rainfall) if float(rainfall) > 5 else float(rainfall) * 30

        # The crop model itself has NO location input — it's trained purely
        # on N/P/K/temperature/humidity/pH/rainfall (see ml_models.py), so
        # two farmers in different states with the same soil numbers would
        # otherwise get an identical list regardless of state. When a state
        # is given, pull more candidates than we need and re-rank using
        # real historical state-level crop production records
        # (regional_crops.py), instead of leaving state purely decorative.
        fetch_n = 12 if state else 6
        recommendations = crop_model.recommend_crops(
            n=n, p=p, k=k, temperature=float(temperature), humidity=float(humidity),
            ph=ph, rainfall=rainfall_mm, top_n=fetch_n,
        )

        for rec in recommendations:
            rec["yield_estimate"] = yield_model.get_expected_yield(
                rec["crop"], state=state, season=season, rainfall=rainfall_mm, temperature=float(temperature)
            )
            rec["season_match"] = (
                season is not None and season.strip().lower() in rec.get("season", "").lower()
            ) if season else None
            rec["regionally_grown"] = is_grown_in_state(rec["crop"], state) if state else None

        # market_estimate is the one network-hitting call per crop (yield
        # is a local model lookup) — run these concurrently instead of one
        # at a time, so a slow/unreachable live price API costs one wait,
        # not one wait PER recommended crop.
        with ThreadPoolExecutor(max_workers=len(recommendations)) as pool:
            market_results = pool.map(
                lambda rec: market_service.get_price_estimate(rec["crop"], state=state), recommendations
            )
        for rec, market_estimate in zip(recommendations, market_results):
            rec["market_estimate"] = market_estimate

        if state:
            # Only a CONFIRMED real match (True) gets bubbled up. None and
            # False are deliberately tied at the same tier and keep their
            # original model-confidence order — the data has real gaps
            # (e.g. Rajasthan is entirely absent from this dataset), so
            # treating "no record" as equivalent to "actively worse" would
            # bury good, high-confidence picks under a data-completeness
            # artifact rather than a real regional signal.
            tier = {True: 0, None: 1, False: 1}
            recommendations.sort(key=lambda r: tier[r["regionally_grown"]])
        recommendations = recommendations[:6]

        recommendations = _add_profitability(recommendations)

        user = auth.current_user()
        if recommendations:
            log_recommendation(
                {"location": location, "state": state, "district": district, "season": season,
                 "n": n, "p": p, "k": k, "ph": ph, "temperature": temperature, "humidity": humidity,
                 "rainfall": rainfall},
                recommendations[0], user_id=user["id"] if user else None,
            )

        return jsonify({
            "success": True,
            "recommendations": recommendations,
            "weather": weather_data,
            "model": crop_model.get_model_info(),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def _add_profitability(recommendations):
    """Profitability is estimated revenue potential (expected yield x
    predicted price), ranked RELATIVE to the other recommended crops in
    this same response. It's explicitly revenue, not net profit -- there's
    no real cost-of-cultivation dataset behind this app, so subtracting
    costs would mean inventing numbers. Only crops with BOTH a real yield
    estimate and a real price estimate get a rating; others say so."""
    revenues = []
    for rec in recommendations:
        yld = rec["yield_estimate"]
        mkt = rec["market_estimate"]
        if yld.get("covered") and mkt.get("covered"):
            revenue_per_ha = yld["predicted_yield_tonnes_per_ha"] * 10 * mkt["predicted_modal_price"]
            rec["_revenue_per_ha_rs"] = revenue_per_ha
            revenues.append(revenue_per_ha)
        else:
            rec["_revenue_per_ha_rs"] = None

    if len(revenues) >= 2:
        sorted_rev = sorted(revenues, reverse=True)
        hi_cut = sorted_rev[max(0, len(sorted_rev) // 3 - 1)]
        lo_cut = sorted_rev[min(len(sorted_rev) - 1, (2 * len(sorted_rev)) // 3)]
        for rec in recommendations:
            rev = rec["_revenue_per_ha_rs"]
            if rev is None:
                rec["profitability"] = {"covered": False,
                                         "message": "Needs both a real yield estimate and a real price "
                                                     "estimate for this crop — not available for all crops yet."}
            else:
                rating = "High" if rev >= hi_cut else ("Low" if rev <= lo_cut else "Medium")
                rec["profitability"] = {"covered": True, "rating": rating,
                                         "estimated_revenue_per_ha_rs": round(rev, 0),
                                         "basis": "expected yield x predicted price (revenue, not net profit — "
                                                   "cultivation costs are not modeled)"}
        for rec in recommendations:
            rec.pop("_revenue_per_ha_rs", None)
    else:
        for rec in recommendations:
            rec["profitability"] = {"covered": False,
                                     "message": "Not enough recommended crops with both real yield and "
                                                 "price data to compare profitability."}
            rec.pop("_revenue_per_ha_rs", None)
    return recommendations


# ========================================================================= #
# Soil health
# ========================================================================= #
@app.route("/api/soil-health", methods=["POST"])
@auth.login_required
def soil_health():
    try:
        data = request.json or {}
        result = analyze_soil(
            n=float(data.get("n", 0)), p=float(data.get("p", 0)), k=float(data.get("k", 0)),
            ph=float(data.get("ph", 6.5)),
            organic_carbon=float(data["organic_carbon"]) if data.get("organic_carbon") not in (None, "") else None,
        )
        user = auth.current_user()
        if user:
            farm_records.log_soil_health(user["id"], result["soil_health_score"],
                                          result["nitrogen_status"], result["phosphorus_status"],
                                          result["potassium_status"])
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ========================================================================= #
# Irrigation
# ========================================================================= #
@app.route("/api/water-management", methods=["POST"])
@auth.login_required
def water_management():
    try:
        data = request.json or {}
        crop_type = data.get("crop_type")
        soil_type = data.get("soil_type")
        location = data.get("location")
        lat, lon = data.get("lat"), data.get("lon")

        if lat is not None and lon is not None:
            weather_forecast = weather_service.get_forecast_by_coords(float(lat), float(lon))
        else:
            weather_forecast = weather_service.get_forecast(location or "Delhi")

        advice = water_advisor.get_irrigation_advice(
            crop_type=crop_type, soil_type=soil_type, weather_forecast=weather_forecast
        )
        summary = _irrigation_summary(advice["irrigation_schedule"])
        user = auth.current_user()
        if user:
            total_mm = sum(d["water_amount_mm"] for d in advice["irrigation_schedule"])
            farm_records.log_water_usage(user["id"], crop_type, round(total_mm, 1))
        return jsonify({"success": True, "advice": advice, "forecast": weather_forecast,
                         "summary": summary,
                         "alerts": weather_service.get_alerts(weather_forecast)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def _irrigation_summary(schedule):
    """The single-line 'Water Required: 18mm / Next Irrigation: after 3
    days' headline — derived from the same schedule already computed, not
    a separate calculation."""
    next_day = next((d for d in schedule if d["irrigation_needed"]), None)
    if not next_day:
        return {"water_required_mm": 0, "next_irrigation_in_days": None,
                "message": "No irrigation needed in the next 7 days based on the forecast."}
    return {
        "water_required_mm": next_day["water_amount_mm"],
        "next_irrigation_in_days": next_day["day"],
        "message": f"{next_day['water_amount_mm']}mm required — next irrigation in "
                   f"{next_day['day']} day{'s' if next_day['day'] != 1 else ''}.",
    }


# ========================================================================= #
# Market
# ========================================================================= #
@app.route("/api/market-trends/<crop>")
@auth.login_required
def get_market_trends(crop):
    try:
        state = request.args.get("state")
        estimate = market_service.get_price_estimate(crop, state=state)
        return jsonify({"success": True, "estimate": estimate})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/market-prices/<crop>")
@auth.login_required
def get_market_prices(crop):
    try:
        state = request.args.get("state")
        result = market_service.get_market_prices(crop, state=state)
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/market-nearby/<crop>")
@auth.login_required
def get_market_nearby(crop):
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
        result = market_service.get_nearby_markets(crop, lat, lon)
        return jsonify({"success": True, "result": result})
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "lat and lon query params are required"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ========================================================================= #
# Fertilizer recommendation
# ========================================================================= #
@app.route("/api/fertilizer-plan", methods=["POST"])
@auth.login_required
def fertilizer_plan():
    try:
        data = request.json or {}
        result = get_fertilizer_plan(data.get("crop", ""), area_acres=float(data.get("area_acres", 1.0)))
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ========================================================================= #
# Crop calendar
# ========================================================================= #
@app.route("/api/crop-calendar", methods=["POST"])
@auth.login_required
def crop_calendar():
    try:
        data = request.json or {}
        crop = data.get("crop", "")
        sowing_date_str = data.get("sowing_date")
        sowing_date = (
            datetime.strptime(sowing_date_str, "%Y-%m-%d").date() if sowing_date_str else date.today()
        )
        profile = water_advisor.irrigation_profiles.get(
            crop.strip().lower(), water_advisor.default_profile
        )
        result = get_crop_calendar(crop, sowing_date, irrigation_interval_days=profile["interval_days"])

        user = auth.current_user()
        if user and result.get("covered") and result.get("type") == "annual":
            farm_records.save_crop_plan(
                user["id"], result["crop"], result["sowing_date"], result["expected_harvest_date"],
                json.dumps(result["events"]),
            )
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ========================================================================= #
# Disease reference (symptom-based, NOT image AI — see disease_reference.py)
# ========================================================================= #
@app.route("/api/disease-symptoms/<crop>")
@auth.login_required
def disease_symptoms(crop):
    return jsonify({"success": True, "result": list_symptoms_for_crop(crop, extra_diseases=get_custom_diseases(crop))})


@app.route("/api/disease-check", methods=["POST"])
@auth.login_required
def disease_check():
    try:
        data = request.json or {}
        crop = data.get("crop", "")
        result = match_disease(crop, data.get("symptoms", []), extra_diseases=get_custom_diseases(crop))

        user = auth.current_user()
        if user and result.get("covered") and result.get("matches"):
            farm_records.log_disease_check(user["id"], result["crop"], result["matches"][0]["disease"])
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/disease-photo", methods=["POST"])
@auth.login_required
def disease_photo():
    """Stores an uploaded/captured leaf photo for the farmer's own record.
    It is NOT analyzed — see disease_reference.py for why there's no real
    image classifier wired up here."""
    if "photo" not in request.files:
        return jsonify({"success": False, "error": "No photo file provided."}), 400
    file = request.files["photo"]
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_IMAGE_EXT:
        return jsonify({"success": False, "error": f"Unsupported file type: {ext}"}), 400

    filename = secure_filename(f"{uuid.uuid4().hex}.{ext}")
    file.save(os.path.join(UPLOAD_DIR, filename))
    return jsonify({"success": True, "url": f"/static/uploads/{filename}",
                     "note": "Saved for your own reference — not analyzed by any image model."})


# ========================================================================= #
# Standalone yield prediction
# ========================================================================= #
@app.route("/api/yield-prediction", methods=["POST"])
@auth.login_required
def yield_prediction():
    try:
        data = request.json or {}
        crop = data.get("crop", "")
        area_acres = float(data.get("area_acres", 1))
        state = data.get("state")
        season = data.get("season")
        rainfall = data.get("rainfall")
        temperature = data.get("temperature")

        result = yield_model.get_expected_yield(
            crop, state=state, season=season,
            rainfall=float(rainfall) if rainfall not in (None, "") else None,
            temperature=float(temperature) if temperature not in (None, "") else None,
        )
        if result.get("covered"):
            area_ha = area_acres * 0.404686
            total_tonnes = round(result["predicted_yield_tonnes_per_ha"] * area_ha, 2)
            result["area_acres"] = area_acres
            result["total_expected_yield_tonnes"] = total_tonnes
            result["accuracy_pct_note"] = "This is the model's held-out R\u00b2 expressed as a " \
                                            "percentage, not classification accuracy — see README."

            user = auth.current_user()
            if user:
                farm_records.log_yield_prediction(user["id"], crop, area_acres, total_tonnes,
                                                    result["test_r2"])
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ========================================================================= #
# Profit estimation
# ========================================================================= #
@app.route("/api/profit-estimation", methods=["POST"])
@auth.login_required
def profit_estimation_route():
    try:
        data = request.json or {}
        crop = data.get("crop", "")
        area_acres = float(data.get("area_acres", 1))
        state = data.get("state")
        season = data.get("season")

        yield_est = yield_model.get_expected_yield(crop, state=state, season=season)
        price_est = market_service.get_price_estimate(crop, state=state)

        result = estimate_profit(
            area_acres=area_acres, expenses=data.get("expenses", {}),
            yield_estimate=yield_est, price_estimate=price_est,
            manual_price_rs_per_quintal=data.get("manual_price_rs_per_quintal"),
        )
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ========================================================================= #
# Farm records / dashboard
# ========================================================================= #
@app.route("/api/farm/expense", methods=["POST"])
@auth.login_required
def add_expense():
    data = request.json or {}
    farm_records.add_expense(session["user_id"], data.get("category", "other"),
                              float(data.get("amount_rs", 0)), data.get("crop"), data.get("note"))
    return jsonify({"success": True})


@app.route("/api/farm/expense/<int:record_id>", methods=["PUT"])
@auth.login_required
def update_expense_route(record_id):
    data = request.json or {}
    ok = farm_records.update_expense(session["user_id"], record_id, data.get("category", "other"),
                                      float(data.get("amount_rs", 0)), data.get("crop"), data.get("note"))
    if not ok:
        return jsonify({"success": False, "error": "Record not found."}), 404
    return jsonify({"success": True})


@app.route("/api/farm/expense/<int:record_id>", methods=["DELETE"])
@auth.login_required
def delete_expense_route(record_id):
    ok = farm_records.delete_expense(session["user_id"], record_id)
    if not ok:
        return jsonify({"success": False, "error": "Record not found."}), 404
    return jsonify({"success": True})


@app.route("/api/farm/income", methods=["POST"])
@auth.login_required
def add_income():
    data = request.json or {}
    farm_records.add_income(session["user_id"], float(data.get("amount_rs", 0)),
                             data.get("crop"), data.get("note"))
    return jsonify({"success": True})


@app.route("/api/farm/income/<int:record_id>", methods=["PUT"])
@auth.login_required
def update_income_route(record_id):
    data = request.json or {}
    ok = farm_records.update_income(session["user_id"], record_id, float(data.get("amount_rs", 0)),
                                     data.get("crop"), data.get("note"))
    if not ok:
        return jsonify({"success": False, "error": "Record not found."}), 404
    return jsonify({"success": True})


@app.route("/api/farm/income/<int:record_id>", methods=["DELETE"])
@auth.login_required
def delete_income_route(record_id):
    ok = farm_records.delete_income(session["user_id"], record_id)
    if not ok:
        return jsonify({"success": False, "error": "Record not found."}), 404
    return jsonify({"success": True})


@app.route("/api/farm/dashboard")
@auth.login_required
def farm_dashboard():
    return jsonify({"success": True, "dashboard": farm_records.get_dashboard(session["user_id"])})


@app.route("/api/farm/records")
@auth.login_required
def farm_records_route():
    return jsonify({"success": True, "records": farm_records.get_farm_records(session["user_id"])})


@app.route("/api/farm/fertilizer-usage", methods=["POST"])
@auth.login_required
def add_fertilizer_usage_route():
    data = request.json or {}
    farm_records.add_fertilizer_usage(
        session["user_id"], data.get("crop"), data.get("fertilizer", ""),
        float(data.get("quantity_kg", 0)) if data.get("quantity_kg") else None,
        data.get("applied_on"), data.get("note"),
    )
    return jsonify({"success": True})


@app.route("/api/farm/fertilizer-usage/<int:record_id>", methods=["PUT"])
@auth.login_required
def update_fertilizer_usage_route(record_id):
    data = request.json or {}
    ok = farm_records.update_fertilizer_usage(
        session["user_id"], record_id, data.get("crop"), data.get("fertilizer", ""),
        float(data.get("quantity_kg", 0)) if data.get("quantity_kg") else None,
        data.get("applied_on"), data.get("note"),
    )
    if not ok:
        return jsonify({"success": False, "error": "Record not found."}), 404
    return jsonify({"success": True})


@app.route("/api/farm/fertilizer-usage/<int:record_id>", methods=["DELETE"])
@auth.login_required
def delete_fertilizer_usage_route(record_id):
    ok = farm_records.delete_fertilizer_usage(session["user_id"], record_id)
    if not ok:
        return jsonify({"success": False, "error": "Record not found."}), 404
    return jsonify({"success": True})


@app.route("/api/farm/analytics")
@auth.login_required
def farm_analytics():
    period = request.args.get("period", "monthly")
    if period not in ("monthly", "yearly"):
        period = "monthly"
    return jsonify({"success": True, "analytics": farm_records.get_analytics(session["user_id"], period)})


# ========================================================================= #
# Knowledge base
# ========================================================================= #
@app.route("/api/knowledge-base")
@auth.login_required
def knowledge_base():
    return jsonify({"success": True, "result": get_knowledge_base()})


@app.route("/api/schemes/eligibility", methods=["POST"])
@auth.login_required
def schemes_eligibility():
    data = request.json or {}
    result = check_eligibility(
        owns_land=bool(data.get("owns_land")), grows_notified_crop=bool(data.get("grows_notified_crop")),
        income_tax_payer=bool(data.get("income_tax_payer")),
        government_employee=bool(data.get("government_employee")),
    )
    return jsonify({"success": True, "result": result})


# ========================================================================= #
# Smart notifications
# ========================================================================= #
@app.route("/api/notifications")
@auth.login_required
def notifications():
    user = auth.current_user()
    lat, lon = request.args.get("lat"), request.args.get("lon")

    forecast = None
    try:
        if lat and lon:
            forecast = weather_service.get_forecast_by_coords(float(lat), float(lon))
        elif user and user.get("location"):
            forecast = weather_service.get_forecast(user["location"])
    except Exception:
        forecast = None

    crop_plans = farm_records.get_active_crop_plans(user["id"])
    latest_match = farm_records.get_latest_disease_check(user["id"])

    notifs = build_notifications(crop_plans, forecast, latest_disease_match=latest_match)
    return jsonify({"success": True, "notifications": notifs})


# ========================================================================= #
# AI chatbot (real Google Gemini API call — see chat_service.py)
# ========================================================================= #
@app.route("/api/chat", methods=["POST"])
@auth.login_required
@limiter.limit("20 per hour")
def chat():
    data = request.json or {}
    result = chat_service.send_message(data.get("message", ""), history=data.get("history", []))
    return jsonify(result)


if __name__ == "__main__":
    # debug mode is opt-in via env, not hardcoded — Flask's debug mode
    # exposes an interactive in-browser debugger that lets anyone who can
    # trigger an unhandled exception execute arbitrary Python on the
    # server. Fine for local development (set FLASK_DEBUG=1), never safe
    # to leave on for anything reachable outside your own machine.
    # use_reloader=False: the debug reloader watches the whole project
    # directory, including krushi.db — every recommendation/login write to
    # that SQLite file was triggering a full server restart mid-session.
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, use_reloader=False, host="0.0.0.0", port=5000)
