# Kate Talk contract (30 Sep 2026, final hour)

Interaction pattern inspired by Revolut AIR (message, short answer, one inline chart, follow-up chips, composer with mic), in our own KBC design system (`design-system/kate-foresight/MASTER.md`). Deterministic intent routing + templates. No LLM required; numbers only from backend calculations. Demo clock = `config.today()` (2026-09-30).

## Files and owners
| File | Owner |
|---|---|
| `backend/talk_api.py`, `backend/engine/spending.py`, `backend/tests/test_talk.py` | data/intent agent |
| `backend/voice_api.py`, `backend/tests/test_voice.py`, `frontend/js/voice.js` | voice agent |
| `frontend/js/talk.js`, `frontend/js/i18n-talk.js` | conversation UI agent |
| `frontend/js/charts.js` (add only: `categoryBars`, `miniTimeline`) | chart agent |
| `frontend/js/main.js`, `backend/api.py`, `frontend/css/app.css` | integrator only |

## API (customer token only; customer id only from the token; `?lang=nl|en|fr`)
- `GET /me/talk/briefing` -> TalkResponse (intent `briefing`: 1-2 sentences from the priority moment + suggestions)
- `POST /me/talk {text: str (1..300), context?: {moment_type?: str, period_days?: 90}}` -> TalkResponse. Chat text never selects a customer.
- `POST /me/talk/goal/confirm {purpose, amount, keep_accessible}` -> reuse the goals store exactly like `POST /me/goals` (same validation, same cap) and return TalkResponse intent `goal_saved` with the recomputed allocation chart and the updated recommendation text.
- `GET /me/talk/voice-status` -> `{ stt: bool, tts: bool }` (voice agent)
- `POST /me/talk/transcribe` (multipart `audio`, <= 1 MB, <= 30 s, webm/ogg/mp4/wav/mpeg) -> `{ text, amount_candidates: [number] }` (voice agent)
- `POST /me/talk/speak {text}` -> audio/mpeg of a server-validated short answer (voice agent; only text produced by /me/talk in this session, max 400 chars)

TalkResponse:
```json
{ "intent": "spending|upcoming|goal_proposal|goal_saved|why|save_more|briefing|clarify",
  "message": "short answer, 1-3 sentences, localized",
  "as_of": "2026-09-30",
  "period": { "from": "2026-07-01", "to": "2026-09-30", "label": "1 jul – 30 sep 2026" } | null,
  "chart": null | { "kind": "category_bars", "unit": "eur", "rows": [{ "key": "groceries", "label": "Boodschappen", "value": 812.4 }], "total": 2210.0 }
           | { "kind": "allocation", "segments": [{ "key": "buffer|goal:<id>|remaining", "label": "...", "value": 12300 }], "total": 26000 }
           | { "kind": "timeline", "items": [{ "date": "2026-11-12", "kind": "deadline|reminder_window|expected_payment|renewal|effective_date|estimate", "title": "...", "basis": "contract|legal|estimate_from_history|customer_goal" }] },
  "facts": [{ "label": "Inkomsten", "value": 7800, "unit": "eur" }],
  "evidence": ["technical source lines, English ok"],
  "assumptions": ["localized assumption lines"],
  "proposal": null | { "purpose": "renovation", "amount": 8000, "keep_accessible": true, "summary": "Verbouwing · €8.000 · beschikbaar houden" },
  "suggestions": [{ "label": "Waarom raad je dit aan?", "text": "Waarom raad je dit aan?" }],
  "context": { "moment_type": "idle_cash", "period_days": 90 },
  "synthetic": true }
```
Spending semantics (from `transactions[].category`): income = salary, pension, bonus, holiday_pay, invoice_income, benefit; saving/investing (own products, not spending) = pension_saving; spending = everything else with amount < 0 (groceries, rent, mortgage, energy, telecom, transport, insurance, childcare, notary). Period "last three months" = the 3 full calendar months up to the demo date's month end (Jul, Aug, Sep 2026), stated exactly.
