"""
Layer model for grouping architectural elements by visual/organisational category.

Elements already carry a ``layer: str`` name field.  This module adds a
:class:`Layer` object that defines properties (colour, visibility, lock state)
for each named layer, and integrates those properties into the :class:`Building`
model.

Usage::

    from archit_app.building.layer import Layer
    from archit_app import Building

    b = (
        Building()
        .add_layer(Layer("Structure",  color_hex="#FF0000"))
        .add_layer(Layer("Furniture",  color_hex="#FFA500", visible=False))
    )

    # Renderers honour visibility: hidden layers are skipped automatically.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# Layer model
# ---------------------------------------------------------------------------


class Layer(BaseModel):
    """A named drawing layer with display properties.

    Parameters
    ----------
    name:
        Unique layer identifier (matches the ``layer`` field on elements).
    color_hex:
        Display colour as a CSS hex string (e.g. ``"#2E86AB"``).
        Defaults to mid-grey ``"#808080"``.
    visible:
        When ``False`` the layer is hidden; renderers should skip its elements.
    locked:
        When ``True`` the layer's elements should not be selectable/editable
        by interactive tools (no effect on rendering).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    color_hex: str = "#808080"
    visible: bool = True
    locked: bool = False

    @field_validator("color_hex")
    @classmethod
    def _validate_hex(cls, v: str) -> str:
        if not re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", v):
            raise ValueError(
                f"color_hex must be a 3- or 6-digit CSS hex colour (e.g. '#2E86AB'), got {v!r}"
            )
        return v.upper()

    def with_color(self, color_hex: str) -> "Layer":
        return self.model_copy(update={"color_hex": color_hex})

    def show(self) -> "Layer":
        return self.model_copy(update={"visible": True})

    def hide(self) -> "Layer":
        return self.model_copy(update={"visible": False})

    def lock(self) -> "Layer":
        return self.model_copy(update={"locked": True})

    def unlock(self) -> "Layer":
        return self.model_copy(update={"locked": False})

    def __repr__(self) -> str:  # pragma: no cover
        flags = []
        if not self.visible:
            flags.append("hidden")
        if self.locked:
            flags.append("locked")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        return f"Layer({self.name!r}, {self.color_hex}{flag_str})"
