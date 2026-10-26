"""
MoneyMap logic: totals, safe-to-spend, the money-map calendar colours and behaviour-triggered tips.
Pure Python (no UI), so every rule is unit-tested in tests/test_insights.py.
"""
import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from models import EXPENSE, INCOME, SurvivalPlan, Transaction, WeeklyGoal, week_start

GREEN, RED, EVEN = "green", "red", "even"


@dataclass
class Tip:
    key: str
    title: str
    body: str
    icon: str
    reason: str = ""


TIP_LIBRARY = {
    "jars": Tip("jars", "Rule of Jars",
                "Try splitting tomorrow's income into 3 pots: NEEDS (food, transport, rent), "
                "SAVE (even R10), and SPEND. When the SPEND pot is empty, you stop.", "SAVINGS"),
    "good_day": Tip("good_day", "Good days pay for slow days",
                    "You earned more than usual today. Put part of the extra aside now, before it "
                    "disappears. Slow days will come - this is your cushion.", "TRENDING_UP"),
    "slow_week": Tip("slow_week", "Slow days happen",
                     "No income for a few days? Cover NEEDS first: food, transport, rent. Pause the "
                     "nice-to-haves until money comes in again.", "HOURGLASS_BOTTOM"),
    "leaks": Tip("leaks", "Find the small leaks",
                 "Airtime bundles, snacks and 'fun' add up. Buying a weekly data bundle instead of "
                 "daily ones can save a lot each month.", "WATER_DROP"),
    "target_met": Tip("target_met", "Survival target reached!",
                      "You earned enough for this week's essentials. Anything extra this week can "
                      "go to savings first. Tap 'Put money aside' on Home.", "EMOJI_EVENTS"),
    "shortfall": Tip("shortfall", "Essentials first",
                     "Your cash is less than what you still need this week. Spend only on needs, "
                     "and avoid mashonisa loans - they can cost 30-50% a month.", "PRIORITY_HIGH"),
    "start": Tip("start", "Start with today",
                 "MoneyMap doesn't need your monthly salary. Just add what you earned and spent "
                 "today. After a week you'll see your own money map.", "EDIT_CALENDAR"),
    "low_month": Tip("low_month", "Plan from your low weeks",
                     "If your income goes up and down, plan your budget on a slow week, not your "
                     "best week. Then every good week leaves you extra.", "INSIGHTS"),
    "scam": Tip("scam", "Never share your PIN or OTP",
                "Banks never ask for your PIN or one-time PIN on the phone. If someone does, hang "
                "up and call the bank's official number.", "SHIELD"),
    "buffer": Tip("buffer", "Build a small buffer",
                  "Aim to save one week of survival money first. A small buffer is the cheapest "
                  "loan you will ever get - it's your own money.", "ACCOUNT_BALANCE_WALLET"),
    "separate": Tip("separate", "Business money is not pocket money",
                    "If you sell or trade, keep stock money separate. Pay yourself a fixed amount "
                    "and leave the rest to buy new stock.", "STOREFRONT"),
}
ROTATING = ["low_month", "buffer", "scam", "separate", "jars", "leaks"]


