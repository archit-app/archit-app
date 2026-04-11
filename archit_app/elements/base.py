"""
Base class for all architectural elements.

All elements are immutable Pydantic models. To "modify" an element,
produce a new one via model_copy(update={...}).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from archit_app.geometry.crs import CoordinateSystem, WORLD
from archit_app.geometry.transform import Transform2D


class Element(BaseModel):
    """
    Base for every architectural element (Wall, Room, Opening, Column, etc.).

    Frozen: all attributes are read-only after construction.
    Mutation returns a new object via model_copy(update={...}).
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    id: UUID = Field(default_factory=uuid4)
    tags: dict[str, Any] = Field(default_factory=dict)
    transform: Transform2D = Field(default_factory=Transform2D.identity)
    layer: str = "default"
    crs: CoordinateSystem = WORLD

    # ------------------------------------------------------------------
    # Mutation helpers (return new instances)
    # ------------------------------------------------------------------

    def with_tag(self, key: str, value: Any) -> "Element":
        """Return a copy with an additional or updated tag."""
        return self.model_copy(update={"tags": {**self.tags, key: value}})

    def without_tag(self, key: str) -> "Element":
        """Return a copy with the specified tag removed."""
        return self.model_copy(update={"tags": {k: v for k, v in self.tags.items() if k != key}})

    def with_transform(self, t: Transform2D) -> "Element":
        """Return a copy with an additional transform composed on top."""
        return self.model_copy(update={"transform": self.transform @ t})

    def on_layer(self, layer: str) -> "Element":
        """Return a copy assigned to a different layer."""
        return self.model_copy(update={"layer": layer})

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id!s:.8}...)"
