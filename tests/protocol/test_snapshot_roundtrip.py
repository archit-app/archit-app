"""Snapshot construction + JSON-roundtrip + level filtering."""

from __future__ import annotations

import json

from archit_app.protocol import (
    BudgetHints,
    FloorplanSnapshot,
    parse_message,
)


def test_compact_snapshot_basics(tiny_building):
    snap = tiny_building.to_protocol_snapshot(mode="compact")
    assert snap.mode == "compact"
    assert snap.total_rooms == 2
    assert len(snap.levels) == 1
    lvl = snap.levels[0]
    assert lvl.index == 0
    assert len(lvl.room_refs) == 2
    assert {r.kind for r in lvl.room_refs} == {"room"}
    # compact mode never carries raw walls/furniture/columns
    assert lvl.walls is None
    assert lvl.furniture is None
    assert lvl.columns is None


def test_detailed_snapshot_includes_arrays(tiny_building):
    snap = tiny_building.to_protocol_snapshot(mode="detailed")
    assert snap.mode == "detailed"
    lvl = snap.levels[0]
    # No walls in this fixture, but the field must be present (empty tuple).
    assert lvl.walls == ()
    assert lvl.columns == ()
    assert lvl.furniture == ()


def test_snapshot_level_filter(tiny_building):
    snap = tiny_building.to_protocol_snapshot(mode="compact", level_index=0)
    assert len(snap.levels) == 1
    assert snap.levels[0].index == 0


def test_snapshot_json_roundtrip(tiny_building):
    snap = tiny_building.to_protocol_snapshot(mode="compact")
    js = snap.model_dump_json()
    parsed = parse_message(js)
    assert isinstance(parsed, FloorplanSnapshot)
    assert parsed.total_rooms == snap.total_rooms
    # Roundtrip via dict too.
    d = json.loads(js)
    parsed2 = parse_message(d)
    assert isinstance(parsed2, FloorplanSnapshot)


def test_budget_default_is_exposed(tiny_building):
    snap = tiny_building.to_protocol_snapshot(
        mode="detailed",
        budget=BudgetHints(max_elements_per_level=1),
    )
    assert snap.budget.max_elements_per_level == 1
    # No walls in the fixture, so nothing actually gets truncated.
    assert snap.budget.truncated is False


def test_unknown_mode_raises(tiny_building):
    import pytest

    with pytest.raises(ValueError):
        tiny_building.to_protocol_snapshot(mode="weird")
