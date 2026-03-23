"""
gui.py — Expense Tracker GUI (Kivy) with Admin / User role system
Screens: Login, Register, Dashboard, Expenses, AddExpense,
         Stats, Settings, AdminPanel
"""

import os
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")

from kivy.config import Config
Config.set("graphics", "width",  "400")
Config.set("graphics", "height", "800")
Config.set("graphics", "resizable", "0")

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.clock import Clock
from kivy.utils import get_color_from_hex
from kivy.core.text import LabelBase
from datetime import datetime

import logic

# ── FontAwesome ───────────────────────────────────────────────────────────────
_HERE   = os.path.dirname(os.path.abspath(__file__))
_FA_TTF = os.path.join(_HERE, "fontawesome-webfont.ttf")
_FA_OK  = False
if os.path.exists(_FA_TTF):
    try:
        LabelBase.register(name="FontAwesome", fn_regular=_FA_TTF)
        _FA_OK = True
    except Exception:
        pass

IC = {
    "home":    "\uf015", "list":    "\uf03a", "plus":    "\uf067",
    "chart":   "\uf080", "cog":     "\uf013", "check":   "\uf00c",
    "times":   "\uf00d", "edit":    "\uf044", "trash":   "\uf1f8",
    "save":    "\uf0c7", "left":    "\uf060", "right":   "\uf061",
    "user":    "\uf007", "users":   "\uf0c0", "lock":    "\uf023",
    "unlock":  "\uf09c", "shield":  "\uf132", "sign_in": "\uf090",
    "sign_out":"\uf08b", "key":     "\uf084", "crown":   "\uf521",
}

# ── Colour Palette ────────────────────────────────────────────────────────────
C = {
    "bg":      "#0F1117", "surface": "#1A1D27", "card":    "#22263A",
    "accent":  "#6C63FF", "accent2": "#FF6584", "green":   "#4ECCA3",
    "text":    "#EAEAEA", "subtext": "#8892A4", "error":   "#FF5370",
    "warning": "#FFB347", "white":   "#FFFFFF", "divider": "#2E3250",
    "admin":   "#FFB347", "user_c":  "#4ECCA3",
}

def hex_c(k): return get_color_from_hex(C[k])

# ── Shared Widgets ────────────────────────────────────────────────────────────

class ColoredBox(BoxLayout):
    def __init__(self, bg_color, radius=0, **kw):
        super().__init__(**kw)
        self._bg  = bg_color
        self._rad = radius
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*get_color_from_hex(self._bg))
            if self._rad:
                RoundedRectangle(pos=self.pos, size=self.size, radius=[self._rad])
            else:
                Rectangle(pos=self.pos, size=self.size)


def lbl(text, size=14, color="text", bold=False, halign="left", **kw):
    w = Label(text=str(text), font_size=sp(size), color=hex_c(color),
              bold=bold, halign=halign, markup=False,
              text_size=(None, None), **kw)
    w.bind(size=lambda s, v: setattr(s, "text_size", (v[0], None)))
    return w


def inp(hint, password=False, filter=None, multiline=False, height=dp(48), **kw):
    return TextInput(
        hint_text=hint, password=password,
        input_filter=filter, multiline=multiline,
        size_hint_y=None, height=height, font_size=sp(14),
        background_color=hex_c("card"), foreground_color=hex_c("text"),
        hint_text_color=hex_c("subtext"), cursor_color=hex_c("accent"),
        padding=[dp(12), dp(10)], **kw)


def plain_btn(text, bg="accent", fg="white", height=dp(48),
              font_size=14, on_press=None, **kw):
    b = Button(text=text, font_size=sp(font_size),
               color=hex_c(fg), background_normal="",
               background_color=hex_c(bg),
               size_hint_y=None, height=height, **kw)
    if on_press:
        b.bind(on_press=on_press)
    return b


def card(orientation="vertical", padding=dp(14), spacing=dp(8), **kw):
    return ColoredBox(bg_color=C["card"], radius=dp(12),
                      orientation=orientation, padding=padding,
                      spacing=spacing, **kw)


def icon_btn(codepoint, label_text, bg, size=15, height=dp(48),
             color_key="white", **kw):
    """
    A real Button with rounded background.
    Uses standard Kivy Button so .bind(on_press=...) works correctly.
    """
    text = label_text if label_text else ""
    b = Button(
        text=text,
        font_size=sp(size),
        color=hex_c(color_key),
        background_normal="",
        background_color=(0, 0, 0, 0),
        size_hint_y=None,
        height=height,
        bold=True,
        **kw
    )
    bg_color = get_color_from_hex(bg)
    def _draw(btn, *_):
        btn.canvas.before.clear()
        with btn.canvas.before:
            Color(*get_color_from_hex(bg))
            RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(10)])
    b.bind(pos=_draw, size=_draw)
    return b


def popup_ok(title, message, color="text"):
    content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
    content.add_widget(lbl(message, size=13, color=color, halign="center"))
    ok = plain_btn("OK", bg="green", fg="bg", height=dp(44))
    content.add_widget(ok)
    p = Popup(title=title, content=content,
              size_hint=(0.85, None), height=dp(210),
              background_color=hex_c("surface"),
              title_color=hex_c("text"), separator_color=hex_c("accent"))
    ok.bind(on_press=p.dismiss)
    p.open()


def popup_confirm(title, message, on_yes):
    content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
    content.add_widget(lbl(message, size=13, color="subtext", halign="center"))
    row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(44))
    b_no  = plain_btn("Cancel", bg="card",  height=dp(44))
    b_yes = plain_btn("Confirm", bg="error", height=dp(44))
    row.add_widget(b_no); row.add_widget(b_yes)
    content.add_widget(row)
    p = Popup(title=title, content=content,
              size_hint=(0.85, None), height=dp(230),
              background_color=hex_c("surface"),
              title_color=hex_c("text"), separator_color=hex_c("accent2"))
    b_no.bind(on_press=p.dismiss)
    def _yes(_): p.dismiss(); on_yes()
    b_yes.bind(on_press=_yes)
    p.open()


def role_badge(role):
    color = C["admin"] if role == "admin" else C["user_c"]
    text  = "ADMIN" if role == "admin" else "USER"
    box   = ColoredBox(bg_color=color, radius=dp(6),
                       size_hint=(None, None), size=(dp(54), dp(20)),
                       padding=[dp(4), 0])
    box.add_widget(Label(text=text, font_size=sp(9), bold=True,
                          color=hex_c("bg"), halign="center",
                          valign="middle"))
    return box


