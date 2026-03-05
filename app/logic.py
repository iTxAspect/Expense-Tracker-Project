"""
logic.py - Business logic layer for Expense Tracker
Sits between GUI and database: validation, formatting, and computed data.
"""

from datetime import datetime, date
import database as db


# ─── DATE HELPERS ─────────────────────────────────────────────────────────────

def today_str():
    return date.today().isoformat()   # e.g. "2026-03-05"


def parse_date(date_str):
    """Parse a date string (YYYY-MM-DD) → date object, or None on failure."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def format_date_display(date_str):
    """Convert '2026-03-05' → 'Mar 05, 2026'."""
    d = parse_date(date_str)
    if d:
        return d.strftime("%b %d, %Y")
    return date_str


def month_year_label(month, year):
    """Return e.g. 'March 2026'."""
    return datetime(year, month, 1).strftime("%B %Y")


# ─── FORMATTING ───────────────────────────────────────────────────────────────

def format_currency(amount, symbol="$"):
    """Format a float as currency string."""
    try:
        return f"{symbol}{float(amount):,.2f}"
    except (ValueError, TypeError):
        return f"{symbol}0.00"


def format_expense_row(expense: dict) -> dict:
    """
    Enrich an expense dict with display-ready fields.
    Input comes straight from database.get_all_expenses().
    """
    expense["amount_display"] = format_currency(expense.get("amount", 0))
    expense["date_display"]   = format_date_display(expense.get("date", ""))
    expense["label"]          = (
        f"{expense.get('category_icon', '💰')}  "
        f"{expense.get('title', 'Untitled')}  •  "
        f"{expense['amount_display']}"
    )
    return expense


# ─── VALIDATION ───────────────────────────────────────────────────────────────

def validate_expense(title, amount_str, category_id, date_str):
    """
    Validate expense fields.
    Returns (True, None) on success or (False, error_message) on failure.
    """
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


# ─── EXPENSE OPERATIONS ───────────────────────────────────────────────────────

def add_expense(title, amount_str, category_id, date_str, note=""):
    """Validate then save a new expense. Returns (True, id) or (False, msg)."""
    ok, err = validate_expense(title, amount_str, category_id, date_str)
    if not ok:
        return False, err
    expense_id = db.add_expense(
        title.strip(), float(amount_str), category_id, date_str, note.strip()
    )
    return True, expense_id


def update_expense(expense_id, title, amount_str, category_id, date_str, note=""):
    """Validate then update an expense. Returns (True, None) or (False, msg)."""
    ok, err = validate_expense(title, amount_str, category_id, date_str)
    if not ok:
        return False, err
    db.update_expense(
        expense_id, title.strip(), float(amount_str), category_id, date_str, note.strip()
    )
    return True, None


def delete_expense(expense_id):
    db.delete_expense(expense_id)


def get_expense(expense_id):
    return db.get_expense_by_id(expense_id)


def get_expenses(category_id=None, month=None, year=None, limit=None):
    """Return display-ready expense list."""
    rows = db.get_all_expenses(
        category_id=category_id, month=month, year=year, limit=limit
    )
    return [format_expense_row(r) for r in rows]


def get_recent(n=5):
    rows = db.get_recent_expenses(n)
    return [format_expense_row(r) for r in rows]


# ─── CATEGORIES ───────────────────────────────────────────────────────────────

def get_categories():
    return db.get_all_categories()


def get_category_map():
    """Return {id: category_dict} mapping."""
    return {c["id"]: c for c in db.get_all_categories()}


def get_category_names():
    """Return list of (id, display_name) tuples for spinners."""
    return [(c["id"], f"{c['icon']} {c['name']}") for c in db.get_all_categories()]


# ─── STATS / DASHBOARD ────────────────────────────────────────────────────────

def get_dashboard_data(month=None, year=None):
    """
    Compute all data needed for the dashboard screen.
    Defaults to current month/year.
    """
    now = datetime.now()
    month = month or now.month
    year  = year  or now.year

    total        = db.get_total_by_month(month, year)
    by_category  = db.get_spending_by_category(month, year)
    daily_totals = db.get_daily_totals(month, year)
    recent       = get_recent(5)
    budgets      = {b["category_id"]: b for b in db.get_budgets()}

    # Attach budget info to category spending
    for cat in by_category:
        budget = budgets.get(cat["id"])
        cat["budget_limit"]  = budget["monthly_limit"] if budget else None
        cat["budget_pct"]    = (
            min(cat["total"] / budget["monthly_limit"] * 100, 100)
            if budget and budget["monthly_limit"] > 0 else None
        )
        cat["over_budget"]   = (
            cat["total"] > budget["monthly_limit"]
            if budget else False
        )
        cat["total_display"] = format_currency(cat["total"])

    return {
        "month":         month,
        "year":          year,
        "month_label":   month_year_label(month, year),
        "total":         total,
        "total_display": format_currency(total),
        "by_category":   by_category,
        "daily_totals":  daily_totals,
        "recent":        recent,
    }


def prev_month(month, year):
    if month == 1:
        return 12, year - 1
    return month - 1, year


def next_month(month, year):
    if month == 12:
        return 1, year + 1
    return month + 1, year


# ─── BUDGET ───────────────────────────────────────────────────────────────────

def set_budget(category_id, limit_str):
    """Validate and save a budget limit."""
    try:
        limit = float(limit_str)
        if limit < 0:
            return False, "Budget limit must be non-negative."
    except (ValueError, TypeError):
        return False, "Budget must be a valid number."
    db.set_budget(category_id, limit)
    return True, None


def get_budgets():
    return db.get_budgets()


# ─── INIT ─────────────────────────────────────────────────────────────────────

def init():
    """Call once at app startup to initialise the database."""
    db.init_db()