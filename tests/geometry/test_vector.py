"""Tests for Vector2D and Vector3D."""

import math

import pytest

from archit_app.geometry.crs import SCREEN, WORLD
from archit_app.geometry.vector import Vector2D, Vector3D

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def v2(x, y, crs=WORLD):
    return Vector2D(x=x, y=y, crs=crs)


def v3(x, y, z, crs=WORLD):
    return Vector3D(x=x, y=z, z=z, crs=crs)


# ===========================================================================
# Vector2D
# ===========================================================================

class TestVector2D:

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    def test_magnitude_axis(self):
        assert v2(3, 0).magnitude == pytest.approx(3.0)
        assert v2(0, 4).magnitude == pytest.approx(4.0)

    def test_magnitude_diagonal(self):
        assert v2(3, 4).magnitude == pytest.approx(5.0)

    def test_magnitude_sq(self):
        assert v2(3, 4).magnitude_sq == pytest.approx(25.0)

    def test_normalized_unit(self):
        n = v2(3, 4).normalized()
        assert n.magnitude == pytest.approx(1.0)
        assert n.x == pytest.approx(0.6)
        assert n.y == pytest.approx(0.8)

    def test_normalized_already_unit(self):
        n = v2(1, 0).normalized()
        assert n.x == pytest.approx(1.0)
        assert n.y == pytest.approx(0.0)

    def test_normalized_zero_raises(self):
        with pytest.raises(ValueError, match="zero"):
            v2(0, 0).normalized()

    def test_dot_product(self):
        assert v2(1, 0).dot(v2(0, 1)) == pytest.approx(0.0)
        assert v2(3, 4).dot(v2(3, 4)) == pytest.approx(25.0)
        assert v2(1, 0).dot(v2(-1, 0)) == pytest.approx(-1.0)

    def test_cross_product_orthogonal(self):
        # CCW +X × +Y = +1
        assert v2(1, 0).cross(v2(0, 1)) == pytest.approx(1.0)
        # CW opposite
        assert v2(0, 1).cross(v2(1, 0)) == pytest.approx(-1.0)

    def test_cross_parallel_is_zero(self):
        assert v2(1, 0).cross(v2(2, 0)) == pytest.approx(0.0)

    def test_rotated_90_ccw(self):
        r = v2(1, 0).rotated(math.pi / 2)
        assert r.x == pytest.approx(0.0, abs=1e-9)
        assert r.y == pytest.approx(1.0)

    def test_rotated_180(self):
        r = v2(1, 0).rotated(math.pi)
        assert r.x == pytest.approx(-1.0)
        assert r.y == pytest.approx(0.0, abs=1e-9)

    def test_rotated_360_identity(self):
        orig = v2(3, 7)
        r = orig.rotated(2 * math.pi)
        assert r.x == pytest.approx(orig.x)
        assert r.y == pytest.approx(orig.y)

    def test_perpendicular(self):
        # CCW perpendicular of +X is +Y
        p = v2(1, 0).perpendicular()
        assert p.x == pytest.approx(0.0, abs=1e-9)
        assert p.y == pytest.approx(1.0)

    def test_perpendicular_orthogonal(self):
        v = v2(3, 4)
        p = v.perpendicular()
        assert v.dot(p) == pytest.approx(0.0, abs=1e-9)

    def test_angle_east(self):
        assert v2(1, 0).angle() == pytest.approx(0.0)

    def test_angle_north(self):
        assert v2(0, 1).angle() == pytest.approx(math.pi / 2)

    def test_angle_west(self):
        a = v2(-1, 0).angle()
        assert abs(a) == pytest.approx(math.pi)

    def test_as_array(self):
        arr = v2(3, 4).as_array()
        assert arr.shape == (2,)
        assert arr[0] == pytest.approx(3.0)
        assert arr[1] == pytest.approx(4.0)

    # ------------------------------------------------------------------
    # Arithmetic
    # ------------------------------------------------------------------

    def test_add(self):
        result = v2(1, 2) + v2(3, 4)
        assert result.x == pytest.approx(4.0)
        assert result.y == pytest.approx(6.0)

    def test_sub(self):
        result = v2(5, 3) - v2(2, 1)
        assert result.x == pytest.approx(3.0)
        assert result.y == pytest.approx(2.0)

    def test_mul_scalar(self):
        result = v2(1, 2) * 3
        assert result.x == pytest.approx(3.0)
        assert result.y == pytest.approx(6.0)

    def test_rmul_scalar(self):
        result = 3 * v2(1, 2)
        assert result.x == pytest.approx(3.0)
        assert result.y == pytest.approx(6.0)

    def test_div_scalar(self):
        result = v2(6, 4) / 2
        assert result.x == pytest.approx(3.0)
        assert result.y == pytest.approx(2.0)

    def test_div_zero_raises(self):
        with pytest.raises(ZeroDivisionError):
            v2(1, 2) / 0

    def test_neg(self):
        result = -v2(3, -4)
        assert result.x == pytest.approx(-3.0)
        assert result.y == pytest.approx(4.0)

    def test_crs_preserved_on_arithmetic(self):
        result = v2(1, 0) + v2(2, 0)
        assert result.crs == WORLD

    def test_crs_mismatch_add_raises(self):
        with pytest.raises(Exception):
            v2(1, 0, WORLD) + v2(1, 0, SCREEN)

    def test_crs_mismatch_dot_raises(self):
        with pytest.raises(Exception):
            v2(1, 0, WORLD).dot(v2(1, 0, SCREEN))

    def test_crs_mismatch_cross_raises(self):
        with pytest.raises(Exception):
            v2(1, 0, WORLD).cross(v2(0, 1, SCREEN))

    def test_repr(self):
        r = repr(v2(1, 2))
        assert "Vector2D" in r
        assert "1" in r

    def test_frozen(self):
        with pytest.raises(Exception):
            v2(1, 2).x = 99  # type: ignore


