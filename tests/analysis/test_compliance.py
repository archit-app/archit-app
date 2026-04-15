"""Tests for analysis.compliance — zoning compliance checker."""

import pytest
from archit_app import (
    Building, BuildingMetadata, Level, Room,
    Land, Setbacks, ZoningInfo,
    Point2D, Polygon2D, WORLD,
)
from archit_app.analysis.compliance import check_compliance, ComplianceReport


def _rect_room(x, y, w, h, program="office"):
    boundary = Polygon2D.rectangle(x, y, w, h, crs=WORLD)
    return Room(boundary=boundary, program=program)


def _simple_land(w=20.0, h=20.0) -> "Land":
    """Square lot: w × h meters."""
    return Land.from_polygon(Polygon2D.rectangle(0, 0, w, h, crs=WORLD))


def _one_floor_building(room_w=8.0, room_h=8.0, floor_height=3.0) -> "Building":
    """Single ground-floor building with one room."""
    room = _rect_room(1, 1, room_w, room_h)
    level = Level(index=0, elevation=0.0, floor_height=floor_height).add_room(room)
    return Building().add_level(level)


def _two_floor_building(room_w=8.0, room_h=8.0) -> "Building":
    room = _rect_room(1, 1, room_w, room_h)
    b = Building()
    for i in range(2):
        level = Level(index=i, elevation=float(i * 3), floor_height=3.0).add_room(room)
        b = b.add_level(level)
    return b


class TestFARCheck:
    def test_far_compliant(self):
        # Lot 20×20=400m², 1 floor 8×8=64m², FAR=0.16 < max_far=0.5
        land = _simple_land().with_zoning(ZoningInfo(max_far=0.5))
        building = _one_floor_building()
        report = check_compliance(building, land)
        far_check = next(c for c in report.checks if "FAR" in c.name)
        assert far_check.compliant is True

    def test_far_non_compliant(self):
        # Lot 20×20=400m², 2 floors 8×8=128m², FAR=0.32 > max_far=0.2
        land = _simple_land().with_zoning(ZoningInfo(max_far=0.2))
        building = _two_floor_building()
        report = check_compliance(building, land)
        far_check = next(c for c in report.checks if "FAR" in c.name)
        assert far_check.compliant is False

    def test_no_max_far_skips_check(self):
        land = _simple_land().with_zoning(ZoningInfo())
        building = _one_floor_building()
        report = check_compliance(building, land)
        names = [c.name for c in report.checks]
        assert not any("FAR" in n for n in names)


class TestHeightCheck:
    def test_height_compliant(self):
        # 1 floor, floor_height=3m → total height=3m < max=10m
        land = _simple_land().with_zoning(ZoningInfo(max_height_m=10.0))
        building = _one_floor_building(floor_height=3.0)
        report = check_compliance(building, land)
        h_check = next(c for c in report.checks if "height" in c.name.lower())
        assert h_check.compliant is True
        assert h_check.actual == pytest.approx(3.0)

    def test_height_non_compliant(self):
        land = _simple_land().with_zoning(ZoningInfo(max_height_m=5.0))
        building = _two_floor_building()  # elevation=3 + floor_height=3 → 6m
        report = check_compliance(building, land)
        h_check = next(c for c in report.checks if "height" in c.name.lower())
        assert h_check.compliant is False

    def test_no_zoning_no_height_check(self):
        land = _simple_land()
        building = _one_floor_building()
        report = check_compliance(building, land)
        names = [c.name for c in report.checks]
        assert not any("height" in n.lower() for n in names)


class TestLotCoverageCheck:
    def test_coverage_compliant(self):
        # 8×8=64m² on 20×20=400m² → coverage=0.16 < 0.5
        land = _simple_land().with_zoning(ZoningInfo(max_lot_coverage=0.5))
        building = _one_floor_building()
        report = check_compliance(building, land)
        cov = next(c for c in report.checks if "coverage" in c.name.lower())
        assert cov.compliant is True

    def test_coverage_non_compliant(self):
        # 16×16=256m² on 20×20=400m² → coverage=0.64 > 0.5
        land = _simple_land().with_zoning(ZoningInfo(max_lot_coverage=0.5))
        building = _one_floor_building(room_w=16.0, room_h=16.0)
        report = check_compliance(building, land)
        cov = next(c for c in report.checks if "coverage" in c.name.lower())
        assert cov.compliant is False


class TestFootprintChecks:
    def test_within_lot_compliant(self):
        land = _simple_land(20, 20)
        building = _one_floor_building(room_w=5, room_h=5)
        report = check_compliance(building, land)
        lot_check = next(c for c in report.checks if "lot boundary" in c.name.lower())
        assert lot_check.compliant is True

    def test_outside_lot_non_compliant(self):
        land = _simple_land(5, 5)   # tiny lot
        building = _one_floor_building(room_w=8, room_h=8)  # bigger footprint
        report = check_compliance(building, land)
        lot_check = next(c for c in report.checks if "lot boundary" in c.name.lower())
        assert lot_check.compliant is False

    def test_within_setback_compliant(self):
        # Lot 0→20, setback 2m → buildable 2→18.
        # Room placed at (3,3) with 4×4 m → sits entirely within the buildable zone.
        land = (
            _simple_land(20, 20)
            .with_setbacks(Setbacks(front=2, back=2, left=2, right=2))
        )
        room = _rect_room(3, 3, 4, 4)
        level = Level(index=0, elevation=0.0, floor_height=3.0).add_room(room)
        building = Building().add_level(level)
        report = check_compliance(building, land)
        sb_check = next(c for c in report.checks if "setback" in c.name.lower())
        assert sb_check.compliant is True


class TestReportHelpers:
    def test_overall_compliant(self):
        land = _simple_land().with_zoning(ZoningInfo(max_far=2.0, max_height_m=50.0))
        building = _one_floor_building()
        report = check_compliance(building, land)
        assert report.compliant is True

    def test_failed_checks_list(self):
        land = _simple_land().with_zoning(ZoningInfo(max_far=0.01))  # too strict
        building = _one_floor_building()
        report = check_compliance(building, land)
        assert len(report.failed_checks) >= 1

    def test_summary_is_string(self):
        land = _simple_land()
        building = _one_floor_building()
        report = check_compliance(building, land)
        assert isinstance(report.summary(), str)
