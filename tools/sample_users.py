"""
Create sample test users - each has their own encrypted data folder and PIN.
These are made-up personas for testing, not real people.

    python tools/sample_users.py           create all sample users (replaces old sample data)

Open one with:   python main.py --profile thandi     (or sipho, grace, newuser)

| Profile | PIN   | Who                                                        |
|---------|-------|------------------------------------------------------------|
| thandi  | 48261 | Delivery rider weekdays + Saturday market stall; 3 bad days |
| sipho   | 73915 | Seasonal farm worker: paid in big lumps every 2 weeks      |
| grace   | 60418 | Street vendor: small steady daily sales, lots of airtime   |
| newuser | -     | No data - use it to test onboarding (create PIN + plan)    |
"""
import os
import random
import shutil
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from models import EXPENSE, INCOME, SurvivalPlan, Transaction, WeeklyGoal, week_start  # noqa: E402
from storage import Vault  # noqa: E402

SAMPLES_DIR = os.path.join(ROOT, "samples")


def _vault(name):
    path = os.path.join(SAMPLES_DIR, name)
    if os.path.exists(path):
        shutil.rmtree(path)
    return Vault(path)


def _past_goals(plan, today, rnd, choices):
    goals = {}
    for back in range(6, 0, -1):
        wk = week_start(today - timedelta(weeks=back))
        goals[wk.isoformat()] = WeeklyGoal(plan.weekly_target, rnd.choice(choices), wk)
    return goals


def thandi(today):
    """Up-and-down income. Ends with 3 days of spending more than she earned -> Rule of Jars tip."""
    rnd = random.Random(42)  # nosec B311
    plan = SurvivalPlan({"Rent": 375, "Food": 350, "Transport": 150, "Airtime & data": 50}, starting_cash=1200)
    txs = []
    for back in range(42, -1, -1):
        d = today - timedelta(days=back)
        if d.weekday() < 5 and rnd.random() < 0.8:
            txs.append(Transaction(INCOME, rnd.choice([150, 180, 220, 260, 300]), "Deliveries", d))
        if d.weekday() == 5:
            txs.append(Transaction(INCOME, rnd.choice([250, 400, 550]), "Selling", d, note="Saturday market"))
        txs.append(Transaction(EXPENSE, rnd.choice([40, 50, 65, 80]), "Food", d))
        if d.weekday() < 5 and rnd.random() < 0.6:
            txs.append(Transaction(EXPENSE, rnd.choice([20, 30]), "Transport", d))
        if rnd.random() < 0.25:
            txs.append(Transaction(EXPENSE, rnd.choice([29, 49]), "Airtime & data", d))
        if rnd.random() < 0.12:
            txs.append(Transaction(EXPENSE, rnd.choice([60, 120]), "Fun", d))
        if d.weekday() == 0:
            txs.append(Transaction(EXPENSE, 375, "Rent", d, note="Room - weekly"))
        if d.weekday() == 5 and rnd.random() < 0.5:
            txs.append(Transaction(EXPENSE, 200, "Business stock", d))
    for back in (2, 1, 0):   # three slow days in a row (incl. today) with no income
        d = today - timedelta(days=back)
        txs = [t for t in txs if not (t.date == d and t.type == INCOME)]
    return "48261", plan, txs, _past_goals(plan, today, rnd, [0, 50, 100])


def sipho(today):
    """Seasonal farm work: paid R1 800 every second Friday, nothing in between. Last pay was 9+ days ago."""
    rnd = random.Random(7)  # nosec B311
    plan = SurvivalPlan({"Rent": 250, "Food": 300, "Transport": 100}, starting_cash=350)
    txs = []
    last_friday = today - timedelta(days=(today.weekday() - 4) % 7 or 7)
    paydays = {last_friday - timedelta(days=7 + 14 * i) for i in range(4)}
    for back in range(56, -1, -1):
        d = today - timedelta(days=back)
        if d in paydays:
            txs.append(Transaction(INCOME, 1350, "Wages", d, note="Farm - 2 weeks pay"))
        if rnd.random() < 0.15:
            txs.append(Transaction(INCOME, rnd.choice([100, 150]), "Piece job", d, note="Garden work"))
        txs.append(Transaction(EXPENSE, rnd.choice([30, 40, 50]), "Food", d))
        if d.weekday() == 0:
            txs.append(Transaction(EXPENSE, 250, "Rent", d))
        if d.weekday() in (0, 4):
            txs.append(Transaction(EXPENSE, 50, "Transport", d))
        if d in paydays:
            txs.append(Transaction(EXPENSE, 300, "Family support", d, note="Sent home"))
    txs = [t for t in txs if not (t.type == INCOME and t.date > today - timedelta(days=4))]
    return "73915", plan, txs, _past_goals(plan, today, rnd, [0, 0, 200])


def grace(today):
    """Street vendor: small steady sales every day. Has reached this week's target, but spends a lot on airtime."""
    rnd = random.Random(99)  # nosec B311
    plan = SurvivalPlan({"Rent": 300, "Food": 250, "Transport": 70, "Airtime & data": 30}, starting_cash=800)
    txs = []
    for back in range(35, -1, -1):
        d = today - timedelta(days=back)
        if d.weekday() < 6:
            txs.append(Transaction(INCOME, rnd.choice([160, 180, 200, 220]), "Selling", d, note="Fruit & sweets"))
            txs.append(Transaction(EXPENSE, rnd.choice([60, 80, 90]), "Business stock", d))
        txs.append(Transaction(EXPENSE, rnd.choice([30, 40]), "Food", d))
        if rnd.random() < 0.5:
            txs.append(Transaction(EXPENSE, rnd.choice([12, 15, 29]), "Airtime & data", d, note="Daily bundle"))
        if d.weekday() == 0:
            txs.append(Transaction(EXPENSE, 300, "Rent", d))
    # this week: an extra good selling day so the weekly target is met, plus airtime leaks
    txs.append(Transaction(INCOME, 750, "Selling", today, note="Big order for a party"))
    txs.append(Transaction(EXPENSE, 99, "Airtime & data", today, note="Data bundle"))
    txs.append(Transaction(EXPENSE, 99, "Airtime & data", today, note="Another data bundle"))
    txs.append(Transaction(EXPENSE, 150, "Fun", today, note="Party"))
    return "60418", plan, txs, _past_goals(plan, today, rnd, [50, 100, 150])


PERSONAS = {"thandi": thandi, "sipho": sipho, "grace": grace}


def create_all(today=None):
    today = today or date.today()
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    for name, build in PERSONAS.items():
        pin, plan, txs, goals = build(today)
        vault = _vault(name)
        vault.create(pin, plan)
        vault.save(txs, plan, goals)
        print(f"  {name:8} PIN {pin}   {len(txs):3} transactions")
    newuser = os.path.join(SAMPLES_DIR, "newuser")
    if os.path.exists(newuser):
        shutil.rmtree(newuser)
    os.makedirs(newuser)
    print("  newuser  (empty - tests onboarding)")
    print(f"Sample users ready in {SAMPLES_DIR}")


if __name__ == "__main__":
    create_all()
