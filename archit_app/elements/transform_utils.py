"""
Element copy/transform utilities.

All functions are **pure** — they return new elements with new UUIDs and leave
the originals unchanged.  Geometry is translated in world-space (meters).

Supported operations
--------------------
* :func:`copy_element`   — translate to a new position
* :func:`mirror_element` — reflect across a vertical or horizontal axis
* :func:`array_element`  — create a linear array of copies

Usage::

    from archit_app.elements.transform_utils import copy_element, mirror_element, array_element

    # Move a wall 2 m along X
    wall2 = copy_element(wall, dx=2.0, dy=0.0)

    # Mirror across x=3.0
    mirrored = mirror_element(wall, axis_x=3.0)

    # 4-element row, 1.2 m apart in X
    row = array_element(sofa, count=4, dx=1.2, dy=0.0)
"""

from __future__ import annotations

from typing import TypeVar
from uuid import uuid4

from archit_app.elements.base import Element
from archit_app.geometry.point import Point2D
from archit_app.geometry.polygon import Polygon2D

E = TypeVar("E", bound=Element)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _translate_point(p: Point2D, dx: float, dy: float) -> Point2D:
    return p.model_copy(update={"x": p.x + dx, "y": p.y + dy})


def _translate_poly(poly: Polygon2D, dx: float, dy: float) -> Polygon2D:
    new_ext = tuple(_translate_point(p, dx, dy) for p in poly.exterior)
    new_holes = tuple(
        tuple(_translate_point(p, dx, dy) for p in hole)
        for hole in poly.holes
    )
    return poly.model_copy(update={"exterior": new_ext, "holes": new_holes})


def _mirror_point_x(p: Point2D, axis_x: float) -> Point2D:
    """Reflect a point across the vertical line x = axis_x."""
    return p.model_copy(update={"x": 2 * axis_x - p.x})


def _mirror_point_y(p: Point2D, axis_y: float) -> Point2D:
    """Reflect a point across the horizontal line y = axis_y."""
    return p.model_copy(update={"y": 2 * axis_y - p.y})


def _mirror_poly_x(poly: Polygon2D, axis_x: float) -> Polygon2D:
    new_ext = tuple(_mirror_point_x(p, axis_x) for p in poly.exterior)
    new_holes = tuple(
        tuple(_mirror_point_x(p, axis_x) for p in hole)
        for hole in poly.holes
    )
    return poly.model_copy(update={"exterior": new_ext, "holes": new_holes})


def _mirror_poly_y(poly: Polygon2D, axis_y: float) -> Polygon2D:
    new_ext = tuple(_mirror_point_y(p, axis_y) for p in poly.exterior)
    new_holes = tuple(
        tuple(_mirror_point_y(p, axis_y) for p in hole)
        for hole in poly.holes
    )
    return poly.model_copy(update={"exterior": new_ext, "holes": new_holes})


def _translate_geometry(geom, dx: float, dy: float):
    """Translate any Polygon2D or Curve-like geometry."""
    if isinstance(geom, Polygon2D):
        return _translate_poly(geom, dx, dy)
    # For curve-based wall geometry that has control points or start/end
    # we do a best-effort translate of known attributes.
    updates = {}
    for attr in ("start", "end", "center"):
        val = getattr(geom, attr, None)
        if isinstance(val, Point2D):
            updates[attr] = _translate_point(val, dx, dy)
    if "control_points" in geom.model_fields:
        cps = getattr(geom, "control_points", None)
        if cps is not None:
            updates["control_points"] = tuple(_translate_point(p, dx, dy) for p in cps)
    return geom.model_copy(update=updates) if updates else geom


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def copy_element(element: E, dx: float, dy: float) -> E:
    """Return a translated copy of *element* with a new UUID.

    Parameters
    ----------
    element:
        Any :class:`~archit_app.elements.base.Element` subclass.
    dx:
        Horizontal displacement in meters (+x direction).
    dy:
        Vertical displacement in meters (+y direction).

    Returns
    -------
    E
        A new element of the same type, displaced by (dx, dy), with a fresh
        UUID.
    """
    updates: dict = {"id": uuid4()}

    # Translate known geometry fields
    for field_name in ("geometry", "boundary", "footprint"):
        geom = getattr(element, field_name, None)
        if geom is not None:
            updates[field_name] = _translate_geometry(geom, dx, dy)

    # Translate scalar position fields (TextAnnotation.position, etc.)
    pos = getattr(element, "position", None)
    if isinstance(pos, Point2D):
        updates["position"] = _translate_point(pos, dx, dy)

    # Wall geometry attribute (Curve or Polygon2D)
    if "geometry" not in updates:
        geom = getattr(element, "geometry", None)
        if geom is not None:
            updates["geometry"] = _translate_geometry(geom, dx, dy)

    return element.model_copy(update=updates)  # type: ignore[return-value]


