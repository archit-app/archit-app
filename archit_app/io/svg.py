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
    "stair_fill": "#E8F4E8",       # light green
    "stair_stroke": "#2E7D32",
    "slab_fill": "none",
    "slab_stroke": "#8D6E63",      # brown
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


def _render_wall(wall: Wall, vt: ViewTransform, parent: ET.Element,
                 fill_override: str | None = None) -> None:
    d = _geom_to_path(wall.geometry, vt)
    ET.SubElement(parent, "path", {
        "d": d,
        "fill": fill_override or PALETTE["wall_fill"],
        "stroke": PALETTE["wall_stroke"],
        "stroke-width": PALETTE["wall_stroke_width"],
        "class": "wall",
    })


def _render_opening(opening: Opening, vt: ViewTransform, parent: ET.Element) -> None:
    if opening.kind == OpeningKind.ARCHWAY:
        fill, stroke = "#D7CCC8", "#6D4C41"  # brown
    elif opening.kind == OpeningKind.PASS_THROUGH:
        fill, stroke = PALETTE["window_fill"], PALETTE["window_stroke"]
    elif opening.kind == OpeningKind.WINDOW:
        fill, stroke = PALETTE["window_fill"], PALETTE["window_stroke"]
    else:  # DOOR
        fill, stroke = PALETTE["door_fill"], PALETTE["door_stroke"]

    d = _polygon2d_path(opening.geometry, vt)
    ET.SubElement(parent, "path", {
        "d": d,
        "fill": fill,
        "stroke": stroke,
        "stroke-width": PALETTE["opening_stroke_width"],
        "class": f"opening {opening.kind.value}",
    })

    # Door swing arc (only for DOOR kind)
    if opening.kind == OpeningKind.DOOR and opening.swing is not None:
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


def _render_column(col: Column, vt: ViewTransform, parent: ET.Element,
                   fill_override: str | None = None) -> None:
    d = _polygon2d_path(col.geometry, vt)
    ET.SubElement(parent, "path", {
        "d": d,
        "fill": fill_override or PALETTE["column_fill"],
        "stroke": PALETTE["column_stroke"],
        "stroke-width": PALETTE["column_stroke_width"],
        "class": "column",
    })


# ---------------------------------------------------------------------------
# Furniture — category-specific architectural plan-view symbols
# ---------------------------------------------------------------------------

# Colour tokens (warm, paper-like palette)
_FC_BASE   = "#F5F0E7"  # parchment base
_FC_SOFT   = "#EDE5D6"  # cushions / pillow surfaces
_FC_PANEL  = "#CEBFA5"  # headboard / armrest solids
_FC_WOOD   = "#D8CDB8"  # wood / cabinet surfaces
_FC_STROKE = "#7D6B54"  # primary outline
_FC_DETAIL = "#A08870"  # inner detail lines
_FC_WET    = "#E4F0F5"  # bathroom / wet areas
_FC_DARK   = "#4A3C2E"  # label text

# Base fill by category (wet/wood groups differ from default parchment)
_FURN_BASE_FILL: dict[str, str] = {
    "bathtub": _FC_WET, "shower": _FC_WET, "toilet": _FC_WET,
    "sink": _FC_WET, "washing_machine": _FC_WET,
    "wardrobe": _FC_WOOD, "bookshelf": _FC_WOOD, "dresser": _FC_WOOD,
    "kitchen_counter": _FC_WOOD, "island": _FC_WOOD, "tv_unit": _FC_WOOD,
}


# ── SVG primitive helpers ─────────────────────────────────────────────────────

def _fr(g: ET.Element, x: float, y: float, w: float, h: float,
        fill: str = _FC_BASE, stroke: str = _FC_DETAIL,
        sw: float = 0.5, rx: float = 0.0) -> None:
    """Rounded-or-plain rect helper for furniture symbols."""
    if w <= 0 or h <= 0:
        return
    a: dict[str, str] = {
        "x": f"{x:.2f}", "y": f"{y:.2f}",
        "width": f"{w:.2f}", "height": f"{h:.2f}",
        "fill": fill, "stroke": stroke, "stroke-width": f"{sw:.2f}",
    }
    if rx:
        a["rx"] = f"{rx:.2f}"; a["ry"] = f"{rx:.2f}"
    ET.SubElement(g, "rect", a)


