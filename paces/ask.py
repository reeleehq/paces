"""The ask segmenter's interaction half: what the machine proposes, and the page
a human answers it on (issue #10, ``docs/alignment/07 §7.2–7.4``).

"Ask the user" is first-class, and the gap between a 30-minute chore and a
2-minute confirmation is the *proposal*. So this module is three pure pieces
around one JSON contract:

- :func:`propose` — what the machine pre-computes from a :class:`Segmentation`:
  a proposed step count K with the evidence for it (the cheapest, highest-value
  question comes first, §7.3 step 1), the candidate cuts, the steps, and the
  snap targets a tap lands on (the cuts, plus the grid's unit ticks when there
  is a grid: on rhythmic content a boundary is a downbeat).
- :func:`render_ask_page` — the default UI: one self-contained static HTML page
  (no server, no framework, no dependency) that asks for K, lets a human tap
  along with the media to add cuts, strike cuts that are wrong and mark steps
  that are not in the media, and exports the answers as JSON.
- :func:`load_answers` — reads those answers back as :class:`Answers`: the
  step count (only when the human touched it), a :mod:`paces.corrections`
  log, and — when the proposal had nothing to correct (the refused state) —
  the boundaries the human tapped, so the answers re-enter the next
  :func:`~paces.segmenters.segment` run as constraints or as boundaries.

**The seam is the contract, not a callback.** Any other UI — the real
frontend, a CLI prompt, a notebook widget, or an agent with the proposal in
context (§7.4) — reads the proposal JSON and writes the answers JSON; nothing
here has to change for it.

>>> from paces.segmenters import segment
>>> proposal = propose(segment(boundaries=[0, 10, 20, 30]))
>>> proposal["k"], proposal["cuts"]
(3, ['10', '20'])
"""

from __future__ import annotations

import html
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files

from paces.corrections import (
    DFLT_MERGE_TOLERANCE_S,
    DFLT_MIN_STEP_S,
    Correction,
    normalize_corrections,
    time_str,
)
from paces.ask_contract import (
    ANSWERS_KIND,
    CONTRACT_VERSION,
    PROPOSAL_KIND,
    AnswersDocument,
    Proposal,
    ProposedStep,
    Snap,
    contract_schemas,
)
from paces.model import seconds_per_unit
from paces.segmentation import Segmentation

#: How far a tap may land from a snap target and still snap to it (§7.3 step
#: 3). It is the merge tolerance on purpose: both absorb the same thing, the
#: imprecision of a human tapping along, so one number serves both.
DFLT_SNAP_S = DFLT_MERGE_TOLERANCE_S
#: Above this many grid ticks the page snaps to cuts only — a dense tick list
#: would make every tap snap somewhere and bloat the page.
DFLT_MAX_GRID_TICKS = 2000

_ASSETS = files("paces") / "data" / "ask"


def _grid_ticks(seg: Segmentation, lo: float, hi: float, *, limit: int) -> list[str]:
    """The grid's unit boundaries inside ``[lo, hi]`` (downbeats, for a dance)."""
    grid = seg.grid
    spu = seconds_per_unit(grid) if grid is not None else None
    if not spu or grid.origin is None or hi <= lo:
        return []
    origin = float(grid.origin)
    first, last = math.ceil((lo - origin) / spu), math.floor((hi - origin) / spu)
    if last - first + 1 > limit:
        return []
    return [time_str(origin + n * spu) for n in range(first, last + 1)]


def _meets(seg: Segmentation, cut: str) -> bool:
    """Whether one step ends at ``cut`` and another begins there (no gap).

    Unnamed segmentations (no steps) are spans between cuts, so every cut meets.

    >>> from paces.segmenters import segment
    >>> propose(segment(boundaries=[0, 10, 20]))["cutMeets"]
    [True]
    """
    if not seg.steps:
        return True
    spans = [(time_str(a), time_str(b)) for step in seg.steps for a, b in step.spans]
    return any(b == cut for _, b in spans) and any(a == cut for a, _ in spans)


