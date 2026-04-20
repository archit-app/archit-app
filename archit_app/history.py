"""
Undo / redo history stack for Building objects.

Because Building (and every object it contains) is immutable, history is
trivially implemented as an immutable tuple of snapshots with a cursor.

Usage::

    history = History.start(building)
    history = history.push(building.add_level(new_level))

    building, history = history.undo()
    building, history = history.redo()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from archit_app.building.building import Building


class HistoryError(Exception):
    """Raised when undo/redo is requested but not possible."""


class History(BaseModel):
    """
    Immutable undo/redo stack of Building snapshots.

    The stack holds up to ``max_snapshots`` entries. When the limit is
    reached, the oldest snapshot is silently dropped.

    ``cursor`` is the index of the *current* snapshot in ``snapshots``.
    Snapshots after ``cursor`` are the redo branch (they exist only after
    one or more undo() calls).
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    snapshots: tuple["Building", ...]
    cursor: int
    max_snapshots: int = 100

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def start(cls, building: "Building", max_snapshots: int = 100) -> "History":
        """Create a new history with ``building`` as the only snapshot."""
        return cls(snapshots=(building,), cursor=0, max_snapshots=max_snapshots)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current(self) -> "Building":
        """The Building at the current cursor position."""
        return self.snapshots[self.cursor]  # type: ignore[index]

    @property
    def can_undo(self) -> bool:
        return self.cursor > 0

    @property
    def can_redo(self) -> bool:
        return self.cursor < len(self.snapshots) - 1

    # ------------------------------------------------------------------
    # Mutations (return new History)
    # ------------------------------------------------------------------

    def push(self, building: "Building") -> "History":
        """
        Record a new state. Any redo branch is discarded.

        If ``max_snapshots`` would be exceeded the oldest snapshot is dropped
        and the cursor adjusted accordingly.
        """
        # Truncate redo branch
        kept = self.snapshots[: self.cursor + 1]
        new_snaps = (*kept, building)

        # Enforce cap
        if len(new_snaps) > self.max_snapshots:
            new_snaps = new_snaps[len(new_snaps) - self.max_snapshots:]

        return self.model_copy(update={
            "snapshots": new_snaps,
            "cursor": len(new_snaps) - 1,
        })

    def undo(self) -> tuple["Building", "History"]:
        """
        Move one step back in history.

        Returns ``(building, new_history)``.
        Raises ``HistoryError`` if already at the beginning.
        """
        if not self.can_undo:
            raise HistoryError("Nothing to undo.")
        new_cursor = self.cursor - 1
        new_history = self.model_copy(update={"cursor": new_cursor})
        return new_history.current, new_history

    def redo(self) -> tuple["Building", "History"]:
        """
        Move one step forward in history.

        Returns ``(building, new_history)``.
        Raises ``HistoryError`` if already at the latest snapshot.
        """
        if not self.can_redo:
            raise HistoryError("Nothing to redo.")
        new_cursor = self.cursor + 1
        new_history = self.model_copy(update={"cursor": new_cursor})
        return new_history.current, new_history

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"History(snapshots={len(self.snapshots)}, "
            f"cursor={self.cursor}, "
            f"can_undo={self.can_undo}, can_redo={self.can_redo})"
        )
