# paces.media_paths

Where a document’s relative media lives, and the one boundary it is read within.

A document’s artifact uris are relative to a *base* folder (`media_from`,
usually the document’s own folder). Reading them is confined to a *root*
(`media_root`, by default the base itself), so a document cannot name a file
the caller did not mean to expose; a caller whose media sits beside the
document (`../media/a.mp4`) widens the root explicitly. Both renderers that
read files (flow copies them, card embeds posters) resolve through here.

### Module Attributes

| [`SHOWN_ROLES`](#paces.media_paths.SHOWN_ROLES)   | clip, gif, poster; card: poster).   |
|----------------------------------------------------------------|-------------------------------------|

### Functions

| [`is_relative_path`](#paces.media_paths.is_relative_path)(uri)                            | A file path relative to the document: no scheme, no leading slash or drive.                                                         |
|---------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| [`resolve_media`](#paces.media_paths.resolve_media)(uri, media_from[, media_root])     | The file `uri` names, or `None` when it is not a relative path, there is no base, or the file does not exist.                       |
| [`unshowable_steps`](#paces.media_paths.unshowable_steps)(doc)                            | Steps that have artifacts, none of which has a role a renderer knows, as `(step id, roles)`: such a step would render an empty box. |
| [`warn_unshowable`](#paces.media_paths.warn_unshowable)(doc, renderer, \*[, stacklevel]) | Warn, naming steps and roles, about artifacts `renderer` cannot show.                                                               |

### paces.media_paths.SHOWN_ROLES *= ('clip', 'gif', 'poster')*

clip, gif, poster; card:
poster). Kept equal to `SHOWN_ROLES` in `flow-core.js` by a test.

* **Type:**
  The artifact roles the renderers can show (flow

### paces.media_paths.is_relative_path(uri)

A file path relative to the document: no scheme, no leading slash or drive.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### paces.media_paths.resolve_media(uri, media_from, media_root=None)

The file `uri` names, or `None` when it is not a relative path, there
is no base, or the file does not exist.

Raises `ValueError` when the uri leaves the root (`media_root`, default
`media_from`): the caller must widen it on purpose.

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### paces.media_paths.unshowable_steps(doc)

Steps that have artifacts, none of which has a role a renderer knows, as
`(step id, roles)`: such a step would render an empty box.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]]

### paces.media_paths.warn_unshowable(doc, renderer, , stacklevel=2)

Warn, naming steps and roles, about artifacts `renderer` cannot show.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)
