"""API Translation Layer for Roborock map editing.

This module translates VirtualState changes into physical RoborockCommand RPC calls.
It handles:
- Protocol-specific payload formatting (V1 vs B01)
- Two-stage sync (structural then additive)
- Command batching and sequencing
"""

from __future__ import annotations

import asyncio
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

if TYPE_CHECKING:
    from roborock.devices.traits.v1.command import CommandTrait

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
        """Translate to SPLIT_ROOM command.

        V1 payload format:
        [segment_id, x1, y1, x2, y2]
        """
        params = [edit.segment_id, int(edit.x1), int(edit.y1), int(edit.x2), int(edit.y2)]
        return RoborockCommand.SPLIT_ROOM, params

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

    Implements the Two-Stage Sync pattern:
    1. Structural Sync: Split, merge, rename operations
    2. Additive Sync: Virtual walls, no-go zones

    This ordering is critical because structural changes destroy old Room IDs
    and create new ones.
    """

    def __init__(self, command_trait: CommandTrait, protocol: str = "v1") -> None:
        """Initialize the translation layer.

        Args:
            command_trait: The device's command trait for sending commands.
            protocol: Protocol version ("v1" or "b01_q7").
        """
        self._command = command_trait
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
        """Execute all pending edits using Two-Stage Sync.

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

        # Stage 1: Structural Sync
        structural_edits = virtual_state.get_structural_edits()
        if structural_edits:
            _LOGGER.info(f"Stage 1: Executing {len(structural_edits)} structural edits")
            for edit in structural_edits:
                result = await self._execute_edit(edit, map_flag)
                results.append(result)

                if not result.success:
                    _LOGGER.error(f"Structural edit failed: {result.error}")
                    # Stop on structural failure - remaining edits may be invalid
                    break

        # Intermediate: Check if we need to repopulate room IDs
        structural_success = all(r.success for r in results if r.edit in structural_edits)
        if structural_success and structural_edits:
            _LOGGER.info("Structural sync complete - room IDs may have changed")
            # TODO: Implement room ID remapping if needed

        # Stage 2: Additive Sync
        additive_edits = virtual_state.get_additive_edits()
        if additive_edits and structural_success:
            _LOGGER.info(f"Stage 2: Executing {len(additive_edits)} additive edits")
            for edit in additive_edits:
                result = await self._execute_edit(edit, map_flag)
                results.append(result)

                if not result.success:
                    _LOGGER.error(f"Additive edit failed: {result.error}")
                    # Continue on additive failure - they're independent

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
        """
        # Different protocols handle map binding differently
        if isinstance(params, dict):
            params["map_flag"] = map_flag
        elif isinstance(params, list):
            # For list params, we may need to wrap in a dict or prepend
            # This depends on the specific command - V1 often uses [map_flag, ...data]
            params = [map_flag] + params
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
                await self._command.send(RoborockCommand.MANUAL_BAK_MAP, [map_flag] if map_flag else [])
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
                await self._command.send(RoborockCommand.RECOVER_MAP, [map_flag] if map_flag else [])
            else:
                _LOGGER.warning("B01 protocol restore not supported")
                return False
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to restore map backup: {e}")
            return False
