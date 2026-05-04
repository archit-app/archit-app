"""
Beam element.

A beam is a horizontal structural member spanning between supports (columns, walls).
Its footprint is a polygon in plan; cross-section dimensions and elevation describe
its 3-D profile.
"""

from __future__ import annotations

import math
from enum import Enum

from pydantic import model_validator

from archit_app.elements.base import Element
from archit_app.geometry.crs import WORLD, CoordinateSystem
from archit_app.geometry.point import Point2D
from archit_app.geometry.polygon import Polygon2D


class BeamSection(str, Enum):
    RECTANGULAR = "rectangular"
    I_SECTION = "i_section"     # wide-flange / H-beam
    T_SECTION = "t_section"
    CIRCULAR = "circular"       # round HSS / tube
    CUSTOM = "custom"


class Beam(Element):
    """
    A structural beam.

    geometry:    footprint polygon of the beam centerline extruded to plan width
    width:       cross-section width in meters (plan dimension)
    depth:       structural depth of the cross-section in meters (vertical)
    elevation:   elevation of the beam's top surface in meters
    section:     cross-section shape classification
    level_index: which Level this beam belongs to
    material:    optional material identifier
    """

    geometry: Polygon2D
    width: float
    depth: float
    elevation: float
    section: BeamSection = BeamSection.RECTANGULAR
    level_index: int = 0
    material: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "Beam":
        if self.width <= 0:
            raise ValueError(f"Beam width must be positive, got {self.width}.")
        if self.depth <= 0:
            raise ValueError(f"Beam depth must be positive, got {self.depth}.")
        return self

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def span(self) -> float:
        """Span length in meters (centreline distance between the two end faces)."""
        pts = self.geometry.exterior
        if len(pts) == 4:
            # A straight beam polygon has vertices: start-left, end-left, end-right, start-right
            # Centreline endpoints are midpoints of the start pair and end pair.
            mid_start_x = (pts[0].x + pts[3].x) / 2
            mid_start_y = (pts[0].y + pts[3].y) / 2
            mid_end_x = (pts[1].x + pts[2].x) / 2
            mid_end_y = (pts[1].y + pts[2].y) / 2
            dx = mid_end_x - mid_start_x
            dy = mid_end_y - mid_start_y
            return math.sqrt(dx * dx + dy * dy)
        bb = self.geometry.bounding_box()
        return max(bb.width, bb.height)

    @property
    def soffit_elevation(self) -> float:
        """Elevation of the beam's bottom face (soffit) in meters."""
        return self.elevation - self.depth

    def bounding_box(self):
        return self.geometry.bounding_box()

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def straight(
        cls,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        width: float,
        depth: float,
        elevation: float,
        section: BeamSection = BeamSection.RECTANGULAR,
        level_index: int = 0,
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Beam":
        """
        Create a straight beam between two endpoints.

        The plan footprint is a rectangle of the given width centred on the
        line from (x1, y1) to (x2, y2).
        """
        dx, dy = x2 - x1, y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1e-10:
            raise ValueError("Beam endpoints must not be the same point.")

        nx, ny = -dy / length, dx / length
        half = width / 2
        pts = (
            Point2D(x=x1 + nx * half, y=y1 + ny * half, crs=crs),
            Point2D(x=x2 + nx * half, y=y2 + ny * half, crs=crs),
            Point2D(x=x2 - nx * half, y=y2 - ny * half, crs=crs),
            Point2D(x=x1 - nx * half, y=y1 - ny * half, crs=crs),
        )
        geometry = Polygon2D(exterior=pts, crs=crs)
        return cls(
            geometry=geometry,
            width=width,
            depth=depth,
            elevation=elevation,
            section=section,
            level_index=level_index,
            crs=crs,
            **kwargs,
        )

    def __repr__(self) -> str:
        return (
            f"Beam(section={self.section.value}, span≈{self.span:.2f}m, "
            f"width={self.width}m, depth={self.depth}m, elevation={self.elevation}m)"
        )
