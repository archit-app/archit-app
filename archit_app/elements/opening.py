"""
Openings: doors, windows, archways, pass-throughs.

Openings are punched into walls. They carry their own geometry (the hole shape)
and optional swing arcs (for doors) and frame details.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field, model_validator

from archit_app.elements.base import Element
from archit_app.geometry.curve import ArcCurve
from archit_app.geometry.polygon import Polygon2D


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
    """

    kind: OpeningKind
    geometry: Polygon2D
    width: float
    height: float
    sill_height: float = 0.0
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
