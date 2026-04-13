# Qrevo Curv 2 Flow Control & Feedback Improvement Plan

Date: 2026-04-10  
Device: Qrevo Curv 2 Flow (`roborock.vacuum.a245`)  
Device ID: `<DEVICE_ID>`

## Goal

Explain why robot control feels thin, document the commands that work, and define a better feedback plan for future robot operations.

## Executive summary

This repo exposes a thin pass-through API with a few helper commands. It is useful for sending raw device commands, but it does not provide much opinionated feedback, validation, or state-aware guidance.

The practical consequence is:
- commands often return only `ok`,
- command success does not mean the expected state change happened,
- room-targeted cleaning requires trial-and-error on payload shape,
- long-running jobs need manual status checks before/after execution.

## Why control feels weak

1. Commands are mostly raw RPC passthroughs.
2. The CLI does not enforce state-aware workflows.
3. Success responses are not rich enough to confirm intent.
4. Job execution and cleaning state are not surfaced as first-class feedback.
5. Some useful command schemas had to be discovered live.

## Commands already verified and what they showed

### Inspection / discovery

| Command | Outcome |
| --- | --- |
| `rooms` | Worked; returned the current room map |
| `home` | Worked; returned cached home/layout data |
| `maps` | Worked; returned map metadata |
| `map-data --include_path` | Worked; returned JSON geometry/path data |
| `map-image` | Worked; wrote an image file |
| `status` | Worked; returned live device state |
| `features` | Worked; returned capability flags |
| `get_room_mapping` | Worked; returned room/segment mappings |
| `get_customize_clean_mode` | Worked; returned per-segment clean settings |

### Job/control commands

| Command | Outcome |
| --- | --- |
| `app_start` | Worked |
| `app_pause` | Worked |
| `app_stop` | Worked |
| `app_charge` | Worked |
| `set_mop_mode [300]` | Worked |
| `set_clean_motor_mode [{"fan_power":102}]` | Worked |
| `set_customize_clean_mode [...]` | Worked |
| `app_segment_clean [1]` | Worked; started a live cleaning run |

### Unsupported / broken

| Command | Outcome |
| --- | --- |
| `flow-led-status` | Unsupported |
| `q10-*` session commands | Unsupported for this model |
| `clean-record` | Broken CLI/API binding |

## Current live behavior observed

Most recent clean run showed:
- `state: 23`
- `inCleaning: 3`
- `fanPower: 102`
- `waterBoxStatus: 1`
- `waterBoxMode: 235`
- `mopMode: 300`
- `washPhase: 13`

This suggests a mop-capable cleaning cycle, not a strongly opinionated vacuum-only workflow.

## Proposed structure for better feedback

### 1. Command outcome matrix

Add a durable table for:
- verified working
- unsupported
- broken
- untested

### 2. Pre/post status capture

For every actuation command, document:
- pre-status
- command payload
- immediate response
- post-status
- visible physical outcome when relevant

### 3. Command recipe docs

Add copy-paste recipes for:
- clean all rooms
- clean all rooms except office
- vacuum-only room run
- return to dock safely

### 4. Feedback gaps

Track where the API is thin:
- no job ID
- no progress events
- minimal error detail
- limited schema discovery

## Follow-up docs to update

- `docs/qrevo-curv-2-flow-command-check.md`
- `docs/plans/qrevo-curv-2-flow-remaining-live-tests.md`
- `docs/V1_API_COMMANDS.md`

## Open questions

1. Which room is the office?
2. Can the device expose richer command responses than `ok`?
3. Is there a stable payload schema for `app_segment_clean` across all runs?

## Success criteria

- [ ] Command outcomes are documented clearly
- [ ] Thin-API limitations are explained plainly
- [ ] Feedback gaps are listed with concrete next steps
- [ ] The remaining live tests can be traced back to a single plan

