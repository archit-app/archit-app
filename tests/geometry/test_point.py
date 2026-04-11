import pytest

from archit_app import WORLD, SCREEN, Point2D, Point3D, Vector2D, CRSMismatchError, Transform2D


def test_point_add_vector():
    p = Point2D(x=1.0, y=2.0, crs=WORLD)
    v = Vector2D(x=3.0, y=4.0, crs=WORLD)
    result = p + v
    assert isinstance(result, Point2D)
    assert result.x == pytest.approx(4.0)
    assert result.y == pytest.approx(6.0)
    assert result.crs == WORLD


def test_point_subtract_point_gives_vector():
    p1 = Point2D(x=5.0, y=3.0, crs=WORLD)
    p2 = Point2D(x=2.0, y=1.0, crs=WORLD)
    result = p1 - p2
    assert isinstance(result, Vector2D)
    assert result.x == pytest.approx(3.0)
    assert result.y == pytest.approx(2.0)


def test_point_subtract_vector():
    p = Point2D(x=5.0, y=3.0, crs=WORLD)
    v = Vector2D(x=1.0, y=1.0, crs=WORLD)
    result = p - v
    assert isinstance(result, Point2D)
    assert result.x == pytest.approx(4.0)
    assert result.y == pytest.approx(2.0)


def test_point_add_point_raises():
    p1 = Point2D(x=1.0, y=0.0, crs=WORLD)
    p2 = Point2D(x=2.0, y=0.0, crs=WORLD)
    with pytest.raises(TypeError):
        _ = p1 + p2


def test_point_crs_mismatch_raises():
    p = Point2D(x=0.0, y=0.0, crs=WORLD)
    v = Vector2D(x=1.0, y=0.0, crs=SCREEN)
    with pytest.raises(CRSMismatchError):
        _ = p + v


def test_point_distance():
    p1 = Point2D(x=0.0, y=0.0, crs=WORLD)
    p2 = Point2D(x=3.0, y=4.0, crs=WORLD)
    assert p1.distance_to(p2) == pytest.approx(5.0)


def test_point_midpoint():
    p1 = Point2D(x=0.0, y=0.0, crs=WORLD)
    p2 = Point2D(x=4.0, y=2.0, crs=WORLD)
    mid = p1.midpoint(p2)
    assert mid.x == pytest.approx(2.0)
    assert mid.y == pytest.approx(1.0)


def test_point_transformed():
    p = Point2D(x=0.0, y=0.0, crs=WORLD)
    t = Transform2D.translate(5.0, 3.0)
    result = p.transformed(t)
    assert result.x == pytest.approx(5.0)
    assert result.y == pytest.approx(3.0)


def test_point_as_array():
    import numpy as np
    p = Point2D(x=1.5, y=2.5, crs=WORLD)
    arr = p.as_array()
    assert arr.shape == (2,)
    assert arr[0] == pytest.approx(1.5)
    assert arr[1] == pytest.approx(2.5)


def test_point3d_subtract():
    from archit_app import Vector3D
    p1 = Point3D(x=3.0, y=4.0, z=5.0, crs=WORLD)
    p2 = Point3D(x=1.0, y=1.0, z=1.0, crs=WORLD)
    v = p1 - p2
    assert isinstance(v, Vector3D)
    assert v.x == pytest.approx(2.0)
    assert v.z == pytest.approx(4.0)
