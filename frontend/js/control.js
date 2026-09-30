// Control room (admin). Owner: control-room agent. DOM via el()/textContent only.
import { state, t, api, el, clear, icon, fmtEur, fmtDate, openPanel, toast, navigate, registerStrings } from './core.js';
import { hBars, distribution } from './charts.js';
import strings from './i18n-control.js';

registerStrings(strings);

const TABS = ['overview', 'moments', 'queue', 'rules', 'audit'];
const lastQuery = {};           // per-tab query string, so filters persist when switching tabs
let header = null;              // cached { today, customers, at }
let renderSeq = 0;

// ---------------------------------------------------------------- helpers
function h(tag, cls, text, attrs) {
  const n = el(tag, cls || '', text == null ? undefined : String(text));
  if (attrs) for (const [k, v] of Object.entries(attrs)) if (v != null && v !== false) n.setAttribute(k, v === true ? '' : String(v));
  return n;
}
function add(parent, ...kids) { kids.flat().forEach((k) => k && parent.appendChild(k)); return parent; }
function has(key) { const v = t(key); return v !== key; }
function tt(key, fallback, ...args) { const v = t(key, ...args); return v === key ? (fallback ?? key) : v; }
export function typeLabel(k) { return tt('c_type_' + k, k); }
const srcLabel = (k) => tt('c_src_' + k, k);
const chLabel = (k) => (k == null ? '–' : tt('c_ch_' + k, k));
const reasonLabel = (k) => tt('c_reason_' + k, String(k).replace(/_/g, ' '));
const stLabel = (k) => tt('c_st_' + k, k);
const rqLabel = (k) => tt('c_rq_' + k, k);
function safeDate(v, style = 'medium') { if (!v) return '–'; try { return fmtDate(v, style); } catch { return String(v); } }
function fmtWindow(w) {
  if (!w) return '–';
  if (Array.isArray(w)) return w.filter(Boolean).map((d) => safeDate(d)).join(' – ') || '–';
  return String(w);
}
function get(params, k) { if (!params) return ''; try { return (typeof params.get === 'function' ? params.get(k) : params[k]) || ''; } catch { return ''; } }
function qs(obj) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(obj)) if (v !== '' && v != null && !(k === 'page' && String(v) === '1')) p.set(k, v);
  const s = p.toString();
  return s ? '?' + s : '';
}
function go(tab, obj) { const q = qs(obj || {}); lastQuery[tab] = q; navigate('#/control/' + tab + q); }
function num(v) { return typeof v === 'number' ? v.toLocaleString(state.lang === 'en' ? 'en-GB' : state.lang + '-BE') : String(v ?? '–'); }
function str(v) { if (v == null) return '–'; if (typeof v === 'object') return JSON.stringify(v); return String(v); }

