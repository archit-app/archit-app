"""
Ramp element.

A ramp is a continuous inclined surface connecting two floor levels.
Unlike a staircase, a ramp has no discrete steps.
"""

from __future__ import annotations

import math
from enum import Enum

from pydantic import model_validator

from archit_app.elements.base import Element
from archit_app.geometry.crs import WORLD, CoordinateSystem
from archit_app.geometry.point import Point2D
from archit_app.geometry.polygon import Polygon2D


class RampType(str, Enum):
    STRAIGHT = "straight"
    CURVED = "curved"
    SWITCHBACK = "switchback"   # two straight runs with a landing


class Ramp(Element):
    """
    An inclined ramp connecting two floor levels.

    boundary:           footprint polygon in plan
    width:              ramp width in meters (perpendicular to travel direction)
    slope_angle:        slope angle in radians (positive = ascending in travel direction)
    direction:          travel direction angle in radians (0 = +x)
    bottom_level_index: level the ramp departs from
    top_level_index:    level the ramp arrives at
    ramp_type:          geometry classification
    has_landing:        True if there is an intermediate flat landing
    material:           optional material identifier
    """

    boundary: Polygon2D
    width: float
    slope_angle: float
    direction: float = 0.0
    bottom_level_index: int = 0
    top_level_index: int = 1
    ramp_type: RampType = RampType.STRAIGHT
    has_landing: bool = False
    material: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "Ramp":
        if self.width <= 0:
            raise ValueError(f"Ramp width must be positive, got {self.width}.")
        if not (0 < self.slope_angle < math.pi / 2):
            raise ValueError(
                f"slope_angle must be in (0, π/2) radians, got {self.slope_angle:.4f}."
            )
        if self.bottom_level_index >= self.top_level_index:
            raise ValueError(
                f"bottom_level_index ({self.bottom_level_index}) must be less than "
                f"top_level_index ({self.top_level_index})."
            )
        return self

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def total_rise(self) -> float:
        """Total vertical height covered in meters, derived from boundary length and slope."""
        bb = self.boundary.bounding_box()
        run = max(bb.width, bb.height)
        return run * math.tan(self.slope_angle)

    @property
    def slope_percent(self) -> float:
        """Slope expressed as a percentage (rise/run × 100)."""
        return math.tan(self.slope_angle) * 100

    def bounding_box(self):
        return self.boundary.bounding_box()

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def straight(
        cls,
        x: float,
        y: float,
        width: float,
        length: float,
        slope_angle: float,
        direction: float = 0.0,
        bottom_level_index: int = 0,
        top_level_index: int = 1,
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Ramp":
        """
        Create a straight ramp.

        x, y:        lower-left corner of the footprint
        width:       ramp width in meters
        length:      horizontal run length in meters
        slope_angle: incline in radians
        direction:   travel direction in radians (0 = +x)
        """
        cos_d = math.cos(direction)
        sin_d = math.sin(direction)

        def _rotate(lx: float, ly: float) -> tuple[float, float]:
            return (
                x + lx * cos_d - ly * sin_d,
                y + lx * sin_d + ly * cos_d,
            )

        corners = (
            _rotate(0.0, 0.0),
            _rotate(length, 0.0),
            _rotate(length, width),
            _rotate(0.0, width),
        )
        boundary = Polygon2D(
            exterior=tuple(Point2D(x=cx, y=cy, crs=crs) for cx, cy in corners),
            crs=crs,
        )
        return cls(
            boundary=boundary,
            width=width,
            slope_angle=slope_angle,
            direction=direction,
            bottom_level_index=bottom_level_index,
            top_level_index=top_level_index,
            ramp_type=RampType.STRAIGHT,
            crs=crs,
            **kwargs,
        )

    def __repr__(self) -> str:
        return (
            f"Ramp(type={self.ramp_type.value}, slope={math.degrees(self.slope_angle):.1f}°, "
            f"width={self.width}m, levels={self.bottom_level_index}→{self.top_level_index})"
        )
