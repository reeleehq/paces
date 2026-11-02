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

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from paces.model import MetricGrid

__all__ = [
    "DFLT_CHAPTERS_CONFIDENCE",
    "DFLT_EXPLICIT_CONFIDENCE",
    "DFLT_GRID_CONFIDENCE",
    "SegStep",
    "Segmentation",
    "Span",
]

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
