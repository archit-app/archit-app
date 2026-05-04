"""Tests for Segment2D, Ray2D, Line2D, and Polyline2D."""

import math

import pytest

from archit_app.geometry.crs import SCREEN, WORLD
from archit_app.geometry.point import Point2D
from archit_app.geometry.primitives import Line2D, Polyline2D, Ray2D, Segment2D
from archit_app.geometry.vector import Vector2D

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def p(x: float, y: float, crs=WORLD) -> Point2D:
    return Point2D(x=x, y=y, crs=crs)


def v(x: float, y: float, crs=WORLD) -> Vector2D:
    return Vector2D(x=x, y=y, crs=crs)


# ---------------------------------------------------------------------------
# Segment2D
# ---------------------------------------------------------------------------

class TestSegment2D:
    def test_basic_properties(self):
        seg = Segment2D(start=p(0, 0), end=p(3, 4))
        assert seg.length == pytest.approx(5.0)
        assert seg.midpoint == p(1.5, 2.0)
        assert seg.crs == WORLD

    def test_direction(self):
        seg = Segment2D(start=p(0, 0), end=p(1, 0))
        d = seg.direction
        assert d.x == pytest.approx(1.0)
        assert d.y == pytest.approx(0.0)

    def test_direction_diagonal(self):
        seg = Segment2D(start=p(0, 0), end=p(1, 1))
        d = seg.direction
        assert d.magnitude == pytest.approx(1.0)
        assert d.x == pytest.approx(1 / math.sqrt(2))
        assert d.y == pytest.approx(1 / math.sqrt(2))

    def test_zero_length_direction_raises(self):
        seg = Segment2D(start=p(1, 2), end=p(1, 2))
        with pytest.raises(ValueError, match="zero length"):
            _ = seg.direction

    def test_crs_mismatch_raises(self):
        with pytest.raises(Exception):
            Segment2D(start=p(0, 0, WORLD), end=p(1, 1, SCREEN))

    def test_at_interpolation(self):
        seg = Segment2D(start=p(0, 0), end=p(4, 0))
        assert seg.at(0.0) == p(0, 0)
        assert seg.at(1.0) == p(4, 0)
        assert seg.at(0.5) == p(2, 0)

    def test_closest_point_perpendicular(self):
        seg = Segment2D(start=p(0, 0), end=p(4, 0))
        cp = seg.closest_point(p(2, 3))
        assert cp.x == pytest.approx(2.0)
        assert cp.y == pytest.approx(0.0)

    def test_closest_point_clamped_at_start(self):
        seg = Segment2D(start=p(0, 0), end=p(4, 0))
        cp = seg.closest_point(p(-2, 0))
        assert cp == p(0, 0)

    def test_closest_point_clamped_at_end(self):
        seg = Segment2D(start=p(0, 0), end=p(4, 0))
        cp = seg.closest_point(p(6, 0))
        assert cp == p(4, 0)

    def test_distance_to_point(self):
        seg = Segment2D(start=p(0, 0), end=p(4, 0))
        assert seg.distance_to_point(p(2, 3)) == pytest.approx(3.0)

    def test_intersect_crossing(self):
        seg1 = Segment2D(start=p(0, 0), end=p(4, 0))
        seg2 = Segment2D(start=p(2, -2), end=p(2, 2))
        pt = seg1.intersect(seg2)
        assert pt is not None
        assert pt.x == pytest.approx(2.0)
        assert pt.y == pytest.approx(0.0)

    def test_intersect_parallel_returns_none(self):
        seg1 = Segment2D(start=p(0, 0), end=p(4, 0))
        seg2 = Segment2D(start=p(0, 1), end=p(4, 1))
        assert seg1.intersect(seg2) is None

    def test_intersect_non_overlapping_returns_none(self):
        seg1 = Segment2D(start=p(0, 0), end=p(1, 0))
        seg2 = Segment2D(start=p(3, -1), end=p(3, 1))
        assert seg1.intersect(seg2) is None

    def test_reversed(self):
        seg = Segment2D(start=p(0, 0), end=p(1, 2))
        r = seg.reversed()
        assert r.start == p(1, 2)
        assert r.end == p(0, 0)

    def test_as_polyline(self):
        seg = Segment2D(start=p(0, 0), end=p(1, 1))
        poly = seg.as_polyline()
        assert isinstance(poly, Polyline2D)
        assert len(poly) == 2

    def test_as_line(self):
        seg = Segment2D(start=p(0, 0), end=p(1, 0))
        line = seg.as_line()
        assert isinstance(line, Line2D)
        assert line.distance_to_point(p(5, 0)) == pytest.approx(0.0)

    def test_vector(self):
        seg = Segment2D(start=p(1, 2), end=p(4, 6))
        vec = seg.vector
        assert vec.x == pytest.approx(3.0)
        assert vec.y == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# Ray2D
