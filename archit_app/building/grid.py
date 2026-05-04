"""
Structural grid.

A StructuralGrid defines named reference axes (like A–H and 1–8 on a typical
structural drawing) that columns, beams, and walls can align to.

Design notes:
- GridAxis is not an Element — it carries no UUID or layer; it is a pure
  geometric reference line associated with the building, not any single level.
- StructuralGrid is a frozen Pydantic model stored on Building.
- Axes are stored as two sequences (x_axes and y_axes) representing the two
  families of grid lines. Conventionally x_axes are numbered (1, 2, 3…) and
  y_axes are lettered (A, B, C…), but this is not enforced.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, model_validator

from archit_app.geometry.crs import WORLD, CoordinateSystem
from archit_app.geometry.point import Point2D
from archit_app.geometry.vector import Vector2D


class GridAxis(BaseModel):
    """
    A single named grid reference line defined by a start and end point.

    name:  axis label, e.g. "A", "1", "Grid-3"
    start: one endpoint of the axis line (world space)
    end:   the other endpoint of the axis line (world space)
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: str
    start: Point2D
    end: Point2D

    @model_validator(mode="after")
    def _validate(self) -> "GridAxis":
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        if math.sqrt(dx * dx + dy * dy) < 1e-10:
            raise ValueError(f"GridAxis '{self.name}': start and end must not be the same point.")
        return self

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def length(self) -> float:
        """Length of the axis in meters."""
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        return math.sqrt(dx * dx + dy * dy)

    @property
    def direction(self) -> Vector2D:
        """Unit vector along the axis (start → end)."""
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        mag = math.sqrt(dx * dx + dy * dy)
        return Vector2D(x=dx / mag, y=dy / mag, crs=self.start.crs)

    @property
    def midpoint(self) -> Point2D:
        """Midpoint of the axis."""
        return Point2D(
            x=(self.start.x + self.end.x) / 2,
            y=(self.start.y + self.end.y) / 2,
            crs=self.start.crs,
        )

    def nearest_point(self, p: Point2D) -> Point2D:
        """
        Return the closest point on this axis to p (clamped to the segment).
        """
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-20:
            return self.start
        t = ((p.x - self.start.x) * dx + (p.y - self.start.y) * dy) / len_sq
        t = max(0.0, min(1.0, t))
        return Point2D(
            x=self.start.x + t * dx,
            y=self.start.y + t * dy,
            crs=self.start.crs,
        )

    def __repr__(self) -> str:
        return f"GridAxis(name={self.name!r}, length={self.length:.2f}m)"


