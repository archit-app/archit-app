"""
Coordinate Reference System (CRS) definitions.

Canonical conventions for this package:
- Internal unit: meters (float64)
- Y direction: Y-up (architectural convention)
- Screen/image layers are responsible for Y-flip, not geometry

The five coordinate spaces:
  WORLD      — meters, Y-up, origin at site datum
  SCREEN     — pixels, Y-down, origin top-left
  IMAGE      — pixels, Y-down, origin top-left (same as screen unless canvas offset)
  LOCAL      — meters, Y-up, per-element origin (managed per Element)
  WGS84      — geographic lat/lon (handled at import/export boundaries only)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class YDirection(Enum):
    UP = auto()    # architectural / mathematical convention
    DOWN = auto()  # screen / image convention


class LengthUnit(Enum):
    METERS = 1.0
    FEET = 0.3048
    INCHES = 0.0254
    MILLIMETERS = 0.001
    PIXELS = None  # unitless — scale resolved at runtime via pixels_per_meter

    def to_meters(self, value: float, pixels_per_meter: float | None = None) -> float:
        if self is LengthUnit.PIXELS:
            if pixels_per_meter is None:
                raise ValueError(
                    "Cannot convert PIXELS to meters without pixels_per_meter."
                )
            return value / pixels_per_meter
        return value * self.value  # type: ignore[operator]

    def from_meters(self, value: float, pixels_per_meter: float | None = None) -> float:
        if self is LengthUnit.PIXELS:
            if pixels_per_meter is None:
                raise ValueError(
                    "Cannot convert meters to PIXELS without pixels_per_meter."
                )
            return value * pixels_per_meter
        return value / self.value  # type: ignore[operator]


@dataclass(frozen=True)
class CoordinateSystem:
    """
    Describes a coordinate space. Carry this with every Point/Vector so that
    arithmetic between mismatched spaces raises CRSMismatchError immediately.
    """

    name: str
    unit: LengthUnit
    y_direction: YDirection
    origin: tuple[float, float] = (0.0, 0.0)  # in meters, if applicable
    pixels_per_meter: float | None = None       # only for PIXELS unit spaces
    epsg_code: int | None = None                # only for geographic spaces

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CoordinateSystem):
            return NotImplemented
        # Identity is defined by (name, unit, y_direction) — not mutable config
        return (
            self.name == other.name
            and self.unit == other.unit
            and self.y_direction == other.y_direction
        )

    def __hash__(self) -> int:
        return hash((self.name, self.unit, self.y_direction))

    def __repr__(self) -> str:
        return f"CoordinateSystem({self.name!r}, {self.unit.name}, {self.y_direction.name})"


# ---------------------------------------------------------------------------
# Module-level singletons — import these everywhere
# ---------------------------------------------------------------------------

WORLD = CoordinateSystem("world", LengthUnit.METERS, YDirection.UP)
SCREEN = CoordinateSystem("screen", LengthUnit.PIXELS, YDirection.DOWN)
IMAGE = CoordinateSystem("image", LengthUnit.PIXELS, YDirection.DOWN)
WGS84 = CoordinateSystem("geographic", LengthUnit.METERS, YDirection.UP, epsg_code=4326)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CRSMismatchError(ValueError):
    """Raised when two spatial objects with incompatible CRS are combined."""

    def __init__(self, a: CoordinateSystem, b: CoordinateSystem, op: str = "operate on") -> None:
        super().__init__(
            f"Cannot {op} objects in CRS '{a.name}' and '{b.name}'. "
            f"Convert explicitly first using .to(target_crs, converter)."
        )


def require_same_crs(a: CoordinateSystem, b: CoordinateSystem, op: str = "operate on") -> None:
    """Assert that two CRS match; raise CRSMismatchError otherwise."""
    if a != b:
        raise CRSMismatchError(a, b, op)
