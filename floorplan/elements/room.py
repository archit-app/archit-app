"""
Room element.

Rooms are the primary spatial unit of a floorplan. They are defined by a
boundary polygon and optional holes (for structural voids, columns, courtyards).
"""

from __future__ import annotations

from floorplan.elements.base import Element
from floorplan.geometry.point import Point2D
from floorplan.geometry.polygon import Polygon2D


class Room(Element):
    """
    A room or space in a floorplan.

    boundary:    outer boundary polygon (CCW orientation)
    holes:       voids within the room (columns, service shafts, courtyards)
    name:        human-readable name ("Living Room", "Bedroom 1", etc.)
    program:     space program type ("bedroom", "kitchen", "corridor", etc.)
    level_index: which Level this room belongs to (0 = ground floor)
    """

    boundary: Polygon2D
    holes: tuple[Polygon2D, ...] = ()
    name: str = ""
    program: str = ""
    level_index: int = 0

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def area(self) -> float:
        """Net floor area in m² (boundary area minus holes)."""
        base = self.boundary.area
        return base - sum(h.area for h in self.holes)

    @property
    def gross_area(self) -> float:
        """Gross floor area in m² (boundary area, ignoring holes)."""
        return self.boundary.area

    @property
    def perimeter(self) -> float:
        """Perimeter of the outer boundary in meters."""
        return self.boundary.perimeter

    @property
    def centroid(self) -> Point2D:
        """Centroid of the outer boundary."""
        return self.boundary.centroid

    def contains_point(self, p: Point2D) -> bool:
        """True if the point is inside the room (excluding holes)."""
        if not self.boundary.contains_point(p):
            return False
        return not any(h.contains_point(p) for h in self.holes)

    def bounding_box(self):
        return self.boundary.bounding_box()

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_hole(self, hole: Polygon2D) -> "Room":
        """Return a new Room with an additional void polygon."""
        return self.model_copy(update={"holes": (*self.holes, hole)})

    def with_name(self, name: str) -> "Room":
        return self.model_copy(update={"name": name})

    def with_program(self, program: str) -> "Room":
        return self.model_copy(update={"program": program})

    def __repr__(self) -> str:
        return (
            f"Room(name={self.name!r}, program={self.program!r}, "
            f"area={self.area:.2f}m², level={self.level_index})"
        )
