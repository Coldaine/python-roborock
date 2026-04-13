"""Tests for the virtual state machine and edit objects."""

from unittest.mock import MagicMock, patch

import pytest

from roborock.map.editor import (
    EditStatus,
    EditType,
    MergeRoomsEdit,
    NoGoZoneEdit,
    RenameRoomEdit,
    SplitRoomEdit,
    VirtualState,
    VirtualWallEdit,
)


class TestVirtualWallEdit:
    """Tests for VirtualWallEdit."""

    def test_creation(self):
        edit = VirtualWallEdit(x1=100, y1=200, x2=300, y2=400)
        assert edit.edit_type == EditType.VIRTUAL_WALL
        assert edit.x1 == 100
        assert edit.y2 == 400

    def test_validation_zero_length(self):
        """Wall with zero length should be invalid."""
        edit = VirtualWallEdit(x1=100, y1=100, x2=100, y2=100)
        map_data = MagicMock()
        map_data.charger = None

        is_valid, error = edit.validate(map_data)
        assert is_valid is False
        assert "non-zero length" in error

    def test_validation_near_charger(self):
        """Wall too close to charger should be invalid."""
        edit = VirtualWallEdit(x1=100, y1=100, x2=200, y2=200)

        map_data = MagicMock()
        charger = MagicMock()
        charger.x = 150
        charger.y = 150
        map_data.charger = charger

        is_valid, error = edit.validate(map_data)
        assert is_valid is False
        assert "charger" in error.lower()

    def test_validation_valid(self):
        """Valid wall should pass."""
        edit = VirtualWallEdit(x1=1000, y1=1000, x2=2000, y2=2000)

        map_data = MagicMock()
        charger = MagicMock()
        charger.x = 0
        charger.y = 0
        map_data.charger = charger

        is_valid, error = edit.validate(map_data)
        assert is_valid is True
        assert error is None

    def test_to_dict(self):
        edit = VirtualWallEdit(x1=100, y1=200, x2=300, y2=400)
        data = edit.to_dict()
        assert data["edit_type"] == "VIRTUAL_WALL"
        assert data["x1"] == 100
        assert data["y2"] == 400


class TestNoGoZoneEdit:
    """Tests for NoGoZoneEdit."""

    def test_creation(self):
        edit = NoGoZoneEdit(x1=100, y1=200, x2=300, y2=400)
        assert edit.edit_type == EditType.NO_GO_ZONE

    def test_validation_too_small(self):
        """Zone too small should be invalid."""
        edit = NoGoZoneEdit(x1=100, y1=100, x2=105, y2=105)
        map_data = MagicMock()

        is_valid, error = edit.validate(map_data)
        assert is_valid is False
        assert "area" in error.lower()

    def test_validation_valid(self):
        """Valid zone should pass."""
        edit = NoGoZoneEdit(x1=100, y1=100, x2=500, y2=500)
        map_data = MagicMock()

        is_valid, error = edit.validate(map_data)
        assert is_valid is True
        assert error is None


class TestSplitRoomEdit:
    """Tests for SplitRoomEdit."""

    def test_creation(self):
        edit = SplitRoomEdit(segment_id=16, x1=100, y1=0, x2=100, y2=1000)
        assert edit.edit_type == EditType.SPLIT_ROOM
        assert edit.segment_id == 16

    def test_validation_room_not_found(self):
        """Split for non-existent room should be invalid."""
        edit = SplitRoomEdit(segment_id=99, x1=100, y1=0, x2=100, y2=1000)

        map_data = MagicMock()
        map_data.rooms = {16: MagicMock()}

        is_valid, error = edit.validate(map_data)
        assert is_valid is False
        assert "not found" in error

    def test_validation_line_not_intersecting(self):
        """Split line not intersecting room should be invalid."""
        edit = SplitRoomEdit(segment_id=16, x1=500, y1=0, x2=500, y2=1000)

        room = MagicMock()
        room.x0 = 0
        room.x1 = 100
        room.y0 = 0
        room.y1 = 100

        map_data = MagicMock()
        map_data.rooms = {16: room}

        is_valid, error = edit.validate(map_data)
        assert is_valid is False
        assert "does not intersect" in error


class TestMergeRoomsEdit:
    """Tests for MergeRoomsEdit."""

    def test_creation(self):
        edit = MergeRoomsEdit(segment_ids=[16, 17])
        assert edit.edit_type == EditType.MERGE_ROOMS

    def test_validation_not_enough_rooms(self):
        """Merge with < 2 rooms should be invalid."""
        edit = MergeRoomsEdit(segment_ids=[16])
        map_data = MagicMock()

        is_valid, error = edit.validate(map_data)
        assert is_valid is False
        assert "at least 2" in error

    def test_validation_room_not_found(self):
        """Merge with non-existent room should be invalid."""
        edit = MergeRoomsEdit(segment_ids=[16, 99])

        map_data = MagicMock()
        map_data.rooms = {16: MagicMock()}

        is_valid, error = edit.validate(map_data)
        assert is_valid is False
        assert "not found" in error


class TestRenameRoomEdit:
    """Tests for RenameRoomEdit."""

    def test_creation(self):
        edit = RenameRoomEdit(segment_id=16, new_name="Kitchen", old_name="Room 16")
        assert edit.edit_type == EditType.RENAME_ROOM

    def test_validation_room_not_found(self):
        """Rename for non-existent room should be invalid."""
        edit = RenameRoomEdit(segment_id=99, new_name="Kitchen")

        map_data = MagicMock()
        map_data.rooms = {16: MagicMock()}

        is_valid, error = edit.validate(map_data)
        assert is_valid is False
        assert "not found" in error

    def test_validation_empty_name(self):
        """Empty name should be invalid."""
        edit = RenameRoomEdit(segment_id=16, new_name="")

        map_data = MagicMock()
        map_data.rooms = {16: MagicMock()}

        is_valid, error = edit.validate(map_data)
        assert is_valid is False
        assert "empty" in error.lower()


