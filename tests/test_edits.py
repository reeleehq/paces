"""Edit protection: typed patches write Locks; regeneration cannot eat edits.

The scenario throughout is the POC's real failure mode: a human fixes a
caption / a name, analysis re-runs, and the regenerated document must keep the
fix (docs/07-annotation-model.md §1.3).
"""

from __future__ import annotations

import pytest

from paces.edits import apply_edits, merge_regenerated
from paces.model import Measure, Origin, SourceSpan, Step, StepDocument, Source


def _doc(**overrides) -> StepDocument:
    """A small two-step document with spans, the shape a projection makes."""
    fields = dict(
        id="guide",
        title="A guide",
        sources=[Source(id="vid", kind="video", uri="https://example.com/v")],
        steps=[
            Step(
                id="a",
                name="Step A",
                duration=Measure(value="2", unit="eight"),
                spans=[SourceSpan(source="vid", start="10", end="20")],
                origin=Origin(generated_by="segmenter:grid-placed"),
            ),
            Step(
                id="b",
                name="Step B",
                duration=Measure(value="4", unit="eight"),
                spans=[
                    SourceSpan(source="vid", start="20", end="35", caption="machine")
                ],
                origin=Origin(generated_by="segmenter:grid-placed"),
            ),
        ],
    )
    fields.update(overrides)
    return StepDocument(**fields)


# ── apply_edits ─────────────────────────────────────────────────────────────


def test_set_by_step_id_records_a_reversible_lock():
    doc = apply_edits(
        _doc(),
        [{"op": "set", "path": "/steps/b/spans/0/caption", "value": "hand-fixed"}],
        by="user:thor",
    )
    step_b = doc.steps[1]
    assert step_b.spans[0].caption == "hand-fixed"
    (lock,) = step_b.locks
    assert lock.path == "/spans/0/caption"
    assert lock.was == "machine"
    assert lock.by == "user:thor"


def test_set_by_index_and_doc_level_lock():
    doc = apply_edits(
        _doc(),
        [
            {"op": "set", "path": "/steps/0/name", "value": "Renamed"},
            {"op": "set", "path": "/title", "value": "Better title"},
        ],
        by="user:thor",
    )
    assert doc.steps[0].name == "Renamed"
    assert doc.steps[0].locks[0].path == "/name"
    assert doc.title == "Better title"
    assert doc.locks[0].path == "/title"
    assert doc.locks[0].was == "A guide"


def test_editing_a_locked_path_again_replaces_the_lock():
    doc = apply_edits(
        _doc(), [{"op": "set", "path": "/steps/a/name", "value": "v1"}], by="user:t"
    )
    doc = apply_edits(
        doc, [{"op": "set", "path": "/steps/a/name", "value": "v2"}], by="user:t"
    )
    (lock,) = doc.steps[0].locks
    assert lock.was == "v1"  # the last edit stays reversible


def test_bad_paths_and_ops_are_informative_and_atomic():
    original = _doc()
    with pytest.raises(ValueError, match="no item with id 'zz'"):
        apply_edits(
            original,
            [{"op": "set", "path": "/steps/zz/name", "value": "x"}],
            by="user:t",
        )
    with pytest.raises(ValueError, match="unsupported op"):
        apply_edits(
            original,
            [{"op": "append", "path": "/steps", "value": {}}],
            by="user:t",
        )
    with pytest.raises(ValueError, match="no field"):
        apply_edits(
            original,
            [{"op": "set", "path": "/steps/a/nope", "value": "x"}],
            by="user:t",
        )
    assert original == _doc()  # nothing was half-applied


def test_invalid_value_fails_schema_validation():
    with pytest.raises(Exception, match="duration"):
        apply_edits(
            _doc(),
            [{"op": "set", "path": "/steps/a/duration", "value": 3.5}],
            by="user:t",
        )


# ── merge_regenerated ───────────────────────────────────────────────────────


def test_merge_keeps_committed_notes_and_resources_a_regeneration_lacks():
    from paces.model import Resource

    committed = _doc(
        notes=["Start easy."],
        resources=[Resource(id="mat", name="A mat"), Resource(id="w", name="Weight")],
    )
    committed = apply_edits(
        committed,
        [{"op": "set", "path": "/resources/mat/name", "value": "A thick mat"}],
        by="user:thor",
    )
    merged = merge_regenerated(committed, _doc())  # analysis never writes either
    assert merged.notes == ["Start easy."]
    assert {r.id: r.name for r in merged.resources} == {"mat": "A thick mat", "w": "Weight"}


