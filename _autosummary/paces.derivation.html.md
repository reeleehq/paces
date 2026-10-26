# paces.derivation

Media derivation: fill 

```
``
```

ArtifactRef\`\`s with real clips, gifs and posters.

For every excerpt-bearing [`SourceSpan`](paces.model.html.md#paces.model.SourceSpan), cut a loopable
mp4, a palette-quality gif and a poster frame from the local media, write
them through a store keyed by document-relative uri, and upsert the
resulting [`ArtifactRef`](paces.model.html.md#paces.model.ArtifactRef)s onto the owning step. The
design — where media lands, why CI needs no system ffmpeg, and the
`subject_locator=` seam — is ADR-0005 (`docs/adr/0005-media-derivation.md`);
this docstring only summarises the contracts.

**The locator seam (Shape B — locator observes, core decides).** A
`subject_locator` is a callable receiving a [`LocateQuery`](#paces.derivation.LocateQuery) and
returning a [`SubjectObservation`](#paces.derivation.SubjectObservation) — timed raw region evidence — or
`None`, which means “no crop” and is both the default locator’s honest
answer ([`full_frame()`](#paces.derivation.full_frame)) and the zero-detections fallback. The *core*
owns the one policy pipeline ([`resolve_crop_box()`](#paces.derivation.resolve_crop_box)): union regions per
sample → robust percentile envelope → pad → force aspect → clamp → \*\*one
static box per excerpt window\*\* (measured on 2.5–6 s loops; per-frame crops
are unstable). A `None` observation gets no policy: no crop means
genuinely uncropped, not letterboxed.

**Crop recipes** persist in a sidecar (`<document-stem>.recipes.json`,
next to the document, committed and diffable) keyed by the span address
`{step_id}/{source}/{role}/{start}`. A recipe whose inputs still match is
reused (the locator is skipped); a **locked** recipe’s box is used verbatim
— never re-padded, re-aspected or clamped — and survives drift with a loud
flag. Hand-override = edit `box`, set `locked: true`.

**Honesty flags over silence.** Every skipped span, unverifiable identity,
kept lock, refreshed or orphaned recipe, and stale artifact is a named flag
in the result — never a silent drop.

All media I/O goes through `mixing` (behind the `[media]` extra) — never
moviepy/ffmpeg directly.

### Module Attributes

| [`ENVELOPE_LO`](#paces.derivation.ENVELOPE_LO)    | Crop-policy defaults — the POC's shipped production values (`docs/poc-reference/tools/build_media.py`): 4th/96th percentile robust envelope, 16% padding, 4:5 portrait-ish aspect (width/height).   |
|-----------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`DFLT_ROLES`](#paces.derivation.DFLT_ROLES)     | The artifact roles derive produces, in production order.                                                                                                                                            |
| [`MEDIA_PREFIX`](#paces.derivation.MEDIA_PREFIX)   | Uri prefix (and store-key prefix) for derived media — POSIX '/', always.                                                                                                                            |
| [`Box`](#paces.derivation.Box)            | (x, y, w, h) from the frame's top-left.                                                                                                                                                             |
| [`SubjectLocator`](#paces.derivation.SubjectLocator) | returns an observation, or `None` meaning "no crop".                                                                                                                                                |

### Functions

| [`check_media_requirements`](#paces.derivation.check_media_requirements)()                    | Two-channel media preflight (ADR-0005 §2), reported distinctly:                                                                                                          |
|------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`derive_document`](#paces.derivation.derive_document)(document, \*, media[, ...])   | Derive media for every excerpt-bearing span and return the updated document (the caller persists it; media and recipes are written here).                                |
| [`full_frame`](#paces.derivation.full_frame)(query)                             | The default locator: no crop, ever — a real implementation of the contract whose honest answer is `None` (docs/09: the seam must be "genuinely pluggable and nullable"). |
| [`load_recipes`](#paces.derivation.load_recipes)(path)                            | Read the sidecar (missing file → an empty one).                                                                                                                          |
| [`resolve_crop_box`](#paces.derivation.resolve_crop_box)(observation, \*, frame_size) | The locator-agnostic crop policy: observation → ONE static box.                                                                                                          |
| [`save_recipes`](#paces.derivation.save_recipes)(recipes, path)                   | Write the sidecar in the document's canonical wire style.                                                                                                                |

### Classes

| [`CropRecipe`](#paces.derivation.CropRecipe)(\*[, box, sourceAssetId, params, ...])   | One span's derivation parameters: the resolved `box` (the *final* post-policy crop; `None` = full frame, a recorded decision) plus the input fingerprint that makes drift detectable.   |
|------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`DeriveResult`](#paces.derivation.DeriveResult)(document[, flags, derived])            | What a derive run did: the updated document, the honesty flags, and one row per derived (or byte-stably reused) span.                                                                   |
| [`DirStore`](#paces.derivation.DirStore)(rootdir)                                   | Minimal `MutableMapping[str, bytes]` over files under a root directory, keyed by relative POSIX paths (`media/b4.mp4`).                                                                 |
| [`LocateQuery`](#paces.derivation.LocateQuery)(media_path, start_s, end_s, ...)        | What a `subject_locator` is asked: one excerpt window of one media file, with read-only hints.                                                                                          |
| [`RecipesFile`](#paces.derivation.RecipesFile)(\*[, kind, schemaVersion, entries])     | The sidecar document: span address → [`CropRecipe`](#paces.derivation.CropRecipe).                                                                                       |
| [`SubjectObservation`](#paces.derivation.SubjectObservation)(samples)                         | Timed raw region evidence: `samples[i] = (t_s, (box, box, ...))` — one region tuple per probed instant.                                                                                 |

### paces.derivation.Box

(x, y, w, h) from the frame’s top-left.

* **Type:**
  A pixel box

alias of [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int)]

### *class* paces.derivation.CropRecipe(\*, box=None, window, frameWidth, frameHeight, sourceAssetId=None, locator, params=<factory>, locked=False, mediaDigest=None)

Bases: `_WireBase`

One span’s derivation parameters: the resolved `box` (the *final*
post-policy crop; `None` = full frame, a recorded decision) plus the
input fingerprint that makes drift detectable. `params` and `locator`
are read on reconcile — a locator upgrade or an aspect/pad change
re-locates an unlocked entry; a stored box is never re-run through the
policy. `media_digest` stamps what the stored media was actually cut
with (box + window + source hash), so a hand-edited box or a re-timed
window forces a re-encode instead of silently serving stale bytes —
the POC’s crops.json failure, kept dead. `params` values are decimal
strings (the sidecar is committed — no floats on the wire).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### paces.derivation.DFLT_ROLES *= ('clip', 'gif', 'poster')*

The artifact roles derive produces, in production order.

### *class* paces.derivation.DeriveResult(document, flags=list(), derived=list())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What a derive run did: the updated document, the honesty flags, and
one row per derived (or byte-stably reused) span.

### *class* paces.derivation.DirStore(rootdir)

Bases: [`MutableMapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.MutableMapping)