function skeleton(lines = 4) {
  const w = h('div', 'stack-3', null, { 'aria-busy': 'true' });
  add(w, h('span', 'sr-only', t('c_loading')));
  for (let i = 0; i < lines; i++) { const s = h('div', 'skeleton'); s.style.height = i === 0 ? '96px' : '40px'; w.appendChild(s); }
  return w;
}
function errorBox(err, retry) {
  const b = h('div', 'card empty', null, { role: 'alert' });
  add(b, h('p', '', t('c_error') + (err && err.message ? ': ' + err.message : '')));
  const btn = h('button', 'btn btn-secondary btn-sm', t('c_retry'), { type: 'button' });
  btn.addEventListener('click', retry);
  return add(b, btn);
}
function empty(text) { return h('div', 'empty', text || t('c_empty')); }
async function load(slot, fetcher, draw) {
  clear(slot); slot.appendChild(skeleton());
  const seq = renderSeq;
  try {
    const data = await fetcher();
    if (seq !== renderSeq) return;
    clear(slot); draw(data);
  } catch (err) {
    if (seq !== renderSeq) return;
    clear(slot); slot.appendChild(errorBox(err, () => load(slot, fetcher, draw)));
  }
}
function table(cols, rows, { onRow, caption } = {}) {
  const wrap = h('div', 'table-wrap');
  wrap.style.overflowX = 'auto';
  const tb = h('table', 'table');
  if (caption) add(tb, h('caption', 'sr-only', caption));
  const tr = h('tr');
  cols.forEach((c) => tr.appendChild(h('th', '', c.label, { scope: 'col' })));
  add(tb, add(h('thead'), tr));
  const body = h('tbody');
  rows.forEach((r) => {
    const row = h('tr');
    cols.forEach((c) => {
      const td = h('td', c.num ? 'num' : '');
      const v = c.render(r);
      if (v instanceof Node) td.appendChild(v); else td.textContent = v == null ? '–' : String(v);
      row.appendChild(td);
    });
    if (onRow) {
      row.tabIndex = 0; row.style.cursor = 'pointer';
      row.addEventListener('click', () => onRow(r, row));
      row.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onRow(r, row); } });
    }
    body.appendChild(row);
  });
  add(tb, body);
  return add(wrap, tb);
}
function kvTable(obj, caption) {
  const rows = [];
  const walk = (o, prefix) => {
    for (const [k, v] of Object.entries(o || {})) {
      if (v && typeof v === 'object' && !Array.isArray(v)) walk(v, prefix + k + ' · ');
      else rows.push([prefix + k.replace(/_/g, ' '), v]);
    }
  };
  walk(obj, '');
  if (!rows.length) return empty();
  return table([{ label: t('c_col_key'), render: (r) => r[0] }, { label: t('c_col_value'), num: true, render: (r) => typeof r[1] === 'number' ? num(r[1]) : str(r[1]) }], rows, { caption });
}
function pager(page, pageSize, total, onPage) {
  const nav = h('nav', 'pager', null, { 'aria-label': 'Pagination' });
  const from = total ? (page - 1) * pageSize + 1 : 0;
  const to = Math.min(page * pageSize, total);
  const prev = h('button', 'btn btn-secondary btn-sm', t('c_prev'), { type: 'button' });
  const next = h('button', 'btn btn-secondary btn-sm', t('c_next'), { type: 'button' });
  prev.disabled = page <= 1; next.disabled = to >= total;
  prev.addEventListener('click', () => onPage(page - 1));
  next.addEventListener('click', () => onPage(page + 1));
  return add(nav, prev, h('span', 'num muted', t('c_pager', from, to, total), { 'aria-live': 'polite' }), next);
}
function select(label, name, value, options) {
  const f = fieldWrap();
  add(f, h('span', 'label', label));
  const s = h('select', 'field', null, { name });
  s.appendChild(h('option', '', t('c_all'), { value: '' }));
  options.forEach(([v, l]) => { const o = h('option', '', l, { value: v }); if (v === value) o.selected = true; s.appendChild(o); });
  f.appendChild(s);
  return [f, s];
}
function fieldWrap() {
  const f = h('label', 'ctl-field');
  Object.assign(f.style, { display: 'flex', flexDirection: 'column', gap: '4px', minWidth: '160px' });
  return f;
}
function card(title, ...kids) {
  const c = h('section', 'card stack-3');
  c.style.padding = '16px';
  if (title) c.appendChild(h('h2', 'section-title', title));
  return add(c, kids);
}
function row(gap = 12) { const r = h('div'); r.style.display = 'flex'; r.style.flexWrap = 'wrap'; r.style.gap = gap + 'px'; r.style.alignItems = 'flex-end'; return r; }
function grid(min) { const g = h('div'); g.style.display = 'grid'; g.style.gap = '16px'; g.style.gridTemplateColumns = `repeat(auto-fit, minmax(${min}px, 1fr))`; return g; }

// ---------------------------------------------------------------- entry
export function renderControl(root, tab, params) {
  renderSeq++;
  if (!TABS.includes(tab)) tab = 'overview';
  const q = !params ? '' : typeof params.get === 'function' ? params.toString() : new URLSearchParams(params).toString();
  lastQuery[tab] = q ? '?' + q : '';
  clear(root);
  const page = h('div', 'control stack-4');
  page.style.maxWidth = '1280px'; page.style.margin = '0 auto'; page.style.padding = '16px';
  const head = renderHeader(() => { header = null; renderControl(root, tab, params); });
  const tabs = renderTabs(tab);
  const panel = h('div', 'stack-4', null, { role: 'tabpanel', id: 'control-panel', 'aria-labelledby': 'ctab-' + tab, tabindex: '-1' });
  add(page, head, tabs, panel);
  root.appendChild(page);
  const views = { overview: viewOverview, moments: viewMoments, queue: viewQueue, rules: viewRules, audit: viewAudit };
  views[tab](panel, params);
}

