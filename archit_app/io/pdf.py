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


_PAL = {
    "background":    _c(250, 250, 250),
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
    "scale_bar":     _c( 51,  51,  51),
    "room_label":    _c( 26,  58,  92),
    "annotation":    _c(102, 102, 102),
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

        if room.name or room.program:
            centroid = room.boundary.centroid
            cx, cy = vt.pt(centroid)
            label = room.name or room.program
            area_text = f"{room.area:.1f} m²"
            lh = font_size * 1.3
            _set_fill(c, _PAL["room_label"])
            c.setFont("Helvetica-Bold", font_size)
            c.drawCentredString(cx, cy + lh * 0.3, label)
            _set_fill(c, _PAL["annotation"])
            c.setFont("Helvetica", font_size * 0.8)
            c.drawCentredString(cx, cy - lh * 0.3, area_text)


def _render_walls(c, level: Level, vt: _VT) -> None:
    for wall in level.walls:
        pts = _geom_pts(wall.geometry, vt)
        _draw_polygon(c, pts, _PAL["wall_fill"], _PAL["wall_stroke"], 0.3)
        for opening in wall.openings:
            _render_single_opening(c, opening, vt)


def _render_single_opening(c, opening, vt: _VT) -> None:
    pts = [vt.pt(p) for p in opening.geometry.exterior]
    if opening.kind == OpeningKind.WINDOW:
        _draw_polygon(c, pts, _PAL["window_fill"], _PAL["window_stroke"], 0.4)
    else:
        _draw_polygon(c, pts, _PAL["door_fill"], _PAL["door_stroke"], 0.4)


def _render_columns(c, level: Level, vt: _VT) -> None:
    for col in level.columns:
        pts = [vt.pt(p) for p in col.geometry.exterior]
        _draw_polygon(c, pts, _PAL["column_fill"], _PAL["column_stroke"], 0.4)


def _render_openings(c, level: Level, vt: _VT) -> None:
    for opening in level.openings:
        _render_single_opening(c, opening, vt)


def _render_scale_bar(c, vt: _VT, margin: float, page_h: float) -> None:
    bar_len = vt.s(1.0)   # 1 meter in PDF points
    bx = margin
    by = margin * 0.45
    bh = max(2.0, vt.s(0.03))

    _set_fill(c, _PAL["scale_bar"])
    _set_stroke(c, _PAL["scale_bar"])
    c.rect(bx, by, bar_len, bh, fill=1, stroke=0)

    _set_fill(c, _PAL["annotation"])
    c.setFont("Helvetica", max(5.0, vt.s(0.08)))
    c.drawCentredString(bx + bar_len / 2, by - max(7.0, vt.s(0.1)), "1 m")


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
    _render_walls(c, level, vt)
    _render_openings(c, level, vt)
    _render_columns(c, level, vt)
    _render_scale_bar(c, vt, margin, page_h)
    _render_title(c, title, vt, margin, page_h, font_size)


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
    _draw_level_page(c, level, pw, ph, margin, title)
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
        _draw_level_page(c, level, pw, ph, margin, title)
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
