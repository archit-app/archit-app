"""
PDF export for floorplan levels and buildings.

Requires the optional dependency: pip install archit-app[pdf]  (reportlab >=4)

Each Level is rendered as one PDF page using the same visual style as the SVG
exporter.  The drawing is scaled to fill the chosen paper size while
preserving aspect ratio.  Multi-level buildings are exported as a single
multi-page PDF.

Usage::

    from archit_app.io.pdf import save_level_pdf, save_building_pdf

    # Single level on A3 paper (landscape if the drawing is wider than tall)
    save_level_pdf(level, "ground_floor.pdf", paper_size="A3")

    # All levels in one multi-page PDF
    save_building_pdf(building, "my_house.pdf", paper_size="A4")

    # Get raw PDF bytes (e.g. for HTTP response)
    pdf_bytes = level_to_pdf_bytes(level)
"""

from __future__ import annotations

import io
import math

from archit_app.building.building import Building
from archit_app.building.level import Level
from archit_app.elements.opening import OpeningKind
from archit_app.geometry.bbox import BoundingBox2D
from archit_app.geometry.point import Point2D


# ---------------------------------------------------------------------------
# Optional dependency guard
# ---------------------------------------------------------------------------

def _require_reportlab():
    try:
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib import colors as rl_colors
        from reportlab.lib.pagesizes import A4, A3, A2, A1, letter
        return rl_canvas, rl_colors, {"A1": A1, "A2": A2, "A3": A3, "A4": A4, "letter": letter}
    except ImportError:
        raise ImportError(
            "reportlab is required for PDF export. "
            "Install it with: pip install archit-app[pdf]"
        )


# ---------------------------------------------------------------------------
# Color palette (r, g, b normalised to 0–1)
# ---------------------------------------------------------------------------

def _c(r, g, b):
    return r / 255, g / 255, b / 255


# Brand colors
_BRAND_VOID = _c(0x0C, 0x10, 0x18)
_BRAND_VELLUM = _c(0xE8, 0xED, 0xF5)
_BRAND_BLUEPRINT = _c(0x3B, 0x82, 0xF6)
_BRAND_DATUM = _c(0xF5, 0x9E, 0x0B)


_PAL = {
    "background":    _BRAND_VELLUM,
    "room_fill":     _c(214, 232, 245),
    "room_stroke":   _c( 91, 141, 184),
    "wall_fill":     _c( 74,  74,  74),
    "wall_stroke":   _c( 42,  42,  42),
    "column_fill":   _c(192,  57,  43),
    "column_stroke": _c(146,  43,  33),
    "door_fill":     _c(255, 255, 255),
    "door_stroke":   _c( 91, 141, 184),
    "window_fill":   _c(174, 214, 241),
    "window_stroke": _c( 41, 128, 185),
    "scale_bar":     _BRAND_VOID,
    "room_label":    _BRAND_BLUEPRINT,
    "annotation":    _c(102, 102, 102),
    "brand_void":    _BRAND_VOID,
    "brand_vellum":  _BRAND_VELLUM,
    "brand_blueprint": _BRAND_BLUEPRINT,
    "brand_datum":   _BRAND_DATUM,
    # Extended palette
    "furniture_fill":   _c(255, 248, 220),
    "furniture_stroke": _c(160, 132,  92),
    "beam_stroke":      _c(123,  63,   0),
    "ramp_stroke":      _c( 74, 144, 217),
    "ramp_arrow":       _c( 44,  95, 138),
    "dim_line":         _c(136, 136, 136),
    "dim_text":         _c( 85,  85,  85),
    "section_line":     _c(204,  34,   0),
    "stair_fill":       _c(232, 244, 232),
    "stair_stroke":     _c( 46, 125,  50),
    "slab_stroke":      _c(141, 110,  99),
    "archway_fill":     _c(215, 204, 200),
    "archway_stroke":   _c(109,  76,  65),
}

_MARGIN_PT = 36.0   # 0.5 inch margin


# ---------------------------------------------------------------------------
# Coordinate transform  (world Y-up → PDF Y-up, fitted to page)
# ---------------------------------------------------------------------------

class _VT:
    """
    Maps world coordinates (Y-up, meters) to PDF points (Y-up from page bottom).
    The drawing is fitted inside the page minus margin.
    """

    def __init__(
        self,
        bbox: BoundingBox2D,
        page_w: float,
        page_h: float,
        margin: float,
    ) -> None:
        draw_w = page_w - 2 * margin
        draw_h = page_h - 2 * margin
        sx = draw_w / bbox.width  if bbox.width  > 0 else 1.0
        sy = draw_h / bbox.height if bbox.height > 0 else 1.0
        self.scale  = min(sx, sy)
        self.margin = margin
        self.min_x  = bbox.min_corner.x
        self.min_y  = bbox.min_corner.y
        # Centre the drawing in the available space
        fitted_w = bbox.width  * self.scale
        fitted_h = bbox.height * self.scale
        self.offset_x = margin + (draw_w - fitted_w) / 2
        self.offset_y = margin + (draw_h - fitted_h) / 2

    def __call__(self, x: float, y: float) -> tuple[float, float]:
        px = self.offset_x + (x - self.min_x) * self.scale
        py = self.offset_y + (y - self.min_y) * self.scale   # PDF is Y-up — no flip!
        return px, py

    def pt(self, p: Point2D) -> tuple[float, float]:
        return self(p.x, p.y)

    def s(self, v: float) -> float:
        return v * self.scale


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _set_fill(c, rgb):
    c.setFillColorRGB(*rgb)


