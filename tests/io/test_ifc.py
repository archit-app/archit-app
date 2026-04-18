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
from archit_app.io.ifc import save_building_ifc, building_to_ifc, building_from_ifc, level_from_ifc

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

    # -----------------------------------------------------------------------
    # Extended elements: Ramp, Beam, Furniture, Elevator
    # -----------------------------------------------------------------------

    def test_ramp_exported_as_ifc_ramp(self):
        from archit_app import Ramp
        ramp = Ramp.straight(x=0, y=6, width=1.5, length=4.0, slope_angle=math.atan(1 / 12))
        level = Level(index=0, elevation=0.0, floor_height=3.0).add_ramp(ramp)
        b = Building().add_level(level)
        model = building_to_ifc(b)
        ifc_ramps = model.by_type("IfcRamp")
        assert len(ifc_ramps) == 1
        assert ifc_ramps[0].Representation is not None

    def test_beam_exported_as_ifc_beam(self):
        from archit_app.elements.beam import Beam
        beam = Beam.straight(x1=0, y1=2, x2=6, y2=2, width=0.3, depth=0.5, elevation=3.0)
        level = Level(index=0, elevation=0.0, floor_height=3.0).add_beam(beam)
        b = Building().add_level(level)
        model = building_to_ifc(b)
        ifc_beams = model.by_type("IfcBeam")
        assert len(ifc_beams) == 1
        assert ifc_beams[0].Representation is not None

    def test_furniture_exported_as_ifc_furnishing_element(self):
        from archit_app import Furniture
        furn = Furniture.sofa(x=1, y=1)
        level = Level(index=0, elevation=0.0, floor_height=3.0).add_furniture(furn)
        b = Building().add_level(level)
        model = building_to_ifc(b)
        ifc_furn = model.by_type("IfcFurnishingElement")
        assert len(ifc_furn) == 1
        assert ifc_furn[0].Representation is not None

    def test_elevator_exported_as_ifc_transport_element(self):
        from archit_app.elements.elevator import Elevator
        elev_elem = Elevator.standard(x=8, y=0, bottom_level_index=0, top_level_index=1)
        level = Level(index=0, elevation=0.0, floor_height=3.0)
        b = Building().add_level(level).add_elevator(elev_elem)
        model = building_to_ifc(b)
        ifc_elev = model.by_type("IfcTransportElement")
        assert len(ifc_elev) == 1
        assert ifc_elev[0].Representation is not None


# ---------------------------------------------------------------------------
# IFC import (building_from_ifc) tests — skipped when ifcopenshell is absent
# ---------------------------------------------------------------------------


@_ifc_skip
class TestIfcImport:
    """Round-trip and import correctness tests (requires ifcopenshell)."""

    @pytest.fixture()
    def building(self):
        return _make_building()

    @pytest.fixture()
    def roundtrip(self, building, tmp_path):
        """Export → import round-trip; returns imported Building."""
        path = str(tmp_path / "rt.ifc")
        save_building_ifc(building, path)
        return building_from_ifc(path)

    def test_building_from_ifc_returns_building(self, roundtrip):
        assert isinstance(roundtrip, Building)

    def test_level_count_preserved(self, building, roundtrip):
        assert len(roundtrip.levels) == len(building.levels)

    def test_level_elevation_preserved(self, building, roundtrip):
        orig_elev = building.levels[0].elevation
        imp_elev = roundtrip.levels[0].elevation
        assert math.isclose(orig_elev, imp_elev, abs_tol=1e-3)

    def test_level_name_preserved(self, building, roundtrip):
        assert roundtrip.levels[0].name == building.levels[0].name

    def test_walls_imported(self, building, roundtrip):
        assert len(roundtrip.levels[0].walls) == len(building.levels[0].walls)

    def test_rooms_imported(self, building, roundtrip):
        assert len(roundtrip.levels[0].rooms) == len(building.levels[0].rooms)

    def test_columns_imported(self, building, roundtrip):
        assert len(roundtrip.levels[0].columns) == len(building.levels[0].columns)

    def test_slabs_imported(self, building, roundtrip):
        assert len(roundtrip.levels[0].slabs) == len(building.levels[0].slabs)

    def test_staircases_imported(self, building, roundtrip):
        assert len(roundtrip.levels[0].staircases) == len(building.levels[0].staircases)

    def test_room_name_preserved(self, roundtrip):
        room = roundtrip.levels[0].rooms[0]
        assert room.name == "Living Room"

    def test_wall_height_preserved(self, building, roundtrip):
        orig_height = building.levels[0].walls[0].height
        imp_height = roundtrip.levels[0].walls[0].height
        assert math.isclose(orig_height, imp_height, abs_tol=1e-3)

    def test_wall_polygon_vertex_count(self, building, roundtrip):
        orig = building.levels[0].walls[0].geometry
        imp = roundtrip.levels[0].walls[0].geometry
        # Both should be Polygon2D with the same number of exterior vertices
        assert len(imp.exterior) == len(orig.exterior)

    def test_building_name_preserved(self, building, roundtrip):
        assert roundtrip.metadata.name == building.metadata.name

    def test_openings_imported_as_level_openings(self, roundtrip):
        # Doors from wall.openings are exported as IfcDoor and imported to level.openings
        lv = roundtrip.levels[0]
        total = len(lv.openings) + sum(len(w.openings) for w in lv.walls)
        assert total >= 1

    def test_multi_level_roundtrip(self, tmp_path):
        b = Building()
        for i in range(3):
            room = Room(
                boundary=Polygon2D.rectangle(0, 0, 5, 4, crs=WORLD),
                name=f"Room {i}",
                program="living",
            )
            lv = Level(index=i, elevation=float(i * 3), floor_height=3.0).add_room(room)
            b = b.add_level(lv)
        path = str(tmp_path / "ml.ifc")
        save_building_ifc(b, path)
        restored = building_from_ifc(path)
        assert len(restored.levels) == 3
        elevations = [lv.elevation for lv in restored.levels]
        assert all(math.isclose(a, b_elev, abs_tol=1e-3)
                   for a, b_elev in zip(elevations, [0.0, 3.0, 6.0]))

    def test_level_from_ifc_returns_level(self, building, tmp_path):
        from archit_app.building.level import Level as _Level
        path = str(tmp_path / "lv.ifc")
        save_building_ifc(building, path)
        lv = level_from_ifc(path, storey_index=0)
        assert isinstance(lv, _Level)
        assert len(lv.rooms) >= 1

    def test_empty_building_roundtrip(self, tmp_path):
        b = Building(metadata=BuildingMetadata(name="Empty"))
        lv = Level(index=0, elevation=0.0, floor_height=3.0)
        b = b.add_level(lv)
        path = str(tmp_path / "empty.ifc")
        save_building_ifc(b, path)
        restored = building_from_ifc(path)
        assert len(restored.levels) == 1
        assert len(restored.levels[0].rooms) == 0

    def test_import_guard_raises(self, tmp_path):
        """building_from_ifc must raise ImportError when ifcopenshell is absent."""
        from unittest.mock import patch
        import sys
        path = str(tmp_path / "dummy.ifc")
        with patch.dict(sys.modules, {"ifcopenshell": None, "ifcopenshell.guid": None}):
            with pytest.raises(ImportError, match="ifcopenshell"):
                building_from_ifc(path)
