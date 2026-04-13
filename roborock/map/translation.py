"""API Translation Layer for Roborock map editing.

This module translates VirtualState changes into physical RoborockCommand RPC calls.
It handles:
- Protocol-specific payload formatting (V1 vs B01)
- Three-stage sync (topology, property, then additive edits)
- Command batching and sequencing
"""

from __future__ import annotations

import asyncio
import copy
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from roborock.roborock_typing import RoborockB01Q7Methods, RoborockCommand

from .editor import (
    EditObject,
    EditStatus,
    EditType,
    MergeRoomsEdit,
    NoGoZoneEdit,
    RenameRoomEdit,
    SplitRoomEdit,
    VirtualWallEdit,
)
from .geometry import BoundingBox, calculate_room_overlap

if TYPE_CHECKING:
    from vacuum_map_parser_base.map_data import MapData

    from roborock.devices.traits.v1.command import CommandTrait
    from roborock.devices.traits.v1.map_content import MapContentTrait

    from .editor import VirtualState

_LOGGER = logging.getLogger(__name__)


@dataclass
class TranslationResult:
    """Result of translating and executing an edit."""

    success: bool
    edit: EditObject
    command: str | None = None
    params: Any = None
    error: str | None = None
    new_segment_ids: list[int] | None = None  # For split/merge operations


class ProtocolTranslator(ABC):
    """Abstract base for protocol-specific translation."""

    @abstractmethod
    def translate_virtual_wall(self, edit: VirtualWallEdit) -> tuple[str, Any]:
        """Translate virtual wall edit to command."""
        ...

    @abstractmethod
    def translate_no_go_zone(self, edit: NoGoZoneEdit) -> tuple[str, Any]:
        """Translate no-go zone edit to command."""
        ...

    @abstractmethod
    def translate_split_room(self, edit: SplitRoomEdit) -> tuple[str, Any]:
        """Translate room split edit to command."""
        ...

    @abstractmethod
    def translate_merge_rooms(self, edit: MergeRoomsEdit) -> tuple[str, Any]:
        """Translate room merge edit to command."""
        ...

    @abstractmethod
    def translate_rename_room(self, edit: RenameRoomEdit) -> tuple[str, Any]:
        """Translate room rename edit to command."""
        ...


class V1ProtocolTranslator(ProtocolTranslator):
    """Translator for V1 protocol commands."""

    def translate_virtual_wall(self, edit: VirtualWallEdit) -> tuple[str, Any]:
        """Translate to SET_VIRTUAL_WALL command.

        V1 payload format (inferred):
        {
            "map_flag": int,
            "walls": [[x1, y1, x2, y2], ...]
        }
        """
        # V1 uses the full map update approach
        wall_data = [int(edit.x1), int(edit.y1), int(edit.x2), int(edit.y2)]
        return RoborockCommand.SET_VIRTUAL_WALL, [wall_data]

    def translate_no_go_zone(self, edit: NoGoZoneEdit) -> tuple[str, Any]:
        """Translate to SET_NO_GO_ZONES command."""
        zone_data = [int(edit.x1), int(edit.y1), int(edit.x2), int(edit.y2)]
        return RoborockCommand.SET_NO_GO_ZONES, [zone_data]

    def translate_split_room(self, edit: SplitRoomEdit) -> tuple[str, Any]:
        """Translate to SPLIT_SEGMENT command.

        V1 payload format:
        [segment_id, x1, y1, x2, y2]
        """
        params = [edit.segment_id, int(edit.x1), int(edit.y1), int(edit.x2), int(edit.y2)]
        return RoborockCommand.SPLIT_SEGMENT, params

    def translate_merge_rooms(self, edit: MergeRoomsEdit) -> tuple[str, Any]:
        """Translate to MERGE_SEGMENT command.

        V1 payload format:
        [segment_id1, segment_id2, ...]
        """
        return RoborockCommand.MERGE_SEGMENT, edit.segment_ids

    def translate_rename_room(self, edit: RenameRoomEdit) -> tuple[str, Any]:
        """Translate to NAME_SEGMENT command.

        V1 payload format:
        [segment_id, "name"]
        """
        return RoborockCommand.NAME_SEGMENT, [edit.segment_id, edit.new_name]


