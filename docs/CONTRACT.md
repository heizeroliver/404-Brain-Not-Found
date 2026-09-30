# Redesign contract (single source of truth for all agents, 30 Sep 2026)

Design rules: `design-system/kate-foresight/MASTER.md` (read the override block first) and `pages/customer.md`, `pages/control-room.md`.
Old UI stays at `frontend/legacy.html` (fallback, do not edit). New UI: `frontend/index.html` + ES modules in `frontend/js/` + `frontend/css/app.css`.
Security rules: DOM built with `el()`/`textContent` only, never `innerHTML` with data. All API calls through `api()`. No new external scripts except the existing ElevenLabs widget.

## Frontend files and owners (one owner per file)
| File | Owner | Exports |
|---|---|---|
| `frontend/index.html` | design-system agent | shell: `<header id="app-header">`, `<main id="app">`, `<div id="panel-root">`, `<div id="toast-root">`; loads `css/app.css`, `tailwind.css` (optional), `<script type="module" src="js/main.js">` |
| `frontend/css/app.css` | design-system agent | tokens + component classes below |
| `frontend/js/core.js` | design-system agent | see Core API |
| `frontend/js/main.js` | design-system agent | login screen, header (brand, prototype label, NL/EN/FR switch, logout), hash router, calls `renderCustomer` / `renderControl` |
| `frontend/js/charts.js` | design-system agent | see Charts API |
| `frontend/js/customer.js` | customer agent | `export function renderCustomer(root, section)`; `section` in `overview|timeline|plans|data` |
| `frontend/js/control.js` | control-room agent | `export function renderControl(root, tab, params)`; `tab` in `overview|moments|queue|rules|audit` |
| `frontend/js/i18n-customer.js`, `frontend/js/i18n-control.js` | customer / control agent | `export default { nl: {...}, en: {...}, fr: {...} }` merged by core via `registerStrings` |

## Core API (`frontend/js/core.js`)
```js
export const state;            // { token, role: "customer"|"admin"|null, profile, lang: "nl"|"en"|"fr" }
export function registerStrings(dict)        // merge { nl:{}, en:{}, fr:{} }
export function t(key, ...args)              // function values are called with args; falls back en -> key
export async function api(path, { method, body } = {})  // JSON in/out, adds Bearer token and ?lang when opts.lang true; throws Error(detail); 401 -> logout
export function el(tag, className?, text?)   // text via textContent
export function clear(node)
export function icon(name, size = 20)        // SVG element from a static set: home, calendar, target, shield, info, close, chevron, check, user, phone, search, filter, refresh, alert, arrow-right, play, mic
export function fmtEur(n)                    // locale-aware, NL/FR "€ 1.234" style per Intl nl-BE / fr-BE / en-GB, no decimals
export function fmtDate(iso, style = "long") // Intl date in current language
export function openPanel({ title, content, onClose })  // right side panel (desktop) / full-screen dialog (<768px); role="dialog" aria-modal, focus trap, Esc, returns focus to the opener; returns { close, setContent }
export function toast(message, kind = "info") // role="status"
export function navigate(hash)               // e.g. "#/customer/overview", "#/control/moments?type=idle_cash"
export function onLanguageChange(fn)
```
## CSS component classes (`frontend/css/app.css`)
`.btn .btn-primary .btn-secondary .btn-quiet .btn-sm`, `.card`, `.section-title`, `.eyebrow`, `.muted`, `.num` (tabular-nums), `.field`, `.label`, `.chip` (filter chip, `aria-pressed`), `.tag` (small status text: `.tag-warn .tag-ok .tag-info`), `.tabs` + `.tab[aria-selected=true]`, `.table`, `.pager`, `.metric` (`.metric-value`, `.metric-label`, `.metric-def`), `.empty`, `.skeleton`, `.sr-only`, `.layout-2col` (2/3 + 1/3, stacks < 1024px), `.stack-*` spacing helpers, `.details` (styled `<details>`).

