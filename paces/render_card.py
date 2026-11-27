"""The card renderer: one routine on a printable card, as HTML or PDF.

``render_card(doc)`` returns a self-contained, print-styled HTML page: the
title, what you need, the structure with counts, and a row per step with its
poster, description, cues and cautions. It fits one or two sheets, A4 or
Letter (``@page`` carries the paper size), and uses plain tables and no script
so even an old print engine lays it out. Posters are embedded as data URIs
when ``media_from`` is given, so the card is one file.

``write_card_pdf`` turns that page into a PDF through the fleet's converter,
``pdfdol``, an optional extra (``paces[pdf]``): the model and every renderer
stay pydantic-only (ADR-0004), and importing this module imports nothing
heavy. Without the extra, asking for a PDF says exactly what to install.

The card reads the document and one strings table; it never depends on the
analyser. "What you need" is the document's ``resources`` and "Notes" its
``notes``; a cue's ``label`` is printed beside it.
"""

from __future__ import annotations

import base64
import html
import mimetypes
import shutil
from collections.abc import Mapping
from pathlib import Path

from paces.model import Step, StepDocument

PAPERS = {"a4": "A4", "letter": "Letter"}
DFLT_PAPER = "a4"
#: Posters bigger than this are not embedded (a card is a printout).
MAX_EMBED_BYTES = 400_000
#: Width of one picture on the card, in mm.
PIC_MM = 28

DEFAULT_STRINGS = {
    "needs": "What you need",
    "notes": "Notes",
    "structure": "Structure",
    "steps": "Steps",
    "start": "Start",
    "end": "End",
    "optional": "optional",
    "variant_of": "variant of {step}",
    "round_count": "{n} ×",
    "in_all": "{count} in all",
    "cue_kinds": {
        "setup": "Set-up",
        "technique": "Technique",
        "fault": "Avoid",
        "breath": "Breathing",
        "safety": "Safety",
        "warning": "Careful",
        "caution": "Careful",
        "count": "Count",
        "lyric": "Lyric",
        "caption": "Note",
    },
    "learner_led": "as needed",
    "between_passes": "between passes",
    "rounds": "{n} rounds",
    "units": {
        "rep": ["rep", "reps"],
        "eight": ["eight", "eights"],
        "bar": ["bar", "bars"],
        "second": ["second", "seconds"],
        "minute": ["minute", "minutes"],
        "set": ["set", "sets"],
    },
    "caution_kinds": ["warning", "caution", "fault", "safety"],
    "kind_first": ["setup"],
}

#: Plain CSS: tables and blocks only (no grid, no flex), so an old print engine
#: lays it out the same as a modern one. Sizes are in pt and mm.
_CSS = """
@page { size: %(paper)s; margin: 14mm 13mm; }
* { box-sizing: border-box; }
body { margin: 0; color: #1c1a22; font: 10pt/1.4 "Helvetica Neue", Arial, sans-serif; }
h1 { font-size: 20pt; line-height: 1.1; margin: 0 0 2mm; }
h2 { font-size: 9pt; letter-spacing: .12em; text-transform: uppercase; color: #5b4a73;
     margin: 6mm 0 2mm; border-bottom: .3mm solid #cfc6de; padding-bottom: 1mm; }
ul.needs { margin: 0; padding-left: 5mm; }
p.note { margin: 0 0 1.5mm; }
table { width: 100%%; border-collapse: collapse; }
td { vertical-align: top; padding: 2mm 2mm 2mm 0; }
tr.step { page-break-inside: avoid; border-bottom: .2mm solid #e3dcee; }
td.pic .fig { display: inline-block; vertical-align: top; width: 28mm; margin-right: 2mm; }
td.pic img { width: 28mm; height: auto; display: block; border: .2mm solid #cfc6de; }
td.pic .fig span { display: block; font-size: 7pt; text-align: center; color: #5b4a73; }
td.num { width: 8mm; font-weight: bold; color: #5b4a73; }
td.count { width: 24mm; text-align: right; white-space: nowrap; font-weight: bold; }
tr.group td { padding-top: 3mm; font-weight: bold; }
tr.nested td.name { padding-left: 4mm; }
.name b { font-size: 11pt; }
.desc { margin: .5mm 0 0; font-weight: normal; }
.cuegroup { margin: 1mm 0 0; }
.cuegroup > span { font-size: 7pt; letter-spacing: .1em; text-transform: uppercase; color: #5b4a73; font-weight: normal; }
.cue { margin: .4mm 0 0; padding-left: 2mm; border-left: .8mm solid #7c3aed; font-style: italic; font-weight: normal; }
.cue.caution { border-left-color: #c0143c; font-style: normal; }
.cue span { font-size: 7pt; letter-spacing: .1em; text-transform: uppercase; font-style: normal; color: #5b4a73; }
.badge { color: #5b4a73; font-size: 8pt; }
.outline, .outline ul { margin: 0; padding-left: 6mm; }
.outline li { margin: .4mm 0; }
footer { margin-top: 6mm; color: #5b4a73; font-size: 8pt; }
"""


