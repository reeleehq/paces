// The ask page (paces issue #10). Two layers: a pure core (time format, snap,
// answers) that node tests import, and a DOM layer that runs only in a browser.
"use strict";

// ── pure core ─────────────────────────────────────────────────────────────

/** Seconds as paces' wire decimal: 3 places, trailing zeros dropped ("95.8"). */
function timeStr(t) {
  const text = Number(t).toFixed(3).replace(/\.?0+$/, "");
  return text === "-0" || text === "" ? "0" : text;
}

/** The nearest target within windowS of t, else t itself. */
function snap(t, targets, windowS) {
  let best = null;
  for (const target of targets) {
    const d = Math.abs(target - t);
    if (d <= windowS && (best === null || d < Math.abs(best - t))) best = target;
  }
  return best === null ? { t, snapped: false } : { t: best, snapped: true };
}

/**
 * The answers JSON from the proposal and what the human did.
 * state: { k, struck: [cut strings], added: [time strings], absent: [step ids], at }
 * Order matters (the log replays in order): absent steps first, judged on the
 * proposed layout; then struck cuts (merge); then added cuts (split).
 */
function buildAnswers(proposal, state) {
  const meta = {};
  if (proposal.author) meta.author = proposal.author;
  if (state.at) meta.at = state.at;
  const corrections = [];
  for (const step of proposal.steps) {
    if (!state.absent.includes(step.id) || !step.spans.length) continue;
    const [a, b] = step.spans[0].map(Number);
    corrections.push({ verb: "absent", anchorT: timeStr((a + b) / 2), stepId: step.id, ...meta });
  }
  for (const cut of proposal.cuts) {
    if (state.struck.includes(cut)) corrections.push({ verb: "merge", anchorT: cut, ...meta });
  }
  const added = [...new Set(state.added)].sort((x, y) => Number(x) - Number(y));
  for (const t of added) corrections.push({ verb: "split", anchorT: t, ...meta });
  const k = Number.isInteger(state.k) && state.k > 0 ? state.k : null;
  return {
    kind: "PacesAskAnswers",
    k,
    corrections,
    proposal: { method: proposal.method, media: proposal.media, title: proposal.title },
  };
}

/** Each cut the page lists: proposed (maybe struck) and added, in time order. */
function cutRows(proposal, state) {
  const rows = proposal.cuts.map((t) => ({ t, kind: state.struck.includes(t) ? "struck" : "proposed" }));
  for (const t of new Set(state.added)) if (!proposal.cuts.includes(t)) rows.push({ t, kind: "added" });
  return rows.sort((a, b) => Number(a.t) - Number(b.t));
}

// ── the draft store: the one place the page touches browser storage ───────

function draftStore(key) {
  return {
    load() {
      try { return JSON.parse(window.localStorage.getItem(key) || "null"); } catch { return null; }
    },
    save(value) {
      try { window.localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode: keep going */ }
    },
    clear() {
      try { window.localStorage.removeItem(key); } catch { /* ignore */ }
    },
  };
}

function draftKey(proposal) {
  const text = JSON.stringify([proposal.title, proposal.media, proposal.cuts, proposal.steps.map((s) => s.id)]);
  let h = 0;
  for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) | 0;
  return `paces-ask:${(h >>> 0).toString(36)}`;
}

// ── the page ──────────────────────────────────────────────────────────────

function mmss(t) {
  const s = Number(t);
  const m = Math.floor(s / 60);
  return `${m}:${(s - m * 60).toFixed(1).padStart(4, "0")}`;
}

