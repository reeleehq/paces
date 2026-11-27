"""The flow renderer: a static step-through player for any document.

``render_flow(doc, "out/")`` writes a folder: the player (HTML, CSS and vanilla
JS shipped as package data under ``paces/data/flow/``, no build step),
``document.json`` (the document, loaded by the player at run time),
``strings.json`` (every word the player says that the document does not), a
``data.js`` copy of both for a folder opened straight from disk, and the media
the document's artifacts point at. A second routine is a different
``document.json`` and nothing else.

Like :mod:`paces.render`, this depends on the document only, never on the
analyser, and on pydantic alone (ADR-0004): the player's files are copied, not
generated.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Iterator, Mapping
from importlib import resources
from pathlib import Path

from paces.model import Step, StepDocument, dumps_document

#: The player's own files, copied verbatim from package data.
PLAYER_FILES = ("index.html", "flow.css", "flow-core.js", "flow.js")
STRINGS_FILE = "strings.json"


def _steps(steps: list[Step]) -> Iterator[Step]:
    for step in steps:
        yield step
        yield from _steps(step.steps)


def default_strings() -> dict:
    """The player's one strings table, as shipped (English)."""
    text = (
        resources.files("paces")
        .joinpath("data", "flow", STRINGS_FILE)
        .read_text(encoding="utf-8")
    )
    return json.loads(text)


def _merged_strings(overrides: Mapping | None) -> dict:
    """The default table with ``overrides`` applied; one level deep for the
    nested tables (``units``, ``roles``), so a translation need only give the
    words it changes."""
    table = default_strings()
    for key, value in (overrides or {}).items():
        if isinstance(value, Mapping) and isinstance(table.get(key), dict):
            table[key] = {**table[key], **value}
        else:
            table[key] = value
    return table


def _ship_media(
    doc: StepDocument,
    media_from: Path | None,
    media_root: Path | None,
    out: Path,
) -> tuple[StepDocument, list[str]]:
    """Copy each artifact's file into the output folder and return the document
    to ship plus the uris that could not be shipped.

    The shipped path is the file's path relative to the media root, so media that
    lives beside the document (outside the output folder) lands under the output
    folder and the shipped document points there. With the default root (the
    base folder) a uri keeps its own path. Web uris are left alone; uris that
    are not relative paths, or whose file is missing, are reported."""
    from paces.media_paths import is_relative_path, resolve_media

    shipped = doc.model_copy(deep=True)
    unshipped: list[str] = []
    out_root = out.resolve()
    root = (
        Path(media_root or media_from).resolve() if (media_root or media_from) else None
    )
    for step in _steps(shipped.steps):
        for artifact in step.artifacts:
            uri = artifact.uri
            if uri.startswith(("http://", "https://")):
                continue  # the player loads it from where it is
            if not is_relative_path(uri):
                unshipped.append(uri)
                continue
            if media_from is None:
                if not (out_root / uri).resolve().is_file():
                    unshipped.append(uri)
                continue
            source = resolve_media(uri, media_from, media_root)
            if source is None:
                unshipped.append(uri)
                continue
            relative = source.relative_to(root).as_posix()
            target = (out_root / relative).resolve()
            if out_root not in target.parents:
                raise ValueError(f"artifact uri escapes the output folder: {uri!r}")
            if source != target:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            artifact.uri = relative
    return shipped, unshipped


def render_flow(
    doc: StepDocument,
    output_dir: str | Path,
    *,
    media_from: str | Path | None = None,
    media_root: str | Path | None = None,
    strings: Mapping | None = None,
) -> Path:
    """Write the player folder for ``doc`` into ``output_dir`` and return it.

    ``media_from`` is the folder the document's relative artifact uris are
    relative to (usually the document's own folder). Files are read only within
    ``media_root`` (default ``media_from``; widen it for media that lives beside
    the document) and are copied to their path relative to that root, which is
    where the shipped ``document.json`` points. ``strings`` overrides entries of the
    default strings table (a translation, a different word for "Start").
    Warns, naming them, about artifacts whose files could not be found.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    package = resources.files("paces").joinpath("data", "flow")
    for name in PLAYER_FILES:
        (out / name).write_text(
            package.joinpath(name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    doc, missing = _ship_media(
        doc,
        Path(media_from) if media_from else None,
        Path(media_root) if media_root else None,
        out,
    )
    document_text = dumps_document(doc)
    table = _merged_strings(strings)
    (out / "document.json").write_text(document_text, encoding="utf-8")
    (out / STRINGS_FILE).write_text(
        json.dumps(table, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out / "data.js").write_text(
        "window.PACES_FLOW = "
        + json.dumps(
            {"document": json.loads(document_text), "strings": table},
            ensure_ascii=False,
        )
        + ";\n",
        encoding="utf-8",
    )
    if missing:
        import warnings

        warnings.warn(
            f"{len(missing)} media file(s) the document points at were not shipped "
            f"to {out} (not found, or not a relative path): {', '.join(missing[:5])}"
            + (" ..." if len(missing) > 5 else ""),
            stacklevel=2,
        )
    return out
