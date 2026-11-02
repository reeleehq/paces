# paces.ask

The ask segmenter’s interaction half: what the machine proposes, and the page
a human answers it on (issue #10, `docs/alignment/07 §7.2–7.4`).

“Ask the user” is first-class, and the gap between a 30-minute chore and a
2-minute confirmation is the *proposal*. So this module is three pure pieces
around one JSON contract:

- [`propose()`](#paces.ask.propose) — what the machine pre-computes from a `Segmentation`:
  a proposed step count K with the evidence for it (the cheapest, highest-value
  question comes first, §7.3 step 1), the candidate cuts, the steps, and the
  snap targets a tap lands on (the cuts, plus the grid’s unit ticks when there
  is a grid: on rhythmic content a boundary is a downbeat).
- [`render_ask_page()`](#paces.ask.render_ask_page) — the default UI: one self-contained static HTML page
  (no server, no framework, no dependency) that asks for K, lets a human tap
  along with the media to add cuts, strike cuts that are wrong and mark steps
  that are not in the media, and exports the answers as JSON.
- [`load_answers()`](#paces.ask.load_answers) — reads those answers back as [`Answers`](#paces.ask.Answers): the
  step count (only when the human touched it), a [`paces.corrections`](paces.corrections.html.md#module-paces.corrections)
  log, and — when the proposal had nothing to correct (the refused state) —
  the boundaries the human tapped, so the answers re-enter the next
  [`segment()`](paces.segmenters.html.md#paces.segmenters.segment) run as constraints or as boundaries.

**The seam is the contract, not a callback.** Any other UI — the real
frontend, a CLI prompt, a notebook widget, or an agent with the proposal in
context (§7.4) — reads the proposal JSON and writes the answers JSON; nothing
here has to change for it.

```pycon
>>> from paces.segmenters import segment
>>> proposal = propose(segment(boundaries=[0, 10, 20, 30]))
>>> proposal["k"], proposal["cuts"]
(3, ['10', '20'])
```

### Module Attributes

| [`CONTRACT_VERSION`](#paces.ask.CONTRACT_VERSION)    | The proposal/answers contract version.                                                                                             |
|----------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------|
| [`DFLT_SNAP_S`](#paces.ask.DFLT_SNAP_S)         | How far a tap may land from a snap target and still snap to it (§7.3 step 3).                                                      |
| [`DFLT_MAX_GRID_TICKS`](#paces.ask.DFLT_MAX_GRID_TICKS) | Above this many grid ticks the page snaps to cuts only — a dense tick list would make every tap snap somewhere and bloat the page. |

### Functions

| [`load_answers`](#paces.ask.load_answers)(answers)                         | [`Answers`](#paces.ask.Answers) from the page's answers JSON.   |
|------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| [`propose`](#paces.ask.propose)(seg, \*[, media, title, snap_s, ...]) | What the machine pre-computes for a human to confirm — a JSON-ready dict.                |
| [`render_ask_page`](#paces.ask.render_ask_page)(proposal, \*[, author])       | The default `ask` UI: a self-contained static HTML page.                                 |

### Classes

| [`Answers`](#paces.ask.Answers)(k[, corrections, boundaries])   | What a human answered on the ask page, ready for the next run.   |
|------------------------------------------------------------------------------------------|------------------------------------------------------------------|

### *class* paces.ask.Answers(k, corrections=(), boundaries=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What a human answered on the ask page, ready for the next run.

`k` is the step count they gave (`None` unless they touched it);
`corrections` is a [`paces.corrections`](paces.corrections.html.md#module-paces.corrections) log; `boundaries` holds
the cuts they tapped when the proposal had none to correct (the refused
state), from 0 to the media’s end — `None` otherwise.

### paces.ask.CONTRACT_VERSION *= 1*

The proposal/answers contract version. Both documents carry it; a reader
refuses any other, so a page and a loader of different ages fail loudly.

### paces.ask.DFLT_MAX_GRID_TICKS *= 2000*

Above this many grid ticks the page snaps to cuts only — a dense tick list
would make every tap snap somewhere and bloat the page.

### paces.ask.DFLT_SNAP_S *= 1.5*

How far a tap may land from a snap target and still snap to it (§7.3 step
3). It is the merge tolerance on purpose: both absorb the same thing, the
imprecision of a human tapping along, so one number serves both.

### paces.ask.load_answers(answers)

[`Answers`](#paces.ask.Answers) from the page’s answers JSON.

Validated here, so a bad file fails now and not halfway through a re-run:
the kind, the contract `version` (required), `k`, every correction,
and the boundaries.

```pycon
>>> load_answers({"kind": "PacesAskAnswers", "version": 1, "k": 4,
...               "corrections": [{"verb": "split", "anchorT": "15"}]})
Answers(k=4, corrections=(Correction(verb='split', anchor_t=15.0, span=None, step_id=None, author='', at='', media_key=None, reason=''),), boundaries=None)
```

* **Return type:**
  [`Answers`](#paces.ask.Answers)

### paces.ask.propose(seg, , media=None, title='', snap_s=1.5, min_step_s=0.25, max_grid_ticks=2000)

What the machine pre-computes for a human to confirm — a JSON-ready dict.

`k` is the proposed step count (`None` when the segmentation has
nothing to count) and `k_evidence` says where it came from, so the human
confirms a number they can see the reasoning for. Times are decimal
strings, as everywhere on paces’ wire; cuts that are the same millisecond
are one cut. `minStepS` is the narrowest step a split may make
([`DFLT_MIN_STEP_S`](paces.corrections.html.md#paces.corrections.DFLT_MIN_STEP_S)): the page ignores a tap
closer than that to a cut, as replay would.

```pycon
>>> propose(Segmentation(boundaries=(0, 10, 10.0001, 20)))["cuts"]
['10']
```

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### paces.ask.render_ask_page(proposal, , author='')

The default `ask` UI: a self-contained static HTML page.

It posts nothing. The human’s answers autosave in the browser (so a
closed tab loses nothing) and leave as a downloaded `answers.json` or
copied text, which [`load_answers()`](#paces.ask.load_answers) reads. `author` is stamped on
every correction the page emits.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
