# Adding New Devices to python-roborock

This document outlines the workflow and necessary steps for adding a new Roborock device (specifically, the Qrevo Curv 2 Flow) to the `python-roborock` library, based on the project's documentation (`CONTRIBUTING.md`, `README.md`, and CLI structure).

## 1. Device Discovery & Feature Extraction

The primary method for adding a new device is to extract its hardware capabilities directly from the Roborock cloud using the built-in CLI tools.

### Relevant CLI Commands (`roborock/cli.py`)
- **Authentication:** `uv run roborock login --email <your-email>`
  - Uses an interactive Email + OTP flow. Stores credentials locally in `~/.roborock`.
- **Information Gathering:** `uv run roborock get-device-info`
  - Connects to the API, queries the devices, and outputs their specific feature sets, protocol versions, and internal model IDs in YAML format.

### Required Data
From the `get-device-info` output, we need:
- `model`: The internal identifier (e.g., `roborock.vacuum.a15X`).
- `protocol_version`: Typically `v1` for standard vacuums or `a01`/`b01` for others.
- `new_feature_info` & `feature_info`: Hex strings and integer lists that map to the physical capabilities of the vacuum (e.g., SpiraFlow roller, specific camera types, mop modules).

## 2. Codebase Updates

Once the device data is acquired, the following files must be updated to fully integrate the new model:

### `device_info.yaml`
- **Action:** Paste the YAML output from `get-device-info` directly into this file.
- **Purpose:** Acts as the source of truth for generating the supported features documentation.

### `roborock/data/code_mappings.py`
- **Action:** Add the new internal model ID to the appropriate product family enum (e.g., the `VIVIAN` series `ProductInfo` tuple).
- **Purpose:** Maps the raw model string to a readable nickname and groups it with similar devices.

### `roborock/device_features.py`
- **Action:** Define the specific capabilities of the new model by mapping its `RoborockProductNickname` to a list of `ProductFeatures` (e.g., `CLEANMODE_MAXPLUS`, `MOP_SPIN_MODULE`).
- **Purpose:** Tells the library which API commands (fan speeds, mop intensities, dock controls) the vacuum supports.

### `roborock/const.py` (Optional)
- **Action:** If the device requires specific constant mappings or overrides, add them here.

## 3. Testing & Documentation

As per `CONTRIBUTING.md`:

### Test Data
- **Action:** Capture the Home API data for the new device and save it as `tests/testdata/home_data_device_<device_name>.json`.
- **Purpose:** Ensures device discovery and initialization tests pass during CI.

### Documentation
- **Action:** Run `uv run roborock update-docs` after modifying `device_info.yaml`.
- **Purpose:** Automatically regenerates `SUPPORTED_FEATURES.md` based on the new device capabilities.

## Summary Workflow for Curv 2 Flow

1. User runs `uv run roborock login --email <email>` and completes OTP.
2. User runs `uv run roborock get-device-info` and provides the YAML output.
3. Agent updates `device_info.yaml`, `code_mappings.py`, and `device_features.py`.
4. Agent runs `uv run roborock update-docs`.
5. Agent requests/creates test JSON fixtures.
6. Agent runs `uv run pytest` and `uv run pre-commit run --all-files` to validate.