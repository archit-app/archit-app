"""
Canonical JSON serialization and deserialization for the floorplan package.

Format is designed to be:
  - Human-readable (pretty by default)
  - Fully round-trippable (serialize → deserialize → identical object graph)
  - Forward-compatible (version field for future migration)

Usage:
    from archit_app.io.json_schema import building_to_json, building_from_json

    json_str = building_to_json(my_building, indent=2)
    restored = building_from_json(json_str)
"""

from __future__ import annotations

import json
import math
from typing import Any
from uuid import UUID

from archit_app.building.building import Building, BuildingMetadata
from archit_app.building.level import Level
from archit_app.building.site import SiteContext
from archit_app.elements.column import Column, ColumnShape
from archit_app.elements.opening import Frame, Opening, OpeningKind, SwingGeometry
from archit_app.elements.room import Room
from archit_app.elements.wall import Wall, WallType
from archit_app.geometry.crs import (
    IMAGE,
    SCREEN,
    WORLD,
    WGS84,
    CoordinateSystem,
    LengthUnit,
    YDirection,
)
from archit_app.geometry.curve import ArcCurve, BezierCurve, NURBSCurve
from archit_app.geometry.point import Point2D
from archit_app.geometry.polygon import Polygon2D
from archit_app.geometry.transform import Transform2D

FORMAT_VERSION = "0.1.0"

# Known CRS singletons — serialized by name, looked up on deserialize
_CRS_SINGLETONS: dict[str, CoordinateSystem] = {
    "world": WORLD,
    "screen": SCREEN,
    "image": IMAGE,
    "geographic": WGS84,
}


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _ser_crs(crs: CoordinateSystem) -> str:
    return crs.name


def _des_crs(name: str) -> CoordinateSystem:
    if name in _CRS_SINGLETONS:
        return _CRS_SINGLETONS[name]
    # Custom CRS — store/restore full definition
    raise ValueError(
        f"Unknown CRS name {name!r}. "
        f"Known singletons: {list(_CRS_SINGLETONS.keys())}"
    )


def _ser_pt(p: Point2D) -> list[float]:
    return [p.x, p.y]


def _des_pt(data: list[float], crs: CoordinateSystem) -> Point2D:
    return Point2D(x=data[0], y=data[1], crs=crs)


def _ser_transform(t: Transform2D) -> list[list[float]]:
    return t.to_list()


def _des_transform(data: list[list[float]]) -> Transform2D:
    return Transform2D.from_list(data)


def _ser_polygon(poly: Polygon2D) -> dict[str, Any]:
    return {
        "type": "Polygon2D",
        "crs": _ser_crs(poly.crs),
        "exterior": [_ser_pt(p) for p in poly.exterior],
        "holes": [[_ser_pt(p) for p in h] for h in poly.holes],
    }


def _des_polygon(data: dict[str, Any]) -> Polygon2D:
    crs = _des_crs(data["crs"])
    exterior = tuple(_des_pt(p, crs) for p in data["exterior"])
    holes = tuple(tuple(_des_pt(p, crs) for p in h) for h in data.get("holes", []))
    return Polygon2D(exterior=exterior, holes=holes, crs=crs)


def _ser_geometry(geom) -> dict[str, Any]:
    """Serialize a wall geometry (Polygon2D or curve)."""
    if isinstance(geom, Polygon2D):
        return _ser_polygon(geom)
    if isinstance(geom, ArcCurve):
        return {
            "type": "ArcCurve",
            "crs": _ser_crs(geom.crs),
            "center": _ser_pt(geom.center),
            "radius": geom.radius,
            "start_angle": geom.start_angle,
            "end_angle": geom.end_angle,
            "clockwise": geom.clockwise,
        }
    if isinstance(geom, BezierCurve):
        return {
            "type": "BezierCurve",
            "crs": _ser_crs(geom.crs),
            "control_points": [_ser_pt(p) for p in geom.control_points],
        }
    if isinstance(geom, NURBSCurve):
        return {
            "type": "NURBSCurve",
            "crs": _ser_crs(geom.crs),
            "control_points": [_ser_pt(p) for p in geom.control_points],
            "weights": list(geom.weights),
            "knots": list(geom.knots),
            "degree": geom.degree,
        }
    raise TypeError(f"Cannot serialize geometry of type {type(geom).__name__}")


