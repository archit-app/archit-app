"""Tests for archit_app.elements.transform_utils."""

from __future__ import annotations

import pytest

from archit_app import (
    WORLD,
    Furniture,
    Polygon2D,
    Room,
    Wall,
    array_element,
    copy_element,
    mirror_element,
)
from archit_app.elements.annotation import TextAnnotation

# ---------------------------------------------------------------------------
# copy_element
# ---------------------------------------------------------------------------

class TestCopyElement:

    def test_returns_new_uuid(self):
        furn = Furniture.sofa(x=0, y=0)
        copy = copy_element(furn, dx=2.0, dy=0.0)
        assert copy.id != furn.id

    def test_translates_footprint(self):
        furn = Furniture.sofa(x=0, y=0)
        copy = copy_element(furn, dx=3.0, dy=1.0)
        orig_cx = furn.footprint.centroid.x
        copy_cx = copy.footprint.centroid.x
        assert copy_cx == pytest.approx(orig_cx + 3.0, abs=0.1)

    def test_original_unchanged(self):
        furn = Furniture.sofa(x=0, y=0)
        orig_cx = furn.footprint.centroid.x
        copy_element(furn, dx=5.0, dy=0.0)
        assert furn.footprint.centroid.x == pytest.approx(orig_cx)

    def test_copy_room(self):
        room = Room(
            boundary=Polygon2D.rectangle(0, 0, 4, 3, crs=WORLD),
            name="Hall",
            program="living",
        )
        copied = copy_element(room, dx=5.0, dy=0.0)
        assert copied.id != room.id
        assert copied.boundary.centroid.x == pytest.approx(room.boundary.centroid.x + 5.0, abs=0.1)

    def test_copy_annotation_position(self):
        ann = TextAnnotation.note(x=1.0, y=2.0, text="Hi", crs=WORLD)
        copied = copy_element(ann, dx=0.0, dy=3.0)
        assert copied.position.y == pytest.approx(2.0 + 3.0)

    def test_copy_wall(self):
        wall = Wall.straight(0, 0, 4, 0, thickness=0.2, height=3.0)
        copied = copy_element(wall, dx=0.0, dy=2.0)
        assert copied.id != wall.id


# ---------------------------------------------------------------------------
# mirror_element
# ---------------------------------------------------------------------------

class TestMirrorElement:

    def test_must_provide_exactly_one_axis(self):
        furn = Furniture.sofa(x=2, y=2)
        with pytest.raises(ValueError):
            mirror_element(furn)  # neither
        with pytest.raises(ValueError):
            mirror_element(furn, axis_x=0.0, axis_y=0.0)  # both

    def test_mirror_x_axis(self):
        furn = Furniture.sofa(x=2, y=0)
        mirrored = mirror_element(furn, axis_x=0.0)
        # centroid.x should be negated
        assert mirrored.footprint.centroid.x == pytest.approx(-furn.footprint.centroid.x, abs=0.2)

    def test_mirror_y_axis(self):
        furn = Furniture.sofa(x=0, y=3)
        mirrored = mirror_element(furn, axis_y=0.0)
        assert mirrored.footprint.centroid.y == pytest.approx(-furn.footprint.centroid.y, abs=0.2)

    def test_mirror_returns_new_uuid(self):
        furn = Furniture.sofa(x=2, y=2)
        mirrored = mirror_element(furn, axis_x=0.0)
        assert mirrored.id != furn.id

    def test_mirror_annotation_position(self):
        ann = TextAnnotation.note(x=4.0, y=2.0, text="X", crs=WORLD)
        mirrored = mirror_element(ann, axis_x=0.0)
        assert mirrored.position.x == pytest.approx(-4.0)

    def test_mirror_room(self):
        room = Room(
            boundary=Polygon2D.rectangle(1, 0, 4, 3, crs=WORLD),
            name="Hall",
            program="living",
        )
        mirrored = mirror_element(room, axis_x=0.0)
        # Original centroid.x ≈ 3; mirrored should be ≈ -3
        assert mirrored.boundary.centroid.x < 0


# ---------------------------------------------------------------------------
# array_element
# ---------------------------------------------------------------------------

class TestArrayElement:

    def test_count_equals_length(self):
        furn = Furniture.desk(x=0, y=0)
        row = array_element(furn, count=5, dx=1.5, dy=0.0)
        assert len(row) == 5

    def test_all_have_unique_uuids(self):
        furn = Furniture.desk(x=0, y=0)
        row = array_element(furn, count=4, dx=1.5, dy=0.0)
        ids = {e.id for e in row}
        assert len(ids) == 4

    def test_first_copy_at_original_position(self):
        furn = Furniture.desk(x=2, y=1)
        row = array_element(furn, count=3, dx=1.5, dy=0.0)
        assert row[0].footprint.centroid.x == pytest.approx(
            furn.footprint.centroid.x, abs=0.1
        )

    def test_spacing_correct(self):
        furn = Furniture.desk(x=0, y=0)
        row = array_element(furn, count=3, dx=2.0, dy=0.0)
        cx0 = row[0].footprint.centroid.x
        cx1 = row[1].footprint.centroid.x
        cx2 = row[2].footprint.centroid.x
        assert cx1 - cx0 == pytest.approx(2.0, abs=0.05)
        assert cx2 - cx0 == pytest.approx(4.0, abs=0.05)

    def test_diagonal_array(self):
        furn = Furniture.sofa(x=0, y=0)
        row = array_element(furn, count=3, dx=1.0, dy=1.0)
        assert row[2].footprint.centroid.y == pytest.approx(
            row[0].footprint.centroid.y + 2.0, abs=0.1
        )

    def test_count_zero_raises(self):
        furn = Furniture.sofa(x=0, y=0)
        with pytest.raises(ValueError):
            array_element(furn, count=0, dx=1.0, dy=0.0)
