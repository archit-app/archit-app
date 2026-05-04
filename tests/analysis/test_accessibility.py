"""Tests for accessibility analysis."""

import math

from archit_app import WORLD, Level, Opening, Polygon2D, Ramp, Room, Wall
from archit_app.analysis.accessibility import (
    MIN_DOOR_WIDTH_M,
    AccessibilityReport,
    check_accessibility,
)


def _room(x, y, w, h, program="office"):
    return Room(boundary=Polygon2D.rectangle(x, y, w, h, crs=WORLD), program=program)


def _level(*rooms, walls=(), openings=(), ramps=()):
    lv = Level(index=0, elevation=0.0, floor_height=3.0)
    for r in rooms:
        lv = lv.add_room(r)
    for w in walls:
        lv = lv.add_wall(w)
    for o in openings:
        lv = lv.add_opening(o)
    for ramp in ramps:
        lv = lv.add_ramp(ramp)
    return lv


class TestCheckAccessibility:

    def test_returns_report(self):
        lv = _level()
        r = check_accessibility(lv)
        assert isinstance(r, AccessibilityReport)

    def test_empty_level_passes(self):
        r = check_accessibility(_level())
        assert r.passed_all

    def test_level_index_recorded(self):
        lv = Level(index=3, elevation=9.0, floor_height=3.0)
        r = check_accessibility(lv)
        assert r.level_index == 3


class TestDoorWidthChecks:

    def test_wide_door_passes(self):
        door = Opening.door(x=0, y=0, width=1.0, height=2.1)
        lv = _level(openings=(door,))
        r = check_accessibility(lv)
        door_checks = [c for c in r.checks if c.name == "door_clear_width"]
        assert all(c.passed for c in door_checks)

    def test_narrow_door_fails(self):
        door = Opening.door(x=0, y=0, width=0.7, height=2.1)
        lv = _level(openings=(door,))
        r = check_accessibility(lv)
        door_checks = [c for c in r.checks if c.name == "door_clear_width"]
        assert any(not c.passed for c in door_checks)

    def test_exact_minimum_passes(self):
        door = Opening.door(x=0, y=0, width=MIN_DOOR_WIDTH_M, height=2.1)
        lv = _level(openings=(door,))
        r = check_accessibility(lv)
        door_checks = [c for c in r.checks if c.name == "door_clear_width"]
        assert all(c.passed for c in door_checks)

    def test_door_on_wall_checked(self):
        wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        door = Opening.door(x=1, y=0, width=0.7, height=2.1)
        wall = wall.add_opening(door)
        lv = _level(walls=(wall,))
        r = check_accessibility(lv)
        door_checks = [c for c in r.checks if c.name == "door_clear_width"]
        assert any(not c.passed for c in door_checks)

    def test_windows_not_checked(self):
        window = Opening.window(x=0, y=0, width=0.5, height=1.2)
        lv = _level(openings=(window,))
        r = check_accessibility(lv)
        door_checks = [c for c in r.checks if c.name == "door_clear_width"]
        assert len(door_checks) == 0

    def test_element_id_recorded(self):
        door = Opening.door(x=0, y=0, width=0.7, height=2.1)
        lv = _level(openings=(door,))
        r = check_accessibility(lv)
        check = next(c for c in r.checks if c.name == "door_clear_width")
        assert check.element_id == door.id


class TestRampSlopeChecks:

    def test_gentle_ramp_passes(self):
        ramp = Ramp.straight(x=0, y=0, width=1.5, length=3.6,
                             slope_angle=math.atan(1 / 12))
        lv = _level(ramps=(ramp,))
        r = check_accessibility(lv)
        ramp_checks = [c for c in r.checks if c.name == "ramp_slope"]
        assert all(c.passed for c in ramp_checks)

    def test_steep_ramp_fails(self):
        ramp = Ramp.straight(x=0, y=0, width=1.5, length=2.0,
                             slope_angle=math.radians(15))
        lv = _level(ramps=(ramp,))
        r = check_accessibility(lv)
        ramp_checks = [c for c in r.checks if c.name == "ramp_slope"]
        assert any(not c.passed for c in ramp_checks)

    def test_ramp_element_id_in_check(self):
        ramp = Ramp.straight(x=0, y=0, width=1.5, length=3.6,
                             slope_angle=math.radians(15))
        lv = _level(ramps=(ramp,))
        r = check_accessibility(lv)
        check = next(c for c in r.checks if c.name == "ramp_slope")
        assert check.element_id == ramp.id


class TestWetRoomTurningCircle:

    def test_large_bathroom_passes(self):
        room = _room(0, 0, 3, 3, "bathroom")
        lv = _level(room)
        r = check_accessibility(lv)
        wet_checks = [c for c in r.checks if c.name == "wet_room_turning_circle"]
        assert all(c.passed for c in wet_checks)

    def test_tiny_toilet_warns(self):
        room = _room(0, 0, 0.8, 0.8, "toilet")
        lv = _level(room)
        r = check_accessibility(lv)
        wet_checks = [c for c in r.checks if c.name == "wet_room_turning_circle"]
        assert any(not c.passed for c in wet_checks)

    def test_non_wet_room_skipped(self):
        room = _room(0, 0, 0.8, 0.8, "office")
        lv = _level(room)
        r = check_accessibility(lv)
        wet_checks = [c for c in r.checks if c.name == "wet_room_turning_circle"]
        assert len(wet_checks) == 0


class TestCorridorWidthChecks:

    def test_wide_corridor_passes(self):
        room = _room(0, 0, 5, 1.5, "corridor")
        lv = _level(room)
        r = check_accessibility(lv)
        corr_checks = [c for c in r.checks if c.name == "corridor_width"]
        assert all(c.passed for c in corr_checks)

    def test_narrow_corridor_fails(self):
        room = _room(0, 0, 5, 0.8, "hallway")
        lv = _level(room)
        r = check_accessibility(lv)
        corr_checks = [c for c in r.checks if c.name == "corridor_width"]
        assert any(not c.passed for c in corr_checks)

    def test_non_corridor_skipped(self):
        room = _room(0, 0, 5, 0.8, "bedroom")
        lv = _level(room)
        r = check_accessibility(lv)
        corr_checks = [c for c in r.checks if c.name == "corridor_width"]
        assert len(corr_checks) == 0


class TestReportProperties:

    def test_passed_all(self):
        r = check_accessibility(_level())
        assert r.passed_all

    def test_failures(self):
        door = Opening.door(x=0, y=0, width=0.5, height=2.1)
        r = check_accessibility(_level(openings=(door,)))
        assert len(r.failures) >= 1

    def test_errors_vs_warnings(self):
        # A tiny toilet generates a warning (not an error)
        room = _room(0, 0, 0.5, 0.5, "toilet")
        r = check_accessibility(_level(room))
        assert any(c.severity == "warning" for c in r.failures)

    def test_summary_contains_level(self):
        lv = Level(index=2, elevation=6.0, floor_height=3.0)
        r = check_accessibility(lv)
        assert "2" in r.summary()

    def test_summary_pass(self):
        r = check_accessibility(_level())
        assert "PASS" in r.summary()
