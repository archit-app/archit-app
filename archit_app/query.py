"""
Element query / selection system.

Provides a fluent builder for filtering elements on a Level.

Usage::

    from archit_app.query import query

    # All walls on the structural layer
    walls = query(level).walls().on_layer("structural").list()

    # Rooms with program "bedroom" and area > 15 m²
    bedrooms = [
        r for r in query(level).rooms().with_program("bedroom").list()
        if r.area > 15.0
    ]

    # Any element tagged fire_rating=REI60 within a bounding box
    count = query(level).all().tagged("fire_rating", "REI60").within_bbox(zone_bb).count()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from archit_app.geometry.bbox import BoundingBox2D

if TYPE_CHECKING:
    from archit_app.building.level import Level
    from archit_app.elements.base import Element


_MISSING = object()  # sentinel for optional value argument in tagged()


class ElementQuery:
    """
    Fluent builder for filtering elements on a Level.

    Each method returns a new ElementQuery so calls can be chained.
    Terminal methods: ``.list()``, ``.first()``, ``.count()``.
    """

    def __init__(self, elements: list["Element"]) -> None:
        self._elements = elements

    # ------------------------------------------------------------------
    # Type filters
    # ------------------------------------------------------------------

    def _filter_type(self, *types: type) -> "ElementQuery":
        return ElementQuery([e for e in self._elements if isinstance(e, types)])

    def walls(self) -> "ElementQuery":
        from archit_app.elements.wall import Wall
        return self._filter_type(Wall)

    def rooms(self) -> "ElementQuery":
        from archit_app.elements.room import Room
        return self._filter_type(Room)

    def openings(self) -> "ElementQuery":
        from archit_app.elements.opening import Opening
        return self._filter_type(Opening)

    def columns(self) -> "ElementQuery":
        from archit_app.elements.column import Column
        return self._filter_type(Column)

    def staircases(self) -> "ElementQuery":
        from archit_app.elements.staircase import Staircase
        return self._filter_type(Staircase)

    def slabs(self) -> "ElementQuery":
        from archit_app.elements.slab import Slab
        return self._filter_type(Slab)

    def ramps(self) -> "ElementQuery":
        from archit_app.elements.ramp import Ramp
        return self._filter_type(Ramp)

    def beams(self) -> "ElementQuery":
        from archit_app.elements.beam import Beam
        return self._filter_type(Beam)

    def furniture(self) -> "ElementQuery":
        from archit_app.elements.furniture import Furniture
        return self._filter_type(Furniture)

    def text_annotations(self) -> "ElementQuery":
        from archit_app.elements.annotation import TextAnnotation
        return self._filter_type(TextAnnotation)

    def dimensions(self) -> "ElementQuery":
        from archit_app.elements.annotation import DimensionLine
        return self._filter_type(DimensionLine)

    def section_marks(self) -> "ElementQuery":
        from archit_app.elements.annotation import SectionMark
        return self._filter_type(SectionMark)

    def all(self) -> "ElementQuery":
        """No type filter — keep every element."""
        return ElementQuery(list(self._elements))

    # ------------------------------------------------------------------
    # Attribute filters
    # ------------------------------------------------------------------

    def on_layer(self, layer: str) -> "ElementQuery":
        """Keep elements whose ``layer`` field equals ``layer``."""
        return ElementQuery([e for e in self._elements if e.layer == layer])

    def tagged(self, key: str, value: Any = _MISSING) -> "ElementQuery":
        """
        Keep elements that have a tag with ``key``.

        If ``value`` is also given, only keep elements where ``tags[key] == value``.
        """
        if value is _MISSING:
            return ElementQuery([e for e in self._elements if key in e.tags])
        return ElementQuery([
            e for e in self._elements if e.tags.get(key) == value
        ])

    def with_program(self, program: str) -> "ElementQuery":
        """Keep Room elements with the given program string.

        Non-Room elements in the pool are silently dropped.
        """
        from archit_app.elements.room import Room
        return ElementQuery([
            e for e in self._elements
            if isinstance(e, Room) and e.program == program
        ])

    def within_bbox(self, bbox: BoundingBox2D) -> "ElementQuery":
        """
        Keep elements whose bounding box overlaps ``bbox``.

        Elements without a ``bounding_box()`` method are kept unconditionally
        (they cannot be excluded spatially).
        """
        result = []
        for e in self._elements:
            try:
                ebb = e.bounding_box()
                if ebb is not None and bbox.intersects(ebb):
                    result.append(e)
                elif ebb is None:
                    result.append(e)
            except AttributeError:
                result.append(e)
        return ElementQuery(result)

    def with_id(self, element_id: UUID) -> "ElementQuery":
        """Keep the element with the given UUID (at most one result)."""
        return ElementQuery([e for e in self._elements if e.id == element_id])

    # ------------------------------------------------------------------
    # Terminal methods
    # ------------------------------------------------------------------

    def list(self) -> list["Element"]:
        """Return all matching elements as a list."""
        return list(self._elements)

    def first(self) -> "Element | None":
        """Return the first matching element, or None if there are none."""
        return self._elements[0] if self._elements else None

    def count(self) -> int:
        """Return the number of matching elements."""
        return len(self._elements)

    def __repr__(self) -> str:
        return f"ElementQuery({len(self._elements)} elements)"


def query(level: "Level") -> ElementQuery:
    """
    Return an ElementQuery seeded with *all* elements on ``level``.

    Example::

        walls = query(level).walls().on_layer("structural").list()
    """
    elements: list[Element] = []
    for collection in (
        level.walls, level.rooms, level.openings, level.columns,
        level.staircases, level.slabs, level.ramps, level.beams,
        level.furniture, level.text_annotations, level.dimensions,
        level.section_marks,
    ):
        elements.extend(collection)
    return ElementQuery(elements)
