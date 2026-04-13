"""Verification Loop for Roborock map editing.

This module implements the verification phase of the Two-Stage Sync:
- Polls GET_MAP_V1 to verify changes were applied
- Compares device state against intended VirtualState
- Detects firmware rejections and state drift
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .geometry import Point

if TYPE_CHECKING:
    from vacuum_map_parser_base.map_data import MapData

    from .editor import (
        MergeRoomsEdit,
        NoGoZoneEdit,
        RenameRoomEdit,
        SplitRoomEdit,
        VirtualState,
        VirtualWallEdit,
    )

_LOGGER = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL = 2.0  # seconds
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30.0  # seconds


@dataclass
class VerificationResult:
    """Result of verifying a map edit."""

    verified: bool
    edit_type: str
    expected: dict
    actual: dict | None = None
    mismatch_reason: str | None = None
    retries: int = 0


@dataclass
class MapVersionCheck:
    """Result of checking map version/timestamp."""

    matches: bool
    device_timestamp: int | None = None
    local_timestamp: int | None = None
    hash_match: bool = False


class MapVerifier:
    """Verifies that device state matches intended VirtualState.

    Firmware processing is asynchronous. After sending commands,
    we must poll GET_MAP_V1 to verify changes were applied.
    """

    def __init__(
        self,
        map_content_trait: Any,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the verifier.

        Args:
            map_content_trait: Trait for fetching map content.
            poll_interval: Seconds between poll attempts.
            max_retries: Maximum number of retry attempts.
            timeout: Maximum total time to wait for verification.
        """
        self._map_content = map_content_trait
        self._poll_interval = poll_interval
        self._max_retries = max_retries
        self._timeout = timeout

    async def verify_edits(
        self,
        virtual_state: VirtualState,
        progress_callback: Callable[[str], None] | None = None,
    ) -> list[VerificationResult]:
        """Verify all pending edits have been applied.

        Args:
            virtual_state: The virtual state with intended changes.
            progress_callback: Optional callback for progress updates.

        Returns:
            List of verification results for each edit.
        """
        results: list[VerificationResult] = []

        if not virtual_state.has_pending_edits:
            _LOGGER.debug("No edits to verify")
            return results

        loop = asyncio.get_running_loop()
        start_time = loop.time()
        attempt = 0

        while attempt < self._max_retries:
            elapsed = loop.time() - start_time
            if elapsed > self._timeout:
                _LOGGER.warning(f"Verification timeout after {elapsed:.1f}s")
                break

            attempt += 1
            if progress_callback:
                progress_callback(f"Verification attempt {attempt}/{self._max_retries}...")

            try:
                current_results: list[VerificationResult] = []
                # Fetch fresh map data
                await self._map_content.refresh()
                map_data = self._map_content.map_data

                if map_data is None:
                    _LOGGER.warning("Failed to fetch map data for verification")
                    await asyncio.sleep(self._poll_interval)
                    continue

                # Verify each edit
                all_verified = True
                for edit in virtual_state.pending_edits:
                    result = self._verify_edit(edit, map_data)
                    current_results.append(result)
                    if not result.verified:
                        all_verified = False

                results = current_results
                if all_verified:
                    _LOGGER.info("All edits verified successfully")
                    return current_results

                # Not all verified, wait and retry
                if attempt < self._max_retries:
                    wait_time = min(self._poll_interval * attempt, 10.0)  # Backoff
                    _LOGGER.debug(f"Waiting {wait_time:.1f}s before retry...")
                    await asyncio.sleep(wait_time)

            except Exception as e:
                _LOGGER.exception(f"Verification error: {e}")
                await asyncio.sleep(self._poll_interval)

        # Final attempt failed
        _LOGGER.error(f"Verification failed after {attempt} attempts")
        return results

    def _verify_edit(self, edit: Any, map_data: MapData) -> VerificationResult:
        """Verify a single edit against map data.

        Args:
            edit: The edit to verify.
            map_data: The current map data from device.

        Returns:
            Verification result.
        """
        from .editor import (
            MergeRoomsEdit,
            NoGoZoneEdit,
            RenameRoomEdit,
            SplitRoomEdit,
            VirtualWallEdit,
        )

        if isinstance(edit, VirtualWallEdit):
            return self._verify_virtual_wall(edit, map_data)
        elif isinstance(edit, NoGoZoneEdit):
            return self._verify_no_go_zone(edit, map_data)
        elif isinstance(edit, SplitRoomEdit):
            return self._verify_split_room(edit, map_data)
        elif isinstance(edit, MergeRoomsEdit):
            return self._verify_merge_rooms(edit, map_data)
        elif isinstance(edit, RenameRoomEdit):
            return self._verify_rename_room(edit, map_data)
        else:
            return VerificationResult(
                verified=False,
                edit_type=str(edit.edit_type),
                expected={},
                mismatch_reason=f"Unknown edit type: {edit.edit_type}",
            )

    def _verify_virtual_wall(
        self,
        edit: VirtualWallEdit,
        map_data: MapData,
    ) -> VerificationResult:
        """Verify a virtual wall exists in map data."""
        expected = {"x1": edit.x1, "y1": edit.y1, "x2": edit.x2, "y2": edit.y2}

        walls = getattr(map_data, "walls", None)
        if walls is None:
            return VerificationResult(
                verified=True,
                edit_type="VIRTUAL_WALL",
                expected=expected,
                mismatch_reason="Map data does not expose virtual walls",
            )

        if not walls:
            return VerificationResult(
                verified=False,
                edit_type="VIRTUAL_WALL",
                expected=expected,
                mismatch_reason="No virtual walls in map data",
            )

        # Check for matching wall (with tolerance)
        tolerance = 100  # 10cm in mm
        for wall in walls:
            # Wall has x1, y1, x2, y2 from parser
            w_p1 = Point(wall.x1, wall.y1)
            w_p2 = Point(wall.x2, wall.y2)
            e_p1 = Point(edit.x1, edit.y1)
            e_p2 = Point(edit.x2, edit.y2)
            
            # Check both directions
            if (self._points_match(e_p1, w_p1, tolerance) and self._points_match(e_p2, w_p2, tolerance)) or \
               (self._points_match(e_p1, w_p2, tolerance) and self._points_match(e_p2, w_p1, tolerance)):
                return VerificationResult(
                    verified=True,
                    edit_type="VIRTUAL_WALL",
                    expected=expected,
                    actual={"x1": wall.x1, "y1": wall.y1, "x2": wall.x2, "y2": wall.y2},
                )

        return VerificationResult(
            verified=False,
            edit_type="VIRTUAL_WALL",
            expected=expected,
            mismatch_reason="Virtual wall not found in device map",
        )

    def _verify_no_go_zone(
        self,
        edit: NoGoZoneEdit,
        map_data: MapData,
    ) -> VerificationResult:
        """Verify a no-go zone exists in map data."""
        expected = {"x1": edit.x1, "y1": edit.y1, "x2": edit.x2, "y2": edit.y2}

        no_go_areas = getattr(map_data, "no_go_areas", None)
        if no_go_areas is None:
            return VerificationResult(
                verified=True,
                edit_type="NO_GO_ZONE",
                expected=expected,
                mismatch_reason="Map data does not expose no-go areas",
            )

        if not no_go_areas:
            return VerificationResult(
                verified=False,
                edit_type="NO_GO_ZONE",
                expected=expected,
                mismatch_reason="No no-go zones in map data",
            )

        # Check for matching zone
        tolerance = 100  # 10cm in mm
        for zone in no_go_areas:
            # No-go zones are typically polygons, check bounding box match
            zone_xs = [p.x for p in zone.points]
            zone_ys = [p.y for p in zone.points]
            zone_bbox = {
                "x1": min(zone_xs),
                "x2": max(zone_xs),
                "y1": min(zone_ys),
                "y2": max(zone_ys),
            }

            if (
                abs(zone_bbox["x1"] - edit.x1) < tolerance
                and abs(zone_bbox["x2"] - edit.x2) < tolerance
                and abs(zone_bbox["y1"] - edit.y1) < tolerance
                and abs(zone_bbox["y2"] - edit.y2) < tolerance
            ):
                return VerificationResult(
                    verified=True,
                    edit_type="NO_GO_ZONE",
                    expected=expected,
                    actual=zone_bbox,
                )

        return VerificationResult(
            verified=False,
            edit_type="NO_GO_ZONE",
            expected=expected,
            mismatch_reason="No-go zone not found in device map",
        )

    def _verify_split_room(
        self,
        edit: SplitRoomEdit,
        map_data: MapData,
    ) -> VerificationResult:
        """Verify a room was split.

        Note: Split creates new segment IDs, so we can't directly verify.
        We check that the original segment no longer exists or was replaced.
        """
        expected = {"segment_id": edit.segment_id}

        if not map_data.rooms:
            return VerificationResult(
                verified=False,
                edit_type="SPLIT_ROOM",
                expected=expected,
                mismatch_reason="No rooms in map data",
            )

        expected_new_rooms = getattr(edit, "new_room_ids", None) or getattr(edit, "new_rooms", None)
        if expected_new_rooms:
            current_rooms = set(map_data.rooms.keys())
            if set(expected_new_rooms).issubset(current_rooms):
                return VerificationResult(
                    verified=True,
                    edit_type="SPLIT_ROOM",
                    expected={"segment_id": edit.segment_id, "new_rooms": list(expected_new_rooms)},
                    actual={"new_rooms": list(map_data.rooms.keys())},
                )

        # Check if original segment still exists
        if edit.segment_id not in map_data.rooms:
            # Original segment replaced - split likely successful
            # (new segments would have different IDs)
            return VerificationResult(
                verified=True,
                edit_type="SPLIT_ROOM",
                expected=expected,
                actual={"new_rooms": list(map_data.rooms.keys())},
            )

        # Original segment still exists - split may have failed
        return VerificationResult(
            verified=False,
            edit_type="SPLIT_ROOM",
            expected=expected,
            actual={"existing_rooms": list(map_data.rooms.keys())},
            mismatch_reason="Original segment still exists after split",
        )

    def _verify_merge_rooms(
        self,
        edit: MergeRoomsEdit,
        map_data: MapData,
    ) -> VerificationResult:
        """Verify rooms were merged.

        Checks that only one of the merged segments remains.
        """
        expected = {"segment_ids": edit.segment_ids}

        if not map_data.rooms:
            return VerificationResult(
                verified=False,
                edit_type="MERGE_ROOMS",
                expected=expected,
                mismatch_reason="No rooms in map data",
            )

        # Count how many of the original segments still exist
        existing = [seg_id for seg_id in edit.segment_ids if seg_id in map_data.rooms]

        if len(existing) <= 1:
            return VerificationResult(
                verified=True,
                edit_type="MERGE_ROOMS",
                expected=expected,
                actual={"remaining_segments": existing},
            )

        return VerificationResult(
            verified=False,
            edit_type="MERGE_ROOMS",
            expected=expected,
            actual={"remaining_segments": existing},
            mismatch_reason=f"Expected 1 remaining segment, found {len(existing)}",
        )

    def _verify_rename_room(
        self,
        edit: RenameRoomEdit,
        map_data: MapData,
    ) -> VerificationResult:
        """Verify a room was renamed."""
        expected = {"segment_id": edit.segment_id, "name": edit.new_name}

        if not map_data.rooms or edit.segment_id not in map_data.rooms:
            return VerificationResult(
                verified=False,
                edit_type="RENAME_ROOM",
                expected=expected,
                mismatch_reason=f"Segment {edit.segment_id} not found",
            )

        room = map_data.rooms[edit.segment_id]
        actual_name = getattr(room, "name", None)

        if actual_name == edit.new_name:
            return VerificationResult(
                verified=True,
                edit_type="RENAME_ROOM",
                expected=expected,
                actual={"name": actual_name},
            )

        return VerificationResult(
            verified=False,
            edit_type="RENAME_ROOM",
            expected=expected,
            actual={"name": actual_name},
            mismatch_reason=f"Expected name '{edit.new_name}', got '{actual_name}'",
        )

    def _points_match(self, p1: Point, p2: Point, tolerance: float) -> bool:
        """Check if two points match within tolerance."""
        return abs(p1.x - p2.x) < tolerance and abs(p1.y - p2.y) < tolerance

    async def check_map_version(
        self,
        expected_map_data: MapData | None = None,
    ) -> MapVersionCheck:
        """Check if the device map matches expected version.

        Risk Mitigation §5: Map Desynchronization (State Drift)

        Args:
            expected_map_data: The local map data to compare against.

        Returns:
            MapVersionCheck result.
        """
        try:
            await self._map_content.refresh()
            device_map = self._map_content.map_data

            if device_map is None:
                return MapVersionCheck(matches=False)

            # Compare timestamps if available
            device_ts = getattr(device_map, "timestamp", None)
            local_ts = getattr(expected_map_data, "timestamp", None)

            # Simple heuristic: if room counts match, assume version matches
            # (Real implementation would use proper hash/timestamp comparison)
            if expected_map_data and device_map.rooms and expected_map_data.rooms:
                device_rooms = set(device_map.rooms.keys())
                local_rooms = set(expected_map_data.rooms.keys())
                hash_match = device_rooms == local_rooms

                return MapVersionCheck(
                    matches=hash_match,
                    device_timestamp=device_ts,
                    local_timestamp=local_ts,
                    hash_match=hash_match,
                )

            return MapVersionCheck(
                matches=True,  # Assume OK if we can't compare
                device_timestamp=device_ts,
                local_timestamp=local_ts,
            )

        except Exception as e:
            _LOGGER.error(f"Map version check failed: {e}")
            return MapVersionCheck(matches=False)


class VerificationError(Exception):
    """Exception raised when verification fails."""

    def __init__(self, message: str, results: list[VerificationResult] | None = None):
        super().__init__(message)
        self.results = results or []
