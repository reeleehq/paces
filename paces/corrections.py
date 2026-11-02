"""Human corrections as a replayable log of constraints (issue #10, ADR-0003 §4).

"Ask the user" is a first-class segmenter, and this module is the half of it
that decides how an answer *survives a re-run*: corrections re-enter as
constraints for the next run, never as a patch on an output that the next run
would overwrite (``docs/alignment/07 §7.5``).

Two rules from that section shape everything here:

- **Five verbs, constraints only.** ``pin`` ("it is HERE"), ``forbid`` ("it is
  not there"), ``absent`` ("not in this media"), ``split`` ("that is two
  steps") and ``merge`` ("those are one step"). ``rename`` is deliberately not
  a verb: a name is content and belongs in the document layer, which is what
  lets the log be replayed against a completely different segmenter.
- **Keyed by time, not by step id.** ``anchor_t`` is a point on the media clock;
  a step id invented by one run may mean something else in the next, a time
  does not.

How the log is honoured is a seam on the segmenter, not here: a capability
that lists ``"corrections"`` in ``reads`` receives the log as an input and
treats it as solver constraints (the alignment engine, issue #9, will). For
every other segmenter, :func:`segment` falls back to :func:`replay`, which
applies the log to the result in order. A correction is **never silently
dropped**: one that finds nothing to act on, or that would make the result
infeasible, is reported in ``Segmentation.flags``.

>>> from paces.segmenters import segment
>>> log = [split(15.0), merge(20.0)]
>>> seg = segment(boundaries=[0, 10, 20, 30], corrections=log)
>>> seg.boundaries
(0.0, 10.0, 15.0, 30.0)
>>> [s.spans for s in seg.steps]
[((0.0, 10.0),), ((10.0, 15.0),), ((15.0, 30.0),)]
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, get_args

from paces.model import decimal_str
from paces.segmentation import (  # noqa: F401 — TIME_PLACES/time_str re-exported
    DFLT_EXPLICIT_CONFIDENCE,
    TIME_PLACES,
    SegStep,
    Segmentation,
    Span,
    time_str,
)
from paces.segmentation import edges as _edges
from paces.segmentation import overlaps as _overlaps

Verb = Literal["pin", "forbid", "absent", "split", "merge"]
VERBS: tuple[str, ...] = get_args(Verb)

#: How far a ``merge`` time may sit from the boundary it means. A human taps
#: approximately; the machine finds the cut (``docs/alignment/07 §7.3`` step 3
#: snaps taps within ±1.5 s).
DFLT_MERGE_TOLERANCE_S = 1.5

#: The narrowest step a ``split`` may create. A split closer than this to an
#: existing cut is a tap on that cut, not a new step, so it is unmatched.
DFLT_MIN_STEP_S = 0.25


def _to_ms(value, *, what: str) -> float:
    """A finite time rounded to :data:`TIME_PLACES`, or a ``ValueError``."""
    if isinstance(value, bool):  # True is 1.0 to float(); never a time
        raise ValueError(f"{what} must be a time in seconds, got {value!r}")
    try:
        t = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{what} must be a time in seconds, got {value!r}") from None
    if not math.isfinite(t):
        raise ValueError(f"{what} must be a finite time, got {value!r}")
    return round(t, TIME_PLACES)


@dataclass(frozen=True, slots=True, kw_only=True)
class Correction:
    """One thing a human said about a segmentation, keyed by media time.

    ``step_id`` is for display only and is NEVER the join key: replay finds
    its target by ``anchor_t``. ``media_key`` records which rendering of the
    media the correction was true of, so a later re-cut can migrate the log.
    Times are kept to the millisecond (:data:`TIME_PLACES`), so the wire form
    round-trips exactly.

    >>> split(0.8550444).anchor_t
    0.855
    """

    verb: Verb
    anchor_t: float  # WHERE on the media clock — the durable key
    span: Span | None = None  # pin: where it is; forbid: where it is not
    step_id: str | None = None
    author: str = ""
    at: str = ""  # ISO-8601 timestamp
    media_key: str | None = None
    reason: str = ""

    def __post_init__(self):
        for name in ("author", "at", "reason"):
            if not isinstance(getattr(self, name), str):
                raise ValueError(
                    f"{name} must be a string, got {getattr(self, name)!r}"
                )
        for name in ("step_id", "media_key"):
            if getattr(self, name) is not None and not isinstance(
                getattr(self, name), str
            ):
                raise ValueError(
                    f"{name} must be a string or None, got {getattr(self, name)!r}"
                )
        if self.verb not in VERBS:
            raise ValueError(f"unknown verb {self.verb!r}; expected one of {VERBS}")
        object.__setattr__(self, "anchor_t", _to_ms(self.anchor_t, what="anchor_t"))
        needs_span = self.verb in ("pin", "forbid")
        if needs_span != (self.span is not None):
            raise ValueError(
                f"{self.verb!r} {'needs' if needs_span else 'takes no'} span="
            )
        if self.span is not None:
            if not isinstance(self.span, (tuple, list)) or len(self.span) != 2:
                raise ValueError(f"span must be (start, end), got {self.span!r}")
            start, end = (_to_ms(t, what="span") for t in self.span)
            if not start < end:
                raise ValueError(
                    f"span must be (start, end) with start < end: {self.span}"
                )
            if self.verb == "pin" and not start <= self.anchor_t < end:
                raise ValueError(
                    f"a pin's anchor_t ({self.anchor_t}) must lie inside its span {self.span}"
                )
            object.__setattr__(self, "span", (start, end))

    @property
    def label(self) -> str:
        """``'split@95.8'`` — how flags name this correction."""
        return f"{self.verb}@{decimal_str(self.anchor_t, places=TIME_PLACES)}"


# ── the five verbs ──────────────────────────────────────────────────────────


def pin(span: Span, *, anchor_t: float | None = None, **meta) -> Correction:
    """Pin — "the step is HERE": the step covering ``anchor_t`` (default: the span's
    midpoint) occupies exactly ``span``."""
    span = tuple(span)
    if anchor_t is None and len(span) == 2:
        anchor_t = (float(span[0]) + float(span[1])) / 2
    return Correction(verb="pin", anchor_t=anchor_t, span=span, **meta)


def forbid(anchor_t: float, span: Span, **meta) -> Correction:
    """Forbid — "the step at ``anchor_t`` is not in ``span``"."""
    return Correction(verb="forbid", anchor_t=anchor_t, span=tuple(span), **meta)


def absent(anchor_t: float, **meta) -> Correction:
    """Absent — "the step placed at ``anchor_t`` is not in this media"."""
    return Correction(verb="absent", anchor_t=anchor_t, **meta)


def split(at_t: float, **meta) -> Correction:
    """Split — "that is two steps": cut the step covering ``at_t`` there (K += 1)."""
    return Correction(verb="split", anchor_t=at_t, **meta)


def merge(at_t: float, **meta) -> Correction:
    """Merge — "those are one step": remove the cut nearest ``at_t`` (K -= 1)."""
    return Correction(verb="merge", anchor_t=at_t, **meta)


# ── wire form (no floats on the wire, docs/07 §6.5) ─────────────────────────

_WIRE_KEYS = {
    "verb": "verb",
    "anchor_t": "anchorT",
    "span": "span",
    "step_id": "stepId",
    "author": "author",
    "at": "at",
    "media_key": "mediaKey",
    "reason": "reason",
}
_REQUIRED_WIRE_KEYS = ("verb", "anchorT")


def to_wire(correction: Correction) -> dict:
    """A JSON-ready dict: camelCase keys, times as decimal strings, defaults omitted."""
    wire: dict = {"verb": correction.verb, "anchorT": time_str(correction.anchor_t)}
    if correction.span is not None:
        wire["span"] = [time_str(t) for t in correction.span]
    for field_name in ("step_id", "author", "at", "media_key", "reason"):
        value = getattr(correction, field_name)
        if value:
            wire[_WIRE_KEYS[field_name]] = value
    return wire


def from_wire(wire: Mapping) -> Correction:
    """Parse one wire dict. Unknown or missing keys raise ``ValueError`` (a typo
    must not vanish, and a correction without a verb or a time is not one).

    >>> from_wire({"verb": "split", "anchorT": "95.8"}) == split(95.8)
    True
    """
    if not isinstance(wire, Mapping):
        raise ValueError(f"a correction must be a mapping, got {wire!r}")
    by_wire = {w: f for f, w in _WIRE_KEYS.items()}
    unknown = sorted(set(wire) - set(by_wire))
    if unknown:
        raise ValueError(f"unknown correction keys {unknown}; known: {sorted(by_wire)}")
    missing = [key for key in _REQUIRED_WIRE_KEYS if key not in wire]
    if missing:
        raise ValueError(f"correction {dict(wire)} is missing {missing}")
    kwargs = {by_wire[key]: value for key, value in wire.items()}
    span = kwargs.get("span")
    if span is not None:
        if not isinstance(span, (list, tuple)):
            raise ValueError(f"span must be a [start, end] list, got {span!r}")
        kwargs["span"] = tuple(span)
    return Correction(**kwargs)


def normalize_corrections(
    corrections: Iterable[Correction | Mapping] | None,
) -> tuple[Correction, ...]:
    """Accept :class:`Correction` objects or their wire dicts, in log order.

    A log is a *sequence*: one correction passed bare (a mapping) is refused
    rather than iterated over its keys.

    >>> normalize_corrections({"verb": "split", "anchorT": "1"})
    Traceback (most recent call last):
    ...
    ValueError: corrections must be a list of corrections, got a single mapping; wrap it in a list
    """
    if corrections is None:
        return ()
    if isinstance(corrections, (Mapping, Correction)):
        kind = "mapping" if isinstance(corrections, Mapping) else "Correction"
        raise ValueError(
            f"corrections must be a list of corrections, got a single {kind}; "
            "wrap it in a list"
        )
    if isinstance(corrections, (str, bytes)) or not isinstance(corrections, Iterable):
        raise ValueError(
            f"corrections must be a list of corrections, got {corrections!r:.80}"
        )
    return tuple(c if isinstance(c, Correction) else from_wire(c) for c in corrections)


# ── replay: the fallback for segmenters that do not read the log ────────────


@dataclass(frozen=True, slots=True)
class _State:
    """What replay threads through the log: the steps and the cut set."""

    steps: tuple[SegStep, ...]
    boundaries: frozenset[float]
    seen_ids: frozenset[str] = frozenset()  # never reused: a forbid names one


@dataclass(frozen=True, slots=True)
class _Options:
    merge_tolerance_s: float
    min_step_s: float
    cuts_only: bool  # decided once, from the input: no steps, only boundaries


@dataclass(frozen=True, slots=True)
class _PendingForbid:
    """A forbid's target, resolved at its log position, judged after the log."""

    correction: Correction
    step_id: str


