"""
gui.py - Full Kivy GUI for Android Expense Tracker
Screens: Dashboard, Add/Edit Expense, Expense List, Categories, Budgets
Run with: python gui.py
Build for Android with: buildozer android debug
"""

# ── Kivy config MUST come before any other kivy imports ──────────────────────
import os
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")

from kivy.config import Config
Config.set("graphics", "width",  "400")
Config.set("graphics", "height", "800")
Config.set("graphics", "resizable", "0")

# ── Imports ───────────────────────────────────────────────────────────────────
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.metrics import dp, sp
from kivy.clock import Clock
from kivy.utils import get_color_from_hex
from datetime import datetime

import logic

# ── Colour Palette ────────────────────────────────────────────────────────────
C = {
    "bg":        "#0F1117",
    "surface":   "#1A1D27",
    "card":      "#22263A",
    "accent":    "#6C63FF",
    "accent2":   "#FF6584",
    "green":     "#4ECCA3",
    "text":      "#EAEAEA",
    "subtext":   "#8892A4",
    "error":     "#FF5370",
    "warning":   "#FFB347",
    "white":     "#FFFFFF",
    "divider":   "#2E3250",
}


def hex_c(key):
    return get_color_from_hex(C[key])


# ── Reusable Widget Helpers ───────────────────────────────────────────────────

class ColoredBox(BoxLayout):
    """A BoxLayout with a solid background color."""
    def __init__(self, bg_color, radius=0, **kwargs):
        super().__init__(**kwargs)
        self._bg_color = bg_color
        self._radius = radius
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*get_color_from_hex(self._bg_color))
            if self._radius:
                RoundedRectangle(pos=self.pos, size=self.size, radius=[self._radius])
            else:
                Rectangle(pos=self.pos, size=self.size)


def make_label(text, size=14, color="text", bold=False, halign="left", **kwargs):
    lbl = Label(
        text=text,
        font_size=sp(size),
        color=hex_c(color),
        bold=bold,
        halign=halign,
        text_size=(None, None),
        **kwargs
    )
    lbl.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
    return lbl


def make_button(text, bg=C["accent"], fg=C["white"], on_press=None,
                height=dp(48), radius=dp(12), font_size=15, **kwargs):
    btn = Button(
        text=text,
        size_hint_y=None,
        height=height,
        font_size=sp(font_size),
        color=get_color_from_hex(fg),
        background_normal="",
        background_color=get_color_from_hex(bg),
        **kwargs
    )
    if on_press:
        btn.bind(on_press=on_press)
    return btn


def make_input(hint, multiline=False, input_filter=None, height=dp(48), **kwargs):
    ti = TextInput(
        hint_text=hint,
        multiline=multiline,
        input_filter=input_filter,
        size_hint_y=None,
        height=height,
        font_size=sp(14),
        background_color=get_color_from_hex(C["card"]),
        foreground_color=hex_c("text"),
        hint_text_color=hex_c("subtext"),
        cursor_color=hex_c("accent"),
        padding=[dp(12), dp(10)],
        **kwargs
    )
    return ti


def card_widget(padding=dp(16), spacing=dp(8), orientation="vertical", **kwargs):
    box = ColoredBox(bg_color=C["card"], radius=dp(14),
                     orientation=orientation,
                     padding=padding, spacing=spacing, **kwargs)
    return box


def show_popup(title, message, color="text"):
    content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
    content.add_widget(make_label(message, size=14, color=color, halign="center"))
    btn = make_button("OK", height=dp(44))
    content.add_widget(btn)
    popup = Popup(
        title=title,
        content=content,
        size_hint=(0.85, None),
        height=dp(200),
        background_color=hex_c("surface"),
        title_color=hex_c("text"),
        separator_color=hex_c("accent"),
    )
    btn.bind(on_press=popup.dismiss)
    popup.open()