# ---------------------------------------------------------------------------

class TestRay2D:
    def test_basic(self):
        ray = Ray2D(origin=p(0, 0), direction=v(1, 0))
        assert ray.at(3.0) == p(3, 0)

    def test_normalised_direction(self):
        ray = Ray2D(origin=p(0, 0), direction=v(3, 4))
        d = ray.unit_direction
        assert d.magnitude == pytest.approx(1.0)

    def test_zero_direction_raises(self):
        with pytest.raises(ValueError):
            Ray2D(origin=p(0, 0), direction=v(0, 0))

    def test_crs_property(self):
        ray = Ray2D(origin=p(0, 0), direction=v(1, 0))
        assert ray.crs == WORLD

    def test_intersect_segment_hit(self):
        ray = Ray2D(origin=p(0, 0), direction=v(1, 0))
        seg = Segment2D(start=p(2, -1), end=p(2, 1))
        pt = ray.intersect_segment(seg)
        assert pt is not None
        assert pt.x == pytest.approx(2.0)
        assert pt.y == pytest.approx(0.0)

    def test_intersect_segment_miss_behind(self):
        ray = Ray2D(origin=p(0, 0), direction=v(1, 0))
        seg = Segment2D(start=p(-2, -1), end=p(-2, 1))
        assert ray.intersect_segment(seg) is None

    def test_intersect_segment_parallel(self):
        ray = Ray2D(origin=p(0, 0), direction=v(1, 0))
        seg = Segment2D(start=p(0, 1), end=p(4, 1))
        assert ray.intersect_segment(seg) is None

    def test_to_segment(self):
        ray = Ray2D(origin=p(0, 0), direction=v(1, 0))
        seg = ray.to_segment(5.0)
        assert seg.start == p(0, 0)
        assert seg.end.x == pytest.approx(5.0)
        assert seg.end.y == pytest.approx(0.0)

    def test_intersect_line(self):
        ray = Ray2D(origin=p(0, 0), direction=v(1, 0))
        line = Line2D(point=p(2, 5), direction=v(0, 1))
        pt = ray.intersect_line(line)
        assert pt is not None
        assert pt.x == pytest.approx(2.0)
        assert pt.y == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Line2D
# ---------------------------------------------------------------------------

