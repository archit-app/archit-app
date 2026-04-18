"""Tests for JSON serialization round-trips."""

import json
import math
import tempfile
import os

import pytest

from archit_app import (
    WORLD,
    Building,
    BuildingMetadata,
    Level,
    Opening,
    OpeningKind,
    Point2D,
    Polygon2D,
    Room,
    Wall,
    WallType,
    Column,
    ArcCurve,
    BezierCurve,
)
from archit_app.io.json_schema import (
    building_to_dict,
    building_from_dict,
    building_to_json,
    building_from_json,
    save_building,
    load_building,
)


def _roundtrip(building: Building) -> Building:
    return building_from_json(building_to_json(building))


# ---------------------------------------------------------------------------
# Basic round-trip
# ---------------------------------------------------------------------------


def test_empty_building_roundtrip():
    b = Building(metadata=BuildingMetadata(name="Test"))
    restored = _roundtrip(b)
    assert restored.metadata.name == "Test"
    assert len(restored.levels) == 0


def test_single_level_building_roundtrip(single_level_building):
    restored = _roundtrip(single_level_building)
    assert len(restored.levels) == 1
    lv = restored.levels[0]
    assert lv.index == 0
    assert lv.elevation == 0.0
    assert len(lv.rooms) == 1
    assert len(lv.walls) == 1


def test_multi_level_building_roundtrip(multi_level_building):
    restored = _roundtrip(multi_level_building)
    assert len(restored.levels) == 3
    assert [lv.index for lv in restored.levels] == [0, 1, 2]


def test_room_fields_preserved(single_level_building):
    original_room = single_level_building.levels[0].rooms[0]
    restored = _roundtrip(single_level_building)
    room = restored.levels[0].rooms[0]
    assert room.name == original_room.name
    assert room.program == original_room.program
    assert room.area == pytest.approx(original_room.area, rel=1e-6)
    assert room.id == original_room.id


def test_wall_fields_preserved(single_level_building):
    original_wall = single_level_building.levels[0].walls[0]
    restored = _roundtrip(single_level_building)
    wall = restored.levels[0].walls[0]
    assert wall.wall_type == original_wall.wall_type
    assert wall.thickness == pytest.approx(original_wall.thickness)
    assert wall.height == pytest.approx(original_wall.height)
    assert wall.id == original_wall.id


def test_wall_with_door_roundtrip(wall_with_door):
    level = Level(index=0, elevation=0.0, floor_height=3.0).add_wall(wall_with_door)
    b = Building().add_level(level)
    restored = _roundtrip(b)
    wall = restored.levels[0].walls[0]
    assert len(wall.openings) == 1
    assert wall.openings[0].kind == OpeningKind.DOOR
    assert wall.openings[0].width == pytest.approx(0.9)


def test_donut_room_roundtrip(donut_room):
    level = Level(index=0, elevation=0.0, floor_height=3.0).add_room(donut_room)
    b = Building().add_level(level)
    restored = _roundtrip(b)
    room = restored.levels[0].rooms[0]
    assert room.area == pytest.approx(donut_room.area, rel=1e-6)


def test_column_roundtrip(rectangular_column):
    level = Level(index=0, elevation=0.0, floor_height=3.0).add_column(rectangular_column)
    b = Building().add_level(level)
    restored = _roundtrip(b)
    col = restored.levels[0].columns[0]
    assert col.height == pytest.approx(rectangular_column.height)
    assert col.shape == rectangular_column.shape


def test_metadata_roundtrip():
    b = Building(metadata=BuildingMetadata(
        name="Grand Tower",
        architect="Jane Doe",
        client="Acme Corp",
        project_number="2024-001",
        date="2024-01-15",
    ))
    restored = _roundtrip(b)
    assert restored.metadata.name == "Grand Tower"
    assert restored.metadata.architect == "Jane Doe"
    assert restored.metadata.client == "Acme Corp"


def test_arc_curve_wall_roundtrip():
    """Wall with ArcCurve geometry round-trips correctly."""
    center = Point2D(x=5.0, y=0.0, crs=WORLD)
    arc = ArcCurve(center=center, radius=5.0, start_angle=0.0, end_angle=math.pi, crs=WORLD)
    wall = Wall(geometry=arc, thickness=0.2, height=3.0)
    level = Level(index=0, elevation=0.0, floor_height=3.0).add_wall(wall)
    b = Building().add_level(level)
    restored = _roundtrip(b)
    w = restored.levels[0].walls[0]
    assert isinstance(w.geometry, ArcCurve)
    assert w.geometry.radius == pytest.approx(5.0)
    assert w.geometry.start_angle == pytest.approx(0.0)
    assert w.geometry.end_angle == pytest.approx(math.pi)


def test_bezier_curve_wall_roundtrip():
    pts = (
        Point2D(x=0, y=0, crs=WORLD),
        Point2D(x=1, y=2, crs=WORLD),
        Point2D(x=3, y=2, crs=WORLD),
        Point2D(x=4, y=0, crs=WORLD),
    )
    curve = BezierCurve(control_points=pts, crs=WORLD)
    wall = Wall(geometry=curve, thickness=0.2, height=3.0)
    level = Level(index=0, elevation=0.0, floor_height=3.0).add_wall(wall)
    b = Building().add_level(level)
    restored = _roundtrip(b)
    w = restored.levels[0].walls[0]
    assert isinstance(w.geometry, BezierCurve)
    assert len(w.geometry.control_points) == 4


# ---------------------------------------------------------------------------
# JSON structure
# ---------------------------------------------------------------------------


def test_json_is_valid_json(single_level_building):
    s = building_to_json(single_level_building)
    parsed = json.loads(s)
    assert parsed["_archit_app_version"] == "0.2.0"
    assert "levels" in parsed
    assert "metadata" in parsed


def test_json_coordinate_format(single_level_building):
    d = building_to_dict(single_level_building)
    room_data = d["levels"][0]["rooms"][0]
    assert room_data["type"] == "Room"
    exterior = room_data["boundary"]["exterior"]
    assert isinstance(exterior, list)
    assert all(isinstance(coord, list) and len(coord) == 2 for coord in exterior)


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def test_save_and_load_building(single_level_building):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        save_building(single_level_building, path)
        loaded = load_building(path)
        assert len(loaded.levels) == 1
        assert len(loaded.levels[0].rooms) == 1
    finally:
        os.unlink(path)


def test_tags_roundtrip():
    room = Room(
        boundary=Polygon2D.rectangle(0, 0, 4, 4, crs=WORLD),
        name="tagged",
        tags={"fire_rating": "1hr", "occupancy": 50},
    )
    level = Level(index=0, elevation=0.0, floor_height=3.0).add_room(room)
    b = Building().add_level(level)
    restored = _roundtrip(b)
    r = restored.levels[0].rooms[0]
    assert r.tags["fire_rating"] == "1hr"
    assert r.tags["occupancy"] == 50
