# Local Map Editor (Optimistic UI)

## TL;DR

> **Quick Summary**: Build a conversational, programmatic map editing workflow. This tool will allow users to describe edits to a Roborock map via natural language. The system will maintain a "Virtual State" locally, render modified PNGs for user approval, and then translate approved changes into physical `RoborockCommand` RPC calls to the robot.
>
> **Deliverables**:
> - A Geometric Math Engine for parsing `MapData` into calculable structures (polygons, lines, points).
> - A Local State Machine supporting "Edit Objects" (Virtual Walls, No-Go Zones, Room Splits/Merges) with Undo/Revert.
> - An API Translation Layer mapping approved Virtual State changes to `device.send_command(...)`.
> - A Verification Loop to ensure the robot's cloud map matches the intended local state.
>
> **Estimated Effort**: High (requires significant mathematical/geometric implementation).

---

## Architectural Workflow

The system is designed around an **Optimistic UI Pattern**, split into three distinct phases:

### Phase 1: Local Replication & The "Virtual State"
1. **Pull Data**: `HomeTrait.discover_home()` fetches the raw binary map via `GET_MAP_V1`.
2. **Initialize Local State**: The `MapParser` (from `vacuum-map-parser-roborock`) reads the binary into a local `MapData` object.
3. **Geometric Engine**: We convert Roborock's internal coordinate system (usually mm relative to a charger or origin point) into manipulatable Python shapes (using `shapely` or standard geometry math).
    * _Challenge_: Mapping the coordinate scale from the binary array directly to bounding boxes (`[min_x, max_x, min_y, max_y]`).

### Phase 2: The Conversational Edit Loop
When the user requests an edit (e.g., "Add a virtual wall across the hallway"):
1. **Mutation**: Instead of modifying the robot immediately, the system generates an "Edit Object" (e.g., `VirtualWall(x1, y1, x2, y2)`).
2. **Apply Local Edit**: The Edit Object is appended to a local stack and applied to our Virtual State `MapData`.
3. **Interactive Preview**: The CLI generates a temporary PNG (e.g., `temp_preview.png`) with the proposed edits drawn in red. The user is prompted to check this file before proceeding.
4. **Approval/Undo**: The user reviews the PNG. If incorrect, we pop the Edit Object off the stack (Undo). If approved, we proceed to Phase 3.

### Phase 3: Execution & Verification (Three-Stage Sync)
Because topology edits (like `SPLIT_ROOM`) destroy old Room IDs and create new ones, property edits (like `NAME_SEGMENT`) depend on the remapped IDs, and additive edits (like `SET_VIRTUAL_WALL`) should only run after topology changes settle. Therefore, the Translation Layer must execute a **Three-Stage Sync**:

1. **Stage 1 (Structural Sync)**: Translate and send all room split, merge, and rename commands.
2. **Intermediate Repopulate**: Pause and poll `GET_MAP_V1` until the firmware reflects the structural changes. Update the Local State Machine with the new, valid Room IDs.
3. **Stage 2 (Additive Sync)**: Re-map any remaining "Edit Objects" (Virtual Walls, No-Go Zones, Carpet Areas) to the newly generated Room IDs and send those commands to the robot.
4. **Final Verification Polling**: Firmware processing is asynchronous. We must implement a polling loop (e.g., 3 retries over 10 seconds) calling `GET_MAP_V1` to verify that the robot's final state matches our Local State. Catch firmware rejections (e.g., virtual wall intersecting the dock).

---

## Critical Considerations & Risk Mitigation

### 1. Partial Failures & Transactional Integrity
* **Risk**: If a batch of 5 edits is sent and the 4th fails, the first 3 are permanently applied with no automatic rollback.
* **Mitigation**:
    - **Physical Rollback**: The Local State Machine must track "inverse" commands for every action.
    - **Pre-Sync Snapshot**: Investigate `manual_bak_map` and `recover_map` commands to create a restorable checkpoint before applying batches.

### 2. Map Switch Safety (State Blocking)
* **Risk**: `HomeTrait.discover_home()` physically switches maps, which takes time and can fail if the robot is busy cleaning.
* **Mitigation**: Prioritize the `DeviceCache`. If map data is already cached, perform all "Optimistic" edits against the cache. Only force a physical map switch/refresh if the user explicitly requests a "Live Sync" and the robot is idle.

### 3. Parser Dependencies (Black Box Extraction)
* **Risk**: `vacuum-map-parser-roborock` is optimized for image rendering and may obscure or discard the raw binary/mathematical coordinates required for a Geometric Engine.
* **Mitigation**: Exploration confirms the parser exposes `map_data.image.dimensions` (offset/scale) and raw `[x,y]` coordinates (in mm) for all rooms/walls. The raw math is fully accessible; no custom binary decoder is needed.

### 4. Protocol Fragmentation (V1 vs. A01/B01)
* **Risk**: Payload structures for map editing may differ significantly between protocol versions (e.g., older S5 vs. newer Qrevo Curv).
* **Mitigation**: Implement a polymorphic Translation Layer that selects the correct payload schema based on the device's protocol version and capabilities.