class TestLine2D:
    def test_basic_properties(self):
        line = Line2D(point=p(0, 0), direction=v(1, 0))
        assert line.crs == WORLD
        d = line.unit_direction
        assert d.magnitude == pytest.approx(1.0)

    def test_from_two_points(self):
        line = Line2D.from_two_points(p(0, 0), p(4, 0))
        assert line.distance_to_point(p(2, 0)) == pytest.approx(0.0)

    def test_from_segment(self):
        seg = Segment2D(start=p(1, 1), end=p(3, 3))
        line = Line2D.from_segment(seg)
        assert line.distance_to_point(p(5, 5)) == pytest.approx(0.0, abs=1e-9)

    def test_distance_to_point(self):
        line = Line2D(point=p(0, 0), direction=v(1, 0))
        assert line.distance_to_point(p(5, 3)) == pytest.approx(3.0)

    def test_closest_point(self):
        line = Line2D(point=p(0, 0), direction=v(1, 0))
        cp = line.closest_point(p(3, 7))
        assert cp.x == pytest.approx(3.0)
        assert cp.y == pytest.approx(0.0)

    def test_project(self):
        line = Line2D(point=p(0, 0), direction=v(1, 0))
        t = line.project(p(5, 99))
        assert t == pytest.approx(5.0)

    def test_side_of(self):
        line = Line2D(point=p(0, 0), direction=v(1, 0))
        # Y-up: left of the eastward line is positive Y
        assert line.side_of(p(0, 1)) > 0
        assert line.side_of(p(0, -1)) < 0

    def test_intersect_crossing(self):
        line1 = Line2D(point=p(0, 0), direction=v(1, 0))
        line2 = Line2D(point=p(2, -5), direction=v(0, 1))
        pt = line1.intersect(line2)
        assert pt is not None
        assert pt.x == pytest.approx(2.0)
        assert pt.y == pytest.approx(0.0)

    def test_intersect_parallel_returns_none(self):
        line1 = Line2D(point=p(0, 0), direction=v(1, 0))
        line2 = Line2D(point=p(0, 1), direction=v(1, 0))
        assert line1.intersect(line2) is None

    def test_crs_mismatch_raises(self):
        with pytest.raises(Exception):
            Line2D(point=p(0, 0, WORLD), direction=v(1, 0, SCREEN))

    def test_parallel_offset(self):
        line = Line2D(point=p(0, 0), direction=v(1, 0))
        offset = line.parallel_offset(3.0)
        # Offset should be 3 units to the left (normal direction = +Y for eastward line)
        assert offset.distance_to_point(p(0, 3)) == pytest.approx(0.0, abs=1e-9)

    def test_parallel_offset_negative(self):
        line = Line2D(point=p(0, 0), direction=v(1, 0))
        offset = line.parallel_offset(-2.0)
        assert offset.distance_to_point(p(0, -2)) == pytest.approx(0.0, abs=1e-9)

    def test_normal(self):
        line = Line2D(point=p(0, 0), direction=v(1, 0))
        n = line.normal
        # Normal to eastward line should be northward (0, 1)
        assert n.x == pytest.approx(0.0, abs=1e-9)
        assert n.y == pytest.approx(1.0)

    def test_intersect_segment(self):
        line = Line2D(point=p(0, 0), direction=v(1, 0))
        seg = Segment2D(start=p(3, -2), end=p(3, 2))
        pt = line.intersect_segment(seg)
        assert pt is not None
        assert pt.x == pytest.approx(3.0)
        assert pt.y == pytest.approx(0.0)

    def test_as_ray(self):
        line = Line2D(point=p(1, 2), direction=v(0, 1))
        ray = line.as_ray()
        assert isinstance(ray, Ray2D)
        assert ray.origin == p(1, 2)

    def test_zero_direction_raises(self):
        with pytest.raises(ValueError):
            Line2D(point=p(0, 0), direction=v(0, 0))


# ---------------------------------------------------------------------------
# Polyline2D
# ---------------------------------------------------------------------------

