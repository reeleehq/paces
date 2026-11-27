"""Where a document's relative media lives, and the one boundary it is read within.

A document's artifact uris are relative to a *base* folder (``media_from``,
usually the document's own folder). Reading them is confined to a *root*
(``media_root``, by default the base itself), so a document cannot name a file
the caller did not mean to expose; a caller whose media sits beside the
document (``../media/a.mp4``) widens the root explicitly. Both renderers that
read files (flow copies them, card embeds posters) resolve through here.
"""

from __future__ import annotations

import re
from pathlib import Path

_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def is_relative_path(uri: str) -> bool:
    """A file path relative to the document: no scheme, no leading slash or drive."""
    return not (uri.startswith(("/", "\\")) or _SCHEME.match(uri))


def resolve_media(
    uri: str, media_from: str | Path | None, media_root: str | Path | None = None
) -> Path | None:
    """The file ``uri`` names, or ``None`` when it is not a relative path, there
    is no base, or the file does not exist.

    Raises ``ValueError`` when the uri leaves the root (``media_root``, default
    ``media_from``): the caller must widen it on purpose.
    """
    if media_from is None or not is_relative_path(uri):
        return None
    base = Path(media_from).resolve()
    root = Path(media_root).resolve() if media_root is not None else base
    if root != base and root not in base.parents:
        raise ValueError(
            f"the media root {root} must contain the media base {base} "
            "(media_from); widen media_root to a parent folder"
        )
    path = (base / uri).resolve()
    if path != root and root not in path.parents:
        raise ValueError(
            f"artifact uri {uri!r} resolves outside the media root {root}; "
            "pass the folder that holds the media as media_root / --media-root"
        )
    return path if path.is_file() else None


#: The artifact roles the renderers can show (flow: clip, gif, poster; card:
#: poster). Kept equal to ``SHOWN_ROLES`` in ``flow-core.js`` by a test.
SHOWN_ROLES = ("clip", "gif", "poster")


def unshowable_steps(doc) -> list[tuple[str, list[str]]]:
    """Steps that have artifacts, none of which has a role a renderer knows, as
    ``(step id, roles)``: such a step would render an empty box."""

    def walk(steps):
        for step in steps:
            yield step
            yield from walk(step.steps)

    found = []
    for step in walk(doc.steps):
        roles = sorted({a.role for a in step.artifacts})
        if roles and not any(role in SHOWN_ROLES for role in roles):
            found.append((step.id, roles))
    return found


def warn_unshowable(doc, renderer: str, *, stacklevel: int = 2) -> None:
    """Warn, naming steps and roles, about artifacts ``renderer`` cannot show."""
    import warnings

    found = unshowable_steps(doc)
    if found:
        listed = "; ".join(f"{i} ({', '.join(r)})" for i, r in found[:5])
        warnings.warn(
            f"{len(found)} step(s) have artifacts {renderer} cannot show "
            f"(it shows roles {', '.join(SHOWN_ROLES)}): {listed}"
            + (" ..." if len(found) > 5 else ""),
            stacklevel=stacklevel,
        )
