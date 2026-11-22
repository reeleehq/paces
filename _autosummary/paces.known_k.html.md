# paces.known_k

Known-K change points: the step count a human gave turns peak-picking into exact change-point detection (paces#39).

The ask page asks for the number of steps first (`docs/alignment/07 §7.3`
step 1): one integer turns “find the peaks of a novelty curve” into “find the
K-1 change points that best split this signal”, which kernel change-point
detection solves exactly (`docs/alignment/05 §7`, `07 §2.16`). The
`known-k` capability is that consumer of `k`:

- **features**: a frame-wise description of the media’s audio
  ([`audio_features()`](#paces.known_k.audio_features): MFCCs and their spectral contrast, each dimension
  standardised), through paces’ own audio decode (the `[audio]` extra);
- **cuts**: [`known_k_cuts()`](#paces.known_k.known_k_cuts), `ruptures.KernelCPD(...).predict(n_bkps=K-1)`
  over those frames, no cut closer than `min_step_s` to another or to an end
  (the `[cpd]` extra; `ruptures` is BSD-2-Clause);
- **names**: zipped on when a step list of exactly K was given, else honestly
  unnamed (the `explicit` segmenter’s rule, [`paces.segmenters.steps_on_boundaries()`](paces.segmenters.html.md#paces.segmenters.steps_on_boundaries)).

The boundaries are a proposal: the confidence is low
([`DFLT_KNOWN_K_CONFIDENCE`](#paces.known_k.DFLT_KNOWN_K_CONFIDENCE)) and the result is flagged
`boundaries-proposed` for the ask page to confirm. A K the media is too
short to hold (fewer than `min_step_s` per step) is refused, with a reason,
never a made-up split.

The pure core, [`known_k_cuts()`](#paces.known_k.known_k_cuts), runs on any feature matrix:

```pycon
>>> import numpy as np
>>> x = np.repeat([[0.0], [5.0], [0.0]], 50, axis=0)  # three flat steps (needs ruptures)
>>> known_k_cuts(x, 3, frame_s=0.1, min_step_s=1.0)
[5.0, 10.0]
```

### Module Attributes

| [`DFLT_HOP_S`](#paces.known_k.DFLT_HOP_S)              | fine enough for a step boundary, coarse enough that kernel change-point detection stays fast on a long video.   |
|--------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|
| [`DFLT_N_MFCC`](#paces.known_k.DFLT_N_MFCC)             | MFCC coefficients per frame.                                                                                    |
| [`DFLT_KNOWN_K_MIN_STEP_S`](#paces.known_k.DFLT_KNOWN_K_MIN_STEP_S) | The narrowest step a cut may make (s), from a cut or an end.                                                    |
| [`DFLT_KNOWN_K_CONFIDENCE`](#paces.known_k.DFLT_KNOWN_K_CONFIDENCE) | the human confirms it on the ask page.                                                                          |
| [`DFLT_KERNEL`](#paces.known_k.DFLT_KERNEL)             | rbf compares feature distributions, not just means.                                                             |
| [`DFLT_SAMPLE_RATE`](#paces.known_k.DFLT_SAMPLE_RATE)        | The sample rate audio is decoded at for the features.                                                           |

### Functions

| [`audio_features`](#paces.known_k.audio_features)(path, \*[, hop_s, n_mfcc, ...])   | `(features, frame_s, duration_s)` of the audio of `path`: per frame, its MFCCs and spectral contrast, each dimension standardised over the media (so no one dimension's scale decides the cuts).                                                 |
|---------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`known_k_cuts`](#paces.known_k.known_k_cuts)(features, k, \*, frame_s[, ...])    | The `k - 1` interior cut times (s) that best split `features` (one row per frame, `frame_s` apart) into `k` steps, by kernel change-point detection; `[]` for one step, `None` when `k` steps of at least `min_step_s` do not fit in the frames. |

### paces.known_k.DFLT_HOP_S *: [float](https://docs.python.org/3/builtins/functions.html#float)* *= 0.1*

fine enough for a step boundary, coarse
enough that kernel change-point detection stays fast on a long video.

* **Type:**
  Seconds between two feature frames

### paces.known_k.DFLT_KERNEL *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)* *= 'rbf'*

rbf compares feature distributions, not just means.

* **Type:**
  The ruptures kernel

### paces.known_k.DFLT_KNOWN_K_CONFIDENCE *: [float](https://docs.python.org/3/builtins/functions.html#float)* *= 0.35*

the human confirms it on the ask page.

* **Type:**
  A proposal from the signal alone

### paces.known_k.DFLT_KNOWN_K_MIN_STEP_S *: [float](https://docs.python.org/3/builtins/functions.html#float)* *= 2.0*

The narrowest step a cut may make (s), from a cut or an end.

### paces.known_k.DFLT_N_MFCC *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 13*

MFCC coefficients per frame.

### paces.known_k.DFLT_SAMPLE_RATE *: [int](https://docs.python.org/3/builtins/functions.html#int)* *= 22050*

The sample rate audio is decoded at for the features.

### paces.known_k.audio_features(path, , hop_s=0.1, n_mfcc=13, sample_rate=22050)

`(features, frame_s, duration_s)` of the audio of `path`: per frame,
its MFCCs and spectral contrast, each dimension standardised over the
media (so no one dimension’s scale decides the cuts).

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`Any`](https://docs.python.org/3/library/typing.html#typing.Any), [`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float)]

### paces.known_k.known_k_cuts(features, k, , frame_s, min_step_s=2.0, kernel='rbf')

The `k - 1` interior cut times (s) that best split `features` (one
row per frame, `frame_s` apart) into `k` steps, by kernel
change-point detection; `[]` for one step, `None` when `k` steps of
at least `min_step_s` do not fit in the frames.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`float`](https://docs.python.org/3/builtins/functions.html#float)] | [`None`](https://docs.python.org/3/builtins/constants.html#None)
