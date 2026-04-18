"""
Tests for extended element rendering in SVG, PDF, and PNG outputs.

Covers: Furniture, Beam, Ramp, TextAnnotation, DimensionLine, SectionMark,
        Staircase, Slab.
Each renderer (SVG always available; PDF/PNG guarded by optional deps).
"""

from __future__ import annotations

import math
import sys
from unittest.mock import patch

import pytest

from archit_app import (
    WORLD, Level, Wall, Room, Polygon2D,
    Furniture, Ramp,
)
from archit_app.elements.beam import Beam
from archit_app.elements.annotation import TextAnnotation, DimensionLine, SectionMark
from archit_app.elements.staircase import Staircase
from archit_app.elements.slab import Slab, SlabType
from archit_app.geometry.point import Point2D
from archit_app.io.svg import level_to_svg

try:
    import reportlab as _rl  # noqa: F401
    _RL = True
except ImportError:
    _RL = False

try:
    from PIL import Image  # noqa: F401
    _PIL = True
except ImportError:
    _PIL = False

_skip_pdf = pytest.mark.skipif(not _RL,  reason="reportlab not installed")
_skip_png = pytest.mark.skipif(not _PIL, reason="Pillow not installed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_level() -> Level:
    """A minimal 6×5 m level with a room and a wall."""
    room = Room(
        boundary=Polygon2D.rectangle(0, 0, 6, 5, crs=WORLD),
        name="Hall", program="living",
    )
    wall = Wall.straight(0, 0, 6, 0, thickness=0.2, height=3.0)
    return (
        Level(index=0, elevation=0.0, floor_height=3.0)
        .add_room(room)
        .add_wall(wall)
    )


def _level_with_furniture() -> Level:
    sofa = Furniture.sofa(x=1, y=1)
    desk = Furniture.desk(x=3, y=3)
    return _base_level().add_furniture(sofa).add_furniture(desk)


def _level_with_beam() -> Level:
    beam = Beam.straight(x1=0, y1=2, x2=6, y2=2, width=0.3, depth=0.5, elevation=3.0)
    return _base_level().add_beam(beam)


def _level_with_ramp() -> Level:
    ramp = Ramp.straight(x=1, y=1, width=1.2, length=3.6,
                         slope_angle=math.atan(1 / 12))
    return _base_level().add_ramp(ramp)


def _level_with_text_annotation() -> Level:
    ann = TextAnnotation.note(
        x=2, y=2, text="Important note", crs=WORLD,
    )
    return _base_level().add_text_annotation(ann)


def _level_with_dimension() -> Level:
    dim = DimensionLine.horizontal(0, 6, y=5.5, crs=WORLD)
    return _base_level().add_dimension(dim)


def _level_with_section_mark() -> Level:
    mark = SectionMark.horizontal(0, 6, y=2.5, tag="A", crs=WORLD)
    return _base_level().add_section_mark(mark)


def _level_with_staircase() -> Level:
    stair = Staircase.straight(
        x=0.5, y=0.5, width=1.2, rise_count=12, direction=0.0,
    )
    return _base_level().add_staircase(stair)


def _level_with_slab() -> Level:
    slab = Slab(
        boundary=Polygon2D.rectangle(0, 0, 6, 5, crs=WORLD),
        slab_type=SlabType.FLOOR,
        thickness=0.2,
        elevation=0.0,
    )
    return _base_level().add_slab(slab)


# ---------------------------------------------------------------------------
# SVG tests (always run — no optional dep)
# ---------------------------------------------------------------------------

class TestSVGFurniture:

    def test_furniture_group_present(self):
        svg = level_to_svg(_level_with_furniture())
        assert 'id="furniture"' in svg

    def test_furniture_path_present(self):
        svg = level_to_svg(_level_with_furniture())
        assert 'class="furniture"' in svg

    def test_furniture_label_in_svg(self):
        lv = _base_level().add_furniture(Furniture.sofa(x=1, y=1))
        svg = level_to_svg(lv)
        # label should contain "sofa" or "Sofa" (category fallback)
        assert "ofa" in svg.lower()


class TestSVGBeam:

    def test_beam_group_present(self):
        svg = level_to_svg(_level_with_beam())
        assert 'id="beams"' in svg

    def test_beam_class_in_svg(self):
        svg = level_to_svg(_level_with_beam())
        assert 'class="beam"' in svg


class TestSVGRamp:

    def test_ramp_group_present(self):
        svg = level_to_svg(_level_with_ramp())
        assert 'id="ramps"' in svg

    def test_ramp_class_in_svg(self):
        svg = level_to_svg(_level_with_ramp())
        assert 'class="ramp"' in svg

    def test_ramp_arrow_marker_in_defs(self):
        svg = level_to_svg(_level_with_ramp())
        assert 'id="arrowhead"' in svg


class TestSVGTextAnnotation:

    def test_annotation_group_present(self):
        svg = level_to_svg(_level_with_text_annotation())
        assert 'id="annotations"' in svg

    def test_annotation_text_in_svg(self):
        svg = level_to_svg(_level_with_text_annotation())
        assert "Important note" in svg

    def test_annotation_class_in_svg(self):
        svg = level_to_svg(_level_with_text_annotation())
        assert 'class="annotation"' in svg


class TestSVGDimensionLine:

    def test_dimension_group_present(self):
        svg = level_to_svg(_level_with_dimension())
        assert 'id="dimensions"' in svg

    def test_dimension_label_in_svg(self):
        svg = level_to_svg(_level_with_dimension())
        # dimension label = "6.00 m" or similar
        assert "6.00" in svg or "6.0" in svg

    def test_dimension_lines_rendered(self):
        svg = level_to_svg(_level_with_dimension())
        # extension lines and dim line are <line> elements
        assert "<line" in svg


class TestSVGSectionMark:

    def test_section_group_present(self):
        svg = level_to_svg(_level_with_section_mark())
        assert 'id="section-marks"' in svg

    def test_section_tag_in_svg(self):
        svg = level_to_svg(_level_with_section_mark())
        assert ">A<" in svg

    def test_section_cut_line_in_svg(self):
        svg = level_to_svg(_level_with_section_mark())
        assert 'class="section-mark"' in svg

    def test_section_circle_bubble_in_svg(self):
        svg = level_to_svg(_level_with_section_mark())
        assert "<circle" in svg


class TestSVGStaircase:

    def test_staircase_group_present(self):
        svg = level_to_svg(_level_with_staircase())
        assert 'id="staircases"' in svg

    def test_staircase_class_in_svg(self):
        svg = level_to_svg(_level_with_staircase())
        assert 'class="staircase"' in svg

    def test_staircase_tread_lines_in_svg(self):
        svg = level_to_svg(_level_with_staircase())
        assert "<line" in svg


class TestSVGSlab:

    def test_slab_group_present(self):
        svg = level_to_svg(_level_with_slab())
        assert 'id="slabs"' in svg

    def test_slab_class_in_svg(self):
        svg = level_to_svg(_level_with_slab())
        assert 'class="slab"' in svg


class TestSVGLayeringOrder:
    """Verify render groups appear in the expected layer order."""

    def test_rooms_before_walls(self):
        svg = level_to_svg(_base_level())
        rooms_pos = svg.index('id="rooms"')
        walls_pos = svg.index('id="walls"')
        assert rooms_pos < walls_pos

    def test_walls_before_columns(self):
        from archit_app.elements.column import Column
        lv = _base_level().add_column(
            Column.rectangular(x=5, y=4, width=0.3, depth=0.3, height=3.0)
        )
        svg = level_to_svg(lv)
        walls_pos = svg.index('id="walls"')
        cols_pos = svg.index('id="columns"')
        assert walls_pos < cols_pos


# ---------------------------------------------------------------------------
# PDF tests (skipped without reportlab)
# ---------------------------------------------------------------------------

@_skip_pdf
class TestPDFFurnitureBeamRamp:

    def test_level_with_furniture_produces_pdf(self):
        from archit_app.io.pdf import level_to_pdf_bytes
        data = level_to_pdf_bytes(_level_with_furniture())
        assert data[:4] == b"%PDF"

    def test_level_with_beam_produces_pdf(self):
        from archit_app.io.pdf import level_to_pdf_bytes
        data = level_to_pdf_bytes(_level_with_beam())
        assert data[:4] == b"%PDF"

    def test_level_with_ramp_produces_pdf(self):
        from archit_app.io.pdf import level_to_pdf_bytes
        data = level_to_pdf_bytes(_level_with_ramp())
        assert data[:4] == b"%PDF"

    def test_level_with_annotation_produces_pdf(self):
        from archit_app.io.pdf import level_to_pdf_bytes
        data = level_to_pdf_bytes(_level_with_text_annotation())
        assert data[:4] == b"%PDF"

    def test_level_with_dimension_produces_pdf(self):
        from archit_app.io.pdf import level_to_pdf_bytes
        data = level_to_pdf_bytes(_level_with_dimension())
        assert data[:4] == b"%PDF"

    def test_level_with_section_mark_produces_pdf(self):
        from archit_app.io.pdf import level_to_pdf_bytes
        data = level_to_pdf_bytes(_level_with_section_mark())
        assert data[:4] == b"%PDF"

    def test_level_with_staircase_produces_pdf(self):
        from archit_app.io.pdf import level_to_pdf_bytes
        data = level_to_pdf_bytes(_level_with_staircase())
        assert data[:4] == b"%PDF"

    def test_level_with_slab_produces_pdf(self):
        from archit_app.io.pdf import level_to_pdf_bytes
        data = level_to_pdf_bytes(_level_with_slab())
        assert data[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# PNG tests (skipped without Pillow)
# ---------------------------------------------------------------------------

@_skip_png
class TestPNGFurnitureBeamRamp:

    def test_level_with_furniture_produces_png(self):
        from archit_app.io.image import level_to_png_bytes
        data = level_to_png_bytes(_level_with_furniture())
        assert data[:8] == b"\x89PNG\r\n\x1a\n"

    def test_level_with_beam_produces_png(self):
        from archit_app.io.image import level_to_png_bytes
        data = level_to_png_bytes(_level_with_beam())
        assert data[:8] == b"\x89PNG\r\n\x1a\n"

    def test_level_with_ramp_produces_png(self):
        from archit_app.io.image import level_to_png_bytes
        data = level_to_png_bytes(_level_with_ramp())
        assert data[:8] == b"\x89PNG\r\n\x1a\n"

    def test_level_with_annotation_produces_png(self):
        from archit_app.io.image import level_to_png_bytes
        data = level_to_png_bytes(_level_with_text_annotation())
        assert data[:8] == b"\x89PNG\r\n\x1a\n"

    def test_level_with_dimension_produces_png(self):
        from archit_app.io.image import level_to_png_bytes
        data = level_to_png_bytes(_level_with_dimension())
        assert data[:8] == b"\x89PNG\r\n\x1a\n"

    def test_level_with_section_mark_produces_png(self):
        from archit_app.io.image import level_to_png_bytes
        data = level_to_png_bytes(_level_with_section_mark())
        assert data[:8] == b"\x89PNG\r\n\x1a\n"

    def test_level_with_staircase_produces_png(self):
        from archit_app.io.image import level_to_png_bytes
        data = level_to_png_bytes(_level_with_staircase())
        assert data[:8] == b"\x89PNG\r\n\x1a\n"

    def test_level_with_slab_produces_png(self):
        from archit_app.io.image import level_to_png_bytes
        data = level_to_png_bytes(_level_with_slab())
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
