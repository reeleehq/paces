"""JSON Schema export: the committed file tracks the model; fixtures hold."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from paces import schema as schema_module
from paces.model import StepDocument, dumps_document, loads_document
from paces.tools import schema as schema_tool


def test_committed_schema_matches_the_model():
    assert schema_module.packaged_schema_text() == schema_module.dumps_schema(), (
        "paces/data/schema/step-document.schema.json is stale; regenerate with "
        "`python -m paces schema --output paces/data/schema/step-document.schema.json`"
    )


def test_schema_uses_the_wire_names():
    props = schema_module.step_document_schema()["properties"]
    assert "schemaVersion" in props and "schema_version" not in props


def test_schema_tool_returns_text_and_writes_a_file(tmp_path):
    out = tmp_path / "s.json"
    assert schema_tool(output=str(out)) == str(out)
    assert out.read_text(encoding="utf-8") == schema_tool()
    assert json.loads(out.read_text(encoding="utf-8"))["title"] == "StepDocument"


def test_cli_schema_verb(tmp_path):
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "paces", "schema"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["title"] == "StepDocument"


def test_fixture_sets_are_not_empty():
    assert len(schema_module.fixture_paths("pass")) >= 3
    assert len(schema_module.fixture_paths("fail")) >= 5


@pytest.mark.parametrize(
    "path", schema_module.fixture_paths("pass"), ids=lambda p: p.stem
)
def test_pass_fixtures_validate_and_round_trip(path):
    doc = loads_document(path.read_text(encoding="utf-8"))
    assert loads_document(dumps_document(doc)) == doc


@pytest.mark.parametrize(
    "path", schema_module.fixture_paths("fail"), ids=lambda p: p.stem
)
def test_fail_fixtures_are_rejected(path):
    with pytest.raises(ValidationError):
        StepDocument.model_validate_json(path.read_text(encoding="utf-8"))


def test_bad_fixture_kind_is_an_error():
    with pytest.raises(ValueError):
        schema_module.fixture_paths("maybe")
