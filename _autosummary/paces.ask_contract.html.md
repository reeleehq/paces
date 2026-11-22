# paces.ask_contract

The ask contract as types: the proposal a machine writes and the answers a human returns.

[`paces.ask`](paces.ask.html.md#module-paces.ask) produces and reads these two JSON documents (`docs/alignment/07
§7.4`), and every other UI (the real frontend, a CLI prompt, an agent) speaks
the same two. They are declared here as pydantic models, so the shape is
written once, `load_answers` validates against it, and the JSON Schema a
TypeScript side needs comes from [`contract_schemas()`](#paces.ask_contract.contract_schemas) and not from a second
hand-written copy.

Field names are camelCase on the wire, as the page reads them. Times are
decimal strings, as everywhere on paces’ wire.

```pycon
>>> sorted(contract_schemas())
['answers', 'proposal']
```

### Module Attributes

| [`CONTRACT_VERSION`](#paces.ask_contract.CONTRACT_VERSION)   | The proposal/answers contract version.   |
|---------------------------------------------------------------------|------------------------------------------|

### Functions

| [`contract_schemas`](#paces.ask_contract.contract_schemas)()   | The JSON Schema of both documents, for a UI written in another language.   |
|-----------------------------------------------------------------------|----------------------------------------------------------------------------|

### Classes

| [`AnswersDocument`](#paces.ask_contract.AnswersDocument)(\*[, kind, k, corrections, ...])   | What the page exports ([`paces.ask.load_answers()`](paces.ask.html.md#paces.ask.load_answers) reads it).             |
|-----------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| [`Proposal`](#paces.ask_contract.Proposal)(\*[, kind, version, answersKind, ...])    | What the machine pre-computes for a human to confirm ([`paces.ask.propose()`](paces.ask.html.md#paces.ask.propose)). |
| [`ProposedStep`](#paces.ask_contract.ProposedStep)(\*, id[, name])                       | A step as the machine found it: its spans, as `[start, end]` time strings.                                                                     |
| [`Snap`](#paces.ask_contract.Snap)(\*, windowS, targets)                         | Where a tap lands: within `window_s` of a target (a cut, or a grid tick).                                                                      |

### *class* paces.ask_contract.AnswersDocument(, kind='', version, k=None, corrections=[], boundaries=None, proposal=None)

Bases: `_Wire`

What the page exports ([`paces.ask.load_answers()`](paces.ask.html.md#paces.ask.load_answers) reads it).

`corrections` is a [`paces.corrections`](paces.corrections.html.md#module-paces.corrections) log, each entry validated by
[`paces.corrections.normalize_corrections()`](paces.corrections.html.md#paces.corrections.normalize_corrections). `boundaries` holds the
cuts tapped when the proposal had none to correct, from 0 to the media’s
end, as time strings or seconds.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'frozen': True, 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### paces.ask_contract.CONTRACT_VERSION *= 1*

The proposal/answers contract version. Both documents carry it; a reader
refuses any other, so a page and a loader of different ages fail loudly.

### *class* paces.ask_contract.Proposal(, kind='PacesAskProposal', version=1, answersKind='PacesAskAnswers', title='', media=None, method=None, flags=[], k, kEvidence, extent, cuts, cutMeets=[], steps, minStepS, snap)

Bases: `_Wire`

What the machine pre-computes for a human to confirm ([`paces.ask.propose()`](paces.ask.html.md#paces.ask.propose)).

`cut_meets` is aligned with `cuts`: `True` where one step ends and
another begins (so striking the cut merges them), `False` at the edge of a
gap between steps, where there is nothing to merge. Empty (an older proposal)
reads as all `True`.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'frozen': True, 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.ask_contract.ProposedStep(, id, name=None, spans)

Bases: `_Wire`

A step as the machine found it: its spans, as `[start, end]` time strings.

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'frozen': True, 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### *class* paces.ask_contract.Snap(, windowS, targets)

Bases: `_Wire`

Where a tap lands: within `window_s` of a target (a cut, or a grid tick).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'frozen': True, 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### paces.ask_contract.contract_schemas()

The JSON Schema of both documents, for a UI written in another language.

```pycon
>>> contract_schemas()["proposal"]["properties"]["kind"]["const"]
'PacesAskProposal'
```

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]
