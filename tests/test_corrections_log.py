"""The correction log across renderings, and stored in lacing (paces#34)."""

import pytest

from paces.corrections import (
    Correction,
    forbid,
    from_wire,
    merge,
    migrate_corrections,
    pin,
    replay,
    split,
    stale_corrections,
    to_wire,
)
from paces.segmentation import SegStep, Segmentation
from paces.segmenters import segment


def _shift(t, cuts):
    """mixing's rule, inlined so these tests need no audio extra."""
    cut_before = sum(c["end"] - c["start"] for c in cuts if c["end"] <= t)
    for c in cuts:
        if c["start"] <= t < c["end"]:
            return c["start"] - cut_before
    return t - cut_before


# ── stale corrections ───────────────────────────────────────────────────────


def test_a_correction_from_another_rendering_is_skipped_and_said():
    seg = Segmentation(steps=(SegStep(id="a", spans=((0.0, 10.0),)),), boundaries=(0.0, 10.0))
    log = [split(5, media_key="old"), split(7, media_key="new"), split(3)]
    out = replay(seg, log, media_key="new")
    assert out.boundaries == (0.0, 3.0, 7.0, 10.0)  # 5 was not applied
    assert out.flags[0].startswith("correction-stale: split@5 (made against media 'old'")
    assert "corrected: split@7" in out.flags and "corrected: split@3" in out.flags


def test_without_a_media_key_every_correction_applies():
    seg = Segmentation(steps=(SegStep(id="a", spans=((0.0, 10.0),)),), boundaries=(0.0, 10.0))
    out = replay(seg, [split(5, media_key="old")])
    assert out.boundaries == (0.0, 5.0, 10.0)
    assert not any(f.startswith("correction-stale") for f in out.flags)


def test_segment_holds_stale_corrections_back_from_every_path():
    log = [split(15.0, media_key="v1"), merge(20.0, media_key="v2")]
    seg = segment(boundaries=[0, 10, 20, 30], corrections=log, media_key="v2")
    assert seg.boundaries == (0.0, 10.0, 30.0)  # the merge applied, the split did not
    assert any(f.startswith("correction-stale: split@15") for f in seg.flags)


def test_segment_says_stale_even_when_it_refuses():
    seg = segment(corrections=[split(1.0, media_key="v1")], media_key="v2")
    assert "no-signal" in seg.flags
    assert any(f.startswith("correction-stale: split@1") for f in seg.flags)


def test_stale_corrections_keeps_log_order():
    log = [split(1, media_key="b"), split(2), split(3, media_key="a"), split(4, media_key="b")]
    current, flags = stale_corrections(log, "b")
    assert [c.anchor_t for c in current] == [1.0, 2.0, 4.0]
    assert len(flags) == 1


# ── migrating across a re-cut ───────────────────────────────────────────────


def test_migration_moves_times_and_records_where_from():
    log = [
        split(30, media_key="v1", author="ana"),
        pin((40, 50), media_key="v1"),
        forbid(5, (25, 35), media_key="v1"),
        merge(8, media_key="other"),
        split(2),
    ]
    moved = migrate_corrections(
        log, cuts=[(10, 20)], from_media_key="v1", to_media_key="v2", remap=_shift
    )
    assert moved.dropped == ()
    a, b, c, d, e = moved.corrections
    assert (a.anchor_t, a.media_key, a.migrated_from, a.author) == (20.0, "v2", "v1", "ana")
    assert (b.span, b.anchor_t) == ((30.0, 40.0), 35.0)
    assert c.span == (15.0, 25.0) and c.anchor_t == 5.0
    assert d == log[3] and e == log[4]  # another rendering, and no key: untouched


def test_what_a_cut_removes_is_returned_not_lost():
    log = [split(15, media_key="v1"), pin((11, 19), anchor_t=12, media_key="v1")]
    moved = migrate_corrections(
        log, cuts=[{"start": 10, "end": 20}], from_media_key="v1", to_media_key="v2",
        remap=_shift,
    )
    assert moved.corrections == ()
    assert [why for _, why in moved.dropped] == ["its time was cut out"] * 2
    assert moved.flags[0].startswith("correction-unmigrated: split@15")


def test_a_span_the_cuts_remove_is_dropped():
    log = [forbid(5, (12, 18), media_key="v1")]
    moved = migrate_corrections(
        log, cuts=[(10, 20)], from_media_key="v1", to_media_key="v2", remap=_shift
    )
    assert moved.corrections == () and moved.dropped[0][1] == "the cuts remove its span"


def test_migrated_corrections_apply_to_the_new_rendering():
    old = [split(25.0, media_key="v1")]
    moved = migrate_corrections(
        old, cuts=[(5, 10)], from_media_key="v1", to_media_key="v2", remap=_shift
    ).corrections
    seg = segment(boundaries=[0, 10, 30], corrections=moved, media_key="v2")
    assert seg.boundaries == (0.0, 10.0, 20.0, 30.0)


