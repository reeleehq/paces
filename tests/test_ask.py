"""The ask segmenter's interaction half: proposal → page → answers (#10)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from importlib.resources import files

import pytest

from paces import tools
from paces.ask import (
    ANSWERS_KIND,
    CONTRACT_VERSION,
    Answers,
    load_answers,
    propose,
    render_ask_page,
)
from paces.corrections import (
    DFLT_MERGE_TOLERANCE_S,
    DFLT_MIN_STEP_S,
    split,
    time_str,
)
from paces.model import decimal_str
from paces.segmenters import Segmentation, segment

CUTS = [0, 10, 20, 30]
NAMES = ["intro", "verse", "chorus"]
GRID = {"unit": "eight", "subdivisions": 8, "tempoBpm": "120", "origin": "0"}
ASK_JS = files("paces") / "data" / "ask" / "ask.js"


# ── propose: what the machine pre-computes ──────────────────────────────────


def test_k_comes_from_the_steps_with_its_evidence():
    proposal = propose(segment(boundaries=CUTS, steps=NAMES))
    assert proposal["k"] == 3
    assert "explicit" in proposal["kEvidence"]
    assert proposal["cuts"] == ["10", "20"]
    assert [s["id"] for s in proposal["steps"]] == NAMES
    assert proposal["steps"][0]["spans"] == [["0", "10"]]


def test_k_is_none_when_there_is_nothing_to_count():
    proposal = propose(segment("video.mp4"))  # the refused state
    assert proposal["k"] is None
    assert proposal["cuts"] == [] and proposal["extent"] is None


def test_snap_targets_add_the_grid_ticks_to_the_cuts():
    proposal = propose(segment(boundaries=CUTS, grid=GRID))  # 4 s per eight
    targets = proposal["snap"]["targets"]
    assert targets == ["0", "4", "8", "10", "12", "16", "20", "24", "28"]
    assert proposal["snap"]["windowS"] == time_str(DFLT_MERGE_TOLERANCE_S)


def test_the_proposal_carries_the_contract():
    proposal = propose(segment(boundaries=CUTS))
    assert proposal["version"] == CONTRACT_VERSION
    assert proposal["answersKind"] == ANSWERS_KIND
    assert proposal["minStepS"] == time_str(DFLT_MIN_STEP_S)


def test_cuts_are_deduped_after_rounding_and_k_counts_the_deduped():
    proposal = propose(Segmentation(boundaries=(0, 10, 10.0001, 9.9999, 20)))
    assert proposal["cuts"] == ["10"]
    assert proposal["k"] == 2 and proposal["extent"] == ["0", "20"]


def test_a_too_dense_grid_falls_back_to_cuts_only():
    proposal = propose(segment(boundaries=CUTS, grid=GRID), max_grid_ticks=3)
    assert proposal["snap"]["targets"] == ["10", "20"]


def test_the_proposal_is_json_with_no_floats():
    proposal = propose(segment(boundaries=[0, 10.123456, 20], grid=GRID))
    text = json.dumps(proposal)
    assert not re.search(r":\s*-?\d+\.\d", text)  # every time is a string
    assert "10.123" in proposal["cuts"]


# ── the page ────────────────────────────────────────────────────────────────


def test_the_page_is_self_contained_and_carries_the_proposal():
    proposal = propose(segment(boundaries=CUTS, steps=NAMES), media="v.mp4")
    page = render_ask_page(proposal, author="user:thor")
    assert "{{" not in page  # every placeholder filled
    assert not re.search(r"""(src|href)=["']https?:""", page)  # nothing fetched
    data = re.search(
        r'<script type="application/json" id="proposal">(.*?)</script>', page, re.S
    ).group(1)
    assert json.loads(data) == {**proposal, "author": "user:thor"}


def test_a_title_cannot_break_out_of_the_page():
    evil = "</script><script>alert(1)</script>"
    page = render_ask_page(propose(segment(boundaries=CUTS), title=evil))
    assert evil not in page
    assert page.count("<script") == 2  # the data block and the page script


@pytest.mark.parametrize("title", ["{{js}}", "{{data}}", "{{css}}{{title}}"])
def test_a_placeholder_in_the_title_stays_text(title):
    page = render_ask_page(propose(segment(boundaries=CUTS), title=title))
    assert page.count("function timeStr") == 1  # the script went in once
    assert f"<h1>{title}</h1>" in page


