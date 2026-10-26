"""The subtitle / transcript cue segmenters (issue #6)."""

from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from paces import tools
from paces.cues import detect_cues, normalize_timed_text
from paces.segmenters import capabilities, segment

SRT = """1
00:00:00,000 --> 00:00:05,000
Hi everyone, welcome back.

2
00:00:12,000 --> 00:00:18,000
Now we start with the basic step.

3
00:00:20,000 --> 00:00:24,000
Keep your weight forward.

4
00:00:40,000 --> 00:00:46,000
Step two: add the turn.

5
00:01:10,000 --> 00:01:15,000
And finally, put it together.
"""


def test_srt_subtitles_become_proposed_named_spans():
    seg = segment("v.mp4", metadata={"subtitles": SRT})
    assert seg.method == "subtitle-cues"
    assert [s.name for s in seg.steps] == [
        "we start with the basic step",
        "add the turn",
        "put it together",
    ]
    assert seg.steps[0].spans == ((12.0, 40.0),)
    assert seg.boundaries == (12.0, 40.0, 70.0, 75.0)
    assert "proposed-uncertain" in seg.flags
    assert seg.confidence < 0.9  # a proposer, not an authority


def test_transcript_cue_dicts_use_the_transcript_capability():
    cues = [
        {"start": 0, "end": 5, "text": "Intro"},
        {"start": 20, "end": 25, "text": "First, the stance."},
        {"start": 60, "end": 65, "text": "Next, the turn."},
    ]
    seg = segment(transcript=cues)
    assert seg.method == "transcript-cues"
    assert [s.name for s in seg.steps] == ["the stance", "the turn"]
    assert seg.steps[0].source == "transcript-cues"


def test_srt_file_path_is_read(tmp_path):
    path = tmp_path / "talk.srt"
    path.write_text(SRT, encoding="utf-8")
    seg = segment(transcript=str(path))
    assert len(seg.steps) == 3


def test_no_markers_is_the_refused_state_not_an_invention():
    seg = segment(transcript=[{"start": 0, "end": 5, "text": "Just chatting."}])
    assert seg.steps == () and seg.boundaries == ()
    assert "no-signal" in seg.flags


def test_close_cues_fold_into_one_step():
    rows = [
        {"start": 10, "end": 12, "text": "Now we begin."},
        {"start": 14, "end": 16, "text": "Next keep going."},
    ]
    assert [r["start"] for r in detect_cues(rows)] == [10.0]
    assert len(detect_cues(rows, min_gap_s=1)) == 2


def test_marker_alone_is_found_but_unnamed():
    seg = segment(transcript=[{"start": 5, "end": 9, "text": "Next."}])
    assert seg.steps[0].name == "" and seg.steps[0].id == "cue-1"
    assert "naming-abstained" in seg.flags


def test_long_names_trim_at_a_word_boundary():
    text = "Now " + "word " * 30
    (row,) = detect_cues([{"start": 0, "end": 1, "text": text}], max_name_chars=20)
    assert row["name"] == "word word word word"


def test_ytdlp_subtitle_index_is_no_fact():
    seg = segment(
        "v.mp4", metadata={"subtitles": {"en": [{"ext": "vtt", "url": "http://x"}]}}
    )
    assert "no-signal" in seg.flags


def test_priority_chapters_over_cues_and_cues_over_nothing():
    chapters = [{"start": 0, "end": 10, "title": "A"}]
    seg = segment(metadata={"chapters": chapters, "subtitles": SRT})
    assert seg.method == "chapters"
    assert "ignored: metadata (subtitles)" in seg.flags
    seg = segment(transcript=SRT, metadata={"subtitles": SRT})
    assert seg.method == "subtitle-cues"  # human cues outrank ASR
    assert "ignored: transcript" in seg.flags


def test_explicit_segmenter_pin_and_missing_input():
    assert segment(transcript=SRT, segmenter="transcript-cues").steps
    with pytest.raises(ValueError, match="needs inputs"):
        segment(segmenter="transcript-cues")


def test_malformed_cues_say_what_is_wrong():
    with pytest.raises(ValueError, match="cues\\[0\\]"):
        normalize_timed_text([{"start": "x", "text": "hi"}])
    with pytest.raises(ValueError, match="unusable times"):
        normalize_timed_text([{"start": 5, "end": 1, "text": "hi"}])


def test_registered_and_listed():
    assert {"subtitle-cues", "transcript-cues"} <= set(capabilities())


VTT_NO_HOURS = """WEBVTT

00:12.000 --> 00:15.000
<c>Now</c> the <00:00:13.000><c>basic step</c>

00:40.000 --> 00:44.000
Next, the turn.
"""


