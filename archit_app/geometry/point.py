"""
2D and 3D point types with CRS tagging.

Points represent positions in space. They transform with full affine transforms
(including translation), unlike vectors.

Operator algebra:
  Point2D + Vector2D → Point2D    (displacement)
  Point2D - Point2D  → Vector2D   (difference)
  Point2D + Point2D  → TypeError  (meaningless: adding two positions)
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from pydantic import BaseModel

from archit_app.geometry.crs import CoordinateSystem, WORLD, require_same_crs
from archit_app.geometry.vector import Vector2D, Vector3D

if TYPE_CHECKING:
    from archit_app.geometry.converter import CoordinateConverter
    from archit_app.geometry.transform import Transform2D


class Point2D(BaseModel, frozen=True):
    """An immutable 2D position carrying its coordinate system."""

    x: float
    y: float
    crs: CoordinateSystem = WORLD

    model_config = {"arbitrary_types_allowed": True}

    # ------------------------------------------------------------------
    # Arithmetic
    # ------------------------------------------------------------------

    def __add__(self, other: object) -> "Point2D":
        if isinstance(other, Vector2D):
            require_same_crs(self.crs, other.crs, "add")
            return Point2D(x=self.x + other.x, y=self.y + other.y, crs=self.crs)
        if isinstance(other, Point2D):
            raise TypeError(
                "Cannot add two Point2D objects. "
                "Use Point2D + Vector2D to displace a point."
            )
        return NotImplemented

    def __sub__(self, other: object) -> "Vector2D | Point2D":
        if isinstance(other, Point2D):
            require_same_crs(self.crs, other.crs, "subtract")
            return Vector2D(x=self.x - other.x, y=self.y - other.y, crs=self.crs)
        if isinstance(other, Vector2D):
            require_same_crs(self.crs, other.crs, "subtract")
            return Point2D(x=self.x - other.x, y=self.y - other.y, crs=self.crs)
        return NotImplemented

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def distance_to(self, other: "Point2D") -> float:
        require_same_crs(self.crs, other.crs, "measure distance")
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def midpoint(self, other: "Point2D") -> "Point2D":
        require_same_crs(self.crs, other.crs, "midpoint")
        return Point2D(x=(self.x + other.x) / 2, y=(self.y + other.y) / 2, crs=self.crs)

    def to(
        self, target: CoordinateSystem, converter: "CoordinateConverter"
    ) -> "Point2D":
        """Convert this point to *target* CRS using *converter*."""
        arr = converter.convert(self.as_array(), self.crs, target)
        return Point2D(x=float(arr[0]), y=float(arr[1]), crs=target)

    def transformed(self, t: "Transform2D") -> "Point2D":
        result = t.apply_to_array(self.as_array().reshape(1, 2))
        return Point2D(x=float(result[0, 0]), y=float(result[0, 1]), crs=self.crs)

    def as_array(self) -> np.ndarray:
        return np.array([self.x, self.y], dtype=np.float64)

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)

    def __repr__(self) -> str:
        return f"Point2D(x={self.x}, y={self.y}, crs={self.crs.name!r})"


class Point3D(BaseModel, frozen=True):
    """An immutable 3D position carrying its coordinate system."""

    x: float
    y: float
    z: float
    crs: CoordinateSystem = WORLD

    model_config = {"arbitrary_types_allowed": True}

    def __add__(self, other: object) -> "Point3D":
        if isinstance(other, Vector3D):
            require_same_crs(self.crs, other.crs, "add")
            return Point3D(x=self.x + other.x, y=self.y + other.y, z=self.z + other.z, crs=self.crs)
        if isinstance(other, Point3D):
            raise TypeError("Cannot add two Point3D objects.")
        return NotImplemented

    def __sub__(self, other: object) -> "Vector3D | Point3D":
        if isinstance(other, Point3D):
            require_same_crs(self.crs, other.crs, "subtract")
            return Vector3D(
                x=self.x - other.x, y=self.y - other.y, z=self.z - other.z, crs=self.crs
            )
        if isinstance(other, Vector3D):
            require_same_crs(self.crs, other.crs, "subtract")
            return Point3D(
                x=self.x - other.x, y=self.y - other.y, z=self.z - other.z, crs=self.crs
            )
        return NotImplemented

    def distance_to(self, other: "Point3D") -> float:
        require_same_crs(self.crs, other.crs, "measure distance")
        return math.sqrt(
            (self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2
        )

    def as_array(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z], dtype=np.float64)

    def as_2d(self) -> Point2D:
        """Drop the Z component."""
        return Point2D(x=self.x, y=self.y, crs=self.crs)

    def __repr__(self) -> str:
        return f"Point3D(x={self.x}, y={self.y}, z={self.z}, crs={self.crs.name!r})"