def _merged(overrides: Mapping | None) -> dict:
    """The default strings with ``overrides`` applied (one level deep for the
    nested tables), so a translation need only give the words it changes."""
    table = {
        k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULT_STRINGS.items()
    }
    for key, value in (overrides or {}).items():
        if isinstance(value, Mapping) and isinstance(table.get(key), dict):
            table[key] = {**table[key], **value}
        else:
            table[key] = value
    return table


def _count(measure, strings: dict) -> str:
    forms = strings["units"].get(measure.unit)
    one = float(measure.value) == 1
    word = (forms[0] if one else forms[1]) if forms else measure.unit
    return f"{measure.value} {word}"


def _learner_led(step: Step) -> bool:
    return "learner-led" in step.tags


def _step_count(step: Step, strings: dict) -> str:
    """What a step's count column says: its count in the domain's unit, or
    "as needed" for a step the learner leads (its duration is a placeholder)."""
    if _learner_led(step):
        return strings["learner_led"]
    return _rounds(step, strings) + _count(step.duration, strings)


def _rounds(step: Step, strings: dict) -> str:
    return f"{strings['round_count'].format(n=step.repeat)} " if step.repeat > 1 else ""


#: Where a poster sits in the movement; the card shows start before mid before end.
_POSITION_RANK = {"start": 0, "mid": 1, "end": 2}


def _poster_srcs(
    step: Step, media_from: Path | None, media_root: Path | None
) -> list[tuple[str, str | None]]:
    """The step's posters, in order, as data URIs (embedded, so the card is one
    file). Posters whose file is missing, too big, or not a relative path are
    left out; a remote poster is left out too: printing must not fetch from the
    network. Raises ``ValueError`` for a uri that leaves the media root."""
    from paces.media_paths import resolve_media

    out = []
    posters = [a for a in step.artifacts if a.role == "poster"]
    posters.sort(key=lambda a: _POSITION_RANK.get(str(a.attrs.get("position")), 1))
    for artifact in posters:
        path = resolve_media(artifact.uri, media_from, media_root)
        if path is None or path.stat().st_size > MAX_EMBED_BYTES:
            continue
        mime = artifact.mime or mimetypes.guess_type(path.name)[0] or "image/jpeg"
        data = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
        out.append((data, artifact.attrs.get("label")))
    return out


def _cue_label(cue) -> str:
    return f" <b>{html.escape(cue.label)}</b>" if cue.label else ""


def _resource_item(resource, strings: dict) -> str:
    text = html.escape(resource.name)
    if resource.quantity is not None:
        text = f"{html.escape(_count(resource.quantity, strings))} · {text}"
    if resource.optional:
        text += f" <i>({html.escape(strings['optional'])})</i>"
    if resource.note:
        text += f" — {html.escape(resource.note)}"
    return f"<li>{text}</li>"


def _kind_label(kind: str, strings: dict) -> str:
    """A cue kind's heading: from the strings table, else the kind's own name."""
    return strings["cue_kinds"].get(kind, kind)


def group_cues(cues: list, strings: dict) -> list[tuple[str, list]]:
    """Cues grouped by kind, in reading order: the ``kind_first`` kinds (set-up),
    then the cautions, then every other kind in first-seen order."""
    kinds: list[str] = []
    for cue in cues:
        if cue.kind not in kinds:
            kinds.append(cue.kind)

    def rank(kind: str) -> int:
        if kind in strings["kind_first"]:
            return 0
        return 1 if kind in strings["caution_kinds"] else 2

    kinds.sort(key=rank)  # stable: first-seen order within a rank
    return [(k, [c for c in cues if c.kind == k]) for k in kinds]


def _cue_html(cues: list, strings: dict) -> str:
    """A step's cues, one block per kind: a heading, then the lines."""
    blocks = []
    for kind, group in group_cues(cues, strings):
        caution = kind in strings["caution_kinds"]
        lines = "".join(
            f'<p class="cue{" caution" if caution else ""}">'
            f"{_cue_label(cue).strip()}{' ' if cue.label else ''}{html.escape(cue.text)}</p>"
            for cue in group
        )
        blocks.append(
            f'<div class="cuegroup"><span>{html.escape(_kind_label(kind, strings))}</span>{lines}</div>'
        )
    return "".join(blocks)


