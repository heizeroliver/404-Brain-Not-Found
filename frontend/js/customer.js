// Customer app: overview, timeline, plans, data. DOM via el()/textContent only.
import { state, t, api, el, clear, icon, fmtEur, fmtDate, openPanel, toast, navigate, registerStrings } from "./core.js";
import { allocationBar } from "./charts.js";
import strings from "./i18n-customer.js";

registerStrings(strings);

let renderSeq = 0;          // guards against late responses after navigation
let openPanelRef = null;    // currently open panel (closed after mutations)
let tlDays = 90;

const lq = (path) => path + (path.includes("?") ? "&" : "?") + "lang=" + encodeURIComponent(state.lang || "nl");
const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : "");

function h(tag, cls, text, kids) {
  const n = el(tag, cls || "", text);
  (kids || []).forEach((k) => k && n.appendChild(k));
  return n;
}
function btn(label, cls, onClick) {
  const b = el("button", "btn " + (cls || "btn-secondary"), label);
  b.type = "button";
  if (onClick) b.addEventListener("click", onClick);
  return b;
}
function closePanel() {
  if (openPanelRef) { try { openPanelRef.close(); } catch (_) { /* already closed */ } openPanelRef = null; }
}
function panel(title, content) {
  closePanel();
  openPanelRef = openPanel({ title, content, onClose: () => { openPanelRef = null; } });
  return openPanelRef;
}
function srcLabel(s) { return t("src_" + s); }
function kindIcon(kind) {
  return icon({ deadline: "alert", expected_payment: "arrow-right", renewal: "refresh", effective_date: "calendar", reminder_window: "calendar" }[kind] || "calendar", 18);
}
function goalLabel(g) { return `${cap(t("gp_" + g.purpose))} · ${fmtEur(g.amount)}`; }

function skeleton(root) {
  clear(root);
  const box = h("div", "stack-4", null, [el("div", "skeleton"), el("div", "skeleton"), el("div", "skeleton")]);
  box.setAttribute("aria-busy", "true");
  box.appendChild(el("p", "sr-only", t("c_loading")));
  root.appendChild(box);
}
function errorState(root, err, retry) {
  clear(root);
  const box = h("div", "card empty", null, [el("p", "", t("c_load_error") + (err && err.message ? err.message : String(err)))]);
  box.setAttribute("role", "alert");
  box.appendChild(btn(t("c_retry"), "btn-secondary", retry));
  root.appendChild(box);
}
async function load(root, fn, render) {
  const seq = ++renderSeq;
  skeleton(root);
  try {
    const data = await fn();
    if (seq !== renderSeq) return;
    clear(root);
    render(data);
  } catch (err) {
    if (seq !== renderSeq) return;
    errorState(root, err, () => renderCustomer(root, currentSection));
  }
}

let currentSection = "overview";
export function renderCustomer(root, section) {
  currentSection = ["overview", "timeline", "plans", "data"].includes(section) ? section : "overview";
  closePanel();
  if (currentSection === "timeline") return renderTimeline(root);
  if (currentSection === "plans") return renderPlans(root);
  if (currentSection === "data") return renderData(root);
  return renderOverview(root);
}

// ------------------------------------------------------------------ allocation
function allocationSection(a) {
  const sec = h("section", "card stack-3", null, [el("h2", "section-title", t("alloc_title"))]);
  if (!a) return sec;
  // funded amounts come from the backend (engine/allocation.py) and always add up to savings
  const segs = [{ key: "buffer", label: t("alloc_buffer"), value: a.buffer_covered ?? Math.min(a.buffer, a.savings), color: "#003665" }];
  (a.reserved || []).forEach((r) => {
    if (r.covered > 0) segs.push({ key: "goal-" + r.goal_id, label: cap(t("gp_" + r.purpose)), value: r.covered, color: "#00AEEF" });
  });
  segs.push({ key: "remaining", label: t("alloc_remaining"), value: a.remaining, color: "#9FB7CC", pattern: "hatch" });
  sec.appendChild(allocationBar(segs, { label: t("alloc_total", fmtEur(a.savings)) }));
  if (a.shortfall > 0) {
    const n = el("p", "tag tag-warn", t("alloc_short", fmtEur(a.shortfall)));
    sec.appendChild(n);
  }
  const note = el("p", "muted", t("alloc_assumption", a.buffer_months || 6, fmtEur(a.net_monthly_income || 0)));
  note.style.fontSize = "14px";
  sec.appendChild(note);
  return sec;
}