def _des_geometry(data: dict[str, Any]):
    """Deserialize a wall geometry."""
    kind = data["type"]
    crs = _des_crs(data["crs"])
    if kind == "Polygon2D":
        return _des_polygon(data)
    if kind == "ArcCurve":
        return ArcCurve(
            center=_des_pt(data["center"], crs),
            radius=data["radius"],
            start_angle=data["start_angle"],
            end_angle=data["end_angle"],
            clockwise=data.get("clockwise", False),
            crs=crs,
        )
    if kind == "BezierCurve":
        return BezierCurve(
            control_points=tuple(_des_pt(p, crs) for p in data["control_points"]),
            crs=crs,
        )
    if kind == "NURBSCurve":
        return NURBSCurve(
            control_points=tuple(_des_pt(p, crs) for p in data["control_points"]),
            weights=tuple(data["weights"]),
            knots=tuple(data["knots"]),
            degree=data["degree"],
            crs=crs,
        )
    raise ValueError(f"Unknown geometry type: {kind!r}")


def _base_fields(el) -> dict[str, Any]:
    """Serialize fields from the Element base class."""
    return {
        "id": str(el.id),
        "tags": el.tags,
        "layer": el.layer,
        "transform": _ser_transform(el.transform),
        "crs": _ser_crs(el.crs),
    }


def _des_base_kwargs(data: dict[str, Any]) -> dict[str, Any]:
    """Deserialize base Element kwargs."""
    from uuid import UUID

    return {
        "id": UUID(data["id"]),
        "tags": data.get("tags", {}),
        "layer": data.get("layer", "default"),
        "transform": _des_transform(data.get("transform", [[1,0,0],[0,1,0],[0,0,1]])),
        "crs": _des_crs(data.get("crs", "world")),
    }


# ---------------------------------------------------------------------------
# Element serializers
# ---------------------------------------------------------------------------


def _ser_frame(frame: Frame | None) -> dict[str, Any] | None:
    if frame is None:
        return None
    return {**_base_fields(frame), "width": frame.width, "depth": frame.depth, "material": frame.material}


def _des_frame(data: dict[str, Any] | None) -> Frame | None:
    if data is None:
        return None
    return Frame(width=data["width"], depth=data.get("depth", 0.0), material=data.get("material"), **_des_base_kwargs(data))


def _ser_swing(swing: SwingGeometry | None) -> dict[str, Any] | None:
    if swing is None:
        return None
    arc_data = _ser_geometry(swing.arc)
    return {**_base_fields(swing), "arc": arc_data, "side": swing.side}


def _des_swing(data: dict[str, Any] | None) -> SwingGeometry | None:
    if data is None:
        return None
    arc = _des_geometry(data["arc"])
    return SwingGeometry(arc=arc, side=data.get("side", "left"), **_des_base_kwargs(data))


def _ser_opening(o: Opening) -> dict[str, Any]:
    return {
        "type": "Opening",
        **_base_fields(o),
        "kind": o.kind.value,
        "geometry": _ser_polygon(o.geometry),
        "width": o.width,
        "height": o.height,
        "sill_height": o.sill_height,
        "swing": _ser_swing(o.swing),
        "frame": _ser_frame(o.frame),
    }


def _des_opening(data: dict[str, Any]) -> Opening:
    return Opening(
        kind=OpeningKind(data["kind"]),
        geometry=_des_polygon(data["geometry"]),
        width=data["width"],
        height=data["height"],
        sill_height=data.get("sill_height", 0.0),
        swing=_des_swing(data.get("swing")),
        frame=_des_frame(data.get("frame")),
        **_des_base_kwargs(data),
    )


def _ser_wall(w: Wall) -> dict[str, Any]:
    return {
        "type": "Wall",
        **_base_fields(w),
        "wall_type": w.wall_type.value,
        "thickness": w.thickness,
        "height": w.height,
        "material": w.material,
        "geometry": _ser_geometry(w.geometry),
        "openings": [_ser_opening(o) for o in w.openings],
    }


def _des_wall(data: dict[str, Any]) -> Wall:
    return Wall(
        wall_type=WallType(data.get("wall_type", "interior")),
        thickness=data["thickness"],
        height=data["height"],
        material=data.get("material"),
        geometry=_des_geometry(data["geometry"]),
        openings=tuple(_des_opening(o) for o in data.get("openings", [])),
        **_des_base_kwargs(data),
    )


def _ser_room(r: Room) -> dict[str, Any]:
    return {
        "type": "Room",
        **_base_fields(r),
        "name": r.name,
        "program": r.program,
        "level_index": r.level_index,
        "boundary": _ser_polygon(r.boundary),
        "holes": [_ser_polygon(h) for h in r.holes],
    }


