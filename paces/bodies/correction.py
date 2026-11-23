"""Body schema for a human correction — the log of ``docs/alignment/07 §7.5``, stored.

``annot://schema/guide-correction/v1``, tier ``correction``: one row per entry
of a guide's correction log (:mod:`paces.corrections`), in log order
(``ordinal``). The log is kept **separately from the result**: it is human input
with provenance, not analysis, so :func:`paces.evidence.to_store`'s
re-derivation never prunes it, and only
:func:`paces.evidence.corrections_to_store` rewrites it.

The annotation's reference is the stretch of media the correction is about:
a ``pin``'s or ``forbid``'s ``span`` (where the step is, or is not), so an
interval query finds it, and a point at ``anchor_t`` for the other verbs. A
``pin``'s or ``forbid``'s ``anchor_t`` is then not the reference's start (a
forbid's anchor lies outside its span), so it travels in the body as a
decimal string: the *key* naming which step is meant, not an interval.

``author`` and ``at`` are required here, though optional on
:class:`~paces.corrections.Correction`: a hand-written log stays easy to type,
and a stored log is where provenance pays (paces#34).
"""

from __future__ import annotations

from typing import Literal

from lacing.schema import register_body_schema
from pydantic import Field

from paces.bodies._base import BodyBase, Decimal

CORRECTION_TIER = "correction"
CORRECTION_BODY_SCHEMA_URI = "annot://schema/guide-correction/v1"


class GuideCorrectionBodyV1(BodyBase):
    """One entry of a guide's correction log."""

    doc_id: str = Field(..., description="Which guide this correction belongs to.")
    ordinal: int = Field(
        ...,
        ge=0,
        description=(
            "The entry's position in the log. Replay applies corrections in "
            "this order, each to the result of the ones before it."
        ),
    )
    verb: Literal["pin", "forbid", "absent", "split", "merge"] = Field(
        ..., description="What the human said (paces.corrections.VERBS)."
    )
    anchor_t: Decimal | None = Field(
        None,
        description=(
            "For pin and forbid, whose reference is their span: the time naming "
            "the step meant, in seconds. None for the other verbs, whose "
            "reference is a point at it."
        ),
    )
    step_id: str | None = Field(
        None, description="The step id shown when it was made; display only."
    )
    author: str = Field(..., min_length=1, description="Who made the correction.")
    at: str = Field(..., min_length=1, description="When (ISO-8601).")
    media_key: str | None = Field(
        None,
        description=(
            "Which rendering of the media the correction was true of. A replay "
            "told another key skips it as stale until it is migrated."
        ),
    )
    migrated_from: str | None = Field(
        None,
        description="The media key it was migrated from, when a re-cut moved it.",
    )
    reason: str = Field("", description="Why, in the human's words.")


register_body_schema(CORRECTION_BODY_SCHEMA_URI, GuideCorrectionBodyV1)
