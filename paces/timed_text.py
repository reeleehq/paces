"""Timed-text normalisation: any subtitle/transcript shape → ``{start, end, text}`` rows.

Depends on nothing else in ``paces`` — it is the input boundary of the cue
segmenters (``paces/cues.py``) and of ``segment(transcript=...)``.

Accepted shapes:

- SRT or WebVTT *text* (VTT when it starts with ``WEBVTT``, after any BOM or
  whitespace; hour fields optional) — parsed by the fleet's ``mixing.srt``,
  which is an optional dependency here: only text parsing needs it.
- a path (``str`` or :class:`~pathlib.Path`) to an ``.srt``/``.vtt`` file;
- cue mappings ``{start, end, text}`` or ``(start, end, text)`` triples (the
  shape ``paces.evidence`` takes for transcripts);
- a Whisper result ``{"segments": [{start, end, text}, ...]}``.

Simple markup (``<i>..</i>``, VTT ``<c>`` and inline timestamp tags, ASS
overrides like ``{\\an8}``) is stripped from cue text.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_MARKUP_RE = re.compile(r"<[^>]*>|\{\\[^}]*\}")
_MAX_PATH_CHARS = 1024
_MIXING_INSTALL_HINT = (
    "Parsing SRT/VTT text needs the optional `mixing` package: "
    "pip install mixing (or pass cue mappings / (start, end, text) triples)."
)


def _mixing_srt():
    try:
        from mixing import srt
    except ImportError as error:
        raise ImportError(_MIXING_INSTALL_HINT) from error
    return srt


def _parse_srt(text: str) -> list[dict]:
    return [
        {"start": c.start, "end": c.end, "text": c.text}
        for c in _mixing_srt().parse_srt(text)
    ]


def _parse_vtt(text: str) -> list[dict]:
    """Cue-level WebVTT via mixing's private helpers.

    TODO: switch to a public ``mixing.srt.parse_vtt`` once it exists —
    https://github.com/reeleehq/mixing/issues/79
    """
    srt = _mixing_srt()
    return [
        {"start": c.start, "end": c.end, "text": srt._vtt_clean(c.text)}
        for c in srt._vtt_cues(text)
    ]


def _read_if_path(source: str | Path) -> str:
    if isinstance(source, Path):
        return source.read_text(encoding="utf-8")
    if "-->" in source:
        return source  # timed text itself
    if len(source) < _MAX_PATH_CHARS and "\n" not in source:
        try:
            if Path(source).is_file():
                return Path(source).read_text(encoding="utf-8")
        except OSError:
            pass
    raise ValueError(
        "timed text: not SRT/VTT (no '-->' timing line) and not an existing "
        f"file: {source[:80]!r}"
    )


def _parse_text(text: str) -> list[dict]:
    stripped = text.lstrip("﻿ \t\r\n")
    if stripped.startswith("WEBVTT"):
        return _parse_vtt(stripped)
    return _parse_srt(stripped)


def _cue_row(i: int, item: Any) -> dict:
    if isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
        if len(item) != 3:
            raise ValueError(f"cues[{i}]: expected (start, end, text); got {item!r}")
        item = dict(zip(("start", "end", "text"), item))
    if not isinstance(item, Mapping):
        raise TypeError(
            f"cues[{i}]: expected a mapping or (start, end, text) — "
            f"got {type(item).__name__}"
        )
    if item.get("text") is None or isinstance(item.get("start"), bool):
        raise ValueError(f"cues[{i}]: needs numeric start and text; got {dict(item)!r}")
    try:
        start = float(item["start"])
        end = float(item.get("end", start))
        text = " ".join(_MARKUP_RE.sub("", str(item["text"])).split())
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"cues[{i}]: needs numeric start (and end) plus text; got "
            f"keys {sorted(item)} ({error})"
        ) from None
    if not (math.isfinite(start) and math.isfinite(end)) or start < 0 or end < start:
        raise ValueError(f"cues[{i}]: unusable times start={start}, end={end}")
    return {"start": start, "end": end, "text": text}


def normalize_timed_text(source: str | Path | Sequence | Mapping | None) -> list[dict]:
    """Uniform, sorted ``{start, end, text}`` rows from any accepted timed text.

    >>> normalize_timed_text([(1, 3, "<i>Now</i> we turn")])
    [{'start': 1.0, 'end': 3.0, 'text': 'Now we turn'}]
    >>> normalize_timed_text({"segments": [{"start": 0, "end": 2, "text": " Hi"}]})
    [{'start': 0.0, 'end': 2.0, 'text': 'Hi'}]
    >>> normalize_timed_text(None)
    []
    """
    if source is None:
        return []
    if isinstance(source, (str, Path)):
        raw: Sequence = _parse_text(_read_if_path(source))
    elif isinstance(source, Mapping):
        if "segments" not in source:
            raise ValueError(
                "timed text: a mapping must be a Whisper result with 'segments'; "
                f"got keys {sorted(source)}"
            )
        raw = list(source["segments"])
    else:
        raw = list(source)
    rows = [_cue_row(i, item) for i, item in enumerate(raw)]
    rows = [row for row in rows if row["text"]]
    rows.sort(key=lambda row: (row["start"], row["end"]))
    return rows
