"""
PNG / raster export for floorplan levels and buildings.

Requires the optional dependency: pip install archit-app[image]  (Pillow >=10)

Each level is rendered as a raster image using the same visual style as the SVG
exporter — rooms in light blue, walls in dark grey, columns in red.  A 2×
supersample is applied before downscaling so edges look smooth at all scales.

Usage::

    from archit_app.io.image import save_level_png, save_building_pngs

    # Single level at 150 pixels/meter (≈ 1:6 scale)
    save_level_png(level, "ground_floor.png", pixels_per_meter=150)

    # All levels into a directory
    save_building_pngs(building, "output/", pixels_per_meter=100)

    # Get raw bytes (e.g. for serving over HTTP)
    png_bytes = level_to_png_bytes(level, pixels_per_meter=100)
"""

from __future__ import annotations

import io
import math
from typing import TYPE_CHECKING

from archit_app.building.building import Building
from archit_app.building.level import Level
from archit_app.elements.opening import OpeningKind
from archit_app.geometry.bbox import BoundingBox2D
from archit_app.geometry.point import Point2D

if TYPE_CHECKING:  # pragma: no cover
    pass


# ---------------------------------------------------------------------------
# Optional dependency guard
# ---------------------------------------------------------------------------

def _require_pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont
        return Image, ImageDraw, ImageFont
    except ImportError:
        raise ImportError(
            "Pillow is required for PNG export. "
            "Install it with: pip install archit-app[image]"
        )


# ---------------------------------------------------------------------------
# Color palette (hex strings, same visual style as svg.py)
# ---------------------------------------------------------------------------

_PAL = {
    "background":    (250, 250, 250),
    "room_fill":     (214, 232, 245),
    "room_stroke":   ( 91, 141, 184),
    "wall_fill":     ( 74,  74,  74),
    "wall_stroke":   ( 42,  42,  42),
    "column_fill":   (192,  57,  43),
    "column_stroke": (146,  43,  33),
    "door_fill":     (255, 255, 255),
    "door_stroke":   ( 91, 141, 184),
    "window_fill":   (174, 214, 241),
    "window_stroke": ( 41, 128, 185),
    "scale_bar":     ( 51,  51,  51),
    "room_label":    ( 26,  58,  92),
    "annotation":    (102, 102, 102),
    # Extended palette
    "furniture_fill":   (255, 248, 220),
    "furniture_stroke": (160, 132,  92),
    "beam_stroke":      (123,  63,   0),
    "ramp_stroke":      ( 74, 144, 217),
    "ramp_arrow":       ( 44,  95, 138),
    "dim_line":         (136, 136, 136),
    "dim_text":         ( 85,  85,  85),
    "section_line":     (204,  34,   0),
    "stair_fill":       (232, 244, 232),
    "stair_stroke":     ( 46, 125,  50),
    "slab_stroke":      (141, 110,  99),
    "archway_fill":     (215, 204, 200),
    "archway_stroke":   (109,  76,  65),
}

_MARGIN = 40   # pixels (before supersampling)
_SUPERSAMPLE = 2


# ---------------------------------------------------------------------------
# Internal coordinate transform  (world Y-up → pixel Y-down)
# ---------------------------------------------------------------------------

class _VT:
    """World → pixel coordinate mapping with Y-flip."""

    def __init__(self, bbox: BoundingBox2D, ppm: float, margin: float) -> None:
        self.ppm = ppm
        self.margin = margin
        self.min_x = bbox.min_corner.x
        self.max_y = bbox.max_corner.y
        self.width  = int(math.ceil(bbox.width  * ppm + 2 * margin))
        self.height = int(math.ceil(bbox.height * ppm + 2 * margin))

    def __call__(self, x: float, y: float) -> tuple[float, float]:
        px = (x - self.min_x) * self.ppm + self.margin
        py = (self.max_y - y) * self.ppm + self.margin
        return px, py

    def pt(self, p: Point2D) -> tuple[float, float]:
        return self(p.x, p.y)

    def s(self, v: float) -> float:
        """Scale a distance."""
        return v * self.ppm


# ---------------------------------------------------------------------------
# Element renderers
# ---------------------------------------------------------------------------

def _poly_pts(points, vt: _VT) -> list[tuple[float, float]]:
    return [vt.pt(p) for p in points]


