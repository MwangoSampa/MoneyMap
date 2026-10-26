# Build Sprint log – MoneyMap

## 1. Plan
- Confirmed the Week 3 design brief: build for **irregular income**, not salaried users.
- Key decision: onboarding asks for a **weekly survival target**, never a monthly salary.
- Priorities, in order: (1) data saves correctly and safely, (2) the four core views work, (3) looks and polish.

## 2. Build (order followed)
1. `models.py` – `Transaction`, `WeeklyGoal`, `SurvivalPlan`, categories with icons. Input validation inside the classes.
2. `storage.py` – JSON persistence to `data/`, atomic writes + `.bak`, then encryption and the PIN lock.
3. `insights.py` – today's totals, safe-to-spend, calendar colours, red-day streaks, behaviour-triggered tips.
4. `main.py` – Flet UI: onboarding, lock, Home, Add, History, Learn, Settings, shared theme.

## 3. Test
- **Automated (isolated) tests:** `tests/test_core.py`, 45 tests, all passing. They cover models, money logic,
  save/load, encryption, wrong-PIN lockout, tamper detection, and recovery from a damaged file, and that each sample test user triggers the right tips on every day of the week.
- **Security scans:** Bandit (static code scan) – 0 issues. pip-audit (library vulnerabilities) – none found.
- **Manual UI run-through:** onboarding → add income/expense → calendar → tips → lock/unlock → wrong PIN.
- **Sample test users:** Thandi, Sipho, Grace and New user (`docs/sample_test_users.md`) with a 10-task test script.
- **Peer testing:** record each session in `peer_feedback_notes.md`.

## 4. Iterate – changes made from testing so far
| Found during | Problem | Fix |
|---|---|---|
| Unit test | `parse_amount` test expected wrong rounding for "R1,250.505" | Corrected the test; amounts are rounded to cents |
| UI run | Text fields didn't stretch the full width of their card | Shared `card()` and page column now stretch children |
| UI run | Calendar legend items stacked on separate lines | Legend rows set to `tight=True` so they sit side by side |
| UI run | "Safe to spend R0" gave no reason when cash was short | Home now says how much more is needed for essentials |
| Code review | Demo data never added "Business stock" (wrong indentation) | Fixed the indentation in `tools/demo_data.py` |
| Sample user Sipho | Low cash showed "Rule of Jars" before the more urgent warning | Tips are now ordered by urgency: "Essentials first" comes first |
| Sample user Sipho | Negative cash showed as "R-40" | Money format now shows "-R40" |
| Sample user Thandi | Her "3 bad days" tip only showed on some weekdays | Sample data fixed; a test now checks every day of the week |

Add a row here every time peer feedback leads to a change.

## 5. Polish & package
- One theme for every screen: `PRIMARY`, `INCOME_COLOR`, `EXPENSE_COLOR`, `PAD = 16`, `RADIUS = 16`.
- High-contrast ADD INCOME / ADD EXPENSE buttons with icons **and** labels.
- Clean folder structure, `requirements.txt`, VS Code workspace, README, app icon.
