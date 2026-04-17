"""
Tests for PNG raster export (archit_app.io.image).

Structure:
  - TestImportGuard  — always run; ImportError fires without Pillow.
  - TestPngExport    — skipped when Pillow is absent.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from archit_app import (
    WORLD, Building, BuildingMetadata, Column, Level,
    Opening, Point2D, Polygon2D, Room, Wall, WallType,
)
from archit_app.io.image import (
    level_to_png_bytes,
    save_level_png,
    save_building_pngs,
)

try:
    from PIL import Image as _PIL_Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_Image = None
    _PIL_AVAILABLE = False

_skip = pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")


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


def _make_building() -> Building:
    return Building(
        metadata=BuildingMetadata(name="PNG Test"),
        levels=(_make_level(0), _make_level(1)),
    )


# ---------------------------------------------------------------------------
# Import guard
# ---------------------------------------------------------------------------

class TestImportGuard:
    def _patch_missing(self):
        return patch.dict(sys.modules, {"PIL": None, "PIL.Image": None,
                                         "PIL.ImageDraw": None, "PIL.ImageFont": None})

    def test_level_to_png_bytes_raises_without_pillow(self):
        level = Level(index=0, elevation=0.0, floor_height=3.0)
        with self._patch_missing():
            with pytest.raises(ImportError, match="Pillow"):
                level_to_png_bytes(level)

    def test_save_level_png_raises_without_pillow(self, tmp_path):
        level = Level(index=0, elevation=0.0, floor_height=3.0)
        with self._patch_missing():
            with pytest.raises(ImportError, match="Pillow"):
                save_level_png(level, str(tmp_path / "out.png"))


# ---------------------------------------------------------------------------
# PNG export tests
# ---------------------------------------------------------------------------

@_skip
class TestPngExport:

    def test_level_to_png_bytes_returns_bytes(self):
        level = _make_level()
        data = level_to_png_bytes(level, pixels_per_meter=50)
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_png_bytes_is_valid_png(self):
        level = _make_level()
        data = level_to_png_bytes(level, pixels_per_meter=50)
        assert data[:4] == b"\x89PNG"

    def test_png_image_dimensions(self):
        level = _make_level()
        data = level_to_png_bytes(level, pixels_per_meter=50, margin=40)
        img = _PIL_Image.open(__import__("io").BytesIO(data))
        # Room is 6×5 m; at 50 px/m + 2×40 margin = 380×330 px
        assert img.width > 6 * 50
        assert img.height > 5 * 50

    def test_png_dpi_metadata(self):
        level = _make_level()
        data = level_to_png_bytes(level, pixels_per_meter=50, dpi=150)
        img = _PIL_Image.open(__import__("io").BytesIO(data))
        dpi_info = img.info.get("dpi")
        if dpi_info:
            assert dpi_info[0] == pytest.approx(150, abs=2)

    def test_png_different_scales(self):
        level = _make_level()
        small = level_to_png_bytes(level, pixels_per_meter=25)
        large = level_to_png_bytes(level, pixels_per_meter=100)
        img_small = _PIL_Image.open(__import__("io").BytesIO(small))
        img_large = _PIL_Image.open(__import__("io").BytesIO(large))
        assert img_large.width > img_small.width
        assert img_large.height > img_small.height

    def test_empty_level_produces_valid_png(self):
        level = Level(index=0, elevation=0.0, floor_height=3.0)
        data = level_to_png_bytes(level, pixels_per_meter=50)
        assert data[:4] == b"\x89PNG"

    def test_save_level_png_creates_file(self, tmp_path):
        level = _make_level()
        path = str(tmp_path / "floor.png")
        save_level_png(level, path, pixels_per_meter=50)
        import os
        assert os.path.isfile(path)
        assert os.path.getsize(path) > 0

    def test_save_building_pngs_creates_one_file_per_level(self, tmp_path):
        building = _make_building()
        paths = save_building_pngs(building, str(tmp_path), pixels_per_meter=50)
        assert len(paths) == len(building.levels)
        import os
        for p in paths:
            assert os.path.isfile(p)

    def test_save_building_pngs_filenames(self, tmp_path):
        building = _make_building()
        paths = save_building_pngs(building, str(tmp_path), pixels_per_meter=50)
        import os
        names = [os.path.basename(p) for p in paths]
        assert "level_00.png" in names
        assert "level_01.png" in names

    def test_png_is_rgb(self):
        level = _make_level()
        data = level_to_png_bytes(level, pixels_per_meter=50)
        img = _PIL_Image.open(__import__("io").BytesIO(data))
        assert img.mode == "RGB"

    def test_custom_title_does_not_crash(self):
        level = _make_level()
        data = level_to_png_bytes(level, pixels_per_meter=50, title="My Custom Title")
        assert data[:4] == b"\x89PNG"
