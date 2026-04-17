"""
Linear geometry primitives: Segment2D, Ray2D, Line2D, and Polyline2D.

Segment2D  — a finite directed line segment between two Point2D endpoints.
Ray2D      — a half-line from an origin in a given direction (extends to ∞).
Line2D     — an infinite line defined by a point and a direction.
Polyline2D — an ordered sequence of Point2D forming connected segments.

All types are immutable Pydantic models that carry a CRS and support the
standard geometry API (transformed, distance_to_point, closest_point, …).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pydantic import BaseModel, field_validator, model_validator

from archit_app.geometry.crs import CoordinateSystem, WORLD, require_same_crs
from archit_app.geometry.point import Point2D
from archit_app.geometry.vector import Vector2D

if TYPE_CHECKING:
    from archit_app.geometry.bbox import BoundingBox2D
    from archit_app.geometry.polygon import Polygon2D
    from archit_app.geometry.transform import Transform2D

_EPS = 1e-10


# ---------------------------------------------------------------------------
# Segment2D
# ---------------------------------------------------------------------------

class Segment2D(BaseModel, frozen=True):
    """
    A finite, directed line segment from *start* to *end*.

    Both endpoints must share the same CRS.  The segment carries that CRS
    as its own ``crs`` attribute so callers never have to inspect endpoints.
    """

    start: Point2D
    end: Point2D

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def _crs_match(self) -> "Segment2D":
        require_same_crs(self.start.crs, self.end.crs, "Segment2D endpoints")
        return self

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def crs(self) -> CoordinateSystem:
        return self.start.crs

    @property
    def length(self) -> float:
        return self.start.distance_to(self.end)

    @property
    def direction(self) -> Vector2D:
        """Unit vector from *start* to *end*. Raises if segment has zero length."""
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        mag = math.sqrt(dx * dx + dy * dy)
        if mag < _EPS:
            raise ValueError("Segment has zero length — direction is undefined.")
        return Vector2D(x=dx / mag, y=dy / mag, crs=self.crs)

    @property
    def midpoint(self) -> Point2D:
        return self.start.midpoint(self.end)

    @property
    def vector(self) -> Vector2D:
        """Un-normalised displacement vector from *start* to *end*."""
        return Vector2D(
            x=self.end.x - self.start.x,
            y=self.end.y - self.start.y,
            crs=self.crs,
        )

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def at(self, t: float) -> Point2D:
        """
        Interpolate along the segment.

        ``t=0`` → *start*, ``t=1`` → *end*.
        Values outside [0, 1] extrapolate beyond the endpoints.
        """
        return Point2D(
            x=self.start.x + t * (self.end.x - self.start.x),
            y=self.start.y + t * (self.end.y - self.start.y),
            crs=self.crs,
        )

    def parameter_of(self, p: Point2D) -> float:
        """
        Return the scalar parameter *t* such that ``self.at(t)`` is the
        foot of the perpendicular from *p* onto the (infinite) line through
        this segment.  Clamp to [0, 1] to stay within the segment.
        """
        require_same_crs(self.crs, p.crs, "parameter_of")
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        denom = dx * dx + dy * dy
        if denom < _EPS:
            return 0.0
        t = ((p.x - self.start.x) * dx + (p.y - self.start.y) * dy) / denom
        return max(0.0, min(1.0, t))

    def closest_point(self, p: Point2D) -> Point2D:
        """Return the point on the segment closest to *p*."""
        return self.at(self.parameter_of(p))

    def distance_to_point(self, p: Point2D) -> float:
        """Minimum distance from *p* to this segment."""
        return p.distance_to(self.closest_point(p))

    def intersect(self, other: "Segment2D") -> "Point2D | None":
        """
        Return the intersection point of this segment and *other*, or
        ``None`` if they are parallel or do not intersect within their
        finite extents.

        Uses the classic parametric segment-segment test.
        """
        require_same_crs(self.crs, other.crs, "intersect")
        x1, y1 = self.start.x, self.start.y
        x2, y2 = self.end.x, self.end.y
        x3, y3 = other.start.x, other.start.y
        x4, y4 = other.end.x, other.end.y

        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < _EPS:
            return None  # parallel or collinear

        t_num = (x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)
        u_num = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3))

        t = t_num / denom
        u = u_num / denom

        if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
            return self.at(t)
        return None

    def reversed(self) -> "Segment2D":
        """Return a new segment with *start* and *end* swapped."""
        return Segment2D(start=self.end, end=self.start)

    def transformed(self, t: "Transform2D") -> "Segment2D":
        return Segment2D(
            start=self.start.transformed(t),
            end=self.end.transformed(t),
        )

    def as_polyline(self) -> "Polyline2D":
        """Wrap this segment in a two-point :class:`Polyline2D`."""
        return Polyline2D(points=(self.start, self.end))

    def as_line(self) -> "Line2D":
        """Return the infinite line that contains this segment."""
        return Line2D(point=self.start, direction=self.direction)

    def __repr__(self) -> str:
        return (
            f"Segment2D(start={self.start!r}, end={self.end!r}, "
            f"length={self.length:.4f})"
        )


# ---------------------------------------------------------------------------
# Ray2D
# ---------------------------------------------------------------------------

class Ray2D(BaseModel, frozen=True):
    """
    A half-line starting at *origin* and extending in *direction* to infinity.

    *direction* is normalised on construction.
    """

    origin: Point2D
    direction: Vector2D

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def _normalise_direction(self) -> "Ray2D":
        require_same_crs(self.origin.crs, self.direction.crs, "Ray2D")
        if self.direction.magnitude < _EPS:
            raise ValueError("Ray2D direction must be non-zero.")
        return self

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def crs(self) -> CoordinateSystem:
        return self.origin.crs

    @property
    def unit_direction(self) -> Vector2D:
        """Return the normalised direction vector."""
        return self.direction.normalized()

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def at(self, t: float) -> Point2D:
        """
        Return the point at parameter *t* along the ray.

        ``t=0`` → *origin*; ``t > 0`` → forward; ``t < 0`` is behind the
        origin (still computed but represents the extension behind the ray).
        """
        d = self.unit_direction
        return Point2D(
            x=self.origin.x + t * d.x,
            y=self.origin.y + t * d.y,
            crs=self.crs,
        )

    def intersect_segment(self, seg: Segment2D) -> "Point2D | None":
        """
        Return the intersection of this ray with *seg*, or ``None``.

        The intersection must lie on the ray's forward direction (t ≥ 0) and
        within the finite extent of *seg*.
        """
        require_same_crs(self.crs, seg.crs, "intersect_segment")
        ox, oy = self.origin.x, self.origin.y
        d = self.unit_direction
        dx, dy = d.x, d.y

        x3, y3 = seg.start.x, seg.start.y
        x4, y4 = seg.end.x, seg.end.y

        denom = dx * (y4 - y3) - dy * (x4 - x3)
        if abs(denom) < _EPS:
            return None

        t = ((x3 - ox) * (y4 - y3) - (y3 - oy) * (x4 - x3)) / denom
        u_num = (x3 - ox) * dy - (y3 - oy) * dx
        u = u_num / denom

        if t >= -_EPS and 0.0 <= u <= 1.0:
            return self.at(max(0.0, t))
        return None

    def intersect_line(self, line: "Line2D") -> "Point2D | None":
        """Return the intersection with an infinite *line*, or ``None``."""
        require_same_crs(self.crs, line.crs, "intersect_line")
        # Use segment of large length to represent the line
        far = 1e9
        seg = Segment2D(start=line.at(-far), end=line.at(far))
        return self.intersect_segment(seg)

    def to_segment(self, length: float) -> Segment2D:
        """Return a finite segment of *length* starting at the origin."""
        return Segment2D(start=self.origin, end=self.at(length))

    def transformed(self, t: "Transform2D") -> "Ray2D":
        new_origin = self.origin.transformed(t)
        end = self.at(1.0).transformed(t)
        new_dir = Vector2D(
            x=end.x - new_origin.x,
            y=end.y - new_origin.y,
            crs=self.crs,
        )
        return Ray2D(origin=new_origin, direction=new_dir)

    def __repr__(self) -> str:
        d = self.unit_direction
        return (
            f"Ray2D(origin={self.origin!r}, "
            f"direction=({d.x:.4f}, {d.y:.4f}))"
        )


# ---------------------------------------------------------------------------
# Line2D
# ---------------------------------------------------------------------------

class Line2D(BaseModel, frozen=True):
    """
    An infinite line defined by a *point* on the line and a *direction*.

    *direction* does not need to be normalised — it is stored as-is but
    normalised internally for most calculations.
    """

    point: Point2D
    direction: Vector2D

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def _validate(self) -> "Line2D":
        require_same_crs(self.point.crs, self.direction.crs, "Line2D")
        if self.direction.magnitude < _EPS:
            raise ValueError("Line2D direction must be non-zero.")
        return self

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def crs(self) -> CoordinateSystem:
        return self.point.crs

    @property
    def unit_direction(self) -> Vector2D:
        return self.direction.normalized()

    @property
    def normal(self) -> Vector2D:
        """Unit normal to the line (90° CCW from the direction)."""
        return self.unit_direction.perpendicular().normalized()

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def from_two_points(cls, p1: Point2D, p2: Point2D) -> "Line2D":
        """Construct from two distinct points that lie on the line."""
        require_same_crs(p1.crs, p2.crs, "Line2D.from_two_points")
        direction = Vector2D(x=p2.x - p1.x, y=p2.y - p1.y, crs=p1.crs)
        return cls(point=p1, direction=direction)

    @classmethod
    def from_segment(cls, seg: Segment2D) -> "Line2D":
        """Construct the infinite line that contains *seg*."""
        return cls.from_two_points(seg.start, seg.end)

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def at(self, t: float) -> Point2D:
        """Return the point at parameter *t* (measured in units of the direction magnitude)."""
        d = self.unit_direction
        return Point2D(
            x=self.point.x + t * d.x,
            y=self.point.y + t * d.y,
            crs=self.crs,
        )

    def project(self, p: Point2D) -> float:
        """
        Return the signed scalar projection of *p* onto this line.

        The result is the parameter *t* such that ``self.at(t)`` is the foot
        of the perpendicular from *p*.
        """
        require_same_crs(self.crs, p.crs, "project")
        d = self.unit_direction
        return (p.x - self.point.x) * d.x + (p.y - self.point.y) * d.y

    def closest_point(self, p: Point2D) -> Point2D:
        """Return the foot of the perpendicular from *p* to this line."""
        return self.at(self.project(p))

    def distance_to_point(self, p: Point2D) -> float:
        """Perpendicular (minimum) distance from *p* to this line."""
        return p.distance_to(self.closest_point(p))

    def side_of(self, p: Point2D) -> float:
        """
        Return the signed distance from *p* to the line.

        Positive → left side of the directed line, negative → right side.
        """
        require_same_crs(self.crs, p.crs, "side_of")
        n = self.normal
        return (p.x - self.point.x) * n.x + (p.y - self.point.y) * n.y

    def intersect(self, other: "Line2D") -> "Point2D | None":
        """
        Return the intersection point of two infinite lines, or ``None`` if
        they are parallel (including coincident).
        """
        require_same_crs(self.crs, other.crs, "intersect")
        d1 = self.unit_direction
        d2 = other.unit_direction

        denom = d1.x * d2.y - d1.y * d2.x
        if abs(denom) < _EPS:
            return None

        dx = other.point.x - self.point.x
        dy = other.point.y - self.point.y
        t = (dx * d2.y - dy * d2.x) / denom
        return self.at(t)

    def intersect_segment(self, seg: Segment2D) -> "Point2D | None":
        """
        Return the intersection with *seg*, or ``None`` if parallel or the
        intersection falls outside the finite segment.
        """
        require_same_crs(self.crs, seg.crs, "intersect_segment")
        other = Line2D.from_segment(seg)
        pt = self.intersect(other)
        if pt is None:
            return None
        t = seg.parameter_of(pt)
        # Accept if the closest segment point is very close to the candidate
        if seg.at(t).distance_to(pt) < _EPS * 10:
            # Ensure t is within [0, 1] (i.e., intersection within segment)
            raw_t = (
                (pt.x - seg.start.x) * (seg.end.x - seg.start.x)
                + (pt.y - seg.start.y) * (seg.end.y - seg.start.y)
            )
            seg_len_sq = seg.length ** 2
            if seg_len_sq < _EPS:
                return None
            raw_t /= seg_len_sq
            if -_EPS <= raw_t <= 1.0 + _EPS:
                return pt
        return None

    def parallel_offset(self, distance: float) -> "Line2D":
        """
        Return a new line parallel to this one, offset by *distance*.

        Positive distance → left side (in the direction normal).
        """
        n = self.normal
        new_point = Point2D(
            x=self.point.x + distance * n.x,
            y=self.point.y + distance * n.y,
            crs=self.crs,
        )
        return Line2D(point=new_point, direction=self.direction)

    def transformed(self, t: "Transform2D") -> "Line2D":
        new_point = self.point.transformed(t)
        end = self.at(1.0).transformed(t)
        new_dir = Vector2D(
            x=end.x - new_point.x,
            y=end.y - new_point.y,
            crs=self.crs,
        )
        return Line2D(point=new_point, direction=new_dir)

    def as_ray(self) -> Ray2D:
        """Return a :class:`Ray2D` with the same origin and direction."""
        return Ray2D(origin=self.point, direction=self.unit_direction)

    def __repr__(self) -> str:
        d = self.unit_direction
        return (
            f"Line2D(point={self.point!r}, "
            f"direction=({d.x:.4f}, {d.y:.4f}))"
        )


# ---------------------------------------------------------------------------
# Polyline2D
# ---------------------------------------------------------------------------

class Polyline2D(BaseModel, frozen=True):
    """
    An ordered sequence of :class:`Point2D` forming a connected piecewise-
    linear path.

    All points must share the same CRS.  A polyline with fewer than two
    points is valid as a degenerate case but has zero length.
    """

    points: tuple[Point2D, ...]

    model_config = {"arbitrary_types_allowed": True}

    @field_validator("points", mode="before")
    @classmethod
    def _coerce_tuple(cls, v: object) -> tuple:
        if isinstance(v, (list, tuple)):
            return tuple(v)
        raise ValueError("points must be a list or tuple of Point2D")

    @model_validator(mode="after")
    def _validate(self) -> "Polyline2D":
        if len(self.points) >= 2:
            crs0 = self.points[0].crs
            for i, p in enumerate(self.points[1:], 1):
                require_same_crs(crs0, p.crs, f"Polyline2D point[{i}]")
        return self

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def crs(self) -> CoordinateSystem:
        if not self.points:
            return WORLD
        return self.points[0].crs

    @property
    def start_point(self) -> Point2D:
        if not self.points:
            raise ValueError("Polyline2D has no points.")
        return self.points[0]

    @property
    def end_point(self) -> Point2D:
        if not self.points:
            raise ValueError("Polyline2D has no points.")
        return self.points[-1]

    @property
    def length(self) -> float:
        """Total arc length of the polyline."""
        total = 0.0
        for i in range(len(self.points) - 1):
            total += self.points[i].distance_to(self.points[i + 1])
        return total

    @property
    def is_closed(self) -> bool:
        """True if the first and last points are the same (within tolerance)."""
        if len(self.points) < 2:
            return False
        return self.points[0].distance_to(self.points[-1]) < _EPS

    # ------------------------------------------------------------------
    # Segments
    # ------------------------------------------------------------------

    def segment_at(self, index: int) -> Segment2D:
        """Return the *i*-th segment (zero-based)."""
        n = len(self.points)
        if n < 2:
            raise ValueError("Polyline2D needs at least 2 points to form a segment.")
        if not (0 <= index < n - 1):
            raise IndexError(f"Segment index {index} out of range for {n} points.")
        return Segment2D(start=self.points[index], end=self.points[index + 1])

    def segments(self) -> tuple[Segment2D, ...]:
        """Return all segments as an immutable tuple."""
        if len(self.points) < 2:
            return ()
        return tuple(
            Segment2D(start=self.points[i], end=self.points[i + 1])
            for i in range(len(self.points) - 1)
        )

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def bbox(self) -> "BoundingBox2D":
        """Axis-aligned bounding box enclosing all vertices."""
        from archit_app.geometry.bbox import BoundingBox2D

        if not self.points:
            raise ValueError("Cannot compute bbox of empty Polyline2D.")
        return BoundingBox2D.from_points(self.points)

    def closest_point(self, p: Point2D) -> Point2D:
        """Return the point on the polyline closest to *p*."""
        if not self.segments():
            return self.points[0]
        best_pt = self.points[0]
        best_d = float("inf")
        for seg in self.segments():
            candidate = seg.closest_point(p)
            d = candidate.distance_to(p)
            if d < best_d:
                best_d = d
                best_pt = candidate
        return best_pt

    def distance_to_point(self, p: Point2D) -> float:
        """Minimum distance from *p* to any segment of the polyline."""
        return p.distance_to(self.closest_point(p))

    def reversed(self) -> "Polyline2D":
        """Return a new polyline with points in reverse order."""
        return Polyline2D(points=tuple(reversed(self.points)))

    def transformed(self, t: "Transform2D") -> "Polyline2D":
        return Polyline2D(points=tuple(p.transformed(t) for p in self.points))

    def append(self, p: Point2D) -> "Polyline2D":
        """Return a new polyline with *p* appended."""
        if self.points:
            require_same_crs(self.crs, p.crs, "append")
        return Polyline2D(points=self.points + (p,))

    def close(self) -> "Polyline2D":
        """Return a closed version by appending the first point if not already closed."""
        if self.is_closed or len(self.points) < 2:
            return self
        return Polyline2D(points=self.points + (self.points[0],))

    def to_polygon(self) -> "Polygon2D":
        """
        Convert to a :class:`Polygon2D`.

        The polyline must be closed (or will be closed automatically).
        """
        from archit_app.geometry.polygon import Polygon2D

        closed = self.close()
        return Polygon2D(exterior=closed.points, crs=self.crs)

    def intersections(self, other: "Polyline2D") -> tuple[Point2D, ...]:
        """Return all intersection points between this polyline and *other*."""
        require_same_crs(self.crs, other.crs, "intersections")
        result: list[Point2D] = []
        for s1 in self.segments():
            for s2 in other.segments():
                pt = s1.intersect(s2)
                if pt is not None:
                    result.append(pt)
        return tuple(result)

    def __len__(self) -> int:
        return len(self.points)

    def __getitem__(self, index: int) -> Point2D:
        return self.points[index]

    def __repr__(self) -> str:
        return (
            f"Polyline2D(points={len(self.points)}, "
            f"length={self.length:.4f}, crs={self.crs.name!r})"
        )
