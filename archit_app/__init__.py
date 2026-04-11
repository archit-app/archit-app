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
from archit_app.geometry.vector import Vector2D, Vector3D
from archit_app.geometry.point import Point2D, Point3D
from archit_app.geometry.bbox import BoundingBox2D, BoundingBox3D
from archit_app.geometry.polygon import Polygon2D
from archit_app.geometry.curve import ArcCurve, BezierCurve, NURBSCurve, CurveBase

from archit_app.elements.base import Element
from archit_app.elements.opening import Opening, OpeningKind, SwingGeometry, Frame
from archit_app.elements.wall import Wall, WallType
from archit_app.elements.column import Column, ColumnShape
from archit_app.elements.room import Room

from archit_app.building.site import SiteContext
from archit_app.building.level import Level
from archit_app.building.building import Building, BuildingMetadata

from archit_app.core.registry import register, get, list_registered, get_all

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
