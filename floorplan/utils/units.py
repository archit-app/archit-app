"""
Unit conversion utilities.

All internal values are stored in meters. Use these helpers at import/export
boundaries only — never inside core geometry or element code.
"""

from floorplan.geometry.crs import LengthUnit


def to_meters(value: float, unit: LengthUnit, pixels_per_meter: float | None = None) -> float:
    """Convert a value from the given unit to meters."""
    return unit.to_meters(value, pixels_per_meter)


def from_meters(value: float, unit: LengthUnit, pixels_per_meter: float | None = None) -> float:
    """Convert a value in meters to the given unit."""
    return unit.from_meters(value, pixels_per_meter)


def convert(value: float, from_unit: LengthUnit, to_unit: LengthUnit,
            pixels_per_meter: float | None = None) -> float:
    """Convert a value from one unit to another."""
    meters = to_meters(value, from_unit, pixels_per_meter)
    return from_meters(meters, to_unit, pixels_per_meter)
