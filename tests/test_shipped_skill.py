"""The skill that ships with the package: valid, in the package data, and true
to the CLI it describes."""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path

from paces.tools import _dispatch_funcs

CLI_VERBS = {f.__name__.replace("_", "-") for f in _dispatch_funcs}
SKILL = resources.files("paces").joinpath("data", "skills", "paces", "SKILL.md")


def _front_matter(text: str) -> dict:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert match, "SKILL.md must start with YAML front matter"
    fields = {}
    for key in ("name", "description"):
        found = re.search(rf"^{key}:\s*(>-?\n(?:  .*\n?)+|.*)$", match.group(1), re.M)
        assert found, f"front matter lacks {key}"
        fields[key] = " ".join(found.group(1).replace(">-", "").split())
    return fields


def test_skill_is_in_the_package_data_with_valid_front_matter():
    text = SKILL.read_text(encoding="utf-8")
    fields = _front_matter(text)
    assert fields["name"] == "paces"  # the folder's name
    assert 40 < len(fields["description"]) <= 1024


def test_every_verb_the_skill_names_exists():
    text = SKILL.read_text(encoding="utf-8")
    named = set(re.findall(r"^\d+\. \*\*`([a-z-]+)`\*\*", text, re.M))
    named |= set(re.findall(r"\*\*`([a-z-]+)`\*\*", text))
    assert {"segment", "to-document", "render", "schema", "validate"} <= named
    assert named <= CLI_VERBS, named - CLI_VERBS


def test_every_paces_command_it_shows_names_a_real_verb():
    text = SKILL.read_text(encoding="utf-8")
    for verb in re.findall(r"`paces ([a-z][a-z-]+)", text):
        assert verb in CLI_VERBS, verb


def test_the_renderers_it_lists_are_registered():
    from paces.tools import _RENDERERS

    text = SKILL.read_text(encoding="utf-8")
    for name in re.findall(r"^\| `([a-z]+)`", text, re.M):
        assert name in _RENDERERS, name
    assert {"flow", "card"} <= set(re.findall(r"^\| `([a-z]+)`", text, re.M))


def test_the_claude_code_bridge_is_a_relative_symlink_to_the_shipped_skill():
    link = Path(__file__).parent.parent / ".claude" / "skills" / "paces"
    if not link.is_symlink():
        return  # no .claude/ in an sdist; a Windows checkout without symlinks
    assert not Path(str(link.readlink())).is_absolute()
    assert (link / "SKILL.md").read_text(encoding="utf-8") == SKILL.read_text(
        encoding="utf-8"
    )
