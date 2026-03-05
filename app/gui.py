"""
gui.py - Expense Tracker GUI (Kivy)
Icons via FontAwesome 4 TTF — place fontawesome-webfont.ttf next to this file.
"""

import os
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")

from kivy.config import Config
Config.set("graphics", "width",  "400")
Config.set("graphics", "height", "800")
Config.set("graphics", "resizable", "0")

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
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

# ── Register FontAwesome 4 ────────────────────────────────────────────────────
_HERE   = os.path.dirname(os.path.abspath(__file__))
_FA_TTF = os.path.join(_HERE, "fontawesome-webfont.ttf")
_FA_OK  = False
if os.path.exists(_FA_TTF):
    try:
        LabelBase.register(name="FontAwesome", fn_regular=_FA_TTF)
        _FA_OK = True
    except Exception:
        pass

# ── Icon codepoints (FontAwesome 4) ──────────────────────────────────────────
IC = {
    "home":        "\uf015",
    "list":        "\uf03a",
    "plus":        "\uf067",
    "chart":       "\uf080",
    "cog":         "\uf013",
    "check":       "\uf00c",
    "times":       "\uf00d",
    "edit":        "\uf044",
    "trash":       "\uf1f8",
    "save":        "\uf0c7",
    "left":        "\uf060",
    "right":       "\uf061",
    "money":       "\uf0d6",
    "tag":         "\uf02b",
    "calendar":    "\uf073",
    "exclamation": "\uf071",
}

def icon_label(codepoint, size=18, color_key="subtext", **kwargs):
    """A Label that renders a single FontAwesome icon using font_name directly."""
    if _FA_OK:
        lbl = Label(
            text=codepoint,
            font_name="FontAwesome",
            font_size=sp(size),
            color=get_color_from_hex(C[color_key]),
            halign="center",
            valign="middle",
            **kwargs
        )
        lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
    else:
        # Fallback: use a short ASCII stand-in
        fallback = {
            IC["home"]: "H", IC["list"]: "L", IC["plus"]: "+",
            IC["chart"]: "S", IC["cog"]: "G", IC["check"]: "OK",
            IC["times"]: "X", IC["edit"]: "E", IC["trash"]: "D",
            IC["save"]: "S", IC["left"]: "<", IC["right"]: ">",
            IC["money"]: "$",
        }
        lbl = Label(
            text=fallback.get(codepoint, "?"),
            font_size=sp(size),
            color=get_color_from_hex(C[color_key]),
            halign="center", valign="middle",
            **kwargs
        )
        lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
    return lbl


def icon_btn(codepoint, label_text, bg, size=18, height=dp(48),
             color_key="white", **kwargs):
    """
    A Button that shows a FontAwesome icon + text label.
    Uses font_name on the button itself — works without markup.
    """
    if _FA_OK:
        btn = Button(
            text=f"{codepoint}  {label_text}" if label_text else codepoint,
            font_name="FontAwesome",
            font_size=sp(size),
            color=get_color_from_hex(C[color_key]),
            background_normal="",
            background_color=get_color_from_hex(bg),
            size_hint_y=None,
            height=height,
            **kwargs
        )
    else:
        btn = Button(
            text=label_text or codepoint,
            font_size=sp(size),
            color=get_color_from_hex(C[color_key]),
            background_normal="",
            background_color=get_color_from_hex(bg),
            size_hint_y=None,
            height=height,
            **kwargs
        )
    return btn


# ── Colour Palette ────────────────────────────────────────────────────────────
C = {
    "bg":      "#0F1117",
    "surface": "#1A1D27",
    "card":    "#22263A",
    "accent":  "#6C63FF",
    "accent2": "#FF6584",
    "green":   "#4ECCA3",
    "text":    "#EAEAEA",
    "subtext": "#8892A4",
    "error":   "#FF5370",
    "warning": "#FFB347",
    "white":   "#FFFFFF",
    "divider": "#2E3250",
    "bg_dark": "#080A10",
}

def hex_c(key): return get_color_from_hex(C[key])

# ── Helpers ───────────────────────────────────────────────────────────────────

class ColoredBox(BoxLayout):
    def __init__(self, bg_color, radius=0, **kwargs):
        super().__init__(**kwargs)
        self._bg  = bg_color
        self._rad = radius
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*get_color_from_hex(self._bg))
            if self._rad:
                RoundedRectangle(pos=self.pos, size=self.size,
                                 radius=[self._rad])
            else:
                Rectangle(pos=self.pos, size=self.size)