def _set_stroke(c, rgb, width: float = 0.5):
    c.setStrokeColorRGB(*rgb)
    c.setLineWidth(width)


def _draw_polygon(c, pts: list[tuple[float, float]],
                  fill_rgb, stroke_rgb, stroke_width: float = 0.5) -> None:
    if len(pts) < 3:
        return
    _set_fill(c, fill_rgb)
    _set_stroke(c, stroke_rgb, stroke_width)
    path = c.beginPath()
    path.moveTo(*pts[0])
    for x, y in pts[1:]:
        path.lineTo(x, y)
    path.close()
    c.drawPath(path, fill=1, stroke=1)


def _geom_pts(geom, vt: _VT, resolution: int = 32) -> list[tuple[float, float]]:
    from archit_app.geometry.polygon import Polygon2D
    if isinstance(geom, Polygon2D):
        return [vt.pt(p) for p in geom.exterior]
    return [vt.pt(p) for p in geom.to_polyline(resolution)]


# ---------------------------------------------------------------------------
# Element renderers
# ---------------------------------------------------------------------------

def _render_rooms(c, level: Level, vt: _VT, font_size: float) -> None:
    for room in level.rooms:
        pts = [vt.pt(p) for p in room.boundary.exterior]
        _draw_polygon(c, pts, _PAL["room_fill"], _PAL["room_stroke"], 0.5)
    # Room labels are rendered by _render_room_labels_polished() so they sit
    # on top of walls / furniture.


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255


def _material_fill(element, default: tuple, material_library) -> tuple:
    """Return a material-derived fill color tuple, or *default*."""
    if material_library is None:
        return default
    mat_name = getattr(element, "material", None)
    if not mat_name:
        return default
    mat = material_library.get(mat_name)
    return _hex_to_rgb(mat.color_hex) if mat is not None else default


def _render_walls(c, level: Level, vt: _VT, material_library=None) -> None:
    for wall in level.walls:
        pts = _geom_pts(wall.geometry, vt)
        fill = _material_fill(wall, _PAL["wall_fill"], material_library)
        _draw_polygon(c, pts, fill, _PAL["wall_stroke"], 0.3)
        for opening in wall.openings:
            _render_single_opening(c, opening, vt)


def _render_single_opening(c, opening, vt: _VT) -> None:
    pts = [vt.pt(p) for p in opening.geometry.exterior]
    if opening.kind == OpeningKind.ARCHWAY:
        _draw_polygon(c, pts, _PAL["archway_fill"], _PAL["archway_stroke"], 0.4)
    elif opening.kind in (OpeningKind.WINDOW, OpeningKind.PASS_THROUGH):
        _draw_polygon(c, pts, _PAL["window_fill"], _PAL["window_stroke"], 0.4)
        _render_window_glazing(c, opening, vt)
    else:  # DOOR
        _draw_polygon(c, pts, _PAL["door_fill"], _PAL["door_stroke"], 0.4)
        # Swing arc handled in dedicated pass.


def _render_columns(c, level: Level, vt: _VT, material_library=None) -> None:
    for col in level.columns:
        pts = [vt.pt(p) for p in col.geometry.exterior]
        fill = _material_fill(col, _PAL["column_fill"], material_library)
        _draw_polygon(c, pts, fill, _PAL["column_stroke"], 0.4)


def _render_openings(c, level: Level, vt: _VT) -> None:
    for opening in level.openings:
        _render_single_opening(c, opening, vt)


def _render_furniture(c, level: Level, vt: _VT, font_size: float) -> None:
    for furn in level.furniture:
        pts = [vt.pt(p) for p in furn.footprint.exterior]
        _draw_polygon(c, pts, _PAL["furniture_fill"], _PAL["furniture_stroke"], 0.3)
        label = furn.label or furn.category.value.replace("_", " ").title()
        if label:
            centroid = furn.footprint.centroid
            cx, cy = vt.pt(centroid)
            _set_fill(c, _PAL["furniture_stroke"])
            c.setFont("Helvetica", max(4.0, font_size * 0.7))
            c.drawCentredString(cx, cy - font_size * 0.25, label)


