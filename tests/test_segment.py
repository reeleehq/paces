"""The segmenter seam: selection, the two v1 segmenters, honesty states."""

from __future__ import annotations

import json

import pytest

from paces.model import MetricGrid
from paces.projection import to_document
from paces.segmenters import Capability, capabilities, register, segment

GRID = {"unit": "eight", "subdivisions": 8, "tempoBpm": "129.2", "origin": "51.2"}
#: The POC routine as (name, eights) pairs — kickoff's "common real case".
ROUTINE_STEPS = [
    ("Mise en place", 2),
    ("Pas pieds pointe et ronde", 6),
    ("Soleil avec les bras", 4),
    ("Déhanchés", 8),
    ("Moulinets de bras", 4),
    ("Genou vers le bas", 4),
    ("Pas pieds pointe, bras alternés", 4),
    ("Taper dans les mains du voisin", 4),
    ("Avancer / reculer sur le refrain", 8),
]


def test_grid_placed_selected_and_placed():
    seg = segment("video.mp4", steps=ROUTINE_STEPS, grid=GRID)
    assert seg.method == "grid-placed"
    assert seg.unit == "eight"
    assert len(seg.steps) == 9
    assert seg.boundaries[0] == pytest.approx(51.2)
    # block 4 starts 12 eights in: 51.2 + 12 * 3.715 ≈ 95.78 (POC: 95.8)
    block4 = seg.steps[3]
    assert block4.spans[0][0] == pytest.approx(95.78, abs=0.05)
    assert block4.name == "Déhanchés"
    # ids are readable slugs, accents folded
    assert block4.id == "dehanches"


def test_grid_placed_places_children_within_the_parent():
    steps = [
        {"name": "Déhanchés", "duration": 8, "children": [("tête", 4), ("étoiles", 4)]},
    ]
    seg = segment("video.mp4", steps=steps, grid=GRID)
    parent = seg.steps[0]
    assert len(parent.children) == 2
    assert parent.children[0].spans[0][0] == pytest.approx(parent.spans[0][0])
    assert parent.children[1].spans[0][0] == pytest.approx(
        parent.spans[0][0] + 4 * 3.71517, abs=0.01
    )


def test_explicit_boundaries_with_names():
    seg = segment(boundaries=[0, 10, 20], steps=["intro", "verse"])
    assert seg.method == "explicit"
    assert [step.name for step in seg.steps] == ["intro", "verse"]
    assert seg.steps[0].spans == ((0.0, 10.0),)
    assert seg.flags == ()


def test_explicit_boundaries_abstain_from_naming():
    """Found-unnamed is a valid, honest state — names are never invented."""
    seg = segment(boundaries=[0, 10, 20, 30])
    assert seg.boundaries == (0.0, 10.0, 20.0, 30.0)
    assert all(step.name == "" for step in seg.steps)
    assert "naming-abstained" in seg.flags


def test_refusal_is_a_result_not_an_exception():
    seg = segment("video.mp4")
    assert seg.steps == () and seg.boundaries == ()
    assert seg.confidence == 0.0
    assert "no-signal" in seg.flags
    assert any(flag.startswith("try:") for flag in seg.flags)


def test_named_segmenter_overrides_selection():
    seg = segment(
        boundaries=[0, 5], steps=[("all of it", 4)], grid=GRID, segmenter="explicit"
    )
    assert seg.method == "explicit"


def test_named_segmenter_with_missing_inputs_says_what_is_missing():
    with pytest.raises(ValueError, match="grid"):
        segment("video.mp4", segmenter="grid-placed", steps=ROUTINE_STEPS)


def test_unknown_segmenter_lists_the_registry():
    with pytest.raises(ValueError, match="explicit"):
        segment("video.mp4", segmenter="does-not-exist")


def test_registering_a_capability_is_additive():
    """ADR-0003 §1: adding a segmenter edits nothing that exists."""
    before = set(capabilities())
    register(
        Capability(
            name="test-noop",
            gives="segmentation",
            summary="test",
            target="paces.segmenters:_segment_explicit",
            needs=frozenset({"boundaries"}),
        )
    )
    try:
        assert set(capabilities()) == before | {"test-noop"}
        seg = segment(boundaries=[0, 1], segmenter="test-noop")
        assert seg.method == "test-noop"
    finally:
        from paces import segmenters as segment_module

        segment_module._CAPABILITIES.pop("test-noop")


