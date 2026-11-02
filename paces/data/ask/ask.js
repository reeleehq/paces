// The ask page (paces issue #10). Two layers: a pure core — time format, snap,
// the reducer that makes every state decision, and the answers — that node
// tests import, and a DOM layer that only dispatches actions and renders.
"use strict";

// ── pure core ─────────────────────────────────────────────────────────────

const TIME_PLACES = 3;

/**
 * Seconds as paces' wire decimal, exactly as Python's
 * decimal_str(t, places=3) writes it for t >= 0: 3 places, trailing zeros
 * dropped ("95.8"). toFixed breaks an exact binary tie (10.0625) upward;
 * Python's format rounds it to even ("10.062"), so a tie is corrected here.
 * toFixed(20) tells a tie apart: a double >= 0.0005 is never within 5e-21
 * of a tie without being on it.
 */
function timeStr(t) {
  const x = Number(t);
  let text = x.toFixed(TIME_PLACES);
  if (x >= 0 && /\.\d{3}50*$/.test(x.toFixed(20)) && /[13579]$/.test(text)) {
    const digits = (BigInt(text.replace(".", "")) - 1n).toString().padStart(TIME_PLACES + 1, "0");
    text = `${digits.slice(0, -TIME_PLACES)}.${digits.slice(-TIME_PLACES)}`;
  }
  text = text.replace(/0+$/, "").replace(/\.$/, "");
  return text === "-0" || text === "" ? "0" : text;
}