class MoneyBook:
    """Holds the user's transactions, survival plan and weekly goals, and answers questions about them."""

    def __init__(self, transactions=None, plan=None, goals=None):
        self.transactions = list(transactions or [])
        self.plan = plan or SurvivalPlan()
        self.goals = dict(goals or {})   # "YYYY-MM-DD" (Monday) -> WeeklyGoal

    # ------------------------------------------------------------- changes
    def add(self, tx: Transaction):
        self.transactions.append(tx)
        return tx

    def remove(self, tx_id):
        before = len(self.transactions)
        self.transactions = [t for t in self.transactions if t.id != tx_id]
        return len(self.transactions) < before

    def goal_for(self, day) -> WeeklyGoal:
        key = week_start(day).isoformat()
        goal = self.goals.get(key)
        if goal is None:
            goal = WeeklyGoal(self.plan.weekly_target, 0.0, key)
            self.goals[key] = goal
        return goal

    def put_aside(self, amount, day):
        if amount > self.cash_on_hand():
            raise ValueError("You don't have that much cash right now")
        self.goal_for(day).add_saving(amount)

    # ------------------------------------------------------------- totals
    def on_day(self, day):
        return [t for t in self.transactions if t.date == day]

    def between(self, start, end):
        """Transactions with start <= date <= end."""
        return [t for t in self.transactions if start <= t.date <= end]

    @staticmethod
    def totals(txs):
        money_in = round(sum(t.amount for t in txs if t.type == INCOME), 2)
        money_out = round(sum(t.amount for t in txs if t.type == EXPENSE), 2)
        return money_in, money_out

    def day_totals(self, day):
        return self.totals(self.on_day(day))

    def week_totals(self, day):
        start = week_start(day)
        return self.totals(self.between(start, start + timedelta(days=6)))

    def total_saved(self):
        return round(sum(g.saved for g in self.goals.values()), 2)

    def cash_on_hand(self):
        net = sum(t.signed_amount for t in self.transactions)
        return round(self.plan.starting_cash + net - self.total_saved(), 2)

    def essential_spent_this_week(self, day):
        start = week_start(day)
        return round(sum(t.amount for t in self.between(start, day) if t.is_essential), 2)

    def still_needed(self, day):
        """How much of this week's survival target has not been paid yet."""
        target = self.goal_for(day).target
        return round(max(0.0, target - self.essential_spent_this_week(day)), 2)

    def days_left_in_week(self, day):
        return 7 - day.weekday()   # includes today

    def safe_to_spend(self, day):
        """Cash you can use today after keeping enough for the rest of this week's essentials."""
        free = self.cash_on_hand() - self.still_needed(day)
        return round(max(0.0, free / self.days_left_in_week(day)), 2)

    # ------------------------------------------------------------- money map (calendar)
    def day_status(self, day):
        txs = self.on_day(day)
        if not txs:
            return None
        money_in, money_out = self.totals(txs)
        if money_in > money_out:
            return GREEN
        if money_out > money_in:
            return RED
        return EVEN

    def month_statuses(self, year, month):
        days = calendar.monthrange(year, month)[1]
        return {d: self.day_status(date(year, month, d)) for d in range(1, days + 1)}

    def red_streak(self, today):
        """Red days in a row, ending today (or yesterday if nothing is logged today yet)."""
        day = today if self.on_day(today) else today - timedelta(days=1)
        streak = 0
        while self.day_status(day) == RED:
            streak += 1
            day -= timedelta(days=1)
        return streak

    def usual_income_day(self, today, lookback=28):
        """Average income on the days you earned something (today not included)."""
        start = today - timedelta(days=lookback)
        per_day = {}
        for t in self.between(start, today - timedelta(days=1)):
            if t.type == INCOME:
                per_day[t.date] = per_day.get(t.date, 0) + t.amount
        return round(sum(per_day.values()) / len(per_day), 2) if per_day else 0.0

    # ------------------------------------------------------------- behaviour-triggered tips
    def triggered_tips(self, today):
        if not self.transactions:
            return [self._tip("start", "You haven't added anything yet")]
        tips = []
        if self.cash_on_hand() < self.still_needed(today):   # most urgent first
            tips.append(self._tip("shortfall", "Your cash is below what this week's essentials still need"))
        streak = self.red_streak(today)
        if streak >= 3:
            tips.append(self._tip("jars", f"You spent more than you earned {streak} days in a row"))
        today_in, _ = self.day_totals(today)
        usual = self.usual_income_day(today)
        if usual and today_in >= usual * 1.5:
            tips.append(self._tip("good_day", f"Today you earned R{today_in:,.0f} - usually about R{usual:,.0f}"))
        last3 = self.between(today - timedelta(days=2), today)
        has_history = any(t.date < today - timedelta(days=2) for t in self.transactions)
        if has_history and not any(t.type == INCOME for t in last3):
            tips.append(self._tip("slow_week", "No income logged in the last 3 days"))
        week_in, week_out = self.week_totals(today)
        target = self.goal_for(today).target
        if target and week_in >= target:
            tips.append(self._tip("target_met", f"You earned R{week_in:,.0f} this week - target R{target:,.0f}"))
        start = week_start(today)
        leaks = sum(t.amount for t in self.between(start, today) if t.category in ("Airtime & data", "Fun"))
        if week_out and leaks / week_out > 0.25 and leaks >= 50:
            tips.append(self._tip("leaks", f"Airtime and fun are {leaks / week_out:.0%} of your spending this week"))
        return tips

    def tip_of_the_day(self, today):
        return TIP_LIBRARY[ROTATING[today.toordinal() % len(ROTATING)]]

    @staticmethod
    def _tip(key, reason):
        base = TIP_LIBRARY[key]
        return Tip(base.key, base.title, base.body, base.icon, reason)