def _render_beams(c, level: Level, vt: _VT) -> None:
    for beam in level.beams:
        pts = [vt.pt(p) for p in beam.geometry.exterior]
        _set_fill(c, (1, 1, 1))
        _set_stroke(c, _PAL["beam_stroke"], 0.8)
        c.setDash(4, 2)
        path = c.beginPath()
        if pts:
            path.moveTo(*pts[0])
            for x, y in pts[1:]:
                path.lineTo(x, y)
            path.close()
        c.drawPath(path, fill=0, stroke=1)
        c.setDash()  # reset dash


def _render_ramps(c, level: Level, vt: _VT) -> None:
    import math as _math
    for ramp in level.ramps:
        pts = [vt.pt(p) for p in ramp.boundary.exterior]
        _set_fill(c, (1, 1, 1))
        _set_stroke(c, _PAL["ramp_stroke"], 0.8)
        path = c.beginPath()
        if pts:
            path.moveTo(*pts[0])
            for x, y in pts[1:]:
                path.lineTo(x, y)
            path.close()
        c.drawPath(path, fill=0, stroke=1)

        # Direction arrow at centroid
        centroid = ramp.boundary.centroid
        cx, cy = vt.pt(centroid)
        arrow_len = vt.s(min(ramp.width, 0.8) * 0.5)
        dx = _math.cos(ramp.direction) * arrow_len
        dy = _math.sin(ramp.direction) * arrow_len  # PDF Y-up — no flip
        _set_stroke(c, _PAL["ramp_arrow"], 1.0)
        c.line(cx - dx * 0.5, cy - dy * 0.5, cx + dx * 0.5, cy + dy * 0.5)


def _render_staircases(c, level: Level, vt: _VT) -> None:
    import math as _math
    for stair in level.staircases:
        pts = [vt.pt(p) for p in stair.boundary.exterior]
        _draw_polygon(c, pts, _PAL["stair_fill"], _PAL["stair_stroke"], 0.75)

        # Draw tread lines perpendicular to travel direction
        bb = stair.boundary.bounding_box()
        sx0, sy0 = vt(bb.min_corner.x, bb.min_corner.y)
        sx1, sy1 = vt(bb.max_corner.x, bb.max_corner.y)
        cos_d = _math.cos(stair.direction + _math.pi / 2)
        sin_d = _math.sin(stair.direction + _math.pi / 2)
        step_size = vt.s(stair.run_depth)
        travel_len = max(abs(sx1 - sx0), abs(sy1 - sy0))
        n_treads = max(1, int(travel_len / max(step_size, 1)))
        cx = (sx0 + sx1) / 2
        cy = (sy0 + sy1) / 2
        half_w = travel_len * 0.4
        _set_stroke(c, _PAL["stair_stroke"], 0.4)
        for i in range(n_treads + 1):
            t = -0.5 + i / max(n_treads, 1)
            dx = _math.cos(stair.direction) * travel_len * t
            dy = _math.sin(stair.direction) * travel_len * t  # PDF Y-up
            lx1 = cx + dx - cos_d * half_w
            ly1 = cy + dy - sin_d * half_w
            lx2 = cx + dx + cos_d * half_w
            ly2 = cy + dy + sin_d * half_w
            c.line(lx1, ly1, lx2, ly2)


def _render_slabs(c, level: Level, vt: _VT) -> None:
    from archit_app.elements.slab import SlabType
    for slab in level.slabs:
        pts = [vt.pt(p) for p in slab.boundary.exterior]
        _set_fill(c, (1, 1, 1))
        _set_stroke(c, _PAL["slab_stroke"], 0.75)
        dash = (4, 3) if slab.slab_type == SlabType.FLOOR else (2, 2)
        c.setDash(*dash)
        path = c.beginPath()
        if pts:
            path.moveTo(*pts[0])
            for x, y in pts[1:]:
                path.lineTo(x, y)
            path.close()
        c.drawPath(path, fill=0, stroke=1)
        c.setDash()


def _render_dimensions(c, level: Level, vt: _VT, font_size: float) -> None:
    for dim in level.dimensions:
        sx_s, sy_s = vt.pt(dim.start)
        sx_e, sy_e = vt.pt(dim.end)
        dl_s = vt.pt(dim.dimension_line_start)
        dl_e = vt.pt(dim.dimension_line_end)
        lp = vt.pt(dim.label_position)

        _set_stroke(c, _PAL["dim_line"], 0.4)
        c.setDash(3, 2)
        c.line(sx_s, sy_s, dl_s[0], dl_s[1])
        c.line(sx_e, sy_e, dl_e[0], dl_e[1])
        c.setDash()
        c.line(dl_s[0], dl_s[1], dl_e[0], dl_e[1])

        _set_fill(c, _PAL["dim_text"])
        c.setFont("Helvetica", max(4.0, font_size * 0.75))
        c.drawCentredString(lp[0], lp[1] + 2, dim.label)


