"""
archit_app — A general-purpose, extensible floorplan library.

Quick start:
    from archit_app import Wall, Room, Level, Building, Point2D, Polygon2D, WORLD

Coordinate convention:
    - Internal unit: meters (float64)
    - Y direction: Y-up (architectural convention)
    - Screen/image layers are responsible for Y-flip
"""

from archit_app.geometry.crs import (
    CoordinateSystem,
    CRSMismatchError,
    LengthUnit,
    YDirection,
    WORLD,
    SCREEN,
    IMAGE,
    WGS84,
    require_same_crs,
)
from archit_app.geometry.transform import Transform2D
from archit_app.geometry.converter import CoordinateConverter, ConversionPathNotFoundError, build_default_converter
from archit_app.geometry.vector import Vector2D, Vector3D
from archit_app.geometry.point import Point2D, Point3D
from archit_app.geometry.bbox import BoundingBox2D, BoundingBox3D
from archit_app.geometry.polygon import Polygon2D
from archit_app.geometry.curve import ArcCurve, BezierCurve, NURBSCurve, CurveBase
from archit_app.geometry.primitives import Segment2D, Ray2D, Line2D, Polyline2D

from archit_app.elements.base import Element
from archit_app.elements.opening import Opening, OpeningKind, SwingGeometry, Frame
from archit_app.elements.wall import Wall, WallType
from archit_app.elements.wall_join import miter_join, butt_join, join_walls
from archit_app.elements.column import Column, ColumnShape
from archit_app.elements.room import Room
from archit_app.elements.staircase import Staircase, StaircaseType
from archit_app.elements.slab import Slab, SlabType
from archit_app.elements.ramp import Ramp, RampType
from archit_app.elements.elevator import Elevator, ElevatorDoor
from archit_app.elements.beam import Beam, BeamSection
from archit_app.elements.furniture import Furniture, FurnitureCategory
from archit_app.elements.annotation import TextAnnotation, DimensionLine, SectionMark
from archit_app.elements.material import Material, MaterialCategory, MaterialLibrary, default_library

from archit_app.building.land import Land, Setbacks, ZoningInfo
from archit_app.building.site import SiteContext
from archit_app.building.level import Level
from archit_app.building.building import (
    Building, BuildingMetadata, BuildingStats,
    ValidationIssue, ValidationReport,
)
from archit_app.building.layer import Layer
from archit_app.building.grid import StructuralGrid, GridAxis

from archit_app.history import History, HistoryError
from archit_app.viewport import Viewport
from archit_app.query import ElementQuery, query

from archit_app.core.registry import register, get, list_registered, get_all
from archit_app.core.errors import (
    ArchitError,
    OverlapError,
    OutOfBoundsError,
    ElementNotFoundError,
    GeometryError,
    SessionError,
)

from archit_app.units import (
    to_feet, to_inches, to_mm, to_cm,
    from_feet, from_inches, from_mm, from_cm,
    parse_dimension,
)

from archit_app.elements.transform_utils import (
    copy_element, mirror_element, array_element,
)

__version__ = "0.4.0"

__all__ = [
    # Geometry
    "CoordinateSystem",
    "CRSMismatchError",
    "LengthUnit",
    "YDirection",
    "WORLD",
    "SCREEN",
    "IMAGE",
    "WGS84",
    "require_same_crs",
    "Transform2D",
    "CoordinateConverter",
    "ConversionPathNotFoundError",
    "build_default_converter",
    "Vector2D",
    "Vector3D",
    "Point2D",
    "Point3D",
    "BoundingBox2D",
    "BoundingBox3D",
    "Polygon2D",
    "ArcCurve",
    "BezierCurve",
    "NURBSCurve",
    "CurveBase",
    "Segment2D",
    "Ray2D",
    "Line2D",
    "Polyline2D",
    # Elements
    "Element",
    "Opening",
    "OpeningKind",
    "SwingGeometry",
    "Frame",
    "Wall",
    "WallType",
    "miter_join",
    "butt_join",
    "join_walls",
    "Column",
    "ColumnShape",
    "Room",
    "Staircase",
    "StaircaseType",
    "Slab",
    "SlabType",
    "Ramp",
    "RampType",
    "Elevator",
    "ElevatorDoor",
    "Beam",
    "BeamSection",
    "Furniture",
    "FurnitureCategory",
    "TextAnnotation",
    "DimensionLine",
    "SectionMark",
    "Material",
    "MaterialCategory",
    "MaterialLibrary",
    "default_library",
    # Building / Land
    "Land",
    "Setbacks",
    "ZoningInfo",
    "SiteContext",
    "Level",
    "Building",
    "BuildingMetadata",
    "BuildingStats",
    "ValidationIssue",
    "ValidationReport",
    "Layer",
    "StructuralGrid",
    "GridAxis",
    # Application infrastructure
    "History",
    "HistoryError",
    "Viewport",
    "ElementQuery",
    "query",
    # Registry
    "register",
    "get",
    "list_registered",
    "get_all",
    # Errors
    "ArchitError",
    "OverlapError",
    "OutOfBoundsError",
    "ElementNotFoundError",
    "GeometryError",
    "SessionError",
    # Unit conversion
    "to_feet",
    "to_inches",
    "to_mm",
    "to_cm",
    "from_feet",
    "from_inches",
    "from_mm",
    "from_cm",
    "parse_dimension",
    # Element transforms
    "copy_element",
    "mirror_element",
    "array_element",
]
