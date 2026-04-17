"""Tests for BoundingBox2D and BoundingBox3D."""

import pytest

from archit_app.geometry.crs import WORLD, SCREEN
from archit_app.geometry.point import Point2D, Point3D
from archit_app.geometry.bbox import BoundingBox2D, BoundingBox3D


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def p2(x, y, crs=WORLD):
    return Point2D(x=x, y=y, crs=crs)


def p3(x, y, z, crs=WORLD):
    return Point3D(x=x, y=y, z=z, crs=crs)


def bb(x0, y0, x1, y1, crs=WORLD):
    return BoundingBox2D(min_corner=p2(x0, y0, crs), max_corner=p2(x1, y1, crs))


# ===========================================================================
# BoundingBox2D
# ===========================================================================

class TestBoundingBox2D:

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def test_basic(self):
        b = bb(0, 0, 4, 3)
        assert b.min_corner.x == pytest.approx(0.0)
        assert b.max_corner.y == pytest.approx(3.0)

    def test_invalid_min_gt_max_raises(self):
        with pytest.raises(ValueError):
            bb(5, 0, 3, 4)   # min_x > max_x

    def test_invalid_min_y_gt_max_y_raises(self):
        with pytest.raises(ValueError):
            bb(0, 5, 4, 3)   # min_y > max_y

    def test_degenerate_point_allowed(self):
        # Zero-area box (single point) is valid
        b = bb(2, 2, 2, 2)
        assert b.area == pytest.approx(0.0)

    def test_crs_mismatch_raises(self):
        with pytest.raises(Exception):
            BoundingBox2D(min_corner=p2(0, 0, WORLD), max_corner=p2(1, 1, SCREEN))

    # ------------------------------------------------------------------
    # from_points
    # ------------------------------------------------------------------

    def test_from_points_basic(self):
        pts = [p2(1, 3), p2(5, 0), p2(2, 7)]
        b = BoundingBox2D.from_points(pts)
        assert b.min_corner.x == pytest.approx(1.0)
        assert b.min_corner.y == pytest.approx(0.0)
        assert b.max_corner.x == pytest.approx(5.0)
        assert b.max_corner.y == pytest.approx(7.0)

    def test_from_points_single(self):
        b = BoundingBox2D.from_points([p2(3, 4)])
        assert b.min_corner == b.max_corner

    def test_from_points_empty_raises(self):
        with pytest.raises(ValueError):
            BoundingBox2D.from_points([])

    def test_from_points_crs_mismatch_raises(self):
        with pytest.raises(Exception):
            BoundingBox2D.from_points([p2(0, 0, WORLD), p2(1, 1, SCREEN)])

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    def test_width(self):
        assert bb(1, 0, 5, 3).width == pytest.approx(4.0)

    def test_height(self):
        assert bb(0, 2, 4, 7).height == pytest.approx(5.0)

    def test_area(self):
        assert bb(0, 0, 3, 4).area == pytest.approx(12.0)

    def test_center(self):
        c = bb(0, 0, 4, 6).center
        assert c.x == pytest.approx(2.0)
        assert c.y == pytest.approx(3.0)

    def test_crs_property(self):
        assert bb(0, 0, 1, 1).crs == WORLD

    # ------------------------------------------------------------------
    # contains_point
    # ------------------------------------------------------------------

    def test_contains_interior(self):
        assert bb(0, 0, 4, 4).contains_point(p2(2, 2))

    def test_contains_on_boundary(self):
        assert bb(0, 0, 4, 4).contains_point(p2(0, 0))
        assert bb(0, 0, 4, 4).contains_point(p2(4, 4))

    def test_not_contains_exterior(self):
        assert not bb(0, 0, 4, 4).contains_point(p2(5, 2))

    def test_contains_crs_mismatch_raises(self):
        with pytest.raises(Exception):
            bb(0, 0, 4, 4).contains_point(p2(2, 2, SCREEN))

    # ------------------------------------------------------------------
    # intersects
    # ------------------------------------------------------------------

    def test_intersects_overlapping(self):
        assert bb(0, 0, 4, 4).intersects(bb(2, 2, 6, 6))

    def test_intersects_touching(self):
        # Boxes that touch exactly on an edge do intersect (inclusive)
        assert bb(0, 0, 4, 4).intersects(bb(4, 0, 8, 4))

    def test_not_intersects_disjoint(self):
        assert not bb(0, 0, 2, 2).intersects(bb(3, 3, 5, 5))

    def test_intersects_containment(self):
        assert bb(0, 0, 10, 10).intersects(bb(2, 2, 4, 4))

    # ------------------------------------------------------------------
    # intersection
    # ------------------------------------------------------------------

    def test_intersection_basic(self):
        i = bb(0, 0, 4, 4).intersection(bb(2, 2, 6, 6))
        assert i is not None
        assert i.min_corner.x == pytest.approx(2.0)
        assert i.min_corner.y == pytest.approx(2.0)
        assert i.max_corner.x == pytest.approx(4.0)
        assert i.max_corner.y == pytest.approx(4.0)

    def test_intersection_none_when_disjoint(self):
        i = bb(0, 0, 2, 2).intersection(bb(3, 3, 5, 5))
        assert i is None

    # ------------------------------------------------------------------
    # union
    # ------------------------------------------------------------------

    def test_union(self):
        u = bb(0, 0, 2, 2).union(bb(1, 1, 4, 5))
        assert u.min_corner.x == pytest.approx(0.0)
        assert u.min_corner.y == pytest.approx(0.0)
        assert u.max_corner.x == pytest.approx(4.0)
        assert u.max_corner.y == pytest.approx(5.0)

    def test_union_disjoint(self):
        u = bb(0, 0, 1, 1).union(bb(3, 3, 4, 4))
        assert u.min_corner.x == pytest.approx(0.0)
        assert u.max_corner.x == pytest.approx(4.0)

    # ------------------------------------------------------------------
    # expanded
    # ------------------------------------------------------------------

    def test_expanded(self):
        e = bb(1, 1, 3, 3).expanded(0.5)
        assert e.min_corner.x == pytest.approx(0.5)
        assert e.min_corner.y == pytest.approx(0.5)
        assert e.max_corner.x == pytest.approx(3.5)
        assert e.max_corner.y == pytest.approx(3.5)

    def test_expanded_zero(self):
        b = bb(1, 1, 3, 3)
        e = b.expanded(0.0)
        assert e.min_corner.x == pytest.approx(b.min_corner.x)
        assert e.max_corner.x == pytest.approx(b.max_corner.x)

    # ------------------------------------------------------------------
    # to_polygon
    # ------------------------------------------------------------------

    def test_to_polygon(self):
        from archit_app.geometry.polygon import Polygon2D
        poly = bb(0, 0, 3, 4).to_polygon()
        assert isinstance(poly, Polygon2D)
        assert poly.area == pytest.approx(12.0)

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def test_repr(self):
        assert "BoundingBox2D" in repr(bb(0, 0, 1, 1))


# ===========================================================================
# BoundingBox3D
# ===========================================================================

class TestBoundingBox3D:

    def _bb(self, x0, y0, z0, x1, y1, z1):
        return BoundingBox3D(
            min_corner=p3(x0, y0, z0),
            max_corner=p3(x1, y1, z1),
        )

    def test_basic(self):
        b = self._bb(0, 0, 0, 4, 3, 2)
        assert b.width == pytest.approx(4.0)
        assert b.depth == pytest.approx(3.0)
        assert b.height == pytest.approx(2.0)

    def test_volume(self):
        assert self._bb(0, 0, 0, 4, 3, 2).volume == pytest.approx(24.0)

    def test_crs_property(self):
        assert self._bb(0, 0, 0, 1, 1, 1).crs == WORLD

    def test_crs_mismatch_raises(self):
        with pytest.raises(Exception):
            BoundingBox3D(
                min_corner=p3(0, 0, 0, WORLD),
                max_corner=p3(1, 1, 1, SCREEN),
            )

    def test_zero_volume(self):
        b = self._bb(1, 1, 1, 1, 1, 1)
        assert b.volume == pytest.approx(0.0)
