"""
logic.py — Business logic / service layer for Expense Tracker

OOP Design:
  - Encapsulation : all DB access goes through this module; GUI never
                    imports database directly. Internal helpers prefixed _.
  - Polymorphism  : register/login/logout work transparently for both
                    user and admin roles; callers don't branch on role.
  - Single Responsibility: date helpers, formatters, validators, auth,
                    CRUD, export are each in their own named section.

Phase 3 additions:
  - Brute-force login lockout (5 attempts → 30-min cooldown)
  - Audit log for all admin actions
  - Input sanitisation helper
  - CSV export
"""

import hashlib
import hmac
import os
import csv
import io
import re
import secrets
from datetime import datetime, date, timedelta
import database as db


# ── Session State ─────────────────────────────────────────────────────────────
current_user: dict | None = None

# ── Lockout config ────────────────────────────────────────────────────────────
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES     = 30


# ── Password Hashing (PBKDF2-HMAC-SHA256) ────────────────────────────────────

def _hash_password(plain: str, salt: str = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256", plain.encode("utf-8"), salt.encode("utf-8"),
        iterations=260_000
    )
    return f"{salt}${key.hex()}"


def _verify_password(plain: str, stored: str) -> bool:
    try:
        salt, _ = stored.split("$", 1)
        return hmac.compare_digest(stored, _hash_password(plain, salt))
    except Exception:
        return False


# ── Phase 3: Input Sanitisation ───────────────────────────────────────────────

def sanitise(text: str, max_len: int = 200) -> str:
    """
    Encapsulation helper — sanitise all user input before DB writes.
    Strips whitespace, removes control characters, truncates to max_len.
    Called internally by add_expense, update_expense, register, add_category.
    """
    if not isinstance(text, str):
        return ""
    # Remove control characters (keep newlines for note fields)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = text.strip()
    return text[:max_len]


# ── Auth ──────────────────────────────────────────────────────────────────────

def register(username: str, password: str, role: str = "user"):
    if not username or not username.strip():
        return False, "Username cannot be empty."
    if len(username.strip()) < 3:
        return False, "Username must be at least 3 characters."
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters."
    if role not in ("user", "admin"):
        return False, "Invalid role."

    hashed = _hash_password(password)
    uid    = db.create_user(sanitise(username, 50), hashed, role)
    if uid is None:
        return False, "Username already taken."
    user = db.get_user_by_id(uid)
    return True, user


