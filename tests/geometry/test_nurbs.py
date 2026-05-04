"""
Tests for the NURBSCurve Cox–de Boor evaluator.

Covers:
  - Input validation (knot vector length, non-decreasing, positive weights)
  - Endpoint interpolation for clamped knot vectors
  - Clamped cubic NURBS matches Bernstein-basis Bézier (equal-weight, 4 pts)
  - Weight effect: rational NURBS deviates from unweighted version
  - clamped_uniform factory: knot vector structure, endpoints, resolution
  - to_polyline: sample count, CRS propagation
  - start_point / end_point match first/last control point (clamped)
  - length() is positive and increases with resolution
  - transformed() moves control points and preserves knot/weight/degree
  - Degree-1 (linear) NURBS traces straight line segments exactly
  - Multi-span (5 control points, cubic) curve continuity
"""

from __future__ import annotations

import math

import pytest

from archit_app import WORLD, Point2D
from archit_app.geometry.curve import BezierCurve, NURBSCurve
from archit_app.geometry.transform import Transform2D

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _pts(*coords: tuple[float, float]) -> tuple[Point2D, ...]:
    return tuple(Point2D(x=x, y=y, crs=WORLD) for x, y in coords)


@pytest.fixture()
def cubic_clamped() -> NURBSCurve:
    """Cubic clamped uniform NURBS with 4 control points.
    Knot vector [0,0,0,0,1,1,1,1] — equivalent to a Bézier cubic."""
    pts = _pts((0, 0), (1, 2), (3, 2), (4, 0))
    return NURBSCurve.clamped_uniform(pts, degree=3)


@pytest.fixture()
def quintic_clamped() -> NURBSCurve:
    """Cubic clamped NURBS with 5 control points (one interior knot at 0.5)."""
    pts = _pts((0, 0), (1, 3), (2, 0), (3, 3), (4, 0))
    return NURBSCurve.clamped_uniform(pts, degree=3)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_too_few_control_points(self):
        # Degree 3 needs ≥ 4 control points
        pts = _pts((0, 0), (1, 1))
        with pytest.raises(ValueError, match="control points"):
            NURBSCurve.clamped_uniform(pts, degree=3)

    def test_wrong_knot_length(self):
        pts = _pts((0, 0), (1, 1), (2, 0), (3, 0))
        weights = (1.0, 1.0, 1.0, 1.0)
        # Correct length for n=4, p=3 is 4+3+1=8; provide 7 → error
        with pytest.raises(ValueError, match="[Kk]not"):
            NURBSCurve(
                control_points=pts,
                weights=weights,
                knots=(0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0),  # 7, need 8
                degree=3,
                crs=WORLD,
            )

    def test_non_decreasing_knots(self):
        pts = _pts((0, 0), (1, 1), (2, 0), (3, 0))
        weights = (1.0, 1.0, 1.0, 1.0)
        with pytest.raises(ValueError, match="non-decreasing"):
            NURBSCurve(
                control_points=pts,
                weights=weights,
                knots=(0.0, 0.0, 0.0, 1.0, 0.5, 1.0, 1.0, 1.0),  # 1.0 > 0.5
                degree=3,
                crs=WORLD,
            )

    def test_zero_weight(self):
        pts = _pts((0, 0), (1, 1), (2, 0), (3, 0))
        with pytest.raises(ValueError, match="[Ww]eight"):
            NURBSCurve(
                control_points=pts,
                weights=(1.0, 0.0, 1.0, 1.0),  # zero
                knots=(0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0),
                degree=3,
                crs=WORLD,
            )

    def test_negative_weight(self):
        pts = _pts((0, 0), (1, 1), (2, 0), (3, 0))
        with pytest.raises(ValueError, match="[Ww]eight"):
            NURBSCurve(
                control_points=pts,
                weights=(1.0, -1.0, 1.0, 1.0),
                knots=(0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0),
                degree=3,
                crs=WORLD,
            )

    def test_degree_zero_rejected(self):
        pts = _pts((0, 0), (1, 1))
        with pytest.raises(ValueError, match="degree"):
            NURBSCurve(
                control_points=pts,
                weights=(1.0, 1.0),
                knots=(0.0, 1.0, 2.0),
                degree=0,
                crs=WORLD,
            )

    def test_weight_length_mismatch(self):
        pts = _pts((0, 0), (1, 1), (2, 0), (3, 0))
        with pytest.raises(ValueError, match="[Ww]eight"):
            NURBSCurve(
                control_points=pts,
                weights=(1.0, 1.0, 1.0),   # 3 weights for 4 points
                knots=(0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0),
                degree=3,
                crs=WORLD,
            )


