"""
Level (floor) within a building.

A Level contains all architectural elements on a single horizontal plane.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from archit_app.elements.base import Element
from archit_app.elements.beam import Beam
from archit_app.elements.column import Column
from archit_app.elements.opening import Opening
from archit_app.elements.ramp import Ramp
from archit_app.elements.room import Room
from archit_app.elements.slab import Slab
from archit_app.elements.staircase import Staircase
from archit_app.elements.wall import Wall
from archit_app.geometry.bbox import BoundingBox2D


class Level(BaseModel):
    """
    A single storey/floor of a building.

    index:        floor number (0 = ground, negative = basement, positive = upper floors)
    elevation:    height of this floor's slab above site datum, in meters
    floor_height: floor-to-ceiling height in meters
    name:         human-readable label ("Ground Floor", "Level 2", etc.)
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    index: int
    elevation: float
    floor_height: float
    name: str = ""

    walls: tuple[Wall, ...] = ()
    rooms: tuple[Room, ...] = ()
    openings: tuple[Opening, ...] = ()
    columns: tuple[Column, ...] = ()
    staircases: tuple[Staircase, ...] = ()
    slabs: tuple[Slab, ...] = ()
    ramps: tuple[Ramp, ...] = ()
    beams: tuple[Beam, ...] = ()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_element_by_id(self, element_id: UUID) -> Element | None:
        for collection in (
            self.walls, self.rooms, self.openings, self.columns,
            self.staircases, self.slabs, self.ramps, self.beams,
        ):
            for el in collection:
                if el.id == element_id:
                    return el
        return None

    @property
    def bounding_box(self) -> BoundingBox2D | None:
        boxes = []
        for w in self.walls:
            boxes.append(w.bounding_box())
        for r in self.rooms:
            boxes.append(r.bounding_box())
        for c in self.columns:
            boxes.append(c.bounding_box())
        if not boxes:
            return None
        result = boxes[0]
        for bb in boxes[1:]:
            result = result.union(bb)
        return result

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_wall(self, wall: Wall) -> "Level":
        return self.model_copy(update={"walls": (*self.walls, wall)})

    def add_room(self, room: Room) -> "Level":
        return self.model_copy(update={"rooms": (*self.rooms, room)})

    def add_opening(self, opening: Opening) -> "Level":
        return self.model_copy(update={"openings": (*self.openings, opening)})

    def add_column(self, column: Column) -> "Level":
        return self.model_copy(update={"columns": (*self.columns, column)})

    def add_staircase(self, staircase: Staircase) -> "Level":
        return self.model_copy(update={"staircases": (*self.staircases, staircase)})

    def add_slab(self, slab: Slab) -> "Level":
        return self.model_copy(update={"slabs": (*self.slabs, slab)})

    def add_ramp(self, ramp: Ramp) -> "Level":
        return self.model_copy(update={"ramps": (*self.ramps, ramp)})

    def add_beam(self, beam: Beam) -> "Level":
        return self.model_copy(update={"beams": (*self.beams, beam)})

    def remove_element(self, element_id: UUID) -> "Level":
        return self.model_copy(
            update={
                "walls": tuple(w for w in self.walls if w.id != element_id),
                "rooms": tuple(r for r in self.rooms if r.id != element_id),
                "openings": tuple(o for o in self.openings if o.id != element_id),
                "columns": tuple(c for c in self.columns if c.id != element_id),
                "staircases": tuple(s for s in self.staircases if s.id != element_id),
                "slabs": tuple(s for s in self.slabs if s.id != element_id),
                "ramps": tuple(r for r in self.ramps if r.id != element_id),
                "beams": tuple(b for b in self.beams if b.id != element_id),
            }
        )

    def __repr__(self) -> str:
        return (
            f"Level(index={self.index}, elevation={self.elevation}m, "
            f"walls={len(self.walls)}, rooms={len(self.rooms)}, "
            f"columns={len(self.columns)})"
        )