class TestVirtualState:
    """Tests for VirtualState class."""

    def test_empty_state(self):
        state = VirtualState()
        assert state.has_pending_edits is False
        assert state.can_undo is False
        assert state.can_redo is False
        assert len(state) == 0

    async def test_add_edit_success(self):
        """Successfully adding an edit."""
        map_data = MagicMock()
        map_data.rooms = None
        map_data.charger = None

        state = VirtualState(map_data)
        edit = VirtualWallEdit(x1=100, y1=100, x2=200, y2=200)

        success, error = await state.add_edit(edit)
        assert success is True
        assert error is None
        assert len(state) == 1
        assert state.has_pending_edits is True
        assert state.can_undo is True

    async def test_add_edit_validation_failure(self):
        """Adding an invalid edit should fail."""
        map_data = MagicMock()
        map_data.charger = None

        state = VirtualState(map_data)
        edit = VirtualWallEdit(x1=100, y1=100, x2=100, y2=100)  # Zero length

        success, error = await state.add_edit(edit)
        assert success is False
        assert error is not None
        assert len(state) == 0

    async def test_undo_redo(self):
        """Undo and redo functionality."""
        map_data = MagicMock()
        map_data.rooms = None
        map_data.charger = None

        state = VirtualState(map_data)
        edit = VirtualWallEdit(x1=100, y1=100, x2=200, y2=200)
        await state.add_edit(edit)

        # Undo
        undone = await state.undo()
        assert undone is not None
        assert undone.edit_id == edit.edit_id
        assert len(state) == 0
        assert state.can_redo is True

        # Redo
        redone = await state.redo()
        assert redone is not None
        assert len(state) == 1
        assert state.can_redo is False

    async def test_undo_empty_stack(self):
        """Undo on empty stack should return None."""
        state = VirtualState()
        assert await state.undo() is None

    async def test_redo_empty_stack(self):
        """Redo on empty stack should return None."""
        state = VirtualState()
        assert await state.redo() is None

    async def test_clear(self):
        """Clear should reset all edits."""
        map_data = MagicMock()
        map_data.rooms = None
        map_data.charger = None

        state = VirtualState(map_data)
        await state.add_edit(VirtualWallEdit(x1=100, y1=100, x2=200, y2=200))
        await state.add_edit(NoGoZoneEdit(x1=0, y1=0, x2=100, y2=100))

        assert len(state) == 2
        await state.clear()
        assert len(state) == 0
        assert state.has_pending_edits is False

    async def test_get_edits_by_type(self):
        """Filter edits by type."""
        map_data = MagicMock()
        map_data.rooms = None
        map_data.charger = None

        state = VirtualState(map_data)
        await state.add_edit(VirtualWallEdit(x1=100, y1=100, x2=200, y2=200))
        await state.add_edit(NoGoZoneEdit(x1=0, y1=0, x2=100, y2=100))
        await state.add_edit(VirtualWallEdit(x1=300, y1=300, x2=400, y2=400))

        walls = state.get_edits_by_type(EditType.VIRTUAL_WALL)
        assert len(walls) == 2

        zones = state.get_edits_by_type(EditType.NO_GO_ZONE)
        assert len(zones) == 1

    async def test_structural_vs_additive_edits(self):
        """Correct classification of structural and additive edits."""
        map_data = MagicMock()
        # Set up room with actual coordinate values for intersection check
        room = MagicMock()
        room.x0 = 0
        room.x1 = 100
        room.y0 = 0
        room.y1 = 100
        map_data.rooms = {16: room, 17: room}
        map_data.charger = None

        state = VirtualState(map_data)

        # Structural edits
        await state.add_edit(SplitRoomEdit(segment_id=16, x1=50, y1=0, x2=50, y2=100))
        await state.add_edit(MergeRoomsEdit(segment_ids=[16, 17]))
        await state.add_edit(RenameRoomEdit(segment_id=16, new_name="Kitchen"))

        # Additive edits
        await state.add_edit(VirtualWallEdit(x1=100, y1=100, x2=200, y2=200))
        await state.add_edit(NoGoZoneEdit(x1=0, y1=0, x2=100, y2=100))

        structural = state.get_structural_edits()
        assert len(structural) == 3

        additive = state.get_additive_edits()
        assert len(additive) == 2

    async def test_to_dict(self):
        """Serialization to dict."""
        map_data = MagicMock()
        map_data.rooms = None
        map_data.charger = None

        state = VirtualState(map_data)
        await state.add_edit(VirtualWallEdit(x1=100, y1=100, x2=200, y2=200))

        data = state.to_dict()
        assert "edits" in data
        assert len(data["edits"]) == 1

    async def test_redo_stack_cleared_on_new_edit(self):
        """Adding new edit should clear redo stack."""
        map_data = MagicMock()
        map_data.rooms = None
        map_data.charger = None

        state = VirtualState(map_data)
        await state.add_edit(VirtualWallEdit(x1=100, y1=100, x2=200, y2=200))
        await state.undo()

        assert state.can_redo is True

        await state.add_edit(NoGoZoneEdit(x1=0, y1=0, x2=100, y2=100))
        assert state.can_redo is False
