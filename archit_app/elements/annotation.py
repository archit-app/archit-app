"""
Annotation elements for construction documents.

Three concrete types cover the main annotation needs:

TextAnnotation
    A text label or note anchored to a point.  Used for room names,
    general notes, elevation markers, and any free-form text.

DimensionLine
    A linear dimension between two measured points with perpendicular
    extension lines and an auto-computed or overridden value label.
    The ``offset`` controls how far the dimension line sits from the
    measured line (positive = left of the start→end direction).

SectionMark
    A section-cut indicator — a line across the plan with a tag and
    a view-direction arrow at each end.

All three extend ``Element`` (immutable Pydantic model, UUID, tags, layer).

Level integration::

    level = (
        level
        .add_text_annotation(TextAnnotation.note(x=5, y=5, text="Load-bearing wall"))
        .add_dimension(DimensionLine.between(p1, p2, offset=0.5))
        .add_section_mark(SectionMark(start=p_a, end=p_b, tag="A"))
    )
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import model_validator

from archit_app.elements.base import Element
from archit_app.geometry.crs import CoordinateSystem, WORLD, require_same_crs
from archit_app.geometry.point import Point2D
from archit_app.geometry.primitives import Segment2D
from archit_app.geometry.vector import Vector2D


# ---------------------------------------------------------------------------
# TextAnnotation
# ---------------------------------------------------------------------------

class TextAnnotation(Element):
    """
    A text note or label anchored to a plan-space point.

    Attributes:
        position:  Anchor point in WORLD coordinates.
        text:      The displayed string.
        rotation:  Rotation angle in degrees, counter-clockwise from +X axis.
        size:      Approximate text height in meters (used for rendering hints).
        anchor:    Which part of the text bounding box sits at *position*.
                   One of ``"center"``, ``"left"``, ``"right"``,
                   ``"top"``, ``"bottom"``, ``"top_left"``, ``"top_right"``,
                   ``"bottom_left"``, ``"bottom_right"``.
    """

    position: Point2D
    text: str
    rotation: float = 0.0           # degrees CCW from +X
    size: float = 0.25              # meters — approximate text height
    anchor: Literal[
        "center", "left", "right",
        "top", "bottom",
        "top_left", "top_right",
        "bottom_left", "bottom_right",
    ] = "center"

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def note(
        cls,
        x: float,
        y: float,
        text: str,
        *,
        rotation: float = 0.0,
        size: float = 0.25,
        anchor: str = "center",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "TextAnnotation":
        """
        Create a free-form note at world coordinates (x, y).

        Parameters
        ----------
        x, y:      World-space position in meters.
        text:      The annotation text.
        rotation:  Degrees CCW from +X (default 0 = horizontal).
        size:      Approximate text height in meters.
        anchor:    Text-box alignment on the anchor point.
        """
        return cls(
            position=Point2D(x=x, y=y, crs=crs),
            text=text,
            rotation=rotation,
            size=size,
            anchor=anchor,  # type: ignore[arg-type]
            crs=crs,
            **kwargs,
        )

    @classmethod
    def room_label(
        cls,
        x: float,
        y: float,
        room_name: str,
        area_m2: float | None = None,
        *,
        size: float = 0.3,
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "TextAnnotation":
        """
        Convenience factory for a room name label, optionally including area.

        The text is formatted as ``"Room Name\\n00.0 m²"`` when area is given.
        """
        text = room_name
        if area_m2 is not None:
            text = f"{room_name}\n{area_m2:.1f} m²"
        return cls.note(x, y, text, size=size, crs=crs, **kwargs)

    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        short = self.text[:20] + "…" if len(self.text) > 20 else self.text
        return f"TextAnnotation(text={short!r}, pos=({self.position.x:.2f}, {self.position.y:.2f}))"


# ---------------------------------------------------------------------------
# DimensionLine
# ---------------------------------------------------------------------------

class DimensionLine(Element):
    """
    A linear dimension annotation between two measured points.

    The dimension line runs parallel to the *start* → *end* vector, offset
    perpendicularly by ``offset`` meters (positive = left-hand side of the
    travel direction, i.e. CCW in Y-up space).  Extension lines connect the
    measured points to the dimension line endpoints.

    Attributes:
        start:           First measurement point.
        end:             Second measurement point.
        offset:          Perpendicular offset of the dimension line in meters.
        label_override:  If non-empty, shown instead of the computed distance.
        decimal_places:  Decimal places in the auto-computed label (default 2).
        unit_suffix:     Unit string appended to the label (default ``"m"``).
    """

    start: Point2D
    end: Point2D
    offset: float = 0.5
    label_override: str = ""
    decimal_places: int = 2
    unit_suffix: str = "m"

    @model_validator(mode="after")
    def _crs_match(self) -> "DimensionLine":
        require_same_crs(self.start.crs, self.end.crs, "DimensionLine endpoints")
        return self

    # ------------------------------------------------------------------
    # Computed geometry
    # ------------------------------------------------------------------

    @property
    def measured_distance(self) -> float:
        """Straight-line distance between *start* and *end* in meters."""
        return self.start.distance_to(self.end)

    @property
    def label(self) -> str:
        """
        The text shown on the dimension line.

        Returns ``label_override`` if set, otherwise formats the measured
        distance with ``decimal_places`` digits and appends ``unit_suffix``.
        """
        if self.label_override:
            return self.label_override
        d = self.measured_distance
        return f"{d:.{self.decimal_places}f} {self.unit_suffix}".strip()

    @property
    def midpoint(self) -> Point2D:
        """Midpoint of the *measured* line (where the label is placed)."""
        return self.start.midpoint(self.end)

    @property
    def direction(self) -> Vector2D:
        """
        Unit vector from *start* to *end*.
        Raises ``ValueError`` if the two points coincide.
        """
        seg = Segment2D(start=self.start, end=self.end)
        return seg.direction

    @property
    def normal(self) -> Vector2D:
        """
        Unit normal to the dimension direction (90° CCW = left-hand side in Y-up).
        This is the direction the offset is applied in.
        """
        return self.direction.perpendicular().normalized()

    @property
    def dimension_line_start(self) -> Point2D:
        """Start of the drawn dimension line (offset from the measured start)."""
        n = self.normal
        return Point2D(
            x=self.start.x + self.offset * n.x,
            y=self.start.y + self.offset * n.y,
            crs=self.start.crs,
        )

    @property
    def dimension_line_end(self) -> Point2D:
        """End of the drawn dimension line (offset from the measured end)."""
        n = self.normal
        return Point2D(
            x=self.end.x + self.offset * n.x,
            y=self.end.y + self.offset * n.y,
            crs=self.end.crs,
        )

    @property
    def label_position(self) -> Point2D:
        """Mid-point of the drawn dimension line (where the label is centred)."""
        return self.dimension_line_start.midpoint(self.dimension_line_end)

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def between(
        cls,
        start: Point2D,
        end: Point2D,
        *,
        offset: float = 0.5,
        label_override: str = "",
        decimal_places: int = 2,
        unit_suffix: str = "m",
        **kwargs,
    ) -> "DimensionLine":
        """
        Create a dimension line between two ``Point2D`` objects.

        Parameters
        ----------
        start, end:      The two points being dimensioned.
        offset:          Perpendicular offset distance in meters.
        label_override:  Custom label text (empty → auto from distance).
        decimal_places:  Auto-label decimal precision.
        unit_suffix:     Unit string for the auto-label.
        """
        return cls(
            start=start,
            end=end,
            offset=offset,
            label_override=label_override,
            decimal_places=decimal_places,
            unit_suffix=unit_suffix,
            crs=start.crs,
            **kwargs,
        )

    @classmethod
    def horizontal(
        cls,
        x1: float,
        x2: float,
        y: float,
        *,
        offset: float = 0.5,
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "DimensionLine":
        """
        Create a horizontal dimension between x-coordinates at height y.

        The dimension line is offset ``offset`` meters above the measured line
        (positive offset → upward for a horizontal dimension).

        Parameters
        ----------
        x1, x2:  X-coordinates of the two measured points.
        y:        Y-coordinate of the measured line.
        offset:   Perpendicular offset above the line.
        """
        return cls.between(
            Point2D(x=x1, y=y, crs=crs),
            Point2D(x=x2, y=y, crs=crs),
            offset=offset,
            **kwargs,
        )

    @classmethod
    def vertical(
        cls,
        y1: float,
        y2: float,
        x: float,
        *,
        offset: float = 0.5,
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "DimensionLine":
        """
        Create a vertical dimension between y-coordinates at position x.

        The dimension line is offset ``offset`` meters to the left of the
        measured line (positive offset → leftward for a bottom-to-top dim).

        Parameters
        ----------
        y1, y2:  Y-coordinates of the two measured points.
        x:       X-coordinate of the measured line.
        offset:  Perpendicular offset to the left of the line.
        """
        return cls.between(
            Point2D(x=x, y=y1, crs=crs),
            Point2D(x=x, y=y2, crs=crs),
            offset=offset,
            **kwargs,
        )

    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"DimensionLine(label={self.label!r}, "
            f"dist={self.measured_distance:.3f}m, offset={self.offset}m)"
        )


# ---------------------------------------------------------------------------
# SectionMark
# ---------------------------------------------------------------------------

class SectionMark(Element):
    """
    A section-cut indicator across a plan.

    Represents the standard architectural section mark: a line across the
    drawing indicating where a vertical section cut is taken, with a tag
    (e.g. ``"A"``, ``"B"``, ``"01"``) and a view-direction arrow at each end.

    The convention used here:
    - ``"left"``  → the section is viewed looking to the left of the
                    *start* → *end* travel direction (i.e. toward the normal).
    - ``"right"`` → viewed looking to the right (away from the normal).
    - ``"both"``  → section is drawn looking in both directions.

    Attributes:
        start:          Start point of the cut line.
        end:            End point of the cut line.
        tag:            Identifier label (e.g. ``"A"``, ``"01"``).
        view_direction: Which side of the cut line the viewer looks toward.
        reference:      Optional sheet/detail reference (e.g. ``"A-201"``).
    """

    start: Point2D
    end: Point2D
    tag: str = "A"
    view_direction: Literal["left", "right", "both"] = "left"
    reference: str = ""

    @model_validator(mode="after")
    def _crs_match(self) -> "SectionMark":
        require_same_crs(self.start.crs, self.end.crs, "SectionMark endpoints")
        return self

    # ------------------------------------------------------------------
    # Computed geometry
    # ------------------------------------------------------------------

    @property
    def length(self) -> float:
        """Length of the section cut line in meters."""
        return self.start.distance_to(self.end)

    @property
    def midpoint(self) -> Point2D:
        """Mid-point of the cut line."""
        return self.start.midpoint(self.end)

    @property
    def cut_line(self) -> Segment2D:
        """The section cut as a ``Segment2D``."""
        return Segment2D(start=self.start, end=self.end)

    @property
    def direction(self) -> Vector2D:
        """
        Unit vector along the cut line (start → end).
        Raises ``ValueError`` if start and end coincide.
        """
        return self.cut_line.direction

    @property
    def view_vector(self) -> Vector2D:
        """
        Unit vector pointing in the view direction (perpendicular to the cut).

        For ``view_direction="left"`` this is the CCW normal (left-hand side
        of the travel direction).  For ``"right"`` it is the CW normal.
        When ``"both"``, the left-hand normal is returned.
        """
        n = self.direction.perpendicular().normalized()
        if self.view_direction == "right":
            return Vector2D(x=-n.x, y=-n.y, crs=n.crs)
        return n

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def horizontal(
        cls,
        x1: float,
        x2: float,
        y: float,
        tag: str = "A",
        *,
        view_direction: Literal["left", "right", "both"] = "left",
        reference: str = "",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "SectionMark":
        """
        Create a horizontal section cut at height *y* from x1 to x2.

        ``view_direction="left"`` means the viewer looks upward (+Y) through
        the plan.
        """
        return cls(
            start=Point2D(x=x1, y=y, crs=crs),
            end=Point2D(x=x2, y=y, crs=crs),
            tag=tag,
            view_direction=view_direction,
            reference=reference,
            crs=crs,
            **kwargs,
        )

    @classmethod
    def vertical(
        cls,
        y1: float,
        y2: float,
        x: float,
        tag: str = "A",
        *,
        view_direction: Literal["left", "right", "both"] = "left",
        reference: str = "",
        crs: CoordinateSystem = WORLD,
        **kwargs,
    ) -> "SectionMark":
        """
        Create a vertical section cut at position *x* from y1 to y2.

        ``view_direction="left"`` means the viewer looks to the left (−X
        direction) in the standard Y-up convention.
        """
        return cls(
            start=Point2D(x=x, y=y1, crs=crs),
            end=Point2D(x=x, y=y2, crs=crs),
            tag=tag,
            view_direction=view_direction,
            reference=reference,
            crs=crs,
            **kwargs,
        )

    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"SectionMark(tag={self.tag!r}, "
            f"len={self.length:.2f}m, "
            f"view={self.view_direction!r})"
        )