def test_merge_keeps_locked_values_and_takes_fresh_elsewhere():
    committed = apply_edits(
        _doc(),
        [{"op": "set", "path": "/steps/b/spans/0/caption", "value": "hand-fixed"}],
        by="user:thor",
    )
    # regeneration moved a boundary AND regressed the caption
    fresh = _doc()
    fresh.steps[1].spans[0].caption = "machine v2"
    fresh.steps[1].spans[0].start = "21"
    fresh.steps[0].name = "Step A improved"

    merged = merge_regenerated(committed, fresh)
    assert merged.steps[1].spans[0].caption == "hand-fixed"  # lock wins
    assert merged.steps[1].spans[0].start == "21"  # fresh wins unlocked
    assert merged.steps[0].name == "Step A improved"
    assert merged.steps[1].locks == committed.steps[1].locks  # protection travels


def test_merge_keeps_doc_level_locks():
    committed = apply_edits(
        _doc(), [{"op": "set", "path": "/title", "value": "My title"}], by="user:t"
    )
    fresh = _doc(title="Regenerated title")
    merged = merge_regenerated(committed, fresh)
    assert merged.title == "My title"


def test_protected_committed_only_step_survives_where_it_was():
    committed = _doc()
    committed.steps.insert(
        1,
        Step(
            id="human-extra",
            name="A step the human added",
            duration=Measure(value="1", unit="eight"),
            origin=Origin(generated_by="user:thor"),
        ),
    )
    fresh = _doc()  # regeneration knows nothing of the human step
    merged = merge_regenerated(committed, fresh)
    assert [s.id for s in merged.steps] == ["a", "human-extra", "b"]


def test_unprotected_committed_only_step_is_superseded():
    committed = _doc()
    committed.steps.append(
        Step(
            id="stale-analysis",
            name="Old analysis output",
            duration=Measure(value="1", unit="eight"),
            origin=Origin(generated_by="segmenter:grid-placed"),
        )
    )
    merged = merge_regenerated(committed, _doc())
    assert [s.id for s in merged.steps] == ["a", "b"]


def test_fresh_only_steps_are_kept():
    fresh = _doc()
    fresh.steps.append(
        Step(
            id="new-find",
            name="Newly detected",
            duration=Measure(value="1", unit="eight"),
        )
    )
    merged = merge_regenerated(_doc(), fresh)
    assert merged.steps[-1].id == "new-find"


def test_committed_cues_and_questions_survive_a_cueless_regeneration():
    from paces.model import Anchor, Cue, OpenQuestion

    committed = _doc()
    committed.cues.append(
        Cue(id="c1", kind="lyric", text="qué calor", anchor=Anchor(step="a"))
    )
    committed.questions.append(OpenQuestion(id="q1", text="Which side first?"))
    merged = merge_regenerated(committed, _doc())
    assert merged.cues[0].text == "qué calor"
    assert merged.questions[0].id == "q1"


def test_lock_on_a_path_the_fresh_structure_lost_is_kept_as_record():
    committed = apply_edits(
        _doc(),
        [{"op": "set", "path": "/steps/b/spans/0/caption", "value": "kept"}],
        by="user:t",
    )
    fresh = _doc()
    fresh.steps[1].spans = []  # regeneration dropped the span entirely
    merged = merge_regenerated(committed, fresh)
    assert merged.steps[1].spans == []  # structure follows fresh...
    assert merged.steps[1].locks[0].was == "machine"  # ...the record survives


def test_tools_roundtrip_edit_and_merge():
    from paces import tools

    doc_dict = tools.to_document(
        tools.segment(boundaries=[0, 10, 20], steps=["intro", "verse"]),
        doc_id="g",
        title="G",
        source="https://example.com/v",
    )
    edited = tools.edit(
        doc_dict,
        [{"op": "set", "path": "/steps/intro/name", "value": "Intro!"}],
        by="user:thor",
    )
    assert edited["steps"][0]["name"] == "Intro!"
    merged = tools.merge(edited, doc_dict)
    assert merged["steps"][0]["name"] == "Intro!"


# ── adversarial-review regressions (PR #11) ────────────────────────────────


