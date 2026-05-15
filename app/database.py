"""
database.py — MySQL persistence layer for Expense Tracker
Replaces SQLite with MySQL via mysql-connector-python.

Install driver:
    pip install mysql-connector-python

MySQL setup (run once as root):
    CREATE DATABASE expense_tracker CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    CREATE USER 'expense_user'@'localhost' IDENTIFIED BY 'StrongPass123!';
    GRANT ALL PRIVILEGES ON expense_tracker.* TO 'expense_user'@'localhost';
    FLUSH PRIVILEGES;

OOP Design:
  - Encapsulation : all SQL is contained here; no raw SQL leaks to logic.py.
  - Single Responsibility: each function does exactly one DB operation.
  - Data Integrity: foreign keys enforced by MySQL engine (InnoDB).
"""

import mysql.connector
from mysql.connector import IntegrityError, Error as MySQLError

# ── Connection config — edit these to match your MySQL server ─────────────────
DB_CONFIG = {
    "host":     "localhost",
    "port":     3306,
    "user":     "expense_user",
    "password": "StrongPass123!",
    "database": "expense_tracker",
    "charset":  "utf8mb4",
    "collation":"utf8mb4_unicode_ci",
    "autocommit": False,
    "time_zone": "+00:00",
}


# ── Connection ────────────────────────────────────────────────────────────────

