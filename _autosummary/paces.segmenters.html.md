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

Honesty rules (`docs/alignment/07 §9.5`): a segmenter may never return a
step count it has no evidence for. Four legitimate return states — confident /
found-unnamed / proposed-uncertain / refused — all expressed by the type, none
by an exception.

### Functions

| [`capabilities`](#paces.segmenters.capabilities)()                          | The registered capability catalog (read-only view).            |
|------------------------------------------------------------------------------------------|----------------------------------------------------------------|
| [`register`](#paces.segmenters.register)(capability)                    | Register a segmentation capability; returns it for assignment. |
| [`segment`](#paces.segmenters.segment)([media, segmenter, steps, ...]) | Cut *media* into named steps, using whatever else is present.  |

### Classes

| [`Capability`](#paces.segmenters.Capability)(\*, name, gives, summary, target)     | What one method needs, gives, and costs.             |
|---------------------------------------------------------------------------------------------------|------------------------------------------------------|
| [`SegStep`](#paces.segmenters.SegStep)(\*, id[, name, spans, confidence, ...])  | One named piece of the media, as an analysis result. |
| [`Segmentation`](#paces.segmenters.Segmentation)(\*[, steps, boundaries, unit, ...]) | What every segmenter returns.                        |

### *class* paces.segmenters.Capability(, name, gives, summary, target, needs=frozenset({}), reads=frozenset({}), boosts=dict(), requires=(), licence='MIT', base=0.0, s_per_min=0.0, usd_per_hour=0.0, device='cpu', fixed_s=0.0, resolution_s=1.0, calibrated_on=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What one method needs, gives, and costs. Selection reads ONLY this.

The record from `docs/alignment/06 §1.2`, reused unchanged so the
eventual planner and the segmenter registry share one declaration format.
`target` is a lazy `"module:func"` ref — listing a heavy capability
must not import its dependencies.

### *class* paces.segmenters.SegStep(, id, name='', spans=(), confidence=0.0, children=(), source='', evidence=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

One named piece of the media, as an analysis result.

`name=''` means “found, not named” — a VALID state, not an error.
`spans` is a tuple because a step legitimately appears in several places
(run-through AND breakdown).

### *class* paces.segmenters.Segmentation(, steps=(), boundaries=(), unit='seconds', grid=None, confidence=0.0, method='', flags=(), elapsed_s=0.0, spent_usd=0.0)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What every segmenter returns. Reviewable, re-runnable, arguable.

`boundaries` is separate from `steps` and populated even when naming
failed: nine excellent unnamed cuts are a useful, honest result. `steps`
may be empty while `boundaries` is not.

### paces.segmenters.capabilities()

The registered capability catalog (read-only view).

* **Return type:**
  [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Capability`](#paces.segmenters.Capability)]

### paces.segmenters.register(capability)

Register a segmentation capability; returns it for assignment.

* **Return type:**
  [`Capability`](#paces.segmenters.Capability)

### paces.segmenters.segment(media=None, , segmenter=None, steps=None, boundaries=None, grid=None, metadata=None, k=None, catalog=None)

Cut *media* into named steps, using whatever else is present.

Returns a [`Segmentation`](#paces.segmenters.Segmentation) ALWAYS. A segmenter that cannot name the
steps returns `boundaries` and `steps=()`; when nothing applies the
result is the refused state (`flags=('no-signal', 'try: ...')`), not an
exception.

The seam: `segmenter=None` selects from what is present; a name pins it.

```pycon
>>> seg = segment(boundaries=[0, 10, 20], steps=['intro', 'verse'])
>>> [(s.name, s.spans) for s in seg.steps]
[('intro', ((0.0, 10.0),)), ('verse', ((10.0, 20.0),))]
```

* **Return type:**
  [`Segmentation`](#paces.segmenters.Segmentation)
