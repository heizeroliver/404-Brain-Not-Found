// Kate Foresight shell: header, login, hash router, Kate voice widget.
import { state, t, api, abortAllRequests, el, clear, icon, navigate, onLanguageChange, setLang, toast, errorState } from "./core.js";

const $ = (id) => document.getElementById(id);
const CUSTOMER_SECTIONS = ["overview", "talk", "timeline", "plans", "data"];
const CONTROL_TABS = ["overview", "moments", "queue", "rules", "audit"];
const NAV = [
  { key: "overview", label: "nav_overview", icon: "home" },
  { key: "talk", label: "nav_talk", icon: "mic" },
  { key: "timeline", label: "nav_timeline", icon: "calendar" },
  { key: "plans", label: "nav_plans", icon: "target" },
  { key: "data", label: "nav_data", icon: "shield" },
];
const PERSONAS = [
  { id: "lien", name: "Lien", sub: "29 · Leuven", blurb: { nl: "Huurt al 4 jaar, €26k gespaard, vakantiegeld in mei, Bolero-ETF's.", en: "Renting 4 years, €26k saved, holiday pay in May, Bolero ETFs.", fr: "Locataire depuis 4 ans, €26k d'épargne, pécule de vacances en mai, ETF Bolero." } },
  { id: "marc", name: "Marc", sub: "47 · Brussel", blurb: { nl: "Diesel-bedrijfswagen, woningverzekering +8% binnen 6 weken, Chloé wordt 18.", en: "Diesel company car, home insurance +8% in 6 weeks, Chloé turns 18.", fr: "Voiture de société diesel, assurance habitation +8 % dans 6 semaines, Chloé a 18 ans." } },
  { id: "rita", name: "Rita", sub: "71 · Kortrijk", blurb: { nl: "Pensioen, €48k spaargeld, verdachte betaling tegengehouden. Een adviseur belt haar.", en: "Pension, €48k on savings, a suspicious payment held. An advisor calls her.", fr: "Pension, €48k d'épargne, paiement suspect retenu. Un conseiller l'appelle." } },
  { id: "admin", name: "Control room", sub: "KBC · admin", blurb: { nl: "Momenten over alle klanten, kanaalmix, adviseurwachtrij, beslissingslog.", en: "Moments across all customers, channel mix, advisor queue, decision log.", fr: "Moments sur tous les clients, mix de canaux, file conseiller, journal." } },
];

// ---------------------------------------------------------------- session (survives reload within the tab)
function saveSession() {
  try {
    if (state.token) sessionStorage.setItem("kate_session", JSON.stringify({ token: state.token, role: state.role, profile: state.profile }));
    else sessionStorage.removeItem("kate_session");
  } catch (_) {}
}
function loadSession() {
  try {
    const s = JSON.parse(sessionStorage.getItem("kate_session") || "null");
    if (s && s.token) { state.token = s.token; state.role = s.role; state.profile = s.profile; }
  } catch (_) {}
}

// ---------------------------------------------------------------- Kate voice widget (ElevenLabs), customer only
let assistantEl = null, widgetLoaded = false, assistantFor = null;
function removeAssistant() { if (assistantEl) { assistantEl.remove(); assistantEl = null; } assistantFor = null; }
async function loadAssistant() {
  if (state.role !== "customer") { removeAssistant(); return; }
  const key = state.token + "|" + state.lang;
  if (assistantFor === key) return;
  removeAssistant();
  assistantFor = key;
  try {
    const cfg = await api("/me/assistant", { lang: true });
    if (!cfg || !cfg.enabled || !cfg.agent_id || assistantFor !== key) return;
    if (!widgetLoaded) {
      const sc = document.createElement("script");
      sc.src = "https://unpkg.com/@elevenlabs/convai-widget-embed"; sc.async = true; sc.type = "text/javascript";
      document.body.appendChild(sc); widgetLoaded = true;
    }
    assistantEl = document.createElement("elevenlabs-convai");
    assistantEl.setAttribute("agent-id", cfg.agent_id);
    assistantEl.setAttribute("dynamic-variables", JSON.stringify(cfg.dynamic_variables || {}));
    assistantEl.setAttribute("action-text", t("talk_kate"));
    assistantEl.setAttribute("start-call-text", t("talk_start"));
    assistantEl.setAttribute("end-call-text", t("talk_end"));
    document.body.appendChild(assistantEl);
  } catch (_) { /* voice conversation is optional */ }
}