def lbl(text, size=14, color="text", bold=False, halign="left", **kw):
    w = Label(text=text, font_size=sp(size), color=hex_c(color),
              bold=bold, halign=halign, markup=False,
              text_size=(None, None), **kw)
    w.bind(size=lambda s, v: setattr(s, "text_size", (v[0], None)))
    return w


def btn(text, bg="accent", fg="white", height=dp(48),
        font_size=14, on_press=None, **kw):
    """Plain text button (no icons)."""
    b = Button(text=text, font_size=sp(font_size),
               color=hex_c(fg), background_normal="",
               background_color=hex_c(bg),
               size_hint_y=None, height=height, **kw)
    if on_press:
        b.bind(on_press=on_press)
    return b


def inp(hint, multiline=False, filter=None, height=dp(48), **kw):
    return TextInput(
        hint_text=hint, multiline=multiline, input_filter=filter,
        size_hint_y=None, height=height, font_size=sp(14),
        background_color=hex_c("card"), foreground_color=hex_c("text"),
        hint_text_color=hex_c("subtext"), cursor_color=hex_c("accent"),
        padding=[dp(12), dp(10)], **kw)


def card(orientation="vertical", padding=dp(14), spacing=dp(8), **kw):
    return ColoredBox(bg_color=C["card"], radius=dp(12),
                      orientation=orientation,
                      padding=padding, spacing=spacing, **kw)


def divider():
    w = Widget(size_hint_y=None, height=dp(1))
    with w.canvas:
        Color(*hex_c("divider"))
        Rectangle(pos=w.pos, size=w.size)
    w.bind(pos=lambda s,_: s.canvas.clear() or
           _draw_div(s), size=lambda s,_: _draw_div(s))
    return w

def _draw_div(w):
    w.canvas.clear()
    with w.canvas:
        Color(*hex_c("divider"))
        Rectangle(pos=w.pos, size=w.size)


# ── Popups ────────────────────────────────────────────────────────────────────

def popup_ok(title, message, color="text"):
    content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
    content.add_widget(lbl(message, size=14, color=color, halign="center"))
    ok_btn = icon_btn(IC["check"], "OK", bg=C["green"],
                      color_key="bg", height=dp(44))
    content.add_widget(ok_btn)
    p = Popup(title=title, content=content,
              size_hint=(0.85, None), height=dp(210),
              background_color=hex_c("surface"),
              title_color=hex_c("text"),
              separator_color=hex_c("accent"))
    ok_btn.bind(on_press=p.dismiss)
    p.open()


def popup_confirm(title, message, on_yes):
    content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
    content.add_widget(lbl(message, size=13, color="subtext", halign="center"))
    row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(44))
    b_no  = icon_btn(IC["times"], "Cancel", bg=C["card"],  height=dp(44))
    b_yes = icon_btn(IC["check"], "Delete", bg=C["error"], height=dp(44))
    row.add_widget(b_no)
    row.add_widget(b_yes)
    content.add_widget(row)
    p = Popup(title=title, content=content,
              size_hint=(0.85, None), height=dp(230),
              background_color=hex_c("surface"),
              title_color=hex_c("text"),
              separator_color=hex_c("accent2"))
    b_no.bind(on_press=p.dismiss)
    def _yes(_):
        p.dismiss()
        on_yes()
    b_yes.bind(on_press=_yes)
    p.open()


# ── NavBar ────────────────────────────────────────────────────────────────────

