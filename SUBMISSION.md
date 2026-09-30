# Submission kit: Kate Foresight (404 Brain Not Found, KBC case)

Deadline: **23:00 CEST** on Builderbase. Target: submitted by 22:45. Nobody pushes after submission.

## (a) Builderbase project description (paste as is)

Kate Foresight is a working proof of concept for scalable personalization at KBC. One deterministic decision engine combines three sources: the customer's own calendar (holiday pay, renewals, a child turning 18, maturing savings), Belgium's calendar (tax and rule changes, illustrated with 2026 measures) and intent the customer states in plain language ("keep €8,000 for my renovation"). It ranks moments, protects customers in difficulty (care mode drops all offers), caps frequency and recommends a channel, including a person. Customers see one priority moment with why-now reasons they can correct, a savings allocation that recalculates when they set a goal, and can request an adviser; the operator sees that exact request in the control room, with drill-down charts, a rule studio with a non-mutating impact preview, and an audit log of what was shown, deferred or suppressed. FastAPI, NL/EN/FR, 10,000 synthetic customers measured at 1.3 s per daily pass, token-scoped API, Aikido-scanned.

## (b) Video script (target 2:52, hard limit 3:00)

Full click-by-click script, setup and fallbacks: [docs/DEMO_RUN.md](docs/DEMO_RUN.md). Record in **EN** (header switch). Restart `./run.sh` right before recording (state is in memory); pre-log-in three browser profiles: **lien**, **rita**, **admin**.

| Time | On screen | Voice-over (short) |
|---|---|---|
| 0:00-0:12 | Lien, `#/customer/overview`. | Problem and promise: one decision engine over your calendar, Belgium's calendar and what you tell it. |
| 0:12-0:32 | **Timeline**, 90 days then **12 months**: reminder windows (idle cash, first home), deadline 31 Dec (pension top-up), renewal 1 Jul 2027, expected holiday pay 22 May 2027. | Known dates, reminder windows and estimates are labelled as what they are. |
| 0:32-1:15 | **Talk to Kate**: type "Keep €8,000 available for my renovation" → **What changes if you confirm?** (savings €26,000; modeled buffer €12,300, assumption; reserved €0 → €8,000; remaining €13,700 → €5,700) → **Apply this plan** → "Why do you recommend this?". | The preview saves nothing; Lien applies; Why shows evidence, goal, assumptions. |
| 1:15-1:40 | Rita: "We held a payment" → **Ask an adviser** → **Request contact** → AR id under **My requests**. | Protective situation, sales paused; prototype request, no real adviser contacted. |
| 1:40-2:15 | Admin: **Advisor queue** → same AR id → **Decision receipt** (or **Moments** → search "rita" → Payment protection). | Recognised situation, shown recommendation, withheld suggestions (Idle cash, Term account maturity), reason "Sales suggestions paused while we help", deferred by weekly cap, channel Advisor. |
| 2:15-2:40 | Optional: **Rule studio** → **Preview impact** (do not activate). | A rule is data; preview activates nothing. |
| 2:40-2:55 | Control room overview. | 203 synthetic customers in the prototype; 10,000 benchmarked (rules + arbitration, 1.3 s, one process, excludes loading/storage); 2.3M is proposed architecture. Close: "Kate Foresight makes personalization something the customer can understand, correct and act on—and the bank can explain." |

If long, cut the rule studio. Voice: live ElevenLabs is not verified (tested with mocks); type unless the microphone worked in a test run on the recording laptop. If voice fails, type the same sentence; the text answer stays.

## (c) Final submission checklist

1. [ ] Video is under 3:00 (check the uploaded duration), uploaded to YouTube as **Unlisted**, and the link plays in an incognito window.
2. [ ] Builderbase description pasted from section (a) (under 150 words).
3. [ ] Repo is **public**: https://github.com/heizeroliver/404-Brain-Not-Found opens in incognito and shows the new README.
4. [ ] Aikido **before** and **after** screenshots taken; final scan has no open high or critical issues.
5. [ ] Both Aikido screenshots uploaded to Builderbase and committed as `screenshots/aikido-before.png` and `screenshots/aikido-after.png`; the README placeholder line replaced with the two images.
6. [ ] README renders on GitHub: all screenshots load, links to `backend/README.md` and `SUBMISSION.md` work.
7. [ ] No secrets in the repo: `git ls-files | grep -i env` shows only `backend/.env.example`; `git grep -nE "AIza|xi-api-key|sk_[a-z0-9]{10}|DEMO_PASSWORD=.+|JWT_SECRET=.+"` returns nothing; no `.mp3` or `decision_log.jsonl` tracked.
8. [ ] Fresh clone plus `./run.sh` works from zero, and `cd backend && ../.venv/bin/pytest -q` passes (fully offline).
9. [ ] All Builderbase fields filled: team name, KBC case, video link, description, repo link, Aikido screenshots.
10. [ ] Submitted before 23:00 CEST (aim 22:45); screenshot the confirmation page; nobody pushes to `main` afterwards.

## (d) If the jury asks (60 seconds)

**"Kate already does proactive nudges. What is new?"**
Kate's 140+ situations react to what already happened; Foresight projects what is about to happen from two calendars, the customer's life and Belgium's rules. It is the decision layer above the nudges: it chooses the moment, the channel and when a human must step in, and explains every choice.

**"How does it scale to 2.3 million customers?"**
Rules are conditions over a flat customer twin, so they run as a nightly BigQuery batch, while Pub/Sub events (salary lands, invoice arrives, payment held) re-evaluate one customer in real time on Cloud Run. Arbitration is per customer and stateless, the LLM only phrases, and the frequency cap keeps it at one pushed moment per customer per week.

**"Isn't this creepy?"**
It uses only data KBC already holds as bank and insurer, and every card shows exactly which signals were used and why. One tap on Never or a consent toggle switches it off, and vulnerable customers get fewer messages, not more: care mode drops every offer and brings in a person.

**"Why templates instead of an LLM?"**
Numbers, eligibility and channel must be exact and auditable, so the engine computes them and NL/EN/FR templates carry them. Gemini is pluggable and may only rephrase, with validation that every number already exists in the evidence; tonight it was blocked on the lab project by org policy and the product still works, which is the point.

**"How is it secure?"**
The customer id comes only from the JWT, so no endpoint ever accepts another customer's id; admin routes need the admin role, every input is validated with extra fields forbidden, and login and voice are rate limited. Secrets live only in a git-ignored `.env`, dependencies are pinned in a lockfile, and Aikido scans before and after show what we fixed.

**"What would you build for the final on 20 October?"**
Live Pub/Sub triggers on stage (a salary lands, a moment appears) and a BigQuery run over 2.3 million synthetic twins with timing and cost. Then an advisor cockpit that shows the same moment and Why?, and a measurement loop: helpfulness, opt-outs and fairness per segment.