// ------------------------------------------------------------------ moments
function keyDateLine(m) {
  const d = m.key_date || (m.window && m.window[1]);
  if (!m.date_label_kind || !d) return null;
  return h("p", "num", null, [el("strong", "", t("dl_" + m.date_label_kind) + ": "), document.createTextNode(fmtDate(d))]);
}

function requestedLabel(req) { return t("ar_done", req.id); }

function primaryButton(m, root) {
  const a = m.action || { kind: "none" };
  if (a.kind === "none" || !a.label) return null;
  if (a.kind === "advisor_request") {
    if (m.requested) {
      const b = btn(requestedLabel(m.requested), "btn-primary");
      b.disabled = true;
      return b;
    }
    const b = btn(a.label, "btn-primary", () => confirmAdvisor(m, b));
    return b;
  }
  const target = { open_plans: "#/customer/plans", open_timeline: "#/customer/timeline", open_data: "#/customer/data" }[a.kind];
  if (!target) return null;
  return btn(a.label, "btn-primary", () => navigate(target));
}

function confirmAdvisor(m, trigger) {
  const body = h("div", "stack-4", null, [el("p", "", t("ar_confirm_text"))]);
  const status = el("p", "");
  status.setAttribute("role", "status");
  const ok = btn(t("ar_confirm"), "btn-primary");
  const no = btn(t("ar_cancel"), "btn-secondary", () => closePanel());
  const row = h("div", "stack-2", null, [ok, no]);
  body.appendChild(row);
  body.appendChild(status);
  ok.addEventListener("click", async () => {
    ok.disabled = true; no.disabled = true; trigger.disabled = true;
    ok.textContent = t("ar_pending");
    try {
      const res = await api(lq("/me/advisor-requests"), { method: "POST", body: { moment_type: m.type } });
      const req = res.request || res;
      m.requested = req;
      trigger.textContent = requestedLabel(req);
      trigger.disabled = true;
      row.remove();
      status.textContent = t("ar_created", req.id, t("ar_status_" + req.status));
      body.appendChild(btn(t("c_close"), "btn-secondary", () => closePanel()));
    } catch (err) {
      ok.disabled = false; no.disabled = false; trigger.disabled = false;
      ok.textContent = t("ar_confirm");
      status.textContent = t("save_fail") + err.message;
    }
  });
  panel(t("ar_confirm_title"), body);
}

function openWhy(m) {
  const c = h("div", "stack-4", null, [el("h3", "", m.title)]);
  if (m.why_reasons && m.why_reasons.length) {
    c.appendChild(h("ul", "stack-2", null, m.why_reasons.map((r) => el("li", "", r))));
  } else if (m.why) c.appendChild(el("p", "", m.why));
  const dl = el("dl", "stack-2");
  const add = (k, v) => { if (v === null || v === undefined || v === "") return; dl.appendChild(el("dt", "label", k)); dl.appendChild(el("dd", "", v)); };
  if (m.window && m.window[0]) add(t("c_key_dates"), m.window[1] && m.window[1] !== m.window[0] ? t("c_period", fmtDate(m.window[0]), fmtDate(m.window[1])) : fmtDate(m.window[0]));
  add(t("c_source"), srcLabel(m.source));
  add(t("c_channel"), t("ch_" + m.channel));
  if (m.legal_basis_label) add(t("c_legal"), m.legal_basis_label);
  c.appendChild(dl);
  if (m.human_review_required === true) c.appendChild(h("p", "tag tag-info", t("c_human")));
  const det = h("details", "details", null, [el("summary", "", t("c_tech"))]);
  if (m.evidence && m.evidence.length) det.appendChild(h("ul", "stack-1", null, m.evidence.map((e) => el("li", "muted num", e))));
  if (typeof m.confidence === "number") det.appendChild(el("p", "muted", t("c_rule_conf", Math.round(m.confidence * 100))));
  c.appendChild(det);
  const toPlans = m.source === "life_calendar" || m.type === "idle_cash" || (m.action && m.action.kind === "open_plans");
  const fix = h("p", "", null, [el("span", "", t("c_wrong") + " ")]);
  const link = el("a", "", toPlans ? t("c_wrong_goal") : t("c_wrong_data"));
  link.href = toPlans ? "#/customer/plans" : "#/customer/data";
  link.addEventListener("click", () => closePanel());
  fix.appendChild(link);
  c.appendChild(fix);
  panel(t("c_why_title"), c);
}

