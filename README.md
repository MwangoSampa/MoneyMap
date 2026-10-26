# MoneyMap

**Budgeting and money confidence for people whose income changes every day.**
Team MoneyMap Pioneers · Python + Flet desktop/mobile app · offline-first

MoneyMap doesn't ask *"What is your monthly salary?"*. It asks *"What did you earn today?"*

---

## 1. Problem statement
Millions of gig workers, small traders and seasonal earners have **irregular income**. Most budgeting apps assume a
fixed monthly salary. That mismatch causes stress, poor planning and little access to practical financial literacy.

## 2. The app
A simple, **offline-first** budgeting and financial-literacy app for irregular and informal income.
All data stays on the device, encrypted, and works without internet.

## 3. User journey

| Stage | Screen | What happens |
|---|---|---|
| **Plan (onboarding)** | Welcome → Weekly plan | Create a 5-number PIN, then set a **weekly survival target** (rent, food, transport, airtime) and the cash you have now. No monthly salary. |
| **View 1** | Home | Today's snapshot: **Money In Today / Money Out Today / Safe-to-Spend**. Big, high-contrast **ADD INCOME** (green) and **ADD EXPENSE** (red) buttons. Weekly survival-target progress bar and a tip. |
| **View 2** | Add | Tap a **picture category** → tap or type the amount → **SAVE**. Quick-amount buttons (R20–R500), Today/Yesterday. |
| **View 3** | History / Money Map | A **calendar**, not a spreadsheet: 🟩 green day = earned more than spent, 🟥 red day = overspent, grey = nothing added. Tap a day to see (and delete) its entries. |
| **View 4** | Learn | **30-second tips triggered by behaviour**, e.g. 3 red days in a row → *"Rule of Jars"*; a big earning day → *"Good days pay for slow days"*; no income for 3 days → *"Slow days happen"*. Plus a library of money bites. |
| Extra | Settings | Edit weekly plan, change PIN, lock now, export my data, erase everything. |

**Safe-to-spend** = (cash on hand − what this week's essentials still need) ÷ days left in the week.

## 4. Technical integration

| Course unit | Where it is used |
|---|---|
| **Unit 4 – OOP** | `models.py`: `Transaction(type, amount, category, date)`, `WeeklyGoal(target, saved)`, `SurvivalPlan`, `Category`. Validation lives in the classes. |
| **Unit 4 – Files** | `storage.py`: saves to `data/transactions.json` and `data/goals.json` (plus `settings.json`). Atomic saves with a `.bak` backup so a crash can't destroy data. |
| **Unit 6 – Flet** | `main.py`: routing between `/home`, `/add`, `/history`, `/learn`, `/settings`, `/lock`; one shared theme (`PRIMARY`, `PAD`, `RADIUS`, card style) for consistent padding and contrast on every screen. |
| Testing / debugging | `tests/test_core.py` – 45 isolated tests. `MONEYMAP_DEBUG=1` prints every load/save (print-debugging). `__repr__` on models for readable debug output. |
| Security (SSDLC) | PIN hashed with scrypt, AES-256-GCM encrypted files, 5-try lockout, auto-lock after 5 min, tamper detection, export & erase (POPIA). |

```
MoneyMapApp/
├── main.py            Flet app: routing + all views + shared theme
├── models.py          Transaction, WeeklyGoal, SurvivalPlan, categories
├── insights.py        Safe-to-spend, money-map colours, behaviour-triggered tips
├── storage.py         JSON persistence + encryption + PIN lock
├── data/              transactions.json, goals.json, settings.json (created on first run)
├── assets/            icon.png, icon.ico
├── tests/             test_core.py
├── samples/           sample test users (thandi, sipho, grace, newuser) - encrypted
├── tools/             sample_users.py (creates test users), demo_data.py
├── Run MoneyMap.bat / Sample Test Users.bat / Run Tests.bat   double-click launchers
├── docs/              build sprint log, peer-feedback notes, screenshots
├── requirements.txt
└── MoneyMap.code-workspace   VS Code run + test configs
```

> **Note for assessors:** `transactions.json` and `goals.json` are real JSON files, but their content is encrypted
> (AES-256) so a lost phone doesn't expose someone's finances. To see the data in plain JSON, use
> **Settings → Export my data** (writes `data/moneymap-export.json`).

## 5. Run it

**Easiest (Windows):** double-click **`Run MoneyMap.bat`**. It installs what's needed the first time and opens the app.

**Sample test users:** double-click **`Sample Test Users.bat`** and pick one:

| Test user | PIN | Story |
|---|---|---|
| Thandi | 48261 | Delivery rider + Saturday market, 3 slow days in a row |
| Sipho | 73915 | Seasonal farm worker, paid every 2 weeks, cash is tight |
| Grace | 60418 | Street vendor, steady sales, target met, spends a lot on data |
| New user | – | Empty - tests the first-time setup |

Full test script and expected results: [`docs/sample_test_users.md`](docs/sample_test_users.md).

**Tests:** double-click **`Run Tests.bat`** (45 tests + Bandit security scan).

**In VS Code:** double-click **`MoneyMap.code-workspace`**, run `python -m pip install -r requirements-dev.txt` once in
the terminal, then press **F5** and pick **MoneyMap (run app)** or one of the **Test user** configs.

Requires Python 3.10+ (tick "Add python.exe to PATH" when installing). The first launch downloads the Flet
desktop runtime, so it needs internet once; after that MoneyMap works offline.

## 6. Build Sprint process
See [`docs/build_sprint_log.md`](docs/build_sprint_log.md) for Plan → Build → Test → Iterate → Polish & Package, and
[`docs/peer_feedback_notes.md`](docs/peer_feedback_notes.md) for the peer-testing record.