### 5. Map Desynchronization (State Drift)
* **Risk**: If the robot rotates or overwrites its map while the user is editing locally, applying the batch of edits will result in corrupted/misplaced geometry.
* **Mitigation**: Implement a "Version Check" loop. Use map hashes/timestamps (if available in the status) to verify the robot's current geometry matches the one used to build the local Virtual State before executing the sync.

### 6. Multi-Floor Context Binding
* **Risk**: Commands sent without explicit map flagging may apply to the currently active floor rather than the floor the user is editing.
* **Mitigation**: Every command in the translation layer must be explicitly bound to the target `map_flag` ID.

---

## Technical Implementation Details

### The Coordinate Matrix (Algebraic Reversal)
To ensure edits are placed correctly, the system must map between Image Space (PNG pixels) and Robot Space (mm). The parser `vacuum-map-parser-roborock` exposes an `ImageDimensions` object (`top`, `left`, `scale`) that defines the crop and zoom applied during rendering. It also divides the raw Robot Space by a factor of 50 to create its internal Grid Space.

**The Formula to translate a click on the PNG back to a Robot API command:**
* `Robot_X = ((Pixel_X / dimensions.scale) + dimensions.left) * 50`
* `Robot_Y = ((Pixel_Y / dimensions.scale) + dimensions.top) * 50`

The `Geometric Engine` must use these exact algebraic reversals to build the Translation Layer payloads. Failure to use the parser's dynamic `left`/`top` offsets will result in walls drifting outside of the rooms.

### Required Dependencies
* **Geometry Math**: Evaluate `shapely` (heavy, robust) vs. a custom pure-python implementation for basic line-segment and bounding-box math.
* **Rendering**: Enhancements to the existing `MapParser` to draw "pending" edits (e.g., dotted lines for proposed virtual walls).

### API Command Mapping Target
The translation layer must reliably implement the following commands from `roborock/roborock_typing.py`:
* `SPLIT_ROOM` / `MERGE_SEGMENT` / `RENAME_ROOM` / `SET_ROOM_ORDER`
* `SET_VIRTUAL_WALL` / `SET_NO_GO_ZONES` / `SET_MOP_FORBIDDEN_ZONE`
* `SET_CARPET_AREA` / `SET_SEGMENT_GROUND_MATERIAL` / `SAVE_FURNITURES`
* `SAVE_MAP` (to commit the changes permanently)

### Geometric Translation Challenges
The primary engineering hurdle is translating natural language ("the kitchen") into exact coordinates.
1. The user identifies the "Kitchen" (or we list it via `RoomsTrait`).
2. The Geometric Engine calculates the `[min_x, max_x, min_y, max_y]` of the Kitchen's pixels in the map array.
3. We determine the user's intent (e.g., "split in half vertically").
4. The Engine calculates the exact `x1, y1, x2, y2` coordinates that form a line cleanly intersecting the kitchen's walls without leaving the segment.

---

## Testing Strategy & Guardrails (CRITICAL)

Because the map editor is inherently destructive (operations like splitting rooms and saving walls overwrite the robot's state), **destructive commands MUST NOT be executed on physical robots during automated or ad-hoc testing** (unless explicitly part of a signed-off, manual risk-assessment scenario).

1. **No Live Destructive Testing:** All translation layers and CLI execution paths must be tested against a Mock MQTT Broker or simulated local devices.
2. **Transactional Integrity Verification:** Tests must explicitly verify that `create_map_backup` is called before execution, and `restore_map_backup` is invoked immediately upon any failure in the Two/Three-Stage Sync batch.
3. **Payload Parity Validation:** Mock E2E tests must capture the outbound RPC payloads emitted by `TranslationLayer` and assert they mathematically match the expected constraints (e.g., coordinates are properly transformed integers, `map_flag` is injected, V1 additive batches include original state).
4. **Dynamic Protocol Fallback:** Tests must ensure the CLI dynamically chooses the V1 or A01/B01 translator based on `device_info.yaml` (via `code_mappings`), rather than hardcoding.

---

## Next Steps for Implementation (Revised)

1. **Fix Transactional Integrity:** Update `roborock/cli.py` (`_execute_edit`) to wrap the `translation.execute_edits` call in a `create_map_backup()` / `restore_map_backup()` try/except block.
2. **Implement Dynamic Protocol Selection:** Update the CLI to resolve the correct protocol version using `RoborockProductNickname` and `ProductInfo` instead of hardcoding `"v1"`.
3. **Safe E2E MQTT Tests:** Build an end-to-end integration test (`tests/e2e/test_map_editor_mqtt.py`) that feeds a real map JSON payload (e.g., `home_data_device_a245.json`) into the `MapParser`, runs the full CLI edit flow (VirtualState -> Editor -> TranslationLayer), and traps the outbound MQTT messages to assert correctness without physical side-effects.
4. **Natural Language Semantic Engine:** Enhance the CLI input parsing to support conversational commands (e.g., "Split the Kitchen in half") vs raw coordinate/room ID injections.