function feedbackRow(m, root) {
  const row = h("div", "stack-2", null, []);
  row.setAttribute("role", "group");
  row.setAttribute("aria-label", t("fb_group"));
  row.style.display = "flex"; row.style.flexWrap = "wrap"; row.style.gap = "8px";
  [["not_now", "fb_not_now"], ["not_relevant", "fb_not_relevant"], ["never", "fb_never"], ["helpful", "fb_helpful"]].forEach(([action, key]) => {
    const b = btn(t(key), "btn-quiet btn-sm", async () => {
      row.querySelectorAll("button").forEach((x) => { x.disabled = true; });
      try {
        await api("/me/feedback", { method: "POST", body: { moment_type: m.type, action } });
        closePanel();
        toast(t("fb_thanks"), "info");
        renderCustomer(root, currentSection);
      } catch (err) {
        row.querySelectorAll("button").forEach((x) => { x.disabled = false; });
        toast(t("feedback_fail") + err.message, "error");
      }
    });
    row.appendChild(b);
  });
  return row;
}

function priorityCard(m, root) {
  const card = h("article", "card stack-3", null, [el("p", "eyebrow", srcLabel(m.source)), el("h2", "", m.title), el("p", "", m.message)]);
  const kd = keyDateLine(m);
  if (kd) card.appendChild(kd);
  const actions = h("div", "", null, []);
  actions.style.display = "flex"; actions.style.flexWrap = "wrap"; actions.style.gap = "8px";
  const p = primaryButton(m, root);
  if (p) actions.appendChild(p);
  actions.appendChild(btn(t("c_why"), "btn-secondary", () => openWhy(m)));
  card.appendChild(actions);
  card.appendChild(feedbackRow(m, root));
  return card;
}

