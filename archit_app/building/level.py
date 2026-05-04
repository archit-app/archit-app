"""
Level (floor) within a building.

A Level contains all architectural elements on a single horizontal plane.
"""

from __future__ import annotations

import weakref
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

# Module-level Shapely cache, keyed weakly on Level instances.  When a Level is
# garbage-collected (which happens automatically after each immutable mutation
# produces a fresh instance), its cache entry is dropped — so cached polygons
# never outlive their owning Level and the cache is implicitly invalidated by
# the existing immutability semantics.
#
# Each value is a dict with two sub-dicts:
#   "rooms": {(room_id, tolerance_m): buffered_shapely_polygon}
#   "walls": {wall_id: shapely_box}
_SHAPELY_CACHE: "weakref.WeakKeyDictionary[Level, dict]" = weakref.WeakKeyDictionary()


def _level_shapely_cache(level: "Level") -> dict:
    """Return (creating if needed) the Shapely cache dict for *level*."""
    cache = _SHAPELY_CACHE.get(level)
    if cache is None:
        cache = {"rooms": {}, "walls": {}}
        _SHAPELY_CACHE[level] = cache
    return cache


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

        wall_cache: dict = _level_shapely_cache(self)["walls"]

        for coll in (
            self.walls, self.rooms, self.columns,
            self.beams, self.slabs, self.ramps, self.staircases, self.furniture,
        ):
            is_walls = coll is self.walls
            for el in coll:
                geom = wall_cache.get(el.id) if is_walls else None
                if geom is None:
                    bb = el.bounding_box()
                    if bb is None:
                        continue
                    geom = shp_box(
                        bb.min_corner.x, bb.min_corner.y,
                        bb.max_corner.x, bb.max_corner.y,
                    )
                    if is_walls:
                        wall_cache[el.id] = geom
                geometries.append(geom)
                elements.append(el)

        return STRtree(geometries), elements

    def walls_for_room(
        self,
        room_id: UUID,
        tolerance_m: float = 0.35,
        *,
        verbose: bool = False,
    ) -> list[Wall] | list[dict]:
        """Return the walls that form (or closely border) a room's boundary.

        Uses a Shapely buffered-intersection test: a wall is considered part of
        a room's boundary when its bounding box intersects the room polygon
        expanded by *tolerance_m* on all sides.  This handles walls that sit
        slightly outside the nominal room boundary due to wall thickness.

        Parameters
        ----------
        room_id:
            UUID of the room to query.
        tolerance_m:
            Expansion distance in metres applied to the room polygon before
            testing intersection (default 0.35 m — slightly larger than a
            standard 200 mm wall so both faces are captured).
        verbose:
            When ``False`` (default) return ``list[Wall]`` for backward
            compatibility.  When ``True`` return a list of records of the
            form ``{"wall": Wall, "intersection_area_m2": float,
            "distance_to_room_m": float}`` describing how each candidate
            relates to the room.  ``distance_to_room_m`` is measured against
            the *un-buffered* room polygon and is ``0.0`` for walls that
            actually intersect the room.

        Returns
        -------
        list[Wall] | list[dict]
            Walls (or verbose records) whose geometry intersects the expanded
            room boundary, sorted by wall type (exterior first) then by
            length descending.

        Raises
        ------
        KeyError
            If no room with *room_id* exists on this level.
        ImportError
            If Shapely is not installed.
        """
        try:
            from shapely.geometry import Polygon as ShpPolygon
            from shapely.geometry import box as shp_box
        except ImportError:
            raise ImportError(
                "Shapely is required for walls_for_room. "
                "Install it with: pip install shapely"
            )

        room = next((r for r in self.rooms if r.id == room_id), None)
        if room is None:
            raise KeyError(f"No room with id {room_id} on level {self.index}.")

        cache = _level_shapely_cache(self)
        room_cache: dict = cache["rooms"]
        wall_cache: dict = cache["walls"]

        # Build (or fetch) the un-buffered and buffered Shapely room polygons.
        # The un-buffered version is needed for distance/area in verbose mode.
        room_key_raw = (room.id, None)
        shp_room_raw = room_cache.get(room_key_raw)
        if shp_room_raw is None:
            pts = room.boundary.exterior
            shp_room_raw = ShpPolygon([(p.x, p.y) for p in pts])
            room_cache[room_key_raw] = shp_room_raw

        room_key_buf = (room.id, float(tolerance_m))
        shp_room = room_cache.get(room_key_buf)
        if shp_room is None:
            shp_room = shp_room_raw.buffer(tolerance_m)
            room_cache[room_key_buf] = shp_room

        from archit_app.elements.wall import WallType

        def _sort_key(w: Wall):
            order = {WallType.EXTERIOR: 0, WallType.CURTAIN: 1}.get(w.wall_type, 2)
            return (order, -w.length)

        if not verbose:
            result: list[Wall] = []
            for wall in self.walls:
                wall_box = wall_cache.get(wall.id)
                if wall_box is None:
                    bb = wall.bounding_box()
                    if bb is None:
                        continue
                    wall_box = shp_box(
                        bb.min_corner.x, bb.min_corner.y,
                        bb.max_corner.x, bb.max_corner.y,
                    )
                    wall_cache[wall.id] = wall_box
                if shp_room.intersects(wall_box):
                    result.append(wall)
            return sorted(result, key=_sort_key)

        # Verbose mode: compute intersection area and signed distance.
        records: list[dict] = []
        for wall in self.walls:
            wall_box = wall_cache.get(wall.id)
            if wall_box is None:
                bb = wall.bounding_box()
                if bb is None:
                    continue
                wall_box = shp_box(
                    bb.min_corner.x, bb.min_corner.y,
                    bb.max_corner.x, bb.max_corner.y,
                )
                wall_cache[wall.id] = wall_box
            if not shp_room.intersects(wall_box):
                continue
            try:
                inter_area = float(shp_room.intersection(wall_box).area)
            except Exception:
                inter_area = 0.0
            try:
                dist = float(shp_room_raw.distance(wall_box))
            except Exception:
                dist = 0.0
            records.append({
                "wall": wall,
                "intersection_area_m2": inter_area,
                "distance_to_room_m": dist,
            })

        records.sort(key=lambda rec: _sort_key(rec["wall"]))
        return records

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

    def add_walls(self, walls) -> "Level":
        """Add multiple walls in a single operation, returning one new Level.

        Parameters
        ----------
        walls:
            Any iterable of :class:`~archit_app.elements.wall.Wall` objects.

        Returns
        -------
        Level
            New Level with all *walls* appended in the order supplied.
        """
        new_walls = tuple(walls)
        return self.model_copy(update={"walls": (*self.walls, *new_walls)})

    def add_room(self, room: Room) -> "Level":
        return self.model_copy(update={"rooms": (*self.rooms, room)})

    def add_rooms(self, rooms) -> "Level":
        """Add multiple rooms in a single operation, returning one new Level.

        Parameters
        ----------
        rooms:
            Any iterable of :class:`~archit_app.elements.room.Room` objects.

        Returns
        -------
        Level
            New Level with all *rooms* appended in the order supplied.
        """
        new_rooms = tuple(rooms)
        return self.model_copy(update={"rooms": (*self.rooms, *new_rooms)})

    def add_opening(self, opening: Opening) -> "Level":
        return self.model_copy(update={"openings": (*self.openings, opening)})

    def add_openings(self, openings) -> "Level":
        """Add multiple openings in a single tuple rebuild."""
        new_openings = tuple(openings)
        return self.model_copy(
            update={"openings": (*self.openings, *new_openings)}
        )

    def add_column(self, column: Column) -> "Level":
        return self.model_copy(update={"columns": (*self.columns, column)})

    def add_columns(self, columns) -> "Level":
        """Add multiple columns in a single tuple rebuild."""
        new_columns = tuple(columns)
        return self.model_copy(
            update={"columns": (*self.columns, *new_columns)}
        )

    def add_staircase(self, staircase: Staircase) -> "Level":
        return self.model_copy(update={"staircases": (*self.staircases, staircase)})

    def add_staircases(self, staircases) -> "Level":
        """Add multiple staircases in a single tuple rebuild."""
        new_stairs = tuple(staircases)
        return self.model_copy(
            update={"staircases": (*self.staircases, *new_stairs)}
        )

    def add_slab(self, slab: Slab) -> "Level":
        return self.model_copy(update={"slabs": (*self.slabs, slab)})

    def add_slabs(self, slabs) -> "Level":
        """Add multiple slabs in a single tuple rebuild."""
        new_slabs = tuple(slabs)
        return self.model_copy(update={"slabs": (*self.slabs, *new_slabs)})

    def add_ramp(self, ramp: Ramp) -> "Level":
        return self.model_copy(update={"ramps": (*self.ramps, ramp)})

    def add_ramps(self, ramps) -> "Level":
        """Add multiple ramps in a single tuple rebuild."""
        new_ramps = tuple(ramps)
        return self.model_copy(update={"ramps": (*self.ramps, *new_ramps)})

    def add_beam(self, beam: Beam) -> "Level":
        return self.model_copy(update={"beams": (*self.beams, beam)})

    def add_beams(self, beams) -> "Level":
        """Add multiple beams in a single tuple rebuild."""
        new_beams = tuple(beams)
        return self.model_copy(update={"beams": (*self.beams, *new_beams)})

    def add_furniture(self, item: Furniture) -> "Level":
        return self.model_copy(update={"furniture": (*self.furniture, item)})

    def add_furniture_items(self, items) -> "Level":
        """Add multiple furniture items in a single tuple rebuild.

        Named ``add_furniture_items`` (rather than the plural ``add_furnitures``)
        because ``add_furniture`` is already used for the single-item form and
        "furniture" is a mass noun.
        """
        new_items = tuple(items)
        return self.model_copy(
            update={"furniture": (*self.furniture, *new_items)}
        )

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
