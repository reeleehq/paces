# paces.segmentation

What a segmenter returns: [`Segmentation`](#paces.segmentation.Segmentation), its [`SegStep`](#paces.segmentation.SegStep) records and
the `Span` they cover — the analysis-result types, with nothing else.

They live apart from [`paces.segmenters`](paces.segmenters.html.md#module-paces.segmenters) (the registry and the
`segment()` facade) so a module that only consumes or reshapes a result —
[`paces.corrections`](paces.corrections.html.md#module-paces.corrections), [`paces.projection`](paces.projection.html.md#module-paces.projection), [`paces.ask`](paces.ask.html.md#module-paces.ask), the
evidence layer — depends on the types and not on the facade, and the facade
can import those modules without a cycle. [`paces.segmenters`](paces.segmenters.html.md#module-paces.segmenters) re-exports
every name here, so `from paces.segmenters import Segmentation` keeps
working.

### Module Attributes

| [`TIME_PLACES`](#paces.segmentation.TIME_PLACES)   | milliseconds, the wire's resolution.   |
|----------------------------------------------------------------|----------------------------------------|

### Functions

| [`edges`](#paces.segmentation.edges)(steps)                                  | Every span start and end of `steps` (top level).                                                                                                                                                                        |
|------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`inconsistencies`](#paces.segmentation.inconsistencies)(seg, \*[, max_overlap_flags]) | What no segmentation may contain, as `inconsistent:` flags — never repaired, never raised: empty spans, spans of different steps that overlap, children outside their parent, and step edges missing from `boundaries`. |
| [`overlaps`](#paces.segmentation.overlaps)(a, b)                                | True when the two spans share a positive length of time.                                                                                                                                                                |
| [`time_str`](#paces.segmentation.time_str)(t)                                   | A time as paces' millisecond wire decimal — the one formatter every time producer shares (the ask page's `timeStr` mirrors it).                                                                                         |

### Classes

| [`SegStep`](#paces.segmentation.SegStep)(\*, id[, name, spans, confidence, ...])   | One named piece of the media, as an analysis result.   |
|----------------------------------------------------------------------------------------------------|--------------------------------------------------------|
| [`Segmentation`](#paces.segmentation.Segmentation)(\*[, steps, boundaries, unit, ...])  | What every segmenter returns.                          |

### *class* paces.segmentation.SegStep(, id, name='', spans=(), confidence=0.0, children=(), source='', evidence=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

One named piece of the media, as an analysis result.

`name=''` means “found, not named” — a VALID state, not an error.
`spans` is a tuple because a step legitimately appears in several places
(run-through AND breakdown).

### *class* paces.segmentation.Segmentation(, steps=(), boundaries=(), unit='seconds', grid=None, confidence=0.0, method='', flags=(), elapsed_s=0.0, spent_usd=0.0)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What every segmenter returns. Reviewable, re-runnable, arguable.

`boundaries` is separate from `steps` and populated even when naming
failed: nine excellent unnamed cuts are a useful, honest result. `steps`
may be empty while `boundaries` is not.

### paces.segmentation.TIME_PLACES *= 3*

milliseconds, the wire’s
resolution. Corrections round to it at construction, so their wire round trip
is lossless (`decimal_str` writes exactly this many).

* **Type:**
  Decimal places every computed time keeps (spans, boundaries, corrections)

### paces.segmentation.edges(steps)

Every span start and end of `steps` (top level).

* **Return type:**
  [`set`](https://docs.python.org/3/builtins/stdtypes.html#set)[[`float`](https://docs.python.org/3/builtins/functions.html#float)]

### paces.segmentation.inconsistencies(seg, , max_overlap_flags=20)

What no segmentation may contain, as `inconsistent:` flags — never
repaired, never raised: empty spans, spans of different steps that
overlap, children outside their parent, and step edges missing from
`boundaries`. [`paces.segmenters.segment()`](paces.segmenters.html.md#paces.segmenters.segment) runs it on every result,
whichever segmenter produced it and whether or not a correction log ran.

```pycon
>>> inconsistencies(Segmentation(
...     steps=(SegStep(id="a", spans=((0.0, 10.0),)),
...            SegStep(id="b", spans=((8.0, 20.0),))),
...     boundaries=(0.0, 10.0, 20.0)))
("inconsistent: steps 'a' and 'b' overlap (8–10)", 'inconsistent: step edges not in boundaries: 8')
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)]

### paces.segmentation.overlaps(a, b)

True when the two spans share a positive length of time.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### paces.segmentation.time_str(t)

A time as paces’ millisecond wire decimal — the one formatter every
time producer shares (the ask page’s `timeStr` mirrors it).

```pycon
>>> time_str(95.80000001), time_str(10.0625)  # exact binary ties round half-even
('95.8', '10.062')
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
