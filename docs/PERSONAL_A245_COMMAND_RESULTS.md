# PERSONAL DOCUMENT: Qrevo Curv 2 Flow (a245) Command Test Results

> **NOTE:** This file is strictly for personal reference and should NOT be included in any upstream Pull Requests to the main `python-roborock` repository.

**Device ID:** `7FjpPFODrdwoiHnJvL6eW2`
**Model:** `roborock.vacuum.a245`
**Serial Number:** `REPNBH54502144`
**Dock SN:** `7020709H254500677` (firmware v0092)
**Test Date:** 2026-03-19
**Firmware BOM:** A.03.0777 (FCC, US, English)

---

## Working GET Commands (Confirmed)

### Map Commands
| Command | Response |
|---------|----------|
| `get_multi_maps_list` | Full map data: 1 map "First Floor", 12 rooms (9 named), 9 furniture items, 1 backup map. Max 4 maps. |
| `get_map_status` | `[1]` |
| `get_room_mapping` | 9 named rooms with IoT IDs: Kitchen(1), Bedroom(3), Bathroom(6), Bathroom1(7), Laundry(9), Dining room1(10), Living room(11), Dining room(14), Bedroom1(15) |
| `get_segment_status` | `[1]` |
| `get_map_beautification_status` | `{"status": 65535}` |
| `get_offline_map_status` | `{"common_switch_status": 0}` |
| `get_dynamic_map_diff` | Returns diff data with obstacle/space counts, nonces |
| `get_map_v1` | `["ok"]` (triggers map data via separate channel) |

### Dock & Mop Commands
| Command | Response |
|---------|----------|
| `get_dust_collection_mode` | `{"mode": 0}` |
| `get_dust_collection_switch_status` | `{"status": 1}` (enabled) |
| `get_wash_towel_mode` | `{"wash_mode": 10}` |
| `get_smart_wash_params` | `{"smart_wash": 2, "wash_interval": 1200}` (wash every 1200s) |
| `get_wash_water_temperature` | `{"wash_water_temperature": 1}` |
| `get_auto_delivery_cleaning_fluid` | `{"status": 1}` (enabled) |
| `get_dock_info` | `{"sn": "7020709H254500677", "version": "0092"}` |
| `app_get_dryer_setting` | `{"status": 1, "on": {"cliff_on": 1000, "cliff_off": 1000, "count": 10, "dry_time": 14400, "dry_heating_film_time": 3600}, ...}` |

### Cleaning & Suction Settings
| Command | Response |
|---------|----------|
| `get_carpet_mode` | `[{"enable": 0, "current_integral": 1000, "current_high": 500, "current_low": 1000, "stall_time": 10}]` |
| `get_carpet_clean_mode` | `[{"carpet_clean_mode": 0}]` |
| `app_get_carpet_deep_clean_status` | `{"status": 0}` |
| `get_collision_avoid_status` | `{"status": 1}` (enabled) |
| `get_clean_motor_mode` | `[{"water_box_mode": 235, "fan_power": 102, "mop_mode": 300, "distance_off": 0}]` |
| `get_custom_mode` | `[102]` (Balanced) |
| `get_water_box_custom_mode` | `{"water_box_mode": 235, "distance_off": 0}` |
| `app_get_clean_estimate_info` | Returns estimate struct (all zeros when idle) |

### AI & Detection
| Command | Response |
|---------|----------|
| `get_identify_furniture_status` | `{"status": 1}` (enabled) |
| `get_identify_ground_material_status` | `{"status": 1}` (enabled) |
| `get_clean_follow_ground_material_status` | `{"status": 0}` (disabled) |
| `get_pet_supplies_deep_clean_status` | `{"status": 1}` (enabled) |
| `get_dirty_object_detect_status` | `{"status": 0}` (disabled) |
| `get_stretch_tag_status` | `{"status": 1}` (enabled) |
| `get_handle_leak_water_status` | `{"status": 0}` (no leak) |

