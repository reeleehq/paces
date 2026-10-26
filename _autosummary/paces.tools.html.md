# paces.tools

Agent-callable tool surface over `paces` — plain functions with JSON-able
arguments returning JSON-ready values, deliberately CLI/MCP/HTTP-agnostic.

This module is the SSOT for “what paces can do”: every surface (the `cw`
CLI in `__main__.py` today; `py2mcp`/`qh` wrappers tomorrow) dispatches
over `_dispatch_funcs` and nothing else. Arguments that carry structure
(steps, grids, documents) accept a Python object, a JSON string, or a path to
a JSON file, so the same function serves the library, the shell, and an agent.

### Functions

| [`derive`](#paces.tools.derive)(document, \*, media[, output, ...])         | Derive real media (clip + gif + poster) for every excerpt-bearing span and write the refs into the document.   |
|-----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------|
| [`edit`](#paces.tools.edit)(document, edits, \*, by[, reason, output])    | Apply typed patches to a document; every edit writes a Lock.                                                   |
| [`list_segmenters`](#paces.tools.list_segmenters)()                                  | The registered segmentation capabilities: name → what it needs/gives.                                          |
| [`measure_grid`](#paces.tools.measure_grid)(media, \*[, unit, subdivisions, ...]) | Measure a metric grid (tempo, macro-structure, estimated origin) from a local media file.                      |
| [`merge`](#paces.tools.merge)(committed, fresh, \*[, output])              | Merge a fresh analysis projection against the committed document.                                              |
| [`render`](#paces.tools.render)(document, \*[, output, renderer])           | Render a step document into learning material.                                                                 |
| [`resolve`](#paces.tools.resolve)(document)                                  | Compute absolute offsets and wall-clock times for a document's steps.                                          |
| [`segment`](#paces.tools.segment)([media, steps, boundaries, grid, ...])     | Cut media into steps using whatever else is present (ADR-0003).                                                |
| [`suggest_excerpts`](#paces.tools.suggest_excerpts)(document, \*[, units, role, ...]) | Mark each step's loopable sub-window (the `excerpt` derive cuts).                                              |
| [`to_document`](#paces.tools.to_document)(segmentation, \*[, doc_id, ...])       | Project a segmentation into a step document (the committed artifact).                                          |
| [`validate`](#paces.tools.validate)(document)                                 | Schema + semantic check of a step document; returns `{"issues": [...]}`.                                       |

### paces.tools.derive(document, , media, output=None, subject_locator=None, roles='clip,gif,poster', aspect=None, pad=None)

Derive real media (clip + gif + poster) for every excerpt-bearing
span and write the refs into the document. Needs the [media] extra.

`document` must be a *path* here (the anchor for the `media/` dir
and the crop-recipes sidecar — ADR-0005 §1); library callers with an
in-memory document use [`paces.derivation.derive_document()`](paces.derivation.html.md#paces.derivation.derive_document) with an
explicit store. `media` is one local file, or `{"<source-id>":
"<path>"}` when several sources carry excerpts. `subject_locator` is
a lazy `"module:attr"` ref to an ADR-0005 §3 locator; the default is
no crop, and `paces.pose:rtmlib_pose` is the shipped pointable one
(rtmlib pose boxes, `pip install paces[pose]`). The updated document is written back to `output` (default:
the document path itself — derive’s media side effects and the refs
pointing at them must not go out of sync); the returned payload carries
`flags` — read them, they are the honesty report.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### paces.tools.edit(document, edits, , by, reason=None, output=None)

Apply typed patches to a document; every edit writes a Lock.

`edits` is a list of `{"op": "set", "path": "/steps/b4/name",
"value": ...}` (JSON value, string, or file path). `by` identifies the
editor (“user:thor”, “agent:<model>”). Locked paths survive
regeneration (see `merge`).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### paces.tools.list_segmenters()

The registered segmentation capabilities: name → what it needs/gives.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### paces.tools.measure_grid(media, , unit='eight', subdivisions=8, total_units=None, output=None)

Measure a metric grid (tempo, macro-structure, estimated origin) from
a local media file. Needs the [audio] extra.

Returns `{"grid", "confidence", "flags", "evidence"}` — origin is an
estimate (first beat of the music region) and the flags say so; override
with an explicit `grid=` on `segment` when it is wrong.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### paces.tools.merge(committed, fresh, , output=None)

Merge a fresh analysis projection against the committed document.

Locked paths keep the committed value; everything else takes the fresh
value; protected committed-only steps survive. This is how re-running
analysis never eats a hand edit.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### paces.tools.render(document, , output=None, renderer='html')

Render a step document into learning material.

`renderer='html'` (v1’s one implementation) produces the self-contained
practice page. Returns the output path when `output=` is given,
otherwise the rendered text itself.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### paces.tools.resolve(document)

Compute absolute offsets and wall-clock times for a document’s steps.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### paces.tools.segment(media=None, , steps=None, boundaries=None, grid=None, metadata=None, segmenter=None, k=None, output=None)

Cut media into steps using whatever else is present (ADR-0003).

`steps`, `boundaries`, `grid` and `metadata` accept JSON values,
JSON strings, or paths to JSON files — `metadata` notably takes a
yt-dlp `.info.json` (its `chapters` become a named segmentation).
Returns the segmentation as a JSON-ready dict (also written to
`output=` when given) — honest about naming
(`flags: ['naming-abstained']`) and about refusal
(`flags: ['no-signal', 'try: ...']`); never a fabricated step list.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### paces.tools.suggest_excerpts(document, , units=None, role='performance', overwrite=False, output=None)

Mark each step’s loopable sub-window (the `excerpt` derive cuts).

v1 heuristic (issue #3): the excerpt is the span’s whole grid window;
`units=N` takes the first N metric units instead. Never overwrites an
existing excerpt unless `overwrite` (and never a locked one). Returns
`{"document", "flags", "suggested"}`; writes to `output=` when given.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### paces.tools.to_document(segmentation, , doc_id='guide', title='', source=None, domain='generic', lang='en', output=None)

Project a segmentation into a step document (the committed artifact).

`source` is the media URI the spans refer into. With `output=`, the
canonical wire form is also written to that path.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### paces.tools.validate(document)

Schema + semantic check of a step document; returns `{"issues": [...]}`.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)
