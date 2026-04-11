# Qrevo Curv 2 Flow command check

Date: 2026-04-08

## Model mapping found in this repo

- `device_info.yaml` contains `name: Qrevo Curv 2 Flow`
- That entry maps to `model: roborock.vacuum.a245`
- That entry is marked `protocol_version: '1.0'`

Conclusion: the repo metadata is consistent with this model using the standard vacuum command path in `roborock`, not the session-only `q10-*` command set. Runtime dispatch is based on the live device protocol value after login, but the local support metadata points to the standard protocol-1.0 path.

## Expected command flow

From `roborock/cli.py` and the live CLI help:

1. `uv run roborock login --email <email> [--password <password>]`
2. `uv run roborock discover`
3. `uv run roborock list-devices`
4. `uv run roborock status --device_id <device_id>`

This is the documented typical CLI flow. In practice, `discover` is recommended but not strictly required because device data is refreshed on demand when needed.

Useful related commands for this model:

- `uv run roborock get-device-info`
- `uv run roborock home --device_id <device_id> [--refresh]`
- `uv run roborock features --device_id <device_id>`
- `uv run roborock command --device_id <device_id> --cmd <cmd> [--params <json>]`

## Commands tested and outputs

### 1. CLI help

Command:

```powershell
uv run roborock --help
```

Result: works

Output:

```text
Usage: roborock [OPTIONS] COMMAND [ARGS]...

Options:
  --version    Show the version and exit.
  -d, --debug
  --help       Show this message and exit.

Commands:
  child-lock
  clean-record
  clean-summary
  command
  consumables
  discover
  dnd
  dock-summary
  execute-scene
  features
  flow-led-status
  get-device-info
  home
  led-status
  list-devices
  list-scenes
  login
  map-data
  map-image
  maps
  network-info
  parser
  reset-consumable
  rooms
  session
  set-volume
  status
  update-docs
  volume
```

### 2. Version

Command:

```powershell
uv run roborock --version
```

Result: works

Output:

```text
roborock, version 4.17.2
```

### 3. Login help

Command:

```powershell
uv run roborock login --help
```

Result: works

Output:

```text
Usage: roborock login [OPTIONS]

  Login to Roborock account.

Options:
  --email TEXT     [required]
  --reauth         Re-authenticate even if cached credentials exist.
  --password TEXT  Password for the Roborock account. If not provided, an
                   email code will be requested.
  --help           Show this message and exit.
```

### 4. Device info help

Command:

```powershell
uv run roborock get-device-info --help
```

Result: works

Output:

```text
Usage: roborock get-device-info [OPTIONS]

  Connects to devices and prints their feature information in YAML format.

  Can also parse device info from a Home Assistant diagnostic file using
  --diagnostic-file.

Options:
  --record                 Save new device info entries to the YAML file.
  --device-info-file TEXT  Path to the YAML file with device and product data.
  --diagnostic-file TEXT   Path to a Home Assistant diagnostic JSON file to
                           parse instead of connecting to devices.
  --help                   Show this message and exit.
```

### 5. Status help

Command:

```powershell
uv run roborock status --help
```

Result: works

Output:

```text
Usage: roborock status [OPTIONS]

  Get device status.

Options:
  --device_id TEXT  [required]
  --help            Show this message and exit.
```

### 6. Generic command help

Command:

```powershell
uv run roborock command --help
```

Result: works

Output:

```text
Usage: roborock command [OPTIONS]

Options:
  --device_id TEXT  [required]
  --cmd TEXT        [required]
  --params TEXT
  --help            Show this message and exit.
```

### 7. Features help

Command:

```powershell
uv run roborock features --help
```

Result: works

Output:

```text
Usage: roborock features [OPTIONS]

  Get device room mapping info.

Options:
  --device_id TEXT  [required]
  --help            Show this message and exit.
```

### 8. Home help

Command:

```powershell
uv run roborock home --help
```

Result: works

Output:

```text
Usage: roborock home [OPTIONS]

  Discover and cache home layout (maps and rooms).

Options:
  --device_id TEXT  [required]
  --refresh         Refresh status before discovery.
  --help            Show this message and exit.
```

### 9. Discover without login

Command:

```powershell
uv run roborock discover
```

Result: command runs, but device discovery is blocked until login

Output:

```text
Error: You must login first
```

### 10. List devices without login

Command:

```powershell
uv run roborock list-devices
```

Result: command runs, but device listing is blocked until login

Output:

```text
Error: You must login first
```

