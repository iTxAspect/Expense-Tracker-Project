"""
tests/test_logic.py
Full unit & integration test suite for database.py and logic.py.
Uses a temporary file-based SQLite database (not :memory:) so that
foreign keys and cascade deletes work correctly across connections.
"""

import os
import sys
import tempfile
import pytest

# ── Make app/ importable ────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import database as db
import logic


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """
    Each test gets a clean database in a temp file.
    Resets logic.current_user between tests.
    """
    db_file = tmp_path / "test_expenses.db"
    db.DB_NAME = str(db_file)
    db.init_db()
    logic.current_user = None
    yield
    logic.current_user = None


# ─────────────────────────────────────────────────────────────────────────────
#  PASSWORD HASHING
# ─────────────────────────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        h = logic._hash_password("mysecret")
        assert "mysecret" not in h

    def test_hash_contains_salt_separator(self):
        h = logic._hash_password("mysecret")
        assert "$" in h
        salt, hsh = h.split("$", 1)
        assert len(salt) == 32          # 16 bytes → 32 hex chars
        assert len(hsh)  == 64          # SHA-256 → 64 hex chars

    def test_same_password_different_hashes(self):
        h1 = logic._hash_password("password")
        h2 = logic._hash_password("password")
        assert h1 != h2                  # different random salts

    def test_verify_correct_password(self):
        h = logic._hash_password("correct")
        assert logic._verify_password("correct", h) is True

    def test_verify_wrong_password(self):
        h = logic._hash_password("correct")
        assert logic._verify_password("wrong", h) is False

    def test_verify_empty_password(self):
        h = logic._hash_password("correct")
        assert logic._verify_password("", h) is False

    def test_verify_malformed_hash(self):
        assert logic._verify_password("anything", "notahash") is False


# ─────────────────────────────────────────────────────────────────────────────
#  REGISTRATION
# ─────────────────────────────────────────────────────────────────────────────

class TestRegister:
    def test_register_success(self):
        ok, user = logic.register("alice", "Password1")
        assert ok is True
        assert user["username"] == "alice"
        assert user["role"]     == "user"

    def test_register_admin_role(self):
        ok, user = logic.register("boss", "Password1", role="admin")
        assert ok is True
        assert user["role"] == "admin"

    def test_register_duplicate_username(self):
        logic.register("alice", "Password1")
        ok, msg = logic.register("alice", "Different1")
        assert ok is False
        assert "taken" in msg.lower()

    def test_register_username_too_short(self):
        ok, msg = logic.register("ab", "Password1")
        assert ok is False
        assert "3" in msg

    def test_register_empty_username(self):
        ok, msg = logic.register("", "Password1")
        assert ok is False

    def test_register_password_too_short(self):
        ok, msg = logic.register("alice", "abc")
        assert ok is False
        assert "6" in msg

    def test_register_invalid_role(self):
        ok, msg = logic.register("alice", "Password1", role="superuser")
        assert ok is False

    def test_password_not_stored_plaintext(self):
        logic.register("alice", "MySecret99")
        row = db.get_user_by_username("alice")
        assert row["password"] != "MySecret99"
        assert "$" in row["password"]


# ─────────────────────────────────────────────────────────────────────────────
#  LOGIN / LOGOUT / SESSION
# ─────────────────────────────────────────────────────────────────────────────

class TestAuth:
    def setup_method(self):
        logic.register("alice", "AlicePass1")
        logic.register("admin_user", "AdminPass1", role="admin")

    def test_login_success(self):
        ok, user = logic.login("alice", "AlicePass1")
        assert ok is True
        assert user["username"] == "alice"
        assert logic.current_user is not None

    def test_login_wrong_password(self):
        ok, msg = logic.login("alice", "wrongpass")
        assert ok is False
        assert "incorrect" in msg.lower()
        assert logic.current_user is None

    def test_login_unknown_user(self):
        ok, msg = logic.login("nobody", "pass")
        assert ok is False
        assert "not found" in msg.lower()

    def test_login_empty_credentials(self):
        ok, msg = logic.login("", "")
        assert ok is False

    def test_logout_clears_session(self):
        logic.login("alice", "AlicePass1")
        logic.logout()
        assert logic.current_user is None
        assert logic.is_logged_in() is False

    def test_is_admin_false_for_user(self):
        logic.login("alice", "AlicePass1")
        assert logic.is_admin() is False

    def test_is_admin_true_for_admin(self):
        logic.login("admin_user", "AdminPass1")
        assert logic.is_admin() is True

    def test_is_logged_in(self):
        assert logic.is_logged_in() is False
        logic.login("alice", "AlicePass1")
        assert logic.is_logged_in() is True


