"""
MoneyMap data model (Unit 4 - OOP).

Transaction  - one money-in or money-out event.
WeeklyGoal   - the user's weekly survival target and what they put aside that week.
Category     - what the money was for / where it came from (icon-first for low-literacy users).

This file has NO user-interface code, so every rule here can be tested on its own.
"""
from dataclasses import dataclass
from datetime import date, timedelta
import uuid

INCOME = "income"
EXPENSE = "expense"
MAX_AMOUNT = 1_000_000


@dataclass(frozen=True)
class Category:
    name: str
    type: str          # INCOME or EXPENSE
    icon: str          # name of a Material icon, mapped to ft.Icons in the UI
    essential: bool = False   # counts toward the weekly survival target


CATEGORIES = [
    # money in
    Category("Deliveries", INCOME, "DELIVERY_DINING"),
    Category("Selling", INCOME, "STOREFRONT"),
    Category("Piece job", INCOME, "HANDYMAN"),
    Category("Wages", INCOME, "PAYMENTS"),
    Category("Family / gift", INCOME, "VOLUNTEER_ACTIVISM"),
    Category("Other income", INCOME, "ADD_CIRCLE"),
    # money out
    Category("Food", EXPENSE, "RESTAURANT", essential=True),
    Category("Transport", EXPENSE, "DIRECTIONS_BUS", essential=True),
    Category("Rent", EXPENSE, "HOME", essential=True),
    Category("Airtime & data", EXPENSE, "PHONE_ANDROID", essential=True),
    Category("School", EXPENSE, "SCHOOL", essential=True),
    Category("Health", EXPENSE, "LOCAL_HOSPITAL", essential=True),
    Category("Business stock", EXPENSE, "INVENTORY_2"),
    Category("Family support", EXPENSE, "FAMILY_RESTROOM"),
    Category("Fun", EXPENSE, "CELEBRATION"),
    Category("Other", EXPENSE, "MORE_HORIZ"),
]
_BY_NAME = {c.name: c for c in CATEGORIES}


def categories_for(tx_type):
    return [c for c in CATEGORIES if c.type == tx_type]


def get_category(name):
    return _BY_NAME.get(name)


def parse_amount(value):
    """Turn user input into a safe money amount, or raise ValueError with a friendly message."""
    try:
        amount = round(float(str(value).replace(",", "").replace("R", "").strip()), 2)
    except (TypeError, ValueError):
        raise ValueError("Please type an amount, for example 50")
    if not (0 < amount <= MAX_AMOUNT):   # also rejects NaN and infinity
        raise ValueError("Amount must be more than R0")
    return amount


def to_date(value):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValueError(f"Not a valid date: {value!r}")


def week_start(day):
    """Weeks run Monday to Sunday."""
    return day - timedelta(days=day.weekday())


class Transaction:
    def __init__(self, type, amount, category, date, note="", id=None):
        if type not in (INCOME, EXPENSE):
            raise ValueError("Type must be income or expense")
        cat = get_category(category)
        if cat is None or cat.type != type:
            raise ValueError(f"Unknown {type} category: {category!r}")
        self.type = type
        self.amount = parse_amount(amount)
        self.category = category
        self.date = to_date(date)
        self.note = str(note or "").strip()[:60]
        self.id = id or uuid.uuid4().hex[:12]

    @property
    def is_income(self):
        return self.type == INCOME

    @property
    def is_essential(self):
        return self.type == EXPENSE and get_category(self.category).essential

    @property
    def signed_amount(self):
        return self.amount if self.is_income else -self.amount

    def to_dict(self):
        return {"id": self.id, "type": self.type, "amount": self.amount, "category": self.category,
                "date": self.date.isoformat(), "note": self.note}

    @classmethod
    def from_dict(cls, d):
        return cls(d["type"], d["amount"], d["category"], d["date"], d.get("note", ""), d.get("id"))

    def __repr__(self):  # helpful when print-debugging
        return f"Transaction({self.type}, R{self.amount:.2f}, {self.category}, {self.date})"


class WeeklyGoal:
    """Weekly survival target (e.g. rent + food + transport) and money put aside that week."""

    def __init__(self, target, saved=0.0, week_of=None):
        target = float(target)
        if target < 0 or target > MAX_AMOUNT:
            raise ValueError("Target must be between R0 and R1 000 000")
        self.target = round(target, 2)
        self.saved = round(max(0.0, float(saved)), 2)
        self.week_of = week_start(to_date(week_of or date.today()))

    def add_saving(self, amount):
        self.saved = round(self.saved + parse_amount(amount), 2)

    def to_dict(self):
        return {"target": self.target, "saved": self.saved, "week_of": self.week_of.isoformat()}

    @classmethod
    def from_dict(cls, d):
        return cls(d["target"], d.get("saved", 0.0), d.get("week_of"))

    def __repr__(self):
        return f"WeeklyGoal(target=R{self.target:.2f}, saved=R{self.saved:.2f}, week_of={self.week_of})"


class SurvivalPlan:
    """What the user needs each week to survive. Set during onboarding (the Plan stage)."""
    DEFAULT_ITEMS = ("Rent", "Food", "Transport", "Airtime & data")

    def __init__(self, items=None, starting_cash=0.0):
        self.items = {}
        for name, value in (items or {}).items():
            value = float(value or 0)
            if value < 0 or value > MAX_AMOUNT:
                raise ValueError(f"{name}: amount must be between R0 and R1 000 000")
            self.items[str(name)[:30]] = round(value, 2)
        self.starting_cash = round(max(0.0, float(starting_cash or 0)), 2)

    @property
    def weekly_target(self):
        return round(sum(self.items.values()), 2)

    def to_dict(self):
        return {"items": self.items, "starting_cash": self.starting_cash}

    @classmethod
    def from_dict(cls, d):
        return cls(d.get("items", {}), d.get("starting_cash", 0.0))
