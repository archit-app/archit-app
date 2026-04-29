"""Stable references to elements across protocol messages."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from archit_app.protocol._base import ProtocolBase

ElementKind = Literal[
    "wall",
    "room",
    "opening",
    "column",
    "beam",
    "slab",
    "ramp",
    "staircase",
    "elevator",
    "furniture",
    "level",
    "building",
    "land",
    "annotation",
    "dimension",
]


class ElementRef(ProtocolBase):
    """A versioned, level-scoped reference to a single building element.

    Equality and hashing are inherited from Pydantic's frozen model behavior,
    so refs can be used in sets/dicts to dedupe cross-message references.
    """

    id: str = Field(..., description="UUID string of the referenced element.")
    kind: ElementKind
    level_index: int | None = Field(
        default=None,
        description="Level index when applicable (None for building/land).",
    )
    revision: int | None = Field(
        default=None,
        description=(
            "Optional building-revision number this ref was captured against; "
            "lets readers detect stale references after later mutations."
        ),
    )