# ─────────────────────────────────────────────────────────────────────────────
#  CHANGE PASSWORD
# ─────────────────────────────────────────────────────────────────────────────

class TestChangePassword:
    def setup_method(self):
        logic.register("alice", "OldPass1")
        logic.login("alice", "OldPass1")

    def test_change_password_success(self):
        ok, msg = logic.change_own_password("OldPass1", "NewPass99")
        assert ok is True
        logic.logout()
        ok, _ = logic.login("alice", "NewPass99")
        assert ok is True

    def test_change_password_wrong_old(self):
        ok, msg = logic.change_own_password("WrongOld", "NewPass99")
        assert ok is False
        assert "incorrect" in msg.lower()

    def test_change_password_too_short(self):
        ok, msg = logic.change_own_password("OldPass1", "abc")
        assert ok is False
        assert "6" in msg

    def test_change_password_not_logged_in(self):
        logic.logout()
        ok, msg = logic.change_own_password("OldPass1", "NewPass99")
        assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
#  EXPENSE VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

class TestExpenseValidation:
    def test_valid_expense(self):
        ok, err = logic.validate_expense("Coffee", "4.50", 1, "2026-03-01")
        assert ok is True
        assert err is None

    def test_empty_title(self):
        ok, err = logic.validate_expense("", "4.50", 1, "2026-03-01")
        assert ok is False

    def test_whitespace_title(self):
        ok, err = logic.validate_expense("   ", "4.50", 1, "2026-03-01")
        assert ok is False

    def test_zero_amount(self):
        ok, err = logic.validate_expense("Coffee", "0", 1, "2026-03-01")
        assert ok is False

    def test_negative_amount(self):
        ok, err = logic.validate_expense("Coffee", "-5", 1, "2026-03-01")
        assert ok is False

    def test_non_numeric_amount(self):
        ok, err = logic.validate_expense("Coffee", "abc", 1, "2026-03-01")
        assert ok is False

    def test_no_category(self):
        ok, err = logic.validate_expense("Coffee", "4.50", None, "2026-03-01")
        assert ok is False

    def test_invalid_date_format(self):
        ok, err = logic.validate_expense("Coffee", "4.50", 1, "01/03/2026")
        assert ok is False

    def test_invalid_date_string(self):
        ok, err = logic.validate_expense("Coffee", "4.50", 1, "not-a-date")
        assert ok is False

    def test_boundary_amount_minimum(self):
        ok, err = logic.validate_expense("Coffee", "0.01", 1, "2026-03-01")
        assert ok is True

    def test_boundary_amount_large(self):
        ok, err = logic.validate_expense("Car", "99999.99", 1, "2026-03-01")
        assert ok is True


# ─────────────────────────────────────────────────────────────────────────────
#  EXPENSE CRUD
# ─────────────────────────────────────────────────────────────────────────────

