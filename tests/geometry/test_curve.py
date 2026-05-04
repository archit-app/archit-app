"""Tests for ArcCurve and BezierCurve."""

import math

import pytest

from archit_app.geometry.crs import SCREEN, WORLD
from archit_app.geometry.curve import ArcCurve, BezierCurve
from archit_app.geometry.point import Point2D
from archit_app.geometry.transform import Transform2D

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def p(x, y, crs=WORLD):
    return Point2D(x=x, y=y, crs=crs)


def arc(cx, cy, r, start, end, *, clockwise=False):
    return ArcCurve(
        center=p(cx, cy),
        radius=r,
        start_angle=start,
        end_angle=end,
        clockwise=clockwise,
        crs=WORLD,
    )


# ===========================================================================
# ArcCurve
# ===========================================================================

class TestArcCurve:

    # ------------------------------------------------------------------
    # Construction / validation
    # ------------------------------------------------------------------

    def test_basic_construction(self):
        a = arc(0, 0, 1.0, 0, math.pi)
        assert a.radius == pytest.approx(1.0)
        assert a.crs == WORLD

    def test_negative_radius_raises(self):
        with pytest.raises(ValueError, match="radius"):
            arc(0, 0, -1.0, 0, math.pi)

    def test_zero_radius_raises(self):
        with pytest.raises(ValueError):
            arc(0, 0, 0.0, 0, math.pi)

    def test_crs_mismatch_raises(self):
        with pytest.raises(Exception):
            ArcCurve(center=p(0, 0, SCREEN), radius=1.0,
                     start_angle=0, end_angle=math.pi, crs=WORLD)

    # ------------------------------------------------------------------
    # start_point / end_point
    # ------------------------------------------------------------------

    def test_start_point_east(self):
        a = arc(0, 0, 2.0, 0, math.pi / 2)
        sp = a.start_point
        assert sp.x == pytest.approx(2.0)
        assert sp.y == pytest.approx(0.0, abs=1e-9)

    def test_end_point_north(self):
        a = arc(0, 0, 2.0, 0, math.pi / 2)
        ep = a.end_point
        assert ep.x == pytest.approx(0.0, abs=1e-9)
        assert ep.y == pytest.approx(2.0)

    def test_start_point_with_offset_center(self):
        a = arc(1, 1, 1.0, 0, math.pi)
        sp = a.start_point
        assert sp.x == pytest.approx(2.0)
        assert sp.y == pytest.approx(1.0)

    def test_mid_point(self):
        # Quarter arc from 0 to π/2; midpoint at π/4
        a = arc(0, 0, 1.0, 0, math.pi / 2)
        mp = a.mid_point
        assert mp.x == pytest.approx(math.cos(math.pi / 4))
        assert mp.y == pytest.approx(math.sin(math.pi / 4))

    # ------------------------------------------------------------------
    # span_angle
    # ------------------------------------------------------------------

    def test_span_angle_quarter(self):
        a = arc(0, 0, 1.0, 0, math.pi / 2)
        assert a.span_angle() == pytest.approx(math.pi / 2)

    def test_span_angle_full_circle(self):
        a = arc(0, 0, 1.0, 0, 2 * math.pi)
        assert a.span_angle() == pytest.approx(2 * math.pi)

    def test_span_angle_wrap_around(self):
        # CCW arc from 3π/2 to π/2 (wraps through 0) = π
        a = arc(0, 0, 1.0, 3 * math.pi / 2, math.pi / 2)
        assert a.span_angle() == pytest.approx(math.pi)

    def test_span_angle_clockwise(self):
        a = arc(0, 0, 1.0, math.pi / 2, 0, clockwise=True)
        assert a.span_angle() == pytest.approx(math.pi / 2)

    # ------------------------------------------------------------------
    # to_polyline
    # ------------------------------------------------------------------

    def test_to_polyline_count(self):
        a = arc(0, 0, 1.0, 0, math.pi)
        pts = a.to_polyline(16)
        assert len(pts) == 17   # resolution + 1

    def test_to_polyline_on_circle(self):
        a = arc(0, 0, 1.0, 0, 2 * math.pi)
        for pt in a.to_polyline(64):
            r = math.sqrt(pt.x ** 2 + pt.y ** 2)
            assert r == pytest.approx(1.0, rel=1e-9)

    def test_to_polyline_endpoints_match(self):
        a = arc(0, 0, 1.0, 0, math.pi / 2)
        pts = a.to_polyline(32)
        assert pts[0].x == pytest.approx(a.start_point.x)
        assert pts[-1].y == pytest.approx(a.end_point.y)

    # ------------------------------------------------------------------
    # length
    # ------------------------------------------------------------------

    def test_length_semicircle(self):
        # Semicircle r=1 → arc length = π
        a = arc(0, 0, 1.0, 0, math.pi)
        assert a.length(128) == pytest.approx(math.pi, rel=1e-3)

    def test_length_full_circle(self):
        a = arc(0, 0, 1.0, 0, 2 * math.pi)
        assert a.length(256) == pytest.approx(2 * math.pi, rel=1e-3)

    def test_length_quarter_circle(self):
        a = arc(0, 0, 2.0, 0, math.pi / 2)
        assert a.length(128) == pytest.approx(math.pi, rel=1e-3)

    # ------------------------------------------------------------------
    # transformed
    # ------------------------------------------------------------------

    def test_transformed_translate(self):
        a = arc(0, 0, 1.0, 0, math.pi)
        t = Transform2D.translate(3, 4)
        ta = a.transformed(t)
        assert ta.center.x == pytest.approx(3.0)
        assert ta.center.y == pytest.approx(4.0)
        assert ta.radius == pytest.approx(1.0)  # translation doesn't scale radius

    def test_transformed_scale(self):
        a = arc(0, 0, 1.0, 0, math.pi)
        t = Transform2D.scale(2, 2)
        ta = a.transformed(t)
        assert ta.radius == pytest.approx(2.0)

    def test_transformed_preserves_angles(self):
        a = arc(0, 0, 1.0, 0, math.pi / 2)
        t = Transform2D.translate(5, 0)
        ta = a.transformed(t)
        assert ta.start_angle == pytest.approx(a.start_angle)
        assert ta.end_angle == pytest.approx(a.end_angle)

    def test_transformed_crs_preserved(self):
        a = arc(0, 0, 1.0, 0, math.pi)
        ta = a.transformed(Transform2D.identity())
        assert ta.crs == WORLD


