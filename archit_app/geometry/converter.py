"""
Graph-based coordinate system converter.

Registers directed transforms between named CoordinateSystem objects and finds
conversion paths automatically using BFS — callers never need to manually chain
transforms.

Example::

    from archit_app.geometry.converter import CoordinateConverter, build_default_converter
    from archit_app.geometry.crs import WORLD, SCREEN

    conv = build_default_converter(
        viewport_height_px=600.0,
        pixels_per_meter=50.0,
        canvas_origin_world=(0.0, 0.0),
    )

    screen_pt = Point2D(x=100, y=200, crs=SCREEN)
    world_pt  = screen_pt.to(WORLD, conv)
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

import numpy as np

from archit_app.geometry.crs import (
    CoordinateSystem,
    IMAGE,
    SCREEN,
    WORLD,
)
from archit_app.geometry.transform import Transform2D

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ConversionPathNotFoundError(KeyError):
    """Raised when no registered transform path exists between two CRS."""

    def __init__(self, src: CoordinateSystem, dst: CoordinateSystem) -> None:
        super().__init__(
            f"No conversion path from CRS '{src.name}' to '{dst.name}'. "
            f"Register the relevant transforms with CoordinateConverter.register()."
        )
        self.src = src
        self.dst = dst


# ---------------------------------------------------------------------------
# Core converter
# ---------------------------------------------------------------------------


class CoordinateConverter:
    """
    Registry of 2D affine transforms between named coordinate systems.

    Internally maintains a directed graph where nodes are CRS names and edges
    are Transform2D objects.  When you register a forward transform, the
    inverse is stored automatically.  Conversions that need to hop through an
    intermediate CRS are found via BFS.

    Usage::

        conv = CoordinateConverter()
        conv.register(SCREEN, WORLD, screen_to_world_transform)

        # direct conversion
        world_pts = conv.convert(screen_pts, SCREEN, WORLD)

        # multi-hop: if SCREEN→WORLD and WORLD→WGS84 are registered,
        # SCREEN→WGS84 is resolved automatically
    """

    def __init__(self) -> None:
        # _graph[src_name][dst_name] = Transform2D
        self._graph: dict[str, dict[str, Transform2D]] = {}
        # keep a reference to the full CRS object so we can return typed results
        self._crs_by_name: dict[str, CoordinateSystem] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        src: CoordinateSystem,
        dst: CoordinateSystem,
        transform: Transform2D,
    ) -> None:
        """
        Register the forward transform ``src → dst``.

        The inverse ``dst → src`` is computed and stored automatically.
        Registering the same pair twice silently overwrites the previous
        transform (and its inverse).
        """
        self._ensure_node(src)
        self._ensure_node(dst)
        self._graph[src.name][dst.name] = transform
        self._graph[dst.name][src.name] = transform.inverse()

    def _ensure_node(self, crs: CoordinateSystem) -> None:
        if crs.name not in self._graph:
            self._graph[crs.name] = {}
        # Always update so the latest CRS object wins (e.g. different ppm)
        self._crs_by_name[crs.name] = crs

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def convert(
        self,
        points: np.ndarray,
        src: CoordinateSystem,
        dst: CoordinateSystem,
    ) -> np.ndarray:
        """
        Convert an ``(N, 2)`` array of points from *src* to *dst*.

        If *src* and *dst* are the same CRS the input is returned unchanged.
        If multiple hops are required (e.g. SCREEN → WORLD → WGS84) the
        transforms are chained automatically.

        Args:
            points: ``(N, 2)`` float64 array.  A ``(2,)`` 1-D array is also
                accepted and a ``(2,)`` array is returned.
            src: Source coordinate system.
            dst: Destination coordinate system.

        Returns:
            Converted ``(N, 2)`` (or ``(2,)``) float64 array.

        Raises:
            ConversionPathNotFoundError: If no registered path connects *src*
                to *dst*.
        """
        pts = np.asarray(points, dtype=np.float64)
        if src == dst:
            return pts

        path = self._bfs_path(src.name, dst.name)
        if path is None:
            raise ConversionPathNotFoundError(src, dst)

        for a, b in zip(path, path[1:]):
            pts = self._graph[a][b].apply_to_array(pts)

        return pts

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def registered_crs(self) -> list[CoordinateSystem]:
        """Return all CRS objects that have at least one registered edge."""
        return list(self._crs_by_name.values())

    def can_convert(self, src: CoordinateSystem, dst: CoordinateSystem) -> bool:
        """Return True if a conversion path from *src* to *dst* is available."""
        if src == dst:
            return True
        return self._bfs_path(src.name, dst.name) is not None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _bfs_path(self, src_name: str, dst_name: str) -> list[str] | None:
        """BFS over the CRS graph; returns ordered list of node names or None."""
        if src_name not in self._graph or dst_name not in self._graph:
            return None
        if src_name == dst_name:
            return [src_name]

        visited: set[str] = {src_name}
        queue: deque[list[str]] = deque([[src_name]])

        while queue:
            path = queue.popleft()
            current = path[-1]
            for neighbour in self._graph.get(current, {}):
                if neighbour == dst_name:
                    return path + [neighbour]
                if neighbour not in visited:
                    visited.add(neighbour)
                    queue.append(path + [neighbour])

        return None

    def __repr__(self) -> str:
        edges = sum(len(v) for v in self._graph.values()) // 2
        nodes = list(self._graph.keys())
        return f"CoordinateConverter(crs={nodes}, edges={edges})"


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------


def build_default_converter(
    viewport_height_px: float,
    pixels_per_meter: float,
    canvas_origin_world: tuple[float, float] = (0.0, 0.0),
) -> CoordinateConverter:
    """
    Build a ``CoordinateConverter`` pre-loaded with the standard screen / image
    / world transforms for a 2-D viewport.

    This covers the three most common conversions needed by a rendering layer:

    * ``SCREEN ↔ IMAGE``  — identity (canvas fills the whole image)
    * ``SCREEN ↔ WORLD``  — Y-flip + pixel-to-meter scale + world origin shift
    * ``IMAGE ↔ WORLD``   — derived automatically from the two above via BFS

    Args:
        viewport_height_px: Height of the rendering viewport in pixels.  Needed
            to convert Y-down screen coordinates to Y-up world coordinates.
        pixels_per_meter: How many pixels correspond to one metre.
        canvas_origin_world: World-space ``(x, y)`` coordinate that maps to the
            *bottom-left* corner of the canvas (i.e. screen ``(0, h)``).
            Defaults to ``(0, 0)``.

    Returns:
        A ``CoordinateConverter`` with ``SCREEN``, ``IMAGE``, and ``WORLD``
        edges registered.

    Example::

        conv = build_default_converter(
            viewport_height_px=600,
            pixels_per_meter=50,
            canvas_origin_world=(10.0, 5.0),
        )
        world_pt = conv.convert(np.array([[100.0, 200.0]]), SCREEN, WORLD)
    """
    conv = CoordinateConverter()

    # --- SCREEN ↔ IMAGE --------------------------------------------------
    # Assume the canvas exactly covers the image (no offset).
    conv.register(SCREEN, IMAGE, Transform2D.identity())

    # --- SCREEN ↔ WORLD --------------------------------------------------
    # Derivation for a screen point (px, py):
    #   1. translate(0, -h): (px,  py - h)         shift so bottom-left = origin
    #   2. scale(1/ppm, -1/ppm): (px/ppm,  (h-py)/ppm)   scale + flip Y
    #   3. translate(ox, oy):  add world origin offset
    ox, oy = canvas_origin_world
    ppm = pixels_per_meter
    screen_to_world = (
        Transform2D.translate(ox, oy)
        @ Transform2D.scale(1.0 / ppm, -1.0 / ppm)
        @ Transform2D.translate(0.0, -viewport_height_px)
    )
    conv.register(SCREEN, WORLD, screen_to_world)

    return conv
