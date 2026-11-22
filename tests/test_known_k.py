"""The known-k segmenter and the k-mismatch flag (paces#39)."""

from __future__ import annotations

import pytest

from paces import segment


def test_an_answered_k_the_result_disagrees_with_is_flagged():
    """The ask page's step count is said when the result has another count,
    whichever segmenter ran, instead of being dropped silently."""
    seg = segment(boundaries=[0, 10, 20, 30], k=4)
    assert "k-mismatch: k=4, found 3 steps" in seg.flags
    assert not any(f.startswith("k-mismatch") for f in segment(boundaries=[0, 10, 20, 30], k=3).flags)


def test_known_k_cuts_finds_the_k_minus_1_change_points():
    np = pytest.importorskip("numpy")
    pytest.importorskip("ruptures")
    from paces.known_k import known_k_cuts

    x = np.repeat([[0.0, 1.0], [5.0, 1.0], [0.0, 3.0]], 50, axis=0)
    assert known_k_cuts(x, 3, frame_s=0.1, min_step_s=1.0) == [5.0, 10.0]
    assert known_k_cuts(x, 1, frame_s=0.1) == []
    assert known_k_cuts(x, 20, frame_s=0.1, min_step_s=1.0) is None  # 20 x 1 s > 15 s


def _three_sounds(path, seconds=(6.0, 5.0, 7.0), rate=22050):
    """A wav of a low tone, noise, then a high tone: three steps whose audio differs."""
    np = pytest.importorskip("numpy")
    sf = pytest.importorskip("soundfile")
    rng = np.random.default_rng(0)
    parts = []
    for i, s in enumerate(seconds):
        t = np.arange(int(s * rate)) / rate
        if i == 0:
            parts.append(0.4 * np.sin(2 * np.pi * 220 * t))
        elif i == 1:
            parts.append(0.3 * rng.standard_normal(len(t)))
        else:
            parts.append(0.4 * np.sin(2 * np.pi * 1760 * t))
    sf.write(str(path), np.concatenate(parts), rate)
    return [seconds[0], seconds[0] + seconds[1]]


def test_the_known_k_segmenter_cuts_the_media_where_its_audio_changes(tmp_path):
    """Media plus the human's k, nothing else: known-k is chosen, and its
    K-1 cuts land on the changes; named when a step list of K was given."""
    pytest.importorskip("ruptures")
    pytest.importorskip("librosa")
    wav = tmp_path / "three.wav"
    truth = _three_sounds(wav)
    seg = segment(str(wav), k=3)
    assert seg.method == "known-k"
    assert len(seg.boundaries) == 4
    for got, want in zip(seg.boundaries[1:-1], truth):
        assert abs(got - want) <= 0.3, (seg.boundaries, truth)
    assert "boundaries-proposed" in seg.flags and "naming-abstained" in seg.flags
    assert not any(f.startswith(("ignored", "k-mismatch")) for f in seg.flags)
    named = segment(str(wav), k=3, steps=["tone", "noise", "whistle"])
    assert [s.name for s in named.steps] == ["tone", "noise", "whistle"]


def test_a_k_the_media_cannot_hold_is_refused_with_a_reason(tmp_path):
    pytest.importorskip("ruptures")
    pytest.importorskip("librosa")
    wav = tmp_path / "three.wav"
    _three_sounds(wav)
    seg = segment(str(wav), k=50)
    assert seg.steps == () and any(f.startswith("k-too-large") for f in seg.flags)