class NavBar(ColoredBox):
    """
    Bottom navigation bar.
    Each tab = a transparent Button whose font is set to FontAwesome,
    so the icon codepoint renders correctly. Text label is drawn underneath
    using a separate plain Label.
    """
    TABS = [
        (IC["home"],  "Home",     "dashboard"),
        (IC["list"],  "Expenses", "expenses"),
        (IC["plus"],  "Add",      "add_expense"),
        (IC["chart"], "Stats",    "stats"),
        (IC["cog"],   "Settings", "settings"),
    ]

    def __init__(self, sm, **kwargs):
        super().__init__(bg_color=C["surface"],
                         orientation="horizontal",
                         size_hint_y=None, height=dp(62),
                         padding=[0, 0], spacing=0, **kwargs)
        self.sm = sm
        # Store (icon_lbl, text_lbl) per screen for highlight
        self._tab_widgets = {}

        for codepoint, label_text, screen_name in self.TABS:
            # Container for icon + label stacked vertically
            tab_col = BoxLayout(orientation="vertical",
                                spacing=0, padding=[0, dp(4)])

            # ── Icon: a transparent Button with FA font ───────────────────
            # Using Button (not Label) because Button handles touch natively.
            # We set font_name=FontAwesome so the codepoint renders as an icon.
            ic_btn = Button(
                text=codepoint if _FA_OK else label_text[0],
                font_name="FontAwesome" if _FA_OK else "Roboto",
                font_size=sp(20),
                color=hex_c("subtext"),
                background_normal="",
                background_color=(0, 0, 0, 0),
                size_hint_y=None,
                height=dp(30),
                halign="center",
                valign="middle",
            )
            ic_btn.bind(size=lambda w, s: setattr(w, "text_size", s))
            ic_btn.bind(on_press=lambda _, sn=screen_name: self._go(sn))

            # ── Text label under icon ─────────────────────────────────────
            tx_lbl = Label(
                text=label_text,
                font_size=sp(9),
                color=hex_c("subtext"),
                size_hint_y=None,
                height=dp(14),
                halign="center",
                valign="middle",
            )
            tx_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))

            tab_col.add_widget(ic_btn)
            tab_col.add_widget(tx_lbl)

            self._tab_widgets[screen_name] = (ic_btn, tx_lbl)
            self.add_widget(tab_col)

    def _go(self, screen_name):
        self.sm.transition = SlideTransition(duration=0.18)
        self.sm.current = screen_name
        # Sync highlight on ALL screens' navbars
        for s in self.sm.screens:
            if hasattr(s, "nav_bar") and s.nav_bar:
                s.nav_bar.highlight(screen_name)

    def highlight(self, screen_name):
        for name, (ic_btn, tx_lbl) in self._tab_widgets.items():
            c = hex_c("accent") if name == screen_name else hex_c("subtext")
            ic_btn.color = c
            tx_lbl.color = c


# ── Base Screen ───────────────────────────────────────────────────────────────

