"""
Furniture element.

Furniture items are represented by a plan-view footprint polygon plus
optional 3-D dimensions (width × depth × height).  The footprint is
sufficient for layout studies — collision detection, clearance checks,
and area budgets — without requiring a full 3-D model.

Typical usage::

    table = Furniture.dining_table(x=2.0, y=3.0)
    sofa  = Furniture.sofa(x=0.5, y=1.0)
    bed   = Furniture.bed_double(x=0.3, y=0.5)

    level = level.add_furniture(table).add_furniture(sofa).add_furniture(bed)

All factories place the piece with its **lower-left corner** at (x, y)
in world coordinates.  Rotate with ``element.with_transform(
Transform2D.rotate(angle))``.

Standard dimensions used in the factories are approximate mid-range
residential values; override via keyword arguments as needed.
"""

from __future__ import annotations

import math
from enum import Enum

from archit_app.elements.base import Element
from archit_app.geometry.crs import CoordinateSystem, WORLD
from archit_app.geometry.point import Point2D
from archit_app.geometry.polygon import Polygon2D


# ---------------------------------------------------------------------------
# Category enum
# ---------------------------------------------------------------------------

class FurnitureCategory(str, Enum):
    """Semantic category of a furniture piece."""

    SOFA            = "sofa"
    ARMCHAIR        = "armchair"
    DINING_CHAIR    = "dining_chair"
    OFFICE_CHAIR    = "office_chair"
    DINING_TABLE    = "dining_table"
    COFFEE_TABLE    = "coffee_table"
    DESK            = "desk"
    BED             = "bed"
    WARDROBE        = "wardrobe"
    DRESSER         = "dresser"
    BOOKSHELF       = "bookshelf"
    TV_UNIT         = "tv_unit"
    KITCHEN_COUNTER = "kitchen_counter"
    ISLAND          = "island"
    BATHTUB         = "bathtub"
    SHOWER          = "shower"
    TOILET          = "toilet"
    SINK            = "sink"
    WASHING_MACHINE = "washing_machine"
    CUSTOM          = "custom"


# ---------------------------------------------------------------------------
# Furniture element
# ---------------------------------------------------------------------------

