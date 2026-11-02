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
from paces.segmenters import (
    DFLT_EXPLICIT_CONFIDENCE,
    SegStep,
    Segmentation,
    Span,
)

Verb = Literal["pin", "forbid", "absent", "split", "merge"]
VERBS: tuple[str, ...] = get_args(Verb)

#: How far a ``merge`` time may sit from the boundary it means. A human taps
#: approximately; the machine finds the cut (``docs/alignment/07 §7.3`` step 3
#: snaps taps within ±1.5 s).
DFLT_MERGE_TOLERANCE_S = 1.5


@dataclass(frozen=True, slots=True, kw_only=True)
class Correction:
    """One thing a human said about a segmentation, keyed by media time.

    ``step_id`` is for display only and is NEVER the join key: replay finds
    its target by ``anchor_t``. ``media_key`` records which rendering of the
    media the correction was true of, so a later re-cut can migrate the log.
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
        if self.verb not in VERBS:
            raise ValueError(f"unknown verb {self.verb!r}; expected one of {VERBS}")
        if not math.isfinite(self.anchor_t):
            raise ValueError(f"anchor_t must be a finite time, got {self.anchor_t!r}")
        needs_span = self.verb in ("pin", "forbid")
        if needs_span != (self.span is not None):
            raise ValueError(
                f"{self.verb!r} {'needs' if needs_span else 'takes no'} span="
            )
        if self.span is not None:
            start, end = self.span
            if not (math.isfinite(start) and math.isfinite(end) and start < end):
                raise ValueError(
                    f"span must be (start, end) with start < end: {self.span}"
                )
            if self.verb == "pin" and not start <= self.anchor_t <= end:
                raise ValueError(
                    f"a pin's anchor_t ({self.anchor_t}) must lie inside its span {self.span}"
                )

    @property
    def label(self) -> str:
        """``'split@95.8'`` — how flags name this correction."""
        return f"{self.verb}@{decimal_str(self.anchor_t)}"


# ── the five verbs ──────────────────────────────────────────────────────────


def pin(span: Span, *, anchor_t: float | None = None, **meta) -> Correction:
    """Pin — "the step is HERE": the step covering ``anchor_t`` (default: the span's
    midpoint) occupies exactly ``span``."""
    start, end = map(float, span)
    anchor = (start + end) / 2 if anchor_t is None else float(anchor_t)
    return Correction(verb="pin", anchor_t=anchor, span=(start, end), **meta)


def forbid(anchor_t: float, span: Span, **meta) -> Correction:
    """Forbid — "the step at ``anchor_t`` is not in ``span``"."""
    return Correction(
        verb="forbid", anchor_t=float(anchor_t), span=tuple(map(float, span)), **meta
    )


def absent(anchor_t: float, **meta) -> Correction:
    """Absent — "the step placed at ``anchor_t`` is not in this media"."""
    return Correction(verb="absent", anchor_t=float(anchor_t), **meta)


def split(at_t: float, **meta) -> Correction:
    """Split — "that is two steps": cut the step covering ``at_t`` there (K += 1)."""
    return Correction(verb="split", anchor_t=float(at_t), **meta)


def merge(at_t: float, **meta) -> Correction:
    """Merge — "those are one step": remove the cut nearest ``at_t`` (K -= 1)."""
    return Correction(verb="merge", anchor_t=float(at_t), **meta)


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


def to_wire(correction: Correction) -> dict:
    """A JSON-ready dict: camelCase keys, times as decimal strings, defaults omitted."""
    wire: dict = {"verb": correction.verb, "anchorT": decimal_str(correction.anchor_t)}
    if correction.span is not None:
        wire["span"] = [decimal_str(t) for t in correction.span]
    for field_name in ("step_id", "author", "at", "media_key", "reason"):
        value = getattr(correction, field_name)
        if value:
            wire[_WIRE_KEYS[field_name]] = value
    return wire


def from_wire(wire: Mapping) -> Correction:
    """Parse one wire dict; unknown keys raise (a typo must not vanish)."""
    by_wire = {w: f for f, w in _WIRE_KEYS.items()}
    unknown = sorted(set(wire) - set(by_wire))
    if unknown:
        raise ValueError(f"unknown correction keys {unknown}; known: {sorted(by_wire)}")
    kwargs = {by_wire[key]: value for key, value in wire.items()}
    kwargs["anchor_t"] = float(kwargs["anchor_t"])
    if kwargs.get("span") is not None:
        kwargs["span"] = tuple(float(t) for t in kwargs["span"])
    return Correction(**kwargs)


def normalize_corrections(
    corrections: Iterable[Correction | Mapping] | None,
) -> tuple[Correction, ...]:
    """Accept :class:`Correction` objects or their wire dicts, in log order."""
    return tuple(
        c if isinstance(c, Correction) else from_wire(c) for c in corrections or ()
    )


# ── replay: the fallback for segmenters that do not read the log ────────────


def replay(
    seg: Segmentation,
    corrections: Iterable[Correction | Mapping],
    *,
    merge_tolerance_s: float = DFLT_MERGE_TOLERANCE_S,
) -> Segmentation:
    """Apply a correction log to a segmentation, in log order.

    Each correction acts on the result of the ones before it, as the human
    made them. Applied ones are flagged ``corrected: <verb>@<t>``; one that
    finds nothing to act on is flagged ``correction-unmatched``, one that
    would leave an empty or inverted span ``correction-infeasible``, and a
    ``forbid`` the current placement violates ``correction-unenforced`` —
    moving a step elsewhere needs a solver, which replay is not.
    """
    steps = list(seg.steps)
    boundaries = set(seg.boundaries)
    flags: list[str] = []
    for correction in normalize_corrections(corrections):
        apply = _APPLY[correction.verb]
        outcome = apply(steps, boundaries, correction, merge_tolerance_s)
        flags.append(outcome or f"corrected: {correction.label}")
    return dataclasses.replace(
        seg,
        steps=tuple(steps),
        boundaries=tuple(sorted(boundaries)),
        flags=seg.flags + tuple(flags),
    )


def _covering(steps: Sequence[SegStep], t: float) -> tuple[int, int] | None:
    """(step index, span index) of the first span with ``start <= t < end``."""
    for i, step in enumerate(steps):
        for j, (start, end) in enumerate(step.spans):
            if start <= t < end:
                return i, j
    return None


def _with_span(step: SegStep, j: int, span: Span | None) -> SegStep:
    """``step`` with span ``j`` replaced (or removed, for ``None``)."""
    spans = list(step.spans)
    if span is None:
        del spans[j]
    else:
        spans[j] = span
    return dataclasses.replace(step, spans=tuple(spans))


def _unmatched(correction: Correction, why: str) -> str:
    return f"correction-unmatched: {correction.label} ({why})"


def _apply_split(steps, boundaries, correction, _tolerance) -> str | None:
    t = correction.anchor_t
    hit = _covering(steps, t)
    if hit is None or steps[hit[0]].spans[hit[1]][0] == t:
        return _unmatched(correction, "no step spans that time")
    i, j = hit
    step = steps[i]
    start, end = step.spans[j]
    taken = {s.id for s in steps}
    new_id = next(
        f"{step.id}-{n}"
        for n in range(2, len(taken) + 3)
        if f"{step.id}-{n}" not in taken
    )
    tail = SegStep(
        id=new_id,
        spans=((t, end),),
        confidence=DFLT_EXPLICIT_CONFIDENCE,
        children=tuple(c for c in step.children if c.spans and c.spans[0][0] >= t),
        source="correction",
        evidence={"correction": correction.label, "split_from": step.id},
    )
    head = dataclasses.replace(
        _with_span(step, j, (start, t)),
        children=tuple(
            c for c in step.children if not (c.spans and c.spans[0][0] >= t)
        ),
    )
    steps[i : i + 1] = [head, tail]
    boundaries.add(t)
    return None


def _apply_merge(steps, boundaries, correction, tolerance) -> str | None:
    t = correction.anchor_t
    near = [b for b in boundaries if abs(b - t) <= tolerance]
    if not near:
        return _unmatched(correction, f"no cut within {decimal_str(tolerance)} s")
    cut = min(near, key=lambda b: (abs(b - t), b))
    left = next(
        (
            (i, j)
            for i, s in enumerate(steps)
            for j, sp in enumerate(s.spans)
            if sp[1] == cut
        ),
        None,
    )
    right = next(
        (
            (i, j)
            for i, s in enumerate(steps)
            for j, sp in enumerate(s.spans)
            if sp[0] == cut
        ),
        None,
    )
    if left is None or right is None or left[0] == right[0]:
        return _unmatched(correction, "no two steps meet at that cut")
    (li, lj), (ri, rj) = left, right
    absorbed_end = steps[ri].spans[rj][1]
    left_step = _with_span(steps[li], lj, (steps[li].spans[lj][0], absorbed_end))
    right_step = _with_span(steps[ri], rj, None)
    if not left_step.name and right_step.name:  # keep the name a human can see
        left_step = dataclasses.replace(
            left_step, id=right_step.id, name=right_step.name
        )
        right_step = dataclasses.replace(right_step, id=steps[li].id, name="")
    if right_step.spans:
        steps[li], steps[ri] = left_step, right_step
    else:  # the right step was only that span: it is gone, its children move left
        steps[li] = dataclasses.replace(
            left_step, children=left_step.children + right_step.children
        )
        del steps[ri]
    boundaries.discard(cut)
    return None


def _apply_pin(steps, boundaries, correction, _tolerance) -> str | None:
    hit = _covering(steps, correction.anchor_t)
    if hit is None:
        return _unmatched(correction, "no step spans that time")
    i, j = hit
    old_start, old_end = steps[i].spans[j]
    new_start, new_end = correction.span
    moves = {old_start: new_start, old_end: new_end}

    def _moved(span: Span) -> Span:
        return (moves.get(span[0], span[0]), moves.get(span[1], span[1]))

    # Neighbours that abut the pinned span move with it — the replay analogue
    # of "one pin re-solves its neighbours".
    moved = [[_moved(sp) for sp in s.spans] for s in steps]
    moved[i][j] = (new_start, new_end)
    if any(start >= end for spans in moved for start, end in spans):
        return f"correction-infeasible: {correction.label} (would empty a neighbouring step)"
    for k, step in enumerate(steps):
        spans = tuple(moved[k])
        if spans != step.spans or k == i:
            steps[k] = dataclasses.replace(step, spans=spans)
    steps[i] = dataclasses.replace(steps[i], confidence=DFLT_EXPLICIT_CONFIDENCE)
    for old, new in moves.items():
        if old in boundaries:
            boundaries.discard(old)
            boundaries.add(new)
    return None


def _apply_forbid(steps, _boundaries, correction, _tolerance) -> str | None:
    hit = _covering(steps, correction.anchor_t)
    if hit is None:
        return _unmatched(correction, "no step spans that time")
    i, _ = hit
    lo, hi = correction.span
    if any(start < hi and lo < end for start, end in steps[i].spans):
        return (
            f"correction-unenforced: {correction.label} (step {steps[i].id!r} "
            "overlaps the forbidden span; moving it needs a solver)"
        )
    return None


def _apply_absent(steps, _boundaries, correction, _tolerance) -> str | None:
    hit = _covering(steps, correction.anchor_t)
    if hit is None:
        return _unmatched(correction, "no step spans that time")
    del steps[hit[0]]  # the cuts stay: the time is still there, just not this step
    return None


_APPLY = {
    "split": _apply_split,
    "merge": _apply_merge,
    "pin": _apply_pin,
    "forbid": _apply_forbid,
    "absent": _apply_absent,
}
