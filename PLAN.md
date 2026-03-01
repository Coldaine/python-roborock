# Planning: Roborock Curv 2 Flow Integration & Matter Surface Probing

This document tracks the phased execution plan for probing and documenting the Roborock Curv 2 Flow (Qrevo Curv) API surface, both via the standard Cloud/Local protocol and the new Matter surface.

---

## Phase 1: Roborock Cloud/Local API Surface (python-roborock)

### Step 1 — Install the CLI and authenticate
```bash
pipx install python-roborock
roborock login   # OAuth with your Roborock account
roborock list-devices  # dumps device ID, model string, IP, token
```
This immediately tells you your vacuum's internal model ID (something like `roborock.vacuum.a??`), which you can cross-reference against the `python-roborock` [supported model list](https://python-roborock.readthedocs.io/en/latest/api_commands.html).

### Step 2 — Enumerate what the device responds to
The CLI has a raw command interface. Blast the documented command list at your device and note which ones return data vs. errors:
```bash
# Get current status
roborock get-prop --device-id <id> get_status

# Try all property getters in a loop
for cmd in get_status get_prop get_consumable get_summary get_clean_record get_room_mapping; do
  echo "=== $cmd ===" && roborock send-command --device-id <id> $cmd
done
```
Commands that return `{"error": ...}` or no data are your unsupported surface.

### Step 3 — Enable HA debug logging and trigger actions
Once HA is connected (even if partial), go to **Settings → System → Logs → Enable Debug** for the `roborock` integration and `python_roborock` library. Then:
1. Call `roborock.get_maps` from **Developer Tools → Actions** — this dumps room segment IDs and names.
2. Trigger a run via the UI and watch the debug log to see what properties are polled and what payloads come back.
3. Download the **Diagnostics file** from the device page (Settings → Devices → your vacuum → Download Diagnostics) — this is a JSON dump of every entity HA was able to populate.

The diagnostics file is your ground truth for what's actually working vs. showing as `unavailable`.

---

## Phase 2: Matter Surface Probe

### Step 1 — Commission via chip-tool
Install `chip-tool` on your Linux home lab machine and commission the Curv 2 Flow to a local Matter fabric:
```bash
# Install via snap (easiest on Linux)
sudo snap install chip-tool

# Commission with your device's setup code (shown in the Roborock app)
chip-tool pairing code <node-id> <setup-code>
```

### Step 2 — Read the device descriptor to discover supported clusters
This is the most important step — it dumps the full cluster manifest:
```bash
# Read descriptor cluster to list all supported clusters/endpoints
chip-tool descriptor read device-type-list <node-id> 0xFFFF
chip-tool descriptor read server-list <node-id> 1
```
For a robot vacuum, Matter defines the **RVC (Robotic Vacuum Cleaner) device type** (0x0075) with these candidate clusters:
- `RVCRunMode` — cleaning modes (Eco, Turbo, etc.)
- `RVCCleanMode` — vacuum vs. mop vs. hybrid
- `OperationalState` — start/stop/pause/dock
- `ServiceArea` — room/zone targeting (Matter 1.4+)

### Step 3 — Read and probe each cluster
```bash
# Check operational state
chip-tool operationalstate read current-state <node-id> 1

# List available run modes
chip-tool rvcrunmode read supported-modes <node-id> 1

# List available clean modes
chip-tool rvccleanmode read supported-modes <node-id> 1

# Check if ServiceArea (room targeting) is implemented
chip-tool servicearea read supported-areas <node-id> 1
```
Anything that returns actual data is part of your live Matter surface. Anything that returns `UNSUPPORTED_ATTRIBUTE` or `UNSUPPORTED_CLUSTER` is not implemented by Roborock's firmware yet.

---

## Phase 3: Document and Contribute Back

Once you have your findings — especially the model ID, which commands return valid data, and what the Diagnostics JSON looks like — you're in a position to open a GitHub issue or PR on `python-roborock`. The maintainer explicitly said for the Qrevo Curv line that they rely entirely on user-provided data since they don't have the hardware themselves. Your diagnostic dump could directly unblock support for your model for everyone.