def test_the_default_remap_is_mixings():
    pytest.importorskip("mixing.transcript.formats")
    moved = migrate_corrections(
        [split(30, media_key="v1")], cuts=[(10, 20)], from_media_key="v1", to_media_key="v2"
    )
    assert moved.corrections[0].anchor_t == 20.0


def test_bad_cuts_are_refused():
    with pytest.raises(ValueError, match="start < end"):
        migrate_corrections([], cuts=[(20, 10)], from_media_key="a", to_media_key="b", remap=_shift)


def test_migrated_from_round_trips_on_the_wire():
    c = Correction(verb="split", anchor_t=3.0, media_key="v2", migrated_from="v1")
    wire = to_wire(c)
    assert wire["migratedFrom"] == "v1"
    assert from_wire(wire) == c
    assert "migratedFrom" not in to_wire(split(3.0))


# ── the log in lacing ───────────────────────────────────────────────────────


@pytest.fixture
def store():
    lacing = pytest.importorskip("lacing")
    return lacing.MemoryStore()


def test_a_log_round_trips_through_the_store(store):
    from paces.evidence import corrections_from_store, corrections_to_store

    log = [
        split(95.8, media_key="v1", author="ana", at="2026-11-01T10:00:00Z", reason="two moves"),
        pin((1.25, 3.5), step_id="s2", author="ben"),
        forbid(4, (10, 12)),
    ]
    write = corrections_to_store(
        log, store=store, asset_id="a" * 64, author="cleo", at="2026-11-02T09:00:00Z"
    )
    assert write.written == 3
    back = corrections_from_store(store, asset_id="a" * 64)
    assert back[0] == log[0]
    assert (back[1].author, back[1].at, back[1].span) == ("ben", "2026-11-02T09:00:00Z", (1.25, 3.5))
    assert back[2].author == "cleo"


def test_storing_the_same_log_again_writes_nothing(store):
    from paces.evidence import corrections_from_store, corrections_to_store

    corrections_to_store([split(5)], store=store, asset_id="x", author="ana")
    again = corrections_to_store(
        corrections_from_store(store, asset_id="x"), store=store, asset_id="x"
    )
    assert (again.written, again.updated, again.unchanged) == (0, 0, 1)


def test_a_shorter_log_replaces_a_longer_one(store):
    from paces.evidence import corrections_from_store, corrections_to_store

    corrections_to_store([split(1), split(2), split(3)], store=store, asset_id="x", author="a")
    write = corrections_to_store([split(1)], store=store, asset_id="x", author="a")
    assert write.removed == 2
    assert [c.anchor_t for c in corrections_from_store(store, asset_id="x")] == [1.0]


def test_a_stored_correction_names_its_author(store):
    from paces.evidence import corrections_to_store

    with pytest.raises(ValueError, match="names its author"):
        corrections_to_store([split(1)], store=store, asset_id="x")


def test_guides_keep_their_own_logs(store):
    from paces.evidence import corrections_from_store, corrections_to_store

    corrections_to_store([split(1)], store=store, asset_id="x", doc_id="g1", author="a")
    corrections_to_store([split(2)], store=store, asset_id="x", doc_id="g2", author="a")
    assert corrections_from_store(store, asset_id="x", doc_id="g1")[0].anchor_t == 1.0
    assert corrections_from_store(store, asset_id="x", doc_id="g2")[0].anchor_t == 2.0


def test_activity_says_who_made_it(store):
    from paces.evidence import corrections_to_store

    migrated = Correction(verb="split", anchor_t=2.0, media_key="v2", migrated_from="v1")
    corrections_to_store([split(1), migrated], store=store, asset_id="x", author="a")
    activities = sorted(row.provenance.activity for row in store.all())
    assert activities == ["create", "migrate"]


def test_re_deriving_the_guide_never_prunes_its_corrections(store):
    from paces.evidence import corrections_from_store, corrections_to_store, to_store

    corrections_to_store([split(5)], store=store, asset_id="x", author="a")
    to_store(segment(boundaries=[0, 10]), store=store, asset_id="x")
    to_store(segment(boundaries=[0, 4, 10]), store=store, asset_id="x")
    assert len(corrections_from_store(store, asset_id="x")) == 1


def test_the_cli_takes_the_rendering(tmp_path):
    import json

    from paces.tools import segment as segment_tool

    log = json.dumps([{"verb": "split", "anchorT": "15", "mediaKey": "v1"}])
    out = segment_tool(boundaries="[0, 10, 20, 30]", corrections=log, rendering="v2")
    assert any(f.startswith("correction-stale: split@15") for f in out["flags"])
