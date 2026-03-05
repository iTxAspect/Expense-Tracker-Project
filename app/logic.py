"""
logic.py — Business logic layer for Expense Tracker
Handles: auth (login/register/logout), validation, formatting,
         expense operations, stats, budget management.
Session state is kept in this module (current_user dict).
"""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, date
import database as db


# ── Session State ─────────────────────────────────────────────────────────────
# Single in-memory session. On Android the process lives as long as the app.
current_user: dict | None = None


# ── Password Hashing (PBKDF2-HMAC-SHA256, no external deps) ──────────────────

def _hash_password(plain: str, salt: str = None) -> str:
    """Return 'salt$hash' string. Generate new salt when salt is None."""
    if salt is None:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256", plain.encode("utf-8"), salt.encode("utf-8"),
        iterations=260_000
    )
    return f"{salt}${key.hex()}"


def _verify_password(plain: str, stored: str) -> bool:
    """Verify a plain password against a stored 'salt$hash' string."""
    try:
        salt, _ = stored.split("$", 1)
        return hmac.compare_digest(stored, _hash_password(plain, salt))
    except Exception:
        return False


# ── Auth ──────────────────────────────────────────────────────────────────────

def register(username: str, password: str, role: str = "user"):
    """
    Register a new user. Returns (True, user_dict) or (False, error_msg).
    Role 'admin' can only be set by an existing admin or during first-run seed.
    """
    if not username or not username.strip():
        return False, "Username cannot be empty."
    if len(username.strip()) < 3:
        return False, "Username must be at least 3 characters."
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters."
    if role not in ("user", "admin"):
        return False, "Invalid role."

    hashed = _hash_password(password)
    uid    = db.create_user(username.strip(), hashed, role)
    if uid is None:
        return False, "Username already taken."
    user = db.get_user_by_id(uid)
    return True, user


def login(username: str, password: str):
    """
    Authenticate. Returns (True, user_dict) or (False, error_msg).
    Sets global current_user on success.
    """
    global current_user
    if not username or not password:
        return False, "Username and password are required."
    user = db.get_user_by_username(username)
    if not user:
        return False, "User not found."
    if not _verify_password(password, user["password"]):
        return False, "Incorrect password."
    current_user = user
    return True, user


def logout():
    global current_user
    current_user = None


def get_current_user() -> dict | None:
    return current_user


def is_admin() -> bool:
    return current_user is not None and current_user["role"] == "admin"


def is_logged_in() -> bool:
    return current_user is not None


def _uid():
    """Return current user's id, or None (admin sees all)."""
    if current_user is None:
        return None
    return None if is_admin() else current_user["id"]


# ── Seed default admin on first run ──────────────────────────────────────────

def seed_admin_if_needed():
    """
    Create a default admin account if no admin exists yet.
    Default credentials:  admin / Admin123
    The user should change this password after first login.
    """
    if db.count_admins() == 0:
        register("admin", "Admin123", role="admin")


# ── Date Helpers ──────────────────────────────────────────────────────────────

def today_str() -> str:
    return date.today().isoformat()


