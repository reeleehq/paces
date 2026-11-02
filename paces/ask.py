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
- :func:`load_answers` — reads those answers back: ``(k, corrections)``, where
  ``corrections`` is a :mod:`paces.corrections` log, so the answers re-enter
  the next :func:`~paces.segmenters.segment` run as constraints.

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
from collections.abc import Mapping
from importlib.resources import files

from paces.corrections import Correction, normalize_corrections
from paces.model import decimal_str, seconds_per_unit
from paces.segmenters import Segmentation

PROPOSAL_KIND = "PacesAskProposal"
ANSWERS_KIND = "PacesAskAnswers"

#: How far a tap may land from a snap target and still snap to it (§7.3 step 3).
DFLT_SNAP_S = 1.5
#: Above this many grid ticks the page snaps to cuts only — a dense tick list
#: would make every tap snap somewhere and bloat the page.
DFLT_MAX_GRID_TICKS = 2000

_ASSETS = files("paces") / "data" / "ask"


def _t(value: float) -> str:
    return decimal_str(value, places=3)


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
    return [_t(origin + n * spu) for n in range(first, last + 1)]


def propose(
    seg: Segmentation,
    *,
    media: str | None = None,
    title: str = "",
    snap_s: float = DFLT_SNAP_S,
    max_grid_ticks: int = DFLT_MAX_GRID_TICKS,
) -> dict:
    """What the machine pre-computes for a human to confirm — a JSON-ready dict.

    ``k`` is the proposed step count (``None`` when the segmentation has
    nothing to count) and ``k_evidence`` says where it came from, so the human
    confirms a number they can see the reasoning for. Times are decimal
    strings, as everywhere on paces' wire.
    """
    cuts = sorted(seg.boundaries)
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
    return {
        "kind": PROPOSAL_KIND,
        "title": title,
        "media": media,
        "method": seg.method,
        "flags": list(seg.flags),
        "k": k,
        "kEvidence": why,
        "extent": [_t(t) for t in extent] if extent else None,
        "cuts": [_t(t) for t in interior],
        "steps": [
            {
                "id": step.id,
                "name": step.name,
                "spans": [[_t(a), _t(b)] for a, b in step.spans],
            }
            for step in seg.steps
        ],
        "snap": {
            "windowS": _t(snap_s),
            "targets": sorted({*map(_t, interior), *ticks}, key=float),
        },
    }


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
    data = json.dumps({**proposal, "author": author}, ensure_ascii=False)
    # No "<" may reach the data block: a "</script>" (or "<!--") inside a
    # title or flag would end it early. JSON reads "\u003c" back as "<".
    data = data.replace("<", "\\u003c")
    template = (_ASSETS / "ask.html").read_text(encoding="utf-8")
    return (
        template.replace(
            "{{title}}", html.escape(proposal.get("title") or "Check the steps")
        )
        .replace("{{css}}", (_ASSETS / "ask.css").read_text(encoding="utf-8"))
        .replace("{{js}}", (_ASSETS / "ask.js").read_text(encoding="utf-8"))
        .replace("{{data}}", data)
    )


def load_answers(answers: Mapping) -> tuple[int | None, tuple[Correction, ...]]:
    """``(k, corrections)`` from the page's answers JSON.

    ``k`` is the human's step count (``None`` if they did not give one); the
    corrections are a :mod:`paces.corrections` log, validated here so a bad
    file fails now and not halfway through a re-run.

    >>> load_answers({"kind": "PacesAskAnswers", "k": 4,
    ...               "corrections": [{"verb": "split", "anchorT": "15"}]})
    (4, (Correction(verb='split', anchor_t=15.0, span=None, step_id=None, author='', at='', media_key=None, reason=''),))
    """
    if not isinstance(answers, Mapping) or answers.get("kind") != ANSWERS_KIND:
        got = (
            answers.get("kind")
            if isinstance(answers, Mapping)
            else type(answers).__name__
        )
        raise ValueError(
            f"expected {ANSWERS_KIND} answers (from the ask page), got {got!r}"
        )
    unknown = sorted(set(answers) - {"kind", "k", "corrections", "proposal"})
    if unknown:
        raise ValueError(f"unknown answers keys {unknown}")
    k = answers.get("k")
    if k is not None and (isinstance(k, bool) or not isinstance(k, int) or k < 1):
        raise ValueError(f"k must be a positive integer or null, got {k!r}")
    return k, normalize_corrections(answers.get("corrections", []))