class B01Q7ProtocolTranslator(ProtocolTranslator):
    """Translator for B01 Q7 protocol commands."""

    def translate_virtual_wall(self, edit: VirtualWallEdit) -> tuple[str, Any]:
        """Translate to service.set_virtual_wall command."""
        # B01 uses different command structure
        wall_data = {
            "x1": int(edit.x1),
            "y1": int(edit.y1),
            "x2": int(edit.x2),
            "y2": int(edit.y2),
        }
        return RoborockB01Q7Methods.SET_VIRTUAL_WALL, wall_data

    def translate_no_go_zone(self, edit: NoGoZoneEdit) -> tuple[str, Any]:
        """Translate to service.set_zone_points command."""
        zone_data = {
            "x1": int(edit.x1),
            "y1": int(edit.y1),
            "x2": int(edit.x2),
            "y2": int(edit.y2),
        }
        return RoborockB01Q7Methods.SET_ZONE_POINTS, zone_data

    def translate_split_room(self, edit: SplitRoomEdit) -> tuple[str, Any]:
        """Translate to service.split_room command."""
        params = {
            "segment_id": edit.segment_id,
            "x1": int(edit.x1),
            "y1": int(edit.y1),
            "x2": int(edit.x2),
            "y2": int(edit.y2),
        }
        return RoborockB01Q7Methods.SPLIT_ROOM, params

    def translate_merge_rooms(self, edit: MergeRoomsEdit) -> tuple[str, Any]:
        """B01 may not support merge, or uses different command."""
        # B01 doesn't have a direct merge command; may need to use different approach
        _LOGGER.warning("B01 protocol may not support room merge directly")
        return RoborockB01Q7Methods.ARRANGE_ROOM, {"segment_ids": edit.segment_ids}

    def translate_rename_room(self, edit: RenameRoomEdit) -> tuple[str, Any]:
        """Translate to service.rename_room command."""
        return RoborockB01Q7Methods.RENAME_ROOM, {
            "segment_id": edit.segment_id,
            "name": edit.new_name,
        }


