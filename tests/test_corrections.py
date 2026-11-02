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
    normalize_corrections,
    merge,
    pin,
    replay,
    split,
    to_wire,
)
from paces.segmentation import inconsistencies
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
    assert "satisfied: forbid@12" in satisfied.flags
    assert not any(f.startswith("corrected: forbid") for f in satisfied.flags)


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


_SOLVER_SAW: list = []


def _solver_reading_the_log(inputs):
    """A segmenter double that honours the log itself (the issue #9 shape)."""
    _SOLVER_SAW.append(inputs["corrections"])
    return Segmentation(
        boundaries=(0.0, 30.0), steps=(SegStep(id="x", spans=((0.0, 30.0),)),)
    )


def test_a_segmenter_that_reads_the_log_receives_it_and_is_not_replayed():
    _SOLVER_SAW.clear()
    solver = Capability(
        name="solver",
        gives="segmentation",
        summary="test double",
        target=f"{__name__}:_solver_reading_the_log",
        needs=frozenset({"boundaries"}),
        reads=frozenset({"corrections"}),
    )
    seg = segment(boundaries=CUTS, segmenter=solver, corrections=[split(15)])
    assert _SOLVER_SAW == [(split(15),)]
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


# ── review findings: each case below once behaved wrongly ───────────────────

GAPPY = {  # chapters with gaps between them: A 0–8, B 10–20, C 22–30
    "chapters": [
        {"start_time": 0, "end_time": 8, "title": "A"},
        {"start_time": 10, "end_time": 20, "title": "B"},
        {"start_time": 22, "end_time": 30, "title": "C"},
    ]
}
GRID = {"unit": "eight", "subdivisions": 8, "tempoBpm": "123.7", "origin": "0.37"}
GRID_ROWS = [("a", 1), ("b", 1.5), ("c", 0.7), ("d", 1)]


def _seg(*steps, boundaries=None):
    """A hand-built segmentation; boundaries default to every span edge."""
    edges = {t for s in steps for span in s.spans for t in span}
    return Segmentation(steps=steps, boundaries=tuple(sorted(boundaries or edges)))


def _flagged(seg, prefix):
    return [f for f in seg.flags if f.startswith(prefix)]


def test_times_are_kept_to_the_millisecond_so_the_wire_is_lossless():
    """A grid-placed boundary is an ugly float; the wire writes 3 places."""
    grid_placed = segment(steps=GRID_ROWS, grid=GRID)
    b1, b2 = grid_placed.boundaries[1:3]
    assert b1 != round(b1, 3)  # the premise: an unrounded time
    for c in [pin((b1, b2)), split(0.8550444), forbid(b1, (b1, b2)), split(0.1 + 0.2)]:
        assert from_wire(json.loads(json.dumps(to_wire(c)))) == c
    assert split(0.8550444).anchor_t == 0.855
    assert pin((b1, b2)).span == (round(b1, 3), round(b2, 3))


def test_a_refused_segmentation_still_reports_every_correction():
    log = [split(5), merge(5), pin((1, 2)), forbid(5, (0, 1)), absent(5)]
    seg = segment(corrections=log)
    assert "no-signal" in seg.flags
    assert [f.split(" (")[0] for f in _flagged(seg, "correction-unmatched")] == [
        f"correction-unmatched: {c.label}" for c in log
    ]


def test_corrections_are_validated_before_any_segmenter_runs():
    with pytest.raises(ValueError, match="missing"):
        segment(corrections=[{"verb": "split"}])


@pytest.mark.parametrize(
    "wire, match",
    [
        ({"verb": "split"}, "missing \\['anchorT'\\]"),
        ({"anchorT": "1"}, "missing \\['verb'\\]"),
        ({"verb": "pin", "anchorT": "1", "span": ["0", "1", "2"]}, "start, end"),
        ({"verb": "split", "anchorT": "soon"}, "time in seconds"),
        ({"verb": "split", "anchorT": "1e400"}, "finite"),
    ],
)
def test_from_wire_raises_value_errors_only(wire, match):
    with pytest.raises(ValueError, match=match):
        from_wire(wire)


