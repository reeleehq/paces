/* paces flow player: the pure part (no DOM). Loaded by index.html and by the
 * node tests. Everything here is a function of the document and the settings. */
(function (root) {
  "use strict";

  /* A decimal string ("7", "129.2") as a number. */
  function num(text) { return Number(text); }

  /* Expand the document into the ordered "stops" the player walks through.
   * A step with children cycles them `repeat` times (round r of n); a step
   * with no children and repeat > 1 is itself repeated. Each stop remembers
   * its top-level group (for the ribbon) and the chain of ancestors. */
  function buildStops(doc) {
    var stops = [];
    function walk(step, ctx) {
      var rounds = step.repeat || 1;
      if (step.steps && step.steps.length) {
        for (var r = 1; r <= rounds; r++) {
          var inner = { group: ctx.group, parents: ctx.parents.concat([step]),
            rounds: ctx.rounds.concat(rounds > 1 ? [{ step: step, round: r, of: rounds }] : []) };
          step.steps.forEach(function (child) { walk(child, inner); });
        }
      } else {
        for (var k = 1; k <= rounds; k++) {
          stops.push({
            step: step, group: ctx.group, parents: ctx.parents,
            rounds: ctx.rounds.concat(rounds > 1 ? [{ step: step, round: k, of: rounds }] : []),
            index: stops.length
          });
        }
      }
    }
    (doc.steps || []).forEach(function (step, g) {
      walk(step, { group: g, parents: [], rounds: [] });
    });
    return stops;
  }

  /* The grid applies to a measure when the document has a tempo and the
   * measure is in the grid's own unit. */
  function gridApplies(doc, measure) {
    var g = doc.metric;
    return !!(g && g.tempoBpm && g.unit === measure.unit);
  }

  /* THE CLOCK. Seconds a stop lasts, from the document and the viewer's
   * settings: {bpm, secondsPerRep, secondsPerStep, pace}. The document stores
   * no seconds, so:
   *   - a measure in the grid's unit lasts value x subdivisions beats at bpm;
   *   - a measure in seconds lasts that long;
   *   - anything else (reps, ...) lasts value x secondsPerRep, or, when the
   *     viewer chose to pace by step, secondsPerStep.
   * Timed mode and its count-along are the only callers. A third mode that
   * advances on an external event does not call this at all: it calls
   * player.advance() when its event fires. */
  function stopSeconds(doc, stop, settings) {
    var m = stop.step.duration, value = num(m.value);
    if (gridApplies(doc, m)) {
      var bpm = settings.bpm || num(doc.metric.tempoBpm);
      return value * (doc.metric.subdivisions || 1) * 60 / bpm;
    }
    if (m.unit === "second") return value;
    if (m.unit === "minute") return value * 60;
    return settings.pace === "step" ? settings.secondsPerStep : value * settings.secondsPerRep;
  }

  /* "7 reps", "4 eights", "1 rep": the unit in the document's own words,
   * pluralised from the strings table. */
  function formatMeasure(m, strings) {
    var forms = (strings.units || {})[m.unit];
    var one = num(m.value) === 1;
    var word = forms ? (one ? forms[0] : forms[1]) : m.unit;
    return m.value + " " + word;
  }

  /* "round 2 of 3" from the strings template. */
  function formatRound(r, strings) {
    return strings.round.replace("{round}", r.round).replace("{of}", r.of);
  }

  /* Deep link into a source at a time, or null. */
  function deepLink(source, startSeconds) {
    if (!source || !/^https?:/.test(source.uri)) return null;
    if (/youtu/.test(source.uri)) {
      return source.uri + (source.uri.indexOf("?") >= 0 ? "&" : "?") + "t=" + Math.floor(startSeconds);
    }
    return source.uri;
  }

  /* Cues that belong on a stop: anchored to the step or to an ancestor. */
  function cuesFor(doc, stop) {
    var ids = {};
    ids[stop.step.id] = true;
    stop.parents.forEach(function (p) { ids[p.id] = true; });
    return (doc.cues || []).filter(function (c) { return ids[c.anchor.step]; });
  }

  /* One medium for a step: a looping clip, else a gif, else a poster. */
  function pickMedia(step) {
    var by = {};
    (step.artifacts || []).forEach(function (a) { (by[a.role] = by[a.role] || []).push(a); });
    var stem = function (u) { return u.replace(/\.[^./]+$/, ""); };
    if (by.clip) {
      var clip = by.clip[0];
      var poster = (by.poster || []).filter(function (p) { return stem(p.uri) === stem(clip.uri); })[0] || (by.poster || [])[0];
      return { kind: "video", src: clip.uri, mime: clip.mime || "video/mp4", poster: poster && poster.uri };
    }
    if (by.gif) return { kind: "image", src: by.gif[0].uri };
    if (by.poster) return { kind: "image", src: by.poster[0].uri };
    return null;
  }

  /* Ribbon colour for group g of n: a ramp between two colours. */
  function groupColour(g, n, from, to) {
    var t = n <= 1 ? 0 : g / (n - 1), out = [];
    for (var i = 0; i < 3; i++) out.push(Math.round(from[i] + (to[i] - from[i]) * t));
    return "rgb(" + out.join(",") + ")";
  }

  var api = { buildStops: buildStops, stopSeconds: stopSeconds, gridApplies: gridApplies,
    formatMeasure: formatMeasure, formatRound: formatRound, deepLink: deepLink,
    cuesFor: cuesFor, pickMedia: pickMedia, groupColour: groupColour };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PacesFlowCore = api;
})(typeof self !== "undefined" ? self : this);