def replay(
    seg: Segmentation,
    corrections: Iterable[Correction | Mapping],
    *,
    merge_tolerance_s: float = DFLT_MERGE_TOLERANCE_S,
    min_step_s: float = DFLT_MIN_STEP_S,
) -> Segmentation:
    """Apply a correction log to a segmentation, in log order.

    Each correction acts on the result of the ones before it, as the human
    made them. Applied ones are flagged ``corrected: <verb>@<t>``; one that
    finds nothing to act on is flagged ``correction-unmatched``, one that
    would leave an empty, inverted or overlapping span
    ``correction-infeasible`` (and changes nothing). A ``forbid`` is judged
    against the *final* placement: ``satisfied: forbid@<t>``, or
    ``correction-unenforced`` — moving a step elsewhere needs a solver, which
    replay is not. A pin that clips a child step out of existence says so
    (``correction-clipped``). Checking the result is not replay's job:
    :func:`paces.segmenters.segment` runs
    :func:`~paces.segmentation.inconsistencies` on every segmentation. A log
    in which no correction edits the cut set leaves ``boundaries`` exactly as
    given (duplicates included); once one does, they are rebuilt from it.

    >>> seg = Segmentation(steps=(SegStep(id="a", spans=((0.0, 10.0),)),),
    ...                    boundaries=(0.0, 10.0))
    >>> replay(seg, [split(5), split(5.1)]).flags
    ('corrected: split@5', 'correction-unmatched: split@5.1 (within 0.25 s of a cut)')
    """
    options = _Options(
        merge_tolerance_s=merge_tolerance_s,
        min_step_s=min_step_s,
        cuts_only=not seg.steps,
    )
    state = _State(
        steps=tuple(seg.steps),
        boundaries=frozenset(seg.boundaries),
        seen_ids=frozenset(step.id for step in seg.steps),
    )
    outcomes: list = []
    cuts_touched = False  # once a correction edits the cut set, it is rebuilt
    for correction in normalize_corrections(corrections):
        before = state.boundaries
        state, outcome = _APPLY[correction.verb](state, correction, options)
        cuts_touched = cuts_touched or state.boundaries != before
        outcomes.append(outcome)
    flags = tuple(_final_flags(state.steps, outcomes))
    unchanged = not cuts_touched
    return dataclasses.replace(
        seg,
        steps=state.steps,
        boundaries=seg.boundaries if unchanged else tuple(sorted(state.boundaries)),
        flags=seg.flags + flags,
    )