class TestExpenseCRUD:
    def setup_method(self):
        logic.register("alice", "AlicePass1")
        logic.register("bob",   "BobPass1")
        logic.register("admin", "AdminPass1", role="admin")
        logic.login("alice", "AlicePass1")
        self.cat_id = db.get_all_categories()[0]["id"]

    def test_add_expense_success(self):
        ok, eid = logic.add_expense("Lunch", "12.50", self.cat_id, "2026-03-01")
        assert ok is True
        assert isinstance(eid, int)

    def test_add_expense_not_logged_in(self):
        logic.logout()
        ok, msg = logic.add_expense("Lunch", "12.50", self.cat_id, "2026-03-01")
        assert ok is False

    def test_add_expense_invalid(self):
        ok, msg = logic.add_expense("", "12.50", self.cat_id, "2026-03-01")
        assert ok is False

    def test_get_expenses_only_own(self):
        logic.add_expense("Alice item", "10", self.cat_id, "2026-03-01")
        logic.logout()
        logic.login("bob", "BobPass1")
        logic.add_expense("Bob item", "20", self.cat_id, "2026-03-01")
        exps = logic.get_expenses()
        assert all(e["username"] == "bob" for e in exps)

    def test_admin_sees_all_expenses(self):
        logic.add_expense("Alice item", "10", self.cat_id, "2026-03-01")
        logic.logout()
        logic.login("bob", "BobPass1")
        logic.add_expense("Bob item", "20", self.cat_id, "2026-03-01")
        logic.logout()
        logic.login("admin", "AdminPass1")
        exps = logic.get_expenses()
        users = {e["username"] for e in exps}
        assert "alice" in users
        assert "bob"   in users

    def test_update_own_expense(self):
        ok, eid = logic.add_expense("Lunch", "12.50", self.cat_id, "2026-03-01")
        ok, msg = logic.update_expense(eid, "Dinner", "25.00", self.cat_id, "2026-03-01")
        assert ok is True
        exp = logic.get_expense(eid)
        assert exp["title"]  == "Dinner"
        assert exp["amount"] == 25.00

    def test_user_cannot_edit_others_expense(self):
        ok, eid = logic.add_expense("Alice item", "10", self.cat_id, "2026-03-01")
        logic.logout()
        logic.login("bob", "BobPass1")
        ok, msg = logic.update_expense(eid, "Hacked", "999", self.cat_id, "2026-03-01")
        assert ok is False

    def test_admin_can_edit_any_expense(self):
        ok, eid = logic.add_expense("Alice item", "10", self.cat_id, "2026-03-01")
        logic.logout()
        logic.login("admin", "AdminPass1")
        ok, msg = logic.update_expense(eid, "Changed", "50", self.cat_id, "2026-03-01")
        assert ok is True

    def test_delete_own_expense(self):
        ok, eid = logic.add_expense("Lunch", "12.50", self.cat_id, "2026-03-01")
        logic.delete_expense(eid)
        assert logic.get_expense(eid) is None

    def test_user_cannot_delete_others_expense(self):
        ok, eid = logic.add_expense("Alice item", "10", self.cat_id, "2026-03-01")
        logic.logout()
        logic.login("bob", "BobPass1")
        logic.delete_expense(eid)       # silently ignored
        logic.logout()
        logic.login("alice", "AlicePass1")
        assert logic.get_expense(eid) is not None   # still exists


# ─────────────────────────────────────────────────────────────────────────────
#  BUDGET
# ─────────────────────────────────────────────────────────────────────────────

class TestBudget:
    def setup_method(self):
        logic.register("alice", "AlicePass1")
        logic.login("alice", "AlicePass1")
        self.cat_id = db.get_all_categories()[0]["id"]

    def test_set_budget_success(self):
        ok, msg = logic.set_budget(self.cat_id, "200")
        assert ok is True

    def test_set_budget_invalid(self):
        ok, msg = logic.set_budget(self.cat_id, "abc")
        assert ok is False

    def test_set_budget_negative(self):
        ok, msg = logic.set_budget(self.cat_id, "-50")
        assert ok is False

    def test_get_budgets(self):
        logic.set_budget(self.cat_id, "150")
        budgets = logic.get_budgets()
        assert any(b["category_id"] == self.cat_id for b in budgets)

    def test_over_budget_flag(self):
        from datetime import datetime
        logic.set_budget(self.cat_id, "10.00")
        logic.add_expense("Big purchase", "50.00", self.cat_id,
                          datetime.now().strftime("%Y-%m-%d"))
        data = logic.get_dashboard_data()
        for cat in data["by_category"]:
            if cat["id"] == self.cat_id:
                assert cat["over_budget"] is True
                break

    def test_budget_not_over_when_under(self):
        from datetime import datetime
        logic.set_budget(self.cat_id, "100.00")
        logic.add_expense("Small", "5.00", self.cat_id,
                          datetime.now().strftime("%Y-%m-%d"))
        data = logic.get_dashboard_data()
        for cat in data["by_category"]:
            if cat["id"] == self.cat_id:
                assert cat["over_budget"] is False
                break


# ─────────────────────────────────────────────────────────────────────────────
#  ADMIN USER MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

