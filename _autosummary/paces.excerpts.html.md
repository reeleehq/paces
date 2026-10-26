# paces.excerpts

Excerpt suggestion: mark the loopable sub-window each step’s clip is cut
from.

A [`SourceSpan`](paces.model.html.md#paces.model.SourceSpan) with an `excerpt` is what media
derivation (ADR-0005) cuts; nothing upstream sets one. This module holds the
v1 heuristic (issue #3’s cost note): \*\*a step’s excerpt is its own grid
window\*\* — the span itself — or, with `units=`, its first N metric units.
Editorial window-picking (the POC spent ~11 min of LLM agents over contact
sheets choosing windows by eye) is a later capability that replaces this
default behind the same seam; corrections meanwhile are ordinary document
edits, which a suggestion must never eat:

- an existing excerpt is only replaced under `overwrite=True`, and even
  then only by a real new suggestion — **never by nothing** (a heuristic
  that cannot compute a window keeps what the human picked, with a flag);
- a step carrying any span-level lock that could denote an excerpt gets
  **no suggestions at all**: lock paths are recorded in index form and a
  regeneration merge reorders spans (`edits.py`’s own premise), so “which
  span does `/spans/0/excerpt` mean now?” cannot be answered here —
  abstaining loses a default; guessing can silently undo a locked edit.

Honesty flags over silence: every span this module skips or cannot fill is
flagged by name.

### Module Attributes

| [`DFLT_EXCERPT_ROLE`](#paces.excerpts.DFLT_EXCERPT_ROLE)   | The span role a clip is cut from by default — the at-tempo run-through.   |
|----------------------------------------------------------------------|---------------------------------------------------------------------------|

### Functions

| [`suggest_excerpts`](#paces.excerpts.suggest_excerpts)(document, \*[, units, role, ...])   | Fill each step's first *role* span with a suggested `excerpt`.   |
|-------------------------------------------------------------------------------------------------------|------------------------------------------------------------------|

### Classes

| [`ExcerptResult`](#paces.excerpts.ExcerptResult)(document[, flags, suggested])   | The updated document plus the honesty flags.   |
|------------------------------------------------------------------------------------------------|------------------------------------------------|

### paces.excerpts.DFLT_EXCERPT_ROLE *= 'performance'*

The span role a clip is cut from by default — the at-tempo run-through.

### *class* paces.excerpts.ExcerptResult(document, flags=list(), suggested=list())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

The updated document plus the honesty flags.

### paces.excerpts.suggest_excerpts(document, , units=None, role='performance', overwrite=False)

Fill each step’s first *role* span with a suggested `excerpt`.

* **Parameters:**
  * **document** ([`StepDocument`](paces.model.html.md#paces.model.StepDocument)) – the committed document (worked on a deep copy).
  * **units** ([`float`](https://docs.python.org/3/builtins/functions.html#float) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – `None` (default) → the excerpt is the span’s whole window
    (`start`..\`\`end\`\` — for grid-placed segmentation that IS the
    block’s grid window, which is issue #3’s acceptance). A number →
    the first that-many metric units from the span’s start, computed
    through the document’s grid and clipped to the span’s end.
  * **role** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – which span carries the clip (default `"performance"` — the
    run-through). A step whose spans lack the role is flagged; a
    step with SEVERAL role spans gets a suggestion on the first and
    a `multiple-<role>-spans:` flag for the rest (the POC’s b8
    shape — the other moments still derive once excerpts are set by
    hand or a future picker).
  * **overwrite** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – replace existing excerpts with new suggestions. Off by
    default; replacement never degrades to deletion, and a span-
    locked step abstains entirely (see the module docstring).
* **Return type:**
  [`ExcerptResult`](#paces.excerpts.ExcerptResult)
