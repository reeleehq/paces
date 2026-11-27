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

from paces.model import StepDocument

SCHEMA_FILENAME = "step-document.schema.json"


def step_document_schema() -> dict:
    """The JSON Schema of the document's wire form (camelCase keys)."""
    return StepDocument.model_json_schema(by_alias=True)


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
    """The shipped fixture documents: ``kind`` is ``"pass"`` or ``"fail"``."""
    if kind not in ("pass", "fail"):
        raise ValueError(f"kind must be 'pass' or 'fail', got {kind!r}")
    root = Path(str(resources.files("paces").joinpath("data", "fixtures", kind)))
    return sorted(root.glob("*.json"))