class TranslationLayer:
    """Translates VirtualState changes to device commands.

    Implements the Three-Stage Sync pattern:
    1. Topology Sync: Split and merge operations
    2. Property Sync: Rename operations after room ID remapping
    3. Additive Sync: Virtual walls and no-go zones

    This ordering is critical because topology changes destroy old Room IDs
    and create new ones.
    """

    def __init__(
        self,
        command_trait: CommandTrait,
        map_content_trait: MapContentTrait | None = None,
        protocol: str = "v1",
    ) -> None:
        """Initialize the translation layer.

        Args:
            command_trait: The device's command trait for sending commands.
            map_content_trait: Trait for fetching map content (for ID remapping).
            protocol: Protocol version ("v1" or "b01_q7").
        """
        self._command = command_trait
        self._map_content = map_content_trait
        self._protocol = protocol

        # Select appropriate translator
        if protocol == "v1":
            self._translator: ProtocolTranslator = V1ProtocolTranslator()
        elif protocol == "b01_q7":
            self._translator = B01Q7ProtocolTranslator()
        else:
            raise ValueError(f"Unsupported protocol: {protocol}")

    async def execute_edits(
        self,
        virtual_state: VirtualState,
        map_flag: int | None = None,
    ) -> list[TranslationResult]:
        """Execute all pending edits using Three-Stage Sync.

        Args:
            virtual_state: The virtual state containing pending edits.
            map_flag: The map flag to bind commands to (for multi-floor safety).

        Returns:
            List of results for each edit operation.
        """
        results: list[TranslationResult] = []

        if not virtual_state.has_pending_edits:
            _LOGGER.debug("No pending edits to execute")
            return results

        # Stage 1: Topology Sync (ID destroying: split/merge)
        topology_edits = [edit for edit in virtual_state.get_topology_edits() if edit.status == EditStatus.APPLIED]
        if topology_edits:
            _LOGGER.info(f"Stage 1: Executing {len(topology_edits)} topology edits")
            for edit in topology_edits:
                result = await self._execute_edit(edit, map_flag)
                results.append(result)

                if not result.success:
                    _LOGGER.error(f"Topology edit failed: {result.error}")
                    # Stop on topology failure - remaining edits may be invalid
                    break

        # Intermediate: Check if we need to repopulate room IDs
        topology_success = all(r.success for r in results if r.edit in topology_edits)
        if topology_success and topology_edits and self._map_content:
            _LOGGER.info("Topology sync complete - room IDs may have changed")
            await self._repopulate_room_ids(virtual_state)

        # Stage 2: Property Sync (ID dependent: rename)
        property_edits = [edit for edit in virtual_state.get_property_edits() if edit.status == EditStatus.APPLIED]
        if property_edits and topology_success:
            _LOGGER.info(f"Stage 2: Executing {len(property_edits)} property edits")
            for edit in property_edits:
                result = await self._execute_edit(edit, map_flag)
                results.append(result)

        # Stage 3: Additive Sync (Absolute coordinates: walls/zones)
        additive_edits = [edit for edit in virtual_state.get_additive_edits() if edit.status == EditStatus.APPLIED]
        if additive_edits and topology_success:
            _LOGGER.info(f"Stage 3: Executing {len(additive_edits)} additive edits")

            if self._protocol == "v1":
                # V1 requires batching additive edits as they overwrite the entire state
                batch_results = await self._execute_v1_additive_batch(virtual_state, additive_edits, map_flag)
                results.extend(batch_results)
            else:
                # B01 might support individual updates (verify)
                for edit in additive_edits:
                    result = await self._execute_edit(edit, map_flag)
                    results.append(result)

        return results

    async def _execute_v1_additive_batch(
        self,
        virtual_state: VirtualState,
        edits: list[EditObject],
        map_flag: int | None,
    ) -> list[TranslationResult]:
        """Execute additive edits as a batch for V1 protocol.
        
        V1 commands like set_virtual_wall overwrite the entire list,
        so we must combine new edits with existing state.
        """
        results: list[TranslationResult] = []
        pending_walls = [e for e in edits if isinstance(e, VirtualWallEdit) and e.status == EditStatus.APPLIED]
        pending_zones = [e for e in edits if isinstance(e, NoGoZoneEdit) and e.status == EditStatus.APPLIED]
        pending_mop_zones = [e for e in edits if e.edit_type == EditType.MOP_FORBIDDEN_ZONE and e.status == EditStatus.APPLIED]
        
        # 1. Handle Virtual Walls
        if pending_walls:
            # Combine original walls with new ones
            all_walls = list(virtual_state._original_walls)
            for wall in pending_walls:
                all_walls.append((wall.x1, wall.y1, wall.x2, wall.y2))
            
            # Format: [map_flag, [[x1, y1, x2, y2], ...]]
            params = [list(w) for w in all_walls]
            if map_flag is not None:
                params = [map_flag, params]
            
            try:
                _LOGGER.debug(f"Sending V1 wall batch: {params}")
                await self._command.send(RoborockCommand.SET_VIRTUAL_WALL, params)
                for edit in pending_walls:
                    edit.status = EditStatus.SYNCED
                    results.append(TranslationResult(success=True, edit=edit))
            except Exception as e:
                _LOGGER.error(f"Failed to sync wall batch: {e}")
                for edit in pending_walls:
                    edit.status = EditStatus.FAILED
                    results.append(TranslationResult(success=False, edit=edit, error=str(e)))

        # 2. Handle No-Go Zones
        if pending_zones:
            # Combine original zones with new ones
            all_zones = list(virtual_state._original_no_go_zones)
            for zone in pending_zones:
                all_zones.append((zone.x1, zone.y1, zone.x2, zone.y2))
            
            # Format: [map_flag, [[x1, y1, x2, y2], ...]]
            params = [list(z) for z in all_zones]
            if map_flag is not None:
                params = [map_flag, params]
                
            try:
                _LOGGER.debug(f"Sending V1 zone batch: {params}")
                await self._command.send(RoborockCommand.SET_NO_GO_ZONES, params)
                for edit in pending_zones:
                    edit.status = EditStatus.SYNCED
                    results.append(TranslationResult(success=True, edit=edit))
            except Exception as e:
                _LOGGER.error(f"Failed to sync zone batch: {e}")
                for edit in pending_zones:
                    edit.status = EditStatus.FAILED
                    results.append(TranslationResult(success=False, edit=edit, error=str(e)))

        # 3. Handle Mop Forbidden Zones
        if pending_mop_zones:
            # Combine original mop zones with new ones
            all_mop_zones = list(virtual_state._original_mop_zones)
            for zone in pending_mop_zones:
                # Mop zones are typically same 4-coord format
                if hasattr(zone, 'x1'):
                    all_mop_zones.append((zone.x1, zone.y1, zone.x2, zone.y2))
            
            params = [list(z) for z in all_mop_zones]
            if map_flag is not None:
                params = [map_flag, params]
                
            try:
                _LOGGER.debug(f"Sending V1 mop zone batch: {params}")
                await self._command.send(RoborockCommand.SET_MOP_FORBIDDEN_ZONE, params)
                for edit in pending_mop_zones:
                    edit.status = EditStatus.SYNCED
                    results.append(TranslationResult(success=True, edit=edit))
            except Exception as e:
                _LOGGER.error(f"Failed to sync mop zone batch: {e}")
                for edit in pending_mop_zones:
                    edit.status = EditStatus.FAILED
                    results.append(TranslationResult(success=False, edit=edit, error=str(e)))
                    
        return results

    async def _execute_edit(
        self,
        edit: EditObject,
        map_flag: int | None = None,
    ) -> TranslationResult:
        """Execute a single edit.

        Args:
            edit: The edit to execute.
            map_flag: The map flag for multi-floor binding.

        Returns:
            TranslationResult with execution status.
        """
        # Translate edit to command
        command, params = self._translate(edit)

        if command is None:
            return TranslationResult(
                success=False,
                edit=edit,
                error="Translation failed - unsupported edit type",
            )

        # Bind to map flag if provided (Risk Mitigation §6: Multi-Floor Context)
        if map_flag is not None:
            params = self._bind_to_map(params, map_flag)

        # Update status
        edit.status = EditStatus.SYNCING

        try:
            # Send command
            _LOGGER.debug(f"Sending command: {command} with params: {params}")
            response = await self._command.send(command, params)

            # Handle response
            if isinstance(response, dict) and "error" in response:
                edit.status = EditStatus.FAILED
                return TranslationResult(
                    success=False,
                    edit=edit,
                    command=command,
                    params=params,
                    error=response["error"],
                )

            edit.status = EditStatus.SYNCED
            return TranslationResult(
                success=True,
                edit=edit,
                command=command,
                params=params,
            )

        except Exception as e:
            edit.status = EditStatus.FAILED
            _LOGGER.exception(f"Command execution failed: {e}")
            return TranslationResult(
                success=False,
                edit=edit,
                command=command,
                params=params,
                error=str(e),
            )

    def _translate(self, edit: EditObject) -> tuple[str | None, Any]:
        """Translate an edit to command and params."""
        if isinstance(edit, VirtualWallEdit):
            return self._translator.translate_virtual_wall(edit)
        elif isinstance(edit, NoGoZoneEdit):
            return self._translator.translate_no_go_zone(edit)
        elif isinstance(edit, SplitRoomEdit):
            return self._translator.translate_split_room(edit)
        elif isinstance(edit, MergeRoomsEdit):
            return self._translator.translate_merge_rooms(edit)
        elif isinstance(edit, RenameRoomEdit):
            return self._translator.translate_rename_room(edit)
        else:
            _LOGGER.warning(f"Unsupported edit type: {edit.edit_type}")
            return None, None

    def _bind_to_map(self, params: Any, map_flag: int) -> Any:
        """Bind command parameters to a specific map flag.

        This ensures commands apply to the correct floor in multi-map setups.

        This is a pure function - it does not mutate the input params.
        """
        # Create a deep copy to avoid mutating the original input
        params = copy.deepcopy(params)

        # Different protocols handle map binding differently
        if isinstance(params, dict):
            # Prevent double-wrapping by checking if already bound
            if params.get("map_flag") != map_flag:
                params["map_flag"] = map_flag
        elif isinstance(params, list):
            # Translator-produced list payloads are unbound, so always prepend.
            params = [map_flag] + params
        # For other types (primitives, None, etc.), return as-is with map_flag wrapped in a list
        elif params is not None:
            params = [map_flag, params]
        else:
            params = [map_flag]

        return params

    async def create_map_backup(self, map_flag: int | None = None) -> bool:
        """Create a map backup for rollback support.

        Args:
            map_flag: The map to backup.

        Returns:
            True if backup was created successfully.
        """
        try:
            if self._protocol == "v1":
                await self._command.send(RoborockCommand.MANUAL_BAK_MAP, [map_flag] if map_flag is not None else [])
            else:
                # B01 may not support explicit backup
                _LOGGER.warning("B01 protocol backup not supported")
                return False
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to create map backup: {e}")
            return False

    async def restore_map_backup(self, map_flag: int | None = None) -> bool:
        """Restore map from backup.

        Args:
            map_flag: The map to restore.

        Returns:
            True if restore was successful.
        """
        try:
            if self._protocol == "v1":
                await self._command.send(RoborockCommand.RECOVER_MAP, [map_flag] if map_flag is not None else [])
            else:
                _LOGGER.warning("B01 protocol restore not supported")
                return False
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to restore map backup: {e}")
            return False

    async def _repopulate_room_ids(self, virtual_state: VirtualState) -> None:
        """Fetch fresh map and remap old Room IDs to new ones.

        This is used between Stage 1 and Stage 2 of the Three-Stage Sync
        to ensure subsequent edits (like renames or zones) use the correct
        segment IDs after a split or merge operation.
        """
        if not self._map_content:
            return

        # 1. Save old room data (from virtual_state's base_map)
        if virtual_state._base_map is None or not virtual_state._base_map.rooms:
            _LOGGER.warning("Cannot remap rooms: No base map data available")
            return
        
        old_rooms = virtual_state._base_map.rooms

        # 2. Fetch fresh map data from device
        try:
            _LOGGER.info("Refreshing map for room ID remapping...")
            await self._map_content.refresh()
            new_map = self._map_content.map_data
            if not new_map or not new_map.rooms:
                _LOGGER.warning("Fresh map has no rooms, cannot remap")
                return
            
            new_rooms = new_map.rooms
        except Exception as e:
            _LOGGER.error(f"Failed to refresh map for remapping: {e}")
            return

        # 3. Build spatial mapping (Old ID -> List of New IDs)
        id_map: dict[int, list[int]] = {}
        for old_id, old_room in old_rooms.items():
            old_bbox = BoundingBox(min_x=old_room.x0, max_x=old_room.x1, min_y=old_room.y0, max_y=old_room.y1)
            
            for new_id, new_room in new_rooms.items():
                new_bbox = BoundingBox(min_x=new_room.x0, max_x=new_room.x1, min_y=new_room.y0, max_y=new_room.y1)
                
                # Check overlap
                overlap = calculate_room_overlap(old_bbox, new_bbox)
                if overlap > 0.4:  # Catch splits (~0.5 overlap)
                    if old_id not in id_map:
                        id_map[old_id] = []
                    id_map[old_id].append(new_id)

        if not id_map:
            _LOGGER.info("No room ID changes detected")
            return

        _LOGGER.debug(f"Room ID remapping table: {id_map}")

        # 4. Update pending edits in VirtualState
        # Property edits (rename) depend on current segment IDs.
        # Additive edits (walls/zones) use absolute mm and don't need remapping.
        pending_property = virtual_state.get_property_edits()
        for edit in pending_property:
            if edit.status != EditStatus.APPLIED:
                continue

            if isinstance(edit, RenameRoomEdit):
                if edit.segment_id in id_map:
                    # Pick the best match (first one for now)
                    new_id = id_map[edit.segment_id][0]
                    _LOGGER.info(f"Remapping RenameRoomEdit: {edit.segment_id} -> {new_id}")
                    edit.segment_id = new_id

        # Topology edits could also be chained, though less common in a single batch.
        pending_topology = virtual_state.get_topology_edits()
        for edit in pending_topology:
            if edit.status != EditStatus.APPLIED:
                continue
            
            if isinstance(edit, SplitRoomEdit):
                if edit.segment_id in id_map:
                    new_id = id_map[edit.segment_id][0]
                    _LOGGER.info(f"Remapping SplitRoomEdit: {edit.segment_id} -> {new_id}")
                    edit.segment_id = new_id
            
            elif isinstance(edit, MergeRoomsEdit):
                new_segment_ids = []
                for old_id in edit.segment_ids:
                    if old_id in id_map:
                        new_segment_ids.append(id_map[old_id][0])
                    else:
                        new_segment_ids.append(old_id)
                
                if new_segment_ids != edit.segment_ids:
                    _LOGGER.info(f"Remapping MergeRoomsEdit: {edit.segment_ids} -> {new_segment_ids}")
                    edit.segment_ids = new_segment_ids

        # 5. Update the base map for the VirtualState so subsequent matches are correct
        # This is important if we're doing multiple rounds or just to keep state consistent.
        await virtual_state.refresh_base_map(new_map)
        _LOGGER.info("Refreshed VirtualState base map after remapping")