class TestPolyline2D:
    def test_basic_properties(self):
        poly = Polyline2D(points=[p(0, 0), p(1, 0), p(1, 1)])
        assert len(poly) == 3
        assert poly.start_point == p(0, 0)
        assert poly.end_point == p(1, 1)
        assert poly.crs == WORLD

    def test_length(self):
        poly = Polyline2D(points=[p(0, 0), p(3, 0), p(3, 4)])
        assert poly.length == pytest.approx(7.0)

    def test_single_point_length(self):
        poly = Polyline2D(points=[p(0, 0)])
        assert poly.length == pytest.approx(0.0)

    def test_segments(self):
        poly = Polyline2D(points=[p(0, 0), p(1, 0), p(1, 1)])
        segs = poly.segments()
        assert len(segs) == 2
        assert isinstance(segs[0], Segment2D)

    def test_segment_at(self):
        poly = Polyline2D(points=[p(0, 0), p(2, 0), p(2, 2)])
        seg = poly.segment_at(1)
        assert seg.start == p(2, 0)
        assert seg.end == p(2, 2)

    def test_segment_at_out_of_range(self):
        poly = Polyline2D(points=[p(0, 0), p(1, 0)])
        with pytest.raises(IndexError):
            poly.segment_at(5)

    def test_is_closed_false(self):
        poly = Polyline2D(points=[p(0, 0), p(1, 0), p(1, 1)])
        assert not poly.is_closed

    def test_is_closed_true(self):
        poly = Polyline2D(points=[p(0, 0), p(1, 0), p(1, 1), p(0, 0)])
        assert poly.is_closed

    def test_close(self):
        poly = Polyline2D(points=[p(0, 0), p(1, 0), p(1, 1)])
        closed = poly.close()
        assert closed.is_closed
        assert len(closed) == 4
        assert closed[-1] == p(0, 0)

    def test_close_already_closed_is_noop(self):
        pts = [p(0, 0), p(1, 0), p(1, 1), p(0, 0)]
        poly = Polyline2D(points=pts)
        assert poly.close() is poly

    def test_reversed(self):
        poly = Polyline2D(points=[p(0, 0), p(1, 0), p(2, 0)])
        r = poly.reversed()
        assert r.points[0] == p(2, 0)
        assert r.points[-1] == p(0, 0)

    def test_append(self):
        poly = Polyline2D(points=[p(0, 0), p(1, 0)])
        extended = poly.append(p(2, 0))
        assert len(extended) == 3
        assert extended[-1] == p(2, 0)

    def test_append_crs_mismatch_raises(self):
        poly = Polyline2D(points=[p(0, 0), p(1, 0)])
        with pytest.raises(Exception):
            poly.append(p(2, 0, SCREEN))

    def test_crs_mismatch_in_points_raises(self):
        with pytest.raises(Exception):
            Polyline2D(points=[p(0, 0, WORLD), p(1, 0, SCREEN)])

    def test_closest_point(self):
        poly = Polyline2D(points=[p(0, 0), p(4, 0), p(4, 4)])
        cp = poly.closest_point(p(2, 2))
        # Closest is (2, 0) on the first segment
        assert cp.x == pytest.approx(2.0)
        assert cp.y == pytest.approx(0.0)

    def test_distance_to_point(self):
        poly = Polyline2D(points=[p(0, 0), p(4, 0)])
        assert poly.distance_to_point(p(2, 3)) == pytest.approx(3.0)

    def test_bbox(self):
        poly = Polyline2D(points=[p(1, 2), p(5, 3), p(3, 7)])
        bb = poly.bbox()
        assert bb.min_corner.x == pytest.approx(1.0)
        assert bb.min_corner.y == pytest.approx(2.0)
        assert bb.max_corner.x == pytest.approx(5.0)
        assert bb.max_corner.y == pytest.approx(7.0)

    def test_to_polygon(self):
        from archit_app.geometry.polygon import Polygon2D

        poly = Polyline2D(points=[p(0, 0), p(2, 0), p(2, 2), p(0, 2)])
        polygon = poly.to_polygon()
        assert isinstance(polygon, Polygon2D)
        assert polygon.area == pytest.approx(4.0)

    def test_getitem(self):
        poly = Polyline2D(points=[p(0, 0), p(1, 0), p(2, 0)])
        assert poly[1] == p(1, 0)

    def test_intersections_crossing_polylines(self):
        h = Polyline2D(points=[p(0, 1), p(4, 1)])
        v_poly = Polyline2D(points=[p(2, 0), p(2, 4)])
        pts = h.intersections(v_poly)
        assert len(pts) == 1
        assert pts[0].x == pytest.approx(2.0)
        assert pts[0].y == pytest.approx(1.0)

    def test_intersections_no_crossing(self):
        h1 = Polyline2D(points=[p(0, 0), p(4, 0)])
        h2 = Polyline2D(points=[p(0, 1), p(4, 1)])
        assert len(h1.intersections(h2)) == 0

    def test_repr(self):
        poly = Polyline2D(points=[p(0, 0), p(1, 0)])
        assert "Polyline2D" in repr(poly)