// ---------------------------------------------------------------- header
function renderHeader() {
  const header = $("app-header");
  clear(header);
  const inner = el("div", "header-inner container" + (state.role === "admin" ? " container-wide" : ""));
  const brand = el("a", "brand");
  brand.href = state.role === "admin" ? "#/control/overview" : state.role === "customer" ? "#/customer/overview" : "#/login";
  const mark = el("img", "brand-logo"); mark.src = "assets/kbc-logo.png"; mark.alt = "KBC"; mark.height = 32;
  const words = el("span", "brand-words");
  words.append(el("span", "brand-name", t("brand")), el("span", "brand-proto", t("proto")));
  brand.append(mark, words);

  const right = el("div", "header-right");
  const sw = el("div", "lang-switch");
  sw.setAttribute("role", "group"); sw.setAttribute("aria-label", t("lang_group"));
  for (const l of ["nl", "en", "fr"]) {
    const b = el("button", "lang-btn", l.toUpperCase());
    b.type = "button"; b.lang = l;
    b.setAttribute("aria-pressed", String(state.lang === l));
    b.addEventListener("click", () => setLang(l));
    sw.appendChild(b);
  }
  right.appendChild(sw);
  if (state.token) {
    right.appendChild(el("span", "header-user", (state.profile && state.profile.name) || (state.role === "admin" ? "Control room" : "")));
    const out = el("button", "btn btn-quiet btn-sm header-logout", t("logout"));
    out.type = "button"; out.addEventListener("click", () => logout());
    right.appendChild(out);
  }
  inner.append(brand, right);
  header.appendChild(inner);
}

// ---------------------------------------------------------------- customer nav
function renderCustomerNav(section) {
  let nav = $("customer-nav");
  if (!nav) {
    nav = el("nav", "customer-nav");
    nav.id = "customer-nav";
    $("app-header").after(nav);
  }
  clear(nav);
  nav.setAttribute("aria-label", t("nav_label"));
  const ul = el("ul", "container");
  for (const n of NAV) {
    const li = el("li");
    const a = el("a", "nav-link");
    a.href = "#/customer/" + n.key;
    a.append(icon(n.icon, 20), el("span", null, t(n.label)));
    if (n.key === section) a.setAttribute("aria-current", "page");
    li.appendChild(a); ul.appendChild(li);
  }
  nav.appendChild(ul);
  document.body.classList.add("has-bottom-nav");
}
function removeCustomerNav() { const n = $("customer-nav"); if (n) n.remove(); document.body.classList.remove("has-bottom-nav"); }

// ---------------------------------------------------------------- login
function renderLogin(root) {
  const wrap = el("div", "container login stack-lg");
  const h1 = el("h1", "page-title", t("login_title")); h1.tabIndex = -1;
  const logo = el("img", "login-logo"); logo.src = "assets/kbc-logo.png"; logo.alt = "KBC"; logo.height = 40;
  wrap.append(logo, h1, el("p", "muted", t("login_sub")));
  const grid = el("div", "persona-grid");
  const form = el("form", "card login-form");
  const idField = el("input", "field"); idField.id = "login-id"; idField.autocomplete = "username"; idField.placeholder = "lien"; idField.required = true;
  const pwField = el("input", "field"); pwField.id = "login-pw"; pwField.type = "password"; pwField.autocomplete = "current-password"; pwField.required = true;
  for (const p of PERSONAS) {
    const b = el("button", "card persona");
    b.type = "button";
    const av = el("span", "avatar", p.name.slice(0, 1)); av.setAttribute("aria-hidden", "true");
    const txt = el("span", "persona-text");
    txt.append(el("span", "persona-name", p.name), el("span", "persona-sub", p.sub), el("span", "persona-blurb muted", p.blurb[state.lang] || p.blurb.en));
    b.append(av, txt);
    b.addEventListener("click", () => {
      idField.value = p.id;
      grid.querySelectorAll(".persona").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      pwField.focus();
    });
    b.setAttribute("aria-pressed", "false");
    grid.appendChild(b);
  }
  const l1 = el("label", "label-block"); l1.append(el("span", "label", t("persona")), idField);
  const l2 = el("label", "label-block"); l2.append(el("span", "label", t("password")), pwField);
  const submit = el("button", "btn btn-primary", t("open_app")); submit.type = "submit";
  const err = el("p", "form-error"); err.setAttribute("role", "alert");
  form.append(l1, l2, submit, err);
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    err.textContent = "";
    submit.disabled = true;
    try {
      const body = await api("/login", { method: "POST", body: { customer_id: idField.value.trim(), password: pwField.value } });
      state.token = body.access_token; state.role = body.role; state.profile = body.profile;
      saveSession();
      pwField.value = "";
      navigate(state.role === "admin" ? "#/control/overview" : "#/customer/overview");
    } catch (e) {
      err.textContent = e.message === "Invalid credentials" ? t("invalid") : t("login_fail") + e.message;
    } finally { submit.disabled = false; }
  });
  wrap.append(grid, form);
  root.appendChild(wrap);
}

