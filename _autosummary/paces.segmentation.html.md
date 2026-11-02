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