def lock_badge():
    """Red LOCKED badge for locked user accounts."""
    box = ColoredBox(bg_color=C["error"], radius=dp(6),
                     size_hint=(None, None), size=(dp(54), dp(20)),
                     padding=[dp(4), 0])
    box.add_widget(Label(text="LOCKED", font_size=sp(9), bold=True,
                          color=hex_c("white"), halign="center",
                          valign="middle"))
    return box


# ── NavBar ────────────────────────────────────────────────────────────────────

class NavBar(ColoredBox):
    USER_TABS  = [
        (IC["home"],   "Home",     "dashboard"),
        (IC["list"],   "Expenses", "expenses"),
        (IC["plus"],   "Add",      "add_expense"),
        (IC["chart"],  "Stats",    "stats"),
        (IC["cog"],    "Settings", "settings"),
    ]
    ADMIN_TABS = [
        (IC["home"],   "Home",     "dashboard"),
        (IC["list"],   "Expenses", "expenses"),
        (IC["plus"],   "Add",      "add_expense"),
        (IC["users"],  "Users",    "admin_panel"),
        (IC["cog"],    "Settings", "settings"),
    ]

    def __init__(self, sm, **kw):
        super().__init__(bg_color=C["surface"], orientation="horizontal",
                         size_hint_y=None, height=dp(62),
                         padding=[0, 0], spacing=0, **kw)
        self.sm = sm
        self._tabs = {}
        tabs = self.ADMIN_TABS if logic.is_admin() else self.USER_TABS
        self._build_tabs(tabs)

    def _build_tabs(self, tabs):
        self.clear_widgets()
        self._tabs = {}
        for cp, label_text, screen_name in tabs:
            col = BoxLayout(orientation="vertical", spacing=0, padding=[0, dp(4)])
            ic_btn = Button(
                text=cp if _FA_OK else label_text[0],
                font_name="FontAwesome" if _FA_OK else "Roboto",
                font_size=sp(20), color=hex_c("subtext"),
                background_normal="", background_color=(0, 0, 0, 0),
                size_hint_y=None, height=dp(30),
                halign="center", valign="middle")
            ic_btn.bind(size=lambda w, s: setattr(w, "text_size", s))
            ic_btn.bind(on_press=lambda _, sn=screen_name: self._go(sn))
            tx = Label(text=label_text, font_size=sp(9),
                       color=hex_c("subtext"), size_hint_y=None, height=dp(14),
                       halign="center", valign="middle")
            tx.bind(size=lambda w, s: setattr(w, "text_size", s))
            col.add_widget(ic_btn); col.add_widget(tx)
            self._tabs[screen_name] = (ic_btn, tx)
            self.add_widget(col)

    def refresh_for_role(self):
        tabs = self.ADMIN_TABS if logic.is_admin() else self.USER_TABS
        self._build_tabs(tabs)

    def _go(self, sn):
        self.sm.transition = SlideTransition(duration=0.18)
        self.sm.current = sn
        for s in self.sm.screens:
            if hasattr(s, "nav_bar") and s.nav_bar:
                s.nav_bar.highlight(sn)

    def highlight(self, sn):
        for name, (ib, tx) in self._tabs.items():
            c = hex_c("accent") if name == sn else hex_c("subtext")
            ib.color = c; tx.color = c


# ── Base Screen ───────────────────────────────────────────────────────────────

class BaseScreen(Screen):
    def __init__(self, nav_bar=None, **kw):
        super().__init__(**kw)
        self.nav_bar = nav_bar
        root = ColoredBox(bg_color=C["bg"], orientation="vertical",
                          padding=0, spacing=0)
        self.content_area = BoxLayout(orientation="vertical",
                                      padding=[dp(14), dp(10)], spacing=dp(10))
        root.add_widget(self.content_area)
        if nav_bar:
            root.add_widget(nav_bar)
        self.add_widget(root)

    def go(self, screen_name):
        app = App.get_running_app()
        app.sm.transition = SlideTransition(duration=0.18)
        app.sm.current = screen_name
        dest = app.sm.get_screen(screen_name)
        if dest.nav_bar:
            dest.nav_bar.highlight(screen_name)

    def logout_and_go_login(self):
        logic.logout()
        app = App.get_running_app()
        app.sm.transition = FadeTransition(duration=0.25)
        app.sm.current = "login"


# ── LOGIN SCREEN ──────────────────────────────────────────────────────────────

class LoginScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._build()

    def _build(self):
        # Outer bg
        root = ColoredBox(bg_color=C["bg"], orientation="vertical",
                          padding=0, spacing=0)

        # Scrollable centre column
        scroll = ScrollView(do_scroll_x=False)
        inner  = BoxLayout(orientation="vertical",
                           size_hint_y=None, spacing=dp(18),
                           padding=[dp(28), dp(60), dp(28), dp(30)])
        inner.bind(minimum_height=inner.setter("height"))

        # Title
        inner.add_widget(lbl("Expense Tracker", size=28, bold=True,
                               color="accent", halign="center",
                               size_hint_y=None, height=dp(44)))
        inner.add_widget(lbl("Sign in to continue", size=13,
                               color="subtext", halign="center",
                               size_hint_y=None, height=dp(22)))
        inner.add_widget(Widget(size_hint_y=None, height=dp(10)))

        # Fields
        inner.add_widget(lbl("Username", size=11, color="subtext",
                               size_hint_y=None, height=dp(18)))
        self.t_user = inp("Enter your username")
        inner.add_widget(self.t_user)

        inner.add_widget(lbl("Password", size=11, color="subtext",
                               size_hint_y=None, height=dp(18)))
        self.t_pass = inp("Enter your password", password=True)
        inner.add_widget(self.t_pass)

        inner.add_widget(Widget(size_hint_y=None, height=dp(8)))

        # Sign In button — plain_btn is a real Button, always works
        login_b = plain_btn("Sign In", bg="accent", fg="white",
                             height=dp(52), font_size=16)
        login_b.bind(on_press=self._login)
        inner.add_widget(login_b)

        # Register link
        reg_b = plain_btn("Don't have an account?  Register here",
                           bg="surface", fg="accent",
                           height=dp(44), font_size=12)
        reg_b.bind(on_press=lambda _: self._go_register())
        inner.add_widget(reg_b)

        # Error label
        self.err_lbl = lbl("", size=12, color="error", halign="center",
                             size_hint_y=None, height=dp(24))
        inner.add_widget(self.err_lbl)

        scroll.add_widget(inner)
        root.add_widget(scroll)
        self.add_widget(root)

    def _login(self, _):
        self.err_lbl.text = ""
        username = self.t_user.text.strip()
        password = self.t_pass.text
        if not username or not password:
            self.err_lbl.text = "Please enter username and password."
            return
        ok, result = logic.login(username, password)
        if not ok:
            self.err_lbl.text = result
            return
        app = App.get_running_app()
        for s in app.sm.screens:
            if hasattr(s, "nav_bar") and s.nav_bar:
                s.nav_bar.refresh_for_role()
        app.sm.transition = FadeTransition(duration=0.2)
        app.sm.current    = "dashboard"
        for s in app.sm.screens:
            if hasattr(s, "nav_bar") and s.nav_bar:
                s.nav_bar.highlight("dashboard")
        self.t_user.text = ""
        self.t_pass.text = ""

    def _go_register(self):
        App.get_running_app().sm.current = "register"
        self.t_user.text = ""
        self.t_pass.text = ""


