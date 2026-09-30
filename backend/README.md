# Kate Foresight — backend

FastAPI moment engine for the KBC case: **two calendars** (the customer's life calendar,
option A, and the world's rulebook, option D) plus a protection layer (care mode, option C),
one arbitration engine, narration in NL/FR/EN, Kate voice notes, and a control room.

```
backend/
  api.py                    FastAPI app: /login, /me/*, /admin/*
  auth.py                   PBKDF2 demo password, JWT HS256 (8 h), role claims
  config.py                 env only (python-dotenv), demo clock (DEMO_TODAY)
  store.py                  in-memory feedback/deliveries/consents + append-only decision log
  data/generate.py          seeded synthetic Belgian dataset -> data/customers.json (203 customers)
  engine/models.py          Moment (Appendix A + source/category/facts), Customer, Consents
  engine/rules/*.py         one module per moment: detect(customer, today) -> list[Moment]
  engine/rules/rulebook.py  world rules (option D): declarative, pydantic-validated, no code execution
  engine/twin.py            digital twin: flat typed view of a customer for the rulebook
  engine/arbitrate.py       score, vulnerability guard, frequency cap, channel choice, decision log
  engine/narrate.py         Gemini (Developer API or Vertex) with deterministic template fallback
  engine/voice.py           ElevenLabs TTS with the AI disclosure line
  tests/                    pytest: security, rules, arbitration
```

## Run

```bash
cd backend
python3.11 -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then set JWT_SECRET and DEMO_PASSWORD (or use ../run.sh, which generates them)
python data/generate.py         # regenerates data/customers.json (deterministic, seed 20260930)
uvicorn api:app --reload        # http://localhost:8000
pytest -q                       # runs fully offline
```

Or from the repo root: `./run.sh` (creates the venv and `.env`, starts the API on :8000 and the
frontend on :5173).

Login: `POST /login {"customer_id": "lien" | "marc" | "rita" | "admin", "password": <DEMO_PASSWORD>}`.
One shared demo password is a deliberate demo simplification (a real deployment authenticates
through itsme / the KBC identity platform); it never appears in code, only in the git-ignored `.env`.

The engine clock is frozen with `DEMO_TODAY=2026-09-30` so the storyline is reproducible
(Marc's home policy renews in 42 days, Chloé turns 18 in 43 days, ...). Remove it to use the
real date; if you demo more than ~6 weeks later, regenerate the dataset with a new `TODAY` in
`data/generate.py` so salaries do not look as if they stopped.

## Routes

| Route | Auth | What |
|---|---|---|
| `POST /login` | rate limited 5/min | JWT with `sub` and `role` |
| `GET /me` | customer | profile (no transaction list) |
| `GET /me/moments` | customer | today's arbitrated, narrated moments + `care_mode` |
| `GET /me/timeline` | customer | next 12 months: calendar rules projected month by month + world rules |
| `POST /me/feedback` | customer | `{moment_type, action: not_now\|not_relevant\|never\|helpful}` |
| `GET/PUT /me/consents` | customer | `use_insurance_data`, `use_other_banks`, `marketing` (change which rules run) |
| `GET /me/voice/{moment_type}` | customer, rate limited | Kate voice note (mp3) or 404 |
| `GET /admin/overview` | admin | aggregates over all customers, decision log tail (ids only) |
| `GET/POST /admin/rules` | admin | world rulebook; POST adds a validated rule and reports the affected count |

## Enable Gemini narration

Without a key the narrator uses deterministic NL/FR/EN templates built from each moment's
structured `facts` (this is what the tests use). To switch on Gemini:

1. **Gemini Developer API** (preferred tonight): free key from aistudio.google.com with a personal
   account -> `GEMINI_API_KEY=...` in `backend/.env` (`GOOGLE_API_KEY` also works).
2. **Vertex AI**: `gcloud auth application-default login`, then `GCP_PROJECT=...`,
   `GCP_LOCATION=europe-west1` (the team's lab project denies all Vertex models, hence option 1).
3. `GEMINI_MODEL` defaults to `gemini-2.5-flash`.

`GET /health` shows which backend is active (`developer_api`, `vertex` or `template`).
Guardrails: the model only receives structured fields (type, window, evidence, facts, first name),
the system prompt (ACTION_PLAN.md Appendix B) forbids inventing numbers and tells it to ignore
instructions inside the data, and the output is validated (JSON shape, max 45 words, every number
in the message must already appear in the evidence). Any failure falls back to the template.

## Enable Kate's voice

`ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_NL`, `ELEVENLABS_VOICE_FR` (voice ids from the voice
library, search "Vlaams" / "nl-BE"), optional `ELEVENLABS_MODEL` (default `eleven_multilingual_v2`).
Every note starts with the AI disclosure line ("Ik ben Kate, de digitale assistent van KBC." /
"Je suis Kate, l'assistante digitale de KBC."), AI Act Art. 50. Audio is cached in memory per text.

## Security design (for the Aikido narrative)

- **No IDOR by construction**: the customer id comes from the JWT `sub` only. `/me/*` routes have
  no customer parameter in path, query or body; `tests/test_security.py` proves Lien's token can
  never read Marc's data.
- **Roles**: `role` claim (`customer` | `admin`); `/admin/*` requires `admin`, customer routes
  reject admin tokens; admin responses are aggregates with customer ids only.
- **Auth hygiene**: demo password from env, PBKDF2-hashed at startup with a random salt, verified
  with `hmac.compare_digest`; the hash is computed even for unknown users (no timing-based user
  enumeration); identical 401 for wrong password and unknown user. JWT HS256, `exp` 8 h, `iss`
  check, required claims. The app refuses to start without `DEMO_PASSWORD`, and without
  `JWT_SECRET` in production (dev generates a random one and warns).
- **Validation everywhere**: pydantic models on every input; feedback accepts only the enum;
  moment types and ids are regex-bound; world rules are declarative data (conditions + impact
  formula + text templates), never code; template rendering only substitutes whitelisted
  `{placeholders}` from a flat dict of primitives (no attribute access).
- **Rate limiting** (slowapi): `/login` 5/min, `/me/voice/*` 10/min.
- **Hygiene**: CORS restricted to `FRONTEND_ORIGIN`; security headers (nosniff, DENY framing,
  no-referrer, CSP `default-src 'none'`, no-store); no `/docs` or OpenAPI exposure; generic 500
  body; 422 bodies never echo the submitted input (could contain a password); pinned dependencies;
  no `eval`, no SQL, no shell.
- **LLM safety**: structured fields only, other customers' data never leaves the engine, numbers
  never come from the model, prompt-injection instruction in the system prompt, output validated.
- **Vulnerability guard**: a care-mode moment (income drop) drops every sales moment and routes to
  a human (AI Act Art. 5, CCD2 forbearance).
- **Audit**: every arbitration decision, feedback, consent change and rule addition is appended to
  an in-memory list and to `data/decision_log.jsonl` (git-ignored); the control room shows the tail.

## Data

`data/customers.json` is synthetic (seeded generator, 3 personas + 200 customers, 12 months of
transactions with Belgian payees: employer, landlord, Colruyt, NMBS/De Lijn/TEC, Doccle Engie/Luminus,
kinderopvang, notaris, Proximus/Telenet/VOO, KBC Pensioensparen, holiday pay in May, bonus in
December). No real person is represented. Figures used by the rules come only from
`ACTION_PLAN.md` section 3.

## Not finished / next

- Evidence strings are English (audit language); the narrated message and "Why?" are localized.
- Feedback, deliveries, consents and admin-added rules live in memory: a restart resets the demo.
- `use_other_banks` is stored and audited but no multibanking data exists in the dataset.
- Term-account maturity, energy-invoice spike and Guardian Angel moments (Rita's storyline) are in
  the data (Doccle invoices +30% since June) but not yet rules.
- ElevenLabs voice ids must be picked in the voice library; no Flemish voice is bundled.
