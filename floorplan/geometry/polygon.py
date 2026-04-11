"""
General 2D polygon with optional holes.

Backed by shapely for geometric operations but stored as tuples of Point2D
for Pydantic compatibility and CRS enforcement.

Design notes:
- Exterior and holes are stored as immutable tuples of Point2D.
- Shapely objects are computed lazily and not stored in the model.
- All shapely operations preserve the CRS of the original polygon.
- Boolean operations (union, intersection, difference) may return None
  when the result is empty.
"""

from __future__ import annotations

import functools
from typing import Any, Iterable

import shapely
import shapely.geometry
from pydantic import BaseModel, field_validator, model_serializer, model_validator

from floorplan.geometry.bbox import BoundingBox2D
from floorplan.geometry.crs import CoordinateSystem, WORLD, require_same_crs
from floorplan.geometry.point import Point2D


class Polygon2D(BaseModel, frozen=True):
    """
    An immutable 2D polygon with optional holes.

    All vertices must share the same CRS. The exterior ring should be
    counter-clockwise (CCW) for positive area; holes should be CW.
    Shapely will handle normalization automatically.
    """

    exterior: tuple[Point2D, ...]
    holes: tuple[tuple[Point2D, ...], ...] = ()
    crs: CoordinateSystem = WORLD

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def _validate(self) -> "Polygon2D":
        if len(self.exterior) < 3:
            raise ValueError("Polygon exterior must have at least 3 vertices.")
        for p in self.exterior:
            require_same_crs(self.crs, p.crs, "construct Polygon2D exterior")
        for hole in self.holes:
            if len(hole) < 3:
                raise ValueError("Polygon hole must have at least 3 vertices.")
            for p in hole:
                require_same_crs(self.crs, p.crs, "construct Polygon2D hole")
        return self

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        return {
            "exterior": [(p.x, p.y) for p in self.exterior],
            "holes": [[(p.x, p.y) for p in h] for h in self.holes],
            "crs": self.crs.name,
        }

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> "Polygon2D":
        # Support deserializing from the serialized dict format
        if isinstance(obj, dict) and "exterior" in obj:
            crs_name = obj.get("crs", "world")
            from floorplan.geometry.crs import WORLD, SCREEN, IMAGE, WGS84
            crs_map = {"world": WORLD, "screen": SCREEN, "image": IMAGE, "geographic": WGS84}
            crs = crs_map.get(crs_name, WORLD)
            exterior = tuple(Point2D(x=x, y=y, crs=crs) for x, y in obj["exterior"])
            holes = tuple(
                tuple(Point2D(x=x, y=y, crs=crs) for x, y in h) for h in obj.get("holes", [])
            )
            return cls(exterior=exterior, holes=holes, crs=crs)
        return super().model_validate(obj, **kwargs)

    # ------------------------------------------------------------------
    # Shapely bridge (private, lazy)
    # ------------------------------------------------------------------

    def _to_shapely(self) -> shapely.Polygon:
        exterior_coords = [(p.x, p.y) for p in self.exterior]
        holes_coords = [[(p.x, p.y) for p in h] for h in self.holes]
        return shapely.Polygon(exterior_coords, holes_coords)

    @classmethod
    def _from_shapely(cls, poly: shapely.Polygon, crs: CoordinateSystem) -> "Polygon2D":
        if poly.is_empty:
            raise ValueError("Cannot create Polygon2D from empty shapely Polygon.")
        exterior = tuple(
            Point2D(x=x, y=y, crs=crs) for x, y in poly.exterior.coords[:-1]
        )
        holes = tuple(
            tuple(Point2D(x=x, y=y, crs=crs) for x, y in ring.coords[:-1])
            for ring in poly.interiors
        )
        return cls(exterior=exterior, holes=holes, crs=crs)

    # ------------------------------------------------------------------
    # Properties (delegates to shapely)
    # ------------------------------------------------------------------

    @property
    def area(self) -> float:
        return self._to_shapely().area

    @property
    def perimeter(self) -> float:
        return self._to_shapely().length

    @property
    def centroid(self) -> Point2D:
        c = self._to_shapely().centroid
        return Point2D(x=c.x, y=c.y, crs=self.crs)

    @property
    def is_valid(self) -> bool:
        return self._to_shapely().is_valid

    @property
    def is_convex(self) -> bool:
        sp = self._to_shapely()
        return sp.equals(sp.convex_hull)

    def bounding_box(self) -> BoundingBox2D:
        return BoundingBox2D.from_points(self.exterior)

    # ------------------------------------------------------------------
    # Spatial operations
    # ------------------------------------------------------------------

    def contains_point(self, p: Point2D) -> bool:
        require_same_crs(self.crs, p.crs, "contains_point")
        return self._to_shapely().contains(shapely.Point(p.x, p.y))

    def intersects(self, other: "Polygon2D") -> bool:
        require_same_crs(self.crs, other.crs, "intersects")
        return self._to_shapely().intersects(other._to_shapely())

    def buffer(self, distance: float) -> "Polygon2D":
        result = self._to_shapely().buffer(distance)
        return Polygon2D._from_shapely(result, self.crs)

    def union(self, other: "Polygon2D") -> "Polygon2D":
        require_same_crs(self.crs, other.crs, "union")
        result = self._to_shapely().union(other._to_shapely())
        return Polygon2D._from_shapely(result, self.crs)

    def intersection(self, other: "Polygon2D") -> "Polygon2D | None":
        require_same_crs(self.crs, other.crs, "intersection")
        result = self._to_shapely().intersection(other._to_shapely())
        if result.is_empty:
            return None
        return Polygon2D._from_shapely(result, self.crs)

    def difference(self, other: "Polygon2D") -> "Polygon2D | None":
        require_same_crs(self.crs, other.crs, "difference")
        result = self._to_shapely().difference(other._to_shapely())
        if result.is_empty:
            return None
        return Polygon2D._from_shapely(result, self.crs)

    def simplify(self, tolerance: float, preserve_topology: bool = True) -> "Polygon2D":
        result = self._to_shapely().simplify(tolerance, preserve_topology=preserve_topology)
        return Polygon2D._from_shapely(result, self.crs)

    def convex_hull(self) -> "Polygon2D":
        result = self._to_shapely().convex_hull
        return Polygon2D._from_shapely(result, self.crs)

    def transformed(self, t: "Transform2D") -> "Polygon2D":
        from floorplan.geometry.transform import Transform2D

        new_exterior = tuple(p.transformed(t) for p in self.exterior)
        new_holes = tuple(tuple(p.transformed(t) for p in h) for h in self.holes)
        return Polygon2D(exterior=new_exterior, holes=new_holes, crs=self.crs)

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def from_shapely(cls, poly: shapely.Polygon, crs: CoordinateSystem = WORLD) -> "Polygon2D":
        return cls._from_shapely(poly, crs)

    @classmethod
    def rectangle(
        cls, x: float, y: float, width: float, height: float, crs: CoordinateSystem = WORLD
    ) -> "Polygon2D":
        """Create an axis-aligned rectangle."""
        pts = (
            Point2D(x=x, y=y, crs=crs),
            Point2D(x=x + width, y=y, crs=crs),
            Point2D(x=x + width, y=y + height, crs=crs),
            Point2D(x=x, y=y + height, crs=crs),
        )
        return cls(exterior=pts, crs=crs)

    @classmethod
    def circle(
        cls, center_x: float, center_y: float, radius: float,
        resolution: int = 32, crs: CoordinateSystem = WORLD
    ) -> "Polygon2D":
        """Create a circle approximated as a polygon."""
        import math
        pts = tuple(
            Point2D(
                x=center_x + radius * math.cos(2 * math.pi * i / resolution),
                y=center_y + radius * math.sin(2 * math.pi * i / resolution),
                crs=crs,
            )
            for i in range(resolution)
        )
        return cls(exterior=pts, crs=crs)

    def __repr__(self) -> str:
        return (
            f"Polygon2D(vertices={len(self.exterior)}, "
            f"holes={len(self.holes)}, crs={self.crs.name!r})"
        )
