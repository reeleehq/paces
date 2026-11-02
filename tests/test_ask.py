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
    load_answers,
    propose,
    render_ask_page,
)
from paces.corrections import split
from paces.model import decimal_str
from paces.segmenters import segment

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
    assert proposal["snap"]["windowS"] == "1.5"


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


def test_render_refuses_what_is_not_a_proposal():
    with pytest.raises(ValueError, match="PacesAskProposal"):
        render_ask_page({"cuts": []})


# ── answers back in ─────────────────────────────────────────────────────────


def _answers(**overrides):
    return {
        "kind": ANSWERS_KIND,
        "k": 4,
        "corrections": [{"verb": "split", "anchorT": "15"}],
        **overrides,
    }


def test_load_answers_gives_k_and_a_validated_log():
    k, log = load_answers(_answers())
    assert k == 4 and log == (split(15),)


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
    values = [0, 15, 95.8, 0.8550444, 10.1235, 1e-7, 123.4567, 7.0005]
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
        "absent": ["intro"],
        "at": "2026-11-02T10:00:00Z",
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
    k, log = load_answers(answers)
    seg = segment(boundaries=CUTS, steps=NAMES, corrections=log)
    assert k == 3
    assert seg.boundaries == (0.0, 10.0, 16.0, 24.0, 30.0)
    assert not [f for f in seg.flags if f.startswith("correction-")]


@needs_node
def test_js_an_unset_k_is_null_not_zero():
    proposal = propose(segment(boundaries=CUTS))
    state = {"k": None, "struck": [], "added": [], "absent": [], "at": ""}
    answers = _run_js(f"core.buildAnswers({json.dumps(proposal)}, {json.dumps(state)})")
    assert answers["k"] is None and answers["corrections"] == []
    assert load_answers(answers) == (None, ())
