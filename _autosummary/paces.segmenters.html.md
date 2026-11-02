# paces.segmenters

Segmentation is a seam, not a stage (ADR-0003).

`segment(media, ...)` takes media plus a `segmenter=`, and the segmenter
is where the variation lives. Segmenters are *registered* capabilities —
adding one is a new file with one `register(Capability(...))` call; nothing
existing is edited. The default is selected from what is present (the facts),
reported in `Segmentation.method`, and overridable by the one keyword.

A segmenter’s information can be intrinsic (features of the media), external
explicit (coordinates handed over), external derived (computed from the
surrounding annotations), or mixed — mixed being the normal case. v1 ships the
two maximally different ones so the seam is shaped by both rather than by one:

- `grid-placed` (external, derived — the que-calor shape): an ordered step
  list with domain durations, placed on the timeline by a metric grid.
- `explicit` (external, explicit — “ask the user”, first-class): boundaries
  or spans supplied directly, named when names were supplied, honestly unnamed
  when not.

Plus `chapters` (external, explicit): author-supplied chapter metadata — a
yt-dlp info dict or ffprobe’s `-show_chapters` output — is a complete named
segmentation for ~0 cost, and most tutorial content on the web carries it.

Plus `subtitle-cues` and `transcript-cues` (`paces/cues.py`): proposers
that read step markers (“now”, “next”, “step two”) out of timed text — uploader
subtitles or any transcript — and return low-confidence, honestly flagged
spans. Like `grid-measured` (`paces/measure.py`) they register when
`paces` is imported — the package `__init__` imports their module, so
`from paces.segmenters import segment` sees them too.

Honesty rules (`docs/alignment/07 §9.5`): a segmenter may never return a
step count it has no evidence for. Four legitimate return states — confident /
found-unnamed / proposed-uncertain / refused — all expressed by the type, none
by an exception.

### Functions

| [`capabilities`](#paces.segmenters.capabilities)()                          | The registered capability catalog (read-only view).                      |
|------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| [`place_on_grid`](#paces.segmenters.place_on_grid)(steps, grid)              | Place an ordered step list on the timeline using a metric grid.          |
| [`register`](#paces.segmenters.register)(capability)                    | Register a segmentation capability; returns it for assignment.           |
| [`segment`](#paces.segmenters.segment)([media, segmenter, steps, ...]) | Cut *media* into named steps, using whatever else is present.            |
| [`unique_slug_ids`](#paces.segmenters.unique_slug_ids)(names, \*[, fallback])  | One unique, git-readable id per name; unnamed ones get `{fallback}-{i}`. |

### Classes

| [`Capability`](#paces.segmenters.Capability)(\*, name, gives, summary, target)   | What one method needs, gives, and costs.   |
|-------------------------------------------------------------------------------------------------|--------------------------------------------|

### *class* paces.segmenters.Capability(, name, gives, summary, target, needs=frozenset({}), reads=frozenset({}), boosts=dict(), requires=(), licence='MIT', base=0.0, s_per_min=0.0, usd_per_hour=0.0, device='cpu', fixed_s=0.0, resolution_s=1.0, calibrated_on=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What one method needs, gives, and costs. Selection reads ONLY this.

The record from `docs/alignment/06 §1.2`, reused unchanged so the
eventual planner and the segmenter registry share one declaration format.
`target` is a lazy `"module:func"` ref — listing a heavy capability
must not import its dependencies.

### paces.segmenters.capabilities()

The registered capability catalog (read-only view).

* **Return type:**
  [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Capability`](#paces.segmenters.Capability)]

### paces.segmenters.place_on_grid(steps, grid)

Place an ordered step list on the timeline using a metric grid.

The que-calor shape: cumulative domain durations from the grid’s origin,
`span = origin + cumulative_units * seconds_per_unit`. Children subdivide
their parent’s span the same way. `steps` takes any form
[`segment()`](#paces.segmenters.segment) takes (`(name, duration)` pairs, mappings with
`children`); every step needs a positive duration, and the grid a tempo
and an origin — anything missing or invalid is a `ValueError` naming it.

```pycon
>>> seg = place_on_grid([("a", 1), ("b", 2)],
...                     {"unit": "eight", "subdivisions": 8,
...                      "tempoBpm": "120", "origin": "1"})
>>> [s.spans for s in seg.steps], seg.boundaries
([((1.0, 5.0),), ((5.0, 13.0),)], (1.0, 5.0, 13.0))
```

* **Return type:**
  [`Segmentation`](paces.segmentation.html.md#paces.segmentation.Segmentation)

### paces.segmenters.register(capability)

Register a segmentation capability; returns it for assignment.

* **Return type:**
  [`Capability`](#paces.segmenters.Capability)

### paces.segmenters.segment(media=None, , segmenter=None, steps=None, boundaries=None, grid=None, metadata=None, transcript=None, k=None, corrections=None, catalog=None)

Cut *media* into named steps, using whatever else is present.

Returns a `Segmentation` ALWAYS. A segmenter that cannot name the
steps returns `boundaries` and `steps=()`; when nothing applies the
result is the refused state (`flags=('no-signal', 'try: ...')`), not an
exception.

The seam: `segmenter=None` selects from what is present; a name pins it.

`corrections` is a human’s correction log ([`paces.corrections`](paces.corrections.html.md#module-paces.corrections)):
constraints that survive re-runs. A segmenter that lists
`"corrections"` in `reads` receives the log and honours it itself;
for any other, the log is replayed over its result, and every correction
that could not be honoured is flagged, never dropped.

```pycon
>>> seg = segment(boundaries=[0, 10, 20], steps=['intro', 'verse'])
>>> [(s.name, s.spans) for s in seg.steps]
[('intro', ((0.0, 10.0),)), ('verse', ((10.0, 20.0),))]
```

* **Return type:**
  [`Segmentation`](paces.segmentation.html.md#paces.segmentation.Segmentation)

### paces.segmenters.unique_slug_ids(names, , fallback='step')

One unique, git-readable id per name; unnamed ones get `{fallback}-{i}`.

```pycon
>>> unique_slug_ids(["Turn", "", "Turn"], fallback="cue")
['turn', 'cue-2', 'turn-2']
```

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]