// ------------------------------------------------------------------ overview
function renderOverview(root) {
  load(root, () => api(lq("/me/overview")), (d) => {
    const grid = el("div", "layout-2col");
    const main = el("div", "stack-6");
    const side = el("aside", "stack-6");
    grid.appendChild(main); grid.appendChild(side);
    root.appendChild(grid);

    if (d.care_mode) {
      main.appendChild(h("section", "card stack-2", null, [el("h2", "section-title", t("c_care_title")), el("p", "muted", t("c_care_text"))]));
    }
    if (d.priority) main.appendChild(priorityCard(d.priority, root));
    else main.appendChild(h("section", "card empty", null, [el("p", "", t("c_empty"))]));
    main.appendChild(allocationSection(d.allocation));

    // side: upcoming
    const up = h("section", "card stack-3", null, [el("h2", "section-title", t("side_upcoming"))]);
    if (d.upcoming && d.upcoming.length) {
      const ul = el("ul", "stack-2");
      d.upcoming.forEach((it) => {
        const li = el("li", "");
        li.style.display = "flex"; li.style.gap = "8px"; li.style.alignItems = "flex-start";
        li.appendChild(kindIcon(it.kind));
        li.appendChild(h("div", "", null, [el("div", "num muted", fmtDate(it.date, "medium")), el("div", "", it.title)]));
        ul.appendChild(li);
      });
      up.appendChild(ul);
    } else up.appendChild(el("p", "muted", t("side_none_upcoming")));
    side.appendChild(up);

    // side: plans
    const pl = h("section", "card stack-3", null, [el("h2", "section-title", t("side_plans"))]);
    if (d.goals && d.goals.length) pl.appendChild(h("ul", "stack-1", null, d.goals.map((g) => el("li", "num", goalLabel(g)))));
    else pl.appendChild(el("p", "muted", t("side_plans_none")));
    const pa = el("a", "", t("side_plans_link"));
    pa.href = "#/customer/plans";
    pl.appendChild(pa);
    side.appendChild(pl);

    // side: others
    if (d.others && d.others.length) {
      const ot = h("section", "card stack-3", null, [el("h2", "section-title", t("side_others"))]);
      const ul = el("ul", "stack-3");
      d.others.forEach((m) => {
        const li = h("li", "stack-1", null, [el("p", "eyebrow", srcLabel(m.source)), el("div", "", m.title)]);
        const w = btn(t("c_why"), "btn-quiet btn-sm", () => openWhy(m));
        w.setAttribute("aria-label", t("c_why") + " " + m.title);
        li.appendChild(w);
        if (m.requested) li.appendChild(el("p", "tag tag-ok", requestedLabel(m.requested)));
        ul.appendChild(li);
      });
      ot.appendChild(ul);
      side.appendChild(ot);
    }

    // side: advisor requests
    if (d.advisor_requests && d.advisor_requests.length) {
      const ar = h("section", "card stack-3", null, [el("h2", "section-title", t("ar_title"))]);
      ar.appendChild(h("ul", "stack-2", null, d.advisor_requests.map((r) =>
        h("li", "", null, [el("div", "num", r.id), el("div", "muted", `${t("ar_status_" + r.status)} · ${fmtDate(r.updated || r.created, "medium")}`)]))));
      side.appendChild(ar);
    }
  });
}

// ------------------------------------------------------------------ timeline
async function fetchTimeline(days) {
  try { return await api(lq("/me/timeline2?days=" + days)); }
  catch (err) {
    if (/not found/i.test(err.message)) return api(lq("/me/timeline-v2?days=" + days));
    throw err;
  }
}

function renderTimeline(root) {
  load(root, () => fetchTimeline(tlDays), (d) => {
    const wrap = h("div", "stack-6", null, [el("h1", "section-title", t("tl_title"))]);
    const seg = el("div", "tabs");
    seg.setAttribute("role", "group");
    seg.setAttribute("aria-label", t("tl_horizon"));
    [[90, "tl_90"], [365, "tl_365"]].forEach(([n, key]) => {
      const b = btn(t(key), "chip", () => { tlDays = n; renderTimeline(root); });
      b.setAttribute("aria-pressed", String(tlDays === n));
      seg.appendChild(b);
    });
    wrap.appendChild(seg);

    const legend = h("section", "card stack-2", null, [el("h2", "label", t("tl_legend"))]);
    legend.appendChild(el("p", "muted", `${t("tl_sources")}: ${["life_calendar", "world_rule", "protection"].map(srcLabel).join(" · ")}`));
    const kinds = el("ul", "");
    kinds.style.display = "flex"; kinds.style.flexWrap = "wrap"; kinds.style.gap = "12px"; kinds.style.listStyle = "none"; kinds.style.padding = "0";
    ["deadline", "reminder_window", "expected_payment", "renewal", "effective_date"].forEach((k) => {
      const li = h("li", "muted", null, [kindIcon(k), el("span", "", " " + t("k_" + k))]);
      li.style.display = "inline-flex"; li.style.alignItems = "center"; li.style.gap = "4px";
      kinds.appendChild(li);
    });
    legend.appendChild(kinds);
    wrap.appendChild(legend);

    const items = d.items || [];
    if (!items.length) {
      const e = h("section", "card empty", null, [el("p", "", t("tl_empty"))]);
      if (d.next_after_horizon) e.appendChild(el("p", "muted", t("tl_next", fmtDate(d.next_after_horizon.date), d.next_after_horizon.title)));
      wrap.appendChild(e);
    } else {
      const lang = { nl: "nl-BE", en: "en-GB", fr: "fr-BE" }[state.lang] || "nl-BE";
      const monthFmt = new Intl.DateTimeFormat(lang, { month: "long", year: "numeric" });
      const groups = new Map();
      items.forEach((it) => {
        const k = String(it.date).slice(0, 7);
        if (!groups.has(k)) groups.set(k, []);
        groups.get(k).push(it);
      });
      groups.forEach((list, k) => {
        const sec = h("section", "card stack-3", null, [el("h2", "section-title", cap(monthFmt.format(new Date(k + "-01T12:00:00"))))]);
        const ul = el("ul", "stack-3");
        list.forEach((it) => {
          const li = el("li", "");
          li.style.display = "flex"; li.style.gap = "12px"; li.style.alignItems = "flex-start";
          li.appendChild(kindIcon(it.kind));
          const txt = h("div", "stack-1", null, [
            el("div", "num", fmtDate(it.date) + (it.end && it.end !== it.date ? " – " + fmtDate(it.end) : "")),
            el("div", "", it.title),
            el("div", "muted", `${t("k_" + it.kind)} · ${srcLabel(it.source)}`),
          ]);
          li.appendChild(txt);
          ul.appendChild(li);
        });
        sec.appendChild(ul);
        wrap.appendChild(sec);
      });
      if (d.next_after_horizon) wrap.appendChild(el("p", "muted", t("tl_next", fmtDate(d.next_after_horizon.date), d.next_after_horizon.title)));
    }
    root.appendChild(wrap);
  });
}

