"""
Column element.

Columns are vertical structural elements. Their cross-section is always
represented as a Polygon2D (circles are approximated as polygons).
"""

from __future__ import annotations

import math
from enum import Enum

from archit_app.elements.base import Element
from archit_app.geometry.crs import CoordinateSystem, WORLD
from archit_app.geometry.polygon import Polygon2D


class ColumnShape(str, Enum):
    RECTANGULAR = "rectangular"
    CIRCULAR = "circular"
    CUSTOM = "custom"


class Column(Element):
    """
    A vertical structural column.

    geometry: cross-section polygon in world space
    height:   column height in meters
    shape:    semantic shape type (for rendering/export hints)
    material: optional material identifier
    """

    geometry: Polygon2D
    height: float
    shape: ColumnShape = ColumnShape.CUSTOM
    material: str | None = None

    def bounding_box(self):
        return self.geometry.bounding_box()

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def rectangular(
        cls,
        x: float,
        y: float,
        width: float,
        depth: float,
        height: float = 3.0,
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Column":
        """Create a rectangular column with lower-left corner at (x, y)."""
        geom = Polygon2D.rectangle(x, y, width, depth, crs=crs)
        return cls(geometry=geom, height=height, shape=ColumnShape.RECTANGULAR, **kwargs)

    @classmethod
    def circular(
        cls,
        center_x: float,
        center_y: float,
        diameter: float,
        height: float = 3.0,
        resolution: int = 32,
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Column":
        """Create a circular column approximated as a regular polygon."""
        geom = Polygon2D.circle(center_x, center_y, diameter / 2, resolution=resolution, crs=crs)
        return cls(geometry=geom, height=height, shape=ColumnShape.CIRCULAR, **kwargs)

    def __repr__(self) -> str:
        return (
            f"Column(shape={self.shape.value}, height={self.height}m, "
            f"crs={self.crs.name!r})"
        )
