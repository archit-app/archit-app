"""
Parametric curve types for non-Manhattan geometry.

All curves implement to_polyline(resolution) to convert to a sequence of
Point2D for use with shapely and boolean operations.

Resolution is the quality knob: higher = more accurate but slower.
"""

from __future__ import annotations

import math
from abc import abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel, model_validator

from archit_app.geometry.crs import WORLD, CoordinateSystem, require_same_crs
from archit_app.geometry.point import Point2D

if TYPE_CHECKING:
    from archit_app.geometry.polygon import Polygon2D
    from archit_app.geometry.transform import Transform2D


class CurveBase(BaseModel, frozen=True):
    """Abstract base for all curve types."""

    crs: CoordinateSystem = WORLD

    model_config = {"arbitrary_types_allowed": True}

    @abstractmethod
    def to_polyline(self, resolution: int = 32) -> tuple[Point2D, ...]:
        """Sample the curve into a sequence of points."""
        ...

    def to_polygon(self, resolution: int = 32) -> "Polygon2D":
        """Convert to a closed polygon (assumes the curve is meant to be closed)."""
        from archit_app.geometry.polygon import Polygon2D

        pts = self.to_polyline(resolution)
        return Polygon2D(exterior=pts, crs=self.crs)

    def length(self, resolution: int = 128) -> float:
        """Approximate arc length by summing polyline segment lengths."""
        pts = self.to_polyline(resolution)
        total = 0.0
        for i in range(len(pts) - 1):
            total += pts[i].distance_to(pts[i + 1])
        return total

    @abstractmethod
    def transformed(self, t: "Transform2D") -> "CurveBase":
        ...

    @property
    def start_point(self) -> Point2D:
        return self.to_polyline(2)[0]

    @property
    def end_point(self) -> Point2D:
        return self.to_polyline(2)[-1]


class ArcCurve(CurveBase):
    """
    A circular arc defined by center, radius, and angular span.

    Angles are in radians, measured from the +X axis.
    clockwise=False (default) means CCW in Y-up space.
    """

    center: Point2D
    radius: float
    start_angle: float   # radians
    end_angle: float     # radians
    clockwise: bool = False

    @model_validator(mode="after")
    def _validate(self) -> "ArcCurve":
        require_same_crs(self.crs, self.center.crs, "construct ArcCurve")
        if self.radius <= 0:
            raise ValueError(f"ArcCurve radius must be positive, got {self.radius}.")
        return self

    def to_polyline(self, resolution: int = 32) -> tuple[Point2D, ...]:
        start = self.start_angle
        end = self.end_angle

        if self.clockwise:
            if end > start:
                end -= 2 * math.pi
        else:
            if end < start:
                end += 2 * math.pi

        angles = [start + (end - start) * i / resolution for i in range(resolution + 1)]
        return tuple(
            Point2D(
                x=self.center.x + self.radius * math.cos(a),
                y=self.center.y + self.radius * math.sin(a),
                crs=self.crs,
            )
            for a in angles
        )

    @property
    def start_point(self) -> Point2D:
        return Point2D(
            x=self.center.x + self.radius * math.cos(self.start_angle),
            y=self.center.y + self.radius * math.sin(self.start_angle),
            crs=self.crs,
        )

    @property
    def end_point(self) -> Point2D:
        return Point2D(
            x=self.center.x + self.radius * math.cos(self.end_angle),
            y=self.center.y + self.radius * math.sin(self.end_angle),
            crs=self.crs,
        )

    @property
    def mid_point(self) -> Point2D:
        mid_angle = (self.start_angle + self.end_angle) / 2
        return Point2D(
            x=self.center.x + self.radius * math.cos(mid_angle),
            y=self.center.y + self.radius * math.sin(mid_angle),
            crs=self.crs,
        )

    def span_angle(self) -> float:
        """Total angular span in radians (always positive)."""
        start, end = self.start_angle, self.end_angle
        if self.clockwise:
            if end > start:
                end -= 2 * math.pi
            return abs(start - end)
        else:
            if end < start:
                end += 2 * math.pi
            return abs(end - start)

    def transformed(self, t: "Transform2D") -> "ArcCurve":
        new_center = self.center.transformed(t)
        # Scale radius by the transform's scale factor (assumes uniform scale)
        import numpy as np
        scale = math.sqrt(abs(float(np.linalg.det(t.matrix[:2, :2]))))
        return ArcCurve(
            center=new_center,
            radius=self.radius * scale,
            start_angle=self.start_angle,
            end_angle=self.end_angle,
            clockwise=self.clockwise,
            crs=self.crs,
        )