### 11. Get device info without login

Command:

```powershell
uv run roborock get-device-info
```

Result: command runs, but live device inspection is blocked until login

Output:

```text
Discovering devices...
Error: You must login first
```

## Live Authenticated Attempt Wave (current run)

This section records the current live run (T1-T9) using the evidence transcripts under `.sisyphus/evidence/live-qrevo-curv-2-flow/`. Historical help/pre-login outputs above are intentionally preserved.

### Command matrix (T1-T9)

| command | outcome | notes | evidence |
| --- | --- | --- | --- |
| `safety gate checklist (runbook validation)` | pass | T1 established required supervision, abort triggers, and emergency `pause -> stop -> charge` sequence before any actuating attempt. | [`task-1-safety-gate.txt`](../.sisyphus/evidence/live-qrevo-curv-2-flow/task-1-safety-gate.txt) |
| `evidence scaffold checks (naming + structure)` | pass | T2 validated strict transcript format and filename policy for deterministic auditability. | [`task-2-evidence-scaffold.txt`](../.sisyphus/evidence/live-qrevo-curv-2-flow/task-2-evidence-scaffold.txt) |
| `doc baseline snapshot` | pass | T3 captured pre-live baseline headings and pre-login command status before authenticated attempts. | [`task-3-doc-baseline.txt`](../.sisyphus/evidence/live-qrevo-curv-2-flow/task-3-doc-baseline.txt) |
| `rtk uv run roborock login --email pmaclyman@gmail.com --reauth` | resolved | The assistant’s direct non-interactive attempt originally stalled at the OTP prompt, but the blocker is now cleared: a valid authenticated cache exists locally and downstream authenticated CLI commands succeed against the real device. | [`task-4-login-success.txt`](../.sisyphus/evidence/live-qrevo-curv-2-flow/task-4-login-success.txt), [`task-4-login-failure.txt`](../.sisyphus/evidence/live-qrevo-curv-2-flow/task-4-login-failure.txt) |
| `rtk uv run roborock discover`; `rtk uv run roborock list-devices`; `rtk uv run roborock get-device-info` | pass | T5 now succeeds with authenticated state: `discover` finds `Qrevo Curv 2 Flow`, `list-devices` pins `7FjpPFODrdwoiHnJvL6eW2`, and `get-device-info` confirms `model: roborock.vacuum.a245` and `protocol_version: '1.0'`. A transient parallel-rerun cache-write race was observed, so the sequential reruns are the authoritative evidence. | [`task-5-discovery.txt`](../.sisyphus/evidence/live-qrevo-curv-2-flow/task-5-discovery.txt), [`task-5-device-selection.txt`](../.sisyphus/evidence/live-qrevo-curv-2-flow/task-5-device-selection.txt), [`task-5-model-confirmation.txt`](../.sisyphus/evidence/live-qrevo-curv-2-flow/task-5-model-confirmation.txt) |
| `rtk uv run roborock status --device_id definitely-invalid-device-id`; authenticated read-only sweep on `7FjpPFODrdwoiHnJvL6eW2` | mixed | T6 now reaches the real device and mostly works: `status`, `features`, `home`, `maps`, `consumables`, `clean-summary`, `network-info`, and `volume` succeed; the invalid-device negative case returns `Device ... not found`; `clean-record` fails with an authenticated CLI bug (`AttributeError: 'PropertiesApi' object has no attribute 'clean_record'`). | [`task-6-invalid-device.txt`](../.sisyphus/evidence/live-qrevo-curv-2-flow/task-6-invalid-device.txt), [`task-6-readonly-sweep.txt`](../.sisyphus/evidence/live-qrevo-curv-2-flow/task-6-readonly-sweep.txt) |
| `rtk uv run roborock set-volume` / `dnd` / `led-status` / `flow-led-status` / `child-lock`; `rtk uv run roborock command --cmd app_start|app_pause|app_stop|app_charge` | mixed | T7 is now live-validated. Volume, DND, LED, child-lock, and all four generic movement commands return success. `app_start` drives the robot into an active state and `app_stop`/`app_charge` return it to safe charging. `flow-led-status` is explicitly unsupported on this model, matching the feature map. Some toggle changes do not appear in immediate generic `status` snapshots even when the command-specific response confirms the change. | [`task-7-toggle-roundtrip.txt`](../.sisyphus/evidence/live-qrevo-curv-2-flow/task-7-toggle-roundtrip.txt), [`task-7-movement.txt`](../.sisyphus/evidence/live-qrevo-curv-2-flow/task-7-movement.txt) |
| `rtk uv run roborock session q10-vacuum-pause --device_id 7FjpPFODrdwoiHnJvL6eW2` | pass | T8 now reaches the intended protocol gate and returns the expected unsupported message: `Device does not support B01 Q10 protocol. Is it a Q10?` No anomaly path was triggered. | [`task-8-q10-unsupported.txt`](../.sisyphus/evidence/live-qrevo-curv-2-flow/task-8-q10-unsupported.txt), [`task-8-q10-anomaly.txt`](../.sisyphus/evidence/live-qrevo-curv-2-flow/task-8-q10-anomaly.txt) |
| `rtk uv run roborock status --device_id 7FjpPFODrdwoiHnJvL6eW2` | pass | T9 now verifies a safe terminal state. Live status returned `state: 8`, which maps to `charging` in `roborock/data/v1/v1_code_mappings.py`; `inCleaning: 0`, `inReturning: 0`, `chargeStatus: 1`, and `battery: 100` support the safe-state claim. | [`task-9-final-state.txt`](../.sisyphus/evidence/live-qrevo-curv-2-flow/task-9-final-state.txt), [`task-9-final-state-error.txt`](../.sisyphus/evidence/live-qrevo-curv-2-flow/task-9-final-state-error.txt) |

