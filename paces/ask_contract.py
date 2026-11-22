"""The ask contract as types: the proposal a machine writes and the answers a human returns.

:mod:`paces.ask` produces and reads these two JSON documents (``docs/alignment/07
§7.4``), and every other UI (the real frontend, a CLI prompt, an agent) speaks
the same two. They are declared here as pydantic models, so the shape is
written once, ``load_answers`` validates against it, and the JSON Schema a
TypeScript side needs comes from :func:`contract_schemas` and not from a second
hand-written copy.

Field names are camelCase on the wire, as the page reads them. Times are
decimal strings, as everywhere on paces' wire.

>>> sorted(contract_schemas())
['answers', 'proposal']
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

PROPOSAL_KIND = "PacesAskProposal"
ANSWERS_KIND = "PacesAskAnswers"
#: The proposal/answers contract version. Both documents carry it; a reader
#: refuses any other, so a page and a loader of different ages fail loudly.
CONTRACT_VERSION = 1


class _Wire(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, frozen=True, extra="forbid"
    )


class ProposedStep(_Wire):
    """A step as the machine found it: its spans, as ``[start, end]`` time strings."""

    id: str
    name: str | None = None
    spans: list[tuple[str, str]]


class Snap(_Wire):
    """Where a tap lands: within ``window_s`` of a target (a cut, or a grid tick)."""

    window_s: str
    targets: list[str]


class Proposal(_Wire):
    """What the machine pre-computes for a human to confirm (:func:`paces.ask.propose`)."""

    kind: Literal["PacesAskProposal"] = PROPOSAL_KIND
    version: Literal[1] = CONTRACT_VERSION
    answers_kind: Literal["PacesAskAnswers"] = ANSWERS_KIND
    title: str = ""
    media: str | None = None
    method: str | None = None
    flags: list[str] = []
    k: int | None
    k_evidence: str
    extent: tuple[str, str] | None
    cuts: list[str]
    steps: list[ProposedStep]
    min_step_s: str
    snap: Snap


class AnswersDocument(_Wire):
    """What the page exports (:func:`paces.ask.load_answers` reads it).

    ``corrections`` is a :mod:`paces.corrections` log, each entry validated by
    :func:`paces.corrections.normalize_corrections`. ``boundaries`` holds the
    cuts tapped when the proposal had none to correct, from 0 to the media's
    end, as time strings or seconds.
    """

    kind: str = Field("", validate_default=True)
    version: int
    k: int | None = None
    corrections: list[dict[str, Any]] = []
    boundaries: list[Any] | None = None
    proposal: Any = None

    @model_validator(mode="before")
    @classmethod
    def _known_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            known = set(cls.model_fields) | {
                f.alias for f in cls.model_fields.values() if f.alias
            }
            unknown = sorted(set(data) - known)
            if unknown:
                raise ValueError(f"unknown answers keys {unknown}")
        return data

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v != ANSWERS_KIND:
            raise ValueError(
                f"expected {ANSWERS_KIND} answers (from the ask page), got {v!r}"
            )
        return v

    @field_validator("version", mode="before")
    @classmethod
    def _version(cls, v: Any) -> Any:
        if v != CONTRACT_VERSION or isinstance(v, bool):
            raise ValueError(
                f"expected version {CONTRACT_VERSION} answers, got version {v!r} "
                "(re-export them from a page made by this paces)"
            )
        return v

    @field_validator("k", mode="before")
    @classmethod
    def _k(cls, v: Any) -> Any:
        if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 1):
            raise ValueError(f"k must be a positive integer or null, got {v!r}")
        return v

    @field_validator("boundaries", mode="before")
    @classmethod
    def _boundaries_is_a_list(cls, v: Any) -> Any:
        if v is not None and (not isinstance(v, list) or len(v) < 2):
            raise ValueError(f"boundaries must be a list of 2 or more times, got {v!r}")
        return v


def contract_schemas() -> dict[str, dict]:
    """The JSON Schema of both documents, for a UI written in another language.

    >>> contract_schemas()["proposal"]["properties"]["kind"]["const"]
    'PacesAskProposal'
    """
    return {
        "proposal": Proposal.model_json_schema(by_alias=True),
        "answers": AnswersDocument.model_json_schema(by_alias=True),
    }
