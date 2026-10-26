"""Isolated tests for the data model, money logic and storage.   Run:  python -m pytest -v"""
import json
import os
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from insights import GREEN, RED, MoneyBook  # noqa: E402
from models import EXPENSE, INCOME, SurvivalPlan, Transaction, WeeklyGoal, parse_amount, week_start  # noqa: E402
from storage import LockedOut, StorageError, Vault, WrongPin  # noqa: E402

MON = date(2026, 10, 26)   # a Monday
PIN = "48261"


def tx(kind, amount, cat, day):
    return Transaction(kind, amount, cat, day)


def plan(target_food=300, rent=400, cash=500):
    return SurvivalPlan({"Food": target_food, "Rent": rent}, starting_cash=cash)


# ------------------------------------------------------------------ models
class TestModels:
    def test_transaction_round_trip(self):
        t = tx(INCOME, "150", "Deliveries", MON)
        assert Transaction.from_dict(t.to_dict()).to_dict() == t.to_dict()

    @pytest.mark.parametrize("bad", ["", "abc", "-5", "0", "nan", "inf", "2000000", None])
    def test_bad_amounts_rejected(self, bad):
        with pytest.raises(ValueError):
            parse_amount(bad)

    def test_amount_accepts_friendly_input(self):
        assert parse_amount("R1,250.50") == 1250.5

    def test_category_must_match_type(self):
        with pytest.raises(ValueError):
            tx(EXPENSE, 10, "Deliveries", MON)   # Deliveries is an income category

    def test_essential_flag(self):
        assert tx(EXPENSE, 10, "Food", MON).is_essential
        assert not tx(EXPENSE, 10, "Fun", MON).is_essential

    def test_weekly_goal(self):
        g = WeeklyGoal(700, week_of=date(2026, 10, 29))
        assert g.week_of == MON
        g.add_saving(50)
        assert g.saved == 50

    def test_plan_target(self):
        assert plan().weekly_target == 700

    def test_week_starts_monday(self):
        assert week_start(date(2026, 11, 1)) == MON   # Sunday -> previous Monday


# ------------------------------------------------------------------ money logic
class TestInsights:
    def test_today_totals(self):
        b = MoneyBook([tx(INCOME, 200, "Deliveries", MON), tx(EXPENSE, 50, "Food", MON)], plan())
        assert b.day_totals(MON) == (200, 50)

    def test_cash_on_hand_includes_start_and_savings(self):
        b = MoneyBook([tx(INCOME, 200, "Deliveries", MON)], plan(cash=500))
        b.put_aside(100, MON)
        assert b.cash_on_hand() == 600

    def test_cannot_put_aside_more_than_cash(self):
        b = MoneyBook([], plan(cash=50))
        with pytest.raises(ValueError):
            b.put_aside(100, MON)

    def test_safe_to_spend_keeps_money_for_essentials(self):
        # cash 1400, still need 700 for the week, 7 days left -> 100 a day
        b = MoneyBook([], plan(cash=1400))
        assert b.still_needed(MON) == 700
        assert b.safe_to_spend(MON) == 100

    def test_essential_spending_reduces_still_needed(self):
        b = MoneyBook([tx(EXPENSE, 400, "Rent", MON)], plan(cash=1400))
        assert b.still_needed(MON) == 300
        assert b.safe_to_spend(MON) == round((1000 - 300) / 7, 2)

    def test_safe_to_spend_never_negative(self):
        assert MoneyBook([], plan(cash=0)).safe_to_spend(MON) == 0

    def test_calendar_colours(self):
        b = MoneyBook([tx(INCOME, 100, "Deliveries", MON), tx(EXPENSE, 300, "Food", MON + timedelta(1))], plan())
        st = b.month_statuses(2026, 10)
        assert st[26] == GREEN and st[27] == RED and st[28] is None

    def test_red_streak_and_jars_tip(self):
        days = [MON + timedelta(i) for i in range(3)]
        b = MoneyBook([tx(EXPENSE, 80, "Food", d) for d in days], plan())
        assert b.red_streak(days[-1]) == 3
        assert "jars" in [t.key for t in b.triggered_tips(days[-1])]

    def test_streak_counts_from_yesterday_if_today_empty(self):
        days = [MON + timedelta(i) for i in range(3)]
        b = MoneyBook([tx(EXPENSE, 80, "Food", d) for d in days], plan())
        assert b.red_streak(days[-1] + timedelta(1)) == 3

    def test_good_day_tip(self):
        txs = [tx(INCOME, 100, "Deliveries", MON - timedelta(i)) for i in range(1, 8)]
        txs.append(tx(INCOME, 300, "Deliveries", MON))
        b = MoneyBook(txs, plan(cash=5000))
        assert "good_day" in [t.key for t in b.triggered_tips(MON)]

    def test_slow_week_tip(self):
        b = MoneyBook([tx(INCOME, 100, "Deliveries", MON - timedelta(10))], plan(cash=5000))
        assert "slow_week" in [t.key for t in b.triggered_tips(MON)]

    def test_target_met_tip(self):
        b = MoneyBook([tx(INCOME, 800, "Selling", MON)], plan(cash=0))
        assert "target_met" in [t.key for t in b.triggered_tips(MON)]

    def test_new_user_gets_start_tip(self):
        assert [t.key for t in MoneyBook([], plan()).triggered_tips(MON)] == ["start"]


