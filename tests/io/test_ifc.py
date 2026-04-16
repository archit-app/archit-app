"""
Tests for IFC 4.x export (archit_app.io.ifc).

Tests are grouped into two classes:
  - TestImportGuard  — always run; verifies the ImportError guard fires when
                       ifcopenshell is not installed.
  - TestIfcExport    — skipped when ifcopenshell is absent; verifies the
                       generated IFC model structure and entity counts.
"""

from __future__ import annotations

import math
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
    Polygon2D,
    Room,
    Slab,
    SlabType,
    Staircase,
    Wall,
    WallType,
)
from archit_app.io.ifc import save_building_ifc, building_to_ifc

try:
    import ifcopenshell as _ifcopenshell
    _IFC_AVAILABLE = True
except ImportError:
    _ifcopenshell = None  # type: ignore[assignment]
    _IFC_AVAILABLE = False

_ifc_skip = pytest.mark.skipif(
    not _IFC_AVAILABLE,
    reason="ifcopenshell is not installed; skipping IFC export tests",
)


def _make_building(name: str = "Test Building") -> Building:
    """Minimal single-level building for structural assertions."""
    room_pts = (
        (0, 0), (6, 0), (6, 5), (0, 5),
    )
    boundary = Polygon2D(
        exterior=tuple(
            __import__("archit_app").Point2D(x=x, y=y, crs=WORLD)
            for x, y in room_pts
        ),
        crs=WORLD,
    )
    room = Room(boundary=boundary, name="Living Room", program="living")
    wall = Wall.straight(0, 0, 6, 0, thickness=0.2, height=3.0, wall_type=WallType.EXTERIOR)
    door = Opening.door(x=1.0, y=-0.1, width=0.9, height=2.1)
    wall = wall.add_opening(door)

    col = Column.rectangular(x=5.5, y=4.5, width=0.3, depth=0.3, height=3.0)
    slab = Slab.rectangular(x=0, y=0, width=6, depth=5, thickness=0.2,
                             elevation=0.0, slab_type=SlabType.FLOOR)

    stair = Staircase.straight(
        x=7, y=0, width=1.2, rise_count=10,
        rise_height=0.175, run_depth=0.28,
        bottom_level_index=0, top_level_index=1,
    )

    level = (
        Level(index=0, elevation=0.0, floor_height=3.0, name="Ground Floor")
        .add_room(room)
        .add_wall(wall)
        .add_column(col)
        .add_slab(slab)
        .add_staircase(stair)
    )
    return (
        Building(metadata=BuildingMetadata(name=name, architect="A. Architect"))
        .add_level(level)
    )


# ---------------------------------------------------------------------------
# Import guard tests — always run (no ifcopenshell needed)
# ---------------------------------------------------------------------------


class TestImportGuard:
    """Verify the ImportError guard when ifcopenshell is absent."""

    def _patch_missing(self):
        """Context manager that hides ifcopenshell from the import system."""
        return patch.dict(sys.modules, {"ifcopenshell": None, "ifcopenshell.guid": None})

    def test_building_to_ifc_raises_when_missing(self, single_level_building):
        with self._patch_missing():
            with pytest.raises(ImportError, match="ifcopenshell"):
                building_to_ifc(single_level_building)

    def test_save_building_ifc_raises_when_missing(self, single_level_building, tmp_path):
        with self._patch_missing():
            with pytest.raises(ImportError, match="ifcopenshell"):
                save_building_ifc(single_level_building, str(tmp_path / "out.ifc"))


# ---------------------------------------------------------------------------
# Full export tests — skipped when ifcopenshell is absent
# ---------------------------------------------------------------------------


