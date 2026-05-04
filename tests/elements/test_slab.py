import pytest

from archit_app import WORLD, Polygon2D, Slab, SlabType


def test_rectangular_factory():
    s = Slab.rectangular(x=0, y=0, width=10, depth=8, thickness=0.25, elevation=0.0)
    assert isinstance(s, Slab)
    assert s.slab_type == SlabType.FLOOR


def test_area():
    s = Slab.rectangular(x=0, y=0, width=5, depth=4, thickness=0.2, elevation=0)
    assert s.area == pytest.approx(20.0)
    assert s.gross_area == pytest.approx(20.0)


def test_area_with_hole():
    s = Slab.rectangular(x=0, y=0, width=10, depth=10, thickness=0.25, elevation=0)
    hole = Polygon2D.rectangle(4, 4, 2, 2, crs=WORLD)
    s2 = s.add_hole(hole)
    assert s2.area == pytest.approx(100.0 - 4.0)
    assert s2.gross_area == pytest.approx(100.0)


def test_perimeter():
    s = Slab.rectangular(x=0, y=0, width=5, depth=4, thickness=0.2, elevation=0)
    assert s.perimeter == pytest.approx(18.0)


def test_thickness_validation():
    with pytest.raises(ValueError):
        Slab.rectangular(x=0, y=0, width=5, depth=5, thickness=0.0, elevation=0)


def test_roof_type():
    s = Slab.rectangular(x=0, y=0, width=10, depth=8, thickness=0.3,
                          elevation=9.0, slab_type=SlabType.ROOF)
    assert s.slab_type == SlabType.ROOF
    assert s.elevation == pytest.approx(9.0)


def test_frozen():
    s = Slab.rectangular(x=0, y=0, width=5, depth=5, thickness=0.2, elevation=0)
    with pytest.raises(Exception):
        s.thickness = 0.5  # type: ignore


def test_bounding_box():
    s = Slab.rectangular(x=1, y=2, width=6, depth=4, thickness=0.2, elevation=0)
    bb = s.bounding_box()
    assert bb.width == pytest.approx(6.0)
    assert bb.height == pytest.approx(4.0)