def test_span_lock_follows_the_span_through_a_reorder():
    """Finding 1 (BLOCKER): a fresh doc inserts a new span BEFORE the locked
    one; the locked caption must land on the matched span, not position 0."""
    committed = apply_edits(
        _doc(),
        [{"op": "set", "path": "/steps/b/spans/0/caption", "value": "hand-fixed"}],
        by="user:thor",
    )
    fresh = _doc()
    fresh.steps[1].spans = [
        SourceSpan(source="vid", role="closeup", start="5", end="9"),
        SourceSpan(source="vid", start="20", end="35", caption="machine v2"),
    ]
    merged = merge_regenerated(committed, fresh)
    closeup, performance = merged.steps[1].spans
    assert closeup.caption is None  # the new span is untouched
    assert performance.caption == "hand-fixed"  # the lock followed its span


def test_source_lock_follows_the_source_through_a_reorder():
    committed = _doc()
    committed.sources.append(Source(id="notes", kind="document", uri="notes.html"))
    committed = apply_edits(
        committed,
        [{"op": "set", "path": "/sources/1/uri", "value": "notes-v2.html"}],
        by="user:thor",
    )
    # canonicalised to id-form at record time
    assert committed.locks[0].path == "/sources/notes/uri"
    fresh = _doc()
    fresh.sources = [
        Source(id="notes", kind="document", uri="notes.html"),
        Source(id="vid", kind="video", uri="https://example.com/v"),
    ]
    merged = merge_regenerated(committed, fresh)
    by_id = {s.id: s for s in merged.sources}
    assert by_id["notes"].uri == "notes-v2.html"
    assert by_id["vid"].uri == "https://example.com/v"


def test_digit_step_ids_resolve_id_first():
    """Finding 2: chapters titled '1','2' mint digit ids; /steps/1 must mean
    the step whose id is '1', not position 1."""
    doc = _doc()
    doc.steps[0].id = "1"
    doc.steps[1].id = "0"
    edited = apply_edits(
        doc, [{"op": "set", "path": "/steps/1/name", "value": "hit"}], by="user:t"
    )
    assert edited.steps[0].name == "hit"  # id '1' is at position 0
    assert edited.steps[1].name == "Step B"


def test_step_shaped_attrs_data_does_not_capture_the_lock():
    """Finding 3: user data in attrs that happens to look like a Step must
    not swallow the Lock, and the edit must survive a merge."""
    committed = _doc()
    committed.attrs["things"] = [{"duration": 1, "spans": [], "note": "orig"}]
    committed = apply_edits(
        committed,
        [{"op": "set", "path": "/attrs/things/0/note", "value": "fixed"}],
        by="user:thor",
    )
    assert committed.locks and committed.locks[0].path == "/attrs/things/0/note"
    assert "locks" not in committed.attrs["things"][0]  # user data unpolluted
    assert all(not s.locks for s in committed.steps)
    fresh = _doc()
    fresh.attrs["things"] = [{"duration": 1, "spans": [], "note": "orig"}]
    merged = merge_regenerated(committed, fresh)
    assert merged.attrs["things"][0]["note"] == "fixed"  # committed attrs win


def test_duplicate_step_ids_are_flagged_by_the_validator():
    from paces.model import validate_document

    doc = _doc()
    doc.steps[1].id = "a"
    issues = validate_document(doc)
    assert any("duplicate step id 'a'" in issue for issue in issues)


def test_a_single_bare_edit_mapping_is_accepted():
    doc = apply_edits(
        _doc(), {"op": "set", "path": "/title", "value": "One edit"}, by="user:t"
    )
    assert doc.title == "One edit"


def test_camel_case_paths_are_accepted_and_canonicalised():
    doc = apply_edits(
        _doc(),
        [{"op": "set", "path": "/steps/a/variantOf", "value": "b"}],
        by="user:t",
    )
    assert doc.steps[0].variant_of == "b"
    assert doc.steps[0].locks[0].path == "/variant_of"


# ── re-review regressions (the probes that beat the first fix) ─────────────


def test_span_lock_survives_a_same_role_insertion():
    """R1: the inserted span shares (source, role) with the locked one —
    exact-start anchoring must carry the caption to the right span."""
    committed = apply_edits(
        _doc(),
        [{"op": "set", "path": "/steps/b/spans/0/caption", "value": "hand-fixed"}],
        by="user:thor",
    )
    fresh = _doc()
    fresh.steps[1].spans = [
        SourceSpan(source="vid", start="5", end="9", caption="new closeup"),
        SourceSpan(source="vid", start="20", end="35", caption="machine v2"),
    ]
    merged = merge_regenerated(committed, fresh)
    first, second = merged.steps[1].spans
    assert first.caption == "new closeup"  # untouched
    assert second.caption == "hand-fixed"  # the lock followed start=20


