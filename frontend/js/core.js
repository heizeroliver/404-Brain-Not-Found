// Kate Foresight core: state, i18n, API, DOM helpers, panel, toast, router helper.
// Security: DOM is built with el()/textContent only. Never innerHTML with data.

const LANGS = ["nl", "en", "fr"];

function loadLang() {
  try { const v = localStorage.getItem("kate_lang"); return LANGS.includes(v) ? v : "nl"; } catch (_) { return "nl"; }
}

export const state = { token: null, role: null, profile: null, lang: loadLang() };

// ------------------------------------------------------------------ i18n
const STRINGS = { nl: {}, en: {}, fr: {} };

export function registerStrings(dict) {
  if (!dict) return;
  for (const l of LANGS) if (dict[l]) Object.assign(STRINGS[l], dict[l]);
}

export function t(key, ...args) {
  const v = STRINGS[state.lang]?.[key] ?? STRINGS.en[key] ?? key;
  return typeof v === "function" ? v(...args) : v;
}

registerStrings({
  nl: {
    brand: "Kate Foresight", proto: "Prototype voor de KBC-case · fictieve data", logout: "Afmelden",
    lang_group: "Taal", login_title: "Wie opent de app?", login_sub: "Kies een fictieve klant en open de app zoals die klant hem ziet.",
    persona: "Persona", password: "Demowachtwoord", open_app: "Open de app",
    invalid: "Ongeldige gegevens.", login_fail: "Aanmelden mislukt: ", session_expired: "Je sessie is verlopen. Meld je opnieuw aan.",
    nav_overview: "Overzicht", nav_talk: "Praat met Kate", nav_timeline: "Tijdlijn", nav_plans: "Mijn plannen", nav_data: "Mijn gegevens", nav_label: "Hoofdnavigatie",
    close: "Sluiten", load_error: "Dit onderdeel kon niet laden.", retry: "Opnieuw proberen", loading: "Laden…",
    talk_kate: "Praat met Kate", talk_start: "Start gesprek", talk_end: "Stop",
    chart_total: "Totaal", chart_value: "Waarde", chart_share: "Aandeel", chart_item: "Onderdeel",
  },
  en: {
    brand: "Kate Foresight", proto: "Prototype for the KBC case · synthetic data", logout: "Log out",
    lang_group: "Language", login_title: "Who is opening the app?", login_sub: "Pick a fictional customer and open the app the way they see it.",
    persona: "Persona", password: "Demo password", open_app: "Open the app",
    invalid: "Invalid credentials.", login_fail: "Login failed: ", session_expired: "Your session expired. Please log in again.",
    nav_overview: "Overview", nav_talk: "Talk to Kate", nav_timeline: "Timeline", nav_plans: "My plans", nav_data: "My data", nav_label: "Main navigation",
    close: "Close", load_error: "This section could not load.", retry: "Try again", loading: "Loading…",
    talk_kate: "Talk to Kate", talk_start: "Start conversation", talk_end: "End",
    chart_total: "Total", chart_value: "Value", chart_share: "Share", chart_item: "Item",
  },
  fr: {
    brand: "Kate Foresight", proto: "Prototype pour le cas KBC · données fictives", logout: "Se déconnecter",
    lang_group: "Langue", login_title: "Qui ouvre l'app ?", login_sub: "Choisissez un client fictif et ouvrez l'app comme il la voit.",
    persona: "Persona", password: "Mot de passe démo", open_app: "Ouvrir l'app",
    invalid: "Identifiants invalides.", login_fail: "Connexion impossible : ", session_expired: "Votre session a expiré. Reconnectez-vous.",
    nav_overview: "Aperçu", nav_talk: "Parler à Kate", nav_timeline: "Calendrier", nav_plans: "Mes projets", nav_data: "Mes données", nav_label: "Navigation principale",
    close: "Fermer", load_error: "Cette section n'a pas pu se charger.", retry: "Réessayer", loading: "Chargement…",
    talk_kate: "Parler à Kate", talk_start: "Démarrer", talk_end: "Arrêter",
    chart_total: "Total", chart_value: "Valeur", chart_share: "Part", chart_item: "Élément",
  },
});

const langListeners = [];
export function onLanguageChange(fn) { langListeners.push(fn); return () => { const i = langListeners.indexOf(fn); if (i >= 0) langListeners.splice(i, 1); }; }
export function setLang(lang) {
  if (!LANGS.includes(lang) || lang === state.lang) return;
  state.lang = lang;
  try { localStorage.setItem("kate_lang", lang); } catch (_) {}
  document.documentElement.lang = lang;
  for (const fn of [...langListeners]) { try { fn(lang); } catch (e) { console.error(e); } }
}