# ── small pure helpers over spans ───────────────────────────────────────────


def _covering(steps: Sequence[SegStep], t: float) -> tuple[int, int] | None:
    """(step index, span index) of the first span with ``start <= t < end``."""
    for i, step in enumerate(steps):
        for j, (start, end) in enumerate(step.spans):
            if start <= t < end:
                return i, j
    return None


def _edges_at(steps: Sequence[SegStep], t: float, side: int) -> list[tuple[int, int]]:
    """(step, span) indices of every span whose start (``side=0``) or end
    (``side=1``) is exactly ``t``."""
    return [
        (i, j)
        for i, step in enumerate(steps)
        for j, span in enumerate(step.spans)
        if span[side] == t
    ]


def _falls_in(child: SegStep, span: Span) -> bool:
    """A child belongs to the parent span its first span starts in."""
    return bool(child.spans) and span[0] <= child.spans[0][0] < span[1]


def _with_span(step: SegStep, j: int, span: Span | None) -> SegStep:
    """``step`` with span ``j`` replaced (or removed, for ``None``)."""
    spans = list(step.spans)
    if span is None:
        del spans[j]
    else:
        spans[j] = span
    return dataclasses.replace(step, spans=tuple(spans))


def _nearest(candidates: Iterable[float], t: float, tolerance: float) -> float | None:
    """The candidate nearest ``t`` within ``tolerance``; ties go to the earlier."""
    near = [b for b in candidates if abs(b - t) <= tolerance]
    return min(near, key=lambda b: (abs(b - t), b)) if near else None