def confirm_popup(title, message, on_confirm):
    content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
    content.add_widget(make_label(message, size=14, color="subtext", halign="center"))
    btns = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(44))
    b_no  = make_button("Cancel", bg=C["card"])
    b_yes = make_button("Delete",  bg=C["error"])
    btns.add_widget(b_no)
    btns.add_widget(b_yes)
    content.add_widget(btns)
    popup = Popup(
        title=title, content=content,
        size_hint=(0.85, None), height=dp(220),
        background_color=hex_c("surface"),
        title_color=hex_c("text"),
        separator_color=hex_c("accent2"),
    )
    b_no.bind(on_press=popup.dismiss)
    def _confirm(_):
        popup.dismiss()
        on_confirm()
    b_yes.bind(on_press=_confirm)
    popup.open()


# ── Nav Bar ───────────────────────────────────────────────────────────────────

class NavBar(ColoredBox):
    TABS = [
        ("🏠", "Dashboard",  "dashboard"),
        ("📋", "Expenses",   "expenses"),
        ("➕", "Add",        "add_expense"),
        ("📊", "Stats",      "stats"),
        ("⚙️", "Settings",   "settings"),
    ]

    def __init__(self, screen_manager, **kwargs):
        super().__init__(bg_color=C["surface"], orientation="horizontal",
                         size_hint_y=None, height=dp(60),
                         padding=[dp(4), 0], spacing=0, **kwargs)
        self.sm = screen_manager
        self._btns = {}
        for icon, label, screen in self.TABS:
            btn = Button(
                text=f"{icon}\n{label}",
                font_size=sp(10),
                color=hex_c("subtext"),
                background_normal="",
                background_color=(0, 0, 0, 0),
                halign="center",
            )
            btn.bind(on_press=lambda b, s=screen: self._go(s))
            self._btns[screen] = btn
            self.add_widget(btn)

    def _go(self, screen_name):
        self.sm.transition = SlideTransition(duration=0.2)
        self.sm.current = screen_name
        self.highlight(screen_name)

    def highlight(self, screen_name):
        for name, btn in self._btns.items():
            if name == screen_name:
                btn.color = hex_c("accent")
            else:
                btn.color = hex_c("subtext")


# ── Base Screen ───────────────────────────────────────────────────────────────

class BaseScreen(Screen):
    def __init__(self, nav_bar=None, **kwargs):
        super().__init__(**kwargs)
        self.nav_bar = nav_bar
        root = ColoredBox(bg_color=C["bg"], orientation="vertical",
                          padding=0, spacing=0)
        self.content_area = BoxLayout(orientation="vertical",
                                      padding=[dp(14), dp(12)],
                                      spacing=dp(10))
        root.add_widget(self.content_area)
        if nav_bar:
            root.add_widget(nav_bar)
        self.add_widget(root)

    def go(self, screen_name):
        app = App.get_running_app()
        app.sm.current = screen_name
        # Highlight the correct tab on the destination screen's own navbar
        dest = app.sm.get_screen(screen_name)
        if dest.nav_bar:
            dest.nav_bar.highlight(screen_name)


# ── Dashboard Screen ──────────────────────────────────────────────────────────

class DashboardScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_month = datetime.now().month
        self.current_year  = datetime.now().year
        self._build()

    def _build(self):
        ca = self.content_area
        ca.clear_widgets()

        # Header
        header = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        header.add_widget(make_label("💸 ExpenseTracker", size=20, color="text", bold=True))
        header.add_widget(Widget())
        btn_add = make_button("+ Add", height=dp(36), size_hint_x=None, width=dp(80))
        btn_add.bind(on_press=lambda _: self.go("add_expense"))
        header.add_widget(btn_add)
        ca.add_widget(header)

        # Month navigator
        nav = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(4))
        btn_prev = make_button("◀", bg=C["card"], height=dp(36),
                               size_hint_x=None, width=dp(40))
        btn_next = make_button("▶", bg=C["card"], height=dp(36),
                               size_hint_x=None, width=dp(40))
        self.month_lbl = make_label(
            logic.month_year_label(self.current_month, self.current_year),
            size=15, color="text", bold=True, halign="center"
        )
        btn_prev.bind(on_press=self._prev_month)
        btn_next.bind(on_press=self._next_month)
        nav.add_widget(btn_prev)
        nav.add_widget(self.month_lbl)
        nav.add_widget(btn_next)
        ca.add_widget(nav)

        # Scrollable body
        scroll = ScrollView(do_scroll_x=False)
        body = BoxLayout(orientation="vertical", spacing=dp(12),
                         size_hint_y=None, padding=[0, dp(4)])
        body.bind(minimum_height=body.setter("height"))
        self._populate_body(body)
        scroll.add_widget(body)
        ca.add_widget(scroll)

    def _populate_body(self, body):
        data = logic.get_dashboard_data(self.current_month, self.current_year)

        # Total card
        total_card = card_widget(size_hint_y=None, height=dp(90))
        total_card.add_widget(make_label("Total Spending", size=12, color="subtext"))
        total_card.add_widget(make_label(data["total_display"], size=30,
                                         color="accent", bold=True))
        body.add_widget(total_card)

        # Category breakdown
        body.add_widget(make_label("By Category", size=13, color="subtext",
                                   size_hint_y=None, height=dp(20)))
        for cat in data["by_category"]:
            if cat["total"] == 0:
                continue
            row = card_widget(size_hint_y=None, height=dp(72),
                               orientation="vertical", spacing=dp(4))
            top = BoxLayout(size_hint_y=None, height=dp(24))
            top.add_widget(make_label(
                f"{cat['icon']} {cat['name']}", size=13, color="text"))
            top.add_widget(make_label(cat["total_display"], size=13,
                                       color="accent2", halign="right"))
            row.add_widget(top)
            # Progress bar
            if cat.get("budget_pct") is not None:
                bar_bg = ColoredBox(bg_color=C["divider"], radius=dp(4),
                                    size_hint_y=None, height=dp(8))
                fill_color = C["error"] if cat["over_budget"] else C["green"]
                fill_pct   = cat["budget_pct"] / 100
                bar_fill = ColoredBox(bg_color=fill_color, radius=dp(4),
                                      size_hint=(fill_pct, 1))
                bar_bg.add_widget(bar_fill)
                row.add_widget(bar_bg)
                budget_lbl = f"Budget: {logic.format_currency(cat['budget_limit'])}"
                if cat["over_budget"]:
                    budget_lbl += "  ⚠️ Over budget!"
                row.add_widget(make_label(budget_lbl, size=11, color="subtext",
                                           size_hint_y=None, height=dp(14)))
            body.add_widget(row)

        # Recent expenses
        body.add_widget(make_label("Recent Expenses", size=13, color="subtext",
                                   size_hint_y=None, height=dp(20)))
        if not data["recent"]:
            body.add_widget(make_label("No expenses yet – tap + Add!",
                                        size=13, color="subtext", halign="center",
                                        size_hint_y=None, height=dp(40)))
        for exp in data["recent"]:
            self._expense_row(body, exp)

    def _expense_row(self, parent, exp):
        row = card_widget(orientation="horizontal", size_hint_y=None, height=dp(52),
                           padding=[dp(10), dp(6)], spacing=dp(8))
        icon_lbl = make_label(exp.get("category_icon", "💰"), size=20,
                               size_hint_x=None, width=dp(32))
        info = BoxLayout(orientation="vertical", spacing=dp(2))
        info.add_widget(make_label(exp["title"], size=13, color="text", bold=True))
        info.add_widget(make_label(exp["date_display"], size=11, color="subtext"))
        amt_lbl = make_label(exp["amount_display"], size=14, color="accent2",
                              bold=True, halign="right", size_hint_x=None, width=dp(80))
        row.add_widget(icon_lbl)
        row.add_widget(info)
        row.add_widget(amt_lbl)
        parent.add_widget(row)

    def _prev_month(self, _):
        self.current_month, self.current_year = logic.prev_month(
            self.current_month, self.current_year)
        self.on_enter()

    def _next_month(self, _):
        self.current_month, self.current_year = logic.next_month(
            self.current_month, self.current_year)
        self.on_enter()

    def on_enter(self, *_):
        self._build()


# ── Expenses List Screen ──────────────────────────────────────────────────────

class ExpensesScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def _build(self):
        ca = self.content_area
        ca.clear_widgets()

        header = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        header.add_widget(make_label("📋 All Expenses", size=18, bold=True))
        header.add_widget(Widget())
        btn_add = make_button("+ Add", height=dp(36), size_hint_x=None, width=dp(80))
        btn_add.bind(on_press=lambda _: self.go("add_expense"))
        header.add_widget(btn_add)
        ca.add_widget(header)

        # Filter spinner
        cats = [("", "All Categories")] + logic.get_category_names()
        self._cat_map_by_display = {f"{icon} {nm}" if icon else nm: cid
                                     for cid, nm in (logic.get_category_names())}
        spinner_values = [v for _, v in cats]
        self.cat_spinner = Spinner(
            text="All Categories",
            values=spinner_values,
            size_hint_y=None, height=dp(40),
            font_size=sp(13),
            background_normal="",
            background_color=get_color_from_hex(C["card"]),
            color=hex_c("text"),
        )
        self.cat_spinner.bind(text=lambda _, v: self._refresh())
        ca.add_widget(self.cat_spinner)

        self.list_scroll = ScrollView(do_scroll_x=False)
        self.list_body = BoxLayout(orientation="vertical", spacing=dp(8),
                                   size_hint_y=None, padding=[0, dp(4)])
        self.list_body.bind(minimum_height=self.list_body.setter("height"))
        self.list_scroll.add_widget(self.list_body)
        ca.add_widget(self.list_scroll)
        self._refresh()

    def _refresh(self):
        self.list_body.clear_widgets()
        # Determine category filter
        sel = self.cat_spinner.text
        cat_id = None
        if sel != "All Categories":
            for cid, name in logic.get_category_names():
                display = f"{dict(zip(['id','name','icon','color'], []))} "
                # match by display string
                if f"{logic.get_category_map()[cid]['icon']} {name}" == sel or name == sel:
                    cat_id = cid
                    break

        expenses = logic.get_expenses(category_id=cat_id)
        if not expenses:
            self.list_body.add_widget(
                make_label("No expenses found.", size=14, color="subtext",
                            halign="center", size_hint_y=None, height=dp(60))
            )
            return

        for exp in expenses:
            self._expense_item(exp)

    def _expense_item(self, exp):
        row = card_widget(orientation="horizontal", size_hint_y=None, height=dp(64),
                           padding=[dp(10), dp(6)], spacing=dp(8))
        icon_lbl = make_label(exp.get("category_icon", "💰"), size=22,
                               size_hint_x=None, width=dp(36))
        info = BoxLayout(orientation="vertical", spacing=dp(2))
        info.add_widget(make_label(exp["title"], size=13, color="text", bold=True))
        info.add_widget(make_label(
            f"{exp['category_name']}  •  {exp['date_display']}",
            size=11, color="subtext"))
        right = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(80),
                           spacing=dp(2))
        right.add_widget(make_label(exp["amount_display"], size=14, color="accent2",
                                     bold=True, halign="right"))
        btn_row = BoxLayout(spacing=dp(4), size_hint_y=None, height=dp(26))
        b_edit = make_button("✏️", bg=C["accent"], height=dp(26),
                              size_hint_x=None, width=dp(36), font_size=11)
        b_del  = make_button("🗑", bg=C["error"],  height=dp(26),
                              size_hint_x=None, width=dp(36), font_size=11)
        exp_id = exp["id"]
        b_edit.bind(on_press=lambda _, eid=exp_id: self._edit(eid))
        b_del.bind(on_press=lambda  _, eid=exp_id: self._delete(eid))
        btn_row.add_widget(b_edit)
        btn_row.add_widget(b_del)
        right.add_widget(btn_row)
        row.add_widget(icon_lbl)
        row.add_widget(info)
        row.add_widget(right)
        self.list_body.add_widget(row)

    def _edit(self, expense_id):
        app = App.get_running_app()
        app.sm.get_screen("add_expense").load_expense(expense_id)
        self.go("add_expense")

    def _delete(self, expense_id):
        def _do_delete():
            logic.delete_expense(expense_id)
            self._refresh()
        confirm_popup("Delete Expense",
                      "Are you sure you want to delete this expense?",
                      _do_delete)

    def on_enter(self, *_):
        self._build()