def _geom_pts(geom, vt: _VT, resolution: int = 32) -> list[tuple[float, float]]:
    from archit_app.geometry.polygon import Polygon2D
    if isinstance(geom, Polygon2D):
        return _poly_pts(geom.exterior, vt)
    return [vt.pt(p) for p in geom.to_polyline(resolution)]


def _draw_polygon(draw, pts: list[tuple[float, float]],
                  fill, outline, stroke_width: int = 1) -> None:
    if len(pts) < 3:
        return
    draw.polygon(pts, fill=fill, outline=outline)


def _render_rooms(draw, level: Level, vt: _VT, font, font_small) -> None:
    for room in level.rooms:
        pts = _poly_pts(room.boundary.exterior, vt)
        _draw_polygon(draw, pts, fill=_PAL["room_fill"], outline=_PAL["room_stroke"])

        # Room label
        if room.name or room.program:
            c = room.boundary.centroid
            cx, cy = vt.pt(c)
            label = room.name or room.program
            area_text = f"{room.area:.1f} m²"
            lh = vt.s(0.25)   # line height proportional to scale
            draw.text((cx, cy - lh * 0.5), label,    fill=_PAL["room_label"], font=font, anchor="mm")
            draw.text((cx, cy + lh * 0.5), area_text, fill=_PAL["annotation"], font=font_small, anchor="mm")


def _material_fill_png(element, default: str, material_library) -> str:
    """Return a material-derived hex color, or *default*."""
    if material_library is None:
        return default
    mat_name = getattr(element, "material", None)
    if not mat_name:
        return default
    mat = material_library.get(mat_name)
    return mat.color_hex if mat is not None else default


def _render_walls(draw, level: Level, vt: _VT, material_library=None) -> None:
    for wall in level.walls:
        pts = _geom_pts(wall.geometry, vt)
        fill = _material_fill_png(wall, _PAL["wall_fill"], material_library)
        _draw_polygon(draw, pts, fill=fill, outline=_PAL["wall_stroke"])
        for opening in wall.openings:
            _render_single_opening(draw, opening, vt)


def _render_single_opening(draw, opening, vt: _VT) -> None:
    pts = _poly_pts(opening.geometry.exterior, vt)
    if opening.kind == OpeningKind.ARCHWAY:
        fill   = _PAL["archway_fill"]
        stroke = _PAL["archway_stroke"]
    elif opening.kind in (OpeningKind.WINDOW, OpeningKind.PASS_THROUGH):
        fill   = _PAL["window_fill"]
        stroke = _PAL["window_stroke"]
    else:  # DOOR
        fill   = _PAL["door_fill"]
        stroke = _PAL["door_stroke"]
    _draw_polygon(draw, pts, fill=fill, outline=stroke)
    # Door swing arc
    if opening.kind == OpeningKind.DOOR and opening.swing is not None:
        arc_pts = [vt.pt(p) for p in opening.swing.arc.to_polyline(24)]
        if len(arc_pts) >= 2:
            draw.line(arc_pts, fill=_PAL["door_stroke"], width=max(1, int(vt.s(0.02))))


def _render_columns(draw, level: Level, vt: _VT, material_library=None) -> None:
    for col in level.columns:
        pts = _poly_pts(col.geometry.exterior, vt)
        fill = _material_fill_png(col, _PAL["column_fill"], material_library)
        _draw_polygon(draw, pts, fill=fill, outline=_PAL["column_stroke"])


def _render_openings(draw, level: Level, vt: _VT) -> None:
    for opening in level.openings:
        _render_single_opening(draw, opening, vt)


def _render_furniture(draw, level: Level, vt: _VT, font_small) -> None:
    for furn in level.furniture:
        pts = _poly_pts(furn.footprint.exterior, vt)
        _draw_polygon(draw, pts, fill=_PAL["furniture_fill"], outline=_PAL["furniture_stroke"])
        label = furn.label or furn.category.value.replace("_", " ").title()
        if label:
            c = furn.footprint.centroid
            cx, cy = vt.pt(c)
            draw.text((cx, cy), label, fill=_PAL["furniture_stroke"], font=font_small, anchor="mm")


def _render_beams(draw, level: Level, vt: _VT) -> None:
    for beam in level.beams:
        pts = _geom_pts(beam.geometry, vt)
        # Draw outline only (no fill) with dashed line approximated by segments
        if len(pts) >= 2:
            draw.polygon(pts, fill=None, outline=_PAL["beam_stroke"])


