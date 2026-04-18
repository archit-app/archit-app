"""
Tests for Building.validate(), Building.duplicate_level(), Level.duplicate(),
and Building.to_agent_context().
"""

from __future__ import annotations

import pytest

from archit_app import (
    WORLD,
    Building,
    BuildingMetadata,
    Level,
    Room,
    Polygon2D,
    Wall,
    ValidationReport,
    ValidationIssue,
    Staircase,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_room() -> Room:
    return Room(
        boundary=Polygon2D.rectangle(0, 0, 4, 4, crs=WORLD),
        name="Living Room",
        program="living",
    )


@pytest.fixture
def simple_level(simple_room) -> Level:
    wall = Wall.straight(0, 0, 4, 0, thickness=0.2, height=3.0)
    return (
        Level(index=0, elevation=0.0, floor_height=3.0, name="Ground Floor")
        .add_room(simple_room)
        .add_wall(wall)
    )


@pytest.fixture
def simple_building(simple_level) -> Building:
    return Building(
        metadata=BuildingMetadata(name="Test House", architect="A. Arch"),
    ).add_level(simple_level)


# ---------------------------------------------------------------------------
# Level.duplicate()
# ---------------------------------------------------------------------------

class TestLevelDuplicate:

    def test_duplicate_returns_new_level(self, simple_level):
        dup = simple_level.duplicate(new_index=1, new_elevation=3.0)
        assert dup.index == 1
        assert dup.elevation == 3.0

    def test_duplicate_preserves_element_counts(self, simple_level):
        dup = simple_level.duplicate(new_index=1, new_elevation=3.0)
        assert len(dup.rooms) == len(simple_level.rooms)
        assert len(dup.walls) == len(simple_level.walls)

    def test_duplicate_assigns_fresh_ids_by_default(self, simple_level):
        dup = simple_level.duplicate(new_index=1, new_elevation=3.0)
        orig_ids = {r.id for r in simple_level.rooms}
        dup_ids  = {r.id for r in dup.rooms}
        assert orig_ids.isdisjoint(dup_ids)

    def test_duplicate_preserves_ids_when_asked(self, simple_level):
        dup = simple_level.duplicate(new_index=1, new_elevation=3.0, new_ids=False)
        orig_ids = {r.id for r in simple_level.rooms}
        dup_ids  = {r.id for r in dup.rooms}
        assert orig_ids == dup_ids

    def test_duplicate_name(self, simple_level):
        dup = simple_level.duplicate(new_index=1, new_elevation=3.0, name="First Floor")
        assert dup.name == "First Floor"

    def test_original_level_unchanged(self, simple_level):
        simple_level.duplicate(new_index=1, new_elevation=3.0)
        assert simple_level.index == 0
        assert simple_level.elevation == 0.0


# ---------------------------------------------------------------------------
# Building.duplicate_level()
# ---------------------------------------------------------------------------

class TestBuildingDuplicateLevel:

    def test_duplicate_level_adds_new_level(self, simple_building):
        b2 = simple_building.duplicate_level(
            source_index=0, new_index=1, new_elevation=3.0
        )
        assert len(b2.levels) == 2

    def test_duplicate_level_preserves_element_counts(self, simple_building):
        b2 = simple_building.duplicate_level(
            source_index=0, new_index=1, new_elevation=3.0
        )
        assert len(b2.get_level(1).rooms) == len(b2.get_level(0).rooms)

    def test_duplicate_level_raises_for_missing_source(self, simple_building):
        with pytest.raises(KeyError):
            simple_building.duplicate_level(source_index=99, new_index=2, new_elevation=6.0)

    def test_duplicate_level_sorted_by_index(self, simple_building):
        b2 = simple_building.duplicate_level(
            source_index=0, new_index=-1, new_elevation=-3.0
        )
        indices = [lv.index for lv in b2.levels]
        assert indices == sorted(indices)


# ---------------------------------------------------------------------------
# Building.to_agent_context()
# ---------------------------------------------------------------------------

class TestToAgentContext:

    def test_returns_dict(self, simple_building):
        ctx = simple_building.to_agent_context()
        assert isinstance(ctx, dict)

    def test_contains_building_name(self, simple_building):
        ctx = simple_building.to_agent_context()
        assert ctx["building_name"] == "Test House"

    def test_contains_total_levels(self, simple_building):
        ctx = simple_building.to_agent_context()
        assert ctx["total_levels"] == 1

    def test_contains_levels_list(self, simple_building):
        ctx = simple_building.to_agent_context()
        assert len(ctx["levels"]) == 1

    def test_level_has_rooms(self, simple_building):
        ctx = simple_building.to_agent_context()
        assert len(ctx["levels"][0]["rooms"]) == 1

    def test_room_has_area(self, simple_building):
        ctx = simple_building.to_agent_context()
        room = ctx["levels"][0]["rooms"][0]
        assert room["area_m2"] > 0

    def test_gross_area_present(self, simple_building):
        ctx = simple_building.to_agent_context()
        assert ctx["gross_floor_area_m2"] > 0

    def test_json_serialisable(self, simple_building):
        import json
        ctx = simple_building.to_agent_context()
        s = json.dumps(ctx)  # must not raise
        assert isinstance(s, str)


# ---------------------------------------------------------------------------
# Building.validate()
# ---------------------------------------------------------------------------

class TestBuildingValidate:

    def test_valid_building_has_no_issues(self, simple_building):
        report = simple_building.validate()
        assert isinstance(report, ValidationReport)
        assert report.issues == []
        assert not report.has_errors
        assert not report.has_warnings

    def test_duplicate_level_index_is_an_error(self, simple_level):
        # Manually create a building with duplicate level indices
        level_copy = simple_level.duplicate(new_index=0, new_elevation=3.0, new_ids=True)
        # Add two levels with the same index by bypassing add_level de-duplication
        b = Building().model_copy(update={"levels": (simple_level, level_copy)})
        report = b.validate()
        assert report.has_errors
        assert any("Duplicate level index" in i.message for i in report.issues)

    def test_staircase_broken_link_is_warning(self, simple_level):
        stair = Staircase.straight(
            x=5, y=0, width=1.2, rise_count=10,
            bottom_level_index=0, top_level_index=99,  # 99 doesn't exist
        )
        lv = simple_level.add_staircase(stair)
        b = Building().add_level(lv)
        report = b.validate()
        assert report.has_warnings
        assert any("top_level_index 99" in i.message for i in report.issues)

    def test_staircase_valid_links_no_warning(self, simple_level):
        level1 = Level(index=1, elevation=3.0, floor_height=3.0)
        stair = Staircase.straight(
            x=5, y=0, width=1.2, rise_count=10,
            bottom_level_index=0, top_level_index=1,
        )
        lv = simple_level.add_staircase(stair)
        b = Building().add_level(lv).add_level(level1)
        report = b.validate()
        assert not report.has_warnings

    def test_report_repr(self, simple_building):
        report = simple_building.validate()
        assert "ValidationReport" in repr(report)