class BezierCurve(CurveBase):
    """
    Quadratic (3 control points) or cubic (4 control points) Bézier curve.
    """

    control_points: tuple[Point2D, ...]

    @model_validator(mode="after")
    def _validate(self) -> "BezierCurve":
        if len(self.control_points) not in (3, 4):
            raise ValueError(
                f"BezierCurve requires 3 (quadratic) or 4 (cubic) control points, "
                f"got {len(self.control_points)}."
            )
        for p in self.control_points:
            require_same_crs(self.crs, p.crs, "construct BezierCurve")
        return self

    @property
    def degree(self) -> int:
        return len(self.control_points) - 1

    def _evaluate(self, t: float) -> Point2D:
        """De Casteljau's algorithm."""
        pts = list(self.control_points)
        while len(pts) > 1:
            pts = [
                Point2D(
                    x=(1 - t) * pts[i].x + t * pts[i + 1].x,
                    y=(1 - t) * pts[i].y + t * pts[i + 1].y,
                    crs=self.crs,
                )
                for i in range(len(pts) - 1)
            ]
        return pts[0]

    def to_polyline(self, resolution: int = 32) -> tuple[Point2D, ...]:
        return tuple(self._evaluate(i / resolution) for i in range(resolution + 1))

    @property
    def start_point(self) -> Point2D:
        return self.control_points[0]

    @property
    def end_point(self) -> Point2D:
        return self.control_points[-1]

    def transformed(self, t: "Transform2D") -> "BezierCurve":
        new_pts = tuple(p.transformed(t) for p in self.control_points)
        return BezierCurve(control_points=new_pts, crs=self.crs)