def mirror_element(
    element: E,
    *,
    axis_x: float | None = None,
    axis_y: float | None = None,
) -> E:
    """Return a mirrored copy of *element* with a new UUID.

    Exactly one of *axis_x* or *axis_y* must be provided.

    Parameters
    ----------
    element:
        The element to mirror.
    axis_x:
        Vertical mirror axis: reflect across the line ``x = axis_x``.
    axis_y:
        Horizontal mirror axis: reflect across the line ``y = axis_y``.

    Returns
    -------
    E
        A new element reflected across the specified axis, with a fresh UUID.
    """
    if (axis_x is None) == (axis_y is None):
        raise ValueError("Exactly one of axis_x or axis_y must be provided.")

    def _mirror_geom(geom):
        if isinstance(geom, Polygon2D):
            if axis_x is not None:
                return _mirror_poly_x(geom, axis_x)
            return _mirror_poly_y(geom, axis_y)  # type: ignore[arg-type]
        # Curve-like geometry
        updates = {}
        for attr in ("start", "end", "center"):
            val = getattr(geom, attr, None)
            if isinstance(val, Point2D):
                if axis_x is not None:
                    updates[attr] = _mirror_point_x(val, axis_x)
                else:
                    updates[attr] = _mirror_point_y(val, axis_y)  # type: ignore[arg-type]
        if "control_points" in getattr(geom, "model_fields", {}):
            cps = getattr(geom, "control_points", None)
            if cps is not None:
                if axis_x is not None:
                    updates["control_points"] = tuple(_mirror_point_x(p, axis_x) for p in cps)
                else:
                    updates["control_points"] = tuple(_mirror_point_y(p, axis_y) for p in cps)  # type: ignore[arg-type]
        return geom.model_copy(update=updates) if updates else geom

    updates: dict = {"id": uuid4()}

    for field_name in ("geometry", "boundary", "footprint"):
        geom = getattr(element, field_name, None)
        if geom is not None:
            updates[field_name] = _mirror_geom(geom)

    pos = getattr(element, "position", None)
    if isinstance(pos, Point2D):
        if axis_x is not None:
            updates["position"] = _mirror_point_x(pos, axis_x)
        else:
            updates["position"] = _mirror_point_y(pos, axis_y)  # type: ignore[arg-type]

    return element.model_copy(update=updates)  # type: ignore[return-value]


def array_element(element: E, count: int, dx: float, dy: float) -> list[E]:
    """Return a linear array of *count* copies of *element*.

    The first copy is the original position (dx * 0, dy * 0) and each
    subsequent copy is offset by (dx, dy) relative to the previous one.

    Parameters
    ----------
    element:
        The element to array.
    count:
        Total number of elements in the result (including the first at offset 0).
    dx:
        Step in the X direction (meters).
    dy:
        Step in the Y direction (meters).

    Returns
    -------
    list[E]
        *count* elements; each with a unique UUID.
    """
    if count < 1:
        raise ValueError(f"count must be >= 1, got {count}.")
    return [copy_element(element, dx * i, dy * i) for i in range(count)]