Minimal `MutableMapping[str, bytes]` over files under a root
directory, keyed by relative POSIX paths (`media/b4.mp4`).

The default backend of the ADR-0005 store seam — stdlib-only so the
pydantic-only core stays intact (ADR-0004). Inject a `dol`/`s3dol`
store for other backends; the key contract (document-relative POSIX uri)
is backend-independent.

### paces.derivation.ENVELOPE_LO *= 4*

Crop-policy defaults — the POC’s shipped production values
(`docs/poc-reference/tools/build_media.py`): 4th/96th percentile robust
envelope, 16% padding, 4:5 portrait-ish aspect (width/height).

### *class* paces.derivation.LocateQuery(media_path, start_s, end_s, frame_width, frame_height, step_id, tags=())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What a `subject_locator` is asked: one excerpt window of one media
file, with read-only hints. Times are float seconds — a computed view,
like [`paces.model.resolve()`](paces.model.html.md#paces.model.resolve)’s output, never the stored document.

### paces.derivation.MEDIA_PREFIX *= 'media'*

Uri prefix (and store-key prefix) for derived media — POSIX ‘/’, always.

### *class* paces.derivation.RecipesFile(\*, kind='paces.crop-recipes', schemaVersion='0.1.0', entries=<factory>)

Bases: `_WireBase`

The sidecar document: span address → [`CropRecipe`](#paces.derivation.CropRecipe).

#### model_config *: [ClassVar](https://docs.python.org/3/library/typing.html#typing.ClassVar)[ConfigDict]* *= {'alias_generator': <function to_camel>, 'extra': 'forbid', 'populate_by_name': True}*

Configuration for the model, should be a dictionary conforming to [`ConfigDict`][pydantic.config.ConfigDict].

### paces.derivation.SubjectLocator

returns an observation, or `None` meaning “no crop”.

* **Type:**
  The seam

alias of `Callable`[[[`LocateQuery`](#paces.derivation.LocateQuery)], `SubjectObservation | None`]

### *class* paces.derivation.SubjectObservation(samples)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Timed raw region evidence: `samples[i] = (t_s, (box, box, ...))` —
one region tuple per probed instant. Deliberately not person-shaped: one
box for a dancer, two for judo, hands + workpiece for cooking. Samples
are transient locator output; only the resolved box is ever persisted.

### paces.derivation.check_media_requirements()

Two-channel media preflight (ADR-0005 §2), reported distinctly:

- `bundled_ffmpeg` — the pip-bundled imageio-ffmpeg binary, which is
  all `derive` needs (mp4/gif via mixing; posters via cv2).
- `system_ffmpeg` — a PATH ffmpeg, which `derive` does NOT need but
  `measure_grid` on non-wav input does (pydub knows nothing of the
  bundled binary). A bundled-only check would report healthy on a
  machine where `measure_grid("video.mp4")` fails.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### paces.derivation.derive_document(document, , media, doc_path=None, media_store=None, recipes_path=None, subject_locator=None, aspect=0.8, pad=0.16, roles=('clip', 'gif', 'poster'))

Derive media for every excerpt-bearing span and return the updated
document (the caller persists it; media and recipes are written here).

* **Parameters:**
  * **document** ([`StepDocument`](paces.model.html.md#paces.model.StepDocument)) – the committed document (worked on a deep copy).
  * **media** – local media — one path when exactly one source carries
    excerpts, else `{source_id: path}`.
  * **doc_path** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – the document’s file path — the anchor for the default
    media store (`<dir>/media/`) and recipes sidecar
    (`<dir>/<stem>.recipes.json`). Without it, `media_store`
    AND `recipes_path` must be given explicitly: a document that
    arrived as data has no directory, and deriving into cwd
    silently would make every written uri a lie (ADR-0005 §1).
  * **media_store** ([`MutableMapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.MutableMapping) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – `MutableMapping[str, bytes]` keyed by
    document-relative POSIX uri. Default: [`DirStore`](#paces.derivation.DirStore) beside
    the document.
  * **recipes_path** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – the crop-recipes sidecar path.
  * **subject_locator** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`LocateQuery`](#paces.derivation.LocateQuery)], [`SubjectObservation`](#paces.derivation.SubjectObservation) | [`None`](https://docs.python.org/3/builtins/constants.html#None)]]) – the ADR-0005 §3 seam; default [`full_frame()`](#paces.derivation.full_frame)
    (no crop).
  * **aspect** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – crop aspect (w/h) the policy forces — only when a locator
    yields regions; never applied to a locked or full-frame box.
  * **pad** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – padding fraction around the envelope.
  * **roles** ([`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)]) – which artifact roles to produce, of `("clip", "gif",
    "poster")`.
* **Return type:**
  [`DeriveResult`](#paces.derivation.DeriveResult)

### paces.derivation.full_frame(query)

The default locator: no crop, ever — a real implementation of the
contract whose honest answer is `None` (docs/09: the seam must be
“genuinely pluggable and nullable”). Pointable replacement: rtmlib pose
boxes (Apache-2.0; never YOLO/ultralytics — AGPL, see ADR-0005 §3).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### paces.derivation.load_recipes(path)

Read the sidecar (missing file → an empty one).

* **Return type:**
  [`RecipesFile`](#paces.derivation.RecipesFile)

### paces.derivation.resolve_crop_box(observation, , frame_size, aspect=0.8, pad=0.16, lo=4, hi=96)

The locator-agnostic crop policy: observation → ONE static box.

Union regions per sample → robust percentile envelope (`lo`/`hi`) →
pad → force `aspect` (w/h, expanding the deficient dimension) → clamp
into the frame (shrinking aspect-true when the padded box exceeds it).
`None` in (no observation, or no sample carried a region) → `None`
out: full frame, no policy — no crop is genuinely uncropped.

```pycon
>>> obs = SubjectObservation(samples=((0.0, ((40, 40, 20, 40),)),))
>>> resolve_crop_box(obs, frame_size=(200, 200), pad=0.0, aspect=0.5)
(40, 40, 20, 40)
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int), [`int`](https://docs.python.org/3/builtins/functions.html#int)] | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### paces.derivation.save_recipes(recipes, path)

Write the sidecar in the document’s canonical wire style.

Deliberately NOT `exclude_none`: `box: null` (full frame) and
`sourceAssetId: null` (identity unverified) are recorded decisions a
hand-editor must be able to see and override (ADR-0005 §3).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)
