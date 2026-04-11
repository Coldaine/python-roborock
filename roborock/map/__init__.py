"""Module for Roborock map related data classes and editing."""

from .editor import (
    EditObject,
    EditStatus,
    EditType,
    MergeRoomsEdit,
    NoGoZoneEdit,
    RenameRoomEdit,
    SplitRoomEdit,
    VirtualState,
    VirtualWallEdit,
)
from .geometry import (
    BoundingBox,
    CoordinateTransformer,
    LineSegment,
    Point,
    Polygon,
    calculate_split_line,
    line_intersects_box,
)
from .map_parser import MapParserConfig, ParsedMapData
from .translation import TranslationLayer, TranslationResult
from .verifier import MapVerifier, VerificationResult

__all__ = [
    # Map parsing
    "MapParserConfig",
    "ParsedMapData",
    # Geometry
    "Point",
    "LineSegment",
    "BoundingBox",
    "Polygon",
    "CoordinateTransformer",
    "calculate_split_line",
    "line_intersects_box",
    # Editor
    "EditType",
    "EditStatus",
    "EditObject",
    "VirtualWallEdit",
    "NoGoZoneEdit",
    "SplitRoomEdit",
    "MergeRoomsEdit",
    "RenameRoomEdit",
    "VirtualState",
    # Translation
    "TranslationLayer",
    "TranslationResult",
    # Verification
    "MapVerifier",
    "VerificationResult",
]
