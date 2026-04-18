"""
Level (floor) within a building.

A Level contains all architectural elements on a single horizontal plane.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

from archit_app.elements.annotation import DimensionLine, SectionMark, TextAnnotation
from archit_app.elements.base import Element
from archit_app.elements.beam import Beam
from archit_app.elements.column import Column
from archit_app.elements.furniture import Furniture
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
    furniture: tuple[Furniture, ...] = ()
    text_annotations: tuple[TextAnnotation, ...] = ()
    dimensions: tuple[DimensionLine, ...] = ()
    section_marks: tuple[SectionMark, ...] = ()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_element_by_id(self, element_id: UUID) -> Element | None:
        for collection in (
            self.walls, self.rooms, self.openings, self.columns,
            self.staircases, self.slabs, self.ramps, self.beams,
            self.furniture, self.text_annotations, self.dimensions,
            self.section_marks,
        ):
            for el in collection:
                if el.id == element_id:
                    return el
        return None

    def spatial_index(self):
        """Build and return a Shapely STRtree over all spatially-aware elements.

        Elements must have a ``bounding_box()`` method (walls, rooms, columns,
        beams, slabs, ramps, staircases, furniture).  Annotation elements
        without a bounding box are excluded.

        Returns
        -------
        tuple[STRtree, list[Element]]
            A ``(tree, elements)`` pair where ``elements[i]`` corresponds to
            the *i*-th geometry in the STRtree.  Query the tree with Shapely
            geometry objects and use the returned indices to look up elements.

        Raises
        ------
        ImportError
            If Shapely is not installed.

        Example
        -------
        ::

            from shapely.geometry import box
            tree, elements = level.spatial_index()
            hits = tree.query(box(0, 0, 3, 3))
            nearby = [elements[i] for i in hits]
        """
        try:
            from shapely.geometry import box as shp_box
            from shapely.strtree import STRtree
        except ImportError:
            raise ImportError(
                "Shapely is required for spatial_index. "
                "Install it with: pip install shapely"
            )

        geometries = []
        elements = []

        for coll in (
            self.walls, self.rooms, self.columns,
            self.beams, self.slabs, self.ramps, self.staircases, self.furniture,
        ):
            for el in coll:
                bb = el.bounding_box()
                if bb is not None:
                    geometries.append(
                        shp_box(bb.min_corner.x, bb.min_corner.y,
                                bb.max_corner.x, bb.max_corner.y)
                    )
                    elements.append(el)

        return STRtree(geometries), elements

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

    def add_furniture(self, item: Furniture) -> "Level":
        return self.model_copy(update={"furniture": (*self.furniture, item)})

    def add_text_annotation(self, annotation: TextAnnotation) -> "Level":
        return self.model_copy(
            update={"text_annotations": (*self.text_annotations, annotation)}
        )

    def add_dimension(self, dimension: DimensionLine) -> "Level":
        return self.model_copy(update={"dimensions": (*self.dimensions, dimension)})

    def add_section_mark(self, mark: SectionMark) -> "Level":
        return self.model_copy(
            update={"section_marks": (*self.section_marks, mark)}
        )

    def replace_element(self, element_id: UUID, new_element: Element) -> "Level":
        """Return a new Level with the element replaced in-place (same position in its collection).

        Raises KeyError if no element with that id exists on this level.
        """
        found = False

        def _sub(coll: tuple, eid: UUID, replacement: Element) -> tuple:
            nonlocal found
            result = []
            for item in coll:
                if item.id == eid:
                    result.append(replacement)
                    found = True
                else:
                    result.append(item)
            return tuple(result)

        updated = self.model_copy(update={
            "walls": _sub(self.walls, element_id, new_element),
            "rooms": _sub(self.rooms, element_id, new_element),
            "openings": _sub(self.openings, element_id, new_element),
            "columns": _sub(self.columns, element_id, new_element),
            "staircases": _sub(self.staircases, element_id, new_element),
            "slabs": _sub(self.slabs, element_id, new_element),
            "ramps": _sub(self.ramps, element_id, new_element),
            "beams": _sub(self.beams, element_id, new_element),
            "furniture": _sub(self.furniture, element_id, new_element),
            "text_annotations": _sub(self.text_annotations, element_id, new_element),
            "dimensions": _sub(self.dimensions, element_id, new_element),
            "section_marks": _sub(self.section_marks, element_id, new_element),
        })
        if not found:
            raise KeyError(f"No element with id {element_id} found on level {self.index}.")
        return updated

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
                "furniture": tuple(f for f in self.furniture if f.id != element_id),
                "text_annotations": tuple(
                    a for a in self.text_annotations if a.id != element_id
                ),
                "dimensions": tuple(
                    d for d in self.dimensions if d.id != element_id
                ),
                "section_marks": tuple(
                    s for s in self.section_marks if s.id != element_id
                ),
            }
        )

    def duplicate(
        self,
        new_index: int,
        new_elevation: float,
        *,
        name: str = "",
        new_ids: bool = True,
    ) -> "Level":
        """Return a copy of this level at a different index and elevation.

        Parameters
        ----------
        new_index:
            Floor index for the duplicated level.
        new_elevation:
            Elevation (meters) of the duplicated level.
        name:
            Optional name for the new level.  Defaults to empty string.
        new_ids:
            When ``True`` (default) all elements in the copy receive fresh
            UUIDs so the two levels remain independent.  Set to ``False``
            only when you intentionally want shared identity.
        """
        def _fresh(element: Element) -> Element:
            if new_ids:
                return element.model_copy(update={"id": uuid4()})
            return element

        return self.model_copy(update={
            "index": new_index,
            "elevation": new_elevation,
            "name": name,
            "walls": tuple(_fresh(w) for w in self.walls),
            "rooms": tuple(_fresh(r) for r in self.rooms),
            "openings": tuple(_fresh(o) for o in self.openings),
            "columns": tuple(_fresh(c) for c in self.columns),
            "staircases": tuple(_fresh(s) for s in self.staircases),
            "slabs": tuple(_fresh(s) for s in self.slabs),
            "ramps": tuple(_fresh(r) for r in self.ramps),
            "beams": tuple(_fresh(b) for b in self.beams),
            "furniture": tuple(_fresh(f) for f in self.furniture),
            "text_annotations": tuple(_fresh(a) for a in self.text_annotations),
            "dimensions": tuple(_fresh(d) for d in self.dimensions),
            "section_marks": tuple(_fresh(s) for s in self.section_marks),
        })

    def __repr__(self) -> str:
        return (
            f"Level(index={self.index}, elevation={self.elevation}m, "
            f"walls={len(self.walls)}, rooms={len(self.rooms)}, "
            f"columns={len(self.columns)})"
        )