def test_render_refuses_what_is_not_a_proposal():
    with pytest.raises(ValueError, match="PacesAskProposal"):
        render_ask_page({"cuts": []})
    with pytest.raises(ValueError, match="version"):
        render_ask_page({**propose(segment(boundaries=CUTS)), "version": 2})


# ── answers back in ─────────────────────────────────────────────────────────


def _answers(**overrides):
    return {
        "kind": ANSWERS_KIND,
        "version": CONTRACT_VERSION,
        "k": 4,
        "corrections": [{"verb": "split", "anchorT": "15"}],
        **overrides,
    }


def test_load_answers_gives_k_and_a_validated_log():
    assert load_answers(_answers()) == Answers(k=4, corrections=(split(15),))


def test_load_answers_reads_tapped_boundaries():
    got = load_answers(_answers(corrections=[], boundaries=["0", "10", "20.5"]))
    assert got.boundaries == (0.0, 10.0, 20.5)


@pytest.mark.parametrize(
    "answers, match",
    [
        ({"k": 3}, "PacesAskAnswers"),
        (_answers(k=0), "positive integer"),
        (_answers(k=True), "positive integer"),
        (_answers(k="3"), "positive integer"),
        (_answers(extra=1), "unknown answers keys"),
        (_answers(corrections=[{"verb": "split"}]), "missing"),
        ([], "PacesAskAnswers"),
        ({k: v for k, v in _answers().items() if k != "version"}, "version"),
        (_answers(version=2), "version"),
        (_answers(boundaries=["0"]), "2 or more"),
        (_answers(boundaries=["0", "x"]), "times in seconds"),
        (_answers(boundaries=["10", "5"]), "increasing"),
        (_answers(boundaries=["-1", "5"]), "increasing"),
    ],
)
def test_bad_answers_fail_before_any_rerun(answers, match):
    with pytest.raises(ValueError, match=match):
        load_answers(answers)


def test_tool_ask_writes_the_page(tmp_path):
    seg = tools.segment(boundaries=json.dumps(CUTS), steps=json.dumps(NAMES))
    out = tools.ask(seg, media="v.mp4", output=str(tmp_path / "ask.html"))
    assert "PacesAskProposal" in (tmp_path / "ask.html").read_text()
    assert out == str(tmp_path / "ask.html")


def test_tool_segment_takes_the_answers(tmp_path):
    path = tmp_path / "answers.json"
    path.write_text(json.dumps(_answers()))
    payload = tools.segment(
        boundaries=json.dumps(CUTS),
        corrections=json.dumps([{"verb": "merge", "anchorT": "20"}]),
        answers=str(path),
    )
    # the explicit log runs first, the answers after it
    assert [f for f in payload["flags"] if f.startswith("corrected")] == [
        "corrected: merge@20",
        "corrected: split@15",
    ]
    assert payload["boundaries"] == [0.0, 10.0, 15.0, 30.0]
    assert "ignored: k" in payload["flags"]  # no segmenter reads k yet: said so


def test_an_explicit_k_wins_over_the_answered_one(monkeypatch):
    seen = {}
    real = tools.segment_module.segment

    def _spy(*args, **kwargs):
        seen["k"] = kwargs["k"]
        return real(*args, **kwargs)

    monkeypatch.setattr(tools.segment_module, "segment", _spy)
    tools.segment(boundaries=json.dumps(CUTS), answers=json.dumps(_answers()), k=7)
    assert seen["k"] == 7
    tools.segment(boundaries=json.dumps(CUTS), answers=json.dumps(_answers()))
    assert seen["k"] == 4


def test_tool_segment_uses_answered_boundaries_unless_given():
    answers = json.dumps(_answers(corrections=[], boundaries=["0", "12", "30"]))
    assert tools.segment("v.mp4", answers=answers)["boundaries"] == [0.0, 12.0, 30.0]
    given = tools.segment(boundaries=json.dumps(CUTS), answers=answers)
    assert given["boundaries"] == [0.0, 10.0, 20.0, 30.0]


# ── the page's pure core, run in node ───────────────────────────────────────

node = shutil.which("node")
needs_node = pytest.mark.skipif(node is None, reason="node is not installed")


