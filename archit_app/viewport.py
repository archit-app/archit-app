"""
Viewport — immutable view-state model for rendering and UI.

A Viewport describes the relationship between world space and the canvas:
which level is active, where the camera is (pan), and how far it is zoomed in.

It provides helpers to convert between world and screen coordinates without
requiring a full CoordinateConverter graph, and can produce one on demand.

Usage::

    vp = Viewport(canvas_width_px=1200, canvas_height_px=800, pixels_per_meter=50)

    # Fit a bounding box into the canvas
    vp = vp.fit(level.bounding_box)

    # Convert a mouse click to world space
    world_pt = vp.screen_to_world(mouse_x, mouse_y)

    # Zoom in 20 % centred on the mouse position
    vp = vp.zoom(1.2, around_sx=mouse_x, around_sy=mouse_y)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, model_validator

from archit_app.geometry.bbox import BoundingBox2D
from archit_app.geometry.converter import CoordinateConverter, build_default_converter
from archit_app.geometry.crs import SCREEN, WORLD
from archit_app.geometry.point import Point2D

if TYPE_CHECKING:
    pass


class Viewport(BaseModel):
    """
    Immutable view-state: canvas dimensions, scale, pan, and active level.

    pan_x / pan_y are the **world-space coordinates of the canvas centre**.
    This is more intuitive than storing the canvas-origin offset and keeps
    the "centre of the view" obvious regardless of canvas size.
    """

    model_config = ConfigDict(frozen=True)

    canvas_width_px: float
    canvas_height_px: float
    pixels_per_meter: float = 50.0
    pan_x: float = 0.0   # world X under canvas centre
    pan_y: float = 0.0   # world Y under canvas centre
    active_level_index: int = 0

    @model_validator(mode="after")
    def _validate(self) -> "Viewport":
        if self.canvas_width_px <= 0 or self.canvas_height_px <= 0:
            raise ValueError("Canvas dimensions must be positive.")
        if self.pixels_per_meter <= 0:
            raise ValueError("pixels_per_meter must be positive.")
        return self

    # ------------------------------------------------------------------
    # Coordinate conversion
    # ------------------------------------------------------------------

    def world_to_screen(self, point: Point2D) -> tuple[float, float]:
        """Convert a world-space Point2D to (sx, sy) canvas pixel coordinates.

        Y is flipped: world Y-up → screen Y-down.
        """
        cx = self.canvas_width_px / 2.0
        cy = self.canvas_height_px / 2.0
        sx = cx + (point.x - self.pan_x) * self.pixels_per_meter
        sy = cy - (point.y - self.pan_y) * self.pixels_per_meter  # Y-flip
        return sx, sy

    def screen_to_world(self, sx: float, sy: float) -> Point2D:
        """Convert canvas pixel coordinates to a world-space Point2D."""
        cx = self.canvas_width_px / 2.0
        cy = self.canvas_height_px / 2.0
        wx = self.pan_x + (sx - cx) / self.pixels_per_meter
        wy = self.pan_y - (sy - cy) / self.pixels_per_meter  # Y-flip
        return Point2D(x=wx, y=wy, crs=WORLD)

    # ------------------------------------------------------------------
    # Mutation helpers (return new Viewport)
    # ------------------------------------------------------------------

    def zoom(
        self,
        factor: float,
        around_sx: float | None = None,
        around_sy: float | None = None,
    ) -> "Viewport":
        """
        Scale the view by ``factor`` (> 1 zooms in, < 1 zooms out).

        If ``around_sx`` / ``around_sy`` are given the zoom is centred on
        that screen point (the world point under the cursor stays fixed).
        Otherwise the canvas centre is used.
        """
        if around_sx is None:
            around_sx = self.canvas_width_px / 2.0
        if around_sy is None:
            around_sy = self.canvas_height_px / 2.0

        # World point under the anchor pixel — must remain fixed after zoom
        anchor = self.screen_to_world(around_sx, around_sy)

        new_ppm = self.pixels_per_meter * factor

        # Recompute pan so that anchor world point stays under anchor pixel
        cx = self.canvas_width_px / 2.0
        cy = self.canvas_height_px / 2.0
        new_pan_x = anchor.x - (around_sx - cx) / new_ppm
        new_pan_y = anchor.y + (around_sy - cy) / new_ppm  # Y-flip

        return self.model_copy(update={
            "pixels_per_meter": new_ppm,
            "pan_x": new_pan_x,
            "pan_y": new_pan_y,
        })

    def pan(self, dx_px: float, dy_px: float) -> "Viewport":
        """
        Shift the view by ``(dx_px, dy_px)`` screen pixels.

        Positive dx moves the view right (world moves left);
        positive dy moves the view down (world moves up — Y-flip).
        """
        new_pan_x = self.pan_x - dx_px / self.pixels_per_meter
        new_pan_y = self.pan_y + dy_px / self.pixels_per_meter  # Y-flip
        return self.model_copy(update={"pan_x": new_pan_x, "pan_y": new_pan_y})

    def fit(self, bbox: BoundingBox2D, padding: float = 0.1) -> "Viewport":
        """
        Fit ``bbox`` into the canvas with ``padding`` fraction of extra margin.

        Updates pan and pixels_per_meter so the entire bounding box is visible
        and centred. Returns a new Viewport.
        """
        if bbox is None:
            return self

        w = bbox.width
        h = bbox.height

        if w <= 0 or h <= 0:
            # Degenerate bbox — just centre it
            cx = (bbox.min_corner.x + bbox.max_corner.x) / 2.0
            cy = (bbox.min_corner.y + bbox.max_corner.y) / 2.0
            return self.model_copy(update={"pan_x": cx, "pan_y": cy})

        scale_x = self.canvas_width_px / (w * (1.0 + padding))
        scale_y = self.canvas_height_px / (h * (1.0 + padding))
        new_ppm = min(scale_x, scale_y)

        cx = (bbox.min_corner.x + bbox.max_corner.x) / 2.0
        cy = (bbox.min_corner.y + bbox.max_corner.y) / 2.0

        return self.model_copy(update={
            "pixels_per_meter": new_ppm,
            "pan_x": cx,
            "pan_y": cy,
        })

    def with_active_level(self, index: int) -> "Viewport":
        """Return a copy with a different active level."""
        return self.model_copy(update={"active_level_index": index})

    # ------------------------------------------------------------------
    # CoordinateConverter integration
    # ------------------------------------------------------------------

    def to_converter(self) -> CoordinateConverter:
        """
        Build a CoordinateConverter consistent with this viewport's state.

        The resulting converter registers SCREEN ↔ IMAGE ↔ WORLD using the
        current pan and pixels_per_meter.  The canvas origin (top-left) maps
        to world (pan_x - canvas_w/2/ppm, pan_y + canvas_h/2/ppm).
        """
        origin_world_x = self.pan_x - (self.canvas_width_px / 2.0) / self.pixels_per_meter
        origin_world_y = self.pan_y - (self.canvas_height_px / 2.0) / self.pixels_per_meter
        return build_default_converter(
            viewport_height_px=self.canvas_height_px,
            pixels_per_meter=self.pixels_per_meter,
            canvas_origin_world=(origin_world_x, origin_world_y),
        )

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Viewport({self.canvas_width_px:.0f}×{self.canvas_height_px:.0f}px, "
            f"{self.pixels_per_meter:.1f}px/m, "
            f"pan=({self.pan_x:.2f},{self.pan_y:.2f}), "
            f"level={self.active_level_index})"
        )
