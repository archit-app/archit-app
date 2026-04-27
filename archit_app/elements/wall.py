"""
Wall element.

Walls are the primary structural/enclosing element of a floorplan.
They support straight, arc, and spline geometry (non-Manhattan).
Openings (doors, windows) are punched into walls.
"""

from __future__ import annotations

from enum import Enum
from typing import Union

from pydantic import Field, model_validator

from archit_app.elements.base import Element
from archit_app.elements.opening import Opening
from archit_app.geometry.bbox import BoundingBox2D
from archit_app.geometry.curve import ArcCurve, BezierCurve, NURBSCurve
from archit_app.geometry.polygon import Polygon2D


class WallType(str, Enum):
    EXTERIOR = "exterior"
    INTERIOR = "interior"
    CURTAIN = "curtain"
    SHEAR = "shear"
    PARTY = "party"        # shared with neighbouring building
    RETAINING = "retaining"


# Wall geometry can be a polygon (box wall) or a centre-line curve
WallGeometry = Union[Polygon2D, ArcCurve, BezierCurve, NURBSCurve]


class Wall(Element):
    """
    A wall element.

    geometry: either a Polygon2D (box/face representation) or a centre-line
              curve (ArcCurve, BezierCurve). When a curve is used, thickness
              defines the total wall width centred on the curve.
    thickness: wall thickness in meters
    height:    floor-to-ceiling height in meters
    wall_type: structural classification
    openings:  doors/windows punched into this wall (immutable tuple)
    material:  optional material identifier key (for future material registry)
    """

    geometry: WallGeometry
    thickness: float
    height: float
    wall_type: WallType = WallType.INTERIOR
    openings: tuple[Opening, ...] = ()
    material: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "Wall":
        if self.thickness <= 0:
            raise ValueError(f"Wall thickness must be positive, got {self.thickness}.")
        if self.height <= 0:
            raise ValueError(f"Wall height must be positive, got {self.height}.")
        return self

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def length(self) -> float:
        """Approximate wall length along its centre line."""
        if isinstance(self.geometry, Polygon2D):
            # For a box wall polygon, length ≈ longer side of bounding box
            bb = self.geometry.bounding_box()
            return max(bb.width, bb.height)
        # For curve-based walls, use the curve length
        return self.geometry.length()

    @property
    def start_point(self) -> tuple[float, float] | None:
        """
        Approximate centre-line start point as ``(x, y)`` in metres.

        For straight walls created with :meth:`straight`, the polygon stores
        four corner vertices; the start point is the midpoint of vertices 0
        and 3 (the two corners at the original *start* end of the wall).
        Returns ``None`` for non-polygon geometry (arc, spline).
        """
        if not isinstance(self.geometry, Polygon2D):
            return None
        pts = self.geometry.exterior
        if len(pts) < 4:
            return None
        return (
            round((pts[0].x + pts[3].x) / 2, 6),
            round((pts[0].y + pts[3].y) / 2, 6),
        )

    @property
    def end_point(self) -> tuple[float, float] | None:
        """
        Approximate centre-line end point as ``(x, y)`` in metres.

        Mirrors :attr:`start_point` — uses vertices 1 and 2 of the polygon.
        Returns ``None`` for non-polygon geometry.
        """
        if not isinstance(self.geometry, Polygon2D):
            return None
        pts = self.geometry.exterior
        if len(pts) < 4:
            return None
        return (
            round((pts[1].x + pts[2].x) / 2, 6),
            round((pts[1].y + pts[2].y) / 2, 6),
        )

    def facing_direction(self) -> str:
        """
        Cardinal or intercardinal compass direction the wall *faces* (its outward normal).

        For straight polygon walls the normal is computed from the centre-line
        direction vector; for curve geometry the first tangent segment is used.
        Returns one of: ``"N"``, ``"NE"``, ``"E"``, ``"SE"``,
        ``"S"``, ``"SW"``, ``"W"``, ``"NW"``, or ``"unknown"``.
        """
        import math

        sp = self.start_point
        ep = self.end_point
        if sp is None or ep is None:
            return "unknown"

        dx = ep[0] - sp[0]
        dy = ep[1] - sp[1]
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1e-10:
            return "unknown"

        # Left-hand normal (same convention as Wall.straight factory)
        nx = -dy / length
        ny = dx / length

        # Convert to compass bearing: 0° = N (+Y), clockwise
        bearing = math.degrees(math.atan2(nx, ny)) % 360

        # Map to 8-point compass
        idx = round(bearing / 45) % 8
        return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][idx]

    def bounding_box(self) -> BoundingBox2D:
        if isinstance(self.geometry, Polygon2D):
            return self.geometry.bounding_box()
        # Convert curve to polyline and compute bbox
        pts = self.geometry.to_polyline()
        return BoundingBox2D.from_points(pts)

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_opening(self, opening: Opening) -> "Wall":
        """Return a new Wall with the given opening added."""
        return self.model_copy(update={"openings": (*self.openings, opening)})

    def remove_opening(self, opening_id) -> "Wall":
        """Return a new Wall without the opening matching the given id."""
        return self.model_copy(
            update={"openings": tuple(o for o in self.openings if o.id != opening_id)}
        )

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
        thickness: float = 0.2,
        height: float = 3.0,
        wall_type: WallType = WallType.INTERIOR,
        **kwargs,
    ) -> "Wall":
        """
        Create a straight wall from two endpoints.
        Builds a rectangular polygon offsetting by thickness/2 on each side.
        """
        import math

        from archit_app.geometry.crs import WORLD
        from archit_app.geometry.point import Point2D
        from archit_app.geometry.vector import Vector2D

        dx, dy = x2 - x1, y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1e-10:
            raise ValueError("Wall endpoints must not be the same point.")

        # Perpendicular unit vector (normal to wall)
        nx, ny = -dy / length, dx / length
        half = thickness / 2

        pts = (
            Point2D(x=x1 + nx * half, y=y1 + ny * half, crs=WORLD),
            Point2D(x=x2 + nx * half, y=y2 + ny * half, crs=WORLD),
            Point2D(x=x2 - nx * half, y=y2 - ny * half, crs=WORLD),
            Point2D(x=x1 - nx * half, y=y1 - ny * half, crs=WORLD),
        )
        geom = Polygon2D(exterior=pts, crs=WORLD)
        return cls(
            geometry=geom,
            thickness=thickness,
            height=height,
            wall_type=wall_type,
            **kwargs,
        )

    def __repr__(self) -> str:
        geom_type = type(self.geometry).__name__
        return (
            f"Wall(type={self.wall_type.value}, thickness={self.thickness}m, "
            f"height={self.height}m, geometry={geom_type}, "
            f"openings={len(self.openings)})"
        )