# ------------------------------------------------------------------ storage + security
class TestStorage:
    def make(self, tmp_path):
        v = Vault(str(tmp_path))
        v.create(PIN, plan())
        return v

    def test_save_and_load_round_trip(self, tmp_path):
        v = self.make(tmp_path)
        txs = [tx(INCOME, 150, "Deliveries", MON)]
        goals = {"2026-10-26": WeeklyGoal(700, 50, MON)}
        v.save(txs, plan(), goals)
        v.lock()
        v2 = Vault(str(tmp_path))
        v2.unlock(PIN)
        loaded, p, g = v2.load()
        assert [t.to_dict() for t in loaded] == [t.to_dict() for t in txs]
        assert p.weekly_target == 700 and g["2026-10-26"].saved == 50

    def test_files_are_encrypted(self, tmp_path):
        v = self.make(tmp_path)
        v.save([Transaction(EXPENSE, 77, "Food", MON, note="bread and milk")], plan(), {})
        for name in ("transactions.json", "goals.json", "settings.json"):
            text = open(tmp_path / name).read()
            assert "bread" not in text and "Food" not in text and PIN not in text

    def test_wrong_pin_and_lockout(self, tmp_path):
        v = self.make(tmp_path)
        v.lock()
        for _ in range(4):
            with pytest.raises(WrongPin):
                v.unlock("99887")
        with pytest.raises(LockedOut):
            v.unlock("99887")
        with pytest.raises(LockedOut):
            v.unlock(PIN)   # even the right PIN is refused during lockout

    def test_weak_pin_refused(self, tmp_path):
        with pytest.raises(StorageError):
            Vault(str(tmp_path)).create("12345", plan())

    def test_locked_vault_cannot_load(self, tmp_path):
        v = self.make(tmp_path)
        v.lock()
        with pytest.raises(StorageError):
            v.load()

    def test_tampered_file_detected(self, tmp_path):
        v = self.make(tmp_path)
        path = tmp_path / "transactions.json"
        obj = json.loads(path.read_text())
        obj["data"] = obj["data"][:-6] + "AAAAAA"
        path.write_text(json.dumps(obj))
        with pytest.raises(StorageError):
            v.load()

    def test_damaged_file_recovers_from_backup(self, tmp_path):
        v = self.make(tmp_path)
        v.save([tx(INCOME, 10, "Deliveries", MON)], plan(), {})
        v.save([tx(INCOME, 10, "Deliveries", MON), tx(INCOME, 20, "Selling", MON)], plan(), {})
        (tmp_path / "transactions.json").write_text("{ broken json")   # simulated crash mid-write
        txs, _, _ = v.load()
        assert len(txs) == 1   # the previous good version from .bak

    def test_change_pin_keeps_data(self, tmp_path):
        v = self.make(tmp_path)
        v.save([tx(INCOME, 10, "Deliveries", MON)], plan(), {})
        v.change_pin(PIN, "70362")
        v.lock()
        with pytest.raises(WrongPin):
            v.unlock(PIN)
        v.unlock("70362")
        assert len(v.load()[0]) == 1

    def test_export_and_erase(self, tmp_path):
        v = self.make(tmp_path)
        v.save([tx(INCOME, 10, "Deliveries", MON)], plan(), {})
        out = v.export_plain()
        assert json.load(open(out))["transactions"][0]["category"] == "Deliveries"
        v.erase_all(PIN)
        assert not Vault(str(tmp_path)).is_set_up()


# ------------------------------------------------------------------ sample test users
class TestSampleUsers:
    @pytest.mark.parametrize("offset", range(7))   # every day of the week
    def test_personas_trigger_expected_tips(self, offset):
        from tools.sample_users import PERSONAS
        today = MON + timedelta(days=offset)
        expected = {"thandi": {"jars"}, "sipho": {"jars", "slow_week"}, "grace": {"target_met", "leaks"}}
        for name, build in PERSONAS.items():
            _, plan_, txs, goals = build(today)
            keys = {t.key for t in MoneyBook(txs, plan_, goals).triggered_tips(today)}
            assert expected[name] <= keys, (name, today, keys)

    def test_sample_users_open_with_their_pins(self, tmp_path, monkeypatch):
        import tools.sample_users as su
        monkeypatch.setattr(su, "SAMPLES_DIR", str(tmp_path))
        su.create_all(MON)
        for name, pin in (("thandi", "48261"), ("sipho", "73915"), ("grace", "60418")):
            v = Vault(str(tmp_path / name))
            v.unlock(pin)
            assert len(v.load()[0]) > 50
        assert not Vault(str(tmp_path / "newuser")).is_set_up()
