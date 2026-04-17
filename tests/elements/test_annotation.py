"""Tests for TextAnnotation, DimensionLine, and SectionMark."""

import math
import pytest

from archit_app import (
    TextAnnotation, DimensionLine, SectionMark,
    Level, Point2D, WORLD,
)
from archit_app.geometry.crs import SCREEN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def p(x, y, crs=WORLD):
    return Point2D(x=x, y=y, crs=crs)


def _level():
    return Level(index=0, elevation=0.0, floor_height=3.0)


# ===========================================================================
# TextAnnotation
# ===========================================================================

class TestTextAnnotation:

    def test_note_factory_basic(self):
        a = TextAnnotation.note(1.0, 2.0, "Hello")
        assert a.text == "Hello"
        assert a.position.x == pytest.approx(1.0)
        assert a.position.y == pytest.approx(2.0)

    def test_note_defaults(self):
        a = TextAnnotation.note(0, 0, "X")
        assert a.rotation == pytest.approx(0.0)
        assert a.size == pytest.approx(0.25)
        assert a.anchor == "center"

    def test_note_rotation(self):
        a = TextAnnotation.note(0, 0, "Rotated", rotation=90.0)
        assert a.rotation == pytest.approx(90.0)

    def test_note_size(self):
        a = TextAnnotation.note(0, 0, "Big", size=0.5)
        assert a.size == pytest.approx(0.5)

    def test_note_anchor(self):
        a = TextAnnotation.note(0, 0, "A", anchor="bottom_left")
        assert a.anchor == "bottom_left"

    def test_room_label_without_area(self):
        a = TextAnnotation.room_label(5.0, 5.0, "Living Room")
        assert a.text == "Living Room"
        assert a.size == pytest.approx(0.3)

    def test_room_label_with_area(self):
        a = TextAnnotation.room_label(5.0, 5.0, "Kitchen", area_m2=12.5)
        assert "Kitchen" in a.text
        assert "12.5" in a.text
        assert "m²" in a.text

    def test_frozen(self):
        a = TextAnnotation.note(0, 0, "x")
        with pytest.raises(Exception):
            a.text = "y"  # type: ignore

    def test_unique_ids(self):
        a1 = TextAnnotation.note(0, 0, "a")
        a2 = TextAnnotation.note(0, 0, "a")
        assert a1.id != a2.id

    def test_repr(self):
        a = TextAnnotation.note(0, 0, "Test note")
        assert "Test note" in repr(a)

    def test_repr_long_text_truncated(self):
        a = TextAnnotation.note(0, 0, "A" * 50)
        r = repr(a)
        assert "…" in r

    def test_crs_default_world(self):
        a = TextAnnotation.note(0, 0, "x")
        assert a.crs == WORLD
        assert a.position.crs == WORLD


# ===========================================================================
# DimensionLine
# ===========================================================================

