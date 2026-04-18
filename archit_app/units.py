"""
Unit conversion utilities for architectural dimensions.

All internal values in archit_app are stored in **meters** (float64).
This module provides helpers for converting to/from common architectural
units and for parsing human-readable dimension strings.

Usage::

    from archit_app.units import to_feet, from_inches, parse_dimension

    meters = from_inches(36)        # 0.9144
    ft = to_feet(3.048)             # 10.0
    m = parse_dimension("12'-6\"")  # 3.81
    m = parse_dimension("3800mm")   # 3.8
    m = parse_dimension("3.8m")     # 3.8
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Conversion constants (all relative to 1 metre)
# ---------------------------------------------------------------------------

_FEET_PER_METER     = 3.280839895013124
_INCHES_PER_METER   = 39.37007874015748
_MM_PER_METER       = 1_000.0
_CM_PER_METER       = 100.0

# ---------------------------------------------------------------------------
# To-metric helpers (meters → other)
# ---------------------------------------------------------------------------


def to_feet(meters: float) -> float:
    """Convert meters to decimal feet."""
    return meters * _FEET_PER_METER


def to_inches(meters: float) -> float:
    """Convert meters to inches."""
    return meters * _INCHES_PER_METER


def to_mm(meters: float) -> float:
    """Convert meters to millimeters."""
    return meters * _MM_PER_METER


def to_cm(meters: float) -> float:
    """Convert meters to centimeters."""
    return meters * _CM_PER_METER


# ---------------------------------------------------------------------------
# From-other helpers (other → meters)
# ---------------------------------------------------------------------------


def from_feet(feet: float) -> float:
    """Convert decimal feet to meters."""
    return feet / _FEET_PER_METER


def from_inches(inches: float) -> float:
    """Convert inches to meters."""
    return inches / _INCHES_PER_METER


def from_mm(mm: float) -> float:
    """Convert millimeters to meters."""
    return mm / _MM_PER_METER


def from_cm(cm: float) -> float:
    """Convert centimeters to meters."""
    return cm / _CM_PER_METER


# ---------------------------------------------------------------------------
# parse_dimension — human-readable string → meters
# ---------------------------------------------------------------------------

_FEET_INCHES_RE = re.compile(
    r"""
    ^\s*
    (?:
        (?P<ft>\d+(?:\.\d+)?)\s*['′]   # feet part: 12' or 12′
        (?:\s*-?\s*                     # optional separator (space, hyphen, or both)
            (?P<in>\d+(?:\.\d+)?)\s*["″]  # inches part: 6" or 6″
        )?
    |
        (?P<in_only>\d+(?:\.\d+)?)\s*["″]  # bare inches: 6"
    )
    \s*$
    """,
    re.VERBOSE,
)

_UNIT_RE = re.compile(
    r"""
    ^\s*
    (?P<value>-?\d+(?:\.\d+)?)
    \s*
    (?P<unit>mm|cm|m|ft|feet|foot|in|inch|inches|'|")?
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)


def parse_dimension(s: str) -> float:
    """Parse an architectural dimension string and return meters.

    Supported formats
    -----------------
    * ``"12'-6\""``  — feet and inches (US/imperial)
    * ``"12'6\""``   — feet and inches without separator
    * ``"6\""``      — bare inches
    * ``"3.8m"``     — metres (explicit unit)
    * ``"3800mm"``   — millimetres
    * ``"38cm"``     — centimetres
    * ``"3.5ft"``    — decimal feet
    * ``"3.5"``      — bare float interpreted as meters

    Parameters
    ----------
    s:
        Dimension string.

    Returns
    -------
    float
        Equivalent value in meters.

    Raises
    ------
    ValueError
        If the string cannot be parsed.
    """
    if not isinstance(s, str):
        raise TypeError(f"Expected str, got {type(s).__name__}")

    # --- Feet-and-inches pattern ---
    m = _FEET_INCHES_RE.match(s)
    if m:
        ft  = float(m.group("ft")  or 0)
        ins = float(m.group("in")  or m.group("in_only") or 0)
        return from_feet(ft) + from_inches(ins)

    # --- Numeric + optional unit ---
    m = _UNIT_RE.match(s)
    if m:
        value = float(m.group("value"))
        unit  = (m.group("unit") or "m").lower()
        if unit in ("mm",):
            return from_mm(value)
        if unit in ("cm",):
            return from_cm(value)
        if unit in ("m",):
            return value
        if unit in ("ft", "feet", "foot", "'"):
            return from_feet(value)
        if unit in ("in", "inch", "inches", '"'):
            return from_inches(value)

    raise ValueError(f"Cannot parse dimension string: {s!r}")