def _render_section_marks(c, level: Level, vt: _VT, font_size: float) -> None:
    import math as _math
    for mark in level.section_marks:
        cl = mark.cut_line
        sx_s, sy_s = vt.pt(cl.start)
        sx_e, sy_e = vt.pt(cl.end)

        _set_stroke(c, _PAL["section_line"], 1.2)
        c.setDash(6, 3)
        c.line(sx_s, sy_s, sx_e, sy_e)
        c.setDash()

        # Tag circle at midpoint
        mp = mark.midpoint
        mx, my = vt.pt(mp)
        r = max(4.0, vt.s(0.1))
        c.setFillColorRGB(1, 1, 1)
        _set_stroke(c, _PAL["section_line"], 1.0)
        c.circle(mx, my, r, fill=1, stroke=1)
        _set_fill(c, _PAL["section_line"])
        c.setFont("Helvetica-Bold", max(4.0, r * 1.0))
        c.drawCentredString(mx, my - r * 0.4, mark.tag)


def _render_text_annotations(c, level: Level, vt: _VT, font_size: float) -> None:
    import math as _math
    for ann in level.text_annotations:
        px, py = vt.pt(ann.position)
        _set_fill(c, _PAL["annotation"])
        c.setFont("Helvetica", max(5.0, font_size * 0.8))
        c.saveState()
        c.translate(px, py)
        c.rotate(_math.degrees(ann.rotation))
        c.drawCentredString(0, 0, ann.text)
        c.restoreState()


def _render_scale_bar(c, vt: _VT, margin: float, page_h: float) -> None:
    """5-metre scale bar in 1 m alternating cells, bottom-left."""
    n = 5
    seg = vt.s(1.0)
    bx = margin
    by = margin * 0.55
    bh = max(3.5, vt.s(0.05))

    # Outline
    _set_fill(c, (1, 1, 1))
    _set_stroke(c, _PAL["brand_void"], 0.4)
    c.rect(bx, by, seg * n, bh, fill=0, stroke=1)
    # Alternating cells
    for i in range(n):
        if i % 2 == 0:
            _set_fill(c, _PAL["brand_void"])
        else:
            _set_fill(c, (1, 1, 1))
        _set_stroke(c, _PAL["brand_void"], 0.3)
        c.rect(bx + i * seg, by, seg, bh, fill=1, stroke=1)
    # Tick labels
    _set_fill(c, _PAL["brand_void"])
    c.setFont("Helvetica", max(5.0, vt.s(0.08)))
    for i in range(n + 1):
        c.drawCentredString(bx + i * seg, by - max(7.0, vt.s(0.1)), f"{i}")
    c.drawString(bx + n * seg + 4, by + bh * 0.2, "m")


def _render_title_block(
    c, vt: _VT, margin: float, page_w: float, page_h: float,
    *, project_name: str, project_number: str, level_label: str,
    scale_label: str, date_label: str,
) -> tuple[float, float, float, float]:
    """Title block in the top-right corner. Returns (x, y, w, h)."""
    block_w = 200.0
    block_h = 90.0
    pad = 8.0
    bx = page_w - margin * 0.5 - block_w
    by = page_h - margin * 0.5 - block_h

    # Outer frame
    _set_fill(c, (1, 1, 1))
    _set_stroke(c, _PAL["brand_void"], 0.8)
    c.rect(bx, by, block_w, block_h, fill=1, stroke=1)

    # ARCHIT wordmark strip (top of block — i.e. higher y in PDF)
    strip_h = 18.0
    _set_fill(c, _PAL["brand_void"])
    c.rect(bx, by + block_h - strip_h, block_w, strip_h, fill=1, stroke=0)
    _set_fill(c, _PAL["brand_vellum"])
    c.setFont("Helvetica-Bold", 11)
    c.drawString(bx + pad, by + block_h - strip_h + 6, "ARCHIT")
    _set_fill(c, _PAL["brand_datum"])
    c.setFont("Helvetica", 8)
    c.drawRightString(bx + block_w - pad, by + block_h - strip_h + 6, scale_label)

    # Body rows (below strip).  PDF Y-up: rows count downward from the strip.
    row_y = by + block_h - strip_h - 12

    def _row(label: str, value: str, y: float, *, value_color=None) -> None:
        _set_fill(c, _PAL["brand_void"])
        c.setFont("Helvetica-Bold", 6.5)
        c.drawString(bx + pad, y, label.upper())
        _set_fill(c, value_color or _PAL["brand_void"])
        c.setFont("Helvetica", 9)
        c.drawString(bx + pad, y - 11, value or "—")

    _row("Project", project_name or "(unnamed)", row_y)
    if project_number:
        _row("No.", project_number, row_y - 22)
        _row("Date / Sheet", f"{date_label}  ·  {level_label}", row_y - 44,
             value_color=_PAL["brand_blueprint"])
    else:
        _row("Date / Sheet", f"{date_label}  ·  {level_label}", row_y - 22,
             value_color=_PAL["brand_blueprint"])

    return bx, by, block_w, block_h


