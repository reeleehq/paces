/* paces flow player: DOM, state and transport. The document is data
 * (document.json); every word the player says that the document does not is in
 * strings.json. Nothing here knows what kind of routine it is showing.
 *
 * Views: an overview (before the first step), a step, and a done card.
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
  var COUNT_IN_SECONDS = 5;

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

  var SVG_NS = "http://www.w3.org/2000/svg";
  function icon(path, extra) {
    var svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("aria-hidden", "true");
    if (extra) svg.setAttribute("class", extra);
    (Array.isArray(path) ? path : [path]).forEach(function (d) {
      var p = document.createElementNS(SVG_NS, "path"); p.setAttribute("d", d); svg.appendChild(p);
    });
    return svg;
  }
  var ICONS = {
    prev: "M15 5l-7 7 7 7", next: "M9 5l7 7-7 7", play: "M8 5v14l11-7z",
    pause: ["M8 5v14", "M16 5v14"], check: "M5 12l5 5 9-10", list: ["M8 6h12", "M8 12h12", "M8 18h12", "M4 6h.01", "M4 12h.01", "M4 18h.01"],
    close: ["M6 6l12 12", "M18 6L6 18"]
  };

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
    var wide = window.matchMedia ? window.matchMedia("(min-width: 900px)") : { matches: false };

    var state = { view: "overview", i: 0, mode: "manual", playing: false, waiting: false, countIn: 0,
      progress: 0, waited: 0, finished: false, lastBeat: -1, lastWhole: -1, lastRep: -1,
      soundOn: true, clickOn: true, keepAwake: "playing", moreOpen: false, sheet: false,
      mediaIndex: {}, totalSeconds: 0,
      settings: { bpm: grid ? Number(grid.tempoBpm) : 0, secondsPerRep: 3, secondsPerStep: 30, pace: "rep" } };
    var hash = /s=(\d+)/.exec(location.hash);
    if (hash && Number(hash[1]) < stops.length) { state.i = Number(hash[1]); state.view = "step"; }

    if (!stops.length) { app.textContent = S.empty; return; }
    function fmt(template, values) {
      return template.replace(/\{(\w+)\}/g, function (_, k) { return values[k] === undefined ? "" : values[k]; });
    }
    function mmss(t) { var n = Math.max(0, Math.ceil(t)); return Math.floor(n / 60) + ":" + String(n % 60).padStart(2, "0"); }
    function colourOf(group) { return C.groupColour(group, groups, RAMP_FROM, RAMP_TO); }

    /* ── skeleton ─────────────────────────────────────────────── */
    var status = el("p", { class: "sr", "aria-live": "polite" });
    var titleEl = el("h1", { text: doc.title });
    var posEl = el("span", { class: "pos" });
    var modeBtn = el("button", { class: "chip", type: "button", onclick: function () { toggleMode(); } });
    var paceBtn = el("button", { class: "chip", type: "button", "aria-expanded": "false", text: S.settings, onclick: function () {
      var open = pace.hasAttribute("hidden"); if (open) pace.removeAttribute("hidden"); else pace.setAttribute("hidden", "");
      paceBtn.setAttribute("aria-expanded", String(open)); } });
    var pace = el("div", { class: "pace", hidden: "" });
    var strip = el("div", { class: "strip", "aria-hidden": "true" });
    var stripBtn = el("button", { class: "stripbtn", type: "button", onclick: function () { openSheet(); } }, [strip]);
    var cellsWide = el("div", { class: "ribbon" });
    var stage = el("main", { class: "stage" });
    var outline = el("nav", { class: "outline", "aria-label": S.allSteps });
    var prev = el("button", { class: "nav", type: "button", "aria-label": S.previous, onclick: function () { advance(-1, true); } }, [icon(ICONS.prev)]);
    var next = el("button", { class: "nav", type: "button", "aria-label": S.next, onclick: function () { advance(1, true); } }, [icon(ICONS.next)]);
    var playBtn = el("button", { class: "play", type: "button", onclick: function () { togglePlay(); } });
    var playLabel = el("span", { class: "playlabel" });
    var beats = el("div", { class: "beats", "aria-hidden": "true" });
    var sheetEl = null;
    var bar = el("footer", { class: "bar" }, [el("div", { class: "barin" }, [prev,
      el("div", { class: "mid" }, [beats, el("div", { class: "playwrap" }, [playBtn, playLabel])]), next])]);

    app.textContent = "";
    app.appendChild(el("div", { class: "shell" }, [status,
      el("header", { class: "top" }, [el("div", { class: "titles" }, [titleEl, posEl]), el("div", { class: "modes" }, [modeBtn, paceBtn])]),
      pace,
      el("div", { class: "ribwrap" }, [stripBtn, cellsWide]),
      el("div", { class: "layout" }, [stage, el("aside", { class: "side" }, [el("h2", { text: S.allSteps }), outline])]),
      bar]));

    /* ribbon cells: one per stop, a gap between groups and a wider one between rounds */
    var cells = [], stripCells = [], lastGroup = -1, lastRound = "";
    stops.forEach(function (s) {
      var roundKey = s.rounds.map(function (r) { return r.step.id + r.round; }).join("/");
      var cls = (s.group !== lastGroup ? " newgroup" : roundKey !== lastRound ? " newround" : "");
      lastGroup = s.group; lastRound = roundKey;
      var cell = el("button", { class: "cell" + cls, type: "button", style: "--c:" + colourOf(s.group),
        "aria-label": (s.index + 1) + ". " + s.step.name, onclick: function () { go(s.index, true); } });
      cells[s.index] = cell; cellsWide.appendChild(cell);
      var tick = el("i", { class: cls, style: "--c:" + colourOf(s.group) });
      stripCells[s.index] = tick; strip.appendChild(tick);
    });
    stripBtn.appendChild(el("span", { class: "striplabel" }));

    /* outline rows (side pane and sheet share the builder) */
    function buildOutline(into, onPick) {
      var rows = [], lastChain = "";
      stops.forEach(function (s) {
        var chain = s.parents.map(function (p) { return p.id; }).join("/") + "|" + s.rounds.map(function (r) { return r.step.id + r.round; }).join("/");
        if (s.parents.length && chain !== lastChain) {
          var heading = s.parents.map(function (p) { return p.name; }).join(" › ");
          var rounds = s.rounds.filter(function (r) { return s.parents.indexOf(r.step) >= 0; })
            .map(function (r) { return C.formatRound(r, S); }).join(" · ");
          into.appendChild(el("p", { class: "olhead", text: heading + (rounds ? " · " + rounds : "") }));
        }
        lastChain = chain;
        var rowRounds = s.rounds.filter(function (r) { return r.step === s.step; }).map(function (r) { return C.formatRound(r, S); }).join(" · ");
        var b = el("button", { class: "ol" + (s.parents.length ? " nested" : ""), type: "button", onclick: function () { onPick(s.index); } }, [
          el("span", { class: "olname", text: s.step.name }),
          el("span", { class: "olcount", text: (rowRounds ? rowRounds + " · " : "") + C.formatCount(s.step, S) })]);
        rows[s.index] = b; into.appendChild(b);
      });
      return rows;
    }
    var outlineItems = buildOutline(outline, function (i) { go(i, true); });

    /* ── pace settings ────────────────────────────────────────── */
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
    var sounds = el("input", { type: "checkbox", checked: "" });
    sounds.addEventListener("change", function () { state.soundOn = sounds.checked; });
    pace.appendChild(el("label", { class: "field" }, [el("span", { text: S.sounds }), sounds]));
    var awake = el("select", {}, [el("option", { value: "playing", text: S.awakePlaying }), el("option", { value: "open", text: S.awakeOpen }), el("option", { value: "never", text: S.awakeNever })]);
    awake.addEventListener("change", function () { state.keepAwake = awake.value; syncWakeLock(); });
    pace.appendChild(field(S.keepAwake, awake));
    var paceBy = el("select", {}, [el("option", { value: "rep", text: S.paceByRep }), el("option", { value: "step", text: S.paceByStep })]);
    var repField, stepField;
    function syncPace() { var byStep = state.settings.pace === "step"; repField.querySelector("input").disabled = byStep; stepField.querySelector("input").disabled = !byStep; }
    paceBy.addEventListener("change", function () { state.settings.pace = paceBy.value; syncPace(); });
    pace.appendChild(field(S.paceBy, paceBy));
    repField = field(S.secondsPerRep, number(3, 0.5, 60, 0.5, function (v) { state.settings.secondsPerRep = v; }));
    stepField = field(S.secondsPerStep, number(30, 1, 600, 1, function (v) { state.settings.secondsPerStep = v; }));
    pace.appendChild(repField); pace.appendChild(stepField); syncPace();

    /* ── what the big count shows ─────────────────────────────── */
    function bigCount(stop) {
      var m = stop.step.duration, forms = (S.units || {})[m.unit];
      var unitWord = forms ? forms[1] : m.unit;
      if (C.isLearnerLed(stop.step)) {
        return state.playing && state.waiting ? { text: mmss(state.waited), sub: S.restUp } : { text: S.learnerLed, sub: "" };
      }
      if (state.mode !== "timed" || (!state.playing && state.progress === 0 && state.countIn === 0)) {
        return { text: m.value, sub: unitWord };       /* the target, in the same spot as the count */
      }
      var total = C.stopSeconds(doc, stop, state.settings);
      var byReps = !C.gridApplies(doc, m) && m.unit !== "second" && m.unit !== "minute" && state.settings.pace !== "step";
      if (C.gridApplies(doc, m)) {
        var n = Number(m.value);
        return { text: Math.min(n, Math.floor(state.progress * n) + 1) + " / " + n, sub: unitWord };
      }
      if (byReps) {
        var N = Number(m.value);
        return { text: Math.min(N, Math.floor(state.progress * N) + 1) + " / " + N, sub: unitWord };
      }
      return { text: mmss(total * (1 - state.progress)), sub: S.remaining };
    }

    /* ── rendering ────────────────────────────────────────────── */
    var overviewCounts = (function () {
      var rounds = 0;
      stops.forEach(function (s) { s.rounds.forEach(function (r) { rounds = Math.max(rounds, r.of); }); });
      var secs = 0;
      stops.forEach(function (s) { var t = C.stopSeconds(doc, s, state.settings); if (t) secs += t; });
      return { rounds: rounds, seconds: secs };
    })();
    function aboutText() {
      var t = 0; stops.forEach(function (s) { var x = C.stopSeconds(doc, s, state.settings); if (x) t += x; });
      return t ? fmt(S.about, { t: Math.max(1, Math.round(t / 60)) }) : "";
    }

    function render() {
      var s = stops[state.i];
      document.body.dataset.view = state.view;
      posEl.textContent = state.view === "overview" ? "" : state.view === "done" ? S.doneShort : fmt(S.position, { n: state.i + 1, total: stops.length });
      stripBtn.setAttribute("aria-label", S.allSteps + " · " + posEl.textContent);
      stripBtn.querySelector(".striplabel").textContent = posEl.textContent;
      var seen = state.view === "done" ? stops.length : state.view === "overview" ? 0 : state.i;
      cells.forEach(function (c, i) {
        c.className = c.className.replace(/ ?(on|done)\b/g, "") + (state.view === "step" && i === state.i ? " on" : i < seen ? " done" : "");
        if (state.view === "step" && i === state.i) c.setAttribute("aria-current", "step"); else c.removeAttribute("aria-current");
        c.style.removeProperty("--p");
      });
      stripCells.forEach(function (c, i) { c.className = c.className.replace(/ ?(on|done)\b/g, "") + (state.view === "step" && i === state.i ? " on" : i < seen ? " done" : ""); });
      outlineItems.forEach(function (o, i) { o.className = o.className.replace(/ ?on\b/, "") + (state.view === "step" && i === state.i ? " on" : ""); });
      if (state.view === "step" && outlineItems[state.i] && outlineItems[state.i].scrollIntoView && wide.matches) outlineItems[state.i].scrollIntoView({ block: "nearest" });
      stage.style.setProperty("--c", colourOf(state.view === "step" ? s.group : 0));
      stage.textContent = "";
      if (state.view === "overview") renderOverview();
      else if (state.view === "done") renderDone();
      else renderStep(s);
      modeBtn.textContent = state.mode === "timed" ? S.timed : S.manual;
      modeBtn.setAttribute("aria-pressed", String(state.mode === "timed"));
      modeBtn.setAttribute("aria-label", S.mode + ": " + modeBtn.textContent);
      var barOn = state.view === "step";
      bar.hidden = !barOn;
      prev.setAttribute("aria-disabled", String(state.i === 0)); next.setAttribute("aria-disabled", String(state.i === stops.length - 1));
      var timed = state.mode === "timed";
      playBtn.hidden = !timed; playLabel.hidden = !timed;
      playBtn.textContent = "";
      var label = state.playing ? (state.waiting ? S.ready : S.pause) : S.play;
      playBtn.appendChild(icon(state.playing ? (state.waiting ? ICONS.check : ICONS.pause) : ICONS.play));
      playBtn.setAttribute("aria-label", label); playLabel.textContent = label;
      playBtn.classList.toggle("running", state.playing && !state.waiting);
      beats.hidden = !(timed && s && C.beatsIn(doc, s));
      drawBeats(-1);
      status.textContent = state.view === "step" ? posEl.textContent + " " + s.step.name : state.view === "done" ? S.done : "";
      try { history.replaceState(history.state, "", state.view === "step" ? "#s=" + state.i : location.pathname + location.search); } catch (e) { /* sandboxed frame */ }
    }

    function counts() {
      var bits = [fmt(S.stepsCount, { n: stops.length })];
      if (overviewCounts.rounds > 1) bits.push(fmt(S.roundsCount, { n: overviewCounts.rounds }));
      var about = aboutText(); if (about) bits.push(about);
      return bits.join(" · ");
    }

    function renderOverview() {
      var first = stops[0];
      stage.appendChild(el("article", { class: "card overview" }, [
        el("h2", { class: "ovtitle", text: doc.title }),
        el("p", { class: "ovcounts", text: counts() }),
        doc.credits ? el("p", { class: "ovcredit", text: doc.credits }) : null,
        el("button", { class: "bigbtn primary", type: "button", onclick: function () { beginTimed(); } }, [icon(ICONS.play), document.createTextNode(S.start)]),
        el("button", { class: "bigbtn", type: "button", onclick: function () { state.mode = "manual"; go(0); state.view = "step"; render(); } }, [document.createTextNode(S.stepThrough)]),
        resourcesBlock(),
        el("p", { class: "ovnext", text: S.firstUp + " " + first.step.name })]));
    }

    function resourcesBlock() {
      var has = (doc.resources || []).length || (doc.notes || []).length;
      if (!has) return null;
      var box = el("div", { class: "ovbefore" });
      if ((doc.resources || []).length) {
        box.appendChild(el("h3", { text: S.needs }));
        box.appendChild(el("ul", {}, doc.resources.map(function (r) {
          var text = (r.quantity ? C.formatMeasure(r.quantity, S) + " · " : "") + r.name + (r.optional ? " (" + S.optional + ")" : "") + (r.note ? " — " + r.note : "");
          return el("li", { text: text });
        })));
      }
      if ((doc.notes || []).length) {
        box.appendChild(el("h3", { text: S.notes }));
        doc.notes.forEach(function (n) { box.appendChild(el("p", { text: n })); });
      }
      return box;
    }

    function renderDone() {
      stage.appendChild(el("article", { class: "card overview done" }, [
        el("h2", { class: "ovtitle", text: S.done }),
        el("p", { class: "ovcounts", text: fmt(S.doneCounts, { n: stops.length, t: mmss(state.totalSeconds) }) }),
        el("button", { class: "bigbtn primary", type: "button", onclick: function () { state.finished = false; state.totalSeconds = 0; state.mode = "timed"; go(0); state.view = "step"; render(); } }, [icon(ICONS.play), document.createTextNode(S.restart)]),
        el("button", { class: "bigbtn", type: "button", onclick: function () { state.mode = "manual"; go(0); state.view = "step"; render(); } }, [document.createTextNode(S.stepThrough)])]));
    }

    function renderStep(s) {
      var step = s.step;
      var card = el("article", { class: "card" });
      stage.appendChild(card);
      var ctx = [];
      s.rounds.forEach(function (r) { if (s.parents.indexOf(r.step) >= 0) ctx.push(C.formatRound(r, S)); });
      if (s.pos && s.pos.of > 1) ctx.push(fmt(S.stepOf, { n: s.pos.n, of: s.pos.of }));
      card.appendChild(el("p", { class: "context", text: ctx.join(" · ") || " " }));

      var options = C.listMedia(step);
      var shown = state.mediaIndex[step.id] || 0;
      if (shown >= options.length) shown = 0;
      if (options.length) {
        card.appendChild(mediaNode(options[shown]));
        if (options.length > 1) {
          card.appendChild(el("div", { class: "alts", role: "group", "aria-label": S.versions }, options.map(function (o, i) {
            var name = (i === 0 ? S.main : "") + (o.label ? (i === 0 ? " · " : "") + o.label : (i === 0 ? "" : fmt(S.alternative, { n: i })));
            return el("button", { class: "alt" + (i === shown ? " on" : ""), type: "button", "aria-pressed": String(i === shown), text: name,
              onclick: function () { state.mediaIndex[step.id] = i; render(); } });
          })));
        }
      }
      (s.heads || []).forEach(function (p) { if (!options.length) { var m = C.listMedia(p)[0]; if (m) card.appendChild(mediaNode(m)); } });

      card.appendChild(el("div", { class: "head" }, [el("h2", { text: step.name }),
        el("span", { class: "count", text: C.formatCount(step, S) })]));
      var badges = [];
      if (step.optional) badges.push(S.optional);
      if (step.variantOf) badges.push(fmt(S.variantOf, { step: step.variantOf }));
      if (badges.length) card.appendChild(el("p", { class: "badges", text: badges.join(" · ") }));

      var big = bigCount(s);
      var counting = state.countIn > 0;
      var bigEl = el("div", { class: "bigcount" + (counting ? " getready" : ""), "aria-hidden": counting || state.playing ? "true" : "false" }, [
        el("span", { class: "bignum", text: counting ? String(Math.ceil(state.countIn)) : big.text }),
        el("span", { class: "bigsub", text: counting ? S.getReady : big.sub })]);
      bigEl.setAttribute("data-big", "1");
      card.appendChild(bigEl);
      card.appendChild(el("div", { class: "fillbar", "aria-hidden": "true" }, [el("i", {})]));

      (s.heads || []).forEach(function (p) { if (p.description) card.appendChild(el("p", { class: "lead", text: p.description })); });
      if (step.description) card.appendChild(el("p", { class: "desc", text: step.description }));

      /* cues: a short list up front, everything else behind one disclosure */
      var cueGroups = C.groupCues(C.cuesFor(doc, s), S);
      var max = wide.matches ? 5 : 3;
      var head = C.headCues(cueGroups, max);
      var cueBox = el("div", { class: "cues" });
      cueGroups.forEach(function (g) {
        var inHead = g.cues.filter(function (c) { return head.shown.indexOf(c) >= 0; });
        if (!inHead.length) return;
        var block = el("div", { class: "cuegroup" }, [el("span", { class: "cuekind", text: g.label })]);
        inHead.forEach(function (c) { block.appendChild(cueLine(c, g.caution)); });
        cueBox.appendChild(block);
      });
      if (cueBox.childNodes.length) card.appendChild(cueBox);

      var extraCaptions = (step.spans || []).filter(function (sp) { return sp.caption; });
      var links = (step.spans || []).map(function (span) {
        var url = C.deepLink(sources[span.source], Number(span.start));
        return url ? el("a", { href: url, target: "_blank", rel: "noopener", text: fmt(S.watch, { t: mmss(Number(span.start)), role: S.roles[span.role] || span.role }) }) : null;
      }).filter(Boolean);
      if (head.hidden || extraCaptions.length || links.length) {
        var more = el("details", { class: "more" }, [el("summary", { text: head.hidden ? fmt(S.allCues, { n: head.hidden + head.shown.length }) : S.moreInfo })]);
        if (state.moreOpen) more.setAttribute("open", "");
        more.addEventListener("toggle", function () { state.moreOpen = more.open; });
        cueGroups.forEach(function (g) {
          var rest = g.cues.filter(function (c) { return head.shown.indexOf(c) < 0; });
          if (!rest.length) return;
          var block = el("div", { class: "cuegroup" }, [el("span", { class: "cuekind", text: g.label })]);
          rest.forEach(function (c) { block.appendChild(cueLine(c, g.caution)); });
          more.appendChild(block);
        });
        extraCaptions.forEach(function (sp) { more.appendChild(el("p", { class: "caption", text: (sp.label ? sp.label + " — " : "") + sp.caption })); });
        if (links.length) more.appendChild(el("p", { class: "links" }, links));
        card.appendChild(more);
      }

      /* during a rest, what comes next with its picture */
      var isRest = C.isLearnerLed(step) || (step.tags || []).indexOf("between-passes") >= 0 || (step.tags || []).indexOf("rest") >= 0;
      var nxt = stops[state.i + 1];
      if (nxt && isRest) {
        var nm = C.listMedia(nxt.step)[0];
        card.appendChild(el("div", { class: "upnext" }, [el("span", { class: "cuekind", text: S.next2 }),
          nm ? mediaNode(nm, true) : null, el("b", { text: nxt.step.name })]));
      } else if (nxt) {
        card.appendChild(el("p", { class: "nextline", text: S.next2 + ": " + nxt.step.name }));
      }
    }

    function cueLine(c, caution) {
      return el("p", { class: "cue" + (caution ? " caution" : "") }, [
        c.label ? el("b", { class: "cuelabel", text: c.label + " " }) : null, document.createTextNode(c.text)]);
    }

    function mediaNode(m, small) {
      var cls = "media" + (small ? " small" : "");
      if (m.kind === "video") {
        var v = el("video", { class: cls, loop: "", muted: "", playsinline: "", autoplay: "", preload: "metadata" }, [el("source", { src: m.src, type: m.mime })]);
        v.muted = true; if (m.poster) v.setAttribute("poster", m.poster);
        return v;
      }
      return el("img", { class: cls, src: m.src, alt: "" });
    }

    function drawBeats(active) {
      if (beats.hidden) return;
      var n = grid.subdivisions || 1;
      if (beats.childNodes.length !== n) { beats.textContent = ""; for (var k = 0; k < n; k++) beats.appendChild(el("i", {})); }
      Array.prototype.forEach.call(beats.childNodes, function (b, k) { b.className = k === active ? "on" : ""; });
    }

    /* ── the sheet: every step, for jumping from a phone ──────── */
    function openSheet() {
      if (state.sheet) return;
      state.sheet = true;
      var list = el("div", { class: "sheetlist" });
      var rows = buildOutline(list, function (i) { closeSheet(true); go(i, true); });
      sheetEl = el("div", { class: "sheetwrap" }, [
        el("div", { class: "scrim", onclick: function () { closeSheet(); } }),
        el("section", { class: "sheet", role: "dialog", "aria-modal": "true", "aria-label": S.allSteps }, [
          el("div", { class: "sheethead" }, [el("h2", { text: S.allSteps }),
            el("button", { class: "nav small", type: "button", "aria-label": S.close, onclick: function () { closeSheet(); } }, [icon(ICONS.close)])]),
          list])]);
      document.body.appendChild(sheetEl);
      if (rows[state.i]) { rows[state.i].classList.add("on"); rows[state.i].scrollIntoView({ block: "center" }); }
      try { history.pushState({ sheet: true }, ""); } catch (e) { /* ignore */ }
    }
    function closeSheet(fromPick) {
      if (!state.sheet) return;
      state.sheet = false;
      if (sheetEl) { sheetEl.remove(); sheetEl = null; }
      if (!fromPick) { try { if (history.state && history.state.sheet) history.back(); } catch (e) { /* ignore */ } }
    }
    window.addEventListener("popstate", function () { if (state.sheet) closeSheet(true); });

    /* ── the one way the position moves ───────────────────────── */
    function go(i, fromUser) {
      if (i < 0 || i >= stops.length) return false;
      state.i = i; state.progress = 0; state.waited = 0; state.lastBeat = -1; state.lastWhole = -1; state.lastRep = -1;
      state.finished = false; state.waiting = false;
      if (state.view !== "step") state.view = "step";
      render(); return true;
    }
    function advance(by, fromUser) { return go(state.i + (by === undefined ? 1 : by), !!fromUser); }

    /* ── sound, wake lock ─────────────────────────────────────── */
    var audio = null;
    function ensureAudio() {
      try {
        audio = audio || new (window.AudioContext || window.webkitAudioContext)();
        if (audio.state === "suspended") audio.resume();
      } catch (e) { audio = null; }
    }
    function tone(freq, seconds, volume) {
      if (!audio) return;
      var o = audio.createOscillator(), g = audio.createGain();
      o.frequency.value = freq;
      g.gain.setValueAtTime(volume || 0.12, audio.currentTime);
      g.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + seconds);
      o.connect(g); g.connect(audio.destination); o.start(); o.stop(audio.currentTime + seconds + 0.02);
    }
    function clickSound(accent) { if (state.clickOn) tone(accent ? 1200 : 800, 0.06); }
    function pip() { if (state.soundOn) tone(660, 0.08, 0.1); }
    function changeTone() { if (state.soundOn && !(grid && state.clickOn)) tone(1040, 0.35, 0.14); }
    function finishTone() { if (state.soundOn) { tone(784, 0.2, 0.14); setTimeout(function () { tone(1046, 0.4, 0.14); }, 220); } }
    function rep() { if (state.soundOn) tone(520, 0.04, 0.08); }

    var wake = null;
    function syncWakeLock() {
      var want = state.keepAwake === "open" || (state.keepAwake === "playing" && state.playing);
      if (!navigator.wakeLock) return;
      if (want && !wake) {
        navigator.wakeLock.request("screen").then(function (l) { wake = l; l.addEventListener("release", function () { wake = null; }); }, function () { /* refused */ });
      } else if (!want && wake) { wake.release(); wake = null; }
    }
    document.addEventListener("visibilitychange", function () {
      if (document.hidden && state.playing) { stopPlaying(); status.textContent = S.pausedHidden; }
      else if (!document.hidden) syncWakeLock();
    });

    /* ── timed mode ───────────────────────────────────────────── */
    /* Progress through a stop is a fraction (0..1), advanced by elapsed time
     * over the stop's CURRENT length: so a tempo change mid-step keeps the
     * position, and the overrun at a boundary is carried into the next stop
     * (the count does not drift from the music). */
    var raf = 0, last = 0;
    function paint() {
      var s = stops[state.i], bigNode = stage.querySelector("[data-big]");
      if (bigNode) {
        var b = state.countIn > 0 ? null : bigCount(s);
        bigNode.querySelector(".bignum").textContent = state.countIn > 0 ? String(Math.ceil(state.countIn)) : b.text;
      }
      var fill = stage.querySelector(".fillbar i"); if (fill) fill.style.transform = "scaleX(" + state.progress + ")";
      var cell = cells[state.i]; if (cell) cell.style.setProperty("--p", String(state.progress));
    }
    function tick(now) {
      if (!state.playing) return;
      var dt = (now - last) / 1000; last = now;
      state.totalSeconds += dt;
      if (state.countIn > 0) {
        var before = Math.ceil(state.countIn);
        state.countIn = Math.max(0, state.countIn - dt);
        if (Math.ceil(state.countIn) !== before && state.countIn > 0) pip();
        if (state.countIn === 0) { changeTone(); render(); } else paint();
        raf = requestAnimationFrame(tick); return;
      }
      var stop = stops[state.i];
      var total = C.stopSeconds(doc, stop, state.settings);
      if (total === null) {                 /* learner-led: wait for the viewer, count up */
        state.waiting = true; state.waited += dt;
        if (!stage.querySelector(".bigcount .bignum")) render();
        paint(); raf = requestAnimationFrame(tick); return;
      }
      state.progress += dt / total;
      var overrun = 0;
      if (state.progress >= 1) { overrun = (state.progress - 1) * total; state.progress = 1; }
      var nBeats = C.beatsIn(doc, stop);
      if (nBeats) {
        var beat = Math.min(nBeats - 1, Math.floor(state.progress * nBeats));
        if (beat !== state.lastBeat) {
          state.lastBeat = beat; clickSound(beat % (grid.subdivisions || 1) === 0);
          drawBeats(beat % (grid.subdivisions || 1));
        }
      } else {
        var remaining = total * (1 - state.progress), whole = Math.ceil(remaining);
        var m = stop.step.duration, byReps = m.unit !== "second" && m.unit !== "minute" && state.settings.pace !== "step";
        if (byReps) {
          var r = Math.min(Number(m.value) - 1, Math.floor(state.progress * Number(m.value)));
          if (r !== state.lastRep) { state.lastRep = r; if (r > 0) rep(); }
        } else if (whole !== state.lastWhole) {
          state.lastWhole = whole; if (whole >= 1 && whole <= 3) pip();
        }
      }
      paint();
      if (state.progress >= 1) {
        if (!go(state.i + 1)) { complete(); return; }
        changeTone();
        state.progress = Math.min(0.999, overrun / (C.stopSeconds(doc, stops[state.i], state.settings) || 1));
      }
      raf = requestAnimationFrame(tick);
    }
    function complete() {
      state.finished = true; state.playing = false; state.waiting = false; cancelAnimationFrame(raf);
      state.view = "done"; finishTone(); syncWakeLock(); render();
    }
    function beginTimed() {
      state.mode = "timed"; state.totalSeconds = 0;
      go(0); state.view = "step";
      ensureAudio();
      state.countIn = COUNT_IN_SECONDS; startPlaying(true);
    }
    function startPlaying(keepCountIn) {
      ensureAudio();                       /* inside the press: iOS needs a gesture */
      if (state.view !== "step") { state.view = "step"; }
      if (state.finished) { state.finished = false; go(0); }
      if (!keepCountIn) state.countIn = 0;
      state.playing = true; last = performance.now(); syncWakeLock(); render(); raf = requestAnimationFrame(tick);
    }
    function stopPlaying() {
      state.playing = false; state.waiting = false; cancelAnimationFrame(raf); state.countIn = 0; syncWakeLock(); render();
    }
    function togglePlay() {
      if (state.playing && state.waiting) {          /* "Ready": move on, keep running */
        state.waiting = false; state.waited = 0;
        if (!go(state.i + 1)) { complete(); return; }
        changeTone(); last = performance.now(); raf = requestAnimationFrame(tick); return;
      }
      state.playing ? stopPlaying() : startPlaying();
    }
    function toggleMode() {
      if (state.playing) stopPlaying();
      state.mode = state.mode === "timed" ? "manual" : "timed";
      if (state.view === "overview") state.view = "step";
      render();
    }

    /* ── keys and swipe ───────────────────────────────────────── */
    document.addEventListener("keydown", function (e) {
      if (/^(INPUT|SELECT|TEXTAREA)$/.test((e.target || {}).tagName)) return;
      if (e.key === "Escape" && state.sheet) { closeSheet(); return; }
      if (state.view !== "step") return;
      if (e.key === "ArrowRight" || e.key === "ArrowDown") { advance(1, true); e.preventDefault(); }
      else if (e.key === "ArrowLeft" || e.key === "ArrowUp") { advance(-1, true); e.preventDefault(); }
      else if (e.key === " " && state.mode === "timed" && !/^(BUTTON|A|SUMMARY)$/.test((e.target || {}).tagName)) { togglePlay(); e.preventDefault(); }
      else if (e.key === "t") toggleMode();
    });
    var x0 = null, y0 = null;
    stage.addEventListener("touchstart", function (e) { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; }, { passive: true });
    stage.addEventListener("touchend", function (e) {
      if (x0 === null || state.view !== "step") return;
      var dx = e.changedTouches[0].clientX - x0, dy = e.changedTouches[0].clientY - y0; x0 = null;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) advance(dx < 0 ? 1 : -1, true);
    }, { passive: true });

    window.player = { advance: advance, go: go, state: state, stops: stops };
    render();
  }
})();
