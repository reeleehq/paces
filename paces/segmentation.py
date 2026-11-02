"""What a segmenter returns: :class:`Segmentation`, its :class:`SegStep` records and
the ``Span`` they cover — the analysis-result types, with nothing else.

They live apart from :mod:`paces.segmenters` (the registry and the
``segment()`` facade) so a module that only consumes or reshapes a result —
:mod:`paces.corrections`, :mod:`paces.projection`, :mod:`paces.ask`, the
evidence layer — depends on the types and not on the facade, and the facade
can import those modules without a cycle. :mod:`paces.segmenters` re-exports
every name here, so ``from paces.segmenters import Segmentation`` keeps
working.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from paces.model import MetricGrid, decimal_str

__all__ = [
    "DFLT_CHAPTERS_CONFIDENCE",
    "DFLT_EXPLICIT_CONFIDENCE",
    "DFLT_GRID_CONFIDENCE",
    "SegStep",
    "Segmentation",
    "Span",
    "TIME_PLACES",
    "edges",
    "inconsistencies",
    "overlaps",
    "time_str",
]

#: Decimal places every computed time keeps (spans, boundaries, corrections): milliseconds, the wire's
#: resolution. Corrections round to it at construction, so their wire round trip
#: is lossless (``decimal_str`` writes exactly this many).
TIME_PLACES = 3


Span = tuple[float, float]  # seconds, half-open

# Confidence constants: placement from user-supplied inputs is arithmetic, so
# what these grade is trust in the inputs, not in any inference.
DFLT_EXPLICIT_CONFIDENCE = 0.95  # a human said so
DFLT_GRID_CONFIDENCE = 0.9  # exact given the grid; the grid itself may drift
DFLT_CHAPTERS_CONFIDENCE = 0.9  # the author said so, in metadata


@dataclass(frozen=True, slots=True, kw_only=True)
class SegStep:
    """One named piece of the media, as an analysis result.

    ``name=''`` means "found, not named" — a VALID state, not an error.
    ``spans`` is a tuple because a step legitimately appears in several places
    (run-through AND breakdown).
    """

    id: str
    name: str = ""
    spans: tuple[Span, ...] = ()
    confidence: float = 0.0
    children: tuple["SegStep", ...] = ()
    source: str = ""  # which capability produced it
    evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class Segmentation:
    """What every segmenter returns. Reviewable, re-runnable, arguable.

    ``boundaries`` is separate from ``steps`` and populated even when naming
    failed: nine excellent unnamed cuts are a useful, honest result. ``steps``
    may be empty while ``boundaries`` is not.
    """

    steps: tuple[SegStep, ...] = ()  # ordered; MAY be empty while boundaries is not
    boundaries: tuple[float, ...] = ()  # the raw cut set, always
    unit: str = "seconds"  # "eight" | "rep" | "seconds"
    grid: MetricGrid | None = None
    confidence: float = 0.0
    method: str = ""  # which capability ran (the ADR's "reported default")
    flags: tuple[str, ...] = ()  # 'naming-abstained', 'no-signal', 'try: ...'
    elapsed_s: float = 0.0
    spent_usd: float = 0.0


# ── consistency: what no segmentation may contain ───────────────────────────


def edges(steps: Iterable[SegStep]) -> set[float]:
    """Every span start and end of ``steps`` (top level)."""
    return {t for step in steps for span in step.spans for t in span}


def overlaps(a: Span, b: Span) -> bool:
    """True when the two spans share a positive length of time."""
    return max(a[0], b[0]) < min(a[1], b[1])


#: Overlap flags listed one per pair before the rest are summarised: the
#: check runs on every segmentation, and dense overlaps make pairs by the
#: hundred thousand.
DFLT_MAX_OVERLAP_FLAGS = 20


def inconsistencies(
    seg: Segmentation, *, max_overlap_flags: int = DFLT_MAX_OVERLAP_FLAGS
) -> tuple[str, ...]:
    """What no segmentation may contain, as ``inconsistent:`` flags — never
    repaired, never raised: empty spans, spans of different steps that
    overlap, children outside their parent, and step edges missing from
    ``boundaries``. :func:`paces.segmenters.segment` runs it on every result,
    whichever segmenter produced it and whether or not a correction log ran.

    >>> inconsistencies(Segmentation(
    ...     steps=(SegStep(id="a", spans=((0.0, 10.0),)),
    ...            SegStep(id="b", spans=((8.0, 20.0),))),
    ...     boundaries=(0.0, 10.0, 20.0)))
    ("inconsistent: steps 'a' and 'b' overlap (8–10)", 'inconsistent: step edges not in boundaries: 8')
    """

    spans = sorted((span, step.id) for step in seg.steps for span in step.spans)
    flags = [
        f"inconsistent: step {step_id!r} has an empty span at {time_str(span[0])}"
        for span, step_id in spans
        if span[0] >= span[1]
    ]
    # A sweep, not all pairs: it runs on every segmentation, and subtitle
    # cues can make thousands of steps. Only spans still open can overlap.
    active: list[tuple[Span, str]] = []
    overlap_flags: list[str] = []
    for b, b_id in spans:
        active = [(a, a_id) for a, a_id in active if a[1] > b[0]]
        overlap_flags += [
            f"inconsistent: steps {a_id!r} and {b_id!r} overlap "
            f"({time_str(max(a[0], b[0]))}–{time_str(min(a[1], b[1]))})"
            for a, a_id in active
            if a_id != b_id and overlaps(a, b)
        ]
        active.append((b, b_id))
    flags += overlap_flags[:max_overlap_flags]
    if len(overlap_flags) > max_overlap_flags:
        flags.append(
            f"inconsistent: {len(overlap_flags) - max_overlap_flags} more "
            "overlapping pairs not listed"
        )
    flags += [
        f"inconsistent: child {child.id!r} of {step.id!r} lies outside its parent"
        for step in seg.steps
        for child in step.children
        for span in child.spans
        if not any(p[0] <= span[0] and span[1] <= p[1] for p in step.spans)
    ]
    missing = sorted(edges(seg.steps) - set(seg.boundaries))
    if missing:
        listed = ", ".join(time_str(t) for t in missing)
        flags.append(f"inconsistent: step edges not in boundaries: {listed}")
    return tuple(flags)


def time_str(t: float) -> str:
    """A time as paces' millisecond wire decimal — the one formatter every
    time producer shares (the ask page's ``timeStr`` mirrors it).

    >>> time_str(95.80000001), time_str(10.0625)  # exact binary ties round half-even
    ('95.8', '10.062')
    """
    return decimal_str(t, places=TIME_PLACES)
