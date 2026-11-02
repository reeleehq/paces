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

| [`TIME_PLACES`](#paces.corrections.TIME_PLACES)            | milliseconds, the wire's resolution.                       |
|-------------------------------------------------------------------------|------------------------------------------------------------|
| [`DFLT_MERGE_TOLERANCE_S`](#paces.corrections.DFLT_MERGE_TOLERANCE_S) | How far a `merge` time may sit from the boundary it means. |
| [`DFLT_MIN_STEP_S`](#paces.corrections.DFLT_MIN_STEP_S)        | The narrowest step a `split` may create.                   |

### Functions

| [`absent`](#paces.corrections.absent)(anchor_t, \*\*meta)          | Absent — "the step placed at `anchor_t` is not in this media".                                                 |
|--------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------|
| [`forbid`](#paces.corrections.forbid)(anchor_t, span, \*\*meta)    | Forbid — "the step at `anchor_t` is not in `span`".                                                            |
| [`from_wire`](#paces.corrections.from_wire)(wire)                     | Parse one wire dict.                                                                                           |
| [`merge`](#paces.corrections.merge)(at_t, \*\*meta)               | Merge — "those are one step": remove the cut nearest `at_t` (K -= 1).                                          |
| [`normalize_corrections`](#paces.corrections.normalize_corrections)(corrections)  | Accept [`Correction`](#paces.corrections.Correction) objects or their wire dicts, in log order.  |
| [`pin`](#paces.corrections.pin)(span, \*[, anchor_t])           | Pin — "the step is HERE": the step covering `anchor_t` (default: the span's midpoint) occupies exactly `span`. |
| [`replay`](#paces.corrections.replay)(seg, corrections, \*[, ...]) | Apply a correction log to a segmentation, in log order.                                                        |
| [`split`](#paces.corrections.split)(at_t, \*\*meta)               | Split — "that is two steps": cut the step covering `at_t` there (K += 1).                                      |
| [`to_wire`](#paces.corrections.to_wire)(correction)                 | A JSON-ready dict: camelCase keys, times as decimal strings, defaults omitted.                                 |

### Classes

| [`Correction`](#paces.corrections.Correction)(\*, verb, anchor_t[, span, ...])   | One thing a human said about a segmentation, keyed by media time.   |
|------------------------------------------------------------------------------------------------|---------------------------------------------------------------------|

### *class* paces.corrections.Correction(, verb, anchor_t, span=None, step_id=None, author='', at='', media_key=None, reason='')

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

One thing a human said about a segmentation, keyed by media time.

`step_id` is for display only and is NEVER the join key: replay finds
its target by `anchor_t`. `media_key` records which rendering of the
media the correction was true of, so a later re-cut can migrate the log.
Times are kept to the millisecond ([`TIME_PLACES`](#paces.corrections.TIME_PLACES)), so the wire form
round-trips exactly.

```pycon
>>> split(0.8550444).anchor_t
0.855
```

#### *property* label *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)*

`'split@95.8'` — how flags name this correction.

### paces.corrections.DFLT_MERGE_TOLERANCE_S *= 1.5*

How far a `merge` time may sit from the boundary it means. A human taps
approximately; the machine finds the cut (`docs/alignment/07 §7.3` step 3
snaps taps within ±1.5 s).

### paces.corrections.DFLT_MIN_STEP_S *= 0.25*

The narrowest step a `split` may create. A split closer than this to an
existing cut is a tap on that cut, not a new step, so it is unmatched.

### paces.corrections.TIME_PLACES *= 3*

milliseconds, the wire’s
resolution. Times are rounded to it at construction, so `to_wire` →
`from_wire` is lossless (`decimal_str` writes exactly this many).

* **Type:**
  Decimal places a correction’s times keep

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

### paces.corrections.replay(seg, corrections, , merge_tolerance_s=1.5, min_step_s=0.25)

Apply a correction log to a segmentation, in log order.

Each correction acts on the result of the ones before it, as the human
made them. Applied ones are flagged `corrected: <verb>@<t>`; one that
finds nothing to act on is flagged `correction-unmatched`, one that
would leave an empty, inverted or overlapping span
`correction-infeasible` (and changes nothing). A `forbid` is judged
against the *final* placement: `satisfied: forbid@<t>`, or
`correction-unenforced` — moving a step elsewhere needs a solver, which
replay is not. A pin that clips a child step out of existence says so
(`correction-clipped`). A last consistency pass flags
(`inconsistent:`) any empty span, any overlap between steps, and any
step edge missing from `boundaries`.

```pycon
>>> seg = Segmentation(steps=(SegStep(id="a", spans=((0.0, 10.0),)),),
...                    boundaries=(0.0, 10.0))
>>> replay(seg, [split(5), split(5.1)]).flags
('corrected: split@5', 'correction-unmatched: split@5.1 (within 0.25 s of a cut)')
```

* **Return type:**
  [`Segmentation`](paces.segmenters.html.md#paces.segmenters.Segmentation)

### paces.corrections.split(at_t, \*\*meta)

Split — “that is two steps”: cut the step covering `at_t` there (K += 1).

* **Return type:**
  [`Correction`](#paces.corrections.Correction)

### paces.corrections.to_wire(correction)

A JSON-ready dict: camelCase keys, times as decimal strings, defaults omitted.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)