## Charts API (`frontend/js/charts.js`), accessible SVG, no library
```js
export function allocationBar(segments, { label })    // segments: [{ key, label, value, color?, pattern? }]; one horizontal stacked bar + legend table with amounts; zero/negative values never drawn negative
export function hBars(rows, { label, unit, onSelect }) // rows: [{ key, label, value }]; direct value labels; bars are <button>s when onSelect given (keyboard + click); returns element
export function distribution(rows, { label })         // rows: [{ key, label, value }]; horizontal bars with count and % of total, total shown
```
Each chart: `<figure>` with `<figcaption>`, `role="img"` + aria-label summary on the SVG, and a visually hidden `<table>` with the same numbers.

## Backend API (all new routes; existing routes stay compatible)
Customer (`backend/customer_api.py`, customer token only, customer id only from the token, `?lang=nl|en|fr`):
- `GET /me/overview` -> `{ today, care_mode, priority: Moment|null, others: [Moment], upcoming: [TimelineItem] (next 90 days, max 5), allocation: Allocation, goals: [Goal], advisor_requests: [Request] }`
- `GET /me/timeline2?days=90|365` -> `{ today, days, items: [TimelineItem], next_after_horizon: TimelineItem|null }`
- `POST /me/advisor-requests {moment_type, note?}` -> 201 new or 200 existing open `{ request, created }`; 404 if the moment is not in the customer's current feed; 429 above cap
- `GET /me/advisor-requests` -> `{ items: [Request] }`

`Moment` = `{ type, title, message, why_reasons: [str], why, source: life_calendar|world_rule|protection, category, stakes, channel, delivery: now|queued, window: [start, end], date_label_kind, confidence: float|null, human_review_required: bool, legal_basis_label, evidence: [str] (technical), action: { kind: advisor_request|open_timeline|open_plans|open_data|none, label }, requested: Request|null }`
`TimelineItem` = `{ date, end, kind: reminder_window|deadline|expected_payment|effective_date|renewal, type, title, source, channel, human_review_required: bool|null, confidence: float|null }` (null when unknown; never placeholders)
`Allocation` = `{ savings, buffer, buffer_months, net_monthly_income, reserved: [{goal_id, purpose, amount}], reserved_total, reserved_covered, shortfall, remaining, assumption }` where `reserved_covered = min(reserved_total, max(savings - buffer, 0))`, `remaining = max(savings - buffer - reserved_total, 0)`, `shortfall = max(reserved_total - max(savings - buffer, 0), 0)`. Must equal the numbers the idle_cash rule uses.
`Request` = `{ id, moment_type, status: requested|in_review|resolved, created, updated, reason }`

Control room (`backend/control_api.py`, admin token only):
- `GET /admin/v2/overview` -> `{ today, cohort: {customers}, metrics: [{key, label_key, value, definition_key}], moments_by_type: [{key, value}], channel_recommendations: [{key, value}], attention: [{kind, text_key, count}], computed_at }` metrics keys: `customers_with_moment` (customers), `moments_total` (moments), `advisor_routing_recommended` (moments whose recommended channel is advisor), `advisor_requests_open` (requests)
- `GET /admin/v2/moments?type=&source=&channel=&status=&q=&page=1&page_size=25` -> `{ total_moments, total_customers, page, page_size, items: [{ customer_id, customer_name, type, source, stakes, channel, delivery, status: shown|queued|suppressed, window, evidence, decision_path: [str] }] }`
- `GET /admin/v2/advisor-requests?status=` -> `{ items: [Request + customer_id, customer_name, context] }`; `PATCH /admin/v2/advisor-requests/{id} {status}` -> Request (logged)
- `GET /admin/v2/rule-template` -> one illustrative template (form fields + defaults, `illustrative: true`)
- `POST /admin/v2/rules/preview {rule}` -> `{ affected, total, sample: [ids], changes_summary, suppressed: {reason: count} }` (never mutates the rulebook)
- `POST /admin/v2/rules/activate {rule}` -> 201 (logged; same validation as `POST /admin/rules`)
- `GET /admin/v2/audit?q=&decision=&page=&page_size=` -> `{ consents: {...}, feedback: {...}, suppressed_by_reason: [{key, value}], log: { total, page, items } }`
