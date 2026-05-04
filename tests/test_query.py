"""Tests for the ElementQuery / query() selection system."""

import pytest

from archit_app import (
    WORLD,
    Column,
    Furniture,
    Level,
    Opening,
    Polygon2D,
    Room,
    Wall,
    query,
)
from archit_app.query import ElementQuery

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_level() -> Level:
    r1 = Room(boundary=Polygon2D.rectangle(0, 0, 5, 4, crs=WORLD),
              name="Bedroom", program="bedroom")
    r2 = Room(boundary=Polygon2D.rectangle(5, 0, 5, 4, crs=WORLD),
              name="Kitchen", program="kitchen")
    w1 = Wall.straight(0, 0, 10, 0, thickness=0.2, height=3.0)
    w2 = Wall.straight(0, 0, 0, 8, thickness=0.2, height=3.0).on_layer("structural")
    door = Opening.door(x=2, y=0, width=0.9, height=2.1)
    col = Column.rectangular(x=4.8, y=3.8, width=0.3, depth=0.3)
    sofa = Furniture.sofa(x=1, y=1).with_tag("color", "blue")
    desk = Furniture.desk(x=6, y=1)

    return (
        Level(index=0, elevation=0.0, floor_height=3.0)
        .add_room(r1)
        .add_room(r2)
        .add_wall(w1)
        .add_wall(w2)
        .add_opening(door)
        .add_column(col)
        .add_furniture(sofa)
        .add_furniture(desk)
    )


@pytest.fixture
def level():
    return _make_level()


# ---------------------------------------------------------------------------
# query() factory
# ---------------------------------------------------------------------------

class TestQueryFactory:

    def test_returns_element_query(self, level):
        q = query(level)
        assert isinstance(q, ElementQuery)

    def test_all_count(self, level):
        # 2 rooms + 2 walls + 1 opening + 1 column + 2 furniture = 8
        assert query(level).all().count() == 8


# ---------------------------------------------------------------------------
# Type filters
# ---------------------------------------------------------------------------

class TestTypeFilters:

    def test_walls(self, level):
        assert query(level).walls().count() == 2

    def test_rooms(self, level):
        assert query(level).rooms().count() == 2

    def test_openings(self, level):
        assert query(level).openings().count() == 1

    def test_columns(self, level):
        assert query(level).columns().count() == 1

    def test_furniture(self, level):
        assert query(level).furniture().count() == 2

    def test_staircases_empty(self, level):
        assert query(level).staircases().count() == 0

    def test_slabs_empty(self, level):
        assert query(level).slabs().count() == 0

    def test_all_no_filter(self, level):
        assert query(level).all().count() == 8


# ---------------------------------------------------------------------------
# Attribute filters
# ---------------------------------------------------------------------------

class TestOnLayer:

    def test_default_layer(self, level):
        # All elements except w2 are on "default"
        result = query(level).walls().on_layer("default")
        assert result.count() == 1

    def test_structural_layer(self, level):
        result = query(level).walls().on_layer("structural")
        assert result.count() == 1

    def test_nonexistent_layer(self, level):
        assert query(level).all().on_layer("nonexistent").count() == 0


class TestTagged:

    def test_key_only(self, level):
        result = query(level).furniture().tagged("color")
        assert result.count() == 1

    def test_key_and_value_match(self, level):
        result = query(level).furniture().tagged("color", "blue")
        assert result.count() == 1

    def test_key_and_value_no_match(self, level):
        result = query(level).furniture().tagged("color", "red")
        assert result.count() == 0

    def test_missing_key(self, level):
        result = query(level).all().tagged("fire_rating")
        assert result.count() == 0


class TestWithProgram:

    def test_bedroom(self, level):
        rooms = query(level).with_program("bedroom").list()
        assert len(rooms) == 1
        assert rooms[0].name == "Bedroom"

    def test_kitchen(self, level):
        assert query(level).with_program("kitchen").count() == 1

    def test_no_match(self, level):
        assert query(level).with_program("library").count() == 0

    def test_non_rooms_dropped(self, level):
        # Walls don't have programs — they should be absent
        result = query(level).with_program("bedroom")
        for e in result.list():
            from archit_app.elements.room import Room
            assert isinstance(e, Room)


class TestWithinBbox:

    def test_room_in_bbox(self, level):
        from archit_app.geometry.bbox import BoundingBox2D
        from archit_app.geometry.point import Point2D
        bbox = BoundingBox2D(
            min_corner=Point2D(x=0, y=0, crs=WORLD),
            max_corner=Point2D(x=6, y=5, crs=WORLD),
        )
        rooms = query(level).rooms().within_bbox(bbox).list()
        assert len(rooms) >= 1

    def test_nothing_in_tiny_bbox(self, level):
        from archit_app.geometry.bbox import BoundingBox2D
        from archit_app.geometry.point import Point2D
        bbox = BoundingBox2D(
            min_corner=Point2D(x=100, y=100, crs=WORLD),
            max_corner=Point2D(x=101, y=101, crs=WORLD),
        )
        assert query(level).rooms().within_bbox(bbox).count() == 0


# ---------------------------------------------------------------------------
# Terminal methods
# ---------------------------------------------------------------------------

class TestTerminals:

    def test_list_returns_list(self, level):
        result = query(level).walls().list()
        assert isinstance(result, list)
        assert len(result) == 2

    def test_first_returns_element(self, level):
        el = query(level).walls().first()
        from archit_app.elements.wall import Wall
        assert isinstance(el, Wall)

    def test_first_returns_none_when_empty(self, level):
        assert query(level).staircases().first() is None

    def test_count(self, level):
        assert query(level).rooms().count() == 2

    def test_chaining(self, level):
        # Chain: all walls on default layer
        result = query(level).all().walls().on_layer("default").count()
        assert result == 1