def _des_room(data: dict[str, Any]) -> Room:
    return Room(
        name=data.get("name", ""),
        program=data.get("program", ""),
        level_index=data.get("level_index", 0),
        boundary=_des_polygon(data["boundary"]),
        holes=tuple(_des_polygon(h) for h in data.get("holes", [])),
        **_des_base_kwargs(data),
    )


def _ser_column(c: Column) -> dict[str, Any]:
    return {
        "type": "Column",
        **_base_fields(c),
        "shape": c.shape.value,
        "height": c.height,
        "material": c.material,
        "geometry": _ser_polygon(c.geometry),
    }


def _des_column(data: dict[str, Any]) -> Column:
    return Column(
        shape=ColumnShape(data.get("shape", "custom")),
        height=data["height"],
        material=data.get("material"),
        geometry=_des_polygon(data["geometry"]),
        **_des_base_kwargs(data),
    )


# ---------------------------------------------------------------------------
# Building / Level serializers
# ---------------------------------------------------------------------------


def _ser_level(lv: Level) -> dict[str, Any]:
    return {
        "index": lv.index,
        "elevation": lv.elevation,
        "floor_height": lv.floor_height,
        "name": lv.name,
        "walls": [_ser_wall(w) for w in lv.walls],
        "rooms": [_ser_room(r) for r in lv.rooms],
        "openings": [_ser_opening(o) for o in lv.openings],
        "columns": [_ser_column(c) for c in lv.columns],
    }


def _des_level(data: dict[str, Any]) -> Level:
    return Level(
        index=data["index"],
        elevation=data["elevation"],
        floor_height=data["floor_height"],
        name=data.get("name", ""),
        walls=tuple(_des_wall(w) for w in data.get("walls", [])),
        rooms=tuple(_des_room(r) for r in data.get("rooms", [])),
        openings=tuple(_des_opening(o) for o in data.get("openings", [])),
        columns=tuple(_des_column(c) for c in data.get("columns", [])),
    )


def _ser_site(site: SiteContext | None) -> dict[str, Any] | None:
    if site is None:
        return None
    return {
        "boundary": _ser_polygon(site.boundary) if site.boundary else None,
        "north_angle": site.north_angle,
        "address": site.address,
        "epsg_code": site.epsg_code,
    }


def _des_site(data: dict[str, Any] | None) -> SiteContext | None:
    if data is None:
        return None
    return SiteContext(
        boundary=_des_polygon(data["boundary"]) if data.get("boundary") else None,
        north_angle=data.get("north_angle", 0.0),
        address=data.get("address", ""),
        epsg_code=data.get("epsg_code"),
    )


def building_to_dict(building: Building) -> dict[str, Any]:
    """Convert a Building to a JSON-serializable dict."""
    return {
        "_archit_app_version": FORMAT_VERSION,
        "metadata": {
            "name": building.metadata.name,
            "project_number": building.metadata.project_number,
            "architect": building.metadata.architect,
            "client": building.metadata.client,
            "date": building.metadata.date,
        },
        "levels": [_ser_level(lv) for lv in building.levels],
        "site": _ser_site(building.site),
    }


def building_from_dict(data: dict[str, Any]) -> Building:
    """Reconstruct a Building from a dict (as produced by building_to_dict)."""
    meta = data.get("metadata", {})
    metadata = BuildingMetadata(
        name=meta.get("name", ""),
        project_number=meta.get("project_number", ""),
        architect=meta.get("architect", ""),
        client=meta.get("client", ""),
        date=meta.get("date", ""),
    )
    levels = tuple(_des_level(lv) for lv in data.get("levels", []))
    site = _des_site(data.get("site"))
    return Building(metadata=metadata, levels=levels, site=site)


# ---------------------------------------------------------------------------
# Top-level JSON string API
# ---------------------------------------------------------------------------


def building_to_json(building: Building, indent: int = 2) -> str:
    """Serialize a Building to a JSON string."""
    return json.dumps(building_to_dict(building), indent=indent, ensure_ascii=False)


def building_from_json(s: str) -> Building:
    """Deserialize a Building from a JSON string."""
    return building_from_dict(json.loads(s))


def save_building(building: Building, path: str, indent: int = 2) -> None:
    """Write a Building to a .archit_app.json file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(building_to_json(building, indent=indent))


def load_building(path: str) -> Building:
    """Read a Building from a .archit_app.json file."""
    with open(path, encoding="utf-8") as f:
        return building_from_json(f.read())