# ── Add / Edit Expense Screen ─────────────────────────────────────────────────

class AddExpenseScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._editing_id = None
        self._build()

    def _build(self):
        ca = self.content_area
        ca.clear_widgets()

        self._header_lbl = make_label("➕ Add Expense", size=18, bold=True,
                                       size_hint_y=None, height=dp(36))
        ca.add_widget(self._header_lbl)

        scroll = ScrollView(do_scroll_x=False)
        form = BoxLayout(orientation="vertical", spacing=dp(12),
                          size_hint_y=None, padding=[0, dp(6)])
        form.bind(minimum_height=form.setter("height"))

        form.add_widget(make_label("Title *", size=12, color="subtext",
                                    size_hint_y=None, height=dp(18)))
        self.inp_title = make_input("e.g. Lunch at café")
        form.add_widget(self.inp_title)

        form.add_widget(make_label("Amount *", size=12, color="subtext",
                                    size_hint_y=None, height=dp(18)))
        self.inp_amount = make_input("0.00", input_filter="float")
        form.add_widget(self.inp_amount)

        form.add_widget(make_label("Category *", size=12, color="subtext",
                                    size_hint_y=None, height=dp(18)))
        cat_values = [f"{icon} {nm}" for _, (icon, nm)
                      in [(cid, (logic.get_category_map()[cid]["icon"],
                                  logic.get_category_map()[cid]["name"]))
                          for cid, _ in logic.get_category_names()]]
        # Simpler: rebuild from get_category_names
        cat_names = logic.get_category_names()
        self._cat_id_for_display = {}
        display_vals = []
        for cid, disp in cat_names:
            self._cat_id_for_display[disp] = cid
            display_vals.append(disp)
        self.cat_spinner = Spinner(
            text=display_vals[0] if display_vals else "Select",
            values=display_vals,
            size_hint_y=None, height=dp(44),
            font_size=sp(13),
            background_normal="",
            background_color=get_color_from_hex(C["card"]),
            color=hex_c("text"),
        )
        form.add_widget(self.cat_spinner)

        form.add_widget(make_label("Date * (YYYY-MM-DD)", size=12, color="subtext",
                                    size_hint_y=None, height=dp(18)))
        self.inp_date = make_input("YYYY-MM-DD")
        self.inp_date.text = logic.today_str()
        form.add_widget(self.inp_date)

        form.add_widget(make_label("Note (optional)", size=12, color="subtext",
                                    size_hint_y=None, height=dp(18)))
        self.inp_note = make_input("Add a note…", multiline=True, height=dp(70))
        form.add_widget(self.inp_note)

        form.add_widget(Widget(size_hint_y=None, height=dp(8)))

        self.btn_save = make_button("💾  Save Expense")
        self.btn_save.bind(on_press=self._save)
        form.add_widget(self.btn_save)

        self.btn_cancel = make_button("Cancel", bg=C["card"])
        self.btn_cancel.bind(on_press=self._cancel)
        form.add_widget(self.btn_cancel)

        scroll.add_widget(form)
        ca.add_widget(scroll)

    def load_expense(self, expense_id):
        """Populate the form with an existing expense for editing."""
        self._editing_id = expense_id
        exp = logic.get_expense(expense_id)
        if not exp:
            return
        self._header_lbl.text = "✏️ Edit Expense"
        self.btn_save.text     = "💾  Update Expense"
        self.inp_title.text    = exp["title"]
        self.inp_amount.text   = str(exp["amount"])
        self.inp_date.text     = exp["date"]
        self.inp_note.text     = exp.get("note", "")
        # Set spinner
        cat_map = logic.get_category_map()
        cat = cat_map.get(exp["category_id"])
        if cat:
            disp = f"{cat['icon']} {cat['name']}"
            if disp in self.cat_spinner.values:
                self.cat_spinner.text = disp

    def _save(self, _):
        title   = self.inp_title.text.strip()
        amount  = self.inp_amount.text.strip()
        date    = self.inp_date.text.strip()
        note    = self.inp_note.text.strip()
        cat_disp = self.cat_spinner.text
        cat_id   = self._cat_id_for_display.get(cat_disp)

        if self._editing_id:
            ok, msg = logic.update_expense(
                self._editing_id, title, amount, cat_id, date, note)
        else:
            ok, msg = logic.add_expense(title, amount, cat_id, date, note)

        if ok:
            show_popup("✅ Saved", "Expense saved successfully!", color="green")
            self._reset()
            Clock.schedule_once(lambda _: self.go("expenses"), 0.6)
        else:
            show_popup("❌ Error", msg, color="error")

    def _cancel(self, _):
        self._reset()
        self.go("expenses")

    def _reset(self):
        self._editing_id  = None
        self._header_lbl.text = "➕ Add Expense"
        self.btn_save.text    = "💾  Save Expense"
        self.inp_title.text   = ""
        self.inp_amount.text  = ""
        self.inp_date.text    = logic.today_str()
        self.inp_note.text    = ""

    def on_enter(self, *_):
        if not self._editing_id:
            self._reset()
            self._build()