/** m:ss.s for people; rounds first, so 59.96 s is "1:00.0", never "0:60.0". */
function mmss(t) {
  const tenths = Math.round(Number(t) * 10);
  const m = Math.floor(tenths / 600);
  return `${m}:${((tenths - m * 600) / 10).toFixed(1).padStart(4, "0")}`;
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

const byTime = (a, b) => Number(a) - Number(b);
const sortedUnique = (times) => [...new Set(times)].sort(byTime);
const stepLabel = (step) => `“${step.name || step.id}”`;

/**
 * What the human has said so far. k is the proposal's guess until the human
 * touches it (kTouched); only a touched k is sent. duration is the media's,
 * once known (a time string). previous is what Start over replaced, for Undo.
 */
function freshState(proposal) {
  return { k: proposal.k, kTouched: false, struck: [], added: [], absent: [], at: "", duration: null, previous: null };
}

/**
 * Absent steps are keyed by their row in the proposal, never by id: two rows
 * may share an id (a repeated name), and each is its own occurrence.
 */
const rowKey = (index) => String(index);
const isAbsent = (state, index) => state.absent.includes(rowKey(index));

/** The spans, as numbers, of the steps marked not in the media. */
function absentSpans(proposal, state) {
  return proposal.steps
    .filter((step, i) => isAbsent(state, i))
    .flatMap((step) => step.spans.map((span) => span.map(Number)));
}

/** Every cut still standing, as numbers: unstruck proposed, added, and the ends. */
function liveCuts(proposal, state) {
  const ends = proposal.extent ? proposal.extent : ["0", ...(state.duration ? [state.duration] : [])];
  return [...ends, ...proposal.cuts.filter((c) => !state.struck.includes(c)), ...state.added].map(Number);
}

function nearest(values, t) {
  let best = null;
  for (const v of values) if (best === null || Math.abs(v - t) < Math.abs(best - t)) best = v;
  return best === null ? null : { t: best, gap: Math.abs(best - t) };
}

const same = (state, message = "") => ({ state, message });

// One rule per action: (proposal, state, action) -> { state, message, fresh? }.
// A refusal returns the same state and says why.
const RULES = {
  tap(p, s, { t: raw }) {
    // M1: a struck cut is not a snap target, so strike + tap = move it.
    const targets = p.snap.targets.filter((c) => !s.struck.includes(c)).map(Number);
    const { t: snappedT, snapped } = snap(Number(raw), targets, Number(p.snap.windowS));
    const key = timeStr(snappedT);
    const t = Number(key);
    const at = mmss(key);
    if (p.cuts.includes(key)) {
      if (!s.struck.includes(key)) return same(s, `There is already a cut at ${at}.`);
      return { state: { ...s, struck: s.struck.filter((c) => c !== key) }, message: `Kept the proposed cut at ${at}.` };
    }
    if (p.extent) {
      const [lo, hi] = p.extent.map(Number);
      if (t < lo || t > hi) {
        return same(s, `Not added: ${at} is outside the part being checked (${mmss(lo)}–${mmss(hi)}).`);
      }
    }
    const inside = absentSpans(p, s).find(([a, b]) => a < t && t < b);
    if (inside) {
      return same(s, `Not added: ${at} is inside a step you marked as not in the video (${mmss(inside[0])}–${mmss(inside[1])}).`);
    }
    const near = nearest(liveCuts(p, s), t);
    if (near && near.gap === 0) return same(s, `There is already a cut at ${at}.`);
    if (near && near.gap < Number(p.minStepS)) {
      return same(s, `Not added: ${at} is within ${p.minStepS} s of the cut at ${mmss(near.t)}.`);
    }
    return { state: { ...s, added: [...s.added, key] }, message: `Cut at ${at}${snapped ? " (snapped)" : ""}.`, fresh: key };
  },

  strike(p, s, { cut }) {
    if (!p.cuts.includes(cut) || s.struck.includes(cut)) return same(s);
    const t = Number(cut);
    const border = p.steps.find(
      (step, i) => isAbsent(s, i) && step.spans.some((span) => span.map(Number).includes(t)),
    );
    if (border) {
      return same(s, `The cut at ${mmss(cut)} borders ${stepLabel(border)}, which you marked as not in the video. Untick that first.`);
    }
    return { state: { ...s, struck: [...s.struck, cut] }, message: `The cut at ${mmss(cut)} will be merged.` };
  },

  keep(p, s, { cut }) {
    if (!s.struck.includes(cut)) return same(s);
    const near = nearest(s.added.map(Number), Number(cut));
    if (near && near.gap < Number(p.minStepS)) {
      return same(s, `The cut at ${mmss(cut)} stays merged: you added one at ${mmss(near.t)}, within ${p.minStepS} s of it. Remove that one first.`);
    }
    return { state: { ...s, struck: s.struck.filter((c) => c !== cut) }, message: `Kept the cut at ${mmss(cut)}.` };
  },

  remove(p, s, { cut }) {
    if (!s.added.includes(cut)) return same(s);
    return { state: { ...s, added: s.added.filter((c) => c !== cut) }, message: `Removed the cut at ${mmss(cut)}.` };
  },

  absent(p, s, { index, on }) {
    const step = p.steps[index];
    const key = rowKey(index);
    if (!step) return same(s);
    if (!on) {
      if (!s.absent.includes(key)) return same(s);
      return { state: { ...s, absent: s.absent.filter((k) => k !== key) }, message: `${stepLabel(step)} is back in.` };
    }
    if (s.absent.includes(key)) return same(s);
    if (!step.spans.length) return same(s, `${stepLabel(step)} has no time in this video to mark.`);
    const spans = step.spans.map((span) => span.map(Number));
    const struck = s.struck.find((c) => spans.some((span) => span.includes(Number(c))));
    if (struck) {
      return same(s, `${stepLabel(step)} borders the cut at ${mmss(struck)}, which you marked “not a cut”. Keep that cut first.`);
    }
    const added = s.added.find((c) => spans.some(([a, b]) => a < Number(c) && Number(c) < b));
    if (added) return same(s, `You added a cut at ${mmss(added)} inside ${stepLabel(step)}. Remove it first.`);
    return { state: { ...s, absent: [...s.absent, key] }, message: `${stepLabel(step)} will be marked as not in the video.` };
  },

  setK(p, s, { value }) {
    const n = Number.parseInt(value, 10);
    return { state: { ...s, k: Number.isInteger(n) && n > 0 ? n : null, kTouched: true } };
  },

  startOver(p, s) {
    const { previous, ...kept } = s;
    return { state: { ...freshState(p), duration: s.duration, previous: kept }, message: "Started over." };
  },

  undoStartOver(p, s) {
    if (!s.previous) return same(s);
    return { state: { ...s.previous, previous: null }, message: "Restored your answers." };
  },

  duration(p, s, { seconds }) {
    const d = Number(seconds);
    if (!Number.isFinite(d) || d <= 0 || timeStr(d) === s.duration) return same(s);
    const past = s.added.filter((t) => Number(t) >= d);
    const message = past.length
      ? `${past.length} of your cuts lie past the end of this media (${mmss(d)}) and will not be sent.`
      : "";
    return { state: { ...s, duration: timeStr(d) }, message };
  },
};

// Actions that record a fact about the media, not something the human said:
// they neither stamp the time nor close the Undo of a Start over.
const PASSIVE = new Set(["duration"]);

/**
 * The page's one state transition: (proposal, state, action) -> { state,
 * message, fresh }. message is what the status line says ("" for nothing);
 * fresh is the cut just added, for a one-time highlight. action.at (an ISO
 * time) stamps a change. Any change other than Start over closes its Undo.
 */
function reduce(proposal, state, action) {
  const rule = RULES[action.type];
  if (!rule) throw new Error(`unknown action type ${JSON.stringify(action.type)}`);
  const out = { message: "", fresh: null, ...rule(proposal, state, action) };
  if (out.state !== state && !PASSIVE.has(action.type)) {
    out.state = { ...out.state, at: action.at || out.state.at };
    if (action.type !== "startOver") out.state.previous = null;
  }
  return out;
}

/**
 * The answers JSON from the proposal and what the human did.
 * Order matters (the log replays in order): absent steps first, judged on the
 * proposed layout; then struck cuts (merge); then added cuts (split). With no
 * extent (nothing was proposed), the taps are the boundaries themselves:
 * 0, the taps, and the media's end.
 */
function buildAnswers(proposal, state) {
  const meta = {};
  if (proposal.author) meta.author = proposal.author;
  if (state.at) meta.at = state.at;
  const k = state.kTouched && Number.isInteger(state.k) && state.k > 0 ? state.k : null;
  const answers = { kind: proposal.answersKind, version: proposal.version, k };
  const end = state.duration ? Number(state.duration) : Infinity; // unknown: keep all
  const added = sortedUnique(state.added).filter((t) => Number(t) < end);
  const corrections = [];
  if (!proposal.extent) {
    const last = added.length ? Number(added[added.length - 1]) : 0;
    const end = state.duration && Number(state.duration) > last ? [state.duration] : [];
    const cuts = sortedUnique(["0", ...added, ...end]);
    if (added.length && cuts.length >= 2) answers.boundaries = cuts;
  } else {
    for (const [i, step] of proposal.steps.entries()) {
      if (!isAbsent(state, i) || !step.spans.length) continue;
      const [a, b] = step.spans[0].map(Number);
      corrections.push({ verb: "absent", anchorT: timeStr((a + b) / 2), stepId: step.id, ...meta });
    }
    for (const cut of proposal.cuts) {
      if (state.struck.includes(cut)) corrections.push({ verb: "merge", anchorT: cut, ...meta });
    }
    for (const t of added) corrections.push({ verb: "split", anchorT: t, ...meta });
  }
  answers.corrections = corrections;
  answers.proposal = { method: proposal.method, media: proposal.media, title: proposal.title };
  return answers;
}

/** Each cut the page lists: proposed (maybe struck) and added, in time order. */
function cutRows(proposal, state) {
  const rows = proposal.cuts.map((t) => ({ t, kind: state.struck.includes(t) ? "struck" : "proposed" }));
  for (const t of new Set(state.added)) if (!proposal.cuts.includes(t)) rows.push({ t, kind: "added" });
  return rows.sort((a, b) => byTime(a.t, b.t));
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
  };
}

