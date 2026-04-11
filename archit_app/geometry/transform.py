"""
Affine 2D transforms using 3×3 homogeneous matrices.

All Transform2D objects are immutable. Compose with @ to create new transforms.

Convention:
  - Column vectors: apply as  p' = M @ [x, y, 1]^T
  - Compose left-to-right: (T1 @ T2) applies T2 first, then T1
"""

from __future__ import annotations

import math
from typing import Annotated, Any

import numpy as np
from pydantic import BaseModel, ConfigDict


class Transform2D:
    """
    Immutable 3×3 homogeneous affine transform for 2D space.

    A lightweight wrapper around a numpy array. Not a Pydantic model — this
    avoids Pydantic's field validation complexity for numpy arrays. Serialization
    is done via explicit to_list() / from_list() methods.
    """

    __slots__ = ("_m",)

    def __init__(self, matrix: np.ndarray | None = None) -> None:
        if matrix is None:
            matrix = np.eye(3, dtype=np.float64)
        m = np.asarray(matrix, dtype=np.float64)
        if m.shape != (3, 3):
            raise ValueError(f"Transform2D matrix must be 3×3, got shape {m.shape}.")
        # Store as immutable view
        m.flags.writeable = False
        object.__setattr__(self, "_m", m)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("Transform2D is immutable.")

    @property
    def matrix(self) -> np.ndarray:
        return self._m

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def identity(cls) -> "Transform2D":
        return cls(np.eye(3, dtype=np.float64))

    @classmethod
    def translate(cls, dx: float, dy: float) -> "Transform2D":
        m = np.eye(3, dtype=np.float64)
        m[0, 2] = dx
        m[1, 2] = dy
        return cls(m)

    @classmethod
    def scale(cls, sx: float, sy: float) -> "Transform2D":
        return cls(np.diag([sx, sy, 1.0]))

    @classmethod
    def rotate(cls, angle_rad: float) -> "Transform2D":
        c, s = math.cos(angle_rad), math.sin(angle_rad)
        m = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
        return cls(m)

    @classmethod
    def reflect_y(cls) -> "Transform2D":
        """Flip Y axis — the core of screen↔world conversion."""
        return cls.scale(1.0, -1.0)

    @classmethod
    def from_matrix(cls, m: np.ndarray) -> "Transform2D":
        return cls(m)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_list(self) -> list[list[float]]:
        return self._m.tolist()

    @classmethod
    def from_list(cls, data: list[list[float]]) -> "Transform2D":
        return cls(np.array(data, dtype=np.float64))

    # Pydantic v2 support
    @classmethod
    def __get_validators__(cls):
        yield cls._validate

    @classmethod
    def _validate(cls, v: Any) -> "Transform2D":
        if isinstance(v, cls):
            return v
        if isinstance(v, list):
            return cls.from_list(v)
        if isinstance(v, np.ndarray):
            return cls(v)
        raise ValueError(f"Cannot convert {type(v)} to Transform2D")

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> Any:
        from pydantic_core import core_schema

        def validate(v: Any) -> "Transform2D":
            return cls._validate(v)

        def serialize(v: "Transform2D") -> list[list[float]]:
            return v.to_list()

        return core_schema.no_info_plain_validator_function(
            validate,
            serialization=core_schema.plain_serializer_function_ser_schema(serialize),
        )

    # ------------------------------------------------------------------
    # Composition and application
    # ------------------------------------------------------------------

    def __matmul__(self, other: "Transform2D") -> "Transform2D":
        """Compose: self @ other applies other first, then self."""
        return Transform2D(self._m @ other._m)

    def apply_to_array(self, pts: np.ndarray) -> np.ndarray:
        """
        Apply transform to an (N, 2) array of points.
        Returns an (N, 2) array.
        """
        pts = np.asarray(pts, dtype=np.float64)
        single = pts.ndim == 1
        if single:
            pts = pts.reshape(1, 2)
        ones = np.ones((pts.shape[0], 1), dtype=np.float64)
        homogeneous = np.hstack([pts, ones])  # (N, 3)
        transformed = (self._m @ homogeneous.T).T  # (N, 3)
        result = transformed[:, :2] / transformed[:, 2:3]
        return result[0] if single else result

    def inverse(self) -> "Transform2D":
        return Transform2D(np.linalg.inv(self._m))

    def is_identity(self, tol: float = 1e-9) -> bool:
        return bool(np.allclose(self._m, np.eye(3), atol=tol))

    # ------------------------------------------------------------------
    # Equality and hashing
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Transform2D):
            return NotImplemented
        return bool(np.allclose(self._m, other._m))

    def __hash__(self) -> int:
        return hash(self._m.tobytes())

    def __repr__(self) -> str:
        m = self._m
        return (
            f"Transform2D([\n"
            f"  [{m[0,0]:.4f}, {m[0,1]:.4f}, {m[0,2]:.4f}],\n"
            f"  [{m[1,0]:.4f}, {m[1,1]:.4f}, {m[1,2]:.4f}],\n"
            f"  [{m[2,0]:.4f}, {m[2,1]:.4f}, {m[2,2]:.4f}]\n"
            f"])"
        )