def test_span_lock_survives_an_intra_group_swap():
    """R1b: two same-(source, role) spans, fresh emits them reordered."""
    committed = _doc()
    committed.steps[1].spans = [
        SourceSpan(source="vid", start="20", end="35", caption="first"),
        SourceSpan(source="vid", start="40", end="55", caption="second"),
    ]
    committed = apply_edits(
        committed,
        [{"op": "set", "path": "/steps/b/spans/1/caption", "value": "hand-fixed"}],
        by="user:thor",
    )
    fresh = _doc()
    fresh.steps[1].spans = [
        SourceSpan(source="vid", start="40", end="55", caption="second v2"),
        SourceSpan(source="vid", start="20", end="35", caption="first v2"),
    ]
    merged = merge_regenerated(committed, fresh)
    by_start = {span.start: span for span in merged.steps[1].spans}
    assert by_start["40"].caption == "hand-fixed"
    assert by_start["20"].caption == "first v2"


def test_ambiguous_span_lock_declines_instead_of_guessing():
    """Moved start + non-singleton group = no confident match: nothing is
    written to any span; the lock survives as the record."""
    committed = _doc()
    committed.steps[1].spans = [
        SourceSpan(source="vid", start="20", end="35", caption="first"),
        SourceSpan(source="vid", start="40", end="55", caption="second"),
    ]
    committed = apply_edits(
        committed,
        [{"op": "set", "path": "/steps/b/spans/0/caption", "value": "hand-fixed"}],
        by="user:thor",
    )
    fresh = _doc()
    fresh.steps[1].spans = [  # both starts moved, group of two: ambiguous
        SourceSpan(source="vid", start="21", end="35", caption="first v2"),
        SourceSpan(source="vid", start="41", end="55", caption="second v2"),
    ]
    merged = merge_regenerated(committed, fresh)
    assert [s.caption for s in merged.steps[1].spans] == ["first v2", "second v2"]
    assert merged.steps[1].locks  # the record survives even when unapplied


def test_singleton_group_still_matches_when_the_boundary_moved():
    """The original headline case must keep working: one span per (source,
    role) on each side, start changed by regeneration — the lock re-applies."""
    committed = apply_edits(
        _doc(),
        [{"op": "set", "path": "/steps/b/spans/0/caption", "value": "hand-fixed"}],
        by="user:thor",
    )
    fresh = _doc()
    fresh.steps[1].spans[0].start = "21"
    merged = merge_regenerated(committed, fresh)
    assert merged.steps[1].spans[0].caption == "hand-fixed"


def test_renaming_a_step_id_works_in_both_spellings():
    """R2: the lock site resolves before the mutation, so /id is editable."""
    by_id = apply_edits(
        _doc(),
        [{"op": "set", "path": "/steps/a/id", "value": "renamed"}],
        by="user:t",
    )
    assert by_id.steps[0].id == "renamed"
    assert by_id.steps[0].locks[0].path == "/id"
    assert by_id.steps[0].locks[0].was == "a"

    by_index = apply_edits(
        _doc(),
        [{"op": "set", "path": "/steps/0/id", "value": "renamed"}],
        by="user:t",
    )
    assert by_index.steps[0].id == "renamed"


def test_scalar_list_edits_do_not_survive_but_keep_their_record():
    """R4: documented limitation — a scalar has no identity but its value."""
    committed = _doc()
    committed.steps[0].tags = ["wrong-tag"]
    committed = apply_edits(
        committed,
        [{"op": "set", "path": "/steps/a/tags/0", "value": "right-tag"}],
        by="user:t",
    )
    fresh = _doc()
    fresh.steps[0].tags = ["wrong-tag"]
    merged = merge_regenerated(committed, fresh)
    assert merged.steps[0].tags == ["wrong-tag"]  # not protected, by design
    assert merged.steps[0].locks  # but the record survives


def _repeats(names_and_starts) -> StepDocument:
    """A document of steps named and timed as given, with the generated ids
    a segmenter makes for repeats (``turn``, ``turn-2``, ...)."""
    from paces.segmenters import unique_slug_ids

    names = [n for n, _ in names_and_starts]
    return _doc(
        steps=[
            Step(
                id=sid,
                name=name,
                duration=Measure(value="1", unit="eight"),
                spans=[SourceSpan(source="vid", start=str(start), end=str(start + 4))],
                origin=Origin(generated_by="segmenter:grid-placed"),
            )
            for sid, (name, start) in zip(unique_slug_ids(names), names_and_starts)
        ]
    )