def get_connection():
    """
    Open and return a new MySQL connection.
    Each function is responsible for closing it when done.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    return conn


def _row_to_dict(cursor, row):
    """Convert a cursor row to a dict using column names."""
    if row is None:
        return None
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


def _rows_to_dicts(cursor, rows):
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


# ── Schema Init ───────────────────────────────────────────────────────────────

def init_db():
    """
    Create all tables if they do not exist.
    Safe to call on every app startup — uses IF NOT EXISTS.
    MySQL differences from SQLite:
      - AUTO_INCREMENT instead of AUTOINCREMENT
      - TINYINT(1) instead of INTEGER for booleans
      - DATETIME instead of TEXT for timestamps
      - VARCHAR instead of TEXT for short strings
      - ON DUPLICATE KEY UPDATE instead of ON CONFLICT
      - DOUBLE instead of REAL
    """
    conn = get_connection()
    c    = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id           INT          NOT NULL AUTO_INCREMENT,
            username     VARCHAR(50)  NOT NULL,
            password     VARCHAR(200) NOT NULL,
            role         ENUM('user','admin') NOT NULL DEFAULT 'user',
            is_locked    TINYINT(1)   NOT NULL DEFAULT 0,
            locked_until DATETIME     DEFAULT NULL,
            created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uq_username (username)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id    INT         NOT NULL AUTO_INCREMENT,
            name  VARCHAR(50) NOT NULL,
            icon  VARCHAR(10) NOT NULL DEFAULT '?',
            color VARCHAR(20) NOT NULL DEFAULT '#4CAF50',
            PRIMARY KEY (id),
            UNIQUE KEY uq_category_name (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id          INT          NOT NULL AUTO_INCREMENT,
            user_id     INT          NOT NULL,
            title       VARCHAR(100) NOT NULL,
            amount      DOUBLE       NOT NULL,
            category_id INT          DEFAULT NULL,
            date        DATE         NOT NULL,
            note        TEXT,
            created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            CONSTRAINT fk_exp_user     FOREIGN KEY (user_id)     REFERENCES users(id)      ON DELETE CASCADE,
            CONSTRAINT fk_exp_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
            INDEX idx_expenses_user_date (user_id, date),
            INDEX idx_expenses_category  (category_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id            INT    NOT NULL AUTO_INCREMENT,
            user_id       INT    NOT NULL,
            category_id   INT    NOT NULL,
            monthly_limit DOUBLE NOT NULL,
            PRIMARY KEY (id),
            UNIQUE KEY uq_budget (user_id, category_id),
            CONSTRAINT fk_bud_user     FOREIGN KEY (user_id)     REFERENCES users(id)      ON DELETE CASCADE,
            CONSTRAINT fk_bud_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            id           INT          NOT NULL AUTO_INCREMENT,
            username     VARCHAR(50)  NOT NULL,
            success      TINYINT(1)   NOT NULL DEFAULT 0,
            ip_hint      VARCHAR(50)  NOT NULL DEFAULT 'local',
            attempted_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            INDEX idx_attempts_username (username, attempted_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id         INT          NOT NULL AUTO_INCREMENT,
            actor_id   INT          DEFAULT NULL,
            actor_name VARCHAR(50)  NOT NULL,
            action     VARCHAR(50)  NOT NULL,
            target     VARCHAR(100) NOT NULL DEFAULT '',
            detail     VARCHAR(255) NOT NULL DEFAULT '',
            created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            CONSTRAINT fk_audit_actor FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL,
            INDEX idx_audit_actor (actor_id, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # Seed default categories (ignore if already exist)
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
    c.executemany("""
        INSERT IGNORE INTO categories (name, icon, color) VALUES (%s, %s, %s)
    """, defaults)

    conn.commit()
    c.close()
    conn.close()


# ── USER CRUD ─────────────────────────────────────────────────────────────────

def create_user(username, hashed_password, role="user"):
    """Insert a new user. Returns new user id, or None if username taken."""
    conn = get_connection()
    c    = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
            (username.strip(), hashed_password, role)
        )
        conn.commit()
        uid = c.lastrowid
    except IntegrityError:
        uid = None
    finally:
        c.close()
        conn.close()
    return uid


def get_user_by_username(username):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = %s", (username.strip(),))
    row  = c.fetchone()
    result = _row_to_dict(c, row)
    c.close(); conn.close()
    return result


def get_user_by_id(user_id):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    row  = c.fetchone()
    result = _row_to_dict(c, row)
    c.close(); conn.close()
    return result


def get_all_users():
    conn = get_connection()
    c    = conn.cursor()
    c.execute("""
        SELECT id, username, role, is_locked, locked_until, created_at
        FROM users ORDER BY created_at
    """)
    rows   = c.fetchall()
    result = _rows_to_dicts(c, rows)
    c.close(); conn.close()
    return result


def update_user_role(user_id, new_role):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("UPDATE users SET role=%s WHERE id=%s", (new_role, user_id))
    conn.commit()
    c.close(); conn.close()


def delete_user(user_id):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()
    c.close(); conn.close()


def change_password(user_id, new_hashed_password):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("UPDATE users SET password=%s WHERE id=%s",
              (new_hashed_password, user_id))
    conn.commit()
    c.close(); conn.close()


def count_admins():
    conn = get_connection()
    c    = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    n = c.fetchone()[0]
    c.close(); conn.close()
    return n


# ── LOCKOUT ───────────────────────────────────────────────────────────────────

def set_user_locked(user_id, locked_until_iso):
    """
    Lock or unlock a user.
    locked_until_iso = ISO datetime string ('2026-03-01T14:30:00'), or None to unlock.
    """
    conn = get_connection()
    c    = conn.cursor()
    is_locked = 1 if locked_until_iso else 0
    # MySQL DATETIME accepts 'YYYY-MM-DD HH:MM:SS' — replace T separator
    locked_until_mysql = locked_until_iso.replace("T", " ")[:19] if locked_until_iso else None
    c.execute(
        "UPDATE users SET is_locked=%s, locked_until=%s WHERE id=%s",
        (is_locked, locked_until_mysql, user_id)
    )
    conn.commit()
    c.close(); conn.close()


def record_login_attempt(username, success: bool, ip_hint: str = "local"):
    conn = get_connection()
    c    = conn.cursor()
    c.execute(
        "INSERT INTO login_attempts (username, success, ip_hint) VALUES (%s, %s, %s)",
        (username.strip(), 1 if success else 0, ip_hint)
    )
    conn.commit()
    c.close(); conn.close()


def count_recent_failures(username, within_minutes: int = 30) -> int:
    """Count failed login attempts for username in the last N minutes."""
    conn = get_connection()
    c    = conn.cursor()
    # MySQL uses DATE_SUB / NOW() instead of SQLite's datetime('now', ...)
    c.execute("""
        SELECT COUNT(*) FROM login_attempts
        WHERE username = %s
          AND success  = 0
          AND attempted_at >= DATE_SUB(NOW(), INTERVAL %s MINUTE)
    """, (username.strip(), within_minutes))
    n = c.fetchone()[0]
    c.close(); conn.close()
    return n


def clear_login_attempts(username):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("DELETE FROM login_attempts WHERE username=%s", (username.strip(),))
    conn.commit()
    c.close(); conn.close()


# ── AUDIT LOG ─────────────────────────────────────────────────────────────────

def write_audit(actor_id, actor_name: str, action: str,
                target: str = "", detail: str = ""):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO audit_log (actor_id, actor_name, action, target, detail)
        VALUES (%s, %s, %s, %s, %s)
    """, (actor_id, actor_name, action, target, detail))
    conn.commit()
    c.close(); conn.close()