def _pictures(imgs: list[tuple[str, str | None]], strings: dict) -> str:
    """One picture, or a start and end pair, or all of them in order. An
    artifact's own ``label`` is its caption; a bare pair is Start and End."""
    pair = [strings["start"], strings["end"]] if len(imgs) == 2 else [""] * len(imgs)
    figures = []
    for (src, own), default in zip(imgs, pair):
        label = own or default
        caption = f"<span>{html.escape(str(label))}</span>" if label else ""
        figures.append(
            f'<div class="fig"><img src="{html.escape(src)}" alt="">{caption}</div>'
        )
    return "".join(figures)


def _step_row(step: Step, *, number, nested, cues, strings, imgs, pic_width) -> str:
    pic = _pictures(imgs, strings)
    badges = []
    if step.optional:
        badges.append(strings["optional"])
    if step.variant_of:
        badges.append(strings["variant_of"].format(step=step.variant_of))
    if "between-passes" in step.tags:
        badges.append(strings["between_passes"])
    badge = (
        f'<div class="badge">{html.escape(" · ".join(badges))}</div>' if badges else ""
    )
    desc = (
        f'<p class="desc">{html.escape(step.description)}</p>'
        if step.description
        else ""
    )
    count = _step_count(step, strings)
    row_class = "step nested" if nested else "step"
    pic_cell = (
        f'<td class="pic" style="width:{pic_width}mm">{pic}</td>' if pic_width else ""
    )
    cue_html = _cue_html(cues, strings)
    return (
        f'<tr class="{row_class}">'
        f'<td class="num">{number}</td>'
        f"{pic_cell}"
        f'<td class="name"><b>{html.escape(step.name)}</b>{badge}{desc}'
        f"{cue_html}</td>"
        f'<td class="count">{html.escape(count)}</td></tr>'
    )


def _group_row(step: Step, cues: list, strings: dict, span: int) -> str:
    """A heading row for a step that has children: its name and repeat, its own
    description and the cues anchored to it."""
    desc = (
        f'<p class="desc">{html.escape(step.description)}</p>'
        if step.description
        else ""
    )
    own = _cue_html(cues, strings)
    title = html.escape(f"{_rounds(step, strings)}{step.name}")
    return f'<tr class="group"><td colspan="{span}">{title}{desc}{own}</td></tr>'


def _outline_item(step: Step, strings: dict) -> str:
    if step.steps:
        # a group's duration is the total, repeats included (validate_document)
        total = strings["in_all"].format(count=_count(step.duration, strings))
        note = (
            f"{strings['rounds'].format(n=step.repeat)} · {total}"
            if step.repeat > 1
            else total
        )
        inner = "".join(_outline_item(child, strings) for child in step.steps)
        return f"<li>{html.escape(step.name)} <i>({html.escape(note)})</i><ul>{inner}</ul></li>"
    counts = html.escape(_step_count(step, strings))
    mark = (
        f" <i>({html.escape(strings['between_passes'])})</i>"
        if "between-passes" in step.tags
        else ""
    )
    return f"<li>{html.escape(step.name)} — {counts}{mark}</li>"