def test_a_single_correction_passed_where_a_log_is_expected_is_refused():
    one = {"verb": "absent", "anchorT": "5"}
    with pytest.raises(ValueError, match="single mapping; wrap it in a list"):
        normalize_corrections(one)
    with pytest.raises(ValueError, match="single mapping"):
        tools.segment(boundaries="[0, 10, 20]", corrections=json.dumps(one))
    payload = tools.segment(boundaries="[0, 10, 20]", corrections=json.dumps([one]))
    assert "corrected: absent@5" in payload["flags"]


def test_pin_across_a_gap_that_would_overlap_a_neighbour_is_infeasible():
    seg = segment(metadata=GAPPY, corrections=[pin((5, 25), anchor_t=15)])
    assert _spans(seg) == _spans(segment(metadata=GAPPY))
    assert _flagged(seg, "correction-infeasible: pin@15 (would overlap step")
    assert not _flagged(seg, "inconsistent")


def test_pin_inside_a_gap_moves_only_that_step():
    seg = segment(metadata=GAPPY, corrections=[pin((9, 21))])
    assert [s.spans for s in seg.steps] == [
        ((0.0, 8.0),),
        ((9.0, 21.0),),
        ((22.0, 30.0),),
    ]
    assert seg.boundaries == (0.0, 8.0, 9.0, 21.0, 22.0, 30.0)
    assert "corrected: pin@15" in seg.flags and not _flagged(seg, "inconsistent")


def test_pin_past_the_far_edge_of_a_neighbour_is_infeasible():
    seg = segment(
        boundaries=[0, 10, 20, 25, 30], corrections=[pin((10, 27), anchor_t=15)]
    )
    assert _flagged(seg, "correction-infeasible: pin@15 (would empty")


def test_pin_moves_only_the_abutting_time_order_neighbours():
    """'x' shares the edge value 10 but is not v's neighbour: it must not move."""
    seg = _seg(
        SegStep(id="a", spans=((0.0, 10.0),)),
        SegStep(id="v", spans=((10.0, 20.0),)),
        SegStep(id="b", spans=((20.0, 30.0),)),
    )
    moved = replay(seg, [pin((12, 18))])
    assert [s.spans for s in moved.steps] == [
        ((0.0, 12.0),),
        ((12.0, 18.0),),
        ((18.0, 30.0),),
    ]
    overlapping = _seg(
        SegStep(id="a", spans=((0.0, 10.0),)),
        SegStep(id="v", spans=((10.0, 20.0),)),
        SegStep(id="x", spans=((10.0, 12.0),)),
    )
    out = replay(overlapping, [pin((5, 20), anchor_t=15)])
    assert [s.spans for s in out.steps] == [s.spans for s in overlapping.steps]
    assert _flagged(out, "correction-infeasible: pin@15 (would overlap step 'x')")
    # the input itself overlapped: segment() says so, replay does not check
    assert any(f.startswith("inconsistent: steps") for f in inconsistencies(out))


def test_pin_clips_its_children_and_flags_any_it_drops():
    seg = _seg(
        SegStep(id="a", spans=((0.0, 10.0),)),
        SegStep(
            id="v",
            spans=((10.0, 20.0),),
            children=(
                SegStep(id="c1", spans=((10.0, 15.0),)),
                SegStep(id="c2", spans=((15.0, 20.0),)),
            ),
        ),
        SegStep(id="b", spans=((20.0, 30.0),)),
    )
    clipped = replay(seg, [pin((12, 25))])
    assert [c.spans for c in clipped.steps[1].children] == [
        ((12.0, 15.0),),
        ((15.0, 20.0),),
    ]
    dropped = replay(seg, [pin((16, 25), anchor_t=17)])
    assert [c.id for c in dropped.steps[1].children] == ["c2"]
    assert dropped.steps[1].children[0].spans == ((16.0, 20.0),)
    assert _flagged(dropped, "correction-clipped: pin@17 (dropped child 'c1' of 'v'")