def _fc(g: ET.Element, cx: float, cy: float, r: float,
        fill: str = _FC_BASE, stroke: str = _FC_DETAIL, sw: float = 0.5) -> None:
    if r <= 0:
        return
    ET.SubElement(g, "circle", {
        "cx": f"{cx:.2f}", "cy": f"{cy:.2f}", "r": f"{r:.2f}",
        "fill": fill, "stroke": stroke, "stroke-width": f"{sw:.2f}",
    })


def _fe(g: ET.Element, cx: float, cy: float, rx: float, ry: float,
        fill: str = _FC_BASE, stroke: str = _FC_DETAIL, sw: float = 0.5) -> None:
    if rx <= 0 or ry <= 0:
        return
    ET.SubElement(g, "ellipse", {
        "cx": f"{cx:.2f}", "cy": f"{cy:.2f}",
        "rx": f"{rx:.2f}", "ry": f"{ry:.2f}",
        "fill": fill, "stroke": stroke, "stroke-width": f"{sw:.2f}",
    })


def _fl(g: ET.Element, x1: float, y1: float, x2: float, y2: float,
        stroke: str = _FC_DETAIL, sw: float = 0.4, dash: str = "") -> None:
    a: dict[str, str] = {
        "x1": f"{x1:.2f}", "y1": f"{y1:.2f}",
        "x2": f"{x2:.2f}", "y2": f"{y2:.2f}",
        "stroke": stroke, "stroke-width": f"{sw:.2f}", "fill": "none",
    }
    if dash:
        a["stroke-dasharray"] = dash
    ET.SubElement(g, "line", a)


# ── Per-category draw functions  (x0,y0 = SVG top-left; w,h = pixel dims) ────

