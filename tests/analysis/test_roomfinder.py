"""Tests for room-from-walls auto-detection."""

import pytest
from archit_app import Wall, Room, Level, Polygon2D, WORLD
from archit_app.analysis.roomfinder import find_rooms, rooms_from_walls


def _box_walls(x, y, w, h, thickness=0.1):
    """Return 4 walls forming a closed rectangle."""
    return [
        Wall.straight(x,     y,     x + w, y,     thickness=thickness, height=3.0),
        Wall.straight(x + w, y,     x + w, y + h, thickness=thickness, height=3.0),
        Wall.straight(x + w, y + h, x,     y + h, thickness=thickness, height=3.0),
        Wall.straight(x,     y + h, x,     y,     thickness=thickness, height=3.0),
    ]


class TestFindRooms:

    def test_empty_walls_returns_empty(self):
        assert find_rooms([]) == []

    def test_single_box_finds_room(self):
        walls = _box_walls(0, 0, 6, 4)
        polygons = find_rooms(walls, min_area=1.0)
        assert len(polygons) >= 1

    def test_found_polygon_area(self):
        walls = _box_walls(0, 0, 6, 4, thickness=0.05)
        polygons = find_rooms(walls, min_area=1.0)
        assert len(polygons) >= 1
        # Largest polygon area should be close to the interior area
        assert polygons[0].area > 1.0

    def test_min_area_filter(self):
        walls = _box_walls(0, 0, 6, 4)
        # With very large min_area, nothing should pass
        polygons = find_rooms(walls, min_area=10000.0)
        assert polygons == []

    def test_returns_polygon2d_objects(self):
        from archit_app.geometry.polygon import Polygon2D
        walls = _box_walls(0, 0, 4, 3)
        polygons = find_rooms(walls, min_area=0.5)
        for p in polygons:
            assert isinstance(p, Polygon2D)

    def test_sorted_largest_first(self):
        walls = _box_walls(0, 0, 6, 4)
        polygons = find_rooms(walls, min_area=0.1)
        areas = [p.area for p in polygons]
        assert areas == sorted(areas, reverse=True)


class TestRoomsFromWalls:

    def test_returns_room_objects(self):
        walls = _box_walls(0, 0, 6, 4)
        rooms = rooms_from_walls(walls, min_area=1.0)
        for r in rooms:
            assert isinstance(r, Room)

    def test_level_index_assigned(self):
        walls = _box_walls(0, 0, 6, 4)
        rooms = rooms_from_walls(walls, level_index=2, min_area=1.0)
        for r in rooms:
            assert r.level_index == 2

    def test_program_assigned(self):
        walls = _box_walls(0, 0, 6, 4)
        rooms = rooms_from_walls(walls, program="auto", min_area=1.0)
        for r in rooms:
            assert r.program == "auto"

    def test_numbered_names(self):
        walls = _box_walls(0, 0, 6, 4)
        rooms = rooms_from_walls(walls, min_area=1.0)
        if rooms:
            assert rooms[0].name == "Room 1"

    def test_empty_walls(self):
        assert rooms_from_walls([]) == []

    def test_rooms_addable_to_level(self):
        walls = _box_walls(0, 0, 6, 4)
        rooms = rooms_from_walls(walls, min_area=1.0)
        lv = Level(index=0, elevation=0.0, floor_height=3.0)
        for r in rooms:
            lv = lv.add_room(r)
        assert len(lv.rooms) == len(rooms)
