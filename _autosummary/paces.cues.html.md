# paces.cues

Lexical cue segmenters: subtitles and transcripts → proposed named spans.

Instructional narration announces its own structure — “now”, “next”, “step
two”, “and finally”. Over *timed text* those words are a near-free boundary
detector with a name attached (`docs/alignment/07 §2.13(a)`, `§6.3`): no
ASR bill when the text already exists (uploader subtitles, auto-captions, a
transcript from an earlier run).

Two capabilities share one detector, because the *source* differs in how far
it can be trusted, not in what is done with it:

- `subtitle-cues` — `metadata={"subtitles": ...}`: human-written or
  auto-caption cues.
- `transcript-cues` — `transcript=...`: any transcript (ASR output).

Both are *proposers*, not authorities: the result is graded
`proposed-uncertain` (`DFLT_CUES_CONFIDENCE`) and flagged so. When no cue
word is found the result is the refused state, never an invented step list.
The LLM rung over a transcript is `mixing.chapters.detect_chapters`; it is
a different capability and is not wrapped here.

Accepted timed text: whatever [`paces.timed_text.normalize_timed_text()`](paces.timed_text.html.md#paces.timed_text.normalize_timed_text)
takes — SRT/WebVTT text or file, cue mappings, `(start, end, text)` triples,
a Whisper `{"segments": ...}` result. Parsing subtitle *text* needs the
optional `mixing` package; cue rows do not.

Word-level transcripts (one cue per word) mostly yield *unnamed* steps: the
marker is found but the name that follows it lives in later cues. Pass
phrase- or sentence-level cues when you want names.

Registration: these capabilities register when this module is imported, and
`paces/__init__.py` imports it — so any `paces.*` import (including
`from paces.segmenters import segment`) sees them. `paces.segmenters`
does not import this module itself, which would be circular.

### Module Attributes

| [`DFLT_CUE_PATTERNS`](#paces.cues.DFLT_CUE_PATTERNS)   | Discourse markers that open a step, matched at the start of a cue (case- insensitive).   |
|----------------------------------------------------------------------|------------------------------------------------------------------------------------------|

### Functions

| [`detect_cues`](#paces.cues.detect_cues)(cues, \*[, patterns, min_gap_s, ...])   | Cue rows that open a step: `{start, name, cue}` (the matched marker).   |
|------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------|
| [`normalize_timed_text`](#paces.cues.normalize_timed_text)(source)                        | Uniform, sorted `{start, end, text}` rows from any accepted timed text. |

### paces.cues.DFLT_CUE_PATTERNS *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), ...]* *= ('(?:(?:and|so|ok(?:ay)?|alright)[,\\\\s]+)?(now|next|first\\\\s+of\\\\s+all|first(?:ly)?|second(?:ly)?|third(?:ly)?|finally|lastly)\\\\b[,\\\\s]\*', '((?:step|number|part)\\\\s+(?:\\\\d+|one|two|three|four|five|six|seven|eight|nine|ten))\\\\b[\\\\s:.,)-]\*', '(to\\\\s+start|to\\\\s+begin|moving\\\\s+on|after\\\\s+that)\\\\b[,\\\\s]\*')*

Discourse markers that open a step, matched at the start of a cue (case-
insensitive). Each may carry a leading “and”/”so”/”okay”. Capture group 1
is the marker, stripped from the step’s name. Deliberately narrow: bare
“then”, “and then”, “let’s” and leading numerals (“2.”) were dropped as
too false-positive-prone in running speech.

### paces.cues.detect_cues(cues, , patterns=('(?:(?:and|so|ok(?:ay)?|alright)[,\\\\s]+)?(now|next|first\\\\s+of\\\\s+all|first(?:ly)?|second(?:ly)?|third(?:ly)?|finally|lastly)\\\\b[,\\\\s]\*', '((?:step|number|part)\\\\s+(?:\\\\d+|one|two|three|four|five|six|seven|eight|nine|ten))\\\\b[\\\\s:.,)-]\*', '(to\\\\s+start|to\\\\s+begin|moving\\\\s+on|after\\\\s+that)\\\\b[,\\\\s]\*'), min_gap_s=8.0, max_name_chars=60)

Cue rows that open a step: `{start, name, cue}` (the matched marker).

A cue opens a step when its text — after any speaker or sound-tag prefix
(”- “, “>> “, “[music] “) — starts with one of *patterns*; one that lands
within *min_gap_s* of the previous accepted step is folded into it (and
lends it its name if that step had none). The name is the cue’s text
without its lead-in marker, trimmed to *max_name_chars* at a word boundary
(a marker alone leaves the name empty — found, not named).

```pycon
>>> rows = [{"start": 0, "end": 4, "text": "Hi everyone"},
...         {"start": 10, "end": 14, "text": ">> Now we do the turn."}]
>>> detect_cues(rows)
[{'start': 10.0, 'name': 'we do the turn', 'cue': 'Now'}]
```

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]

### paces.cues.normalize_timed_text(source)

Uniform, sorted `{start, end, text}` rows from any accepted timed text.

```pycon
>>> normalize_timed_text([(1, 3, "<i>Now</i> we turn")])
[{'start': 1.0, 'end': 3.0, 'text': 'Now we turn'}]
>>> normalize_timed_text({"segments": [{"start": 0, "end": 2, "text": " Hi"}]})
[{'start': 0.0, 'end': 2.0, 'text': 'Hi'}]
>>> normalize_timed_text(None)
[]
```

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]