function renderHeader(onRefresh) {
  const hd = h('header', 'control-head');
  Object.assign(hd.style, { display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '12px' });
  const left = h('div');
  add(left, h('h1', 'section-title', t('c_title')));
  const meta = h('p', 'muted');
  meta.style.margin = '0'; meta.style.fontSize = '14px';
  left.appendChild(meta);
  const fill = () => {
    meta.textContent = header
      ? [t('c_demo_date', safeDate(header.today, 'long')), t('c_cohort', header.customers ?? 203), t('c_refreshed', header.at)].join(' · ')
      : t('c_cohort', 203);
  };
  fill();
  if (!header) {
    api('/admin/v2/overview').then((d) => { setHeader(d); fill(); }).catch(() => {});
  }
  const btn = h('button', 'btn btn-secondary btn-sm', null, { type: 'button' });
  add(btn, icon('refresh', 16), h('span', '', ' ' + t('c_refresh')));
  btn.addEventListener('click', onRefresh);
  return add(hd, left, btn);
}
function setHeader(d) {
  const at = new Date(d.computed_at || Date.now());
  header = { today: d.today, customers: d.cohort && d.cohort.customers,
    at: isNaN(at) ? String(d.computed_at) : at.toLocaleTimeString(state.lang === 'en' ? 'en-GB' : state.lang + '-BE', { hour: '2-digit', minute: '2-digit' }) };
}

function renderTabs(active) {
  const list = h('div', 'tabs', null, { role: 'tablist', 'aria-label': t('c_tabs_label') });
  const btns = TABS.map((k) => {
    const b = h('button', 'tab', t('c_tab_' + k), { type: 'button', role: 'tab', id: 'ctab-' + k, 'aria-controls': 'control-panel', 'aria-selected': k === active ? 'true' : 'false', tabindex: k === active ? '0' : '-1' });
    b.addEventListener('click', () => { if (k !== active) navigate('#/control/' + k + (lastQuery[k] || '')); });
    return b;
  });
  list.addEventListener('keydown', (e) => {
    const i = btns.indexOf(document.activeElement);
    if (i < 0) return;
    let j = null;
    if (e.key === 'ArrowRight') j = (i + 1) % btns.length;
    else if (e.key === 'ArrowLeft') j = (i - 1 + btns.length) % btns.length;
    else if (e.key === 'Home') j = 0; else if (e.key === 'End') j = btns.length - 1;
    if (j == null) return;
    e.preventDefault(); btns[j].focus(); btns[j].click();
    setTimeout(() => { const n = document.getElementById('ctab-' + TABS[j]); if (n) n.focus(); }, 60);
  });
  return add(list, btns);
}