def _render_north_arrow(c, anchor_x: float, anchor_y: float,
                         north_angle_deg: float) -> None:
    """North arrow centered at (anchor_x, anchor_y) in PDF points (Y-up)."""
    import math as _math
    r = 18.0
    # Background circle
    _set_fill(c, (1, 1, 1))
    _set_stroke(c, _PAL["brand_void"], 0.6)
    c.circle(anchor_x, anchor_y, r, fill=1, stroke=1)
    ang = _math.radians(north_angle_deg)
    # PDF is Y-up so north (bearing 0°) = +Y in PDF as well.  Bearing CW means
    # +sin offset on X, +cos offset on Y (no flip).
    tip_x = anchor_x + _math.sin(ang) * (r - 2)
    tip_y = anchor_y + _math.cos(ang) * (r - 2)
    bl_x = anchor_x - _math.sin(ang) * (r - 2) * 0.35 + _math.cos(ang) * 4
    bl_y = anchor_y - _math.cos(ang) * (r - 2) * 0.35 - _math.sin(ang) * 4
    br_x = anchor_x - _math.sin(ang) * (r - 2) * 0.35 - _math.cos(ang) * 4
    br_y = anchor_y - _math.cos(ang) * (r - 2) * 0.35 + _math.sin(ang) * 4

    # Filled half (datum colour)
    _set_fill(c, _PAL["brand_datum"])
    _set_stroke(c, _PAL["brand_void"], 0.4)
    p = c.beginPath()
    p.moveTo(tip_x, tip_y)
    p.lineTo(br_x, br_y)
    p.lineTo(anchor_x, anchor_y)
    p.close()
    c.drawPath(p, fill=1, stroke=1)
    # Hollow half
    _set_fill(c, (1, 1, 1))
    p = c.beginPath()
    p.moveTo(tip_x, tip_y)
    p.lineTo(bl_x, bl_y)
    p.lineTo(anchor_x, anchor_y)
    p.close()
    c.drawPath(p, fill=1, stroke=1)
    # "N" label outside the tip
    label_x = anchor_x + _math.sin(ang) * (r + 6)
    label_y = anchor_y + _math.cos(ang) * (r + 6) - 3
    _set_fill(c, _PAL["brand_void"])
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(label_x, label_y, "N")


def _exterior_walls_pdf(level: Level):
    from archit_app.elements.wall import WallType
    return [w for w in level.walls
            if getattr(w, "wall_type", None) == WallType.EXTERIOR]


def _render_exterior_dimensions(c, level: Level, vt: _VT) -> None:
    """Annotate every exterior wall segment with its length in mm.

    Labels are placed perpendicular to the wall, offset 300 mm to the *outside*.
    """
    import math as _math
    walls = _exterior_walls_pdf(level)
    if not walls:
        return
    offset_world = 0.3
    tick = 4.0
    _set_stroke(c, _PAL["brand_datum"], 0.4)
    _set_fill(c, _PAL["brand_datum"])
    c.setFont("Helvetica", 7)
    for wall in walls:
        sp = wall.start_point
        ep = wall.end_point
        if sp is None or ep is None:
            continue
        ax, ay = sp
        bx, by = ep
        dx = bx - ax
        dy = by - ay
        L = _math.hypot(dx, dy)
        if L < 0.05:
            continue
        nx = -dy / L
        ny = dx / L
        ox1, oy1 = ax + nx * offset_world, ay + ny * offset_world
        ox2, oy2 = bx + nx * offset_world, by + ny * offset_world
        sx1, sy1 = vt(ox1, oy1)
        sx2, sy2 = vt(ox2, oy2)
        wsx1, wsy1 = vt(ax, ay)
        wsx2, wsy2 = vt(bx, by)
        # Extension lines
        c.line(wsx1, wsy1, sx1, sy1)
        c.line(wsx2, wsy2, sx2, sy2)
        # Dimension line
        c.line(sx1, sy1, sx2, sy2)
        # End ticks
        ddx, ddy = sx2 - sx1, sy2 - sy1
        dd_len = _math.hypot(ddx, ddy) or 1.0
        tdx = -ddy / dd_len * (tick / 2)
        tdy = ddx / dd_len * (tick / 2)
        for px, py in ((sx1, sy1), (sx2, sy2)):
            c.line(px - tdx, py - tdy, px + tdx, py + tdy)
        # Label
        mx = (sx1 + sx2) / 2
        my = (sy1 + sy2) / 2
        lx = mx + (-ddy / dd_len) * 7
        ly = my + (ddx / dd_len) * 7
        ang = _math.degrees(_math.atan2(ddy, ddx))
        if ang > 90:
            ang -= 180
        elif ang < -90:
            ang += 180
        c.saveState()
        c.translate(lx, ly)
        c.rotate(ang)
        c.drawCentredString(0, 0, f"{int(round(L * 1000))}")
        c.restoreState()


