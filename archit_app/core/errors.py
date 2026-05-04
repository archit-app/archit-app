"""
Typed error hierarchy for archit-app primitive failures.

Tools (e.g. archit-studio's tool layer) catch :class:`ArchitError` and emit
structured JSON payloads ``{code, message, element_id, hint}`` instead of
flat strings, giving downstream LLM agents a stable signal for what kind of
failure occurred so they can choose the right recovery action.

Usage::

    from archit_app import ArchitError, OverlapError

    raise OverlapError(
        "Room 'kitchen' overlaps with 'living'.",
        element_id="room_kitchen",
        hint="Reduce the kitchen footprint or move it.",
    )
"""

from __future__ import annotations


class ArchitError(Exception):
    """
    Base class for all typed archit-app errors.

    Attributes
    ----------
    message : str
        Human-readable description of what went wrong.
    code : str
        Stable machine-readable identifier for the error category. Subclasses
        provide a sensible default; pass an explicit ``code`` to override.
    element_id : str | None
        Optional id of the offending element (room, wall, opening, etc.).
    hint : str | None
        Optional short suggestion for how to recover.
    """

    #: Default code; subclasses override.
    default_code: str = "archit_error"

    def __init__(
        self,
        message: str,
        code: str | None = None,
        element_id: str | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code if code is not None else self.default_code
        self.element_id = element_id
        self.hint = hint

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class OverlapError(ArchitError):
    """Raised when two geometric elements overlap when they must not."""

    default_code = "overlap"


class OutOfBoundsError(ArchitError):
    """Raised when an element falls outside its container's allowed region."""

    default_code = "out_of_bounds"


class ElementNotFoundError(ArchitError):
    """Raised when a referenced element id does not resolve."""

    default_code = "element_not_found"


class GeometryError(ArchitError):
    """Raised when geometric input is malformed or numerically degenerate."""

    default_code = "geometry_error"


class SessionError(ArchitError):
    """Raised when session/state preconditions are violated."""

    default_code = "session_error"


__all__ = [
    "ArchitError",
    "OverlapError",
    "OutOfBoundsError",
    "ElementNotFoundError",
    "GeometryError",
    "SessionError",
]
