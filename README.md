# Kate Foresight

**Team 404 Brain Not Found · Tectonic Hackathon 2026 · KBC case**

Belgian financial life runs on two calendars: your own (salary, holiday pay in May, the year-end bonus, insurance renewals, a lease ending, a child turning 18) and Belgium's (tax deadlines, new rules such as the 2026 capital-gains tax). KBC is a bank and an insurer, so it already holds both. Kate Foresight is a decision layer that reads both calendars for every customer, predicts the money moments that are about to happen, and delivers the right help at the right moment through the right channel: an in-app card, a Kate voice note, or a human advisor. Every message shows why it appears, and the customer can correct it. This repo is a working proof of concept: a rule engine, an arbitration engine, a customer app in NL/EN/FR, and a control room over 203 synthetic customers.

## The problem KBC asked

> "Imagine a future where KBC perfectly understands what customers need and responds at exactly the right moment... a vision and proof of concept for a scalable personalization approach for 2,300,000+ customers... not another feature."

KBC's five questions: which signals help us understand what customers need; how customers can be recognized by situation, behavior and intent; how experiences adapt automatically; how this works across products, services and channels; and how it creates meaningful impact for millions at the same time.

## Our answer: Kate Foresight

- **Explicit anticipation.** Kate already sends proactive suggestions in many situations. Foresight adds an explicit, calendar-based layer that looks at what is about to happen and explains why now: a pension-saving top-up before 31 December, holiday pay in May, a home policy renewing at +8%, a fossil company car losing its tax deductibility.
- **Two calendars.** The customer's life calendar (10 life-calendar and protection rules) and Belgium's rulebook (4 world rules: capital-gains tax 2026, insurance tax 9.6%, company-car deductibility 50/25/0%, Flemish renovation obligation within 6 years). World rules are declarative data, so a new government measure is a JSON file, not a code release.
- **Bank + insurer data.** Transactions, savings, investments, pension saving and insurance contracts in one view: a combination a bank-insurer holds and most pure payment apps do not.
- **Glass box.** Every card has a Why? drawer (signals, rule, confidence, legal basis, channel, human review). The customer answers Not now / Not relevant / Never / Helpful, and consents switch whole rule families off. The feed changes immediately.
- **Intent, stated by the customer.** Lien types "Ik wil €8.000 beschikbaar houden voor mijn verbouwing". Kate turns it into a goal proposal (renovation, €8,000, keep accessible), Lien confirms, and the engine recalculates: the idle-cash suggestion drops from €13,700 to €5,700 and Why? shows "€8,000 reserved for your renovation (your own goal)". The parser is deterministic; an LLM may only propose the parse, never an amount the customer did not type.
- **Talk to Kate (voice).** A Siri-style voice conversation (ElevenLabs agent) that only knows the moments the engine computed for this customer, so it cannot invent numbers. Setup: [docs/ELEVENLABS_AGENT.md](docs/ELEVENLABS_AGENT.md).
- **The engine chooses the channel, including a human.** High stakes or low digital comfort go to an advisor. A vulnerability guard (care mode) drops every sales message when a customer is under pressure.

## How the prototype answers KBC's five questions

| KBC question | How Kate Foresight answers it | Where to see it |
|---|---|---|
| 1. What signals help us understand what customers need? | Salary rhythm, holiday pay, year-end bonus, idle savings, Doccle energy invoices (+26%), insurance renewal dates and premiums, life dates (child turns 18, lease end), a payment held by the fraud engine, plus Belgium's rule changes. Feedback is a signal too. | Why? drawer on any card lists the exact signals |
| 2. How can customers be recognized by situation, behavior and intent? | A digital twin per customer: situation from the two calendars, behavior from transaction patterns and digital comfort (1 to 5), intent from goals the customer states in plain language, feedback and consents. Care mode recognizes vulnerability (held payment, income drop). | Lien vs Rita: same engine, different treatment |
| 3. How can experiences adapt automatically? | Arbitration ranks by stakes x urgency x confidence x affinity, applies a frequency cap (1 pushed moment per week unless high stakes), drops sales in care mode, and narrates in NL/EN/FR. Not relevant lowers weight, Never switches a moment off. | Click Not relevant, the card disappears |
| 4. How can it work across products, services and channels? | One decision layer over banking, savings, investing (Bolero), pension saving and insurance. The engine picks the channel: in-app card, Kate voice note, or advisor call. New products plug in as a rule module or a world rule. | Marc's company car goes to an advisor; Rita gets a callback |
| 5. How can you create impact for millions at the same time? | A new world rule runs against every customer twin in seconds and reports who is affected and by how much. The same rules run as a nightly batch plus real-time triggers. Frequency caps and feedback keep it helpful, not noisy. | Control room: paste a rule, click Run against all customers |

