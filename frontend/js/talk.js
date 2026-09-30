// "Praat met Kate": AIR-style chat (question right, short answer + one chart left,
// sources disclosure, follow-up chips, sticky composer). DOM via el()/textContent only.
import { state, t, api, el, clear, icon, fmtEur, fmtDate, toast, registerStrings } from "./core.js";
import * as charts from "./charts.js";
import strings from "./i18n-talk.js";

registerStrings(strings);

const CSS = `
.talk { max-width: 760px; margin: 0 auto; padding: 24px 16px 0; display: flex; flex-direction: column; min-height: calc(100vh - 180px); }
.talk-head { padding-bottom: 16px; border-bottom: 1px solid var(--line); }
.talk-head h1 { font-size: 22px; font-weight: 700; color: var(--navy); }
.talk-sub { color: var(--muted); font-size: 14px; margin-top: 2px; }
.talk-note { color: var(--muted); font-size: 12px; margin-top: 8px; display: flex; gap: 6px; align-items: flex-start; }
.talk-log { flex: 1; display: flex; flex-direction: column; gap: 24px; padding: 24px 0; }
.talk-msg { display: flex; flex-direction: column; gap: 12px; max-width: 100%; }
.talk-msg-user { align-items: flex-end; }
.talk-bubble-user { background: var(--navy); color: #fff; padding: 10px 16px; border-radius: 16px 16px 4px 16px; max-width: 80%; overflow-wrap: anywhere; }
.talk-msg-kate { align-items: flex-start; }
.talk-who { font-size: 12px; font-weight: 700; color: var(--blue-text); letter-spacing: .04em; text-transform: uppercase; }
.talk-text { color: var(--ink); font-size: 16px; line-height: 1.55; max-width: 640px; }
.talk-card { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 16px; width: 100%; box-shadow: var(--shadow); }
.talk-facts { display: flex; flex-wrap: wrap; gap: 8px 24px; margin: 0; }
.talk-facts div { display: flex; flex-direction: column; }
.talk-facts dt { font-size: 12px; color: var(--muted); }
.talk-facts dd { margin: 0; font-weight: 700; color: var(--navy); font-variant-numeric: tabular-nums; }
.talk-tl { list-style: none; margin: 0; padding: 0; }
.talk-tl li { display: grid; grid-template-columns: 96px 1fr; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--line); }
.talk-tl li:last-child { border-bottom: 0; }
.talk-tl-date { font-weight: 700; color: var(--navy); font-variant-numeric: tabular-nums; font-size: 14px; }
.talk-tl-meta { font-size: 12px; color: var(--muted); }
.talk-src { width: 100%; }
.talk-src ul { margin: 4px 0 8px; padding-left: 18px; font-size: 13px; color: var(--muted); }
.talk-src h4 { font-size: 13px; margin-top: 8px; }
.talk-src .micro { color: var(--muted); }
.talk-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.talk-chips .chip { text-align: left; }
.talk-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: flex-end; }
.talk-amount { max-width: 180px; }
.talk-typing { display: inline-flex; gap: 4px; align-items: center; color: var(--muted); font-size: 14px; }
.talk-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--muted); animation: talkblink 1.2s infinite; }
.talk-dot:nth-child(2) { animation-delay: .2s; } .talk-dot:nth-child(3) { animation-delay: .4s; }
@keyframes talkblink { 0%, 80%, 100% { opacity: .25; } 40% { opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .talk-dot { animation: none; } }
.talk-starters { padding-bottom: 16px; }
.talk-starters p { font-size: 13px; color: var(--muted); margin-bottom: 8px; }
.talk-composer { position: sticky; bottom: 0; background: var(--surface); border-top: 1px solid var(--line); padding: 12px 0 16px; display: flex; gap: 8px; align-items: center; z-index: 10; }
.talk-composer .field { flex: 1; }
.tk-preview { border-top: 1px solid var(--line); padding-top: 12px; }
.tk-pv-title { font-size: 16px; font-weight: 700; color: var(--navy); }
.tk-plans { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.tk-plan { background: var(--bg, #F4F7FA); border-radius: 10px; padding: 12px; }
.tk-plan-facts { flex-direction: column; gap: 6px; }
.tk-rec { flex-direction: column; gap: 8px; }
.tk-rec dd { font-weight: 400; color: var(--ink); }
@media (max-width: 560px) { .tk-plans { grid-template-columns: 1fr; } }
.talk-err { color: var(--danger); display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.talk-empty { color: var(--muted); font-size: 14px; }
@media (max-width: 767px) {
  .talk { padding: 16px 16px 0; min-height: auto; }
  .talk-composer { position: fixed; left: 0; right: 0; bottom: calc(63px + env(safe-area-inset-bottom)); padding: 8px 16px; z-index: 29; }
  .talk-log { padding-bottom: 80px; }
  .talk-bubble-user { max-width: 88%; }
  .talk-tl li { grid-template-columns: 80px 1fr; }
}`;

