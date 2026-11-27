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


def _is_local(uri: str) -> bool:
    return not uri.startswith(("http://", "https://", "/", "data:"))


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


def _copy_media(doc: StepDocument, media_from: Path | None, out: Path) -> list[str]:
    """Copy each relative artifact into the output folder at the same relative
    path (the document's uris are document-relative). Returns the uris that
    could not be found, so the caller can say so instead of shipping dead clips."""
    missing: list[str] = []
    for step in _steps(doc.steps):
        for artifact in step.artifacts:
            if not _is_local(artifact.uri):
                continue
            target = (out / artifact.uri).resolve()
            if out.resolve() not in target.parents:
                raise ValueError(
                    f"artifact uri escapes the output folder: {artifact.uri!r}"
                )
            source = (media_from / artifact.uri) if media_from else None
            if source is not None and source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.resolve() != target:
                    shutil.copyfile(source, target)
            elif not target.is_file():
                missing.append(artifact.uri)
    return missing


def render_flow(
    doc: StepDocument,
    output_dir: str | Path,
    *,
    media_from: str | Path | None = None,
    strings: Mapping | None = None,
) -> Path:
    """Write the player folder for ``doc`` into ``output_dir`` and return it.

    ``media_from`` is the folder the document's relative artifact uris are
    relative to (usually the document's own folder); the files are copied to the
    same relative paths in the output. ``strings`` overrides entries of the
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
    missing = _copy_media(doc, Path(media_from) if media_from else None, out)
    if missing:
        import warnings

        warnings.warn(
            f"{len(missing)} media file(s) the document points at were not found "
            f"and are missing from {out}: {', '.join(missing[:5])}"
            + (" ..." if len(missing) > 5 else ""),
            stacklevel=2,
        )
    return out
