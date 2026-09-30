# Submission kit: Kate Foresight (404 Brain Not Found, KBC case)

Deadline: **23:00 CEST** on Builderbase. Target: submitted by 22:45. Nobody pushes after submission.

## (a) Builderbase project description (paste as is)

Kate Foresight is a working proof of concept for scalable personalization at KBC. One deterministic decision engine combines three sources: the customer's own calendar (holiday pay, renewals, a child turning 18, maturing savings), Belgium's calendar (tax and rule changes, illustrated with 2026 measures) and intent the customer states in plain language ("keep €8,000 for my renovation"). It ranks moments, protects customers in difficulty (care mode drops all offers), caps frequency and recommends a channel, including a person. Customers see one priority moment with why-now reasons they can correct, a savings allocation that recalculates when they set a goal, and can request an adviser; the operator sees that exact request in the control room, with drill-down charts, a rule studio with a non-mutating impact preview, and an audit log of what was shown, deferred or suppressed. FastAPI, NL/EN/FR, 10,000 synthetic customers measured at 1.3 s per daily pass, token-scoped API, Aikido-scanned.

## (b) Video script (target 2:50, hard limit 3:00)

Setup: restart `./run.sh` right before recording. Browser 1440×900, NL, logged out, passwords at hand.

| Time | On screen (exact clicks) | Voice-over (English) |
|---|---|---|
| 0:00-0:12 | Login screen. | "KBC asked how a bank can respond at exactly the right moment for 2.3 million customers. Kate Foresight is one decision engine over three things: your money history, your calendar and what you tell us." |
| 0:12-0:40 | Log in as **lien**, open **Praat met Kate**. Click the chip or type "Waar ging mijn geld de voorbije drie maanden?". | "Lien asks where her money went. Kate answers for an exact period, first of July to thirtieth of September, with categories that add up to the total, and income and pension saving kept apart." |
| 0:40-1:00 | Ask "Wat komt er de komende 90 dagen?". | "What's coming? Contract dates, legal changes and estimates from her own history, each labelled for what it is." |
| 1:00-1:30 | Ask "Hou €8.000 beschikbaar voor mijn verbouwing", show the editable amount, click **Bevestig**. | "Then she tells Kate something no data shows: eight thousand euros is for her renovation. Kate proposes, Lien confirms, and the engine recalculates: buffer, reserved goal, and five thousand seven hundred left. No money moves." |
| 1:30-1:45 | Ask "Waarom raad je dit aan?", open **Bronnen en aannames**. Click **Overzicht**: the recommendation now says €5.700. | "Why? The evidence, her goal and our assumptions, in the open. The overview changed with it." |
| 1:45-2:05 | Log out, **marc**, **Vraag een adviseur** on the company-car moment, confirm. | "High-stakes moments go to a person. Marc requests an adviser; the prototype creates a real request, and says no call is actually placed." |
| 2:05-2:35 | Log out, **admin**. Overview metrics and charts, then **Adviseurswachtrij**: Marc's request, **Start behandeling**. | "The operator sees the same decisions across 203 synthetic customers, recommendations labelled as recommendations, and Marc's exact request in the queue." |
| 2:35-2:52 | Stay on the control room. | "Rules plus arbitration ran for 10,000 synthetic customers in 1.3 seconds on one process; 2.3 million is an extrapolation, and production needs shared storage and event triggers. Every route is token-scoped and Aikido-scanned. Kate Foresight, by 404 Brain Not Found." |

If long, cut the Marc step (keep the operator queue by pre-creating one request before recording). Voice: only show the microphone if it worked on the recording laptop in a test run; otherwise type.

## (c) Final submission checklist

1. [ ] Video is under 3:00 (check the uploaded duration), uploaded to YouTube as **Unlisted**, and the link plays in an incognito window.
2. [ ] Builderbase description pasted from section (a) (under 150 words).
3. [ ] Repo is **public**: https://github.com/heizeroliver/404-Brain-Not-Found opens in incognito and shows the new README.
4. [ ] Aikido **before** and **after** screenshots taken; final scan has no open high or critical issues.
5. [ ] Both Aikido screenshots uploaded to Builderbase and committed as `screenshots/aikido-before.png` and `screenshots/aikido-after.png`; the README placeholder line replaced with the two images.
6. [ ] README renders on GitHub: all screenshots load, links to `backend/README.md` and `SUBMISSION.md` work.
7. [ ] No secrets in the repo: `git ls-files | grep -i env` shows only `backend/.env.example`; `git grep -nE "AIza|xi-api-key|sk_[a-z0-9]{10}|DEMO_PASSWORD=.+|JWT_SECRET=.+"` returns nothing; no `.mp3` or `decision_log.jsonl` tracked.
8. [ ] Fresh clone plus `./run.sh` works from zero, and `cd backend && ../.venv/bin/pytest -q` shows 51 passed.
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
