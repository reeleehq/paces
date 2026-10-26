"""Lexical cue segmenters: subtitles and transcripts → proposed named spans.

Instructional narration announces its own structure — "now", "next", "step
two", "and finally". Over *timed text* those words are a near-free boundary
detector with a name attached (``docs/alignment/07 §2.13(a)``, ``§6.3``): no
ASR bill when the text already exists (uploader subtitles, auto-captions, a
transcript from an earlier run).

Two capabilities share one detector, because the *source* differs in how far
it can be trusted, not in what is done with it:

- ``subtitle-cues`` — ``metadata={"subtitles": ...}``: human-written or
  auto-caption cues.
- ``transcript-cues`` — ``transcript=...``: any transcript (ASR output).

Both are *proposers*, not authorities: the result is graded
``proposed-uncertain`` (``DFLT_CUES_CONFIDENCE``) and flagged so. When no cue
word is found the result is the refused state, never an invented step list.
The LLM rung over a transcript is ``mixing.chapters.detect_chapters``; it is
a different capability and is not wrapped here.

Accepted timed text: whatever :func:`paces.timed_text.normalize_timed_text`
takes — SRT/WebVTT text or file, cue mappings, ``(start, end, text)`` triples,
a Whisper ``{"segments": ...}`` result. Parsing subtitle *text* needs the
optional ``mixing`` package; cue rows do not.

Word-level transcripts (one cue per word) mostly yield *unnamed* steps: the
marker is found but the name that follows it lives in later cues. Pass
phrase- or sentence-level cues when you want names.

Registration: these capabilities register when this module is imported, and
``paces/__init__.py`` imports it — so any ``paces.*`` import (including
``from paces.segmenters import segment``) sees them. ``paces.segmenters``
does not import this module itself, which would be circular.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from paces.segmenters import (
    Capability,
    SegStep,
    Segmentation,
    register,
    unique_slug_ids,
)
from paces.timed_text import normalize_timed_text

__all__ = ["DFLT_CUE_PATTERNS", "detect_cues", "normalize_timed_text"]

DFLT_CUES_CONFIDENCE = 0.5  # lexical cues are a hint, not a measurement
DFLT_MIN_GAP_S = 8.0  # cues closer than this to the last boundary are one step
DFLT_MAX_NAME_CHARS = 60

#: Discourse markers that open a step, matched at the start of a cue (case-
#: insensitive). Each may carry a leading "and"/"so"/"okay". Capture group 1
#: is the marker, stripped from the step's name. Deliberately narrow: bare
#: "then", "and then", "let's" and leading numerals ("2.") were dropped as
#: too false-positive-prone in running speech.
DFLT_CUE_PATTERNS: tuple[str, ...] = (
    r"(?:(?:and|so|ok(?:ay)?|alright)[,\s]+)?(now|next|first\s+of\s+all|first(?:ly)?|second(?:ly)?"
    r"|third(?:ly)?|finally|lastly)\b[,\s]*",
    r"((?:step|number|part)\s+(?:\d+|one|two|three|four|five|six|seven|eight"
    r"|nine|ten))\b[\s:.,)-]*",
    r"(to\s+start|to\s+begin|moving\s+on|after\s+that)\b[,\s]*",
)

#: Speaker / sound-tag prefixes stripped before matching: "- ", ">> ", "[music] ".
_PREFIX_RE = re.compile(r"^(?:\s*(?:-+|>>+|\[[^\]]*\])\s*)+")


# ── the detector ────────────────────────────────────────────────────────────


def detect_cues(
    cues: Sequence[Mapping],
    *,
    patterns: Sequence[str] = DFLT_CUE_PATTERNS,
    min_gap_s: float = DFLT_MIN_GAP_S,
    max_name_chars: int = DFLT_MAX_NAME_CHARS,
) -> list[dict]:
    """Cue rows that open a step: ``{start, name, cue}`` (the matched marker).

    A cue opens a step when its text — after any speaker or sound-tag prefix
    ("- ", ">> ", "[music] ") — starts with one of *patterns*; one that lands
    within *min_gap_s* of the previous accepted step is folded into it (and
    lends it its name if that step had none). The name is the cue's text
    without its lead-in marker, trimmed to *max_name_chars* at a word boundary
    (a marker alone leaves the name empty — found, not named).

    >>> rows = [{"start": 0, "end": 4, "text": "Hi everyone"},
    ...         {"start": 10, "end": 14, "text": ">> Now we do the turn."}]
    >>> detect_cues(rows)
    [{'start': 10.0, 'name': 'we do the turn', 'cue': 'Now'}]
    """
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]

    def _name(text: str) -> str:
        name = text.strip(" ,.;:!?-")
        if len(name) > max_name_chars:
            name = name[:max_name_chars].rsplit(" ", 1)[0].rstrip(" ,.;:-")
        return name

    found: list[dict] = []
    for cue in cues:
        text = _PREFIX_RE.sub("", cue["text"])
        match = next((m for m in (p.match(text) for p in compiled) if m), None)
        if match is None:
            continue
        name = _name(text[match.end() :])
        if found and cue["start"] - found[-1]["start"] < min_gap_s:
            if not found[-1]["name"]:
                found[-1]["name"] = name
            continue
        found.append(
            {
                "start": float(cue["start"]),
                "name": name,
                "cue": (match.group(1) if match.re.groups else match.group(0)).strip(),
            }
        )
    return found


def _segment_cue_source(cues: list[dict], *, source: str) -> Segmentation:
    openers = detect_cues(cues)
    end = max((cue["end"] for cue in cues), default=0.0)
    flags: tuple[str, ...] = ()
    if openers and openers[-1]["start"] >= end:
        openers = openers[:-1]  # a marker on the very last instant opens nothing
        flags += ("trailing-cue-dropped",)
    if not openers:
        return Segmentation(
            flags=(
                "no-signal",
                "try: the other cue source via segmenter=, chapters in metadata, "
                "boundaries=[...], or an LLM pass",
                *flags,
            ),
        )
    starts = [row["start"] for row in openers]
    spans = zip(starts, starts[1:] + [end])
    ids = unique_slug_ids([row["name"] for row in openers], fallback="cue")
    steps = tuple(
        SegStep(
            id=step_id,
            name=row["name"],
            spans=(span,),
            confidence=DFLT_CUES_CONFIDENCE,
            source=source,
            evidence={"cue": row["cue"]},
        )
        for step_id, row, span in zip(ids, openers, spans)
    )
    flags = ("proposed-uncertain", *flags)
    if starts[0] > 0:
        flags += (f"intro-before: {starts[0]:g}s",)
    if not any(step.name for step in steps):
        flags += ("naming-abstained",)
    return Segmentation(
        steps=steps,
        boundaries=tuple(starts + [end]),
        confidence=DFLT_CUES_CONFIDENCE,
        flags=flags,
    )


def _segment_subtitles(inputs: Mapping[str, Any]) -> Segmentation:
    return _segment_cue_source(inputs["subtitles"], source="subtitle-cues")


def _segment_transcript(inputs: Mapping[str, Any]) -> Segmentation:
    return _segment_cue_source(inputs["transcript"], source="transcript-cues")


SUBTITLE_CUES = register(
    Capability(
        name="subtitle-cues",
        gives="segmentation",
        summary=(
            "Propose named spans from a subtitle track by lexical step cues "
            "('now', 'next', 'step two'). Free; a hint, not an authority."
        ),
        target="paces.cues:_segment_subtitles",
        needs=frozenset({"meta.subtitles"}),
        base=0.4,  # below chapters (0.75) and explicit boundaries (0.5)
        resolution_s=DFLT_MIN_GAP_S,
    )
)

TRANSCRIPT_CUES = register(
    Capability(
        name="transcript-cues",
        gives="segmentation",
        summary=(
            "Propose named spans from any transcript by the same lexical "
            "step cues. Free once the transcript exists."
        ),
        target="paces.cues:_segment_transcript",
        needs=frozenset({"transcript"}),
        base=0.35,  # an ASR transcript is a step less trustworthy than subtitles
        resolution_s=DFLT_MIN_GAP_S,
    )
)