# ── Stats Screen ──────────────────────────────────────────────────────────────

class StatsScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_month = datetime.now().month
        self.current_year  = datetime.now().year
        self._build()

    def _build(self):
        ca = self.content_area
        ca.clear_widgets()
        ca.add_widget(make_label("📊 Statistics", size=18, bold=True,
                                  size_hint_y=None, height=dp(36)))

        nav = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(4))
        btn_prev = make_button("◀", bg=C["card"], height=dp(36),
                               size_hint_x=None, width=dp(40))
        btn_next = make_button("▶", bg=C["card"], height=dp(36),
                               size_hint_x=None, width=dp(40))
        self.month_lbl = make_label(
            logic.month_year_label(self.current_month, self.current_year),
            size=15, color="text", bold=True, halign="center"
        )
        btn_prev.bind(on_press=self._prev)
        btn_next.bind(on_press=self._next)
        nav.add_widget(btn_prev)
        nav.add_widget(self.month_lbl)
        nav.add_widget(btn_next)
        ca.add_widget(nav)

        scroll = ScrollView(do_scroll_x=False)
        body = BoxLayout(orientation="vertical", spacing=dp(10),
                          size_hint_y=None, padding=[0, dp(4)])
        body.bind(minimum_height=body.setter("height"))
        self._populate_stats(body)
        scroll.add_widget(body)
        ca.add_widget(scroll)

    def _populate_stats(self, body):
        data = logic.get_dashboard_data(self.current_month, self.current_year)

        # Total card
        tc = card_widget(size_hint_y=None, height=dp(80))
        tc.add_widget(make_label("Monthly Total", size=12, color="subtext"))
        tc.add_widget(make_label(data["total_display"], size=28,
                                  color="accent", bold=True))
        body.add_widget(tc)

        # Bar chart (ASCII-style)
        body.add_widget(make_label("Spending by Category", size=13, color="subtext",
                                    size_hint_y=None, height=dp(20)))
        max_total = max((c["total"] for c in data["by_category"]), default=1) or 1
        for cat in data["by_category"]:
            if cat["total"] == 0:
                continue
            pct = cat["total"] / max_total
            row = ColoredBox(bg_color=C["card"], radius=dp(10),
                              orientation="vertical", size_hint_y=None, height=dp(58),
                              padding=[dp(10), dp(6)], spacing=dp(4))
            top = BoxLayout(size_hint_y=None, height=dp(20))
            top.add_widget(make_label(f"{cat['icon']} {cat['name']}", size=12, color="text"))
            top.add_widget(make_label(cat["total_display"], size=12,
                                       color="accent2", halign="right"))
            row.add_widget(top)
            bar_bg = ColoredBox(bg_color=C["divider"], radius=dp(4),
                                 size_hint_y=None, height=dp(10))
            color_hex = cat.get("color", C["accent"])
            bar_fill = ColoredBox(bg_color=color_hex, radius=dp(4),
                                   size_hint=(pct, 1))
            bar_bg.add_widget(bar_fill)
            row.add_widget(bar_bg)
            body.add_widget(row)

        # Daily breakdown
        if data["daily_totals"]:
            body.add_widget(make_label("Daily Breakdown", size=13, color="subtext",
                                        size_hint_y=None, height=dp(20)))
            for d in data["daily_totals"]:
                row = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(8))
                row.add_widget(make_label(f"Day {d['day']}", size=12, color="subtext",
                                           size_hint_x=None, width=dp(54)))
                row.add_widget(make_label(logic.format_currency(d["total"]),
                                           size=13, color="text"))
                body.add_widget(row)

    def _prev(self, _):
        self.current_month, self.current_year = logic.prev_month(
            self.current_month, self.current_year)
        self.on_enter()

    def _next(self, _):
        self.current_month, self.current_year = logic.next_month(
            self.current_month, self.current_year)
        self.on_enter()

    def on_enter(self, *_):
        self._build()