@_ifc_skip
class TestIfcExport:
    """IFC structure and entity count assertions (requires ifcopenshell)."""

    @pytest.fixture()
    def building(self):
        return _make_building()

    @pytest.fixture()
    def model(self, building):
        return building_to_ifc(building)

    # -----------------------------------------------------------------------
    # Spatial hierarchy
    # -----------------------------------------------------------------------

    def test_ifc_schema_is_ifc4(self, model):
        assert model.schema == "IFC4"

    def test_has_one_project(self, model):
        projects = model.by_type("IfcProject")
        assert len(projects) == 1

    def test_project_name(self, model, building):
        project = model.by_type("IfcProject")[0]
        assert project.Name == building.metadata.name

    def test_has_one_site(self, model):
        assert len(model.by_type("IfcSite")) == 1

    def test_has_one_building(self, model):
        assert len(model.by_type("IfcBuilding")) == 1

    def test_storeys_match_levels(self, model, building):
        storeys = model.by_type("IfcBuildingStorey")
        assert len(storeys) == len(building.levels)

    def test_storey_elevation(self, model, building):
        storey = model.by_type("IfcBuildingStorey")[0]
        level = building.levels[0]
        assert math.isclose(storey.Elevation, level.elevation)

    # -----------------------------------------------------------------------
    # Walls
    # -----------------------------------------------------------------------

    def test_walls_exported(self, model, building):
        level = building.levels[0]
        ifc_walls = model.by_type("IfcWall")
        assert len(ifc_walls) == len(level.walls)

    def test_wall_has_geometry(self, model):
        wall = model.by_type("IfcWall")[0]
        assert wall.Representation is not None

    def test_wall_has_placement(self, model):
        wall = model.by_type("IfcWall")[0]
        assert wall.ObjectPlacement is not None

    # -----------------------------------------------------------------------
    # Rooms (IfcSpace)
    # -----------------------------------------------------------------------

    def test_rooms_exported_as_spaces(self, model, building):
        level = building.levels[0]
        spaces = model.by_type("IfcSpace")
        assert len(spaces) == len(level.rooms)

    def test_room_name(self, model):
        space = model.by_type("IfcSpace")[0]
        assert space.Name == "Living Room"

    def test_room_has_geometry(self, model):
        space = model.by_type("IfcSpace")[0]
        assert space.Representation is not None

    # -----------------------------------------------------------------------
    # Openings (doors from wall.openings)
    # -----------------------------------------------------------------------

    def test_doors_exported(self, model, building):
        level = building.levels[0]
        total_openings = sum(len(w.openings) for w in level.walls) + len(level.openings)
        ifc_doors = model.by_type("IfcDoor")
        ifc_windows = model.by_type("IfcWindow")
        assert len(ifc_doors) + len(ifc_windows) == total_openings

    def test_door_has_geometry(self, model):
        door = model.by_type("IfcDoor")[0]
        assert door.Representation is not None

    # -----------------------------------------------------------------------
    # Columns
    # -----------------------------------------------------------------------

    def test_columns_exported(self, model, building):
        level = building.levels[0]
        ifc_cols = model.by_type("IfcColumn")
        assert len(ifc_cols) == len(level.columns)

    def test_column_has_geometry(self, model):
        col = model.by_type("IfcColumn")[0]
        assert col.Representation is not None

    # -----------------------------------------------------------------------
    # Slabs
    # -----------------------------------------------------------------------

    def test_slabs_exported(self, model, building):
        level = building.levels[0]
        ifc_slabs = model.by_type("IfcSlab")
        assert len(ifc_slabs) == len(level.slabs)

    def test_slab_predefined_type_floor(self, model):
        slab = model.by_type("IfcSlab")[0]
        assert slab.PredefinedType == "FLOOR"

    # -----------------------------------------------------------------------
    # Staircases
    # -----------------------------------------------------------------------

    def test_stairs_exported(self, model, building):
        level = building.levels[0]
        ifc_stairs = model.by_type("IfcStair")
        assert len(ifc_stairs) == len(level.staircases)

    def test_stair_has_geometry(self, model):
        stair = model.by_type("IfcStair")[0]
        assert stair.Representation is not None

    # -----------------------------------------------------------------------
    # GUIDs — stable across re-exports
    # -----------------------------------------------------------------------

    def test_element_guids_are_stable(self, building):
        """Same building exported twice must produce identical element GUIDs."""
        m1 = building_to_ifc(building)
        m2 = building_to_ifc(building)
        guids1 = {e.GlobalId for e in m1.by_type("IfcWall")}
        guids2 = {e.GlobalId for e in m2.by_type("IfcWall")}
        assert guids1 == guids2

    # -----------------------------------------------------------------------
    # Multi-level building
    # -----------------------------------------------------------------------

    def test_multi_level_storeys(self):
        b = Building()
        for i in range(3):
            lv = Level(index=i, elevation=float(i * 3), floor_height=3.0)
            b = b.add_level(lv)
        model = building_to_ifc(b)
        assert len(model.by_type("IfcBuildingStorey")) == 3

    # -----------------------------------------------------------------------
    # File round-trip
    # -----------------------------------------------------------------------

    def test_save_and_reload(self, building, tmp_path):
        """Written IFC file can be read back with ifcopenshell."""
        path = str(tmp_path / "test.ifc")
        save_building_ifc(building, path)

        reloaded = _ifcopenshell.open(path)
        assert reloaded.schema == "IFC4"
        assert len(reloaded.by_type("IfcProject")) == 1
        assert len(reloaded.by_type("IfcBuildingStorey")) == len(building.levels)

    # -----------------------------------------------------------------------
    # Units
    # -----------------------------------------------------------------------

    def test_unit_assignment_present(self, model):
        units = model.by_type("IfcUnitAssignment")
        assert len(units) == 1

    def test_length_unit_is_metre(self, model):
        unit_set = model.by_type("IfcUnitAssignment")[0]
        length_units = [
            u for u in unit_set.Units
            if hasattr(u, "UnitType") and u.UnitType == "LENGTHUNIT"
        ]
        assert len(length_units) == 1
        assert length_units[0].Name == "METRE"