class TestDimensionLine:

    def test_between_factory(self):
        d = DimensionLine.between(p(0, 0), p(3, 0))
        assert d.measured_distance == pytest.approx(3.0)

    def test_measured_distance_diagonal(self):
        d = DimensionLine.between(p(0, 0), p(3, 4))
        assert d.measured_distance == pytest.approx(5.0)

    def test_auto_label(self):
        d = DimensionLine.between(p(0, 0), p(3, 0))
        assert d.label == "3.00 m"

    def test_auto_label_decimal_places(self):
        d = DimensionLine.between(p(0, 0), p(3, 0), decimal_places=0)
        assert d.label == "3 m"

    def test_auto_label_unit_suffix(self):
        d = DimensionLine.between(p(0, 0), p(3, 0), unit_suffix="mm")
        assert "mm" in d.label

    def test_label_override(self):
        d = DimensionLine.between(p(0, 0), p(3, 0), label_override="custom")
        assert d.label == "custom"

    def test_midpoint(self):
        d = DimensionLine.between(p(0, 0), p(4, 0))
        assert d.midpoint.x == pytest.approx(2.0)
        assert d.midpoint.y == pytest.approx(0.0)

    def test_direction_horizontal(self):
        d = DimensionLine.between(p(0, 0), p(4, 0))
        dr = d.direction
        assert dr.x == pytest.approx(1.0)
        assert dr.y == pytest.approx(0.0)

    def test_normal_horizontal(self):
        # Normal to eastward dimension is northward (+Y) in Y-up
        d = DimensionLine.between(p(0, 0), p(4, 0))
        n = d.normal
        assert n.x == pytest.approx(0.0, abs=1e-9)
        assert n.y == pytest.approx(1.0)

    def test_dimension_line_start_offset(self):
        # Horizontal dim at y=0 with offset 0.5 → dimension line at y=0.5
        d = DimensionLine.between(p(0, 0), p(4, 0), offset=0.5)
        assert d.dimension_line_start.x == pytest.approx(0.0)
        assert d.dimension_line_start.y == pytest.approx(0.5)

    def test_dimension_line_end_offset(self):
        d = DimensionLine.between(p(0, 0), p(4, 0), offset=0.5)
        assert d.dimension_line_end.x == pytest.approx(4.0)
        assert d.dimension_line_end.y == pytest.approx(0.5)

    def test_label_position_mid(self):
        d = DimensionLine.between(p(0, 0), p(4, 0), offset=0.5)
        lp = d.label_position
        assert lp.x == pytest.approx(2.0)
        assert lp.y == pytest.approx(0.5)

    def test_horizontal_factory(self):
        d = DimensionLine.horizontal(0.0, 5.0, y=3.0, offset=0.4)
        assert d.start.x == pytest.approx(0.0)
        assert d.start.y == pytest.approx(3.0)
        assert d.end.x == pytest.approx(5.0)
        assert d.measured_distance == pytest.approx(5.0)

    def test_vertical_factory(self):
        d = DimensionLine.vertical(0.0, 4.0, x=2.0, offset=0.3)
        assert d.start.y == pytest.approx(0.0)
        assert d.end.y == pytest.approx(4.0)
        assert d.measured_distance == pytest.approx(4.0)

    def test_crs_mismatch_raises(self):
        with pytest.raises(Exception):
            DimensionLine.between(p(0, 0, WORLD), p(1, 0, SCREEN))

    def test_default_offset(self):
        d = DimensionLine.between(p(0, 0), p(1, 0))
        assert d.offset == pytest.approx(0.5)

    def test_frozen(self):
        d = DimensionLine.between(p(0, 0), p(1, 0))
        with pytest.raises(Exception):
            d.offset = 1.0  # type: ignore

    def test_repr(self):
        d = DimensionLine.between(p(0, 0), p(3, 0))
        assert "3.00 m" in repr(d)


# ===========================================================================
# SectionMark
# ===========================================================================

class TestSectionMark:

    def test_basic_construction(self):
        s = SectionMark(start=p(0, 5), end=p(10, 5), tag="A")
        assert s.tag == "A"
        assert s.length == pytest.approx(10.0)

    def test_horizontal_factory(self):
        s = SectionMark.horizontal(0, 10, y=5.0, tag="B")
        assert s.start.x == pytest.approx(0.0)
        assert s.start.y == pytest.approx(5.0)
        assert s.end.x == pytest.approx(10.0)
        assert s.tag == "B"

    def test_vertical_factory(self):
        s = SectionMark.vertical(0, 8, x=3.0, tag="C")
        assert s.start.x == pytest.approx(3.0)
        assert s.start.y == pytest.approx(0.0)
        assert s.end.y == pytest.approx(8.0)

    def test_midpoint(self):
        s = SectionMark.horizontal(0, 10, y=5.0)
        assert s.midpoint.x == pytest.approx(5.0)
        assert s.midpoint.y == pytest.approx(5.0)

    def test_cut_line_is_segment(self):
        from archit_app.geometry.primitives import Segment2D
        s = SectionMark.horizontal(0, 4, y=2.0)
        assert isinstance(s.cut_line, Segment2D)
        assert s.cut_line.length == pytest.approx(4.0)

    def test_direction_horizontal(self):
        s = SectionMark.horizontal(0, 5, y=0.0)
        d = s.direction
        assert d.x == pytest.approx(1.0)
        assert d.y == pytest.approx(0.0)

    def test_view_vector_left(self):
        # Eastward cut, view_direction=left → view is northward (+Y)
        s = SectionMark.horizontal(0, 5, y=0.0, view_direction="left")
        v = s.view_vector
        assert v.x == pytest.approx(0.0, abs=1e-9)
        assert v.y == pytest.approx(1.0)

    def test_view_vector_right(self):
        # Eastward cut, view_direction=right → view is southward (-Y)
        s = SectionMark.horizontal(0, 5, y=0.0, view_direction="right")
        v = s.view_vector
        assert v.x == pytest.approx(0.0, abs=1e-9)
        assert v.y == pytest.approx(-1.0)

    def test_view_vector_both_returns_left(self):
        s = SectionMark.horizontal(0, 5, y=0.0, view_direction="both")
        v = s.view_vector
        assert v.y == pytest.approx(1.0)

    def test_reference_field(self):
        s = SectionMark.horizontal(0, 5, y=0.0, tag="A", reference="A-201")
        assert s.reference == "A-201"

    def test_crs_mismatch_raises(self):
        with pytest.raises(Exception):
            SectionMark(start=p(0, 0, WORLD), end=p(5, 0, SCREEN), tag="A")

    def test_default_view_direction(self):
        s = SectionMark.horizontal(0, 5, y=0.0)
        assert s.view_direction == "left"

    def test_frozen(self):
        s = SectionMark.horizontal(0, 5, y=0.0)
        with pytest.raises(Exception):
            s.tag = "Z"  # type: ignore

    def test_repr(self):
        s = SectionMark.horizontal(0, 5, y=0.0, tag="A")
        assert "A" in repr(s)
        assert "SectionMark" in repr(s)