// ------------------------------------------------------------------ API
export const API_BASE = window.API_BASE_URL || (location.port === "5173" ? "http://localhost:8000" : "");

export async function api(path, { method = "GET", body, lang = false, headers: extra } = {}) {
  let url = API_BASE + path;
  if (lang) url += (url.includes("?") ? "&" : "?") + "lang=" + encodeURIComponent(state.lang);
  const headers = { Accept: "application/json", ...(extra || {}) };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  const res = await fetch(url, { method, headers, body: body === undefined ? undefined : (typeof body === "string" ? body : JSON.stringify(body)) });
  if (res.status === 401 && state.token) {
    window.dispatchEvent(new CustomEvent("kate:logout", { detail: { reason: "expired" } }));
    throw new Error("Session expired");
  }
  if (!res.ok) {
    let detail = res.statusText || ("HTTP " + res.status);
    try {
      const j = await res.json();
      if (typeof j.detail === "string") detail = j.detail;
      else if (Array.isArray(j.detail)) detail = j.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
      else if (j.detail) detail = JSON.stringify(j.detail);
    } catch (_) {}
    const err = new Error(detail); err.status = res.status; throw err;
  }
  if (res.status === 204) return null;
  const txt = await res.text();
  if (!txt) return null;
  try { return JSON.parse(txt); } catch (_) { return txt; }
}

// ------------------------------------------------------------------ DOM
export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}
export function clear(node) { if (node) while (node.firstChild) node.removeChild(node.firstChild); }

