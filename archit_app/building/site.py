"""
SiteContext — backward-compatible alias for Land.

``SiteContext`` and ``Land`` are now the same type.  Use ``Land`` for all new
code.  ``Land.minimal()`` replaces the old ``SiteContext(north_angle=…)``
pattern when no parcel boundary is available.

This module is kept for import compatibility only.
"""

from archit_app.building.land import Land

SiteContext = Land

__all__ = ["SiteContext"]
