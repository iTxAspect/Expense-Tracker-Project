"""
database.py — SQLite persistence layer for Expense Tracker
Tables: users, categories, expenses, budgets
All expense queries are scoped by user_id (admin sees all via user_id=None).
"""

import sqlite3
import os

_HERE   = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(_HERE, "expenses.db")


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    c    = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT    NOT NULL UNIQUE,
            password   TEXT    NOT NULL,
            role       TEXT    NOT NULL DEFAULT 'user'
                               CHECK(role IN ('user','admin')),
            created_at TEXT    DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name  TEXT    NOT NULL UNIQUE,
            icon  TEXT    DEFAULT '?',
            color TEXT    DEFAULT '#4CAF50'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            title       TEXT    NOT NULL,
            amount      REAL    NOT NULL,
            category_id INTEGER,
            date        TEXT    NOT NULL,
            note        TEXT    DEFAULT '',
            created_at  TEXT    DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)     REFERENCES users(id)      ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            category_id   INTEGER NOT NULL,
            monthly_limit REAL    NOT NULL,
            UNIQUE(user_id, category_id),
            FOREIGN KEY (user_id)     REFERENCES users(id)      ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
        )
    """)

    defaults = [
        ("Food & Dining", "F", "#FF5722"),
        ("Transport",     "T", "#2196F3"),
        ("Shopping",      "S", "#9C27B0"),
        ("Health",        "H", "#F44336"),
        ("Entertainment", "E", "#FF9800"),
        ("Bills",         "B", "#607D8B"),
        ("Education",     "D", "#3F51B5"),
        ("Other",         "O", "#4CAF50"),
    ]
    c.executemany(
        "INSERT OR IGNORE INTO categories (name, icon, color) VALUES (?,?,?)",
        defaults
    )

    conn.commit()
    conn.close()


# ── USER CRUD ─────────────────────────────────────────────────────────────────

def create_user(username, hashed_password, role="user"):
    conn = get_connection()
    c    = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (username, password, role) VALUES (?,?,?)",
            (username.strip(), hashed_password, role)
        )
        conn.commit()
        uid = c.lastrowid
    except sqlite3.IntegrityError:
        uid = None
    finally:
        conn.close()
    return uid


def get_user_by_username(username):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username.strip(),))
    row  = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row  = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_users():
    conn = get_connection()
    c    = conn.cursor()
    c.execute("SELECT id, username, role, created_at FROM users ORDER BY created_at")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_user_role(user_id, new_role):
    conn = get_connection()
    conn.execute("UPDATE users SET role=? WHERE id=?", (new_role, user_id))
    conn.commit()
    conn.close()


def delete_user(user_id):
    conn = get_connection()
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


def change_password(user_id, new_hashed_password):
    conn = get_connection()
    conn.execute("UPDATE users SET password=? WHERE id=?",
                 (new_hashed_password, user_id))
    conn.commit()
    conn.close()


def count_admins():
    conn = get_connection()
    c    = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    n = c.fetchone()[0]
    conn.close()
    return n


# ── EXPENSE CRUD ──────────────────────────────────────────────────────────────

def add_expense(user_id, title, amount, category_id, date, note=""):
    conn = get_connection()
    c    = conn.cursor()
    c.execute(
        "INSERT INTO expenses (user_id,title,amount,category_id,date,note) VALUES (?,?,?,?,?,?)",
        (user_id, title, float(amount), category_id, date, note)
    )
    conn.commit()
    eid = c.lastrowid
    conn.close()
    return eid


def update_expense(expense_id, title, amount, category_id, date, note=""):
    conn = get_connection()
    conn.execute(
        "UPDATE expenses SET title=?,amount=?,category_id=?,date=?,note=? WHERE id=?",
        (title, float(amount), category_id, date, note, expense_id)
    )
    conn.commit()
    conn.close()


def delete_expense(expense_id):
    conn = get_connection()
    conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()
    conn.close()


def get_expense_by_id(expense_id):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("""
        SELECT e.*, c.name AS category_name, c.icon AS category_icon,
               c.color AS category_color, u.username
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        LEFT JOIN users      u ON e.user_id     = u.id
        WHERE e.id = ?
    """, (expense_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_expenses(user_id=None, limit=None, offset=0,
                     category_id=None, month=None, year=None):
    conn   = get_connection()
    c      = conn.cursor()
    query  = """
        SELECT e.*, c.name AS category_name, c.icon AS category_icon,
               c.color AS category_color, u.username
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        LEFT JOIN users      u ON e.user_id     = u.id
        WHERE 1=1
    """
    params = []
    if user_id is not None:
        query += " AND e.user_id=?"; params.append(user_id)
    if category_id:
        query += " AND e.category_id=?"; params.append(category_id)
    if month and year:
        query += " AND strftime('%m',e.date)=? AND strftime('%Y',e.date)=?"
        params.extend([f"{month:02d}", str(year)])
    elif year:
        query += " AND strftime('%Y',e.date)=?"; params.append(str(year))
    query += " ORDER BY e.date DESC, e.created_at DESC"
    if limit:
        query += " LIMIT ? OFFSET ?"; params.extend([limit, offset])
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── CATEGORY CRUD ─────────────────────────────────────────────────────────────

def get_all_categories():
    conn = get_connection()
    c    = conn.cursor()
    c.execute("SELECT * FROM categories ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_category(name, icon="?", color="#4CAF50"):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("INSERT OR IGNORE INTO categories (name,icon,color) VALUES (?,?,?)",
              (name, icon, color))
    conn.commit()
    cid = c.lastrowid
    conn.close()
    return cid


def delete_category(category_id):
    conn = get_connection()
    conn.execute("DELETE FROM categories WHERE id=?", (category_id,))
    conn.commit()
    conn.close()


# ── AGGREGATIONS ──────────────────────────────────────────────────────────────

def get_total_by_month(month, year, user_id=None):
    conn = get_connection()
    c    = conn.cursor()
    q    = "SELECT COALESCE(SUM(amount),0) AS total FROM expenses WHERE strftime('%m',date)=? AND strftime('%Y',date)=?"
    p    = [f"{month:02d}", str(year)]
    if user_id is not None:
        q += " AND user_id=?"; p.append(user_id)
    c.execute(q, p)
    row = c.fetchone()
    conn.close()
    return row["total"] if row else 0.0


def get_spending_by_category(month=None, year=None, user_id=None):
    conn  = get_connection()
    c     = conn.cursor()
    query = """
        SELECT c.id, c.name, c.icon, c.color,
               COALESCE(SUM(e.amount),0) AS total
        FROM categories c
        LEFT JOIN expenses e ON c.id = e.category_id
    """
    params = []
    where  = []
    if user_id is not None:
        where.append("e.user_id=?"); params.append(user_id)
    if month and year:
        where.append("strftime('%m',e.date)=? AND strftime('%Y',e.date)=?")
        params.extend([f"{month:02d}", str(year)])
    if where:
        query += " AND " + " AND ".join(where)
    query += " GROUP BY c.id ORDER BY total DESC"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_daily_totals(month, year, user_id=None):
    conn = get_connection()
    c    = conn.cursor()
    q    = "SELECT strftime('%d',date) AS day, SUM(amount) AS total FROM expenses WHERE strftime('%m',date)=? AND strftime('%Y',date)=?"
    p    = [f"{month:02d}", str(year)]
    if user_id is not None:
        q += " AND user_id=?"; p.append(user_id)
    q += " GROUP BY day ORDER BY day"
    c.execute(q, p)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_expenses(n=5, user_id=None):
    return get_all_expenses(user_id=user_id, limit=n)


def get_global_stats():
    """Admin only — per-user totals."""
    conn = get_connection()
    c    = conn.cursor()
    c.execute("""
        SELECT u.id, u.username, u.role,
               COUNT(e.id) AS expense_count,
               COALESCE(SUM(e.amount),0) AS total_spent
        FROM users u
        LEFT JOIN expenses e ON u.id = e.user_id
        GROUP BY u.id ORDER BY total_spent DESC
    """)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── BUDGET ────────────────────────────────────────────────────────────────────

def set_budget(user_id, category_id, monthly_limit):
    conn = get_connection()
    conn.execute("""
        INSERT INTO budgets (user_id, category_id, monthly_limit) VALUES (?,?,?)
        ON CONFLICT(user_id, category_id)
        DO UPDATE SET monthly_limit = excluded.monthly_limit
    """, (user_id, category_id, float(monthly_limit)))
    conn.commit()
    conn.close()


def get_budgets(user_id):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("""
        SELECT b.*, c.name AS category_name, c.icon, c.color
        FROM budgets b JOIN categories c ON b.category_id = c.id
        WHERE b.user_id = ?
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]