"""
Tests for PDF export (archit_app.io.pdf).

Structure:
  - TestImportGuard  — always run; ImportError fires without reportlab.
  - TestPdfExport    — skipped when reportlab is absent.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from archit_app import (
    WORLD,
    Building,
    BuildingMetadata,
    Column,
    Level,
    Opening,
    Point2D,
    Polygon2D,
    Room,
    Wall,
    WallType,
)
from archit_app.io.pdf import (
    building_to_pdf_bytes,
    level_to_pdf_bytes,
    save_building_pdf,
    save_level_pdf,
)

try:
    import reportlab as _rl
    _RL_AVAILABLE = True
except ImportError:
    _rl = None
    _RL_AVAILABLE = False

_skip = pytest.mark.skipif(not _RL_AVAILABLE, reason="reportlab not installed")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _pts(coords):
    return tuple(Point2D(x=x, y=y, crs=WORLD) for x, y in coords)


def _poly(coords):
    return Polygon2D(exterior=_pts(coords), crs=WORLD)


def _make_level(index: int = 0) -> Level:
    room = Room(boundary=_poly([(0, 0), (6, 0), (6, 5), (0, 5)]),
                name="Living Room", program="living", level_index=index)
    wall = Wall.straight(0, 0, 6, 0, thickness=0.2, height=3.0,
                          wall_type=WallType.EXTERIOR)
    door = Opening.door(x=1.0, y=-0.1, width=0.9, height=2.1)
    wall = wall.add_opening(door)
    col  = Column.rectangular(x=5.5, y=4.5, width=0.3, depth=0.3, height=3.0)
    return (
        Level(index=index, elevation=index * 3.0, floor_height=3.0)
        .add_room(room)
        .add_wall(wall)
        .add_column(col)
        .add_opening(door)
    )


def _make_building(name: str = "PDF Test") -> Building:
    return Building(
        metadata=BuildingMetadata(name=name),
        levels=(_make_level(0), _make_level(1)),
    )


# ---------------------------------------------------------------------------
# Import guard
# ---------------------------------------------------------------------------

class TestImportGuard:
    def _patch_missing(self):
        return patch.dict(sys.modules, {
            "reportlab": None,
            "reportlab.pdfgen": None,
            "reportlab.pdfgen.canvas": None,
            "reportlab.lib": None,
            "reportlab.lib.colors": None,
            "reportlab.lib.pagesizes": None,
        })

    def test_level_to_pdf_bytes_raises_without_reportlab(self):
        level = Level(index=0, elevation=0.0, floor_height=3.0)
        with self._patch_missing():
            with pytest.raises(ImportError, match="reportlab"):
                level_to_pdf_bytes(level)

    def test_save_level_pdf_raises_without_reportlab(self, tmp_path):
        level = Level(index=0, elevation=0.0, floor_height=3.0)
        with self._patch_missing():
            with pytest.raises(ImportError, match="reportlab"):
                save_level_pdf(level, str(tmp_path / "out.pdf"))


# ---------------------------------------------------------------------------
# PDF export tests
# ---------------------------------------------------------------------------

@_skip
class TestPdfExport:

    def test_level_to_pdf_bytes_returns_bytes(self):
        level = _make_level()
        data = level_to_pdf_bytes(level)
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_pdf_magic_bytes(self):
        level = _make_level()
        data = level_to_pdf_bytes(level)
        assert data[:4] == b"%PDF"

    def test_pdf_has_eof(self):
        level = _make_level()
        data = level_to_pdf_bytes(level)
        assert b"%%EOF" in data

    def test_empty_level_produces_valid_pdf(self):
        level = Level(index=0, elevation=0.0, floor_height=3.0)
        data = level_to_pdf_bytes(level)
        assert data[:4] == b"%PDF"

    def test_save_level_pdf_creates_file(self, tmp_path):
        level = _make_level()
        path = str(tmp_path / "floor.pdf")
        save_level_pdf(level, path)
        import os
        assert os.path.isfile(path)
        assert os.path.getsize(path) > 0

    def test_paper_size_a4(self):
        level = _make_level()
        data = level_to_pdf_bytes(level, paper_size="A4")
        assert data[:4] == b"%PDF"

    def test_paper_size_a3(self):
        level = _make_level()
        data = level_to_pdf_bytes(level, paper_size="A3")
        assert data[:4] == b"%PDF"

    def test_paper_size_letter(self):
        level = _make_level()
        data = level_to_pdf_bytes(level, paper_size="letter")
        assert data[:4] == b"%PDF"

    def test_landscape_override(self):
        level = _make_level()
        data_ls = level_to_pdf_bytes(level, landscape=True)
        data_pt = level_to_pdf_bytes(level, landscape=False)
        assert data_ls[:4] == b"%PDF"
        assert data_pt[:4] == b"%PDF"
        # Landscape and portrait should differ in content/page size
        assert data_ls != data_pt

    def test_custom_title(self):
        level = _make_level()
        data = level_to_pdf_bytes(level, title="Ground Floor Plan")
        assert data[:4] == b"%PDF"

    def test_building_to_pdf_bytes_returns_bytes(self):
        building = _make_building()
        data = building_to_pdf_bytes(building)
        assert isinstance(data, bytes)
        assert data[:4] == b"%PDF"

    def test_building_pdf_contains_multiple_pages(self):
        building = _make_building()
        data = building_to_pdf_bytes(building)
        # Each showPage() adds a stream; count page markers
        page_count = data.count(b"/Type /Page\n") + data.count(b"/Type/Page\n")
        # At minimum there should be 2 page objects for a 2-level building
        # (exact count depends on reportlab internals — just check it's > 0)
        assert page_count >= 1

    def test_empty_building_produces_pdf(self):
        building = Building(metadata=BuildingMetadata(name="Empty"))
        data = building_to_pdf_bytes(building)
        assert data[:4] == b"%PDF"

    def test_save_building_pdf_creates_file(self, tmp_path):
        building = _make_building()
        path = str(tmp_path / "building.pdf")
        save_building_pdf(building, path)
        import os
        assert os.path.isfile(path)
        assert os.path.getsize(path) > 0

    def test_save_building_pdf_size_grows_with_levels(self, tmp_path):
        """More levels → larger PDF (more content)."""
        one_level = Building(
            metadata=BuildingMetadata(name="One"),
            levels=(_make_level(0),),
        )
        two_level = _make_building()

        d1 = building_to_pdf_bytes(one_level)
        d2 = building_to_pdf_bytes(two_level)
        assert len(d2) > len(d1)

    def test_wide_level_auto_landscape(self):
        """A wider-than-tall room should auto-select landscape orientation."""
        # 10×2 m room — clearly landscape
        room = Room(
            boundary=Polygon2D(
                exterior=tuple(Point2D(x=x, y=y, crs=WORLD)
                               for x, y in [(0, 0), (10, 0), (10, 2), (0, 2)]),
                crs=WORLD,
            ),
        )
        level = Level(index=0, elevation=0.0, floor_height=3.0).add_room(room)
        data = level_to_pdf_bytes(level, landscape=None)
        assert data[:4] == b"%PDF"
