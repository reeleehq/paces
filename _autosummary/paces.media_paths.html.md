# paces.media_paths

Where a document’s relative media lives, and the one boundary it is read within.

A document’s artifact uris are relative to a *base* folder (`media_from`,
usually the document’s own folder). Reading them is confined to a *root*
(`media_root`, by default the base itself), so a document cannot name a file
the caller did not mean to expose; a caller whose media sits beside the
document (`../media/a.mp4`) widens the root explicitly. Both renderers that
read files (flow copies them, card embeds posters) resolve through here.

### Functions

| [`is_relative_path`](#paces.media_paths.is_relative_path)(uri)                        | A file path relative to the document: no scheme, no leading slash or drive.                                   |
|-----------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| [`resolve_media`](#paces.media_paths.resolve_media)(uri, media_from[, media_root]) | The file `uri` names, or `None` when it is not a relative path, there is no base, or the file does not exist. |

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