def test_to_document_carries_units_grid_and_decimal_strings():
    seg = segment("video.mp4", steps=ROUTINE_STEPS, grid=GRID)
    doc = to_document(
        seg,
        doc_id="que-calor",
        title="Que Calor",
        source="https://youtu.be/q_TUyxUhoEw",
    )
    assert doc.metric is not None and doc.metric.tempo_bpm == "129.2"
    assert doc.steps[0].duration.model_dump() == {"value": "2", "unit": "eight"}
    span = doc.steps[0].spans[0]
    assert span.start == "51.2"
    if "." in span.end:
        assert len(span.end.split(".")[1]) <= 3  # clean decimals, no float drift
    assert doc.sources[0].uri == "https://youtu.be/q_TUyxUhoEw"
    # provenance: which segmenter said so
    assert doc.steps[0].origin.generated_by == "segmenter:grid-placed"


def test_tools_segment_accepts_json_strings():
    from paces.tools import segment as segment_tool

    payload = segment_tool(
        "video.mp4",
        steps=json.dumps([["intro", 2], ["outro", 2]]),
        grid=json.dumps(GRID),
    )
    assert payload["method"] == "grid-placed"
    assert payload["steps"][0]["name"] == "intro"
    json.dumps(payload)  # JSON-ready throughout


@pytest.mark.parametrize(
    "value, places, expected",
    [
        (-0.0004, 3, "0"),  # rounds to zero: no sign (#40)
        (-0.0, 3, "0"),
        (-0.0005, 3, "-0.001"),
        (100, 0, "100"),  # places=0: no fraction to trim, digits stay
        (-0.4, 0, "0"),
        (72.60000000000001, 3, "72.6"),
    ],
)
def test_decimal_str_writes_clean_wire_decimals(value, places, expected):
    from paces.model import decimal_str

    assert decimal_str(value, places=places) == expected


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_decimal_str_refuses_non_finite_values(value):
    from paces.model import decimal_str

    with pytest.raises(ValueError, match="non-finite"):
        decimal_str(value)


def test_place_on_grid_is_the_public_placement():
    from paces.segmenters import place_on_grid

    seg = place_on_grid(ROUTINE_STEPS, GRID)
    assert [s.spans for s in seg.steps] == [
        s.spans for s in segment(steps=ROUTINE_STEPS, grid=GRID).steps
    ]


@pytest.mark.parametrize(
    "steps, grid, match",
    [
        (ROUTINE_STEPS, {"unit": "eight", "subdivisions": 8}, "tempoBpm and origin"),
        (ROUTINE_STEPS, {**GRID, "origin": None}, "with origin$"),
        ([], GRID, "at least one step"),
        ([("back", -1)], GRID, r"positive, finite durations: \['back'\]"),
        ([("nan", float("nan"))], GRID, "positive, finite"),
        ([("zero", 0)], GRID, "positive, finite"),
        (["no duration"], GRID, "duration for every step"),
        ([{"name": "p", "duration": 2, "children": ["c"]}], GRID, r"\['c'\]"),
    ],
)
def test_place_on_grid_names_what_is_missing(steps, grid, match):
    from paces.segmenters import place_on_grid

    with pytest.raises(ValueError, match=match):
        place_on_grid(steps, grid)


@pytest.mark.parametrize("origin, start", [("0", 0.0), ("0.0", 0.0), ("51.2", 51.2)])
def test_resolve_computes_wall_clock_from_any_origin_including_zero(origin, start):
    """An origin of 0 is a real origin, not a missing one (#46)."""
    from paces.model import resolve

    doc = to_document(
        segment(steps=[("a", 1)], grid={**GRID, "origin": origin}),
        doc_id="d",
        title="t",
    )
    assert resolve(doc)["steps"][0]["start_s"] == pytest.approx(start)


def test_resolve_without_an_origin_has_no_wall_clock():
    from paces.model import resolve

    doc = to_document(segment(steps=[("a", 1)], grid=GRID), doc_id="d", title="t")
    doc = doc.model_copy(
        update={"metric": doc.metric.model_copy(update={"origin": None})}
    )
    assert resolve(doc)["steps"][0]["start_s"] is None


def test_resolve_treats_a_numeric_zero_origin_as_an_origin():
    """A grid updated in place skips wire validation; 0 must still be 0 (#46)."""
    from paces.model import resolve

    doc = to_document(segment(steps=[("a", 1)], grid=GRID), doc_id="d", title="t")
    doc = doc.model_copy(update={"metric": doc.metric.model_copy(update={"origin": 0})})
    assert resolve(doc)["steps"][0]["start_s"] == 0.0


def test_duplicate_step_names_get_unique_ids_tree_wide():
    """Edits, locks and the evidence layer address steps by id (#47)."""
    steps = [
        ("Turn", 2),
        ("Turn", 2),
        {"name": "Kick", "duration": 4, "children": [("Turn", 2), ("Turn", 2)]},
    ]
    seg = segment(steps=steps, grid=GRID)
    ids = [seg.steps[0].id, seg.steps[1].id, *(c.id for c in seg.steps[2].children)]
    assert ids == ["turn", "turn-2", "turn-3", "turn-4"]
    doc = to_document(seg, doc_id="d", title="t")
    from paces.model import validate_document

    assert not [i for i in validate_document(doc) if "duplicate step id" in i]


