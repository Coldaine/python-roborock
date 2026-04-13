# Qrevo Curv 2 Flow Remaining Live Test Plan

## Goal

Complete the remaining live validation for `Qrevo Curv 2 Flow` (`roborock.vacuum.a245`, device id `<DEVICE_ID>`), with special focus on:

1. the remaining untested map commands,
2. job/cleaning-plan commands not yet explicitly validated,
3. a room-targeted run that is **vacuum only** and covers **all rooms except the user's office**.

## What is already verified

- Authenticated device discovery works.
- Device pinning works (`<DEVICE_ID>`).
- These map/layout inspection commands work live:
  - `uv run roborock home --device_id <DEVICE_ID>`
  - `uv run roborock maps --device_id <DEVICE_ID>`
  - `uv run roborock rooms --device_id <DEVICE_ID>`
  - `uv run roborock map-data --device_id <DEVICE_ID>`
- Generic job-control commands work live:
  - `uv run roborock command --device_id <DEVICE_ID> --cmd app_start`
  - `uv run roborock command --device_id <DEVICE_ID> --cmd app_pause`
  - `uv run roborock command --device_id <DEVICE_ID> --cmd app_stop`
  - `uv run roborock command --device_id <DEVICE_ID> --cmd app_charge`
- Final safe-state validation works via:
  - `uv run roborock status --device_id <DEVICE_ID>`

## Constraints and operating rules

- Run auth-refreshing CLI commands sequentially; do **not** parallelize commands that may rewrite `~/.roborock`.
- Use live status checks before and after any actuating command.
- End every movement/job test with the robot back in a safe charging state.
- Do not use destructive or global commands outside the previously approved scope.
- For room-targeted cleaning, do not start until the office room mapping is confirmed.

## Known live room map

Current `rooms` output for device `<DEVICE_ID>`:

- `1` → `Kitchen`
- `3` → `Bedroom`
- `6` → `Bathroom`
- `7` → `Bathroom1`
- `9` → `Laundry`
- `10` → `Dining room1`
- `11` → `Living room`
- `14` → `Dining room`
- `15` → `Bedroom1`

Important: there is **no room literally named `Office`** in the current mapping. Before building the "all rooms except office" run, the agent must determine which of the existing room names/segment ids corresponds to the user's office.

## Remaining command groups to test

### 1. Untested map commands

Run and capture outputs for:

```powershell
uv run roborock map-data --device_id <DEVICE_ID> --include_path
uv run roborock map-image --device_id <DEVICE_ID> --output-file .sisyphus/evidence/live-qrevo-curv-2-flow/latest-map.png
uv run roborock rooms --device_id <DEVICE_ID>
```

Acceptance:

- `map-data` returns parseable JSON with useful geometry/path content.
- `map-image` writes an image file successfully.
- `rooms` output is used to pin the office room id.

### 2. Remaining job / plan-oriented command discovery

The repo exposes a generic command path:

```powershell
uv run roborock command --device_id <DEVICE_ID> --cmd <command_name> --params '<json>'
```

The lower-level docs mention these candidate commands relevant to room-targeted cleaning and mode control:

- `app_segment_clean`
- `resume_segment_clean`
- `stop_segment_clean`
- `set_clean_motor_mode`
- `set_mop_mode`
- `set_customize_clean_mode`
- `get_customize_clean_mode`
- `get_room_mapping`

These are **candidates**, not yet validated for this model. The next agent should probe them carefully, one at a time, starting with read-only/introspection-safe variants.

### 3. Office-excluded vacuum-only room plan

Target outcome:

- clean **all mapped rooms except the office**,
- use **vacuum only** mode,
- no mop-only or mop-plus behavior,
- end in a safe charging state.

## Required execution phases

### Phase A - Confirm office mapping

1. Re-run:

```powershell
uv run roborock rooms --device_id <DEVICE_ID>
```

2. Determine which segment id is the office.
   - If the room name has been renamed since the last run, use the current live name.
   - If it is still ambiguous, stop and get the user's confirmation **before** any room-targeted cleaning run.

3. Build:
   - `OFFICE_SEGMENT_ID=<office id>`
   - `TARGET_SEGMENTS=<all known segment ids except office>`

With the current map, that target list will be built from:

```text
1,3,6,7,9,10,11,14,15
```

minus the office segment.

### Phase B - Discover the vacuum-only mode controls

The agent should test these in increasing-risk order:

1. Query current status/baseline:

```powershell
uv run roborock status --device_id <DEVICE_ID>
uv run roborock features --device_id <DEVICE_ID>
```

2. Probe generic commands that appear to be mode/introspection related:

```powershell
uv run roborock command --device_id <DEVICE_ID> --cmd get_room_mapping
uv run roborock command --device_id <DEVICE_ID> --cmd get_customize_clean_mode
```

3. If the command path is accepted, probe candidate vacuum/mop mode setters with explicit evidence capture and immediate status verification.

Candidate commands to evaluate:

```powershell
uv run roborock command --device_id <DEVICE_ID> --cmd set_clean_motor_mode --params '<json>'
uv run roborock command --device_id <DEVICE_ID> --cmd set_mop_mode --params '<json>'
uv run roborock command --device_id <DEVICE_ID> --cmd set_customize_clean_mode --params '<json>'
```

The exact params are still model-specific and must be discovered/validated before use. Do not assume Q10 `onlysweep` params apply to this device, because we already proved the Q10 path is not the primary protocol here.

### Phase C - Construct the office-excluded cleaning command

Once the office segment id is known and the vacuum-only mode mechanism is verified, construct a generic-command plan using `app_segment_clean` with the target segment list.

Command template:

```powershell
uv run roborock command --device_id <DEVICE_ID> --cmd app_segment_clean --params '<json>'
```

The agent must populate `<json>` only after discovering the accepted schema for this model. The command should encode:

- target room/segment ids = all non-office segments,
- vacuum-only mode,
- no mop-only override.

### Phase D - Execute with tight verification

For the chosen room-targeted command:

1. Capture pre-status:

```powershell
uv run roborock status --device_id <DEVICE_ID>
```

2. Execute the room-targeted cleaning command.

3. Capture immediate post-status.

4. Confirm with the user whether the robot visibly started cleaning the expected non-office area.

5. End safely:

```powershell
uv run roborock command --device_id <DEVICE_ID> --cmd app_stop
uv run roborock command --device_id <DEVICE_ID> --cmd app_charge
uv run roborock status --device_id <DEVICE_ID>
```

## What the next agent must not assume

- Do not assume `Bedroom` or `Bedroom1` is the office without confirmation.
- Do not assume Q10 `q10-set-clean-mode --mode onlysweep` applies to this device.
- Do not claim a room/job command "worked" from `ok` alone; require both device-state evidence and, for motion jobs, visible physical confirmation when possible.

## Deliverables

The next agent should leave behind:

1. evidence files for the remaining map commands,
2. evidence for discovered generic-command params/schemas,
3. one explicit transcript for the office-excluded vacuum-only room plan,
4. a final safe-state transcript,
5. doc updates to `docs/qrevo-curv-2-flow-command-check.md` promoting these remaining commands to worked / unsupported / broken.

