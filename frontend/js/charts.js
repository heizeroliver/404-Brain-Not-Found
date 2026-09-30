// Accessible SVG charts, no library. Built with createElementNS and textContent only.
import { el, t, fmtEur, fmtNum, fmtDate, registerStrings } from "./core.js";

const NS = "http://www.w3.org/2000/svg";
let uid = 0;
function s(tag, attrs = {}, text) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null) n.setAttribute(k, String(v));
  if (text !== undefined && text !== null) n.textContent = String(text);
  return n;
}
const safe = (v) => { const n = Number(v); return Number.isFinite(n) && n > 0 ? n : 0; };
const raw = (v) => { const n = Number(v); return Number.isFinite(n) ? n : 0; };
const PALETTE = ["#0B325E", "#00709C", "#00ACEF", "#475569", "#94A3B8", "#9FB7CC", "#1E5A8C"];

function fmtValue(v, unit) {
  if (unit === "eur" || unit === "€") return fmtEur(v);
  return fmtNum(v) + (unit && unit !== "count" ? " " + unit : "");
}
function isDark(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || ""));
  if (!m) return true;
  const n = parseInt(m[1], 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 140;
}
function pct(v, total) { return total > 0 ? Math.round((v / total) * 100) : 0; }

function figure(label) {
  const fig = el("figure", "chart");
  if (label) fig.appendChild(el("figcaption", null, label));
  return fig;
}
function hiddenTable(label, headers, rows) {
  const tbl = el("table", "sr-only");
  if (label) tbl.appendChild(el("caption", null, label));
  const thead = el("thead"); const tr = el("tr");
  headers.forEach((h) => { const th = el("th", null, h); th.scope = "col"; tr.appendChild(th); });
  thead.appendChild(tr); tbl.appendChild(thead);
  const tb = el("tbody");
  rows.forEach((r) => { const row = el("tr"); r.forEach((c, i) => { const cell = el(i === 0 ? "th" : "td", null, c); if (i === 0) cell.scope = "row"; row.appendChild(cell); }); tb.appendChild(row); });
  tbl.appendChild(tb);
  return tbl;
}
function svgRoot(width, height, summary) {
  const svg = s("svg", { viewBox: `0 0 ${width} ${height}`, width: "100%", preserveAspectRatio: "xMinYMin meet", role: "img", "aria-label": summary });
  svg.appendChild(s("title", {}, summary));
  return svg;
}
function hatchDefs(svg, id, color) {
  const defs = s("defs");
  const p = s("pattern", { id, width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" });
  p.appendChild(s("rect", { width: 6, height: 6, fill: "#fff" }));
  p.appendChild(s("rect", { width: 3, height: 6, fill: color }));
  defs.appendChild(p); svg.appendChild(defs);
}

// ------------------------------------------------------------------ allocationBar
// segments: [{ key, label, value, color?, pattern? ("hatch") }]
export function allocationBar(segments = [], { label, unit = "eur" } = {}) {
  const segs = segments.map((sg, i) => ({ ...sg, v: safe(sg.value), color: sg.color || PALETTE[i % PALETTE.length] }));
  const total = segs.reduce((a, b) => a + b.v, 0);
  const fig = figure(label);
  const W = 600, H = 32, barY = 0, barH = 32;
  const summary = (label ? label + ": " : "") + segs.map((sg) => `${sg.label} ${fmtValue(sg.v, unit)}`).join(", ") + `. ${t("chart_total")} ${fmtValue(total, unit)}.`;
  const svg = svgRoot(W, H, summary);
  const hid = "hatch-" + (++uid);
  hatchDefs(svg, hid, "#9FB7CC");
  svg.appendChild(s("rect", { x: 0, y: barY, width: W, height: barH, rx: 6, fill: "#EEF2F6" }));
  let x = 0;
  const labels = el("div", "alloc-labels");
  const drawn = segs.filter((sg) => sg.v > 0);
  drawn.forEach((sg, i) => {
    const w = total > 0 ? Math.max((sg.v / total) * W, 0) : 0;
    if (w <= 0) return;
    const fill = sg.pattern === "hatch" || sg.key === "remaining" ? `url(#${hid})` : sg.color;
    const r = s("rect", { x: x.toFixed(2), y: barY, width: w.toFixed(2), height: barH, fill, stroke: "#fff", "stroke-width": i < drawn.length - 1 ? 2 : 0 });
    r.appendChild(s("title", {}, `${sg.label}: ${fmtValue(sg.v, unit)} (${pct(sg.v, total)}%)`));
    svg.appendChild(r);
    // direct label inside segment when wide enough
    const text = `${pct(sg.v, total)}%`;
    const lab = el("span", "alloc-label num", text);
    lab.style.width = ((w / W) * 100).toFixed(3) + "%";
    lab.setAttribute("aria-hidden", "true");
    labels.appendChild(lab);
    x += w;
  });
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("height", String(H));
  svg.classList.add("alloc-svg");
  fig.append(labels, svg);

  // legend table (visible) with amounts
  const tbl = el("table", "legend-table");
  const tb = el("tbody");
  segs.forEach((sg) => {
    const tr = el("tr");
    const td1 = el("td");
    const sw = el("span", "swatch" + (sg.pattern === "hatch" || sg.key === "remaining" ? " swatch-hatch" : ""));
    if (!(sg.pattern === "hatch" || sg.key === "remaining")) sw.style.background = sg.color;
    sw.setAttribute("aria-hidden", "true");
    td1.append(sw, document.createTextNode(sg.label));
    const td2 = el("td", "num", fmtValue(sg.v, unit));
    tr.append(td1, td2); tb.appendChild(tr);
  });
  const trT = el("tr", "total");
  trT.append(el("td", null, t("chart_total")), el("td", "num", fmtValue(total, unit)));
  tb.appendChild(trT);
  tbl.appendChild(tb);
  fig.appendChild(tbl);
  return fig;
}

// ------------------------------------------------------------------ hBars
// rows: [{ key, label, value }]; onSelect(key, row) makes each bar keyboard focusable
export function hBars(rows = [], { label, unit, onSelect, selected } = {}) {
  return barChart(rows, { label, unit, onSelect, selected, showPct: false });
}

// ------------------------------------------------------------------ distribution
export function distribution(rows = [], { label, unit, onSelect, selected } = {}) {
  return barChart(rows, { label, unit, onSelect, selected, showPct: true });
}

function barChart(rows, { label, unit, onSelect, selected, showPct }) {
  const data = rows.map((r) => ({ ...r, v: safe(r.value), shown: raw(r.value) }));
  const total = data.reduce((a, b) => a + b.v, 0);
  const max = Math.max(...data.map((d) => d.v), 0);
  const fig = figure(label);
  const W = 600, rowH = 36, gap = 8, labelW = 190, valueW = showPct ? 110 : 80;
  const barMax = W - labelW - valueW - 12;
  const H = Math.max(data.length * (rowH + gap), rowH);
  const summary = (label ? label + ": " : "") + (data.length ? data.map((d) => `${d.label} ${fmtValue(d.v, unit)}${showPct ? ` (${pct(d.v, total)}%)` : ""}`).join(", ") : "0") + (showPct ? `. ${t("chart_total")} ${fmtValue(total, unit)}.` : ".");
  const svg = svgRoot(W, H, summary);
  svg.style.maxWidth = W + "px";
  if (onSelect) svg.setAttribute("role", "group"), svg.setAttribute("aria-label", summary);

  data.forEach((d, i) => {
    const y = i * (rowH + gap);
    const w = max > 0 ? Math.max((d.v / max) * barMax, 0) : 0;
    const g = s("g");
    const lab = d.label.length > 26 ? d.label.slice(0, 25) + "…" : d.label;
    g.appendChild(s("text", { x: 0, y: y + rowH / 2 + 5, "font-size": 14, fill: "#0F1B2D" }, lab));
    g.appendChild(s("rect", { x: labelW, y: y + 6, width: barMax, height: rowH - 12, rx: 4, fill: "#F1F5F9" }));
    const bar = s("rect", { class: "bar-focus", x: labelW, y: y + 6, width: Math.max(w, d.v > 0 ? 2 : 0).toFixed(2), height: rowH - 12, rx: 4, fill: "#0B325E" });
    g.appendChild(bar);
    const valTxt = fmtValue(d.v, unit) + (showPct ? ` · ${pct(d.v, total)}%` : "");
    g.appendChild(s("text", { x: W - 4, y: y + rowH / 2 + 5, "text-anchor": "end", "font-size": 14, "font-weight": 600, fill: "#0F1B2D" }, valTxt));
    const tip = s("title", {}, `${d.label}: ${valTxt}`);
    g.appendChild(tip);
    if (onSelect) {
      g.setAttribute("class", "bar-hit");
      g.setAttribute("role", "button");
      g.setAttribute("tabindex", "0");
      g.setAttribute("aria-label", `${d.label}: ${valTxt}`);
      if (selected !== undefined) g.setAttribute("aria-pressed", String(selected === d.key));
      // full-row hit area
      g.insertBefore(s("rect", { x: 0, y, width: W, height: rowH, fill: "transparent" }), g.firstChild);
      const fire = () => onSelect(d.key, d);
      g.addEventListener("click", fire);
      g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fire(); } });
    }
    svg.appendChild(g);
  });
  fig.appendChild(svg);
  if (showPct) fig.appendChild(el("p", "chart-total num", `${t("chart_total")}: ${fmtValue(total, unit)}`));
  const headers = showPct ? [t("chart_item"), t("chart_value"), t("chart_share")] : [t("chart_item"), t("chart_value")];
  fig.appendChild(hiddenTable(label, headers, data.map((d) => showPct ? [d.label, fmtValue(d.v, unit), pct(d.v, total) + "%"] : [d.label, fmtValue(d.v, unit)])));
  return fig;
}

