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
from archit_app.building.grid import GridAxis, StructuralGrid
from archit_app.building.land import Land
from archit_app.building.level import Level
from archit_app.elements.annotation import DimensionLine, SectionMark, TextAnnotation
from archit_app.elements.beam import Beam, BeamSection
from archit_app.elements.column import Column, ColumnShape
from archit_app.elements.elevator import Elevator, ElevatorDoor
from archit_app.elements.furniture import Furniture, FurnitureCategory
from archit_app.elements.opening import Frame, Opening, OpeningKind, SwingGeometry
from archit_app.elements.ramp import Ramp, RampType
from archit_app.elements.room import Room
from archit_app.elements.slab import Slab, SlabType
from archit_app.elements.staircase import Staircase, StaircaseType
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

FORMAT_VERSION = "0.3.0"
PREVIOUS_VERSIONS = ("0.1.0", "0.2.0")   # versions we can migrate from

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


def _ser_staircase(s: Staircase) -> dict[str, Any]:
    return {
        "type": "Staircase", **_base_fields(s),
        "boundary": _ser_polygon(s.boundary),
        "rise_count": s.rise_count, "rise_height": s.rise_height,
        "run_depth": s.run_depth, "width": s.width,
        "stair_type": s.stair_type.value, "direction": s.direction,
        "bottom_level_index": s.bottom_level_index, "top_level_index": s.top_level_index,
        "has_landing": s.has_landing, "nosing": s.nosing, "material": s.material,
    }


def _des_staircase(data: dict[str, Any]) -> Staircase:
    return Staircase(
        boundary=_des_polygon(data["boundary"]),
        rise_count=data["rise_count"], rise_height=data["rise_height"],
        run_depth=data["run_depth"], width=data["width"],
        stair_type=StaircaseType(data.get("stair_type", "straight")),
        direction=data.get("direction", 0.0),
        bottom_level_index=data.get("bottom_level_index", 0),
        top_level_index=data.get("top_level_index", 1),
        has_landing=data.get("has_landing", False), nosing=data.get("nosing", 0.02),
        material=data.get("material"), **_des_base_kwargs(data),
    )


def _ser_slab(s: Slab) -> dict[str, Any]:
    return {
        "type": "Slab", **_base_fields(s),
        "boundary": _ser_polygon(s.boundary),
        "holes": [_ser_polygon(h) for h in s.holes],
        "thickness": s.thickness, "elevation": s.elevation,
        "slab_type": s.slab_type.value, "level_index": s.level_index,
        "material": s.material,
    }


def _des_slab(data: dict[str, Any]) -> Slab:
    return Slab(
        boundary=_des_polygon(data["boundary"]),
        holes=tuple(_des_polygon(h) for h in data.get("holes", [])),
        thickness=data["thickness"], elevation=data["elevation"],
        slab_type=SlabType(data.get("slab_type", "floor")),
        level_index=data.get("level_index", 0),
        material=data.get("material"), **_des_base_kwargs(data),
    )


def _ser_beam(b: Beam) -> dict[str, Any]:
    return {
        "type": "Beam", **_base_fields(b),
        "geometry": _ser_polygon(b.geometry),
        "width": b.width, "depth": b.depth, "elevation": b.elevation,
        "section": b.section.value, "level_index": b.level_index,
        "material": b.material,
    }


def _des_beam(data: dict[str, Any]) -> Beam:
    return Beam(
        geometry=_des_polygon(data["geometry"]),
        width=data["width"], depth=data["depth"], elevation=data["elevation"],
        section=BeamSection(data.get("section", "rectangular")),
        level_index=data.get("level_index", 0),
        material=data.get("material"), **_des_base_kwargs(data),
    )


def _ser_ramp(r: Ramp) -> dict[str, Any]:
    return {
        "type": "Ramp", **_base_fields(r),
        "boundary": _ser_polygon(r.boundary),
        "width": r.width, "slope_angle": r.slope_angle,
        "direction": r.direction,
        "bottom_level_index": r.bottom_level_index,
        "top_level_index": r.top_level_index,
        "ramp_type": r.ramp_type.value,
        "has_landing": r.has_landing, "material": r.material,
    }


def _des_ramp(data: dict[str, Any]) -> Ramp:
    return Ramp(
        boundary=_des_polygon(data["boundary"]),
        width=data["width"], slope_angle=data["slope_angle"],
        direction=data.get("direction", 0.0),
        bottom_level_index=data.get("bottom_level_index", 0),
        top_level_index=data.get("top_level_index", 1),
        ramp_type=RampType(data.get("ramp_type", "straight")),
        has_landing=data.get("has_landing", False),
        material=data.get("material"), **_des_base_kwargs(data),
    )


