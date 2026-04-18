"""
SVG export for floorplan levels and buildings.

Renders a clean 2D floorplan diagram as SVG. Coordinate system: SVG is Y-down,
so all Y coordinates are flipped relative to the Y-up world space.

Usage:
    from archit_app.io.svg import level_to_svg, building_to_svg_pages

    svg_str = level_to_svg(my_level, pixels_per_meter=50)
    with open("floor_0.svg", "w") as f:
        f.write(svg_str)
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from typing import Iterable

from archit_app.building.building import Building
from archit_app.building.level import Level
from archit_app.elements.column import Column
from archit_app.elements.opening import Opening, OpeningKind
from archit_app.elements.room import Room
from archit_app.elements.wall import Wall
from archit_app.geometry.bbox import BoundingBox2D
from archit_app.geometry.curve import ArcCurve, BezierCurve, NURBSCurve
from archit_app.geometry.point import Point2D
from archit_app.geometry.polygon import Polygon2D

# lazily imported to avoid hard dependency checks at module level
# (Furniture, Beam, Ramp, TextAnnotation, DimensionLine, SectionMark)

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
    # Extended palette for new elements
    "furniture_fill": "#FFF8DC",   # cornsilk
    "furniture_stroke": "#A0845C",
    "beam_stroke": "#7B3F00",      # dark brown, dashed centreline
    "ramp_stroke": "#4A90D9",      # blue diagonal hatching
    "ramp_arrow": "#2C5F8A",
    "dim_line": "#888888",         # dimension lines
    "dim_text": "#555555",
    "section_line": "#CC2200",     # red cut line
    "section_text": "#CC2200",
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


def _render_furniture(furniture, vt: ViewTransform, parent: ET.Element) -> None:
    """Render a Furniture item: filled footprint polygon + centred label."""
    d = _polygon2d_path(furniture.footprint, vt)
    ET.SubElement(parent, "path", {
        "d": d,
        "fill": PALETTE["furniture_fill"],
        "stroke": PALETTE["furniture_stroke"],
        "stroke-width": "0.5",
        "class": "furniture",
    })
    label = furniture.label or furniture.category.value.replace("_", " ").title()
    if label:
        c = furniture.footprint.centroid
        cx, cy = vt.pt_to_svg(c)
        ET.SubElement(parent, "text", {
            "x": str(round(cx, 2)),
            "y": str(round(cy, 2)),
            "text-anchor": "middle",
            "dominant-baseline": "middle",
            "fill": PALETTE["furniture_stroke"],
            "font-size": "6",
            "font-family": "sans-serif",
        }).text = label


def _render_beam(beam, vt: ViewTransform, parent: ET.Element) -> None:
    """Render a Beam: footprint outline (dashed) + dashed centreline."""
    d = _polygon2d_path(beam.geometry, vt)
    ET.SubElement(parent, "path", {
        "d": d,
        "fill": "none",
        "stroke": PALETTE["beam_stroke"],
        "stroke-width": "1",
        "stroke-dasharray": "4 2",
        "class": "beam",
    })
    # Centreline: midpoint of the two longest opposite edges
    pts = beam.geometry.exterior
    n = len(pts)
    if n >= 4:
        mid_start = vt.pt_to_svg(pts[0].midpoint(pts[n // 2]))
        mid_end = vt.pt_to_svg(pts[1].midpoint(pts[n // 2 + 1] if n // 2 + 1 < n else pts[0]))
        d_cl = f"M {mid_start[0]:.3f} {mid_start[1]:.3f} L {mid_end[0]:.3f} {mid_end[1]:.3f}"
        ET.SubElement(parent, "path", {
            "d": d_cl,
            "fill": "none",
            "stroke": PALETTE["beam_stroke"],
            "stroke-width": "0.5",
            "stroke-dasharray": "6 3",
        })


def _render_ramp(ramp, vt: ViewTransform, parent: ET.Element) -> None:
    """Render a Ramp: footprint outline + diagonal hatching + direction arrow."""
    d = _polygon2d_path(ramp.boundary, vt)
    ET.SubElement(parent, "path", {
        "d": d,
        "fill": "none",
        "stroke": PALETTE["ramp_stroke"],
        "stroke-width": "1",
        "class": "ramp",
    })

    # Diagonal hatch lines clipped to bounding box
    bb = ramp.boundary.bounding_box()
    x0, y0 = vt.to_svg(bb.min_corner.x, bb.min_corner.y)
    x1, y1 = vt.to_svg(bb.max_corner.x, bb.max_corner.y)
    # In SVG coords y0 > y1 (flipped), normalise
    svg_left, svg_top = min(x0, x1), min(y0, y1)
    svg_right, svg_bot = max(x0, x1), max(y0, y1)
    step = max(4.0, (svg_right - svg_left) / 5)
    hatch_lines = []
    t = svg_left
    while t <= svg_right + (svg_bot - svg_top):
        hatch_lines.append(
            f"M {svg_left:.1f} {(svg_top + t - svg_left):.1f} "
            f"L {(svg_left + t - svg_top):.1f} {svg_top:.1f}"
        )
        t += step
    if hatch_lines:
        ET.SubElement(parent, "path", {
            "d": " ".join(hatch_lines),
            "fill": "none",
            "stroke": PALETTE["ramp_stroke"],
            "stroke-width": "0.4",
            "opacity": "0.5",
            "clip-path": f"path('{d}')",
        })

    # Direction arrow at centroid
    c = ramp.boundary.centroid
    cx, cy = vt.pt_to_svg(c)
    arrow_len = vt.scale(min(ramp.width, 0.8) * 0.6)
    import math as _math
    # ramp.direction is world-space angle; in SVG Y-flip negates the sin
    dx = _math.cos(ramp.direction) * arrow_len
    dy = -_math.sin(ramp.direction) * arrow_len  # Y-flip
    ET.SubElement(parent, "line", {
        "x1": str(round(cx - dx * 0.5, 2)),
        "y1": str(round(cy - dy * 0.5, 2)),
        "x2": str(round(cx + dx * 0.5, 2)),
        "y2": str(round(cy + dy * 0.5, 2)),
        "stroke": PALETTE["ramp_arrow"],
        "stroke-width": "1.5",
        "marker-end": "url(#arrowhead)",
    })


def _render_text_annotation(ann, vt: ViewTransform, parent: ET.Element) -> None:
    """Render a TextAnnotation as an SVG <text> element."""
    sx, sy = vt.pt_to_svg(ann.position)
    # rotation: world CCW → SVG CW (negate)
    rot_deg = -math.degrees(ann.rotation)
    font_size = max(6, vt.scale(ann.size * 0.5))
    # anchor mapping
    anchor_map = {"center": "middle", "left": "start", "right": "end"}
    text_anchor = anchor_map.get(ann.anchor, "middle")

    transform = f"rotate({rot_deg:.2f},{sx:.2f},{sy:.2f})" if rot_deg else ""
    attrs = {
        "x": str(round(sx, 2)),
        "y": str(round(sy, 2)),
        "text-anchor": text_anchor,
        "dominant-baseline": "middle",
        "fill": PALETTE["annotation"],
        "font-size": str(round(font_size, 1)),
        "font-family": "sans-serif",
        "class": "annotation",
    }
    if transform:
        attrs["transform"] = transform
    ET.SubElement(parent, "text", attrs).text = ann.text


def _render_dimension_line(dim, vt: ViewTransform, parent: ET.Element) -> None:
    """Render a DimensionLine: extension lines + measurement line + label."""
    sx_s, sy_s = vt.pt_to_svg(dim.start)
    sx_e, sy_e = vt.pt_to_svg(dim.end)
    dl_s_sx, dl_s_sy = vt.pt_to_svg(dim.dimension_line_start)
    dl_e_sx, dl_e_sy = vt.pt_to_svg(dim.dimension_line_end)
    lp_sx, lp_sy = vt.pt_to_svg(dim.label_position)

    stroke = PALETTE["dim_line"]
    sw = "0.5"

    # Extension lines (from control points to dimension line)
    ET.SubElement(parent, "line", {
        "x1": str(round(sx_s, 2)), "y1": str(round(sy_s, 2)),
        "x2": str(round(dl_s_sx, 2)), "y2": str(round(dl_s_sy, 2)),
        "stroke": stroke, "stroke-width": sw,
    })
    ET.SubElement(parent, "line", {
        "x1": str(round(sx_e, 2)), "y1": str(round(sy_e, 2)),
        "x2": str(round(dl_e_sx, 2)), "y2": str(round(dl_e_sy, 2)),
        "stroke": stroke, "stroke-width": sw,
    })

    # Dimension line with tick marks (small perpendicular strokes at endpoints)
    ET.SubElement(parent, "line", {
        "x1": str(round(dl_s_sx, 2)), "y1": str(round(dl_s_sy, 2)),
        "x2": str(round(dl_e_sx, 2)), "y2": str(round(dl_e_sy, 2)),
        "stroke": stroke, "stroke-width": sw,
    })

    # Label
    ET.SubElement(parent, "text", {
        "x": str(round(lp_sx, 2)),
        "y": str(round(lp_sy - 3, 2)),   # slight offset above line
        "text-anchor": "middle",
        "dominant-baseline": "middle",
        "fill": PALETTE["dim_text"],
        "font-size": "7",
        "font-family": "sans-serif",
    }).text = dim.label


def _render_section_mark(mark, vt: ViewTransform, parent: ET.Element) -> None:
    """Render a SectionMark: bold cut line + triangle end markers + tag bubble."""
    cl = mark.cut_line
    sx_s, sy_s = vt.pt_to_svg(cl.start)
    sx_e, sy_e = vt.pt_to_svg(cl.end)

    stroke = PALETTE["section_line"]

    # Cut line (bold dashed)
    ET.SubElement(parent, "line", {
        "x1": str(round(sx_s, 2)), "y1": str(round(sy_s, 2)),
        "x2": str(round(sx_e, 2)), "y2": str(round(sy_e, 2)),
        "stroke": stroke,
        "stroke-width": "1.5",
        "stroke-dasharray": "6 3",
        "class": "section-mark",
    })

    # Tag bubble (circle + text) at midpoint
    mp = mark.midpoint
    mx, my = vt.pt_to_svg(mp)
    r = max(5.0, vt.scale(0.12))
    ET.SubElement(parent, "circle", {
        "cx": str(round(mx, 2)), "cy": str(round(my, 2)),
        "r": str(round(r, 2)),
        "fill": "white", "stroke": stroke, "stroke-width": "1",
    })
    ET.SubElement(parent, "text", {
        "x": str(round(mx, 2)),
        "y": str(round(my, 2)),
        "text-anchor": "middle",
        "dominant-baseline": "middle",
        "fill": PALETTE["section_text"],
        "font-size": str(round(r * 1.2, 1)),
        "font-family": "sans-serif",
        "font-weight": "bold",
    }).text = mark.tag

    # Small filled triangles at start and end indicating view direction
    def _triangle(sx, sy, angle_deg, size=4.0):
        a = math.radians(angle_deg)
        tip_x = sx + math.cos(a) * size
        tip_y = sy - math.sin(a) * size  # Y-flip
        left_x = sx + math.cos(a + math.pi * 0.75) * size * 0.6
        left_y = sy - math.sin(a + math.pi * 0.75) * size * 0.6
        right_x = sx + math.cos(a - math.pi * 0.75) * size * 0.6
        right_y = sy - math.sin(a - math.pi * 0.75) * size * 0.6
        return f"M {tip_x:.2f} {tip_y:.2f} L {left_x:.2f} {left_y:.2f} L {right_x:.2f} {right_y:.2f} Z"

    vv = mark.view_vector
    view_angle = math.degrees(math.atan2(vv.y, vv.x))

    if mark.view_direction in ("left", "both"):
        d_tri = _triangle(sx_s, sy_s, view_angle)
        ET.SubElement(parent, "path", {"d": d_tri, "fill": stroke})
    if mark.view_direction in ("right", "both"):
        d_tri = _triangle(sx_e, sy_e, view_angle)
        ET.SubElement(parent, "path", {"d": d_tri, "fill": stroke})


def _ensure_defs(svg: ET.Element) -> ET.Element:
    """Return the <defs> element, creating it if needed."""
    defs = svg.find("defs")
    if defs is None:
        defs = ET.Element("defs")
        svg.insert(0, defs)
    return defs


def _add_arrowhead_marker(svg: ET.Element) -> None:
    """Add a reusable arrowhead marker to <defs>."""
    defs = _ensure_defs(svg)
    marker = ET.SubElement(defs, "marker", {
        "id": "arrowhead",
        "markerWidth": "6", "markerHeight": "6",
        "refX": "5", "refY": "3",
        "orient": "auto",
    })
    ET.SubElement(marker, "path", {
        "d": "M 0 0 L 6 3 L 0 6 Z",
        "fill": PALETTE["ramp_arrow"],
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

    # Add defs (arrowhead marker for ramp direction)
    _add_arrowhead_marker(svg)

    # Rooms layer (bottom-most)
    room_group = ET.SubElement(svg, "g", {"id": "rooms"})
    for room in level.rooms:
        _render_room(room, vt, room_group)

    # Ramps (above rooms, below walls)
    if level.ramps:
        ramp_group = ET.SubElement(svg, "g", {"id": "ramps"})
        for ramp in level.ramps:
            _render_ramp(ramp, vt, ramp_group)

    # Walls layer
    wall_group = ET.SubElement(svg, "g", {"id": "walls"})
    for wall in level.walls:
        _render_wall(wall, vt, wall_group)
        for opening in wall.openings:
            _render_opening(opening, vt, wall_group)

    # Level-standalone openings
    opening_group = ET.SubElement(svg, "g", {"id": "openings"})
    for opening in level.openings:
        _render_opening(opening, vt, opening_group)

    # Beams (above walls)
    if level.beams:
        beam_group = ET.SubElement(svg, "g", {"id": "beams"})
        for beam in level.beams:
            _render_beam(beam, vt, beam_group)

    # Columns layer
    col_group = ET.SubElement(svg, "g", {"id": "columns"})
    for col in level.columns:
        _render_column(col, vt, col_group)

    # Furniture layer
    if level.furniture:
        furn_group = ET.SubElement(svg, "g", {"id": "furniture"})
        for furn in level.furniture:
            _render_furniture(furn, vt, furn_group)

    # Dimensions layer
    if level.dimensions:
        dim_group = ET.SubElement(svg, "g", {"id": "dimensions"})
        for dim in level.dimensions:
            _render_dimension_line(dim, vt, dim_group)

    # Section marks layer
    if level.section_marks:
        sec_group = ET.SubElement(svg, "g", {"id": "section-marks"})
        for mark in level.section_marks:
            _render_section_mark(mark, vt, sec_group)

    # Text annotations (topmost)
    if level.text_annotations:
        ann_group = ET.SubElement(svg, "g", {"id": "annotations"})
        for ann in level.text_annotations:
            _render_text_annotation(ann, vt, ann_group)

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
