---
name: paces
description: >-
  Turn instructional media (a video of someone teaching a routine, a recipe, a
  workout, a kata) into a structured step document, then into learning
  material: a practice page, a step-through player (flow), or a printable card
  and PDF. Use when asked to "turn this video into steps", "make a practice
  page / step-through / flow from a routine", "make a printable card or PDF of
  this routine", "segment a tutorial", "add loop clips to the steps", "export
  the step document's JSON Schema", or when a step document (StepDocument)
  already exists and needs rendering, editing or validating. Not for
  extracting poses or scoring movement, and not for editing video.
metadata:
  audience: users
---

# paces

`paces` turns instructional media into a **step document** (`StepDocument`: named steps with counts in the domain's own unit, nested steps and repeats, cues, source spans, optional looping clips) and renders that document into learning material. Analysis and rendering are separate: every renderer reads the document, never the analyser.

```bash
pip install paces          # core: pydantic only
pip install 'paces[cli]'   # the `paces` command (and `python -m paces`)
pip install 'paces[pdf]'   # PDF cards (pdfdol; also needs the wkhtmltopdf program)
```

Other extras: `media` (loop clips, gifs, posters), `audio` (measure the tempo grid), `pose` (auto-crop to the person), `lacing` (the evidence layer), `cpd` (known-step-count segmentation).

## The verbs, in the order they run

Every verb is a plain function in `paces.tools` and a subcommand of `paces`; `paces <verb> --help` is the reference. Structured arguments take a Python object, a JSON string or a path to a JSON file.

1. **`measure-grid`** (`[audio]`): tempo and origin of the media, when the routine is counted to music. `segment` calls it for you when it has local media and no grid.
2. **`segment`**: cut the media into steps with whatever is present: a step list with durations and a grid (`grid-placed`), explicit boundaries, uploader chapters or subtitles, a transcript with step markers, or a known step count. `paces list-segmenters` says what each needs.
3. **`ask`** (optional): write the page a human answers on (how many steps? tap along to add or strike cuts). Feed its `answers.json` back to `segment --answers`. Use it when the machine cannot know the count.
4. **`to-document`**: project the segmentation into the committed `StepDocument` (give it `--source`, `--title`, `--domain`).
5. **`suggest-excerpts`**, then **`derive`** (`[media]`): mark each step's loopable window, then cut looping mp4s, gifs and posters into `media/` beside the document. The document's artifact uris are document-relative: keep the media next to it.
6. **`edit`** and **`merge`**: typed patches that write a Lock; locked fields survive a re-run, `merge` brings a regenerated document in without overwriting a human's decision.
7. **`validate`** and **`resolve`**: schema and semantic check (`issues`), and the absolute offsets the document deliberately does not store.
8. **`render`**: see below.
9. **`schema`**: the JSON Schema of the document (`paces schema --output step-document.schema.json`), for another language, a form, or an agent checking a document. Synthetic pass/fail example documents ship as package data under `paces/data/fixtures/`.

## Rendering

`paces render document.json --renderer <name> --output <path>`

| renderer | writes | use it for |
|---|---|---|
| `html` (default) | one practice page, with a count-along transport when the document has a tempo | a quick page |
| `flow` | a **folder**: a static step-through player, `document.json`, `strings.json`, the media | stepping through a routine on a phone: manual (buttons, keys, swipe) or timed (by the grid, or by a seconds-per-rep or per-step the viewer sets). A second routine is only a different `document.json`. Serve the folder over http (opened straight from disk it falls back to `data.js`). |
| `card` | print HTML (`--output x.html`) or a **PDF** (`--output x.pdf`, needs `paces[pdf]`), `--paper a4\|letter` | a one- or two-sheet printable card: structure with counts, a row per step with poster, cues and cautions |

**Artifact roles shown:** `clip` (a looping video, paired with the `poster` of the same file name), `gif` and `poster`; the card shows posters only. An artifact with any other role is not shown, and `render` warns naming the step and its roles when a step has artifacts and none can be shown. Among alternatives the main artifact is the one with `attrs.main` true, else the first; `attrs.label` captions it and `attrs.position` (`start`, `mid`, `end`) orders a card's posters.

Tags the renderers understand on a step: `learner-led` (no fixed length: shown as "as needed", timed mode waits for the viewer) and `between-passes` (a rest dropped from the last pass of a repeat).

When media lives outside the output folder, say where: `--media-from DIR` (what the document's relative uris are relative to; default the document's folder) and `--media-root DIR` (the boundary files may be read from; default `--media-from`; widen it for `../media/...`). The card shows each step's posters, as a start and end pair when there are two.

"What you need" on the card is the document's `resources` (and `notes` are printed too; a cue's `label` is shown beside it). Words the player and the card say that the document does not are in one strings table each, overridable (a translation is a table, not a fork). If a PDF is requested without the extra, the error says what to install.

## Honesty rules (do not bend them)

- **A segmenter never returns a step count it has no evidence for.** It returns one of: confident, found-but-unnamed, proposed-and-uncertain, or refused (`no-signal`, with a suggestion). It does not raise for "cannot tell". Never fill in a count to make a page look complete; say what was unknown and offer `ask`.
- **Uncertainty is content.** Open questions and flags travel in the document; do not strip them.
- **Human decisions are locks.** Re-running never overwrites a locked field; use `edit` to change one, `merge` to bring in a regeneration.
- **No floats on the wire; no seconds stored.** Times are decimal strings; durations are in the domain's own unit (`eight`, `rep`, `second`); absolute times come from `resolve`. A renderer that needs seconds (timed mode) takes them from the viewer's settings, not the document.
- **Rights are content.** Sources carry `rights` and `attribution`; keep them, and do not republish someone else's media without them.
- The document never carries how an artifact was made, only what it is.