def render_card(
    doc: StepDocument,
    *,
    paper: str = DFLT_PAPER,
    media_from: str | Path | None = None,
    media_root: str | Path | None = None,
    strings: Mapping | None = None,
) -> str:
    """The print-styled card page for ``doc`` (self-contained HTML).

    ``paper`` is ``"a4"`` or ``"letter"``. ``media_from`` is the folder the
    document's relative poster uris are relative to; posters found there are
    embedded. ``strings`` overrides entries of the default strings table.
    """
    if paper.lower() not in PAPERS:
        raise ValueError(f"unknown paper {paper!r}; available: {sorted(PAPERS)}")
    table = _merged(strings)
    root = Path(media_from) if media_from else None
    cues: dict[str, list] = {}
    for cue in doc.cues:
        cues.setdefault(cue.anchor.step, []).append(cue)

    items = [_resource_item(r, table) for r in doc.resources]
    if not items:
        # 0.0.3x documents kept the list in attrs["render.card"]["needs"]
        legacy = doc.attrs.get("render.card")
        old = legacy.get("needs") if isinstance(legacy, dict) else None
        old = [old] if isinstance(old, str) else old if isinstance(old, list) else []
        items = [f"<li>{html.escape(str(n))}</li>" for n in old]
    needs_html = (
        f'<h2>{html.escape(table["needs"])}</h2><ul class="needs">'
        + "".join(items)
        + "</ul>"
        if items
        else ""
    )
    notes_html = (
        f"<h2>{html.escape(table['notes'])}</h2>"
        + "".join(f'<p class="note">{html.escape(n)}</p>' for n in doc.notes)
        if doc.notes
        else ""
    )

    rows: list[str] = []
    number = 0

    def _all(steps):
        for step in steps:
            yield step
            yield from _all(step.steps)

    # the picture column exists only when some step has a picture to show
    base_root = Path(media_root) if media_root else None
    posters = {st.id: _poster_srcs(st, root, base_root) for st in _all(doc.steps)}
    widest = max((len(v) for v in posters.values()), default=0)
    pic_width = widest * (PIC_MM + 2) + 1 if widest else 0
    with_pics = bool(widest)

    def emit(step: Step, nested: bool) -> None:
        nonlocal number
        if step.steps:
            rows.append(
                _group_row(step, cues.get(step.id, []), table, 4 if with_pics else 3)
            )
            for child in step.steps:
                emit(child, True)
            return
        number += 1
        rows.append(
            _step_row(
                step,
                number=number,
                nested=nested,
                cues=cues.get(step.id, []),
                strings=table,
                imgs=posters[step.id],
                pic_width=pic_width,
            )
        )

    for step in doc.steps:
        emit(step, False)

    credits = f"<footer>{html.escape(doc.credits)}</footer>" if doc.credits else ""
    outline = "".join(_outline_item(s, table) for s in doc.steps)
    css = _CSS % {"paper": PAPERS[paper.lower()]}
    return f"""<!doctype html>
<html lang="{html.escape(doc.lang)}">
<head>
<meta charset="utf-8">
<title>{html.escape(doc.title)}</title>
<style>{css}</style>
</head>
<body>
<h1>{html.escape(doc.title)}</h1>
{needs_html}
{notes_html}
<h2>{html.escape(table["structure"])}</h2>
<ul class="outline">{outline}</ul>
<h2>{html.escape(table["steps"])}</h2>
<table>{"".join(rows)}</table>
{credits}
</body>
</html>
"""


# ── PDF (optional extra) ───────────────────────────────────────────────────

PDF_EXTRA_HINT = (
    "PDF output needs the optional extra: install paces[pdf] "
    "(pip install 'paces[pdf]'). It pulls pdfdol, whose default engine also "
    "needs the wkhtmltopdf program (brew install wkhtmltopdf, or "
    "apt-get install wkhtmltopdf)."
)


def write_card_pdf(
    page: str,
    output: str | Path,
    *,
    paper: str = DFLT_PAPER,
    engine: str | None = None,
) -> Path:
    """Convert a card page to a PDF at ``output`` through ``pdfdol``.

    ``engine=None`` is pdfdol's default (wkhtmltopdf); ``engine="chromium"``
    prints with headless Chromium (needs ``pdfdol[chromium]``). Raises
    ``RuntimeError`` naming exactly what to install when something is missing.
    """
    try:
        import pdfdol
    except ImportError as error:
        raise RuntimeError(PDF_EXTRA_HINT) from error
    if engine is None and shutil.which("wkhtmltopdf") is None:
        raise RuntimeError(
            "wkhtmltopdf is not installed (it is pdfdol's default engine): "
            "brew install wkhtmltopdf, or apt-get install wkhtmltopdf; "
            "or pass engine='chromium' (with the pdfdol[chromium] extra)."
        )
    size = PAPERS[paper.lower()]
    if engine == "chromium":
        try:
            pdfdol.get_pdf(
                page,
                str(output),
                src_kind="html",
                engine="chromium",
                page_format=size,
                media="print",
                margin="14mm 13mm",
                keep_together="tr.step",
            )
        except ImportError as error:
            raise RuntimeError(
                "engine='chromium' needs the pdfdol[chromium] extra and "
                "'playwright install chromium'."
            ) from error
    else:
        pdfdol.get_pdf(
            page,
            str(output),
            src_kind="html",
            options={
                "page-size": size,
                "margin-top": "14mm",
                "margin-bottom": "14mm",
                "margin-left": "13mm",
                "margin-right": "13mm",
                "encoding": "UTF-8",
                "disable-smart-shrinking": "",
            },
        )
    return Path(output)