def get_audit_log(limit: int = 100) -> list:
    conn = get_connection()
    c    = conn.cursor()
    c.execute("""
        SELECT * FROM audit_log
        ORDER BY created_at DESC LIMIT %s
    """, (limit,))
    rows   = c.fetchall()
    result = _rows_to_dicts(c, rows)
    c.close(); conn.close()
    return result


# ── EXPENSE CRUD ──────────────────────────────────────────────────────────────

def add_expense(user_id, title, amount, category_id, date, note=""):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO expenses (user_id, title, amount, category_id, date, note)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (user_id, title, float(amount), category_id, date, note))
    conn.commit()
    eid = c.lastrowid
    c.close(); conn.close()
    return eid


def update_expense(expense_id, title, amount, category_id, date, note=""):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("""
        UPDATE expenses
        SET title=%s, amount=%s, category_id=%s, date=%s, note=%s
        WHERE id=%s
    """, (title, float(amount), category_id, date, note, expense_id))
    conn.commit()
    c.close(); conn.close()


def delete_expense(expense_id):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("DELETE FROM expenses WHERE id=%s", (expense_id,))
    conn.commit()
    c.close(); conn.close()


def get_expense_by_id(expense_id):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("""
        SELECT e.*, c.name  AS category_name,
                    c.icon  AS category_icon,
                    c.color AS category_color,
                    u.username
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        LEFT JOIN users      u ON e.user_id     = u.id
        WHERE e.id = %s
    """, (expense_id,))
    row    = c.fetchone()
    result = _row_to_dict(c, row)
    c.close(); conn.close()
    return result


def get_all_expenses(user_id=None, limit=None, offset=0,
                     category_id=None, month=None, year=None):
    conn   = get_connection()
    c      = conn.cursor()
    query  = """
        SELECT e.*, c.name  AS category_name,
                    c.icon  AS category_icon,
                    c.color AS category_color,
                    u.username
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        LEFT JOIN users      u ON e.user_id     = u.id
        WHERE 1=1
    """
    params = []
    if user_id is not None:
        query += " AND e.user_id=%s"; params.append(user_id)
    if category_id:
        query += " AND e.category_id=%s"; params.append(category_id)
    if month and year:
        # MySQL uses MONTH() and YEAR() functions
        query += " AND MONTH(e.date)=%s AND YEAR(e.date)=%s"
        params.extend([month, year])
    elif year:
        query += " AND YEAR(e.date)=%s"; params.append(year)
    query += " ORDER BY e.date DESC, e.created_at DESC"
    if limit:
        query += " LIMIT %s OFFSET %s"; params.extend([limit, offset])
    c.execute(query, params)
    rows   = c.fetchall()
    result = _rows_to_dicts(c, rows)
    c.close(); conn.close()
    return result


# ── CATEGORY CRUD ─────────────────────────────────────────────────────────────

def get_all_categories():
    conn = get_connection()
    c    = conn.cursor()
    c.execute("SELECT * FROM categories ORDER BY name")
    rows   = c.fetchall()
    result = _rows_to_dicts(c, rows)
    c.close(); conn.close()
    return result


