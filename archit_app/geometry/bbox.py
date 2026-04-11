"""
Bounding box types (axis-aligned).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from pydantic import BaseModel, model_validator

from archit_app.geometry.crs import CoordinateSystem, WORLD, require_same_crs
from archit_app.geometry.point import Point2D, Point3D

if TYPE_CHECKING:
    from archit_app.geometry.polygon import Polygon2D


class BoundingBox2D(BaseModel, frozen=True):
    """Axis-aligned bounding box in 2D."""

    min_corner: Point2D
    max_corner: Point2D

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def _validate(self) -> "BoundingBox2D":
        require_same_crs(self.min_corner.crs, self.max_corner.crs, "construct BoundingBox2D")
        if self.min_corner.x > self.max_corner.x or self.min_corner.y > self.max_corner.y:
            raise ValueError(
                f"min_corner {self.min_corner} must be ≤ max_corner {self.max_corner}."
            )
        return self

    @classmethod
    def from_points(cls, points: Iterable[Point2D]) -> "BoundingBox2D":
        pts = list(points)
        if not pts:
            raise ValueError("Cannot create BoundingBox2D from empty sequence.")
        crs = pts[0].crs
        for p in pts[1:]:
            require_same_crs(crs, p.crs, "build bounding box")
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        return cls(
            min_corner=Point2D(x=min(xs), y=min(ys), crs=crs),
            max_corner=Point2D(x=max(xs), y=max(ys), crs=crs),
        )

    @property
    def crs(self) -> CoordinateSystem:
        return self.min_corner.crs

    @property
    def width(self) -> float:
        return self.max_corner.x - self.min_corner.x

    @property
    def height(self) -> float:
        return self.max_corner.y - self.min_corner.y

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Point2D:
        return self.min_corner.midpoint(self.max_corner)

    def contains_point(self, p: Point2D) -> bool:
        require_same_crs(self.crs, p.crs, "contains_point")
        return (
            self.min_corner.x <= p.x <= self.max_corner.x
            and self.min_corner.y <= p.y <= self.max_corner.y
        )

    def intersects(self, other: "BoundingBox2D") -> bool:
        require_same_crs(self.crs, other.crs, "intersects")
        return (
            self.min_corner.x <= other.max_corner.x
            and self.max_corner.x >= other.min_corner.x
            and self.min_corner.y <= other.max_corner.y
            and self.max_corner.y >= other.min_corner.y
        )

    def intersection(self, other: "BoundingBox2D") -> "BoundingBox2D | None":
        require_same_crs(self.crs, other.crs, "intersection")
        if not self.intersects(other):
            return None
        crs = self.crs
        return BoundingBox2D(
            min_corner=Point2D(
                x=max(self.min_corner.x, other.min_corner.x),
                y=max(self.min_corner.y, other.min_corner.y),
                crs=crs,
            ),
            max_corner=Point2D(
                x=min(self.max_corner.x, other.max_corner.x),
                y=min(self.max_corner.y, other.max_corner.y),
                crs=crs,
            ),
        )

    def union(self, other: "BoundingBox2D") -> "BoundingBox2D":
        require_same_crs(self.crs, other.crs, "union")
        crs = self.crs
        return BoundingBox2D(
            min_corner=Point2D(
                x=min(self.min_corner.x, other.min_corner.x),
                y=min(self.min_corner.y, other.min_corner.y),
                crs=crs,
            ),
            max_corner=Point2D(
                x=max(self.max_corner.x, other.max_corner.x),
                y=max(self.max_corner.y, other.max_corner.y),
                crs=crs,
            ),
        )

    def expanded(self, margin: float) -> "BoundingBox2D":
        crs = self.crs
        return BoundingBox2D(
            min_corner=Point2D(x=self.min_corner.x - margin, y=self.min_corner.y - margin, crs=crs),
            max_corner=Point2D(x=self.max_corner.x + margin, y=self.max_corner.y + margin, crs=crs),
        )

    def to_polygon(self) -> "Polygon2D":
        from archit_app.geometry.polygon import Polygon2D

        crs = self.crs
        corners = (
            self.min_corner,
            Point2D(x=self.max_corner.x, y=self.min_corner.y, crs=crs),
            self.max_corner,
            Point2D(x=self.min_corner.x, y=self.max_corner.y, crs=crs),
        )
        return Polygon2D(exterior=corners, crs=crs)

    def __repr__(self) -> str:
        return (
            f"BoundingBox2D(min={self.min_corner.as_tuple()}, "
            f"max={self.max_corner.as_tuple()}, crs={self.crs.name!r})"
        )


class BoundingBox3D(BaseModel, frozen=True):
    """Axis-aligned bounding box in 3D."""

    min_corner: Point3D
    max_corner: Point3D

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def _validate(self) -> "BoundingBox3D":
        require_same_crs(self.min_corner.crs, self.max_corner.crs, "construct BoundingBox3D")
        return self

    @property
    def crs(self) -> CoordinateSystem:
        return self.min_corner.crs

    @property
    def width(self) -> float:
        return self.max_corner.x - self.min_corner.x

    @property
    def depth(self) -> float:
        return self.max_corner.y - self.min_corner.y

    @property
    def height(self) -> float:
        return self.max_corner.z - self.min_corner.z

    @property
    def volume(self) -> float:
        return self.width * self.depth * self.height
