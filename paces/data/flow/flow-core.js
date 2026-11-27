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
    /* `heads`: the ancestors for which this stop is the first of a round, so
     * their own description and media are shown once per round, on that stop. */
    function walk(step, ctx, first) {
      var rounds = Math.max(1, step.repeat || 1);
      if (step.steps && step.steps.length) {
        for (var r = 1; r <= rounds; r++) {
          /* a rest BETWEEN the passes is not after the last one */
          var shown = step.steps.filter(function (child) {
            return !(r === rounds && hasTag(child, "between-passes"));
          });
          /* a learner counts stations: rests are not numbered */
          var stations = shown.filter(function (child) { return !isRest(child); });
          var seen = 0;
          shown.forEach(function (child, i) {
            var rest = isRest(child);
            if (!rest) seen += 1;
            var inner = { group: ctx.group, parents: ctx.parents.concat([step]),
              rounds: ctx.rounds.concat(rounds > 1 ? [{ step: step, round: r, of: rounds }] : []),
              pos: rest ? null : { n: seen, of: stations.length } };
            walk(child, inner, i === 0 ? (r === 1 ? first : []).concat([step]) : []);
          });
        }
      } else {
        for (var k = 1; k <= rounds; k++) {
          stops.push({
            step: step, group: ctx.group, parents: ctx.parents, heads: k === 1 ? first : [],
            pos: ctx.pos || null,
            rounds: ctx.rounds.concat(rounds > 1 ? [{ step: step, round: k, of: rounds }] : []),
            index: stops.length
          });
        }
      }
    }
    (doc.steps || []).forEach(function (step, g) {
      walk(step, { group: g, parents: [], rounds: [] }, []);
    });
    return stops;
  }

  /* A rest: led by the learner, or between the passes of a repeat, or tagged rest. */
  function isRest(step) {
    return hasTag(step, "learner-led") || hasTag(step, "between-passes") || hasTag(step, "rest");
  }

  function hasTag(step, tag) { return (step.tags || []).indexOf(tag) >= 0; }

  /* A step the learner leads has no fixed length: its duration is a
   * placeholder the clock ignores and counts do not show. */
  function isLearnerLed(step) { return hasTag(step, "learner-led"); }

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
    if (isLearnerLed(stop.step)) return null;     /* waits for the viewer */
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
  function formatCount(step, strings) {
    return isLearnerLed(step) ? strings.learnerLed : formatMeasure(step.duration, strings);
  }

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
    if (!source) return null;
    var url;
    try { url = new URL(source.uri); } catch (e) { return null; }
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    var host = url.hostname.replace(/^www\./, "");
    if (host === "youtu.be" || host === "youtube.com" || host === "m.youtube.com" || host === "music.youtube.com") {
      url.searchParams.set("t", String(Math.floor(startSeconds)));
    } else if (/\.(mp4|webm|mov|m4v|mp3|wav|ogg)$/i.test(url.pathname)) {
      url.hash = "t=" + Math.floor(startSeconds);   /* media fragment */
    }
    return url.toString();
  }

  /* Beats in a stop under the grid (value x subdivisions), or 0 without one. */
  function beatsIn(doc, stop) {
    var m = stop.step.duration;
    return gridApplies(doc, m) ? num(m.value) * (doc.metric.subdivisions || 1) : 0;
  }

  /* Cues that belong on a stop: anchored to the step or to an ancestor. */
  function cuesFor(doc, stop) {
    var ids = {};
    ids[stop.step.id] = true;
    stop.parents.forEach(function (p) { ids[p.id] = true; });
    return (doc.cues || []).filter(function (c) { return ids[c.anchor.step]; });
  }

  /* The artifact roles the player can show. The renderers document the same
   * three; a step with artifacts but none of these is reported at render time. */
  var SHOWN_ROLES = ["clip", "gif", "poster"];

  /* width / height of an artifact when the document says them, else null */
  function ratioOf(a) { return a.width && a.height ? a.width / a.height : null; }

  function stemOf(uri) { return uri.replace(/\.[^./]+$/, ""); }

  /* Everything a step can show, main first. Each option is a looping clip with
   * its poster (paired by file name), or a gif, or a still. Order: options
   * marked attrs.main, then document order. `label` is attrs.label, else the
   * source role the artifact came from, else null (the caller names it). */
  function listMedia(step) {
    var arts = (step.artifacts || []).filter(function (a) { return SHOWN_ROLES.indexOf(a.role) >= 0; });
    var posters = arts.filter(function (a) { return a.role === "poster"; });
    var used = {};
    var options = [];
    function label(a) { return (a.attrs && a.attrs.label) || a.derivedFrom || null; }
    arts.forEach(function (a) {
      if (a.role !== "clip") return;
      var p = posters.filter(function (q) { return stemOf(q.uri) === stemOf(a.uri); })[0];
      if (p) used[p.uri] = true;
      options.push({ kind: "video", src: a.uri, mime: a.mime || "video/mp4", poster: p && p.uri, ratio: ratioOf(a),
        label: label(a), main: !!(a.attrs && a.attrs.main), variant: a.attrs && a.attrs.variant });
    });
    arts.forEach(function (a) {
      if (a.role === "gif") options.push({ kind: "image", src: a.uri, ratio: ratioOf(a), label: label(a), main: !!(a.attrs && a.attrs.main), variant: a.attrs && a.attrs.variant });
    });
    arts.forEach(function (a) {
      if (a.role === "poster" && !used[a.uri]) options.push({ kind: "image", still: true, src: a.uri, label: label(a), main: !!(a.attrs && a.attrs.main) });
    });
    var mains = options.filter(function (o) { return o.main; });
    var rest = options.filter(function (o) { return !o.main; });
    return mains.concat(rest);
  }

  /* The versions a viewer can choose between: the loops (video, gif). Stills
   * are not choices; they are shown only when there is nothing that moves. */
  function choices(options) {
    var loops = options.filter(function (o) { return !o.still; });
    if (!loops.length) return options.slice(0, 1);
    /* one choice per variant: an mp4 and a gif of one variant are one choice,
     * and the player takes the video (the first loop of the variant) */
    var seen = {}, out = [];
    loops.forEach(function (o, i) {
      var key = o.variant || ("#" + i);
      if (seen[key] === undefined) { seen[key] = out.length; out.push(o); }
      else if (o.kind === "video" && out[seen[key]].kind !== "video") out[seen[key]] = o;
    });
    return out;
  }

  /* The dosage a step carries (attrs.load, attrs.effort), as one short line. */
  function dosage(step) {
    var a = step.attrs || {};
    return [a.load, a.effort].filter(Boolean).join(" · ");
  }

  /* The main medium of a step, or null. */
  function pickMedia(step) {
    var list = listMedia(step);
    return list.length ? list[0] : null;
  }

  /* Cues grouped by kind in reading order: kinds in strings.kindFirst (set-up),
   * then cautions (strings.cautionKinds), then the rest in first-seen order.
   * Returns [{kind, label, caution, cues}]; an unknown kind is labelled with
   * its own name. */
  function groupCues(cues, strings) {
    var noticeKinds = strings.noticeKinds || [];
    cues = cues.filter(function (c) { return noticeKinds.indexOf(c.kind) < 0; });
    var kinds = [];
    cues.forEach(function (c) { if (kinds.indexOf(c.kind) < 0) kinds.push(c.kind); });
    var cautions = strings.cautionKinds || [], first = strings.kindFirst || [];
    function rank(k) { return first.indexOf(k) >= 0 ? 0 : cautions.indexOf(k) >= 0 ? 1 : 2; }
    var order = kinds.map(function (k, i) { return { k: k, i: i }; })
      .sort(function (x, y) { return rank(x.k) - rank(y.k) || x.i - y.i; });
    return order.map(function (o) {
      return { kind: o.k, label: (strings.cueKinds || {})[o.k] || o.k, caution: cautions.indexOf(o.k) >= 0,
        cues: cues.filter(function (c) { return c.kind === o.k; }) };
    });
  }

  /* Notices (kinds in strings.noticeKinds) are information, not instructions:
   * shown apart from the cues. */
  function notices(cues, strings) {
    var kinds = strings.noticeKinds || [];
    return cues.filter(function (c) { return kinds.indexOf(c.kind) >= 0; });
  }

  /* What a learner counts about the routine: its rounds, its steps (rests are
   * not steps) and, when every step counts in one unit, the total of that unit. */
  function learnerCounts(doc, stops) {
    var rounds = 0, perRound = 0, steps = 0, units = {}, total = 0;
    stops.forEach(function (s) {
      s.rounds.forEach(function (r) { rounds = Math.max(rounds, r.of); });
      if (isRest(s.step)) return;
      steps += 1;
      units[s.step.duration.unit] = true; total += num(s.step.duration.value);
      if (s.pos && s.pos.n === s.pos.of && s.rounds.length && perRound === 0) perRound = s.pos.of;
    });
    var unitNames = Object.keys(units);
    return { rounds: rounds, steps: rounds > 1 && perRound ? perRound : steps,
      total: unitNames.length === 1 ? total : null, unit: unitNames.length === 1 ? unitNames[0] : null };
  }

  /* At most `max` cues to show up front: every caution first, then the rest in
   * reading order; the remainder is for a disclosure. */
  function headCues(groups, max) {
    var flat = [];
    groups.forEach(function (g) { g.cues.forEach(function (c) { flat.push({ cue: c, group: g }); }); });
    var cautions = flat.filter(function (x) { return x.group.caution; });
    var shown = cautions.length >= max ? cautions : cautions.concat(
      flat.filter(function (x) { return !x.group.caution; }).slice(0, max - cautions.length));
    var set = shown.map(function (x) { return x.cue; });
    return { shown: set, hidden: flat.length - shown.length };
  }

  /* Ribbon colour for group g of n: a ramp between two colours. */
  function groupColour(g, n, from, to) {
    var t = n <= 1 ? 0 : g / (n - 1), out = [];
    for (var i = 0; i < 3; i++) out.push(Math.round(from[i] + (to[i] - from[i]) * t));
    return "rgb(" + out.join(",") + ")";
  }

  var api = { buildStops: buildStops, stopSeconds: stopSeconds, gridApplies: gridApplies,
    formatMeasure: formatMeasure, formatCount: formatCount, isLearnerLed: isLearnerLed,
    listMedia: listMedia, notices: notices, learnerCounts: learnerCounts, choices: choices, dosage: dosage, isRest: isRest, groupCues: groupCues, headCues: headCues, SHOWN_ROLES: SHOWN_ROLES, formatRound: formatRound, deepLink: deepLink,
    cuesFor: cuesFor, beatsIn: beatsIn, pickMedia: pickMedia, groupColour: groupColour };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PacesFlowCore = api;
})(typeof self !== "undefined" ? self : this);