# ===========================================================================
# Level integration
# ===========================================================================

class TestLevelIntegration:

    def test_add_text_annotation(self):
        lvl = _level()
        a = TextAnnotation.note(1, 1, "Note")
        lvl2 = lvl.add_text_annotation(a)
        assert len(lvl2.text_annotations) == 1
        assert lvl2.text_annotations[0].id == a.id

    def test_add_dimension(self):
        lvl = _level()
        d = DimensionLine.horizontal(0, 5, y=0.0)
        lvl2 = lvl.add_dimension(d)
        assert len(lvl2.dimensions) == 1

    def test_add_section_mark(self):
        lvl = _level()
        s = SectionMark.horizontal(0, 10, y=5.0, tag="A")
        lvl2 = lvl.add_section_mark(s)
        assert len(lvl2.section_marks) == 1

    def test_original_level_unchanged(self):
        lvl = _level()
        lvl.add_text_annotation(TextAnnotation.note(0, 0, "x"))
        assert len(lvl.text_annotations) == 0

    def test_get_text_annotation_by_id(self):
        lvl = _level()
        a = TextAnnotation.note(2, 3, "Find me")
        lvl = lvl.add_text_annotation(a)
        found = lvl.get_element_by_id(a.id)
        assert found is not None
        assert found.id == a.id

    def test_get_dimension_by_id(self):
        lvl = _level()
        d = DimensionLine.between(p(0, 0), p(5, 0))
        lvl = lvl.add_dimension(d)
        assert lvl.get_element_by_id(d.id) is not None

    def test_get_section_mark_by_id(self):
        lvl = _level()
        s = SectionMark.vertical(0, 8, x=3.0)
        lvl = lvl.add_section_mark(s)
        assert lvl.get_element_by_id(s.id) is not None

    def test_remove_text_annotation(self):
        lvl = _level()
        a1 = TextAnnotation.note(0, 0, "a")
        a2 = TextAnnotation.note(1, 0, "b")
        lvl = lvl.add_text_annotation(a1).add_text_annotation(a2)
        lvl = lvl.remove_element(a1.id)
        assert len(lvl.text_annotations) == 1
        assert lvl.text_annotations[0].id == a2.id

    def test_remove_dimension(self):
        lvl = _level()
        d = DimensionLine.between(p(0, 0), p(4, 0))
        lvl = lvl.add_dimension(d)
        lvl = lvl.remove_element(d.id)
        assert len(lvl.dimensions) == 0

    def test_remove_section_mark(self):
        lvl = _level()
        s = SectionMark.horizontal(0, 5, y=0.0)
        lvl = lvl.add_section_mark(s)
        lvl = lvl.remove_element(s.id)
        assert len(lvl.section_marks) == 0

    def test_chained_annotations(self):
        lvl = (
            _level()
            .add_text_annotation(TextAnnotation.note(0, 0, "Note 1"))
            .add_dimension(DimensionLine.horizontal(0, 5, y=0.0))
            .add_section_mark(SectionMark.horizontal(0, 8, y=4.0, tag="A"))
        )
        assert len(lvl.text_annotations) == 1
        assert len(lvl.dimensions) == 1
        assert len(lvl.section_marks) == 1

    def test_default_collections_empty(self):
        lvl = _level()
        assert lvl.text_annotations == ()
        assert lvl.dimensions == ()
        assert lvl.section_marks == ()