def _run_js(expression: str):
    script = (
        f"const core = require({json.dumps(str(ASK_JS))});\n"
        f"process.stdout.write(JSON.stringify({expression}));"
    )
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, check=True
    )
    return json.loads(done.stdout)


@needs_node
def test_js_time_format_matches_the_python_wire_format():
    values = [0, 15, 95.8, 0.8550444, 10.1235, 1e-7, 123.4567, 7.0005, 59.9996]
    # exact binary ties: Python's format rounds half-even, toFixed rounds up
    values += [10.0625, 0.0625, 0.1875, 0.3125, 2.5625, 1023.9375, 0.0005]
    # values that round to zero carry no sign, in either language (#40)
    values += [-0.0004, -0.0, -1e-9]
    got = _run_js(f"{json.dumps(values)}.map(core.timeStr)")
    assert got == [decimal_str(v, places=3) for v in values]


@needs_node
def test_js_snap_goes_to_the_nearest_target_within_the_window():
    got = _run_js(
        "[core.snap(14.6, [10, 16, 20], 1.5), core.snap(13, [10, 16, 20], 1.5)]"
    )
    assert got == [{"t": 16, "snapped": True}, {"t": 13, "snapped": False}]


@needs_node
def test_js_answers_load_and_replay_in_python():
    """The page's answers are exactly what load_answers + segment expect."""
    proposal = propose(segment(boundaries=CUTS, steps=NAMES))
    state = {
        "k": 3,
        "struck": ["20"],
        "added": ["24", "16", "16"],  # out of order, and a double tap
        "absent": ["0"],  # rows, not ids: "intro" is row 0
        "at": "2026-11-02T10:00:00Z",
        "kTouched": True,
    }
    answers = _run_js(
        f"core.buildAnswers({json.dumps({**proposal, 'author': 'user:t'})}, "
        f"{json.dumps(state)})"
    )
    assert [(c["verb"], c["anchorT"]) for c in answers["corrections"]] == [
        ("absent", "5"),
        ("merge", "20"),
        ("split", "16"),
        ("split", "24"),
    ]
    assert all(c["author"] == "user:t" for c in answers["corrections"])
    got = load_answers(answers)
    seg = segment(boundaries=CUTS, steps=NAMES, corrections=got.corrections)
    assert got.k == 3 and got.boundaries is None
    assert seg.boundaries == (0.0, 10.0, 16.0, 24.0, 30.0)
    assert not [f for f in seg.flags if f.startswith("correction-")]


@needs_node
def test_js_an_unset_k_is_null_not_zero():
    proposal = propose(segment(boundaries=CUTS))
    state = {"k": None, "struck": [], "added": [], "absent": [], "at": ""}
    answers = _run_js(f"core.buildAnswers({json.dumps(proposal)}, {json.dumps(state)})")
    assert answers["k"] is None and answers["corrections"] == []
    assert load_answers(answers) == Answers(k=None)


@needs_node
def test_js_mmss_never_shows_sixty_seconds():
    got = _run_js("[59.96, 119.99, 5, 0, 61.04].map(core.mmss)")
    assert got == ["1:00.0", "2:00.0", "0:05.0", "0:00.0", "1:01.0"]


# ── the reducer: every state decision the page makes, run in node ───────────


def _reduce(proposal: dict, actions: list[dict]) -> list[dict]:
    """Each action's ``{state, message, fresh}``, applied in order from a fresh state."""
    return _run_js(
        f"(() => {{ const p = {json.dumps(proposal)}; let s = core.freshState(p);\n"
        f"return {json.dumps(actions)}.map((a) => {{ const out = core.reduce(p, s, a);"
        " s = out.state; return out; }); })()"
    )


def _answers_after(proposal: dict, actions: list[dict]) -> dict:
    return _run_js(
        f"(() => {{ const p = {json.dumps(proposal)}; let s = core.freshState(p);\n"
        f"for (const a of {json.dumps(actions)}) s = core.reduce(p, s, a).state;"
        " return core.buildAnswers(p, s); })()"
    )


def _named():
    return propose(segment(boundaries=CUTS, steps=NAMES))