class BaseScreen(Screen):
    def __init__(self, nav_bar=None, **kwargs):
        super().__init__(**kwargs)
        self.nav_bar = nav_bar
        root = ColoredBox(bg_color=C["bg"], orientation="vertical",
                          padding=0, spacing=0)
        self.content_area = BoxLayout(orientation="vertical",
                                      padding=[dp(14), dp(10)],
                                      spacing=dp(10))
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


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.month = datetime.now().month
        self.year  = datetime.now().year
        self._build()

    def _build(self):
        ca = self.content_area
        ca.clear_widgets()

        # ── Header ────────────────────────────────────────────────────────
        hdr = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        title_row = BoxLayout(spacing=dp(6))
        title_row.add_widget(icon_label(IC["money"], size=20,
                                         color_key="accent",
                                         size_hint_x=None, width=dp(26)))
        title_row.add_widget(lbl("ExpenseTracker", size=19, bold=True))
        hdr.add_widget(title_row)
        hdr.add_widget(Widget())
        add_btn = icon_btn(IC["plus"], "Add", bg=C["accent"],
                           height=dp(36), size_hint_x=None, width=dp(88))
        add_btn.bind(on_press=lambda _: self.go("add_expense"))
        hdr.add_widget(add_btn)
        ca.add_widget(hdr)

        # ── Month nav ─────────────────────────────────────────────────────
        nav = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        b_prev = icon_btn(IC["left"],  "", bg=C["card"],
                          height=dp(38), size_hint_x=None, width=dp(44))
        b_next = icon_btn(IC["right"], "", bg=C["card"],
                          height=dp(38), size_hint_x=None, width=dp(44))
        self._month_lbl = lbl(
            logic.month_year_label(self.month, self.year),
            size=15, bold=True, halign="center")
        b_prev.bind(on_press=self._prev)
        b_next.bind(on_press=self._next)
        nav.add_widget(b_prev)
        nav.add_widget(self._month_lbl)
        nav.add_widget(b_next)
        ca.add_widget(nav)

        # ── Scrollable body ───────────────────────────────────────────────
        scroll = ScrollView(do_scroll_x=False)
        body = BoxLayout(orientation="vertical", spacing=dp(10),
                         size_hint_y=None, padding=[0, dp(4)])
        body.bind(minimum_height=body.setter("height"))
        self._fill_body(body)
        scroll.add_widget(body)
        ca.add_widget(scroll)

    def _fill_body(self, body):
        data = logic.get_dashboard_data(self.month, self.year)

        # Total card
        tc = card(size_hint_y=None, height=dp(86))
        tc.add_widget(lbl("Total Spending", size=12, color="subtext"))
        tc.add_widget(lbl(data["total_display"], size=30,
                           color="accent", bold=True))
        body.add_widget(tc)

        # By category
        body.add_widget(lbl("By Category", size=12, color="subtext",
                              size_hint_y=None, height=dp(22)))
        for cat in data["by_category"]:
            if cat["total"] == 0:
                continue
            c = card(size_hint_y=None, height=dp(68),
                     orientation="vertical", spacing=dp(4))
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
                suffix = "  ⚠ Over!" if cat["over_budget"] else ""
                c.add_widget(lbl(
                    f"Budget: {logic.format_currency(cat['budget_limit'])}"
                    + suffix, size=10, color="subtext",
                    size_hint_y=None, height=dp(14)))
            body.add_widget(c)

        # Recent
        body.add_widget(lbl("Recent Expenses", size=12, color="subtext",
                              size_hint_y=None, height=dp(22)))
        if not data["recent"]:
            body.add_widget(lbl("No expenses yet — tap Add!",
                                 size=13, color="subtext", halign="center",
                                 size_hint_y=None, height=dp(44)))
        for exp in data["recent"]:
            self._exp_row(body, exp)

    def _exp_row(self, parent, exp):
        r = card(orientation="horizontal", size_hint_y=None, height=dp(54),
                  padding=[dp(10), dp(6)], spacing=dp(8))
        r.add_widget(lbl(exp.get("category_icon", "?"), size=22,
                          size_hint_x=None, width=dp(32)))
        info = BoxLayout(orientation="vertical", spacing=dp(2))
        info.add_widget(lbl(exp["title"], size=13, bold=True))
        info.add_widget(lbl(exp["date_display"], size=11, color="subtext"))
        r.add_widget(info)
        r.add_widget(lbl(exp["amount_display"], size=13, color="accent2",
                          bold=True, halign="right",
                          size_hint_x=None, width=dp(80)))
        parent.add_widget(r)

    def _prev(self, _):
        self.month, self.year = logic.prev_month(self.month, self.year)
        self.on_enter()

    def _next(self, _):
        self.month, self.year = logic.next_month(self.month, self.year)
        self.on_enter()

    def on_enter(self, *_):
        self._build()


# ── Expenses List ─────────────────────────────────────────────────────────────

class ExpensesScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def _build(self):
        ca = self.content_area
        ca.clear_widgets()

        hdr = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        title_row = BoxLayout(spacing=dp(6))
        title_row.add_widget(icon_label(IC["list"], size=18,
                                         color_key="text",
                                         size_hint_x=None, width=dp(24)))
        title_row.add_widget(lbl("All Expenses", size=18, bold=True))
        hdr.add_widget(title_row)
        hdr.add_widget(Widget())
        ab = icon_btn(IC["plus"], "Add", bg=C["accent"],
                      height=dp(36), size_hint_x=None, width=dp(88))
        ab.bind(on_press=lambda _: self.go("add_expense"))
        hdr.add_widget(ab)
        ca.add_widget(hdr)

        # Category filter
        cat_names = logic.get_category_names()
        self._cat_map = {disp: cid for cid, disp in cat_names}
        vals = ["All Categories"] + [d for _, d in cat_names]
        self.spinner = Spinner(
            text="All Categories", values=vals,
            size_hint_y=None, height=dp(40), font_size=sp(13),
            background_normal="", color=hex_c("text"),
            background_color=hex_c("card"))
        self.spinner.bind(text=lambda _, v: self._refresh())
        ca.add_widget(self.spinner)

        self.scroll = ScrollView(do_scroll_x=False)
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
        r = card(orientation="horizontal", size_hint_y=None, height=dp(64),
                  padding=[dp(10), dp(6)], spacing=dp(8))
        r.add_widget(lbl(exp.get("category_icon", "?"), size=22,
                          size_hint_x=None, width=dp(34)))
        info = BoxLayout(orientation="vertical", spacing=dp(2))
        info.add_widget(lbl(exp["title"], size=13, bold=True))
        info.add_widget(lbl(
            f"{exp.get('category_name','')}  •  {exp['date_display']}",
            size=11, color="subtext"))
        r.add_widget(info)

        right = BoxLayout(orientation="vertical",
                          size_hint_x=None, width=dp(86), spacing=dp(4))
        right.add_widget(lbl(exp["amount_display"], size=13, color="accent2",
                              bold=True, halign="right"))
        btns = BoxLayout(spacing=dp(4), size_hint_y=None, height=dp(28))
        eid  = exp["id"]
        e_btn = icon_btn(IC["edit"],  "Edit", bg=C["accent"],
                         height=dp(28), font_size=10)
        d_btn = icon_btn(IC["trash"], "Del",  bg=C["error"],
                         height=dp(28), font_size=10)
        e_btn.bind(on_press=lambda _, i=eid: self._edit(i))
        d_btn.bind(on_press=lambda _, i=eid: self._delete(i))
        btns.add_widget(e_btn)
        btns.add_widget(d_btn)
        right.add_widget(btns)
        r.add_widget(right)
        self.list_box.add_widget(r)

    def _edit(self, eid):
        App.get_running_app().sm.get_screen("add_expense").load_expense(eid)
        self.go("add_expense")

    def _delete(self, eid):
        popup_confirm("Delete", "Delete this expense?",
                      lambda: (logic.delete_expense(eid), self._refresh()))

    def on_enter(self, *_):
        self._build()


# ── Add / Edit Expense ────────────────────────────────────────────────────────

class AddExpenseScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._eid = None
        self._build()

    def _build(self):
        ca = self.content_area
        ca.clear_widgets()

        hdr = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        self._ic_lbl = icon_label(IC["plus"], size=18, color_key="accent",
                                   size_hint_x=None, width=dp(26))
        self._hdr_lbl = lbl("Add Expense", size=18, bold=True)
        hdr.add_widget(self._ic_lbl)
        hdr.add_widget(self._hdr_lbl)
        ca.add_widget(hdr)

        scroll = ScrollView(do_scroll_x=False)
        form   = BoxLayout(orientation="vertical", spacing=dp(10),
                           size_hint_y=None, padding=[0, dp(4)])
        form.bind(minimum_height=form.setter("height"))

        def field(label_text):
            form.add_widget(lbl(label_text, size=11, color="subtext",
                                 size_hint_y=None, height=dp(16)))

        field("Title *")
        self.t_title = inp("e.g. Lunch at café")
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
            values=disp_vals,
            size_hint_y=None, height=dp(44), font_size=sp(13),
            background_normal="", color=hex_c("text"),
            background_color=hex_c("card"))
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
        self._ic_lbl.text  = IC["edit"] if _FA_OK else "E"
        self._hdr_lbl.text = "Edit Expense"
        self.save_btn.text = f"{IC['check']}  Update Expense" if _FA_OK \
                             else "Update Expense"
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
            popup_ok("Saved", "Expense saved!", color="green")
            self._reset()
            Clock.schedule_once(lambda _: self.go("expenses"), 0.7)
        else:
            popup_ok("Error", msg, color="error")

    def _cancel(self, _):
        self._reset()
        self.go("expenses")

    def _reset(self):
        self._eid = None
        self._ic_lbl.text  = IC["plus"] if _FA_OK else "+"
        self._hdr_lbl.text = "Add Expense"
        self.save_btn.text = f"{IC['check']}  Save Expense" if _FA_OK \
                             else "Save Expense"
        self.t_title.text  = ""
        self.t_amount.text = ""
        self.t_date.text   = logic.today_str()
        self.t_note.text   = ""

    def on_enter(self, *_):
        if not self._eid:
            self._reset()
            self._build()


# ── Stats ─────────────────────────────────────────────────────────────────────

class StatsScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.month = datetime.now().month
        self.year  = datetime.now().year
        self._build()

    def _build(self):
        ca = self.content_area
        ca.clear_widgets()

        hdr = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        hdr.add_widget(icon_label(IC["chart"], size=18, color_key="text",
                                   size_hint_x=None, width=dp(24)))
        hdr.add_widget(lbl("Statistics", size=18, bold=True))
        ca.add_widget(hdr)

        nav = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        b_p = icon_btn(IC["left"],  "", bg=C["card"],
                       height=dp(38), size_hint_x=None, width=dp(44))
        b_n = icon_btn(IC["right"], "", bg=C["card"],
                       height=dp(38), size_hint_x=None, width=dp(44))
        self._ml = lbl(logic.month_year_label(self.month, self.year),
                       size=15, bold=True, halign="center")
        b_p.bind(on_press=self._prev)
        b_n.bind(on_press=self._next)
        nav.add_widget(b_p)
        nav.add_widget(self._ml)
        nav.add_widget(b_n)
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

        body.add_widget(lbl("Spending by Category", size=12, color="subtext",
                              size_hint_y=None, height=dp(20)))
        mx = max((c["total"] for c in data["by_category"]), default=1) or 1
        for cat in data["by_category"]:
            if cat["total"] == 0:
                continue
            pct = cat["total"] / mx
            r = ColoredBox(bg_color=C["card"], radius=dp(10),
                           orientation="vertical", size_hint_y=None,
                           height=dp(56), padding=[dp(10), dp(6)],
                           spacing=dp(4))
            top = BoxLayout(size_hint_y=None, height=dp(20))
            top.add_widget(lbl(f"{cat['icon']}  {cat['name']}",
                                size=12, color="text"))
            top.add_widget(lbl(cat["total_display"], size=12,
                                color="accent2", halign="right"))
            r.add_widget(top)
            bar = ColoredBox(bg_color=C["divider"], radius=dp(4),
                             size_hint_y=None, height=dp(10))
            bar.add_widget(ColoredBox(
                bg_color=cat.get("color", C["accent"]),
                radius=dp(4), size_hint=(pct, 1)))
            r.add_widget(bar)
            body.add_widget(r)

        if data["daily_totals"]:
            body.add_widget(lbl("Daily Breakdown", size=12, color="subtext",
                                 size_hint_y=None, height=dp(20)))
            for d in data["daily_totals"]:
                row = BoxLayout(size_hint_y=None, height=dp(26), spacing=dp(8))
                row.add_widget(lbl(f"Day {d['day']}", size=12,
                                    color="subtext",
                                    size_hint_x=None, width=dp(54)))
                row.add_widget(lbl(logic.format_currency(d["total"]),
                                    size=13, color="text"))
                body.add_widget(row)

    def _prev(self, _):
        self.month, self.year = logic.prev_month(self.month, self.year)
        self.on_enter()

    def _next(self, _):
        self.month, self.year = logic.next_month(self.month, self.year)
        self.on_enter()

    def on_enter(self, *_): self._build()


# ── Settings ──────────────────────────────────────────────────────────────────

class SettingsScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def _build(self):
        ca = self.content_area
        ca.clear_widgets()

        hdr = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        hdr.add_widget(icon_label(IC["cog"], size=18, color_key="text",
                                   size_hint_x=None, width=dp(24)))
        hdr.add_widget(lbl("Settings & Budgets", size=18, bold=True))
        ca.add_widget(hdr)
        ca.add_widget(lbl("Monthly budget limits per category:",
                           size=12, color="subtext",
                           size_hint_y=None, height=dp(20)))

        scroll = ScrollView(do_scroll_x=False)
        body   = BoxLayout(orientation="vertical", spacing=dp(8),
                           size_hint_y=None, padding=[0, dp(4)])
        body.bind(minimum_height=body.setter("height"))

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

        body.add_widget(Widget(size_hint_y=None, height=dp(8)))
        sb = icon_btn(IC["save"], "Save Budgets", bg=C["accent"],
                      height=dp(50), size=14)
        sb.bind(on_press=self._save)
        body.add_widget(sb)

        scroll.add_widget(body)
        ca.add_widget(scroll)

    def _save(self, _):
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

    def on_enter(self, *_): self._build()


# ── App ───────────────────────────────────────────────────────────────────────

class ExpenseTrackerApp(App):
    def build(self):
        logic.init()
        self.title = "Expense Tracker"
        self.sm    = ScreenManager()

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
        for s in screens:
            if s.nav_bar:
                s.nav_bar.highlight("dashboard")

        root = BoxLayout(orientation="vertical")
        root.add_widget(self.sm)
        return root


if __name__ == "__main__":
    ExpenseTrackerApp().run()