# paces.corrections

Human corrections as a replayable log of constraints (issue #10, ADR-0003 §4).

“Ask the user” is a first-class segmenter, and this module is the half of it
that decides how an answer *survives a re-run*: corrections re-enter as
constraints for the next run, never as a patch on an output that the next run
would overwrite (`docs/alignment/07 §7.5`).

Two rules from that section shape everything here:

- **Five verbs, constraints only.** `pin` (“it is HERE”), `forbid` (“it is
  not there”), `absent` (“not in this media”), `split` (“that is two
  steps”) and `merge` (“those are one step”). `rename` is deliberately not
  a verb: a name is content and belongs in the document layer, which is what
  lets the log be replayed against a completely different segmenter.
- **Keyed by time, not by step id.** `anchor_t` is a point on the media clock;
  a step id invented by one run may mean something else in the next, a time
  does not.

How the log is honoured is a seam on the segmenter, not here: a capability
that lists `"corrections"` in `reads` receives the log as an input and
treats it as solver constraints (the alignment engine, issue #9, will). For
every other segmenter, `segment()` falls back to [`replay()`](#paces.corrections.replay), which
applies the log to the result in order. A correction is \*\*never silently
dropped\*\*: one that finds nothing to act on, or that would make the result
infeasible, is reported in `Segmentation.flags`.

```pycon
>>> from paces.segmenters import segment
>>> log = [split(15.0), merge(20.0)]
>>> seg = segment(boundaries=[0, 10, 20, 30], corrections=log)
>>> seg.boundaries
(0.0, 10.0, 15.0, 30.0)
>>> [s.spans for s in seg.steps]
[((0.0, 10.0),), ((10.0, 15.0),), ((15.0, 30.0),)]
```

### Module Attributes

| [`DFLT_MERGE_TOLERANCE_S`](#paces.corrections.DFLT_MERGE_TOLERANCE_S)   | How far a `merge` time may sit from the boundary it means.   |
|---------------------------------------------------------------------------|--------------------------------------------------------------|
| [`DFLT_MIN_STEP_S`](#paces.corrections.DFLT_MIN_STEP_S)          | The narrowest step a `split` may create.                     |

### Functions

| [`absent`](#paces.corrections.absent)(anchor_t, \*\*meta)                      | Absent — "the step placed at `anchor_t` is not in this media".                                                                           |
|--------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| [`forbid`](#paces.corrections.forbid)(anchor_t, span, \*\*meta)                | Forbid — "the step at `anchor_t` is not in `span`".                                                                                      |
| [`from_wire`](#paces.corrections.from_wire)(wire)                                 | Parse one wire dict.                                                                                                                     |
| [`merge`](#paces.corrections.merge)(at_t, \*\*meta)                           | Merge — "those are one step": remove the cut nearest `at_t` (K -= 1).                                                                    |
| [`migrate_corrections`](#paces.corrections.migrate_corrections)(corrections, \*, cuts, ...) | Move the corrections made against `from_media_key` onto the rendering `to_media_key`, which is that media with `cuts` removed.           |
| [`normalize_corrections`](#paces.corrections.normalize_corrections)(corrections)              | Accept [`Correction`](#paces.corrections.Correction) objects or their wire dicts, in log order.                            |
| [`pin`](#paces.corrections.pin)(span, \*[, anchor_t])                       | Pin — "the step is HERE": the step covering `anchor_t` (default: the span's midpoint) occupies exactly `span`.                           |
| [`replay`](#paces.corrections.replay)(seg, corrections, \*[, ...])             | Apply a correction log to a segmentation, in log order.                                                                                  |
| [`split`](#paces.corrections.split)(at_t, \*\*meta)                           | Split — "that is two steps": cut the step covering `at_t` there (K += 1).                                                                |
| [`stale_corrections`](#paces.corrections.stale_corrections)(corrections, media_key)       | `(current, flags)`: the log without the corrections made against another rendering of the media, and a `correction-stale` flag for each. |
| [`to_wire`](#paces.corrections.to_wire)(correction)                             | A JSON-ready dict: camelCase keys, times as decimal strings, defaults omitted.                                                           |

### Classes

| [`Correction`](#paces.corrections.Correction)(\*, verb, anchor_t[, span, ...])      | One thing a human said about a segmentation, keyed by media time.                                                         |
|---------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| [`CorrectionMigration`](#paces.corrections.CorrectionMigration)(corrections[, dropped, ...]) | What [`migrate_corrections()`](#paces.corrections.migrate_corrections) did: the new log, and what it could not move. |

### *class* paces.corrections.Correction(, verb, anchor_t, span=None, step_id=None, author='', at='', media_key=None, reason='', migrated_from=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

One thing a human said about a segmentation, keyed by media time.

`step_id` is for display only and is NEVER the join key: replay finds
its target by `anchor_t`. `media_key` records which rendering of the
media the correction was true of, so a later re-cut can migrate the log
([`migrate_corrections()`](#paces.corrections.migrate_corrections), which sets `migrated_from`), and a replay
told another key skips it as stale ([`stale_corrections()`](#paces.corrections.stale_corrections)).
Times are kept to the millisecond (`TIME_PLACES`), so the wire form
round-trips exactly.

```pycon
>>> split(0.8550444).anchor_t
0.855
```

#### *property* label *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)*

`'split@95.8'` — how flags name this correction.

### *class* paces.corrections.CorrectionMigration(corrections, dropped=(), moved=0, untagged=0)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What [`migrate_corrections()`](#paces.corrections.migrate_corrections) did: the new log, and what it could not move.

#### *property* flags *: [tuple](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), ...]*

One `correction-unmigrated` line per dropped correction, saying why;
and `correction-migration-empty` when nothing was made against the old
rendering, so a no-op is never mistaken for a migration.

### paces.corrections.DFLT_MERGE_TOLERANCE_S *= 1.5*

How far a `merge` time may sit from the boundary it means. A human taps
approximately; the machine finds the cut (`docs/alignment/07 §7.3` step 3
snaps taps within ±1.5 s).

### paces.corrections.DFLT_MIN_STEP_S *= 0.25*

The narrowest step a `split` may create. A split closer than this to an
existing cut is a tap on that cut, not a new step, so it is unmatched.

### paces.corrections.absent(anchor_t, \*\*meta)

Absent — “the step placed at `anchor_t` is not in this media”.

* **Return type:**
  [`Correction`](#paces.corrections.Correction)

### paces.corrections.forbid(anchor_t, span, \*\*meta)

Forbid — “the step at `anchor_t` is not in `span`”.

* **Return type:**
  [`Correction`](#paces.corrections.Correction)

### paces.corrections.from_wire(wire)

Parse one wire dict. Unknown or missing keys raise `ValueError` (a typo
must not vanish, and a correction without a verb or a time is not one).

```pycon
>>> from_wire({"verb": "split", "anchorT": "95.8"}) == split(95.8)
True
```

* **Return type:**
  [`Correction`](#paces.corrections.Correction)

### paces.corrections.merge(at_t, \*\*meta)

Merge — “those are one step”: remove the cut nearest `at_t` (K -= 1).

* **Return type:**
  [`Correction`](#paces.corrections.Correction)

### paces.corrections.migrate_corrections(corrections, , cuts, from_media_key, to_media_key, remap=None)

Move the corrections made against `from_media_key` onto the rendering
`to_media_key`, which is that media with `cuts` removed.

`cuts` are `(start, end)` pairs or `{"start", "end"}` mappings on the
old timeline (`mixing`’s cut list). Each moved correction’s times go
through `remap` (default: `mixing.transcript.formats.remap_time_after_cuts`,
the fleet’s one rule), its `media_key` becomes `to_media_key` and
`migrated_from` records the old one. A correction whose anchor was cut
out, or whose span the cuts remove or collapse, has nothing left to say
about the new rendering: it is returned in `dropped` with the reason,
never silently lost. Corrections made against any other rendering, or with
no `media_key`, are kept unchanged, in log order.

```pycon
>>> remap = lambda t, cuts: t - sum(c["end"] - c["start"] for c in cuts if c["end"] <= t)
>>> moved = migrate_corrections([split(30, media_key="v1"), merge(5, media_key="v1")],
...                             cuts=[(10, 20)], from_media_key="v1", to_media_key="v2",
...                             remap=remap)
>>> [(c.label, c.media_key, c.migrated_from) for c in moved.corrections]
[('split@20', 'v2', 'v1'), ('merge@5', 'v2', 'v1')]
```

* **Return type:**
  [`CorrectionMigration`](#paces.corrections.CorrectionMigration)

### paces.corrections.normalize_corrections(corrections)

Accept [`Correction`](#paces.corrections.Correction) objects or their wire dicts, in log order.

A log is a *sequence*: one correction passed bare (a mapping) is refused
rather than iterated over its keys.

```pycon
>>> normalize_corrections({"verb": "split", "anchorT": "1"})
Traceback (most recent call last):
...
ValueError: corrections must be a list of corrections, got a single mapping; wrap it in a list
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`Correction`](#paces.corrections.Correction), [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)]

### paces.corrections.pin(span, , anchor_t=None, \*\*meta)

Pin — “the step is HERE”: the step covering `anchor_t` (default: the span’s
midpoint) occupies exactly `span`.

* **Return type:**
  [`Correction`](#paces.corrections.Correction)

### paces.corrections.replay(seg, corrections, , merge_tolerance_s=1.5, min_step_s=0.25, media_key=None)

Apply a correction log to a segmentation, in log order.

`media_key` names the rendering `seg` was made from: a correction made
against another one is skipped and flagged `correction-stale`
([`stale_corrections()`](#paces.corrections.stale_corrections)). `None` (default) applies every correction.

Each correction acts on the result of the ones before it, as the human
made them. Applied ones are flagged `corrected: <verb>@<t>`; one that
finds nothing to act on is flagged `correction-unmatched`, one that
would leave an empty, inverted or overlapping span
`correction-infeasible` (and changes nothing). A `forbid` is judged
against the *final* placement: `satisfied: forbid@<t>`, or
`correction-unenforced` — moving a step elsewhere needs a solver, which
replay is not. A pin that clips a child step out of existence says so
(`correction-clipped`). Checking the result is not replay’s job:
[`paces.segmenters.segment()`](paces.segmenters.html.md#paces.segmenters.segment) runs
[`inconsistencies()`](paces.segmentation.html.md#paces.segmentation.inconsistencies) on every segmentation. A log
in which no correction edits the cut set leaves `boundaries` exactly as
given (duplicates included); once one does, they are rebuilt from it.

```pycon
>>> seg = Segmentation(steps=(SegStep(id="a", spans=((0.0, 10.0),)),),
...                    boundaries=(0.0, 10.0))
>>> replay(seg, [split(5), split(5.1)]).flags
('corrected: split@5', 'correction-unmatched: split@5.1 (within 0.25 s of a cut)')
```

* **Return type:**
  [`Segmentation`](paces.segmentation.html.md#paces.segmentation.Segmentation)

### paces.corrections.split(at_t, \*\*meta)

Split — “that is two steps”: cut the step covering `at_t` there (K += 1).

* **Return type:**
  [`Correction`](#paces.corrections.Correction)

### paces.corrections.stale_corrections(corrections, media_key)

`(current, flags)`: the log without the corrections made against
another rendering of the media, and a `correction-stale` flag for each.

A correction recorded against another `media_key` is about different
times (a re-cut moved everything after its cut), so replaying it would act
on the wrong moment. It is skipped and said, never dropped silently; once
[`migrate_corrections()`](#paces.corrections.migrate_corrections) moves it to this rendering it applies again. A
correction with no `media_key` (a hand-written log), or a call with
`media_key=None` (the rendering is not known), is current.

```pycon
>>> log = [split(5, media_key="cut-a"), split(9, media_key="cut-b"), merge(20)]
>>> current, flags = stale_corrections(log, "cut-b")
>>> [c.label for c in current]
['split@9', 'merge@20']
>>> flags
("correction-stale: split@5 (made against media 'cut-a', not 'cut-b'; migrate it with migrate_corrections)",)
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`Correction`](#paces.corrections.Correction), [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)], [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)]]

### paces.corrections.to_wire(correction)

A JSON-ready dict: camelCase keys, times as decimal strings, defaults omitted.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)
