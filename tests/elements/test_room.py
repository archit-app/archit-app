import pytest

from floorplan import WORLD, Point2D, Polygon2D, Room


def make_room(pts, name="test", program="living") -> Room:
    boundary = Polygon2D(exterior=tuple(pts), crs=WORLD)
    return Room(boundary=boundary, name=name, program=program)


def test_square_room_area(simple_square_room):
    assert simple_square_room.area == pytest.approx(16.0)


def test_l_shaped_room_area(l_shaped_room):
    # L-shape: 6×6 - 3×3 = 27
    assert l_shaped_room.area == pytest.approx(27.0)


def test_donut_room_area(donut_room):
    # 10×10 - 4×4 = 84
    assert donut_room.area == pytest.approx(84.0)


def test_room_contains_point(simple_square_room):
    assert simple_square_room.contains_point(Point2D(x=2, y=2, crs=WORLD))
    assert not simple_square_room.contains_point(Point2D(x=5, y=5, crs=WORLD))


def test_donut_room_hole_exclusion(donut_room):
    # Inside outer boundary but inside the hole
    inside_hole = Point2D(x=5, y=5, crs=WORLD)
    assert not donut_room.contains_point(inside_hole)
    # Inside outer boundary, outside hole
    outside_hole = Point2D(x=1, y=1, crs=WORLD)
    assert donut_room.contains_point(outside_hole)


def test_room_frozen(simple_square_room):
    with pytest.raises(Exception):
        simple_square_room.name = "changed"  # type: ignore


def test_room_with_name(simple_square_room):
    new_room = simple_square_room.with_name("Master Bedroom")
    assert new_room.name == "Master Bedroom"
    assert simple_square_room.name == "square_room"  # unchanged


def test_room_add_hole():
    pts = (
        Point2D(x=0, y=0, crs=WORLD),
        Point2D(x=10, y=0, crs=WORLD),
        Point2D(x=10, y=10, crs=WORLD),
        Point2D(x=0, y=10, crs=WORLD),
    )
    room = Room(boundary=Polygon2D(exterior=pts, crs=WORLD))
    hole = Polygon2D.rectangle(3, 3, 4, 4, crs=WORLD)
    room2 = room.add_hole(hole)
    assert len(room.holes) == 0
    assert len(room2.holes) == 1
    assert room2.area == pytest.approx(10 * 10 - 4 * 4)


def test_room_centroid(simple_square_room):
    c = simple_square_room.centroid
    assert c.x == pytest.approx(2.0)
    assert c.y == pytest.approx(2.0)
