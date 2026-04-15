import pytest

from archit_app import Wall, WallType, miter_join, butt_join, join_walls
from archit_app.geometry.polygon import Polygon2D


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _area(wall: Wall) -> float:
    assert isinstance(wall.geometry, Polygon2D)
    return wall.geometry.area


# ---------------------------------------------------------------------------
# miter_join tests
# ---------------------------------------------------------------------------

class TestMiterJoin:
    def test_returns_two_walls(self):
        # L-corner: wall A along X, wall B along Y, sharing (5, 0)
        a = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        b = Wall.straight(5, 0, 5, 5, thickness=0.2, height=3.0)
        result = miter_join(a, b)
        assert result is not None
        wa, wb = result
        assert isinstance(wa, Wall)
        assert isinstance(wb, Wall)

    def test_trimmed_walls_are_smaller(self):
        a = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        b = Wall.straight(5, 0, 5, 5, thickness=0.2, height=3.0)
        result = miter_join(a, b)
        assert result is not None
        wa, wb = result
        assert _area(wa) < _area(a) + 1e-6
        assert _area(wb) < _area(b) + 1e-6

    def test_no_shared_endpoint_returns_none(self):
        a = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        b = Wall.straight(10, 0, 15, 0, thickness=0.2, height=3.0)
        assert miter_join(a, b) is None

    def test_preserves_wall_metadata(self):
        a = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0,
                          wall_type=WallType.EXTERIOR)
        b = Wall.straight(5, 0, 5, 4, thickness=0.3, height=3.0)
        result = miter_join(a, b)
        assert result is not None
        wa, wb = result
        assert wa.wall_type == WallType.EXTERIOR
        assert wa.thickness == pytest.approx(0.2)
        assert wb.thickness == pytest.approx(0.3)

    def test_right_angle_join_start_of_b(self):
        # Shared at the start of B
        a = Wall.straight(0, 0, 0, 5, thickness=0.2, height=3.0)
        b = Wall.straight(0, 5, 5, 5, thickness=0.2, height=3.0)
        result = miter_join(a, b)
        assert result is not None

    def test_symmetric_90_degree(self):
        # Both walls same thickness at 90° — trimmed areas should be equal
        a = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        b = Wall.straight(5, 0, 5, 5, thickness=0.2, height=3.0)
        result = miter_join(a, b)
        assert result is not None
        wa, wb = result
        assert _area(wa) == pytest.approx(_area(wb), rel=0.05)


# ---------------------------------------------------------------------------
# butt_join tests
# ---------------------------------------------------------------------------

class TestButtJoin:
    def test_returns_two_walls(self):
        a = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        b = Wall.straight(5, 0, 5, 4, thickness=0.2, height=3.0)
        result = butt_join(a, b)
        assert result is not None
        wa, wb = result

    def test_wall_a_unchanged(self):
        a = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        b = Wall.straight(5, 0, 5, 4, thickness=0.2, height=3.0)
        result = butt_join(a, b)
        assert result is not None
        wa, _ = result
        # wall_a should be identical (same geometry)
        assert wa.id == a.id
        assert _area(wa) == pytest.approx(_area(a))

    def test_wall_b_trimmed(self):
        a = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        b = Wall.straight(5, 0, 5, 4, thickness=0.2, height=3.0)
        result = butt_join(a, b)
        assert result is not None
        _, wb = result
        assert _area(wb) < _area(b) + 1e-6

    def test_no_shared_returns_none(self):
        a = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        b = Wall.straight(0, 10, 5, 10, thickness=0.2, height=3.0)
        assert butt_join(a, b) is None


# ---------------------------------------------------------------------------
# join_walls tests
# ---------------------------------------------------------------------------

class TestJoinWalls:
    def test_two_walls_joined(self):
        a = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        b = Wall.straight(5, 0, 5, 5, thickness=0.2, height=3.0)
        result = join_walls([a, b])
        assert len(result) == 2
        # Both should be trimmed
        assert _area(result[0]) <= _area(a) + 1e-6
        assert _area(result[1]) <= _area(b) + 1e-6

    def test_four_walls_room_corner(self):
        # Simple 5×4 room — four walls meeting at four corners
        walls = [
            Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0),  # bottom
            Wall.straight(5, 0, 5, 4, thickness=0.2, height=3.0),  # right
            Wall.straight(5, 4, 0, 4, thickness=0.2, height=3.0),  # top
            Wall.straight(0, 4, 0, 0, thickness=0.2, height=3.0),  # left
        ]
        result = join_walls(walls)
        assert len(result) == 4

    def test_unrelated_walls_unchanged(self):
        a = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        b = Wall.straight(10, 10, 15, 10, thickness=0.2, height=3.0)
        result = join_walls([a, b])
        assert _area(result[0]) == pytest.approx(_area(a))
        assert _area(result[1]) == pytest.approx(_area(b))
