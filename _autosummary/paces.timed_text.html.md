# paces.timed_text

Timed-text normalisation: any subtitle/transcript shape → `{start, end, text}` rows.

Depends on nothing else in `paces` — it is the input boundary of the cue
segmenters (`paces/cues.py`) and of `segment(transcript=...)`.

Accepted shapes:

- SRT or WebVTT *text* (VTT when it starts with `WEBVTT`, after any BOM or
  whitespace; hour fields optional) — parsed by the fleet’s `mixing.srt`,
  which is an optional dependency here: only text parsing needs it.
- a path (`str` or [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)) to an `.srt`/`.vtt` file;
- cue mappings `{start, end, text}` or `(start, end, text)` triples (the
  shape `paces.evidence` takes for transcripts);
- a Whisper result `{"segments": [{start, end, text}, ...]}`.

Simple markup (`<i>..</i>`, VTT `<c>` and inline timestamp tags, ASS
overrides like `{\an8}`) is stripped from cue text.

### Functions

| [`normalize_timed_text`](#paces.timed_text.normalize_timed_text)(source)   | Uniform, sorted `{start, end, text}` rows from any accepted timed text.   |
|---------------------------------------------------------------------------------|---------------------------------------------------------------------------|

### paces.timed_text.normalize_timed_text(source)

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