def _ser_furniture(f: Furniture) -> dict[str, Any]:
    return {
        "type": "Furniture", **_base_fields(f),
        "footprint": _ser_polygon(f.footprint),
        "label": f.label, "category": f.category.value,
        "width": f.width, "depth": f.depth, "height": f.height,
    }


def _des_furniture(data: dict[str, Any]) -> Furniture:
    return Furniture(
        footprint=_des_polygon(data["footprint"]),
        label=data.get("label", ""),
        category=FurnitureCategory(data.get("category", "custom")),
        width=data.get("width", 0.0), depth=data.get("depth", 0.0),
        height=data.get("height", 0.0), **_des_base_kwargs(data),
    )


def _ser_text_annotation(a: TextAnnotation) -> dict[str, Any]:
    return {
        "type": "TextAnnotation", **_base_fields(a),
        "position": _ser_pt(a.position),
        "text": a.text, "rotation": a.rotation,
        "size": a.size, "anchor": a.anchor,
    }


def _des_text_annotation(data: dict[str, Any]) -> TextAnnotation:
    crs = _des_crs(data.get("crs", "world"))
    return TextAnnotation(
        position=_des_pt(data["position"], crs),
        text=data["text"], rotation=data.get("rotation", 0.0),
        size=data.get("size", 0.25), anchor=data.get("anchor", "center"),
        **_des_base_kwargs(data),
    )


def _ser_dimension(d: DimensionLine) -> dict[str, Any]:
    return {
        "type": "DimensionLine", **_base_fields(d),
        "start": _ser_pt(d.start), "end": _ser_pt(d.end),
        "offset": d.offset, "label_override": d.label_override,
        "decimal_places": d.decimal_places, "unit_suffix": d.unit_suffix,
    }


def _des_dimension(data: dict[str, Any]) -> DimensionLine:
    crs = _des_crs(data.get("crs", "world"))
    return DimensionLine(
        start=_des_pt(data["start"], crs), end=_des_pt(data["end"], crs),
        offset=data.get("offset", 0.5),
        label_override=data.get("label_override", ""),
        decimal_places=data.get("decimal_places", 2),
        unit_suffix=data.get("unit_suffix", "m"),
        **_des_base_kwargs(data),
    )


def _ser_section_mark(m: SectionMark) -> dict[str, Any]:
    return {
        "type": "SectionMark", **_base_fields(m),
        "start": _ser_pt(m.start), "end": _ser_pt(m.end),
        "tag": m.tag, "view_direction": m.view_direction,
        "reference": m.reference,
    }


def _des_section_mark(data: dict[str, Any]) -> SectionMark:
    crs = _des_crs(data.get("crs", "world"))
    return SectionMark(
        start=_des_pt(data["start"], crs), end=_des_pt(data["end"], crs),
        tag=data.get("tag", "A"),
        view_direction=data.get("view_direction", "left"),
        reference=data.get("reference", ""),
        **_des_base_kwargs(data),
    )


def _ser_elevator_door(d: ElevatorDoor) -> dict[str, Any]:
    return {
        "id": str(d.id),
        "level_index": d.level_index,
        "position": _ser_pt(d.position),
        "crs": _ser_crs(d.position.crs),
        "width": d.width, "direction": d.direction,
    }


def _des_elevator_door(data: dict[str, Any]) -> ElevatorDoor:
    crs = _des_crs(data.get("crs", "world"))
    return ElevatorDoor(
        id=UUID(data["id"]),
        level_index=data["level_index"],
        position=_des_pt(data["position"], crs),
        width=data.get("width", 0.9),
        direction=data.get("direction", 0.0),
    )


def _ser_elevator(e: Elevator) -> dict[str, Any]:
    return {
        "type": "Elevator", **_base_fields(e),
        "shaft": _ser_polygon(e.shaft),
        "cab_width": e.cab_width, "cab_depth": e.cab_depth,
        "bottom_level_index": e.bottom_level_index,
        "top_level_index": e.top_level_index,
        "doors": [_ser_elevator_door(d) for d in e.doors],
        "capacity_kg": e.capacity_kg, "material": e.material,
    }


