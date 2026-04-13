"""Tests for VirtualState persistence (save/load)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

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


@pytest.fixture
def mock_map_data():
    """Create a mock MapData for testing."""
    map_data = MagicMock()
    map_data.map_flag = 123
    
    # Create mock rooms
    room1 = MagicMock()
    room1.name = "Living Room"
    room1.x0 = 0
    room1.x1 = 100
    room1.y0 = 0
    room1.y1 = 100
    
    room2 = MagicMock()
    room2.name = "Kitchen"
    room2.x0 = 100
    room2.x1 = 200
    room2.y0 = 0
    room2.y1 = 100
    
    map_data.rooms = {16: room1, 17: room2}
    
    # Charger with concrete values (far from test walls)
    charger = MagicMock()
    charger.x = 10000  # Far away from test walls
    charger.y = 10000
    map_data.charger = charger
    
    map_data.vacuum_position = MagicMock()
    map_data.vacuum_position.x = 50
    map_data.vacuum_position.y = 50
    map_data.image = MagicMock()
    map_data.image.width = 800
    map_data.image.height = 600
    map_data.walls = []
    map_data.no_go_areas = []
    map_data.no_mop_areas = []
    
    return map_data


@pytest.fixture
def mock_transformer():
    """Create a mock CoordinateTransformer."""
    return MagicMock()


class TestVirtualStateSaveLoad:
    """Tests for VirtualState persistence."""

    async def test_virtual_state_save_load(self, mock_map_data, mock_transformer):
        """Test that save and load preserve edits correctly."""
        # Create initial state with some edits
        state = VirtualState(mock_map_data, mock_transformer)
        
        # Add edits
        edit1 = VirtualWallEdit(x1=100, y1=200, x2=300, y2=400)
        edit1.status = EditStatus.APPLIED
        await state.add_edit(edit1)
        
        edit2 = NoGoZoneEdit(x1=0, y1=0, x2=500, y2=500)
        edit2.status = EditStatus.APPLIED
        await state.add_edit(edit2)
        
        edit3 = RenameRoomEdit(segment_id=16, new_name="Dining Room", old_name="Living Room")
        edit3.status = EditStatus.APPLIED
        await state.add_edit(edit3)
        
        # Verify edits are in state
        assert len(state) == 3
        assert state.has_pending_edits
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            await state.save(temp_path)
            
            # Verify file exists and has content
            assert temp_path.exists()
            
            # Load the JSON and verify structure
            with open(temp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            assert "version" in data
            assert data["version"] == 1
            assert "edits" in data
            assert len(data["edits"]) == 3
            assert "map_flag" in data
            assert data["map_flag"] == 123
            assert "map_hash" in data
            assert "original_room_names" in data
            assert data["original_room_names"]["16"] == "Living Room"
            assert "timestamp" in data
            
            # Load into new state
            loaded_state = await VirtualState.load(temp_path, mock_map_data)
            
            # Verify loaded state matches original
            assert len(loaded_state) == 3
            assert loaded_state.has_pending_edits
            
            # Check edits are preserved
            edits = loaded_state.pending_edits
            assert len(edits) == 3
            
            # Verify edit types
            edit_types = [e.edit_type for e in edits]
            assert EditType.VIRTUAL_WALL in edit_types
            assert EditType.NO_GO_ZONE in edit_types
            assert EditType.RENAME_ROOM in edit_types
            
            # Verify specific edit data
            wall_edit = [e for e in edits if e.edit_type == EditType.VIRTUAL_WALL][0]
            assert wall_edit.x1 == 100
            assert wall_edit.y1 == 200
            assert wall_edit.x2 == 300
            assert wall_edit.y2 == 400
            
        finally:
            # Cleanup
            if temp_path.exists():
                temp_path.unlink()

    async def test_save_creates_directories(self, mock_map_data, mock_transformer):
        """Test that save creates parent directories if needed."""
        state = VirtualState(mock_map_data, mock_transformer)
        
        edit = VirtualWallEdit(x1=100, y1=100, x2=200, y2=200)
        await state.add_edit(edit)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = Path(tmpdir) / "nested" / "deep" / "state.json"
            
            await state.save(nested_path)
            
            assert nested_path.exists()

    async def test_load_detects_stale_state(self, mock_map_data, mock_transformer):
        """Test that load detects when map has changed."""
        # Create and save state
        state = VirtualState(mock_map_data, mock_transformer)
        edit = VirtualWallEdit(x1=100, y1=100, x2=200, y2=200)
        await state.add_edit(edit)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            await state.save(temp_path)
            
            # Modify the map data (simulate map change)
            mock_map_data.map_flag = 456  # Different map flag
            mock_map_data.rooms = {20: MagicMock()}  # Different rooms
            
            # Load should raise ValueError due to hash mismatch
            with pytest.raises(ValueError, match="hash mismatch"):
                await VirtualState.load(temp_path, mock_map_data)
                
        finally:
            if temp_path.exists():
                temp_path.unlink()

    async def test_load_detects_map_flag_change(self, mock_map_data, mock_transformer):
        """Test that load detects map flag changes (via hash mismatch)."""
        # Create and save state
        state = VirtualState(mock_map_data, mock_transformer)
        edit = VirtualWallEdit(x1=100, y1=100, x2=200, y2=200)
        await state.add_edit(edit)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            await state.save(temp_path)
            
            # Change map flag (this also changes hash since flag is part of hash)
            mock_map_data.map_flag = 456
            
            # Load should raise ValueError due to hash mismatch (flag is part of hash)
            with pytest.raises(ValueError, match="hash mismatch"):
                await VirtualState.load(temp_path, mock_map_data)
                
        finally:
            if temp_path.exists():
                temp_path.unlink()

    async def test_load_missing_file(self, mock_map_data):
        """Test that load raises FileNotFoundError for missing files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_path = Path(tmpdir) / "nonexistent.json"
            
            with pytest.raises(FileNotFoundError):
                await VirtualState.load(nonexistent_path, mock_map_data)

    async def test_save_empty_state(self, mock_map_data, mock_transformer):
        """Test saving an empty state."""
        state = VirtualState(mock_map_data, mock_transformer)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            await state.save(temp_path)
            
            # Load and verify
            loaded_state = await VirtualState.load(temp_path, mock_map_data)
            assert len(loaded_state) == 0
            assert not loaded_state.has_pending_edits
            
        finally:
            if temp_path.exists():
                temp_path.unlink()

    async def test_original_state_preserved(self, mock_map_data, mock_transformer):
        """Test that original room names and zones are preserved."""
        state = VirtualState(mock_map_data, mock_transformer)
        
        edit = VirtualWallEdit(x1=100, y1=100, x2=200, y2=200)
        await state.add_edit(edit)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            await state.save(temp_path)
            
            with open(temp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Verify original state is saved
            assert "original_room_names" in data
            assert data["original_room_names"]["16"] == "Living Room"
            assert data["original_room_names"]["17"] == "Kitchen"
            assert "original_walls" in data
            assert "original_no_go_zones" in data
            assert "original_mop_zones" in data
            
        finally:
            if temp_path.exists():
                temp_path.unlink()


class TestVirtualStateToDict:
    """Tests for VirtualState to_dict/from_dict."""

    def test_to_dict_structure(self, mock_map_data, mock_transformer):
        """Test that to_dict produces expected structure."""
        state = VirtualState(mock_map_data, mock_transformer)
        
        data = state.to_dict()
        
        assert "edits" in data
        assert "original_room_names" in data
        assert "original_walls" in data
        assert "original_no_go_zones" in data
        assert "original_mop_zones" in data
        assert "map_flag" in data
        assert "map_hash" in data

    def test_from_dict_reconstructs_state(self, mock_map_data, mock_transformer):
        """Test that from_dict reconstructs state correctly."""
        # Create original state
        original = VirtualState(mock_map_data, mock_transformer)
        
        # Get dict representation
        data = original.to_dict()
        
        # Reconstruct
        reconstructed = VirtualState.from_dict(data, mock_map_data, mock_transformer)
        
        # Verify
        assert reconstructed.map_flag == original.map_flag
        assert reconstructed.map_hash == original.map_hash
        assert reconstructed._original_room_names == original._original_room_names


class TestVirtualStateHash:
    """Tests for map hash calculation."""

    def test_calculate_map_hash_consistency(self, mock_map_data, mock_transformer):
        """Test that hash calculation is consistent."""
        state = VirtualState(mock_map_data, mock_transformer)
        
        hash1 = state._calculate_map_hash(mock_map_data)
        hash2 = state._calculate_map_hash(mock_map_data)
        
        assert hash1 == hash2
        assert hash1 is not None
        assert len(hash1) == 16  # MD5 truncated to 16 chars

    def test_calculate_map_hash_changes(self, mock_map_data, mock_transformer):
        """Test that hash changes with map data."""
        state = VirtualState(mock_map_data, mock_transformer)
        
        hash1 = state._calculate_map_hash(mock_map_data)
        
        # Modify map
        mock_map_data.map_flag = 999
        hash2 = state._calculate_map_hash(mock_map_data)
        
        assert hash1 != hash2

    def test_calculate_map_hash_none(self, mock_map_data, mock_transformer):
        """Test that hash returns None for None input."""
        state = VirtualState(mock_map_data, mock_transformer)
        
        result = state._calculate_map_hash(None)
        
        assert result is None