class TestAdminManagement:
    def setup_method(self):
        logic.register("admin", "AdminPass1", role="admin")
        logic.register("alice", "AlicePass1")
        logic.register("bob",   "BobPass1")
        logic.login("admin", "AdminPass1")
        self.alice_id = db.get_user_by_username("alice")["id"]
        self.bob_id   = db.get_user_by_username("bob")["id"]

    def test_admin_sees_all_users(self):
        users = logic.admin_get_all_users()
        names = {u["username"] for u in users}
        assert {"admin", "alice", "bob"} <= names

    def test_non_admin_sees_empty(self):
        logic.logout()
        logic.login("alice", "AlicePass1")
        assert logic.admin_get_all_users() == []

    def test_change_role_to_admin(self):
        ok, msg = logic.admin_change_role(self.alice_id, "admin")
        assert ok is True
        user = db.get_user_by_id(self.alice_id)
        assert user["role"] == "admin"

    def test_change_role_to_user(self):
        logic.admin_change_role(self.alice_id, "admin")
        ok, msg = logic.admin_change_role(self.alice_id, "user")
        assert ok is True

    def test_cannot_demote_last_admin(self):
        admin_id = db.get_user_by_username("admin")["id"]
        ok, msg = logic.admin_change_role(admin_id, "user")
        assert ok is False
        assert "last admin" in msg.lower()

    def test_delete_user_cascades_expenses(self):
        logic.logout()
        logic.login("alice", "AlicePass1")
        cat_id = db.get_all_categories()[0]["id"]
        logic.add_expense("Alice expense", "10", cat_id, "2026-03-01")
        logic.logout()
        logic.login("admin", "AdminPass1")
        logic.admin_delete_user(self.alice_id)
        exps = db.get_all_expenses()
        assert not any(e["user_id"] == self.alice_id for e in exps)

    def test_cannot_delete_self(self):
        admin_id = db.get_user_by_username("admin")["id"]
        ok, msg = logic.admin_delete_user(admin_id)
        assert ok is False
        assert "own" in msg.lower()

    def test_non_admin_cannot_delete_user(self):
        logic.logout()
        logic.login("alice", "AlicePass1")
        ok, msg = logic.admin_delete_user(self.bob_id)
        assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
#  DATE & FORMAT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

class TestHelpers:
    def test_today_str_format(self):
        s = logic.today_str()
        assert len(s) == 10
        assert s[4] == "-" and s[7] == "-"

    def test_parse_valid_date(self):
        d = logic.parse_date("2026-03-15")
        assert d.year == 2026 and d.month == 3 and d.day == 15

    def test_parse_invalid_date(self):
        assert logic.parse_date("not-a-date") is None
        assert logic.parse_date("15/03/2026") is None
        assert logic.parse_date("")            is None

    def test_format_currency(self):
        assert logic.format_currency(12.5)    == "$12.50"
        assert logic.format_currency(1000)    == "$1,000.00"
        assert logic.format_currency(0)       == "$0.00"
        assert logic.format_currency("abc")   == "$0.00"

    def test_month_year_label(self):
        assert logic.month_year_label(3, 2026) == "March 2026"
        assert logic.month_year_label(1, 2025) == "January 2025"

    def test_prev_month_normal(self):
        assert logic.prev_month(3, 2026) == (2, 2026)

    def test_prev_month_wrap(self):
        assert logic.prev_month(1, 2026) == (12, 2025)

    def test_next_month_normal(self):
        assert logic.next_month(3, 2026) == (4, 2026)

    def test_next_month_wrap(self):
        assert logic.next_month(12, 2025) == (1, 2026)


# ─────────────────────────────────────────────────────────────────────────────
#  DATABASE INIT & SEED
# ─────────────────────────────────────────────────────────────────────────────

class TestDatabase:
    def test_categories_seeded(self):
        cats = db.get_all_categories()
        assert len(cats) >= 8
        names = [c["name"] for c in cats]
        assert "Food & Dining" in names
        assert "Transport"     in names

    def test_init_db_idempotent(self):
        db.init_db()   # second call — should not raise
        db.init_db()   # third call
        cats = db.get_all_categories()
        assert len(cats) >= 8   # no duplicates

    def test_seed_admin_creates_admin(self):
        logic.seed_admin_if_needed()
        admin = db.get_user_by_username("admin")
        assert admin is not None
        assert admin["role"] == "admin"

    def test_seed_admin_only_once(self):
        logic.seed_admin_if_needed()
        logic.seed_admin_if_needed()
        assert db.count_admins() == 1
