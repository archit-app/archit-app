"""
I/O layer for the floorplan package.

Available formats:
  - JSON    (canonical, fully round-trippable)   archit_app.io.json_schema
  - SVG     (2D rendering, no extra deps)        archit_app.io.svg
  - GeoJSON (GIS export, no extra deps)          archit_app.io.geojson
  - DXF     (AutoCAD, requires ezdxf)            archit_app.io.dxf
  - IFC 4.x (open BIM, requires ifcopenshell)    archit_app.io.ifc
  - PNG     (raster at any DPI/scale, Pillow)    archit_app.io.image
  - PDF     (multi-page, reportlab)              archit_app.io.pdf

Quick access:
"""

from archit_app.io.geojson import (
    building_to_geojson,
    building_to_geojson_str,
    level_from_geojson,
    level_from_geojson_str,
    level_to_geojson,
    level_to_geojson_str,
    save_building_geojson,
    save_level_geojson,
)
from archit_app.io.json_schema import (
    building_from_dict,
    building_from_json,
    building_to_dict,
    building_to_json,
    load_building,
    save_building,
)
from archit_app.io.svg import (
    building_to_svg_pages,
    level_to_svg,
    save_building_svgs,
    save_level_svg,
)

__all__ = [
    # JSON
    "building_to_json",
    "building_from_json",
    "building_to_dict",
    "building_from_dict",
    "save_building",
    "load_building",
    # SVG
    "level_to_svg",
    "building_to_svg_pages",
    "save_level_svg",
    "save_building_svgs",
    # GeoJSON
    "level_to_geojson",
    "building_to_geojson",
    "level_to_geojson_str",
    "building_to_geojson_str",
    "save_level_geojson",
    "save_building_geojson",
    "level_from_geojson",
    "level_from_geojson_str",
    # DXF (imported separately to avoid hard dependency)
    # from archit_app.io.dxf import save_building_dxf
    # IFC (imported separately to avoid hard dependency)
    # from archit_app.io.ifc import save_building_ifc
]