def login(username: str, password: str):
    """
    Authenticate with brute-force lockout.
    Returns (True, user_dict) or (False, error_msg).
    """
    global current_user
    if not username or not password:
        return False, "Username and password are required."

    username = username.strip()

    # ── Check account lockout ─────────────────────────────────────────────
    user = db.get_user_by_username(username)
    if user:
        if user.get("is_locked"):
            locked_until = user.get("locked_until")
            if locked_until:
                try:
                    until_dt = datetime.fromisoformat(locked_until)
                    if datetime.now() < until_dt:
                        remaining = int((until_dt - datetime.now()).total_seconds() / 60) + 1
                        return False, (
                            f"Account locked due to too many failed attempts. "
                            f"Try again in {remaining} minute(s)."
                        )
                    else:
                        # Lockout expired — automatically unlock
                        db.set_user_locked(user["id"], None)
                        db.clear_login_attempts(username)
                        user = db.get_user_by_username(username)
                except ValueError:
                    pass

    # ── Check recent failure count (even for unknown users) ──────────────
    recent_failures = db.count_recent_failures(username, LOCKOUT_MINUTES)
    if recent_failures >= MAX_FAILED_ATTEMPTS:
        # Apply lockout if not already set
        if user and not user.get("is_locked"):
            until = (datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
            db.set_user_locked(user["id"], until)
            _audit(None, "system", "LOCKOUT", username,
                   f"{MAX_FAILED_ATTEMPTS} failed attempts in {LOCKOUT_MINUTES} min")
        return False, (
            f"Account locked after {MAX_FAILED_ATTEMPTS} failed attempts. "
            f"Try again in {LOCKOUT_MINUTES} minutes."
        )

    # ── Validate credentials ──────────────────────────────────────────────
    if not user:
        db.record_login_attempt(username, success=False)
        return False, "User not found."

    if not _verify_password(password, user["password"]):
        db.record_login_attempt(username, success=False)
        # Check if this failure tips over the threshold
        failures_now = db.count_recent_failures(username, LOCKOUT_MINUTES)
        if failures_now >= MAX_FAILED_ATTEMPTS:
            until = (datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
            db.set_user_locked(user["id"], until)
            _audit(None, "system", "LOCKOUT", username,
                   f"Locked after {MAX_FAILED_ATTEMPTS} failed attempts")
            return False, (
                f"Too many failed attempts. Account locked for {LOCKOUT_MINUTES} minutes."
            )
        remaining_attempts = MAX_FAILED_ATTEMPTS - failures_now
        return False, f"Incorrect password. {remaining_attempts} attempt(s) remaining."

    # ── Success ───────────────────────────────────────────────────────────
    db.record_login_attempt(username, success=True)
    db.clear_login_attempts(username)   # reset counter on success
    current_user = user
    _audit(user["id"], user["username"], "LOGIN", "", "Successful login")
    return True, user


def logout():
    global current_user
    if current_user:
        _audit(current_user["id"], current_user["username"], "LOGOUT")
    current_user = None


def get_current_user() -> dict | None:
    return current_user


def is_admin() -> bool:
    return current_user is not None and current_user["role"] == "admin"


def is_logged_in() -> bool:
    return current_user is not None


def _uid():
    """
    Encapsulation helper — data scoping for DB queries.
    Returns None for admins (sees all data) or the logged-in user's id.
    Never called from outside this module (private by convention: _prefix).
    """
    if current_user is None:
        return None
    return None if is_admin() else current_user["id"]


# ── Audit log helper ──────────────────────────────────────────────────────────

def _audit(actor_id, actor_name: str, action: str,
           target: str = "", detail: str = ""):
    """Internal — write an audit log entry. Never raises."""
    try:
        db.write_audit(actor_id, actor_name, action, target, detail)
    except Exception:
        pass   # audit must never crash the main flow


# ── Seed ─────────────────────────────────────────────────────────────────────

def seed_admin_if_needed():
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
        current_user["id"],
        sanitise(title, 100),
        float(amount_str),
        category_id,
        date_str,
        sanitise(note, 500)
    )
    return True, eid


def update_expense(expense_id, title, amount_str, category_id, date_str, note=""):
    if not is_logged_in():
        return False, "Not logged in."
    if not is_admin():
        exp = db.get_expense_by_id(expense_id)
        if not exp or exp["user_id"] != current_user["id"]:
            return False, "Permission denied."
    ok, err = validate_expense(title, amount_str, category_id, date_str)
    if not ok:
        return False, err
    db.update_expense(
        expense_id,
        sanitise(title, 100),
        float(amount_str),
        category_id,
        date_str,
        sanitise(note, 500)
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
    rows = db.get_all_expenses(
        user_id=_uid(),
        category_id=category_id, month=month, year=year, limit=limit
    )
    return [format_expense_row(r) for r in rows]


def get_recent(n=5):
    rows = db.get_recent_expenses(n=n, user_id=_uid())
    return [format_expense_row(r) for r in rows]


# ── Phase 4: CSV Export ───────────────────────────────────────────────────────

def export_expenses_csv(month=None, year=None) -> str:
    """
    Export the current user's expenses (or all for admin) as a CSV string.
    Returns the CSV text ready to write to a file.
    """
    if not is_logged_in():
        return ""
    rows = db.get_all_expenses(user_id=_uid(), month=month, year=year)
    output = io.StringIO()
    writer = csv.writer(output)

    if is_admin():
        headers = ["id", "username", "title", "amount", "category",
                   "date", "note", "created_at"]
        writer.writerow(headers)
        for r in rows:
            writer.writerow([
                r["id"], r.get("username", ""),
                r["title"], r["amount"],
                r.get("category_name", ""),
                r["date"], r.get("note", ""), r["created_at"]
            ])
    else:
        headers = ["id", "title", "amount", "category", "date", "note", "created_at"]
        writer.writerow(headers)
        for r in rows:
            writer.writerow([
                r["id"], r["title"], r["amount"],
                r.get("category_name", ""),
                r["date"], r.get("note", ""), r["created_at"]
            ])

    _audit(current_user["id"], current_user["username"],
           "EXPORT_CSV", "", f"{len(rows)} rows exported")
    return output.getvalue()


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
    db.add_category(sanitise(name, 50), icon, color)
    _audit(current_user["id"], current_user["username"],
           "ADD_CATEGORY", name, "")
    return True, None


def delete_category(category_id):
    if not is_admin():
        return False, "Admin access required."
    cat = get_category_map().get(category_id)
    db.delete_category(category_id)
    if cat:
        _audit(current_user["id"], current_user["username"],
               "DELETE_CATEGORY", cat["name"], "")
    return True, None


# ── Dashboard / Stats ─────────────────────────────────────────────────────────

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
    if not is_admin():
        return []
    return db.get_global_stats()


def get_audit_log(limit=100):
    if not is_admin():
        return []
    return db.get_audit_log(limit)


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
    target = db.get_user_by_id(user_id)
    if target and target["role"] == "admin" and db.count_admins() <= 1:
        return False, "Cannot delete the last admin."
    target_name = target["username"] if target else str(user_id)
    db.delete_user(user_id)
    _audit(current_user["id"], current_user["username"],
           "DELETE_USER", target_name, f"role was {target['role'] if target else '?'}")
    return True, None


def admin_change_role(user_id, new_role):
    if not is_admin():
        return False, "Admin access required."
    if new_role not in ("user", "admin"):
        return False, "Invalid role."
    if user_id == current_user["id"] and new_role == "user":
        if db.count_admins() <= 1:
            return False, "Cannot demote the last admin."
    target = db.get_user_by_id(user_id)
    old_role = target["role"] if target else "?"
    db.update_user_role(user_id, new_role)
    _audit(current_user["id"], current_user["username"],
           "CHANGE_ROLE", target["username"] if target else str(user_id),
           f"{old_role} → {new_role}")
    return True, None


def admin_unlock_user(user_id):
    """Manually unlock a locked account."""
    if not is_admin():
        return False, "Admin access required."
    target = db.get_user_by_id(user_id)
    db.set_user_locked(user_id, None)
    db.clear_login_attempts(target["username"] if target else "")
    _audit(current_user["id"], current_user["username"],
           "UNLOCK_USER", target["username"] if target else str(user_id), "")
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
    _audit(current_user["id"], current_user["username"],
           "CHANGE_PASSWORD", "", "")
    current_user = db.get_user_by_id(current_user["id"])
    return True, None


# ── Init ──────────────────────────────────────────────────────────────────────

def init():
    db.init_db()
    seed_admin_if_needed()