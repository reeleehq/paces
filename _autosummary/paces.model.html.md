# paces.model

The paces intermediate representation: the `StepDocument`.

This is the contract between *analysis* (segment media into steps) and
*rendering* (emit a practice page, a PDF, a deck). Renderers depend on this
document and never on the analyser — the parse → AST → render split the whole
package is organised around (`docs/03-design-brief.md §1`).

Design decisions, each argued in `docs/07-annotation-model.md`:

- **A step has SEVERAL source spans.** The at-tempo run-through and the slow
  explanation are the same step seen twice; `Step.spans` is a list and a
  one-span model is wrong on day one.
- **Duration is domain-specific.** A dance counts 8-counts, a workout counts
  reps; `Measure(value, unit)` stores the unit the learner actually counts,
  and wall-clock seconds are *derived* via the optional `MetricGrid`.
- **No floats on the wire.** Times are decimal strings (`"231.3"`) — exact,
  diffable as one token. Absolute positions are computed by [`resolve()`](#paces.model.resolve),
  never stored.
- **camelCase on the wire, snake_case in Python** (the walkthru convention).
- **Uncertainty is content.** The POC’s `note` fields are promoted to
  [`OpenQuestion`](#paces.model.OpenQuestion); human decisions regeneration must not overwrite are
  [`Lock`](#paces.model.Lock) records.

### Module Attributes

| [`Slug`](#paces.model.Slug)    | Git-readable stable identifier — deliberately NOT a uuid4.                  |
|----------------------------------------------------------|-----------------------------------------------------------------------------|
| [`Decimal`](#paces.model.Decimal) | Exact decimal number as a string ("231.3") — no float representation drift. |

### Functions

| [`decimal_str`](#paces.model.decimal_str)(value, \*[, places])   | A clean wire decimal from a number ('95.78', never '95.78000000001').                        |
|-------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------|
| [`dumps_document`](#paces.model.dumps_document)(doc)                | Serialise a document to its canonical wire form.                                             |
| [`loads_document`](#paces.model.loads_document)(text)               | Parse a document from its wire form (accepts camelCase or snake_case).                       |
| [`resolve`](#paces.model.resolve)(doc)                       | Compute absolute metric offsets (and wall-clock times, when the grid allows) for every step. |
| [`seconds_per_unit`](#paces.model.seconds_per_unit)(grid)             | Seconds one domain unit lasts under *grid*, or None without a tempo.                         |
| [`validate_document`](#paces.model.validate_document)(doc)             | Semantic checks beyond the schema.                                                           |

### Classes

| [`Anchor`](#paces.model.Anchor)(\*, step[, offset])                         | Where a cue attaches: a step, plus an optional relative offset in the domain unit.                                                                                                                                                                                             |
|-----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`ArtifactRef`](#paces.model.ArtifactRef)(\*, role, uri[, assetId, mime, ...])   | WHAT a derived file is, never HOW it was made — the recipe lives in the evidence layer (`paces.evidence`, tier `derivation`) and in the committed span-address-keyed `<stem>.recipes.json` sidecar (ADR-0005 §3), which stay in step: both are keyed by the same span address. |
| [`Cue`](#paces.model.Cue)(\*, id, kind, text, anchor[, duration, ...])   | A landmark the learner can hear or watch for (a lyric, a count, ...).                                                                                                                                                                                                          |
| [`Lock`](#paces.model.Lock)(\*, path, by, at[, was, reason])              | A human (or approved-AI) decision that regeneration MUST NOT overwrite.                                                                                                                                                                                                        |
| [`Measure`](#paces.model.Measure)(\*, value, unit)                           | A duration in the DOMAIN's own unit — never seconds unless the domain's unit is seconds.                                                                                                                                                                                       |
| [`MetricGrid`](#paces.model.MetricGrid)(\*, unit[, subdivisions, ...])          | How the domain unit relates to wall-clock time, when it does at all.                                                                                                                                                                                                           |
| [`OpenQuestion`](#paces.model.OpenQuestion)(\*, id, text[, status, ...])          | The POC's `note` fields, promoted: uncertainty and its resolution are first-class content, not scratch.                                                                                                                                                                        |
| [`Origin`](#paces.model.Origin)(\*[, annotationId, valueDigest, ...])       | Back-reference into the evidence layer: why this node says what it says, and what a regeneration may replace.                                                                                                                                                                  |
| [`Source`](#paces.model.Source)(\*, id, kind, uri[, assetId, ...])          | One input the document's spans refer into (a video, a notes doc, ...).                                                                                                                                                                                                         |
| [`SourceSpan`](#paces.model.SourceSpan)(\*, source[, role, end, excerpt, ...])  | ONE step's presence in ONE source, in ONE role.                                                                                                                                                                                                                                |
| [`Step`](#paces.model.Step)(\*, id, name, duration[, description, ...])   | One named piece of the routine — the unit a learner practises.                                                                                                                                                                                                                 |
| [`StepDocument`](#paces.model.StepDocument)(\*[, kind, schemaVersion, lang, ...]) | The committed, hand-editable, git-diffable step document — the AST.                                                                                                                                                                                                            |

### *class* paces.model.Anchor(, step, offset=None)

Bases: `_Base`

Where a cue attaches: a step, plus an optional relative offset in the
domain unit. NEVER an absolute time.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.model.ArtifactRef(\*, role, uri, assetId=None, mime=None, width=None, height=None, durationS=None, derivedFrom=None, attrs=<factory>)

Bases: `_Base`

WHAT a derived file is, never HOW it was made — the recipe lives in the
evidence layer (`paces.evidence`, tier `derivation`) and in the
committed span-address-keyed `<stem>.recipes.json` sidecar (ADR-0005 §3),
which stay in step: both are keyed by the same span address.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.model.Cue(\*, id, kind, text, anchor, duration=None, source=None, atS=None, attrs=<factory>)

Bases: `_Base`

A landmark the learner can hear or watch for (a lyric, a count, …).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### paces.model.Decimal

Exact decimal number as a string (“231.3”) — no float representation drift.

alias of `Annotated`[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), FieldInfo(annotation=NoneType, required=True, metadata=[_PydanticGeneralMetadata(pattern=’^-?\\d+(\\.\\d+)?$’)])]

### *class* paces.model.Lock(, path, by, at, was=None, reason=None)

Bases: `_Base`

A human (or approved-AI) decision that regeneration MUST NOT overwrite.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.model.Measure(, value, unit)

Bases: `_Base`

A duration in the DOMAIN’s own unit — never seconds unless the domain’s
unit is seconds.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.model.MetricGrid(, unit, subdivisions=1, tempoBpm=None, origin=None, originSource=None)

Bases: `_Base`

How the domain unit relates to wall-clock time, when it does at all.

Optional by design: a “reps” domain has no grid; a dance routine does —
and the grid is what drives the metronome and [`resolve()`](#paces.model.resolve).

A non-positive tempo or subdivision count is unrepresentable, not merely
discouraged: a zero tempo makes every duration infinite and every
`seconds_per_unit` division a crash, so “tempo unknown” is spelled
`tempo_bpm=None`, never `"0"`.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.model.OpenQuestion(\*, id, text, status='open', resolution=None, evidence=<factory>)

Bases: `_Base`

The POC’s `note` fields, promoted: uncertainty and its resolution are
first-class content, not scratch.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.model.Origin(, annotationId=None, valueDigest=None, generatedBy=None, confidence=None)

Bases: `_Base`

Back-reference into the evidence layer: why this node says what it says,
and what a regeneration may replace.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### paces.model.Slug

Git-readable stable identifier — deliberately NOT a uuid4.

alias of `Annotated`[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), FieldInfo(annotation=NoneType, required=True, metadata=[_PydanticGeneralMetadata(pattern=’^[a-z0-9][a-z0-9._-]\*$’)])]

### *class* paces.model.Source(\*, id, kind, uri, assetId=None, durationS=None, title=None, attribution=None, rights=None, attrs=<factory>)

Bases: `_Base`

One input the document’s spans refer into (a video, a notes doc, …).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.model.SourceSpan(\*, source, role='performance', start, end=None, excerpt=None, label=None, caption=None, confidence=None, attrs=<factory>)

Bases: `_Base`

ONE step’s presence in ONE source, in ONE role. A step has a LIST of
these — several roles is the norm, not the exception.

`end=None` means “starts here, extent not recorded” (a deep link is a
point of entry, not an interval; recording an end it does not know would
be invention, not data).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.model.Step(\*, id, name, duration, description='', spans=<factory>, artifacts=<factory>, steps=<factory>, repeat=1, optional=False, variantOf=None, tags=<factory>, questions=<factory>, origin=None, locks=<factory>, attrs=<factory>)

Bases: `_Base`

One named piece of the routine — the unit a learner practises.

A step is a step: sub-steps are `Step``s in ``steps`. `repeat` says the
children cycle N times (the POC’s block 9 is `repeat=4` over two
sub-steps — structure, where the original hand-wrote a display override).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.model.StepDocument(\*, kind='StepDocument', schemaVersion='0.1.0', id, title, lang='en', domain='generic', metric=None, sources=<factory>, steps=<factory>, cues=<factory>, questions=<factory>, credits=None, locks=<factory>, attrs=<factory>)

Bases: `_Base`

The committed, hand-editable, git-diffable step document — the AST.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### paces.model.decimal_str(value, , places=3)

A clean wire decimal from a number (‘95.78’, never ‘95.78000000001’).

The one shared serialisation helper for computed values entering the
document’s no-floats wire format.

```pycon
>>> decimal_str(72.60000000000001, places=3)
'72.6'
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### paces.model.dumps_document(doc)

Serialise a document to its canonical wire form.

camelCase keys in declaration order, 2-space indent, UTF-8 readable
(`ensure_ascii=False` equivalent), trailing newline.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### paces.model.loads_document(text)

Parse a document from its wire form (accepts camelCase or snake_case).

* **Return type:**
  [`StepDocument`](#paces.model.StepDocument)

### paces.model.resolve(doc)

Compute absolute metric offsets (and wall-clock times, when the grid
allows) for every step. Pure; the analogue of walkthru’s
`resolve_timeline`.

Returns a JSON-able dict: `{"unit", "seconds_per_unit", "origin_s",
"total_units", "steps": [{"id", "name", "offset", "duration", "start_s",
"end_s", "repeat", "children": [...]}, ...]}`. Times are floats — this is
a computed view, not the stored document.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### paces.model.seconds_per_unit(grid)

Seconds one domain unit lasts under *grid*, or None without a tempo.

```pycon
>>> seconds_per_unit(MetricGrid(unit='eight', subdivisions=8, tempo_bpm='129.2'))
3.7151702786377707
```

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### paces.model.validate_document(doc)

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
