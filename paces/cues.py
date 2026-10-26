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

Accepted timed text (``timed_text``): SRT text (or WebVTT with hour fields),
a path to an ``.srt``/``.vtt`` file, or cue mappings ``{start, end, text}``.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from paces.segmenters import Capability, SegStep, Segmentation, _slugify, register

DFLT_CUES_CONFIDENCE = 0.5  # lexical cues are a hint, not a measurement
DFLT_MIN_GAP_S = 8.0  # cues closer than this to the last boundary are one step
DFLT_MAX_NAME_CHARS = 60

#: Discourse markers that open a step, matched at the start of a cue (case-
#: insensitive). Each may carry a leading "and"/"so"/"okay". Capture group 1,
#: when present, is the lead-in to strip from the step's name.
DFLT_CUE_PATTERNS: tuple[str, ...] = (
    r"(?:(?:and|so|ok(?:ay)?|alright)[,\s]+)?(now|next|then|first(?:ly)?|second(?:ly)?"
    r"|third(?:ly)?|finally|lastly)\b[,\s]*",
    r"((?:step|number|part|move)\s+(?:\d+|one|two|three|four|five|six|seven|eight"
    r"|nine|ten))\b[\s:.,)-]*",
    r"(let'?s|we'?ll\s+start|to\s+start|to\s+begin|moving\s+on|after\s+that"
    r"|the\s+next)\b[,\s]*",
    r"(\d{1,2})\s*[.):]\s+",
)


# ── timed-text normalisation ────────────────────────────────────────────────


def _cue_row(i: int, item: Any) -> dict:
    if not isinstance(item, Mapping):
        raise TypeError(f"cues[{i}]: expected a mapping — got {type(item).__name__}")
    try:
        start = float(item["start"])
        end = float(item.get("end", start))
        text = " ".join(str(item["text"]).split())
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"cues[{i}]: needs numeric start (and end) plus text; got "
            f"keys {sorted(item)} ({error})"
        ) from None
    if not (math.isfinite(start) and math.isfinite(end)) or start < 0 or end < start:
        raise ValueError(f"cues[{i}]: unusable times start={start}, end={end}")
    return {"start": start, "end": end, "text": text}


def normalize_timed_text(source: str | Sequence | None) -> list[dict]:
    """Uniform, sorted ``{start, end, text}`` rows from any accepted timed text.

    >>> normalize_timed_text("1\\n00:00:01,000 --> 00:00:03,000\\nNow we turn")
    [{'start': 1.0, 'end': 3.0, 'text': 'Now we turn'}]
    >>> normalize_timed_text(None)
    []
    """
    if source is None:
        return []
    if isinstance(source, str):
        text = source
        if "\n" not in source and len(source) < 1024:
            try:
                if Path(source).is_file():
                    text = Path(source).read_text(encoding="utf-8")
            except OSError:
                pass
        from mixing.srt import parse_srt  # the fleet's SRT parser, not a copy

        raw = [
            {"start": c.start, "end": c.end, "text": c.text} for c in parse_srt(text)
        ]
    else:
        raw = list(source)
    rows = [_cue_row(i, item) for i, item in enumerate(raw)]
    rows = [row for row in rows if row["text"]]
    rows.sort(key=lambda row: (row["start"], row["end"]))
    return rows


# ── the detector ────────────────────────────────────────────────────────────


def detect_cues(
    cues: Sequence[Mapping],
    *,
    patterns: Sequence[str] = DFLT_CUE_PATTERNS,
    min_gap_s: float = DFLT_MIN_GAP_S,
    max_name_chars: int = DFLT_MAX_NAME_CHARS,
) -> list[dict]:
    """Cue rows that open a step: ``{start, name, cue}`` (the matched marker).

    A cue opens a step when its text starts with one of *patterns*; one that
    lands within *min_gap_s* of the previous accepted step is folded into it.
    The name is the cue's text without its lead-in marker, trimmed to
    *max_name_chars* at a word boundary (a marker alone leaves the name empty
    — found, not named).

    >>> rows = [{"start": 0, "end": 4, "text": "Hi everyone"},
    ...         {"start": 10, "end": 14, "text": "Now we do the turn."}]
    >>> detect_cues(rows)
    [{'start': 10.0, 'name': 'we do the turn', 'cue': 'Now'}]
    """
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    found: list[dict] = []
    for cue in cues:
        for pattern in compiled:
            match = pattern.match(cue["text"])
            if match:
                break
        else:
            continue
        if found and cue["start"] - found[-1]["start"] < min_gap_s:
            continue
        name = cue["text"][match.end() :].strip(" ,.;:!?-")
        if len(name) > max_name_chars:
            name = name[:max_name_chars].rsplit(" ", 1)[0].rstrip(" ,.;:-")
        found.append(
            {
                "start": float(cue["start"]),
                "name": name,
                "cue": (match.group(1) or match.group(0)).strip(),
            }
        )
    return found


def _segment_cue_source(cues: list[dict], *, source: str) -> Segmentation:
    openers = detect_cues(cues)
    if not openers:
        return Segmentation(
            flags=(
                "no-signal",
                "try: chapters in metadata, boundaries=[...], or an LLM pass",
            ),
        )
    end = max(cue["end"] for cue in cues)
    starts = [row["start"] for row in openers]
    spans = list(zip(starts, starts[1:] + [end]))
    seen: dict[str, int] = {}

    def _step(i: int, row: dict, span) -> SegStep:
        slug = _slugify(row["name"]) if row["name"] else f"cue-{i + 1}"
        seen[slug] = seen.get(slug, 0) + 1
        step_id = slug if seen[slug] == 1 else f"{slug}-{seen[slug]}"
        return SegStep(
            id=step_id,
            name=row["name"],
            spans=(span,),
            confidence=DFLT_CUES_CONFIDENCE,
            source=source,
            evidence={"cue": row["cue"]},
        )

    steps = tuple(
        _step(i, row, span) for i, (row, span) in enumerate(zip(openers, spans))
    )
    flags = ("proposed-uncertain",)
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
