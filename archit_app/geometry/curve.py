"""
Parametric curve types for non-Manhattan geometry.

All curves implement to_polyline(resolution) to convert to a sequence of
Point2D for use with shapely and boolean operations.

Resolution is the quality knob: higher = more accurate but slower.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel, field_validator, model_validator

from archit_app.geometry.crs import CoordinateSystem, WORLD, require_same_crs
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
    Non-Uniform Rational B-Spline curve.

    Stub implementation for v0.1 — to_polyline falls back to linear interpolation
    between control points until a full NURBS evaluator is implemented.
    """

    control_points: tuple[Point2D, ...]
    weights: tuple[float, ...]
    knots: tuple[float, ...]
    degree: int = 3

    @model_validator(mode="after")
    def _validate(self) -> "NURBSCurve":
        if len(self.weights) != len(self.control_points):
            raise ValueError("weights must have same length as control_points.")
        for p in self.control_points:
            require_same_crs(self.crs, p.crs, "construct NURBSCurve")
        return self

    def to_polyline(self, resolution: int = 64) -> tuple[Point2D, ...]:
        # Stub: linear interpolation between control points
        # TODO: implement proper NURBS evaluation in a future release
        pts = self.control_points
        if len(pts) == 0:
            return ()
        if len(pts) == 1:
            return pts

        result = []
        n = len(pts) - 1
        for i in range(resolution + 1):
            t = i / resolution
            seg_t = t * n
            seg_idx = min(int(seg_t), n - 1)
            local_t = seg_t - seg_idx
            p0 = pts[seg_idx]
            p1 = pts[seg_idx + 1]
            result.append(
                Point2D(
                    x=(1 - local_t) * p0.x + local_t * p1.x,
                    y=(1 - local_t) * p0.y + local_t * p1.y,
                    crs=self.crs,
                )
            )
        return tuple(result)

    def transformed(self, t: "Transform2D") -> "NURBSCurve":
        new_pts = tuple(p.transformed(t) for p in self.control_points)
        return NURBSCurve(
            control_points=new_pts,
            weights=self.weights,
            knots=self.knots,
            degree=self.degree,
            crs=self.crs,
        )
