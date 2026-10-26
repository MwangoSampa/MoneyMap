"""
MoneyMap - budgeting & money confidence for irregular income.
Desktop / mobile app built with Flet (Unit 6).

    python main.py

main.py handles routing between the views:
  /welcome  /plan      onboarding (create PIN, weekly survival target)
  /lock                PIN lock screen
  /home                today's snapshot  (View 1)
  /add/income|expense  add a transaction  (View 2)
  /history             money-map calendar (View 3)
  /learn               financial literacy bites (View 4)
  /settings            plan, PIN, export, erase
"""
import asyncio
import calendar
import logging
import os
import sys
import time
from datetime import date, timedelta

import flet as ft

from insights import EVEN, GREEN, RED, TIP_LIBRARY, MoneyBook
from models import EXPENSE, INCOME, SurvivalPlan, Transaction, categories_for, get_category, parse_amount
from storage import LockedOut, StorageError, Vault, pin_problem

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("MONEYMAP_DATA_DIR", os.path.join(BASE_DIR, "data"))
PROFILE = None
if "--profile" in sys.argv:   # sample test users:  python main.py --profile thandi
    idx = sys.argv.index("--profile")
    PROFILE = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
    if not PROFILE or not PROFILE.isalnum():
        sys.exit("Usage: python main.py --profile thandi|sipho|grace|newuser")
    DATA_DIR = os.path.join(BASE_DIR, "samples", PROFILE.lower())
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
AUTO_LOCK_SECONDS = int(os.environ.get("MONEYMAP_AUTO_LOCK", "300"))

