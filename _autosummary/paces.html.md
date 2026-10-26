# paces

Turn instructional media into structured, interactive learning material.

Take a video of someone teaching something — plus, optionally, notes and a
steering prompt — segment it into named steps, build a structured step
document (the AST), and render that into learning material: a practice page
today, other guides later. *Put it through its paces.*

Two phases, one contract between them:

- **Analyse** — [`segment()`](#paces.segment) cuts media into steps. Segmentation is a seam,
  not a stage: segmenters are registered capabilities and the default follows
  from what is present (ADR-0003).
- **Render** — renderers consume the [`StepDocument`](#paces.StepDocument) and never the
  analyser.

Quickstart:

```default
from paces import segment, to_document, render_html

seg = segment(
    "https://youtu.be/...",
    steps=[("Warm-up", 2), ("The turn", 4), ("Finale", 2)],
    grid={"unit": "eight", "subdivisions": 8,
          "tempoBpm": "129.2", "origin": "51.2"},
)
doc = to_document(seg, doc_id="my-routine", title="My routine",
                  source="https://youtu.be/...")
html = render_html(doc)
```

### Functions

| [`dumps_document`](#paces.dumps_document)(doc)                                | Serialise a document to its canonical wire form.                                                                                                                         |
|-----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`loads_document`](#paces.loads_document)(text)                               | Parse a document from its wire form (accepts camelCase or snake_case).                                                                                                   |
| [`resolve`](#paces.resolve)(doc)                                       | Compute absolute metric offsets (and wall-clock times, when the grid allows) for every step.                                                                             |
| [`seconds_per_unit`](#paces.seconds_per_unit)(grid)                             | Seconds one domain unit lasts under *grid*, or None without a tempo.                                                                                                     |
| [`validate_document`](#paces.validate_document)(doc)                             | Semantic checks beyond the schema.                                                                                                                                       |
| [`segment`](#paces.segment)([media, segmenter, steps, ...])            | Cut *media* into named steps, using whatever else is present.                                                                                                            |
| [`register`](#paces.register)(capability)                               | Register a segmentation capability; returns it for assignment.                                                                                                           |
| [`capabilities`](#paces.capabilities)()                                     | The registered capability catalog (read-only view).                                                                                                                      |
| [`measure_grid`](#paces.measure_grid)(media, \*[, unit, subdivisions, ...]) | Measure tempo, macro-structure and (estimated) origin from *media*.                                                                                                      |
| [`to_document`](#paces.to_document)(seg, \*[, doc_id, title, source, ...]) | Project a segmentation into a fresh step document.                                                                                                                       |
| [`suggest_excerpts`](#paces.suggest_excerpts)(document, \*[, units, role, ...]) | Fill each step's first *role* span with a suggested `excerpt`.                                                                                                           |
| [`derive_document`](#paces.derive_document)(document, \*, media[, ...])        | Derive media for every excerpt-bearing span and return the updated document (the caller persists it; media and recipes are written here).                                |
| [`full_frame`](#paces.full_frame)(query)                                  | The default locator: no crop, ever — a real implementation of the contract whose honest answer is `None` (docs/09: the seam must be "genuinely pluggable and nullable"). |
| [`resolve_crop_box`](#paces.resolve_crop_box)(observation, \*, frame_size)      | The locator-agnostic crop policy: observation → ONE static box.                                                                                                          |
| [`check_media_requirements`](#paces.check_media_requirements)()                         | Two-channel media preflight (ADR-0005 §2), reported distinctly:                                                                                                          |
| [`apply_edits`](#paces.apply_edits)(doc, edits, \*, by[, at, reason])      | Apply typed patches to a document, recording a Lock per edit.                                                                                                            |
| [`merge_regenerated`](#paces.merge_regenerated)(committed, fresh)                | Merge a fresh analysis projection against the committed document.                                                                                                        |
| [`render_html`](#paces.render_html)(doc)                                   | The practice page: steps, counts, deep links, captions, and (with a grid) the count-along transport.                                                                     |

### Classes

| [`StepDocument`](#paces.StepDocument)(\*[, kind, schemaVersion, lang, ...])   | The committed, hand-editable, git-diffable step document — the AST.                                                                                                                                                                                                            |
|-------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`Step`](#paces.Step)(\*, id, name, duration[, description, ...])     | One named piece of the routine — the unit a learner practises.                                                                                                                                                                                                                 |
| [`Measure`](#paces.Measure)(\*, value, unit)                             | A duration in the DOMAIN's own unit — never seconds unless the domain's unit is seconds.                                                                                                                                                                                       |
| [`MetricGrid`](#paces.MetricGrid)(\*, unit[, subdivisions, ...])            | How the domain unit relates to wall-clock time, when it does at all.                                                                                                                                                                                                           |
| [`Source`](#paces.Source)(\*, id, kind, uri[, assetId, ...])            | One input the document's spans refer into (a video, a notes doc, ...).                                                                                                                                                                                                         |
| [`SourceSpan`](#paces.SourceSpan)(\*, source[, role, end, excerpt, ...])    | ONE step's presence in ONE source, in ONE role.                                                                                                                                                                                                                                |
| [`ArtifactRef`](#paces.ArtifactRef)(\*, role, uri[, assetId, mime, ...])     | WHAT a derived file is, never HOW it was made — the recipe lives in the evidence layer (`paces.evidence`, tier `derivation`) and in the committed span-address-keyed `<stem>.recipes.json` sidecar (ADR-0005 §3), which stay in step: both are keyed by the same span address. |
| [`Cue`](#paces.Cue)(\*, id, kind, text, anchor[, duration, ...])     | A landmark the learner can hear or watch for (a lyric, a count, ...).                                                                                                                                                                                                          |
| [`Anchor`](#paces.Anchor)(\*, step[, offset])                           | Where a cue attaches: a step, plus an optional relative offset in the domain unit.                                                                                                                                                                                             |
| [`OpenQuestion`](#paces.OpenQuestion)(\*, id, text[, status, ...])            | The POC's `note` fields, promoted: uncertainty and its resolution are first-class content, not scratch.                                                                                                                                                                        |
| [`Lock`](#paces.Lock)(\*, path, by, at[, was, reason])                | A human (or approved-AI) decision that regeneration MUST NOT overwrite.                                                                                                                                                                                                        |
| [`Origin`](#paces.Origin)(\*[, annotationId, valueDigest, ...])         | Back-reference into the evidence layer: why this node says what it says, and what a regeneration may replace.                                                                                                                                                                  |
| [`Segmentation`](#paces.Segmentation)(\*[, steps, boundaries, unit, ...])     | What every segmenter returns.                                                                                                                                                                                                                                                  |
| [`SegStep`](#paces.SegStep)(\*, id[, name, spans, confidence, ...])      | One named piece of the media, as an analysis result.                                                                                                                                                                                                                           |
| [`Capability`](#paces.Capability)(\*, name, gives, summary, target)         | What one method needs, gives, and costs.                                                                                                                                                                                                                                       |
| [`GridMeasurement`](#paces.GridMeasurement)(\*, grid, confidence[, ...])         | A measured grid, how much to trust it, and the evidence why.                                                                                                                                                                                                                   |
| [`ExcerptResult`](#paces.ExcerptResult)(document[, flags, suggested])          | The updated document plus the honesty flags.                                                                                                                                                                                                                                   |
| [`DeriveResult`](#paces.DeriveResult)(document[, flags, derived])             | What a derive run did: the updated document, the honesty flags, and one row per derived (or byte-stably reused) span.                                                                                                                                                          |
| [`DirStore`](#paces.DirStore)(rootdir)                                    | Minimal `MutableMapping[str, bytes]` over files under a root directory, keyed by relative POSIX paths (`media/b4.mp4`).                                                                                                                                                        |
| [`LocateQuery`](#paces.LocateQuery)(media_path, start_s, end_s, ...)         | What a `subject_locator` is asked: one excerpt window of one media file, with read-only hints.                                                                                                                                                                                 |
| [`SubjectObservation`](#paces.SubjectObservation)(samples)                          | Timed raw region evidence: `samples[i] = (t_s, (box, box, ...))` — one region tuple per probed instant.                                                                                                                                                                        |

### *class* paces.Anchor(, step, offset=None)

Bases: `_Base`

Where a cue attaches: a step, plus an optional relative offset in the
domain unit. NEVER an absolute time.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.ArtifactRef(\*, role, uri, assetId=None, mime=None, width=None, height=None, durationS=None, derivedFrom=None, attrs=<factory>)

Bases: `_Base`

WHAT a derived file is, never HOW it was made — the recipe lives in the
evidence layer (`paces.evidence`, tier `derivation`) and in the
committed span-address-keyed `<stem>.recipes.json` sidecar (ADR-0005 §3),
which stay in step: both are keyed by the same span address.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.Capability(, name, gives, summary, target, needs=frozenset({}), reads=frozenset({}), boosts=dict(), requires=(), licence='MIT', base=0.0, s_per_min=0.0, usd_per_hour=0.0, device='cpu', fixed_s=0.0, resolution_s=1.0, calibrated_on=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What one method needs, gives, and costs. Selection reads ONLY this.

The record from `docs/alignment/06 §1.2`, reused unchanged so the
eventual planner and the segmenter registry share one declaration format.
`target` is a lazy `"module:func"` ref — listing a heavy capability
must not import its dependencies.

### *class* paces.Cue(\*, id, kind, text, anchor, duration=None, source=None, atS=None, attrs=<factory>)

Bases: `_Base`

A landmark the learner can hear or watch for (a lyric, a count, …).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.DeriveResult(document, flags=list(), derived=list())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What a derive run did: the updated document, the honesty flags, and
one row per derived (or byte-stably reused) span.

### *class* paces.DirStore(rootdir)

Bases: [`MutableMapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.MutableMapping)

Minimal `MutableMapping[str, bytes]` over files under a root
directory, keyed by relative POSIX paths (`media/b4.mp4`).

The default backend of the ADR-0005 store seam — stdlib-only so the
pydantic-only core stays intact (ADR-0004). Inject a `dol`/`s3dol`
store for other backends; the key contract (document-relative POSIX uri)
is backend-independent.

### *class* paces.ExcerptResult(document, flags=list(), suggested=list())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

The updated document plus the honesty flags.

### *class* paces.GridMeasurement(, grid, confidence, flags=(), evidence=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A measured grid, how much to trust it, and the evidence why.

### *class* paces.LocateQuery(media_path, start_s, end_s, frame_width, frame_height, step_id, tags=())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What a `subject_locator` is asked: one excerpt window of one media
file, with read-only hints. Times are float seconds — a computed view,
like [`paces.model.resolve()`](paces.model.html.md#paces.model.resolve)’s output, never the stored document.

### *class* paces.Lock(, path, by, at, was=None, reason=None)

Bases: `_Base`

A human (or approved-AI) decision that regeneration MUST NOT overwrite.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.Measure(, value, unit)

Bases: `_Base`

A duration in the DOMAIN’s own unit — never seconds unless the domain’s
unit is seconds.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.MetricGrid(, unit, subdivisions=1, tempoBpm=None, origin=None, originSource=None)

Bases: `_Base`

How the domain unit relates to wall-clock time, when it does at all.

Optional by design: a “reps” domain has no grid; a dance routine does —
and the grid is what drives the metronome and [`resolve()`](#paces.resolve).

A non-positive tempo or subdivision count is unrepresentable, not merely
discouraged: a zero tempo makes every duration infinite and every
`seconds_per_unit` division a crash, so “tempo unknown” is spelled
`tempo_bpm=None`, never `"0"`.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.OpenQuestion(\*, id, text, status='open', resolution=None, evidence=<factory>)

Bases: `_Base`

The POC’s `note` fields, promoted: uncertainty and its resolution are
first-class content, not scratch.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.Origin(, annotationId=None, valueDigest=None, generatedBy=None, confidence=None)

Bases: `_Base`

Back-reference into the evidence layer: why this node says what it says,
and what a regeneration may replace.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.SegStep(, id, name='', spans=(), confidence=0.0, children=(), source='', evidence=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

One named piece of the media, as an analysis result.

`name=''` means “found, not named” — a VALID state, not an error.
`spans` is a tuple because a step legitimately appears in several places
(run-through AND breakdown).

### *class* paces.Segmentation(, steps=(), boundaries=(), unit='seconds', grid=None, confidence=0.0, method='', flags=(), elapsed_s=0.0, spent_usd=0.0)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What every segmenter returns. Reviewable, re-runnable, arguable.

`boundaries` is separate from `steps` and populated even when naming
failed: nine excellent unnamed cuts are a useful, honest result. `steps`
may be empty while `boundaries` is not.

### *class* paces.Source(\*, id, kind, uri, assetId=None, durationS=None, title=None, attribution=None, rights=None, attrs=<factory>)

Bases: `_Base`

One input the document’s spans refer into (a video, a notes doc, …).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.SourceSpan(\*, source, role='performance', start, end=None, excerpt=None, label=None, caption=None, confidence=None, attrs=<factory>)

Bases: `_Base`

ONE step’s presence in ONE source, in ONE role. A step has a LIST of
these — several roles is the norm, not the exception.

`end=None` means “starts here, extent not recorded” (a deep link is a
point of entry, not an interval; recording an end it does not know would
be invention, not data).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.Step(\*, id, name, duration, description='', spans=<factory>, artifacts=<factory>, steps=<factory>, repeat=1, optional=False, variantOf=None, tags=<factory>, questions=<factory>, origin=None, locks=<factory>, attrs=<factory>)

Bases: `_Base`

One named piece of the routine — the unit a learner practises.

A step is a step: sub-steps are `Step``s in ``steps`. `repeat` says the
children cycle N times (the POC’s block 9 is `repeat=4` over two
sub-steps — structure, where the original hand-wrote a display override).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.StepDocument(\*, kind='StepDocument', schemaVersion='0.1.0', id, title, lang='en', domain='generic', metric=None, sources=<factory>, steps=<factory>, cues=<factory>, questions=<factory>, credits=None, locks=<factory>, attrs=<factory>)

Bases: `_Base`

The committed, hand-editable, git-diffable step document — the AST.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.SubjectObservation(samples)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Timed raw region evidence: `samples[i] = (t_s, (box, box, ...))` —
one region tuple per probed instant. Deliberately not person-shaped: one
box for a dancer, two for judo, hands + workpiece for cooking. Samples
are transient locator output; only the resolved box is ever persisted.

### paces.apply_edits(doc, edits, , by, at=None, reason=None)

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

### paces.capabilities()

The registered capability catalog (read-only view).

* **Return type:**
  [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Capability`](paces.segmenters.html.md#paces.segmenters.Capability)]

### paces.check_media_requirements()

Two-channel media preflight (ADR-0005 §2), reported distinctly:

- `bundled_ffmpeg` — the pip-bundled imageio-ffmpeg binary, which is
  all `derive` needs (mp4/gif via mixing; posters via cv2).
- `system_ffmpeg` — a PATH ffmpeg, which `derive` does NOT need but
  `measure_grid` on non-wav input does (pydub knows nothing of the
  bundled binary). A bundled-only check would report healthy on a
  machine where `measure_grid("video.mp4")` fails.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### paces.derive_document(document, , media, doc_path=None, media_store=None, recipes_path=None, subject_locator=None, aspect=0.8, pad=0.16, roles=('clip', 'gif', 'poster'))

Derive media for every excerpt-bearing span and return the updated
document (the caller persists it; media and recipes are written here).

* **Parameters:**
  * **document** ([`StepDocument`](paces.model.html.md#paces.model.StepDocument)) – the committed document (worked on a deep copy).
  * **media** – local media — one path when exactly one source carries
    excerpts, else `{source_id: path}`.
  * **doc_path** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – the document’s file path — the anchor for the default
    media store (`<dir>/media/`) and recipes sidecar
    (`<dir>/<stem>.recipes.json`). Without it, `media_store`
    AND `recipes_path` must be given explicitly: a document that
    arrived as data has no directory, and deriving into cwd
    silently would make every written uri a lie (ADR-0005 §1).
  * **media_store** ([`MutableMapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.MutableMapping) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – `MutableMapping[str, bytes]` keyed by
    document-relative POSIX uri. Default: [`DirStore`](#paces.DirStore) beside
    the document.
  * **recipes_path** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – the crop-recipes sidecar path.
  * **subject_locator** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`LocateQuery`](paces.derivation.html.md#paces.derivation.LocateQuery)], [`SubjectObservation`](paces.derivation.html.md#paces.derivation.SubjectObservation) | [`None`](https://docs.python.org/3/builtins/constants.html#None)]]) – the ADR-0005 §3 seam; default [`full_frame()`](#paces.full_frame)
    (no crop).
  * **aspect** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – crop aspect (w/h) the policy forces — only when a locator
    yields regions; never applied to a locked or full-frame box.
  * **pad** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – padding fraction around the envelope.
  * **roles** ([`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)]) – which artifact roles to produce, of `("clip", "gif",
    "poster")`.
* **Return type:**
  [`DeriveResult`](paces.derivation.html.md#paces.derivation.DeriveResult)

### paces.dumps_document(doc)

Serialise a document to its canonical wire form.

camelCase keys in declaration order, 2-space indent, UTF-8 readable
(`ensure_ascii=False` equivalent), trailing newline.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### paces.full_frame(query)

The default locator: no crop, ever — a real implementation of the
contract whose honest answer is `None` (docs/09: the seam must be
“genuinely pluggable and nullable”). Pointable replacement: rtmlib pose
boxes (Apache-2.0; never YOLO/ultralytics — AGPL, see ADR-0005 §3).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### paces.loads_document(text)

Parse a document from its wire form (accepts camelCase or snake_case).

* **Return type:**
  [`StepDocument`](paces.model.html.md#paces.model.StepDocument)

### paces.measure_grid(media, , unit='eight', subdivisions=8, tempo_bpm=None, origin=None, total_units=None, sample_rate=22050)

Measure tempo, macro-structure and (estimated) origin from *media*.

*media* is a local audio (or audio-bearing) file. *tempo_bpm* and
*origin*, when given, are what the caller already knows: they WIN over
the measured values (a disagreement is flagged, never silently resolved).
*total_units* (the sum of a step list’s durations) buys a sanity check: a
routine that cannot fit inside the detected music region is flagged.

Returns a [`GridMeasurement`](#paces.GridMeasurement); whatever could not be measured stays
honestly `None` on the grid, with a flag naming it.

* **Return type:**
  [`GridMeasurement`](paces.measure.html.md#paces.measure.GridMeasurement)

### paces.merge_regenerated(committed, fresh)

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

Edits made through [`apply_edits()`](#paces.apply_edits) are always locked, so “hand edit”
and “protected” coincide by construction; edits made by hand-editing the
JSON without locks are, deliberately, not protected.

* **Return type:**
  [`StepDocument`](paces.model.html.md#paces.model.StepDocument)

### paces.register(capability)

Register a segmentation capability; returns it for assignment.

* **Return type:**
  [`Capability`](paces.segmenters.html.md#paces.segmenters.Capability)

### paces.render_html(doc)

The practice page: steps, counts, deep links, captions, and (with a
grid) the count-along transport. Self-contained; media-free by design —
derived clips arrive via `ArtifactRef` when the media layer exists.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### paces.resolve(doc)

Compute absolute metric offsets (and wall-clock times, when the grid
allows) for every step. Pure; the analogue of walkthru’s
`resolve_timeline`.

Returns a JSON-able dict: `{"unit", "seconds_per_unit", "origin_s",
"total_units", "steps": [{"id", "name", "offset", "duration", "start_s",
"end_s", "repeat", "children": [...]}, ...]}`. Times are floats — this is
a computed view, not the stored document.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### paces.resolve_crop_box(observation, , frame_size, aspect=0.8, pad=0.16, lo=4, hi=96)

The locator-agnostic crop policy: observation → ONE static box.

Union regions per sample → robust percentile envelope (`lo`/`hi`) →
pad → force `aspect` (w/h, expanding the deficient dimension) → clamp
into the frame (shrinking aspect-true when the padded box exceeds it).
`None` in (no observation, or no sample carried a region) → `None`
out: full frame, no policy — no crop is genuinely uncropped.

```pycon
>>> obs = SubjectObservation(samples=((0.0, ((40, 40, 20, 40),)),))
>>> resolve_crop_box(obs, frame_size=(200, 200), pad=0.0, aspect=0.5)
(40, 40, 20, 40)
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int)] | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### paces.seconds_per_unit(grid)

Seconds one domain unit lasts under *grid*, or None without a tempo.

```pycon
>>> seconds_per_unit(MetricGrid(unit='eight', subdivisions=8, tempo_bpm='129.2'))
3.7151702786377707
```

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### paces.segment(media=None, , segmenter=None, steps=None, boundaries=None, grid=None, metadata=None, k=None, catalog=None)

Cut *media* into named steps, using whatever else is present.

Returns a [`Segmentation`](#paces.Segmentation) ALWAYS. A segmenter that cannot name the
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
  [`Segmentation`](paces.segmenters.html.md#paces.segmenters.Segmentation)

### paces.suggest_excerpts(document, , units=None, role='performance', overwrite=False)

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
  [`ExcerptResult`](paces.excerpts.html.md#paces.excerpts.ExcerptResult)

### paces.to_document(seg, , doc_id='guide', title='', source=None, domain='generic', lang='en')

Project a segmentation into a fresh step document.

*source* is the media the spans refer into: a URI string, a
[`Source`](paces.model.html.md#paces.model.Source), or a mapping. Hand edits belong on the
returned document, never back on the segmentation.

* **Return type:**
  [`StepDocument`](paces.model.html.md#paces.model.StepDocument)

### paces.validate_document(doc)

Semantic checks beyond the schema. Returns human-readable issues
(empty list = clean); never raises.

Checks: children durations account for the parent’s (`repeat` included),
span sources exist, cue anchors point at real steps, step ids are unique
(id-addressed edits and the regeneration merge both key on them — a
duplicate makes those silently ambiguous), and no raw `float` has
leaked onto the no-floats wire through an `attrs` bag or a `Lock.was`
(both typed `Any`, so the schema alone cannot catch this).

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### Modules

| [`derivation`](paces.derivation.html.md#module-paces.derivation)   | Media derivation: fill <br/><br/>```<br/>``<br/>```<br/><br/>ArtifactRef\`\`s with real clips, gifs and posters.                                     |
|---------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`edits`](paces.edits.html.md#module-paces.edits)             | Document-layer edit protection: typed patches write Locks; regeneration merges without eating edits.                                                 |
| [`excerpts`](paces.excerpts.html.md#module-paces.excerpts)       | Excerpt suggestion: mark the loopable sub-window each step's clip is cut from.                                                                       |
| [`measure`](paces.measure.html.md#module-paces.measure)         | Measure a [`MetricGrid`](paces.model.html.md#paces.model.MetricGrid) from the media itself.                                  |
| [`model`](paces.model.html.md#module-paces.model)             | The paces intermediate representation: the `StepDocument`.                                                                                           |
| [`pose`](paces.pose.html.md#module-paces.pose)               | The pointable `subject_locator`: person boxes from rtmlib pose keypoints.                                                                            |
| [`projection`](paces.projection.html.md#module-paces.projection)   | The projection from analysis result to document: `to_document`.                                                                                      |
| [`render`](paces.render.html.md#module-paces.render)           | Render a [`StepDocument`](paces.model.html.md#paces.model.StepDocument) into learning material.                              |
| [`segmenters`](paces.segmenters.html.md#module-paces.segmenters)   | Segmentation is a seam, not a stage (ADR-0003).                                                                                                      |
| [`tools`](paces.tools.html.md#module-paces.tools)             | Agent-callable tool surface over `paces` — plain functions with JSON-able arguments returning JSON-ready values, deliberately CLI/MCP/HTTP-agnostic. |
