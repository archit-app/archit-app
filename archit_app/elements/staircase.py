"""
Staircase element.

A staircase represents a set of steps connecting two floor levels.
Its boundary polygon defines the footprint on the plan.
"""

from __future__ import annotations

import math
from enum import Enum

from pydantic import model_validator

from archit_app.elements.base import Element
from archit_app.geometry.crs import WORLD, CoordinateSystem
from archit_app.geometry.point import Point2D
from archit_app.geometry.polygon import Polygon2D


class StaircaseType(str, Enum):
    STRAIGHT = "straight"
    L_SHAPED = "l_shaped"
    U_SHAPED = "u_shaped"
    SPIRAL = "spiral"
    CURVED = "curved"


class Staircase(Element):
    """
    A staircase connecting two floor levels.

    boundary:          footprint polygon in plan (world space)
    rise_count:        number of risers (steps)
    rise_height:       height of each riser in meters
    run_depth:         horizontal depth of each tread in meters
    width:             stair width in meters (perpendicular to travel direction)
    stair_type:        geometry classification
    direction:         angle in radians of the travel direction (0 = +x)
    bottom_level_index: index of the Level this stair departs from
    top_level_index:    index of the Level this stair arrives at
    has_landing:       True if there is an intermediate landing
    nosing:            tread nosing overhang in meters (default 0.02 m)
    material:          optional material identifier
    """

    boundary: Polygon2D
    rise_count: int
    rise_height: float
    run_depth: float
    width: float
    stair_type: StaircaseType = StaircaseType.STRAIGHT
    direction: float = 0.0
    bottom_level_index: int = 0
    top_level_index: int = 1
    has_landing: bool = False
    nosing: float = 0.02
    material: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "Staircase":
        if self.rise_count < 1:
            raise ValueError(f"rise_count must be >= 1, got {self.rise_count}.")
        if self.rise_height <= 0:
            raise ValueError(f"rise_height must be positive, got {self.rise_height}.")
        if self.run_depth <= 0:
            raise ValueError(f"run_depth must be positive, got {self.run_depth}.")
        if self.width <= 0:
            raise ValueError(f"width must be positive, got {self.width}.")
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
        """Total vertical height covered by this staircase in meters."""
        return self.rise_count * self.rise_height

    @property
    def total_run(self) -> float:
        """Total horizontal run length in meters."""
        return self.rise_count * self.run_depth

    @property
    def slope_angle(self) -> float:
        """Slope angle in radians (arctan of rise/run per step)."""
        return math.atan2(self.rise_height, self.run_depth)

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
        rise_count: int,
        rise_height: float = 0.175,
        run_depth: float = 0.28,
        direction: float = 0.0,
        bottom_level_index: int = 0,
        top_level_index: int = 1,
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Staircase":
        """
        Create a straight staircase.

        x, y:    lower-left corner of the footprint
        width:   stair width in meters (perpendicular to travel direction)
        direction: travel direction angle in radians (0 = +x axis)
        """
        run_length = rise_count * run_depth
        cos_d = math.cos(direction)
        sin_d = math.sin(direction)

        # Local rectangle: width along Y, run_length along X, then rotate by direction
        def _rotate(lx: float, ly: float) -> tuple[float, float]:
            return (
                x + lx * cos_d - ly * sin_d,
                y + lx * sin_d + ly * cos_d,
            )

        corners = (
            _rotate(0.0, 0.0),
            _rotate(run_length, 0.0),
            _rotate(run_length, width),
            _rotate(0.0, width),
        )
        boundary = Polygon2D(
            exterior=tuple(Point2D(x=cx, y=cy, crs=crs) for cx, cy in corners),
            crs=crs,
        )
        return cls(
            boundary=boundary,
            rise_count=rise_count,
            rise_height=rise_height,
            run_depth=run_depth,
            width=width,
            stair_type=StaircaseType.STRAIGHT,
            direction=direction,
            bottom_level_index=bottom_level_index,
            top_level_index=top_level_index,
            crs=crs,
            **kwargs,
        )

    def __repr__(self) -> str:
        return (
            f"Staircase(type={self.stair_type.value}, rises={self.rise_count}, "
            f"total_rise={self.total_rise:.2f}m, levels={self.bottom_level_index}→{self.top_level_index})"
        )