def _too_close(t: float, cuts: Iterable[float], min_step_s: float) -> str:
    """Why a split at ``t`` is not a new step, or ``''`` when it is one."""
    gap = min(abs(t - cut) for cut in cuts)
    if gap == 0:
        return "already a cut there"
    if gap < min_step_s:
        return f"within {time_str(min_step_s)} s of a cut"
    return ""


def _done(state: _State, correction: Correction, *extra: str):
    return state, (f"corrected: {correction.label}",) + extra


def _unmatched(state: _State, correction: Correction, why: str):
    return state, (f"correction-unmatched: {correction.label} ({why})",)


def _infeasible(state: _State, correction: Correction, why: str):
    return state, (f"correction-infeasible: {correction.label} ({why})",)


# ── the verbs, replayed (each: state, correction, options → state, outcome) ─


def _apply_split(state: _State, correction: Correction, options: _Options):
    t = correction.anchor_t
    if options.cuts_only:
        return _split_cuts(state, correction, options)
    hit = _covering(state.steps, t)
    if hit is None:
        return _unmatched(state, correction, "no step spans that time")
    i, j = hit
    step = state.steps[i]
    start, end = step.spans[j]
    why = _too_close(t, (start, end), options.min_step_s)
    if why:
        return _unmatched(state, correction, why)
    to_tail = [_falls_in(c, (t, end)) for c in step.children]
    taken = state.seen_ids
    tail_id = next(
        f"{step.id}-{n}"
        for n in range(2, len(taken) + 3)
        if f"{step.id}-{n}" not in taken
    )
    tail = SegStep(
        id=tail_id,
        spans=((t, end),),
        confidence=DFLT_EXPLICIT_CONFIDENCE,
        children=tuple(c for c, moves in zip(step.children, to_tail) if moves),
        source="correction",
        evidence={"correction": correction.label, "split_from": step.id},
    )
    head = dataclasses.replace(
        _with_span(step, j, (start, t)),
        children=tuple(c for c, moves in zip(step.children, to_tail) if not moves),
    )
    # a head child that ran past the cut is trimmed to it (it starts before t,
    # so it is never emptied)
    head, _ = _clip_children(head, (start, t), (start, t))
    steps = state.steps[:i] + (head, tail) + state.steps[i + 1 :]
    return _done(
        dataclasses.replace(
            state,
            steps=steps,
            boundaries=state.boundaries | {t},
            seen_ids=state.seen_ids | {tail_id},
        ),
        correction,
    )