def _furn_bed(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    m = max(1.5, min(w, h) * 0.05)
    # Headboard strip (SVG top = wall / head-of-bed side)
    hb = min(h * 0.16, 10.0)
    _fr(g, x0, y0, w, hb, _FC_PANEL, _FC_STROKE, 0.4)
    # Two pillows
    pw = max(4.0, (w - 5 * m) / 2)
    ph = max(3.0, min(h * 0.2, pw * 0.65, 16.0))
    py = y0 + hb + 2 * m
    rx = min(pw, ph) * 0.35
    _fr(g, x0 + m, py, pw, ph, _FC_SOFT, _FC_DETAIL, 0.4, rx)
    _fr(g, x0 + w - m - pw, py, pw, ph, _FC_SOFT, _FC_DETAIL, 0.4, rx)
    # Turn-down fold line
    _fl(g, x0 + m, py + ph + 3 * m, x0 + w - m, py + ph + 3 * m, _FC_DETAIL, 0.5)


def _furn_sofa(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    m = max(1.0, min(w, h) * 0.04)
    back_h = h * 0.30
    arm_w = max(3.0, min(w * 0.12, 8.0))
    _fr(g, x0, y0, w, back_h, _FC_SOFT, _FC_DETAIL, 0.3)
    _fr(g, x0, y0, arm_w, h, _FC_PANEL, _FC_DETAIL, 0.3)
    _fr(g, x0 + w - arm_w, y0, arm_w, h, _FC_PANEL, _FC_DETAIL, 0.3)
    # Seat-cushion dividers
    seat_w = w - 2 * arm_w
    n = max(2, min(4, round(seat_w / 22)))
    cw = seat_w / n
    for i in range(1, n):
        _fl(g, x0 + arm_w + i * cw, y0 + back_h + m,
            x0 + arm_w + i * cw, y0 + h - m)


def _furn_armchair(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    m = max(1.0, min(w, h) * 0.05)
    arm_w = max(3.0, min(w * 0.18, 7.0))
    back_h = h * 0.32
    _fr(g, x0, y0, w, back_h, _FC_SOFT, _FC_DETAIL, 0.3)
    _fr(g, x0, y0, arm_w, h, _FC_PANEL, _FC_DETAIL, 0.3)
    _fr(g, x0 + w - arm_w, y0, arm_w, h, _FC_PANEL, _FC_DETAIL, 0.3)
    _fr(g, x0 + arm_w + m, y0 + back_h + m,
        w - 2 * arm_w - 2 * m, h - back_h - 2 * m,
        "none", _FC_DETAIL, 0.3, 1.5)


def _furn_dining_table(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    m = max(2.0, min(w, h) * 0.08)
    _fr(g, x0 + m, y0 + m, w - 2 * m, h - 2 * m, "none", _FC_DETAIL, 0.5)
    if w >= h:
        _fl(g, x0 + m, y0 + h / 2, x0 + w - m, y0 + h / 2, _FC_DETAIL, 0.3, "3 2")
    else:
        _fl(g, x0 + w / 2, y0 + m, x0 + w / 2, y0 + h - m, _FC_DETAIL, 0.3, "3 2")


def _furn_coffee_table(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    m = max(1.5, min(w, h) * 0.10)
    _fr(g, x0 + m, y0 + m, w - 2 * m, h - 2 * m, "none", _FC_DETAIL, 0.5)
    m2 = m * 1.9
    _fr(g, x0 + m2, y0 + m2, w - 2 * m2, h - 2 * m2, _FC_SOFT, "none", 0)


def _furn_chair(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    m = max(1.0, min(w, h) * 0.08)
    back_h = h * 0.28
    _fr(g, x0, y0, w, back_h, _FC_SOFT, _FC_DETAIL, 0.35)
    _fr(g, x0 + m, y0 + back_h + m, w - 2 * m, h - back_h - 2 * m,
        "none", _FC_DETAIL, 0.3)
    # Corner legs
    r = max(1.0, min(w, h) * 0.08)
    for lx, ly in [(x0 + r * 1.2, y0 + r * 1.2), (x0 + w - r * 1.2, y0 + r * 1.2),
                   (x0 + r * 1.2, y0 + h - r * 1.2), (x0 + w - r * 1.2, y0 + h - r * 1.2)]:
        _fc(g, lx, ly, r, _FC_PANEL, _FC_STROKE, 0.3)


def _furn_office_chair(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    cx, cy = x0 + w / 2, y0 + h / 2
    r = min(w, h) / 2
    _fc(g, cx, cy, r * 0.74, _FC_SOFT, _FC_DETAIL, 0.4)
    # 5-arm base radiating from centre
    for i in range(5):
        ang = math.pi * (2 * i / 5 - 0.5)
        ax = cx + math.cos(ang) * r * 0.88
        ay = cy + math.sin(ang) * r * 0.88
        _fl(g, cx, cy, ax, ay, _FC_STROKE, 0.5)
        _fc(g, ax, ay, max(1.0, r * 0.09), _FC_PANEL, _FC_STROKE, 0.3)
    _fc(g, cx, cy, r * 0.13, _FC_PANEL, _FC_STROKE, 0.4)
    # Backrest arc at SVG top
    pts_arc = []
    for a in range(-50, 51, 10):
        rad = math.radians(a - 90)
        pts_arc.append((cx + math.cos(rad) * r * 0.67, cy + math.sin(rad) * r * 0.67))
    d_arc = (f"M {pts_arc[0][0]:.2f} {pts_arc[0][1]:.2f}" +
             "".join(f" L {p[0]:.2f} {p[1]:.2f}" for p in pts_arc[1:]))
    ET.SubElement(g, "path", {"d": d_arc, "fill": "none",
                               "stroke": _FC_PANEL, "stroke-width": "1.2"})


def _furn_wardrobe(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    m = max(1.0, min(w, h) * 0.03)
    n = max(2, min(4, round(w / 30)))
    dw = w / n
    for i in range(n):
        dx = x0 + i * dw
        _fr(g, dx + m, y0 + m, dw - 2 * m, h - 2 * m, "none", _FC_DETAIL, 0.4)
        hx = dx + dw / 2 + (dw * 0.18 if i % 2 == 0 else -dw * 0.18)
        hr = max(1.0, min(w, h) * 0.028)
        _fc(g, hx, y0 + h / 2, hr, _FC_PANEL, _FC_STROKE, 0.4)
    for i in range(1, n):
        _fl(g, x0 + i * dw, y0, x0 + i * dw, y0 + h, _FC_STROKE, 0.5)


def _furn_desk(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    m = max(1.5, min(w, h) * 0.06)
    _fr(g, x0 + m, y0 + m, w - 2 * m, h - 2 * m, "none", _FC_DETAIL, 0.4)
    mw = min(w * 0.42, 22.0)
    mh = min(h * 0.28, 12.0)
    _fr(g, x0 + w / 2 - mw / 2, y0 + m * 1.8, mw, mh, _FC_SOFT, _FC_DETAIL, 0.4, 1.0)


def _furn_tv_unit(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    m = max(1.5, min(w, h) * 0.06)
    _fr(g, x0 + m, y0 + m, w - 2 * m, h - 2 * m, "none", _FC_DETAIL, 0.35)
    sw = w * 0.62
    sh = h * 0.55
    _fr(g, x0 + (w - sw) / 2, y0 + (h - sh) / 2,
        sw, sh, "#3A3A3A", _FC_STROKE, 0.4, 1.5)


def _furn_kitchen_counter(x0: float, y0: float, w: float, h: float,
                           g: ET.Element) -> None:
    m = max(1.0, min(w, h) * 0.04)
    _fl(g, x0, y0 + h * 0.14, x0 + w, y0 + h * 0.14, _FC_DETAIL, 0.4)
    _fr(g, x0 + m, y0 + h * 0.18, w - 2 * m, h * 0.78, "none", _FC_DETAIL, 0.35)
    n = max(2, round(w / 30))
    cw = w / n
    for i in range(1, n):
        _fl(g, x0 + i * cw, y0 + h * 0.18, x0 + i * cw, y0 + h * 0.95, _FC_DETAIL, 0.3)


def _furn_island(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    m = max(2.0, min(w, h) * 0.09)
    _fr(g, x0 + m, y0 + m, w - 2 * m, h - 2 * m, "none", _FC_DETAIL, 0.5)
    _fl(g, x0 + w / 2, y0 + m * 1.5, x0 + w / 2, y0 + h - m * 1.5,
        _FC_DETAIL, 0.3, "4 2")


def _furn_bathtub(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    im = min(w, h) * 0.10
    # Inner basin ellipse
    _fe(g, x0 + w / 2, y0 + h / 2, (w / 2) - im, (h / 2) - im,
        "#D8EEF5", _FC_DETAIL, 0.5)
    # Drain at foot (SVG bottom)
    dr = min(w, h) * 0.07
    _fc(g, x0 + w / 2, y0 + h - im * 1.3, dr, _FC_WET, _FC_DETAIL, 0.45)
    # Faucet at head (SVG top = wall side)
    fw = min(w * 0.18, 7.0)
    fh = min(h * 0.07, 3.5)
    _fr(g, x0 + w / 2 - fw / 2, y0 + im * 0.6, fw, fh, _FC_PANEL, _FC_DETAIL, 0.4, fh / 2)


def _furn_shower(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    step = max(4.0, min(w, h) * 0.22)
    parts: list[str] = []
    t = step
    total = w + h
    while t < total:
        ax = x0 + min(t, w)
        ay = y0 + max(h - t, 0.0)
        bx = x0 + max(t - h, 0.0)
        by = y0 + min(t, h)
        parts.append(f"M {ax:.1f} {ay:.1f} L {bx:.1f} {by:.1f}")
        t += step
    if parts:
        ET.SubElement(g, "path", {
            "d": " ".join(parts), "fill": "none",
            "stroke": "#A8CCE0", "stroke-width": "0.5",
        })
    # Drain at centre
    dr = min(w, h) * 0.10
    _fc(g, x0 + w / 2, y0 + h / 2, dr, _FC_WET, _FC_DETAIL, 0.5)
    _fc(g, x0 + w / 2, y0 + h / 2, dr * 0.4, "#7AAEC0", _FC_DETAIL, 0.3)


def _furn_toilet(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    tank_h = h * 0.36
    bowl_h = h - tank_h
    # Tank (SVG top = wall side)
    _fr(g, x0, y0, w, tank_h, _FC_WET, _FC_DETAIL, 0.4, 2.0)
    # Bowl outer rounded rect
    bowl_rx = min(w * 0.45, bowl_h * 0.50)
    _fr(g, x0, y0 + tank_h, w, bowl_h, _FC_WET, _FC_DETAIL, 0.4, bowl_rx)
    # Seat ring
    sm = w * 0.08
    _fe(g, x0 + w / 2, y0 + tank_h + bowl_h * 0.50,
        (w - 2 * sm) / 2, (bowl_h - sm) / 2, "none", _FC_DETAIL, 0.4)
    # Water (inner ellipse, light blue)
    _fe(g, x0 + w / 2, y0 + tank_h + bowl_h * 0.55,
        (w - 2 * sm) / 2 * 0.72, (bowl_h - sm) / 2 * 0.65,
        "#D8EEF5", _FC_DETAIL, 0.3)


def _furn_sink(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    bm = min(w, h) * 0.10
    # Basin
    _fe(g, x0 + w / 2, y0 + h * 0.58,
        (w - 2 * bm) / 2, (h - 3 * bm) / 2,
        "#D8EEF5", _FC_DETAIL, 0.5)
    # Drain
    dr = min(w, h) * 0.07
    _fc(g, x0 + w / 2, y0 + h * 0.65, dr, _FC_WET, _FC_DETAIL, 0.4)
    # Faucet at back (SVG top = wall)
    fw = min(w * 0.22, 8.0)
    fh = min(h * 0.10, 4.0)
    _fr(g, x0 + w / 2 - fw / 2, y0 + bm * 0.6, fw, fh, _FC_PANEL, _FC_DETAIL, 0.4, fh / 2)


def _furn_washing_machine(x0: float, y0: float, w: float, h: float,
                           g: ET.Element) -> None:
    r = min(w, h) * 0.35
    _fc(g, x0 + w / 2, y0 + h / 2, r, "#D8EEF5", _FC_DETAIL, 0.6)
    _fc(g, x0 + w / 2, y0 + h / 2, r * 0.62, "#B8D8E8", _FC_DETAIL, 0.4)
    _fc(g, x0 + w / 2, y0 + h / 2, r * 0.12, _FC_PANEL, _FC_STROKE, 0.4)
    # Control panel strip at top
    cp_h = min(h * 0.15, 5.0)
    cm = min(w, h) * 0.06
    _fr(g, x0 + cm, y0 + cm, w - 2 * cm, cp_h, _FC_SOFT, _FC_DETAIL, 0.3)


def _furn_bookshelf(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    n = max(3, min(5, round(h / 14)))
    sh = h / n
    bd = min(w * 0.14, 5.0)
    _fl(g, x0 + bd, y0, x0 + bd, y0 + h, _FC_DETAIL, 0.4)
    for i in range(1, n):
        _fl(g, x0, y0 + i * sh, x0 + w, y0 + i * sh, _FC_DETAIL, 0.4)
    book_colors = ["#A8C8A0", "#C8A8C0", "#C8C080", "#A8B8C8", "#C8A888"]
    for shelf in range(n):
        sy = y0 + shelf * sh
        bx = x0 + bd + 1.5
        ci = 0
        while bx < x0 + w - 1.5:
            bw = max(3.0, min(8.0, (w - bd) * (0.09 + ci % 3 * 0.025)))
            _fr(g, bx, sy + sh * 0.14, bw, sh * 0.72,
                book_colors[ci % 5], "none", 0)
            bx += bw + 0.8
            ci += 1


def _furn_dresser(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    n = max(3, min(5, round(h / 18)))
    dh = h / n
    m = max(1.0, min(w, h) * 0.04)
    for i in range(n):
        dy = y0 + i * dh
        _fr(g, x0 + m, dy + m * 0.5, w - 2 * m, dh - m, "none", _FC_DETAIL, 0.4)
        hw = min(w * 0.22, 12.0)
        hh = max(1.5, dh * 0.14)
        _fr(g, x0 + w / 2 - hw / 2, dy + (dh - hh) / 2,
            hw, hh, _FC_PANEL, _FC_DETAIL, 0.4, hh / 2)


def _furn_generic(x0: float, y0: float, w: float, h: float, g: ET.Element) -> None:
    m = max(1.5, min(w, h) * 0.07)
    if w > 6 and h > 6:
        _fr(g, x0 + m, y0 + m, w - 2 * m, h - 2 * m, "none", _FC_DETAIL, 0.3)


_FURN_DRAW: dict[str, object] = {
    "sofa":            _furn_sofa,
    "armchair":        _furn_armchair,
    "dining_chair":    _furn_chair,
    "office_chair":    _furn_office_chair,
    "dining_table":    _furn_dining_table,
    "coffee_table":    _furn_coffee_table,
    "desk":            _furn_desk,
    "bed":             _furn_bed,
    "wardrobe":        _furn_wardrobe,
    "dresser":         _furn_dresser,
    "bookshelf":       _furn_bookshelf,
    "tv_unit":         _furn_tv_unit,
    "kitchen_counter": _furn_kitchen_counter,
    "island":          _furn_island,
    "bathtub":         _furn_bathtub,
    "shower":          _furn_shower,
    "toilet":          _furn_toilet,
    "sink":            _furn_sink,
    "washing_machine": _furn_washing_machine,
}


def _render_furniture(furniture, vt: ViewTransform, parent: ET.Element) -> None:
    """Render a Furniture item with a category-specific architectural symbol."""
    cat_val: str = furniture.category.value

    # Bounding box of the footprint in SVG pixel space
    pts_svg = [vt.pt_to_svg(p) for p in furniture.footprint.exterior]
    if not pts_svg:
        return
    xs = [p[0] for p in pts_svg]
    ys = [p[1] for p in pts_svg]
    x0, y0 = min(xs), min(ys)
    w,  h  = max(xs) - x0, max(ys) - y0
    if w < 1.0 or h < 1.0:
        return

    # 1 — Base footprint polygon (background colour + border)
    base_fill = _FURN_BASE_FILL.get(cat_val, _FC_BASE)
    d_poly = _polygon_path(pts_svg)
    ET.SubElement(parent, "path", {
        "d": d_poly,
        "fill": base_fill,
        "stroke": _FC_STROKE,
        "stroke-width": "0.7",
        "class": f"furniture {cat_val}",
    })

    # 2 — Symbol detail elements (category-specific)
    g = ET.SubElement(parent, "g", {"class": "furn-detail"})
    draw_fn = _FURN_DRAW.get(cat_val, _furn_generic)  # type: ignore[assignment]
    draw_fn(x0, y0, w, h, g)  # type: ignore[call-arg]

    # 3 — Label with a translucent white backing for readability
    label = furniture.label or cat_val.replace("_", " ").title()
    cx_svg = x0 + w / 2
    # Tall pieces (bed, wardrobe): label in lower 25 % to clear the symbol
    label_y = y0 + (h * 0.78 if h > w * 1.3 else h / 2)
    fs = max(4.5, min(7.5, min(w, h) * 0.19))
    lw = len(label) * fs * 0.52
    lh_bg = fs + 2.0
    ET.SubElement(parent, "rect", {
        "x": f"{cx_svg - lw / 2 - 1.0:.2f}",
        "y": f"{label_y - lh_bg / 2:.2f}",
        "width": f"{lw + 2.0:.2f}",
        "height": f"{lh_bg:.2f}",
        "fill": "#ffffff", "fill-opacity": "0.65", "stroke": "none",
    })
    ET.SubElement(parent, "text", {
        "x": f"{cx_svg:.2f}", "y": f"{label_y:.2f}",
        "text-anchor": "middle", "dominant-baseline": "middle",
        "fill": _FC_DARK, "font-size": f"{fs:.1f}",
        "font-family": "sans-serif", "font-weight": "500",
        "pointer-events": "none",
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


def _render_staircase(stair, vt: ViewTransform, parent: ET.Element) -> None:
    """Render a Staircase: boundary outline + tread lines + direction arrow."""
    import math as _math
    d = _polygon2d_path(stair.boundary, vt)
    ET.SubElement(parent, "path", {
        "d": d, "fill": PALETTE["stair_fill"],
        "stroke": PALETTE["stair_stroke"], "stroke-width": "0.75",
        "class": "staircase",
    })
    # Draw tread lines parallel to width direction
    bb = stair.boundary.bounding_box()
    sx0, sy0 = vt.to_svg(bb.min_corner.x, bb.min_corner.y)
    sx1, sy1 = vt.to_svg(bb.max_corner.x, bb.max_corner.y)
    cos_d = _math.cos(stair.direction + _math.pi / 2)
    sin_d = _math.sin(stair.direction + _math.pi / 2)
    step_size = vt.scale(stair.run_depth)
    travel_len = max(abs(sx1 - sx0), abs(sy1 - sy0))
    n_treads = max(1, int(travel_len / max(step_size, 1)))
    cx = (sx0 + sx1) / 2
    cy = (sy0 + sy1) / 2
    half_w = max(abs(sx1 - sx0), abs(sy1 - sy0)) * 0.4
    tread_g = ET.SubElement(parent, "g", {"clip-path": f"path('{d}')"})
    for i in range(n_treads + 1):
        t = -0.5 + i / max(n_treads, 1)
        dx = _math.cos(stair.direction) * travel_len * t
        dy = -_math.sin(stair.direction) * travel_len * t
        lx1 = cx + dx - cos_d * half_w
        ly1 = cy + dy + sin_d * half_w
        lx2 = cx + dx + cos_d * half_w
        ly2 = cy + dy - sin_d * half_w
        ET.SubElement(tread_g, "line", {
            "x1": str(round(lx1, 2)), "y1": str(round(ly1, 2)),
            "x2": str(round(lx2, 2)), "y2": str(round(ly2, 2)),
            "stroke": PALETTE["stair_stroke"], "stroke-width": "0.4",
        })


def _render_slab(slab, vt: ViewTransform, parent: ET.Element) -> None:
    """Render a Slab: dashed boundary outline."""
    from archit_app.elements.slab import SlabType
    d = _polygon2d_path(slab.boundary, vt)
    dash = "4 3" if slab.slab_type == SlabType.FLOOR else "2 2"
    ET.SubElement(parent, "path", {
        "d": d, "fill": PALETTE["slab_fill"],
        "stroke": PALETTE["slab_stroke"], "stroke-width": "0.75",
        "stroke-dasharray": dash, "class": "slab",
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
    visible_layers: set[str] | None = None,
    material_library=None,
) -> str:
    """
    Render a Level as an SVG string.

    Args:
        level: the floor level to render
        pixels_per_meter: drawing scale (default 50 px/m ≈ 1:20 at 96dpi)
        margin: padding around the drawing in pixels
        title: optional title drawn at the top
        palette: optional dict to override default colors
        visible_layers: when provided, only elements whose ``layer`` name is
            in this set are rendered.  Pass ``None`` (default) to render all
            layers regardless of visibility.
        material_library: optional :class:`~archit_app.elements.material.MaterialLibrary`
            instance.  When provided, elements with a ``material`` name that
            exists in the library will use the material's ``color_hex`` as their
            fill colour instead of the default palette colour.

    Returns:
        SVG XML as a string (UTF-8)
    """
    global PALETTE
    if palette:
        PALETTE = {**PALETTE, **palette}

    def _visible(element) -> bool:
        """Return True if the element's layer should be rendered."""
        if visible_layers is None:
            return True
        return getattr(element, "layer", "") in visible_layers

    def _material_color(element, default: str) -> str:
        """Return the material's hex colour if available, else *default*."""
        if material_library is None:
            return default
        mat_name = getattr(element, "material", None)
        if mat_name is None:
            return default
        mat = material_library.get(mat_name)
        return mat.color_hex if mat is not None else default

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
        if _visible(room):
            _render_room(room, vt, room_group)

    # Slabs (above rooms, below ramps)
    visible_slabs = [s for s in level.slabs if _visible(s)]
    if visible_slabs:
        slab_group = ET.SubElement(svg, "g", {"id": "slabs"})
        for slab in visible_slabs:
            _render_slab(slab, vt, slab_group)

    # Ramps (above slabs, below staircases)
    visible_ramps = [r for r in level.ramps if _visible(r)]
    if visible_ramps:
        ramp_group = ET.SubElement(svg, "g", {"id": "ramps"})
        for ramp in visible_ramps:
            _render_ramp(ramp, vt, ramp_group)

    # Staircases (above ramps, below walls)
    visible_stairs = [s for s in level.staircases if _visible(s)]
    if visible_stairs:
        stair_group = ET.SubElement(svg, "g", {"id": "staircases"})
        for stair in visible_stairs:
            _render_staircase(stair, vt, stair_group)

    # Walls layer
    wall_group = ET.SubElement(svg, "g", {"id": "walls"})
    for wall in level.walls:
        if _visible(wall):
            _render_wall(wall, vt, wall_group,
                         fill_override=_material_color(wall, PALETTE["wall_fill"]) or None)
            for opening in wall.openings:
                if _visible(opening):
                    _render_opening(opening, vt, wall_group)

    # Level-standalone openings
    opening_group = ET.SubElement(svg, "g", {"id": "openings"})
    for opening in level.openings:
        if _visible(opening):
            _render_opening(opening, vt, opening_group)

    # Beams (above walls)
    visible_beams = [b for b in level.beams if _visible(b)]
    if visible_beams:
        beam_group = ET.SubElement(svg, "g", {"id": "beams"})
        for beam in visible_beams:
            _render_beam(beam, vt, beam_group)

    # Columns layer
    col_group = ET.SubElement(svg, "g", {"id": "columns"})
    for col in level.columns:
        if _visible(col):
            _render_column(col, vt, col_group,
                           fill_override=_material_color(col, PALETTE["column_fill"]) or None)

    # Furniture layer
    visible_furn = [f for f in level.furniture if _visible(f)]
    if visible_furn:
        furn_group = ET.SubElement(svg, "g", {"id": "furniture"})
        for furn in visible_furn:
            _render_furniture(furn, vt, furn_group)

    # Dimensions layer
    visible_dims = [d for d in level.dimensions if _visible(d)]
    if visible_dims:
        dim_group = ET.SubElement(svg, "g", {"id": "dimensions"})
        for dim in visible_dims:
            _render_dimension_line(dim, vt, dim_group)

    # Section marks layer
    visible_marks = [m for m in level.section_marks if _visible(m)]
    if visible_marks:
        sec_group = ET.SubElement(svg, "g", {"id": "section-marks"})
        for mark in visible_marks:
            _render_section_mark(mark, vt, sec_group)

    # Text annotations (topmost)
    visible_anns = [a for a in level.text_annotations if _visible(a)]
    if visible_anns:
        ann_group = ET.SubElement(svg, "g", {"id": "annotations"})
        for ann in visible_anns:
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
    # Build the set of visible layer names from the building's layer registry.
    # Unknown layer names (elements whose layer field isn't in the registry)
    # are always visible.
    if building.layers:
        visible_layers: set[str] | None = {
            name for name, lyr in building.layers.items() if lyr.visible
        }
        # Elements on unregistered layers should still appear — add a sentinel
        # that won't match any real layer name to keep _visible() returning True
        # for those. We do this by passing None when ALL layers are visible.
        if len(visible_layers) == len(building.layers):
            # All registered layers visible → treat as no filter
            visible_layers = None
    else:
        visible_layers = None

    pages = []
    for level in building.levels:
        title = level.name or f"Level {level.index} — {building.metadata.name}"
        svg_str = level_to_svg(
            level,
            pixels_per_meter=pixels_per_meter,
            margin=margin,
            title=title,
            visible_layers=visible_layers,
        )
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
