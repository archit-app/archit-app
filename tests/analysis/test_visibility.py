"""Tests for analysis.visibility — isovist computation."""

import math

import pytest

from archit_app import (
    WORLD,
    Level,
    Point2D,
    Polygon2D,
    Room,
    Wall,
)
from archit_app.analysis.visibility import (
    IsovistResult,
    compute_isovist,
    mutual_visibility,
    visible_area_m2,
)


def _rect_room(x, y, w, h):
    return Room(boundary=Polygon2D.rectangle(x, y, w, h, crs=WORLD))


def _viewpoint(x=0.0, y=0.0):
    return Point2D(x=x, y=y, crs=WORLD)


class TestComputeIsovist:
    def _open_level(self):
        """Level with one large room and no walls — open space."""
        room = _rect_room(0, 0, 20, 20)
        return Level(index=0, elevation=0.0, floor_height=3.0).add_room(room)

    def _walled_level(self):
        """Level with a central blocking wall."""
        room = _rect_room(0, 0, 20, 20)
        # Central vertical wall blocking right half
        wall = Wall.straight(10, 0, 10, 20, thickness=0.3, height=3.0)
        level = Level(index=0, elevation=0.0, floor_height=3.0).add_room(room).add_wall(wall)
        return level

    def test_returns_isovist_result(self):
        level = self._open_level()
        result = compute_isovist(_viewpoint(10, 10), level, max_range=5.0)
        assert result is not None
        assert isinstance(result, IsovistResult)

    def test_isovist_is_polygon2d(self):
        level = self._open_level()
        result = compute_isovist(_viewpoint(10, 10), level, max_range=5.0)
        assert isinstance(result.isovist, Polygon2D)

    def test_isovist_area_positive(self):
        level = self._open_level()
        result = compute_isovist(_viewpoint(10, 10), level, max_range=5.0)
        assert result.area_m2 > 0

    def test_open_space_area_approx_circle(self):
        """Without walls, isovist ≈ circle with radius = max_range."""
        level = self._open_level()
        max_range = 5.0
        result = compute_isovist(_viewpoint(10, 10), level, max_range=max_range, resolution=720)
        expected = math.pi * max_range ** 2
        # Within 5% of a perfect circle
        assert result.area_m2 == pytest.approx(expected, rel=0.05)

    def test_wall_reduces_visible_area(self):
        """A blocking wall should reduce the visible area compared to open space."""
        open_level = self._open_level()
        walled_level = self._walled_level()

        vp = _viewpoint(5, 10)
        open_area = visible_area_m2(vp, open_level, max_range=8.0)
        walled_area = visible_area_m2(vp, walled_level, max_range=8.0)

        assert walled_area < open_area

    def test_room_id_set_when_inside_room(self):
        level = self._open_level()
        room = level.rooms[0]
        result = compute_isovist(_viewpoint(10, 10), level)
        assert result.room_id == room.id

    def test_room_id_none_when_outside_all_rooms(self):
        level = self._open_level()
        result = compute_isovist(_viewpoint(50, 50), level)
        assert result.room_id is None

    def test_empty_level_returns_circle(self):
        """No walls → isovist is a full circle; level with no rooms still works."""
        level = Level(index=0, elevation=0.0, floor_height=3.0)
        result = compute_isovist(_viewpoint(0, 0), level, max_range=3.0, resolution=360)
        assert result is not None
        expected = math.pi * 9.0
        assert result.area_m2 == pytest.approx(expected, rel=0.05)


class TestVisibleAreaM2:
    def test_returns_float(self):
        level = Level(index=0, elevation=0.0, floor_height=3.0)
        area = visible_area_m2(_viewpoint(0, 0), level, max_range=3.0)
        assert isinstance(area, float)
        assert area >= 0.0


class TestMutualVisibility:
    def _level_with_wall(self):
        room = _rect_room(0, 0, 20, 10)
        wall = Wall.straight(10, 0, 10, 10, thickness=0.3, height=3.0)
        return Level(index=0, elevation=0.0, floor_height=3.0).add_room(room).add_wall(wall)

    def test_visible_same_side(self):
        level = self._level_with_wall()
        a = _viewpoint(3, 5)
        b = _viewpoint(7, 5)
        assert mutual_visibility(a, b, level) is True

    def test_not_visible_across_wall(self):
        level = self._level_with_wall()
        a = _viewpoint(3, 5)
        b = _viewpoint(17, 5)
        assert mutual_visibility(a, b, level) is False

    def test_visible_no_walls(self):
        level = Level(index=0, elevation=0.0, floor_height=3.0)
        a = _viewpoint(0, 0)
        b = _viewpoint(10, 10)
        assert mutual_visibility(a, b, level) is True
