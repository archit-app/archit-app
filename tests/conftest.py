"""
Canonical test fixtures for the floorplan package.

Every analysis, I/O, and rendering module should pass against all of these
fixtures before being merged.
"""

import math

import pytest

from archit_app import (
    WORLD,
    Beam,
    Building,
    BuildingMetadata,
    Column,
    DimensionLine,
    Furniture,
    Level,
    Opening,
    Point2D,
    Polygon2D,
    Ramp,
    Room,
    SectionMark,
    Slab,
    Staircase,
    TextAnnotation,
    Wall,
    WallType,
)
from archit_app.elements.elevator import Elevator


@pytest.fixture
def simple_square_room() -> Room:
    """4m × 4m axis-aligned room. The simplest possible floorplan."""
    pts = (
        Point2D(x=0, y=0, crs=WORLD),
        Point2D(x=4, y=0, crs=WORLD),
        Point2D(x=4, y=4, crs=WORLD),
        Point2D(x=0, y=4, crs=WORLD),
    )
    boundary = Polygon2D(exterior=pts, crs=WORLD)
    return Room(boundary=boundary, name="square_room", program="living")


@pytest.fixture
def l_shaped_room() -> Room:
    """L-shaped room — tests non-convex polygon handling."""
    pts = (
        Point2D(x=0, y=0, crs=WORLD),
        Point2D(x=6, y=0, crs=WORLD),
        Point2D(x=6, y=3, crs=WORLD),
        Point2D(x=3, y=3, crs=WORLD),
        Point2D(x=3, y=6, crs=WORLD),
        Point2D(x=0, y=6, crs=WORLD),
    )
    boundary = Polygon2D(exterior=pts, crs=WORLD)
    return Room(boundary=boundary, name="l_room", program="living")


@pytest.fixture
def donut_room() -> Room:
    """Room with a square courtyard hole — tests polygon-with-holes."""
    exterior = (
        Point2D(x=0, y=0, crs=WORLD),
        Point2D(x=10, y=0, crs=WORLD),
        Point2D(x=10, y=10, crs=WORLD),
        Point2D(x=0, y=10, crs=WORLD),
    )
    hole = (
        Point2D(x=3, y=3, crs=WORLD),
        Point2D(x=7, y=3, crs=WORLD),
        Point2D(x=7, y=7, crs=WORLD),
        Point2D(x=3, y=7, crs=WORLD),
    )
    boundary = Polygon2D(exterior=exterior, holes=(hole,), crs=WORLD)
    return Room(boundary=boundary, name="donut_room", program="courtyard")


@pytest.fixture
def simple_wall() -> Wall:
    """A straight 5m exterior wall, 0.2m thick."""
    return Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0, wall_type=WallType.EXTERIOR)


@pytest.fixture
def wall_with_door(simple_wall: Wall) -> Wall:
    """simple_wall with a 0.9m door punched in."""
    door = Opening.door(x=2.0, y=-0.1, width=0.9, height=2.1, wall_thickness=0.2)
    return simple_wall.add_opening(door)


@pytest.fixture
def rectangular_column() -> Column:
    """A 0.4m × 0.4m rectangular column, 3m tall."""
    return Column.rectangular(x=0.0, y=0.0, width=0.4, depth=0.4, height=3.0)


@pytest.fixture
def circular_column() -> Column:
    """A 0.5m diameter circular column, 3m tall."""
    return Column.circular(center_x=0.0, center_y=0.0, diameter=0.5, height=3.0)


@pytest.fixture
def single_level_building(simple_square_room: Room, simple_wall: Wall) -> Building:
    """One ground-floor level with one room and one wall."""
    level = Level(index=0, elevation=0.0, floor_height=3.0, name="Ground Floor")
    level = level.add_room(simple_square_room)
    level = level.add_wall(simple_wall)
    return Building().add_level(level)


@pytest.fixture
def simple_staircase() -> Staircase:
    """12-riser straight staircase."""
    return Staircase.straight(
        x=0, y=0, width=1.2, rise_count=12,
        rise_height=0.175, run_depth=0.28,
        bottom_level_index=0, top_level_index=1,
    )


@pytest.fixture
def simple_slab() -> Slab:
    """4 × 4 m floor slab."""
    return Slab.rectangular(x=0, y=0, width=4, depth=4, thickness=0.2, elevation=0.0)


@pytest.fixture
def simple_ramp() -> Ramp:
    """1.5 m wide accessible ramp (1:12 slope)."""
    return Ramp.straight(x=0, y=0, width=1.5, length=3.6, slope_angle=math.atan(1 / 12))


@pytest.fixture
def simple_beam() -> Beam:
    """5 m structural beam."""
    return Beam.straight(x1=0, y1=0, x2=5, y2=0, width=0.3, depth=0.5, elevation=3.0)


@pytest.fixture
def simple_furniture() -> Furniture:
    """Sofa furniture item."""
    return Furniture.sofa(x=1, y=1)


@pytest.fixture
def simple_text_annotation() -> TextAnnotation:
    """Text label at origin."""
    return TextAnnotation.note(
        text="Test note",
        position=Point2D(x=2.0, y=2.0, crs=WORLD),
    )


@pytest.fixture
def simple_dimension() -> DimensionLine:
    """Horizontal 4 m dimension line."""
    return DimensionLine.horizontal(
        x1=0.0, x2=4.0, y=5.0, crs=WORLD, offset=0.5
    )


@pytest.fixture
def simple_section_mark() -> SectionMark:
    """Horizontal section mark."""
    return SectionMark.horizontal(x1=0.0, x2=5.0, y=3.0, crs=WORLD, tag="A")


@pytest.fixture
def simple_elevator() -> Elevator:
    """1.1 × 1.4 m elevator."""
    return Elevator.rectangular(x=8, y=0, cab_width=1.1, cab_depth=1.4,
                                 bottom_level_index=0, top_level_index=2)


@pytest.fixture
def multi_level_building(simple_square_room: Room, simple_wall: Wall) -> Building:
    """3-storey building — tests Level indexing and Building.get_level."""
    b = Building(metadata=BuildingMetadata(name="Test Tower"))
    for i in range(3):
        level = Level(
            index=i,
            elevation=float(i * 3),
            floor_height=3.0,
            name=f"Level {i}",
        )
        level = level.add_room(simple_square_room)
        level = level.add_wall(simple_wall)
        b = b.add_level(level)
    return b