// ------------------------------------------------------------------ talk charts (categoryBars, miniTimeline)
registerStrings({
  nl: { chart_largest: "grootste categorie", chart_date: "Datum", chart_kind: "Soort", chart_basis: "Basis", chart_title: "Omschrijving", chart_empty: "Geen gegevens.",
    tk_expected_payment: "Verwachte betaling", tk_estimate: "Schatting", tk_deadline: "Deadline", tk_renewal: "Verlenging", tk_effective_date: "Ingangsdatum", tk_reminder_window: "Herinneringsperiode" },
  en: { chart_largest: "largest category", chart_date: "Date", chart_kind: "Kind", chart_basis: "Basis", chart_title: "Description", chart_empty: "No data.",
    tk_expected_payment: "Expected payment", tk_estimate: "Estimate", tk_deadline: "Deadline", tk_renewal: "Renewal", tk_effective_date: "Effective date", tk_reminder_window: "Reminder window" },
  fr: { chart_largest: "plus grande catégorie", chart_date: "Date", chart_kind: "Type", chart_basis: "Base", chart_title: "Description", chart_empty: "Aucune donnée.",
    tk_expected_payment: "Paiement attendu", tk_estimate: "Estimation", tk_deadline: "Échéance", tk_renewal: "Renouvellement", tk_effective_date: "Date d'effet", tk_reminder_window: "Période de rappel" },
});

