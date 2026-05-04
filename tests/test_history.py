"""Tests for History — immutable undo/redo stack."""

import pytest

from archit_app import Building, History, Level
from archit_app.history import HistoryError


def _building(name: str = "") -> Building:
    return Building().with_metadata(name=name)


def _level(index: int = 0) -> Level:
    return Level(index=index, elevation=0.0, floor_height=3.0)


class TestHistoryStart:

    def test_start_creates_history(self):
        h = History.start(_building("A"))
        assert isinstance(h, History)

    def test_current_is_initial(self):
        b = _building("A")
        h = History.start(b)
        assert h.current.metadata.name == "A"

    def test_can_undo_false_initially(self):
        assert not History.start(_building()).can_undo

    def test_can_redo_false_initially(self):
        assert not History.start(_building()).can_redo

    def test_snapshot_count_one(self):
        h = History.start(_building())
        assert len(h.snapshots) == 1
        assert h.cursor == 0


class TestHistoryPush:

    def test_push_adds_snapshot(self):
        h = History.start(_building("A"))
        h2 = h.push(_building("B"))
        assert len(h2.snapshots) == 2
        assert h2.current.metadata.name == "B"

    def test_original_unchanged(self):
        h = History.start(_building("A"))
        h.push(_building("B"))
        assert h.current.metadata.name == "A"

    def test_can_undo_after_push(self):
        h = History.start(_building()).push(_building("B"))
        assert h.can_undo

    def test_push_truncates_redo_branch(self):
        h = History.start(_building("A"))
        h = h.push(_building("B"))
        b, h = h.undo()
        # Now at A, redo branch has B
        assert h.can_redo
        h2 = h.push(_building("C"))
        # After pushing C the redo branch (B) is gone
        assert not h2.can_redo
        assert h2.current.metadata.name == "C"

    def test_max_snapshots_enforced(self):
        h = History.start(_building("0"), max_snapshots=3)
        h = h.push(_building("1"))
        h = h.push(_building("2"))
        h = h.push(_building("3"))   # should drop "0"
        assert len(h.snapshots) == 3
        assert h.current.metadata.name == "3"
        assert h.snapshots[0].metadata.name == "1"  # "0" was dropped


class TestHistoryUndo:

    def test_undo_returns_previous(self):
        h = History.start(_building("A")).push(_building("B"))
        b, h2 = h.undo()
        assert b.metadata.name == "A"
        assert h2.current.metadata.name == "A"

    def test_undo_enables_redo(self):
        h = History.start(_building("A")).push(_building("B"))
        _, h2 = h.undo()
        assert h2.can_redo

    def test_undo_at_beginning_raises(self):
        h = History.start(_building())
        with pytest.raises(HistoryError):
            h.undo()

    def test_multiple_undos(self):
        h = History.start(_building("A"))
        h = h.push(_building("B"))
        h = h.push(_building("C"))
        b, h = h.undo()
        assert b.metadata.name == "B"
        b, h = h.undo()
        assert b.metadata.name == "A"
        assert not h.can_undo


class TestHistoryRedo:

    def test_redo_returns_next(self):
        h = History.start(_building("A")).push(_building("B"))
        _, h_a = h.undo()
        b, h_b = h_a.redo()
        assert b.metadata.name == "B"

    def test_redo_at_end_raises(self):
        h = History.start(_building())
        with pytest.raises(HistoryError):
            h.redo()

    def test_redo_after_push_not_available(self):
        h = History.start(_building("A")).push(_building("B"))
        assert not h.can_redo

    def test_undo_redo_round_trip(self):
        h = History.start(_building("A"))
        h = h.push(_building("B"))
        h = h.push(_building("C"))
        b, h = h.undo()   # → B
        b, h = h.undo()   # → A
        b, h = h.redo()   # → B
        assert b.metadata.name == "B"
        b, h = h.redo()   # → C
        assert b.metadata.name == "C"
        assert not h.can_redo


class TestHistoryImmutability:

    def test_push_does_not_mutate(self):
        h = History.start(_building("A"))
        _ = h.push(_building("B"))
        # Original history still has 1 snapshot
        assert len(h.snapshots) == 1

    def test_frozen(self):
        h = History.start(_building())
        with pytest.raises(Exception):
            h.cursor = 99  # type: ignore

    def test_repr(self):
        h = History.start(_building())
        r = repr(h)
        assert "History" in r
        assert "cursor" in r
