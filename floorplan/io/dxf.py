"""
DXF export for floorplan levels and buildings.

Requires the optional dependency: pip install floorplan[io]

Exports each element type to its own DXF layer:
  - Rooms      → "FP_ROOMS"      (hatch + boundary polyline)
  - Walls      → "FP_WALLS"      (solid hatch)
  - Openings   → "FP_OPENINGS"   (boundary polyline)
  - Columns    → "FP_COLUMNS"    (solid hatch)

For multi-level buildings, layer names are prefixed: "L00_FP_WALLS", etc.

Usage:
    from floorplan.io.dxf import building_to_dxf, save_building_dxf

    doc = building_to_dxf(my_building)
    doc.saveas("my_building.dxf")

    # Or use the convenience function:
    save_building_dxf(my_building, "my_building.dxf")
"""

from __future__ import annotations

from typing import Sequence

from floorplan.building.building import Building
from floorplan.building.level import Level
from floorplan.elements.column import Column
from floorplan.elements.opening import Opening
from floorplan.elements.room import Room
from floorplan.elements.wall import Wall
from floorplan.geometry.polygon import Polygon2D

# DXF ACI color codes
_COLOR = {
    "rooms": 4,       # cyan
    "walls": 252,     # near-black
    "openings": 3,    # green
    "columns": 1,     # red
}


def _require_ezdxf():
    try:
        import ezdxf
        return ezdxf
    except ImportError:
        raise ImportError(
            "ezdxf is required for DXF export. "
            "Install it with: pip install floorplan[io]"
        )


def _poly_coords(poly: Polygon2D) -> list[tuple[float, float]]:
    """Extract exterior ring as list of (x, y) tuples."""
    return [(p.x, p.y) for p in poly.exterior]


def _geom_coords(geom, resolution: int = 32) -> list[tuple[float, float]]:
    """Get (x, y) boundary coords from any wall geometry."""
    if isinstance(geom, Polygon2D):
        return _poly_coords(geom)
    pts = geom.to_polyline(resolution)
    return [(p.x, p.y) for p in pts]


def _add_lwpolyline(msp, coords: list[tuple[float, float]], layer: str, color: int, closed: bool = True):
    """Add a closed LWPolyline to modelspace."""
    if len(coords) < 2:
        return
    pline = msp.add_lwpolyline(coords, dxfattribs={"layer": layer, "color": color})
    pline.close(closed)


def _add_hatch(msp, coords: list[tuple[float, float]], holes: list[list[tuple[float, float]]], layer: str, color: int):
    """Add a solid hatch polygon (with optional holes) to modelspace."""
    if len(coords) < 3:
        return
    hatch = msp.add_hatch(color=color, dxfattribs={"layer": layer})
    hatch.set_pattern_fill("SOLID")

    # Close the exterior ring if needed
    ext = list(coords)
    if ext[0] != ext[-1]:
        ext.append(ext[0])

    with hatch.edit_boundary() as b:
        b.add_polyline_path(ext, is_closed=True)
        for hole in holes:
            h = list(hole)
            if h[0] != h[-1]:
                h.append(h[0])
            b.add_polyline_path(h, is_closed=True)


def _layer_name(prefix: str, element_type: str) -> str:
    return f"{prefix}FP_{element_type.upper()}"


def _export_level(level: Level, msp, prefix: str = "") -> None:
    """Write all elements of a level to the given modelspace."""

    # --- Rooms ---
    room_layer = _layer_name(prefix, "ROOMS")
    for room in level.rooms:
        coords = _poly_coords(room.boundary)
        holes = [[(p.x, p.y) for p in h.exterior] for h in room.holes]
        _add_hatch(msp, coords, holes, room_layer, _COLOR["rooms"])
        _add_lwpolyline(msp, coords, room_layer, _COLOR["rooms"])

    # --- Walls ---
    wall_layer = _layer_name(prefix, "WALLS")
    for wall in level.walls:
        coords = _geom_coords(wall.geometry)
        _add_hatch(msp, coords, [], wall_layer, _COLOR["walls"])
        _add_lwpolyline(msp, coords, wall_layer, _COLOR["walls"])

        # Openings as cutouts drawn on opening layer
        opening_layer = _layer_name(prefix, "OPENINGS")
        for opening in wall.openings:
            oc = _poly_coords(opening.geometry)
            _add_lwpolyline(msp, oc, opening_layer, _COLOR["openings"])

    # --- Level-level openings ---
    opening_layer = _layer_name(prefix, "OPENINGS")
    for opening in level.openings:
        oc = _poly_coords(opening.geometry)
        _add_lwpolyline(msp, oc, opening_layer, _COLOR["openings"])

    # --- Columns ---
    col_layer = _layer_name(prefix, "COLUMNS")
    for col in level.columns:
        coords = _poly_coords(col.geometry)
        _add_hatch(msp, coords, [], col_layer, _COLOR["columns"])
        _add_lwpolyline(msp, coords, col_layer, _COLOR["columns"])


def level_to_dxf(level: Level):
    """
    Export a single Level to a DXF document.

    Returns:
        ezdxf.document.Drawing object — call .saveas(path) to write to disk.
    """
    ezdxf = _require_ezdxf()
    doc = ezdxf.new(dxfversion="R2010")
    doc.header["$INSUNITS"] = 6  # meters (6 = meters in DXF standard)

    # Define layers
    for layer_suffix, color in [
        ("FP_ROOMS", _COLOR["rooms"]),
        ("FP_WALLS", _COLOR["walls"]),
        ("FP_OPENINGS", _COLOR["openings"]),
        ("FP_COLUMNS", _COLOR["columns"]),
    ]:
        doc.layers.add(layer_suffix, color=color)

    msp = doc.modelspace()
    _export_level(level, msp, prefix="")
    return doc


def building_to_dxf(building: Building):
    """
    Export an entire Building to a DXF document.

    Each level gets its own set of layers prefixed by level index:
      L00_FP_WALLS, L01_FP_WALLS, etc.

    Returns:
        ezdxf.document.Drawing object
    """
    ezdxf = _require_ezdxf()
    doc = ezdxf.new(dxfversion="R2010")
    doc.header["$INSUNITS"] = 6  # meters

    msp = doc.modelspace()

    for level in building.levels:
        prefix = f"L{level.index:02d}_"
        for suffix, color in [
            ("FP_ROOMS", _COLOR["rooms"]),
            ("FP_WALLS", _COLOR["walls"]),
            ("FP_OPENINGS", _COLOR["openings"]),
            ("FP_COLUMNS", _COLOR["columns"]),
        ]:
            layer_name = f"{prefix}FP_{suffix.split('_', 1)[-1]}"
            if layer_name not in doc.layers:
                lyr = doc.layers.add(layer_name, color=color)
                # Offset each level slightly in Z for 3D stacking visibility
                # (DXF layer elevation is set per entity, not per layer)

        _export_level(level, msp, prefix=prefix)

    # Add a metadata block comment
    if building.metadata.name:
        doc.header["$PROJECTNAME"] = building.metadata.name

    return doc


def save_level_dxf(level: Level, path: str) -> None:
    """Write a Level to a DXF file."""
    doc = level_to_dxf(level)
    doc.saveas(path)


def save_building_dxf(building: Building, path: str) -> None:
    """Write a Building to a DXF file."""
    doc = building_to_dxf(building)
    doc.saveas(path)
