"""The JSON Schema of a :class:`~paces.model.StepDocument`, for other languages.

A TypeScript form, a validator in another service or an agent checking a
document before it renders all need the wire shape without importing pydantic.
The schema is derived from the model (never hand-written), committed as package
data, and a test fails when the two drift; ``paces schema`` writes it.

Synthetic pass/fail fixture documents ship beside it, so another implementation
can test against the same files.

>>> step_document_schema()["title"]
'StepDocument'
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from paces.model import SCHEMA_VERSION, StepDocument

SCHEMA_FILENAME = "step-document.schema.json"
#: The draft the schema is written in (it uses ``prefixItems``).
JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_ID = (
    f"https://thorwhalen.github.io/paces/schema/{SCHEMA_VERSION}/step-document.json"
)


def _strip_null_defaults(node):
    """Drop ``"default": null`` everywhere. Pydantic emits it for every optional
    field, but on the wire an absent field is *absent* (the canonical form omits
    ``None``): a consumer that applies schema defaults (Zod 4's
    ``z.fromJSONSchema``) would otherwise fill ``null`` into every one."""
    if isinstance(node, dict):
        return {
            key: _strip_null_defaults(value)
            for key, value in node.items()
            if not (key == "default" and value is None)
        }
    if isinstance(node, list):
        return [_strip_null_defaults(item) for item in node]
    return node


def step_document_schema() -> dict:
    """The JSON Schema of the document's wire form (camelCase keys; optional
    fields carry no ``default: null``, they are simply optional)."""
    body = _strip_null_defaults(StepDocument.model_json_schema(by_alias=True))
    return {"$schema": JSON_SCHEMA_DRAFT, "$id": SCHEMA_ID, **body}


def dumps_schema(schema: dict | None = None) -> str:
    """The canonical text of the schema file: 2-space indent, trailing newline."""
    schema = step_document_schema() if schema is None else schema
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def packaged_schema_text() -> str:
    """The committed copy of the schema that ships with the package."""
    return (
        resources.files("paces")
        .joinpath("data", "schema", SCHEMA_FILENAME)
        .read_text(encoding="utf-8")
    )


def fixture_paths(kind: str) -> list[Path]:
    """The shipped fixture documents.

    ``"pass"`` validate; ``"fail"`` are rejected by the JSON Schema itself (and
    by pydantic); ``"fail-python"`` break rules a JSON Schema cannot express
    (a positive tempo, an ISO lock time), so only the Python model rejects them.
    """
    if kind not in ("pass", "fail", "fail-python"):
        raise ValueError(f"kind must be 'pass', 'fail' or 'fail-python', got {kind!r}")
    root = Path(str(resources.files("paces").joinpath("data", "fixtures", kind)))
    return sorted(root.glob("*.json"))