VTT_HOURS = "\ufeff  " + VTT_NO_HOURS.replace("00:12", "00:00:12").replace(
    "00:15", "00:00:15"
).replace("00:40", "00:00:40").replace("00:44", "00:00:44")


@pytest.mark.parametrize("vtt", [VTT_NO_HOURS, VTT_HOURS])
def test_vtt_with_and_without_hours(vtt):
    rows = normalize_timed_text(vtt)
    assert rows[0] == {"start": 12.0, "end": 15.0, "text": "Now the basic step"}
    assert [r["start"] for r in rows] == [12.0, 40.0]


def test_markup_and_speaker_prefixes_are_stripped():
    rows = normalize_timed_text(
        [
            (5, 9, "{\\an8}<i>- Now the stance</i>"),
            (30, 34, ">> [music] Next, the turn"),
        ]
    )
    assert rows[0]["text"] == "- Now the stance"
    assert [r["name"] for r in detect_cues(rows)] == ["the stance", "the turn"]


def test_text_that_is_neither_timed_text_nor_a_file_raises():
    with pytest.raises(ValueError, match="not an existing file"):
        normalize_timed_text("no-such-file.srt")


def test_folded_cue_names_an_unnamed_opener():
    rows = [
        {"start": 10, "end": 11, "text": "Now."},
        {"start": 12, "end": 16, "text": "Step two: the turn."},
    ]
    assert detect_cues(rows) == [{"start": 10.0, "name": "the turn", "cue": "Now"}]


def test_zero_length_trailing_step_is_dropped():
    seg = segment(transcript=[(5, 30, "First, the stance."), (30, 30, "Finally.")])
    assert [s.name for s in seg.steps] == ["the stance"]
    assert seg.boundaries == (5.0, 30.0)
    assert "trailing-cue-dropped" in seg.flags


def test_intro_before_first_cue_is_flagged_only_when_present():
    assert "intro-before: 5s" in segment(transcript=[(5, 9, "Next, x")]).flags
    flags = segment(transcript=[(0, 9, "Next, x")]).flags
    assert not any(f.startswith("intro-before") for f in flags)


def test_path_object_input(tmp_path):
    path = tmp_path / "talk.srt"
    path.write_text(SRT, encoding="utf-8")
    assert len(segment(transcript=Path(path)).steps) == 3


def test_triples_and_whisper_segments():
    triples = [(0, 4, "Hi"), (20, 25, "First, the stance.")]
    whisper = {"segments": [{"start": s, "end": e, "text": t} for s, e, t in triples]}
    assert normalize_timed_text(triples) == normalize_timed_text(whisper)
    assert segment(transcript=whisper).steps[0].name == "the stance"


def test_missing_mixing_names_the_install(monkeypatch):
    real_import = builtins.__import__

    def no_mixing(name, *args, **kwargs):
        if name == "mixing" or name.startswith("mixing."):
            raise ImportError("No module named 'mixing'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_mixing)
    with pytest.raises(ImportError, match="pip install mixing"):
        normalize_timed_text(SRT)
    assert normalize_timed_text([(0, 1, "Now")])  # cue rows need no mixing


def test_cli_timed_text_only_parses_real_json():
    assert tools._timed_text("[draft].srt") == "[draft].srt"
    assert tools._timed_text('[{"start": 0, "end": 1, "text": "x"}]')[0]["text"] == "x"


# ── second-review regressions ───────────────────────────────────────────────


def test_unusable_subtitles_do_not_break_the_chapters_path():
    chapters = [{"start": 0, "end": 10, "title": "A"}]
    seg = segment(metadata={"chapters": chapters, "subtitles": "en"})
    assert seg.method == "chapters"
    assert any(flag.startswith("subtitles-unusable") for flag in seg.flags)


def test_custom_pattern_without_a_group_works():
    rows = [{"start": 0, "end": 5, "text": "Right, go."}]
    (hit,) = detect_cues(rows, patterns=[r"right[,\s]+"])
    assert hit["cue"] == "Right," and hit["name"] == "go"


def test_first_of_all_is_one_marker():
    (hit,) = detect_cues([{"start": 0, "end": 5, "text": "First of all, the stance."}])
    assert hit["name"] == "the stance"


def test_null_text_and_bool_times_are_refused():
    with pytest.raises(ValueError):
        normalize_timed_text([{"start": 0, "end": 1, "text": None}])
    with pytest.raises(ValueError):
        normalize_timed_text([{"start": True, "end": 1, "text": "x"}])


def test_cli_segment_end_to_end_on_a_transcript(tmp_path):
    from paces import tools

    path = tmp_path / "talk.srt"
    path.write_text(SRT, encoding="utf-8")
    out = tools.segment(transcript=str(path))
    assert out["method"] == "transcript-cues" and len(out["steps"]) == 3
