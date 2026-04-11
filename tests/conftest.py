"""
Canonical test fixtures for the floorplan package.

Every analysis, I/O, and rendering module should pass against all of these
fixtures before being merged.
"""

import pytest

from floorplan import (
    WORLD,
    Building,
    BuildingMetadata,
    Column,
    Level,
    Opening,
    OpeningKind,
    Point2D,
    Polygon2D,
    Room,
    Wall,
    WallType,
)


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
