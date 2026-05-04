"""
Elevator element.

An elevator models a vertical transportation shaft spanning multiple levels,
including the cab dimensions and a door position per served level.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from archit_app.elements.base import Element
from archit_app.geometry.crs import WORLD, CoordinateSystem
from archit_app.geometry.point import Point2D
from archit_app.geometry.polygon import Polygon2D


class ElevatorDoor(BaseModel):
    """
    A door opening on the elevator shaft at a specific level.

    level_index: which floor this door serves
    position:    center point of the door on the shaft boundary (world space)
    width:       door clear width in meters
    direction:   door opening direction angle in radians (outward normal from shaft)
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    id: UUID = Field(default_factory=uuid4)
    level_index: int
    position: Point2D
    width: float = 0.9
    direction: float = 0.0

    @model_validator(mode="after")
    def _validate(self) -> "ElevatorDoor":
        if self.width <= 0:
            raise ValueError(f"Door width must be positive, got {self.width}.")
        return self


class Elevator(Element):
    """
    An elevator shaft spanning one or more levels.

    shaft:              footprint polygon of the shaft (world space)
    cab_width:          interior cab width in meters
    cab_depth:          interior cab depth in meters
    bottom_level_index: lowest level served
    top_level_index:    highest level served
    doors:              one ElevatorDoor per served level
    capacity_kg:        rated load capacity in kilograms (optional)
    material:           optional shaft material identifier
    """

    shaft: Polygon2D
    cab_width: float
    cab_depth: float
    bottom_level_index: int = 0
    top_level_index: int = 1
    doors: tuple[ElevatorDoor, ...] = ()
    capacity_kg: float | None = None
    material: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "Elevator":
        if self.cab_width <= 0:
            raise ValueError(f"cab_width must be positive, got {self.cab_width}.")
        if self.cab_depth <= 0:
            raise ValueError(f"cab_depth must be positive, got {self.cab_depth}.")
        if self.bottom_level_index >= self.top_level_index:
            raise ValueError(
                f"bottom_level_index ({self.bottom_level_index}) must be less than "
                f"top_level_index ({self.top_level_index})."
            )
        return self

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def shaft_area(self) -> float:
        """Gross shaft footprint area in m²."""
        return self.shaft.area

    @property
    def cab_area(self) -> float:
        """Interior cab floor area in m²."""
        return self.cab_width * self.cab_depth

    @property
    def levels_served(self) -> list[int]:
        """All level indices served by this elevator."""
        return list(range(self.bottom_level_index, self.top_level_index + 1))

    def bounding_box(self):
        return self.shaft.bounding_box()

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_door(self, door: ElevatorDoor) -> "Elevator":
        """Return a new Elevator with an additional door."""
        return self.model_copy(update={"doors": (*self.doors, door)})

    def remove_door(self, level_index: int) -> "Elevator":
        """Return a new Elevator with the door for the given level removed."""
        return self.model_copy(
            update={"doors": tuple(d for d in self.doors if d.level_index != level_index)}
        )

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def rectangular(
        cls,
        x: float,
        y: float,
        cab_width: float,
        cab_depth: float,
        shaft_clearance: float = 0.15,
        bottom_level_index: int = 0,
        top_level_index: int = 1,
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Elevator":
        """
        Create a rectangular elevator with a shaft that includes a clearance margin
        around the cab on all four sides.

        x, y:             lower-left corner of the shaft
        cab_width:        interior cab dimension in meters
        cab_depth:        interior cab dimension in meters
        shaft_clearance:  structural clearance on each side in meters (default 0.15 m)
        """
        shaft_w = cab_width + 2 * shaft_clearance
        shaft_d = cab_depth + 2 * shaft_clearance
        shaft = Polygon2D.rectangle(x, y, shaft_w, shaft_d, crs=crs)
        return cls(
            shaft=shaft,
            cab_width=cab_width,
            cab_depth=cab_depth,
            bottom_level_index=bottom_level_index,
            top_level_index=top_level_index,
            crs=crs,
            **kwargs,
        )

    def __repr__(self) -> str:
        return (
            f"Elevator(cab={self.cab_width}×{self.cab_depth}m, "
            f"levels={self.bottom_level_index}→{self.top_level_index}, "
            f"doors={len(self.doors)})"
        )