## Kate Talk (AIR-inspired conversation)

Tab **Praat met Kate** answers four supported question types from the customer's own data: where the money went (exact period, categories, income and pension saving kept separate), what is coming in the next 90 days (contract dates, legal dates and estimates labelled as such), "keep €8,000 for my renovation" (proposal with an editable amount and a non-mutating "What changes if you confirm?" preview, explicit **Apply this plan**, allocation and recommendation update, no money moves) and why Kate recommends something (evidence, current goals, assumptions). Deterministic intent routing and templates, not open conversation; every number comes from the backend. Push-to-talk (ElevenLabs speech-to-text and text-to-speech) appears only when `ELEVENLABS_API_KEY` and voice ids are set; it was tested with mocks, not against the live service.

| | |
|---|---|
| ![Spending](screenshots/talk-spending-1440.png) | ![Goal saved](screenshots/talk-goal-saved-1440.png) |

## What's new (latest demo build)

- **Kate Talk understands amounts in questions.** "Why is €5,700 available?" is answered as a why question, not turned into a goal; "Did I spend €100 on groceries?" gets an honest "I can't check a single payment, only category totals"; several ambiguous amounts lead to a clarifying question.
- **"What changes if you confirm?"** Before a goal is saved, Kate shows current vs proposed plan (savings, modeled buffer as an assumption, reserved, remaining), the recommendation before and after, and **Apply this plan** / **Keep my current plan**. The preview (`POST /me/talk/goal/preview`) stores nothing. Oversized goals show the shortfall separately; funded chart segments always add up to the savings.
- **Voice robustness.** The transcript is shown for review before sending, spoken answers do not overlap, and a voice failure keeps the text answer. Live ElevenLabs is not verified (tested with mocks, no key in the test environment).
- **Decision receipt in the control room.** Per customer: situation recognised, recommendation shown, suggestions withheld with the recorded reason (e.g. "Sales suggestions paused while we help"), items deferred by the frequency cap, channel, and advisor request status with its AR id.
- **Scoped answers.** Kate answers only about KBC products and your own data.

## Screenshots (current UI)

| | |
|---|---|
| ![Lien overview](screenshots/lien-overview-1440.png) | ![Why panel](screenshots/lien-why-1440.png) |
| Overview: one priority moment, why now, one action; savings allocation; upcoming. | Why?: plain reasons and dates first, technical evidence behind a disclosure. |
| ![Goal applied](screenshots/lien-plans-1440.png) | ![Adviser request](screenshots/marc-requested-1440.png) |
| My plans: "keep €8,000 for my renovation" splits the savings into buffer €12,300, goal €8,000, remaining €5,700. | Marc asks for an adviser: a prototype request (AR-…), no real call is placed. |
| ![Control room overview](screenshots/control-overview-1440.png) | ![Advisor queue](screenshots/control-queue-1440.png) |
| Control room: 4 defined metrics, moments by type (click to drill down), recommended channels. | Advisor queue: the customer's request with status requested → in review → resolved. |

Mobile: [overview](screenshots/lien-overview-390.png), [plans](screenshots/lien-plans-390.png). Other tabs: [moments](screenshots/control-moments-1440.png), [rule studio](screenshots/control-rules-1440.png), [trust & audit](screenshots/control-audit-1440.png). The previous UI is kept in `screenshots/before/` and runs at `/legacy.html`.

## Try it in 2 minutes

Requirements: Python 3.11+, a browser. No Node, no build step.

```bash
git clone https://github.com/heizeroliver/404-Brain-Not-Found.git
cd 404-Brain-Not-Found
./run.sh
```

`run.sh` creates `.venv`, installs `backend/requirements.lock`, writes `backend/.env` with a generated JWT secret and demo password (printed once, stored as `DEMO_PASSWORD`), then starts the API on :8000 and the app on :5173. Open **http://localhost:5173**, click a persona card, enter the demo password, click **Open de app**.

