"""Tests for Opening.archway() and Opening.pass_through() factories."""

import pytest

from archit_app import Opening, OpeningKind


class TestArchway:

    def test_kind(self):
        op = Opening.archway(x=0, y=0, width=1.2, height=2.4)
        assert op.kind == OpeningKind.ARCHWAY

    def test_dimensions(self):
        op = Opening.archway(x=0, y=0, width=1.5, height=2.5)
        assert op.width == pytest.approx(1.5)
        assert op.height == pytest.approx(2.5)

    def test_sill_height_zero(self):
        op = Opening.archway(x=0, y=0, width=1.2, height=2.4)
        assert op.sill_height == pytest.approx(0.0)

    def test_no_swing(self):
        op = Opening.archway(x=0, y=0, width=1.2, height=2.4)
        assert op.swing is None

    def test_geometry_is_rectangle(self):
        from archit_app.geometry.polygon import Polygon2D
        op = Opening.archway(x=1.0, y=2.0, width=1.2, height=2.4)
        assert isinstance(op.geometry, Polygon2D)

    def test_default_width_height(self):
        op = Opening.archway(x=0, y=0)
        assert op.width == pytest.approx(1.2)
        assert op.height == pytest.approx(2.4)

    def test_tags(self):
        op = Opening.archway(x=0, y=0).with_tag("finish", "stone")
        assert op.tags["finish"] == "stone"

    def test_unique_ids(self):
        a = Opening.archway(x=0, y=0)
        b = Opening.archway(x=0, y=0)
        assert a.id != b.id


class TestPassThrough:

    def test_kind(self):
        op = Opening.pass_through(x=0, y=0)
        assert op.kind == OpeningKind.PASS_THROUGH

    def test_default_sill_height(self):
        op = Opening.pass_through(x=0, y=0)
        assert op.sill_height == pytest.approx(0.85)

    def test_custom_sill_height(self):
        op = Opening.pass_through(x=0, y=0, sill_height=1.0)
        assert op.sill_height == pytest.approx(1.0)

    def test_dimensions(self):
        op = Opening.pass_through(x=0, y=0, width=0.8, height=1.1)
        assert op.width == pytest.approx(0.8)
        assert op.height == pytest.approx(1.1)

    def test_no_swing(self):
        assert Opening.pass_through(x=0, y=0).swing is None

    def test_geometry_present(self):
        from archit_app.geometry.polygon import Polygon2D
        op = Opening.pass_through(x=0, y=0)
        assert isinstance(op.geometry, Polygon2D)

    def test_unique_ids(self):
        a = Opening.pass_through(x=0, y=0)
        b = Opening.pass_through(x=0, y=0)
        assert a.id != b.id

    def test_default_width_height(self):
        op = Opening.pass_through(x=0, y=0)
        assert op.width == pytest.approx(0.9)
        assert op.height == pytest.approx(1.0)