def _render_ramps(draw, level: Level, vt: _VT, font_small) -> None:
    import math as _math
    for ramp in level.ramps:
        pts = _geom_pts(ramp.boundary, vt)
        _draw_polygon(draw, pts, fill=(74, 144, 217, 40), outline=_PAL["ramp_stroke"])
        # Direction arrow
        c = ramp.boundary.centroid
        cx, cy = vt.pt(c)
        arrow_len = vt.s(min(ramp.width, 0.8) * 0.5)
        dx = _math.cos(ramp.direction) * arrow_len
        dy = -_math.sin(ramp.direction) * arrow_len  # Y-flip
        x1, y1 = cx - dx * 0.5, cy - dy * 0.5
        x2, y2 = cx + dx * 0.5, cy + dy * 0.5
        draw.line([(x1, y1), (x2, y2)], fill=_PAL["ramp_arrow"], width=max(1, int(vt.s(0.03))))


def _render_staircases(draw, level: Level, vt: _VT) -> None:
    import math as _math
    for stair in level.staircases:
        pts = _poly_pts(stair.boundary.exterior, vt)
        _draw_polygon(draw, pts, fill=_PAL["stair_fill"], outline=_PAL["stair_stroke"])

        # Draw tread lines
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
        for i in range(n_treads + 1):
            t = -0.5 + i / max(n_treads, 1)
            dx = _math.cos(stair.direction) * travel_len * t
            dy = -_math.sin(stair.direction) * travel_len * t   # Y-flip
            lx1 = cx + dx - cos_d * half_w
            ly1 = cy + dy + sin_d * half_w
            lx2 = cx + dx + cos_d * half_w
            ly2 = cy + dy - sin_d * half_w
            draw.line([(lx1, ly1), (lx2, ly2)], fill=_PAL["stair_stroke"], width=1)


def _render_slabs(draw, level: Level, vt: _VT) -> None:
    for slab in level.slabs:
        pts = _poly_pts(slab.boundary.exterior, vt)
        _draw_polygon(draw, pts, fill=(232, 244, 232, 0), outline=_PAL["slab_stroke"])


def _render_dimensions(draw, level: Level, vt: _VT, font_small) -> None:
    for dim in level.dimensions:
        sx_s, sy_s = vt.pt(dim.start)
        sx_e, sy_e = vt.pt(dim.end)
        dl_s = vt.pt(dim.dimension_line_start)
        dl_e = vt.pt(dim.dimension_line_end)
        lp = vt.pt(dim.label_position)

        draw.line([(sx_s, sy_s), dl_s], fill=_PAL["dim_line"], width=1)
        draw.line([(sx_e, sy_e), dl_e], fill=_PAL["dim_line"], width=1)
        draw.line([dl_s, dl_e], fill=_PAL["dim_line"], width=1)
        draw.text((lp[0], lp[1] - 4), dim.label,
                  fill=_PAL["dim_text"], font=font_small, anchor="mb")


def _render_section_marks(draw, level: Level, vt: _VT, font_small) -> None:
    for mark in level.section_marks:
        cl = mark.cut_line
        sx_s, sy_s = vt.pt(cl.start)
        sx_e, sy_e = vt.pt(cl.end)
        draw.line([(sx_s, sy_s), (sx_e, sy_e)], fill=_PAL["section_line"], width=2)

        mp = mark.midpoint
        mx, my = vt.pt(mp)
        r = max(5, int(vt.s(0.1)))
        draw.ellipse([mx - r, my - r, mx + r, my + r],
                     fill=(255, 255, 255), outline=_PAL["section_line"])
        draw.text((mx, my), mark.tag,
                  fill=_PAL["section_line"], font=font_small, anchor="mm")


def _render_text_annotations(draw, level: Level, vt: _VT, font_small) -> None:
    for ann in level.text_annotations:
        px, py = vt.pt(ann.position)
        draw.text((px, py), ann.text, fill=_PAL["annotation"], font=font_small, anchor="mm")


