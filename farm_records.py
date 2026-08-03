"""
farm_records.py
------------------
Persistent, per-user farm records backing the Farm Dashboard. Every number
in here is either something the farmer typed in (expenses, income) or a
real result from one of the app's own real modules, logged automatically
the moment a logged-in user gets a soil-health score, an irrigation
schedule, or a yield prediction. There is no synthetic/demo data — a new
account's dashboard starts empty, same as the app itself would in
production.
"""

import sqlite3
from datetime import datetime

from auth import get_db


def init_farm_tables():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            category TEXT NOT NULL, amount_rs REAL NOT NULL, crop TEXT, note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            amount_rs REAL NOT NULL, crop TEXT, note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS soil_health_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            score INTEGER NOT NULL, n_status TEXT, p_status TEXT, k_status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS water_usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            crop TEXT, total_water_mm REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS yield_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            crop TEXT, area_acres REAL, predicted_yield_tonnes REAL, model_r2 REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def add_expense(user_id, category, amount_rs, crop=None, note=None):
    conn = get_db()
    conn.execute("INSERT INTO expenses (user_id, category, amount_rs, crop, note) VALUES (?, ?, ?, ?, ?)",
                 (user_id, category, amount_rs, crop, note))
    conn.commit()
    conn.close()


def add_income(user_id, amount_rs, crop=None, note=None):
    conn = get_db()
    conn.execute("INSERT INTO income (user_id, amount_rs, crop, note) VALUES (?, ?, ?, ?)",
                 (user_id, amount_rs, crop, note))
    conn.commit()
    conn.close()


def log_soil_health(user_id, score, n_status, p_status, k_status):
    conn = get_db()
    conn.execute("INSERT INTO soil_health_logs (user_id, score, n_status, p_status, k_status) VALUES (?, ?, ?, ?, ?)",
                 (user_id, score, n_status, p_status, k_status))
    conn.commit()
    conn.close()


def log_water_usage(user_id, crop, total_water_mm):
    conn = get_db()
    conn.execute("INSERT INTO water_usage_logs (user_id, crop, total_water_mm) VALUES (?, ?, ?)",
                 (user_id, crop, total_water_mm))
    conn.commit()
    conn.close()


def log_yield_prediction(user_id, crop, area_acres, predicted_yield_tonnes, model_r2):
    conn = get_db()
    conn.execute(
        "INSERT INTO yield_logs (user_id, crop, area_acres, predicted_yield_tonnes, model_r2) VALUES (?, ?, ?, ?, ?)",
        (user_id, crop, area_acres, predicted_yield_tonnes, model_r2),
    )
    conn.commit()
    conn.close()


def _rows(user_id, table, limit=50):
    conn = get_db()
    rows = conn.execute(f"SELECT * FROM {table} WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                         (user_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_dashboard(user_id):
    expenses = _rows(user_id, "expenses")
    income = _rows(user_id, "income")
    soil_logs = _rows(user_id, "soil_health_logs")
    water_logs = _rows(user_id, "water_usage_logs")
    yield_logs = _rows(user_id, "yield_logs")

    total_expenses = round(sum(e["amount_rs"] for e in expenses), 2)
    total_income = round(sum(i["amount_rs"] for i in income), 2)
    expenses_by_category = {}
    for e in expenses:
        expenses_by_category[e["category"]] = expenses_by_category.get(e["category"], 0) + e["amount_rs"]

    return {
        "expenses": expenses, "income": income, "soil_health_logs": soil_logs,
        "water_usage_logs": water_logs, "yield_logs": yield_logs,
        "summary": {
            "total_expenses_rs": total_expenses, "total_income_rs": total_income,
            "net_profit_rs": round(total_income - total_expenses, 2),
            "expenses_by_category": expenses_by_category,
            "records_present": bool(expenses or income or soil_logs or water_logs or yield_logs),
        },
    }
