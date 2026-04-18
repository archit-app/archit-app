"""
Tests for DXF round-trip import/export (archit_app.io.dxf).

Tests are grouped into two classes:
  - TestImportGuard  — always run; verifies ImportError fires when ezdxf is absent.
  - TestDxfRoundTrip — skipped when ezdxf is absent; verifies that a building
                       exported to DXF and re-imported produces structurally
                       equivalent element counts and geometry.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

import archit_app
from archit_app import (
    WORLD,
    Building,
    BuildingMetadata,
    Column,
    Level,
    Opening,
    Polygon2D,
    Point2D,
    Room,
    Wall,
    WallType,
)
from archit_app.io.dxf import (
    building_from_dxf,
    building_to_dxf,
    level_from_dxf,
    level_to_dxf,
    save_building_dxf,
    save_level_dxf,
)

try:
    import ezdxf as _ezdxf
    _EZDXF_AVAILABLE = True
except ImportError:
    _ezdxf = None  # type: ignore[assignment]
    _EZDXF_AVAILABLE = False

_dxf_skip = pytest.mark.skipif(
    not _EZDXF_AVAILABLE,
    reason="ezdxf is not installed; skipping DXF tests",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pts(coords):
    return tuple(Point2D(x=x, y=y, crs=WORLD) for x, y in coords)


def _poly(coords):
    return Polygon2D(exterior=_pts(coords), crs=WORLD)


def _make_level(index: int = 0) -> Level:
    """Build a test Level with one room, one wall, one column, one opening."""
    room = Room(boundary=_poly([(0, 0), (6, 0), (6, 5), (0, 5)]),
                name="LivingRoom", level_index=index)
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
        .add_opening(door)   # also at level (not attached to wall)
    )


def _make_building(name: str = "DXF Test") -> Building:
    """Two-level building for multi-level round-trip tests."""
    lvl0 = _make_level(0)
    lvl1 = _make_level(1)
    return Building(
        metadata=BuildingMetadata(name=name),
        levels=(lvl0, lvl1),
    )


# ---------------------------------------------------------------------------
# Import guard tests — always run
# ---------------------------------------------------------------------------

class TestImportGuard:
    """Verify that ImportError is raised when ezdxf is absent."""

    def _patch_missing(self):
        return patch.dict(sys.modules, {"ezdxf": None})

    def test_level_to_dxf_raises_when_missing(self):
        level = Level(index=0, elevation=0.0, floor_height=3.0)
        with self._patch_missing():
            with pytest.raises(ImportError, match="ezdxf"):
                level_to_dxf(level)

    def test_level_from_dxf_raises_when_missing(self, tmp_path):
        with self._patch_missing():
            with pytest.raises(ImportError, match="ezdxf"):
                level_from_dxf(str(tmp_path / "nonexistent.dxf"))


# ---------------------------------------------------------------------------
# Round-trip tests — skipped without ezdxf
# ---------------------------------------------------------------------------

@_dxf_skip
class TestDxfRoundTrip:
    """Export → DXF file → import and verify structural equivalence."""

    # ------------------------------------------------------------------
    # Level round-trip
    # ------------------------------------------------------------------

    def test_level_export_produces_dxf_file(self, tmp_path):
        level = _make_level()
        path = str(tmp_path / "level.dxf")
        save_level_dxf(level, path)
        import os
        assert os.path.isfile(path)
        assert os.path.getsize(path) > 0

    def test_level_roundtrip_wall_count(self, tmp_path):
        level = _make_level()
        path = str(tmp_path / "level.dxf")
        save_level_dxf(level, path)
        imported = level_from_dxf(path)
        assert len(imported.walls) == len(level.walls)

    def test_level_roundtrip_room_count(self, tmp_path):
        level = _make_level()
        path = str(tmp_path / "level.dxf")
        save_level_dxf(level, path)
        imported = level_from_dxf(path)
        assert len(imported.rooms) == len(level.rooms)

    def test_level_roundtrip_column_count(self, tmp_path):
        level = _make_level()
        path = str(tmp_path / "level.dxf")
        save_level_dxf(level, path)
        imported = level_from_dxf(path)
        assert len(imported.columns) == len(level.columns)

    def test_level_roundtrip_opening_count(self, tmp_path):
        level = _make_level()
        path = str(tmp_path / "level.dxf")
        save_level_dxf(level, path)
        imported = level_from_dxf(path)
        # Level-level openings are exported; wall-attached openings also exported
        assert len(imported.openings) >= 1

    def test_level_roundtrip_room_area_approx(self, tmp_path):
        level = _make_level()
        path = str(tmp_path / "level.dxf")
        save_level_dxf(level, path)
        imported = level_from_dxf(path)
        original_area = level.rooms[0].area
        imported_area = imported.rooms[0].area
        assert abs(imported_area - original_area) < 0.01

    def test_level_roundtrip_index_param(self, tmp_path):
        level = _make_level(0)
        path = str(tmp_path / "level.dxf")
        save_level_dxf(level, path)
        imported = level_from_dxf(path, level_index=5)
        assert imported.index == 5

    def test_level_roundtrip_custom_defaults(self, tmp_path):
        level = _make_level()
        path = str(tmp_path / "level.dxf")
        save_level_dxf(level, path)
        imported = level_from_dxf(path, wall_height=4.0, wall_thickness=0.3)
        if imported.walls:
            assert imported.walls[0].height == pytest.approx(4.0)
            assert imported.walls[0].thickness == pytest.approx(0.3)

    # ------------------------------------------------------------------
    # Building round-trip
    # ------------------------------------------------------------------

    def test_building_export_produces_dxf_file(self, tmp_path):
        building = _make_building()
        path = str(tmp_path / "building.dxf")
        save_building_dxf(building, path)
        import os
        assert os.path.isfile(path)
        assert os.path.getsize(path) > 0

    def test_building_roundtrip_level_count(self, tmp_path):
        building = _make_building()
        path = str(tmp_path / "building.dxf")
        save_building_dxf(building, path)
        imported = building_from_dxf(path)
        assert len(imported.levels) == len(building.levels)

    def test_building_roundtrip_wall_counts(self, tmp_path):
        building = _make_building()
        path = str(tmp_path / "building.dxf")
        save_building_dxf(building, path)
        imported = building_from_dxf(path)
        for orig_lvl, imp_lvl in zip(building.levels, imported.levels):
            assert len(imp_lvl.walls) == len(orig_lvl.walls)

    def test_building_roundtrip_room_counts(self, tmp_path):
        building = _make_building()
        path = str(tmp_path / "building.dxf")
        save_building_dxf(building, path)
        imported = building_from_dxf(path)
        for orig_lvl, imp_lvl in zip(building.levels, imported.levels):
            assert len(imp_lvl.rooms) == len(orig_lvl.rooms)

    def test_building_roundtrip_column_counts(self, tmp_path):
        building = _make_building()
        path = str(tmp_path / "building.dxf")
        save_building_dxf(building, path)
        imported = building_from_dxf(path)
        for orig_lvl, imp_lvl in zip(building.levels, imported.levels):
            assert len(imp_lvl.columns) == len(orig_lvl.columns)

    def test_building_roundtrip_name(self, tmp_path):
        building = _make_building("MyProject")
        path = str(tmp_path / "building.dxf")
        save_building_dxf(building, path)
        imported = building_from_dxf(path)
        assert imported.metadata.name == "MyProject"

    def test_building_roundtrip_level_indices(self, tmp_path):
        building = _make_building()
        path = str(tmp_path / "building.dxf")
        save_building_dxf(building, path)
        imported = building_from_dxf(path)
        orig_indices = sorted(lvl.index for lvl in building.levels)
        imp_indices  = sorted(lvl.index for lvl in imported.levels)
        assert orig_indices == imp_indices

    def test_building_roundtrip_elevations(self, tmp_path):
        building = _make_building()
        path = str(tmp_path / "building.dxf")
        save_building_dxf(building, path)
        imported = building_from_dxf(path, floor_elevation_step=3.0)
        imp_sorted = sorted(imported.levels, key=lambda l: l.index)
        assert imp_sorted[0].elevation == pytest.approx(0.0)
        assert imp_sorted[1].elevation == pytest.approx(3.0)

    def test_empty_dxf_returns_empty_building(self, tmp_path):
        """A DXF with no FP_* layers should yield a building with no levels."""
        import ezdxf
        doc = ezdxf.new("R2010")
        path = str(tmp_path / "empty.dxf")
        doc.saveas(path)
        imported = building_from_dxf(path)
        assert len(imported.levels) == 0

    # ------------------------------------------------------------------
    # Generic DXF with custom layer mapping
    # ------------------------------------------------------------------

    def test_layer_mapping_walls(self, tmp_path):
        """Import a DXF that uses non-standard layer names."""
        import ezdxf

        # Build a DXF with walls on an "A-WALL" layer
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        coords = [(0, 0), (5, 0), (5, 0.2), (0, 0.2)]
        pline = msp.add_lwpolyline(coords, dxfattribs={"layer": "A-WALL"})
        pline.close(True)
        path = str(tmp_path / "generic.dxf")
        doc.saveas(path)

        imported = level_from_dxf(path, layer_mapping={"A-WALL": "walls"})
        assert len(imported.walls) == 1

    def test_layer_mapping_rooms(self, tmp_path):
        import ezdxf

        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        coords = [(0, 0), (4, 0), (4, 3), (0, 3)]
        pline = msp.add_lwpolyline(coords, dxfattribs={"layer": "A-FLOR"})
        pline.close(True)
        path = str(tmp_path / "generic_rooms.dxf")
        doc.saveas(path)

        imported = level_from_dxf(path, layer_mapping={"A-FLOR": "rooms"})
        assert len(imported.rooms) == 1
        assert imported.rooms[0].area == pytest.approx(12.0, rel=1e-3)

    def test_unknown_layers_are_ignored(self, tmp_path):
        import ezdxf

        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        coords = [(0, 0), (4, 0), (4, 3), (0, 3)]
        pline = msp.add_lwpolyline(coords, dxfattribs={"layer": "TITLE-BLOCK"})
        pline.close(True)
        path = str(tmp_path / "unknown_layers.dxf")
        doc.saveas(path)

        imported = level_from_dxf(path)
        assert len(imported.walls) == 0
        assert len(imported.rooms) == 0

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_degenerate_polyline_skipped(self, tmp_path):
        """Polylines with < 3 vertices should not produce elements."""
        import ezdxf

        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        pline = msp.add_lwpolyline(
            [(0, 0), (1, 0)],
            dxfattribs={"layer": "FP_WALLS"},
        )
        pline.close(False)
        path = str(tmp_path / "degenerate.dxf")
        doc.saveas(path)

        imported = level_from_dxf(path)
        assert len(imported.walls) == 0

    def test_single_level_building_from_level_dxf(self, tmp_path):
        """DXF exported via level_to_dxf (no L00_ prefix) imports as 1-level building."""
        level = _make_level()
        path = str(tmp_path / "single.dxf")
        save_level_dxf(level, path)
        imported = building_from_dxf(path)
        assert len(imported.levels) == 1

    def test_dxf_export_includes_annotation_layer(self, tmp_path):
        from archit_app.elements.annotation import TextAnnotation
        ann = TextAnnotation.note(x=1, y=1, text="Hello", crs=WORLD)
        level = _make_level().add_text_annotation(ann)
        path = str(tmp_path / "ann.dxf")
        save_level_dxf(level, path)
        import ezdxf
        doc = ezdxf.readfile(path)
        layer_names = {lyr.dxf.name for lyr in doc.layers}
        assert "FP_ANNOTATIONS" in layer_names

    def test_dxf_export_includes_dimension_layer(self, tmp_path):
        from archit_app.elements.annotation import DimensionLine
        dim = DimensionLine.horizontal(0, 6, y=5.5, crs=WORLD)
        level = _make_level().add_dimension(dim)
        path = str(tmp_path / "dim.dxf")
        save_level_dxf(level, path)
        import ezdxf
        doc = ezdxf.readfile(path)
        layer_names = {lyr.dxf.name for lyr in doc.layers}
        assert "FP_DIMENSIONS" in layer_names

    def test_dxf_export_includes_section_mark_layer(self, tmp_path):
        from archit_app.elements.annotation import SectionMark
        mark = SectionMark.horizontal(0, 6, y=2.5, tag="A", crs=WORLD)
        level = _make_level().add_section_mark(mark)
        path = str(tmp_path / "sect.dxf")
        save_level_dxf(level, path)
        import ezdxf
        doc = ezdxf.readfile(path)
        layer_names = {lyr.dxf.name for lyr in doc.layers}
        assert "FP_SECTION_MARKS" in layer_names

    # ------------------------------------------------------------------
    # New element type round-trips (stairs/slabs/beams/ramps/furniture)
    # ------------------------------------------------------------------

    def test_staircase_roundtrip(self, tmp_path):
        import math
        from archit_app import Staircase
        stair = Staircase.straight(x=0, y=0, width=1.2, rise_count=10,
                                    rise_height=0.175, run_depth=0.28,
                                    bottom_level_index=0, top_level_index=1)
        level = Level(index=0, elevation=0.0, floor_height=3.0).add_staircase(stair)
        path = str(tmp_path / "stairs.dxf")
        save_level_dxf(level, path)
        restored = level_from_dxf(path)
        assert len(restored.staircases) == 1
        assert restored.staircases[0].rise_count == 10

    def test_slab_roundtrip(self, tmp_path):
        from archit_app import Slab
        slab = Slab.rectangular(x=0, y=0, width=6, depth=5, thickness=0.2, elevation=0.0)
        level = Level(index=0, elevation=0.0, floor_height=3.0).add_slab(slab)
        path = str(tmp_path / "slab.dxf")
        save_level_dxf(level, path)
        restored = level_from_dxf(path)
        assert len(restored.slabs) == 1
        assert restored.slabs[0].thickness == pytest.approx(0.2)

    def test_beam_roundtrip(self, tmp_path):
        from archit_app import Beam
        beam = Beam.straight(x1=0, y1=0, x2=6, y2=0, width=0.3, depth=0.5, elevation=3.0)
        level = Level(index=0, elevation=0.0, floor_height=3.0).add_beam(beam)
        path = str(tmp_path / "beam.dxf")
        save_level_dxf(level, path)
        restored = level_from_dxf(path)
        assert len(restored.beams) == 1

    def test_ramp_roundtrip(self, tmp_path):
        import math
        from archit_app import Ramp
        ramp = Ramp.straight(x=0, y=0, width=1.5, length=3.6,
                              slope_angle=math.atan(1 / 12))
        level = Level(index=0, elevation=0.0, floor_height=3.0).add_ramp(ramp)
        path = str(tmp_path / "ramp.dxf")
        save_level_dxf(level, path)
        restored = level_from_dxf(path)
        assert len(restored.ramps) == 1
        assert restored.ramps[0].width == pytest.approx(1.5, rel=1e-2)

    def test_furniture_roundtrip(self, tmp_path):
        from archit_app import Furniture
        furn = Furniture.sofa(x=1, y=1)
        level = Level(index=0, elevation=0.0, floor_height=3.0).add_furniture(furn)
        path = str(tmp_path / "furn.dxf")
        save_level_dxf(level, path)
        restored = level_from_dxf(path)
        assert len(restored.furniture) == 1

    def test_new_element_layers_defined(self, tmp_path):
        """level_to_dxf must define FP_STAIRS, FP_SLABS, FP_BEAMS, FP_RAMPS, FP_FURNITURE."""
        import ezdxf
        level = _make_level()
        path = str(tmp_path / "layers.dxf")
        save_level_dxf(level, path)
        doc = ezdxf.readfile(path)
        layer_names = {lyr.dxf.name for lyr in doc.layers}
        for expected in ("FP_STAIRS", "FP_SLABS", "FP_BEAMS", "FP_RAMPS", "FP_FURNITURE"):
            assert expected in layer_names, f"Missing layer: {expected}"
