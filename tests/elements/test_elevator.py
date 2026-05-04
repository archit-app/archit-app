import pytest

from archit_app import WORLD, Elevator, ElevatorDoor, Point2D


def test_rectangular_factory():
    e = Elevator.rectangular(x=0, y=0, cab_width=1.1, cab_depth=1.4)
    assert isinstance(e, Elevator)
    assert e.cab_width == pytest.approx(1.1)
    assert e.cab_depth == pytest.approx(1.4)


def test_shaft_includes_clearance():
    clearance = 0.15
    e = Elevator.rectangular(x=0, y=0, cab_width=1.1, cab_depth=1.4,
                              shaft_clearance=clearance)
    bb = e.bounding_box()
    assert bb.width == pytest.approx(1.1 + 2 * clearance)
    assert bb.height == pytest.approx(1.4 + 2 * clearance)


def test_cab_area():
    e = Elevator.rectangular(x=0, y=0, cab_width=1.2, cab_depth=1.5)
    assert e.cab_area == pytest.approx(1.2 * 1.5)


def test_levels_served():
    e = Elevator.rectangular(x=0, y=0, cab_width=1.1, cab_depth=1.4,
                              bottom_level_index=0, top_level_index=3)
    assert e.levels_served == [0, 1, 2, 3]


def test_add_door():
    e = Elevator.rectangular(x=0, y=0, cab_width=1.1, cab_depth=1.4)
    door = ElevatorDoor(level_index=0, position=Point2D(x=0.7, y=0, crs=WORLD))
    e2 = e.add_door(door)
    assert len(e.doors) == 0
    assert len(e2.doors) == 1


def test_remove_door():
    e = Elevator.rectangular(x=0, y=0, cab_width=1.1, cab_depth=1.4)
    door = ElevatorDoor(level_index=0, position=Point2D(x=0.7, y=0, crs=WORLD))
    e2 = e.add_door(door)
    e3 = e2.remove_door(0)
    assert len(e3.doors) == 0


def test_invalid_cab_dimensions():
    with pytest.raises(ValueError):
        Elevator.rectangular(x=0, y=0, cab_width=0, cab_depth=1.4)
    with pytest.raises(ValueError):
        Elevator.rectangular(x=0, y=0, cab_width=1.1, cab_depth=-1)


def test_invalid_level_order():
    with pytest.raises(ValueError):
        Elevator.rectangular(x=0, y=0, cab_width=1.1, cab_depth=1.4,
                             bottom_level_index=2, top_level_index=1)


def test_frozen():
    e = Elevator.rectangular(x=0, y=0, cab_width=1.1, cab_depth=1.4)
    with pytest.raises(Exception):
        e.cab_width = 2.0  # type: ignore
