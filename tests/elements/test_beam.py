import pytest

from archit_app import Beam, BeamSection


def test_straight_factory():
    b = Beam.straight(x1=0, y1=0, x2=5, y2=0, width=0.3, depth=0.5, elevation=3.0)
    assert isinstance(b, Beam)
    assert b.section == BeamSection.RECTANGULAR


def test_span_horizontal():
    b = Beam.straight(x1=0, y1=0, x2=6, y2=0, width=0.3, depth=0.5, elevation=3.0)
    assert b.span == pytest.approx(6.0, abs=0.01)


def test_span_diagonal():
    b = Beam.straight(x1=0, y1=0, x2=3, y2=4, width=0.3, depth=0.5, elevation=3.0)
    # 3-4-5 triangle: span ≈ 5
    assert b.span == pytest.approx(5.0, abs=0.1)


def test_soffit_elevation():
    b = Beam.straight(x1=0, y1=0, x2=5, y2=0, width=0.3, depth=0.5, elevation=3.5)
    assert b.soffit_elevation == pytest.approx(3.0)


def test_bounding_box_width():
    b = Beam.straight(x1=0, y1=0, x2=4, y2=0, width=0.4, depth=0.6, elevation=3.0)
    bb = b.bounding_box()
    assert bb.width == pytest.approx(4.0, abs=0.01)


def test_invalid_width():
    with pytest.raises(ValueError):
        Beam.straight(x1=0, y1=0, x2=5, y2=0, width=0, depth=0.5, elevation=3.0)


def test_invalid_depth():
    with pytest.raises(ValueError):
        Beam.straight(x1=0, y1=0, x2=5, y2=0, width=0.3, depth=-1, elevation=3.0)


def test_same_endpoints_raises():
    with pytest.raises(ValueError):
        Beam.straight(x1=1, y1=1, x2=1, y2=1, width=0.3, depth=0.5, elevation=3.0)


def test_frozen():
    b = Beam.straight(x1=0, y1=0, x2=5, y2=0, width=0.3, depth=0.5, elevation=3.0)
    with pytest.raises(Exception):
        b.depth = 1.0  # type: ignore
