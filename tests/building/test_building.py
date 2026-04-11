import pytest

from archit_app import Building, BuildingMetadata, Level, Room, Wall


def test_building_add_level_sorted(simple_square_room, simple_wall):
    b = Building()
    level2 = Level(index=2, elevation=6.0, floor_height=3.0)
    level0 = Level(index=0, elevation=0.0, floor_height=3.0)
    level1 = Level(index=1, elevation=3.0, floor_height=3.0)
    b = b.add_level(level2).add_level(level0).add_level(level1)
    assert [lv.index for lv in b.levels] == [0, 1, 2]


def test_building_get_level(multi_level_building):
    lv = multi_level_building.get_level(1)
    assert lv is not None
    assert lv.index == 1


def test_building_get_level_missing(multi_level_building):
    assert multi_level_building.get_level(99) is None


def test_building_total_floors(multi_level_building):
    assert multi_level_building.total_floors == 3


def test_building_get_element_by_id(single_level_building):
    lv = single_level_building.levels[0]
    wall = lv.walls[0]
    found = single_level_building.get_element_by_id(wall.id)
    assert found is not None
    assert found.id == wall.id


def test_building_frozen(single_level_building):
    with pytest.raises(Exception):
        single_level_building.metadata = BuildingMetadata(name="changed")  # type: ignore


def test_building_with_metadata(single_level_building):
    updated = single_level_building.with_metadata(name="My House", architect="Jane Doe")
    assert updated.metadata.name == "My House"
    assert updated.metadata.architect == "Jane Doe"
    assert single_level_building.metadata.name == ""  # original unchanged


def test_level_remove_element(simple_square_room, simple_wall):
    lv = Level(index=0, elevation=0.0, floor_height=3.0)
    lv = lv.add_room(simple_square_room).add_wall(simple_wall)
    assert len(lv.rooms) == 1
    lv2 = lv.remove_element(simple_square_room.id)
    assert len(lv2.rooms) == 0
    assert len(lv2.walls) == 1


def test_building_total_gross_area(multi_level_building):
    # 3 levels, each with a 4×4 room = 48 m²
    assert multi_level_building.total_gross_area == pytest.approx(48.0)