# ===========================================================================
# BezierCurve
# ===========================================================================

class TestBezierCurve:

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def test_requires_3_or_4_points(self):
        with pytest.raises(ValueError, match="3.*4"):
            BezierCurve(control_points=(p(0,0), p(1,0)))  # 2 points

    def test_five_points_raises(self):
        with pytest.raises(ValueError):
            BezierCurve(control_points=tuple(p(i, 0) for i in range(5)))

    def test_crs_mismatch_raises(self):
        with pytest.raises(Exception):
            BezierCurve(control_points=(p(0, 0, WORLD), p(1, 0, SCREEN), p(2, 0, WORLD)))

    # ------------------------------------------------------------------
    # Quadratic (degree 2, 3 control points)
    # ------------------------------------------------------------------

    def _quad(self):
        return BezierCurve(
            control_points=(p(0, 0), p(1, 2), p(2, 0)),
            crs=WORLD,
        )

    def test_quadratic_degree(self):
        assert self._quad().degree == 2

    def test_quadratic_start_point(self):
        sp = self._quad().start_point
        assert sp.x == pytest.approx(0.0)
        assert sp.y == pytest.approx(0.0)

    def test_quadratic_end_point(self):
        ep = self._quad().end_point
        assert ep.x == pytest.approx(2.0)
        assert ep.y == pytest.approx(0.0)

    def test_quadratic_midpoint_on_curve(self):
        q = self._quad()
        # At t=0.5 the quadratic Bezier midpoint is:
        # (1-0.5)²·P0 + 2·(1-0.5)·0.5·P1 + 0.5²·P2
        # = 0.25·(0,0) + 0.5·(1,2) + 0.25·(2,0) = (0+0.5+0.5, 0+1+0) = (1, 1)
        mid = q._evaluate(0.5)
        assert mid.x == pytest.approx(1.0)
        assert mid.y == pytest.approx(1.0)

    def test_quadratic_polyline_count(self):
        pts = self._quad().to_polyline(16)
        assert len(pts) == 17

    def test_quadratic_polyline_endpoints(self):
        q = self._quad()
        pts = q.to_polyline(32)
        assert pts[0].x == pytest.approx(0.0)
        assert pts[-1].x == pytest.approx(2.0)

    def test_quadratic_length_positive(self):
        assert self._quad().length(64) > 0

    def test_quadratic_length_less_than_control_polygon(self):
        q = self._quad()
        # Bézier curve is contained within convex hull → shorter than polygon
        ctrl_len = (
            p(0, 0).distance_to(p(1, 2))
            + p(1, 2).distance_to(p(2, 0))
        )
        assert q.length(64) < ctrl_len

    # ------------------------------------------------------------------
    # Cubic (degree 3, 4 control points)
    # ------------------------------------------------------------------

    def _cubic(self):
        return BezierCurve(
            control_points=(p(0, 0), p(1, 3), p(2, 3), p(3, 0)),
            crs=WORLD,
        )

    def test_cubic_degree(self):
        assert self._cubic().degree == 3

    def test_cubic_start_end(self):
        c = self._cubic()
        assert c.start_point == p(0, 0)
        assert c.end_point == p(3, 0)

    def test_cubic_at_t0(self):
        # t=0 → first control point
        assert self._cubic()._evaluate(0.0) == p(0, 0)

    def test_cubic_at_t1(self):
        # t=1 → last control point
        ep = self._cubic()._evaluate(1.0)
        assert ep.x == pytest.approx(3.0)
        assert ep.y == pytest.approx(0.0)

    def test_cubic_midpoint_symmetric(self):
        # Symmetric cubic: midpoint should be at x=1.5
        c = self._cubic()
        mid = c._evaluate(0.5)
        assert mid.x == pytest.approx(1.5)

    def test_cubic_polyline_count(self):
        assert len(self._cubic().to_polyline(8)) == 9

    # ------------------------------------------------------------------
    # transformed
    # ------------------------------------------------------------------

    def test_transformed_translate(self):
        q = self._quad()
        t = Transform2D.translate(10, 5)
        tq = q.transformed(t)
        assert tq.control_points[0].x == pytest.approx(10.0)
        assert tq.control_points[0].y == pytest.approx(5.0)

    def test_transformed_scale(self):
        q = self._quad()
        t = Transform2D.scale(2, 2)
        tq = q.transformed(t)
        assert tq.control_points[-1].x == pytest.approx(4.0)

    def test_transformed_count_preserved(self):
        q = self._quad()
        tq = q.transformed(Transform2D.identity())
        assert len(tq.control_points) == len(q.control_points)

    def test_transformed_cubic(self):
        c = self._cubic()
        t = Transform2D.translate(1, 0)
        tc = c.transformed(t)
        assert tc.start_point.x == pytest.approx(1.0)
        assert tc.end_point.x == pytest.approx(4.0)

    def test_transformed_crs_preserved(self):
        q = self._quad()
        tq = q.transformed(Transform2D.identity())
        assert tq.crs == WORLD

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def test_frozen(self):
        q = self._quad()
        with pytest.raises(Exception):
            q.crs = SCREEN  # type: ignore
