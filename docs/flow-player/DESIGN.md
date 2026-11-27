# Flow player: design brief

The static step-through player that `render(document, renderer="flow", output=...)` writes. Source: `paces/data/flow/`. This brief describes the current build (v2); the decisions behind it are in the section at the end.

## Kind, person, tasks

- **Kind:** a stage with an outline: one step on stage at a time, the whole routine one tap away.
- **Person and device:** someone learning or running a routine, on a phone propped up or in hand, often standing away from it, sometimes on a laptop.
- **Top three tasks:** (1) see this step and what to do in it; (2) move between steps without looking for the control; (3) let it pace me (timed mode), and change the pace.

## Direction

A warm ground, a heat ramp from amber to rose across the groups of the routine, a condensed display face for names, a humanist sans for reading, a mono for counts. Dark is the native mode; a light mode ships under `prefers-color-scheme` (a darker accent so white on it reaches 4.5:1; a solid ink title). The ribbon is the signature: one cell per step coloured by group, a gap between groups and a smaller one between rounds, a progress fill on the running cell.

## Layout (stage with outline)

- **Phone:** a header (title clamped to two lines, mode and pace chips), the strip (one 48 px button to the all-steps sheet), the card, and a fixed bar at thumb reach (previous, a 64 px round play/pause or "Ready", next or Finish). On a step the card reads: context line (20 px: "round 2 of 3 · step 1 of 3", rests are not numbered), the name beside the big count, the progress bar, the media with a loops-only versions switcher, the description, at most three cues grouped by kind, an "All N cues" disclosure, and the next step.
- **Wide (900 px and up):** the card in the left column, the outline of every step (nested, with round and count) in the right, on the overview as well as on steps; a per-step ribbon with a mouse. The bar's inner box is as wide as the layout.

## Actions, tiered

1. Bar: previous, next (Finish on the last step), play/pause/ready (timed). Top: mode, pace.
2. Strip or ribbon cell and outline row: jump to a step.
3. Keyboard: arrows, space (play), `t` (mode), Escape (close the sheet). Swipe on the card.

## Words and icons

Chevrons, play, pause, check, list and close are inline SVG, one stroke style. Every word comes from `strings.json` or the document; the player contains none about any particular routine. The strings table carries unit plural forms, cue-kind headings and the caution kinds.

## Behaviour contract

- The position moves through one function, `advance`. Manual input and the timed clock call it; a third mode (advance on an external event) is one more caller.
- The clock is `stopSeconds(document, stop, settings)`: grid unit x subdivisions at the tempo; seconds as given; otherwise reps x seconds-per-rep or one time per step; `null` for a learner-led step (it waits). The document stores no seconds.
- `#s=N` in the URL is the position; a link with it skips the overview.
- `prefers-reduced-motion` removes transitions. Both colour modes ship. No network request is made.

## Out of scope

Drawing bodies, scoring, anything that needs a camera.

## v2 (paces#81): the rebuild, and the UX read behind it

An independent critique of a real workout-circuit document (phone and desktop, light and dark) and a read from the `ux-expert` agent drove this. The decisions, so the next change does not re-derive them:

- **Views.** An overview (full title, counts, estimated time at the current pace, one large Start for timed mode, "Step through" second, what you need and the notes), a step, and a done card (total time, Restart). A link with `#s=N` skips the overview. The overview is not a step and is outside the step count.
- **The big count** sits under the media beside the step name, never on top of it, in the same place in manual and timed mode so the layout does not jump: manual shows the target ("7 reps"); timed shows what is being counted: time left (`0:23`) for a step in seconds or paced per step, `3 / 7` when paced by repetitions, the eight count with the beat dots on a grid. One progress, shown twice: the bar under the count and the cell in the ribbon.
- **Rests.** A `learner-led` step waits for the viewer in timed mode: it counts up and the play button becomes "Ready" in the same place. A fixed-length rest counts down; in manual mode it does not advance by itself (the viewer chose manual). During any rest the card shows what comes next with its picture. A `between-passes` child is dropped from the last pass (in `buildStops`, so manual mode and the step count agree).
- **Sound** is on in timed mode only, and pressing Start is the consent (the person is standing away from the phone): 3-2-1 pips and a change tone for steps in seconds, a soft tick per repetition for repetition-paced steps, a two-note finish, a 5 s get-ready count-in. When the grid's beat click is on, the change tone is dropped (the accented downbeat already marks the change). Setting: Sounds. Visuals never flash.
- **Screen wake lock**: while playing by default; the Pace panel offers while open or never. Released on pause, finish and mode change; re-requested when the page becomes visible; the clock pauses when the page is hidden and says so, so it never jumps silently. Needs https (not available from a file).
- **Ribbon.** On a phone: a display-only strip fitted to the width, a wider gap between groups than between rounds, as one 48 px button that opens an all-steps sheet (56 px rows, jumping closes it, playback keeps going, its own history entry so Back closes it). With a mouse and room: one target per step.
- **Cues.** At most 3 up front (5 on desktop), grouped by kind with a heading from the strings table, set-up first, cautions always shown; everything else, the captions and the source links behind one "All N cues" disclosure that stays open once opened. Links into a source are shown only when the source has a web address.
- **Versions.** Alternatives among a step's artifacts are a small switcher; the main one is marked (`attrs.main`, else the first), a label comes from `attrs.label`.
- **Fonts and network.** The stylesheet names the three faces; shipping them is a separate change. The folder fetches nothing.
- **Not built, on purpose.** Vibration, a hidden-video wake-lock fallback, per-step custom rest lengths.