function startPage(doc) {
  const $ = (id) => doc.getElementById(id);
  const proposal = JSON.parse($("proposal").textContent);
  const store = draftStore(draftKey(proposal));
  const fresh = () => ({ k: proposal.k, struck: [], added: [], absent: [], at: "" });
  let state = Object.assign(fresh(), store.load() || {});
  let lastAdded = null;

  const status = (text) => { $("status").textContent = text; };
  const touch = () => { state.at = new Date().toISOString(); store.save(state); render(); };

  // Pressed feedback in the same frame as the press (the feedback principle).
  doc.addEventListener("pointerdown", (e) => {
    const b = e.target.closest("button");
    if (b) b.setAttribute("data-pressed", "");
  });
  for (const type of ["pointerup", "pointercancel", "pointerleave"]) {
    doc.addEventListener(type, () => doc.querySelectorAll("button[data-pressed]").forEach((b) => b.removeAttribute("data-pressed")), true);
  }

  const methodBits = [proposal.method && `proposed by ${proposal.method}`, ...proposal.flags.filter((f) => !f.startsWith("try:"))];
  $("method").textContent = methodBits.filter(Boolean).join(" · ");
  $("k-evidence").textContent = proposal.kEvidence;
  if (store.load()) {
    $("restored").hidden = false;
    $("restored-text").textContent = `Picked up where you left off${state.at ? ` (${new Date(state.at).toLocaleString()})` : ""}.`;
  }
  $("start-over").addEventListener("click", () => {
    store.clear(); state = fresh(); $("restored").hidden = true; render(); status("Started over.");
  });

  $("k").value = state.k ?? "";
  $("k").addEventListener("input", (e) => {
    const n = Number.parseInt(e.target.value, 10);
    state.k = Number.isInteger(n) && n > 0 ? n : null;
    touch();
  });

  // Media: the proposal's own, or a file from this device.
  const video = $("video");
  const showMedia = (src) => {
    video.src = src; $("player").hidden = false; $("tap").disabled = false;
    $("no-media-text").textContent = "Or open a copy from this device:";
  };
  if (proposal.media && !/youtu\.?be/.test(proposal.media)) showMedia(proposal.media);
  video.addEventListener("error", () => {
    $("player").hidden = true; $("tap").disabled = true;
    status("This browser cannot play that media here. Open the file from this device instead.");
  });
  $("file").addEventListener("change", (e) => {
    const file = e.target.files && e.target.files[0];
    if (file) { showMedia(URL.createObjectURL(file)); status(`Opened ${file.name}.`); }
  });

  const targets = proposal.snap.targets.map(Number);
  const windowS = Number(proposal.snap.windowS);
  const tap = () => {
    if ($("tap").disabled) return;
    const { t, snapped } = snap(video.currentTime, targets, windowS);
    const key = timeStr(t);
    if (proposal.cuts.includes(key)) {
      state.struck = state.struck.filter((c) => c !== key);
      status(`Kept the proposed cut at ${mmss(key)}.`);
    } else if (!state.added.includes(key)) {
      state.added.push(key);
      status(`Cut at ${mmss(key)}${snapped ? " (snapped)" : ""}.`);
    }
    lastAdded = key;
    touch();
  };
  $("tap").addEventListener("click", tap);
  doc.addEventListener("keydown", (e) => {
    const typing = e.target.closest && e.target.closest("input, textarea");
    if (e.code === "Space" && !typing && !$("player").hidden) { e.preventDefault(); tap(); }
  });

  const button = (label, onClick, extra = {}) => {
    const b = doc.createElement("button");
    b.type = "button"; b.textContent = label;
    Object.assign(b, extra);
    b.addEventListener("click", onClick);
    return b;
  };
  const seek = (t) => () => { if (!$("player").hidden) { video.currentTime = Number(t); video.play(); } };

  function renderCuts() {
    const list = $("cuts");
    list.replaceChildren();
    for (const row of cutRows(proposal, state)) {
      const li = doc.createElement("li");
      li.className = row.kind + (row.t === lastAdded ? " fresh" : "");
      li.append(button(mmss(row.t), seek(row.t), { className: "time link", title: "Play from here" }));
      const label = doc.createElement("span");
      label.className = "grow muted small";
      label.textContent = { proposed: "proposed", struck: "not a cut", added: "added by you" }[row.kind];
      li.append(label);
      if (row.kind === "added") {
        li.append(button("Remove", () => { state.added = state.added.filter((t) => t !== row.t); status(`Removed the cut at ${mmss(row.t)}.`); touch(); }));
      } else {
        const struck = row.kind === "struck";
        li.append(button(struck ? "Keep it" : "Not a cut", () => {
          state.struck = struck ? state.struck.filter((t) => t !== row.t) : [...state.struck, row.t];
          status(struck ? `Kept the cut at ${mmss(row.t)}.` : `The cut at ${mmss(row.t)} will be merged.`);
          touch();
        }, { "aria-pressed": String(struck) }));
      }
      list.append(li);
    }
    if (!list.children.length) {
      const li = doc.createElement("li");
      li.className = "muted"; li.textContent = "No cuts yet. Tap along with the video to add them.";
      list.append(li);
    }
  }

  function renderSteps() {
    const list = $("steps");
    list.replaceChildren();
    for (const step of proposal.steps) {
      const li = doc.createElement("li");
      const label = doc.createElement("label");
      label.className = "grow";
      const box = doc.createElement("input");
      box.type = "checkbox";
      box.checked = state.absent.includes(step.id);
      box.addEventListener("change", () => {
        state.absent = box.checked ? [...state.absent, step.id] : state.absent.filter((id) => id !== step.id);
        touch();
      });
      const span = step.spans[0];
      label.append(box, ` ${step.name || "(unnamed)"} `);
      const when = doc.createElement("span");
      when.className = "muted small";
      when.textContent = span ? `${mmss(span[0])}–${mmss(span[1])} · not in this video` : "not in this video";
      label.append(when);
      li.append(label);
      list.append(li);
    }
    if (!proposal.steps.length) {
      const li = doc.createElement("li");
      li.className = "muted"; li.textContent = "No steps were proposed.";
      list.append(li);
    }
  }

  const answersText = () => JSON.stringify(buildAnswers(proposal, state), null, 2);
  function render() {
    renderCuts();
    renderSteps();
    $("answers").value = answersText();
  }

  $("download").addEventListener("click", () => {
    const url = URL.createObjectURL(new Blob([answersText() + "\n"], { type: "application/json" }));
    const a = doc.createElement("a");
    a.href = url; a.download = "answers.json";
    doc.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    status("Downloaded answers.json.");
  });
  $("copy").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(answersText()); status("Copied the answers."); }
    catch { $("answers").closest("details").open = true; $("answers").select(); status("Select-all is done: copy with your keyboard."); }
  });

  render();
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { timeStr, snap, buildAnswers, cutRows };
} else if (typeof document !== "undefined") {
  startPage(document);
}
