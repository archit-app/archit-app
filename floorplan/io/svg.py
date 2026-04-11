"""
SVG export for floorplan levels and buildings.

Renders a clean 2D floorplan diagram as SVG. Coordinate system: SVG is Y-down,
so all Y coordinates are flipped relative to the Y-up world space.

Usage:
    from floorplan.io.svg import level_to_svg, building_to_svg_pages

    svg_str = level_to_svg(my_level, pixels_per_meter=50)
    with open("floor_0.svg", "w") as f:
        f.write(svg_str)
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from typing import Iterable

from floorplan.building.building import Building
from floorplan.building.level import Level
from floorplan.elements.column import Column
from floorplan.elements.opening import Opening, OpeningKind
from floorplan.elements.room import Room
from floorplan.elements.wall import Wall
from floorplan.geometry.bbox import BoundingBox2D
from floorplan.geometry.curve import ArcCurve, BezierCurve, NURBSCurve
from floorplan.geometry.point import Point2D
from floorplan.geometry.polygon import Polygon2D

# ---------------------------------------------------------------------------
# Default color palette
# ---------------------------------------------------------------------------

PALETTE = {
    "room_fill": "#D6E8F5",        # light blue
    "room_stroke": "#5B8DB8",      # medium blue
    "wall_fill": "#4A4A4A",        # dark gray
    "wall_stroke": "#2A2A2A",
    "column_fill": "#C0392B",      # red
    "column_stroke": "#922B21",
    "door_fill": "#FFFFFF",        # white cutout
    "door_stroke": "#5B8DB8",
    "window_fill": "#AED6F1",      # light cyan
    "window_stroke": "#2980B9",
    "opening_stroke_width": "0.5",
    "room_stroke_width": "1",
    "wall_stroke_width": "0.5",
    "column_stroke_width": "0.5",
    "background": "#FAFAFA",
    "room_label": "#1A3A5C",
    "annotation": "#666666",
}

MARGIN_PX = 40  # canvas margin in pixels


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------


class ViewTransform:
    """Maps world-space (Y-up, meters) to SVG-space (Y-down, pixels)."""

    def __init__(
        self,
        bbox: BoundingBox2D,
        pixels_per_meter: float,
        margin: float = MARGIN_PX,
    ) -> None:
        self.ppm = pixels_per_meter
        self.margin = margin
        self.world_min_x = bbox.min_corner.x
        self.world_max_y = bbox.max_corner.y   # used for Y-flip
        self.svg_width = bbox.width * pixels_per_meter + 2 * margin
        self.svg_height = bbox.height * pixels_per_meter + 2 * margin

    def to_svg(self, x: float, y: float) -> tuple[float, float]:
        """Convert world (x, y) to SVG pixel coords."""
        sx = (x - self.world_min_x) * self.ppm + self.margin
        sy = (self.world_max_y - y) * self.ppm + self.margin  # Y-flip
        return sx, sy

    def pt_to_svg(self, p: Point2D) -> tuple[float, float]:
        return self.to_svg(p.x, p.y)

    def scale(self, v: float) -> float:
        return v * self.ppm


# ---------------------------------------------------------------------------
# SVG element builders
# ---------------------------------------------------------------------------


def _polygon_path(pts: list[tuple[float, float]]) -> str:
    """Build an SVG path 'd' attribute from a list of (sx, sy) tuples."""
    if not pts:
        return ""
    parts = [f"M {pts[0][0]:.3f} {pts[0][1]:.3f}"]
    for x, y in pts[1:]:
        parts.append(f"L {x:.3f} {y:.3f}")
    parts.append("Z")
    return " ".join(parts)


def _polygon2d_path(poly: Polygon2D, vt: ViewTransform) -> str:
    """Convert a Polygon2D exterior to an SVG path 'd' string (evenodd for holes)."""
    exterior_pts = [vt.pt_to_svg(p) for p in poly.exterior]
    d = _polygon_path(exterior_pts)
    for hole in poly.holes:
        hole_pts = [vt.pt_to_svg(p) for p in hole]
        d += " " + _polygon_path(hole_pts)
    return d


def _curve_path(geom, vt: ViewTransform, resolution: int = 32) -> str:
    """Convert an ArcCurve/BezierCurve to SVG path via polyline approximation."""
    pts_world = geom.to_polyline(resolution)
    pts_svg = [vt.pt_to_svg(p) for p in pts_world]
    return _polygon_path(pts_svg)


def _geom_to_path(geom, vt: ViewTransform) -> str:
    if isinstance(geom, Polygon2D):
        return _polygon2d_path(geom, vt)
    return _curve_path(geom, vt)


# ---------------------------------------------------------------------------
# Element renderers
# ---------------------------------------------------------------------------


def _render_room(room: Room, vt: ViewTransform, parent: ET.Element) -> None:
    # Outer boundary with holes (evenodd fill rule)
    exterior_pts = [vt.pt_to_svg(p) for p in room.boundary.exterior]
    d = _polygon_path(exterior_pts)
    for hole in room.boundary.holes:
        hole_pts = [vt.pt_to_svg(p) for p in hole]
        d += " " + _polygon_path(hole_pts)
    for hole in room.holes:
        hole_pts = [vt.pt_to_svg(p) for p in hole.exterior]
        d += " " + _polygon_path(hole_pts)

    ET.SubElement(parent, "path", {
        "d": d,
        "fill": PALETTE["room_fill"],
        "fill-rule": "evenodd",
        "stroke": PALETTE["room_stroke"],
        "stroke-width": PALETTE["room_stroke_width"],
        "class": "room",
    })

    # Room label
    if room.name or room.program:
        c = room.boundary.centroid
        cx, cy = vt.pt_to_svg(c)
        label = room.name or room.program
        program_line = room.program if room.name and room.program else ""
        area_line = f"{room.area:.1f} m²"

        lines = [l for l in [label, program_line, area_line] if l]
        line_height = 11
        start_y = cy - (len(lines) - 1) * line_height / 2

        for i, line in enumerate(lines):
            text_el = ET.SubElement(parent, "text", {
                "x": str(round(cx, 2)),
                "y": str(round(start_y + i * line_height, 2)),
                "text-anchor": "middle",
                "dominant-baseline": "middle",
                "fill": PALETTE["room_label"],
                "font-size": "8" if i > 0 else "9",
                "font-family": "sans-serif",
                "font-weight": "bold" if i == 0 else "normal",
            })
            text_el.text = line


def _render_wall(wall: Wall, vt: ViewTransform, parent: ET.Element) -> None:
    d = _geom_to_path(wall.geometry, vt)
    ET.SubElement(parent, "path", {
        "d": d,
        "fill": PALETTE["wall_fill"],
        "stroke": PALETTE["wall_stroke"],
        "stroke-width": PALETTE["wall_stroke_width"],
        "class": "wall",
    })


def _render_opening(opening: Opening, vt: ViewTransform, parent: ET.Element) -> None:
    if opening.kind == OpeningKind.DOOR:
        fill = PALETTE["door_fill"]
        stroke = PALETTE["door_stroke"]
    elif opening.kind == OpeningKind.WINDOW:
        fill = PALETTE["window_fill"]
        stroke = PALETTE["window_stroke"]
    else:
        fill = PALETTE["door_fill"]
        stroke = PALETTE["door_stroke"]

    d = _polygon2d_path(opening.geometry, vt)
    ET.SubElement(parent, "path", {
        "d": d,
        "fill": fill,
        "stroke": stroke,
        "stroke-width": PALETTE["opening_stroke_width"],
        "class": f"opening {opening.kind.value}",
    })

    # Door swing arc
    if opening.swing is not None:
        arc_pts = [vt.pt_to_svg(p) for p in opening.swing.arc.to_polyline(24)]
        if arc_pts:
            d_arc = f"M {arc_pts[0][0]:.3f} {arc_pts[0][1]:.3f}"
            for x, y in arc_pts[1:]:
                d_arc += f" L {x:.3f} {y:.3f}"
            ET.SubElement(parent, "path", {
                "d": d_arc,
                "fill": "none",
                "stroke": PALETTE["door_stroke"],
                "stroke-width": "0.5",
                "stroke-dasharray": "2 2",
            })


def _render_column(col: Column, vt: ViewTransform, parent: ET.Element) -> None:
    d = _polygon2d_path(col.geometry, vt)
    ET.SubElement(parent, "path", {
        "d": d,
        "fill": PALETTE["column_fill"],
        "stroke": PALETTE["column_stroke"],
        "stroke-width": PALETTE["column_stroke_width"],
        "class": "column",
    })


# ---------------------------------------------------------------------------
# Level → SVG
# ---------------------------------------------------------------------------


def _compute_bbox(level: Level) -> BoundingBox2D | None:
    """Compute a bounding box covering all elements in a level."""
    return level.bounding_box


def level_to_svg(
    level: Level,
    pixels_per_meter: float = 50.0,
    margin: float = MARGIN_PX,
    title: str | None = None,
    palette: dict | None = None,
) -> str:
    """
    Render a Level as an SVG string.

    Args:
        level: the floor level to render
        pixels_per_meter: drawing scale (default 50 px/m ≈ 1:20 at 96dpi)
        margin: padding around the drawing in pixels
        title: optional title drawn at the top
        palette: optional dict to override default colors

    Returns:
        SVG XML as a string (UTF-8)
    """
    global PALETTE
    if palette:
        PALETTE = {**PALETTE, **palette}

    bbox = _compute_bbox(level)
    if bbox is None:
        # Empty level — return a minimal SVG
        svg = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "width": "200", "height": "100"})
        ET.SubElement(svg, "text", {"x": "10", "y": "20", "font-family": "sans-serif"}).text = "Empty level"
        ET.indent(svg)
        return ET.tostring(svg, encoding="unicode")

    vt = ViewTransform(bbox, pixels_per_meter, margin)

    svg = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": str(round(vt.svg_width)),
        "height": str(round(vt.svg_height)),
        "viewBox": f"0 0 {vt.svg_width:.2f} {vt.svg_height:.2f}",
    })

    # Background
    ET.SubElement(svg, "rect", {
        "width": "100%", "height": "100%",
        "fill": PALETTE["background"],
    })

    # Rooms layer
    room_group = ET.SubElement(svg, "g", {"id": "rooms"})
    for room in level.rooms:
        _render_room(room, vt, room_group)

    # Walls layer (on top of rooms)
    wall_group = ET.SubElement(svg, "g", {"id": "walls"})
    for wall in level.walls:
        _render_wall(wall, vt, wall_group)
        # Render openings punched into the wall
        for opening in wall.openings:
            _render_opening(opening, vt, wall_group)

    # Level-standalone openings
    opening_group = ET.SubElement(svg, "g", {"id": "openings"})
    for opening in level.openings:
        _render_opening(opening, vt, opening_group)

    # Columns layer (on top of everything)
    col_group = ET.SubElement(svg, "g", {"id": "columns"})
    for col in level.columns:
        _render_column(col, vt, col_group)

    # Scale bar (bottom-left)
    _render_scale_bar(svg, vt, pixels_per_meter)

    # Title
    if title is None:
        title = level.name or f"Level {level.index}"
    ET.SubElement(svg, "text", {
        "x": str(round(margin)),
        "y": str(round(margin * 0.6)),
        "font-family": "sans-serif",
        "font-size": "12",
        "font-weight": "bold",
        "fill": "#333",
    }).text = title

    ET.indent(svg, space="  ")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(svg, encoding="unicode")


def _render_scale_bar(svg: ET.Element, vt: ViewTransform, pixels_per_meter: float) -> None:
    """Draw a 1-meter scale bar at the bottom left of the SVG."""
    bar_len_px = pixels_per_meter  # exactly 1 meter
    bar_x = vt.margin
    bar_y = vt.svg_height - vt.margin * 0.5
    bar_h = 4

    g = ET.SubElement(svg, "g", {"id": "scale-bar"})
    ET.SubElement(g, "rect", {
        "x": str(round(bar_x, 2)),
        "y": str(round(bar_y - bar_h, 2)),
        "width": str(round(bar_len_px, 2)),
        "height": str(bar_h),
        "fill": "#333",
    })
    ET.SubElement(g, "text", {
        "x": str(round(bar_x + bar_len_px / 2, 2)),
        "y": str(round(bar_y + 8, 2)),
        "text-anchor": "middle",
        "font-family": "sans-serif",
        "font-size": "7",
        "fill": "#555",
    }).text = "1 m"


# ---------------------------------------------------------------------------
# Building → multi-page SVG list
# ---------------------------------------------------------------------------


def building_to_svg_pages(
    building: Building,
    pixels_per_meter: float = 50.0,
    margin: float = MARGIN_PX,
) -> list[tuple[int, str]]:
    """
    Render each level of a building as a separate SVG.

    Returns:
        list of (level_index, svg_string) tuples
    """
    pages = []
    for level in building.levels:
        title = level.name or f"Level {level.index} — {building.metadata.name}"
        svg_str = level_to_svg(level, pixels_per_meter=pixels_per_meter, margin=margin, title=title)
        pages.append((level.index, svg_str))
    return pages


def save_level_svg(level: Level, path: str, **kwargs) -> None:
    """Write a level's SVG to a file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(level_to_svg(level, **kwargs))


def save_building_svgs(building: Building, directory: str, **kwargs) -> list[str]:
    """
    Write one SVG per level to the given directory.

    Returns:
        list of file paths written
    """
    import os

    os.makedirs(directory, exist_ok=True)
    paths = []
    for level_index, svg_str in building_to_svg_pages(building, **kwargs):
        fname = os.path.join(directory, f"level_{level_index:02d}.svg")
        with open(fname, "w", encoding="utf-8") as f:
            f.write(svg_str)
        paths.append(fname)
    return paths