# ── REGISTER SCREEN ───────────────────────────────────────────────────────────

class RegisterScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._build()

    def _build(self):
        root = ColoredBox(bg_color=C["bg"], orientation="vertical",
                          padding=0, spacing=0)

        scroll = ScrollView(do_scroll_x=False)
        inner  = BoxLayout(orientation="vertical",
                           size_hint_y=None, spacing=dp(14),
                           padding=[dp(28), dp(50), dp(28), dp(30)])
        inner.bind(minimum_height=inner.setter("height"))

        inner.add_widget(lbl("Create Account", size=26, bold=True,
                               color="accent", halign="center",
                               size_hint_y=None, height=dp(40)))
        inner.add_widget(lbl("Join Expense Tracker", size=12,
                               color="subtext", halign="center",
                               size_hint_y=None, height=dp(22)))
        inner.add_widget(Widget(size_hint_y=None, height=dp(10)))

        inner.add_widget(lbl("Username  (min 3 characters)", size=11,
                               color="subtext", size_hint_y=None, height=dp(18)))
        self.t_user  = inp("Choose a username")
        inner.add_widget(self.t_user)

        inner.add_widget(lbl("Password  (min 6 characters)", size=11,
                               color="subtext", size_hint_y=None, height=dp(18)))
        self.t_pass  = inp("Choose a password", password=True)
        inner.add_widget(self.t_pass)

        inner.add_widget(lbl("Confirm Password", size=11,
                               color="subtext", size_hint_y=None, height=dp(18)))
        self.t_pass2 = inp("Repeat your password", password=True)
        inner.add_widget(self.t_pass2)

        inner.add_widget(Widget(size_hint_y=None, height=dp(8)))

        reg_b = plain_btn("Create Account", bg="accent", fg="white",
                           height=dp(52), font_size=16)
        reg_b.bind(on_press=self._register)
        inner.add_widget(reg_b)

        back_b = plain_btn("Already have an account?  Sign In",
                            bg="surface", fg="accent",
                            height=dp(44), font_size=12)
        back_b.bind(on_press=lambda _: self._go_login())
        inner.add_widget(back_b)

        self.err_lbl = lbl("", size=12, color="error", halign="center",
                             size_hint_y=None, height=dp(24))
        inner.add_widget(self.err_lbl)

        scroll.add_widget(inner)
        root.add_widget(scroll)
        self.add_widget(root)

    def _register(self, _):
        self.err_lbl.text = ""
        u  = self.t_user.text.strip()
        p  = self.t_pass.text
        p2 = self.t_pass2.text
        if p != p2:
            self.err_lbl.text = "Passwords do not match."
            return
        ok, result = logic.register(u, p, role="user")
        if not ok:
            self.err_lbl.text = result
            return
        popup_ok("Account Created",
                 f"Welcome, {result['username']}!\nYou can now sign in.",
                 color="green")
        Clock.schedule_once(lambda _: self._go_login(), 1.2)

    def _go_login(self):
        App.get_running_app().sm.current = "login"
        self.t_user.text = self.t_pass.text = self.t_pass2.text = ""


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

class DashboardScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.month = datetime.now().month
        self.year  = datetime.now().year

    def _build(self):
        ca = self.content_area
        ca.clear_widgets()
        user = logic.get_current_user()

        # Header
        hdr = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        left = BoxLayout(orientation="vertical", spacing=dp(2))
        left.add_widget(lbl("ExpenseTracker", size=20, bold=True))
        if user:
            role_text = f"Admin Dashboard" if logic.is_admin() else f"Hi, {user['username']}"
            rc = "admin" if logic.is_admin() else "green"
            left.add_widget(lbl(role_text, size=11, color=rc))
        hdr.add_widget(left)
        hdr.add_widget(Widget())
        logout_b = plain_btn("Logout", bg="error", fg="white",
                              height=dp(34), font_size=11,
                              size_hint_x=None, width=dp(72))
        logout_b.bind(on_press=lambda _: self.logout_and_go_login())
        hdr.add_widget(logout_b)
        ca.add_widget(hdr)

        # Month nav
        nav = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        bp = icon_btn(IC["left"],  "", bg=C["card"], height=dp(38),
                      size_hint_x=None, width=dp(44))
        bn = icon_btn(IC["right"], "", bg=C["card"], height=dp(38),
                      size_hint_x=None, width=dp(44))
        self._ml = lbl(logic.month_year_label(self.month, self.year),
                       size=15, bold=True, halign="center")
        bp.bind(on_press=self._prev); bn.bind(on_press=self._next)
        nav.add_widget(bp); nav.add_widget(self._ml); nav.add_widget(bn)
        ca.add_widget(nav)

        # Admin: show global stats banner
        if logic.is_admin():
            stats = logic.get_admin_stats()
            total_users = len(stats)
            grand_total = sum(s["total_spent"] for s in stats)
            banner = card(size_hint_y=None, height=dp(56), orientation="horizontal",
                          spacing=dp(8))
            banner.add_widget(
                lbl(f"Users: {total_users}", size=13, color="admin",
                    bold=True, halign="center"))
            banner.add_widget(
                lbl(f"All Spending: {logic.format_currency(grand_total)}",
                    size=13, color="accent", bold=True, halign="center"))
            ca.add_widget(banner)

        scroll = ScrollView(do_scroll_x=False)
        body   = BoxLayout(orientation="vertical", spacing=dp(10),
                           size_hint_y=None, padding=[0, dp(4)])
        body.bind(minimum_height=body.setter("height"))
        self._fill(body)
        scroll.add_widget(body)
        ca.add_widget(scroll)

    def _fill(self, body):
        data = logic.get_dashboard_data(self.month, self.year)

        tc = card(size_hint_y=None, height=dp(86))
        tc.add_widget(lbl("Total Spending", size=12, color="subtext"))
        tc.add_widget(lbl(data["total_display"], size=30,
                           color="accent", bold=True))
        body.add_widget(tc)

        body.add_widget(lbl("By Category", size=12, color="subtext",
                              size_hint_y=None, height=dp(22)))
        for cat in data["by_category"]:
            if cat["total"] == 0:
                continue
            c = card(size_hint_y=None, height=dp(68), orientation="vertical",
                      spacing=dp(4))
            row = BoxLayout(size_hint_y=None, height=dp(22))
            row.add_widget(lbl(f"{cat['icon']}  {cat['name']}",
                                size=13, color="text"))
            row.add_widget(lbl(cat["total_display"], size=13,
                                color="accent2", halign="right"))
            c.add_widget(row)
            if cat.get("budget_pct") is not None:
                bar_bg = ColoredBox(bg_color=C["divider"], radius=dp(4),
                                    size_hint_y=None, height=dp(8))
                fc = C["error"] if cat["over_budget"] else C["green"]
                bar_bg.add_widget(
                    ColoredBox(bg_color=fc, radius=dp(4),
                               size_hint=(cat["budget_pct"]/100, 1)))
                c.add_widget(bar_bg)
                sfx = "  Over budget!" if cat["over_budget"] else ""
                c.add_widget(lbl(
                    f"Budget: {logic.format_currency(cat['budget_limit'])}" + sfx,
                    size=10, color="subtext", size_hint_y=None, height=dp(14)))
            body.add_widget(c)

        body.add_widget(lbl("Recent Expenses", size=12, color="subtext",
                              size_hint_y=None, height=dp(22)))
        if not data["recent"]:
            body.add_widget(lbl("No expenses yet.", size=13, color="subtext",
                                 halign="center", size_hint_y=None, height=dp(40)))
        for exp in data["recent"]:
            self._exp_row(body, exp)

    def _exp_row(self, parent, exp):
        r = card(orientation="horizontal", size_hint_y=None, height=dp(54),
                  padding=[dp(10), dp(6)], spacing=dp(8))
        r.add_widget(lbl(exp.get("category_icon", "?"), size=20,
                          size_hint_x=None, width=dp(28)))
        info = BoxLayout(orientation="vertical", spacing=dp(2))
        info.add_widget(lbl(exp["title"], size=13, bold=True))
        sub = exp["date_display"]
        if logic.is_admin() and exp.get("owner"):
            sub += f"  •  {exp['owner']}"
        info.add_widget(lbl(sub, size=11, color="subtext"))
        r.add_widget(info)
        r.add_widget(lbl(exp["amount_display"], size=13, color="accent2",
                          bold=True, halign="right",
                          size_hint_x=None, width=dp(80)))
        parent.add_widget(r)

    def _prev(self, _):
        self.month, self.year = logic.prev_month(self.month, self.year)
        self._build()

    def _next(self, _):
        self.month, self.year = logic.next_month(self.month, self.year)
        self._build()

    def on_enter(self, *_): self._build()


# ── EXPENSES LIST ─────────────────────────────────────────────────────────────

class ExpensesScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)

    def _build(self):
        ca = self.content_area
        ca.clear_widgets()

        hdr = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        hdr.add_widget(lbl("All Expenses", size=18, bold=True))
        hdr.add_widget(Widget())
        ab = icon_btn(IC["plus"], "Add", bg=C["accent"],
                      height=dp(36), size_hint_x=None, width=dp(88))
        ab.bind(on_press=lambda _: self.go("add_expense"))
        hdr.add_widget(ab)
        ca.add_widget(hdr)

        cat_names = logic.get_category_names()
        self._cat_map = {disp: cid for cid, disp in cat_names}
        vals = ["All Categories"] + [d for _, d in cat_names]
        self.spinner = Spinner(text="All Categories", values=vals,
                               size_hint_y=None, height=dp(40), font_size=sp(13),
                               background_normal="", color=hex_c("text"),
                               background_color=hex_c("card"))
        self.spinner.bind(text=lambda _, v: self._refresh())
        ca.add_widget(self.spinner)

        self.scroll   = ScrollView(do_scroll_x=False)
        self.list_box = BoxLayout(orientation="vertical", spacing=dp(8),
                                  size_hint_y=None, padding=[0, dp(4)])
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        self.scroll.add_widget(self.list_box)
        ca.add_widget(self.scroll)
        self._refresh()

    def _refresh(self):
        self.list_box.clear_widgets()
        sel    = self.spinner.text
        cat_id = self._cat_map.get(sel) if sel != "All Categories" else None
        exps   = logic.get_expenses(category_id=cat_id)
        if not exps:
            self.list_box.add_widget(
                lbl("No expenses found.", size=14, color="subtext",
                     halign="center", size_hint_y=None, height=dp(60)))
            return
        for e in exps:
            self._item(e)

    def _item(self, exp):
        r = card(orientation="horizontal", size_hint_y=None, height=dp(66),
                  padding=[dp(10), dp(6)], spacing=dp(8))
        r.add_widget(lbl(exp.get("category_icon", "?"), size=20,
                          size_hint_x=None, width=dp(28)))
        info = BoxLayout(orientation="vertical", spacing=dp(2))
        info.add_widget(lbl(exp["title"], size=13, bold=True))
        sub = f"{exp.get('category_name','')}  •  {exp['date_display']}"
        if logic.is_admin() and exp.get("owner"):
            sub += f"  •  {exp['owner']}"
        info.add_widget(lbl(sub, size=11, color="subtext"))
        r.add_widget(info)

        right = BoxLayout(orientation="vertical",
                          size_hint_x=None, width=dp(90), spacing=dp(4))
        right.add_widget(lbl(exp["amount_display"], size=13, color="accent2",
                              bold=True, halign="right"))
        btns = BoxLayout(spacing=dp(4), size_hint_y=None, height=dp(28))
        eid  = exp["id"]
        eb   = icon_btn(IC["edit"],  "Edit", bg=C["accent"],
                         height=dp(28), size=10)
        db_  = icon_btn(IC["trash"], "Del",  bg=C["error"],
                         height=dp(28), size=10)
        eb.bind(on_press=lambda _, i=eid: self._edit(i))
        db_.bind(on_press=lambda _, i=eid: self._delete(i))
        btns.add_widget(eb); btns.add_widget(db_)
        right.add_widget(btns)
        r.add_widget(right)
        self.list_box.add_widget(r)

    def _edit(self, eid):
        App.get_running_app().sm.get_screen("add_expense").load_expense(eid)
        self.go("add_expense")

    def _delete(self, eid):
        popup_confirm("Delete Expense", "Delete this expense permanently?",
                      lambda: (logic.delete_expense(eid), self._refresh()))

    def on_enter(self, *_): self._build()


