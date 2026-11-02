"""Human corrections: a time-keyed log of constraints that survives re-runs (#10)."""

from __future__ import annotations

import json

import pytest

from paces import tools
from paces.corrections import (
    Correction,
    absent,
    forbid,
    from_wire,
    merge,
    pin,
    replay,
    split,
    to_wire,
)
from paces.segmenters import Capability, Segmentation, SegStep, segment

CUTS = [0, 10, 20, 30]
NAMES = ["intro", "verse", "chorus"]


def _spans(seg):
    return [(s.id, s.name, s.spans) for s in seg.steps]


# ── the five verbs, replayed over a segmenter that does not read the log ────


def test_split_adds_a_cut_and_an_honestly_unnamed_step():
    seg = segment(boundaries=CUTS, steps=NAMES, corrections=[split(15)])
    assert seg.boundaries == (0.0, 10.0, 15.0, 20.0, 30.0)
    assert _spans(seg)[1:3] == [
        ("verse", "verse", ((10.0, 15.0),)),
        ("verse-2", "", ((15.0, 20.0),)),  # the human said "two", not the name
    ]
    assert seg.steps[2].source == "correction"
    assert "corrected: split@15" in seg.flags


def test_merge_removes_the_nearest_cut_within_tolerance():
    seg = segment(boundaries=CUTS, steps=NAMES, corrections=[merge(20.9)])
    assert seg.boundaries == (0.0, 10.0, 30.0)
    assert _spans(seg) == [
        ("intro", "intro", ((0.0, 10.0),)),
        ("verse", "verse", ((10.0, 30.0),)),
    ]


def test_merge_keeps_the_visible_name_when_the_left_step_is_unnamed():
    seg = segment(boundaries=CUTS, steps=NAMES, corrections=[split(15), merge(20)])
    assert _spans(seg)[2] == ("chorus", "chorus", ((15.0, 30.0),))


def test_pin_moves_the_step_and_its_abutting_neighbours():
    seg = segment(boundaries=CUTS, steps=NAMES, corrections=[pin((8, 22))])
    assert _spans(seg) == [
        ("intro", "intro", ((0.0, 8.0),)),
        ("verse", "verse", ((8.0, 22.0),)),
        ("chorus", "chorus", ((22.0, 30.0),)),
    ]
    assert seg.boundaries == (0.0, 8.0, 22.0, 30.0)


def test_pin_that_would_empty_a_neighbour_is_infeasible_and_changes_nothing():
    seg = segment(
        boundaries=CUTS, steps=NAMES, corrections=[pin((12, 30), anchor_t=15)]
    )
    assert _spans(seg) == _spans(segment(boundaries=CUTS, steps=NAMES))
    assert any(f.startswith("correction-infeasible: pin@15") for f in seg.flags)


def test_absent_removes_the_step_but_keeps_the_cuts():
    seg = segment(boundaries=CUTS, steps=NAMES, corrections=[absent(12)])
    assert [s.id for s in seg.steps] == ["intro", "chorus"]
    assert seg.boundaries == (0.0, 10.0, 20.0, 30.0)


def test_forbid_is_reported_not_silently_ignored():
    """Moving a step elsewhere needs a solver; replay says so instead of lying."""
    violated = segment(boundaries=CUTS, steps=NAMES, corrections=[forbid(12, (11, 13))])
    assert any(f.startswith("correction-unenforced: forbid@12") for f in violated.flags)
    satisfied = segment(boundaries=CUTS, steps=NAMES, corrections=[forbid(12, (0, 5))])
    assert "corrected: forbid@12" in satisfied.flags


@pytest.mark.parametrize(
    "correction",
    [split(99), merge(99), pin((95, 99)), absent(99), forbid(99, (0, 1)), split(10)],
    ids=lambda c: c.label,
)
def test_a_correction_with_nothing_to_act_on_is_flagged_never_dropped(correction):
    seg = segment(boundaries=CUTS, steps=NAMES, corrections=[correction])
    assert any(
        f.startswith(f"correction-unmatched: {correction.label}") for f in seg.flags
    )
    assert _spans(seg) == _spans(segment(boundaries=CUTS, steps=NAMES))


def test_corrections_apply_in_log_order():
    """The second correction acts on the result of the first, as the human made them."""
    seg = segment(boundaries=CUTS, corrections=[split(15), absent(17)])
    assert [s.spans for s in seg.steps] == [
        ((0.0, 10.0),),
        ((10.0, 15.0),),
        ((20.0, 30.0),),
    ]


