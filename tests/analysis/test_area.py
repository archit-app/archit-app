"""Tests for analysis.area — area program validation."""

import pytest

from archit_app import WORLD, Building, Level, Polygon2D, Room
from archit_app.analysis.area import (
    AreaTarget,
    area_by_program,
    area_by_program_per_level,
    area_report,
    total_gross_area,
    total_net_area,
)


def _rect_room(x, y, w, h, name="", program=""):
    boundary = Polygon2D.rectangle(x, y, w, h, crs=WORLD)
    return Room(boundary=boundary, name=name, program=program)


def _simple_building() -> "Building":
    """Single level with three rooms: 2 bedrooms (16 m² each) + 1 kitchen (8 m²)."""
    bed1 = _rect_room(0, 0, 4, 4, name="Bed1", program="bedroom")
    bed2 = _rect_room(4, 0, 4, 4, name="Bed2", program="bedroom")
    kitchen = _rect_room(8, 0, 4, 2, name="Kitchen", program="kitchen")
    level = (
        Level(index=0, elevation=0.0, floor_height=3.0)
        .add_room(bed1).add_room(bed2).add_room(kitchen)
    )
    return Building().add_level(level)


def _multi_level_building() -> "Building":
    """Two floors, each with one bedroom."""
    b = Building()
    for i in range(2):
        room = _rect_room(0, 0, 4, 4, name=f"Bed{i}", program="bedroom")
        level = Level(index=i, elevation=float(i * 3), floor_height=3.0).add_room(room)
        b = b.add_level(level)
    return b


class TestAreaByProgram:
    def test_returns_all_programs(self):
        building = _simple_building()
        result = area_by_program(building)
        assert set(result.keys()) == {"bedroom", "kitchen"}

    def test_bedroom_total(self):
        building = _simple_building()
        result = area_by_program(building)
        assert result["bedroom"] == pytest.approx(32.0)

    def test_kitchen_total(self):
        building = _simple_building()
        result = area_by_program(building)
        assert result["kitchen"] == pytest.approx(8.0)

    def test_multi_level_aggregation(self):
        building = _multi_level_building()
        result = area_by_program(building)
        assert result["bedroom"] == pytest.approx(32.0)

    def test_empty_building(self):
        result = area_by_program(Building())
        assert result == {}


class TestAreaByProgramPerLevel:
    def test_keys_are_level_indices(self):
        building = _multi_level_building()
        result = area_by_program_per_level(building)
        assert set(result.keys()) == {0, 1}

    def test_per_level_values(self):
        building = _multi_level_building()
        result = area_by_program_per_level(building)
        assert result[0]["bedroom"] == pytest.approx(16.0)
        assert result[1]["bedroom"] == pytest.approx(16.0)


class TestAreaReport:
    def test_compliant_program(self):
        building = _simple_building()
        targets = [AreaTarget(program="bedroom", target_m2=32.0, tolerance_fraction=0.1)]
        results = area_report(building, targets)
        bed = next(r for r in results if r.program == "bedroom")
        assert bed.compliant is True
        assert bed.actual_m2 == pytest.approx(32.0)

    def test_non_compliant_over(self):
        building = _simple_building()
        targets = [AreaTarget(program="bedroom", target_m2=20.0, tolerance_fraction=0.05)]
        results = area_report(building, targets)
        bed = next(r for r in results if r.program == "bedroom")
        assert bed.compliant is False
        assert bed.deviation_fraction > 0

    def test_non_compliant_under(self):
        building = _simple_building()
        targets = [AreaTarget(program="bedroom", target_m2=50.0, tolerance_fraction=0.05)]
        results = area_report(building, targets)
        bed = next(r for r in results if r.program == "bedroom")
        assert bed.compliant is False
        assert bed.deviation_fraction < 0

    def test_program_without_target_has_none_compliant(self):
        building = _simple_building()
        results = area_report(building, [])
        for r in results:
            assert r.compliant is None
            assert r.target_m2 is None

    def test_missing_program_is_included(self):
        """A target for a program not in the building should appear as non-compliant."""
        building = _simple_building()
        targets = [AreaTarget(program="bathroom", target_m2=5.0)]
        results = area_report(building, targets)
        bathroom = next((r for r in results if r.program == "bathroom"), None)
        assert bathroom is not None
        assert bathroom.compliant is False
        assert bathroom.actual_m2 == pytest.approx(0.0)

    def test_sorted_by_program(self):
        building = _simple_building()
        results = area_report(building, [])
        names = [r.program for r in results]
        assert names == sorted(names)


class TestTotals:
    def test_total_gross_area(self):
        building = _simple_building()
        assert total_gross_area(building) == pytest.approx(40.0)

    def test_total_net_area_no_holes(self):
        building = _simple_building()
        assert total_net_area(building) == pytest.approx(40.0)

    def test_empty_building(self):
        assert total_gross_area(Building()) == pytest.approx(0.0)
        assert total_net_area(Building()) == pytest.approx(0.0)