// ------------------------------------------------------------------ plans
function renderPlans(root, prefill) {
  load(root, () => api(lq("/me/overview")), (d) => {
    const grid = el("div", "layout-2col");
    const main = el("div", "stack-6");
    const side = el("aside", "stack-6");
    grid.appendChild(main); grid.appendChild(side);
    root.appendChild(grid);

    const card = h("section", "card stack-3", null, [el("h1", "section-title", t("goal_title"))]);
    const form = el("form", "");
    form.style.display = "flex"; form.style.gap = "8px"; form.style.flexWrap = "wrap";
    const input = el("input", "field");
    input.type = "text"; input.maxLength = 300; input.placeholder = t("goal_ph");
    input.setAttribute("aria-label", t("goal_title"));
    input.style.flex = "1 1 240px";
    if (prefill) input.value = prefill;
    const send = el("button", "btn btn-primary", t("goal_send"));
    send.type = "submit";
    form.appendChild(input); form.appendChild(send);
    card.appendChild(form);
    const proposal = el("div", "stack-2");
    proposal.setAttribute("aria-live", "polite");
    card.appendChild(proposal);
    card.appendChild(el("p", "muted", t("goal_hint")));

    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      clear(proposal);
      send.disabled = true;
      try {
        const res = await api("/me/goals/parse", { method: "POST", body: { text, lang: state.lang } });
        const p = res && res.proposal;
        if (!p) { proposal.appendChild(el("p", "muted", t("goal_none"))); return; }
        proposal.appendChild(el("p", "", t("goal_sentence", t("gp_" + p.purpose), fmtEur(p.amount), p.keep_accessible)));
        const ok = btn(t("goal_confirm"), "btn-primary");
        const no = btn(t("goal_cancel"), "btn-secondary", () => clear(proposal));
        ok.addEventListener("click", async () => {
          ok.disabled = true; no.disabled = true;
          try {
            await api("/me/goals", { method: "POST", body: { purpose: p.purpose, amount: p.amount, keep_accessible: p.keep_accessible } });
            closePanel();
            toast(t("goal_saved"), "info");
            renderPlans(root);
          } catch (err) { ok.disabled = false; no.disabled = false; toast(t("save_fail") + err.message, "error"); }
        });
        const row = h("div", "", null, [ok, no]);
        row.style.display = "flex"; row.style.gap = "8px";
        proposal.appendChild(row);
      } catch (err) { proposal.appendChild(el("p", "", t("c_load_error") + err.message)); }
      finally { send.disabled = false; }
    });
    main.appendChild(card);
    main.appendChild(allocationSection(d.allocation));

    const gl = h("section", "card stack-3", null, [el("h2", "section-title", t("goal_list"))]);
    const goals = d.goals || [];
    if (!goals.length) gl.appendChild(el("p", "muted", t("side_plans_none")));
    else {
      const ul = el("ul", "stack-3");
      goals.forEach((g) => {
        const label = goalLabel(g);
        const li = h("li", "stack-2", null, [el("div", "num", label)]);
        const row = el("div", "");
        row.style.display = "flex"; row.style.gap = "8px";
        const mutate = async (b, prefillText) => {
          row.querySelectorAll("button").forEach((x) => { x.disabled = true; });
          try {
            await api("/me/goals/" + encodeURIComponent(g.id), { method: "DELETE" });
            closePanel();
            if (!prefillText) toast(t("goal_removed"), "info");
            renderPlans(root, prefillText);
          } catch (err) {
            row.querySelectorAll("button").forEach((x) => { x.disabled = false; });
            toast(t("save_fail") + err.message, "error");
          }
        };
        const edit = btn(t("goal_edit"), "btn-quiet btn-sm");
        edit.setAttribute("aria-label", `${t("goal_edit")}: ${label}`);
        edit.addEventListener("click", () => mutate(edit, g.text || t("goal_edit_text", t("gp_" + g.purpose), fmtEur(g.amount))));
        const rm = btn(t("goal_remove"), "btn-quiet btn-sm");
        rm.setAttribute("aria-label", `${t("goal_remove")}: ${label}`);
        rm.addEventListener("click", () => mutate(rm, null));
        row.appendChild(edit); row.appendChild(rm);
        li.appendChild(row);
        ul.appendChild(li);
      });
      gl.appendChild(ul);
    }
    side.appendChild(gl);
    if (prefill) setTimeout(() => input.focus(), 0);
  });
}