def test_forbid_is_judged_after_the_whole_log():
    """A later pin can move the step INTO the forbidden span — or out of it."""
    into = segment(
        boundaries=CUTS,
        steps=NAMES,
        corrections=[forbid(12, (0, 5)), pin((3, 14), anchor_t=12)],
    )
    assert _flagged(into, "correction-unenforced: forbid@12 (step 'verse'")
    assert not _flagged(into, "satisfied")
    out_of = segment(
        boundaries=CUTS, steps=NAMES, corrections=[forbid(12, (11, 13)), pin((14, 18))]
    )
    assert "satisfied: forbid@12" in out_of.flags


def test_merge_does_not_move_the_name_of_a_step_that_lives_on_elsewhere():
    seg = _seg(
        SegStep(id="u", spans=((10.0, 20.0),)),
        SegStep(id="ch", name="chorus", spans=((20.0, 30.0), (40.0, 50.0))),
    )
    out = replay(seg, [merge(20)])
    assert _spans(out) == [
        ("u", "", ((10.0, 30.0),)),
        ("ch", "chorus", ((40.0, 50.0),)),
    ]


def test_merge_only_considers_cuts_where_two_steps_meet():
    """The nearest edge (10.8, a gap) is not a meeting; the cut at 10 is."""
    seg = _seg(
        SegStep(id="a", spans=((0.0, 10.0),)),
        SegStep(id="b", spans=((10.0, 10.8),)),
        SegStep(id="c", spans=((11.0, 20.0),)),
    )
    out = replay(seg, [merge(10.7)])
    assert [s.spans for s in out.steps] == [((0.0, 10.8),), ((11.0, 20.0),)]
    assert out.boundaries == (0.0, 10.8, 11.0, 20.0)


@pytest.mark.parametrize("t", [9.5, 9.0])
def test_merge_across_a_gap_is_unmatched(t):
    seg = segment(metadata=GAPPY, corrections=[merge(t)])
    assert _flagged(seg, f"correction-unmatched: merge@{t:g} (no two steps meet")


def test_merge_halfway_between_two_cuts_takes_the_earlier():
    seg = segment(boundaries=[0, 10, 11, 30], corrections=[merge(10.5)])
    assert seg.boundaries == (0.0, 11.0, 30.0)


def test_merge_after_absent_has_no_two_steps_to_join():
    seg = segment(boundaries=CUTS, steps=NAMES, corrections=[absent(12), merge(10)])
    assert _flagged(seg, "correction-unmatched: merge@10 (no two steps meet")


def test_merge_over_a_degenerate_zero_length_step_tells_no_lies():
    seg = segment(boundaries=[0, 10, 10, 20], corrections=[merge(10)])
    assert "corrected: merge@10" in seg.flags
    assert _flagged(seg, "inconsistent: step 'seg-2' has an empty span")
    assert not _flagged(seg, "inconsistent: steps")  # no positive overlap


def test_split_assigns_children_by_the_span_they_fall_in():
    seg = _seg(
        SegStep(
            id="v",
            spans=((10.0, 20.0), (40.0, 50.0)),
            children=(
                SegStep(id="c1", spans=((12.0, 14.0),)),
                SegStep(
                    id="c2", spans=((42.0, 44.0),)
                ),  # starts after 15, not in the cut span
                SegStep(id="c3", spans=((16.0, 18.0),)),
            ),
        ),
    )
    head, tail = replay(seg, [split(15)]).steps
    assert head.spans == ((10.0, 15.0), (40.0, 50.0))
    assert [c.id for c in head.children] == ["c1", "c2"]
    assert [c.id for c in tail.children] == ["c3"]


@pytest.mark.parametrize(
    "t, why",
    [(10, "already a cut there"), (10.1, "within 0.25 s of a cut"), (19.9, "within")],
)
def test_split_on_or_next_to_a_cut_is_unmatched(t, why):
    seg = segment(boundaries=CUTS, corrections=[split(t)])
    assert _flagged(seg, f"correction-unmatched: split@{t:g} ({why}")
    assert seg.boundaries == tuple(map(float, CUTS))


def test_min_step_s_is_a_keyword():
    seg = _seg(SegStep(id="a", spans=((0.0, 10.0),)))
    assert replay(seg, [split(9.5)], min_step_s=0.1).boundaries == (0.0, 9.5, 10.0)
    assert replay(seg, [split(9.5)], min_step_s=1.0).boundaries == (0.0, 10.0)


