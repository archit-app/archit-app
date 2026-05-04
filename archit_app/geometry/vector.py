"""
2D and 3D vector types with CRS tagging.

Vectors represent directions and magnitudes, NOT positions.
They transform differently from points (no translation applied).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from archit_app.geometry.crs import WORLD, CoordinateSystem, require_same_crs

if TYPE_CHECKING:  # pragma: no cover - typing only
    import numpy as np  # noqa: F401


# Lazy numpy import — keeps `import archit_app` cheap on cold paths that
# never touch geometry. The first call to `as_array()` triggers the import.
_np_module: Any = None


def _np() -> Any:
    global _np_module
    if _np_module is None:
        import numpy as _np_imported

        _np_module = _np_imported
    return _np_module


class Vector2D(BaseModel, frozen=True):
    """An immutable 2D direction vector carrying its coordinate system."""

    x: float
    y: float
    crs: CoordinateSystem = WORLD

    model_config = {"arbitrary_types_allowed": True}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def magnitude(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y)

    @property
    def magnitude_sq(self) -> float:
        return self.x * self.x + self.y * self.y

    def normalized(self) -> "Vector2D":
        mag = self.magnitude
        if mag < 1e-12:
            raise ValueError("Cannot normalize a zero vector.")
        return Vector2D(x=self.x / mag, y=self.y / mag, crs=self.crs)

    def dot(self, other: "Vector2D") -> float:
        require_same_crs(self.crs, other.crs, "dot-product")
        return self.x * other.x + self.y * other.y

    def cross(self, other: "Vector2D") -> float:
        """2D cross product — returns the scalar z-component of the 3D cross."""
        require_same_crs(self.crs, other.crs, "cross-product")
        return self.x * other.y - self.y * other.x

    def rotated(self, angle_rad: float) -> "Vector2D":
        c, s = math.cos(angle_rad), math.sin(angle_rad)
        return Vector2D(
            x=c * self.x - s * self.y,
            y=s * self.x + c * self.y,
            crs=self.crs,
        )

    def perpendicular(self) -> "Vector2D":
        """Returns the 90-degree counter-clockwise perpendicular."""
        return Vector2D(x=-self.y, y=self.x, crs=self.crs)

    def angle(self) -> float:
        """Angle in radians from +X axis, in [-π, π]."""
        return math.atan2(self.y, self.x)

    def as_array(self) -> Any:
        np = _np()
        return np.array([self.x, self.y], dtype=np.float64)

    # ------------------------------------------------------------------
    # Arithmetic
    # ------------------------------------------------------------------

    def __add__(self, other: "Vector2D") -> "Vector2D":
        require_same_crs(self.crs, other.crs, "add")
        return Vector2D(x=self.x + other.x, y=self.y + other.y, crs=self.crs)

    def __sub__(self, other: "Vector2D") -> "Vector2D":
        require_same_crs(self.crs, other.crs, "subtract")
        return Vector2D(x=self.x - other.x, y=self.y - other.y, crs=self.crs)

    def __mul__(self, scalar: float) -> "Vector2D":
        return Vector2D(x=self.x * scalar, y=self.y * scalar, crs=self.crs)

    def __rmul__(self, scalar: float) -> "Vector2D":
        return self.__mul__(scalar)

    def __truediv__(self, scalar: float) -> "Vector2D":
        if scalar == 0:
            raise ZeroDivisionError("Cannot divide vector by zero.")
        return Vector2D(x=self.x / scalar, y=self.y / scalar, crs=self.crs)

    def __neg__(self) -> "Vector2D":
        return Vector2D(x=-self.x, y=-self.y, crs=self.crs)

    def __repr__(self) -> str:
        return f"Vector2D(x={self.x}, y={self.y}, crs={self.crs.name!r})"


class Vector3D(BaseModel, frozen=True):
    """An immutable 3D direction vector carrying its coordinate system."""

    x: float
    y: float
    z: float
    crs: CoordinateSystem = WORLD

    model_config = {"arbitrary_types_allowed": True}

    @property
    def magnitude(self) -> float:
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def normalized(self) -> "Vector3D":
        mag = self.magnitude
        if mag < 1e-12:
            raise ValueError("Cannot normalize a zero vector.")
        return Vector3D(x=self.x / mag, y=self.y / mag, z=self.z / mag, crs=self.crs)

    def dot(self, other: "Vector3D") -> float:
        require_same_crs(self.crs, other.crs, "dot-product")
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: "Vector3D") -> "Vector3D":
        require_same_crs(self.crs, other.crs, "cross-product")
        return Vector3D(
            x=self.y * other.z - self.z * other.y,
            y=self.z * other.x - self.x * other.z,
            z=self.x * other.y - self.y * other.x,
            crs=self.crs,
        )

    def as_array(self) -> Any:
        np = _np()
        return np.array([self.x, self.y, self.z], dtype=np.float64)

    def __add__(self, other: "Vector3D") -> "Vector3D":
        require_same_crs(self.crs, other.crs, "add")
        return Vector3D(x=self.x + other.x, y=self.y + other.y, z=self.z + other.z, crs=self.crs)

    def __sub__(self, other: "Vector3D") -> "Vector3D":
        require_same_crs(self.crs, other.crs, "subtract")
        return Vector3D(x=self.x - other.x, y=self.y - other.y, z=self.z - other.z, crs=self.crs)

    def __mul__(self, scalar: float) -> "Vector3D":
        return Vector3D(x=self.x * scalar, y=self.y * scalar, z=self.z * scalar, crs=self.crs)

    def __rmul__(self, scalar: float) -> "Vector3D":
        return self.__mul__(scalar)

    def __neg__(self) -> "Vector3D":
        return Vector3D(x=-self.x, y=-self.y, z=-self.z, crs=self.crs)

    def __repr__(self) -> str:
        return f"Vector3D(x={self.x}, y={self.y}, z={self.z}, crs={self.crs.name!r})"