def _des_elevator(data: dict[str, Any]) -> Elevator:
    return Elevator(
        shaft=_des_polygon(data["shaft"]),
        cab_width=data["cab_width"], cab_depth=data["cab_depth"],
        bottom_level_index=data.get("bottom_level_index", 0),
        top_level_index=data.get("top_level_index", 1),
        doors=tuple(_des_elevator_door(d) for d in data.get("doors", [])),
        capacity_kg=data.get("capacity_kg"), material=data.get("material"),
        **_des_base_kwargs(data),
    )


def _ser_grid_axis(ax: GridAxis) -> dict[str, Any]:
    return {
        "name": ax.name,
        "start": _ser_pt(ax.start),
        "end": _ser_pt(ax.end),
        "crs": _ser_crs(ax.start.crs),
    }


def _des_grid_axis(data: dict[str, Any]) -> GridAxis:
    crs = _des_crs(data.get("crs", "world"))
    return GridAxis(name=data["name"], start=_des_pt(data["start"], crs), end=_des_pt(data["end"], crs))


def _ser_grid(grid: StructuralGrid | None) -> dict[str, Any] | None:
    if grid is None:
        return None
    return {
        "x_axes": [_ser_grid_axis(ax) for ax in grid.x_axes],
        "y_axes": [_ser_grid_axis(ax) for ax in grid.y_axes],
    }


def _des_grid(data: dict[str, Any] | None) -> StructuralGrid | None:
    if data is None:
        return None
    return StructuralGrid(
        x_axes=tuple(_des_grid_axis(ax) for ax in data.get("x_axes", [])),
        y_axes=tuple(_des_grid_axis(ax) for ax in data.get("y_axes", [])),
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
        "staircases": [_ser_staircase(s) for s in lv.staircases],
        "slabs": [_ser_slab(s) for s in lv.slabs],
        "ramps": [_ser_ramp(r) for r in lv.ramps],
        "beams": [_ser_beam(b) for b in lv.beams],
        "furniture": [_ser_furniture(f) for f in lv.furniture],
        "text_annotations": [_ser_text_annotation(a) for a in lv.text_annotations],
        "dimensions": [_ser_dimension(d) for d in lv.dimensions],
        "section_marks": [_ser_section_mark(m) for m in lv.section_marks],
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
        staircases=tuple(_des_staircase(s) for s in data.get("staircases", [])),
        slabs=tuple(_des_slab(s) for s in data.get("slabs", [])),
        ramps=tuple(_des_ramp(r) for r in data.get("ramps", [])),
        beams=tuple(_des_beam(b) for b in data.get("beams", [])),
        furniture=tuple(_des_furniture(f) for f in data.get("furniture", [])),
        text_annotations=tuple(_des_text_annotation(a) for a in data.get("text_annotations", [])),
        dimensions=tuple(_des_dimension(d) for d in data.get("dimensions", [])),
        section_marks=tuple(_des_section_mark(m) for m in data.get("section_marks", [])),
    )


def _ser_land(land: Land | None) -> dict[str, Any] | None:
    """Serialize a Land (or None) to a JSON-serialisable dict."""
    if land is None:
        return None
    d: dict[str, Any] = {
        "boundary": _ser_polygon(land.boundary) if land.boundary is not None else None,
        "north_angle": land.north_angle,
        "address": land.address,
        "epsg_code": land.epsg_code,
        "elevation_m": land.elevation_m,
        "setbacks": {
            "front": land.setbacks.front,
            "back": land.setbacks.back,
            "left": land.setbacks.left,
            "right": land.setbacks.right,
        },
    }
    if land.latlon_coords is not None:
        d["latlon_coords"] = [list(c) for c in land.latlon_coords]
    if land.origin_lat is not None:
        d["origin_lat"] = land.origin_lat
    if land.origin_lon is not None:
        d["origin_lon"] = land.origin_lon
    if land.zoning is not None:
        z = land.zoning
        d["zoning"] = {
            "zone_code": z.zone_code,
            "max_height_m": z.max_height_m,
            "max_far": z.max_far,
            "max_lot_coverage": z.max_lot_coverage,
            "min_lot_area_m2": z.min_lot_area_m2,
            "allowed_uses": list(z.allowed_uses),
            "notes": z.notes,
            "source": z.source,
        }
    return d


