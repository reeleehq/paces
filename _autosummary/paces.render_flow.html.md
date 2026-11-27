# paces.render_flow

The flow renderer: a static step-through player for any document.

`render_flow(doc, "out/")` writes a folder: the player (HTML, CSS and vanilla
JS shipped as package data under `paces/data/flow/`, no build step),
`document.json` (the document, loaded by the player at run time),
`strings.json` (every word the player says that the document does not), a
`data.js` copy of both for a folder opened straight from disk, and the media
the document’s artifacts point at. A second routine is a different
`document.json` and nothing else.

Like [`paces.render`](paces.render.html.md#module-paces.render), this depends on the document only, never on the
analyser, and on pydantic alone (ADR-0004): the player’s files are copied, not
generated.

### Module Attributes

| [`PLAYER_FILES`](#paces.render_flow.PLAYER_FILES)   | The player's own files, copied verbatim from package data.   |
|-----------------------------------------------------------------|--------------------------------------------------------------|

### Functions

| [`default_strings`](#paces.render_flow.default_strings)()                       | The player's one strings table, as shipped (English).              |
|------------------------------------------------------------------------------------------|--------------------------------------------------------------------|
| [`render_flow`](#paces.render_flow.render_flow)(doc, output_dir, \*[, ...]) | Write the player folder for `doc` into `output_dir` and return it. |

### paces.render_flow.PLAYER_FILES *= ('index.html', 'flow.css', 'flow-core.js', 'flow.js')*

The player’s own files, copied verbatim from package data.

### paces.render_flow.default_strings()

The player’s one strings table, as shipped (English).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### paces.render_flow.render_flow(doc, output_dir, , media_from=None, media_root=None, strings=None)

Write the player folder for `doc` into `output_dir` and return it.

`media_from` is the folder the document’s relative artifact uris are
relative to (usually the document’s own folder). Files are read only within
`media_root` (default `media_from`; widen it for media that lives beside
the document) and are copied to their path relative to that root, which is
where the shipped `document.json` points. `strings` overrides entries of the
default strings table (a translation, a different word for “Start”).
Warns, naming them, about artifacts whose files could not be found.

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)
