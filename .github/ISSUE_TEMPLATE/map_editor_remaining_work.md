---
name: Map Editor - Remaining Work Tracking
about: Track remaining items for Local Map Editor production readiness
title: '[Map Editor] '
labels: ['map-editor', 'tracking']
assignees: []
---

## Map Editor Remaining Work

This issue tracks remaining work for the Local Map Editor feature.

### High Priority

- [ ] **Map Version Check Before Sync** (P1)
  - Call `MapVerifier.check_map_version()` before `execute_edits()` to prevent stale edits
  - File: `roborock/cli.py`
  - Related: `MapVerifier.check_map_version()` in `roborock/map/verifier.py`

- [ ] **Map Boundary Validation** (P2)
  - Prevent walls/zones outside map dimensions
  - File: `roborock/map/editor.py` (validation methods)

### Medium Priority

- [ ] **Complete Missing Edit Types**
  - [ ] `MopForbiddenZoneEdit` - Mop-only forbidden zones
  - [ ] `CarpetAreaEdit` - Carpet detection areas
  - [ ] `SetRoomOrderEdit` - Room cleaning sequence
  - Files: `roborock/map/editor.py`, `roborock/map/translation.py`

- [ ] **Physical Undo Support**
  - After sync, send inverse commands to device for undo
  - Currently undo only affects local virtual state
  - File: `roborock/cli.py`, `roborock/map/translation.py`

- [ ] **Polygon Zone Support**
  - Currently only rectangular zones supported `(x1,y1,x2,y2)`
  - Add polygon support for complex no-go areas
  - Files: `roborock/map/editor.py`, `roborock/map/geometry.py`

### Low Priority

- [ ] **Wall Intersection Detection**
  - Prevent crossing virtual walls that may confuse firmware

- [ ] **Firmware Error Code Mapping**
  - Map firmware-specific rejection codes to user-friendly messages

- [ ] **Multi-Device Coordination**
  - Edit tokens/leases for concurrent editing

---

## Completed ✅

- [x] Pre-sync backup & auto-rollback
- [x] Dynamic protocol detection (V1/B01/A01)
- [x] VirtualState persistence (JSON save/load)
- [x] Concurrency locks (asyncio.Lock)
- [x] E2E tests
- [x] Fix _bind_to_map side effects
