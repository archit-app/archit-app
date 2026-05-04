"""
Slab element.

A slab represents the structural floor or ceiling plate of a level.
It is distinct from Room boundaries: a Room models usable space,
a Slab models the concrete/structural deck.
"""

from __future__ import annotations

from enum import Enum

from pydantic import model_validator

from archit_app.elements.base import Element
from archit_app.geometry.crs import WORLD, CoordinateSystem
from archit_app.geometry.polygon import Polygon2D


class SlabType(str, Enum):
    FLOOR = "floor"
    CEILING = "ceiling"
    ROOF = "roof"


class Slab(Element):
    """
    A structural slab (floor deck, ceiling, or roof plate).

    boundary:    outer outline polygon of the slab
    holes:       penetrations through the slab (shafts, voids, openings)
    thickness:   slab thickness in meters
    elevation:   absolute elevation of the slab's top surface in meters
    slab_type:   FLOOR, CEILING, or ROOF
    level_index: index of the Level this slab belongs to
    material:    optional material identifier
    """

    boundary: Polygon2D
    holes: tuple[Polygon2D, ...] = ()
    thickness: float
    elevation: float
    slab_type: SlabType = SlabType.FLOOR
    level_index: int = 0
    material: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "Slab":
        if self.thickness <= 0:
            raise ValueError(f"Slab thickness must be positive, got {self.thickness}.")
        return self

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def area(self) -> float:
        """Net slab area in m² (boundary minus holes)."""
        return self.boundary.area - sum(h.area for h in self.holes)

    @property
    def gross_area(self) -> float:
        """Gross slab area in m² (boundary only, ignoring holes)."""
        return self.boundary.area

    @property
    def perimeter(self) -> float:
        """Perimeter of the outer boundary in meters."""
        return self.boundary.perimeter

    def bounding_box(self):
        return self.boundary.bounding_box()

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_hole(self, hole: Polygon2D) -> "Slab":
        """Return a new Slab with an additional penetration polygon."""
        return self.model_copy(update={"holes": (*self.holes, hole)})

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
        thickness: float = 0.25,
        elevation: float = 0.0,
        slab_type: SlabType = SlabType.FLOOR,
        level_index: int = 0,
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Slab":
        """Create an axis-aligned rectangular slab."""
        boundary = Polygon2D.rectangle(x, y, width, depth, crs=crs)
        return cls(
            boundary=boundary,
            thickness=thickness,
            elevation=elevation,
            slab_type=slab_type,
            level_index=level_index,
            crs=crs,
            **kwargs,
        )

    def __repr__(self) -> str:
        return (
            f"Slab(type={self.slab_type.value}, area={self.area:.2f}m², "
            f"thickness={self.thickness}m, elevation={self.elevation}m)"
        )