class Furniture(Element):
    """
    A furniture item represented by a plan-view footprint polygon.

    Attributes:
        footprint:  Plan-view outline of the piece (in WORLD CRS, meters).
        label:      Human-readable name (e.g. "Dining Table", "Sofa").
        category:   Semantic category for rendering / analysis.
        width:      Nominal x-dimension of the piece in meters.
        depth:      Nominal y-dimension of the piece in meters.
        height:     Nominal z-dimension of the piece in meters (for 3-D use).
    """

    footprint: Polygon2D
    label: str = ""
    category: FurnitureCategory = FurnitureCategory.CUSTOM
    width: float = 0.0
    depth: float = 0.0
    height: float = 0.0

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def footprint_area(self) -> float:
        """Plan-view area of the footprint in m²."""
        return self.footprint.area

    def bounding_box(self):
        """Axis-aligned bounding box of the footprint."""
        return self.footprint.bounding_box()

    # ------------------------------------------------------------------
    # Generic factory
    # ------------------------------------------------------------------

    @classmethod
    def rectangular(
        cls,
        x: float,
        y: float,
        width: float,
        depth: float,
        *,
        height: float = 0.75,
        label: str = "",
        category: FurnitureCategory = FurnitureCategory.CUSTOM,
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """
        Create a rectangular furniture piece with the lower-left corner at (x, y).

        Parameters
        ----------
        x, y:       Lower-left corner position in meters.
        width:      Dimension along the x-axis in meters.
        depth:      Dimension along the y-axis in meters.
        height:     Vertical dimension in meters (default 0.75 m).
        label:      Display name.
        category:   Semantic category.
        crs:        Coordinate reference system (default WORLD).
        """
        footprint = Polygon2D.rectangle(x, y, width, depth, crs=crs)
        return cls(
            footprint=footprint,
            label=label,
            category=category,
            width=width,
            depth=depth,
            height=height,
            crs=crs,
            **kwargs,
        )

    @classmethod
    def _rect(
        cls,
        x: float,
        y: float,
        width: float,
        depth: float,
        height: float,
        label: str,
        category: FurnitureCategory,
        crs: CoordinateSystem,
        **kwargs,
    ) -> "Furniture":
        """Internal helper used by all named factories."""
        return cls.rectangular(
            x, y, width, depth,
            height=height, label=label, category=category, crs=crs,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Seating
    # ------------------------------------------------------------------

    @classmethod
    def sofa(
        cls,
        x: float,
        y: float,
        width: float = 2.2,
        depth: float = 0.9,
        *,
        height: float = 0.85,
        label: str = "Sofa",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """3-seat sofa, lower-left at (x, y). Default 2.2 × 0.9 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.SOFA, crs, **kwargs)

    @classmethod
    def armchair(
        cls,
        x: float,
        y: float,
        width: float = 0.85,
        depth: float = 0.85,
        *,
        height: float = 0.85,
        label: str = "Armchair",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Single armchair. Default 0.85 × 0.85 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.ARMCHAIR, crs, **kwargs)

    @classmethod
    def dining_chair(
        cls,
        x: float,
        y: float,
        width: float = 0.45,
        depth: float = 0.45,
        *,
        height: float = 0.90,
        label: str = "Dining Chair",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Dining chair. Default 0.45 × 0.45 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.DINING_CHAIR, crs, **kwargs)

    @classmethod
    def office_chair(
        cls,
        x: float,
        y: float,
        diameter: float = 0.65,
        *,
        height: float = 1.2,
        label: str = "Office Chair",
        resolution: int = 24,
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Office chair represented as a circle. Default ⌀ 0.65 m."""
        cx = x + diameter / 2
        cy = y + diameter / 2
        footprint = Polygon2D.circle(cx, cy, diameter / 2,
                                      resolution=resolution, crs=crs)
        return cls(
            footprint=footprint,
            label=label,
            category=FurnitureCategory.OFFICE_CHAIR,
            width=diameter,
            depth=diameter,
            height=height,
            crs=crs,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------

    @classmethod
    def dining_table(
        cls,
        x: float,
        y: float,
        width: float = 1.6,
        depth: float = 0.9,
        *,
        height: float = 0.75,
        label: str = "Dining Table",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Rectangular dining table. Default 1.6 × 0.9 m (seats 4–6)."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.DINING_TABLE, crs, **kwargs)

    @classmethod
    def coffee_table(
        cls,
        x: float,
        y: float,
        width: float = 1.1,
        depth: float = 0.55,
        *,
        height: float = 0.45,
        label: str = "Coffee Table",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Coffee/living-room table. Default 1.1 × 0.55 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.COFFEE_TABLE, crs, **kwargs)

    @classmethod
    def round_table(
        cls,
        x: float,
        y: float,
        diameter: float = 1.0,
        *,
        height: float = 0.75,
        label: str = "Round Table",
        resolution: int = 32,
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Circular table. (x, y) is the lower-left of the bounding square."""
        cx = x + diameter / 2
        cy = y + diameter / 2
        footprint = Polygon2D.circle(cx, cy, diameter / 2,
                                      resolution=resolution, crs=crs)
        return cls(
            footprint=footprint,
            label=label,
            category=FurnitureCategory.DINING_TABLE,
            width=diameter,
            depth=diameter,
            height=height,
            crs=crs,
            **kwargs,
        )

    @classmethod
    def desk(
        cls,
        x: float,
        y: float,
        width: float = 1.4,
        depth: float = 0.7,
        *,
        height: float = 0.75,
        label: str = "Desk",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Office/study desk. Default 1.4 × 0.7 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.DESK, crs, **kwargs)

    # ------------------------------------------------------------------
    # Bedroom
    # ------------------------------------------------------------------

    @classmethod
    def bed_single(
        cls,
        x: float,
        y: float,
        width: float = 0.9,
        depth: float = 2.0,
        *,
        height: float = 0.55,
        label: str = "Single Bed",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Single / twin bed. Default 0.9 × 2.0 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.BED, crs, **kwargs)

    @classmethod
    def bed_double(
        cls,
        x: float,
        y: float,
        width: float = 1.4,
        depth: float = 2.0,
        *,
        height: float = 0.55,
        label: str = "Double Bed",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Double / full bed. Default 1.4 × 2.0 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.BED, crs, **kwargs)

    @classmethod
    def bed_queen(
        cls,
        x: float,
        y: float,
        width: float = 1.6,
        depth: float = 2.0,
        *,
        height: float = 0.55,
        label: str = "Queen Bed",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Queen bed. Default 1.6 × 2.0 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.BED, crs, **kwargs)

    @classmethod
    def bed_king(
        cls,
        x: float,
        y: float,
        width: float = 1.8,
        depth: float = 2.0,
        *,
        height: float = 0.55,
        label: str = "King Bed",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """King bed. Default 1.8 × 2.0 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.BED, crs, **kwargs)

    @classmethod
    def wardrobe(
        cls,
        x: float,
        y: float,
        width: float = 1.8,
        depth: float = 0.6,
        *,
        height: float = 2.1,
        label: str = "Wardrobe",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Built-in / freestanding wardrobe. Default 1.8 × 0.6 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.WARDROBE, crs, **kwargs)

    # ------------------------------------------------------------------
    # Storage & living
    # ------------------------------------------------------------------

    @classmethod
    def bookshelf(
        cls,
        x: float,
        y: float,
        width: float = 0.8,
        depth: float = 0.3,
        *,
        height: float = 1.8,
        label: str = "Bookshelf",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Bookshelf / shelving unit. Default 0.8 × 0.3 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.BOOKSHELF, crs, **kwargs)

    @classmethod
    def tv_unit(
        cls,
        x: float,
        y: float,
        width: float = 1.8,
        depth: float = 0.45,
        *,
        height: float = 0.55,
        label: str = "TV Unit",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """TV cabinet / media unit. Default 1.8 × 0.45 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.TV_UNIT, crs, **kwargs)

    # ------------------------------------------------------------------
    # Kitchen
    # ------------------------------------------------------------------

    @classmethod
    def kitchen_counter(
        cls,
        x: float,
        y: float,
        width: float = 2.4,
        depth: float = 0.6,
        *,
        height: float = 0.9,
        label: str = "Kitchen Counter",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Kitchen worktop / base cabinet run. Default 2.4 × 0.6 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.KITCHEN_COUNTER, crs, **kwargs)

    @classmethod
    def kitchen_island(
        cls,
        x: float,
        y: float,
        width: float = 1.5,
        depth: float = 0.9,
        *,
        height: float = 0.9,
        label: str = "Kitchen Island",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Kitchen island. Default 1.5 × 0.9 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.ISLAND, crs, **kwargs)

    # ------------------------------------------------------------------
    # Bathroom
    # ------------------------------------------------------------------

    @classmethod
    def bathtub(
        cls,
        x: float,
        y: float,
        width: float = 1.7,
        depth: float = 0.75,
        *,
        height: float = 0.6,
        label: str = "Bathtub",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Standard bathtub. Default 1.7 × 0.75 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.BATHTUB, crs, **kwargs)

    @classmethod
    def shower(
        cls,
        x: float,
        y: float,
        width: float = 0.9,
        depth: float = 0.9,
        *,
        height: float = 2.1,
        label: str = "Shower",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Shower enclosure. Default 0.9 × 0.9 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.SHOWER, crs, **kwargs)

    @classmethod
    def toilet(
        cls,
        x: float,
        y: float,
        width: float = 0.38,
        depth: float = 0.65,
        *,
        height: float = 0.4,
        label: str = "Toilet",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Toilet / WC. Default 0.38 × 0.65 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.TOILET, crs, **kwargs)

    @classmethod
    def sink(
        cls,
        x: float,
        y: float,
        width: float = 0.6,
        depth: float = 0.45,
        *,
        height: float = 0.85,
        label: str = "Sink",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Bathroom / kitchen sink. Default 0.6 × 0.45 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.SINK, crs, **kwargs)

    @classmethod
    def washing_machine(
        cls,
        x: float,
        y: float,
        width: float = 0.6,
        depth: float = 0.6,
        *,
        height: float = 0.85,
        label: str = "Washing Machine",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "Furniture":
        """Washing machine / dryer. Default 0.6 × 0.6 m."""
        return cls._rect(x, y, width, depth, height, label,
                         FurnitureCategory.WASHING_MACHINE, crs, **kwargs)

    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        name = self.label or self.category.value
        return (
            f"Furniture({name!r}, "
            f"w={self.width:.2f}m × d={self.depth:.2f}m × h={self.height:.2f}m)"
        )
