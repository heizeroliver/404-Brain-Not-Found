// Kate Talk push-to-talk: record a short clip, transcribe server-side, optional spoken answers.
// The clip is sent once to /me/talk/transcribe and never kept in the browser. textContent only.
import { api, API_BASE, state, icon } from "./core.js";

const MAX_MS = 15000;
const MIME_PREFS = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav"];
const LABELS = {
  nl: { idle: "Spreek", listening: "Luisteren… tik om te stoppen", transcribing: "Omzetten…", error: "Microfoon niet beschikbaar", denied: "Geef toegang tot je microfoon om te spreken.", unsupported: "Opnemen wordt niet ondersteund in deze browser.", failed: "Omzetten mislukt. Typ je vraag." },
  en: { idle: "Speak", listening: "Listening… tap to stop", transcribing: "Transcribing…", error: "Microphone unavailable", denied: "Allow microphone access to speak.", unsupported: "Recording is not supported in this browser.", failed: "Transcription failed. Please type your question." },
  fr: { idle: "Parler", listening: "À l'écoute… touchez pour arrêter", transcribing: "Transcription…", error: "Micro indisponible", denied: "Autorisez l'accès au micro pour parler.", unsupported: "L'enregistrement n'est pas pris en charge par ce navigateur.", failed: "Transcription échouée. Tapez votre question." },
};
function L(lang, key) { return (LABELS[lang] || LABELS.en)[key] || LABELS.en[key]; }
function curLang(lang) { return lang || state.lang || "nl"; }

export async function voiceStatus() {
  try {
    return await api("/me/talk/voice-status", { lang: true });
  } catch (_) {
    return { stt: false, tts: false };
  }
}

function pickMime() {
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return "";
  return MIME_PREFS.find((m) => MediaRecorder.isTypeSupported(m)) || "";
}

async function postAudio(blob, lang) {
  const headers = { Accept: "application/json", "Content-Type": (blob.type || "audio/webm") };
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  const res = await fetch(API_BASE + "/me/talk/transcribe?lang=" + encodeURIComponent(lang), { method: "POST", headers, body: blob });
  if (res.status === 401 && state.token) {
    window.dispatchEvent(new CustomEvent("kate:logout", { detail: { reason: "expired" } }));
    throw new Error("Session expired");
  }
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const err = new Error((data && typeof data.detail === "string") ? data.detail : ("HTTP " + res.status));
    err.status = res.status; throw err;
  }
  return { text: String((data && data.text) || ""), amount_candidates: Array.isArray(data && data.amount_candidates) ? data.amount_candidates : [] };
}

export function createMicButton({ onTranscript, onState, lang } = {}) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn btn-secondary";
  const label = document.createElement("span");
  btn.append(icon("mic"), label);

  let recorder = null, stream = null, chunks = [], timer = null, phase = "idle";

  function set(next, message) {
    phase = next;
    const lg = curLang(lang);
    const text = next === "error" ? (message || L(lg, "error")) : L(lg, next);
    label.textContent = next === "error" ? L(lg, "error") : text;
    btn.setAttribute("aria-label", text);
    btn.setAttribute("aria-pressed", next === "listening" ? "true" : "false");
    btn.disabled = next === "transcribing";
    if (onState) onState(next, message);
  }

  function stopTracks() {
    if (timer) { clearTimeout(timer); timer = null; }
    if (stream) { stream.getTracks().forEach((tr) => { try { tr.stop(); } catch (_) {} }); stream = null; }
  }

  function stop() {
    if (recorder && recorder.state !== "inactive") { try { recorder.stop(); } catch (_) { stopTracks(); } }
    else stopTracks();
  }

  async function start() {
    const lg = curLang(lang);
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === "undefined") {
      set("error", L(lg, "unsupported")); return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      stopTracks();
      set("error", (e && (e.name === "NotAllowedError" || e.name === "SecurityError")) ? L(lg, "denied") : L(lg, "unsupported"));
      return;
    }
    chunks = [];
    const mimeType = pickMime();
    try {
      recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    } catch (_) {
      stopTracks(); set("error", L(lg, "unsupported")); return;
    }
    recorder.ondataavailable = (ev) => { if (ev.data && ev.data.size) chunks.push(ev.data); };
    recorder.onerror = () => { stopTracks(); recorder = null; chunks = []; set("error", L(lg, "failed")); };
    recorder.onstop = async () => {
      const type = ((recorder && recorder.mimeType) || mimeType || "audio/webm").split(";")[0];
      stopTracks();
      recorder = null;
      const blob = new Blob(chunks, { type });
      chunks = [];
      if (!blob.size) { set("idle"); return; }
      set("transcribing");
      try {
        const result = await postAudio(blob, lg);
        set("idle");
        if (onTranscript) onTranscript(result);
      } catch (e) {
        set("error", (e && e.message) || L(lg, "failed"));
      }
    };
    recorder.start();
    timer = setTimeout(stop, MAX_MS);
    set("listening");
  }

  btn.addEventListener("click", () => {
    if (phase === "listening") stop();
    else if (phase !== "transcribing") start();
  });
  // release the microphone if the button leaves the page or the tab is closed
  window.addEventListener("pagehide", stop);
  btn.stop = stop;
  set("idle");
  return btn;
}

export async function speak(text, lang) {
  const lg = curLang(lang);
  const headers = { Accept: "audio/mpeg", "Content-Type": "application/json" };
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  const res = await fetch(API_BASE + "/me/talk/speak?lang=" + encodeURIComponent(lg), {
    method: "POST", headers, body: JSON.stringify({ text: String(text || "").slice(0, 400) }),
  });
  if (!res.ok) { const err = new Error("Voice not available"); err.status = res.status; throw err; }
  const url = URL.createObjectURL(await res.blob());
  const audio = new Audio(url);
  const cleanup = () => { try { URL.revokeObjectURL(url); } catch (_) {} };
  audio.addEventListener("ended", cleanup, { once: true });
  audio.addEventListener("error", cleanup, { once: true });
  await audio.play();
  return () => { try { audio.pause(); } catch (_) {} cleanup(); };
}