### Acceptance status and blocker summary

- T4 blocker is resolved: authenticated cache state now exists locally and downstream real-device commands succeed.
- T5 acceptance is now met: target device `7FjpPFODrdwoiHnJvL6eW2` is pinned to `Qrevo Curv 2 Flow` and live device info confirms `roborock.vacuum.a245`.
- T6 is substantially validated against live auth; the only remaining issue in this sweep is a real `clean-record` CLI implementation defect.
- T7 is live-validated; supported commands succeed, `flow-led-status` is correctly unsupported, and the robot is returned to charging afterward.
- T8 is now met with the expected protocol-mismatch message on the non-Q10 a245 device.
- T9 acceptance is now met: final live status confirms the robot is in `charging` state, not actively cleaning or returning.
- Historical blocker pattern was `RoborockNoResponseFromBaseURL`, with occasional `response code: 9002` during repeated blocked calls. Once valid auth cache was present, those blockers cleared.

### Rerun prerequisites

1. Use the pinned device id `7FjpPFODrdwoiHnJvL6eW2` for any follow-up live command validation.
2. Keep auth-refreshing CLI commands sequential when they rewrite `~/.roborock`; parallel retries can race and briefly corrupt reads.
3. `clean-record` is the main follow-up bug worth fixing in code; it failed under valid auth with `PropertiesApi` missing the expected trait.
4. Preserve the current safe-state baseline by ensuring any future actuating tests end with another authenticated `status` capture.

## Session-only commands found

The interactive session exposes extra commands:

- `q10-vacuum-start`
- `q10-vacuum-pause`
- `q10-vacuum-resume`
- `q10-vacuum-stop`
- `q10-vacuum-dock`
- `q10-empty-dustbin`
- `q10-set-clean-mode`
- `q10-set-fan-level`

These are session-only and are intended for the B01 Q10 path. Based on the local `device_info.yaml` entry for `Qrevo Curv 2 Flow` (`roborock.vacuum.a245`, protocol `1.0`), they are not the primary expected command path for this model. The generic `command` entrypoint can still route to multiple protocol paths at runtime, so this is a “primary path” conclusion, not an impossibility claim.

## Bottom line

The repo already contains explicit support metadata for `Qrevo Curv 2 Flow` as `roborock.vacuum.a245`.

Live command feedback is still fairly thin:
- many commands return only `ok`
- command success does not guarantee the visible job you wanted actually happened
- state verification still depends on manual `status` checks
- room-targeted runs require payload discovery and post-checks

Recent live observation:
- `app_segment_clean [1]` started a live cleaning run
- follow-up `status` showed `inCleaning: 3`, `fanPower: 102`, `waterBoxMode: 235`, `mopMode: 300`, and `washPhase: 13`
- that looks like a mop-capable cleaning cycle, not a strongly opinionated vacuum-only workflow

The recommended control flow for this vacuum is:
 
```powershell
uv run roborock login --email <email>
uv run roborock discover
uv run roborock list-devices
uv run roborock status --device_id <device_id>
```

After login, `home`, `features`, `maps`, `consumables`, and `command` are the next commands to use for richer control and inspection.