**Demo path (3 minutes, EN):** full recording script with click paths and fallbacks in [docs/DEMO_RUN.md](docs/DEMO_RUN.md). Restart `./run.sh` first (state is in memory), click **EN** in the header.
1. **lien** → **Timeline** (`#/customer/timeline`), 12 months: reminder windows, a legal deadline, a contract renewal and an estimated holiday pay, each labelled.
2. **Talk to Kate** (`#/customer/talk`): type `Keep €8,000 available for my renovation` → **What changes if you confirm?** (remaining €13,700 → €5,700, buffer €12,300 is a modeled assumption; the preview saves nothing) → **Apply this plan** → ask `Why do you recommend this?`.
3. **rita** → "We held a payment" → **Ask an adviser** → **Request contact**: a prototype request id (AR-…); no real adviser is contacted.
4. **admin** → **Advisor queue**: the same AR id → **Decision receipt** (also via **Moments** → search `rita` → Payment protection): what was recognised, shown, withheld and why, deferred, and the channel.
5. Optional: **Rule studio** → **Preview impact** (nothing is activated).

**Mijn gegevens / My data** toggles consents (insurance data, other banks, marketing) and the feed changes. Tests: `cd backend && ../.venv/bin/pytest -q` (fully offline). Manual setup, routes, Gemini and ElevenLabs configuration: [backend/README.md](backend/README.md).

## Architecture

```
 SIGNALS                     RULES                      ARBITRATION                OUTPUT              CHANNELS
 bank transactions  ---+                               consent filter
 insurance contracts   |--> life-calendar rules (10) ->vulnerability guard ------> narration --------> in-app card
 life dates, twin      |    world rulebook (4, JSON)   stakes x urgency x          NL/EN/FR templates  Kate voice note
 fraud engine events   |                               confidence x affinity       (LLM optional,      advisor call
 customer feedback  ---+                               frequency cap, channel      numbers never       (human handoff)
 Belgium's rules ------+                               choice, decision log        from the LLM)
                                                              ^                    ElevenLabs voice
                                                              |                    + AI disclosure
                                   feedback: Not now / Not relevant / Never / Helpful, consents
```

- **Backend**: FastAPI (`backend/api.py`), one module per rule in `backend/engine/rules/`, declarative world rules in `rulebook.py`, arbitration in `arbitrate.py`, narration in `narrate.py`, voice in `voice.py`, append-only decision log in `store.py`.
- **Frontend**: one file, `frontend/index.html`, with local `tailwind.css`. DOM built with `textContent` only.
- **Data**: seeded synthetic Belgian dataset, 3 personas plus 200 customers, 12 months of transactions.

### How this scales to 2.3M customers

**Measured:** rules + arbitration for 10,000 synthetic customers took 1.3 s on one process (4 vCPU container). This excludes data loading and validation, durable writes, network delivery and LLM calls, and ran without recording decisions. **Extrapolated, not load-tested:** about 5 minutes for 2.3M customers on one process. Command and table: [docs/BENCHMARK.md](docs/BENCHMARK.md).

- **Nightly batch in BigQuery.** Rules read a flat customer twin; world rules are conditions over twin fields, so they compile to SQL over 2.3M rows. The control room's "affected N customers in seconds" is the same operation at demo size.
- **Real-time triggers via Pub/Sub.** Salary lands, an invoice arrives, a payment is held: the event re-evaluates only that customer's rules and arbitration on Cloud Run. Arbitration is per customer and stateless, so it scales horizontally.
- **LLM only for phrasing.** Numbers, eligibility and channel come from the engine. The LLM (Gemini, pluggable) may rephrase; the output is validated (every number must already be in the evidence) and falls back to templates.
- **Frequency caps** (1 pushed moment per customer per week unless high stakes) keep 2.3M customers from being spammed.
- **Feedback loop.** Not relevant and Never adjust affinity per customer and per moment type; aggregate opt-outs per rule are visible in the control room so KBC can retire a rule that annoys people.
- **EU hosting** in Google Cloud europe-west1 (Belgium) for data residency; hosting location alone does not make a system compliant. The LLM, when used, receives structured fields for one customer only.
- **Today vs production:** the prototype keeps state in process memory and runs as one instance (a restart resets goals, feedback, requests and added rules). Production path (proposed, not built): Cloud Run for API and workers, Firestore or Cloud SQL for customer state and requests, Pub/Sub for event-driven re-evaluation with idempotent deliveries and shared frequency caps, and BigQuery or partitioned workers for cohort computation, with the control room reading precomputed aggregates.

## Security (Aikido)

Aikido scan results before and after our fixes:

`screenshots/aikido-before.png` and `screenshots/aikido-after.png` are added at submission.