# ── ADD / EDIT EXPENSE ────────────────────────────────────────────────────────

class AddExpenseScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._eid = None

    def _build(self):
        ca = self.content_area
        ca.clear_widgets()

        hdr = BoxLayout(size_hint_y=None, height=dp(40))
        self._hdr_lbl = lbl("Add Expense", size=18, bold=True)
        hdr.add_widget(self._hdr_lbl)
        ca.add_widget(hdr)

        scroll = ScrollView(do_scroll_x=False)
        form   = BoxLayout(orientation="vertical", spacing=dp(10),
                           size_hint_y=None, padding=[0, dp(4)])
        form.bind(minimum_height=form.setter("height"))

        def field(t): form.add_widget(lbl(t, size=11, color="subtext",
                                           size_hint_y=None, height=dp(16)))

        field("Title *")
        self.t_title  = inp("e.g. Lunch at café")
        form.add_widget(self.t_title)

        field("Amount *")
        self.t_amount = inp("0.00", filter="float")
        form.add_widget(self.t_amount)

        field("Category *")
        cat_names = logic.get_category_names()
        self._cat_map = {disp: cid for cid, disp in cat_names}
        disp_vals = [d for _, d in cat_names]
        self.cat_spin = Spinner(
            text=disp_vals[0] if disp_vals else "Select",
            values=disp_vals, size_hint_y=None, height=dp(44),
            font_size=sp(13), background_normal="",
            color=hex_c("text"), background_color=hex_c("card"))
        form.add_widget(self.cat_spin)

        field("Date * (YYYY-MM-DD)")
        self.t_date = inp("YYYY-MM-DD")
        self.t_date.text = logic.today_str()
        form.add_widget(self.t_date)

        field("Note (optional)")
        self.t_note = inp("Add a note…", multiline=True, height=dp(70))
        form.add_widget(self.t_note)

        form.add_widget(Widget(size_hint_y=None, height=dp(6)))
        self.save_btn = icon_btn(IC["check"], "Save Expense", bg=C["accent"],
                                  height=dp(50), size=14)
        self.save_btn.bind(on_press=self._save)
        form.add_widget(self.save_btn)

        self.cancel_btn = icon_btn(IC["times"], "Cancel", bg=C["card"],
                                    height=dp(46), size=14)
        self.cancel_btn.bind(on_press=self._cancel)
        form.add_widget(self.cancel_btn)

        scroll.add_widget(form)
        ca.add_widget(scroll)

    def load_expense(self, eid):
        self._eid = eid
        exp = logic.get_expense(eid)
        if not exp:
            return
        self._hdr_lbl.text = "Edit Expense"
        self.t_title.text  = exp["title"]
        self.t_amount.text = str(exp["amount"])
        self.t_date.text   = exp["date"]
        self.t_note.text   = exp.get("note", "")
        cat = logic.get_category_map().get(exp["category_id"])
        if cat:
            disp = f"{cat['icon']} {cat['name']}"
            if disp in self.cat_spin.values:
                self.cat_spin.text = disp

    def _save(self, _):
        cat_id = self._cat_map.get(self.cat_spin.text)
        if self._eid:
            ok, msg = logic.update_expense(
                self._eid, self.t_title.text, self.t_amount.text,
                cat_id, self.t_date.text, self.t_note.text)
        else:
            ok, msg = logic.add_expense(
                self.t_title.text, self.t_amount.text,
                cat_id, self.t_date.text, self.t_note.text)
        if ok:
            popup_ok("Saved", "Expense saved successfully!", color="green")
            self._reset()
            Clock.schedule_once(lambda _: self.go("expenses"), 0.7)
        else:
            popup_ok("Error", msg, color="error")

    def _cancel(self, _):
        self._reset(); self.go("expenses")

    def _reset(self):
        self._eid          = None
        self._hdr_lbl.text = "Add Expense"
        self.t_title.text  = ""
        self.t_amount.text = ""
        self.t_date.text   = logic.today_str()
        self.t_note.text   = ""

    def on_enter(self, *_):
        if not self._eid:
            self._reset()
            self._build()


# ── STATS ─────────────────────────────────────────────────────────────────────

class StatsScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.month = datetime.now().month
        self.year  = datetime.now().year

    def _build(self):
        ca = self.content_area
        ca.clear_widgets()
        ca.add_widget(lbl("Statistics", size=18, bold=True,
                           size_hint_y=None, height=dp(40)))

        nav = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        bp  = icon_btn(IC["left"],  "", bg=C["card"], height=dp(38),
                       size_hint_x=None, width=dp(44))
        bn  = icon_btn(IC["right"], "", bg=C["card"], height=dp(38),
                       size_hint_x=None, width=dp(44))
        self._ml = lbl(logic.month_year_label(self.month, self.year),
                       size=15, bold=True, halign="center")
        bp.bind(on_press=self._prev); bn.bind(on_press=self._next)
        nav.add_widget(bp); nav.add_widget(self._ml); nav.add_widget(bn)
        ca.add_widget(nav)

        scroll = ScrollView(do_scroll_x=False)
        body   = BoxLayout(orientation="vertical", spacing=dp(10),
                           size_hint_y=None, padding=[0, dp(4)])
        body.bind(minimum_height=body.setter("height"))
        self._fill(body)
        scroll.add_widget(body)
        ca.add_widget(scroll)

    def _fill(self, body):
        data = logic.get_dashboard_data(self.month, self.year)
        tc = card(size_hint_y=None, height=dp(80))
        tc.add_widget(lbl("Monthly Total", size=12, color="subtext"))
        tc.add_widget(lbl(data["total_display"], size=28,
                           color="accent", bold=True))
        body.add_widget(tc)

        # Admin: per-user breakdown
        if logic.is_admin():
            body.add_widget(lbl("Per-User Breakdown", size=12, color="admin",
                                 size_hint_y=None, height=dp(22)))
            for stat in logic.get_admin_stats():
                r = card(orientation="horizontal", size_hint_y=None,
                          height=dp(44), padding=[dp(10), dp(4)], spacing=dp(8))
                left = BoxLayout(orientation="vertical", spacing=dp(2))
                left.add_widget(lbl(stat["username"], size=13, bold=True))
                left.add_widget(lbl(f"{stat['expense_count']} expenses",
                                     size=10, color="subtext"))
                r.add_widget(left)
                r.add_widget(role_badge(stat["role"]))
                r.add_widget(lbl(logic.format_currency(stat["total_spent"]),
                                  size=13, color="accent2", bold=True,
                                  halign="right"))
                body.add_widget(r)

        body.add_widget(lbl("Spending by Category", size=12, color="subtext",
                              size_hint_y=None, height=dp(20)))
        mx = max((c["total"] for c in data["by_category"]), default=1) or 1
        for cat in data["by_category"]:
            if cat["total"] == 0:
                continue
            pct = cat["total"] / mx
            r = ColoredBox(bg_color=C["card"], radius=dp(10),
                           orientation="vertical", size_hint_y=None,
                           height=dp(56), padding=[dp(10), dp(6)], spacing=dp(4))
            top = BoxLayout(size_hint_y=None, height=dp(20))
            top.add_widget(lbl(f"{cat['icon']}  {cat['name']}",
                                size=12, color="text"))
            top.add_widget(lbl(cat["total_display"], size=12,
                                color="accent2", halign="right"))
            r.add_widget(top)
            bar = ColoredBox(bg_color=C["divider"], radius=dp(4),
                             size_hint_y=None, height=dp(10))
            bar.add_widget(ColoredBox(bg_color=cat.get("color", C["accent"]),
                                       radius=dp(4), size_hint=(pct, 1)))
            r.add_widget(bar)
            body.add_widget(r)

        if data["daily_totals"]:
            body.add_widget(lbl("Daily Breakdown", size=12, color="subtext",
                                 size_hint_y=None, height=dp(20)))
            for d in data["daily_totals"]:
                row = BoxLayout(size_hint_y=None, height=dp(26), spacing=dp(8))
                row.add_widget(lbl(f"Day {d['day']}", size=12, color="subtext",
                                    size_hint_x=None, width=dp(54)))
                row.add_widget(lbl(logic.format_currency(d["total"]),
                                    size=13, color="text"))
                body.add_widget(row)

    def _prev(self, _):
        self.month, self.year = logic.prev_month(self.month, self.year)
        self._build()

    def _next(self, _):
        self.month, self.year = logic.next_month(self.month, self.year)
        self._build()

    def on_enter(self, *_): self._build()


# ── SETTINGS ─────────────────────────────────────────────────────────────────

class SettingsScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)

    def _build(self):
        ca = self.content_area
        ca.clear_widgets()
        ca.add_widget(lbl("Settings", size=18, bold=True,
                           size_hint_y=None, height=dp(40)))

        scroll = ScrollView(do_scroll_x=False)
        body   = BoxLayout(orientation="vertical", spacing=dp(10),
                           size_hint_y=None, padding=[0, dp(4)])
        body.bind(minimum_height=body.setter("height"))

        # ── Budget section ────────────────────────────────────────────────
        body.add_widget(lbl("Monthly Budget Limits", size=13, color="subtext",
                             size_hint_y=None, height=dp(22)))
        budgets = {b["category_id"]: b["monthly_limit"]
                   for b in logic.get_budgets()}
        self._binps = {}
        for cid, disp in logic.get_category_names():
            cat = logic.get_category_map()[cid]
            r = card(orientation="horizontal", size_hint_y=None,
                      height=dp(50), padding=[dp(10), dp(4)], spacing=dp(8))
            r.add_widget(lbl(f"{cat['icon']}  {cat['name']}",
                              size=13, color="text"))
            bi = inp("0.00", filter="float", height=dp(40),
                      size_hint_x=None, width=dp(100))
            if cid in budgets:
                bi.text = str(budgets[cid])
            self._binps[cid] = bi
            r.add_widget(bi)
            body.add_widget(r)

        sb = icon_btn(IC["save"], "Save Budgets", bg=C["accent"],
                      height=dp(50), size=14)
        sb.bind(on_press=self._save_budgets)
        body.add_widget(sb)

        # ── Change password section ───────────────────────────────────────
        body.add_widget(Widget(size_hint_y=None, height=dp(10)))
        body.add_widget(lbl("Change Password", size=13, color="subtext",
                             size_hint_y=None, height=dp(22)))
        pw_card = card(spacing=dp(10), padding=dp(14))
        pw_card.add_widget(lbl("Current Password", size=11, color="subtext",
                                size_hint_y=None, height=dp(16)))
        self.t_old = inp("Current password", password=True)
        pw_card.add_widget(self.t_old)
        pw_card.add_widget(lbl("New Password", size=11, color="subtext",
                                size_hint_y=None, height=dp(16)))
        self.t_new1 = inp("New password (min 6 chars)", password=True)
        pw_card.add_widget(self.t_new1)
        pw_card.add_widget(lbl("Confirm New Password", size=11, color="subtext",
                                size_hint_y=None, height=dp(16)))
        self.t_new2 = inp("Repeat new password", password=True)
        pw_card.add_widget(self.t_new2)
        cp_btn = icon_btn(IC["key"], "Change Password", bg=C["accent2"],
                           height=dp(46), size=14)
        cp_btn.bind(on_press=self._change_pw)
        pw_card.add_widget(cp_btn)
        body.add_widget(pw_card)

        # ── Phase 4: CSV Export ───────────────────────────────────────────
        body.add_widget(Widget(size_hint_y=None, height=dp(10)))
        body.add_widget(lbl("Data Export", size=13, color="subtext",
                             size_hint_y=None, height=dp(22)))
        exp_card = card(spacing=dp(10), padding=dp(14))
        exp_card.add_widget(lbl(
            "Export all your expenses to a CSV file you can open in Excel or Google Sheets.",
            size=12, color="subtext"))
        csv_btn = plain_btn("Export Expenses as CSV", bg=C["accent"],
                             height=dp(46), font_size=13)
        csv_btn.bind(on_press=self._export_csv)
        exp_card.add_widget(csv_btn)
        body.add_widget(exp_card)

        scroll.add_widget(body)
        ca.add_widget(scroll)

    def _export_csv(self, _):
        import os
        from datetime import datetime
        csv_str = logic.export_expenses_csv()
        if not csv_str:
            popup_ok("Error", "No expenses to export.", color="error")
            return
        # Save next to the app file
        here     = os.path.dirname(os.path.abspath(__file__))
        filename = f"expenses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(here, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(csv_str)
            popup_ok("Exported", f"Saved to:\n{filename}", color="green")
        except Exception as e:
            popup_ok("Error", f"Could not save file:\n{e}", color="error")

    def _save_budgets(self, _):
        errors = []
        for cid, bi in self._binps.items():
            v = bi.text.strip()
            if v:
                ok, msg = logic.set_budget(cid, v)
                if not ok:
                    errors.append(msg)
        if errors:
            popup_ok("Error", "\n".join(errors), color="error")
        else:
            popup_ok("Saved", "Budget limits updated!", color="green")

    def _change_pw(self, _):
        if self.t_new1.text != self.t_new2.text:
            popup_ok("Error", "New passwords do not match.", color="error")
            return
        ok, msg = logic.change_own_password(self.t_old.text, self.t_new1.text)
        if ok:
            popup_ok("Done", "Password changed successfully!", color="green")
            self.t_old.text = self.t_new1.text = self.t_new2.text = ""
        else:
            popup_ok("Error", msg, color="error")

    def on_enter(self, *_): self._build()