@needs_node
def test_js_refused_state_taps_become_boundaries_and_reach_segment():
    """B1: with nothing proposed, the taps are not lost — they are the cuts."""
    proposal = propose(segment("video.mp4"))
    actions = [
        {"type": "duration", "seconds": 30.0},
        {"type": "tap", "t": 20},
        {"type": "tap", "t": 10},
    ]
    answers = _answers_after(proposal, actions)
    assert answers["boundaries"] == ["0", "10", "20", "30"]
    assert answers["corrections"] == []
    payload = tools.segment("video.mp4", answers=json.dumps(answers))
    assert payload["boundaries"] == [0.0, 10.0, 20.0, 30.0]


@needs_node
def test_js_a_tap_outside_the_extent_is_refused_and_says_why():
    proposal = propose(segment(boundaries=[5, 10, 20, 30]))
    [out] = _reduce(proposal, [{"type": "tap", "t": 2}])
    assert out["state"]["added"] == []
    assert "outside the part being checked" in out["message"]


@needs_node
def test_js_a_struck_cut_is_not_a_snap_target():
    """M1: strike 20, tap near it — the cut moves rather than coming back."""
    near = _reduce(_named(), [{"type": "tap", "t": 19.5}])
    assert near[0]["state"]["added"] == [] and "already a cut" in near[0]["message"]
    moved = _reduce(
        _named(), [{"type": "strike", "cut": "20"}, {"type": "tap", "t": 19.5}]
    )
    assert moved[-1]["state"]["added"] == ["19.5"]
    assert moved[-1]["state"]["struck"] == ["20"]


@needs_node
def test_js_absent_steps_guard_their_cuts_and_their_inside():
    """M2: no merge at an absent step's edge, no split inside it."""
    out = _reduce(
        _named(),
        [
            {"type": "absent", "index": 1, "on": True},  # 10–20
            {"type": "strike", "cut": "10"},
            {"type": "strike", "cut": "20"},
            {"type": "tap", "t": 15},
        ],
    )
    assert out[0]["state"]["absent"] == ["1"]
    for refused in out[1:]:
        assert refused["state"] == out[0]["state"]
    assert "borders" in out[1]["message"] and "borders" in out[2]["message"]
    assert "inside a step you marked" in out[3]["message"]
    # and the other way round: a struck edge or an added cut blocks marking it
    struck_first = _reduce(
        _named(),
        [
            {"type": "strike", "cut": "10"},
            {"type": "absent", "index": 1, "on": True},
        ],
    )
    assert struck_first[-1]["state"]["absent"] == []
    added_first = _reduce(
        _named(),
        [{"type": "tap", "t": 15}, {"type": "absent", "index": 1, "on": True}],
    )
    assert added_first[-1]["state"]["absent"] == []


@needs_node
def test_js_a_step_with_no_span_cannot_be_marked_absent():
    proposal = _named()
    proposal["steps"][0]["spans"] = []
    [out] = _reduce(proposal, [{"type": "absent", "index": 0, "on": True}])
    assert out["state"]["absent"] == [] and "no time" in out["message"]


@needs_node
def test_js_a_tap_within_min_step_of_a_cut_is_ignored():
    """M3: a double tap is not two cuts; a struck cut is not a cut."""
    out = _reduce(
        _named(),
        [
            {"type": "tap", "t": 15},
            {"type": "tap", "t": 15.1},
            {"type": "strike", "cut": "20"},
            {"type": "tap", "t": 21.6},  # 1.6 s from 20: beyond the snap window
            {"type": "tap", "t": 21.7},
        ],
    )
    assert out[1]["state"]["added"] == ["15"]
    assert f"within {time_str(DFLT_MIN_STEP_S)} s" in out[1]["message"]
    assert out[-1]["state"]["added"] == ["15", "21.6"]


@needs_node
def test_js_k_is_sent_only_once_the_human_touched_it():
    """M4: the machine's guess pre-fills the field but is not an answer."""
    untouched = _answers_after(_named(), [])
    assert untouched["k"] is None
    confirmed = _answers_after(_named(), [{"type": "setK", "value": "3"}])
    assert confirmed["k"] == 3
    assert confirmed["version"] == CONTRACT_VERSION
    assert confirmed["kind"] == ANSWERS_KIND


