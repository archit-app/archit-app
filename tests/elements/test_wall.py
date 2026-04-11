import pytest

from floorplan import Wall, WallType, Opening, OpeningKind, Point2D, Polygon2D, WORLD


def test_wall_straight_factory():
    wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
    assert isinstance(wall, Wall)
    assert wall.thickness == pytest.approx(0.2)
    assert wall.height == pytest.approx(3.0)


def test_wall_length():
    wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
    assert wall.length == pytest.approx(5.0, abs=0.05)


def test_wall_add_opening_immutable():
    wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
    door = Opening.door(x=2.0, y=-0.1, width=0.9)
    new_wall = wall.add_opening(door)
    assert len(wall.openings) == 0
    assert len(new_wall.openings) == 1


def test_wall_bounding_box():
    wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
    bb = wall.bounding_box()
    assert bb.width == pytest.approx(5.0)


def test_wall_frozen():
    wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
    with pytest.raises(Exception):
        wall.height = 4.0  # type: ignore


def test_wall_invalid_thickness():
    with pytest.raises(ValueError):
        Wall.straight(0, 0, 5, 0, thickness=-0.1, height=3.0)


def test_wall_invalid_height():
    with pytest.raises(ValueError):
        Wall.straight(0, 0, 5, 0, thickness=0.2, height=0)
