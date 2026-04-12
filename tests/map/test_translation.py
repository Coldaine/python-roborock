"""Tests for Roborock map translation and remapping."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from roborock.map import (
    TranslationLayer,
    VirtualState,
    SplitRoomEdit,
    RenameRoomEdit,
    BoundingBox,
    Point,
)
from roborock.map.translation import TranslationResult


@pytest.fixture
def mock_command_trait():
    trait = MagicMock()
    trait.send = AsyncMock(return_value={"result": "ok"})
    return trait


@pytest.fixture
def mock_map_content():
    trait = MagicMock()
    trait.refresh = AsyncMock()
    trait.map_data = None
    return trait


@pytest.fixture
def base_map_data():
    """Create a mock MapData with one room."""
    map_data = MagicMock()
    map_data.map_flag = 1
    
    # Mock room 16: Square from (0,0) to (1000, 1000) in mm
    room16 = MagicMock()
    room16.x0, room16.y0 = 0, 0
    room16.x1, room16.y1 = 1000, 1000
    room16.name = "Original Room"
    
    map_data.rooms = {16: room16}
    
    # Mock image data
    map_data.image = MagicMock()
    map_data.image.dimensions = MagicMock()
    map_data.image.dimensions.top = 0
    map_data.image.dimensions.left = 0
    map_data.image.dimensions.scale = 1.0
    
    return map_data


@pytest.mark.asyncio
async def test_two_stage_sync_with_remapping(mock_command_trait, mock_map_content, base_map_data):
    """Test that room IDs are remapped between Stage 1 and Stage 2."""
    
    # 1. Setup VirtualState with a Split and a Rename
    from roborock.map import CoordinateTransformer
    transformer = CoordinateTransformer(0, 0, 1.0)
    
    state = VirtualState(base_map_data, transformer)
    
    # Split room 16
    split_edit = SplitRoomEdit(segment_id=16, x1=0, y1=500, x2=1000, y2=500)
    await state.add_edit(split_edit)

    # Rename room 16 (this should be remapped to a new ID after split)
    rename_edit = RenameRoomEdit(segment_id=16, new_name="New Kitchen", old_name="Original Room")
    await state.add_edit(rename_edit)
    
    # 2. Setup TranslationLayer
    layer = TranslationLayer(mock_command_trait, mock_map_content, protocol="v1")
    
    # 3. Mock the fresh map returned after structural sync
    # New map has two rooms (17 and 18) where 16 used to be
    new_map = MagicMock()
    new_map.map_flag = 1
    
    room17 = MagicMock()
    room17.x0, room17.y0 = 0, 0
    room17.x1, room17.y1 = 1000, 490  # Slightly smaller than half
    room17.name = "Segment 17"
    
    room18 = MagicMock()
    room18.x0, room18.y0 = 0, 510
    room18.x1, room18.y1 = 1000, 1000
    room18.name = "Segment 18"
    
    new_map.rooms = {17: room17, 18: room18}
    mock_map_content.map_data = new_map
    
    # 4. Execute edits
    results = await layer.execute_edits(state, map_flag=1)
    
    # 5. Assertions
    assert len(results) == 2
    assert results[0].success
    assert results[1].success
    
    # Check that the rename edit's segment_id was updated to 17 (due to overlap)
    # Room 17 (0,0 -> 1000,490) overlaps with old Room 16 (0,0 -> 1000,1000)
    assert rename_edit.segment_id == 17
    
    # Verify commands sent
    assert mock_command_trait.send.call_count == 2
    
    from roborock import RoborockCommand
    # First command: Split room 16
    # V1 Split: [map_flag, segment_id, x1, y1, x2, y2]
    mock_command_trait.send.assert_any_call(RoborockCommand.SPLIT_SEGMENT, [1, 16, 0, 500, 1000, 500])
    
    # Second command: Rename room 17 (remapped!)
    # V1 Rename: [map_flag, segment_id, "name"]
    mock_command_trait.send.assert_any_call(RoborockCommand.NAME_SEGMENT, [1, 17, "New Kitchen"])


@pytest.mark.asyncio
async def test_repopulate_no_map_content(mock_command_trait):
    """Test remapping behavior when MapContentTrait is missing."""
    layer = TranslationLayer(mock_command_trait, None, protocol="v1")
    state = MagicMock()
    state.has_pending_edits = True
    state.get_topology_edits.return_value = []
    state.get_property_edits.return_value = []
    state.get_additive_edits.return_value = []

    # Should not crash and should no-op when no edits exist.
    results = await layer.execute_edits(state, map_flag=1)
    assert results == []
    assert mock_command_trait.send.call_count == 0