# ===========================================================================
# Vector3D
# ===========================================================================

class TestVector3D:

    def _v(self, x, y, z):
        return Vector3D(x=x, y=y, z=z, crs=WORLD)

    def test_magnitude(self):
        assert self._v(1, 2, 2).magnitude == pytest.approx(3.0)

    def test_normalized(self):
        n = self._v(1, 2, 2).normalized()
        assert n.magnitude == pytest.approx(1.0)

    def test_normalized_zero_raises(self):
        with pytest.raises(ValueError):
            self._v(0, 0, 0).normalized()

    def test_dot(self):
        assert self._v(1, 0, 0).dot(self._v(0, 1, 0)) == pytest.approx(0.0)
        assert self._v(1, 2, 3).dot(self._v(1, 2, 3)) == pytest.approx(14.0)

    def test_cross_orthogonal(self):
        # +X × +Y = +Z
        c = self._v(1, 0, 0).cross(self._v(0, 1, 0))
        assert c.x == pytest.approx(0.0, abs=1e-9)
        assert c.y == pytest.approx(0.0, abs=1e-9)
        assert c.z == pytest.approx(1.0)

    def test_cross_anticommutative(self):
        a = self._v(1, 0, 0)
        b = self._v(0, 1, 0)
        ab = a.cross(b)
        ba = b.cross(a)
        assert ab.x == pytest.approx(-ba.x)
        assert ab.y == pytest.approx(-ba.y)
        assert ab.z == pytest.approx(-ba.z)

    def test_add(self):
        r = self._v(1, 2, 3) + self._v(4, 5, 6)
        assert r.x == pytest.approx(5.0)
        assert r.y == pytest.approx(7.0)
        assert r.z == pytest.approx(9.0)

    def test_sub(self):
        r = self._v(5, 5, 5) - self._v(1, 2, 3)
        assert r.x == pytest.approx(4.0)
        assert r.y == pytest.approx(3.0)
        assert r.z == pytest.approx(2.0)

    def test_mul_scalar(self):
        r = self._v(1, 2, 3) * 2
        assert r.z == pytest.approx(6.0)

    def test_rmul_scalar(self):
        r = 2 * self._v(1, 2, 3)
        assert r.z == pytest.approx(6.0)

    def test_neg(self):
        r = -self._v(1, -2, 3)
        assert r.x == pytest.approx(-1.0)
        assert r.y == pytest.approx(2.0)
        assert r.z == pytest.approx(-3.0)

    def test_as_array(self):
        arr = self._v(1, 2, 3).as_array()
        assert arr.shape == (3,)

    def test_crs_mismatch_add_raises(self):
        with pytest.raises(Exception):
            Vector3D(x=1, y=0, z=0, crs=WORLD) + Vector3D(x=0, y=1, z=0, crs=SCREEN)

    def test_repr(self):
        assert "Vector3D" in repr(self._v(1, 2, 3))