const SVGNS = "http://www.w3.org/2000/svg";
// Each icon: list of [tag, attrs] on a 24x24 stroke grid.
const ICONS = {
  home: [["path", { d: "M3 11l9-8 9 8" }], ["path", { d: "M5 10v10h14V10" }], ["path", { d: "M10 20v-6h4v6" }]],
  calendar: [["rect", { x: 3, y: 5, width: 18, height: 16, rx: 2 }], ["path", { d: "M3 10h18M8 3v4M16 3v4" }]],
  target: [["circle", { cx: 12, cy: 12, r: 9 }], ["circle", { cx: 12, cy: 12, r: 5 }], ["circle", { cx: 12, cy: 12, r: 1 }]],
  shield: [["path", { d: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" }]],
  info: [["circle", { cx: 12, cy: 12, r: 9 }], ["path", { d: "M12 11v6M12 7.5v.5" }]],
  close: [["path", { d: "M6 6l12 12M18 6L6 18" }]],
  chevron: [["path", { d: "M9 6l6 6-6 6" }]],
  check: [["path", { d: "M5 12l5 5 9-10" }]],
  user: [["circle", { cx: 12, cy: 8, r: 4 }], ["path", { d: "M4 21c1-4 4-6 8-6s7 2 8 6" }]],
  phone: [["path", { d: "M5 3h4l2 5-3 2a12 12 0 006 6l2-3 5 2v4a2 2 0 01-2 2A18 18 0 013 5a2 2 0 012-2z" }]],
  search: [["circle", { cx: 11, cy: 11, r: 7 }], ["path", { d: "M20 20l-4-4" }]],
  filter: [["path", { d: "M3 5h18l-7 8v6l-4 2v-8z" }]],
  refresh: [["path", { d: "M20 11a8 8 0 10-2 6" }], ["path", { d: "M20 4v7h-7" }]],
  alert: [["path", { d: "M12 3l10 18H2z" }], ["path", { d: "M12 10v5M12 18v.5" }]],
  "arrow-right": [["path", { d: "M4 12h16M14 6l6 6-6 6" }]],
  play: [["path", { d: "M7 4l13 8-13 8z" }]],
  mic: [["rect", { x: 9, y: 3, width: 6, height: 11, rx: 3 }], ["path", { d: "M5 11a7 7 0 0014 0M12 18v3" }]],
};
export function icon(name, size = 20) {
  const svg = document.createElementNS(SVGNS, "svg");
  svg.setAttribute("width", String(size)); svg.setAttribute("height", String(size));
  svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor"); svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round"); svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true"); svg.setAttribute("focusable", "false");
  svg.setAttribute("class", "icon");
  for (const [tag, attrs] of ICONS[name] || []) {
    const n = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
    svg.appendChild(n);
  }
  return svg;
}

// ------------------------------------------------------------------ formatting
const LOCALES = { nl: "nl-BE", fr: "fr-BE", en: "en-GB" };
export function locale() { return LOCALES[state.lang] || "nl-BE"; }
export function fmtEur(n) {
  const v = Number(n);
  if (!Number.isFinite(v)) return "–";
  return new Intl.NumberFormat(locale(), { style: "currency", currency: "EUR", maximumFractionDigits: 0, minimumFractionDigits: 0 }).format(v);
}
export function fmtNum(n) {
  const v = Number(n);
  return Number.isFinite(v) ? new Intl.NumberFormat(locale(), { maximumFractionDigits: 1 }).format(v) : "–";
}
export function fmtDate(iso, style = "long") {
  if (!iso) return "";
  const d = /^\d{4}-\d{2}-\d{2}$/.test(String(iso)) ? new Date(iso + "T12:00:00") : new Date(iso);
  if (isNaN(d)) return String(iso);
  const opts = style === "short" ? { day: "numeric", month: "short" }
    : style === "medium" ? { day: "numeric", month: "short", year: "numeric" }
    : style === "datetime" ? { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }
    : { day: "numeric", month: "long", year: "numeric" };
  return new Intl.DateTimeFormat(locale(), opts).format(d);
}

// ------------------------------------------------------------------ panel (dialog)
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';
let panelSeq = 0;

export function openPanel({ title, content, onClose } = {}) {
  const root = document.getElementById("panel-root") || document.body;
  const opener = document.activeElement;
  const id = "panel-title-" + (++panelSeq);

  const backdrop = el("div", "panel-backdrop");
  const dialog = el("div", "panel");
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-labelledby", id);
  const head = el("div", "panel-head");
  const h = el("h2", "panel-title", title || "");
  h.id = id;
  const closeBtn = el("button", "btn btn-quiet btn-icon");
  closeBtn.type = "button";
  closeBtn.setAttribute("aria-label", t("close"));
  closeBtn.appendChild(icon("close"));
  head.append(h, closeBtn);
  const body = el("div", "panel-body");
  dialog.append(head, body);
  backdrop.appendChild(dialog);

  function setContent(c) {
    clear(body);
    if (c == null) return;
    if (typeof c === "string") body.appendChild(el("p", null, c));
    else if (Array.isArray(c)) c.forEach((x) => x && body.appendChild(x));
    else body.appendChild(c);
  }
  setContent(content);

  let closed = false;
  function close() {
    if (closed) return;
    closed = true;
    document.removeEventListener("keydown", onKey, true);
    backdrop.remove();
    if (!root.querySelector(".panel-backdrop")) document.body.classList.remove("panel-open");
    try { if (opener && opener.focus && document.contains(opener)) opener.focus(); } catch (_) {}
    if (onClose) { try { onClose(); } catch (e) { console.error(e); } }
  }
  function onKey(e) {
    if (!document.contains(dialog)) return;
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); return; }
    if (e.key === "Tab") {
      const f = [...dialog.querySelectorAll(FOCUSABLE)].filter((n) => n.offsetParent !== null || n === document.activeElement);
      if (!f.length) { e.preventDefault(); return; }
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) { e.preventDefault(); first.focus(); }
    }
  }
  closeBtn.addEventListener("click", close);
  backdrop.addEventListener("mousedown", (e) => { if (e.target === backdrop) close(); });
  document.addEventListener("keydown", onKey, true);
  root.appendChild(backdrop);
  document.body.classList.add("panel-open");
  const first = dialog.querySelector(FOCUSABLE);
  (first || dialog).focus();
  return { close, setContent, body, dialog };
}

// ------------------------------------------------------------------ toast
export function toast(message, kind = "info") {
  let root = document.getElementById("toast-root");
  if (!root) { root = el("div"); root.id = "toast-root"; document.body.appendChild(root); }
  const n = el("div", "toast toast-" + kind, message);
  n.setAttribute("role", kind === "error" ? "alert" : "status");
  root.appendChild(n);
  setTimeout(() => n.remove(), 3500);
  return n;
}

// ------------------------------------------------------------------ navigation
export function navigate(hash) {
  const h = hash.startsWith("#") ? hash : "#" + hash;
  if (location.hash === h) window.dispatchEvent(new HashChangeEvent("hashchange"));
  else location.hash = h;
}

// Small helper for modules: loading / error states.
export function errorState(message, onRetry) {
  const box = el("div", "empty");
  box.setAttribute("role", "alert");
  box.appendChild(el("p", null, message || t("load_error")));
  if (onRetry) {
    const b = el("button", "btn btn-secondary btn-sm", t("retry"));
    b.type = "button"; b.addEventListener("click", onRetry); box.appendChild(b);
  }
  return box;
}