def test_a_boundaries_only_segmentation_can_still_be_split_and_merged():
    seg = Segmentation(boundaries=(0.0, 10.0, 20.0))
    out = replay(seg, [merge(10), split(5)])
    assert out.boundaries == (0.0, 5.0, 20.0)
    assert out.flags == ("corrected: merge@10", "corrected: split@5")


def test_the_consistency_check_flags_what_replay_cannot_repair():
    seg = _seg(
        SegStep(id="a", spans=((0.0, 10.0),)),
        SegStep(id="b", spans=((8.0, 20.0),)),
        boundaries=(0.0, 10.0, 20.0),
    )
    out = replay(seg, [absent(25)])
    assert inconsistencies(out) == (
        "inconsistent: steps 'a' and 'b' overlap (8–10)",
        "inconsistent: step edges not in boundaries: 8",
    )
    assert not _flagged(out, "inconsistent")  # checking is segment()'s job


def test_corrections_land_on_grid_placed_results():
    grid_placed = segment(steps=GRID_ROWS, grid=GRID)
    for b in grid_placed.boundaries[1:-1]:  # a tap on any boundary, to the ms
        merged = segment(steps=GRID_ROWS, grid=GRID, corrections=[merge(round(b, 3))])
        assert b not in merged.boundaries and len(merged.steps) == 3
        assert not _flagged(merged, "inconsistent")
    t = grid_placed.boundaries[1] + 0.3
    wire = json.loads(json.dumps([to_wire(split(t)), to_wire(merge(t))]))
    round_trip = segment(steps=GRID_ROWS, grid=GRID, corrections=wire)
    assert round_trip.boundaries == grid_placed.boundaries
    assert _spans(round_trip) == _spans(grid_placed)


def test_a_combined_log_stays_consistent():
    """split, pin, merge, forbid, absent — in one log, on named steps."""
    log = [
        split(15),
        pin((8, 13), anchor_t=12),
        merge(20),
        forbid(25, (0, 5)),
        absent(3),
    ]
    seg = segment(boundaries=CUTS, steps=NAMES, corrections=log)
    assert _spans(seg) == [
        ("verse", "verse", ((8.0, 13.0),)),
        ("chorus", "chorus", ((13.0, 30.0),)),
    ]
    assert seg.flags[-5:] == (
        "corrected: split@15",
        "corrected: pin@12",
        "corrected: merge@20",
        "satisfied: forbid@25",
        "corrected: absent@3",
    )
    assert not _flagged(seg, "inconsistent")


# ── regressions from the second review of #33 ───────────────────────────────


@pytest.mark.parametrize("span", ["15", 5, ["1", "2", "3"]])
def test_from_wire_refuses_a_span_that_is_not_a_pair(span):
    with pytest.raises(ValueError, match="span must be"):
        from_wire({"verb": "forbid", "anchorT": "1", "span": span})


def test_a_non_iterable_log_is_a_value_error():
    with pytest.raises(ValueError, match="list of corrections"):
        segment(boundaries=CUTS, corrections=5)


def test_the_steps_or_cuts_mode_is_decided_once_from_the_input():
    """Removing the last step does not turn a later split into a cut edit."""
    seg = segment(boundaries=[0, 10], corrections=[absent(5), split(5)])
    assert _flagged(seg, "correction-unmatched: split@5")
    assert seg.boundaries == (0.0, 10.0)


def test_a_split_never_reuses_an_id_a_forbid_may_still_name():
    seg = segment(
        boundaries=[0, 10, 20],
        steps=["a", "b"],
        corrections=[split(15), forbid(17, (12, 20)), absent(17), split(12)],
    )
    assert "b-2" not in [s.id for s in seg.steps]  # 'b-2' was absented; not reborn
    assert not _flagged(seg, "correction-unenforced: forbid@17")
    assert "satisfied: forbid@17" in seg.flags


def test_split_trims_a_child_that_straddles_the_cut():
    seg = _seg(
        SegStep(
            id="v",
            spans=((10.0, 20.0),),
            children=(SegStep(id="c", spans=((12.0, 18.0),)),),
        )
    )
    out = replay(seg, [split(15)])
    head, tail = out.steps
    assert [c.spans for c in head.children] == [((12.0, 15.0),)]
    assert tail.children == ()
    assert not _flagged(out, "inconsistent")


