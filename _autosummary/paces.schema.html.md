# paces.schema

The JSON Schema of a [`StepDocument`](paces.model.html.md#paces.model.StepDocument), for other languages.

A TypeScript form, a validator in another service or an agent checking a
document before it renders all need the wire shape without importing pydantic.
The schema is derived from the model (never hand-written), committed as package
data, and a test fails when the two drift; `paces schema` writes it.

Synthetic pass/fail fixture documents ship beside it, so another implementation
can test against the same files.

```pycon
>>> step_document_schema()["title"]
'StepDocument'
```

### Module Attributes

| [`JSON_SCHEMA_DRAFT`](#paces.schema.JSON_SCHEMA_DRAFT)   | The draft the schema is written in (it uses `prefixItems`).   |
|----------------------------------------------------------------------|---------------------------------------------------------------|

### Functions

| [`dumps_schema`](#paces.schema.dumps_schema)([schema])   | The canonical text of the schema file: 2-space indent, trailing newline.                                                          |
|---------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| [`fixture_paths`](#paces.schema.fixture_paths)(kind)      | The shipped fixture documents.                                                                                                    |
| [`packaged_schema_text`](#paces.schema.packaged_schema_text)()   | The committed copy of the schema that ships with the package.                                                                     |
| [`step_document_schema`](#paces.schema.step_document_schema)()   | The JSON Schema of the document's wire form (camelCase keys; optional fields carry no `default: null`, they are simply optional). |

### paces.schema.JSON_SCHEMA_DRAFT *= 'https://json-schema.org/draft/2020-12/schema'*

The draft the schema is written in (it uses `prefixItems`).

### paces.schema.dumps_schema(schema=None)

The canonical text of the schema file: 2-space indent, trailing newline.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### paces.schema.fixture_paths(kind)

The shipped fixture documents.

`"pass"` validate; `"fail"` are rejected by the JSON Schema itself (and
by pydantic); `"fail-python"` break rules a JSON Schema cannot express
(a positive tempo, an ISO lock time), so only the Python model rejects them.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)]

### paces.schema.packaged_schema_text()

The committed copy of the schema that ships with the package.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### paces.schema.step_document_schema()

The JSON Schema of the document’s wire form (camelCase keys; optional
fields carry no `default: null`, they are simply optional).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)
