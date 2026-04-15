"""Tests for analysis.daylighting — solar orientation analysis."""

import math
import pytest
from archit_app import (
    Level, Room, Wall, Opening, OpeningKind,
    Point2D, Polygon2D, WORLD,
)
from archit_app.analysis.daylighting import (
    daylight_report,
    RoomDaylightResult,
    _wall_normal_angle_deg,
    _solar_score,
    _compass_to_cardinal,
    _normal_to_compass,
)


def _rect_room(x, y, w, h, name="room", program="office"):
    return Room(boundary=Polygon2D.rectangle(x, y, w, h, crs=WORLD), name=name, program=program)


class TestSolarHelpers:
    def test_south_facing_max_score(self):
        # south = compass 180
        assert _solar_score(180.0) == pytest.approx(1.0)

    def test_north_facing_zero_score(self):
        assert _solar_score(0.0) == pytest.approx(0.0)
        assert _solar_score(360.0) == pytest.approx(0.0)

    def test_east_west_mid_score(self):
        assert _solar_score(90.0) == pytest.approx(0.0, abs=0.01)
        assert _solar_score(270.0) == pytest.approx(0.0, abs=0.01)

    def test_cardinal_south(self):
        assert _compass_to_cardinal(180.0) == "S"

    def test_cardinal_north(self):
        assert _compass_to_cardinal(0.0) == "N"
        assert _compass_to_cardinal(360.0) == "N"

    def test_cardinal_northeast(self):
        assert _compass_to_cardinal(45.0) == "NE"

    def test_wall_normal_horizontal_wall(self):
        """Horizontal wall (along X) has normal pointing up (+Y = 90°) or down."""
        wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        angle = _wall_normal_angle_deg(wall)
        assert angle is not None
        # Left-hand normal of a +X wall is +Y (90°)
        assert angle == pytest.approx(90.0, abs=1.0)

    def test_wall_normal_vertical_wall(self):
        """Vertical wall (along Y) has normal pointing left (-X = 180°) or right (+X = 0°/360°)."""
        wall = Wall.straight(0, 0, 0, 5, thickness=0.2, height=3.0)
        angle = _wall_normal_angle_deg(wall)
        assert angle is not None
        assert abs(angle - 180.0) < 1.0 or abs(angle) < 1.0 or abs(angle - 360.0) < 1.0


class TestDaylightReport:
    def _level_with_south_window(self):
        """Room at origin with a south-facing wall along Y=0 (normal pointing south = -Y = 270°)."""
        room = _rect_room(0, 0, 6, 6, name="Living")
        # South wall: horizontal, runs along bottom of room (y=0), normal points south (down)
        south_wall = Wall.straight(0, 0, 6, 0, thickness=0.2, height=3.0)
        window = Opening.window(x=2.0, y=-0.1, width=1.5, sill_height=0.9)
        south_wall = south_wall.add_opening(window)
        return (
            Level(index=0, elevation=0.0, floor_height=3.0)
            .add_room(room).add_wall(south_wall),
            window,
        )

    def test_report_has_entry_per_room(self):
        level, _ = self._level_with_south_window()
        results = daylight_report(level)
        assert len(results) == 1

    def test_window_detected(self):
        level, window = self._level_with_south_window()
        results = daylight_report(level)
        r = results[0]
        assert r.window_area_m2 > 0
        assert len(r.windows) >= 1

    def test_window_to_floor_ratio(self):
        level, _ = self._level_with_south_window()
        results = daylight_report(level)
        r = results[0]
        assert r.window_to_floor_ratio > 0
        assert r.floor_area_m2 == pytest.approx(36.0)

    def test_room_with_no_windows(self):
        room = _rect_room(0, 0, 5, 5, name="Dark Room")
        level = Level(index=0, elevation=0.0, floor_height=3.0).add_room(room)
        results = daylight_report(level)
        r = results[0]
        assert r.window_area_m2 == pytest.approx(0.0)
        assert r.avg_solar_score == pytest.approx(0.0)

    def test_north_angle_affects_compass(self):
        """Rotating north_angle by 90° should shift compass bearing by 90°."""
        wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        from archit_app.analysis.daylighting import _wall_normal_angle_deg, _normal_to_compass
        normal = _wall_normal_angle_deg(wall)
        compass_0 = _normal_to_compass(normal, north_angle_deg=0.0)
        compass_90 = _normal_to_compass(normal, north_angle_deg=90.0)
        diff = abs((compass_0 - compass_90) % 360)
        # Difference should be 90° (mod 360, so also accept 270° = -90°)
        assert diff == pytest.approx(90.0, abs=1.0) or diff == pytest.approx(270.0, abs=1.0)

    def test_avg_solar_score_between_0_and_1(self):
        level, _ = self._level_with_south_window()
        results = daylight_report(level)
        r = results[0]
        assert 0.0 <= r.avg_solar_score <= 1.0

    def test_empty_level(self):
        level = Level(index=0, elevation=0.0, floor_height=3.0)
        results = daylight_report(level)
        assert results == []