def _opening_long_axis_pdf(opening) -> tuple | None:
    import math as _math
    pts = list(opening.geometry.exterior)
    if len(pts) < 4:
        return None
    n = len(pts)
    mids = []
    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        mids.append(((a.x + b.x) / 2, (a.y + b.y) / 2))
    pa = (mids[0], mids[2 % n])
    pb = (mids[1 % n], mids[3 % n])
    da = _math.hypot(pa[0][0] - pa[1][0], pa[0][1] - pa[1][1])
    db = _math.hypot(pb[0][0] - pb[1][0], pb[0][1] - pb[1][1])
    return pa if da >= db else pb


def _render_window_glazing(c, opening, vt: _VT) -> None:
    import math as _math
    if opening.kind not in (OpeningKind.WINDOW, OpeningKind.PASS_THROUGH):
        return
    axis = _opening_long_axis_pdf(opening)
    if axis is None:
        return
    (x1, y1), (x2, y2) = axis
    dx, dy = x2 - x1, y2 - y1
    L = _math.hypot(dx, dy)
    if L < 1e-6:
        return
    nx, ny = -dy / L, dx / L
    bb = opening.geometry.bounding_box()
    short = min(bb.width, bb.height)
    off = max(0.02, short * 0.25)
    pairs = [
        ((x1 + nx * off, y1 + ny * off), (x2 + nx * off, y2 + ny * off)),
        ((x1 - nx * off, y1 - ny * off), (x2 - nx * off, y2 - ny * off)),
    ]
    _set_stroke(c, _PAL["brand_blueprint"], 0.4)
    for (ax, ay), (bx_, by_) in pairs:
        sa = vt(ax, ay)
        sb = vt(bx_, by_)
        c.line(sa[0], sa[1], sb[0], sb[1])


def _render_door_swing_pdf(c, opening, level: Level, vt: _VT) -> None:
    import math as _math
    if opening.kind != OpeningKind.DOOR:
        return
    # Use built-in swing geometry if present
    if opening.swing is not None:
        try:
            arc_pts = [vt.pt(p) for p in opening.swing.arc.to_polyline(24)]
        except Exception:
            arc_pts = []
        if len(arc_pts) >= 2:
            _set_stroke(c, _PAL["brand_void"], 0.4)
            c.setDash(2, 2)
            path = c.beginPath()
            path.moveTo(*arc_pts[0])
            for x, y in arc_pts[1:]:
                path.lineTo(x, y)
            c.drawPath(path, fill=0, stroke=1)
            c.setDash()
            return
    axis = _opening_long_axis_pdf(opening)
    if axis is None:
        return
    (x1, y1), (x2, y2) = axis
    rooms = list(level.rooms)
    target = None
    if rooms:
        cx_ = (x1 + x2) / 2
        cy_ = (y1 + y2) / 2
        target = min(rooms, key=lambda r: _math.hypot(
            r.boundary.centroid.x - cx_, r.boundary.centroid.y - cy_))
    if target is None:
        hinge, far = (x1, y1), (x2, y2)
    else:
        d1 = _math.hypot(target.boundary.centroid.x - x1,
                         target.boundary.centroid.y - y1)
        d2 = _math.hypot(target.boundary.centroid.x - x2,
                         target.boundary.centroid.y - y2)
        if d1 <= d2:
            hinge, far = (x1, y1), (x2, y2)
        else:
            hinge, far = (x2, y2), (x1, y1)
    vx, vy = far[0] - hinge[0], far[1] - hinge[1]
    leaf_len = _math.hypot(vx, vy)
    if leaf_len < 1e-6:
        return
    cand_a = (hinge[0] - vy, hinge[1] + vx)
    cand_b = (hinge[0] + vy, hinge[1] - vx)
    if target is not None:
        rcx = target.boundary.centroid.x
        rcy = target.boundary.centroid.y
        if (_math.hypot(cand_a[0] - rcx, cand_a[1] - rcy)
                <= _math.hypot(cand_b[0] - rcx, cand_b[1] - rcy)):
            sweep_end = cand_a
        else:
            sweep_end = cand_b
    else:
        sweep_end = cand_a
    # Approximate the arc with a polyline (24 segments).
    n_seg = 24
    # Determine start/end angles around hinge
    a0 = _math.atan2(far[1] - hinge[1], far[0] - hinge[0])
    a1 = _math.atan2(sweep_end[1] - hinge[1], sweep_end[0] - hinge[0])
    # Choose shortest CCW/CW direction matching the chosen sweep_end
    # Normalize delta to (-pi, pi]
    d_ang = a1 - a0
    while d_ang <= -_math.pi:
        d_ang += 2 * _math.pi
    while d_ang > _math.pi:
        d_ang -= 2 * _math.pi
    pts_world = []
    for i in range(n_seg + 1):
        t = i / n_seg
        ang = a0 + d_ang * t
        pts_world.append((hinge[0] + leaf_len * _math.cos(ang),
                          hinge[1] + leaf_len * _math.sin(ang)))
    _set_stroke(c, _PAL["brand_void"], 0.4)
    c.setDash(2, 2)
    # Closed-leaf segment
    h_pdf = vt(*hinge)
    f_pdf = vt(*far)
    c.line(h_pdf[0], h_pdf[1], f_pdf[0], f_pdf[1])
    # Arc polyline
    path = c.beginPath()
    s0 = vt(*pts_world[0])
    path.moveTo(*s0)
    for wp in pts_world[1:]:
        sp = vt(*wp)
        path.lineTo(*sp)
    c.drawPath(path, fill=0, stroke=1)
    c.setDash()


