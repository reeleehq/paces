"""The flow renderer: the folder it writes, and the player's pure logic.

The player is vanilla JS; its pure part (``flow-core.js``) is run under node
when node is available, which is how the stop expansion, the clock and the
count formatting are pinned without a browser.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from paces.model import ArtifactRef, Measure, Step, StepDocument, loads_document
from paces.render_flow import PLAYER_FILES, default_strings, render_flow
from paces.tools import render

CORE_JS = Path(__file__).parent.parent / "paces" / "data" / "flow" / "flow-core.js"


def _circuit(**extra) -> StepDocument:
    return StepDocument(
        id="circuit",
        title="Bodyweight circuit",
        domain="workout",
        steps=[
            Step(
                id="warm", name="Warm-up", duration=Measure(value="30", unit="second")
            ),
            Step(
                id="round",
                name="Round",
                duration=Measure(value="10", unit="rep"),
                repeat=3,
                steps=[
                    Step(
                        id="squat",
                        name="Squat",
                        duration=Measure(value="10", unit="rep"),
                        artifacts=[
                            ArtifactRef(role="clip", uri="media/squat.mp4"),
                            ArtifactRef(role="poster", uri="media/squat.jpg"),
                        ],
                    ),
                    Step(
                        id="push",
                        name="Push-up",
                        duration=Measure(value="8", unit="rep"),
                    ),
                ],
            ),
        ],
        **extra,
    )


def test_writes_the_player_folder(tmp_path):
    out = render_flow(_circuit(), tmp_path / "out")
    for name in (*PLAYER_FILES, "document.json", "strings.json", "data.js"):
        assert (out / name).is_file(), name
    assert (
        loads_document((out / "document.json").read_text(encoding="utf-8"))
        == _circuit()
    )
    assert 'src="flow.js"' in (out / "index.html").read_text(encoding="utf-8")


def test_a_second_routine_is_only_a_different_document(tmp_path):
    other = StepDocument(id="other", title="Other", steps=[])
    a = render_flow(_circuit(), tmp_path / "a")
    b = render_flow(other, tmp_path / "b")
    for name in (*PLAYER_FILES, "strings.json"):
        assert (a / name).read_bytes() == (b / name).read_bytes(), name
    assert (a / "document.json").read_bytes() != (b / "document.json").read_bytes()


def test_player_files_name_no_particular_routine():
    words = re.compile(r"dance|que calor|kettlebell|workout|recipe|choreo", re.I)
    for name in (*PLAYER_FILES, "strings.json"):
        text = (CORE_JS.parent / name).read_text(encoding="utf-8")
        assert not words.search(text), f"{name} names a domain"


def test_strings_can_be_overridden_one_level_deep(tmp_path):
    out = render_flow(
        _circuit(),
        tmp_path,
        strings={"play": "Go", "units": {"rep": ["rep.", "reps."]}},
    )
    table = json.loads((out / "strings.json").read_text(encoding="utf-8"))
    assert table["play"] == "Go"
    assert table["units"]["rep"] == ["rep.", "reps."]
    assert table["units"]["eight"] == default_strings()["units"]["eight"]


def test_media_is_copied_to_the_same_relative_path(tmp_path):
    src = tmp_path / "doc"
    (src / "media").mkdir(parents=True)
    (src / "media" / "squat.mp4").write_bytes(b"v")
    (src / "media" / "squat.jpg").write_bytes(b"p")
    out = render_flow(_circuit(), tmp_path / "out", media_from=src)
    assert (out / "media" / "squat.mp4").read_bytes() == b"v"
    assert (out / "media" / "squat.jpg").read_bytes() == b"p"


def test_missing_media_is_named_in_a_warning(tmp_path):
    with pytest.warns(UserWarning, match="media/squat.mp4"):
        render_flow(_circuit(), tmp_path / "out")


def test_media_cannot_escape_the_output_folder(tmp_path):
    doc = _circuit()
    doc.steps[0].artifacts = [ArtifactRef(role="clip", uri="../../evil.mp4")]
    with pytest.raises(ValueError, match="media root"):
        render_flow(doc, tmp_path / "out", media_from=tmp_path)


def test_render_tool_flow_needs_an_output_folder(tmp_path):
    with pytest.raises(ValueError, match="output"):
        render(_circuit(), renderer="flow")
    assert render(_circuit(), renderer="flow", output=str(tmp_path / "o")) == str(
        tmp_path / "o"
    )


def test_unknown_renderer_lists_flow():
    with pytest.raises(ValueError, match="flow"):
        render(_circuit(), renderer="nope")


def test_cli_renders_flow_from_a_document_path(tmp_path):
    import sys

    doc = tmp_path / "d.json"
    doc.write_text(
        json.dumps(
            json.loads(
                __import__("paces.model", fromlist=["dumps_document"]).dumps_document(
                    _circuit()
                )
            )
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "paces",
            "render",
            str(doc),
            "--renderer",
            "flow",
            "--output",
            str(tmp_path / "site"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "site" / "document.json").is_file()


# ── the player's pure logic, under node ────────────────────────────────────

node = shutil.which("node")
needs_node = pytest.mark.skipif(node is None, reason="node is not installed")


def _js(expression: str, document: dict):
    script = (
        f"const C = require({json.dumps(str(CORE_JS))});"
        f"const doc = {json.dumps(document)};"
        f"console.log(JSON.stringify({expression}));"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _wire(doc: StepDocument) -> dict:
    return json.loads(doc.model_dump_json(by_alias=True, exclude_none=True))


@needs_node
def test_repeat_expands_into_rounds_of_the_children():
    got = _js(
        "C.buildStops(doc).map(s => [s.step.id, s.group, s.rounds.map(r => r.round + '/' + r.of).join()])",
        _wire(_circuit()),
    )
    assert got[0] == ["warm", 0, ""]
    assert got[1:] == [
        ["squat", 1, "1/3"],
        ["push", 1, "1/3"],
        ["squat", 1, "2/3"],
        ["push", 1, "2/3"],
        ["squat", 1, "3/3"],
        ["push", 1, "3/3"],
    ]


@needs_node
def test_clock_without_a_grid_uses_the_viewers_settings():
    settings = {"secondsPerRep": 3, "secondsPerStep": 40, "pace": "rep"}
    wire = _wire(_circuit())
    secs = _js(
        f"C.buildStops(doc).slice(0, 3).map(s => C.stopSeconds(doc, s, {json.dumps(settings)}))",
        wire,
    )
    assert secs == [30, 30, 24]  # seconds as given; 10 reps x 3; 8 reps x 3
    by_step = {**settings, "pace": "step"}
    assert (
        _js(f"C.stopSeconds(doc, C.buildStops(doc)[1], {json.dumps(by_step)})", wire)
        == 40
    )


@needs_node
def test_clock_with_a_grid_follows_the_tempo():
    doc = StepDocument(
        id="d",
        title="D",
        metric={"unit": "eight", "subdivisions": 8, "tempoBpm": "120"},
        steps=[Step(id="a", name="A", duration=Measure(value="2", unit="eight"))],
    )
    wire = _wire(doc)
    assert _js("C.stopSeconds(doc, C.buildStops(doc)[0], {})", wire) == 8
    assert _js("C.stopSeconds(doc, C.buildStops(doc)[0], {bpm: 240})", wire) == 4


@needs_node
def test_counts_use_the_documents_unit_and_the_strings_table():
    strings = default_strings()
    f = lambda v, u: _js(
        f"C.formatMeasure({{value: {json.dumps(v)}, unit: {json.dumps(u)}}}, {json.dumps(strings)})",
        {},
    )
    assert f("1", "rep") == "1 rep"
    assert f("7", "rep") == "7 reps"
    assert f("4", "eight") == "4 eights"
    assert f("3", "lap") == "3 lap"  # an unknown unit is shown as the document wrote it


@needs_node
def test_repeat_below_one_still_shows_the_step():
    doc = {
        "steps": [{"id": "a", "duration": {"value": "1", "unit": "rep"}, "repeat": -1}]
    }
    assert _js("C.buildStops(doc).length", doc) == 1


@needs_node
def test_nested_repeats_and_group_heads():
    leaf = lambda i: {"id": i, "duration": {"value": "1", "unit": "rep"}}
    doc = {
        "steps": [
            {
                "id": "outer",
                "repeat": 2,
                "duration": {"value": "1", "unit": "rep"},
                "steps": [
                    {
                        "id": "inner",
                        "repeat": 2,
                        "duration": {"value": "1", "unit": "rep"},
                        "steps": [leaf("x")],
                    },
                    leaf("y"),
                ],
            }
        ]
    }
    got = _js(
        "C.buildStops(doc).map(s => [s.step.id, s.rounds.map(r => r.step.id + r.round).join(), s.heads.map(h => h.id).join()])",
        doc,
    )
    assert [g[0] for g in got] == ["x", "x", "y", "x", "x", "y"]
    # the outer group's lead shows on the first stop of each outer round, the inner on each inner round
    assert got[0][2] == "outer,inner" and got[1][2] == "inner" and got[2][2] == ""
    # a new outer round leads with the outer group again
    assert got[3][2] == "outer,inner"


@needs_node
def test_deep_links_are_http_only_and_host_aware():
    f = lambda uri, t: _js(f"C.deepLink({{uri: {json.dumps(uri)}}}, {t})", {})
    assert f("https://youtu.be/abc", 65.9) == "https://youtu.be/abc?t=65"
    assert (
        f("https://www.youtube.com/watch?v=a", 5)
        == "https://www.youtube.com/watch?v=a&t=5"
    )
    assert (
        f("https://example.com/youtube-clone?x=1", 5)
        == "https://example.com/youtube-clone?x=1"
    )
    assert f("https://example.com/a.mp4", 5) == "https://example.com/a.mp4#t=5"
    assert f("javascript:alert(1)", 5) is None
    assert f("media/a.mp4", 5) is None


@needs_node
def test_media_picks_clip_with_its_poster_else_gif_else_poster():
    pick = lambda arts: _js("C.pickMedia(doc)", {"artifacts": arts})
    clip = {"role": "clip", "uri": "m/a.mp4"}
    assert pick([clip, {"role": "poster", "uri": "m/a.jpg"}]) == {
        "kind": "video",
        "src": "m/a.mp4",
        "mime": "video/mp4",
        "poster": "m/a.jpg",
    }
    assert (
        pick([{"role": "gif", "uri": "m/a.gif"}, {"role": "poster", "uri": "m/a.jpg"}])[
            "src"
        ]
        == "m/a.gif"
    )
    assert pick([{"role": "poster", "uri": "m/a.jpg"}])["src"] == "m/a.jpg"
    assert pick([]) is None


def test_data_js_carries_the_same_document_and_strings(tmp_path):
    out = render_flow(_circuit(), tmp_path)
    text = (out / "data.js").read_text(encoding="utf-8")
    payload = json.loads(text[len("window.PACES_FLOW = ") : text.rindex(";")])
    assert payload["document"] == json.loads(
        (out / "document.json").read_text(encoding="utf-8")
    )
    assert payload["strings"] == json.loads(
        (out / "strings.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize(
    "uri", ["/abs/a.mp4", "file:///a.mp4", "C:\\a.mp4", "\\\\host\\a.mp4"]
)
def test_non_relative_media_uris_are_not_shipped_and_are_named(tmp_path, uri):
    doc = _circuit()
    doc.steps[0].artifacts = [ArtifactRef(role="clip", uri=uri)]
    with pytest.warns(UserWarning, match="not shipped"):
        render_flow(doc, tmp_path / "out", media_from=tmp_path)


def test_media_source_cannot_climb_out_of_the_media_folder(tmp_path):
    (tmp_path / "secret.txt").write_text("s")
    src = tmp_path / "doc"
    src.mkdir()
    doc = _circuit()
    doc.steps[0].artifacts = [ArtifactRef(role="clip", uri="../secret.txt")]
    with pytest.raises(ValueError, match="media root"):
        render_flow(doc, tmp_path / "out", media_from=src)


def test_media_beside_the_document_is_shipped_when_the_root_is_widened(tmp_path):
    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "squat.mp4").write_bytes(b"v")
    (tmp_path / "doc").mkdir()
    doc = _circuit()
    doc.steps[1].steps[0].artifacts = [ArtifactRef(role="clip", uri="../media/squat.mp4")]
    out = render_flow(doc, tmp_path / "out", media_from=tmp_path / "doc", media_root=tmp_path)
    assert (out / "media" / "squat.mp4").read_bytes() == b"v"
    shipped = json.loads((out / "document.json").read_text(encoding="utf-8"))
    uris = [a["uri"] for s in shipped["steps"] for c in s.get("steps", []) for a in c.get("artifacts", [])]
    assert uris == ["media/squat.mp4"]  # the shipped document points inside the folder
    # and the caller's own document is untouched
    assert doc.steps[1].steps[0].artifacts[0].uri == "../media/squat.mp4"


def test_cli_media_flags_reach_the_renderers(tmp_path):
    import sys

    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "squat.mp4").write_bytes(b"v")
    (tmp_path / "doc").mkdir()
    doc = _circuit()
    doc.steps[1].steps[0].artifacts = [ArtifactRef(role="clip", uri="../media/squat.mp4")]
    path = tmp_path / "doc" / "d.json"
    path.write_text(__import__("paces.model", fromlist=["x"]).dumps_document(doc), encoding="utf-8")
    run = lambda *extra: subprocess.run(
        [sys.executable, "-m", "paces", "render", str(path), "--renderer", "flow",
         "--output", str(tmp_path / "site"), *extra], capture_output=True, text=True)
    refused = run()
    assert refused.returncode != 0 and "media root" in refused.stderr
    ok = run("--media-root", str(tmp_path))
    assert ok.returncode == 0, ok.stderr
    assert (tmp_path / "site" / "media" / "squat.mp4").is_file()


def test_without_a_base_an_escaping_uri_is_still_refused(tmp_path):
    (tmp_path / "secret.mp4").write_bytes(b"s")
    out = tmp_path / "out"
    out.mkdir()
    doc = _circuit()
    doc.steps[0].artifacts = [ArtifactRef(role="clip", uri="../secret.mp4")]
    with pytest.raises(ValueError, match="escapes the output folder"):
        render_flow(doc, out)


def test_a_media_root_that_does_not_contain_the_base_is_refused(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    doc = _circuit()
    with pytest.raises(ValueError, match="must contain"):
        render_flow(doc, tmp_path / "out", media_from=tmp_path / "a", media_root=tmp_path / "b")


def test_media_root_without_a_base_is_an_error_for_a_non_file_document(tmp_path):
    with pytest.raises(ValueError, match="media_from"):
        render(_circuit(), renderer="flow", output=str(tmp_path / "o"), media_root=str(tmp_path))


def test_a_symlink_inside_the_root_keeps_its_own_name(tmp_path):
    (tmp_path / "store").mkdir()
    (tmp_path / "store" / "x.mp4").write_bytes(b"v")
    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "squat.mp4").symlink_to(tmp_path / "store" / "x.mp4")
    doc = _circuit()
    doc.steps[1].steps[0].artifacts = [ArtifactRef(role="clip", uri="media/squat.mp4")]
    out = render_flow(doc, tmp_path / "out", media_from=tmp_path)
    assert (out / "media" / "squat.mp4").read_bytes() == b"v"
    assert "store/x.mp4" not in (out / "document.json").read_text(encoding="utf-8")


def test_media_cannot_overwrite_the_players_own_files(tmp_path):
    (tmp_path / "index.html").write_text("not the player")
    doc = _circuit()
    doc.steps[0].artifacts = [ArtifactRef(role="clip", uri="index.html")]
    with pytest.raises(ValueError, match="player's own file"):
        render_flow(doc, tmp_path / "out", media_from=tmp_path)


def test_two_files_cannot_ship_to_one_path(tmp_path):
    (tmp_path / "doc" / "media").mkdir(parents=True)
    (tmp_path / "media").mkdir()
    (tmp_path / "doc" / "media" / "a.mp4").write_bytes(b"1")
    (tmp_path / "media" / "a.mp4").write_bytes(b"2")
    doc = _circuit()
    doc.steps[0].artifacts = [ArtifactRef(role="clip", uri="media/a.mp4")]
    doc.steps[1].steps[0].artifacts = [ArtifactRef(role="clip", uri="../media/a.mp4")]
    with pytest.raises(ValueError, match="both be shipped"):
        render_flow(doc, tmp_path / "out", media_from=tmp_path / "doc", media_root=tmp_path)


def test_widening_the_root_leaves_in_base_uris_alone(tmp_path):
    (tmp_path / "doc" / "media").mkdir(parents=True)
    (tmp_path / "doc" / "media" / "a.mp4").write_bytes(b"1")
    doc = _circuit()
    doc.steps[0].artifacts = [ArtifactRef(role="clip", uri="media/a.mp4")]
    out = render_flow(doc, tmp_path / "out", media_from=tmp_path / "doc", media_root=tmp_path)
    assert (out / "media" / "a.mp4").is_file() and not (out / "doc").exists()


def test_rewritten_uris_are_url_quoted(tmp_path):
    (tmp_path / "media").mkdir()
    (tmp_path / "doc").mkdir()
    (tmp_path / "media" / "a b#1.mp4").write_bytes(b"1")
    doc = _circuit()
    doc.steps[0].artifacts = [ArtifactRef(role="clip", uri="../media/a b#1.mp4")]
    out = render_flow(doc, tmp_path / "out", media_from=tmp_path / "doc", media_root=tmp_path)
    assert "media/a%20b%231.mp4" in (out / "document.json").read_text(encoding="utf-8")
    assert (out / "media" / "a b#1.mp4").is_file()
