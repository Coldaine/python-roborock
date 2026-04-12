"""End-to-end tests for the map editor using mock MQTT translation."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from roborock.devices.traits.v1.command import CommandTrait
from roborock.devices.traits.v1.map_content import MapContentTrait
from roborock.map.editor import EditStatus, VirtualState
from roborock.map.translation import TranslationLayer
from roborock.roborock_typing import RoborockCommand
from vacuum_map_parser_base.map_data import MapData, Room
from vacuum_map_parser_roborock.map_data_parser import RoborockMapDataParser


@pytest.fixture
def real_map_data() -> MapData:
    """Load a real map payload to test parsing and translation."""
    # We create a dummy map payload for testing since we don't have the raw binary bytes handy.
    # However, we can construct a valid MapData object simulating what the parser would output.
    map_data = MapData(123, 456)
    map_data.map_flag = 2
    map_data.rooms = {
        10: Room(100, 100, 200, 200, 10),
        11: Room(200, 100, 300, 200, 11),
    }
    # Simulate parser offsets
    map_data.image = MagicMock()
    map_data.image.dimensions.top = 10
    map_data.image.dimensions.left = 20
    map_data.image.dimensions.scale = 1.0
    return map_data


@pytest.mark.asyncio
async def test_v1_three_stage_sync_with_rollback(real_map_data: MapData):
    """Test the complete Two/Three-Stage Sync with a mock CommandTrait."""
    # 1. Setup Mocks
    mock_command_trait = AsyncMock(spec=CommandTrait)
    # Simulate a successful response for standard commands
    mock_command_trait.send.return_value = ["ok"]

    mock_map_content_trait = AsyncMock(spec=MapContentTrait)
    mock_map_content_trait.map_data = real_map_data

    # 2. Initialize the State Machine and Translation Layer
    virtual_state = VirtualState(real_map_data)
    translation = TranslationLayer(
        command_trait=mock_command_trait,
        map_content_trait=mock_map_content_trait,
        protocol="v1",
    )

    from roborock.map.editor import SplitRoomEdit, RenameRoomEdit, VirtualWallEdit
    
    # 3. Create a batch of edits (Topology, Property, and Additive)
    # Edit 1: Split Room 10
    virtual_state.add_edit(SplitRoomEdit(
        segment_id=10,
        x1=150, y1=100,
        x2=150, y2=200
    ))
    # Edit 2: Rename Room 11
    virtual_state.add_edit(RenameRoomEdit(
        segment_id=11,
        old_name="Room 11",
        new_name="Kitchen"
    ))
    # Edit 3: Add a Virtual Wall
    virtual_state.add_edit(VirtualWallEdit(
        x1=100, y1=100,
        x2=200, y2=200
    ))

    # 4. Simulate CLI Execution Flow (from _execute_edit)
    map_flag = real_map_data.map_flag

    # Step A: Create Backup
    await translation.create_map_backup(map_flag)
    mock_command_trait.send.assert_any_call(RoborockCommand.MANUAL_BAK_MAP, [2])
    
    # Step B: Execute Edits
    results = await translation.execute_edits(virtual_state, map_flag)
    
    # Verify all results are successful
    assert all(r.success for r in results)
    
    # Verify the sequence of MQTT (CommandTrait) calls
    # 1. Topology Sync (Split Room 10)
    # 2. Property Sync (Rename Room 11)
    # 3. Additive Sync (Virtual Wall Batch)
    calls = mock_command_trait.send.call_args_list
    
    # Assert manual backup was called first
    assert calls[0][0][0] == RoborockCommand.MANUAL_BAK_MAP
    
    # Assert Split Segment was called next
    assert calls[1][0][0] == RoborockCommand.SPLIT_SEGMENT
    assert calls[1][0][1] == [2, 10, 150, 100, 150, 200]  # Note: map_flag 2 is injected by _bind_to_map
    
    # Assert Rename Room was called next
    assert calls[2][0][0] == RoborockCommand.NAME_SEGMENT
    assert calls[2][0][1] == [2, 11, "Kitchen"]
    
    # Assert Virtual Wall batch was called last
    assert calls[3][0][0] == RoborockCommand.SET_VIRTUAL_WALL
    assert calls[3][0][1] == [2, [[100, 100, 200, 200]]]
    
    # Step C: Trigger Rollback via failure injection
    # Clear the mocks and add a failing edit
    mock_command_trait.reset_mock()
    mock_command_trait.send.side_effect = Exception("Simulated network failure")
    
    virtual_state.add_edit(VirtualWallEdit(x1=0, y1=0, x2=10, y2=10))
    
    # We simulate what the CLI does upon checking result.success:
    results = await translation.execute_edits(virtual_state, map_flag)
    assert not all(r.success for r in results)
        
    await translation.restore_map_backup(map_flag)
    
    # Assert restore backup was called
    mock_command_trait.send.assert_any_call(RoborockCommand.RECOVER_MAP, [2])
