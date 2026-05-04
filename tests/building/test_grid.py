import pytest

from archit_app import WORLD, GridAxis, Point2D, StructuralGrid


@pytest.fixture
def simple_grid() -> StructuralGrid:
    """3×3 regular grid with 6m x-spacing and 6m y-spacing."""
    return StructuralGrid.regular(
        x_spacing=6.0, y_spacing=6.0,
        x_count=3, y_count=3,
        origin_x=0.0, origin_y=0.0,
        grid_length=30.0,
    )


def test_regular_factory_creates_axes(simple_grid):
    assert len(simple_grid.x_axes) == 3
    assert len(simple_grid.y_axes) == 3


def test_default_labels(simple_grid):
    x_names = [a.name for a in simple_grid.x_axes]
    y_names = [a.name for a in simple_grid.y_axes]
    assert x_names == ["1", "2", "3"]
    assert y_names == ["A", "B", "C"]


def test_get_x_axis(simple_grid):
    ax = simple_grid.get_x_axis("2")
    assert ax is not None
    assert ax.name == "2"


def test_get_y_axis(simple_grid):
    ay = simple_grid.get_y_axis("B")
    assert ay is not None
    assert ay.name == "B"


def test_intersection(simple_grid):
    pt = simple_grid.intersection("1", "A")
    assert pt is not None
    assert pt.x == pytest.approx(0.0)
    assert pt.y == pytest.approx(0.0)


def test_intersection_offset(simple_grid):
    pt = simple_grid.intersection("3", "C")
    assert pt is not None
    assert pt.x == pytest.approx(12.0)
    assert pt.y == pytest.approx(12.0)


def test_intersection_missing_axis(simple_grid):
    assert simple_grid.intersection("99", "A") is None
    assert simple_grid.intersection("1", "Z") is None


def test_nearest_intersection(simple_grid):
    p = Point2D(x=6.1, y=5.9, crs=WORLD)
    result = simple_grid.nearest_intersection(p)
    assert result is not None
    x_name, y_name, pt = result
    assert x_name == "2"
    assert y_name == "B"
    assert pt.x == pytest.approx(6.0)
    assert pt.y == pytest.approx(6.0)


def test_snap_within_tolerance(simple_grid):
    p = Point2D(x=0.05, y=0.05, crs=WORLD)
    snapped = simple_grid.snap_to_grid(p, tolerance=0.1)
    assert snapped.x == pytest.approx(0.0)
    assert snapped.y == pytest.approx(0.0)


def test_snap_outside_tolerance(simple_grid):
    p = Point2D(x=1.0, y=1.0, crs=WORLD)
    snapped = simple_grid.snap_to_grid(p, tolerance=0.1)
    assert snapped.x == pytest.approx(1.0)
    assert snapped.y == pytest.approx(1.0)


def test_add_remove_axes(simple_grid):
    new_ax = GridAxis(
        name="4",
        start=Point2D(x=18.0, y=-15.0, crs=WORLD),
        end=Point2D(x=18.0, y=15.0, crs=WORLD),
    )
    g2 = simple_grid.add_x_axis(new_ax)
    assert len(g2.x_axes) == 4
    g3 = g2.remove_x_axis("4")
    assert len(g3.x_axes) == 3


def test_axis_length():
    ax = GridAxis(
        name="1",
        start=Point2D(x=0, y=0, crs=WORLD),
        end=Point2D(x=3, y=4, crs=WORLD),
    )
    assert ax.length == pytest.approx(5.0)


def test_axis_nearest_point():
    ax = GridAxis(
        name="1",
        start=Point2D(x=0, y=0, crs=WORLD),
        end=Point2D(x=10, y=0, crs=WORLD),
    )
    p = Point2D(x=5, y=3, crs=WORLD)
    np_ = ax.nearest_point(p)
    assert np_.x == pytest.approx(5.0)
    assert np_.y == pytest.approx(0.0)


def test_axis_zero_length_raises():
    with pytest.raises(ValueError):
        GridAxis(
            name="bad",
            start=Point2D(x=1, y=1, crs=WORLD),
            end=Point2D(x=1, y=1, crs=WORLD),
        )


def test_grid_frozen(simple_grid):
    with pytest.raises(Exception):
        simple_grid.x_axes = ()  # type: ignore