### Device Info & Status
| Command | Response |
|---------|----------|
| `get_status` | Full status JSON: state 8 (charging), battery 100%, fanPower 102, mopMode 300, dockType 29, etc. |
| `get_consumable` | mainBrushWorkTime: 65230, sideBrushWorkTime: 79201, filterWorkTime: 65230, moprollerWorkTime: 7463 |
| `get_clean_summary` | cleanTime: 79098s, cleanArea: 1395972500cm², cleanCount: 18, dustCollectionCount: 17 |
| `get_network_info` | IP 192.168.0.156, SSID CastleMooseGoose, RSSI -54 |
| `get_timezone` | `["America/Chicago"]` |
| `get_serial_number` | `[{"serial_number": "REPNBH54502144"}]` |
| `get_current_sound` | `[{"sid_in_use": 3, "sid_version": 6, "location": "us", "bom": "A.03.0777", "language": "en"}]` |
| `get_sound_volume` | `[60]` |
| `get_camera_status` | `[28071]` |
| `get_led_status` | `[1]` (on) |
| `get_child_lock_status` | `{"lock_status": 0}` (off) |
| `get_fw_features` | `[111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125]` |
| `app_get_init_status` | Full init: feature_info, new_feature_info (4499197267967999), dsp_version 00.33.46 |
| `app_get_locale` | `[{"name": "custom_A.03.0777_FCC", "bom": "A.03.0777", "location": "us", "language": "en"}]` |

### Timers & Scheduling
| Command | Response |
|---------|----------|
| `get_dnd_timer` | `[{"start_hour": 21, "start_minute": 0, "end_hour": 9, "end_minute": 0, "enabled": 1, "actions": {"resume": 1, "dust": 0, "led": 1, "vol": 1, "dry": 0}}]` |
| `get_valley_electricity_timer` | `[{"start_hour": 0, ..., "enabled": 0}]` (disabled) |

### Security & Network
| Command | Response |
|---------|----------|
| `get_homesec_connect_status` | `{"status": 0, "client_id": "none"}` |
| `get_log_upload_status` | `[{"log_upload_status": 9, "location": "us", "policy_name": 2}]` |
| `get_random_pkey` | Returns RSA public key |
| `get_turn_server` | `{"url": "retry"}` |
| `get_device_ice` | `{"dev_ice": "retry"}` |
| `get_device_sdp` | `{"dev_sdp": "retry"}` |
| `app_get_wifi_list` | `[{"id": 1, "ssid": "CastleMooseGoose"}]` |
| `matter.get_status` | `[{"status": "KeyNotExit"}]` (not configured) |

### Misc
| Command | Response |
|---------|----------|
| `find_me` | `["ok"]` — robot beeped |
| `get_testid` | `[{"testid": ""}]` |

---

## Unsupported Commands (Device Rejected)

| Command | Error |
|---------|-------|
| `get_recover_maps` | `RoborockUnsupportedFeature` |
| `get_recover_map` | `RoborockUnsupportedFeature` |
| `get_map_calibration` | `RoborockUnsupportedFeature` |
| `get_fresh_map` | `RoborockUnsupportedFeature` |
| `get_persist_map` | `RoborockUnsupportedFeature` |
| `get_flow_led_status` | `RoborockUnsupportedFeature` |
| `get_wash_towel_params` | `RoborockUnsupportedFeature` |
| `get_gap_deep_clean_status` | `RoborockUnsupportedFeature` |
| `get_right_brush_stretch_status` | `RoborockUnsupportedFeature` |
| `get_mop_motor_status` | `RoborockUnsupportedFeature` |
| `get_ap_mic_led_status` | `RoborockUnsupportedFeature` |
| `get_fan_motor_work_timeout` | `RoborockUnsupportedFeature` |
| `get_map_v2` | `RoborockUnsupportedFeature` |
| `get_wash_debug_params` | `RoborockUnsupportedFeature` |
| `app_get_amethyst_status` | `RoborockUnsupportedFeature` |
| `get_mop_template_params_summary` | `RoborockUnsupportedFeature` |

## Empty Responses (No Error, No Data)

