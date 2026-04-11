import pytest

from archit_app import WORLD, Point2D, Polygon2D, CRSMismatchError


def square(size=4.0) -> Polygon2D:
    pts = (
        Point2D(x=0, y=0, crs=WORLD),
        Point2D(x=size, y=0, crs=WORLD),
        Point2D(x=size, y=size, crs=WORLD),
        Point2D(x=0, y=size, crs=WORLD),
    )
    return Polygon2D(exterior=pts, crs=WORLD)


def test_area_square():
    poly = square(4.0)
    assert poly.area == pytest.approx(16.0)


def test_polygon_rectangle_factory():
    poly = Polygon2D.rectangle(0, 0, 5, 3, crs=WORLD)
    assert poly.area == pytest.approx(15.0)
    assert len(poly.exterior) == 4


def test_polygon_circle_factory():
    poly = Polygon2D.circle(0, 0, radius=1.0, resolution=360, crs=WORLD)
    assert poly.area == pytest.approx(3.14159, rel=1e-3)


def test_centroid():
    poly = square(4.0)
    c = poly.centroid
    assert c.x == pytest.approx(2.0)
    assert c.y == pytest.approx(2.0)


def test_contains_point():
    poly = square(4.0)
    assert poly.contains_point(Point2D(x=2, y=2, crs=WORLD))
    assert not poly.contains_point(Point2D(x=5, y=5, crs=WORLD))


def test_polygon_with_hole():
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
    poly = Polygon2D(exterior=exterior, holes=(hole,), crs=WORLD)
    # Area = 10*10 - 4*4 = 84
    assert poly.area == pytest.approx(84.0)


def test_bounding_box():
    poly = square(4.0)
    bb = poly.bounding_box()
    assert bb.width == pytest.approx(4.0)
    assert bb.height == pytest.approx(4.0)


def test_union():
    p1 = Polygon2D.rectangle(0, 0, 4, 4, crs=WORLD)
    p2 = Polygon2D.rectangle(2, 0, 4, 4, crs=WORLD)
    result = p1.union(p2)
    assert result.area == pytest.approx(24.0)


def test_intersection():
    p1 = Polygon2D.rectangle(0, 0, 4, 4, crs=WORLD)
    p2 = Polygon2D.rectangle(2, 0, 4, 4, crs=WORLD)
    result = p1.intersection(p2)
    assert result is not None
    assert result.area == pytest.approx(8.0)


def test_no_intersection_returns_none():
    p1 = Polygon2D.rectangle(0, 0, 2, 2, crs=WORLD)
    p2 = Polygon2D.rectangle(5, 5, 2, 2, crs=WORLD)
    assert p1.intersection(p2) is None


def test_is_convex():
    assert square().is_convex

    # L-shape is not convex
    pts = (
        Point2D(x=0, y=0, crs=WORLD),
        Point2D(x=6, y=0, crs=WORLD),
        Point2D(x=6, y=3, crs=WORLD),
        Point2D(x=3, y=3, crs=WORLD),
        Point2D(x=3, y=6, crs=WORLD),
        Point2D(x=0, y=6, crs=WORLD),
    )
    l_shape = Polygon2D(exterior=pts, crs=WORLD)
    assert not l_shape.is_convex


def test_too_few_vertices_raises():
    with pytest.raises(ValueError):
        Polygon2D(
            exterior=(Point2D(x=0, y=0, crs=WORLD), Point2D(x=1, y=0, crs=WORLD)),
            crs=WORLD,
        )


def test_transformed():
    from archit_app import Transform2D
    poly = Polygon2D.rectangle(0, 0, 2, 2, crs=WORLD)
    t = Transform2D.translate(5, 3)
    moved = poly.transformed(t)
    bb = moved.bounding_box()
    assert bb.min_corner.x == pytest.approx(5.0)
    assert bb.min_corner.y == pytest.approx(3.0)