def _render_door_swings(c, level: Level, vt: _VT) -> None:
    seen: set = set()
    for wall in level.walls:
        for op in wall.openings:
            if op.kind == OpeningKind.DOOR and id(op) not in seen:
                _render_door_swing_pdf(c, op, level, vt)
                seen.add(id(op))
    for op in level.openings:
        if op.kind == OpeningKind.DOOR and id(op) not in seen:
            _render_door_swing_pdf(c, op, level, vt)
            seen.add(id(op))


def _render_room_labels_polished(c, level: Level, vt: _VT) -> None:
    import math as _math
    for room in level.rooms:
        try:
            area = room.area
        except Exception:
            area = 0.0
        if area < 2.0:
            continue
        name = room.name or room.program or ""
        if not name:
            continue
        cx, cy = vt.pt(room.boundary.centroid)
        bb = room.boundary.bounding_box()
        rot_deg = 0.0 if bb.width >= bb.height else 90.0
        c.saveState()
        c.translate(cx, cy)
        if rot_deg:
            c.rotate(rot_deg)
        _set_fill(c, _PAL["brand_blueprint"])
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(0, 4, name)
        _set_fill(c, _PAL["brand_void"])
        c.setFont("Helvetica", 7)
        c.drawCentredString(0, -6, f"{area:.1f} m²")
        c.restoreState()


def _format_scale_label_pdf(vt: _VT) -> str:
    """Convert vt.scale (PDF points per world metre) to a 1:N label."""
    if vt.scale <= 0:
        return "1:?"
    pt_per_mm = 72.0 / 25.4
    mm_per_world_m = vt.scale / pt_per_mm
    if mm_per_world_m <= 0:
        return "1:?"
    denom = 1000.0 / mm_per_world_m
    nice = [10, 20, 25, 50, 100, 200, 500, 1000]
    closest = min(nice, key=lambda v: abs(v - denom))
    return f"1:{closest}"


def _render_title(c, title: str, vt: _VT, margin: float, page_h: float,
                  font_size: float) -> None:
    _set_fill(c, _PAL["annotation"])
    c.setFont("Helvetica-Bold", font_size)
    c.drawString(margin, page_h - margin * 0.7, title)


def _render_background(c, page_w: float, page_h: float) -> None:
    _set_fill(c, _PAL["background"])
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)


# ---------------------------------------------------------------------------
# One level → one PDF page
# ---------------------------------------------------------------------------

def _draw_level_page(
    c,            # reportlab Canvas
    level: Level,
    page_w: float,
    page_h: float,
    margin: float,
    title: str,
    material_library=None,
    building: Building | None = None,
) -> None:
    _render_background(c, page_w, page_h)

    bbox = level.bounding_box
    if bbox is None:
        _set_fill(c, _PAL["annotation"])
        c.setFont("Helvetica", 10)
        c.drawString(margin, page_h / 2, "Empty level")
        return

    vt = _VT(bbox, page_w, page_h, margin)
    font_size = max(5.0, vt.s(0.18))

    _render_rooms(c, level, vt, font_size)
    _render_slabs(c, level, vt)
    _render_ramps(c, level, vt)
    _render_staircases(c, level, vt)
    _render_walls(c, level, vt, material_library=material_library)
    _render_openings(c, level, vt)
    _render_door_swings(c, level, vt)
    _render_beams(c, level, vt)
    _render_columns(c, level, vt, material_library=material_library)
    _render_furniture(c, level, vt, font_size)
    _render_dimensions(c, level, vt, font_size)
    _render_section_marks(c, level, vt, font_size)
    _render_text_annotations(c, level, vt, font_size)
    _render_exterior_dimensions(c, level, vt)
    _render_room_labels_polished(c, level, vt)
    _render_scale_bar(c, vt, margin, page_h)

    # Title block + north arrow
    if building is not None:
        project_name = building.metadata.name or title
        project_number = building.metadata.project_number or ""
        date_label = building.metadata.date or ""
        north_angle_deg = float(getattr(building.land, "north_angle", 0.0) or 0.0) \
            if building.land is not None else 0.0
    else:
        project_name = title
        project_number = ""
        date_label = ""
        north_angle_deg = 0.0
    if not date_label:
        try:
            import datetime as _dt
            date_label = _dt.date.today().isoformat()
        except Exception:
            date_label = ""
    level_label = level.name or f"Level {level.index}"
    scale_label = _format_scale_label_pdf(vt)
    bx, by, bw, bh = _render_title_block(
        c, vt, margin, page_w, page_h,
        project_name=project_name,
        project_number=project_number,
        level_label=level_label,
        scale_label=scale_label,
        date_label=date_label,
    )
    _render_north_arrow(c, bx + bw - 28.0, by - 26.0, north_angle_deg)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def level_to_pdf_bytes(
    level: Level,
    *,
    paper_size: str = "A3",
    margin: float = _MARGIN_PT,
    title: str | None = None,
    landscape: bool | None = None,
    material_library=None,
) -> bytes:
    """
    Render *level* as a single-page PDF and return raw bytes.

    Parameters
    ----------
    level:
        The floor level to render.
    paper_size:
        One of ``"A1"``, ``"A2"``, ``"A3"`` (default), ``"A4"``, ``"letter"``.
    margin:
        Border around the drawing in PDF points (1 pt = 1/72 inch).
        Default is 36 pt (0.5 inch).
    title:
        Title text at the top of the page.  Defaults to the level name.
    landscape:
        Force landscape (``True``) or portrait (``False``).  When ``None``
        (default) the orientation is chosen automatically to best fit the
        drawing's aspect ratio.

    Returns
    -------
    bytes
        Raw PDF bytes.
    """
    rl_canvas, _, sizes = _require_reportlab()

    page_size = sizes.get(paper_size.upper(), sizes["A3"])
    pw, ph = page_size

    # Auto-orient
    if landscape is None:
        bbox = level.bounding_box
        if bbox is not None and bbox.width > bbox.height:
            landscape = True
        else:
            landscape = False
    if landscape:
        pw, ph = max(pw, ph), min(pw, ph)
    else:
        pw, ph = min(pw, ph), max(pw, ph)

    if title is None:
        title = level.name or f"Level {level.index}"

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(pw, ph))
    _draw_level_page(c, level, pw, ph, margin, title,
                     material_library=material_library)
    c.save()
    return buf.getvalue()


