# paces.projection

The projection from analysis result to document: `to_document`.

A `Segmentation` is the *analysis result*; a
[`StepDocument`](paces.model.html.md#paces.model.StepDocument) is the *artifact* — committed, hand-edited,
rendered. Keeping them separate (one function between) is what lets the
segmenter re-run without touching hand-edited captions
(`docs/alignment/07 §9.1` decision 6).

### Module Attributes

| [`DECIMAL_PLACES`](#paces.projection.DECIMAL_PLACES)   | Decimal places kept when converting computed seconds to wire decimals — matches the POC's 0.1 s working resolution with headroom.   |
|-------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------|

### Functions

| [`to_document`](#paces.projection.to_document)(seg, \*[, doc_id, title, source, ...])   | Project a segmentation into a fresh step document.   |
|-------------------------------------------------------------------------------------------------------|------------------------------------------------------|

### paces.projection.DECIMAL_PLACES *= 3*

Decimal places kept when converting computed seconds to wire decimals —
matches the POC’s 0.1 s working resolution with headroom.

### paces.projection.to_document(seg, , doc_id='guide', title='', source=None, domain='generic', lang='en')

Project a segmentation into a fresh step document.

*source* is the media the spans refer into: a URI string, a
[`Source`](paces.model.html.md#paces.model.Source), or a mapping. Hand edits belong on the
returned document, never back on the segmentation.

* **Return type:**
  [`StepDocument`](paces.model.html.md#paces.model.StepDocument)
