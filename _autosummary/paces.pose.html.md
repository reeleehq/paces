# paces.pose

The pointable `subject_locator`: person boxes from rtmlib pose keypoints.

ADR-0005 §3 shipped the `subject_locator=` seam with [`paces.derivation.full_frame()`](paces.derivation.html.md#paces.derivation.full_frame)
as its default — a real implementation whose honest answer is “no crop” — and pinned
the contract with fake locators. This module is the pointable replacement: probe the
excerpt window at ~5 fps, run RTMPose over each probed frame, and hand the core one
region list per instant, every person seen. It **observes only**; the core still owns
the one policy pipeline (union → percentile envelope → pad → aspect → clamp → one
static box per window), which is exactly where the POC measured that crops go wrong.

**Licence perimeter.** What this extra itself adds is permissive: rtmlib is
Apache-2.0 (a pure-Python wheel, no bundled binaries or weights) and onnxruntime is
MIT. Its detector is **YOLOX** (Megvii, Apache-2.0) — measured, not assumed: every
`Body` mode downloads a `yolox_*` checkpoint from download.openmmlab.com, and the
RTMDet code in rtmlib is not what `Body` uses. So the accurate claim is *not* “no
YOLO” (the issue and ADR-0005 §3 say RTMDet; that is wrong) but the one that actually
carries the licence: no **ultralytics**, whose YOLOv5/v8/v11 are AGPL-3.0 and whose §13
network clause reaches users you serve rather than only people you hand a copy to. What
is barred is that distribution, not the word YOLO.
`tests/test_pose.py` guards that perimeter as the packaging fact it is. kodokan’s
`pose`/`track` split is the fleet’s worked example of the same quarantine.

\*\*The closure is NOT uniformly permissive, and the wheel’s own notice file will not
tell you so.\*\* opencv — which rtmlib pulls, and which `[media]`’s mixing already
declares — bundles FFmpeg whose licence tier is **platform-dependent** and must be
read off the binary, because `LICENSE-3RD-PARTY.txt` never mentions x264 on any
platform. Measured per wheel (see the PR for #15 for the commands):

- manylinux (what CI installs) and Windows: no x264/x265, no `--enable-gpl`;
  `libavutil license: LGPL version 2.1 or later`.
- macOS, **both** arm64 and x86_64: `--enable-gpl --enable-version3
  --enable-libx264 --enable-libx265`, libx264/libx265 shipped;
  `libavutil license: GPL version 3 or later`.

That tier already arrives with `[media]`. `[pose]` does not raise it — but it is
not free of it either: rtmlib requires opencv-python *and* opencv-contrib-python,
both unpinned, so installing it adds a second wheel carrying its own copy of those
same binaries (issue #20).

**Nothing here is imported until it is used.** `import paces` never touches this
module, and importing *this* module never touches rtmlib: every rtmlib access goes
through `_import_body()` or `_rtmlib_version()`, both of which raise an
`ImportError` naming the extra. Model weights download on first inference, so CI
covers the seam’s contract through fake locators and never runs a model.

Usage — the shell, then the library:

```default
paces derive doc.json --media routine.mp4 --subject-locator paces.pose:rtmlib_pose

from paces.derivation import derive_document
from paces.pose import RtmlibPoseLocator, rtmlib_pose

derive_document(doc, media=..., doc_path=..., subject_locator=rtmlib_pose)
derive_document(..., subject_locator=RtmlibPoseLocator(probe_fps=10.0))
```

### Module Attributes

| [`DFLT_PROBE_FPS`](#paces.pose.DFLT_PROBE_FPS)           | Probe rate across an excerpt window, in samples per second — the POC's rate.                                                                              |
|---------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`DFLT_MODE`](#paces.pose.DFLT_MODE)                | "lightweight" | "balanced" | "performance".                                                                                                               |
| [`DFLT_DEVICE`](#paces.pose.DFLT_DEVICE)              | onnxruntime execution device.                                                                                                                             |
| [`DFLT_KEYPOINT_CONFIDENCE`](#paces.pose.DFLT_KEYPOINT_CONFIDENCE) | A keypoint below this score is noise, not evidence, and never widens a box.                                                                               |
| [`DFLT_MIN_KEYPOINTS`](#paces.pose.DFLT_MIN_KEYPOINTS)       | Fewer confident keypoints than this is not a person — it is a hallucinated limb or two, and boxing it would hand the core a region with no subject in it. |
| [`POSE_EXTRA`](#paces.pose.POSE_EXTRA)               | The extra that carries this locator, and the stem of its recorded identity.                                                                               |
| [`TEST_MODELS_ENVVAR`](#paces.pose.TEST_MODELS_ENVVAR)       | Opt-in for the real-model smoke test.                                                                                                                     |
| [`rtmlib_pose`](#paces.pose.rtmlib_pose)              | no configuration, and the target a CLI `--subject-locator paces.pose:rtmlib_pose` reference resolves to.                                                  |

### Functions

| [`check_pose_requirements`](#paces.pose.check_pose_requirements)()                       | Preflight for the `[pose]` extra, per channel and never silently.             |
|--------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| [`person_boxes`](#paces.pose.person_boxes)(keypoints, scores, \*, frame_size) | One box per person, spanning that person's *confident* keypoints.             |
| [`probe_times`](#paces.pose.probe_times)(start_s, end_s, \*[, probe_fps])    | The instants to look at: ~\`\`probe_fps\`\` samples spread inside the window. |

### Classes

| [`RtmlibPoseLocator`](#paces.pose.RtmlibPoseLocator)(\*[, probe_fps, mode, ...])   | The pointable `subject_locator`: rtmlib pose boxes over a probed window.   |
|--------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------|

### paces.pose.DFLT_DEVICE *= 'cpu'*

onnxruntime execution device. “cpu” is the portable answer and the only one
CI would ever have; “cuda”/”mps” are a caller’s choice, not a default.

### paces.pose.DFLT_KEYPOINT_CONFIDENCE *= 0.3*

A keypoint below this score is noise, not evidence, and never widens a box.
This threshold is load-bearing, not decorative: rtmlib’s `Body` is a
top-down pipeline, so it returns a full 17-keypoint person for a frame with
nobody in it at all. Measured on a blank frame (rtmlib 0.0.15, balanced):
one “person”, every score ~0.11-0.13. Without this filter the locator would
hand the core a confident box around nothing, every time.

### paces.pose.DFLT_MIN_KEYPOINTS *= 4*

Fewer confident keypoints than this is not a person — it is a hallucinated
limb or two, and boxing it would hand the core a region with no subject in
it. The second half of the same defence: a real detection clears 0.3 on far
more than four joints, while the blank-frame phantom above clears it on none.

### paces.pose.DFLT_MODE *= 'balanced'*

“lightweight” | “balanced” | “performance”.

* **Type:**
  rtmlib `Body` accuracy/latency trade-off

### paces.pose.DFLT_PROBE_FPS *= 5.0*

Probe rate across an excerpt window, in samples per second — the POC’s rate.
Excerpts are 2.5–6 s loops, so ~5 fps is 13–30 looks: enough for the 4/96
envelope to shrug off a stray frame, cheap enough to run on CPU.

### paces.pose.POSE_EXTRA *= 'pose'*

The extra that carries this locator, and the stem of its recorded identity.

### *class* paces.pose.RtmlibPoseLocator(, probe_fps=5.0, mode='balanced', device='cpu', keypoint_confidence=0.3, min_keypoints=4, pose_estimator=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

The pointable `subject_locator`: rtmlib pose boxes over a probed window.

Callable per the ADR-0005 §3 contract — a [`LocateQuery`](paces.derivation.html.md#paces.derivation.LocateQuery)
in, a [`SubjectObservation`](paces.derivation.html.md#paces.derivation.SubjectObservation) out, or `None`, the
honest “no crop”, when the window showed nobody. It never resolves a box:
that is the core’s [`resolve_crop_box()`](paces.derivation.html.md#paces.derivation.resolve_crop_box).

`pose_estimator` is the seam inside the seam: any
`callable(frame) -> (keypoints, scores)`. The default is rtmlib’s `Body`
(YOLOX + RTMPose, COCO-17); the replacements are already pointable —
rtmlib’s `Wholebody`, `Hand` and `Animal` solutions have exactly this
shape, and the ADR’s “hands + workpiece for cooking” case is one of them.
Tests inject a fake through it, which is how the contract is exercised with
no weights downloaded and no network reached.

All fields are keyword-only, and the defaults are the shipped policy.

#### *property* locator_name *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)*

The policy identity the crop recipe records — **every** input that
can move a box, not just the model version.

`derive` reuses a stored box when this name and the core’s params
still match (ADR-0005 §3), so anything left out of it silently reuses a
box that something else measured. That is the whole point of the
fingerprint, so the probe rate and both keypoint thresholds are in it
alongside the model:

```default
rtmlib-pose@0.0.16;mode=balanced;fps=5;conf=0.3;minkp=4
```

An injected `pose_estimator` names *itself* — claiming rtmlib’s
version for a box rtmlib did not measure would be exactly the false
identity this exists to prevent — and drops `mode`, which is a
`Body` argument and means nothing to another estimator:

```default
rtmlib-pose@custom:mypkg.my_estimator;fps=5;conf=0.3;minkp=4
```

`device` is deliberately absent: it selects an execution provider,
not a policy, and putting it in would re-locate every box on a machine
change — a false honesty flag, which this codebase treats as the
failure mode it is.

### paces.pose.TEST_MODELS_ENVVAR *= 'PACES_TEST_MODELS'*

Opt-in for the real-model smoke test. Unset (CI, always) = no weights, no
inference — the contract is covered by fake locators instead.

### paces.pose.check_pose_requirements()

Preflight for the `[pose]` extra, per channel and never silently.

- `rtmlib` / `onnxruntime` — the locator and its inference backend.
- `cv2_providers` — rtmlib declares BOTH `opencv-python` and
  `opencv-contrib-python`, while the fleet standardises on the contrib
  superset (mixing’s single cv2 provider). An install can therefore end up
  with two distributions owning one `cv2` package. Reported, not fatal:
  it works until one of them is uninstalled, and a reader deserves to know
  — and, since neither package’s uninstall is safe once both are present
  (each claims files the other also claims), the note names the repair
  command rather than only the collision. See README’s “Auto-crop” section
  for the install recipe that avoids the pair in the first place
  (issue #20).

Downloads nothing: weights arrive on first inference, not on this check.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### paces.pose.person_boxes(keypoints, scores, , frame_size, keypoint_confidence=0.3, min_keypoints=4)

One box per person, spanning that person’s *confident* keypoints.

`keypoints` is `(n_persons, n_keypoints, 2)` and `scores` is
`(n_persons, n_keypoints)` — rtmlib’s output shape, read here as plain
nested sequences, so this stays a pure function and numpy remains the
extra’s business rather than this module’s. A person carrying fewer than
`min_keypoints` confident points is dropped rather than boxed from noise;
boxes are clamped into the frame, and a degenerate one is dropped too.
Zero detections is `()` — evidence that nobody was there, not an error.

Order is rtmlib’s and means nothing: the seam is a *set* of regions per
instant (the core unions them), so no person-identity claim is made here.

```pycon
>>> person_boxes(
...     [[(10, 20), (30, 60)]], [(0.9, 0.9)],
...     frame_size=(100, 100), min_keypoints=2,
... )
((10, 20, 20, 40),)
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int)], [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)]

### paces.pose.probe_times(start_s, end_s, , probe_fps=5.0)

The instants to look at: ~\`\`probe_fps\`\` samples spread inside the window.

Samples sit at the midpoints of `n` equal slices, so each one is strictly
inside `[start_s, end_s)` — a probe on the closing edge would read the
next shot — and a window shorter than one probe interval still gets exactly
one look, at its middle.

```pycon
>>> tuple(round(t, 3) for t in probe_times(0.0, 1.0, probe_fps=5.0))
(0.1, 0.3, 0.5, 0.7, 0.9)
>>> tuple(round(t, 3) for t in probe_times(10.0, 10.05))
(10.025,)
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`float`](https://docs.python.org/3/builtins/functions.html#float), [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)]

### paces.pose.rtmlib_pose *= RtmlibPoseLocator(probe_fps=5.0, mode='balanced', device='cpu', keypoint_confidence=0.3, min_keypoints=4, pose_estimator=None)*

no configuration, and the target a CLI
`--subject-locator paces.pose:rtmlib_pose` reference resolves to.

* **Type:**
  The ready-made locator
* **Return type:**
  [*SubjectObservation*](paces.html.md#paces.SubjectObservation) | *None*