def propose(
    seg: Segmentation,
    *,
    media: str | None = None,
    title: str = "",
    snap_s: float = DFLT_SNAP_S,
    min_step_s: float = DFLT_MIN_STEP_S,
    max_grid_ticks: int = DFLT_MAX_GRID_TICKS,
) -> dict:
    """What the machine pre-computes for a human to confirm — a JSON-ready dict.

    ``k`` is the proposed step count (``None`` when the segmentation has
    nothing to count) and ``k_evidence`` says where it came from, so the human
    confirms a number they can see the reasoning for. Times are decimal
    strings, as everywhere on paces' wire; cuts that are the same millisecond
    are one cut. ``minStepS`` is the narrowest step a split may make
    (:data:`~paces.corrections.DFLT_MIN_STEP_S`): the page ignores a tap
    closer than that to a cut, as replay would.

    >>> propose(Segmentation(boundaries=(0, 10, 10.0001, 20)))["cuts"]
    ['10']
    """
    cuts = sorted({float(time_str(t)) for t in seg.boundaries})
    interior = cuts[1:-1]
    if seg.steps:
        k, why = (
            len(seg.steps),
            f"{len(seg.steps)} steps found by {seg.method or 'the segmenter'}",
        )
    elif len(cuts) >= 2:
        k, why = len(cuts) - 1, f"{len(cuts)} cuts make {len(cuts) - 1} spans (unnamed)"
    else:
        k, why = None, "nothing to count yet: the segmenter found no cuts"
    extent = (cuts[0], cuts[-1]) if len(cuts) >= 2 else None
    ticks = _grid_ticks(seg, *extent, limit=max_grid_ticks) if extent else []
    return Proposal(
        title=title,
        media=media,
        method=seg.method,
        flags=list(seg.flags),
        k=k,
        k_evidence=why,
        extent=tuple(time_str(t) for t in extent) if extent else None,
        cuts=[time_str(t) for t in interior],
        cut_meets=[_meets(seg, time_str(t)) for t in interior],
        steps=[
            ProposedStep(
                id=step.id,
                name=step.name,
                spans=[(time_str(a), time_str(b)) for a, b in step.spans],
            )
            for step in seg.steps
        ],
        min_step_s=time_str(min_step_s),
        snap=Snap(
            window_s=time_str(snap_s),
            targets=sorted({*map(time_str, interior), *ticks}, key=float),
        ),
    ).model_dump(by_alias=True, mode="json")


def render_ask_page(proposal: Mapping, *, author: str = "") -> str:
    """The default ``ask`` UI: a self-contained static HTML page.

    It posts nothing. The human's answers autosave in the browser (so a
    closed tab loses nothing) and leave as a downloaded ``answers.json`` or
    copied text, which :func:`load_answers` reads. ``author`` is stamped on
    every correction the page emits.
    """
    if proposal.get("kind") != PROPOSAL_KIND:
        raise ValueError(
            f"expected a {PROPOSAL_KIND} (from propose()), got {proposal.get('kind')!r}"
        )
    if proposal.get("version") != CONTRACT_VERSION:
        raise ValueError(
            f"expected a version {CONTRACT_VERSION} proposal, "
            f"got version {proposal.get('version')!r}"
        )
    data = json.dumps({**proposal, "author": author}, ensure_ascii=False)
    # No "<" may reach the data block: a "</script>" (or "<!--") inside a
    # title or flag would end it early. JSON reads "\u003c" back as "<".
    data = data.replace("<", "\\u003c")
    fills = {
        "title": html.escape(proposal.get("title") or "Check the steps"),
        "css": (_ASSETS / "ask.css").read_text(encoding="utf-8"),
        "js": (_ASSETS / "ask.js").read_text(encoding="utf-8"),
        "data": data,
    }
    template = (_ASSETS / "ask.html").read_text(encoding="utf-8")
    # One pass: a filled value is never scanned again, so a title such as
    # "{{js}}" stays text instead of pulling the script into the heading.
    return re.sub(r"\{\{(\w+)\}\}", lambda m: fills[m.group(1)], template)


@dataclass(frozen=True, slots=True)
class Answers:
    """What a human answered on the ask page, ready for the next run.

    ``k`` is the step count they gave (``None`` unless they touched it);
    ``corrections`` is a :mod:`paces.corrections` log; ``boundaries`` holds
    the cuts they tapped when the proposal had none to correct (the refused
    state), from 0 to the media's end — ``None`` otherwise.
    """

    k: int | None
    corrections: tuple[Correction, ...] = ()
    boundaries: tuple[float, ...] | None = None


def _answered_boundaries(value) -> tuple[float, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) < 2:
        raise ValueError(f"boundaries must be a list of 2 or more times, got {value!r}")
    if any(isinstance(t, bool) for t in value):
        raise ValueError(f"boundaries must be times in seconds, got {value!r}")
    try:
        times = tuple(float(time_str(float(t))) for t in value)
    except (TypeError, ValueError):
        raise ValueError(
            f"boundaries must be times in seconds, got {value!r}"
        ) from None
    if not all(math.isfinite(t) and t >= 0 for t in times) or any(
        a >= b for a, b in zip(times, times[1:])
    ):
        raise ValueError(f"boundaries must be increasing times >= 0, got {value!r}")
    return times


def load_answers(answers: Mapping) -> Answers:
    """:class:`Answers` from the page's answers JSON.

    Validated here, so a bad file fails now and not halfway through a re-run:
    the kind, the contract ``version`` (required), ``k``, every correction,
    and the boundaries.

    >>> load_answers({"kind": "PacesAskAnswers", "version": 1, "k": 4,
    ...               "corrections": [{"verb": "split", "anchorT": "15"}]})
    Answers(k=4, corrections=(Correction(verb='split', anchor_t=15.0, span=None, step_id=None, author='', at='', media_key=None, reason=''),), boundaries=None)
    """
    if not isinstance(answers, Mapping):
        raise ValueError(
            f"expected {ANSWERS_KIND} answers (from the ask page), "
            f"got {type(answers).__name__!r}"
        )
    doc = AnswersDocument.model_validate(dict(answers))
    return Answers(
        k=doc.k,
        corrections=normalize_corrections(doc.corrections),
        boundaries=_answered_boundaries(doc.boundaries),
    )
