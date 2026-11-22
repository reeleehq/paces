"""Known-K change points: the step count a human gave turns peak-picking into exact change-point detection (paces#39).

The ask page asks for the number of steps first (``docs/alignment/07 §7.3``
step 1): one integer turns "find the peaks of a novelty curve" into "find the
K-1 change points that best split this signal", which kernel change-point
detection solves exactly (``docs/alignment/05 §7``, ``07 §2.16``). The
``known-k`` capability is that consumer of ``k``:

- **features**: a frame-wise description of the media's audio
  (:func:`audio_features`: MFCCs and their spectral contrast, each dimension
  standardised), through paces' own audio decode (the ``[audio]`` extra);
- **cuts**: :func:`known_k_cuts`, ``ruptures.KernelCPD(...).predict(n_bkps=K-1)``
  over those frames, no cut closer than ``min_step_s`` to another or to an end
  (the ``[cpd]`` extra; ``ruptures`` is BSD-2-Clause);
- **names**: zipped on when a step list of exactly K was given, else honestly
  unnamed (the ``explicit`` segmenter's rule, :func:`paces.segmenters.steps_on_boundaries`).

The boundaries are a proposal: the confidence is low
(:data:`DFLT_KNOWN_K_CONFIDENCE`) and the result is flagged
``boundaries-proposed`` for the ask page to confirm. A K the media is too
short to hold (fewer than ``min_step_s`` per step) is refused, with a reason,
never a made-up split.

The pure core, :func:`known_k_cuts`, runs on any feature matrix:

>>> import numpy as np
>>> x = np.repeat([[0.0], [5.0], [0.0]], 50, axis=0)  # three flat steps (needs ruptures)
>>> known_k_cuts(x, 3, frame_s=0.1, min_step_s=1.0)  # doctest: +SKIP
[5.0, 10.0]
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from paces.segmentation import TIME_PLACES, Segmentation
from paces.segmenters import Capability, register, steps_on_boundaries

#: Seconds between two feature frames: fine enough for a step boundary, coarse
#: enough that kernel change-point detection stays fast on a long video.
DFLT_HOP_S: float = 0.1
#: MFCC coefficients per frame.
DFLT_N_MFCC: int = 13
#: The narrowest step a cut may make (s), from a cut or an end.
DFLT_KNOWN_K_MIN_STEP_S: float = 2.0
#: A proposal from the signal alone: the human confirms it on the ask page.
DFLT_KNOWN_K_CONFIDENCE: float = 0.35
#: The ruptures kernel: rbf compares feature distributions, not just means.
DFLT_KERNEL: str = "rbf"
#: The sample rate audio is decoded at for the features.
DFLT_SAMPLE_RATE: int = 22050


def known_k_cuts(
    features: Any,
    k: int,
    *,
    frame_s: float,
    min_step_s: float = DFLT_KNOWN_K_MIN_STEP_S,
    kernel: str = DFLT_KERNEL,
) -> list[float] | None:
    """The ``k - 1`` interior cut times (s) that best split ``features`` (one
    row per frame, ``frame_s`` apart) into ``k`` steps, by kernel
    change-point detection; ``[]`` for one step, ``None`` when ``k`` steps of
    at least ``min_step_s`` do not fit in the frames."""
    import numpy as np
    import ruptures

    x = np.asarray(features, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    if k < 1:
        raise ValueError(f"k must be a positive step count, got {k}")
    if k == 1:
        return []
    min_size = max(2, math.ceil(min_step_s / frame_s))
    if len(x) < k * min_size:
        return None
    bkps = ruptures.KernelCPD(kernel=kernel, min_size=min_size).fit(x).predict(n_bkps=k - 1)
    return [round(b * frame_s, TIME_PLACES) for b in bkps[:-1]]


def audio_features(
    path: Any,
    *,
    hop_s: float = DFLT_HOP_S,
    n_mfcc: int = DFLT_N_MFCC,
    sample_rate: int = DFLT_SAMPLE_RATE,
) -> tuple[Any, float, float]:
    """``(features, frame_s, duration_s)`` of the audio of ``path``: per frame,
    its MFCCs and spectral contrast, each dimension standardised over the
    media (so no one dimension's scale decides the cuts)."""
    import librosa
    import numpy as np

    from paces.measure import _load_audio  # the one decode path, wav or not

    y, sr = _load_audio(path, sample_rate=sample_rate)
    hop = max(1, int(round(hop_s * sr)))
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc, hop_length=hop)
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr, hop_length=hop)
    x = np.vstack([mfcc, contrast]).T
    spread = x.std(axis=0)
    x = (x - x.mean(axis=0)) / np.where(spread > 0, spread, 1.0)
    return x, hop / sr, len(y) / sr


def _segment_known_k(inputs: Mapping[str, Any]) -> Segmentation:
    """The ``known-k`` capability: K steps cut where the media's audio changes most."""
    k = int(inputs["k"])
    features, frame_s, duration = audio_features(inputs["media"])
    cuts = known_k_cuts(features, k, frame_s=frame_s)
    if cuts is None:
        return Segmentation(
            confidence=0.0,
            flags=(
                f"k-too-large: {k} steps of at least {DFLT_KNOWN_K_MIN_STEP_S} s "
                f"do not fit in {duration:.1f} s of media",
            ),
        )
    boundaries = (0.0, *cuts, round(duration, TIME_PLACES))
    steps, flags = steps_on_boundaries(
        boundaries,
        inputs["steps"],
        confidence=DFLT_KNOWN_K_CONFIDENCE,
        source="known-k",
    )
    return Segmentation(
        steps=steps,
        boundaries=boundaries,
        confidence=DFLT_KNOWN_K_CONFIDENCE,
        flags=flags + ("boundaries-proposed",),
    )


KNOWN_K = register(
    Capability(
        name="known-k",
        gives="segmentation",
        summary=(
            "K steps where the media's audio changes most: kernel change-point "
            "detection over MFCC frames, the step count from the ask page"
        ),
        target="paces.known_k:_segment_known_k",
        needs=frozenset({"media.local", "k"}),
        reads=frozenset({"steps"}),
        requires=("ruptures", "librosa"),
        licence="BSD-2-Clause (ruptures)",
        base=0.3,  # below every segmenter that is told where the steps are
        resolution_s=DFLT_HOP_S,
    )
)