def test_an_explicit_step_id_is_kept_and_never_reused():
    seg = segment(
        steps=[("Turn", 1), {"name": "x", "id": "turn", "duration": 1}], grid=GRID
    )
    assert [s.id for s in seg.steps] == ["turn-2", "turn"]


def test_a_step_that_is_neither_name_pair_nor_mapping_is_named_in_the_error():
    with pytest.raises(TypeError, match=r"steps\[1\].*3-item sequence"):
        segment(steps=[("a", 1), ("b", 1, "extra")], grid=GRID)
    with pytest.raises(TypeError, match=r"steps\[0\]\.children\[0\]"):
        segment(steps=[{"name": "p", "duration": 1, "children": [3]}], grid=GRID)


def test_bytes_is_not_a_name_duration_pair():
    with pytest.raises(TypeError, match=r"steps\[0\].*got bytes"):
        segment(steps=[b"ab"], grid=GRID)


def test_duplicate_explicit_ids_name_both_paths():
    steps = [
        {"name": "a", "id": "x", "duration": 1},
        ("b", 1),
        {"name": "c", "duration": 2, "children": [("d", 1), {"name": "e", "id": "x"}]},
    ]
    with pytest.raises(
        ValueError, match=r"'x' at steps\[0\] and steps\[2\]\.children\[1\]"
    ):
        segment(steps=steps, grid=GRID)


def test_generated_ids_are_breadth_first_so_children_never_rename_parents():
    before = segment(steps=[{"name": "Turn", "duration": 2}, ("Turn", 2)], grid=GRID)
    after = segment(
        steps=[{"name": "Turn", "duration": 2, "children": [("Turn", 2)]}, ("Turn", 2)],
        grid=GRID,
    )
    assert [s.id for s in before.steps] == [s.id for s in after.steps]
    assert [s.id for s in after.steps] == ["turn", "turn-2"]
    assert after.steps[0].children[0].id == "turn-3"


def test_partly_undated_steps_are_named_in_a_flag():
    """The refused state's 'try:' must not read as if no durations were given."""
    steps = [("a", 2), {"name": "p", "duration": 2, "children": ["u"]}]
    seg = segment(steps=steps, grid=GRID)
    assert "steps-undated: ['u']" in seg.flags
    assert not [f for f in segment(steps=["a"], grid=GRID).flags if "undated" in f]


def _forbid_measuring(monkeypatch):
    import paces.measure

    def _measure_grid(*args, **kwargs):
        raise AssertionError("measure_grid must not be called")

    monkeypatch.setattr(paces.measure, "measure_grid", _measure_grid)


def test_an_undated_child_keeps_placement_from_being_selected(tmp_path, monkeypatch):
    """'steps.durations' covers children, so no placing segmenter is chosen —
    and grid-measured is never asked to measure for a list it cannot place."""
    steps = [{"name": "p", "duration": 2, "children": ["undated"]}]
    seg = segment(steps=steps, grid=GRID)
    assert seg.method != "grid-placed"
    media = tmp_path / "song.wav"
    media.write_bytes(b"")
    _forbid_measuring(monkeypatch)
    with pytest.raises(
        ValueError,
        match=r"needs inputs you did not provide: \['steps\.durations'\]"
        r".*steps without a duration: \['undated'\]",
    ):
        segment(str(media), steps=steps, segmenter="grid-measured")


@pytest.mark.parametrize("bad", [0, -1, float("nan")])
def test_grid_measured_rejects_bad_durations_before_measuring(
    bad, tmp_path, monkeypatch
):
    pytest.importorskip("mixing")
    pytest.importorskip("librosa")
    media = tmp_path / "song.wav"
    media.write_bytes(b"")
    _forbid_measuring(monkeypatch)
    steps = [("a", 1), {"name": "p", "duration": 2, "children": [("c", bad)]}]
    with pytest.raises(ValueError, match=r"positive, finite durations: \['c'\]"):
        segment(str(media), steps=steps, segmenter="grid-measured")


def test_the_spans_fact_reads_the_whole_step_tree():
    """A span on a child counts, as a duration on a child does (#51)."""
    from paces.segmenters import _facts, _normalize_steps

    nested = _normalize_steps(
        [{"name": "p", "duration": 2, "children": [{"name": "c", "spans": [(1, 2)]}]}]
    )
    flat = _normalize_steps([("p", 2)])
    assert "steps.spans" in _facts(
        media=None, steps=nested, boundaries=None, grid=None, k=None
    )
    assert "steps.spans" not in _facts(
        media=None, steps=flat, boundaries=None, grid=None, k=None
    )