# print-debugging switch:  set MONEYMAP_DEBUG=1 to see every load/save in the terminal
logging.basicConfig(level=logging.DEBUG if os.environ.get("MONEYMAP_DEBUG") == "1" else logging.WARNING,
                    format="[%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("moneymap")

# ------------------------------------------------------------------ shared theme (same look on every screen)
PRIMARY = "#00695C"
PRIMARY_DARK = "#004D40"
INCOME_COLOR = "#1B7F3B"
EXPENSE_COLOR = "#C62828"
EVEN_COLOR = "#F9A825"
BG = "#F3F6F5"
CARD = "#FFFFFF"
INK = "#1A2523"
MUTED = "#55625F"
EMPTY_DAY = "#E4EAE8"
PAD = 16
RADIUS = 16
WEEKDAYS = ["M", "T", "W", "T", "F", "S", "S"]


def icon(name):
    return getattr(ft.Icons, name, ft.Icons.CIRCLE)


def money(amount):
    sign = "-" if amount < 0 else ""
    return sign + "R" + f"{abs(amount):,.0f}".replace(",", " ")


def card(*controls, bgcolor=CARD, padding=PAD, spacing=8):
    return ft.Container(
        content=ft.Column(list(controls), spacing=spacing, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        bgcolor=bgcolor, padding=padding, border_radius=RADIUS,
        shadow=ft.BoxShadow(blur_radius=8, color="#14000000", offset=ft.Offset(0, 2)),
    )


def heading(text, size=18, color=INK):
    return ft.Text(text, size=size, weight=ft.FontWeight.BOLD, color=color)


def muted(text, size=14):
    return ft.Text(text, size=size, color=MUTED)


def big_button(label, icon_name, color, on_click, text_color="#FFFFFF", height=64):
    return ft.Button(
        content=ft.Row([ft.Icon(icon(icon_name), color=text_color, size=26),
                        ft.Text(label, size=17, weight=ft.FontWeight.BOLD, color=text_color)],
                       alignment=ft.MainAxisAlignment.CENTER, spacing=8),
        bgcolor=color, height=height, expand=True, on_click=on_click,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
    )


class MoneyMapApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.vault = Vault(DATA_DIR)
        self.book = None
        self.last_activity = time.time()
        self.route = ""
        self.pending_pin = None
        self.add_type = INCOME
        self.add_category = None
        self.add_day = date.today()
        self.cal_month = date.today().replace(day=1)
        self.selected_day = date.today()
        self._setup_page()

    # ============================================================== page + theme
    def _setup_page(self):
        p = self.page
        p.title = "MoneyMap" + (f" - test user: {PROFILE}" if PROFILE else "")
        p.theme_mode = ft.ThemeMode.LIGHT
        p.theme = ft.Theme(color_scheme_seed=PRIMARY)
        p.bgcolor = BG
        p.padding = 0
        p.window.width = 430
        p.window.height = 880
        p.window.min_width = 360
        p.window.min_height = 640
        ico = os.path.join(ASSETS_DIR, "icon.ico")
        if os.path.exists(ico):
            p.window.icon = ico
        p.on_keyboard_event = lambda e: self.touch()

    def start(self):
        self.go("/lock" if self.vault.is_set_up() else "/welcome")
        self.page.run_task(self.auto_lock_watch)

    # ============================================================== routing
    def go(self, route):
        self.touch()
        protected = route not in ("/welcome", "/plan", "/lock")
        if protected and not self.vault.unlocked:
            route = "/lock"
        self.route = route
        log.debug("route -> %s", route)
        builders = {
            "/welcome": self.view_welcome, "/plan": self.view_plan, "/lock": self.view_lock,
            "/home": self.view_home, "/add/income": lambda: self.view_add(INCOME),
            "/add/expense": lambda: self.view_add(EXPENSE), "/history": self.view_history,
            "/learn": self.view_learn, "/settings": self.view_settings,
        }
        body = builders.get(route, self.view_home)()
        p = self.page
        p.controls.clear()
        p.controls.append(ft.SafeArea(content=ft.Container(content=body, padding=PAD, expand=True), expand=True))
        p.appbar = self.app_bar() if protected else None
        p.navigation_bar = self.nav_bar() if protected else None
        p.update()

    def app_bar(self):
        titles = {"/home": "MoneyMap", "/history": "My Money Map", "/learn": "Learn",
                  "/settings": "Settings", "/add/income": "Add money in", "/add/expense": "Add money out"}
        return ft.AppBar(
            title=ft.Text(titles.get(self.route, "MoneyMap"), weight=ft.FontWeight.BOLD, color="#FFFFFF"),
            bgcolor=PRIMARY, color="#FFFFFF",
            actions=[
                ft.IconButton(icon=ft.Icons.LOCK_OUTLINE, icon_color="#FFFFFF", tooltip="Lock now",
                              on_click=lambda e: self.lock()),
                ft.IconButton(icon=ft.Icons.SETTINGS, icon_color="#FFFFFF", tooltip="Settings",
                              on_click=lambda e: self.go("/settings")),
            ],
        )

    def nav_bar(self):
        routes = ["/home", "/add/income", "/history", "/learn"]
        current = 1 if self.route.startswith("/add") else (routes.index(self.route) if self.route in routes else 0)
        return ft.NavigationBar(
            selected_index=current,
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="Home"),
                ft.NavigationBarDestination(icon=ft.Icons.ADD_CIRCLE_OUTLINE, selected_icon=ft.Icons.ADD_CIRCLE, label="Add"),
                ft.NavigationBarDestination(icon=ft.Icons.CALENDAR_MONTH_OUTLINED, selected_icon=ft.Icons.CALENDAR_MONTH, label="History"),
                ft.NavigationBarDestination(icon=ft.Icons.LIGHTBULB_OUTLINE, selected_icon=ft.Icons.LIGHTBULB, label="Learn"),
            ],
            on_change=lambda e: self.go(routes[e.control.selected_index]),
        )

    # ============================================================== helpers
    def touch(self):
        self.last_activity = time.time()

    async def auto_lock_watch(self):
        """Security: lock automatically after 5 minutes without any activity."""
        while True:
            await asyncio.sleep(5)
            if self.vault.unlocked and time.time() - self.last_activity > AUTO_LOCK_SECONDS:
                self.lock(message="Locked after 5 minutes of no activity")

    def lock(self, message=None):
        self.vault.lock()
        self.book = None   # money data is removed from memory
        self.go("/lock")
        if message:
            self.toast(message)

    def toast(self, message, error=False):
        self.page.show_dialog(ft.SnackBar(
            content=ft.Text(message, color="#FFFFFF", size=15),
            bgcolor=EXPENSE_COLOR if error else PRIMARY_DARK, duration=3500))

    def save(self):
        """Core functionality first: if saving fails, the user must know."""
        try:
            self.vault.save(self.book.transactions, self.book.plan, self.book.goals)
            return True
        except (OSError, StorageError) as e:
            log.exception("Save failed")
            self.toast(f"Could not save: {e}", error=True)
            return False

    def load_book(self):
        transactions, plan, goals = self.vault.load()
        self.book = MoneyBook(transactions, plan, goals)

    def scroll(self, *controls, spacing=14):
        return ft.Column(list(controls), spacing=spacing, scroll=ft.ScrollMode.AUTO, expand=True,
                         horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    # ============================================================== onboarding
    def view_welcome(self):
        pin1 = ft.TextField(label="Create a 5-number PIN", password=True, can_reveal_password=True, max_length=5,
                            keyboard_type=ft.KeyboardType.NUMBER, input_filter=ft.NumbersOnlyInputFilter(),
                            text_size=20, autofocus=True)
        pin2 = ft.TextField(label="Type the PIN again", password=True, max_length=5,
                            keyboard_type=ft.KeyboardType.NUMBER, input_filter=ft.NumbersOnlyInputFilter(), text_size=20)
        error = ft.Text("", color=EXPENSE_COLOR, size=14)

        def next_step(e):
            self.touch()
            problem = pin_problem(pin1.value or "")
            if problem:
                error.value = problem
            elif pin1.value != pin2.value:
                error.value = "The two PINs are not the same"
            else:
                self.pending_pin = pin1.value
                return self.go("/plan")
            self.page.update()

        pin2.on_submit = next_step
        return self.scroll(
            ft.Container(height=12),
            ft.Row([ft.Icon(ft.Icons.MAP, color=PRIMARY, size=56)], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([ft.Text("MoneyMap", size=34, weight=ft.FontWeight.BOLD, color=PRIMARY)],
                   alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([ft.Text("Built for money that comes in on different days.", size=16, color=MUTED)],
                   alignment=ft.MainAxisAlignment.CENTER, wrap=True),
            card(heading("We won't ask for your monthly salary."),
                 muted("We ask one simple question: what did you earn today? "
                       "Your money stays on this device, protected by your PIN.")),
            card(heading("Step 1 of 2 - Your PIN"), pin1, pin2, error,
                 ft.Row([big_button("Next", "ARROW_FORWARD", PRIMARY, next_step)])),
        )

    def view_plan(self):
        editing = self.book is not None
        current = self.book.plan if editing else SurvivalPlan()
        items = dict(current.items) or {k: 0 for k in SurvivalPlan.DEFAULT_ITEMS}
        fields = {}
        total = ft.Text("", size=22, weight=ft.FontWeight.BOLD, color=PRIMARY)
        error = ft.Text("", color=EXPENSE_COLOR)

        def recalc(e=None):
            s = 0.0
            for f in fields.values():
                try:
                    s += float(f.value or 0)
                except ValueError:
                    pass
            total.value = f"Weekly survival target: {money(s)}"
            if e is not None:
                self.page.update()

        for name in items:
            fields[name] = ft.TextField(label=f"{name} per week (R)", value=str(int(items[name])) if items[name] else "",
                                        keyboard_type=ft.KeyboardType.NUMBER, prefix=ft.Text("R "),
                                        input_filter=ft.InputFilter(regex_string=r"^\d*\.?\d{0,2}$"),
                                        on_change=recalc)
        cash = ft.TextField(label="Cash you have right now (R)",
                            value=str(int(current.starting_cash)) if current.starting_cash else "",
                            keyboard_type=ft.KeyboardType.NUMBER, prefix=ft.Text("R "),
                            input_filter=ft.InputFilter(regex_string=r"^\d*\.?\d{0,2}$"), visible=not editing)
        recalc()

        def finish(e):
            self.touch()
            try:
                values = {n: float(f.value or 0) for n, f in fields.items()}
                plan = SurvivalPlan(values, starting_cash=float(cash.value or 0) if not editing else current.starting_cash)
                if plan.weekly_target <= 0:
                    raise ValueError("Add at least one weekly cost, e.g. Food")
                if editing:
                    self.book.plan = plan
                    self.book.goal_for(date.today()).target = plan.weekly_target
                    if self.save():
                        self.toast("Weekly plan updated")
                        self.go("/home")
                    return
                self.vault.create(self.pending_pin, plan)
                self.pending_pin = None
                self.load_book()
                self.go("/home")
                self.toast("Welcome to MoneyMap! Add what you earn and spend each day.")
            except (ValueError, StorageError) as ex:
                error.value = str(ex)
                self.page.update()

        return self.scroll(
            heading("Step 2 of 2 - Your weekly survival target" if not editing else "Your weekly survival target", 20),
            muted("How much do you need each WEEK to get by? Think week by week, not month by month."),
            card(*fields.values(), total),
            card(heading("Starting point"), cash, muted("Money in your pocket or account today.")) if not editing else ft.Container(),
            error,
            ft.Row([big_button("Start MoneyMap" if not editing else "Save plan", "CHECK", PRIMARY, finish)]),
            ft.TextButton("Back", on_click=lambda e: self.go("/settings" if editing else "/welcome")),
        )

    # ============================================================== lock screen
    def view_lock(self):
        pin = ft.TextField(label="PIN", password=True, max_length=5, keyboard_type=ft.KeyboardType.NUMBER,
                           input_filter=ft.NumbersOnlyInputFilter(), text_size=24, autofocus=True,
                           text_align=ft.TextAlign.CENTER)
        error = ft.Text("", color=EXPENSE_COLOR, size=15)

        def unlock(e):
            self.touch()
            try:
                self.vault.unlock(pin.value or "")
                self.load_book()
                self.go("/home")
            except (LockedOut, StorageError) as ex:
                error.value = str(ex)
                pin.value = ""
                self.page.update()

        pin.on_submit = unlock
        remaining = self.vault.lock_remaining()
        if remaining:
            error.value = f"Too many wrong PINs. Try again in {remaining // 60 + 1} min"
        return self.scroll(
            ft.Container(height=60),
            ft.Row([ft.Icon(ft.Icons.LOCK, color=PRIMARY, size=64)], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([heading("MoneyMap is locked", 24, PRIMARY)], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([muted("Enter your 5-number PIN")], alignment=ft.MainAxisAlignment.CENTER),
            card(pin, error, ft.Row([big_button("Unlock", "LOCK_OPEN", PRIMARY, unlock)])),
            ft.Row([muted("Your data is encrypted on this device.", 12)], alignment=ft.MainAxisAlignment.CENTER),
        )

    # ============================================================== View 1: Home
    def view_home(self):
        b, today = self.book, date.today()
        money_in, money_out = b.day_totals(today)
        week_in, _ = b.week_totals(today)
        goal = b.goal_for(today)
        progress = min(1.0, week_in / goal.target) if goal.target else 0
        tips = b.triggered_tips(today)
        tip = tips[0] if tips else b.tip_of_the_day(today)
        shortfall = b.still_needed(today) - b.cash_on_hand()
        hero_note = (f"You need {money(shortfall)} more to cover this week's essentials - spend on needs only"
                     if shortfall > 0 else f"after keeping {money(b.still_needed(today))} for this week's essentials")

        hero = ft.Container(
            content=ft.Column([
                ft.Text("SAFE TO SPEND TODAY", size=13, color="#CFE8E4", weight=ft.FontWeight.BOLD),
                ft.Text(money(b.safe_to_spend(today)), size=44, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                ft.Text(hero_note, size=13, color="#E0F2EF", text_align=ft.TextAlign.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
            bgcolor=PRIMARY, border_radius=RADIUS, padding=20, alignment=ft.Alignment.CENTER,
        )

        def stat(label, value, color):
            return ft.Container(
                content=ft.Column([ft.Text(label, size=12, color=MUTED, weight=ft.FontWeight.BOLD),
                                   ft.Text(money(value), size=24, weight=ft.FontWeight.BOLD, color=color)],
                                  horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                bgcolor=CARD, border_radius=RADIUS, padding=12, expand=True,
                border=ft.Border.all(2, color))

        recent = sorted(b.transactions, key=lambda t: (t.date, t.id), reverse=True)[:4]
        return self.scroll(
            muted(today.strftime("%A %d %B")),
            hero,
            ft.Row([stat("MONEY IN TODAY", money_in, INCOME_COLOR), stat("MONEY OUT TODAY", money_out, EXPENSE_COLOR)]),
            ft.Row([big_button("ADD INCOME", "ADD", INCOME_COLOR, lambda e: self.open_add(INCOME)),
                    big_button("ADD EXPENSE", "REMOVE", EXPENSE_COLOR, lambda e: self.open_add(EXPENSE))]),
            card(
                ft.Row([heading("This week's survival target", 16), ft.Text(money(goal.target), size=16,
                        weight=ft.FontWeight.BOLD, color=PRIMARY)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.ProgressBar(value=progress, color=INCOME_COLOR, bgcolor=EMPTY_DAY, bar_height=12, border_radius=6),
                muted(f"Earned {money(week_in)} of {money(goal.target)} this week ({progress:.0%})"),
                muted(f"Still to pay for essentials: {money(b.still_needed(today))}"),
                ft.Row([muted(f"Put aside this week: {money(goal.saved)}"),
                        ft.OutlinedButton("Put money aside", icon=ft.Icons.SAVINGS, on_click=self.put_aside_dialog)],
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
            ),
            self.tip_card(tip, compact=True),
            card(heading("Recent", 16), *([self.tx_row(t, deletable=False) for t in recent] or
                                          [muted("Nothing yet. Tap ADD INCOME or ADD EXPENSE to start.")])),
        )

    def open_add(self, tx_type):
        self.add_category = None
        self.add_day = date.today()
        self.go("/add/" + tx_type)

    def put_aside_dialog(self, e):
        self.touch()
        field = ft.TextField(label="Amount to put aside (R)", keyboard_type=ft.KeyboardType.NUMBER, autofocus=True,
                             input_filter=ft.InputFilter(regex_string=r"^\d*\.?\d{0,2}$"))
        err = ft.Text("", color=EXPENSE_COLOR)

        def ok(ev):
            try:
                self.book.put_aside(parse_amount(field.value), date.today())
            except ValueError as ex:
                err.value = str(ex)
                return self.page.update()
            self.page.pop_dialog()
            if self.save():
                self.go("/home")
                self.toast("Nice! Money put aside for slow days.")

        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Put money aside"),
            content=ft.Column([muted(f"Cash available: {money(self.book.cash_on_hand())}"), field, err], tight=True),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: self.page.pop_dialog()),
                     ft.FilledButton("Save", on_click=ok)]))

    # ============================================================== View 2: Add transaction
    def view_add(self, tx_type):
        self.add_type = tx_type
        color = INCOME_COLOR if tx_type == INCOME else EXPENSE_COLOR
        amount = ft.TextField(label="Amount", prefix=ft.Text("R ", size=24), text_size=28,
                              keyboard_type=ft.KeyboardType.NUMBER,
                              input_filter=ft.InputFilter(regex_string=r"^\d*\.?\d{0,2}$"))
        note = ft.TextField(label="Note (optional)", max_length=60)
        error = ft.Text("", color=EXPENSE_COLOR, size=15)
        tiles = []

        def pick(name):
            def handler(e):
                self.touch()
                self.add_category = name
                for t in tiles:
                    sel = t.data == name
                    t.bgcolor = color if sel else CARD
                    t.content.controls[0].color = "#FFFFFF" if sel else color
                    t.content.controls[1].color = "#FFFFFF" if sel else INK
                error.value = ""
                self.page.update()
            return handler

        for c in categories_for(tx_type):
            sel = c.name == self.add_category
            tiles.append(ft.Container(
                content=ft.Column([ft.Icon(icon(c.icon), size=34, color="#FFFFFF" if sel else color),
                                   ft.Text(c.name, size=13, weight=ft.FontWeight.BOLD, color="#FFFFFF" if sel else INK,
                                           text_align=ft.TextAlign.CENTER)],
                                  horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4,
                                  alignment=ft.MainAxisAlignment.CENTER),
                width=112, height=96, border_radius=14, bgcolor=color if sel else CARD,
                border=ft.Border.all(2, color), on_click=pick(c.name), data=c.name, ink=True))

        def quick(v):
            def handler(e):
                self.touch()
                amount.value = str(v)
                self.page.update()
            return handler

        day_chips = []

        def set_day(d):
            def handler(e):
                self.touch()
                self.add_day = d
                for ch in day_chips:
                    ch.selected = ch.data == d
                self.page.update()
            return handler

        for label, d in (("Today", date.today()), ("Yesterday", date.today() - timedelta(days=1))):
            day_chips.append(ft.Chip(label=ft.Text(label), selected=self.add_day == d, data=d, on_select=set_day(d)))

        def save(e):
            self.touch()
            if not self.add_category:
                error.value = "Tap a picture first to choose what it was for"
                return self.page.update()
            try:
                t = Transaction(tx_type, amount.value, self.add_category, self.add_day, note.value)
            except ValueError as ex:
                error.value = str(ex)
                return self.page.update()
            self.book.add(t)
            log.debug("added %r", t)
            if self.save():
                self.add_category = None
                self.go("/home")
                self.toast(f"Saved: {money(t.amount)} {'from' if t.is_income else 'on'} {t.category}")

        amount.on_submit = save
        switch = ft.Row([
            ft.Button("Money in", icon=ft.Icons.ARROW_DOWNWARD, expand=True, height=48,
                      bgcolor=INCOME_COLOR if tx_type == INCOME else CARD,
                      color="#FFFFFF" if tx_type == INCOME else INCOME_COLOR,
                      on_click=lambda e: self.open_add(INCOME)),
            ft.Button("Money out", icon=ft.Icons.ARROW_UPWARD, expand=True, height=48,
                      bgcolor=EXPENSE_COLOR if tx_type == EXPENSE else CARD,
                      color="#FFFFFF" if tx_type == EXPENSE else EXPENSE_COLOR,
                      on_click=lambda e: self.open_add(EXPENSE)),
        ])
        return self.scroll(
            switch,
            heading("1. Tap what it was" if tx_type == EXPENSE else "1. Tap where it came from", 16),
            ft.Row(tiles, wrap=True, spacing=10, run_spacing=10, alignment=ft.MainAxisAlignment.CENTER),
            heading("2. How much?", 16),
            amount,
            ft.Row([ft.OutlinedButton(money(v), on_click=quick(v)) for v in (20, 50, 100, 200, 500)], wrap=True),
            ft.Row(day_chips),
            note,
            error,
            ft.Row([big_button("SAVE", "CHECK", color, save)]),
        )

    # ============================================================== View 3: History / Money Map
    def view_history(self):
        b = self.book
        first = self.cal_month
        statuses = b.month_statuses(first.year, first.month)
        today = date.today()
        fill = {GREEN: INCOME_COLOR, RED: EXPENSE_COLOR, EVEN: EVEN_COLOR, None: EMPTY_DAY}

        def select(d):
            def handler(e):
                self.touch()
                self.selected_day = d
                self.go("/history")
            return handler

        def shift(months):
            def handler(e):
                y, m = first.year, first.month + months
                if m == 0:
                    y, m = y - 1, 12
                elif m == 13:
                    y, m = y + 1, 1
                self.cal_month = date(y, m, 1)
                self.go("/history")
            return handler

        rows = [ft.Row([ft.Container(ft.Text(w, weight=ft.FontWeight.BOLD, color=MUTED), expand=1,
                                     alignment=ft.Alignment.CENTER) for w in WEEKDAYS], spacing=4)]
        for week in calendar.Calendar(firstweekday=0).monthdayscalendar(first.year, first.month):
            cells = []
            for d in week:
                if d == 0:
                    cells.append(ft.Container(expand=1, height=46))
                    continue
                day = date(first.year, first.month, d)
                st = statuses[d]
                is_sel = day == self.selected_day
                cells.append(ft.Container(
                    content=ft.Text(str(d), weight=ft.FontWeight.BOLD, color="#FFFFFF" if st else INK),
                    bgcolor=fill[st], expand=1, height=46, border_radius=10, alignment=ft.Alignment.CENTER,
                    border=ft.Border.all(3, INK) if is_sel else (ft.Border.all(2, PRIMARY) if day == today else None),
                    on_click=select(day), ink=True, tooltip=day.strftime("%d %b")))
            rows.append(ft.Row(cells, spacing=4))

        greens = sum(1 for s in statuses.values() if s == GREEN)
        reds = sum(1 for s in statuses.values() if s == RED)
        month_end = date(first.year, first.month, calendar.monthrange(first.year, first.month)[1])
        m_in, m_out = b.totals(b.between(first, month_end))

        def legend(color, text):
            return ft.Row([ft.Container(width=16, height=16, bgcolor=color, border_radius=4), muted(text, 13)], spacing=6, tight=True)

        sel_in, sel_out = b.day_totals(self.selected_day)
        day_txs = b.on_day(self.selected_day)
        return self.scroll(
            ft.Row([ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, on_click=shift(-1), tooltip="Previous month"),
                    heading(first.strftime("%B %Y"), 20),
                    ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, on_click=shift(1), tooltip="Next month")],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            card(*rows, spacing=4),
            ft.Row([legend(INCOME_COLOR, "Earned more"), legend(EXPENSE_COLOR, "Spent more"),
                    legend(EMPTY_DAY, "Nothing added")], wrap=True, spacing=14),
            card(ft.Row([ft.Column([muted("Green days"), heading(str(greens), 22, INCOME_COLOR)]),
                         ft.Column([muted("Red days"), heading(str(reds), 22, EXPENSE_COLOR)]),
                         ft.Column([muted("Month net"), heading(("+" if m_in >= m_out else "-") + money(abs(m_in - m_out)), 22,
                                                                INCOME_COLOR if m_in >= m_out else EXPENSE_COLOR)])],
                        alignment=ft.MainAxisAlignment.SPACE_AROUND)),
            card(heading(self.selected_day.strftime("%A %d %B"), 16),
                 muted(f"In {money(sel_in)}   ·   Out {money(sel_out)}"),
                 *([self.tx_row(t) for t in day_txs] or [muted("Nothing added on this day. Tap another day.")])),
        )

    def tx_row(self, t, deletable=True):
        cat = get_category(t.category)
        color = INCOME_COLOR if t.is_income else EXPENSE_COLOR
        trailing = [ft.Text(("+" if t.is_income else "-") + money(t.amount), weight=ft.FontWeight.BOLD, color=color, size=16)]
        if deletable:
            trailing.append(ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=MUTED, tooltip="Delete",
                                          on_click=lambda e, tx=t: self.confirm_delete(tx)))
        return ft.Row([
            ft.Row([ft.Container(ft.Icon(icon(cat.icon), color="#FFFFFF", size=20), bgcolor=color, border_radius=20,
                                 width=36, height=36, alignment=ft.Alignment.CENTER),
                    ft.Column([ft.Text(t.category, weight=ft.FontWeight.BOLD, color=INK),
                               muted(t.note or t.date.strftime("%d %b"), 12)], spacing=0)], spacing=10, expand=True),
            ft.Row(trailing, spacing=0),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    def confirm_delete(self, t):
        self.touch()

        def yes(e):
            self.page.pop_dialog()
            self.book.remove(t.id)
            if self.save():
                self.go("/history")
                self.toast("Deleted")

        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Delete this?"),
            content=ft.Text(f"{t.category}  {money(t.amount)}  on {t.date.strftime('%d %b')}"),
            actions=[ft.TextButton("Keep it", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton("Delete", bgcolor=EXPENSE_COLOR, on_click=yes)]))

    # ============================================================== View 4: Learn
    def tip_card(self, tip, compact=False):
        controls = [ft.Row([ft.Icon(icon(tip.icon), color="#8A5A00", size=28), heading(tip.title, 16)], spacing=10)]
        if tip.reason:
            controls.append(ft.Text("Because: " + tip.reason, size=13, italic=True, color="#8A5A00"))
        controls.append(ft.Text(tip.body, size=15, color=INK))
        if compact:
            controls.append(ft.TextButton("More money tips", icon=ft.Icons.ARROW_FORWARD, on_click=lambda e: self.go("/learn")))
        return card(*controls, bgcolor="#FFF6DD")

    def view_learn(self):
        today = date.today()
        triggered = self.book.triggered_tips(today)
        shown = {t.key for t in triggered}
        library = [t for k, t in TIP_LIBRARY.items() if k not in shown]
        return self.scroll(
            heading("For you right now", 18),
            muted("These tips appear because of what you added."),
            *([self.tip_card(t) for t in triggered] or [card(muted("No alerts today - well done! Keep adding every day."))]),
            heading("30-second money bites", 18),
            *[card(ft.Row([ft.Icon(icon(t.icon), color=PRIMARY), heading(t.title, 15)]),
                   ft.Text(t.body, size=14, color=INK)) for t in library],
        )

    # ============================================================== Settings
    def view_settings(self):
        b = self.book

        def change_pin(e):
            old = ft.TextField(label="Current PIN", password=True, max_length=5, input_filter=ft.NumbersOnlyInputFilter())
            new = ft.TextField(label="New PIN", password=True, max_length=5, input_filter=ft.NumbersOnlyInputFilter())
            err = ft.Text("", color=EXPENSE_COLOR)

            def ok(ev):
                try:
                    self.vault.change_pin(old.value or "", new.value or "")
                except StorageError as ex:
                    err.value = str(ex)
                    return self.page.update()
                self.page.pop_dialog()
                self.toast("PIN changed")

            self.page.show_dialog(ft.AlertDialog(title=ft.Text("Change PIN"),
                                                 content=ft.Column([old, new, err], tight=True),
                                                 actions=[ft.TextButton("Cancel", on_click=lambda ev: self.page.pop_dialog()),
                                                          ft.FilledButton("Change", on_click=ok)]))

        def export(e):
            path = self.vault.export_plain()
            self.toast(f"Saved a readable copy to {path}. Keep it private - it is not encrypted.")

        def erase(e):
            pin = ft.TextField(label="Enter your PIN to confirm", password=True, max_length=5,
                               input_filter=ft.NumbersOnlyInputFilter())
            err = ft.Text("", color=EXPENSE_COLOR)

            def ok(ev):
                try:
                    self.vault.erase_all(pin.value or "")
                except StorageError as ex:
                    err.value = str(ex)
                    return self.page.update()
                self.page.pop_dialog()
                self.book = None
                self.go("/welcome")
                self.toast("All MoneyMap data was erased from this device")

            self.page.show_dialog(ft.AlertDialog(
                title=ft.Text("Erase everything?"),
                content=ft.Column([muted("This deletes all your transactions and goals. It cannot be undone."), pin, err], tight=True),
                actions=[ft.TextButton("Cancel", on_click=lambda ev: self.page.pop_dialog()),
                         ft.FilledButton("Erase", bgcolor=EXPENSE_COLOR, on_click=ok)]))

        def row(icon_name, title, subtitle, on_click, color=PRIMARY):
            return ft.ListTile(leading=ft.Icon(icon(icon_name), color=color), title=ft.Text(title, weight=ft.FontWeight.BOLD),
                               subtitle=ft.Text(subtitle), on_click=on_click)

        items = "  ·  ".join(f"{k} {money(v)}" for k, v in b.plan.items.items() if v)
        return self.scroll(
            card(heading("My weekly plan", 16), muted(items or "No items yet"),
                 muted(f"Weekly survival target: {money(b.plan.weekly_target)}"),
                 ft.TextButton("Edit weekly plan", icon=ft.Icons.EDIT, on_click=lambda e: self.go("/plan"))),
            card(heading("Security", 16),
                 row("PASSWORD", "Change PIN", "Your PIN unlocks and decrypts your data", change_pin),
                 row("LOCK", "Lock now", f"MoneyMap also locks itself after {AUTO_LOCK_SECONDS // 60} minutes", lambda e: self.lock()),
                 muted("• Data is encrypted with AES-256 and only your PIN can open it\n"
                       "• 5 wrong PINs locks the app for 5 minutes\n"
                       "• Everything stays on this device - no internet needed", 13)),
            card(heading("My data", 16),
                 row("DOWNLOAD", "Export my data", "Save a readable copy (JSON) in the data folder", export),
                 row("DELETE_FOREVER", "Erase everything", "Remove all MoneyMap data from this device", erase, EXPENSE_COLOR)),
            muted(f"Data folder: {DATA_DIR}", 12),
        )


def main(page: ft.Page):
    MoneyMapApp(page).start()


if __name__ == "__main__":
    ft.run(main, assets_dir=ASSETS_DIR)
