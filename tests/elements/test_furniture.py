"""Tests for the Furniture element."""

import math
import pytest

from archit_app import Furniture, FurnitureCategory, Level, Polygon2D, WORLD
from archit_app.geometry.point import Point2D


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rect_poly(x, y, w, d):
    return Polygon2D.rectangle(x, y, w, d, crs=WORLD)


# ---------------------------------------------------------------------------
# Generic rectangular factory
# ---------------------------------------------------------------------------

class TestRectangularFactory:
    def test_basic(self):
        f = Furniture.rectangular(0, 0, 1.4, 0.7)
        assert f.width == pytest.approx(1.4)
        assert f.depth == pytest.approx(0.7)
        assert f.category == FurnitureCategory.CUSTOM

    def test_footprint_area(self):
        f = Furniture.rectangular(0, 0, 2.0, 1.0)
        assert f.footprint_area == pytest.approx(2.0)

    def test_label(self):
        f = Furniture.rectangular(0, 0, 1.0, 1.0, label="My Table")
        assert f.label == "My Table"

    def test_category_override(self):
        f = Furniture.rectangular(0, 0, 1.0, 1.0,
                                   category=FurnitureCategory.DESK)
        assert f.category == FurnitureCategory.DESK

    def test_height(self):
        f = Furniture.rectangular(0, 0, 1.0, 1.0, height=0.45)
        assert f.height == pytest.approx(0.45)

    def test_default_height(self):
        f = Furniture.rectangular(0, 0, 1.0, 1.0)
        assert f.height == pytest.approx(0.75)

    def test_bounding_box(self):
        f = Furniture.rectangular(1.0, 2.0, 3.0, 4.0)
        bb = f.bounding_box()
        assert bb.min_corner.x == pytest.approx(1.0)
        assert bb.min_corner.y == pytest.approx(2.0)
        assert bb.max_corner.x == pytest.approx(4.0)
        assert bb.max_corner.y == pytest.approx(6.0)

    def test_id_unique(self):
        f1 = Furniture.rectangular(0, 0, 1.0, 1.0)
        f2 = Furniture.rectangular(0, 0, 1.0, 1.0)
        assert f1.id != f2.id

    def test_frozen(self):
        f = Furniture.rectangular(0, 0, 1.0, 1.0)
        with pytest.raises(Exception):
            f.label = "changed"  # type: ignore


# ---------------------------------------------------------------------------
# Seating factories
# ---------------------------------------------------------------------------

class TestSeating:
    def test_sofa_defaults(self):
        f = Furniture.sofa(0, 0)
        assert f.category == FurnitureCategory.SOFA
        assert f.width == pytest.approx(2.2)
        assert f.depth == pytest.approx(0.9)
        assert f.label == "Sofa"

    def test_sofa_custom_size(self):
        f = Furniture.sofa(1.0, 2.0, width=3.0, depth=1.0)
        assert f.width == pytest.approx(3.0)
        assert f.footprint_area == pytest.approx(3.0)

    def test_armchair_defaults(self):
        f = Furniture.armchair(0, 0)
        assert f.category == FurnitureCategory.ARMCHAIR
        assert f.width == pytest.approx(0.85)
        assert f.depth == pytest.approx(0.85)

    def test_dining_chair_defaults(self):
        f = Furniture.dining_chair(0, 0)
        assert f.category == FurnitureCategory.DINING_CHAIR
        assert f.width == pytest.approx(0.45)

    def test_office_chair_circular_footprint(self):
        f = Furniture.office_chair(0, 0, diameter=0.65)
        assert f.category == FurnitureCategory.OFFICE_CHAIR
        # Circle area ≈ π*(0.325)² ≈ 0.332
        assert f.footprint_area == pytest.approx(math.pi * (0.65/2)**2, rel=0.02)

    def test_office_chair_dimensions(self):
        f = Furniture.office_chair(0, 0, diameter=0.7)
        assert f.width == pytest.approx(0.7)
        assert f.depth == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

class TestTables:
    def test_dining_table_defaults(self):
        f = Furniture.dining_table(0, 0)
        assert f.category == FurnitureCategory.DINING_TABLE
        assert f.width == pytest.approx(1.6)
        assert f.depth == pytest.approx(0.9)

    def test_coffee_table_defaults(self):
        f = Furniture.coffee_table(0, 0)
        assert f.category == FurnitureCategory.COFFEE_TABLE
        assert f.height == pytest.approx(0.45)

    def test_round_table_circular(self):
        f = Furniture.round_table(0, 0, diameter=1.2)
        assert f.width == pytest.approx(1.2)
        assert f.depth == pytest.approx(1.2)
        assert f.footprint_area == pytest.approx(math.pi * 0.6**2, rel=0.02)

    def test_desk_defaults(self):
        f = Furniture.desk(0, 0)
        assert f.category == FurnitureCategory.DESK
        assert f.width == pytest.approx(1.4)
        assert f.depth == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Bedroom
# ---------------------------------------------------------------------------