| Command | Notes |
|---------|-------|
| `get_customize_clean_mode` | Empty — may need params or no custom modes set |
| `get_clean_sequence` | Empty — no sequence configured |
| `get_timer` | Empty — no timers set |
| `get_server_timer` | Empty — no server timers set |
| `get_scenes_valid_tids` | Empty — no scenes configured |
| `get_timer_summary` | Empty — no timers set |
| `app_get_robot_setting` | Empty — may need params |

## Require Parameters (Errored Due to Missing Params)

| Command | Error |
|---------|-------|
| `get_clean_record` | `param does not contain any element` — needs record ID |
| `get_dynamic_data` | `invalid params` — needs params |
| `get_timer_detail` | `param does not contain any element` — needs timer ID |

## Timed Out

| Command | Notes |
|---------|-------|
| `get_multi_map` | Timed out after 10s |
| `get_prop` | Timed out after 10s |
| `get_clean_record_map` | Timed out after 10s — likely needs params |

---

## Untested Commands (Write/Action — Not Yet Run)

### Safe / Harmless
- `test_sound_volume` — plays a test sound
- `app_wakeup_robot` — wakes from sleep
- `play_audio` — plays audio

### Movement & Cleaning (WILL MOVE ROBOT)
- `app_start` — start full clean
- `app_stop` — stop cleaning
- `app_pause` — pause cleaning
- `app_charge` — return to dock
- `app_spot` — spot clean
- `app_segment_clean` — clean specific rooms (needs params)
- `app_zoned_clean` — clean zones (needs params)
- `app_goto_target` — go to point (needs params)
- `app_rc_start` / `app_rc_move` / `app_rc_stop` / `app_rc_end` — remote control
- `resume_segment_clean` / `resume_zoned_clean` — resume cleaning
- `stop_segment_clean` / `stop_zoned_clean` / `stop_goto_target` — stop specific actions
- `app_start_build_map` — build new map (drives around)
- `app_resume_build_map` — resume map building
- `app_start_patrol` / `app_resume_patrol` — patrol mode
- `app_start_pet_patrol` — pet patrol
- `start_clean` — alternative start

### Dock Actions
- `app_start_wash` / `app_stop_wash` — wash mop
- `app_start_collect_dust` / `app_stop_collect_dust` — empty dustbin
- `start_wash_then_charge` — wash then dock
- `app_empty_rinse_tank_water` — empty rinse tank

### Settings (SET commands — changes device config)
- `change_sound_volume` — set volume
- `set_led_status` / `set_flow_led_status` — LED on/off
- `set_child_lock_status` — child lock
- `set_dnd_timer` / `set_dnd_timer_actions` / `close_dnd_timer` — DND
- `set_custom_mode` — fan/suction power
- `set_mop_mode` — mop mode
- `set_water_box_custom_mode` / `set_water_box_distance_off` — water settings
- `set_collision_avoid_status` — collision avoidance
- `set_carpet_mode` / `set_carpet_clean_mode` — carpet handling
- `set_dust_collection_mode` / `set_dust_collection_switch_status` — dust collection
- `set_smart_wash_params` — smart wash
- `set_wash_towel_mode` — wash mode
- `set_wash_water_temperature` — wash temp
- `set_auto_delivery_cleaning_fluid` — auto cleaning fluid
- `app_set_dryer_setting` / `app_set_dryer_status` — dryer
- `set_identify_furniture_status` — furniture detection
- `set_identify_ground_material_status` — ground material detection
- `set_clean_follow_ground_material_status` — follow ground material
- `set_pet_supplies_deep_clean_status` — pet deep clean
- `set_dirty_object_detect_status` — dirty object detection
- `set_stretch_tag_status` — stretch tag
- `set_handle_leak_water_status` — leak handling
- `set_camera_status` — camera on/off
- `set_timezone` / `set_app_timezone` — timezone
- `set_valley_electricity_timer` / `close_valley_electricity_timer` — off-peak timer
- `set_clean_motor_mode` — motor mode
- `set_clean_sequence` — room order
- `set_clean_repeat_times` — repeat count
- `set_customize_clean_mode` — per-room settings
- `set_offline_map_status` — offline map
- `set_map_beautification_status` — map beautification
- `set_lab_status` — lab features
- `app_set_carpet_deep_clean_status` — carpet deep clean
- `app_set_cross_carpet_cleaning_status` — cross-carpet
- `app_set_dirty_replenish_clean_status` — dirty replenish
- `app_set_dynamic_config` — dynamic config
- `app_set_ignore_stuck_point` — ignore stuck point
- `app_set_smart_cliff_forbidden` — cliff detection
- `app_set_smart_door_sill` / `app_set_door_sill_blocks` — door sills
- `app_ignore_dirty_objects` — ignore dirty objects
- `app_set_robot_setting` — robot setting
- `set_gap_deep_clean_status` — gap deep clean
- `set_ignore_carpet_zone` — ignore carpet zone
- `set_ignore_identify_area` — ignore identify area
- `set_segment_ground_material` — set room material
- `set_scenes_segments` / `set_scenes_zones` — scene config
- `set_voice_chat_volume` — voice chat volume
- `set_airdry_hours` — air dry duration
- `set_fds_endpoint` — FDS endpoint
- `set_homesec_password` / `reset_homesec_password` / `check_homesec_password` — home security
- `enable_homesec_voice` — home security voice
- `enable_log_upload` — log upload