function ensureStyle() {
  if (document.getElementById("talk-style")) return;
  const s = document.createElement("style");
  s.id = "talk-style";
  s.textContent = CSS;
  document.head.appendChild(s);
}

const COLORS = { buffer: "#0B325E", goal: "#00ACEF", remaining: "#9FB7CC" };
const STARTERS = ["tk_starter_1", "tk_starter_2", "tk_starter_3", "tk_starter_4"];

function btn(label, cls, onClick) {
  const b = el("button", "btn " + (cls || "btn-secondary"), label);
  b.type = "button";
  if (onClick) b.addEventListener("click", onClick);
  return b;
}
function lbl(key, fallback) { const v = t(key); return v === key ? (fallback || "") : v; }

export async function renderTalk(root) {
  ensureStyle();
  clear(root);
  let context = null;
  let sending = false;
  let voice = { stt: false, tts: false, mod: null };

  const wrap = el("div", "talk");
  const head = el("header", "talk-head");
  head.append(el("h1", null, t("tk_title")), el("p", "talk-sub", t("tk_sub")));
  const note = el("p", "talk-note");
  note.append(icon("info", 14), el("span", null, t("tk_note")));
  head.appendChild(note);

  const log = el("div", "talk-log");
  log.setAttribute("role", "log");
  log.setAttribute("aria-live", "polite");
  log.setAttribute("aria-label", t("tk_log"));
  const status = el("div", "sr-only");
  status.setAttribute("aria-live", "polite");
  status.setAttribute("role", "status");

  const starters = el("div", "talk-starters");
  starters.appendChild(el("p", null, t("tk_starters")));
  const sc = el("div", "talk-chips");
  STARTERS.forEach((k) => { const c = el("button", "chip", t(k)); c.type = "button"; c.addEventListener("click", () => send(t(k))); sc.appendChild(c); });
  starters.appendChild(sc);

  const form = el("form", "talk-composer");
  form.setAttribute("aria-label", t("tk_input_label"));
  const input = el("input", "field");
  input.type = "text"; input.maxLength = 300; input.autocomplete = "off";
  input.placeholder = t("tk_placeholder");
  input.setAttribute("aria-label", t("tk_input_label"));
  const micSlot = el("span");
  const sendBtn = el("button", "btn btn-primary", t("tk_send"));
  sendBtn.type = "submit";
  form.append(input, micSlot, sendBtn);
  form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });

  wrap.append(head, log, starters, form);
  root.appendChild(wrap);

  function scrollEnd(node) {
    try { node.scrollIntoView({ block: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); } catch (_) {}
  }
  function addUser(text) {
    const m = el("div", "talk-msg talk-msg-user");
    const who = el("span", "sr-only", t("tk_you") + ": ");
    const b = el("div", "talk-bubble-user", text);
    b.prepend(who);
    m.appendChild(b);
    log.appendChild(m);
    scrollEnd(m);
  }
  function typing() {
    const m = el("div", "talk-msg talk-msg-kate");
    const ind = el("div", "talk-typing");
    ind.append(el("span", "talk-dot"), el("span", "talk-dot"), el("span", "talk-dot"), el("span", null, t("tk_typing")));
    m.append(el("span", "talk-who", t("tk_kate")), ind);
    log.appendChild(m);
    status.textContent = t("tk_typing");
    scrollEnd(m);
    return m;
  }
  function addError(message, retry) {
    const m = el("div", "talk-msg talk-msg-kate");
    const box = el("div", "talk-err");
    box.setAttribute("role", "alert");
    box.append(icon("alert", 16), el("span", null, message + (retry && retry.detail ? " (" + retry.detail + ")" : "")));
    if (retry && retry.fn) box.appendChild(btn(t("tk_retry"), "btn-secondary btn-sm", () => { m.remove(); retry.fn(); }));
    m.append(el("span", "talk-who", t("tk_kate")), box);
    log.appendChild(m);
    scrollEnd(m);
  }

  // ---------------------------------------------------------------- charts
  function chartNode(ch) {
    if (!ch || !ch.kind) return null;
    try {
      if (ch.kind === "category_bars") {
        const rows = (ch.rows || []).map((r) => ({ key: r.key, label: r.label, value: r.value }));
        if (typeof charts.categoryBars === "function") return charts.categoryBars(rows, { label: t("tk_spending"), total: ch.total });
        const fig = charts.hBars(rows, { label: t("tk_spending"), unit: "eur" });
        if (ch.total != null) fig.appendChild(el("p", "chart-total num", `${t("tk_total")}: ${fmtEur(ch.total)}`));
        return fig;
      }
      if (ch.kind === "allocation") {
        const segs = (ch.segments || []).map((s) => {
          const k = String(s.key || "");
          const base = k === "buffer" ? "buffer" : k === "remaining" ? "remaining" : "goal";
          const seg = { key: k, label: s.label, value: s.value, color: COLORS[base] };
          if (base === "remaining") seg.pattern = "hatch";
          return seg;
        });
        const fig = charts.allocationBar(segs, { label: t("tk_alloc") + (ch.total != null ? " · " + fmtEur(ch.total) : "") });
        (ch.unfunded || []).forEach((u) => fig.appendChild(el("p", "tag tag-warn",
          lbl("tk_unfunded", "{0}: {1} requested, {2} not covered by savings").replace("{0}", u.label).replace("{1}", fmtEur(u.requested)).replace("{2}", fmtEur(u.shortfall)))));
        return fig;
      }
      if (ch.kind === "timeline") {
        const items = (ch.items || []).map((it) => ({
          ...it, kind_label: lbl("tk_kind_" + it.kind, it.kind), basis_label: lbl("tk_basis_" + it.basis, it.basis), date_label: fmtDate(it.date, "medium"),
        }));
        if (typeof charts.miniTimeline === "function") return charts.miniTimeline(items, { label: t("tk_timeline") });
        const fig = el("figure", "chart");
        fig.appendChild(el("figcaption", null, t("tk_timeline")));
        const ul = el("ul", "talk-tl");
        items.forEach((it) => {
          const li = el("li");
          const body = el("div");
          body.append(el("div", null, it.title || ""), el("div", "talk-tl-meta", `${it.kind_label} · ${it.basis_label}`));
          li.append(el("span", "talk-tl-date", it.date_label), body);
          ul.appendChild(li);
        });
        fig.appendChild(ul);
        return fig;
      }
    } catch (e) { console.error(e); }
    return null;
  }

  function factsNode(facts) {
    if (!facts || !facts.length) return null;
    const dl = el("dl", "talk-facts");
    facts.forEach((f) => {
      const d = el("div");
      const v = f.unit === "eur" ? fmtEur(f.value) : (f.unit === "date" ? fmtDate(f.value, "medium") : String(f.value) + (f.unit && f.unit !== "count" ? " " + f.unit : ""));
      d.append(el("dt", null, f.label), el("dd", null, v));
      dl.appendChild(d);
    });
    return dl;
  }

  function sourcesNode(r) {
    const det = el("details", "details talk-src");
    det.appendChild(el("summary", null, t("tk_sources")));
    const body = el("div");
    if (r.period && r.period.label) body.appendChild(el("p", "small", t("tk_period", r.period.label)));
    if (r.evidence && r.evidence.length) {
      body.appendChild(el("h4", null, t("tk_evidence")));
      const ul = el("ul"); r.evidence.forEach((x) => ul.appendChild(el("li", null, x))); body.appendChild(ul);
    }
    if (r.assumptions && r.assumptions.length) {
      body.appendChild(el("h4", null, t("tk_assumptions")));
      const ul = el("ul"); r.assumptions.forEach((x) => ul.appendChild(el("li", null, x))); body.appendChild(ul);
    }
    const meta = [];
    if (r.as_of) meta.push(t("tk_as_of", fmtDate(r.as_of, "medium")));
    if (r.synthetic !== false) meta.push(t("tk_synthetic"));
    body.appendChild(el("p", "micro", meta.join(" · ")));
    det.appendChild(body);
    return det;
  }

  function chipsNode(sugs) {
    if (!sugs || !sugs.length) return null;
    const box = el("div", "talk-chips");
    box.setAttribute("role", "group");
    box.setAttribute("aria-label", t("tk_followups"));
    sugs.forEach((s) => {
      const c = el("button", "chip", s.label || s.text);
      c.type = "button";
      c.addEventListener("click", () => send(s.text || s.label));
      box.appendChild(c);
    });
    return box;
  }

  function planCol(title, n) {
    const col = el("div", "tk-plan");
    col.appendChild(el("p", "eyebrow", title));
    const dl = el("dl", "talk-facts tk-plan-facts");
    [[lbl("tk_pv_savings", "Savings"), n.savings], [lbl("tk_pv_buffer", "Modeled buffer (assumption)"), n.buffer_covered],
     [lbl("tk_pv_goals", "Reserved for goals"), n.reserved_covered], [lbl("tk_pv_remaining", "Remaining above buffer and goals"), n.remaining]]
      .forEach(([k, v]) => { const d = el("div"); d.append(el("dt", null, k), el("dd", "num", fmtEur(v))); dl.appendChild(d); });
    col.appendChild(dl);
    if (n.shortfall > 0) col.appendChild(el("p", "tag tag-warn", lbl("tk_pv_short", "Not covered by savings: {0}").replace("{0}", fmtEur(n.shortfall))));
    return col;
  }
  function previewNode(pv) {
    const box = el("div", "tk-preview stack-sm");
    box.appendChild(el("h3", "tk-pv-title", lbl("tk_pv_title", "What changes if you confirm?")));
    const grid = el("div", "tk-plans");
    grid.append(planCol(lbl("tk_pv_current", "Current plan"), pv.current), planCol(lbl("tk_pv_proposed", "Proposed plan"), pv.proposed));
    box.appendChild(grid);
    const c = chartNode(pv.proposed.chart);
    if (c) box.appendChild(c);
    const rec = pv.recommendation || {};
    const b = rec.before, a = rec.after;
    const rl = el("dl", "talk-facts tk-rec");
    const row = (k, v) => { const d = el("div"); d.append(el("dt", null, k), el("dd", null, v)); rl.appendChild(d); };
    row(lbl("tk_pv_rec_now", "Kate suggests now"), b ? b.message || b.title : lbl("tk_pv_none", "Nothing"));
    row(lbl("tk_pv_rec_after", "After this plan"), a ? a.message || a.title : lbl("tk_pv_none", "Nothing"));
    box.appendChild(rl);
    box.appendChild(el("p", "small", pv.explanation || ""));
    box.appendChild(el("p", "micro muted", lbl("tk_pv_nothing_saved", "Preview only: nothing is saved and no money moves.") + " " + (pv.assumption || "")));
    return box;
  }

  function proposalNode(p, msgEl, pv) {
    const card = el("div", "talk-card stack-sm");
    card.appendChild(el("p", "eyebrow", t("tk_proposal")));
    card.appendChild(el("p", "num", p.summary || ""));
    let pvSlot = el("div");
    if (pv) pvSlot.appendChild(previewNode(pv));
    card.appendChild(pvSlot);
    const actions = el("div", "talk-actions");
    const lab = el("label", "label-block");
    const id = "tk-amt-" + Math.random().toString(36).slice(2, 8);
    const l = el("span", "label", t("tk_amount")); l.id = id + "-l";
    const amt = el("input", "field talk-amount num");
    amt.type = "number"; amt.min = "1"; amt.step = "1"; amt.inputMode = "numeric";
    amt.value = String(p.amount ?? ""); amt.setAttribute("aria-labelledby", id + "-l");
    lab.append(l, amt);
    const err = el("p", "form-error");
    err.setAttribute("aria-live", "polite");
    const ok = btn(lbl("tk_apply", t("tk_confirm")), "btn-primary");
    const no = btn(lbl("tk_keep", t("tk_cancel")), "btn-secondary");
    let pvTimer = null;
    amt.addEventListener("input", () => {
      clearTimeout(pvTimer);
      pvTimer = setTimeout(async () => {
        const amount = Number(amt.value);
        if (!Number.isFinite(amount) || amount <= 0 || amount > 1000000) return;
        try {
          const next = await api("/me/talk/goal/preview", { method: "POST", lang: true, body: { purpose: p.purpose, amount, keep_accessible: p.keep_accessible !== false } });
          const slot = el("div"); slot.appendChild(previewNode(next)); pvSlot.replaceWith(slot); pvSlot = slot;
        } catch (_) { /* keep the last preview */ }
      }, 350);
    });
    actions.append(lab, ok, no);
    card.append(actions, err);
    const done = () => { ok.disabled = true; no.disabled = true; amt.disabled = true; };
    no.addEventListener("click", () => {
      done();
      card.appendChild(el("p", "muted small", t("tk_canceled")));
      status.textContent = t("tk_canceled");
      input.focus();
    });
    ok.addEventListener("click", async () => {
      const amount = Number(amt.value);
      if (!Number.isFinite(amount) || amount <= 0) { err.textContent = t("tk_amount_invalid"); amt.focus(); return; }
      err.textContent = "";
      done();
      const ind = typing();
      try {
        const r = await api("/me/talk/goal/confirm", { method: "POST", lang: true, body: { purpose: p.purpose, amount, keep_accessible: p.keep_accessible !== false } });
        ind.remove();
        addKate(r);
      } catch (e) {
        ind.remove();
        ok.disabled = false; no.disabled = false; amt.disabled = false;
        err.textContent = t("tk_error") + " " + (e.message || "");
      }
      input.focus();
    });
    return card;
  }

  // one answer plays at a time; a failed voice call never removes the text answer
  let stopPlayback = null;
  async function say(text) {
    try { if (stopPlayback) stopPlayback(); } catch (_) {}
    stopPlayback = null;
    try { stopPlayback = await voice.mod.speak(text, state.lang); }
    catch (e) { console.warn("voice playback failed", e && e.message); toast(lbl("tk_voice_fail", "Spoken answer unavailable; the text answer is shown."), "warn"); }
  }
  function releaseVoice() {
    try { if (stopPlayback) stopPlayback(); } catch (_) {}
    stopPlayback = null;
    try { if (voice.mic && voice.mic.stop) voice.mic.stop(); } catch (_) {}
  }
  const leave = () => { if (!document.body.contains(wrap)) { releaseVoice(); window.removeEventListener("hashchange", leave); window.removeEventListener("kate:logout", releaseVoice); } };
  window.addEventListener("hashchange", () => setTimeout(leave, 0));
  window.addEventListener("kate:logout", releaseVoice);
  new MutationObserver((_, obs) => { if (!document.body.contains(wrap)) { releaseVoice(); obs.disconnect(); } }).observe(root, { childList: true });

  function addKate(r) {
    if (!r || typeof r !== "object") { addError(t("tk_error")); return; }
    if (r.context) context = r.context;
    const m = el("div", "talk-msg talk-msg-kate");
    m.appendChild(el("span", "talk-who", t("tk_kate")));
    const txt = el("p", "talk-text", r.message || "");
    m.appendChild(txt);
    if (voice.tts && voice.mod && typeof voice.mod.speak === "function" && r.message) {
      const sp = btn(t("tk_listen"), "btn-quiet btn-sm", () => say(r.message));
      sp.prepend(icon("play", 14));
      m.appendChild(sp);
      if (voice.speakNext) {  // the question was spoken: answer out loud, like a voice assistant
        voice.speakNext = false;
        say(r.message);
      }
    }
    const chart = chartNode(r.chart);
    const facts = factsNode(r.facts);
    if (chart || facts) {
      const card = el("div", "talk-card stack-md");
      if (chart) card.appendChild(chart);
      if (facts) card.appendChild(facts);
      m.appendChild(card);
    }
    if (r.intent === "goal_proposal" && r.proposal) m.appendChild(proposalNode(r.proposal, m, r.preview));
    m.appendChild(sourcesNode(r));
    const chips = chipsNode(r.suggestions);
    if (chips) m.appendChild(chips);
    log.appendChild(m);
    status.textContent = "";
    scrollEnd(m);
  }

  async function send(raw) {
    const text = String(raw || "").trim().slice(0, 300);
    if (!text || sending) return;
    sending = true;
    sendBtn.disabled = true;
    input.value = "";
    starters.hidden = true;
    const empty = log.querySelector(".talk-empty"); if (empty) empty.remove();
    addUser(text);
    const ind = typing();
    try {
      const body = { text };
      if (context) body.context = context;
      const r = await api("/me/talk", { method: "POST", lang: true, body });
      ind.remove();
      addKate(r);
    } catch (e) {
      ind.remove();
      status.textContent = t("tk_error");
      addError(t("tk_error"), { detail: e && e.message, fn: () => { log.lastElementChild && log.lastElementChild.classList.contains("talk-msg-user") && log.lastElementChild.remove(); send(text); } });
    } finally {
      sending = false;
      sendBtn.disabled = false;
      input.focus();
    }
  }

  // ---------------------------------------------------------------- briefing
  async function loadBriefing() {
    const ind = typing();
    try {
      const r = await api("/me/talk/briefing", { lang: true });
      ind.remove();
      addKate(r);
    } catch (e) {
      ind.remove();
      addError(t("tk_briefing_error"), { detail: e && e.message, fn: loadBriefing });
      if (!log.querySelector(".talk-empty")) log.appendChild(el("p", "talk-empty", t("tk_empty")));
    }
  }

  // ---------------------------------------------------------------- voice (optional)
  async function setupVoice() {
    try {
      const vs = await api("/me/talk/voice-status");
      if (!vs || (!vs.stt && !vs.tts)) return;
      const mod = await import("./voice.js");
      voice = { stt: !!vs.stt, tts: !!vs.tts, mod };
      if (voice.stt && typeof mod.createMicButton === "function") {
        const mic = mod.createMicButton({
          lang: state.lang,
          // show the transcript for a quick check (amounts!) instead of sending blindly; Enter sends
          // contract: onTranscript({ text, amount_candidates }). Only the text goes into the input, for review;
          // amounts are never applied by themselves (a goal still needs explicit confirmation).
          onTranscript(result) {
            const text = result && typeof result.text === "string" ? result.text.trim().slice(0, 300) : "";
            if (!text) { toast(lbl("tk_no_speech", "No speech recognised. Try again or type your question."), "warn"); return; }
            input.value = text; input.focus(); voice.speakNext = true; toast(t("tk_check_transcript"));
          },
          onState(s, message) { if (s === "error") toast(message || t("tk_mic_error"), "warn"); },
        });
        if (mic instanceof Node) { micSlot.appendChild(mic); voice.mic = mic; }
      }
    } catch (_) { /* voice optional: text still works */ }
  }

  await Promise.all([setupVoice(), loadBriefing()]);
  input.focus();
}
