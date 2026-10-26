# Sample test users

Four made-up test profiles (not real people) so anyone can test MoneyMap in minutes.
Each profile has its own encrypted data and PIN. Your own data in `data/` is never touched.

**Open one:** double-click **`Sample Test Users.bat`** and choose 1–4
(or in a terminal: `python main.py --profile thandi`). Sample data is re-created, dated today, each time.

| # | Profile | PIN | Who they are | What the app should show |
|---|---|---|---|---|
| 1 | **Thandi** | `48261` | Delivery rider on weekdays, sells at a market on Saturdays. Weekly target R925. Last 3 days had no deliveries. | Calendar mostly mixed green/red. Learn: **Rule of Jars** ("spent more than you earned … days in a row") and **Slow days happen**. |
| 2 | **Sipho** | `73915` | Seasonal farm worker paid R1 350 every second Friday, small piece jobs in between. Weekly target R650. | Calendar: long red runs with a green pay-day. Learn: **Rule of Jars** and **Slow days happen**; on low-cash days also **Essentials first** and Safe-to-Spend R0 with "You need R… more". |
| 3 | **Grace** | `60418` | Street vendor with small steady daily sales; big party order today; buys lots of data bundles. Weekly target R650. | Home: weekly target bar full. Learn: **Good days pay for slow days**, **Survival target reached!**, **Find the small leaks**. |
| 4 | **New user** | (you create it) | Nobody yet. | Onboarding: create PIN → weekly survival target → Home with "Start with today" tip. |

The expected tips are checked automatically for every day of the week in `tests/test_core.py::TestSampleUsers`.

## Test script (give these tasks to a peer tester, don't help them)

| # | Task | Pass if… |
|---|---|---|
| 1 | Open as **New user**. Set up the app with a PIN and a weekly plan. | Reaches Home without help; weekly target matches what they typed. |
| 2 | "You just earned R150 from deliveries. Add it." | Money In Today goes up by R150; message "Saved: R150 from Deliveries". |
| 3 | "You spent R45 on food. Add it." | Money Out Today goes up; Safe-to-Spend changes. |
| 4 | Open as **Thandi**. "Which days last week did you spend more than you earned?" | Finds the red days on the History calendar. |
| 5 | "Delete the last food expense on one of those days." | Entry disappears; day colour updates. |
| 6 | "Find out why the app is giving you a tip." | Opens Learn and reads the "Because: …" line. |
| 7 | Open as **Grace**. "Put R100 aside for slow days." | Home → Put money aside → R100; "Put aside this week" shows R100. |
| 8 | Lock the app (padlock), then type a wrong PIN twice. | Shows "Wrong PIN - … tries left". Correct PIN opens it again. |
| 9 | Open as **Sipho**. "Can Sipho spend money on fun today? Why?" | Says no / R0 and points at the "You need R… more" message. |
| 10 | Settings → Export my data. | Finds `moneymap-export.json` in the profile's folder and it is readable. |

Write what each tester says and does in [`peer_feedback_notes.md`](peer_feedback_notes.md).

## Auto-lock check
Leave any profile open without touching it for 5 minutes → MoneyMap locks itself and shows
"Locked after 5 minutes of no activity".