- **No IDOR by construction**: JWT per persona; the customer id comes only from the token `sub`. `/me/*` routes take no customer id anywhere. Tests prove Lien's token cannot read Marc's data.
- **Roles**: `/admin/*` requires the admin role; customer routes reject admin tokens; admin responses are aggregates with ids only.
- **Input validation**: pydantic models with `extra="forbid"` on every input; feedback is an enum; world rules are declarative data, never code; templates substitute only whitelisted placeholders.
- **Auth hygiene**: PBKDF2-hashed demo password, constant-time compare, identical 401 for unknown user and wrong password, JWT with `exp` and `iss` checks.
- **Separate admin password**: customers can never log in as admin with the shared demo password; production refuses to start without it.
- **Abuse limits**: 64 KB request bodies, a global rate limit, capped rule schemas and template format specs, capped feedback and goals per customer.
- **Rate limits** on `/login` (5/min) and voice (10/min). Strict CORS to the frontend origin. Security headers (CSP `default-src 'none'`, nosniff, frame DENY, no-referrer, no-store). No `/docs` or OpenAPI exposed. Generic error bodies.
- **Secrets** only in git-ignored `backend/.env`; full pinned lockfile `backend/requirements.lock`. No `eval`, no SQL, no shell.

## EU by design

- **GDPR Art. 21 (right to object)**: Never and the consent toggles switch rule families off at once, including all marketing.
- **GDPR Art. 22 (automated decisions)**: the engine never takes a decision with legal or similar effect. High-stakes moments are routed to a human advisor, and Why? explains the logic.
- **AI Act Art. 50 (transparency)**: the customer app shows "AI-assistent · Kate"; every voice note starts with "Ik ben Kate, de digitale assistent van KBC."
- **CCD2 forbearance (applies from 20 November 2026)**: care mode detects pressure (held payment, income drop), drops every sales message and routes to a person first.
- **European Accessibility Act**: plain-language messages, 48 px touch targets, ARIA labels, a voice alternative, and a human channel for customers with low digital comfort.

## What is unfinished

- **Live Gemini narration** is built and pluggable (`GEMINI_API_KEY` or Vertex) but was blocked on the hackathon's Google Cloud lab project by org policy. The organisers confirmed Gemini is not available on the hackathon projects. The demo runs on deterministic NL/EN/FR templates; in production the language layer would use KBC's own model and only phrase text.
- **Real-time streaming (Pub/Sub) and the 2.3M BigQuery batch** are designed, not built. The demo evaluates 203 customers in memory.
- **Voice notes** need `ELEVENLABS_API_KEY` and voice ids in `backend/.env`; without them the Listen button shows a notice with the line Kate would say.
- **Data is synthetic.** No real customer is represented. Belgian figures come from public sources; the example rule in the control room is marked illustrative.
- **Admin UI is English only**; the customer app is NL/EN/FR. Evidence strings in Why? are English (audit language).
- **State is in memory**: feedback, consents, goals and added rules reset on restart. No advisor cockpit yet.
- **Cloud Run** deploy is scripted (`scripts/deploy_cloud_run.sh`, europe-west1); the demo video runs locally.

## Repo map

```
README.md                 this file
SUBMISSION.md             Builderbase description, video script, checklist, jury Q&A
run.sh                    one-command start (venv, .env, API :8000, app :5173)
Dockerfile                one container: API + app under /app (Cloud Run)
scripts/deploy_cloud_run.sh  deploy from Cloud Shell, secrets generated at deploy time
docs/BENCHMARK.md         measured engine throughput
ACTION_PLAN.md            plan, research notes and sources
CONCEPT_OPTIONS.md        the four concepts we weighed
screenshots/              UI screenshots (and Aikido before/after at submission)
frontend/
  index.html              single-file app: login, customer app (NL/EN/FR), control room
  tailwind.css            local CSS, no CDN
backend/
  api.py                  FastAPI routes: /login, /me/*, /admin/*
  auth.py                 PBKDF2 password, JWT, roles
  config.py               env config, demo clock (DEMO_TODAY=2026-09-30)
  store.py                feedback, consents, append-only decision log
  engine/rules/           one module per life-calendar or protection rule
  engine/rules/rulebook.py  world rules (declarative, validated)
  engine/twin.py          flat customer twin for the rulebook
  engine/arbitrate.py     scoring, vulnerability guard, frequency cap, channel choice
  engine/narrate.py       templates + optional Gemini with validation
  engine/voice.py         ElevenLabs voice with AI disclosure
  engine/intent.py        goal parser (NL/EN/FR), optional LLM, validated
  goals_api.py            /me/goals routes (token-scoped)
  scripts/benchmark.py    throughput benchmark
  data/generate.py        seeded synthetic dataset (203 customers)
  tests/                  67 pytest tests: security, rules, arbitration, language, goals
  requirements.lock       pinned dependencies
```

## Team

**404 Brain Not Found**, Tectonic Hackathon 2026, KBC case. Built in one evening.
