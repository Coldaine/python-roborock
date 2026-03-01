# PERSONAL DOCUMENT: Qrevo Curv 2 Flow (a245) Polling Plan

> **NOTE:** This file is strictly for personal reference and should NOT be included in any upstream Pull Requests to the main `python-roborock` repository.

## Objective
To safely test the integration and understand exactly what data the newly added Qrevo Curv 2 Flow exposes via the Python API, without accidentally triggering any hardware movements or resetting personal usage counters.

## Phase 1: Comprehensive Read-Only Polling
The following commands will be executed sequentially using the device ID `7FjpPFODrdwoiHnJvL6eW2` to map out the current state.

### 1. State & Lifecycle
- `roborock status`: Retrieves the live state (battery, fan power, mop mode, error codes).
- `roborock dock_summary`: Checks the status of the advanced dock (washing, drying, emptying dustbin).

### 2. History & Consumables
- `roborock clean_summary`: Totals (total hours, area, and clean counts).
- `roborock clean_record`: Pulls the log of the most recent cleaning runs.
- `roborock consumables`: Checks the lifespan of the SpiraFlow brush, side brush, filters, and sensors.

### 3. Environment & Mapping
- `roborock maps`: Lists available floor plans.
- `roborock map_data`: Retrieves the coordinate positions of the vacuum, the dock, and defined zones (without saving the actual image).
- `roborock rooms`: Lists internal room IDs and their user-assigned names.
- `roborock network_info`: Checks WiFi signal strength (RSSI), IP, and MAC.

### 4. Device Settings
- `roborock volume`: Current voice prompt volume.
- `roborock child_lock`: Whether physical button lock is active.
- `roborock dnd`: Do Not Disturb schedule.
- `roborock led_status` / `flow_led_status`: Current LED indicator preferences.

---

## Phase 2: Red Zone (Do Not Touch)
To ensure the robot does not unexpectedly begin cleaning, change settings, or lose its consumable history, the following commands are **STRICTLY PROHIBITED** during this testing phase:

- **Movement & Cleaning:** Anything that triggers `app_start`, `app_stop`, `app_pause`, `app_charge` (return to dock), or `app_goto_target`.
- **Settings Mutation:** `set_volume`, `set_child_lock`, `set_dnd_timer`, `set_led_status`.
- **Consumables Reset:** `reset_consumable` (would wipe brush/filter life tracking).
- **Raw Commands:** The `roborock command` CLI tool, which allows arbitrary payload injection.
- **Scene Execution:** `execute_scene`.
