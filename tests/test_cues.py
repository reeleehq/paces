"""The subtitle / transcript cue segmenters (issue #6)."""

from __future__ import annotations

import pytest

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
        {"start": 14, "end": 16, "text": "Then keep going."},
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
    assert len(row["name"]) <= 20 and not row["name"].endswith("wor")


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