def test_a_lock_on_a_repeat_stays_on_it_when_a_repeat_is_inserted_before_it():
    """paces#50: committed [Turn, Kick, Turn] (turn, kick, turn-2) with a lock
    on turn-2; regeneration finds a new Turn at 5 s, so its ids shift to turn,
    turn-2, kick, turn-3. The lock stays on the Turn at 20 s, and the new one
    gets an id no committed step holds."""
    committed = apply_edits(
        _repeats([("Turn", 0), ("Kick", 10), ("Turn", 20)]),
        [{"op": "set", "path": "/steps/turn-2/name", "value": "Turn (left)"}],
        by="user:thor",
    )
    fresh = _repeats([("Turn", 0), ("Turn", 5), ("Kick", 10), ("Turn", 20)])
    merged = merge_regenerated(committed, fresh)
    by_start = {str(s.spans[0].start): s for s in merged.steps}
    assert by_start["20"].name == "Turn (left)" and by_start["20"].id == "turn-2"
    assert by_start["5"].name == "Turn" and by_start["5"].id not in {"turn", "turn-2", "kick"}
    assert by_start["0"].id == "turn"
    assert len({s.id for s in merged.steps}) == 4


def test_repeats_without_times_keep_their_positional_ids():
    """With no span to tell occurrences apart, the merge matches by id as before."""
    committed = _repeats([("Turn", 0), ("Turn", 20)])
    for step in committed.steps:
        step.spans = []
    fresh = committed.model_copy(deep=True)
    assert [s.id for s in merge_regenerated(committed, fresh).steps] == ["turn", "turn-2"]


def _ids(doc) -> list[str]:
    out = []

    def walk(steps):
        for s in steps:
            out.append(s.id)
            walk(s.steps)

    walk(doc.steps)
    return out


def test_repeat_identity_never_makes_two_steps_one_id():
    """paces#58 review: a step named "Turn 2" holds the id a second Turn would
    take; a nested repeat must not take its parent's id; and ids stay unique."""
    committed = _repeats([("Turn", 0), ("Turn", 20)])  # turn, turn-2
    fresh = _repeats([("Turn 2", 10), ("Turn", 0), ("Turn", 20)])  # turn-2, turn, turn-3
    merged = merge_regenerated(committed, fresh)
    ids = _ids(merged)
    assert len(ids) == len(set(ids)), ids
    assert {str(s.spans[0].start): s.id for s in merged.steps}["20"] == "turn-2"

    parent = _repeats([("Turn", 0)])
    nested = _repeats([("Turn", 0)])
    nested.steps[0].steps = _repeats([("Turn", 1), ("Turn", 2)]).steps  # ids turn, turn-2
    nested.steps[0].steps[0].id, nested.steps[0].steps[1].id = "turn-2", "turn-3"
    ids = _ids(merge_regenerated(parent, nested))
    assert len(ids) == len(set(ids)), ids


def test_repeat_identity_reads_time_order_not_list_order():
    committed = _repeats([("Turn", 0), ("Turn", 20)])
    committed.steps.reverse()  # [turn-2 @20, turn @0]
    merged = merge_regenerated(committed, _repeats([("Turn", 0), ("Turn", 20)]))
    assert {str(s.spans[0].start): s.id for s in merged.steps} == {"0": "turn", "20": "turn-2"}


def test_a_renamed_repeat_and_a_cue_on_it_stay_with_their_occurrence():
    """An ``/id`` rename (``turn-2`` -> ``my-turn``) keeps to the Turn at 20 s
    when a Turn is inserted earlier, and a fresh cue anchored to the fresh id
    of that Turn is re-anchored with it."""
    from paces.model import Anchor, Cue

    committed = apply_edits(
        _repeats([("Turn", 0), ("Kick", 10), ("Turn", 20)]),
        [{"op": "set", "path": "/steps/turn-2/id", "value": "my-turn"}],
        by="user:thor",
    )
    fresh = _repeats([("Turn", 0), ("Turn", 5), ("Kick", 10), ("Turn", 20)])
    fresh.cues = [Cue(id="clap", kind="count", text="clap", anchor=Anchor(step="turn-3"))]
    merged = merge_regenerated(committed, fresh)
    by_start = {str(s.spans[0].start): s.id for s in merged.steps}
    assert by_start["20"] == "my-turn" and by_start["5"] not in {"my-turn", "turn"}
    assert merged.cues[0].anchor.step == "my-turn"


def test_unnamed_steps_keep_their_place_ids():
    committed = _repeats([("", 0), ("", 10)])
    fresh = _repeats([("", 0), ("", 5), ("", 10)])
    assert _ids(merge_regenerated(committed, fresh)) == _ids(fresh)
