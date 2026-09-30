# Submission kit: Kate Foresight (404 Brain Not Found, KBC case)

Deadline: **23:00 CEST** on Builderbase. Target: submitted by 22:45. Nobody pushes after submission.

## (a) Builderbase project description (paste as is)

Kate Foresight turns KBC from a bank that reacts into one that sees what is coming. It reads two calendars KBC alone holds for every customer: their life (salary rhythm, holiday pay, insurance renewals, a child turning 18) and Belgium's rulebook (2026 capital-gains tax, insurance tax 9.6%, company-car deductibility). One decision layer ranks each moment by stakes, urgency, confidence and affinity, protects vulnerable customers (care mode drops all sales), caps frequency, and picks the channel: in-app card, Kate voice note, or a human advisor. Customers state intent in plain language ("keep €8,000 for my renovation") and the engine recalculates. Every card shows Why?, and customers correct it with Not now, Not relevant or Never. A control room covers 203 synthetic customers, human handoffs and an append-only decision log; a new government rule runs against all customers in seconds. FastAPI, NL/EN/FR, ElevenLabs voice, measured 10,000 customers in 1.3 s, JWT with no IDOR, scanned with Aikido.

## (b) Video script (target 2:55, hard limit 3:00)

Setup before recording: `./run.sh` running, browser at http://localhost:5173 on the login screen in **NL**, window around 1400 px wide, demo password copied to the clipboard, zoom 100%. If ElevenLabs keys are missing, the Listen step shows Kate's disclosure line as text; keep it in.

| Time | On screen (exact clicks) | Voice-over (English) |
|---|---|---|
| 0:00 to 0:15 | Login screen in NL, the four persona cards. No clicks. | "Every May, Belgian employees get holiday pay. Every December, the pension-saving deadline. And every year, Belgium changes the rules. Banks react to all of this. Kate Foresight sees it coming." |
| 0:15 to 0:25 | Click the **Lien** card, paste the password, click **Open de app**. | "KBC is a bank and an insurer, so it already holds two calendars: the customer's life and Belgium's rulebook. Meet Lien, 29, from Leuven." |
| 0:25 to 0:42 | On the idle-cash card, click **Waarom?**. The drawer opens on the right. | "Her savings have sat above a six-month buffer for half a year, so Kate suggests three safe options. Tap Why: the exact signals, the rule, ninety percent confidence, the legal basis. A glass box, not a black box." |
| 0:42 to 1:00 | Close the drawer. In **Vertel Kate wat eraan komt**, type `Ik wil €8.000 beschikbaar houden voor mijn verbouwing`, click **Vraag Kate**, then **Bevestig**. The idle-cash card drops from €13.700 to €5.700. | "Kate also listens. Lien says she needs eight thousand euros for her renovation. Kate turns it into a goal, Lien confirms, and the engine recalculates. The suggestion drops to five thousand seven hundred. Her intent, not our guess." |
| 1:00 to 1:08 | Scroll to the capital-gains tax card, click **Niet relevant**. The card disappears. | "Her portfolio is under the new exemption, so she taps Not relevant. The customer trains the engine." |
| 1:08 to 1:18 | Click the tab **Tijdlijn**. Scroll to November/December (pension-saving top-up) and May (holiday pay). | "Her life and Belgium's calendar on one timeline: pension saving before thirty-one December, holiday pay in May." |
| 1:18 to 1:25 | Click **Home**, click **Beluister** on the top card. Let it play about 4 seconds. | "Kate can speak Dutch, French or English, and always says first that she is an AI assistant." |
| 1:25 to 1:45 | Click **Afmelden**. Click **FR** in the header. Click **Marc**, paste the password, click **Ouvrir l'app**. Show the company-car card, scroll past Chloé turning 18 and the home insurance +8%. | "Marc, 47, Brussels, in French. His diesel company car loses its deductibility: fifty percent this year, none from 2028. High stakes, so no push: an adviser calls him." |
| 1:45 to 2:08 | Click **Se déconnecter**. Click **NL**. Click **Rita**, paste the password, click **Open de app**. Show the care-mode banner, the held-payment card, the energy card. | "Rita, 71, low digital comfort. The fraud engine held a nine hundred euro payment: the name did not match. Care mode switches on, no offers at all, and a colleague calls her back today." |
| 2:08 to 2:20 | Click **Afmelden**. Click the **Control room** card, paste the password, click **Open de app**. Show the KPI row, channel mix, world rules, decision log. | "This is KBC's view: every moment, every handoff to a human, every customer in care mode, and every decision in an append-only log." |
| 2:20 to 2:40 | Click **Drop in a new rule (JSON, validated server-side)**. Keep the prefilled example rule. Click **Run against all customers**. The result line shows "Affected N of 203 customers". | "Belgium announces a new measure. We drop it in as data, not code, and it runs against every customer in seconds. In production this is a nightly batch in BigQuery plus real-time triggers, for 2.3 million customers, hosted in Belgium." |
| 2:40 to 2:55 | Stay on the control room (or cut to a title card: "Kate Foresight · 404 Brain Not Found"). | "Not another feature: one decision layer every product and channel plugs into. Bank and insurer data in one engine. Explainable, consent-based, and human when it matters. Kate Foresight, by 404 Brain Not Found." |

Rehearse once with a timer. If you run long, cut the Tijdlijn step first, then the Beluister step. Restart `./run.sh` right before recording so goals and feedback start clean.

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
