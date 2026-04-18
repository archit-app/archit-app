"""Tests for Level.spatial_index()."""

from __future__ import annotations

import pytest

try:
    from shapely.geometry import box as shp_box
    _SHAPELY = True
except ImportError:
    _SHAPELY = False

_skip = pytest.mark.skipif(not _SHAPELY, reason="Shapely not installed")

from archit_app import WORLD, Level, Room, Polygon2D, Wall
from archit_app.elements.column import Column


def _make_level() -> Level:
    room = Room(
        boundary=Polygon2D.rectangle(0, 0, 6, 5, crs=WORLD),
        name="Hall",
        program="living",
    )
    wall = Wall.straight(0, 0, 6, 0, thickness=0.2, height=3.0)
    col = Column.rectangular(x=5, y=4, width=0.3, depth=0.3, height=3.0)
    return (
        Level(index=0, elevation=0.0, floor_height=3.0)
        .add_room(room)
        .add_wall(wall)
        .add_column(col)
    )


@_skip
class TestSpatialIndex:

    def test_returns_tree_and_elements(self):
        level = _make_level()
        tree, elements = level.spatial_index()
        assert len(elements) > 0

    def test_query_returns_hits(self):
        level = _make_level()
        tree, elements = level.spatial_index()
        # Query a box that covers the whole level
        hits = tree.query(shp_box(0, 0, 10, 10))
        assert len(hits) > 0

    def test_query_empty_region_returns_no_hits(self):
        level = _make_level()
        tree, elements = level.spatial_index()
        # Far away region
        hits = tree.query(shp_box(100, 100, 200, 200))
        assert len(hits) == 0

    def test_partial_query_filters_correctly(self):
        """Elements in the queried region should be subset of all elements."""
        level = _make_level()
        tree, elements = level.spatial_index()
        # Small query box far from column at (5, 4)
        hits = tree.query(shp_box(0, 0, 2, 2))
        hit_ids = {elements[i].id for i in hits}
        all_ids = {e.id for e in elements}
        assert hit_ids.issubset(all_ids)

    def test_empty_level_returns_empty_tree(self):
        level = Level(index=0, elevation=0.0, floor_height=3.0)
        tree, elements = level.spatial_index()
        assert len(elements) == 0
        hits = tree.query(shp_box(0, 0, 10, 10))
        assert len(hits) == 0