def _des_land(data: dict[str, Any] | None) -> Land | None:
    """
    Deserialize a Land from a dict.

    Accepts both the full ``land`` format (new) and the legacy minimal
    ``site`` format (``boundary``, ``north_angle``, ``address``, ``epsg_code`` only).
    """
    if data is None:
        return None
    from archit_app.building.land import Setbacks, ZoningInfo

    boundary = _des_polygon(data["boundary"]) if data.get("boundary") else None
    setbacks_data = data.get("setbacks", {})
    setbacks = Setbacks(
        front=setbacks_data.get("front", 0.0),
        back=setbacks_data.get("back", 0.0),
        left=setbacks_data.get("left", 0.0),
        right=setbacks_data.get("right", 0.0),
    )
    zoning = None
    if data.get("zoning"):
        z = data["zoning"]
        zoning = ZoningInfo(
            zone_code=z.get("zone_code", ""),
            max_height_m=z.get("max_height_m"),
            max_far=z.get("max_far"),
            max_lot_coverage=z.get("max_lot_coverage"),
            min_lot_area_m2=z.get("min_lot_area_m2"),
            allowed_uses=tuple(z.get("allowed_uses", [])),
            notes=z.get("notes", ""),
            source=z.get("source", ""),
        )
    latlon_raw = data.get("latlon_coords")
    latlon_coords = (
        tuple(tuple(c) for c in latlon_raw) if latlon_raw is not None else None
    )
    return Land(
        boundary=boundary,
        latlon_coords=latlon_coords,
        origin_lat=data.get("origin_lat"),
        origin_lon=data.get("origin_lon"),
        north_angle=data.get("north_angle", 0.0),
        address=data.get("address", ""),
        epsg_code=data.get("epsg_code"),
        elevation_m=data.get("elevation_m", 0.0),
        setbacks=setbacks,
        zoning=zoning,
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
        "land": _ser_land(building.land),
        "elevators": [_ser_elevator(e) for e in building.elevators],
        "grid": _ser_grid(building.grid),
    }


def migrate_json(data: dict[str, Any]) -> dict[str, Any]:
    """
    Upgrade a JSON dict from any older format version to the current one.

    The function is idempotent: passing current-version data returns it
    unchanged.  Unknown versions are passed through without modification so
    that future versions of the library can read files written today.

    Migration chain applied in order:
      0.1.0 → 0.2.0 → 0.3.0
    """
    version = data.get("_archit_app_version", "0.1.0")
    if version == "0.1.0":
        data = _migrate_0_1_to_0_2(data)
        version = "0.2.0"
    if version == "0.2.0":
        data = _migrate_0_2_to_0_3(data)
        version = "0.3.0"
    return data


def _migrate_0_1_to_0_2(data: dict[str, Any]) -> dict[str, Any]:
    """0.1.0 → 0.2.0: rename 'site' key → 'land'; add missing level arrays."""
    data = dict(data)  # shallow copy
    data["_archit_app_version"] = "0.2.0"

    # Rename site → land
    if "site" in data and "land" not in data:
        data["land"] = data.pop("site")

    # Ensure every level has the arrays added in 0.2.0
    new_level_keys = (
        "staircases", "slabs", "ramps", "beams",
        "furniture", "text_annotations", "dimensions", "section_marks",
    )
    for level in data.get("levels", []):
        for key in new_level_keys:
            if key not in level:
                level[key] = []

    return data


def _migrate_0_2_to_0_3(data: dict[str, Any]) -> dict[str, Any]:
    """0.2.0 → 0.3.0: add elevators and grid keys at building level."""
    data = dict(data)
    data["_archit_app_version"] = "0.3.0"
    data.setdefault("elevators", [])
    data.setdefault("grid", None)
    return data


def building_from_dict(data: dict[str, Any]) -> Building:
    """
    Reconstruct a Building from a dict (as produced by building_to_dict).

    Automatically migrates older JSON formats to the current schema before
    deserializing.  Reads the ``land`` key (current format) and falls back to
    the legacy ``site`` key if present.
    """
    data = migrate_json(data)
    meta = data.get("metadata", {})
    metadata = BuildingMetadata(
        name=meta.get("name", ""),
        project_number=meta.get("project_number", ""),
        architect=meta.get("architect", ""),
        client=meta.get("client", ""),
        date=meta.get("date", ""),
    )
    levels = tuple(_des_level(lv) for lv in data.get("levels", []))
    # Accept both the new "land" key and the legacy "site" key
    land_data = data.get("land") or data.get("site")
    land = _des_land(land_data)
    elevators = tuple(_des_elevator(e) for e in data.get("elevators", []))
    grid = _des_grid(data.get("grid"))
    return Building(metadata=metadata, levels=levels, land=land, elevators=elevators, grid=grid)


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