// ---------------------------------------------------------------- overview
function viewOverview(panel) {
  load(panel, () => api('/admin/v2/overview'), (d) => {
    setHeader(d);
    const tiles = grid(220);
    (d.metrics || []).forEach((m) => {
      const c = h('div', 'card metric');
      c.style.padding = '16px';
      add(c, h('div', 'metric-value num', num(m.value)),
        h('div', 'metric-label', tt('c_m_' + m.key, tt(m.label_key, m.key))),
        h('div', 'metric-def muted', tt('c_def_' + m.key, tt(m.definition_key, m.definition || ''))));
      tiles.appendChild(c);
    });
    const charts = grid(420);
    const byType = (d.moments_by_type || []).map((r) => ({ key: r.key, label: typeLabel(r.key), value: r.value }));
    const byCh = (d.channel_recommendations || []).map((r) => ({ key: r.key, label: chLabel(r.key), value: r.value }));
    add(charts,
      card(t('c_chart_types'), h('p', 'muted small', t('c_chart_types_hint')),
        byType.length ? hBars(byType, { label: t('c_chart_types'), unit: '', onSelect: (key) => go('moments', { type: typeof key === 'object' ? key.key : key }) }) : empty()),
      card(t('c_chart_channel'), byCh.length ? distribution(byCh, { label: t('c_chart_channel') }) : empty()));
    const att = h('ul', 'stack-2');
    att.style.listStyle = 'none'; att.style.padding = '0'; att.style.margin = '0';
    (d.attention || []).forEach((a) => {
      const kind = String(a.kind || '');
      let target = null, text;
      if (/request/.test(kind)) { target = () => go('queue', { status: 'requested' }); text = t('c_att_open_requests', a.count); }
      else if (/care/.test(kind)) { target = () => go('moments', { type: 'income_drop_care_mode' }); text = t('c_att_care_mode', a.count); }
      else if (/suppress/.test(kind)) { target = () => go('audit', {}); text = t('c_att_suppressed', a.count); }
      else text = tt(a.text_key, kind, a.count) + (has(a.text_key) ? '' : ': ' + a.count);
      const li = h('li');
      Object.assign(li.style, { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', borderTop: '1px solid var(--line, #E3E8EF)', paddingTop: '8px' });
      add(li, add(h('span'), icon('alert', 16), h('span', '', ' ' + text)));
      if (target) { const b = h('button', 'btn btn-quiet btn-sm', t('c_att_open'), { type: 'button' }); b.addEventListener('click', target); li.appendChild(b); }
      att.appendChild(li);
    });
    add(panel, tiles, charts, card(t('c_attention'), (d.attention || []).length ? att : empty()));
  });
}

// ---------------------------------------------------------------- moments
function viewMoments(panel, params) {
  const f = { q: get(params, 'q'), type: get(params, 'type'), source: get(params, 'source'), channel: get(params, 'channel'), status: get(params, 'status'), page: Number(get(params, 'page')) || 1 };
  const bar = row();
  const sf = fieldWrap();
  add(sf, h('span', 'label', t('c_search')));
  const si = h('input', 'field', null, { type: 'search', name: 'q', placeholder: t('c_search_ph'), value: f.q });
  si.value = f.q;
  sf.appendChild(si);
  const update = (patch) => go('moments', { ...f, ...patch, page: patch.page || 1 });
  si.addEventListener('keydown', (e) => { if (e.key === 'Enter') update({ q: si.value.trim() }); });
  si.addEventListener('change', () => { if (si.value.trim() !== f.q) update({ q: si.value.trim() }); });
  const [tf, ts] = select(t('c_f_type'), 'type', f.type, Object.keys(strings.en).filter((k) => k.startsWith('c_type_')).map((k) => [k.slice(7), typeLabel(k.slice(7))]));
  const [srf, srs] = select(t('c_f_source'), 'source', f.source, ['life_calendar', 'world_rule', 'protection'].map((k) => [k, srcLabel(k)]));
  const [cf, cs] = select(t('c_f_channel'), 'channel', f.channel, ['in_app_card', 'push', 'voice', 'advisor', 'letter'].map((k) => [k, chLabel(k)]));
  const [stf, sts] = select(t('c_f_status'), 'status', f.status, ['shown', 'queued', 'suppressed'].map((k) => [k, stLabel(k)]));
  ts.addEventListener('change', () => update({ type: ts.value }));
  srs.addEventListener('change', () => update({ source: srs.value }));
  cs.addEventListener('change', () => update({ channel: cs.value }));
  sts.addEventListener('change', () => update({ status: sts.value }));
  add(bar, sf, tf, srf, cf, stf);
  const slot = h('div', 'stack-3');
  add(panel, card(null, bar), slot);
  const p = { ...f, page_size: 25 };
  load(slot, () => api('/admin/v2/moments' + qs(p)), (d) => {
    const items = d.items || [];
    add(slot, h('p', 'num', t('c_results', num(d.total_moments ?? items.length), num(d.total_customers ?? 0)), { 'aria-live': 'polite' }));
    if (!items.length) { slot.appendChild(empty()); return; }
    slot.appendChild(table([
      { label: t('c_col_customer'), render: (r) => r.customer_name || r.customer_id },
      { label: t('c_col_moment'), render: (r) => typeLabel(r.type) },
      { label: t('c_col_source'), render: (r) => srcLabel(r.source) },
      { label: t('c_col_channel'), render: (r) => chLabel(r.channel) },
      { label: t('c_col_status'), render: (r) => h('span', 'tag ' + (r.status === 'suppressed' ? 'tag-warn' : r.status === 'shown' ? 'tag-ok' : 'tag-info'), stLabel(r.status)) },
      { label: t('c_col_window'), render: (r) => fmtWindow(r.window) },
    ], items, { caption: t('c_tab_moments'), onRow: (r) => openMoment(r) }));
    slot.appendChild(pager(d.page || f.page, d.page_size || 25, d.total_moments || 0, (pg) => update({ page: pg })));
  });
}
function openMoment(r) {
  const c = h('div', 'stack-3');
  const dl = h('dl');
  [[t('c_col_customer'), `${r.customer_name || ''} (${r.customer_id})`], [t('c_col_moment'), typeLabel(r.type)], [t('c_col_source'), srcLabel(r.source)],
    [t('c_stakes'), r.stakes], [t('c_col_channel'), chLabel(r.channel)], [t('c_delivery'), r.delivery], [t('c_col_status'), stLabel(r.status)], ...(r.reason ? [[t('c_col_reason'), reasonLabel(r.reason)]] : []), [t('c_col_window'), fmtWindow(r.window)]]
    .forEach(([k, v]) => add(dl, h('dt', 'label', k), h('dd', '', str(v))));
  add(c, dl, h('h3', 'section-title', t('c_evidence')));
  const ev = h('ul');
  (r.evidence || []).forEach((e) => ev.appendChild(h('li', '', str(e))));
  c.appendChild((r.evidence || []).length ? ev : empty());
  c.appendChild(h('h3', 'section-title', t('c_decision_path')));
  const ol = h('ol');
  (r.decision_path || []).forEach((s) => ol.appendChild(h('li', '', str(s))));
  c.appendChild((r.decision_path || []).length ? ol : empty());
  openPanel({ title: `${typeLabel(r.type)} · ${r.customer_name || r.customer_id}`, content: c });
}

// ---------------------------------------------------------------- queue
function viewQueue(panel, params) {
  const status = get(params, 'status');
  const chips = h('div', '', null, { role: 'group', 'aria-label': t('c_f_status') });
  Object.assign(chips.style, { display: 'flex', gap: '8px', flexWrap: 'wrap' });
  ['', 'requested', 'in_review', 'resolved'].forEach((s) => {
    const b = h('button', 'chip', rqLabel(s || 'all'), { type: 'button', 'aria-pressed': s === status ? 'true' : 'false' });
    b.addEventListener('click', () => go('queue', { status: s }));
    chips.appendChild(b);
  });
  const slot = h('div', 'stack-3');
  add(panel, chips, h('p', 'muted', t('c_queue_note')), slot);
  const fetcher = () => api('/admin/v2/advisor-requests' + qs({ status }));
  const draw = (d) => {
    const items = d.items || [];
    if (!items.length) { slot.appendChild(empty(t('c_queue_empty'))); return; }
    slot.appendChild(table([
      { label: t('c_col_id'), render: (r) => r.id },
      { label: t('c_col_customer'), render: (r) => r.customer_name || r.customer_id },
      { label: t('c_col_moment'), render: (r) => typeLabel(r.moment_type) },
      { label: t('c_col_reason'), render: (r) => r.reason || (typeof r.context === 'string' ? r.context : '–') },
      { label: t('c_col_created'), render: (r) => safeDate(r.created) },
      { label: t('c_col_status'), render: (r) => h('span', 'tag ' + (r.status === 'resolved' ? 'tag-ok' : r.status === 'in_review' ? 'tag-info' : 'tag-warn'), rqLabel(r.status)) },
      { label: t('c_col_actions'), render: (r) => {
        const w = row(8);
        const act = (label, to) => {
          const b = h('button', 'btn btn-secondary btn-sm', label, { type: 'button' });
          b.addEventListener('click', async () => {
            b.disabled = true;
            try {
              await api('/admin/v2/advisor-requests/' + encodeURIComponent(r.id), { method: 'PATCH', body: { status: to } });
              toast(t('c_status_updated') + ': ' + rqLabel(to), 'success');
              load(slot, fetcher, draw);
            } catch (err) { b.disabled = false; toast(err.message, 'error'); }
          });
          return b;
        };
        if (r.status === 'requested') w.appendChild(act(t('c_start_review'), 'in_review'));
        if (r.status !== 'resolved') w.appendChild(act(t('c_mark_resolved'), 'resolved'));
        return w;
      } },
    ], items, { caption: t('c_tab_queue') }));
  };
  load(slot, fetcher, draw);
}

// ---------------------------------------------------------------- rules
const LANGS = ['nl', 'en', 'fr'];
const DEFAULT_OPS = ['eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in', 'exists', 'missing', 'date_after', 'date_before'];
let rule = null, ruleMeta = null;

function pickList(...cands) {
  for (const c of cands) if (Array.isArray(c) && c.length) return c.map((x) => typeof x === 'string' ? [x, x] : [x.key || x.field || x.name || x.value || x.op, x.label || x.key || x.field || x.name || x.op]);
  return null;
}
function parseValue(s, op) {
  s = String(s).trim();
  if (op === 'exists' || op === 'missing' || s === '') return null;
  if (op === 'in') return s.split(',').map((x) => parseValue(x, 'eq'));
  if (s === 'true') return true; if (s === 'false') return false;
  if (/^-?\d+(\.\d+)?$/.test(s)) return Number(s);
  return s;
}
function showValue(v) { return v == null ? '' : Array.isArray(v) ? v.join(',') : String(v); }

function visibleFrom(eff) {
  const d = new Date(eff + 'T00:00:00Z');
  if (isNaN(d)) return eff;
  d.setUTCDate(d.getUTCDate() - 90);
  return d.toISOString().slice(0, 10);
}

function viewRules(panel) {
  const slot = h('div', 'stack-4');
  panel.appendChild(slot);
  load(slot, () => api('/admin/v2/rule-template'), (tpl) => {
    const base = tpl.rule || tpl.defaults || tpl.template || tpl.example || tpl;
    const meta = { ...tpl };
    const fields = pickList(tpl.allowed_fields, tpl.condition_fields, tpl.fields && tpl.fields.condition_fields, tpl.fields && tpl.fields.conditions && tpl.fields.conditions.fields, tpl.fields && tpl.fields.fields) || [];
    const ops = pickList(tpl.condition_ops, tpl.allowed_ops, tpl.ops, tpl.operators, tpl.fields && tpl.fields.ops, tpl.fields && tpl.fields.conditions && tpl.fields.conditions.ops) || DEFAULT_OPS.map((o) => [o, o]);
    if (!rule) {
      rule = JSON.parse(JSON.stringify(base));
      ['illustrative', 'note', 'form_fields', 'levels', 'stakes', 'impact_kinds', 'condition_ops', 'allowed_fields', 'allowed_ops', 'fields', 'ops', 'operators', 'condition_fields', 'rule', 'defaults', 'template', 'example'].forEach((k) => { if (base === tpl) delete rule[k]; });
      rule.title = rule.title || {}; rule.summary = rule.summary || {};
      rule.conditions = Array.isArray(rule.conditions) && rule.conditions.length ? rule.conditions : [{ field: (fields[0] || ['savings_balance'])[0], op: 'gt', value: 0 }];
    }
    (rule.conditions || []).forEach((c) => { if (c.field && !fields.find((f) => f[0] === c.field)) fields.push([c.field, c.field]); });
    ruleMeta = { fields, ops, illustrative: meta.illustrative !== false };
    drawRules(slot);
  });
}

function drawRules(slot) {
  clear(slot);
  const { fields, ops } = ruleMeta;
  const formBox = h('div', 'stack-3');
  const resultBox = h('div', 'stack-3', null, { 'aria-live': 'polite' });
  const jsonArea = h('textarea', '', null, { rows: '18', spellcheck: 'false', 'aria-label': t('c_advanced_json') });
  Object.assign(jsonArea.style, { width: '100%', fontFamily: 'ui-monospace, Menlo, Consolas, monospace', fontSize: '13px' });
  const jsonMsg = h('p', 'muted', '', { role: 'status' });
  const syncJson = () => { jsonArea.value = JSON.stringify(rule, null, 2); jsonMsg.textContent = ''; };

  const input = (label, value, onInput, attrs) => {
    const f = fieldWrap();
    add(f, h('span', 'label', label));
    const i = h('input', 'field', null, { type: 'text', ...(attrs || {}) });
    i.value = value ?? '';
    i.addEventListener('input', () => { onInput(i.value); if (details.open) syncJson(); });
    return add(f, i);
  };

  const drawForm = () => {
    clear(formBox);
    const r1 = grid(220);
    add(r1,
      input(t('c_rule_id'), rule.id, (v) => { rule.id = v.trim(); }),
      input(t('c_effective'), rule.effective_date, (v) => { rule.effective_date = v; }, { type: 'date' }),
      input(t('c_source_url'), rule.source_url, (v) => { if (v.trim()) rule.source_url = v.trim(); else delete rule.source_url; }, { type: 'url', placeholder: 'https://' }));
    const r2 = grid(260);
    LANGS.forEach((l) => r2.appendChild(input(t('c_rule_title', l.toUpperCase()), rule.title[l], (v) => { if (v) rule.title[l] = v; else delete rule.title[l]; })));
    const r3 = grid(260);
    LANGS.forEach((l) => r3.appendChild(input(t('c_rule_summary', l.toUpperCase()), rule.summary[l], (v) => { if (v) rule.summary[l] = v; else delete rule.summary[l]; })));
    const conds = h('fieldset', 'stack-2');
    Object.assign(conds.style, { border: '1px solid var(--line, #E3E8EF)', borderRadius: '10px', padding: '12px' });
    conds.appendChild(h('legend', 'label', t('c_conditions')));
    rule.conditions.forEach((c, i) => {
      const r = row(8);
      const mk = (label, opts, val, on) => {
        const f = fieldWrap(); add(f, h('span', 'label', label));
        const s = h('select', 'field');
        opts.forEach(([v, l]) => { const o = h('option', '', l, { value: v }); if (v === val) o.selected = true; s.appendChild(o); });
        s.addEventListener('change', () => { on(s.value); if (details.open) syncJson(); });
        return add(f, s);
      };
      add(r,
        mk(t('c_cond_field'), fields, c.field, (v) => { c.field = v; }),
        mk(t('c_cond_op'), ops, c.op, (v) => { c.op = v; c.value = parseValue(showValue(c.value), v); }),
        input(t('c_cond_value'), showValue(c.value), (v) => { c.value = parseValue(v, c.op); }));
      if (rule.conditions.length > 1) {
        const rm = h('button', 'btn btn-quiet btn-sm', t('c_remove'), { type: 'button' });
        rm.addEventListener('click', () => { rule.conditions.splice(i, 1); drawForm(); if (details.open) syncJson(); });
        r.appendChild(rm);
      }
      conds.appendChild(r);
    });
    const addC = h('button', 'btn btn-secondary btn-sm', t('c_add_cond'), { type: 'button' });
    addC.disabled = rule.conditions.length >= 12;
    addC.addEventListener('click', () => { rule.conditions.push({ field: (fields[0] || ['savings_balance'])[0], op: 'gt', value: 0 }); drawForm(); if (details.open) syncJson(); });
    conds.appendChild(addC);
    add(formBox, r1, r2, r3, conds);
  };

  const details = h('details', 'details');
  add(details, h('summary', '', t('c_advanced_json')), jsonArea, jsonMsg);
  details.addEventListener('toggle', () => { if (details.open) syncJson(); });
  jsonArea.addEventListener('input', () => {
    try {
      const parsed = JSON.parse(jsonArea.value);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('object expected');
      parsed.title = parsed.title || {}; parsed.summary = parsed.summary || {};
      parsed.conditions = Array.isArray(parsed.conditions) ? parsed.conditions : [];
      rule = parsed; jsonMsg.textContent = ''; drawForm();
    } catch (err) { jsonMsg.textContent = t('c_json_invalid') + ': ' + err.message; }
  });

  const previewBtn = h('button', 'btn btn-secondary', t('c_preview'), { type: 'button' });
  const activateBtn = h('button', 'btn btn-primary', t('c_activate'), { type: 'button' });
  previewBtn.addEventListener('click', async () => {
    previewBtn.disabled = true; clear(resultBox); resultBox.appendChild(skeleton(2));
    try {
      const d = await api('/admin/v2/rules/preview', { method: 'POST', body: { rule } });
      clear(resultBox);
      const c = card(null);
      add(c, h('p', 'tag tag-info', t('c_preview_only')), h('p', 'metric-value num', t('c_affected', num(d.affected), num(d.total))));
      if (d.total_impact != null) c.appendChild(h('p', 'num', t('c_total_impact') + ': ' + (typeof d.total_impact === 'number' ? fmtEur(d.total_impact) : str(d.total_impact))));
      if (d.visible_today === false) c.appendChild(h('p', 'muted', t('c_not_visible_today', safeDate(rule.visible_from || visibleFrom(rule.effective_date), 'long'))));
      if (d.changes_summary) {
        c.appendChild(h('h3', 'label', t('c_changes')));
        c.appendChild(typeof d.changes_summary === 'object' ? kvTable(d.changes_summary) : h('p', '', String(d.changes_summary)));
      }
      if (Array.isArray(d.sample) && d.sample.length) add(c, h('h3', 'label', t('c_sample')), h('p', 'num', d.sample.map(str).join(', ')));
      if (d.suppressed && Object.keys(d.suppressed).length) add(c, h('h3', 'label', t('c_suppressed')), kvTable(d.suppressed));
      resultBox.appendChild(c);
    } catch (err) { clear(resultBox); resultBox.appendChild(errorBox(err, () => previewBtn.click())); }
    previewBtn.disabled = false;
  });
  activateBtn.addEventListener('click', async () => {
    if (!window.confirm(t('c_confirm_activate'))) return;
    activateBtn.disabled = true;
    try {
      await api('/admin/v2/rules/activate', { method: 'POST', body: { rule } });
      toast(t('c_activated'), 'success');
      header = null;
    } catch (err) {
      if (err.status === 409 || /409|already/i.test(err.message || '')) toast(t('c_already_active'), 'info');
      else toast(err.message, 'error');
    }
    activateBtn.disabled = false;
  });
  const btns = row(8);
  add(btns, previewBtn, activateBtn);
  const top = row(8);
  add(top, h('span', 'tag tag-warn', t('c_illustrative')));
  add(slot, card(t('c_tab_rules'), top, formBox, btns), resultBox, card(null, details));
  drawForm();
}

// ---------------------------------------------------------------- audit
function viewAudit(panel, params) {
  const f = { q: get(params, 'q'), decision: get(params, 'decision'), page: Number(get(params, 'page')) || 1 };
  const slot = h('div', 'stack-4');
  panel.appendChild(slot);
  load(slot, () => api('/admin/v2/audit' + qs({ ...f, page_size: 25 })), (d) => {
    const top = grid(320);
    const all = d.suppressed_by_reason || [];
    const sup = all.filter((r) => r.key !== 'frequency_cap').map((r) => ({ key: r.key, label: reasonLabel(r.key), value: r.value }));
    const deferred = all.find((r) => r.key === 'frequency_cap');
    const supCard = card(t('c_suppressed_reason'), sup.length ? distribution(sup, { label: t('c_suppressed_reason') }) : empty());
    if (deferred) {
      const dv = h('div', 'stack-1');
      Object.assign(dv.style, { borderTop: '1px solid var(--line, #E3E8EF)', paddingTop: '12px' });
      add(dv, h('p', 'label', reasonLabel('frequency_cap') + ': ' + num(deferred.value)), h('p', 'muted', t('c_deferred_note')));
      supCard.appendChild(dv);
    }
    add(top, card(t('c_consents'), kvTable(d.consents, t('c_consents'))), card(t('c_feedback'), kvTable(d.feedback, t('c_feedback'))), supCard);
    const log = d.log || { items: [], total: 0, page: 1 };
    const items = log.items || [];
    const bar = row();
    const sf = fieldWrap(); add(sf, h('span', 'label', t('c_search')));
    const si = h('input', 'field', null, { type: 'search', name: 'q' }); si.value = f.q; sf.appendChild(si);
    const update = (patch) => go('audit', { ...f, ...patch, page: patch.page || 1 });
    si.addEventListener('keydown', (e) => { if (e.key === 'Enter') update({ q: si.value.trim() }); });
    si.addEventListener('change', () => { if (si.value.trim() !== f.q) update({ q: si.value.trim() }); });
    const decisions = [...new Set(items.map((i) => i.decision).filter(Boolean).concat(f.decision ? [f.decision] : []).concat(d.decisions || ['ranked', 'dropped']))];
    const [df, ds] = select(t('c_decision'), 'decision', f.decision, decisions.map((x) => [x, String(x).replace(/_/g, ' ')]));
    ds.addEventListener('change', () => update({ decision: ds.value }));
    add(bar, sf, df);
    const logCard = card(t('c_decision_log'), bar);
    if (!items.length) logCard.appendChild(empty());
    else {
      const pick = (r, ...ks) => { for (const k of ks) if (r[k] != null) return r[k]; return null; };
      logCard.appendChild(table([
        { label: t('c_col_time'), render: (r) => { const v = pick(r, 'ts', 'time', 'at', 'timestamp', 'created'); return v ? safeDate(v, 'medium') : '–'; } },
        { label: t('c_col_customer'), render: (r) => pick(r, 'customer_name', 'customer_id', 'actor') || '–' },
        { label: t('c_col_moment'), render: (r) => { const v = pick(r, 'moment_type', 'type', 'rule_id', 'event'); return v ? typeLabel(v) : '–'; } },
        { label: t('c_col_decision'), render: (r) => pick(r, 'decision', 'action') || '–' },
        { label: t('c_col_detail'), render: (r) => str(pick(r, 'detail', 'reason', 'details', 'note')) },
      ], items, { caption: t('c_decision_log') }));
      logCard.appendChild(pager(log.page || f.page, log.page_size || 25, log.total || items.length, (pg) => update({ page: pg })));
    }
    add(slot, top, logCard);
  });
}
