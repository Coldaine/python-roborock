"""Tests for the geometric math engine."""

import pytest

from roborock.map.geometry import (
    GRID_SCALE_FACTOR,
    BoundingBox,
    CoordinateTransformer,
    LineSegment,
    Point,
    Polygon,
    calculate_split_line,
    line_intersects_box,
)


class TestPoint:
    """Tests for Point class."""

    def test_point_creation(self):
        p = Point(10.5, 20.5)
        assert p.x == 10.5
        assert p.y == 20.5

    def test_point_addition(self):
        p1 = Point(1, 2)
        p2 = Point(3, 4)
        result = p1 + p2
        assert result.x == 4
        assert result.y == 6

    def test_point_subtraction(self):
        p1 = Point(5, 5)
        p2 = Point(2, 3)
        result = p1 - p2
        assert result.x == 3
        assert result.y == 2

    def test_point_scale(self):
        p = Point(10, 20)
        result = p.scale(2)
        assert result.x == 20
        assert result.y == 40


class TestLineSegment:
    """Tests for LineSegment class."""

    def test_midpoint(self):
        line = LineSegment(Point(0, 0), Point(10, 10))
        mid = line.midpoint
        assert mid.x == 5
        assert mid.y == 5

    def test_length_horizontal(self):
        line = LineSegment(Point(0, 0), Point(10, 0))
        assert line.length == 10

    def test_length_diagonal(self):
        line = LineSegment(Point(0, 0), Point(3, 4))
        assert line.length == 5

    def test_interpolate(self):
        line = LineSegment(Point(0, 0), Point(10, 20))
        p = line.interpolate(0.5)
        assert p.x == 5
        assert p.y == 10


class TestBoundingBox:
    """Tests for BoundingBox class."""

    def test_width_height(self):
        box = BoundingBox(10, 30, 20, 50)
        assert box.width == 20
        assert box.height == 30

    def test_center(self):
        box = BoundingBox(0, 10, 0, 10)
        center = box.center
        assert center.x == 5
        assert center.y == 5

    def test_contains_point_inside(self):
        box = BoundingBox(0, 10, 0, 10)
        assert box.contains(Point(5, 5)) is True

    def test_contains_point_outside(self):
        box = BoundingBox(0, 10, 0, 10)
        assert box.contains(Point(15, 5)) is False

    def test_intersects_overlapping(self):
        box1 = BoundingBox(0, 10, 0, 10)
        box2 = BoundingBox(5, 15, 5, 15)
        assert box1.intersects(box2) is True

    def test_intersects_non_overlapping(self):
        box1 = BoundingBox(0, 10, 0, 10)
        box2 = BoundingBox(20, 30, 20, 30)
        assert box1.intersects(box2) is False


class TestPolygon:
    """Tests for Polygon class."""

    def test_bounding_box_triangle(self):
        poly = Polygon([Point(0, 0), Point(10, 0), Point(5, 10)])
        bbox = poly.bounding_box
        assert bbox.min_x == 0
        assert bbox.max_x == 10
        assert bbox.min_y == 0
        assert bbox.max_y == 10

    def test_bounding_box_empty(self):
        poly = Polygon([])
        bbox = poly.bounding_box
        assert bbox.min_x == 0
        assert bbox.max_x == 0


class TestCoordinateTransformer:
    """Tests for CoordinateTransformer class."""

    def test_image_to_robot(self):
        # Create transformer with known parameters
        transformer = CoordinateTransformer(top=10, left=20, scale=4)

        # Convert a point from image to robot space
        image_point = Point(0, 0)
        robot_point = transformer.image_to_robot(image_point)

        # Expected: ((0 / 4) + 20) * 50 = 1000
        assert robot_point.x == 1000
        assert robot_point.y == 500  # ((0 / 4) + 10) * 50 = 500

    def test_robot_to_image(self):
        transformer = CoordinateTransformer(top=10, left=20, scale=4)

        # Convert back from robot to image
        robot_point = Point(1000, 500)
        image_point = transformer.robot_to_image(robot_point)

        # Should get back to (0, 0)
        assert image_point.x == 0
        assert image_point.y == 0

    def test_round_trip_consistency(self):
        """Test that conversions are reversible."""
        transformer = CoordinateTransformer(top=5, left=10, scale=2)

        original = Point(100, 200)
        robot = transformer.image_to_robot(original)
        back = transformer.robot_to_image(robot)

        # Allow for floating point precision
        assert abs(back.x - original.x) < 0.01
        assert abs(back.y - original.y) < 0.01

    def test_grid_conversions(self):
        transformer = CoordinateTransformer(top=0, left=0, scale=1)

        # Grid to robot: multiply by GRID_SCALE_FACTOR (50)
        grid_point = Point(10, 20)
        robot_point = transformer.grid_to_robot(grid_point)
        assert robot_point.x == 500
        assert robot_point.y == 1000

        # Robot to grid: divide by GRID_SCALE_FACTOR
        back = transformer.robot_to_grid(robot_point)
        assert back.x == 10
        assert back.y == 20


class TestCalculateSplitLine:
    """Tests for calculate_split_line function."""

    def test_vertical_split(self):
        box = BoundingBox(0, 100, 0, 100)
        line = calculate_split_line(box, "vertical", 0.5)

        # Vertical split creates horizontal line at y=50
        assert line.p1.y == 50
        assert line.p2.y == 50
        # Line spans full width
        assert line.p1.x == 0
        assert line.p2.x == 100

    def test_horizontal_split(self):
        box = BoundingBox(0, 100, 0, 100)
        line = calculate_split_line(box, "horizontal", 0.5)

        # Horizontal split creates vertical line at x=50
        assert line.p1.x == 50
        assert line.p2.x == 50
        # Line spans full height
        assert line.p1.y == 0
        assert line.p2.y == 100

    def test_invalid_direction(self):
        box = BoundingBox(0, 100, 0, 100)
        with pytest.raises(ValueError, match="Invalid direction"):
            calculate_split_line(box, "diagonal", 0.5)

    def test_invalid_ratio(self):
        box = BoundingBox(0, 100, 0, 100)
        with pytest.raises(ValueError, match="Ratio must be between 0 and 1"):
            calculate_split_line(box, "vertical", 1.5)


class TestLineIntersectsBox:
    """Tests for line_intersects_box function."""

    def test_line_inside_box(self):
        box = BoundingBox(0, 100, 0, 100)
        line = LineSegment(Point(25, 25), Point(75, 75))
        assert line_intersects_box(line, box) is True

    def test_line_crossing_box(self):
        box = BoundingBox(0, 100, 0, 100)
        line = LineSegment(Point(-50, 50), Point(150, 50))
        assert line_intersects_box(line, box) is True

    def test_line_outside_box(self):
        box = BoundingBox(0, 100, 0, 100)
        line = LineSegment(Point(200, 200), Point(300, 300))
        assert line_intersects_box(line, box) is False

    def test_line_touching_corner(self):
        box = BoundingBox(0, 100, 0, 100)
        line = LineSegment(Point(-50, -50), Point(0, 0))
        assert line_intersects_box(line, box) is True