def _split_cuts(state: _State, correction: Correction, options: _Options):
    """Split over a boundaries-only segmentation: add the cut."""
    t, cuts = correction.anchor_t, sorted(state.boundaries)
    interval = next(((a, b) for a, b in zip(cuts, cuts[1:]) if a <= t < b), None)
    if interval is None:
        return _unmatched(state, correction, "no step spans that time")
    why = _too_close(t, interval, options.min_step_s)
    if why:
        return _unmatched(state, correction, why)
    return _done(
        dataclasses.replace(state, boundaries=state.boundaries | {t}), correction
    )


def _meeting_cuts(steps: Sequence[SegStep]) -> dict[float, tuple]:
    """``{cut: ((li, lj), (ri, rj))}`` for every time where a span of one step
    ends and a span of a *different* step starts (both non-empty)."""
    starting: dict[float, list[tuple[int, int]]] = {}
    for ri, step in enumerate(steps):
        for rj, (start, _) in enumerate(step.spans):
            starting.setdefault(start, []).append((ri, rj))
    meets: dict[float, tuple] = {}
    for li, step in enumerate(steps):
        for lj, (lo, cut) in enumerate(step.spans):
            for ri, rj in starting.get(cut, ()):
                if ri != li and lo < cut < steps[ri].spans[rj][1]:
                    meets.setdefault(cut, ((li, lj), (ri, rj)))
    return meets


