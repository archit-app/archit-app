"""Shared fixtures for protocol tests."""

from __future__ import annotations

import pytest

from archit_app import (
    WORLD,
    Building,
    BuildingMetadata,
    Level,
    Point2D,
    Polygon2D,
    Room,
)


@pytest.fixture
def tiny_building() -> Building:
    """Tiny one-level, two-room demo building."""
    kitchen_poly = Polygon2D(
        exterior=(
            Point2D(x=0, y=0, crs=WORLD),
            Point2D(x=4, y=0, crs=WORLD),
            Point2D(x=4, y=3, crs=WORLD),
            Point2D(x=0, y=3, crs=WORLD),
        )
    )
    bedroom_poly = Polygon2D(
        exterior=(
            Point2D(x=4, y=0, crs=WORLD),
            Point2D(x=8, y=0, crs=WORLD),
            Point2D(x=8, y=3, crs=WORLD),
            Point2D(x=4, y=3, crs=WORLD),
        )
    )
    rooms = (
        Room(boundary=kitchen_poly, name="Kitchen", program="kitchen", level_index=0),
        Room(boundary=bedroom_poly, name="Bedroom", program="bedroom", level_index=0),
    )
    level = Level(index=0, elevation=0.0, floor_height=3.0, name="Ground", rooms=rooms)
    return Building(metadata=BuildingMetadata(name="Demo House"), levels=(level,))