def _render_scale_bar(draw, vt: _VT, font_small) -> None:
    bar_len = int(vt.ppm)      # 1 meter in pixels
    bx = int(vt.margin)
    by = vt.height - int(vt.margin * 0.5)
    bh = max(3, int(vt.ppm * 0.04))

    draw.rectangle([bx, by - bh, bx + bar_len, by], fill=_PAL["scale_bar"])
    draw.text((bx + bar_len // 2, by + max(4, int(vt.ppm * 0.06))),
              "1 m", fill=_PAL["annotation"], font=font_small, anchor="mt")


def _render_title(draw, title: str, vt: _VT, font) -> None:
    draw.text((vt.margin, int(vt.margin * 0.55)), title,
              fill=(51, 51, 51), font=font, anchor="lm")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def level_to_png_bytes(
    level: Level,
    *,
    pixels_per_meter: float = 100.0,
    margin: int = _MARGIN,
    title: str | None = None,
    dpi: int = 96,
    material_library=None,
) -> bytes:
    """
    Render *level* as a PNG and return the raw bytes.

    Parameters
    ----------
    level:
        The floor level to render.
    pixels_per_meter:
        Drawing scale.  100 px/m at 96 DPI ≈ 1:25 scale.
    margin:
        Border around the drawing in pixels.
    title:
        Optional title text drawn at the top-left.  Defaults to the level name.
    dpi:
        DPI metadata written into the PNG header (does not change pixel size).

    Returns
    -------
    bytes
        Raw PNG bytes.
    """
    Image, ImageDraw, ImageFont = _require_pillow()

    bbox = level.bounding_box
    if bbox is None:
        img = Image.new("RGB", (400, 200), color=_PAL["background"])
        buf = io.BytesIO()
        img.save(buf, format="PNG", dpi=(dpi, dpi))
        return buf.getvalue()

    # Supersample for anti-aliasing
    s = _SUPERSAMPLE
    vt = _VT(bbox, pixels_per_meter * s, margin * s)

    img = Image.new("RGB", (vt.width, vt.height), color=_PAL["background"])
    draw = ImageDraw.Draw(img)

    # Try to load a reasonably sized font; fall back gracefully
    try:
        from PIL import ImageFont as _IF
        font_size = max(8, int(pixels_per_meter * s * 0.18))
        font_small_size = max(6, int(pixels_per_meter * s * 0.13))
        try:
            font       = _IF.truetype("DejaVuSans.ttf", font_size)
            font_small = _IF.truetype("DejaVuSans.ttf", font_small_size)
        except OSError:
            font       = _IF.load_default(size=font_size)
            font_small = _IF.load_default(size=font_small_size)
    except Exception:
        font = font_small = None

    _render_rooms(draw, level, vt, font, font_small)
    _render_slabs(draw, level, vt)
    _render_ramps(draw, level, vt, font_small)
    _render_staircases(draw, level, vt)
    _render_walls(draw, level, vt, material_library=material_library)
    _render_openings(draw, level, vt)
    _render_beams(draw, level, vt)
    _render_columns(draw, level, vt, material_library=material_library)
    _render_furniture(draw, level, vt, font_small)
    _render_dimensions(draw, level, vt, font_small)
    _render_section_marks(draw, level, vt, font_small)
    _render_text_annotations(draw, level, vt, font_small)
    _render_scale_bar(draw, vt, font_small)

    if title is None:
        title = level.name or f"Level {level.index}"
    _render_title(draw, title, vt, font)

    # Downscale to target resolution
    target = (vt.width // s, vt.height // s)
    img = img.resize(target, Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(dpi, dpi))
    return buf.getvalue()


def save_level_png(
    level: Level,
    path: str,
    *,
    pixels_per_meter: float = 100.0,
    margin: int = _MARGIN,
    title: str | None = None,
    dpi: int = 96,
) -> None:
    """Write a level's floorplan as a PNG file."""
    data = level_to_png_bytes(
        level,
        pixels_per_meter=pixels_per_meter,
        margin=margin,
        title=title,
        dpi=dpi,
    )
    with open(path, "wb") as f:
        f.write(data)


def save_building_pngs(
    building: Building,
    directory: str,
    *,
    pixels_per_meter: float = 100.0,
    margin: int = _MARGIN,
    dpi: int = 96,
) -> list[str]:
    """
    Write one PNG per level to *directory*.

    Returns
    -------
    list[str]
        File paths written (one per level).
    """
    import os
    os.makedirs(directory, exist_ok=True)
    paths = []
    for level in building.levels:
        title = level.name or f"Level {level.index} — {building.metadata.name}"
        fname = os.path.join(directory, f"level_{level.index:02d}.png")
        save_level_png(
            level, fname,
            pixels_per_meter=pixels_per_meter,
            margin=margin,
            title=title,
            dpi=dpi,
        )
        paths.append(fname)
    return paths
