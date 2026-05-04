"""
Openings: doors, windows, archways, pass-throughs.

Openings are punched into walls. They carry their own geometry (the hole shape)
and optional swing arcs (for doors) and frame details.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Literal

from pydantic import model_validator

from archit_app.elements.base import Element
from archit_app.geometry.curve import ArcCurve
from archit_app.geometry.point import Point2D
from archit_app.geometry.polygon import Polygon2D

if TYPE_CHECKING:
    from archit_app.elements.wall import Wall


class OpeningKind(str, Enum):
    DOOR = "door"
    WINDOW = "window"
    ARCHWAY = "archway"
    PASS_THROUGH = "pass_through"


class SwingGeometry(Element):
    """Door swing arc geometry."""

    arc: ArcCurve
    side: Literal["left", "right"] = "left"


class Frame(Element):
    """Door or window frame details."""

    width: float = 0.05    # frame reveal width in meters
    depth: float = 0.0     # frame projection from wall face
    material: str | None = None


class Opening(Element):
    """
    An opening in a wall — door, window, archway, or pass-through.

    geometry: the shape of the hole cut in the wall (in wall-local coordinates)
    width:    nominal clear opening width in meters
    height:   nominal clear opening height in meters
    sill_height: distance from floor to bottom of opening (0.0 for doors)
    position_along_wall: fractional position along the wall centre line (0.0–1.0)
    """

    kind: OpeningKind
    geometry: Polygon2D
    width: float
    height: float
    sill_height: float = 0.0
    position_along_wall: float = 0.5
    swing: SwingGeometry | None = None
    frame: Frame | None = None

    @model_validator(mode="after")
    def _validate(self) -> "Opening":
        if self.width <= 0:
            raise ValueError(f"Opening width must be positive, got {self.width}.")
        if self.height <= 0:
            raise ValueError(f"Opening height must be positive, got {self.height}.")
        if self.sill_height < 0:
            raise ValueError(f"sill_height must be non-negative, got {self.sill_height}.")
        return self

    @classmethod
    def door(
        cls,
        x: float,
        y: float,
        width: float = 0.9,
        height: float = 2.1,
        wall_thickness: float = 0.2,
        **kwargs,
    ) -> "Opening":
        """
        Convenience factory for a simple rectangular door.
        x, y: position of the door's lower-left corner in world space.
        """
        from archit_app.geometry.crs import WORLD

        geom = Polygon2D.rectangle(x, y, width, wall_thickness, crs=WORLD)
        return cls(
            kind=OpeningKind.DOOR,
            geometry=geom,
            width=width,
            height=height,
            sill_height=0.0,
            **kwargs,
        )

    @classmethod
    def window(
        cls,
        x: float,
        y: float,
        width: float = 1.2,
        height: float = 1.2,
        sill_height: float = 0.9,
        wall_thickness: float = 0.2,
        **kwargs,
    ) -> "Opening":
        """Convenience factory for a simple rectangular window."""
        from archit_app.geometry.crs import WORLD

        geom = Polygon2D.rectangle(x, y, width, wall_thickness, crs=WORLD)
        return cls(
            kind=OpeningKind.WINDOW,
            geometry=geom,
            width=width,
            height=height,
            sill_height=sill_height,
            **kwargs,
        )

    @classmethod
    def archway(
        cls,
        x: float,
        y: float,
        width: float = 1.2,
        height: float = 2.4,
        wall_thickness: float = 0.2,
        **kwargs,
    ) -> "Opening":
        """
        Full-height arched opening (no door leaf, no sill).

        x, y: lower-left corner of the opening in world space.
        The geometry is a rectangular hole; the arched head is a semantic
        property expressed via OpeningKind.ARCHWAY.
        """
        from archit_app.geometry.crs import WORLD

        geom = Polygon2D.rectangle(x, y, width, wall_thickness, crs=WORLD)
        return cls(
            kind=OpeningKind.ARCHWAY,
            geometry=geom,
            width=width,
            height=height,
            sill_height=0.0,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Derived render geometry — used by SVG / PDF / DXF / IFC exporters
    # so each renderer agrees on swing arcs and glazing lines.
    # ------------------------------------------------------------------

    def swing_arc(
        self,
        host_wall: "Wall",
        hinge_side: Literal["left", "right", "auto"] = "auto",
        swing_into: Literal["interior", "exterior", "auto"] = "auto",
        segments: int = 16,
    ) -> list[Point2D] | None:
        """
        Approximate the door's swing arc as a polyline of points.

        Returns ``None`` for non-door openings (windows, skylights,
        archways, pass-throughs). Returns a list of ``segments + 1`` points
        starting at the hinge, sweeping through 90° and ending at the far
        corner of the leaf. Coordinates are in the same CRS as
        ``self.geometry``.

        - ``hinge_side``: ``"left"`` or ``"right"`` relative to the wall's
          start→end direction. ``"auto"`` defaults to ``"left"``.
        - ``swing_into``: ``"interior"`` / ``"exterior"`` / ``"auto"``.
          ``"auto"`` swings toward the wall's facing direction (left
          normal, matching :meth:`Wall.facing_direction`). For
          ``"exterior"`` the arc is mirrored across the wall.
        - ``segments``: number of arc segments (default 16 → 17 points).
        """
        import math

        if self.kind != OpeningKind.DOOR:
            return None
        if segments < 1:
            segments = 1

        start = host_wall.start_point
        end = host_wall.end_point
        if start is None or end is None:
            # Curve-based wall — no derivable hinge frame; bail gracefully.
            return None

        x1, y1 = start
        x2, y2 = end
        dx, dy = x2 - x1, y2 - y1
        wlen = math.sqrt(dx * dx + dy * dy)
        if wlen < 1e-10:
            return None

        ux, uy = dx / wlen, dy / wlen        # unit along wall (start→end)
        nx, ny = -uy, ux                      # left-hand normal (matches Wall.straight)

        # Hinge along the wall centre line, on the door's leading edge.
        cx = x1 + self.position_along_wall * dx
        cy = y1 + self.position_along_wall * dy
        hw = self.width / 2

        # Resolve hinge side. "auto" → "left" (door start corner).
        side = hinge_side if hinge_side in ("left", "right") else "left"
        if side == "left":
            hinge_x = cx - hw * ux
            hinge_y = cy - hw * uy
            # Leaf "closed" direction (initial radius vector) points along +u
            rx0, ry0 = ux, uy
        else:
            hinge_x = cx + hw * ux
            hinge_y = cy + hw * uy
            rx0, ry0 = -ux, -uy

        # Decide swing side. "auto" / "interior" → toward the left normal
        # (Wall.facing_direction's outward side is the same left normal,
        # so "interior" here means the side opposite the facing normal).
        # Per spec: "auto" → interior (toward the host room). We follow the
        # convention that the wall's facing_direction is exterior, so the
        # interior side is the *negative* normal.
        if swing_into == "exterior":
            side_sign = +1.0      # toward facing-direction (left normal)
        else:
            # "interior" or "auto"
            side_sign = -1.0      # opposite of facing-direction

        # Counterclockwise rotation of (rx0, ry0) by +theta is:
        #   x' = rx0 * cos - ry0 * sin
        #   y' = rx0 * sin + ry0 * cos
        # We want the arc to sweep from the closed position toward the
        # chosen swing side. The sign of theta picks the rotation direction
        # so the leaf ends up on side_sign * (nx, ny).
        # Cross product of (rx0, ry0) × (nx, ny) tells us which way is "toward
        # the normal":  z = rx0*ny - ry0*nx.  We want the rotated radius to
        # land on side_sign * normal, so pick the angle sign accordingly.
        cross_z = rx0 * ny - ry0 * nx
        theta_dir = 1.0 if (cross_z * side_sign) >= 0 else -1.0
        if abs(cross_z) < 1e-12:
            # Ambiguous — fall back to counterclockwise per spec.
            theta_dir = 1.0

        sweep = math.pi / 2  # 90°
        radius = self.width
        crs = self.geometry.crs

        pts: list[Point2D] = []
        for i in range(segments + 1):
            t = (i / segments) * sweep * theta_dir
            cos_t = math.cos(t)
            sin_t = math.sin(t)
            rx = rx0 * cos_t - ry0 * sin_t
            ry = rx0 * sin_t + ry0 * cos_t
            pts.append(
                Point2D(
                    x=hinge_x + radius * rx,
                    y=hinge_y + radius * ry,
                    crs=crs,
                )
            )
        return pts

    def glazing_lines(
        self,
        host_wall: "Wall",
    ) -> list[tuple[Point2D, Point2D]] | None:
        """
        Two parallel line segments representing a single-pane window's glass.

        Returns ``None`` for doors, archways, and pass-throughs (no glass).
        Each segment spans the opening's width along the wall direction,
        offset slightly inside the wall thickness so renderers can draw
        the canonical pair of glazing lines.

        Coordinates are in the same CRS as ``self.geometry``.
        """
        import math

        if self.kind != OpeningKind.WINDOW:
            return None

        start = host_wall.start_point
        end = host_wall.end_point
        if start is None or end is None:
            return None

        x1, y1 = start
        x2, y2 = end
        dx, dy = x2 - x1, y2 - y1
        wlen = math.sqrt(dx * dx + dy * dy)
        if wlen < 1e-10:
            return None

        ux, uy = dx / wlen, dy / wlen        # unit along wall
        nx, ny = -uy, ux                      # left-hand normal

        cx = x1 + self.position_along_wall * dx
        cy = y1 + self.position_along_wall * dy
        hw = self.width / 2

        # Offset glazing lines a small distance inside each wall face.
        # 1/6th of wall thickness leaves a clear frame band on either side.
        offset = host_wall.thickness / 6.0
        crs = self.geometry.crs

        # Two parallel lines, one on each side of the wall centre line.
        lines: list[tuple[Point2D, Point2D]] = []
        for side_sign in (+1.0, -1.0):
            ox = nx * offset * side_sign
            oy = ny * offset * side_sign
            p_start = Point2D(
                x=cx - hw * ux + ox,
                y=cy - hw * uy + oy,
                crs=crs,
            )
            p_end = Point2D(
                x=cx + hw * ux + ox,
                y=cy + hw * uy + oy,
                crs=crs,
            )
            lines.append((p_start, p_end))
        return lines

    @classmethod
    def pass_through(
        cls,
        x: float,
        y: float,
        width: float = 0.9,
        height: float = 1.0,
        sill_height: float = 0.85,
        wall_thickness: float = 0.2,
        **kwargs,
    ) -> "Opening":
        """
        Counter-height pass-through opening (no door leaf, raised sill).

        x, y: lower-left corner of the rough opening (at floor level).
        sill_height: height of the bottom of the opening above the floor
                     (default 0.85 m — standard counter height).
        """
        from archit_app.geometry.crs import WORLD

        geom = Polygon2D.rectangle(x, y, width, wall_thickness, crs=WORLD)
        return cls(
            kind=OpeningKind.PASS_THROUGH,
            geometry=geom,
            width=width,
            height=height,
            sill_height=sill_height,
            **kwargs,
        )
