"""Tests for JSON serialization round-trips."""

import json
import math
import os
import tempfile

import pytest

from archit_app import (
    WORLD,
    ArcCurve,
    Beam,
    BezierCurve,
    Building,
    BuildingMetadata,
    Column,
    DimensionLine,
    Furniture,
    Level,
    OpeningKind,
    Point2D,
    Polygon2D,
    Ramp,
    Room,
    SectionMark,
    Slab,
    SlabType,
    Staircase,
    TextAnnotation,
    Wall,
)
from archit_app.building.grid import StructuralGrid
from archit_app.elements.elevator import Elevator
from archit_app.io.json_schema import (
    building_from_json,
    building_to_dict,
    building_to_json,
    load_building,
    save_building,
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
    from archit_app import __version__
    assert parsed["_archit_app_version"] == __version__
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


# ---------------------------------------------------------------------------
# Round-trips for newer element types
# ---------------------------------------------------------------------------


def test_staircase_roundtrip():
    stair = Staircase.straight(
        x=0, y=0, width=1.2, rise_count=12,
        rise_height=0.175, run_depth=0.28,
        bottom_level_index=0, top_level_index=1,
    )
    level = Level(index=0, elevation=0.0, floor_height=3.0).add_staircase(stair)
    b = Building().add_level(level)
    restored = _roundtrip(b)
    s = restored.levels[0].staircases[0]
    assert s.rise_count == 12
    assert s.rise_height == pytest.approx(0.175)
    assert s.id == stair.id


def test_slab_roundtrip():
    slab = Slab.rectangular(x=0, y=0, width=6, depth=5, thickness=0.2, elevation=0.0,
                             slab_type=SlabType.FLOOR)
    level = Level(index=0, elevation=0.0, floor_height=3.0).add_slab(slab)
    b = Building().add_level(level)
    restored = _roundtrip(b)
    s = restored.levels[0].slabs[0]
    assert s.thickness == pytest.approx(0.2)
    assert s.slab_type == SlabType.FLOOR
    assert s.id == slab.id


def test_ramp_roundtrip():
    ramp = Ramp.straight(x=0, y=0, width=1.5, length=3.6,
                          slope_angle=math.atan(1 / 12))
    level = Level(index=0, elevation=0.0, floor_height=3.0).add_ramp(ramp)
    b = Building().add_level(level)
    restored = _roundtrip(b)
    r = restored.levels[0].ramps[0]
    assert r.width == pytest.approx(1.5)
    assert r.slope_angle == pytest.approx(ramp.slope_angle)
    assert r.id == ramp.id


def test_beam_roundtrip():
    beam = Beam.straight(x1=0, y1=0, x2=6, y2=0, width=0.3, depth=0.5, elevation=3.0)
    level = Level(index=0, elevation=0.0, floor_height=3.0).add_beam(beam)
    b = Building().add_level(level)
    restored = _roundtrip(b)
    bm = restored.levels[0].beams[0]
    assert bm.width == pytest.approx(0.3)
    assert bm.depth == pytest.approx(0.5)
    assert bm.elevation == pytest.approx(3.0)
    assert bm.id == beam.id


def test_furniture_roundtrip():
    furn = Furniture.sofa(x=1, y=1)
    level = Level(index=0, elevation=0.0, floor_height=3.0).add_furniture(furn)
    b = Building().add_level(level)
    restored = _roundtrip(b)
    f = restored.levels[0].furniture[0]
    assert f.id == furn.id
    assert f.category == furn.category


def test_text_annotation_roundtrip():
    ann = TextAnnotation.note(
        x=2.0, y=2.0, crs=WORLD,
        text="Room A",
        rotation=0.5,
    )
    level = Level(index=0, elevation=0.0, floor_height=3.0).add_text_annotation(ann)
    b = Building().add_level(level)
    restored = _roundtrip(b)
    a = restored.levels[0].text_annotations[0]
    assert a.text == "Room A"
    assert a.rotation == pytest.approx(0.5)
    assert a.id == ann.id


def test_dimension_line_roundtrip():
    dim = DimensionLine.horizontal(x1=0.0, x2=4.0, y=5.0, crs=WORLD, offset=0.5)
    level = Level(index=0, elevation=0.0, floor_height=3.0).add_dimension(dim)
    b = Building().add_level(level)
    restored = _roundtrip(b)
    d = restored.levels[0].dimensions[0]
    assert d.measured_distance == pytest.approx(4.0)
    assert d.offset == pytest.approx(0.5)
    assert d.id == dim.id


def test_section_mark_roundtrip():
    mark = SectionMark.horizontal(x1=0.0, x2=5.0, y=3.0, crs=WORLD, tag="A")
    level = Level(index=0, elevation=0.0, floor_height=3.0).add_section_mark(mark)
    b = Building().add_level(level)
    restored = _roundtrip(b)
    m = restored.levels[0].section_marks[0]
    assert m.tag == "A"
    assert m.id == mark.id


def test_elevator_roundtrip():
    elev = Elevator.rectangular(x=8, y=0, cab_width=1.1, cab_depth=1.4,
                                 bottom_level_index=0, top_level_index=3)
    b = Building().add_elevator(elev)
    restored = _roundtrip(b)
    e = restored.elevators[0]
    assert e.cab_width == pytest.approx(elev.cab_width)
    assert e.cab_depth == pytest.approx(elev.cab_depth)
    assert e.id == elev.id


def test_structural_grid_roundtrip():
    grid = StructuralGrid.regular(x_spacing=6.0, y_spacing=6.0, x_count=3, y_count=3)
    b = Building().with_grid(grid)
    restored = _roundtrip(b)
    g = restored.grid
    assert g is not None
    assert len(g.x_axes) == len(grid.x_axes)
    assert len(g.y_axes) == len(grid.y_axes)


def test_all_element_types_survive_roundtrip():
    """Smoke test: a level with every element type round-trips without data loss."""
    import math as _m
    stair = Staircase.straight(x=7, y=0, width=1.2, rise_count=10,
                                rise_height=0.175, run_depth=0.28,
                                bottom_level_index=0, top_level_index=1)
    slab  = Slab.rectangular(x=0, y=0, width=6, depth=5, thickness=0.2, elevation=0.0)
    ramp  = Ramp.straight(x=0, y=6, width=1.5, length=3.6, slope_angle=_m.atan(1/12))
    beam  = Beam.straight(x1=0, y1=0, x2=6, y2=0, width=0.3, depth=0.5, elevation=3.0)
    furn  = Furniture.sofa(x=1, y=1)
    ann   = TextAnnotation.note(x=3, y=3, crs=WORLD, text="Note")
    dim   = DimensionLine.horizontal(x1=0, x2=4, y=6, crs=WORLD)
    mark  = SectionMark.horizontal(x1=0, x2=5, y=7, crs=WORLD, tag="B")
    room  = Room(boundary=Polygon2D.rectangle(0, 0, 6, 5, crs=WORLD), name="Hall")
    wall  = Wall.straight(0, 0, 6, 0, thickness=0.2, height=3.0)
    col   = Column.rectangular(x=5, y=4, width=0.3, depth=0.3, height=3.0)

    level = (
        Level(index=0, elevation=0.0, floor_height=3.0)
        .add_room(room).add_wall(wall).add_column(col)
        .add_staircase(stair).add_slab(slab).add_ramp(ramp)
        .add_beam(beam).add_furniture(furn)
        .add_text_annotation(ann).add_dimension(dim).add_section_mark(mark)
    )
    elev = Elevator.rectangular(x=10, y=0, cab_width=1.1, cab_depth=1.4,
                                 bottom_level_index=0, top_level_index=1)
    b = Building().add_level(level).add_elevator(elev)
    restored = _roundtrip(b)
    lv = restored.levels[0]
    assert len(lv.rooms) == 1
    assert len(lv.walls) == 1
    assert len(lv.columns) == 1
    assert len(lv.staircases) == 1
    assert len(lv.slabs) == 1
    assert len(lv.ramps) == 1
    assert len(lv.beams) == 1
    assert len(lv.furniture) == 1
    assert len(lv.text_annotations) == 1
    assert len(lv.dimensions) == 1
    assert len(lv.section_marks) == 1
    assert len(restored.elevators) == 1