# ── Settings Screen ───────────────────────────────────────────────────────────

class SettingsScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def _build(self):
        ca = self.content_area
        ca.clear_widgets()
        ca.add_widget(make_label("⚙️ Settings & Budgets", size=18, bold=True,
                                  size_hint_y=None, height=dp(36)))
        ca.add_widget(make_label(
            "Set monthly budget limits per category:", size=13, color="subtext",
            size_hint_y=None, height=dp(22)))

        scroll = ScrollView(do_scroll_x=False)
        body = BoxLayout(orientation="vertical", spacing=dp(10),
                          size_hint_y=None, padding=[0, dp(4)])
        body.bind(minimum_height=body.setter("height"))

        budgets = {b["category_id"]: b["monthly_limit"] for b in logic.get_budgets()}
        self._budget_inputs = {}

        for cid, disp in logic.get_category_names():
            cat = logic.get_category_map()[cid]
            row = card_widget(orientation="horizontal", size_hint_y=None, height=dp(52),
                               padding=[dp(10), dp(4)], spacing=dp(8))
            row.add_widget(make_label(f"{cat['icon']} {cat['name']}", size=13,
                                       color="text"))
            inp = make_input("0.00", input_filter="float", height=dp(40),
                              size_hint_x=None, width=dp(100))
            if cid in budgets:
                inp.text = str(budgets[cid])
            self._budget_inputs[cid] = inp
            row.add_widget(inp)
            body.add_widget(row)

        body.add_widget(Widget(size_hint_y=None, height=dp(8)))
        btn_save = make_button("💾  Save Budgets")
        btn_save.bind(on_press=self._save_budgets)
        body.add_widget(btn_save)

        scroll.add_widget(body)
        ca.add_widget(scroll)

    def _save_budgets(self, _):
        errors = []
        for cid, inp in self._budget_inputs.items():
            val = inp.text.strip()
            if val:
                ok, msg = logic.set_budget(cid, val)
                if not ok:
                    errors.append(msg)
        if errors:
            show_popup("Error", "\n".join(errors), color="error")
        else:
            show_popup("✅ Saved", "Budget limits updated!", color="green")

    def on_enter(self, *_):
        self._build()


# ── App ───────────────────────────────────────────────────────────────────────

class ExpenseTrackerApp(App):
    def build(self):
        logic.init()
        self.title = "Expense Tracker"

        self.sm = ScreenManager()

        # Each screen gets its OWN NavBar instance — a Kivy widget can only
        # have one parent, so sharing a single NavBar across screens crashes.
        screens = [
            DashboardScreen (name="dashboard",   nav_bar=NavBar(self.sm)),
            ExpensesScreen  (name="expenses",    nav_bar=NavBar(self.sm)),
            AddExpenseScreen(name="add_expense", nav_bar=NavBar(self.sm)),
            StatsScreen     (name="stats",       nav_bar=NavBar(self.sm)),
            SettingsScreen  (name="settings",    nav_bar=NavBar(self.sm)),
        ]
        for s in screens:
            self.sm.add_widget(s)

        self.sm.current = "dashboard"
        # Highlight the active tab on every screen's nav bar
        for s in screens:
            if s.nav_bar:
                s.nav_bar.highlight("dashboard")

        root = BoxLayout(orientation="vertical")
        root.add_widget(self.sm)
        return root


if __name__ == "__main__":
    ExpenseTrackerApp().run()