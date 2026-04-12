"""Local State Machine for Roborock map editing.

This module implements the "Virtual State" pattern for optimistic UI map editing.
It provides:
- EditObject base classes for different edit types
- VirtualState to manage pending edits
- Undo/Redo functionality
- Preview generation
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from .geometry import BoundingBox, LineSegment, Point

if TYPE_CHECKING:
    from vacuum_map_parser_base.map_data import MapData

    from .geometry import CoordinateTransformer

_LOGGER = logging.getLogger(__name__)


class EditType(Enum):
    """Types of map edits."""

    VIRTUAL_WALL = auto()
    NO_GO_ZONE = auto()
    MOP_FORBIDDEN_ZONE = auto()
    SPLIT_ROOM = auto()
    MERGE_ROOMS = auto()
    RENAME_ROOM = auto()
    SET_ROOM_ORDER = auto()
    CARPET_AREA = auto()


class EditStatus(Enum):
    """Status of an edit operation."""

    PENDING = auto()  # Created but not applied
    APPLIED = auto()  # Applied to virtual state
    SYNCING = auto()  # Being sent to device
    SYNCED = auto()  # Confirmed on device
    FAILED = auto()  # Failed to apply


@dataclass
class EditObject(ABC):
    """Base class for all edit operations.

    EditObjects represent a single map modification operation.
    They can be applied to a VirtualState to preview changes
    without modifying the physical device.
    """

    edit_type: EditType
    status: EditStatus = field(default=EditStatus.PENDING)
    edit_id: str = field(default_factory=lambda: f"edit_{id(object())}")

    # Inverse command for rollback (populated after application)
    inverse: EditObject | None = field(default=None, repr=False)

    @abstractmethod
    def apply(self, map_data: MapData, transformer: CoordinateTransformer) -> None:
        """Apply this edit to the map data (in-place).

        Args:
            map_data: The map data to modify.
            transformer: Coordinate transformer for space conversions.
        """
        ...

    @abstractmethod
    def create_inverse(self) -> EditObject:
        """Create an inverse edit for rollback purposes.

        Returns:
            An EditObject that undoes this edit.
        """
        ...

    @abstractmethod
    def validate(self, map_data: MapData) -> tuple[bool, str | None]:
        """Validate that this edit can be applied.

        Args:
            map_data: The current map data.

        Returns:
            Tuple of (is_valid, error_message).
        """
        ...

    def to_dict(self) -> dict[str, Any]:
        """Convert edit to dictionary for serialization."""
        return {
            "edit_id": self.edit_id,
            "edit_type": self.edit_type.name,
            "status": self.status.name,
        }


@dataclass
class VirtualWallEdit(EditObject):
    """Add a virtual wall."""

    # Line endpoints in robot space (mm)
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    edit_type: EditType = field(default=EditType.VIRTUAL_WALL, init=False, repr=False)

    def apply(self, map_data: MapData, transformer: CoordinateTransformer) -> None:
        """Add the virtual wall to map data."""
        # Note: vacuum_map_parser_base doesn't expose a way to add walls
        # directly to MapData. This would need to be handled by the
        # translation layer when sending to device.
        _LOGGER.debug(f"Applying virtual wall: ({self.x1}, {self.y1}) -> ({self.x2}, {self.y2})")

    def create_inverse(self) -> EditObject:
        """Create inverse: remove the virtual wall."""
        # Inverse would be a RemoveVirtualWallEdit (not implemented yet)
        # For now, return a no-op placeholder
        return RemoveVirtualWallEdit(x1=self.x1, y1=self.y1, x2=self.x2, y2=self.y2)

    def validate(self, map_data: MapData) -> tuple[bool, str | None]:
        """Validate the virtual wall."""
        # Check line has non-zero length
        if abs(self.x1 - self.x2) < 1 and abs(self.y1 - self.y2) < 1:
            return False, "Virtual wall must have non-zero length"

        # Check if intersecting charger (would be rejected by firmware)
        if map_data.charger:
            charger_point = Point(map_data.charger.x, map_data.charger.y)
            wall = LineSegment(Point(self.x1, self.y1), Point(self.x2, self.y2))
            # Simple distance check
            if self._point_to_segment_distance(charger_point, wall) < 200:  # 20cm
                return False, "Virtual wall too close to charger"

        return True, None

    @staticmethod
    def _point_to_segment_distance(point: Point, segment: LineSegment) -> float:
        """Calculate distance from point to line segment."""
        px, py = point.x, point.y
        x1, y1 = segment.p1.x, segment.p1.y
        x2, y2 = segment.p2.x, segment.p2.y

        line_len = segment.length
        if line_len == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5

        t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / (line_len ** 2)))
        proj_x = x1 + t * (x2 - x1)
        proj_y = y1 + t * (y2 - y1)

        return ((px - proj_x) ** 2 + (py - proj_y) ** 2) ** 0.5

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
        })
        return base


@dataclass
class RemoveVirtualWallEdit(EditObject):
    """Remove a virtual wall (for inverse operations)."""

    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    edit_type: EditType = field(default=EditType.VIRTUAL_WALL, init=False, repr=False)

    def apply(self, map_data: MapData, transformer: CoordinateTransformer) -> None:
        _LOGGER.debug(f"Removing virtual wall: ({self.x1}, {self.y1}) -> ({self.x2}, {self.y2})")

    def create_inverse(self) -> EditObject:
        return VirtualWallEdit(x1=self.x1, y1=self.y1, x2=self.x2, y2=self.y2)

    def validate(self, map_data: MapData) -> tuple[bool, str | None]:
        return True, None


@dataclass
class NoGoZoneEdit(EditObject):
    """Add a no-go zone (rectangular)."""

    # Zone bounds in robot space (mm)
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    edit_type: EditType = field(default=EditType.NO_GO_ZONE, init=False, repr=False)

    def apply(self, map_data: MapData, transformer: CoordinateTransformer) -> None:
        _LOGGER.debug(f"Applying no-go zone: ({self.x1}, {self.y1}) -> ({self.x2}, {self.y2})")

    def create_inverse(self) -> EditObject:
        return RemoveNoGoZoneEdit(x1=self.x1, y1=self.y1, x2=self.x2, y2=self.y2)

    def validate(self, map_data: MapData) -> tuple[bool, str | None]:
        # Check area is non-zero
        if abs(self.x1 - self.x2) < 10 or abs(self.y1 - self.y2) < 10:
            return False, "No-go zone must have area > 10mm x 10mm"
        return True, None

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
        })
        return base


@dataclass
class RemoveNoGoZoneEdit(EditObject):
    """Remove a no-go zone (for inverse operations)."""

    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    edit_type: EditType = field(default=EditType.NO_GO_ZONE, init=False, repr=False)

    def apply(self, map_data: MapData, transformer: CoordinateTransformer) -> None:
        _LOGGER.debug(f"Removing no-go zone: ({self.x1}, {self.y1}) -> ({self.x2}, {self.y2})")

    def create_inverse(self) -> EditObject:
        return NoGoZoneEdit(x1=self.x1, y1=self.y1, x2=self.x2, y2=self.y2)

    def validate(self, map_data: MapData) -> tuple[bool, str | None]:
        return True, None


@dataclass
class SplitRoomEdit(EditObject):
    """Split a room into two segments."""

    segment_id: int = 0
    # Split line in robot space (mm)
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    edit_type: EditType = field(default=EditType.SPLIT_ROOM, init=False, repr=False)

    def apply(self, map_data: MapData, transformer: CoordinateTransformer) -> None:
        _LOGGER.debug(f"Applying room split for segment {self.segment_id}")
        # Note: Room split creates new segment IDs, which will be
        # determined by the firmware response

    def create_inverse(self) -> EditObject:
        # Inverse of split is merge - but we need the new segment IDs
        # This will be populated after the split response
        return MergeRoomsEdit(segment_ids=[self.segment_id])

    def validate(self, map_data: MapData) -> tuple[bool, str | None]:
        # Check segment exists
        if not map_data.rooms or self.segment_id not in map_data.rooms:
            return False, f"Segment {self.segment_id} not found"

        # Check split line intersects room
        room = map_data.rooms[self.segment_id]
        room_bbox = BoundingBox(
            min_x=room.x0,
            max_x=room.x1,
            min_y=room.y0,
            max_y=room.y1,
        )
        split_line = LineSegment(Point(self.x1, self.y1), Point(self.x2, self.y2))

        from .geometry import line_intersects_box
        if not line_intersects_box(split_line, room_bbox):
            return False, "Split line does not intersect room"

        return True, None

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "segment_id": self.segment_id,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
        })
        return base


@dataclass
class MergeRoomsEdit(EditObject):
    """Merge multiple rooms into one."""

    segment_ids: list[int] = field(default_factory=list)
    edit_type: EditType = field(default=EditType.MERGE_ROOMS, init=False, repr=False)

    def apply(self, map_data: MapData, transformer: CoordinateTransformer) -> None:
        _LOGGER.debug(f"Applying room merge for segments: {self.segment_ids}")

    def create_inverse(self) -> EditObject:
        # Inverse of merge is complex - would need to re-split
        # Return placeholder for now
        return SplitRoomEdit(segment_id=self.segment_ids[0] if self.segment_ids else 0)

    def validate(self, map_data: MapData) -> tuple[bool, str | None]:
        if len(self.segment_ids) < 2:
            return False, "Need at least 2 segments to merge"

        if not map_data.rooms:
            return False, "No rooms in map data"

        for seg_id in self.segment_ids:
            if seg_id not in map_data.rooms:
                return False, f"Segment {seg_id} not found"

        return True, None

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({"segment_ids": self.segment_ids})
        return base


@dataclass
class RenameRoomEdit(EditObject):
    """Rename a room."""

    segment_id: int = 0
    new_name: str = ""
    old_name: str = ""  # For inverse
    edit_type: EditType = field(default=EditType.RENAME_ROOM, init=False, repr=False)

    def apply(self, map_data: MapData, transformer: CoordinateTransformer) -> None:
        _LOGGER.debug(f"Renaming room {self.segment_id} to '{self.new_name}'")

    def create_inverse(self) -> EditObject:
        return RenameRoomEdit(
            segment_id=self.segment_id,
            new_name=self.old_name,
            old_name=self.new_name,
        )

    def validate(self, map_data: MapData) -> tuple[bool, str | None]:
        if not map_data.rooms or self.segment_id not in map_data.rooms:
            return False, f"Segment {self.segment_id} not found"
        if not self.new_name:
            return False, "New name cannot be empty"
        return True, None

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "segment_id": self.segment_id,
            "new_name": self.new_name,
            "old_name": self.old_name,
        })
        return base


class VirtualState:
    """Manages a stack of pending edits for optimistic UI.

    The VirtualState maintains a stack of EditObjects that represent
    changes to be applied. It supports:
    - Adding edits to the stack
    - Undo/Redo functionality
    - Preview generation
    - Serialization for persistence
    """

    def __init__(self, map_data: MapData | None = None, transformer: CoordinateTransformer | None = None):
        """Initialize the virtual state.

        Args:
            map_data: The base map data (will be copied).
            transformer: Coordinate transformer for this map.
        """
        self._base_map = map_data
        self._transformer = transformer
        self._edit_stack: list[EditObject] = []
        self._redo_stack: list[EditObject] = []
        self._original_room_names: dict[int, str] = {}

        # Capture original room names for rollback
        if map_data and map_data.rooms:
            for room_id, room in map_data.rooms.items():
                if hasattr(room, 'name'):
                    self._original_room_names[room_id] = room.name

    @property
    def has_pending_edits(self) -> bool:
        """Return True if there are pending edits."""
        return len(self._edit_stack) > 0

    @property
    def pending_edits(self) -> list[EditObject]:
        """Return the list of pending edits."""
        return list(self._edit_stack)

    @property
    def can_undo(self) -> bool:
        """Return True if undo is available."""
        return len(self._edit_stack) > 0

    @property
    def can_redo(self) -> bool:
        """Return True if redo is available."""
        return len(self._redo_stack) > 0

    def add_edit(self, edit: EditObject) -> tuple[bool, str | None]:
        """Add an edit to the stack.

        Args:
            edit: The edit to add.

        Returns:
            Tuple of (success, error_message).
        """
        if self._base_map is None:
            return False, "No base map data available"

        # Validate the edit
        is_valid, error = edit.validate(self._base_map)
        if not is_valid:
            return False, error

        # Create inverse for rollback
        edit.inverse = edit.create_inverse()
        edit.status = EditStatus.APPLIED

        # Apply to virtual state
        if self._transformer:
            edit.apply(self._base_map, self._transformer)

        self._edit_stack.append(edit)
        self._redo_stack.clear()  # Clear redo stack on new edit

        _LOGGER.debug(f"Added edit: {edit.edit_id} ({edit.edit_type.name})")
        return True, None

    def undo(self) -> EditObject | None:
        """Undo the last edit.

        Returns:
            The undone edit, or None if no edits to undo.
        """
        if not self._edit_stack:
            return None

        edit = self._edit_stack.pop()
        self._redo_stack.append(edit)

        # Apply inverse to virtual state
        if edit.inverse and self._base_map and self._transformer:
            edit.inverse.apply(self._base_map, self._transformer)

        _LOGGER.debug(f"Undone edit: {edit.edit_id}")
        return edit

    def redo(self) -> EditObject | None:
        """Redo the last undone edit.

        Returns:
            The redone edit, or None if no edits to redo.
        """
        if not self._redo_stack:
            return None

        edit = self._redo_stack.pop()
        self._edit_stack.append(edit)

        # Re-apply the edit
        if self._base_map and self._transformer:
            edit.apply(self._base_map, self._transformer)

        _LOGGER.debug(f"Redone edit: {edit.edit_id}")
        return edit

    def clear(self) -> None:
        """Clear all edits and reset to base state."""
        self._edit_stack.clear()
        self._redo_stack.clear()
        _LOGGER.debug("Cleared all edits")

    def get_edits_by_type(self, edit_type: EditType) -> list[EditObject]:
        """Get all edits of a specific type.

        Args:
            edit_type: The type of edits to filter by.

        Returns:
            List of matching edits.
        """
        return [e for e in self._edit_stack if e.edit_type == edit_type]

    def get_topology_edits(self) -> list[EditObject]:
        """Get topology edits (split, merge) that destroy/create IDs."""
        topology_types = {EditType.SPLIT_ROOM, EditType.MERGE_ROOMS}
        return [e for e in self._edit_stack if e.edit_type in topology_types]

    def get_property_edits(self) -> list[EditObject]:
        """Get property edits (rename) that depend on current IDs."""
        property_types = {EditType.RENAME_ROOM, EditType.SET_ROOM_ORDER}
        return [e for e in self._edit_stack if e.edit_type in property_types]

    def get_additive_edits(self) -> list[EditObject]:
        """Get additive edits (walls, zones) that use absolute coordinates."""
        additive_types = {
            EditType.VIRTUAL_WALL,
            EditType.NO_GO_ZONE,
            EditType.MOP_FORBIDDEN_ZONE,
            EditType.CARPET_AREA,
        }
        return [e for e in self._edit_stack if e.edit_type in additive_types]

    def get_structural_edits(self) -> list[EditObject]:
        """Deprecated: Use get_topology_edits or get_property_edits instead.
        
        Kept for backward compatibility.
        """
        return self.get_topology_edits() + self.get_property_edits()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the virtual state to a dictionary."""
        return {
            "edits": [e.to_dict() for e in self._edit_stack],
            "original_room_names": self._original_room_names,
        }

    def __len__(self) -> int:
        """Return the number of pending edits."""
        return len(self._edit_stack)
