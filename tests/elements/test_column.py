"""Tests for the Column element."""

import math
import pytest

from archit_app import Column, ColumnShape, WORLD
from archit_app.geometry.crs import SCREEN


class TestColumnRectangular:

    def test_basic(self):
        col = Column.rectangular(x=1.0, y=2.0, width=0.4, depth=0.4, height=3.0)
        assert col.height == pytest.approx(3.0)
        assert col.shape == ColumnShape.RECTANGULAR

    def test_footprint_area(self):
        col = Column.rectangular(x=0, y=0, width=0.3, depth=0.5, height=3.0)
        assert col.geometry.area == pytest.approx(0.15)

    def test_lower_left_position(self):
        col = Column.rectangular(x=2.0, y=3.0, width=0.4, depth=0.4)
        bb = col.bounding_box()
        assert bb.min_corner.x == pytest.approx(2.0)
        assert bb.min_corner.y == pytest.approx(3.0)
        assert bb.max_corner.x == pytest.approx(2.4)
        assert bb.max_corner.y == pytest.approx(3.4)

    def test_default_height(self):
        col = Column.rectangular(x=0, y=0, width=0.3, depth=0.3)
        assert col.height == pytest.approx(3.0)

    def test_material(self):
        col = Column.rectangular(x=0, y=0, width=0.3, depth=0.3, material="concrete")
        assert col.material == "concrete"

    def test_material_default_none(self):
        col = Column.rectangular(x=0, y=0, width=0.3, depth=0.3)
        assert col.material is None

    def test_crs_default_world(self):
        col = Column.rectangular(x=0, y=0, width=0.3, depth=0.3)
        assert col.crs == WORLD

    def test_custom_crs_on_geometry(self):
        # The crs kwarg is forwarded to the geometry polygon, not the element's crs field.
        col = Column.rectangular(x=0, y=0, width=0.3, depth=0.3, crs=SCREEN)
        assert col.geometry.crs == SCREEN

    def test_unique_ids(self):
        c1 = Column.rectangular(x=0, y=0, width=0.3, depth=0.3)
        c2 = Column.rectangular(x=0, y=0, width=0.3, depth=0.3)
        assert c1.id != c2.id

    def test_frozen(self):
        col = Column.rectangular(x=0, y=0, width=0.3, depth=0.3)
        with pytest.raises(Exception):
            col.height = 5.0  # type: ignore

    def test_repr(self):
        col = Column.rectangular(x=0, y=0, width=0.3, depth=0.3)
        r = repr(col)
        assert "Column" in r
        assert "rectangular" in r


class TestColumnCircular:

    def test_basic(self):
        col = Column.circular(center_x=0, center_y=0, diameter=0.4, height=3.0)
        assert col.height == pytest.approx(3.0)
        assert col.shape == ColumnShape.CIRCULAR

    def test_footprint_area_approx_circle(self):
        d = 0.4
        col = Column.circular(center_x=0, center_y=0, diameter=d, height=3.0, resolution=128)
        expected = math.pi * (d / 2) ** 2
        assert col.geometry.area == pytest.approx(expected, rel=0.01)

    def test_bounding_box_centered(self):
        col = Column.circular(center_x=2.0, center_y=3.0, diameter=0.5, resolution=64)
        bb = col.bounding_box()
        # Center should be at (2.0, 3.0) and radius is 0.25
        assert bb.min_corner.x == pytest.approx(2.0 - 0.25, rel=0.01)
        assert bb.max_corner.x == pytest.approx(2.0 + 0.25, rel=0.01)

    def test_resolution_default(self):
        col = Column.circular(center_x=0, center_y=0, diameter=0.4)
        # Default resolution=32 → 32 exterior points
        assert len(col.geometry.exterior) >= 32

    def test_crs_default_world(self):
        col = Column.circular(center_x=0, center_y=0, diameter=0.4)
        assert col.crs == WORLD


class TestColumnShape:

    def test_shape_enum_values(self):
        assert ColumnShape.RECTANGULAR.value == "rectangular"
        assert ColumnShape.CIRCULAR.value == "circular"
        assert ColumnShape.CUSTOM.value == "custom"

    def test_custom_shape_via_direct_construction(self):
        from archit_app.geometry.polygon import Polygon2D
        from archit_app.geometry.point import Point2D

        pts = tuple(Point2D(x=x, y=y) for x, y in [(0,0),(1,0),(0.5,1)])
        poly = Polygon2D(exterior=pts)
        col = Column(geometry=poly, height=3.0, shape=ColumnShape.CUSTOM)
        assert col.shape == ColumnShape.CUSTOM

    def test_bounding_box_returns_bbox2d(self):
        from archit_app.geometry.bbox import BoundingBox2D
        col = Column.rectangular(x=0, y=0, width=0.3, depth=0.3)
        assert isinstance(col.bounding_box(), BoundingBox2D)

    def test_tags_default_empty(self):
        col = Column.rectangular(x=0, y=0, width=0.3, depth=0.3)
        assert col.tags == {}

    def test_with_tag(self):
        col = Column.rectangular(x=0, y=0, width=0.3, depth=0.3)
        col2 = col.with_tag("fire_rating", "2hr")
        assert col2.tags["fire_rating"] == "2hr"
        assert col.tags == {}  # original unchanged
