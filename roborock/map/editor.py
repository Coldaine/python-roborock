"""Local State Machine for Roborock map editing.

This module implements the "Virtual State" pattern for optimistic UI map editing.
It provides:
- EditObject base classes for different edit types
- VirtualState to manage pending edits
- Undo/Redo functionality
- Preview generation
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import logging
import pathlib
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from .geometry import BoundingBox, LineSegment, Point

if TYPE_CHECKING:
    from vacuum_map_parser_base.map_data import MapData

    from .geometry import CoordinateTransformer

_LOGGER = logging.getLogger(__name__)


def _read_json(path: pathlib.Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: pathlib.Path, data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


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
    edit_id: str = field(default_factory=lambda: f"edit_{uuid.uuid4().hex}")

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

    @classmethod
    def from_dict(cls, data: dict) -> 'EditObject':
        """Create edit from dictionary."""
        edit_type_name = data.get("edit_type")
        
        # Determine subclass based on type name
        if edit_type_name == "VIRTUAL_WALL":
            from .editor import VirtualWallEdit as edit_class
        elif edit_type_name == "NO_GO_ZONE":
            from .editor import NoGoZoneEdit as edit_class
        elif edit_type_name == "SPLIT_ROOM":
            from .editor import SplitRoomEdit as edit_class
        elif edit_type_name == "MERGE_ROOMS":
            from .editor import MergeRoomsEdit as edit_class
        elif edit_type_name == "RENAME_ROOM":
            from .editor import RenameRoomEdit as edit_class
        else:
            raise ValueError(f"Unknown or unsupported edit type: {edit_type_name}")
            
        kwargs = dict(data)
        kwargs.pop("edit_type", None)
        status_name = kwargs.pop("status", "PENDING")
        edit_id = kwargs.pop("edit_id", None)
        
        obj = edit_class(**kwargs)
        if edit_id:
            obj.edit_id = edit_id
        obj.status = EditStatus[status_name]
        return obj



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
        self._lock = asyncio.Lock()

        # Capture original state for full physical rollback support
        self._original_room_names: dict[int, str] = {}
        self._original_walls: list[tuple[float, float, float, float]] = []
        self._original_no_go_zones: list[tuple[float, float, float, float]] = []
        self._original_mop_zones: list[tuple[float, float, float, float]] = []

        # Map identifier for validation
        self._map_flag: int | None = None
        self._map_hash: str | None = None

        if map_data:
            self._capture_base_state(map_data)

    def _capture_base_state(self, map_data: MapData) -> None:
        """Capture the base state from map data for rollback and persistence.
        
        Args:
            map_data: The map data to capture state from.
        """
        # Capture map identifier
        self._map_flag = getattr(map_data, 'map_flag', None)
        self._map_hash = self._calculate_map_hash(map_data)
        
        # Capture rooms
        if map_data.rooms:
            for room_id, room in map_data.rooms.items():
                if hasattr(room, 'name') and room.name:
                    self._original_room_names[room_id] = room.name

        # Capture walls (if exposed by parser)
        if hasattr(map_data, 'walls') and map_data.walls:
            for wall in map_data.walls:
                self._original_walls.append((wall.x1, wall.y1, wall.x2, wall.y2))

        # Capture zones (if exposed by parser)
        if hasattr(map_data, 'no_go_areas') and map_data.no_go_areas:
            for zone in map_data.no_go_areas:
                # Note: we simplify to 4-coord bbox for compatibility
                xs = [p.x for p in zone.points]
                ys = [p.y for p in zone.points]
                self._original_no_go_zones.append((min(xs), min(ys), max(xs), max(ys)))

        # Capture mop zones
        if hasattr(map_data, 'no_mop_areas') and map_data.no_mop_areas:
            for zone in map_data.no_mop_areas:
                xs = [p.x for p in zone.points]
                ys = [p.y for p in zone.points]
                self._original_mop_zones.append((min(xs), min(ys), max(xs), max(ys)))

    @property
    def map_hash(self) -> str | None:
        """Return the stored map hash for validation."""
        return getattr(self, '_map_hash', None)

    @property
    def map_flag(self) -> int | None:
        """Return the stored map flag for validation."""
        return getattr(self, '_map_flag', None)

    def _calculate_map_hash(self, map_data: MapData) -> str | None:
        """Calculate a hash of the map for validation purposes.
        
        Args:
            map_data: The map data to hash.
            
        Returns:
            A string hash of key map characteristics, or None if map is None.
        """
        if map_data is None:
            return None
        
        # Create a hash based on map characteristics that would change with map updates
        hash_parts = []
        
        # Map flag
        map_flag = getattr(map_data, 'map_flag', 0)
        hash_parts.append(f"flag:{map_flag}")
        
        # Room IDs and names
        if map_data.rooms:
            room_data = []
            for room_id in sorted(map_data.rooms.keys()):
                room = map_data.rooms[room_id]
                room_name = getattr(room, 'name', '')
                room_data.append(f"{room_id}:{room_name}")
            hash_parts.append(f"rooms:{','.join(room_data)}")
        
        # Image dimensions if available
        if hasattr(map_data, 'image') and map_data.image:
            width = getattr(map_data.image, 'width', 0)
            height = getattr(map_data.image, 'height', 0)
            hash_parts.append(f"dims:{width}x{height}")
        
        # Create hash
        hash_str = "|".join(hash_parts)
        return hashlib.md5(hash_str.encode()).hexdigest()[:16]

    async def acquire(self):
        """Async context manager for lock acquisition.

        Returns:
            An async context manager for the internal lock.
        """
        return self._lock.acquire()

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

    async def add_edit(self, edit: EditObject) -> tuple[bool, str | None]:
        """Add an edit to the stack.

        Args:
            edit: The edit to add.

        Returns:
            Tuple of (success, error_message).
        """
        async with self._lock:
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

    async def undo(self) -> EditObject | None:
        """Undo the last edit.

        Returns:
            The undone edit, or None if no edits to undo.
        """
        async with self._lock:
            if not self._edit_stack:
                return None

            edit = self._edit_stack.pop()
            self._redo_stack.append(edit)

            # Apply inverse to virtual state
            if edit.inverse and self._base_map and self._transformer:
                edit.inverse.apply(self._base_map, self._transformer)

            _LOGGER.debug(f"Undone edit: {edit.edit_id}")
            return edit

    async def redo(self) -> EditObject | None:
        """Redo the last undone edit.

        Returns:
            The redone edit, or None if no edits to redo.
        """
        async with self._lock:
            if not self._redo_stack:
                return None

            edit = self._redo_stack.pop()
            self._edit_stack.append(edit)

            # Re-apply the edit
            if self._base_map and self._transformer:
                edit.apply(self._base_map, self._transformer)

            _LOGGER.debug(f"Redone edit: {edit.edit_id}")
            return edit

    async def refresh_base_map(self, map_data: MapData) -> None:
        """Refresh the base map and coordinate transformer.

        This is used after a physical sync to ensure the virtual state
        matches the current device state.

        Args:
            map_data: The fresh map data from device.
        """
        from .geometry import CoordinateTransformer

        async with self._lock:
            self._base_map = map_data
            # Force re-capture of validation metadata for the refreshed base map.
            self._map_flag = None
            self._map_hash = None
            self._capture_base_state(map_data)
            self._transformer = CoordinateTransformer.from_map_data(map_data)
            _LOGGER.debug("Refreshed base map in VirtualState")

    async def clear(self) -> None:
        """Clear all edits and reset to base state."""
        async with self._lock:
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
            "original_walls": self._original_walls,
            "original_no_go_zones": self._original_no_go_zones,
            "original_mop_zones": self._original_mop_zones,
            "map_flag": getattr(self, '_map_flag', None),
            "map_hash": getattr(self, '_map_hash', None),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], map_data: MapData | None = None, transformer: CoordinateTransformer | None = None) -> "VirtualState":
        """Create a VirtualState from a dictionary.
        
        Args:
            data: The dictionary containing serialized state.
            map_data: The current map data for validation.
            transformer: Coordinate transformer for this map.
            
        Returns:
            A new VirtualState instance with restored edits.
        """
        state = cls(map_data=map_data, transformer=transformer)
        
        # Restore original state
        state._original_room_names = data.get("original_room_names", {})
        state._original_walls = [tuple(w) for w in data.get("original_walls", [])]
        state._original_no_go_zones = [tuple(z) for z in data.get("original_no_go_zones", [])]
        state._original_mop_zones = [tuple(z) for z in data.get("original_mop_zones", [])]
        state._map_flag = data.get("map_flag")
        state._map_hash = data.get("map_hash")
        
        # Restore edits
        state._edit_stack.clear()
        state._redo_stack.clear()
        for edit_data in data.get("edits", []):
            try:
                edit = EditObject.from_dict(edit_data)
                state._edit_stack.append(edit)
            except Exception as e:
                _LOGGER.error(f"Failed to load edit: {e}")
        
        return state

    def __len__(self) -> int:
        """Return the number of pending edits."""
        return len(self._edit_stack)

    async def save(self, path: pathlib.Path) -> None:
        """Save the virtual state to a JSON file.
        
        Args:
            path: Path to save the state to.
            
        Serializes:
            - Edit stack (all pending edits)
            - Base map identifier (map_flag and hash)
            - Original room names for rollback
            - Original walls, zones for rollback
        """
        async with self._lock:
            # Ensure we have current map hash
            if self._base_map is not None and self._map_hash is None:
                self._map_hash = self._calculate_map_hash(self._base_map)
            
            data = {
                "version": 1,
                "edits": [edit.to_dict() for edit in self._edit_stack],
                "original_room_names": self._original_room_names,
                "original_walls": self._original_walls,
                "original_no_go_zones": self._original_no_go_zones,
                "original_mop_zones": self._original_mop_zones,
                "map_flag": self._map_flag,
                "map_hash": self._map_hash,
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            }
            
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            
            await asyncio.to_thread(_write_json, path, data)
            
            _LOGGER.debug(f"Saved virtual state to {path} with {len(self._edit_stack)} edits")

    @classmethod
    async def load(cls, path: pathlib.Path, map_data: MapData) -> "VirtualState":
        """Load a virtual state from a JSON file.
        
        Args:
            path: Path to load the state from.
            map_data: The current map data for validation and reconstruction.
            
        Returns:
            A reconstructed VirtualState instance.
            
        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file is invalid or map validation fails.
        """
        if not path.exists():
            raise FileNotFoundError(f"Virtual state file not found: {path}")
        
        data = await asyncio.to_thread(_read_json, path)
        
        # Create state with map_data
        from .geometry import CoordinateTransformer
        transformer = CoordinateTransformer.from_map_data(map_data)
        state = cls.from_dict(data, map_data=map_data, transformer=transformer)
        
        # Validate map matches saved state
        current_hash = state._calculate_map_hash(map_data)
        saved_hash = data.get("map_hash")
        
        if saved_hash and current_hash != saved_hash:
            _LOGGER.warning(
                f"Map hash mismatch: saved={saved_hash}, current={current_hash}. "
                "The map may have changed since the state was saved."
            )
            raise ValueError(
                "Map has changed since state was saved (hash mismatch). "
                "Saved edits may no longer be valid."
            )
        
        saved_map_flag = data.get("map_flag")
        current_map_flag = getattr(map_data, "map_flag", None)
        
        if saved_map_flag is not None and saved_map_flag != current_map_flag:
            _LOGGER.warning(
                f"Map flag mismatch: saved={saved_map_flag}, current={current_map_flag}"
            )
            raise ValueError(
                f"Map flag changed from {saved_map_flag} to {current_map_flag}. "
                f"Saved edits may no longer be valid."
            )
        
        _LOGGER.debug(f"Loaded virtual state from {path} with {len(state)} edits")
        return state

    async def load_legacy(self, filepath: str | pathlib.Path) -> None:
        """Load pending edits from a JSON file (legacy method, without validation).
        
        This method is kept for backward compatibility. Use load() for new code.
        
        Args:
            filepath: Path to the JSON file.
        """
        path = pathlib.Path(filepath)
        if not path.exists():
            return

        async with self._lock:
            try:
                data = await asyncio.to_thread(_read_json, path)
                self._edit_stack.clear()
                self._redo_stack.clear()
                for edit_data in data.get("edits", []):
                    try:
                        edit = EditObject.from_dict(edit_data)
                        self._edit_stack.append(edit)
                    except Exception as e:
                        _LOGGER.error(f"Failed to load edit: {e}")
            except Exception as e:
                _LOGGER.error(f"Failed to parse virtual state file: {e}")
