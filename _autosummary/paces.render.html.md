# paces.render

Render a [`StepDocument`](paces.model.html.md#paces.model.StepDocument) into learning material.

The renderer depends on the document and [`resolve()`](paces.model.html.md#paces.model.resolve) — never
on the analyser. v1 ships one renderer: a self-contained HTML practice page
(steps, counts, captions, deep links into the sources, and — when the document
has a metric grid — a count-along transport that paces you through the
routine, which is the behaviour the package is named after).

### Module Attributes

| [`ROLE_LABELS`](#paces.render.ROLE_LABELS)   | Span roles shown as deep links, in display order.   |
|----------------------------------------------------------------|-----------------------------------------------------|

### Functions

| [`render_html`](#paces.render.render_html)(doc)   | The practice page: steps, counts, deep links, captions, and (with a grid) the count-along transport.   |
|---------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|

### paces.render.ROLE_LABELS *= {'closeup': 'close-up', 'instruction': 'breakdown', 'performance': 'run-through'}*

Span roles shown as deep links, in display order.

### paces.render.render_html(doc)

The practice page: steps, counts, deep links, captions, and (with a
grid) the count-along transport. Self-contained; media-free by design —
derived clips arrive via `ArtifactRef` when the media layer exists.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
