import math

import numpy as np

from archit_app import Transform2D


def test_identity():
    t = Transform2D.identity()
    assert t.is_identity()


def test_identity_apply():
    t = Transform2D.identity()
    pts = np.array([[1.0, 2.0], [3.0, 4.0]])
    result = t.apply_to_array(pts)
    np.testing.assert_allclose(result, pts)


def test_translate():
    t = Transform2D.translate(3.0, -2.0)
    pts = np.array([[0.0, 0.0], [1.0, 1.0]])
    result = t.apply_to_array(pts)
    np.testing.assert_allclose(result, [[3.0, -2.0], [4.0, -1.0]])


def test_scale():
    t = Transform2D.scale(2.0, 3.0)
    pts = np.array([[1.0, 1.0]])
    result = t.apply_to_array(pts)
    np.testing.assert_allclose(result, [[2.0, 3.0]])


def test_rotate_90():
    t = Transform2D.rotate(math.pi / 2)
    pts = np.array([[1.0, 0.0]])
    result = t.apply_to_array(pts)
    np.testing.assert_allclose(result, [[0.0, 1.0]], atol=1e-10)


def test_reflect_y():
    t = Transform2D.reflect_y()
    pts = np.array([[1.0, 2.0]])
    result = t.apply_to_array(pts)
    np.testing.assert_allclose(result, [[1.0, -2.0]])


def test_compose_matmul():
    t1 = Transform2D.translate(1.0, 0.0)
    t2 = Transform2D.translate(0.0, 2.0)
    combined = t1 @ t2
    pts = np.array([[0.0, 0.0]])
    result = combined.apply_to_array(pts)
    np.testing.assert_allclose(result, [[1.0, 2.0]])


def test_inverse_round_trip():
    t = Transform2D.translate(5.0, -3.0) @ Transform2D.rotate(0.7)
    t_inv = t.inverse()
    composed = t @ t_inv
    assert composed.is_identity(tol=1e-9)


def test_equality():
    t1 = Transform2D.translate(1.0, 2.0)
    t2 = Transform2D.translate(1.0, 2.0)
    t3 = Transform2D.translate(1.0, 3.0)
    assert t1 == t2
    assert t1 != t3


def test_from_matrix():
    m = np.eye(3)
    t = Transform2D.from_matrix(m)
    assert t.is_identity()