class TestBedroom:
    def test_bed_single(self):
        f = Furniture.bed_single(0, 0)
        assert f.category == FurnitureCategory.BED
        assert f.width == pytest.approx(0.9)
        assert f.depth == pytest.approx(2.0)

    def test_bed_double(self):
        f = Furniture.bed_double(0, 0)
        assert f.width == pytest.approx(1.4)

    def test_bed_queen(self):
        f = Furniture.bed_queen(0, 0)
        assert f.width == pytest.approx(1.6)

    def test_bed_king(self):
        f = Furniture.bed_king(0, 0)
        assert f.width == pytest.approx(1.8)

    def test_wardrobe_defaults(self):
        f = Furniture.wardrobe(0, 0)
        assert f.category == FurnitureCategory.WARDROBE
        assert f.height == pytest.approx(2.1)


# ---------------------------------------------------------------------------
# Storage & living
# ---------------------------------------------------------------------------

class TestStorageLiving:
    def test_bookshelf(self):
        f = Furniture.bookshelf(0, 0)
        assert f.category == FurnitureCategory.BOOKSHELF
        assert f.depth == pytest.approx(0.3)

    def test_tv_unit(self):
        f = Furniture.tv_unit(0, 0)
        assert f.category == FurnitureCategory.TV_UNIT
        assert f.width == pytest.approx(1.8)


# ---------------------------------------------------------------------------
# Kitchen
# ---------------------------------------------------------------------------

class TestKitchen:
    def test_kitchen_counter(self):
        f = Furniture.kitchen_counter(0, 0)
        assert f.category == FurnitureCategory.KITCHEN_COUNTER
        assert f.depth == pytest.approx(0.6)

    def test_kitchen_island(self):
        f = Furniture.kitchen_island(0, 0)
        assert f.category == FurnitureCategory.ISLAND


# ---------------------------------------------------------------------------
# Bathroom
# ---------------------------------------------------------------------------

class TestBathroom:
    def test_bathtub(self):
        f = Furniture.bathtub(0, 0)
        assert f.category == FurnitureCategory.BATHTUB
        assert f.width == pytest.approx(1.7)

    def test_shower(self):
        f = Furniture.shower(0, 0)
        assert f.category == FurnitureCategory.SHOWER
        assert f.width == pytest.approx(0.9)
        assert f.depth == pytest.approx(0.9)

    def test_toilet(self):
        f = Furniture.toilet(0, 0)
        assert f.category == FurnitureCategory.TOILET
        assert f.width == pytest.approx(0.38)

    def test_sink(self):
        f = Furniture.sink(0, 0)
        assert f.category == FurnitureCategory.SINK
        assert f.width == pytest.approx(0.6)

    def test_washing_machine(self):
        f = Furniture.washing_machine(0, 0)
        assert f.category == FurnitureCategory.WASHING_MACHINE


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------

class TestRepr:
    def test_repr_with_label(self):
        f = Furniture.sofa(0, 0)
        assert "Sofa" in repr(f)

    def test_repr_without_label(self):
        f = Furniture.rectangular(0, 0, 1.0, 1.0)
        assert "Furniture" in repr(f)


# ---------------------------------------------------------------------------
# Level integration
# ---------------------------------------------------------------------------

class TestLevelIntegration:
    def _make_level(self):
        return Level(index=0, elevation=0.0, floor_height=3.0)

    def test_add_furniture(self):
        lvl = self._make_level()
        f = Furniture.sofa(0, 0)
        lvl2 = lvl.add_furniture(f)
        assert len(lvl2.furniture) == 1
        assert lvl2.furniture[0].id == f.id

    def test_add_multiple(self):
        lvl = self._make_level()
        lvl = lvl.add_furniture(Furniture.sofa(0, 0))
        lvl = lvl.add_furniture(Furniture.dining_table(3, 0))
        assert len(lvl.furniture) == 2

    def test_original_level_unchanged(self):
        lvl = self._make_level()
        lvl.add_furniture(Furniture.sofa(0, 0))
        assert len(lvl.furniture) == 0

    def test_get_element_by_id(self):
        lvl = self._make_level()
        f = Furniture.toilet(2, 3)
        lvl = lvl.add_furniture(f)
        found = lvl.get_element_by_id(f.id)
        assert found is not None
        assert found.id == f.id

    def test_remove_element(self):
        lvl = self._make_level()
        f1 = Furniture.sofa(0, 0)
        f2 = Furniture.bed_double(4, 0)
        lvl = lvl.add_furniture(f1).add_furniture(f2)
        lvl = lvl.remove_element(f1.id)
        assert len(lvl.furniture) == 1
        assert lvl.furniture[0].id == f2.id

    def test_default_furniture_empty(self):
        lvl = self._make_level()
        assert lvl.furniture == ()

    def test_furniture_in_category_filter(self):
        lvl = self._make_level()
        lvl = (
            lvl
            .add_furniture(Furniture.sofa(0, 0))
            .add_furniture(Furniture.bed_queen(4, 0))
            .add_furniture(Furniture.toilet(8, 0))
        )
        beds = [f for f in lvl.furniture if f.category == FurnitureCategory.BED]
        assert len(beds) == 1

    def test_total_furniture_area(self):
        lvl = self._make_level()
        lvl = (
            lvl
            .add_furniture(Furniture.rectangular(0, 0, 2.0, 1.0))  # 2 m²
            .add_furniture(Furniture.rectangular(3, 0, 1.0, 1.0))  # 1 m²
        )
        total = sum(f.footprint_area for f in lvl.furniture)
        assert total == pytest.approx(3.0)
