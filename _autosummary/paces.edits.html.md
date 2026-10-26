# paces.edits

Document-layer edit protection: typed patches write Locks; regeneration
merges without eating edits.

The POC’s single most expensive failure was regeneration destroying hand
edits (`docs/07-annotation-model.md §1.3`). The remedy has two halves, both
here and both store-independent (`docs/07 §6.4` steps 4–6):

- [`apply_edits()`](#paces.edits.apply_edits) — edits are **typed patches**
  (`{"op": "set", "path": "/steps/b4/name", "value": ...}`), validated
  before application, and every edit writes a [`Lock`](paces.model.html.md#paces.model.Lock) with
  the pre-edit value, so every edit is reversible and every protected path is
  explicit.
- [`merge_regenerated()`](#paces.edits.merge_regenerated) — a fresh analysis projection merged against the
  committed document: locked paths keep the committed value, everything else
  takes the fresh value, and committed-only steps that carry protection
  survive.

Path rules (each earned by an adversarial review, PR #11):

- List items are addressed **by id first** (`/steps/b4/name`); an ASCII
  digit segment is an index only when no item carries that id. Ids are
  stabler across regenerations — always prefer them.
- Field segments accept the wire’s camelCase or Python’s snake_case; recorded
  `Lock.path`s are canonicalised to snake_case and to id-form where an
  unambiguous id exists.
- On merge, a lock is re-applied by **matching list items structurally**
  (id; a span’s exact `(source, role, start)`, falling back to
  `(source, role)` only for singleton groups; an artifact’s `uri`) —
  never by bare position, not even within a group, because regeneration
  reorders lists and a positional write would land on the wrong item. When
  no confident match exists, nothing is written and the lock survives as
  the record. Scalar list items (tags) have no identity besides their
  value, so an edited scalar cannot be re-found after regeneration — the
  edit does not survive; only its lock record does.
- `attrs` bags merge committed-over-fresh per key: they are user/renderer
  data that analysis does not produce, so regeneration never wins there.
- Renaming a list item’s `id` onto an id already used by another item in
  the same list is refused at edit time (previously accepted, and only
  flagged later by [`validate_document()`](paces.model.html.md#paces.model.validate_document)) — issue #12.
- A step rename (its own `/id` lock) is remembered by [`merge_regenerated()`](#paces.edits.merge_regenerated):
  a fresh projection that still emits the pre-rename id (because analysis
  does not know about the rename) is matched to the renamed committed step
  instead of being treated as a new, unrelated step — otherwise the old id
  resurfaces alongside the renamed one. This does not follow renames inside
  a merge across multiple regenerations; only the most recent `/id` lock is
  consulted (issue #12).

Not yet recorded anywhere: the fresh values a merge *rejects*. The evidence
they would be recorded against now exists — `paces.evidence` fills
`Origin.annotation_id` / `Origin.value_digest` on every projected step
(issue #4) — but wiring the *rejected* value into the merge is document-side
work and belongs with the rest of issue #12.

### Module Attributes

| [`SUPPORTED_OPS`](#paces.edits.SUPPORTED_OPS)   | The ops v1 supports.   |
|------------------------------------------------------------------|------------------------|

### Functions

| [`apply_edits`](#paces.edits.apply_edits)(doc, edits, \*, by[, at, reason])   | Apply typed patches to a document, recording a Lock per edit.     |
|--------------------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| [`merge_regenerated`](#paces.edits.merge_regenerated)(committed, fresh)             | Merge a fresh analysis projection against the committed document. |

### paces.edits.SUPPORTED_OPS *= ('set',)*

The ops v1 supports. `append`/`delete` arrive at the third real need
(they require tombstone semantics in the merge — see issue #5).

### paces.edits.apply_edits(doc, edits, , by, at=None, reason=None)

Apply typed patches to a document, recording a Lock per edit.

Each edit is `{"op": "set", "path": ..., "value": ...}` (a single edit
may be passed bare). All edits are validated together — an invalid edit
means NO edit is applied. Editing an already-locked path replaces the
lock (`was` becomes the value this edit overwrote, keeping the last
edit reversible).

```pycon
>>> from paces.model import Measure, Step, StepDocument
>>> doc = StepDocument(id='g', title='G', steps=[
...     Step(id='a', name='old', duration=Measure(value='2', unit='eight'))])
>>> edited = apply_edits(doc, [{'op': 'set', 'path': '/steps/a/name',
...                             'value': 'new'}], by='user:thor')
>>> edited.steps[0].name, edited.steps[0].locks[0].was
('new', 'old')
```

* **Return type:**
  [`StepDocument`](paces.model.html.md#paces.model.StepDocument)

### paces.edits.merge_regenerated(committed, fresh)

Merge a fresh analysis projection against the committed document.

The rules, in order of authority:

1. **Locked paths keep the committed value** — on the document and on
   every step matched by id, recursively — re-applied by structural
   match, never by bare position (a reorder must not land a locked value
   on the wrong item).
2. Everything else takes the fresh value (regeneration is allowed to
   improve what nobody protected) — except `attrs`, where committed
   wins per key.
3. Committed-only steps survive when protected (locks in their subtree or
   a `user:` origin); unprotected ones are superseded analysis output.
4. Cues, questions and sources are unioned by id (fresh wins on shared
   ids) — analysis rarely regenerates them, and dropping committed
   content silently is the failure this module exists to prevent.

Edits made through [`apply_edits()`](#paces.edits.apply_edits) are always locked, so “hand edit”
and “protected” coincide by construction; edits made by hand-editing the
JSON without locks are, deliberately, not protected.

* **Return type:**
  [`StepDocument`](paces.model.html.md#paces.model.StepDocument)
