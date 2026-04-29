"""Shared base model for all Floorplan Agent Protocol messages."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ProtocolBase(BaseModel):
    """Strict, frozen base for every protocol model.

    - ``frozen=True``       — immutable after construction (matches archit-app's
                              broader pattern).
    - ``extra="forbid"``    — unknown keys raise ``ValidationError`` so agents
                              fail loudly on malformed messages.
    - ``populate_by_name``  — allow alias-based JSON parsing.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
    )