### Map Editing
- `start_edit_map` / `end_edit_map` — enter/exit map edit mode
- `name_segment` — rename a room
- `name_multi_map` — rename a map
- `split_segment` — split a room
- `merge_segment` — merge rooms
- `manual_segment_map` — manual segmentation
- `manual_bak_map` — manual backup
- `load_multi_map` — switch floor maps
- `save_map` — save current map
- `use_new_map` / `use_old_map` — map selection
- `save_furnitures` — save furniture positions
- `set_carpet_area` — define carpet zones
- `app_update_unsave_map` — update unsaved map
- `recover_map` / `recover_multi_map` — recover maps
- `set_switch_map_mode` — switch map mode

### Destructive (DO NOT RUN without intention)
- `del_map` — delete a map
- `del_clean_record` / `del_clean_record_map_v2` — delete clean history
- `del_timer` / `del_server_timer` — delete timers
- `reset_map` — reset map entirely
- `reset_consumable` — reset consumable counters
- `matter.reset` — reset Matter pairing
- `app_delete_wifi` — delete WiFi config

### Camera & Video
- `start_camera_preview` / `stop_camera_preview` — camera preview
- `start_voice_chat` / `stop_voice_chat` — voice chat
- `switch_video_quality` — video quality
- `switch_water_mark` — watermark toggle

### Misc
- `app_start_easter_egg` / `app_keep_easter_egg` — easter egg
- `app_amethyst_self_check` — amethyst self check
- `app_stat` — statistics
- `dnld_install_sound` — download/install voice pack
- `get_sound_progress` — sound download progress
- `upload_photo` / `upload_data_for_debug_mode` / `user_upload_log` — uploads
- `send_ice_to_robot` / `send_sdp_to_robot` — WebRTC signaling
- `retry_request` — retry
- `resolve_error` — resolve error
- `reunion_scenes` — reunion scenes
- `matter.dnld_key` — Matter key download
- `update_dock` — update dock
- `mop_mode` / `mop_template_id` — mop template
- `add_mop_template_params` / `update_mop_template_params` / `del_mop_template_params` / `sort_mop_template_params` / `get_mop_template_params_by_id` — mop templates
- `set_timer` / `upd_timer` / `set_server_timer` / `upd_server_timer` — timer management
- `stop_fan_motor_work` — stop fan motor

---

## Summary

| Category | Working | Unsupported | Empty | Needs Params | Timeout | Untested |
|----------|---------|-------------|-------|--------------|---------|----------|
| **GET/Read** | **48** | **16** | **7** | **3** | **3** | **0** |
| **SET/Write** | — | — | — | — | — | ~65 |
| **Action** | **1** (find_me) | — | — | — | — | ~30 |
| **Destructive** | — | — | — | — | — | ~8 |
| **Total** | **49** | **16** | **7** | **3** | **3** | ~103 |