@needs_node
def test_js_start_over_can_be_undone():
    """M5: Start over resets everything, k included, and keeps one Undo."""
    out = _reduce(
        _named(),
        [
            {"type": "setK", "value": "5"},
            {"type": "strike", "cut": "10"},
            {"type": "startOver"},
            {"type": "undoStartOver"},
        ],
    )
    before, reset, undone = out[1]["state"], out[2]["state"], out[3]["state"]
    assert reset["k"] == 3 and not reset["kTouched"] and reset["struck"] == []
    assert reset["previous"]["struck"] == ["10"]
    assert undone == {**before, "previous": None}
    # anything done after Start over closes its Undo
    later = _reduce(_named(), [{"type": "startOver"}, {"type": "tap", "t": 15}])
    assert later[-1]["state"]["previous"] is None


@needs_node
def test_js_only_the_just_added_cut_is_fresh():
    out = _reduce(_named(), [{"type": "tap", "t": 15}, {"type": "setK", "value": "4"}])
    assert out[0]["fresh"] == "15" and out[1]["fresh"] is None


# ── regressions from the second review of #37 ───────────────────────────────


@needs_node
def test_js_repeated_names_are_separate_rows():
    """verse/chorus/verse: each occurrence is marked on its own, and replays."""
    names = ["verse", "chorus", "verse"]
    proposal = propose(segment(boundaries=CUTS, steps=names))
    # ids are unique now (#47), but rows stay the key: names still repeat
    assert [s["id"] for s in proposal["steps"]] == ["verse", "chorus", "verse-2"]
    answers = _answers_after(proposal, [{"type": "absent", "index": 2, "on": True}])
    assert [(c["verb"], c["anchorT"]) for c in answers["corrections"]] == [
        ("absent", "25")
    ]
    seg = segment(
        boundaries=CUTS, steps=names, corrections=load_answers(answers).corrections
    )
    assert [s.spans for s in seg.steps] == [((0.0, 10.0),), ((10.0, 20.0),)]
    # the guard checks the row marked, not the first row with that id
    struck = _reduce(
        proposal,
        [{"type": "absent", "index": 2, "on": True}, {"type": "strike", "cut": "20"}],
    )
    assert struck[-1]["state"]["struck"] == []
    assert "borders" in struck[-1]["message"]


@needs_node
def test_js_keep_is_refused_while_a_moved_cut_sits_next_to_it():
    proposal = _named()
    steps = _reduce(
        proposal,
        [
            {"type": "strike", "cut": "10"},
            {"type": "tap", "t": 10.1},  # the move
            {"type": "keep", "cut": "10"},
        ],
    )
    assert steps[-1]["state"]["struck"] == ["10"]
    assert "Remove that one first" in steps[-1]["message"]
    answers = _answers_after(
        proposal, [{"type": "strike", "cut": "10"}, {"type": "tap", "t": 10.1}]
    )
    seg = segment(
        boundaries=CUTS, steps=NAMES, corrections=load_answers(answers).corrections
    )
    assert not [f for f in seg.flags if f.startswith("correction-")]
    assert 10.1 in seg.boundaries and 10.0 not in seg.boundaries


@needs_node
def test_js_taps_past_the_media_end_are_not_sent():
    proposal = propose(segment("video.mp4"))  # refused: taps become boundaries
    out = _reduce(
        proposal,
        [
            {"type": "duration", "seconds": 30},
            {"type": "tap", "t": 10},
            {"type": "tap", "t": 25},
            {"type": "duration", "seconds": 22},  # a shorter file opened
        ],
    )
    assert "will not be sent" in out[-1]["message"]
    answers = _answers_after(
        proposal,
        [
            {"type": "duration", "seconds": 30},
            {"type": "tap", "t": 10},
            {"type": "tap", "t": 25},
            {"type": "duration", "seconds": 22},
        ],
    )
    assert answers["boundaries"] == ["0", "10", "22"]


def test_answered_boundaries_refuse_booleans():
    with pytest.raises(ValueError, match="times in seconds"):
        load_answers(
            {
                "kind": ANSWERS_KIND,
                "version": 1,
                "corrections": [],
                "boundaries": [0, True],
            }
        )


def test_propose_takes_the_min_step_as_a_keyword():
    assert propose(segment(boundaries=CUTS), min_step_s=0.5)["minStepS"] == "0.5"


def test_the_status_line_stays_on_screen():
    css = (files("paces") / "data" / "ask" / "ask.css").read_text()
    assert re.search(r"#status \{[^}]*position: sticky", css)
