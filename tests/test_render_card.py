"""The card renderer: print HTML for any document, and the optional PDF."""

from __future__ import annotations

import builtins
import shutil
import subprocess
import sys

import pytest

from paces import render_card as card
from paces.model import (
    Anchor,
    ArtifactRef,
    Cue,
    Measure,
    Step,
    StepDocument,
    dumps_document,
)
from paces.tools import render


def _doc(**extra) -> StepDocument:
    return StepDocument(
        id="circuit",
        title="Bodyweight <circuit>",
        steps=[
            Step(id="warm", name="Warm-up", duration=Measure(value="30", unit="second")),
            Step(
                id="round",
                name="Round",
                duration=Measure(value="33", unit="rep"),
                repeat=3,
                steps=[
                    Step(
                        id="squat",
                        name="Squat",
                        duration=Measure(value="10", unit="rep"),
                        description="Sit back.",
                        artifacts=[ArtifactRef(role="poster", uri="media/squat.jpg")],
                    ),
                    Step(
                        id="push",
                        name="Push-up",
                        duration=Measure(value="1", unit="rep"),
                        optional=True,
                    ),
                ],
            ),
        ],
        cues=[
            Cue(id="k", kind="warning", text="Knees out.", anchor=Anchor(step="squat")),
            Cue(id="b", kind="count", text="Breathe.", anchor=Anchor(step="round")),
        ],
        **extra,
    )


def test_card_is_print_html_with_the_structure_and_the_steps():
    page = card.render_card(_doc())
    assert "@page { size: A4;" in page
    assert "<script" not in page
    assert "Bodyweight &lt;circuit&gt;" in page  # escaped
    assert "3 × Round" in page and "(3 × 33 reps in all)" in page
    assert "10 reps" in page and "1 rep<" in page and "30 seconds" in page
    assert page.index("Warm-up") < page.index("Squat") < page.index("Push-up")
    assert 'class="cue caution"' in page and "Knees out." in page
    assert "Breathe." in page  # the group's own cue
    assert "optional" in page


def test_letter_paper_and_a_bad_paper():
    assert "size: Letter" in card.render_card(_doc(), paper="letter")
    with pytest.raises(ValueError, match="paper"):
        card.render_card(_doc(), paper="tabloid")


def test_resources_and_notes_are_printed_and_omitted_without():
    from paces.model import Resource

    bare = card.render_card(_doc())
    assert "What you need" not in bare and "Notes" not in bare
    page = card.render_card(
        _doc(
            resources=[
                Resource(id="mat", name="A mat", optional=True),
                Resource(
                    id="w", name="<b>x</b>", quantity=Measure(value="8", unit="kg"), note="each"
                ),
            ],
            notes=["Do one round first.", "Stop if it hurts."],
        )
    )
    assert "What you need" in page and "A mat" in page and "(optional)" in page
    assert "8 kg · &lt;b&gt;x&lt;/b&gt;" in page and "— each" in page
    assert "Notes" in page and "Do one round first." in page


def test_a_cue_label_is_printed_beside_the_cue():
    doc = _doc()
    doc.cues[0].label = "Lowering"
    assert "<b>Lowering</b>" in card.render_card(doc)


def test_posters_are_embedded_and_the_column_exists_only_with_one(tmp_path):
    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "squat.jpg").write_bytes(b"\xff\xd8\xff")
    with_pic = card.render_card(_doc(), media_from=tmp_path)
    assert "data:image/jpeg;base64," in with_pic and 'class="pic"' in with_pic
    without = card.render_card(_doc())
    assert 'class="pic"' not in without and "<img" not in without


def test_posters_cannot_be_read_from_outside_the_media_root(tmp_path):
    (tmp_path / "secret.jpg").write_bytes(b"x")
    doc = _doc()
    doc.steps[1].steps[0].artifacts = [ArtifactRef(role="poster", uri="../secret.jpg")]
    sub = tmp_path / "doc"
    sub.mkdir()
    with pytest.raises(ValueError, match="media root"):
        card.render_card(doc, media_from=sub)
    # widening the root on purpose reads it
    assert "data:image/jpeg;base64," in card.render_card(doc, media_from=sub, media_root=tmp_path)


def _two_posters(tmp_path, names=("start.jpg", "end.jpg")):
    (tmp_path / "media").mkdir(exist_ok=True)
    for n in names:
        (tmp_path / "media" / n).write_bytes(b"\xff\xd8\xff" + n.encode())
    doc = _doc()
    doc.steps[1].steps[0].artifacts = [
        ArtifactRef(role="poster", uri=f"media/{n}") for n in names
    ]
    return doc


def test_two_posters_are_a_start_and_end_pair(tmp_path):
    page = card.render_card(_two_posters(tmp_path), media_from=tmp_path)
    assert page.count("<img") == 2
    assert page.index("Start") < page.index("End")
    assert "width:61mm" in page  # the picture column fits the pair


