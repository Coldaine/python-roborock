"""Geometric Math Engine for Roborock map editing.

This module provides coordinate conversion and geometric operations for map editing.
It handles the conversion between:
- Image Space (PNG pixels)
- Grid Space (parser internal)
- Robot Space (mm coordinates used by API)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vacuum_map_parser_base.map_data import MapData, ImageData

_LOGGER = logging.getLogger(__name__)

# Grid space divides robot space by this factor
GRID_SCALE_FACTOR = 50


@dataclass(frozen=True)
class Point:
    """A 2D point in a specific coordinate space."""

    x: float
    y: float

    def __add__(self, other: Point) -> Point:
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Point) -> Point:
        return Point(self.x - other.x, self.y - other.y)

    def scale(self, factor: float) -> Point:
        """Scale the point by a factor."""
        return Point(self.x * factor, self.y * factor)


@dataclass(frozen=True)
class LineSegment:
    """A line segment defined by two points."""

    p1: Point
    p2: Point

    @property
    def midpoint(self) -> Point:
        """Calculate the midpoint of the line segment."""
        return Point((self.p1.x + self.p2.x) / 2, (self.p1.y + self.p2.y) / 2)

    @property
    def length(self) -> float:
        """Calculate the length of the line segment."""
        dx = self.p2.x - self.p1.x
        dy = self.p2.y - self.p1.y
        return (dx * dx + dy * dy) ** 0.5

    def interpolate(self, t: float) -> Point:
        """Interpolate a point along the line segment.

        Args:
            t: Parameter from 0 (p1) to 1 (p2).

        Returns:
            Interpolated point.
        """
        return Point(
            self.p1.x + t * (self.p2.x - self.p1.x),
            self.p1.y + t * (self.p2.y - self.p1.y),
        )


@dataclass(frozen=True)
class BoundingBox:
    """An axis-aligned bounding box."""

    min_x: float
    max_x: float
    min_y: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def center(self) -> Point:
        return Point(
            (self.min_x + self.max_x) / 2,
            (self.min_y + self.max_y) / 2,
        )

    def contains(self, point: Point) -> bool:
        """Check if a point is inside the bounding box."""
        return (
            self.min_x <= point.x <= self.max_x
            and self.min_y <= point.y <= self.max_y
        )

    def intersects(self, other: BoundingBox) -> bool:
        """Check if this bounding box intersects another."""
        return not (
            self.max_x < other.min_x
            or other.max_x < self.min_x
            or self.max_y < other.min_y
            or other.max_y < self.min_y
        )


@dataclass(frozen=True)
class Polygon:
    """A polygon defined by a list of vertices."""

    vertices: list[Point]

    @property
    def bounding_box(self) -> BoundingBox:
        """Calculate the bounding box of the polygon."""
        if not self.vertices:
            return BoundingBox(0, 0, 0, 0)
        xs = [p.x for p in self.vertices]
        ys = [p.y for p in self.vertices]
        return BoundingBox(min(xs), max(xs), min(ys), max(ys))


class CoordinateTransformer:
    """Transforms coordinates between image, grid, and robot space.

    The parser's ImageDimensions object defines the transformation:
    - top/left: Offset in grid space
    - scale: Scale factor from grid to image space

    Formula (Image -> Robot):
        Robot_X = ((Pixel_X / scale) + left) * 50
        Robot_Y = ((Pixel_Y / scale) + top) * 50

    Formula (Robot -> Image):
        Pixel_X = (Robot_X / 50 - left) * scale
        Pixel_Y = (Robot_Y / 50 - top) * scale
    """

    def __init__(self, top: float, left: float, scale: float) -> None:
        """Initialize the transformer.

        Args:
            top: Y offset in grid space (from ImageDimensions.top).
            left: X offset in grid space (from ImageDimensions.left).
            scale: Scale factor from grid to image space (from ImageDimensions.scale).
        """
        self._top = top
        self._left = left
        self._scale = scale

    @classmethod
    def from_map_data(cls, map_data: MapData) -> CoordinateTransformer | None:
        """Create a transformer from parsed map data.

        Args:
            map_data: The parsed map data from vacuum-map-parser-roborock.

        Returns:
            CoordinateTransformer instance, or None if image data is unavailable.
        """
        if map_data.image is None:
            _LOGGER.error("Map data has no image information")
            return None

        dims = map_data.image.dimensions
        return cls(
            top=float(dims.top),
            left=float(dims.left),
            scale=float(dims.scale),
        )

    def image_to_robot(self, point: Point) -> Point:
        """Convert a point from image space (pixels) to robot space (mm).

        Args:
            point: Point in image coordinates (pixels).

        Returns:
            Point in robot coordinates (mm).
        """
        return Point(
            x=((point.x / self._scale) + self._left) * GRID_SCALE_FACTOR,
            y=((point.y / self._scale) + self._top) * GRID_SCALE_FACTOR,
        )

    def robot_to_image(self, point: Point) -> Point:
        """Convert a point from robot space (mm) to image space (pixels).

        Args:
            point: Point in robot coordinates (mm).

        Returns:
            Point in image coordinates (pixels).
        """
        return Point(
            x=(point.x / GRID_SCALE_FACTOR - self._left) * self._scale,
            y=(point.y / GRID_SCALE_FACTOR - self._top) * self._scale,
        )

    def image_to_grid(self, point: Point) -> Point:
        """Convert a point from image space to grid space.

        Args:
            point: Point in image coordinates (pixels).

        Returns:
            Point in grid coordinates.
        """
        return Point(
            x=(point.x / self._scale) + self._left,
            y=(point.y / self._scale) + self._top,
        )

    def grid_to_image(self, point: Point) -> Point:
        """Convert a point from grid space to image space.

        Args:
            point: Point in grid coordinates.

        Returns:
            Point in image coordinates (pixels).
        """
        return Point(
            x=(point.x - self._left) * self._scale,
            y=(point.y - self._top) * self._scale,
        )

    def grid_to_robot(self, point: Point) -> Point:
        """Convert a point from grid space to robot space (mm).

        Args:
            point: Point in grid coordinates.

        Returns:
            Point in robot coordinates (mm).
        """
        return Point(
            x=point.x * GRID_SCALE_FACTOR,
            y=point.y * GRID_SCALE_FACTOR,
        )

    def robot_to_grid(self, point: Point) -> Point:
        """Convert a point from robot space (mm) to grid space.

        Args:
            point: Point in robot coordinates (mm).

        Returns:
            Point in grid coordinates.
        """
        return Point(
            x=point.x / GRID_SCALE_FACTOR,
            y=point.y / GRID_SCALE_FACTOR,
        )


def calculate_room_overlap(box1: BoundingBox, box2: BoundingBox) -> float:
    """Calculate the overlap ratio between two bounding boxes.

    Uses Intersection over Union (IoU) approach.

    Args:
        box1: First bounding box.
        box2: Second bounding box.

    Returns:
        Ratio of intersection area to union area (0-1).
    """
    # Calculate intersection
    inter_min_x = max(box1.min_x, box2.min_x)
    inter_max_x = min(box1.max_x, box2.max_x)
    inter_min_y = max(box1.min_y, box2.min_y)
    inter_max_y = min(box1.max_y, box2.max_y)

    if inter_max_x < inter_min_x or inter_max_y < inter_min_y:
        return 0.0

    inter_area = (inter_max_x - inter_min_x) * (inter_max_y - inter_min_y)

    # Calculate union
    area1 = box1.width * box1.height
    area2 = box2.width * box2.height
    union_area = area1 + area2 - inter_area

    if union_area <= 0:
        return 0.0

    return inter_area / union_area


def calculate_split_line(
    bounding_box: BoundingBox,
    direction: str = "vertical",
    ratio: float = 0.5,
) -> LineSegment:
    """Calculate a line to split a room.

    Args:
        bounding_box: The bounding box of the room to split.
        direction: "vertical" or "horizontal" split.
        ratio: Position of the split line (0-1).

    Returns:
        A line segment that divides the room.

    Raises:
        ValueError: If direction is invalid or ratio is out of range.
    """
    if not 0 < ratio < 1:
        raise ValueError(f"Ratio must be between 0 and 1, got {ratio}")

    if direction == "vertical":
        # Split along Y axis (horizontal line)
        y = bounding_box.min_y + bounding_box.height * ratio
        return LineSegment(
            Point(bounding_box.min_x, y),
            Point(bounding_box.max_x, y),
        )
    elif direction == "horizontal":
        # Split along X axis (vertical line)
        x = bounding_box.min_x + bounding_box.width * ratio
        return LineSegment(
            Point(x, bounding_box.min_y),
            Point(x, bounding_box.max_y),
        )
    else:
        raise ValueError(f"Invalid direction: {direction}. Use 'vertical' or 'horizontal'.")


def line_intersects_box(line: LineSegment, box: BoundingBox) -> bool:
    """Check if a line segment intersects a bounding box.

    Args:
        line: The line segment to check.
        box: The bounding box to check against.

    Returns:
        True if the line intersects or is inside the box.
    """
    # Check if either endpoint is inside
    if box.contains(line.p1) or box.contains(line.p2):
        return True

    # Check intersection with box edges
    box_edges = [
        LineSegment(Point(box.min_x, box.min_y), Point(box.max_x, box.min_y)),
        LineSegment(Point(box.max_x, box.min_y), Point(box.max_x, box.max_y)),
        LineSegment(Point(box.max_x, box.max_y), Point(box.min_x, box.max_y)),
        LineSegment(Point(box.min_x, box.max_y), Point(box.min_x, box.min_y)),
    ]

    for edge in box_edges:
        if _segments_intersect(line, edge):
            return True

    return False


def _segments_intersect(s1: LineSegment, s2: LineSegment) -> bool:
    """Check if two line segments intersect using cross product method."""

    def cross_product(a: Point, b: Point, c: Point) -> float:
        """Calculate cross product of vectors AB and AC."""
        return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)

    def on_segment(a: Point, b: Point, c: Point) -> bool:
        """Check if point C lies on segment AB."""
        return (
            min(a.x, b.x) <= c.x <= max(a.x, b.x)
            and min(a.y, b.y) <= c.y <= max(a.y, b.y)
        )

    p1, p2 = s1.p1, s1.p2
    p3, p4 = s2.p1, s2.p2

    cp1 = cross_product(p1, p2, p3)
    cp2 = cross_product(p1, p2, p4)
    cp3 = cross_product(p3, p4, p1)
    cp4 = cross_product(p3, p4, p2)

    # General case: segments straddle each other
    if ((cp1 > 0 and cp2 < 0) or (cp1 < 0 and cp2 > 0)) and (
        (cp3 > 0 and cp4 < 0) or (cp3 < 0 and cp4 > 0)
    ):
        return True

    # Special cases: collinear points on segments
    if cp1 == 0 and on_segment(p1, p2, p3):
        return True
    if cp2 == 0 and on_segment(p1, p2, p4):
        return True
    if cp3 == 0 and on_segment(p3, p4, p1):
        return True
    if cp4 == 0 and on_segment(p3, p4, p2):
        return True

    return False
