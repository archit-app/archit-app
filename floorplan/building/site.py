"""
Site context for a building.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from floorplan.geometry.polygon import Polygon2D


class SiteContext(BaseModel):
    """
    Geographic and site context for a building.

    boundary:    lot boundary polygon (optional)
    north_angle: degrees clockwise from world +Y to geographic north
    address:     street address
    epsg_code:   EPSG code for geographic coordinate system (optional)
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    boundary: Polygon2D | None = None
    north_angle: float = 0.0   # degrees clockwise from +Y
    address: str = ""
    epsg_code: int | None = None
