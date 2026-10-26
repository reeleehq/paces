# paces.measure

Measure a [`MetricGrid`](paces.model.html.md#paces.model.MetricGrid) from the media itself.

Roadmap issue #2: when no grid is supplied, the media can often supply its
own — the fleet’s `mixing` package owns the primitives (speech/music
segmentation, beat tracking) and this module composes them, in the cost order
the POC proved out (`docs/01-what-was-built.md §3.1`):

1. **Macro-structure** — `find_segments(strategy="speech_music")` splits
   talk from music; the longest music region is where a routine lives.
2. **Tempo** — `beat_grid` on that region (librosa under the hood).
3. **Origin** — the weak link, stated honestly: tempo alone cannot give the
   phase. v1 anchors on the first detected beat of the music region, reports
   LOW confidence, and flags the estimate for confirmation — per ADR-0003, a
   default chosen automatically must be reported with its confidence and
   overridable by one keyword (`grid=`).

Honesty under failure (adversarial review, PR #13): media with no beat
structure — silence, ambience, an empty file — yields a grid whose tempo is
honestly `None` (never `"0"`: [`MetricGrid`](paces.model.html.md#paces.model.MetricGrid) refuses
non-positive tempi) plus a `tempo-unmeasured` flag, and the `segment()`
facade keeps its returns-a-Segmentation-always contract.

The `grid-measured` capability wires this into `
segment()`: media + a step list with durations, no full grid → measure, then
place exactly as `grid-placed` would. A *partial* `grid=` is honoured as
“what the caller knows” — unit and subdivisions always, and a caller-supplied
tempo or origin **wins over the measured value** (explicit beats inferred),
with a `tempo-disagreement` flag when the media measurably disagrees — the
POC’s doc-said-100-video-says-129 lesson, surfaced as a diff instead of
silently resolved either way.

Everything heavy is imported lazily — `import paces` never pulls librosa —
and the capability preflights `mixing`/`librosa` (the `[audio]` extra).

### Module Attributes

| [`DFLT_MEASURED_CONFIDENCE`](#paces.measure.DFLT_MEASURED_CONFIDENCE)   | "first beat of the music region" is right when the routine starts on bar one, and wrong by an intro.   |
|-----------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|
| [`KNOWN_ORIGIN_CONFIDENCE`](#paces.measure.KNOWN_ORIGIN_CONFIDENCE)    | A caller-supplied origin removes the weak link; the tempo half is reliable.                            |
| [`FIT_BONUS`](#paces.measure.FIT_BONUS)                  | Earned when the declared routine length fits inside the music region.                                  |
| [`TEMPO_DISAGREEMENT_RTOL`](#paces.measure.TEMPO_DISAGREEMENT_RTOL)    | A caller tempo further than this (relative) from the measured one is flagged.                          |

### Functions

| [`measure_grid`](#paces.measure.measure_grid)(media, \*[, unit, subdivisions, ...])   | Measure tempo, macro-structure and (estimated) origin from *media*.   |
|-------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------|

### Classes

| [`GridMeasurement`](#paces.measure.GridMeasurement)(\*, grid, confidence[, ...])   | A measured grid, how much to trust it, and the evidence why.   |
|-------------------------------------------------------------------------------------------------|----------------------------------------------------------------|

### Exceptions

| [`MediaDecodeError`](#paces.measure.MediaDecodeError)   | The file exists but could not be read as audio.   |
|---------------------------------------------------------------------|---------------------------------------------------|

### paces.measure.DFLT_MEASURED_CONFIDENCE *= 0.5*

“first beat of the music
region” is right when the routine starts on bar one, and wrong by an intro.

* **Type:**
  The origin estimate is the honest weak link

### paces.measure.FIT_BONUS *= 0.2*

Earned when the declared routine length fits inside the music region.

### *class* paces.measure.GridMeasurement(, grid, confidence, flags=(), evidence=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A measured grid, how much to trust it, and the evidence why.

### paces.measure.KNOWN_ORIGIN_CONFIDENCE *= 0.75*

A caller-supplied origin removes the weak link; the tempo half is reliable.

### *exception* paces.measure.MediaDecodeError

Bases: [`ValueError`](https://docs.python.org/3/builtins/exceptions.html#ValueError)

The file exists but could not be read as audio.

### paces.measure.TEMPO_DISAGREEMENT_RTOL *= 0.02*

A caller tempo further than this (relative) from the measured one is flagged.

### paces.measure.measure_grid(media, , unit='eight', subdivisions=8, tempo_bpm=None, origin=None, total_units=None, sample_rate=22050)

Measure tempo, macro-structure and (estimated) origin from *media*.

*media* is a local audio (or audio-bearing) file. *tempo_bpm* and
*origin*, when given, are what the caller already knows: they WIN over
the measured values (a disagreement is flagged, never silently resolved).
*total_units* (the sum of a step list’s durations) buys a sanity check: a
routine that cannot fit inside the detected music region is flagged.

Returns a [`GridMeasurement`](#paces.measure.GridMeasurement); whatever could not be measured stays
honestly `None` on the grid, with a flag naming it.

* **Return type:**
  [`GridMeasurement`](#paces.measure.GridMeasurement)