class NURBSCurve(CurveBase):
    """
    Non-Uniform Rational B-Spline (NURBS) curve.

    Evaluation uses the de Boor algorithm in homogeneous coordinates for
    exact rational curve evaluation — no approximation, no linear fallback.

    Attributes:
        control_points: ordered sequence of 2-D control points
        weights:        one positive weight per control point (1.0 = unweighted B-spline)
        knots:          non-decreasing knot vector; must satisfy
                        ``len(knots) == len(control_points) + degree + 1``
        degree:         polynomial degree — 1 = linear, 2 = quadratic, 3 = cubic …

    For the common case of smooth curves that pass through the first and last
    control points, use the :meth:`clamped_uniform` factory.
    """

    control_points: tuple[Point2D, ...]
    weights: tuple[float, ...]
    knots: tuple[float, ...]
    degree: int = 3

    @model_validator(mode="after")
    def _validate(self) -> "NURBSCurve":
        n = len(self.control_points)
        p = self.degree
        if p < 1:
            raise ValueError(f"NURBS degree must be >= 1, got {p}.")
        if n < p + 1:
            raise ValueError(
                f"NURBS degree {p} requires at least {p + 1} control points, got {n}."
            )
        if len(self.weights) != n:
            raise ValueError(
                f"weights length ({len(self.weights)}) must equal "
                f"number of control points ({n})."
            )
        expected = n + p + 1
        if len(self.knots) != expected:
            raise ValueError(
                f"Knot vector length must be {expected} "
                f"(= {n} control points + {p} degree + 1), got {len(self.knots)}."
            )
        for i in range(len(self.knots) - 1):
            if self.knots[i] > self.knots[i + 1] + 1e-12:
                raise ValueError(
                    f"Knot vector must be non-decreasing; "
                    f"knots[{i}]={self.knots[i]} > knots[{i+1}]={self.knots[i + 1]}."
                )
        for i, w in enumerate(self.weights):
            if w <= 0:
                raise ValueError(f"All weights must be positive; weights[{i}] = {w}.")
        for pt in self.control_points:
            require_same_crs(self.crs, pt.crs, "construct NURBSCurve")
        return self

    # ------------------------------------------------------------------
    # Domain
    # ------------------------------------------------------------------

    @property
    def domain(self) -> tuple[float, float]:
        """Valid parameter range ``(t_min, t_max)`` derived from the knot vector."""
        p = self.degree
        n = len(self.control_points) - 1
        return (self.knots[p], self.knots[n + 1])

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def _find_span(self, t: float) -> int:
        """
        Return knot-span index *k* such that ``knots[k] <= t < knots[k+1]``.

        For ``t == t_max`` (the endpoint), the last non-empty interior span is
        returned so that the curve evaluates to the final control point.
        """
        p = self.degree
        n = len(self.control_points) - 1
        t_min, t_max = self.domain

        if t >= t_max:
            # Walk back past any repeated trailing knots.
            k = n
            while k > p and self.knots[k] >= t_max:
                k -= 1
            return k

        # Binary search for the span containing t.
        lo, hi = p, n + 1
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if self.knots[mid] <= t:
                lo = mid
            else:
                hi = mid
        return lo

    def _evaluate(self, t_param: float) -> Point2D:
        """
        Evaluate the NURBS curve at parameter *t_param* using the de Boor
        algorithm in homogeneous coordinates.

        The homogeneous control points ``[w·x, w·y, w]`` are recursed through
        the de Boor scheme; the result is projected back to Euclidean 2-D by
        dividing by the final homogeneous weight.
        """
        p = self.degree
        t_min, t_max = self.domain
        t = max(t_min, min(t_max, t_param))

        k = self._find_span(t)

        # Initialise de Boor array in homogeneous coordinates.
        # d[j - (k-p)] ≡ d_j^{(0)} = [w_j·x_j, w_j·y_j, w_j]
        d: list[list[float]] = []
        for j in range(k - p, k + 1):
            wi = self.weights[j]
            d.append([
                self.control_points[j].x * wi,
                self.control_points[j].y * wi,
                wi,
            ])

        offset = k - p  # maps global index j → d[j - offset]

        # de Boor recurrence — update right-to-left within each level r so
        # that d[j-1] retains its level-(r-1) value when d[j] is computed.
        for r in range(1, p + 1):
            for j in range(k, k - p + r - 1, -1):
                d_idx = j - offset
                denom = self.knots[j + p - r + 1] - self.knots[j]
                alpha = (t - self.knots[j]) / denom if abs(denom) > 1e-12 else 0.0
                for comp in range(3):
                    d[d_idx][comp] = (
                        (1.0 - alpha) * d[d_idx - 1][comp]
                        + alpha * d[d_idx][comp]
                    )

        hw = d[p][2]
        if abs(hw) < 1e-12:
            return self.control_points[k]  # degenerate — fall back to control point
        return Point2D(x=d[p][0] / hw, y=d[p][1] / hw, crs=self.crs)

    # ------------------------------------------------------------------
    # CurveBase interface
    # ------------------------------------------------------------------

    def to_polyline(self, resolution: int = 64) -> tuple[Point2D, ...]:
        """
        Sample the NURBS curve into ``resolution + 1`` evenly-spaced points.

        Uses exact Cox–de Boor evaluation — not linear interpolation.
        For clamped knot vectors the first and last returned points coincide
        with the first and last control points respectively.
        """
        if len(self.control_points) == 0:
            return ()
        t_min, t_max = self.domain
        span = t_max - t_min
        return tuple(
            self._evaluate(t_min + span * i / resolution)
            for i in range(resolution + 1)
        )

    @property
    def start_point(self) -> Point2D:
        return self._evaluate(self.domain[0])

    @property
    def end_point(self) -> Point2D:
        return self._evaluate(self.domain[1])

    def transformed(self, t: "Transform2D") -> "NURBSCurve":
        new_pts = tuple(p.transformed(t) for p in self.control_points)
        return NURBSCurve(
            control_points=new_pts,
            weights=self.weights,
            knots=self.knots,
            degree=self.degree,
            crs=self.crs,
        )

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def clamped_uniform(
        cls,
        control_points: tuple[Point2D, ...],
        degree: int = 3,
        weights: tuple[float, ...] | None = None,
        crs: CoordinateSystem = WORLD,
    ) -> "NURBSCurve":
        """
        Create a clamped NURBS with a uniform interior knot vector.

        A *clamped* knot vector has ``degree + 1`` repeated knots at each end,
        which guarantees that the curve passes through the first and last
        control points — the usual expectation for architectural curves.

        Interior knots are distributed uniformly in the open interval (0, 1).

        Args:
            control_points: at least ``degree + 1`` points
            degree:         polynomial degree (default 3 = cubic)
            weights:        one weight per control point; defaults to all 1.0
                            (giving a plain B-spline)
            crs:            coordinate system

        Example::

            pts = (
                Point2D(0, 0, crs=WORLD),
                Point2D(1, 2, crs=WORLD),
                Point2D(3, 2, crs=WORLD),
                Point2D(4, 0, crs=WORLD),
            )
            curve = NURBSCurve.clamped_uniform(pts, degree=3)
            polyline = curve.to_polyline(resolution=64)
        """
        n = len(control_points)
        if n < degree + 1:
            raise ValueError(
                f"Need at least {degree + 1} control points for degree {degree}."
            )
        if weights is None:
            weights = tuple(1.0 for _ in control_points)

        # Number of interior (free) knots = n - 1 - degree
        num_interior = n - 1 - degree
        if num_interior <= 0:
            interior: tuple[float, ...] = ()
        else:
            interior = tuple(i / (num_interior + 1) for i in range(1, num_interior + 1))

        knots: tuple[float, ...] = (
            tuple(0.0 for _ in range(degree + 1))
            + interior
            + tuple(1.0 for _ in range(degree + 1))
        )
        return cls(
            control_points=control_points,
            weights=weights,
            knots=knots,
            degree=degree,
            crs=crs,
        )
