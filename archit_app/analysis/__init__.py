"""
archit_app.analysis — Spatial and regulatory analysis tools.

Modules
-------
topology      Room adjacency graph (requires networkx)
circulation   Egress path finding (requires networkx)
area          Area program validation
compliance    Zoning compliance checker
daylighting   Solar orientation and window analysis
visibility    Isovist / viewshed computation
accessibility Door-width, corridor, ramp, turning-radius checks
roomfinder    Auto-detect room polygons from a wall set
"""

from archit_app.analysis.accessibility import (
    AccessibilityCheck,
    AccessibilityReport,
    check_accessibility,
)
from archit_app.analysis.area import (
    AreaTarget,
    ProgramAreaResult,
    area_by_program,
    area_by_program_per_level,
    area_report,
    total_gross_area,
    total_net_area,
)
from archit_app.analysis.compliance import (
    ComplianceCheck,
    ComplianceReport,
    check_compliance,
)
from archit_app.analysis.daylighting import (
    RoomDaylightResult,
    WindowSolarResult,
    daylight_report,
)
from archit_app.analysis.roomfinder import (
    find_rooms,
    rooms_from_walls,
)
from archit_app.analysis.visibility import (
    IsovistResult,
    compute_isovist,
    mutual_visibility,
    visible_area_m2,
)

# topology and circulation are imported lazily (require networkx)
# Use them directly:
#   from archit_app.analysis.topology import build_adjacency_graph
#   from archit_app.analysis.circulation import egress_report

__all__ = [
    # area
    "AreaTarget",
    "ProgramAreaResult",
    "area_by_program",
    "area_by_program_per_level",
    "area_report",
    "total_gross_area",
    "total_net_area",
    # compliance
    "ComplianceCheck",
    "ComplianceReport",
    "check_compliance",
    # daylighting
    "RoomDaylightResult",
    "WindowSolarResult",
    "daylight_report",
    # visibility
    "IsovistResult",
    "compute_isovist",
    "visible_area_m2",
    "mutual_visibility",
    # accessibility
    "AccessibilityCheck",
    "AccessibilityReport",
    "check_accessibility",
    # roomfinder
    "find_rooms",
    "rooms_from_walls",
]
