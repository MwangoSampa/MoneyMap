"""
Create 6 weeks of sample data for demos and peer testing.

    python tools/demo_data.py            (refuses if data already exists)
    python tools/demo_data.py --force    (replaces existing data!)

Demo PIN: 48261
Sample user: delivery rider on weekdays, sells at a market stall on Saturdays.
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

DEMO_PIN = "48261"


def build(data_dir, force=False):
    vault = Vault(data_dir)
    if vault.is_set_up():
        if not force:
            print("Data already exists. Use --force to replace it (this deletes your current data).")
            return False
        shutil.rmtree(data_dir)
        vault = Vault(data_dir)
    plan = SurvivalPlan({"Rent": 375, "Food": 350, "Transport": 150, "Airtime & data": 50}, starting_cash=1200)
    vault.create(DEMO_PIN, plan)
    rnd = random.Random(42)  # nosec B311
    today = date.today()
    txs, goals = [], {}
    for back in range(42, -1, -1):
        d = today - timedelta(days=back)
        if d.weekday() < 5 and rnd.random() < 0.8:
            txs.append(Transaction(INCOME, rnd.choice([150, 180, 220, 260, 300]), "Deliveries", d))
        if d.weekday() == 5:
            txs.append(Transaction(INCOME, rnd.choice([250, 400, 550]), "Selling", d))
        txs.append(Transaction(EXPENSE, rnd.choice([40, 50, 65, 80]), "Food", d))
        if d.weekday() < 5 and rnd.random() < 0.6:
            txs.append(Transaction(EXPENSE, rnd.choice([20, 30]), "Transport", d))
        if rnd.random() < 0.25:
            txs.append(Transaction(EXPENSE, rnd.choice([29, 49, 99]), "Airtime & data", d))
        if rnd.random() < 0.15:
            txs.append(Transaction(EXPENSE, rnd.choice([60, 120]), "Fun", d))
        if d.weekday() == 0:
            txs.append(Transaction(EXPENSE, 375, "Rent", d, note="Room - weekly"))
        if d.weekday() == 5 and rnd.random() < 0.5:
            txs.append(Transaction(EXPENSE, 200, "Business stock", d))
    # three red days in a row ending yesterday -> shows the "Rule of Jars" tip
    for back in (3, 2, 1):
        d = today - timedelta(days=back)
        txs = [t for t in txs if not (t.date == d and t.type == INCOME)]
    for back in range(6, 0, -1):
        wk = week_start(today - timedelta(weeks=back))
        goals[wk.isoformat()] = WeeklyGoal(plan.weekly_target, rnd.choice([0, 50, 100]), wk)
    vault.save(txs, plan, goals)
    print(f"Demo data created in {data_dir}  ({len(txs)} transactions).  PIN: {DEMO_PIN}")
    return True


if __name__ == "__main__":
    build(os.environ.get("MONEYMAP_DATA_DIR", os.path.join(ROOT, "data")), force="--force" in sys.argv)
