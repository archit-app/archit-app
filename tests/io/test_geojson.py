"""Tests for GeoJSON export and import."""

import json

import pytest

from archit_app import Level, WORLD, Polygon2D, Room, Wall, WallType, Column
from archit_app.io.geojson import (
    level_to_geojson,
    building_to_geojson,
    level_to_geojson_str,
    level_from_geojson,
    level_from_geojson_str,
)


def test_geojson_is_feature_collection(single_level_building):
    lv = single_level_building.levels[0]
    fc = level_to_geojson(lv)
    assert fc["type"] == "FeatureCollection"
    assert "features" in fc


def test_geojson_has_rooms_and_walls(single_level_building):
    lv = single_level_building.levels[0]
    fc = level_to_geojson(lv)
    types = {f["properties"]["element_type"] for f in fc["features"]}
    assert "room" in types
    assert "wall" in types


def test_geojson_room_properties(simple_square_room):
    lv = Level(index=0, elevation=0.0, floor_height=3.0).add_room(simple_square_room)
    fc = level_to_geojson(lv)
    room_features = [f for f in fc["features"] if f["properties"]["element_type"] == "room"]
    assert len(room_features) == 1
    props = room_features[0]["properties"]
    assert props["name"] == "square_room"
    assert props["program"] == "living"
    assert props["area_m2"] == pytest.approx(16.0, rel=1e-4)


def test_geojson_wall_properties(simple_wall):
    lv = Level(index=0, elevation=0.0, floor_height=3.0).add_wall(simple_wall)
    fc = level_to_geojson(lv)
    wall_features = [f for f in fc["features"] if f["properties"]["element_type"] == "wall"]
    assert len(wall_features) == 1
    props = wall_features[0]["properties"]
    assert props["wall_type"] == "exterior"
    assert props["thickness_m"] == pytest.approx(0.2)


def test_geojson_geometry_is_polygon(single_level_building):
    lv = single_level_building.levels[0]
    fc = level_to_geojson(lv)
    for feature in fc["features"]:
        geom = feature["geometry"]
        assert geom["type"] == "Polygon"
        coords = geom["coordinates"]
        assert isinstance(coords, list)
        assert len(coords) >= 1  # at least exterior ring
        # Each ring is a list of [x, y] pairs
        for ring in coords:
            assert all(len(pt) == 2 for pt in ring)


def test_geojson_closed_rings(single_level_building):
    """GeoJSON polygon rings must be closed (first == last point)."""
    lv = single_level_building.levels[0]
    fc = level_to_geojson(lv)
    for feature in fc["features"]:
        for ring in feature["geometry"]["coordinates"]:
            assert ring[0] == ring[-1], f"Ring not closed: {ring[0]} != {ring[-1]}"


def test_geojson_include_filter(single_level_building):
    lv = single_level_building.levels[0]
    fc = level_to_geojson(lv, include={"rooms"})
    types = {f["properties"]["element_type"] for f in fc["features"]}
    assert "room" in types
    assert "wall" not in types


def test_geojson_building_merges_all_levels(multi_level_building):
    fc = building_to_geojson(multi_level_building)
    level_indices = {f["properties"]["level_index"] for f in fc["features"]}
    assert level_indices == {0, 1, 2}


def test_geojson_str_is_valid_json(single_level_building):
    lv = single_level_building.levels[0]
    s = level_to_geojson_str(lv)
    parsed = json.loads(s)
    assert parsed["type"] == "FeatureCollection"


def test_geojson_opening_in_wall(wall_with_door):
    lv = Level(index=0, elevation=0.0, floor_height=3.0).add_wall(wall_with_door)
    fc = level_to_geojson(lv)
    types = {f["properties"]["element_type"] for f in fc["features"]}
    assert "opening" in types


def test_geojson_column(rectangular_column):
    lv = Level(index=0, elevation=0.0, floor_height=3.0).add_column(rectangular_column)
    fc = level_to_geojson(lv)
    col_features = [f for f in fc["features"] if f["properties"]["element_type"] == "column"]
    assert len(col_features) == 1
    assert col_features[0]["properties"]["shape"] == "rectangular"


def test_geojson_level_name(simple_square_room):
    lv = Level(index=0, elevation=0.0, floor_height=3.0, name="Ground").add_room(simple_square_room)
    fc = level_to_geojson(lv)
    assert fc["name"] == "Ground"


# ---------------------------------------------------------------------------
# GeoJSON import (level_from_geojson)
# ---------------------------------------------------------------------------

class TestGeoJSONImport:

    def _roundtrip_level(self, level: Level) -> Level:
        fc = level_to_geojson(level)
        return level_from_geojson(fc)

    def test_room_roundtrip_count(self, single_level_building):
        lv = single_level_building.levels[0]
        imported = self._roundtrip_level(lv)
        assert len(imported.rooms) == len(lv.rooms)

    def test_wall_roundtrip_count(self, single_level_building):
        lv = single_level_building.levels[0]
        imported = self._roundtrip_level(lv)
        assert len(imported.walls) == len(lv.walls)

    def test_room_name_preserved(self, single_level_building):
        lv = single_level_building.levels[0]
        imported = self._roundtrip_level(lv)
        orig_names = {r.name for r in lv.rooms}
        imp_names  = {r.name for r in imported.rooms}
        assert orig_names == imp_names

    def test_room_program_preserved(self, single_level_building):
        lv = single_level_building.levels[0]
        imported = self._roundtrip_level(lv)
        orig_programs = {r.program for r in lv.rooms}
        imp_programs  = {r.program for r in imported.rooms}
        assert orig_programs == imp_programs

    def test_column_roundtrip_count(self, single_level_building):
        from archit_app.elements.column import Column
        lv = single_level_building.levels[0]
        col = Column.rectangular(x=3, y=2, width=0.3, depth=0.3, height=3.0)
        lv = lv.add_column(col)
        imported = self._roundtrip_level(lv)
        assert len(imported.columns) == 1

    def test_invalid_type_raises(self):
        with pytest.raises((ValueError, TypeError)):
            level_from_geojson({"type": "Feature"})

    def test_from_json_string(self, single_level_building):
        lv = single_level_building.levels[0]
        s = level_to_geojson_str(lv)
        imported = level_from_geojson_str(s)
        assert len(imported.rooms) == len(lv.rooms)

    def test_level_params_respected(self, single_level_building):
        lv = single_level_building.levels[0]
        fc = level_to_geojson(lv)
        imported = level_from_geojson(fc, index=5, elevation=15.0, floor_height=4.0, name="Top")
        assert imported.index == 5
        assert imported.elevation == 15.0
        assert imported.name == "Top"
