# Submission kit: Kate Foresight (404 Brain Not Found, KBC case)

Deadline: **23:00 CEST** on Builderbase. Target: submitted by 22:45. Nobody pushes after submission.

## (a) Builderbase project description (paste as is)

Kate Foresight turns KBC from a bank that reacts into one that sees what is coming. It reads two calendars KBC alone holds for every customer: their life (salary rhythm, holiday pay, insurance renewals, a child turning 18) and Belgium's rulebook (2026 capital-gains tax, insurance tax 9.6%, company-car deductibility). One decision layer ranks each moment by stakes, urgency, confidence and affinity, protects vulnerable customers (care mode drops all sales), caps frequency, and picks the channel: in-app card, Kate voice note, or a human advisor. Every card shows Why?, and customers correct it with Not now, Not relevant or Never. A control room covers 203 synthetic customers, human handoffs and an append-only decision log; a new government rule runs against all customers in seconds. FastAPI, NL/EN/FR, ElevenLabs voice, pluggable Gemini (numbers never from the LLM), JWT with no IDOR, scanned with Aikido.

## (b) Video script (target 2:55, hard limit 3:00)

Setup before recording: `./run.sh` running, browser at http://localhost:5173 on the login screen in **NL**, window around 1400 px wide, demo password copied to the clipboard, zoom 100%. If ElevenLabs keys are missing, the Listen step shows Kate's disclosure line as text; keep it in.

| Time | On screen (exact clicks) | Voice-over (English) |
|---|---|---|
| 0:00 to 0:15 | Login screen in NL, the four persona cards. No clicks. | "Every May, Belgian employees get holiday pay. Every December, the pension-saving deadline. And every year, Belgium changes the rules. Banks react to all of this. Kate Foresight sees it coming." |
| 0:15 to 0:25 | Click the **Lien** card, paste the password, click **Open de app**. | "KBC is a bank and an insurer, so it already holds two calendars: the customer's life and Belgium's rulebook. Meet Lien, 29, from Leuven." |
| 0:25 to 0:42 | On the idle-cash card, click **Waarom?**. The drawer opens on the right. | "Her savings have sat above a six-month buffer for half a year, so Kate suggests three safe options. Tap Why: the exact signals, the rule, ninety percent confidence, the legal basis. A glass box, not a black box." |
| 0:42 to 0:52 | Close the drawer. Scroll to the capital-gains tax card, click **Niet relevant**. The card disappears. | "Her portfolio sits under the new capital-gains exemption, so she taps Not relevant. The card is gone. The customer trains the engine." |
| 0:52 to 1:05 | Click the tab **Komende 12 maanden**. Scroll to December (pension-saving top-up) and May (holiday pay). | "Next twelve months: her life and Belgium's calendar on one timeline. Top up pension saving before thirty-one December. Holiday pay lands in May, and Kate will be ready." |
| 1:05 to 1:15 | Click the tab **Home**, click **Beluister** on the top card. Let the voice note play about 5 seconds. | "Kate can also speak, in Dutch or French. And she always says first that she is an AI assistant." |
| 1:15 to 1:40 | Click **Afmelden**. Click **FR** in the header. Click the **Marc** card, paste the password, click **Ouvrir l'app**. On the company-car card, click **Pourquoi ?**, then scroll past Chloé turning 18 and the home insurance +8% card. | "Marc, 47, Brussels, in French. His diesel company car is fifty percent deductible this year, twenty-five next year, zero from 2028. High stakes, so the engine does not push a product: an advisor calls him. Further down, his daughter turns eighteen and his home policy renews at plus eight percent, with two options." |
| 1:40 to 2:05 | Click **Se déconnecter**. Click **NL**. Click the **Rita** card, paste the password, click **Open de app**. Hover over the care-mode banner, then the held-payment card, then scroll to the energy card. | "Rita, 71, Kortrijk, low digital comfort. The fraud engine held a nine hundred euro payment: the name did not match the account holder. Care mode switches on. No offers at all. A colleague calls her back today, and Kate suggests Guardian Angel. Her energy bills are up twenty-six percent; that also goes through a person." |
| 2:05 to 2:20 | Click **Afmelden**. Click the **Control room** card, paste the password, click **Open de app**. Show the KPI row, channel mix, world rules, decision log. | "This is KBC's view. Two hundred and three customers, fifty-nine handoffs to a human, seven in care mode, and every decision in an append-only log." |
| 2:20 to 2:40 | Click **Drop in a new rule (JSON, validated server-side)**. Keep the prefilled example rule. Click **Run against all customers**. The result line shows "Affected N of 203 customers". | "Belgium announces a new measure. We drop it in as data, not code, and it runs against every customer in seconds. In production this is a nightly batch in BigQuery plus real-time triggers, for 2.3 million customers, hosted in Belgium." |
| 2:40 to 2:55 | Stay on the control room (or cut to a title card: "Kate Foresight · 404 Brain Not Found"). | "Not another feature: one decision layer every product and channel plugs into. Bank and insurer data no fintech has. Explainable, consent-based, and human when it matters. Kate Foresight, by 404 Brain Not Found." |

Rehearse once with a timer. If you run long, cut the Marc scroll (1:30 onward) first, then shorten the Rita line.

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
