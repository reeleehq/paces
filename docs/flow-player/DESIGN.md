# Flow player: design brief

The static step-through player that `render(document, renderer="flow", output=...)` writes. Source: `paces/data/flow/`.

## Kind, person, tasks

- **Kind:** a reader / stage hybrid: one step on stage at a time, the whole routine one tap away.
- **Person and device:** someone learning or running a routine, on a phone propped up or in hand, often standing away from it, sometimes on a laptop.
- **Top three tasks:** (1) see this step and what to do in it; (2) move to the next or previous step without looking for the control; (3) let it pace me (timed mode), and change the pace.

## Direction

The chosen direction is the one of the hand-built page this generalises: a warm ground, a heat ramp from amber to rose across the groups of the routine, a condensed display face for names, a humanist sans for reading, a mono for counts and labels. Dark is the native mode; a light mode ships under `prefers-color-scheme`. Deliberate delta from the template: the ribbon is the signature, one cell per step, coloured by top-level group, with a progress fill on the running cell.

Fonts (Anton, Karla, DM Mono) load from Google Fonts as an enhancement; the stacks fall back to system faces, so an offline folder still reads well. Nothing else is fetched.

## Layout (archetype: stage with outline)

- **Phone (one column):** one top row (title and position, two chips: mode, pace), then the ribbon, then the card. Controls end at about 13% of the height and the card starts at 14%. A fixed bottom bar holds previous, play (timed mode only) and next, at thumb reach, 56 px targets.
- **Wide (from 900 px):** the card in the left column; the right column is the outline of every step (nested, with round and count), sticky, current highlighted. Content uses more than 75% of the width at 1440 px.
- Pace settings live in a panel opened by the Pace chip: tempo and click when the document has a metric grid; seconds per repetition, seconds per step and which one paces, otherwise.

## Actions, tiered

1. Bar: previous, next, play/pause (timed). Top: mode, pace.
2. Ribbon cell and outline row: jump to a step.
3. Keyboard: arrows, space (play), `t` (mode). Swipe on the card.

## Icons and words

Two chevrons (inline SVG, one stroke style). Everything else is a labelled control. Every word comes from `strings.json` or the document; the player contains none about any particular routine. The strings table also carries the plural forms of units, so "1 rep / 7 reps" is the document's own unit in the viewer's language.

## Behaviour contract

- The position moves through one function, `advance`. Manual input and the timed clock call it; a third mode (advance on an external event) is one more caller.
- The clock is `stopSeconds(document, stop, settings)`: grid unit x subdivisions at the tempo; seconds as given; otherwise reps x seconds-per-rep or one time per step. The document stores no seconds.
- `#s=N` in the URL is the position, so a step can be linked.
- `prefers-reduced-motion` removes transitions. Both colour modes ship.

## Out of scope

Drawing bodies, scoring, anything that needs a camera.