function draftKey(proposal) {
  const text = JSON.stringify([proposal.title, proposal.media, proposal.cuts, proposal.steps.map((s) => s.id)]);
  let h = 0;
  for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) | 0;
  return `paces-ask:${(h >>> 0).toString(36)}`;
}

// ── the page: dispatch and render, no decisions ───────────────────────────

/** How long the status line offers to undo a Start over. */
const UNDO_MS = 15000;

function startPage(doc) {
  const $ = (id) => doc.getElementById(id);
  const proposal = JSON.parse($("proposal").textContent);
  const store = draftStore(draftKey(proposal));
  const saved = store.load();
  let state = Object.assign(freshState(proposal), saved || {});
  let fresh = null; // the cut just added: highlighted on the next render only
  let undoOpen = false;
  let undoTimer = null;
  const video = $("video");
  const tapButton = $("tap");

  const say = (text) => { $("status-text").textContent = text; };
  const syncK = () => { $("k").value = state.k ?? ""; };
  function dispatch(action) {
    const out = reduce(proposal, state, { ...action, at: new Date().toISOString() });
    if (out.message) say(out.message);
    if (out.state !== state) { state = out.state; store.save(state); }
    fresh = out.fresh;
    render(); // also after a refusal: a checkbox the reducer refused flips back
    return out;
  }

  // Pressed feedback in the same frame as the press (the feedback principle).
  doc.addEventListener("pointerdown", (e) => {
    const b = e.target.closest && e.target.closest("button");
    if (b) b.setAttribute("data-pressed", "");
  });
  for (const type of ["pointerup", "pointercancel", "pointerleave"]) {
    doc.addEventListener(type, () => doc.querySelectorAll("button[data-pressed]").forEach((b) => b.removeAttribute("data-pressed")), true);
  }

  const methodBits = [proposal.method && `proposed by ${proposal.method}`, ...proposal.flags.filter((f) => !f.startsWith("try:"))];
  $("method").textContent = methodBits.filter(Boolean).join(" · ");
  $("k-evidence").textContent = proposal.kEvidence;
  if (saved) {
    $("restored").hidden = false;
    $("restored-text").textContent = `Picked up where you left off${state.at ? ` (${new Date(state.at).toLocaleString()})` : ""}.`;
  }
  $("start-over").addEventListener("click", () => {
    dispatch({ type: "startOver" });
    $("restored").hidden = true;
    syncK();
    undoOpen = true;
    clearTimeout(undoTimer);
    undoTimer = setTimeout(() => { undoOpen = false; render(); }, UNDO_MS);
    render();
  });
  $("undo").addEventListener("click", () => {
    undoOpen = false;
    clearTimeout(undoTimer);
    dispatch({ type: "undoStartOver" });
    syncK();
  });

  syncK();
  $("k").addEventListener("input", (e) => dispatch({ type: "setK", value: e.target.value }));

  // Media: the proposal's own, or a file from this device. Loading and
  // failure each say so (the heavy-media principle); Cut here waits for the
  // media's metadata, so a tap always has a real clock under it.
  const mediaNote = (text) => { $("no-media-text").textContent = text; };
  const showMedia = (src, name) => {
    tapButton.disabled = true;
    $("player").hidden = false;
    $("media-state").hidden = false;
    $("media-state").textContent = `Loading ${name}…`;
    video.src = src;
    mediaNote("Or open a copy from this device:");
  };
  video.addEventListener("loadedmetadata", () => {
    $("media-state").hidden = true;
    tapButton.disabled = false;
    dispatch({ type: "duration", seconds: video.duration });
  });
  video.addEventListener("error", () => {
    $("player").hidden = true;
    tapButton.disabled = true;
    mediaNote("This browser could not play that media (moved, missing, or a format it does not read). Open a copy from this device:");
    say("Could not play the media here.");
  });
  if (proposal.media && /youtu\.?be/.test(proposal.media)) {
    mediaNote("This page plays files, not YouTube links. Open a downloaded copy from this device:");
  } else if (proposal.media) {
    showMedia(proposal.media, proposal.media);
  }
  $("file").addEventListener("change", (e) => {
    const file = e.target.files && e.target.files[0];
    if (file) { showMedia(URL.createObjectURL(file), file.name); say(`Opened ${file.name}.`); }
  });

  const tap = () => { if (!tapButton.disabled) dispatch({ type: "tap", t: video.currentTime }); };
  tapButton.addEventListener("click", tap);
  // Space taps only from the page itself, the video or Cut here; every other
  // button, link and summary keeps its native Space. A held key taps once.
  const spaceTargets = [doc.body, doc.documentElement, video, tapButton];
  doc.addEventListener("keydown", (e) => {
    if (e.code !== "Space" || !spaceTargets.includes(e.target) || $("player").hidden) return;
    e.preventDefault();
    if (!e.repeat) tap();
  });
  doc.addEventListener("keyup", (e) => {
    // Cut here's own Space-click would tap a second time.
    if (e.code === "Space" && e.target === tapButton) e.preventDefault();
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
      li.className = row.kind + (row.t === fresh ? " fresh" : "");
      li.append(button(mmss(row.t), seek(row.t), { className: "time link", title: "Play from here"}));
      li.lastChild.dataset.focusKey = `time:${row.t}`;
      const label = doc.createElement("span");
      label.className = "grow muted small";
      label.textContent = { proposed: "proposed", struck: "not a cut", added: "added by you" }[row.kind];
      li.append(label);
      if (row.kind === "added") {
        li.append(button("Remove", () => dispatch({ type: "remove", cut: row.t })));
        li.lastChild.dataset.focusKey = `act:${row.t}`;
      } else {
        const struck = row.kind === "struck";
        li.append(button(struck ? "Keep it" : "Not a cut", () => dispatch({ type: struck ? "keep" : "strike", cut: row.t })));
        li.lastChild.setAttribute("aria-pressed", String(struck));
        li.lastChild.dataset.focusKey = `act:${row.t}`;
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
    for (const [i, step] of proposal.steps.entries()) {
      const li = doc.createElement("li");
      const label = doc.createElement("label");
      label.className = "grow";
      const box = doc.createElement("input");
      box.type = "checkbox";
      box.checked = isAbsent(state, i);
      box.disabled = !step.spans.length;
      box.dataset.focusKey = `step:${i}`;
      box.addEventListener("change", () => dispatch({ type: "absent", index: i, on: box.checked }));
      const span = step.spans[0];
      label.append(box, ` ${step.name || "(unnamed)"} `);
      const when = doc.createElement("span");
      when.className = "muted small";
      when.textContent = span ? `${mmss(span[0])}–${mmss(span[1])} · not in this video` : "has no time in this video to mark";
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
  // Rows are rebuilt on every change; keep keyboard focus on the same control
  // (or on its list, never on <body>, where Space would add a cut).
  function render() {
    const focused = doc.activeElement;
    const focusKey = focused && focused.dataset ? focused.dataset.focusKey : undefined;
    const focusList = focused && focused.closest ? focused.closest("#cuts, #steps") : null;
    renderCuts();
    fresh = null; // the highlight plays once, for the row just added
    renderSteps();
    if (focusKey) {
      const again = doc.querySelector(`[data-focus-key="${focusKey}"]`);
      if (again) again.focus();
      else if (focusList) focusList.focus();
    }
    $("k-state").textContent = !state.kTouched
      ? "Edit the number to confirm it. Until you do, it is not sent."
      : state.k === null
        ? "That is not a step count, so none is sent."
        : "Saved with your answers for segmenters that use a known step count.";
    $("undo").hidden = !(undoOpen && state.previous);
    $("answers").value = answersText();
  }

  $("download").addEventListener("click", () => {
    const url = URL.createObjectURL(new Blob([answersText() + "\n"], { type: "application/json" }));
    const a = doc.createElement("a");
    a.href = url; a.download = "answers.json";
    doc.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    say("Downloaded answers.json.");
  });
  $("copy").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(answersText()); say("Copied the answers."); }
    catch { $("answers").closest("details").open = true; $("answers").select(); say("The answers are selected: copy them with your keyboard."); }
  });

  render();
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { timeStr, mmss, snap, freshState, reduce, buildAnswers, cutRows };
} else if (typeof document !== "undefined") {
  startPage(document);
}