def add_category(name, icon="?", color="#4CAF50"):
    conn = get_connection()
    c    = conn.cursor()
    try:
        c.execute(
            "INSERT IGNORE INTO categories (name, icon, color) VALUES (%s, %s, %s)",
            (name, icon, color)
        )
        conn.commit()
        cid = c.lastrowid
    except IntegrityError:
        cid = None
    finally:
        c.close(); conn.close()
    return cid


def delete_category(category_id):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("DELETE FROM categories WHERE id=%s", (category_id,))
    conn.commit()
    c.close(); conn.close()


# ── AGGREGATIONS ──────────────────────────────────────────────────────────────

def get_total_by_month(month, year, user_id=None):
    conn = get_connection()
    c    = conn.cursor()
    q    = """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM expenses
        WHERE MONTH(date)=%s AND YEAR(date)=%s
    """
    p = [month, year]
    if user_id is not None:
        q += " AND user_id=%s"; p.append(user_id)
    c.execute(q, p)
    row = c.fetchone()
    c.close(); conn.close()
    return float(row[0]) if row else 0.0


def get_spending_by_category(month=None, year=None, user_id=None):
    conn      = get_connection()
    c         = conn.cursor()
    join_cond = "c.id = e.category_id"
    params    = []
    if user_id is not None:
        join_cond += " AND e.user_id=%s"; params.append(user_id)
    if month and year:
        join_cond += " AND MONTH(e.date)=%s AND YEAR(e.date)=%s"
        params.extend([month, year])

    query = f"""
        SELECT c.id, c.name, c.icon, c.color,
               COALESCE(SUM(e.amount), 0) AS total
        FROM categories c
        LEFT JOIN expenses e ON {join_cond}
        GROUP BY c.id, c.name, c.icon, c.color
        ORDER BY total DESC
    """
    c.execute(query, params)
    rows   = c.fetchall()
    result = _rows_to_dicts(c, rows)
    c.close(); conn.close()
    return result


def get_daily_totals(month, year, user_id=None):
    conn = get_connection()
    c    = conn.cursor()
    # MySQL uses DAY() instead of strftime('%d', ...)
    q    = """
        SELECT DAY(date) AS day, SUM(amount) AS total
        FROM expenses
        WHERE MONTH(date)=%s AND YEAR(date)=%s
    """
    p = [month, year]
    if user_id is not None:
        q += " AND user_id=%s"; p.append(user_id)
    q += " GROUP BY DAY(date) ORDER BY DAY(date)"
    c.execute(q, p)
    rows   = c.fetchall()
    result = _rows_to_dicts(c, rows)
    c.close(); conn.close()
    return result


def get_recent_expenses(n=5, user_id=None):
    return get_all_expenses(user_id=user_id, limit=n)


def get_global_stats():
    """Admin only — per-user spending totals."""
    conn = get_connection()
    c    = conn.cursor()
    c.execute("""
        SELECT u.id, u.username, u.role, u.is_locked,
               COUNT(e.id)               AS expense_count,
               COALESCE(SUM(e.amount),0) AS total_spent
        FROM users u
        LEFT JOIN expenses e ON u.id = e.user_id
        GROUP BY u.id, u.username, u.role, u.is_locked
        ORDER BY total_spent DESC
    """)
    rows   = c.fetchall()
    result = _rows_to_dicts(c, rows)
    c.close(); conn.close()
    return result


# ── BUDGET ────────────────────────────────────────────────────────────────────

def set_budget(user_id, category_id, monthly_limit):
    """Insert or update a budget limit (upsert using ON DUPLICATE KEY UPDATE)."""
    conn = get_connection()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO budgets (user_id, category_id, monthly_limit)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE monthly_limit = VALUES(monthly_limit)
    """, (user_id, category_id, float(monthly_limit)))
    conn.commit()
    c.close(); conn.close()


def get_budgets(user_id):
    conn = get_connection()
    c    = conn.cursor()
    c.execute("""
        SELECT b.*, c.name AS category_name, c.icon, c.color
        FROM budgets b
        JOIN categories c ON b.category_id = c.id
        WHERE b.user_id = %s
    """, (user_id,))
    rows   = c.fetchall()
    result = _rows_to_dicts(c, rows)
    c.close(); conn.close()
    return result