def test_one_poster_has_no_pair_labels_and_three_are_all_shown(tmp_path):
    one = card.render_card(_two_posters(tmp_path, ("a.jpg",)), media_from=tmp_path)
    assert one.count("<img") == 1 and ">Start<" not in one
    three = card.render_card(_two_posters(tmp_path, ("a.jpg", "b.jpg", "c.jpg")), media_from=tmp_path)
    assert three.count("<img") == 3 and ">Start<" not in three


def test_media_root_flag_reaches_the_card(tmp_path):
    import sys

    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "p.jpg").write_bytes(b"\xff\xd8\xff")
    (tmp_path / "doc").mkdir()
    doc = _doc()
    doc.steps[1].steps[0].artifacts = [ArtifactRef(role="poster", uri="../media/p.jpg")]
    path = tmp_path / "doc" / "d.json"
    path.write_text(dumps_document(doc), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "paces", "render", str(path), "--renderer", "card",
         "--output", str(tmp_path / "c.html"), "--media-root", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "data:image/jpeg;base64," in (tmp_path / "c.html").read_text(encoding="utf-8")


def test_strings_override():
    page = card.render_card(
        _doc(), strings={"steps": "Étapes", "units": {"rep": ["répétition", "répétitions"]}}
    )
    assert "Étapes" in page and "10 répétitions" in page


def test_render_tool_writes_html_and_returns_text_without_output(tmp_path):
    out = tmp_path / "c.html"
    assert render(_doc(), renderer="card", output=str(out), paper="letter") == str(out)
    assert "size: Letter" in out.read_text(encoding="utf-8")
    assert render(_doc(), renderer="card").startswith("<!doctype html>")


def test_pdf_without_the_extra_says_what_to_install(monkeypatch, tmp_path):
    real_import = builtins.__import__

    def refuse(name, *a, **k):
        if name == "pdfdol":
            raise ImportError("no pdfdol")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", refuse)
    with pytest.raises(RuntimeError, match=r"paces\[pdf\]"):
        render(_doc(), renderer="card", output=str(tmp_path / "c.pdf"))
    assert not (tmp_path / "c.pdf").exists()


def test_pdf_without_wkhtmltopdf_says_what_to_install(monkeypatch, tmp_path):
    pytest.importorskip("pdfdol")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="wkhtmltopdf"):
        render(_doc(), renderer="card", output=str(tmp_path / "c.pdf"))


needs_pdf = pytest.mark.skipif(
    shutil.which("wkhtmltopdf") is None, reason="wkhtmltopdf is not installed"
)


@needs_pdf
def test_pdf_is_a_real_pdf_on_the_chosen_paper(tmp_path):
    pytest.importorskip("pdfdol")
    out = tmp_path / "c.pdf"
    assert render(_doc(), renderer="card", output=str(out), paper="letter") == str(out)
    data = out.read_bytes()
    assert data.startswith(b"%PDF")
    pypdf = pytest.importorskip("pypdf")
    reader = pypdf.PdfReader(str(out))
    assert 1 <= len(reader.pages) <= 2
    width = float(reader.pages[0].mediabox.width)
    assert abs(width - 612) < 2  # Letter, in points
    assert "Squat" in reader.pages[0].extract_text()


@needs_pdf
def test_cli_renders_a_pdf(tmp_path):
    pytest.importorskip("pdfdol")
    doc = tmp_path / "d.json"
    doc.write_text(dumps_document(_doc()), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "paces", "render", str(doc), "--renderer", "card",
         "--output", str(tmp_path / "c.pdf")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "c.pdf").read_bytes().startswith(b"%PDF")


def test_the_fixture_is_a_valid_document():
    from paces.model import validate_document

    assert validate_document(_doc()) == []


def test_remote_posters_are_not_fetched_at_print_time():
    doc = _doc()
    doc.steps[1].steps[0].artifacts = [ArtifactRef(role="poster", uri="https://example.com/p.jpg")]
    page = card.render_card(doc)
    assert "example.com" not in page and "<img" not in page


def test_paper_is_refused_where_it_means_nothing():
    with pytest.raises(ValueError, match="paper"):
        render(_doc(), renderer="html", paper="a4")


def test_the_older_attrs_needs_list_is_still_read_when_there_are_no_resources():
    old = card.render_card(_doc(attrs={"render.card": {"needs": ["A mat"]}}))
    assert "What you need" in old and "<li>A mat</li>" in old
    assert "<li>A mat</li>" in card.render_card(_doc(attrs={"render.card": {"needs": "A mat"}}))
    card.render_card(_doc(attrs={"render.card": "nope"}))  # odd values never crash