// rows: [{ key, label, value }] drawn in the given order; total defaults to the sum of rows.
export function categoryBars(rows = [], { label, total, unit = "eur" } = {}) {
  const data = (rows || []).map((r) => ({ ...r, label: String(r.label ?? r.key ?? ""), v: safe(r.value) }));
  const sum = data.reduce((a, b) => a + b.v, 0);
  const tot = Number.isFinite(Number(total)) && Number(total) > 0 ? Number(total) : sum;
  const max = Math.max(...data.map((d) => d.v), 0);
  const topIdx = data.reduce((best, d, i) => (d.v > (best < 0 ? -1 : data[best].v) ? i : best), -1);
  const fig = figure(label);
  fig.classList.add("chart-category");
  const top = topIdx >= 0 ? data[topIdx] : null;
  const summary = (label ? label + ": " : "") + `${t("chart_total").toLowerCase()} ${fmtValue(tot, unit)}` +
    (top && top.v > 0 ? `; ${t("chart_largest")} ${top.label} ${fmtValue(top.v, unit)} (${pct(top.v, tot)}%)` : "");
  const W = 600, rowH = 30, gap = 6, labelW = 170, valueW = 130;
  const barMax = W - labelW - valueW - 12;
  const nRows = data.length + 1; // + total row
  const H = nRows * (rowH + gap);
  const svg = svgRoot(W, H, summary);
  svg.style.maxWidth = "100%";
  data.forEach((d, i) => {
    const y = i * (rowH + gap);
    const w = max > 0 ? (d.v / max) * barMax : 0;
    const g = s("g");
    const lab = d.label.length > 24 ? d.label.slice(0, 23) + "…" : d.label;
    g.appendChild(s("text", { x: 0, y: y + rowH / 2 + 5, "font-size": 14, fill: "#0F1B2D" }, lab));
    g.appendChild(s("rect", { x: labelW, y: y + 5, width: barMax, height: rowH - 10, rx: 4, fill: "#F1F5F9" }));
    g.appendChild(s("rect", { x: labelW, y: y + 5, width: Math.max(w, d.v > 0 ? 2 : 0).toFixed(2), height: rowH - 10, rx: 4, fill: i === topIdx ? "#00ACEF" : "#0B325E" }));
    const valTxt = `${fmtValue(d.v, unit)} · ${pct(d.v, tot)}%`;
    g.appendChild(s("text", { x: W - 4, y: y + rowH / 2 + 5, "text-anchor": "end", "font-size": 14, "font-weight": 600, fill: "#0F1B2D" }, valTxt));
    g.appendChild(s("title", {}, `${d.label}: ${valTxt}`));
    svg.appendChild(g);
  });
  const yT = data.length * (rowH + gap);
  svg.appendChild(s("line", { x1: 0, x2: W, y1: yT + 1, y2: yT + 1, stroke: "#CBD5E1", "stroke-width": 1 }));
  svg.appendChild(s("text", { x: 0, y: yT + rowH / 2 + 6, "font-size": 14, "font-weight": 700, fill: "#0F1B2D" }, t("chart_total")));
  svg.appendChild(s("text", { x: W - 4, y: yT + rowH / 2 + 6, "text-anchor": "end", "font-size": 14, "font-weight": 700, fill: "#0F1B2D" }, fmtValue(tot, unit)));
  fig.appendChild(svg);
  const tRows = data.map((d) => [d.label, fmtValue(d.v, unit), pct(d.v, tot) + "%"]);
  tRows.push([t("chart_total"), fmtValue(tot, unit), tot > 0 ? "100%" : "0%"]);
  fig.appendChild(hiddenTable(label, [t("chart_item"), t("chart_value"), t("chart_share")], tRows));
  return fig;
}

