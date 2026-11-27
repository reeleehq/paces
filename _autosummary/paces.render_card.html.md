# paces.render_card

The card renderer: one routine on a printable card, as HTML or PDF.

`render_card(doc)` returns a self-contained, print-styled HTML page: the
title, what you need, the structure with counts, and a row per step with its
poster, description, cues and cautions. It fits one or two sheets, A4 or
Letter (`@page` carries the paper size), and uses plain tables and no script
so even an old print engine lays it out. Posters are embedded as data URIs
when `media_from` is given, so the card is one file.

`write_card_pdf` turns that page into a PDF through the fleet’s converter,
`pdfdol`, an optional extra (`paces[pdf]`): the model and every renderer
stay pydantic-only (ADR-0004), and importing this module imports nothing
heavy. Without the extra, asking for a PDF says exactly what to install.

The card reads the document and one strings table; it never depends on the
analyser. “What you need” is the document’s `resources` and “Notes” its
`notes`; a cue’s `label` is printed beside it.

### Module Attributes

| [`MAX_EMBED_BYTES`](#paces.render_card.MAX_EMBED_BYTES)   | Posters bigger than this are not embedded (a card is a printout).   |
|--------------------------------------------------------------------|---------------------------------------------------------------------|
| [`PIC_MM`](#paces.render_card.PIC_MM)            | Width of one picture on the card, in mm.                            |
| [`PIC_H_MM`](#paces.render_card.PIC_H_MM)          | Height of the picture block, in mm.                                 |
| [`MAX_PICTURES`](#paces.render_card.MAX_PICTURES)      | the start and end of the main variant.                              |

### Functions

| [`group_cues`](#paces.render_card.group_cues)(cues, strings)                         | Cues grouped by kind, in reading order: the `kind_first` kinds (set-up), then the cautions, then every other kind in first-seen order.   |
|----------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| [`render_card`](#paces.render_card.render_card)(doc, \*[, paper, media_from, ...])    | The print-styled card page for `doc` (self-contained HTML).                                                                              |
| [`write_card_pdf`](#paces.render_card.write_card_pdf)(page, output, \*[, paper, engine]) | Convert a card page to a PDF at `output` through `pdfdol`.                                                                               |

### paces.render_card.MAX_EMBED_BYTES *= 400000*

Posters bigger than this are not embedded (a card is a printout).

### paces.render_card.MAX_PICTURES *= 2*

the start and end of the
main variant. Alternatives do not belong on a printed card.

* **Type:**
  A step’s picture block holds at most this many pictures

### paces.render_card.PIC_H_MM *= 26*

Height of the picture block, in mm. Pictures are fitted inside it (contain).

### paces.render_card.PIC_MM *= 21*

Width of one picture on the card, in mm.

### paces.render_card.group_cues(cues, strings)

Cues grouped by kind, in reading order: the `kind_first` kinds (set-up),
then the cautions, then every other kind in first-seen order.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)]]

### paces.render_card.render_card(doc, , paper='a4', media_from=None, media_root=None, strings=None)

The print-styled card page for `doc` (self-contained HTML).

`paper` is `"a4"` or `"letter"`. `media_from` is the folder the
document’s relative poster uris are relative to; posters found there are
embedded. `strings` overrides entries of the default strings table.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### paces.render_card.write_card_pdf(page, output, , paper='a4', engine=None)

Convert a card page to a PDF at `output` through `pdfdol`.

`engine=None` is pdfdol’s default (wkhtmltopdf); `engine="chromium"`
prints with headless Chromium (needs `pdfdol[chromium]`). Raises
`RuntimeError` naming exactly what to install when something is missing.

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)
