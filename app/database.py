"""
database.py - SQLite database management for Expense Tracker
Handles all data persistence: creating tables, CRUD operations, and queries.
"""

import sqlite3
import os
from datetime import datetime


DB_NAME = "expenses.db"


def get_connection():
    """Create and return a database connection."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Allows dict-like access to rows
    return conn


def init_db():
    """Initialize the database and create tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            icon TEXT DEFAULT '💰',
            color TEXT DEFAULT '#4CAF50'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category_id INTEGER,
            date TEXT NOT NULL,
            note TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER UNIQUE,
            monthly_limit REAL NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)

    # Seed default categories
    default_categories = [
        ("Food & Dining", "🍔", "#FF5722"),
        ("Transport",     "🚗", "#2196F3"),
        ("Shopping",      "🛍️", "#9C27B0"),
        ("Health",        "💊", "#F44336"),
        ("Entertainment", "🎮", "#FF9800"),
        ("Bills",         "📄", "#607D8B"),
        ("Education",     "📚", "#3F51B5"),
        ("Other",         "💰", "#4CAF50"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO categories (name, icon, color) VALUES (?, ?, ?)",
        default_categories
    )

    conn.commit()
    conn.close()


# ─── EXPENSE CRUD ────────────────────────────────────────────────────────────

def add_expense(title, amount, category_id, date, note=""):
    """Insert a new expense record."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO expenses (title, amount, category_id, date, note) VALUES (?, ?, ?, ?, ?)",
        (title, float(amount), category_id, date, note)
    )
    conn.commit()
    expense_id = cursor.lastrowid
    conn.close()
    return expense_id


def update_expense(expense_id, title, amount, category_id, date, note=""):
    """Update an existing expense record."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE expenses
           SET title=?, amount=?, category_id=?, date=?, note=?
           WHERE id=?""",
        (title, float(amount), category_id, date, note, expense_id)
    )
    conn.commit()
    conn.close()


def delete_expense(expense_id):
    """Delete an expense by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()
    conn.close()


def get_expense_by_id(expense_id):
    """Fetch a single expense by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.*, c.name as category_name, c.icon as category_icon, c.color as category_color
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        WHERE e.id = ?
    """, (expense_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_expenses(limit=None, offset=0, category_id=None, month=None, year=None):
    """
    Fetch expenses with optional filters.
    month/year: integers (e.g. month=3, year=2026)
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT e.*, c.name as category_name, c.icon as category_icon, c.color as category_color
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        WHERE 1=1
    """
    params = []

    if category_id:
        query += " AND e.category_id = ?"
        params.append(category_id)
    if month and year:
        query += " AND strftime('%m', e.date) = ? AND strftime('%Y', e.date) = ?"
        params.extend([f"{month:02d}", str(year)])
    elif year:
        query += " AND strftime('%Y', e.date) = ?"
        params.append(str(year))

    query += " ORDER BY e.date DESC, e.created_at DESC"

    if limit:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── CATEGORY CRUD ───────────────────────────────────────────────────────────

def get_all_categories():
    """Return all categories."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categories ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_category(name, icon="💰", color="#4CAF50"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO categories (name, icon, color) VALUES (?, ?, ?)",
        (name, icon, color)
    )
    conn.commit()
    cat_id = cursor.lastrowid
    conn.close()
    return cat_id


# ─── STATS & AGGREGATIONS ────────────────────────────────────────────────────

def get_total_by_month(month, year):
    """Sum of all expenses in a given month/year."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM expenses
        WHERE strftime('%m', date) = ? AND strftime('%Y', date) = ?
    """, (f"{month:02d}", str(year)))
    result = cursor.fetchone()
    conn.close()
    return result["total"] if result else 0.0


def get_spending_by_category(month=None, year=None):
    """Return total spending grouped by category."""
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT c.id, c.name, c.icon, c.color,
               COALESCE(SUM(e.amount), 0) as total
        FROM categories c
        LEFT JOIN expenses e ON c.id = e.category_id
    """
    params = []
    if month and year:
        query += " AND strftime('%m', e.date) = ? AND strftime('%Y', e.date) = ?"
        params.extend([f"{month:02d}", str(year)])
    query += " GROUP BY c.id ORDER BY total DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_daily_totals(month, year):
    """Return day-by-day totals for a given month."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT strftime('%d', date) as day, SUM(amount) as total
        FROM expenses
        WHERE strftime('%m', date) = ? AND strftime('%Y', date) = ?
        GROUP BY day
        ORDER BY day
    """, (f"{month:02d}", str(year)))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_expenses(n=5):
    """Return the n most recent expenses."""
    return get_all_expenses(limit=n)


# ─── BUDGET ──────────────────────────────────────────────────────────────────

def set_budget(category_id, monthly_limit):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO budgets (category_id, monthly_limit)
        VALUES (?, ?)
        ON CONFLICT(category_id) DO UPDATE SET monthly_limit=excluded.monthly_limit
    """, (category_id, float(monthly_limit)))
    conn.commit()
    conn.close()


def get_budgets():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.*, c.name as category_name, c.icon, c.color
        FROM budgets b
        JOIN categories c ON b.category_id = c.id
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]