def save_level_pdf(
    level: Level,
    path: str,
    *,
    paper_size: str = "A3",
    margin: float = _MARGIN_PT,
    title: str | None = None,
    landscape: bool | None = None,
) -> None:
    """Write a level's floorplan as a single-page PDF."""
    data = level_to_pdf_bytes(
        level,
        paper_size=paper_size,
        margin=margin,
        title=title,
        landscape=landscape,
    )
    with open(path, "wb") as f:
        f.write(data)


def building_to_pdf_bytes(
    building: Building,
    *,
    paper_size: str = "A3",
    margin: float = _MARGIN_PT,
    landscape: bool | None = None,
) -> bytes:
    """
    Render all levels of *building* as a multi-page PDF and return raw bytes.

    Each level occupies one page.  Page orientation is chosen per-level unless
    *landscape* is set explicitly.

    Returns
    -------
    bytes
        Raw PDF bytes.
    """
    rl_canvas, _, sizes = _require_reportlab()

    # We need a single canvas with dynamic page sizes (one per level).
    # reportlab supports this by calling canvas.setPageSize() before showPage().
    sizes_map = sizes

    buf = io.BytesIO()

    # Determine initial page size from the first level (or default)
    def _page_dims(level: Level) -> tuple[float, float]:
        base_w, base_h = sizes_map.get(paper_size.upper(), sizes_map["A3"])
        force = landscape
        if force is None:
            bbox = level.bounding_box
            force = (bbox is not None and bbox.width > bbox.height)
        if force:
            return max(base_w, base_h), min(base_w, base_h)
        return min(base_w, base_h), max(base_w, base_h)

    if not building.levels:
        # Empty building — produce a one-page blank PDF
        base_size = sizes_map.get(paper_size.upper(), sizes_map["A3"])
        c = rl_canvas.Canvas(buf, pagesize=base_size)
        c.save()
        return buf.getvalue()

    first_pw, first_ph = _page_dims(building.levels[0])
    c = rl_canvas.Canvas(buf, pagesize=(first_pw, first_ph))

    for i, level in enumerate(building.levels):
        pw, ph = _page_dims(level)
        if i > 0:
            c.setPageSize((pw, ph))
        title = level.name or f"Level {level.index} — {building.metadata.name}"
        _draw_level_page(c, level, pw, ph, margin, title, building=building)
        c.showPage()

    c.save()
    return buf.getvalue()


def save_building_pdf(
    building: Building,
    path: str,
    *,
    paper_size: str = "A3",
    margin: float = _MARGIN_PT,
    landscape: bool | None = None,
) -> None:
    """
    Write all levels of *building* as a multi-page PDF.

    Each level is one page.  Page orientation is chosen automatically to best
    fit each level's drawing, unless *landscape* is specified.
    """
    data = building_to_pdf_bytes(
        building,
        paper_size=paper_size,
        margin=margin,
        landscape=landscape,
    )
    with open(path, "wb") as f:
        f.write(data)