def test_split_partitions_children_between_the_halves():
    child_a = SegStep(id="a", spans=((10.0, 14.0),))
    child_b = SegStep(id="b", spans=((16.0, 20.0),))
    seg = Segmentation(
        steps=(SegStep(id="v", spans=((10.0, 20.0),), children=(child_a, child_b)),),
        boundaries=(10.0, 20.0),
    )
    head, tail = replay(seg, [split(15)]).steps
    assert [c.id for c in head.children] == ["a"]
    assert [c.id for c in tail.children] == ["b"]


# ── the log survives a re-run, because it is keyed by time ──────────────────


def test_the_log_replays_against_a_different_segmenter():
    """Same human log, two methods: ids differ, the time-keyed corrections still land."""
    log = [split(15.0)]
    by_cuts = segment(boundaries=CUTS, corrections=log)
    chapters = {
        "chapters": [
            {"start_time": 0, "end_time": 10, "title": "Intro"},
            {"start_time": 10, "end_time": 20, "title": "Verse"},
            {"start_time": 20, "end_time": 30, "title": "Chorus"},
        ]
    }
    by_chapters = segment(metadata=chapters, corrections=log)
    assert by_cuts.method == "explicit" and by_chapters.method == "chapters"
    assert 15.0 in by_cuts.boundaries and 15.0 in by_chapters.boundaries


def test_a_segmenter_that_reads_the_log_receives_it_and_is_not_replayed():
    seen = {}

    def _solver(inputs):
        seen["corrections"] = inputs["corrections"]
        return Segmentation(
            boundaries=(0.0, 30.0), steps=(SegStep(id="x", spans=((0.0, 30.0),)),)
        )

    import sys
    import types

    module = types.ModuleType("_fake_solver")
    module.run = _solver
    sys.modules["_fake_solver"] = module
    try:
        solver = Capability(
            name="solver",
            gives="segmentation",
            summary="test double",
            target="_fake_solver:run",
            needs=frozenset({"boundaries"}),
            reads=frozenset({"corrections"}),
        )
        seg = segment(boundaries=CUTS, segmenter=solver, corrections=[split(15)])
    finally:
        del sys.modules["_fake_solver"]
    assert seen["corrections"] == (split(15),)
    assert seg.boundaries == (0.0, 30.0)  # not replayed on top
    assert not any(f.startswith("corrected") for f in seg.flags)


# ── the record and its wire form ────────────────────────────────────────────


def test_wire_round_trip_has_no_floats():
    c = pin((90.1, 100.25), step_id="b4", author="user:thor", at="2026-11-02T10:00:00Z")
    wire = to_wire(c)
    assert wire == {
        "verb": "pin",
        "anchorT": "95.175",
        "span": ["90.1", "100.25"],
        "stepId": "b4",
        "author": "user:thor",
        "at": "2026-11-02T10:00:00Z",
    }
    assert from_wire(json.loads(json.dumps(wire))) == c


def test_from_wire_refuses_unknown_keys():
    with pytest.raises(ValueError, match="unknown correction keys"):
        from_wire({"verb": "split", "anchorT": "3", "stepID": "x"})


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"verb": "rename", "anchor_t": 1.0}, "unknown verb"),
        ({"verb": "pin", "anchor_t": 1.0}, "needs span"),
        ({"verb": "split", "anchor_t": 1.0, "span": (0.0, 2.0)}, "takes no span"),
        ({"verb": "forbid", "anchor_t": 1.0, "span": (2.0, 2.0)}, "start < end"),
        ({"verb": "pin", "anchor_t": 5.0, "span": (0.0, 2.0)}, "inside its span"),
        ({"verb": "merge", "anchor_t": float("nan")}, "finite"),
    ],
)
def test_invalid_corrections_fail_at_construction(kwargs, match):
    with pytest.raises(ValueError, match=match):
        Correction(**kwargs)


def test_tool_surface_accepts_a_wire_log(tmp_path):
    log = tmp_path / "corrections.json"
    log.write_text(json.dumps([to_wire(split(15))]))
    payload = tools.segment(boundaries=json.dumps(CUTS), corrections=str(log))
    assert payload["boundaries"] == [0.0, 10.0, 15.0, 20.0, 30.0]
    assert "corrected: split@15" in payload["flags"]
