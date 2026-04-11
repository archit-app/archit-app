"""
floorplan — A general-purpose, extensible floorplan library.

Quick start:
    from floorplan import Wall, Room, Level, Building, Point2D, Polygon2D, WORLD

Coordinate convention:
    - Internal unit: meters (float64)
    - Y direction: Y-up (architectural convention)
    - Screen/image layers are responsible for Y-flip
"""

from floorplan.geometry.crs import (
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
from floorplan.geometry.transform import Transform2D
from floorplan.geometry.vector import Vector2D, Vector3D
from floorplan.geometry.point import Point2D, Point3D
from floorplan.geometry.bbox import BoundingBox2D, BoundingBox3D
from floorplan.geometry.polygon import Polygon2D
from floorplan.geometry.curve import ArcCurve, BezierCurve, NURBSCurve, CurveBase

from floorplan.elements.base import Element
from floorplan.elements.opening import Opening, OpeningKind, SwingGeometry, Frame
from floorplan.elements.wall import Wall, WallType
from floorplan.elements.column import Column, ColumnShape
from floorplan.elements.room import Room

from floorplan.building.site import SiteContext
from floorplan.building.level import Level
from floorplan.building.building import Building, BuildingMetadata

from floorplan.core.registry import register, get, list_registered, get_all

__version__ = "0.1.0"

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
    # Elements
    "Element",
    "Opening",
    "OpeningKind",
    "SwingGeometry",
    "Frame",
    "Wall",
    "WallType",
    "Column",
    "ColumnShape",
    "Room",
    # Building
    "SiteContext",
    "Level",
    "Building",
    "BuildingMetadata",
    # Registry
    "register",
    "get",
    "list_registered",
    "get_all",
]