# ── ADMIN PANEL ───────────────────────────────────────────────────────────────

class AdminPanelScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._tab = "users"   # "users" | "audit"

    def _build(self):
        ca = self.content_area
        ca.clear_widgets()

        # ── Header ────────────────────────────────────────────────────────
        hdr = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        hdr.add_widget(lbl("Admin Panel", size=18, bold=True, color="admin"))
        hdr.add_widget(Widget())
        add_b = plain_btn("+ Add User", bg=C["admin"], fg="bg",
                           height=dp(34), font_size=11,
                           size_hint_x=None, width=dp(90))
        add_b.bind(on_press=self._show_add_user)
        hdr.add_widget(add_b)
        ca.add_widget(hdr)

        # ── Tab bar: Users | Audit Log ────────────────────────────────────
        tab_bar = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        for tab_id, label in [("users", "Users"), ("audit", "Audit Log")]:
            bg = C["accent"] if self._tab == tab_id else C["card"]
            fg = "white"     if self._tab == tab_id else "subtext"
            tb = plain_btn(label, bg=bg, fg=fg, height=dp(38), font_size=12)
            tb.bind(on_press=lambda _, t=tab_id: self._switch_tab(t))
            tab_bar.add_widget(tb)
        ca.add_widget(tab_bar)

        # ── Summary banner ────────────────────────────────────────────────
        stats = logic.get_admin_stats()
        if stats:
            total_users  = len(stats)
            locked_users = sum(1 for s in stats if s.get("is_locked"))
            grand        = sum(s["total_spent"] for s in stats)
            banner = card(orientation="horizontal", size_hint_y=None,
                           height=dp(48), spacing=dp(4))
            banner.add_widget(lbl(f"{total_users} Users",
                                   size=12, color="admin", halign="center", bold=True))
            if locked_users:
                banner.add_widget(lbl(f"{locked_users} Locked",
                                       size=12, color="error", halign="center", bold=True))
            banner.add_widget(lbl(f"Total: {logic.format_currency(grand)}",
                                   size=12, color="accent", halign="center", bold=True))
            ca.add_widget(banner)

        scroll    = ScrollView(do_scroll_x=False)
        self.body = BoxLayout(orientation="vertical", spacing=dp(8),
                               size_hint_y=None, padding=[0, dp(4)])
        self.body.bind(minimum_height=self.body.setter("height"))
        if self._tab == "users":
            self._fill_users()
        else:
            self._fill_audit()
        scroll.add_widget(self.body)
        ca.add_widget(scroll)

    def _switch_tab(self, tab_id):
        self._tab = tab_id
        self._build()

    def _fill_users(self):
        self.body.clear_widgets()
        users = logic.admin_get_all_users()
        me    = logic.get_current_user()
        for u in users:
            is_locked = bool(u.get("is_locked"))
            row_h     = dp(72) if is_locked else dp(62)
            r = card(orientation="horizontal", size_hint_y=None,
                      height=row_h, padding=[dp(10), dp(6)], spacing=dp(8))
            # Left: name + badges + meta
            info = BoxLayout(orientation="vertical", spacing=dp(2))
            name_row = BoxLayout(spacing=dp(6), size_hint_y=None, height=dp(24))
            name_row.add_widget(lbl(u["username"], size=13, bold=True,
                                     size_hint_x=None, width=dp(110)))
            name_row.add_widget(role_badge(u["role"]))
            if is_locked:
                name_row.add_widget(lock_badge())
            info.add_widget(name_row)
            joined = u.get("created_at", "")[:10]
            sub    = f"Joined: {joined}"
            if is_locked and u.get("locked_until"):
                sub += f"  · Locked until {u['locked_until'][:16]}"
            info.add_widget(lbl(sub, size=10, color="subtext"))
            r.add_widget(info)
            r.add_widget(Widget())

            # Right: action buttons (skip for self)
            if u["id"] != me["id"]:
                btns = BoxLayout(spacing=dp(4),
                                 size_hint_x=None, width=dp(120))
                # Unlock button if locked
                if is_locked:
                    ub = plain_btn("Unlock", bg=C["green"], fg="bg",
                                   height=dp(28), font_size=9,
                                   size_hint_x=None, width=dp(52))
                    ub.bind(on_press=lambda _, uid=u["id"]: self._unlock(uid))
                    btns.add_widget(ub)
                # Toggle role button
                new_role = "user" if u["role"] == "admin" else "admin"
                rb_text  = "→User" if u["role"] == "admin" else "→Admin"
                rb_color = C["warning"] if u["role"] == "admin" else C["green"]
                rb = plain_btn(rb_text, bg=rb_color, fg="bg",
                               height=dp(28), font_size=9,
                               size_hint_x=None, width=dp(52))
                rb.bind(on_press=lambda _, uid=u["id"], nr=new_role:
                        self._change_role(uid, nr))
                del_b = plain_btn("Del", bg=C["error"], fg="white",
                                   height=dp(30), font_size=10,
                                   size_hint_x=None, width=dp(38))
                del_b.bind(on_press=lambda _, uid=u["id"], un=u["username"]:
                           self._delete_user(uid, un))
                btns.add_widget(rb)
                btns.add_widget(del_b)
                r.add_widget(btns)
            else:
                r.add_widget(lbl("(You)", size=11, color="subtext",
                                  halign="right",
                                  size_hint_x=None, width=dp(50)))
            self.body.add_widget(r)

    def _change_role(self, uid, new_role):
        ok, msg = logic.admin_change_role(uid, new_role)
        if ok:
            self._fill_users()
        else:
            popup_ok("Error", msg, color="error")

    def _delete_user(self, uid, username):
        popup_confirm(
            "Delete User",
            f"Delete '{username}' and ALL their data?",
            lambda: self._do_delete(uid)
        )

    def _do_delete(self, uid):
        ok, msg = logic.admin_delete_user(uid)
        if ok:
            self._fill_users()
        else:
            popup_ok("Error", msg, color="error")

    def _show_add_user(self, _):
        """Popup form to create a new user."""
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        content.add_widget(lbl("New Username:", size=12, color="subtext",
                                size_hint_y=None, height=dp(18)))
        t_u = inp("username", height=dp(42))
        content.add_widget(t_u)
        content.add_widget(lbl("Password:", size=12, color="subtext",
                                size_hint_y=None, height=dp(18)))
        t_p = inp("password (min 6 chars)", password=True, height=dp(42))
        content.add_widget(t_p)
        content.add_widget(lbl("Role:", size=12, color="subtext",
                                size_hint_y=None, height=dp(18)))
        role_spin = Spinner(text="user", values=["user", "admin"],
                            size_hint_y=None, height=dp(40), font_size=sp(13),
                            background_normal="", color=hex_c("text"),
                            background_color=hex_c("card"))
        content.add_widget(role_spin)
        err = lbl("", size=11, color="error", halign="center",
                   size_hint_y=None, height=dp(18))
        content.add_widget(err)

        btns = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(44))
        b_cancel = plain_btn("Cancel", bg="card",   height=dp(44))
        b_create = plain_btn("Create", bg="accent",  height=dp(44))
        btns.add_widget(b_cancel); btns.add_widget(b_create)
        content.add_widget(btns)

        p = Popup(title="Add New User", content=content,
                  size_hint=(0.9, None), height=dp(420),
                  background_color=hex_c("surface"),
                  title_color=hex_c("admin"),
                  separator_color=hex_c("admin"))

        b_cancel.bind(on_press=p.dismiss)
        def _create(_):
            err.text = ""
            ok, result = logic.register(t_u.text.strip(), t_p.text,
                                         role=role_spin.text)
            if not ok:
                err.text = result
                return
            p.dismiss()
            self._fill_users()
        b_create.bind(on_press=_create)
        p.open()

    def _unlock(self, uid):
        ok, msg = logic.admin_unlock_user(uid)
        if ok:
            self._fill_users()
        else:
            popup_ok("Error", msg, color="error")

    def _fill_audit(self):
        self.body.clear_widgets()
        logs = logic.get_audit_log(limit=200)
        if not logs:
            self.body.add_widget(lbl("No audit events yet.", size=13,
                                      color="subtext", halign="center",
                                      size_hint_y=None, height=dp(50)))
            return
        for entry in logs:
            r = card(orientation="horizontal", size_hint_y=None,
                      height=dp(52), padding=[dp(10), dp(4)], spacing=dp(8))
            left = BoxLayout(orientation="vertical", spacing=dp(2))
            action_color = {
                "LOCKOUT":        "error",
                "DELETE_USER":    "error",
                "LOGIN":          "green",
                "LOGOUT":         "subtext",
                "UNLOCK_USER":    "warning",
                "CHANGE_ROLE":    "warning",
                "CHANGE_PASSWORD":"accent",
                "EXPORT_CSV":     "accent",
            }.get(entry["action"], "text")
            left.add_widget(lbl(entry["action"], size=12, bold=True,
                                 color=action_color))
            detail = entry.get("target", "")
            if entry.get("detail"):
                detail += f"  · {entry['detail']}"
            left.add_widget(lbl(detail, size=10, color="subtext"))
            r.add_widget(left)
            r.add_widget(Widget())
            ts = entry.get("created_at", "")[:16].replace("T", " ")
            right = BoxLayout(orientation="vertical", spacing=dp(2),
                               size_hint_x=None, width=dp(100))
            right.add_widget(lbl(entry.get("actor_name", "?"), size=10,
                                  color="subtext", halign="right"))
            right.add_widget(lbl(ts, size=9, color="subtext", halign="right"))
            r.add_widget(right)
            self.body.add_widget(r)

    def on_enter(self, *_): self._build()


# ── APP ───────────────────────────────────────────────────────────────────────

class ExpenseTrackerApp(App):
    def build(self):
        logic.init()
        self.title = "Expense Tracker"
        self.sm    = ScreenManager()

        # Auth screens (no navbar)
        self.sm.add_widget(LoginScreen   (name="login"))
        self.sm.add_widget(RegisterScreen(name="register"))

        # App screens (each gets own NavBar)
        app_screens = [
            DashboardScreen (name="dashboard",   nav_bar=NavBar(self.sm)),
            ExpensesScreen  (name="expenses",    nav_bar=NavBar(self.sm)),
            AddExpenseScreen(name="add_expense", nav_bar=NavBar(self.sm)),
            StatsScreen     (name="stats",       nav_bar=NavBar(self.sm)),
            SettingsScreen  (name="settings",    nav_bar=NavBar(self.sm)),
            AdminPanelScreen(name="admin_panel", nav_bar=NavBar(self.sm)),
        ]
        for s in app_screens:
            self.sm.add_widget(s)

        # Start on login screen
        self.sm.current = "login"

        root = BoxLayout(orientation="vertical")
        root.add_widget(self.sm)
        return root


if __name__ == "__main__":
    ExpenseTrackerApp().run()