def test_the_consistency_check_flags_a_child_outside_its_parent():
    seg = _seg(
        SegStep(
            id="v",
            spans=((10.0, 20.0),),
            children=(SegStep(id="c", spans=((18.0, 25.0),)),),
        )
    )
    out = replay(seg, [absent(99)])
    assert "inconsistent: child 'c' of 'v' lies outside its parent" in (
        inconsistencies(out)
    )


def test_merge_into_a_named_step_keeps_that_steps_record():
    seg = segment(boundaries=CUTS, steps=NAMES, corrections=[split(15), merge(20)])
    chorus = seg.steps[2]
    assert (chorus.id, chorus.name, chorus.spans) == (
        "chorus",
        "chorus",
        ((15.0, 30.0),),
    )
    assert chorus.source == "explicit"
    assert "split_from" not in chorus.evidence


def test_a_pin_anchor_must_lie_strictly_before_its_span_end():
    with pytest.raises(ValueError, match="inside its span"):
        pin((0, 10), anchor_t=10)


def test_merge_exactly_on_a_cut_that_joins_nothing_does_not_fall_back():
    """The human struck THAT cut (here the edge of a gap); a meeting cut 1 s
    away is not what they meant, even though it is within the tolerance."""
    seg = _seg(
        SegStep(id="a", spans=((0.0, 10.0),)),
        SegStep(id="b", spans=((10.0, 11.0),)),
        SegStep(id="c", spans=((11.5, 20.0),)),
    )
    out = replay(seg, [merge(11)])
    assert out.steps == seg.steps and out.boundaries == seg.boundaries
    assert out.flags == (
        "correction-unmatched: merge@11 (no two steps meet at that exact cut)",
    )
    # one millisecond off that cut, the nearest meeting cut is still found
    assert "corrected: merge@10.999" in replay(seg, [merge(10.999)]).flags


def test_merge_exactly_on_an_end_of_a_boundaries_only_segmentation_is_unmatched():
    out = replay(Segmentation(boundaries=(0.0, 10.0, 11.0)), [merge(11)])
    assert out.boundaries == (0.0, 10.0, 11.0)
    assert out.flags == (
        "correction-unmatched: merge@11 (that is an end, not a cut between steps)",
    )


# ── #36: a log that changes nothing leaves the output alone ─────────────────


def test_a_no_op_log_leaves_the_output_exactly_as_without_one():
    plain = segment(boundaries=[0, 10, 10, 20])  # a duplicate cut: an empty step
    logged = segment(boundaries=[0, 10, 10, 20], corrections=[absent(99)])
    assert logged.boundaries == plain.boundaries == (0.0, 10.0, 10.0, 20.0)
    assert logged.steps == plain.steps
    assert [f for f in logged.flags if not f.startswith("correction-")] == list(
        plain.flags
    )


def test_every_segmentation_is_checked_log_or_not():
    """The consistency check runs on every result, not only after a replay."""
    plain = segment(boundaries=[0, 10, 10, 20])
    assert "inconsistent: step 'seg-2' has an empty span at 10" in plain.flags


@pytest.mark.parametrize(
    "kwargs",
    [
        {"verb": "split", "anchor_t": True},
        {"verb": "split", "anchor_t": 1.0, "author": 5},
        {"verb": "split", "anchor_t": 1.0, "step_id": 3},
    ],
)
def test_correction_fields_have_their_types(kwargs):
    with pytest.raises(ValueError, match="must be"):
        Correction(**kwargs)


def test_the_overlap_check_scales_to_thousands_of_steps():
    import time

    n = 5000
    steps = tuple(SegStep(id=f"s{i}", spans=((float(i), i + 1.0),)) for i in range(n))
    seg = Segmentation(steps=steps, boundaries=tuple(float(i) for i in range(n + 1)))
    started = time.perf_counter()
    assert inconsistencies(seg) == ()
    assert time.perf_counter() - started < 1.0  # all-pairs took ~seconds here
