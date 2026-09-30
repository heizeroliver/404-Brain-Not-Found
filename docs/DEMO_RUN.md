# Demo run: Kate Foresight recording script (170–175 s)

Target length 2:52 (hard limit 3:00). Language: **EN** for the international jury. Every number below
comes from the synthetic demo data (as of 30 Sep 2026) and the backend; nothing is invented on screen.

## Pre-recording setup (do this in order)

1. **Restart the backend right before recording** (`Ctrl+C`, then `./run.sh`). All state (goals, advisor
   requests, feedback) is in memory; a fresh start guarantees Lien has no goal yet and Rita has no open request.
2. Open **three browser profiles** (or one normal + two private windows) at http://localhost:5173, 1440×900:
   - Profile A: log in as **lien** → lands on `#/customer/overview`.
   - Profile B: log in as **rita** → `#/customer/overview`.
   - Profile C: log in as **admin** → `#/control/overview`.
   Login: click the persona card, enter the demo password printed by `run.sh`, click the open-app button.
3. In each profile click **EN** in the header language switch (NL / EN / FR). Language is per browser.
4. Do not create Rita's adviser request in advance: the AR id is created live at 1:15–1:40.
5. Voice: only show the microphone if push-to-talk worked in a test run on this laptop today. Live ElevenLabs
   is **not verified** in the team's test environment (no key there; tested with mocks). Default plan: **type**.
6. Close notifications, zoom 100 %, hide bookmarks bar.

## Script

| Time | Screen and exact clicks | Voice-over (EN) |
|---|---|---|
| **0:00–0:12** Problem / promise | Profile A, `#/customer/overview` (Lien's priority moment "Savings sitting idle"). | "KBC asked how a bank can respond at exactly the right moment for millions of customers. Kate Foresight is one decision engine that reads your own calendar, Belgium's calendar and what you tell it, and explains every choice." |
| **0:12–0:32** Lien anticipation | Click **Timeline** in the customer nav (`#/customer/timeline`). Show the 90-day view (two reminder windows: "Savings sitting idle" 30 Sep–30 Oct, "Ready for a first home?" 30 Sep–29 Dec). Click **12 months**: "Top up your pension saving before year end" (deadline, 31 Dec 2026), "Your holiday pay is coming" (expected payment, 22 May 2027), "Your insurance premium is going up" (renewal, 1 Jul 2027). | "Kate looks ahead. Every item says what kind of date it is: a fixed legal deadline on 31 December, a contract renewal date, a reminder window when advice is useful, and holiday pay that is an estimate from Lien's own history, labelled as expected, not promised." |
| **0:32–1:15** Lien states intent | Click **Talk to Kate** (`#/customer/talk`). Type `Keep €8,000 available for my renovation`, Enter. The proposal card shows **What changes if you confirm?**: Current plan vs Proposed plan: savings €26,000; modeled buffer €12,300 (assumption, six months of net income); reserved for goals €0 → €8,000; remaining €13,700 → €5,700; "Kate suggests now" vs "After this plan"; "Preview only: nothing is saved and no money moves." Click **Apply this plan**. Then type `Why do you recommend this?`, Enter; show evidence, the goal and assumptions. Optional 2 s: click **Overview**, the idle-cash card now says €5,700. | "Then Lien tells Kate something no data shows: eight thousand euros is for her renovation. Before anything is saved, Kate shows what changes: the buffer stays, eight thousand is reserved, and the amount Kate would suggest investing drops from 13,700 to 5,700. The preview saves nothing. Lien applies it, and asks why: the evidence, her own goal and our assumptions, in the open." |
| **1:15–1:40** Rita protective situation | Switch to Profile B, `#/customer/overview`. Priority moment "We held a payment" (€900, payee name mismatch "KBC Veiligheidsdienst"). Click **Ask an adviser** → dialog "Contact an advisor … This is a prototype: no real call is scheduled." → **Request contact**. Point at the new request id **AR-xxxx** under **My requests**. | "Rita is in a different situation: a payment was held because the payee name doesn't match. Kate recognises this and stops selling. Rita asks for an adviser. The prototype creates a real request with its own id; no real adviser is contacted." |
| **1:40–2:15** Operator | Switch to Profile C. Click **Advisor queue** (`#/control/queue`): find the **same AR id** (Rita, Payment protection, status requested). Click the row to open the **Decision receipt** (alternative: **Moments** tab → search `rita` → click the **Payment protection** row). Walk down: situation recognised; recommendation shown; suggestions withheld (Idle cash, Term account maturity); recorded reason "Sales suggestions paused while we help"; deferred items (frequency cap, 1 per week); channel Advisor; advisor request with the AR id and status. Optional: **Start review**. | "In the control room the operator sees Rita's exact request, same id. The decision receipt explains what the engine did for her: what it recognised, what it showed, which sales suggestions it withheld and why, what it deferred because of the weekly cap, and which channel it chose. The bank can explain every decision." |
| **2:15–2:40** Rule studio (optional; cut first if long) | Click **Rule studio** (`#/control/rules`). Keep the illustrative template, click **Preview impact**. Show affected customers. Do **not** click Activate rule. | "A new rule, for example a Belgian tax change, is data, not a release. Preview impact shows who would be affected across all customers; the preview activates nothing." |
| **2:40–2:55** Honest scale + close | Stay on the control room overview (`#/control/overview`). | "Honest scale: this prototype runs on 203 synthetic customers. We benchmarked rules plus arbitration for 10,000 synthetic customers in 1.3 seconds on one process, without data loading, narration or storage. 2.3 million is our proposed architecture, not something we ran. Kate Foresight makes personalization something the customer can understand, correct and act on—and the bank can explain." |

Timing check: 12 + 20 + 43 + 25 + 35 + 25 + 15 = 175 s. Without the rule studio segment, stretch the operator
segment by 10 s and end at about 2:40.

## If something fails during recording

- **Voice fails** (no microphone, no transcript, no spoken answer): type the same sentence. A voice failure keeps
  the text answer ("Spoken answer unavailable; the text answer is shown."), so just continue.
- **Lien already has a renovation goal** or Rita's request already exists: the backend was not restarted. Stop,
  restart `./run.sh`, log in again in all three profiles (tokens survive only if the JWT secret is unchanged).
- **Queue does not show Rita's AR id**: refresh `#/control/queue` or use Moments → search `rita` → Payment protection.
- **Kate asks to clarify**: the sentence contained two amounts. Retype exactly `Keep €8,000 available for my renovation`.

## What not to say

- Do not say ElevenLabs voice was tested live; it was tested with mocks only.
- Do not say an adviser is contacted or money moves; both are explicitly prototype-only.
- Do not claim 2.3M was measured; the benchmark (docs/BENCHMARK.md) excludes data loading, fan-out and storage, and the 32-worker figure is extrapolated.
- Do not claim Aikido results that the team has not screenshotted.

## Submission checklist

1. [ ] Tests pass: `cd backend && ../.venv/bin/pytest -q` (fully offline).
2. [ ] Backend restarted, three profiles logged in, EN selected, dry run done once end to end.
3. [ ] Video under 3:00 (check the uploaded duration), YouTube **Unlisted**, link plays in an incognito window.
4. [ ] Aikido after-scan screenshot taken **by the team** and uploaded (plus the before-scan); do not describe results you have not seen.
5. [ ] README and SUBMISSION.md match what the video shows.
6. [ ] Repo public, no secrets tracked (see SUBMISSION.md checklist item 7).
7. [ ] Builderbase: all fields filled, submitted **before 23:00 CEST** (aim 22:45); screenshot the confirmation.
