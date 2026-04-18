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
    land: Land | None = None
    elevators: tuple[Elevator, ...] = ()
    grid: StructuralGrid | None = None

    @property
    def site(self) -> Land | None:
        """Alias for ``land``.  Provided for backward compatibility."""
        return self.land

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

    def with_site(self, site: Land) -> "Building":
        """Set the site context.  Alias for ``with_land()``; kept for backward compatibility."""
        return self.model_copy(update={"land": site})

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

    def stats(self) -> "BuildingStats":
        """Return a structured summary of element counts and areas across all levels."""
        area_by_program: dict[str, float] = {}
        net_area = 0.0
        counts_by_level = []
        totals = dict(rooms=0, walls=0, openings=0, columns=0,
                      staircases=0, slabs=0, ramps=0, beams=0, furniture=0)

        for lv in self.levels:
            lv_net = sum(r.area for r in lv.rooms)
            net_area += lv_net
            for r in lv.rooms:
                area_by_program[r.program] = area_by_program.get(r.program, 0.0) + r.area
            lv_counts = {
                "level_index": lv.index,
                "rooms": len(lv.rooms),
                "walls": len(lv.walls),
                "openings": len(lv.openings),
                "columns": len(lv.columns),
                "staircases": len(lv.staircases),
                "slabs": len(lv.slabs),
                "ramps": len(lv.ramps),
                "beams": len(lv.beams),
                "furniture": len(lv.furniture),
                "net_area_m2": round(lv_net, 3),
            }
            counts_by_level.append(lv_counts)
            for k in totals:
                totals[k] += lv_counts.get(k, 0)

        return BuildingStats(
            total_levels=len(self.levels),
            total_rooms=totals["rooms"],
            total_walls=totals["walls"],
            total_openings=totals["openings"],
            total_columns=totals["columns"],
            total_furniture=totals["furniture"],
            gross_floor_area_m2=round(self.total_gross_area, 3),
            net_floor_area_m2=round(net_area, 3),
            area_by_program={k: round(v, 3) for k, v in area_by_program.items()},
            element_counts_by_level=counts_by_level,
        )

    def __repr__(self) -> str:
        return (
            f"Building(name={self.metadata.name!r}, "
            f"levels={len(self.levels)}, "
            f"gross_area={self.total_gross_area:.1f}m²)"
        )


class BuildingStats(BaseModel):
    """Structured summary of a building's element counts and areas."""

    model_config = ConfigDict(frozen=True)

    total_levels: int
    total_rooms: int
    total_walls: int
    total_openings: int
    total_columns: int
    total_furniture: int
    gross_floor_area_m2: float
    net_floor_area_m2: float
    area_by_program: dict[str, float]
    element_counts_by_level: list[dict]