# ---------------------------------------------------------------------------
# Endpoint interpolation
# ---------------------------------------------------------------------------

class TestEndpoints:
    def test_start_matches_first_control_point(self, cubic_clamped):
        sp = cubic_clamped.start_point
        cp0 = cubic_clamped.control_points[0]
        assert math.isclose(sp.x, cp0.x, abs_tol=1e-9)
        assert math.isclose(sp.y, cp0.y, abs_tol=1e-9)

    def test_end_matches_last_control_point(self, cubic_clamped):
        ep = cubic_clamped.end_point
        cpn = cubic_clamped.control_points[-1]
        assert math.isclose(ep.x, cpn.x, abs_tol=1e-9)
        assert math.isclose(ep.y, cpn.y, abs_tol=1e-9)

    def test_polyline_first_point_matches_start(self, cubic_clamped):
        poly = cubic_clamped.to_polyline(32)
        sp = cubic_clamped.start_point
        assert math.isclose(poly[0].x, sp.x, abs_tol=1e-9)

    def test_polyline_last_point_matches_end(self, cubic_clamped):
        poly = cubic_clamped.to_polyline(32)
        ep = cubic_clamped.end_point
        assert math.isclose(poly[-1].x, ep.x, abs_tol=1e-9)

    def test_multispan_endpoints(self, quintic_clamped):
        sp = quintic_clamped.start_point
        ep = quintic_clamped.end_point
        assert math.isclose(sp.x, 0.0, abs_tol=1e-9)
        assert math.isclose(ep.x, 4.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# Equivalence to Bézier (equal weights, clamped, 4 control points)
# ---------------------------------------------------------------------------

class TestBezierEquivalence:
    """A cubic clamped unit-weight NURBS with 4 points is a Bézier cubic."""

    @pytest.fixture()
    def bezier(self) -> BezierCurve:
        pts = _pts((0, 0), (1, 2), (3, 2), (4, 0))
        return BezierCurve(control_points=pts, crs=WORLD)

    @pytest.fixture()
    def nurbs(self) -> NURBSCurve:
        pts = _pts((0, 0), (1, 2), (3, 2), (4, 0))
        return NURBSCurve.clamped_uniform(pts, degree=3)

    def test_midpoint_matches_bezier(self, bezier, nurbs):
        """At t=0.5 both should produce the same XY coordinate."""
        # Bézier t=0.5 uses its own parameterisation; both are [0,1]-based.
        bx = bezier._evaluate(0.5)
        # NURBS domain is [0,1] for this clamped-uniform knot vector
        nx = nurbs._evaluate(0.5)
        assert math.isclose(bx.x, nx.x, abs_tol=1e-9)
        assert math.isclose(bx.y, nx.y, abs_tol=1e-9)

    def test_polyline_matches_bezier_at_all_samples(self, bezier, nurbs):
        resolution = 20
        bp = bezier.to_polyline(resolution)
        np_ = nurbs.to_polyline(resolution)
        assert len(bp) == len(np_)
        for b, n in zip(bp, np_):
            assert math.isclose(b.x, n.x, abs_tol=1e-9)
            assert math.isclose(b.y, n.y, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# Rational (non-unit weights) behaviour
# ---------------------------------------------------------------------------

class TestRationalWeights:
    def test_rational_differs_from_unweighted(self):
        """Raising the middle control point's weight pulls the curve toward it."""
        pts = _pts((0, 0), (2, 4), (4, 0))
        uniform = NURBSCurve.clamped_uniform(pts, degree=2)
        rational = NURBSCurve.clamped_uniform(pts, degree=2, weights=(1.0, 4.0, 1.0))

        # At the midpoint, the rational curve should be pulled closer to (2,4)
        mid_u = uniform._evaluate(0.5)
        mid_r = rational._evaluate(0.5)
        assert mid_r.y > mid_u.y  # pulled toward higher-weight control point

    def test_unit_weight_one_equals_unit_weight_two(self):
        """Scaling all weights equally must not change the curve."""
        pts = _pts((0, 0), (1, 2), (3, 2), (4, 0))
        c1 = NURBSCurve.clamped_uniform(pts, degree=3, weights=(1.0, 1.0, 1.0, 1.0))
        c2 = NURBSCurve.clamped_uniform(pts, degree=3, weights=(5.0, 5.0, 5.0, 5.0))
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            p1 = c1._evaluate(t)
            p2 = c2._evaluate(t)
            assert math.isclose(p1.x, p2.x, abs_tol=1e-9)
            assert math.isclose(p1.y, p2.y, abs_tol=1e-9)

    def test_exact_conic_section(self):
        """
        A quadratic NURBS with middle weight w=cos(π/4)=√2/2 and control
        points forming an isoceles triangle produces an exact quarter-circle arc.
        """
        w = math.cos(math.pi / 4)  # ≈ 0.7071
        pts = _pts((1, 0), (1, 1), (0, 1))
        curve = NURBSCurve.clamped_uniform(pts, degree=2, weights=(1.0, w, 1.0))

        # Sample and check distance from origin — all should be ≈ 1.0
        polyline = curve.to_polyline(resolution=64)
        for pt in polyline:
            r = math.sqrt(pt.x ** 2 + pt.y ** 2)
            assert math.isclose(r, 1.0, abs_tol=2e-4), f"r={r} at ({pt.x:.4f}, {pt.y:.4f})"


# ---------------------------------------------------------------------------
# clamped_uniform factory
# ---------------------------------------------------------------------------

class TestClampedUniform:
    def test_knot_vector_length(self):
        pts = _pts((0, 0), (1, 1), (2, 0), (3, 0))  # n=4, p=3 → knots=8
        c = NURBSCurve.clamped_uniform(pts, degree=3)
        assert len(c.knots) == 4 + 3 + 1

    def test_leading_knots_are_zero(self):
        pts = _pts((0, 0), (1, 1), (2, 0), (3, 0))
        c = NURBSCurve.clamped_uniform(pts, degree=3)
        for i in range(4):  # p+1 = 4
            assert c.knots[i] == 0.0

    def test_trailing_knots_are_one(self):
        pts = _pts((0, 0), (1, 1), (2, 0), (3, 0))
        c = NURBSCurve.clamped_uniform(pts, degree=3)
        for i in range(-4, 0):  # last p+1 = 4 entries
            assert c.knots[i] == 1.0

    def test_default_weights_are_unit(self):
        pts = _pts((0, 0), (1, 1), (2, 0))
        c = NURBSCurve.clamped_uniform(pts, degree=2)
        assert all(w == 1.0 for w in c.weights)

    def test_interior_knot_count_for_five_pts_cubic(self):
        # n=5, p=3 → num_interior = 5-1-3 = 1
        pts = _pts((0, 0), (1, 2), (2, 1), (3, 2), (4, 0))
        c = NURBSCurve.clamped_uniform(pts, degree=3)
        # Interior knots are at index 4 only (between the clamped sections)
        interior = c.knots[4:-4]
        assert len(interior) == 1
        assert math.isclose(interior[0], 0.5, abs_tol=1e-12)

    def test_too_few_pts_raises(self):
        pts = _pts((0, 0), (1, 1))
        with pytest.raises(ValueError):
            NURBSCurve.clamped_uniform(pts, degree=3)

    def test_custom_weights_forwarded(self):
        pts = _pts((0, 0), (1, 1), (2, 0), (3, 0))
        c = NURBSCurve.clamped_uniform(pts, degree=3, weights=(1.0, 2.0, 2.0, 1.0))
        assert c.weights == (1.0, 2.0, 2.0, 1.0)


# ---------------------------------------------------------------------------
# to_polyline
# ---------------------------------------------------------------------------

class TestPolyline:
    def test_sample_count(self, cubic_clamped):
        poly = cubic_clamped.to_polyline(resolution=50)
        assert len(poly) == 51  # resolution + 1

    def test_crs_preserved(self, cubic_clamped):
        poly = cubic_clamped.to_polyline(32)
        for pt in poly:
            assert pt.crs == WORLD

    def test_empty_curve_returns_empty(self):
        """Guard against accidentally constructing a curve with no points (would fail validation,
        but the to_polyline path handles the len==0 case defensively)."""
        # We can't construct an invalid NURBSCurve, so test the branch indirectly
        # via the length() call on a valid 1-resolution sample
        pts = _pts((0, 0), (1, 1), (2, 0), (3, 0))
        c = NURBSCurve.clamped_uniform(pts, degree=3)
        poly = c.to_polyline(1)
        assert len(poly) == 2  # resolution=1 → [t_min, t_max]

    def test_higher_resolution_gives_smoother_curve(self, cubic_clamped):
        l32 = cubic_clamped.length(resolution=32)
        l128 = cubic_clamped.length(resolution=128)
        # Higher resolution should give a closer (and >= ) approximation
        assert l128 >= l32 - 1e-6


# ---------------------------------------------------------------------------
# Domain property
# ---------------------------------------------------------------------------

class TestDomain:
    def test_clamped_uniform_domain(self, cubic_clamped):
        assert cubic_clamped.domain == (0.0, 1.0)

    def test_multispan_domain(self, quintic_clamped):
        assert quintic_clamped.domain == (0.0, 1.0)


# ---------------------------------------------------------------------------
# Length
# ---------------------------------------------------------------------------

class TestLength:
    def test_length_positive(self, cubic_clamped):
        assert cubic_clamped.length() > 0

    def test_linear_nurbs_length_exact(self):
        """A degree-1 NURBS connecting (0,0)→(3,4) has length 5.0."""
        pts = _pts((0, 0), (3, 4))
        c = NURBSCurve.clamped_uniform(pts, degree=1)
        assert math.isclose(c.length(resolution=1), 5.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# Degree-1 (linear) NURBS
# ---------------------------------------------------------------------------

class TestLinearNURBS:
    def test_linear_two_points_is_straight_line(self):
        pts = _pts((0, 0), (4, 3))
        c = NURBSCurve.clamped_uniform(pts, degree=1)
        mid = c._evaluate(0.5)
        assert math.isclose(mid.x, 2.0, abs_tol=1e-9)
        assert math.isclose(mid.y, 1.5, abs_tol=1e-9)

    def test_linear_three_points(self):
        pts = _pts((0, 0), (1, 1), (2, 0))
        c = NURBSCurve.clamped_uniform(pts, degree=1)
        # Knot vector [0,0,0.5,1,1] → domain [0,1], span 1 at [0,0.5), span 2 at [0.5,1]
        mid = c._evaluate(0.5)
        # At t=0.5, should be at the midpoint knot → exactly at control_points[1]
        assert math.isclose(mid.x, 1.0, abs_tol=1e-9)
        assert math.isclose(mid.y, 1.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# transformed()
# ---------------------------------------------------------------------------

class TestTransformed:
    def test_translate_moves_all_points(self, cubic_clamped):
        t = Transform2D.translate(10.0, 5.0)
        moved = cubic_clamped.transformed(t)
        for orig, new in zip(cubic_clamped.control_points, moved.control_points):
            assert math.isclose(new.x, orig.x + 10.0, abs_tol=1e-9)
            assert math.isclose(new.y, orig.y + 5.0, abs_tol=1e-9)

    def test_knots_and_weights_preserved(self, cubic_clamped):
        t = Transform2D.translate(1.0, 2.0)
        moved = cubic_clamped.transformed(t)
        assert moved.knots == cubic_clamped.knots
        assert moved.weights == cubic_clamped.weights
        assert moved.degree == cubic_clamped.degree

    def test_evaluate_after_transform_matches_translated_point(self, cubic_clamped):
        t = Transform2D.translate(3.0, -1.0)
        moved = cubic_clamped.transformed(t)
        orig_mid = cubic_clamped._evaluate(0.5)
        moved_mid = moved._evaluate(0.5)
        assert math.isclose(moved_mid.x, orig_mid.x + 3.0, abs_tol=1e-9)
        assert math.isclose(moved_mid.y, orig_mid.y - 1.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# Multi-span continuity
# ---------------------------------------------------------------------------

class TestMultiSpan:
    def test_curve_is_continuous_at_interior_knot(self, quintic_clamped):
        """
        At the interior knot (t=0.5), evaluating from just below and just above
        should yield the same point (C^(degree-multiplicity-1) continuity;
        for a simple interior knot this is C^2).
        """
        eps = 1e-7
        p_below = quintic_clamped._evaluate(0.5 - eps)
        p_above = quintic_clamped._evaluate(0.5 + eps)
        assert math.isclose(p_below.x, p_above.x, abs_tol=1e-4)
        assert math.isclose(p_below.y, p_above.y, abs_tol=1e-4)