def _apply_merge(state: _State, correction: Correction, options: _Options):
    if options.cuts_only:
        return _merge_cuts(state, correction, options)
    t, tolerance = correction.anchor_t, options.merge_tolerance_s
    meets = _meeting_cuts(state.steps)
    if t in state.boundaries and t not in meets:
        # exactly on a cut that joins no two steps (e.g. the edge of an absent
        # step): the human meant THAT cut, so another one nearby is not a match
        return _unmatched(state, correction, "no two steps meet at that exact cut")
    cut = _nearest(meets, t, tolerance)
    if cut is None:
        within = f"within {time_str(tolerance)} s"
        if _nearest(state.boundaries, t, tolerance) is None:
            return _unmatched(state, correction, f"no cut {within}")
        return _unmatched(state, correction, f"no two steps meet {within}")
    (li, lj), (ri, rj) = meets[cut]
    steps = list(state.steps)
    left, right = steps[li], steps[ri]
    absorbed = right.spans[rj]
    moving = [_falls_in(c, absorbed) for c in right.children]
    left = dataclasses.replace(
        _with_span(left, lj, (left.spans[lj][0], absorbed[1])),
        children=left.children + tuple(c for c, m in zip(right.children, moving) if m),
    )
    right = dataclasses.replace(
        _with_span(right, rj, None),
        children=tuple(c for c, m in zip(right.children, moving) if not m),
    )
    if right.spans:  # the right step lives on elsewhere: it keeps its identity
        steps[li], steps[ri] = left, right
    else:  # fully absorbed: it is gone, and the merged step keeps a visible name
        children = left.children + right.children
        # keep the record a human can see: an unnamed left step yields to the
        # named right one (its id, name, source, evidence), not just its label
        survivor = right if (not left.name and right.name) else left
        steps[li] = dataclasses.replace(survivor, spans=left.spans, children=children)
        del steps[ri]
    still_an_edge = cut in _edges(steps)
    boundaries = state.boundaries if still_an_edge else state.boundaries - {cut}
    return _done(
        dataclasses.replace(state, steps=tuple(steps), boundaries=boundaries),
        correction,
    )


def _merge_cuts(state: _State, correction: Correction, options: _Options):
    """Merge over a boundaries-only segmentation: remove the interior cut."""
    tolerance = options.merge_tolerance_s
    interior = sorted(state.boundaries)[1:-1]
    if correction.anchor_t in state.boundaries and correction.anchor_t not in interior:
        return _unmatched(state, correction, "that is an end, not a cut between steps")
    cut = _nearest(interior, correction.anchor_t, tolerance)
    if cut is None:
        return _unmatched(state, correction, f"no cut within {time_str(tolerance)} s")
    return _done(
        dataclasses.replace(state, boundaries=state.boundaries - {cut}), correction
    )


def _neighbour(steps, t: float, side: int, exclude: tuple[int, int]):
    """The time-order neighbour abutting at ``t``: of the spans ending
    (``side=1``) or starting (``side=0``) there, the one nearest in time."""
    found = [hit for hit in _edges_at(steps, t, side) if hit != exclude]
    if not found:
        return None
    # ending at t: the latest-starting is nearest; starting at t: the earliest-ending
    other = 0 if side == 1 else 1
    sign = -1 if side == 1 else 1
    return min(found, key=lambda h: sign * steps[h[0]].spans[h[1]][other])


def _clip_children(step: SegStep, old: Span, new: Span) -> tuple[SegStep, list[str]]:
    """Clip the children of span ``old`` to ``new``; drop (and name) any left empty."""
    kept, dropped = [], []
    for child in step.children:
        if not _falls_in(child, old):
            kept.append(child)
            continue
        spans = tuple(
            (max(s, new[0]), min(e, new[1])) if old[0] <= s < old[1] else (s, e)
            for s, e in child.spans
        )
        spans = tuple(sp for sp in spans if sp[0] < sp[1])
        if spans:
            kept.append(dataclasses.replace(child, spans=spans))
        else:
            dropped.append(child.id)
    return dataclasses.replace(step, children=tuple(kept)), dropped


