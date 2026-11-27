/* paces flow player: DOM, state and transport. The document is data
 * (document.json); every word the player says that the document does not is in
 * strings.json. Nothing here knows what kind of routine it is showing.
 *
 * THE SEAM: `advance(by)` is the one way the position moves. Manual buttons,
 * keys and swipes call it; timed mode calls it when the clock (stopSeconds)
 * says a stop is over. A mode that advances on an external event (a camera
 * counting repetitions, say) is one more caller of `player.advance()`; nothing
 * else in this file would change. Nothing for that is built here. */
(function () {
  "use strict";
  var C = window.PacesFlowCore;
  var app = document.getElementById("app");
  var RAMP_FROM = [255, 192, 46], RAMP_TO = [255, 61, 127];

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else if (k === "class") node.className = attrs[k];
      else if (k.slice(0, 2) === "on") node.addEventListener(k.slice(2), attrs[k]);
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) node.appendChild(c); });
    return node;
  }

  function chevron(dir) {
    var ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("aria-hidden", "true");
    var p = document.createElementNS(ns, "path");
    p.setAttribute("d", dir < 0 ? "M15 5l-7 7 7 7" : "M9 5l7 7-7 7");
    svg.appendChild(p); return svg;
  }

  function loadJson(url, globalKey) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).catch(function () {
      /* opened from disk: fetch is refused, so fall back to data.js */
      return new Promise(function (resolve, reject) {
        if (window.PACES_FLOW) return resolve(window.PACES_FLOW[globalKey]);
        var s = document.createElement("script");
        s.src = "data.js";
        s.onload = function () { window.PACES_FLOW ? resolve(window.PACES_FLOW[globalKey]) : reject(); };
        s.onerror = reject;
        document.head.appendChild(s);
      });
    });
  }

  Promise.all([loadJson("document.json", "document"), loadJson("strings.json", "strings")])
    .then(function (r) {
      try { start(r[0], r[1]); }
      catch (e) { app.textContent = "Could not show this document: " + e.message; if (window.console) console.error(e); }
    }, function () {
      /* strings.json is what would say this in the viewer's language, and it
       * is the thing that failed to load: this one line is the fallback. */
      app.textContent = "Could not load document.json and strings.json. Serve this folder (for example: python -m http.server) rather than opening the file directly.";
    });

  function start(doc, S) {
    document.documentElement.lang = doc.lang || "en";
    document.documentElement.dir = /^(ar|he|fa|ur)(-|$)/i.test(doc.lang || "") ? "rtl" : "ltr";
    document.title = doc.title;
    var stops = C.buildStops(doc);
    var sources = {};
    (doc.sources || []).forEach(function (s) { sources[s.id] = s; });
    var groups = (doc.steps || []).length;
    var grid = doc.metric && doc.metric.tempoBpm ? doc.metric : null;

    var state = { i: 0, mode: "manual", playing: false, progress: 0, finished: false, lastBeat: -1, clickOn: true,
      settings: { bpm: grid ? Number(grid.tempoBpm) : 0, secondsPerRep: 3, secondsPerStep: 30, pace: "rep" } };
    var hash = /s=(\d+)/.exec(location.hash);
    if (hash && Number(hash[1]) < stops.length) state.i = Number(hash[1]);

    if (!stops.length) { app.textContent = S.empty; return; }

    /* ── skeleton ─────────────────────────────────────────────── */
    var title = el("h1", { text: doc.title });
    var posEl = el("span", { class: "pos" });
    var modeBtn = el("button", { class: "chip", type: "button", "aria-pressed": "false", onclick: toggleMode });
    var paceBtn = el("button", { class: "chip", type: "button", "aria-expanded": "false", text: S.settings, onclick: function () {
      var open = pace.hasAttribute("hidden"); if (open) pace.removeAttribute("hidden"); else pace.setAttribute("hidden", "");
      paceBtn.setAttribute("aria-expanded", String(open)); } });
    var ribbon = el("div", { class: "ribbon" });
    var status = el("p", { class: "sr", "aria-live": "polite" });
    var pace = el("div", { class: "pace", hidden: "" });
    var card = el("article", { class: "card" });
    var outline = el("nav", { class: "outline", "aria-label": S.allSteps });
    var prev = el("button", { class: "nav", type: "button", "aria-label": S.previous, onclick: function () { advance(-1, true); } }, [chevron(-1)]);
    var next = el("button", { class: "nav", type: "button", "aria-label": S.next, onclick: function () { advance(1, true); } }, [chevron(1)]);
    var play = el("button", { class: "play", type: "button", onclick: togglePlay });
    var beats = el("div", { class: "beats", "aria-hidden": "true" });

    app.textContent = "";
    app.appendChild(el("div", { class: "shell" }, [status,
      el("header", { class: "top" }, [el("div", { class: "titles" }, [title, posEl]),
        el("div", { class: "modes" }, [modeBtn, paceBtn])]),
      pace, ribbon,
      el("div", { class: "layout" }, [
        el("main", { class: "stage" }, [card]),
        el("aside", { class: "side" }, [el("h2", { text: S.allSteps }), outline])]),
      el("footer", { class: "bar" }, [prev, el("div", { class: "mid" }, [beats, play]), next])
    ]));

    /* ribbon: one cell per stop, grouped by top-level step */
    var byGroup = {};
    stops.forEach(function (s) { (byGroup[s.group] = byGroup[s.group] || []).push(s); });
    var cells = [];
    Object.keys(byGroup).forEach(function (g) {
      var colour = C.groupColour(Number(g), groups, RAMP_FROM, RAMP_TO);
      var box = el("div", { class: "group", style: "--n:" + byGroup[g].length + ";--c:" + colour });
      var row = el("div", { class: "cells" });
      byGroup[g].forEach(function (s) {
        var cell = el("button", { class: "cell", type: "button",
          "aria-label": (s.index + 1) + ". " + s.step.name, onclick: function () { go(s.index, true); } });
        cells[s.index] = cell; row.appendChild(cell);
      });
      box.appendChild(row);
      box.appendChild(el("span", { class: "glabel", text: doc.steps[g].name }));
      ribbon.appendChild(box);
    });

    /* outline: the structure, nested: a heading each time the chain of
     * enclosing steps (and their rounds) changes, then indented rows */
    var outlineItems = [], lastChain = "";
    stops.forEach(function (s) {
      var chain = s.parents.map(function (p) { return p.id; }).join("/") + "|" + s.rounds.map(function (r) { return r.step.id + r.round; }).join("/");
      if (s.parents.length && chain !== lastChain) {
        var heading = s.parents.map(function (p) { return p.name; }).join(" › ");
        var rounds = s.rounds.filter(function (r) { return s.parents.indexOf(r.step) >= 0; })
          .map(function (r) { return C.formatRound(r, S); }).join(" · ");
        outline.appendChild(el("p", { class: "olhead", text: heading + (rounds ? " · " + rounds : "") }));
      }
      lastChain = chain;
      var rowRounds = s.rounds.filter(function (r) { return r.step === s.step; }).map(function (r) { return C.formatRound(r, S); }).join(" · ");
      var b = el("button", { class: "ol" + (s.parents.length ? " nested" : ""), type: "button", onclick: function () { go(s.index, true); } }, [
        el("span", { class: "olname", text: s.step.name }),
        el("span", { class: "olcount", text: (rowRounds ? rowRounds + " · " : "") + C.formatMeasure(s.step.duration, S) })]);
      outlineItems[s.index] = b; outline.appendChild(b);
    });

    /* pace settings */
    function field(labelText, input) { return el("label", { class: "field" }, [el("span", { text: labelText }), input]); }
    function number(value, min, max, step, onchange) {
      var i = el("input", { type: "number", value: String(value), min: String(min), max: String(max), step: String(step) });
      i.addEventListener("input", function () { var v = Number(i.value); if (v > 0) onchange(v); });
      return i;
    }
    if (grid) {
      var tempo = el("input", { type: "range", min: String(Math.round(state.settings.bpm * 0.5)), max: String(Math.round(state.settings.bpm * 1.5)), value: String(state.settings.bpm) });
      var tempoVal = el("output", { text: Math.round(state.settings.bpm) + " " + S.bpm });
      tempo.addEventListener("input", function () { state.settings.bpm = Number(tempo.value); tempoVal.textContent = tempo.value + " " + S.bpm; });
      pace.appendChild(el("div", { class: "field" }, [el("span", { text: S.tempo }), tempo, tempoVal]));
      var click = el("input", { type: "checkbox", checked: "" });
      click.addEventListener("change", function () { state.clickOn = click.checked; });
      pace.appendChild(el("label", { class: "field" }, [el("span", { text: S.sound }), click]));
    }
    var paceBy = el("select", {}, [el("option", { value: "rep", text: S.paceByRep }), el("option", { value: "step", text: S.paceByStep })]);
    var repField, stepField;
    function syncPace() { var byStep = state.settings.pace === "step"; repField.querySelector("input").disabled = byStep; stepField.querySelector("input").disabled = !byStep; }
    paceBy.addEventListener("change", function () { state.settings.pace = paceBy.value; syncPace(); });
    pace.appendChild(field(S.paceBy, paceBy));
    repField = field(S.secondsPerRep, number(3, 0.5, 60, 0.5, function (v) { state.settings.secondsPerRep = v; }));
    stepField = field(S.secondsPerStep, number(30, 1, 600, 1, function (v) { state.settings.secondsPerStep = v; }));
    pace.appendChild(repField); pace.appendChild(stepField); syncPace();

    /* ── rendering one stop ───────────────────────────────────── */
    function render() {
      var s = stops[state.i], step = s.step;
      posEl.textContent = S.position.replace("{n}", state.i + 1).replace("{total}", stops.length);
      cells.forEach(function (c, i) { c.className = "cell" + (i === state.i ? " on" : i < state.i ? " done" : ""); if (i === state.i) c.setAttribute("aria-current", "step"); else c.removeAttribute("aria-current"); });
      status.textContent = posEl.textContent + " " + step.name;
      cells.forEach(function (c) { c.style.removeProperty("--p"); });
      card.style.setProperty("--p", "0");
      outlineItems.forEach(function (o, i) { o.className = "ol" + (i === state.i ? " on" : ""); });
      if (outlineItems[state.i] && outlineItems[state.i].scrollIntoView) outlineItems[state.i].scrollIntoView({ block: "nearest" });
      card.style.setProperty("--c", C.groupColour(s.group, groups, RAMP_FROM, RAMP_TO));
      card.textContent = "";

      var ctx = s.parents.map(function (p) { return p.name; }).concat(s.rounds.map(function (r) { return C.formatRound(r, S); }));
      card.appendChild(el("p", { class: "context", text: ctx.join(" · ") || "\u00a0" }));

      var m = pickMedia(step);
      (s.heads || []).forEach(function (p) { if (!m) m = pickMedia(p); });
      card.appendChild(m ? mediaNode(m) : el("div", { class: "media blank" }, [
        el("span", { class: "tilenum", "aria-hidden": "true", text: String(state.i + 1) }),
        el("span", { class: "bignum", text: C.formatMeasure(step.duration, S) })]));

      var head = el("div", { class: "head" }, [el("h2", { text: step.name }),
        el("span", { class: "count", text: C.formatMeasure(step.duration, S) })]);
      card.appendChild(head);
      var badges = [];
      if (step.optional) badges.push(S.optional);
      if (step.variantOf) badges.push(S.variantOf.replace("{step}", step.variantOf));
      if (badges.length) card.appendChild(el("p", { class: "badges", text: badges.join(" · ") }));
      (s.heads || []).forEach(function (p) { if (p.description) card.insertBefore(el("p", { class: "lead", text: p.description }), head); });
      if (step.description) card.appendChild(el("p", { class: "desc", text: step.description }));

      C.cuesFor(doc, s).forEach(function (cue) {
        var caution = (S.cueKindsCaution || []).indexOf(cue.kind) >= 0;
        card.appendChild(el("p", { class: "cue" + (caution ? " caution" : "") },
          [el("span", { class: "cuekind", text: caution ? S.caution : S.cue }), document.createTextNode(" " + cue.text)]));
      });

      (step.spans || []).forEach(function (span) { if (span.caption) card.appendChild(el("p", { class: "caption", text: (span.label ? span.label + " — " : "") + span.caption })); });
      var links = (step.spans || []).map(function (span) {
        var label = (S.roles[span.role] || span.role) + " " + mmss(Number(span.start));
        var url = C.deepLink(sources[span.source], Number(span.start));
        return url ? el("a", { href: url, target: "_blank", rel: "noopener", text: label }) : el("span", { text: label });
      });
      if (links.length) card.appendChild(el("p", { class: "links" }, links));

      prev.setAttribute("aria-disabled", String(state.i === 0)); next.setAttribute("aria-disabled", String(state.i === stops.length - 1));
      modeBtn.textContent = state.mode === "timed" ? S.timed : S.manual;
      modeBtn.setAttribute("aria-pressed", String(state.mode === "timed"));
      modeBtn.setAttribute("aria-label", S.mode + ": " + modeBtn.textContent);
      play.hidden = state.mode !== "timed";
      play.textContent = state.playing ? S.pause : S.play;
      play.classList.toggle("running", state.playing);
      beats.hidden = !(state.mode === "timed" && C.beatsIn(doc, s));
      drawBeats(-1);
      try { history.replaceState(null, "", "#s=" + state.i); } catch (e) { /* sandboxed frame */ }
    }

    function mediaNode(m) {
      if (m.kind === "video") {
        var v = el("video", { class: "media", loop: "", muted: "", playsinline: "", autoplay: "", preload: "metadata" }, [el("source", { src: m.src, type: m.mime })]);
        v.muted = true; if (m.poster) v.setAttribute("poster", m.poster);
        return v;
      }
      return el("img", { class: "media", src: m.src, alt: "" });
    }
    function mmss(t) { var n = Math.floor(t); return Math.floor(n / 60) + ":" + String(n % 60).padStart(2, "0"); }
    function pickMedia(step) { return C.pickMedia(step); }

    function drawBeats(active) {
      if (beats.hidden) return;
      var n = grid.subdivisions || 1;
      if (beats.childNodes.length !== n) { beats.textContent = ""; for (var k = 0; k < n; k++) beats.appendChild(el("i", {})); }
      Array.prototype.forEach.call(beats.childNodes, function (b, k) { b.className = k === active ? "on" : ""; });
    }

    /* ── the one way the position moves ───────────────────────── */
    function go(i, fromUser) {
      if (i < 0 || i >= stops.length) return false;
      state.i = i; state.progress = 0; state.lastBeat = -1; state.finished = false;
      render(); return true;
    }
    function advance(by, fromUser) { return go(state.i + (by === undefined ? 1 : by), !!fromUser); }

    /* ── timed mode ───────────────────────────────────────────── */
    /* Progress through a stop is a fraction (0..1), advanced by elapsed time
     * over the stop's CURRENT length: so a tempo change mid-step keeps the
     * position, and the overrun at a boundary is carried into the next stop
     * (the count does not drift from the music). */
    var raf = 0, last = 0, audio = null;
    function ensureAudio() {
      try {
        audio = audio || new (window.AudioContext || window.webkitAudioContext)();
        if (audio.state === "suspended") audio.resume();
      } catch (e) { audio = null; }
    }
    function clickSound(accent) {
      if (!state.clickOn || !audio) return;
      var o = audio.createOscillator(), g = audio.createGain();
      o.frequency.value = accent ? 1200 : 800;
      g.gain.setValueAtTime(0.12, audio.currentTime);
      g.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 0.06);
      o.connect(g); g.connect(audio.destination); o.start(); o.stop(audio.currentTime + 0.07);
    }
    function tick(now) {
      if (!state.playing) return;
      var stop = stops[state.i];
      var total = C.stopSeconds(doc, stop, state.settings);
      state.progress += (now - last) / 1000 / total;
      last = now;
      var overrun = 0;
      if (state.progress >= 1) { overrun = (state.progress - 1) * total; state.progress = 1; }
      var nBeats = C.beatsIn(doc, stop);
      if (nBeats) {
        var beat = Math.min(nBeats - 1, Math.floor(state.progress * nBeats));
        if (beat !== state.lastBeat) {
          state.lastBeat = beat; clickSound(beat % (grid.subdivisions || 1) === 0);
          drawBeats(beat % (grid.subdivisions || 1));
        }
      }
      var cell = cells[state.i]; if (cell) cell.style.setProperty("--p", String(state.progress));
      card.style.setProperty("--p", String(state.progress));
      if (state.progress >= 1) {
        if (!go(state.i + 1)) { state.finished = true; stopPlaying(); return; }
        state.progress = Math.min(0.999, overrun / C.stopSeconds(doc, stops[state.i], state.settings));
      }
      raf = requestAnimationFrame(tick);
    }
    function startPlaying() {
      ensureAudio();                       /* inside the press: iOS needs a gesture */
      if (state.finished) { state.finished = false; go(0); }
      state.playing = true; last = performance.now(); render(); raf = requestAnimationFrame(tick);
    }
    function stopPlaying() {
      state.playing = false; cancelAnimationFrame(raf);
      if (state.finished) state.progress = 0;
      render();
    }
    function togglePlay() { state.playing ? stopPlaying() : startPlaying(); }
    function toggleMode() {
      if (state.playing) stopPlaying();
      state.mode = state.mode === "timed" ? "manual" : "timed"; render();
    }

    /* ── keys and swipe ───────────────────────────────────────── */
    document.addEventListener("keydown", function (e) {
      if (/^(INPUT|SELECT|TEXTAREA)$/.test((e.target || {}).tagName)) return;
      if (e.key === "ArrowRight" || e.key === "ArrowDown") { advance(1, true); e.preventDefault(); }
      else if (e.key === "ArrowLeft" || e.key === "ArrowUp") { advance(-1, true); e.preventDefault(); }
      else if (e.key === " " && state.mode === "timed" && !/^(BUTTON|A)$/.test((e.target || {}).tagName)) { togglePlay(); e.preventDefault(); }
      else if (e.key === "t") toggleMode();
    });
    var x0 = null, y0 = null;
    var stage = card.parentNode;
    stage.addEventListener("touchstart", function (e) { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; }, { passive: true });
    stage.addEventListener("touchend", function (e) {
      if (x0 === null) return;
      var dx = e.changedTouches[0].clientX - x0, dy = e.changedTouches[0].clientY - y0; x0 = null;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) advance(dx < 0 ? 1 : -1, true);
    }, { passive: true });

    window.player = { advance: advance, go: go, state: state, stops: stops };
    render();
  }
})();