class StructuralGrid(BaseModel):
    """
    A named structural reference grid for a building.

    x_axes: grid lines typically running in the Y direction (columns numbered 1, 2, 3…)
    y_axes: grid lines typically running in the X direction (rows lettered A, B, C…)

    Conventionally, x_axes are spaced along the X direction (they are vertical
    lines), and y_axes are spaced along the Y direction (horizontal lines).
    The naming matches practice on structural drawings, not the axis they run along.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    x_axes: tuple[GridAxis, ...] = ()
    y_axes: tuple[GridAxis, ...] = ()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_x_axis(self, name: str) -> GridAxis | None:
        """Return the x-axis with the given name, or None."""
        return next((a for a in self.x_axes if a.name == name), None)

    def get_y_axis(self, name: str) -> GridAxis | None:
        """Return the y-axis with the given name, or None."""
        return next((a for a in self.y_axes if a.name == name), None)

    def intersection(self, x_name: str, y_name: str) -> Point2D | None:
        """
        Return the intersection point of an x-axis and a y-axis.

        Returns None if either axis is not found or the lines are parallel.
        """
        ax = self.get_x_axis(x_name)
        ay = self.get_y_axis(y_name)
        if ax is None or ay is None:
            return None
        return _line_intersection(ax, ay)

    def nearest_intersection(self, p: Point2D) -> tuple[str, str, Point2D] | None:
        """
        Find the grid intersection closest to point p.

        Returns (x_axis_name, y_axis_name, intersection_point), or None if
        the grid has no axes.
        """
        if not self.x_axes or not self.y_axes:
            return None

        best_dist = float("inf")
        best: tuple[str, str, Point2D] | None = None

        for ax in self.x_axes:
            for ay in self.y_axes:
                pt = _line_intersection(ax, ay)
                if pt is None:
                    continue
                dx = pt.x - p.x
                dy = pt.y - p.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < best_dist:
                    best_dist = dist
                    best = (ax.name, ay.name, pt)

        return best

    def snap_to_grid(self, p: Point2D, tolerance: float = 0.1) -> Point2D:
        """
        Snap p to the nearest grid intersection within tolerance.

        If no intersection is within tolerance, returns p unchanged.
        """
        result = self.nearest_intersection(p)
        if result is None:
            return p
        _, _, pt = result
        dx = pt.x - p.x
        dy = pt.y - p.y
        if math.sqrt(dx * dx + dy * dy) <= tolerance:
            return pt
        return p

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_x_axis(self, axis: GridAxis) -> "StructuralGrid":
        return self.model_copy(update={"x_axes": (*self.x_axes, axis)})

    def add_y_axis(self, axis: GridAxis) -> "StructuralGrid":
        return self.model_copy(update={"y_axes": (*self.y_axes, axis)})

    def remove_x_axis(self, name: str) -> "StructuralGrid":
        return self.model_copy(
            update={"x_axes": tuple(a for a in self.x_axes if a.name != name)}
        )

    def remove_y_axis(self, name: str) -> "StructuralGrid":
        return self.model_copy(
            update={"y_axes": tuple(a for a in self.y_axes if a.name != name)}
        )

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def regular(
        cls,
        x_spacing: float,
        y_spacing: float,
        x_count: int,
        y_count: int,
        x_labels: list[str] | None = None,
        y_labels: list[str] | None = None,
        origin_x: float = 0.0,
        origin_y: float = 0.0,
        grid_length: float = 100.0,
        crs: CoordinateSystem = WORLD,
    ) -> "StructuralGrid":
        """
        Create a regular orthogonal grid.

        x_spacing: spacing between x-axes (vertical lines) in meters
        y_spacing: spacing between y-axes (horizontal lines) in meters
        x_count:   number of x-axes (numbered 1, 2, … by default)
        y_count:   number of y-axes (lettered A, B, … by default)
        grid_length: length of each axis line in meters
        origin_x/y: position of the first grid intersection

        x_labels / y_labels: custom labels; defaults to "1","2",… and "A","B",…
        """
        if x_labels is None:
            x_labels = [str(i + 1) for i in range(x_count)]
        if y_labels is None:
            y_labels = [chr(ord("A") + i) for i in range(y_count)]

        half = grid_length / 2

        x_axes = tuple(
            GridAxis(
                name=x_labels[i],
                start=Point2D(x=origin_x + i * x_spacing, y=origin_y - half, crs=crs),
                end=Point2D(x=origin_x + i * x_spacing, y=origin_y + half, crs=crs),
            )
            for i in range(x_count)
        )

        y_axes = tuple(
            GridAxis(
                name=y_labels[j],
                start=Point2D(x=origin_x - half, y=origin_y + j * y_spacing, crs=crs),
                end=Point2D(x=origin_x + half, y=origin_y + j * y_spacing, crs=crs),
            )
            for j in range(y_count)
        )

        return cls(x_axes=x_axes, y_axes=y_axes)

    def __repr__(self) -> str:
        return f"StructuralGrid(x_axes={len(self.x_axes)}, y_axes={len(self.y_axes)})"


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _line_intersection(a: GridAxis, b: GridAxis) -> Point2D | None:
    """
    Compute the intersection of two infinite lines defined by GridAxis segments.

    Returns None if lines are parallel (or coincident).
    """
    # Parameterise: P = a.start + t * (a.end - a.start)
    #               Q = b.start + s * (b.end - b.start)
    ax, ay = a.start.x, a.start.y
    adx = a.end.x - ax
    ady = a.end.y - ay

    bx, by = b.start.x, b.start.y
    bdx = b.end.x - bx
    bdy = b.end.y - by

    denom = adx * bdy - ady * bdx
    if abs(denom) < 1e-12:
        return None  # parallel

    t = ((bx - ax) * bdy - (by - ay) * bdx) / denom
    return Point2D(x=ax + t * adx, y=ay + t * ady, crs=a.start.crs)
