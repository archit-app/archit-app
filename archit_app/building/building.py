"""
Building — the top-level container.

A Building holds multiple Levels and optional site context.
It supports multi-storey buildings and high-rises by holding arbitrarily
many Level objects indexed by floor number.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from archit_app.building.grid import StructuralGrid
from archit_app.building.land import Land
from archit_app.building.level import Level
from archit_app.building.site import SiteContext
from archit_app.elements.base import Element
from archit_app.elements.elevator import Elevator


class BuildingMetadata(BaseModel):
    """Descriptive metadata for a building project."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    project_number: str = ""
    architect: str = ""
    client: str = ""
    date: str = ""   # ISO 8601 date string


class Building(BaseModel):
    """
    A complete building with one or more floors.

    levels are kept sorted by index at all times.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    metadata: BuildingMetadata = Field(default_factory=BuildingMetadata)
    levels: tuple[Level, ...] = ()
    site: SiteContext | None = None
    land: Land | None = None
    elevators: tuple[Elevator, ...] = ()
    grid: StructuralGrid | None = None

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_level(self, index: int) -> Level | None:
        return next((lv for lv in self.levels if lv.index == index), None)

    def get_element_by_id(self, element_id: UUID) -> Element | None:
        for level in self.levels:
            el = level.get_element_by_id(element_id)
            if el is not None:
                return el
        return None

    @property
    def total_floors(self) -> int:
        """Number of above-ground floors."""
        return len([lv for lv in self.levels if lv.index >= 0])

    @property
    def total_basements(self) -> int:
        return len([lv for lv in self.levels if lv.index < 0])

    @property
    def total_gross_area(self) -> float:
        """Total gross floor area across all levels in m²."""
        return sum(
            sum(r.gross_area for r in lv.rooms)
            for lv in self.levels
        )

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_level(self, level: Level) -> "Building":
        """Add or replace a level. Levels are kept sorted by index."""
        existing = [lv for lv in self.levels if lv.index != level.index]
        sorted_levels = tuple(sorted((*existing, level), key=lambda lv: lv.index))
        return self.model_copy(update={"levels": sorted_levels})

    def remove_level(self, index: int) -> "Building":
        return self.model_copy(
            update={"levels": tuple(lv for lv in self.levels if lv.index != index)}
        )

    def with_metadata(self, **kwargs) -> "Building":
        new_meta = self.metadata.model_copy(update=kwargs)
        return self.model_copy(update={"metadata": new_meta})

    def with_site(self, site: SiteContext) -> "Building":
        return self.model_copy(update={"site": site})

    def with_land(self, land: Land) -> "Building":
        return self.model_copy(update={"land": land})

    def add_elevator(self, elevator: Elevator) -> "Building":
        return self.model_copy(update={"elevators": (*self.elevators, elevator)})

    def remove_elevator(self, elevator_id) -> "Building":
        return self.model_copy(
            update={"elevators": tuple(e for e in self.elevators if e.id != elevator_id)}
        )

    def with_grid(self, grid: StructuralGrid) -> "Building":
        return self.model_copy(update={"grid": grid})

    def __repr__(self) -> str:
        return (
            f"Building(name={self.metadata.name!r}, "
            f"levels={len(self.levels)}, "
            f"gross_area={self.total_gross_area:.1f}m²)"
        )