function logout(reason) {
  state.token = null; state.role = null; state.profile = null;
  abortAllRequests();  // in-flight responses of the old session are dropped
  saveSession();
  removeAssistant();
  // clear session-derived DOM and let views drop their in-memory caches
  const root = $("app"); if (root) root.replaceChildren();
  try { window.dispatchEvent(new CustomEvent("kate:session-cleared")); } catch (_) {}
  if (reason === "expired") toast(t("session_expired"), "warn");
  navigate("#/login");
}
window.addEventListener("kate:logout", (e) => logout(e.detail && e.detail.reason));

// ---------------------------------------------------------------- router
function parseHash() {
  const raw = (location.hash || "").replace(/^#\/?/, "");
  const [pathPart, query = ""] = raw.split("?");
  const parts = pathPart.split("/").filter(Boolean);
  const params = Object.fromEntries(new URLSearchParams(query));
  return { area: parts[0] || "", sub: parts[1] || "", params };
}

let routeSeq = 0;
async function route() {
  const seq = ++routeSeq;
  const { area, sub, params } = parseHash();
  const root = $("app");

  // guards
  if (!state.token) {
    if (area !== "login") { history.replaceState(null, "", "#/login"); }
    return show(seq, root, "login");
  }
  if (area === "login" || !area) return navigate(state.role === "admin" ? "#/control/overview" : "#/customer/overview");
  if (area === "customer" && state.role !== "customer") return navigate("#/control/overview");
  if (area === "control" && state.role !== "admin") return navigate("#/customer/overview");
  if (area !== "customer" && area !== "control") return navigate(state.role === "admin" ? "#/control/overview" : "#/customer/overview");

  if (area === "customer") {
    const section = CUSTOMER_SECTIONS.includes(sub) ? sub : "overview";
    if (section !== sub) return navigate("#/customer/" + section);
    return show(seq, root, "customer", section);
  }
  const tab = CONTROL_TABS.includes(sub) ? sub : "overview";
  if (tab !== sub) return navigate("#/control/" + tab);
  return show(seq, root, "control", tab, params);
}

async function show(seq, root, view, sub, params) {
  document.body.dataset.view = view;
  renderHeader();
  clear(root);
  root.className = view === "control" ? "view-control" : view === "customer" ? "view-customer" : "view-login";
  if (view === "login") { removeCustomerNav(); removeAssistant(); renderLogin(root); focusMain(root); return; }
  if (view === "customer") { renderCustomerNav(sub); removeAssistant(); } else { removeCustomerNav(); removeAssistant(); }
  const loading = el("div", "container"); loading.appendChild(el("div", "skeleton skeleton-block")); loading.setAttribute("aria-busy", "true");
  root.appendChild(loading);
  try {
    const mod = view === "customer" ? (sub === "talk" ? await import("./talk.js") : await import("./customer.js"))
      : await import("./control.js");
    if (seq !== routeSeq) return;
    clear(root);
    const fn = view === "customer" ? (sub === "talk" ? mod.renderTalk : mod.renderCustomer) : mod.renderControl;
    if (typeof fn !== "function") throw new Error("module has no render function");
    await (view === "customer" ? fn(root, sub) : fn(root, sub, params || {}));
  } catch (e) {
    if (seq !== routeSeq) return;
    console.error(e);
    clear(root);
    const c = el("div", "container");
    c.appendChild(errorState(t("load_error"), () => route()));
    root.appendChild(c);
  }
}

function focusMain(root) {
  const h = root.querySelector("h1");
  if (h && document.activeElement === document.body) { try { h.focus({ preventScroll: true }); } catch (_) {} }
}

// ---------------------------------------------------------------- boot
onLanguageChange(() => { assistantFor = null; route(); });
window.addEventListener("hashchange", route);
document.documentElement.lang = state.lang;
loadSession();
route();