def _apply_pin(state: _State, correction: Correction, _options: _Options):
    hit = _covering(state.steps, correction.anchor_t)
    if hit is None:
        return _unmatched(state, correction, "no step spans that time")
    i, j = hit
    steps = state.steps
    old, new = steps[i].spans[j], correction.span
    # Only the immediate neighbours that abut the pinned span move with it —
    # the replay analogue of "one pin re-solves its neighbours".
    moves = {hit: new}
    before = _neighbour(steps, old[0], side=1, exclude=hit)
    after = _neighbour(steps, old[1], side=0, exclude=hit)
    if before is not None:
        moves[before] = (steps[before[0]].spans[before[1]][0], new[0])
    if after is not None:
        moves[after] = (new[1], steps[after[0]].spans[after[1]][1])
    if any(start >= end for start, end in moves.values()):
        return _infeasible(state, correction, "would empty a neighbouring step")
    moved = [
        tuple(moves.get((k, l), span) for l, span in enumerate(step.spans))
        for k, step in enumerate(steps)
    ]
    clash = next(
        (
            steps[k].id
            for k, spans in enumerate(moved)
            for l, span in enumerate(spans)
            if (k, l) != hit and _overlaps(span, new)
        ),
        None,
    )
    if clash is not None:
        return _infeasible(state, correction, f"would overlap step {clash!r}")
    new_steps, dropped = list(steps), []
    for (k, l), span in moves.items():
        step = dataclasses.replace(new_steps[k], spans=moved[k])
        new_steps[k], lost = _clip_children(step, steps[k].spans[l], span)
        dropped += [f"{child!r} of {step.id!r}" for child in lost]
    new_steps[i] = dataclasses.replace(
        new_steps[i], confidence=DFLT_EXPLICIT_CONFIDENCE
    )
    edges = _edges(new_steps)
    boundaries = {b for b in state.boundaries if b in edges or b not in old} | set(new)
    extra = tuple(
        f"correction-clipped: {correction.label} (dropped child {name}: "
        "outside its step's new span)"
        for name in dropped
    )
    new_state = dataclasses.replace(
        state, steps=tuple(new_steps), boundaries=frozenset(boundaries)
    )
    return _done(new_state, correction, *extra)


def _apply_forbid(state: _State, correction: Correction, _options: _Options):
    hit = _covering(state.steps, correction.anchor_t)
    if hit is None:
        return _unmatched(state, correction, "no step spans that time")
    # Judged after the whole log (see _final_flags): a later pin may move the
    # step into the forbidden span, or out of it.
    return state, _PendingForbid(correction, state.steps[hit[0]].id)


def _apply_absent(state: _State, correction: Correction, _options: _Options):
    hit = _covering(state.steps, correction.anchor_t)
    if hit is None:
        return _unmatched(state, correction, "no step spans that time")
    # the cuts stay: the time is still there, just not this step
    steps = state.steps[: hit[0]] + state.steps[hit[0] + 1 :]
    return _done(dataclasses.replace(state, steps=steps), correction)


_APPLY = {
    "split": _apply_split,
    "merge": _apply_merge,
    "pin": _apply_pin,
    "forbid": _apply_forbid,
    "absent": _apply_absent,
}
assert set(_APPLY) == set(VERBS), "every verb needs exactly one replay rule"


# ── after the log: judge the forbids, check the result is consistent ────────


def _forbid_flag(steps: Sequence[SegStep], pending: _PendingForbid) -> str:
    """``satisfied:`` or ``correction-unenforced:`` for one forbid, on the final
    steps. Its target is the step it named at its log position, or — if that
    step is gone — whatever now covers its time."""
    correction = pending.correction
    target = next((s for s in steps if s.id == pending.step_id), None)
    if target is None:
        hit = _covering(steps, correction.anchor_t)
        target = steps[hit[0]] if hit else None
    if target is None or not any(_overlaps(sp, correction.span) for sp in target.spans):
        return f"satisfied: {correction.label}"
    return (
        f"correction-unenforced: {correction.label} (step {target.id!r} "
        "overlaps the forbidden span; moving it needs a solver)"
    )


def _final_flags(steps: Sequence[SegStep], outcomes: Iterable) -> Iterable[str]:
    for outcome in outcomes:
        if isinstance(outcome, _PendingForbid):
            yield _forbid_flag(steps, outcome)
        else:
            yield from outcome
