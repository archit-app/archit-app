"""Tests for Building.stats() and Level.replace_element()."""

import pytest

from archit_app import (
    WORLD,
    Building,
    BuildingStats,
    Furniture,
    Level,
    Polygon2D,
    Room,
    Wall,
)


def _room(x, y, w, h, program="office"):
    return Room(boundary=Polygon2D.rectangle(x, y, w, h, crs=WORLD), program=program)


def _level(index=0, *rooms):
    lv = Level(index=index, elevation=0.0, floor_height=3.0)
    for r in rooms:
        lv = lv.add_room(r)
    return lv


# ---------------------------------------------------------------------------
# Building.stats()
# ---------------------------------------------------------------------------

class TestBuildingStats:

    def test_returns_building_stats(self):
        b = Building().add_level(_level(0, _room(0, 0, 6, 4)))
        s = b.stats()
        assert isinstance(s, BuildingStats)

    def test_total_levels(self):
        b = (
            Building()
            .add_level(_level(0, _room(0, 0, 6, 4)))
            .add_level(_level(1, _room(0, 0, 6, 4)))
        )
        assert b.stats().total_levels == 2

    def test_total_rooms(self):
        b = Building().add_level(
            _level(0, _room(0, 0, 5, 4, "bedroom"), _room(5, 0, 5, 4, "kitchen"))
        )
        assert b.stats().total_rooms == 2

    def test_gross_floor_area(self):
        b = Building().add_level(_level(0, _room(0, 0, 6, 4)))
        assert b.stats().gross_floor_area_m2 == pytest.approx(24.0)

    def test_net_floor_area(self):
        b = Building().add_level(_level(0, _room(0, 0, 6, 4)))
        assert b.stats().net_floor_area_m2 == pytest.approx(24.0)

    def test_area_by_program(self):
        b = Building().add_level(
            _level(0, _room(0, 0, 5, 4, "bedroom"), _room(5, 0, 5, 4, "kitchen"))
        )
        s = b.stats()
        assert s.area_by_program["bedroom"] == pytest.approx(20.0)
        assert s.area_by_program["kitchen"] == pytest.approx(20.0)

    def test_area_by_program_multi_level(self):
        lv0 = _level(0, _room(0, 0, 6, 4, "office"))
        lv1 = _level(1, _room(0, 0, 6, 4, "office"))
        b = Building().add_level(lv0).add_level(lv1)
        assert b.stats().area_by_program["office"] == pytest.approx(48.0)

    def test_element_counts_by_level(self):
        lv = _level(0, _room(0, 0, 6, 4))
        lv = lv.add_wall(Wall.straight(0, 0, 6, 0, thickness=0.2, height=3.0))
        b = Building().add_level(lv)
        counts = b.stats().element_counts_by_level
        assert len(counts) == 1
        assert counts[0]["walls"] == 1
        assert counts[0]["rooms"] == 1

    def test_total_walls(self):
        lv = _level(0)
        lv = lv.add_wall(Wall.straight(0, 0, 6, 0, thickness=0.2, height=3.0))
        lv = lv.add_wall(Wall.straight(6, 0, 6, 4, thickness=0.2, height=3.0))
        b = Building().add_level(lv)
        assert b.stats().total_walls == 2

    def test_total_furniture(self):
        lv = _level(0).add_furniture(Furniture.sofa(x=0, y=0))
        b = Building().add_level(lv)
        assert b.stats().total_furniture == 1

    def test_empty_building(self):
        s = Building().stats()
        assert s.total_levels == 0
        assert s.total_rooms == 0
        assert s.gross_floor_area_m2 == pytest.approx(0.0)
        assert s.area_by_program == {}

    def test_frozen(self):
        s = Building().stats()
        with pytest.raises(Exception):
            s.total_levels = 99  # type: ignore


# ---------------------------------------------------------------------------
# Level.replace_element()
# ---------------------------------------------------------------------------

class TestLevelReplaceElement:

    def test_replace_room(self):
        r1 = _room(0, 0, 6, 4, "bedroom")
        r2 = _room(0, 0, 6, 4, "office")
        lv = _level(0, r1)
        lv2 = lv.replace_element(r1.id, r2)
        assert len(lv2.rooms) == 1
        assert lv2.rooms[0].program == "office"

    def test_replace_wall(self):
        w1 = Wall.straight(0, 0, 6, 0, thickness=0.2, height=3.0)
        w2 = Wall.straight(0, 0, 6, 0, thickness=0.3, height=3.0)
        lv = Level(index=0, elevation=0.0, floor_height=3.0).add_wall(w1)
        lv2 = lv.replace_element(w1.id, w2)
        assert lv2.walls[0].thickness == pytest.approx(0.3)

    def test_replace_preserves_order(self):
        r1 = _room(0, 0, 3, 4, "a")
        r2 = _room(3, 0, 3, 4, "b")
        r3 = _room(6, 0, 3, 4, "c")
        lv = _level(0, r1, r2, r3)
        r2_new = _room(3, 0, 3, 4, "NEW")
        lv2 = lv.replace_element(r2.id, r2_new)
        programs = [r.program for r in lv2.rooms]
        assert programs == ["a", "NEW", "c"]

    def test_replace_missing_raises(self):
        import uuid
        lv = _level(0, _room(0, 0, 6, 4))
        with pytest.raises(KeyError):
            lv.replace_element(uuid.uuid4(), _room(0, 0, 6, 4))

    def test_original_level_unchanged(self):
        r1 = _room(0, 0, 6, 4, "bedroom")
        lv = _level(0, r1)
        _ = lv.replace_element(r1.id, _room(0, 0, 6, 4, "office"))
        assert lv.rooms[0].program == "bedroom"

    def test_replace_furniture(self):
        sofa = Furniture.sofa(x=0, y=0)
        desk = Furniture.desk(x=0, y=0)
        lv = Level(index=0, elevation=0.0, floor_height=3.0).add_furniture(sofa)
        lv2 = lv.replace_element(sofa.id, desk)
        from archit_app.elements.furniture import FurnitureCategory
        assert lv2.furniture[0].category == FurnitureCategory.DESK