// ------------------------------------------------------------------ data
function renderData(root) {
  load(root, () => api("/me/consents"), (consents) => {
    const wrap = h("div", "stack-6", null, []);
    const sec = h("section", "card stack-4", null, [el("h1", "section-title", t("c_title")), el("p", "muted", t("c_sub"))]);
    [["use_insurance_data", "c_ins", "c_ins_h"], ["use_other_banks", "c_banks", "c_banks_h"], ["marketing", "c_mkt", "c_mkt_h"]].forEach(([key, lk, hk]) => {
      const row = el("label", "");
      row.style.display = "flex"; row.style.gap = "12px"; row.style.alignItems = "flex-start"; row.style.cursor = "pointer";
      const input = document.createElement("input");
      input.type = "checkbox"; input.checked = Boolean(consents[key]);
      input.style.width = "20px"; input.style.height = "20px"; input.style.marginTop = "2px"; input.style.accentColor = "#003665";
      input.addEventListener("change", async () => {
        consents[key] = input.checked;
        input.disabled = true;
        try { await api("/me/consents", { method: "PUT", body: consents }); closePanel(); toast(t("c_saved"), "info"); }
        catch (err) { toast(t("save_fail") + err.message, "error"); input.checked = !input.checked; consents[key] = input.checked; }
        finally { input.disabled = false; }
      });
      row.appendChild(input);
      row.appendChild(h("div", "", null, [el("div", "label", t(lk)), el("div", "muted", t(hk))]));
      sec.appendChild(row);
    });
    sec.appendChild(el("p", "muted", t("c_note")));
    wrap.appendChild(sec);
    wrap.appendChild(h("section", "card stack-2", null, [el("h2", "section-title", t("c_fb_title")), el("p", "", t("c_fb_text"))]));
    const priv = h("section", "card stack-2", null, [el("h2", "section-title", t("c_privacy_title")), el("p", "", t("c_privacy"))]);
    if (!document.querySelector("elevenlabs-convai")) priv.appendChild(el("p", "muted", t("c_voice_note")));
    wrap.appendChild(priv);
    root.appendChild(wrap);
  });
}