def parse_date(date_str: str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def format_date_display(date_str: str) -> str:
    d = parse_date(date_str)
    return d.strftime("%b %d, %Y") if d else date_str


def month_year_label(month: int, year: int) -> str:
    return datetime(year, month, 1).strftime("%B %Y")


def prev_month(month: int, year: int):
    return (12, year - 1) if month == 1 else (month - 1, year)


def next_month(month: int, year: int):
    return (1, year + 1) if month == 12 else (month + 1, year)


# ── Formatters ────────────────────────────────────────────────────────────────

def format_currency(amount, symbol="$") -> str:
    try:
        return f"{symbol}{float(amount):,.2f}"
    except (ValueError, TypeError):
        return f"{symbol}0.00"


def format_expense_row(expense: dict) -> dict:
    expense["amount_display"] = format_currency(expense.get("amount", 0))
    expense["date_display"]   = format_date_display(expense.get("date", ""))
    expense["owner"]          = expense.get("username", "")
    return expense


# ── Validation ────────────────────────────────────────────────────────────────

def validate_expense(title, amount_str, category_id, date_str):
    if not title or not title.strip():
        return False, "Title cannot be empty."
    try:
        amount = float(amount_str)
        if amount <= 0:
            return False, "Amount must be greater than zero."
    except (ValueError, TypeError):
        return False, "Amount must be a valid number."
    if not category_id:
        return False, "Please select a category."
    if not parse_date(date_str):
        return False, "Date must be in YYYY-MM-DD format."
    return True, None


# ── Expense Operations ────────────────────────────────────────────────────────

def add_expense(title, amount_str, category_id, date_str, note=""):
    if not is_logged_in():
        return False, "Not logged in."
    ok, err = validate_expense(title, amount_str, category_id, date_str)
    if not ok:
        return False, err
    eid = db.add_expense(
        current_user["id"], title.strip(),
        float(amount_str), category_id, date_str, note.strip()
    )
    return True, eid


def update_expense(expense_id, title, amount_str, category_id, date_str, note=""):
    if not is_logged_in():
        return False, "Not logged in."
    # Ownership check: admins can edit any expense, users only their own
    if not is_admin():
        exp = db.get_expense_by_id(expense_id)
        if not exp or exp["user_id"] != current_user["id"]:
            return False, "Permission denied."
    ok, err = validate_expense(title, amount_str, category_id, date_str)
    if not ok:
        return False, err
    db.update_expense(
        expense_id, title.strip(), float(amount_str),
        category_id, date_str, note.strip()
    )
    return True, None


def delete_expense(expense_id):
    if not is_logged_in():
        return
    if not is_admin():
        exp = db.get_expense_by_id(expense_id)
        if not exp or exp["user_id"] != current_user["id"]:
            return
    db.delete_expense(expense_id)


def get_expense(expense_id):
    return db.get_expense_by_id(expense_id)


def get_expenses(category_id=None, month=None, year=None, limit=None):
    """Returns display-ready rows. Admins see all users; users see own only."""
    rows = db.get_all_expenses(
        user_id=_uid(),
        category_id=category_id, month=month, year=year, limit=limit
    )
    return [format_expense_row(r) for r in rows]


def get_recent(n=5):
    rows = db.get_recent_expenses(n=n, user_id=_uid())
    return [format_expense_row(r) for r in rows]


# ── Categories ────────────────────────────────────────────────────────────────

def get_categories():
    return db.get_all_categories()


def get_category_map():
    return {c["id"]: c for c in db.get_all_categories()}


def get_category_names():
    return [(c["id"], f"{c['icon']} {c['name']}") for c in db.get_all_categories()]


def add_category(name, icon="?", color="#4CAF50"):
    if not is_admin():
        return False, "Admin access required."
    if not name.strip():
        return False, "Category name cannot be empty."
    db.add_category(name.strip(), icon, color)
    return True, None


def delete_category(category_id):
    if not is_admin():
        return False, "Admin access required."
    db.delete_category(category_id)
    return True, None


# ── Dashboard / Stats ────────────────────────────────────────────────────────

def get_dashboard_data(month=None, year=None):
    now   = datetime.now()
    month = month or now.month
    year  = year  or now.year
    uid   = _uid()

    total        = db.get_total_by_month(month, year, user_id=uid)
    by_category  = db.get_spending_by_category(month, year, user_id=uid)
    daily_totals = db.get_daily_totals(month, year, user_id=uid)
    recent       = get_recent(5)
    budgets      = {b["category_id"]: b
                    for b in db.get_budgets(current_user["id"])} \
                   if current_user else {}

    for cat in by_category:
        budget = budgets.get(cat["id"])
        cat["budget_limit"] = budget["monthly_limit"] if budget else None
        cat["budget_pct"]   = (
            min(cat["total"] / budget["monthly_limit"] * 100, 100)
            if budget and budget["monthly_limit"] > 0 else None
        )
        cat["over_budget"]   = (cat["total"] > budget["monthly_limit"]
                                 if budget else False)
        cat["total_display"] = format_currency(cat["total"])

    return {
        "month": month, "year": year,
        "month_label":   month_year_label(month, year),
        "total":         total,
        "total_display": format_currency(total),
        "by_category":   by_category,
        "daily_totals":  daily_totals,
        "recent":        recent,
    }


def get_admin_stats():
    """Admin-only global overview."""
    if not is_admin():
        return []
    return db.get_global_stats()


# ── Budget ────────────────────────────────────────────────────────────────────

def set_budget(category_id, limit_str):
    if not is_logged_in():
        return False, "Not logged in."
    try:
        limit = float(limit_str)
        if limit < 0:
            return False, "Budget limit must be non-negative."
    except (ValueError, TypeError):
        return False, "Budget must be a valid number."
    db.set_budget(current_user["id"], category_id, limit)
    return True, None


def get_budgets():
    if not is_logged_in():
        return []
    return db.get_budgets(current_user["id"])


# ── Admin User Management ─────────────────────────────────────────────────────

def admin_get_all_users():
    if not is_admin():
        return []
    return db.get_all_users()


def admin_delete_user(user_id):
    if not is_admin():
        return False, "Admin access required."
    if user_id == current_user["id"]:
        return False, "Cannot delete your own account."
    if db.get_user_by_id(user_id) and db.get_user_by_id(user_id)["role"] == "admin":
        if db.count_admins() <= 1:
            return False, "Cannot delete the last admin."
    db.delete_user(user_id)
    return True, None


def admin_change_role(user_id, new_role):
    if not is_admin():
        return False, "Admin access required."
    if new_role not in ("user", "admin"):
        return False, "Invalid role."
    if user_id == current_user["id"] and new_role == "user":
        if db.count_admins() <= 1:
            return False, "Cannot demote the last admin."
    db.update_user_role(user_id, new_role)
    return True, None


def change_own_password(old_password, new_password):
    global current_user
    if not is_logged_in():
        return False, "Not logged in."
    if not _verify_password(old_password, current_user["password"]):
        return False, "Current password is incorrect."
    if len(new_password) < 6:
        return False, "New password must be at least 6 characters."
    hashed = _hash_password(new_password)
    db.change_password(current_user["id"], hashed)
    # Refresh session with updated data
    current_user = db.get_user_by_id(current_user["id"])
    return True, None


# ── Init ──────────────────────────────────────────────────────────────────────

def init():
    """Call once at app startup."""
    db.init_db()
    seed_admin_if_needed()