// Kind marker: distinct shapes so color is never the only signal.
function kindMarker(kind) {
  const svg = s("svg", { viewBox: "0 0 12 12", width: 12, height: 12, "aria-hidden": "true", focusable: "false", class: "tl-marker" });
  const navy = "#0B325E", blue = "#00ACEF";
  switch (kind) {
    case "deadline": svg.appendChild(s("rect", { x: 1.5, y: 1.5, width: 9, height: 9, fill: navy })); break;
    case "renewal": svg.appendChild(s("polygon", { points: "6,0.5 11.5,6 6,11.5 0.5,6", fill: blue })); break;
    case "effective_date": svg.appendChild(s("polygon", { points: "6,1 11.5,11 0.5,11", fill: navy })); break;
    case "reminder_window": svg.appendChild(s("circle", { cx: 6, cy: 6, r: 4.25, fill: "none", stroke: blue, "stroke-width": 2 })); break;
    case "estimate": svg.appendChild(s("circle", { cx: 6, cy: 6, r: 5, fill: "#fff", stroke: "#475569", "stroke-width": 1.5, "stroke-dasharray": "2 1.5" })); break;
    default: svg.appendChild(s("circle", { cx: 6, cy: 6, r: 5, fill: blue })); // expected_payment
  }
  return svg;
}

// items: [{ date, kind, title, basis, basis_label }]; opts.empty = text when there are no items.
export function miniTimeline(items = [], { label, empty } = {}) {
  const list = Array.isArray(items) ? items : [];
  const fig = figure(label);
  fig.classList.add("chart-timeline");
  fig.style.maxWidth = "100%";
  if (!list.length) {
    fig.appendChild(el("p", "muted small", empty || t("chart_empty")));
    return fig;
  }
  const ul = el("ul", "mini-timeline");
  ul.style.cssText = "list-style:none;margin:0;padding:0;max-width:100%;";
  list.forEach((it) => {
    const kindTxt = t("tk_" + (it.kind || "expected_payment"));
    const li = el("li", "tl-item");
    li.style.cssText = "display:grid;grid-template-columns:auto 14px 1fr;gap:4px 8px;align-items:baseline;padding:4px 0;border-bottom:1px solid #E2E8F0;min-width:0;";
    const time = el("time", "tl-date num", fmtDate(it.date, "short"));
    if (it.date) time.dateTime = String(it.date);
    time.style.cssText = "font-weight:600;white-space:nowrap;min-width:3.5em;";
    const mk = el("span", "tl-kind");
    mk.style.cssText = "display:inline-flex;align-self:center;";
    mk.title = kindTxt;
    mk.appendChild(kindMarker(it.kind));
    const body = el("span", "tl-body");
    body.style.cssText = "min-width:0;overflow-wrap:anywhere;";
    body.appendChild(el("span", "sr-only", kindTxt + ": "));
    body.appendChild(el("span", "tl-title", it.title || ""));
    if (it.basis_label) {
      const b = el("span", "tl-basis muted small", " · " + it.basis_label);
      body.appendChild(b);
    }
    li.append(time, mk, body);
    ul.appendChild(li);
  });
  fig.appendChild(ul);
  return fig;
}
