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

# Brand palette (canonical):
#   Void      #0C1018  — primary linework / dark
#   Vellum    #E8EDF5  — paper / background
#   Blueprint #3B82F6  — annotations / labels
#   Datum     #F59E0B  — dimensions / highlights
BRAND_VOID = "#0C1018"
BRAND_VELLUM = "#E8EDF5"
BRAND_BLUEPRINT = "#3B82F6"
BRAND_DATUM = "#F59E0B"

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
    # Brand tokens
    "brand_void": BRAND_VOID,
    "brand_vellum": BRAND_VELLUM,
    "brand_blueprint": BRAND_BLUEPRINT,
    "brand_datum": BRAND_DATUM,
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
    # Room label is rendered separately (top-most layer) by _render_room_label
    # so it sits above walls / furniture / dimensions.


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

    # Window glazing (two parallel thin lines spanning the width).
    if opening.kind in (OpeningKind.WINDOW, OpeningKind.PASS_THROUGH):
        _render_window_glazing(None, vt, opening, parent)


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
    *,
    building: Building | None = None,
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

    # Widen the top margin to leave room for the title block (top-right) and
    # north arrow.  Bump bottom slightly for the scale bar tick labels.
    top_pad_extra = 60.0
    bottom_pad_extra = 18.0
    effective_margin = max(margin, MARGIN_PX)
    vt = ViewTransform(bbox, pixels_per_meter, effective_margin)
    # Stretch the SVG height so the title block / scale bar don't overlap drawing.
    vt.svg_height += top_pad_extra + bottom_pad_extra
    # Shift the world by `top_pad_extra` so the drawing starts below the title.
    # We do this by overriding the y-flip to offset by the extra top padding.
    vt.world_max_y = vt.world_max_y + (top_pad_extra / vt.ppm)

    svg = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": str(round(vt.svg_width)),
        "height": str(round(vt.svg_height)),
        "viewBox": f"0 0 {vt.svg_width:.2f} {vt.svg_height:.2f}",
    })

    # Background — Vellum (paper)
    ET.SubElement(svg, "rect", {
        "width": "100%", "height": "100%",
        "fill": PALETTE["brand_vellum"],
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

    # Walls layer (wall bodies only)
    wall_group = ET.SubElement(svg, "g", {"id": "walls"})
    wall_openings: list = []
    for wall in level.walls:
        if _visible(wall):
            _render_wall(wall, vt, wall_group,
                         fill_override=_material_color(wall, PALETTE["wall_fill"]) or None)
            wall_openings.extend(op for op in wall.openings if _visible(op))

    # Openings layer — wall openings + standalone openings, all in one group
    # so the "Openings" toggle hides/shows every door and window at once.
    opening_group = ET.SubElement(svg, "g", {"id": "openings"})
    all_openings: list[Opening] = []
    for opening in wall_openings:
        _render_opening(opening, vt, opening_group)
        all_openings.append(opening)
    for opening in level.openings:
        if _visible(opening):
            _render_opening(opening, vt, opening_group)
            all_openings.append(opening)

    # Door swing arcs (separate group so they overlay the leaf cleanly).
    swing_group = ET.SubElement(svg, "g", {"id": "door-swings"})
    for opening in all_openings:
        if opening.kind == OpeningKind.DOOR:
            _render_door_swing(svg, vt, opening, level.rooms, swing_group)

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

    # Per-room labels (bold name + area), top-most so they always read.
    room_label_group = ET.SubElement(svg, "g", {"id": "room-labels"})
    for room in level.rooms:
        if _visible(room):
            _render_room_label(room, vt, room_label_group)

    # Dimension chains on exterior walls (mm).
    ext_walls = _exterior_walls(level)
    _render_dimensions(svg, vt, ext_walls)

    # Scale bar (bottom-left, 5 m in 1 m increments).
    _render_scale_bar(svg, vt, pixels_per_meter)

    # Title block (top-right) + north arrow underneath.
    if title is None:
        title = level.name or f"Level {level.index}"

    project_name = ""
    project_number = ""
    date_label = ""
    north_angle_deg = 0.0
    if building is not None:
        project_name = building.metadata.name or ""
        project_number = building.metadata.project_number or ""
        date_label = building.metadata.date or ""
        if building.land is not None:
            north_angle_deg = float(getattr(building.land, "north_angle", 0.0) or 0.0)
    if not project_name:
        project_name = title
    if not date_label:
        try:
            import datetime as _dt
            date_label = _dt.date.today().isoformat()
        except Exception:
            date_label = ""

    level_label = level.name or f"Level {level.index}"
    scale_label = _format_scale_label(pixels_per_meter)

    bx, by, block_w, block_h = _render_title_block(
        svg, vt,
        project_name=project_name,
        project_number=project_number,
        level_label=level_label,
        scale_label=scale_label,
        date_label=date_label,
    )
    # North arrow: centered under the title block, padded.
    arrow_cx = bx + block_w - 24.0
    arrow_cy = by + block_h + 26.0
    _render_north_arrow(svg, vt, north_angle_deg, anchor_x=arrow_cx, anchor_y=arrow_cy)

    ET.indent(svg, space="  ")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(svg, encoding="unicode")


def _render_scale_bar(svg: ET.Element, vt: ViewTransform, pixels_per_meter: float) -> None:
    """Draw a 5-meter scale bar in 1 m increments at the bottom-left of the SVG.

    Renders alternating black/white cells (typical architectural scale bar).
    """
    n_segments = 5
    seg_px = pixels_per_meter  # 1 m per segment
    bar_x = vt.margin
    bar_y = vt.svg_height - vt.margin * 0.55
    bar_h = 5.0

    g = ET.SubElement(svg, "g", {"id": "scale-bar"})
    # Outer outline
    ET.SubElement(g, "rect", {
        "x": f"{bar_x:.2f}",
        "y": f"{bar_y - bar_h:.2f}",
        "width": f"{seg_px * n_segments:.2f}",
        "height": f"{bar_h:.2f}",
        "fill": "none",
        "stroke": PALETTE["brand_void"],
        "stroke-width": "0.6",
    })
    # Alternating segments
    for i in range(n_segments):
        fill = PALETTE["brand_void"] if i % 2 == 0 else "#FFFFFF"
        ET.SubElement(g, "rect", {
            "x": f"{bar_x + i * seg_px:.2f}",
            "y": f"{bar_y - bar_h:.2f}",
            "width": f"{seg_px:.2f}",
            "height": f"{bar_h:.2f}",
            "fill": fill,
            "stroke": PALETTE["brand_void"],
            "stroke-width": "0.4",
        })
    # Tick labels at 0, 1, 2, ..., 5
    for i in range(n_segments + 1):
        tx = bar_x + i * seg_px
        ET.SubElement(g, "text", {
            "x": f"{tx:.2f}",
            "y": f"{bar_y + 9:.2f}",
            "text-anchor": "middle",
            "font-family": "sans-serif",
            "font-size": "7",
            "fill": PALETTE["brand_void"],
        }).text = f"{i}"
    # Unit label
    ET.SubElement(g, "text", {
        "x": f"{bar_x + n_segments * seg_px + 6:.2f}",
        "y": f"{bar_y - 1:.2f}",
        "font-family": "sans-serif",
        "font-size": "7",
        "fill": PALETTE["brand_void"],
    }).text = "m"


# ---------------------------------------------------------------------------
# Polished-export helpers (title block, north arrow, dimensions, swings, glazing)
# ---------------------------------------------------------------------------

def _format_scale_label(pixels_per_meter: float) -> str:
    """Convert pixels_per_meter to a friendly scale string like '1:50'.

    Assumes the SVG is rendered/printed at 96 DPI (≈ 3.7795 px/mm). One world
    metre = pixels_per_meter pixels = pixels_per_meter / 3.7795 mm on paper.
    The drawing scale is then 1 : (1000 / (px_per_mm)).
    """
    if pixels_per_meter <= 0:
        return "1:?"
    px_per_mm = 96.0 / 25.4
    mm_per_world_m = pixels_per_meter / px_per_mm
    if mm_per_world_m <= 0:
        return "1:?"
    denom = 1000.0 / mm_per_world_m
    # Round to a nice architectural scale
    nice = [10, 20, 25, 50, 100, 200, 500, 1000]
    closest = min(nice, key=lambda v: abs(v - denom))
    return f"1:{closest}"


def _render_title_block(
    svg: ET.Element,
    vt: ViewTransform,
    *,
    project_name: str,
    project_number: str,
    level_label: str,
    scale_label: str,
    date_label: str,
) -> tuple[float, float, float, float]:
    """Render a title block in the top-right corner.

    Returns the (x, y, width, height) bounds of the block so the caller can
    place the north arrow directly underneath without overlapping.
    """
    block_w = 180.0
    block_h = 78.0
    pad = 6.0
    bx = vt.svg_width - vt.margin * 0.5 - block_w
    by = vt.margin * 0.4

    g = ET.SubElement(svg, "g", {"id": "title-block"})
    # Outer frame
    ET.SubElement(g, "rect", {
        "x": f"{bx:.2f}", "y": f"{by:.2f}",
        "width": f"{block_w:.2f}", "height": f"{block_h:.2f}",
        "fill": "#FFFFFF", "fill-opacity": "0.9",
        "stroke": PALETTE["brand_void"], "stroke-width": "0.8",
    })
    # ARCHIT wordmark (top strip)
    strip_h = 16.0
    ET.SubElement(g, "rect", {
        "x": f"{bx:.2f}", "y": f"{by:.2f}",
        "width": f"{block_w:.2f}", "height": f"{strip_h:.2f}",
        "fill": PALETTE["brand_void"], "stroke": "none",
    })
    ET.SubElement(g, "text", {
        "x": f"{bx + pad:.2f}",
        "y": f"{by + strip_h * 0.68:.2f}",
        "font-family": "sans-serif",
        "font-size": "10",
        "font-weight": "bold",
        "letter-spacing": "2",
        "fill": PALETTE["brand_vellum"],
    }).text = "ARCHIT"
    ET.SubElement(g, "text", {
        "x": f"{bx + block_w - pad:.2f}",
        "y": f"{by + strip_h * 0.68:.2f}",
        "text-anchor": "end",
        "font-family": "sans-serif",
        "font-size": "7",
        "fill": PALETTE["brand_datum"],
    }).text = scale_label

    # Body lines
    line_y = by + strip_h + 12.0
    line_h = 11.0

    def _row(label: str, value: str, y: float, value_color: str | None = None) -> None:
        ET.SubElement(g, "text", {
            "x": f"{bx + pad:.2f}", "y": f"{y:.2f}",
            "font-family": "sans-serif", "font-size": "6.5",
            "fill": PALETTE["brand_void"], "font-weight": "bold",
            "letter-spacing": "0.5",
        }).text = label.upper()
        ET.SubElement(g, "text", {
            "x": f"{bx + pad:.2f}", "y": f"{y + line_h * 0.85:.2f}",
            "font-family": "sans-serif", "font-size": "8.5",
            "fill": value_color or PALETTE["brand_void"],
        }).text = value or "—"

    _row("Project", project_name or "(unnamed project)", line_y)
    if project_number:
        _row("No.", project_number, line_y + line_h * 1.7)
        _row("Date / Sheet", f"{date_label}   ·   {level_label}",
             line_y + line_h * 3.4, value_color=PALETTE["brand_blueprint"])
    else:
        _row("Date / Sheet", f"{date_label}   ·   {level_label}",
             line_y + line_h * 1.7, value_color=PALETTE["brand_blueprint"])

    return bx, by, block_w, block_h


def _render_north_arrow(
    svg: ET.Element,
    vt: ViewTransform,
    north_angle_deg: float,
    *,
    anchor_x: float,
    anchor_y: float,
) -> None:
    """Draw a north arrow at (anchor_x, anchor_y) — center of the symbol.

    *north_angle_deg* is degrees clockwise from world +Y to geographic north.
    World +Y maps to SVG -Y (Y-flip), so a 0° north points "up" in the SVG.
    """
    r = 18.0
    g = ET.SubElement(svg, "g", {"id": "north-arrow"})
    # Background circle
    ET.SubElement(g, "circle", {
        "cx": f"{anchor_x:.2f}", "cy": f"{anchor_y:.2f}", "r": f"{r:.2f}",
        "fill": "#FFFFFF", "fill-opacity": "0.85",
        "stroke": PALETTE["brand_void"], "stroke-width": "0.6",
    })
    # The needle: a slim isoceles triangle pointing to north
    # Compass bearing → SVG angle. Positive bearing rotates CW; in SVG +X right,
    # +Y down, so a 0° bearing should point to (0, -1).
    ang = math.radians(north_angle_deg)
    # Tip
    tip_x = anchor_x + math.sin(ang) * (r - 2)
    tip_y = anchor_y - math.cos(ang) * (r - 2)
    # Base perpendicular
    base_left_x = anchor_x + math.sin(ang + math.pi) * (r - 2) * 0.35 + math.cos(ang) * 4
    base_left_y = anchor_y - math.cos(ang + math.pi) * (r - 2) * 0.35 + math.sin(ang) * 4
    base_right_x = anchor_x + math.sin(ang + math.pi) * (r - 2) * 0.35 - math.cos(ang) * 4
    base_right_y = anchor_y - math.cos(ang + math.pi) * (r - 2) * 0.35 - math.sin(ang) * 4
    # Filled half (right of axis) in Datum, hollow half in Void
    cx, cy = anchor_x, anchor_y
    ET.SubElement(g, "path", {
        "d": (f"M {tip_x:.2f} {tip_y:.2f} "
              f"L {base_right_x:.2f} {base_right_y:.2f} "
              f"L {cx:.2f} {cy:.2f} Z"),
        "fill": PALETTE["brand_datum"],
        "stroke": PALETTE["brand_void"],
        "stroke-width": "0.5",
    })
    ET.SubElement(g, "path", {
        "d": (f"M {tip_x:.2f} {tip_y:.2f} "
              f"L {base_left_x:.2f} {base_left_y:.2f} "
              f"L {cx:.2f} {cy:.2f} Z"),
        "fill": "#FFFFFF",
        "stroke": PALETTE["brand_void"],
        "stroke-width": "0.5",
    })
    # "N" label outside the tip
    label_x = anchor_x + math.sin(ang) * (r + 6)
    label_y = anchor_y - math.cos(ang) * (r + 6)
    ET.SubElement(g, "text", {
        "x": f"{label_x:.2f}", "y": f"{label_y:.2f}",
        "text-anchor": "middle", "dominant-baseline": "middle",
        "font-family": "sans-serif", "font-size": "9", "font-weight": "bold",
        "fill": PALETTE["brand_void"],
    }).text = "N"


def _exterior_walls(level: Level) -> list[Wall]:
    """Return walls flagged as exterior (best-effort)."""
    from archit_app.elements.wall import WallType
    return [w for w in level.walls if getattr(w, "wall_type", None) == WallType.EXTERIOR]


def _render_dimensions(
    svg: ET.Element,
    vt: ViewTransform,
    exterior_walls: list[Wall],
) -> None:
    """Annotate each exterior wall segment with its length in mm.

    The label is placed perpendicular to the wall, offset 300 mm to the
    *outside*. The outside direction is approximated by the left-hand normal
    of the start→end vector (matches Wall.straight convention).
    """
    if not exterior_walls:
        return
    g = ET.SubElement(svg, "g", {"id": "exterior-dimensions"})
    offset_world = 0.3  # 300 mm
    tick = 4.0  # px
    for wall in exterior_walls:
        sp = wall.start_point
        ep = wall.end_point
        if sp is None or ep is None:
            continue
        ax, ay = sp
        bx, by = ep
        dx = bx - ax
        dy = by - ay
        length_m = math.hypot(dx, dy)
        if length_m < 0.05:
            continue
        # Outward normal = left-hand normal of (ax,ay)->(bx,by) in world space
        nx = -dy / length_m
        ny = dx / length_m
        # Offset endpoints
        ox1 = ax + nx * offset_world
        oy1 = ay + ny * offset_world
        ox2 = bx + nx * offset_world
        oy2 = by + ny * offset_world
        # Convert to SVG
        sx1, sy1 = vt.to_svg(ox1, oy1)
        sx2, sy2 = vt.to_svg(ox2, oy2)
        # Wall endpoints in SVG (for extension lines)
        wsx1, wsy1 = vt.to_svg(ax, ay)
        wsx2, wsy2 = vt.to_svg(bx, by)
        stroke = PALETTE["brand_datum"]
        # Extension lines
        ET.SubElement(g, "line", {
            "x1": f"{wsx1:.2f}", "y1": f"{wsy1:.2f}",
            "x2": f"{sx1:.2f}", "y2": f"{sy1:.2f}",
            "stroke": stroke, "stroke-width": "0.3",
        })
        ET.SubElement(g, "line", {
            "x1": f"{wsx2:.2f}", "y1": f"{wsy2:.2f}",
            "x2": f"{sx2:.2f}", "y2": f"{sy2:.2f}",
            "stroke": stroke, "stroke-width": "0.3",
        })
        # Dimension line
        ET.SubElement(g, "line", {
            "x1": f"{sx1:.2f}", "y1": f"{sy1:.2f}",
            "x2": f"{sx2:.2f}", "y2": f"{sy2:.2f}",
            "stroke": stroke, "stroke-width": "0.5",
        })
        # End ticks (perpendicular short strokes)
        # tick direction in SVG = along the dim line, rotated 90°
        ddx = sx2 - sx1
        ddy = sy2 - sy1
        dd_len = math.hypot(ddx, ddy) or 1.0
        tdx = -ddy / dd_len * (tick / 2)
        tdy = ddx / dd_len * (tick / 2)
        for px, py in ((sx1, sy1), (sx2, sy2)):
            ET.SubElement(g, "line", {
                "x1": f"{px - tdx:.2f}", "y1": f"{py - tdy:.2f}",
                "x2": f"{px + tdx:.2f}", "y2": f"{py + tdy:.2f}",
                "stroke": stroke, "stroke-width": "0.5",
            })
        # Label centered above the dimension line
        mx = (sx1 + sx2) / 2
        my = (sy1 + sy2) / 2
        label_offset = 7.0
        # Push label further out (additional perpendicular)
        lx = mx + (-ddy / dd_len) * label_offset
        ly = my + (ddx / dd_len) * label_offset
        # Compute rotation so text reads along the wall (avoid upside-down)
        ang = math.degrees(math.atan2(ddy, ddx))
        if ang > 90:
            ang -= 180
        elif ang < -90:
            ang += 180
        mm_label = f"{int(round(length_m * 1000))}"
        ET.SubElement(g, "text", {
            "x": f"{lx:.2f}", "y": f"{ly:.2f}",
            "text-anchor": "middle", "dominant-baseline": "middle",
            "font-family": "sans-serif", "font-size": "7",
            "fill": stroke,
            "transform": f"rotate({ang:.2f},{lx:.2f},{ly:.2f})",
        }).text = mm_label


def _opening_long_axis(opening: Opening) -> tuple[Point2D, Point2D] | None:
    """Return the two endpoints of the longer axis of the opening polygon.

    For typical door/window openings this is the line that runs along the wall
    centre-line within the opening footprint.
    """
    pts = list(opening.geometry.exterior)
    if len(pts) < 4:
        return None
    # Pick the longest pair among consecutive midpoints of opposite edges.
    n = len(pts)
    # Edge midpoints
    edge_mids = []
    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        edge_mids.append(Point2D(x=(a.x + b.x) / 2, y=(a.y + b.y) / 2))
    # Pair opposite edges (assume rectangle: 0↔2 and 1↔3)
    pair_a = (edge_mids[0], edge_mids[2 % n])
    pair_b = (edge_mids[1 % n], edge_mids[3 % n])
    da = pair_a[0].distance_to(pair_a[1]) if hasattr(pair_a[0], "distance_to") else math.hypot(
        pair_a[0].x - pair_a[1].x, pair_a[0].y - pair_a[1].y)
    db = pair_b[0].distance_to(pair_b[1]) if hasattr(pair_b[0], "distance_to") else math.hypot(
        pair_b[0].x - pair_b[1].x, pair_b[0].y - pair_b[1].y)
    if da >= db:
        return pair_a
    return pair_b


def _render_door_swing(
    svg: ET.Element,
    vt: ViewTransform,
    opening: Opening,
    rooms: Iterable[Room],
    parent: ET.Element,
) -> None:
    """Render a 90° dashed swing arc for a door opening.

    Hinge = endpoint of the opening's long axis closest to a room's centroid.
    The arc sweeps from the closed-leaf direction toward the room interior.
    """
    if opening.kind != OpeningKind.DOOR:
        return
    axis = _opening_long_axis(opening)
    if axis is None:
        return
    p1, p2 = axis
    # Pick the nearest room centroid to determine which side is interior.
    rooms_list = list(rooms)
    target = None
    if rooms_list:
        # Use the centre of the opening as the probe
        cx = (p1.x + p2.x) / 2
        cy = (p1.y + p2.y) / 2
        target = min(
            rooms_list,
            key=lambda r: math.hypot(r.boundary.centroid.x - cx,
                                     r.boundary.centroid.y - cy),
        )
    # Determine hinge endpoint:
    # If the opening already carries a SwingGeometry, use its arc directly.
    if opening.swing is not None:
        try:
            arc_pts = [vt.pt_to_svg(p) for p in opening.swing.arc.to_polyline(24)]
        except Exception:
            arc_pts = []
        if arc_pts:
            d_arc = f"M {arc_pts[0][0]:.2f} {arc_pts[0][1]:.2f}"
            for x, y in arc_pts[1:]:
                d_arc += f" L {x:.2f} {y:.2f}"
            ET.SubElement(parent, "path", {
                "d": d_arc, "fill": "none",
                "stroke": PALETTE["brand_void"],
                "stroke-width": "0.4",
                "stroke-dasharray": "2 2",
                "class": "door-swing",
            })
            return
    # Otherwise derive an arc geometrically.
    if target is None:
        # Default: hinge = p1, sweep into +normal side
        hinge = p1
        far = p2
    else:
        d1 = math.hypot(target.boundary.centroid.x - p1.x,
                        target.boundary.centroid.y - p1.y)
        d2 = math.hypot(target.boundary.centroid.x - p2.x,
                        target.boundary.centroid.y - p2.y)
        if d1 <= d2:
            hinge, far = p1, p2
        else:
            hinge, far = p2, p1
    # Vector from hinge to far end (along wall) — this is the "closed leaf"
    vx = far.x - hinge.x
    vy = far.y - hinge.y
    leaf_len = math.hypot(vx, vy)
    if leaf_len < 1e-6:
        return
    # Two candidate sweep ends: rotate 90° CW or CCW about hinge
    # Candidate A: CCW (rotate by +90°): (-vy, vx)
    cand_a = (hinge.x - vy, hinge.y + vx)
    cand_b = (hinge.x + vy, hinge.y - vx)
    # Pick whichever is closer to the room centroid (interior direction)
    if target is not None:
        rcx = target.boundary.centroid.x
        rcy = target.boundary.centroid.y
        if (math.hypot(cand_a[0] - rcx, cand_a[1] - rcy)
                <= math.hypot(cand_b[0] - rcx, cand_b[1] - rcy)):
            sweep_end = cand_a
            sweep_flag = 0  # CCW in world; gets flipped in SVG
        else:
            sweep_end = cand_b
            sweep_flag = 1
    else:
        sweep_end = cand_a
        sweep_flag = 0
    # Draw the closed-leaf line + arc using SVG arc command.
    hsx, hsy = vt.pt_to_svg(hinge)
    fsx, fsy = vt.pt_to_svg(Point2D(x=far.x, y=far.y))
    esx, esy = vt.pt_to_svg(Point2D(x=sweep_end[0], y=sweep_end[1]))
    radius_px = vt.scale(leaf_len)
    # World CCW (sweep_flag=0) becomes SVG CW because Y is flipped → so swap
    svg_sweep = 1 - sweep_flag
    # Closed-leaf segment
    ET.SubElement(parent, "line", {
        "x1": f"{hsx:.2f}", "y1": f"{hsy:.2f}",
        "x2": f"{fsx:.2f}", "y2": f"{fsy:.2f}",
        "stroke": PALETTE["brand_void"],
        "stroke-width": "0.4",
        "stroke-dasharray": "2 2",
        "class": "door-leaf",
    })
    # Arc from far → sweep_end with center=hinge, radius=leaf length
    d = (f"M {fsx:.2f} {fsy:.2f} "
         f"A {radius_px:.2f} {radius_px:.2f} 0 0 {svg_sweep} {esx:.2f} {esy:.2f}")
    ET.SubElement(parent, "path", {
        "d": d, "fill": "none",
        "stroke": PALETTE["brand_void"],
        "stroke-width": "0.4",
        "stroke-dasharray": "2 2",
        "class": "door-swing",
    })


def _render_window_glazing(
    svg: ET.Element,
    vt: ViewTransform,
    opening: Opening,
    parent: ET.Element,
) -> None:
    """Draw two parallel thin lines spanning the window opening width.

    The lines run along the long axis of the opening polygon, offset slightly
    to either side of the centre-line (to suggest inner / outer glass face).
    """
    if opening.kind not in (OpeningKind.WINDOW, OpeningKind.PASS_THROUGH):
        return
    axis = _opening_long_axis(opening)
    if axis is None:
        return
    p1, p2 = axis
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return
    # Perpendicular unit vector (world)
    nx = -dy / length
    ny = dx / length
    # Offset = ¼ of the wall thickness embodied in the opening footprint
    # Approximate: use the *short* axis length / 4
    short_axis = _polygon_short_extent(opening.geometry)
    off = max(0.02, short_axis * 0.25)
    a1 = (p1.x + nx * off, p1.y + ny * off)
    a2 = (p2.x + nx * off, p2.y + ny * off)
    b1 = (p1.x - nx * off, p1.y - ny * off)
    b2 = (p2.x - nx * off, p2.y - ny * off)
    for (sx0, sy0), (sx1, sy1) in (
        (vt.to_svg(*a1), vt.to_svg(*a2)),
        (vt.to_svg(*b1), vt.to_svg(*b2)),
    ):
        ET.SubElement(parent, "line", {
            "x1": f"{sx0:.2f}", "y1": f"{sy0:.2f}",
            "x2": f"{sx1:.2f}", "y2": f"{sy1:.2f}",
            "stroke": PALETTE["brand_blueprint"],
            "stroke-width": "0.4",
            "class": "window-glazing",
        })


def _polygon_short_extent(poly: Polygon2D) -> float:
    """Return the minimum dimension of the polygon's axis-aligned bbox."""
    bb = poly.bounding_box()
    return min(bb.width, bb.height)


def _render_room_label(room: Room, vt: ViewTransform, parent: ET.Element) -> None:
    """Centred room label: name (bold) + area (regular). Skip if <2 m².

    Auto-rotates to align with the longer axis of the room bounding box.
    """
    try:
        area = room.area
    except Exception:
        area = 0.0
    if area < 2.0:
        return
    name = room.name or room.program or ""
    if not name:
        return
    c = room.boundary.centroid
    cx, cy = vt.pt_to_svg(c)
    # Rotate text along the longer bbox axis
    bb = room.boundary.bounding_box()
    rot_deg = 0.0 if bb.width >= bb.height else -90.0
    transform = f"rotate({rot_deg:.1f},{cx:.2f},{cy:.2f})" if rot_deg else ""
    g = ET.SubElement(parent, "g", {"class": "room-label"})
    if transform:
        g.set("transform", transform)
    # Name
    ET.SubElement(g, "text", {
        "x": f"{cx:.2f}", "y": f"{cy - 4:.2f}",
        "text-anchor": "middle", "dominant-baseline": "middle",
        "font-family": "sans-serif", "font-size": "9",
        "font-weight": "bold",
        "fill": PALETTE["brand_blueprint"],
    }).text = name
    # Area
    ET.SubElement(g, "text", {
        "x": f"{cx:.2f}", "y": f"{cy + 6:.2f}",
        "text-anchor": "middle", "dominant-baseline": "middle",
        "font-family": "sans-serif", "font-size": "7",
        "fill": PALETTE["brand_void"],
    }).text = f"{area:.1f} m²"


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
            building=building,
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
