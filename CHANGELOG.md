# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.19.0](https://github.com/foXaCe/SmartIR/compare/smartir-v1.18.1...smartir-v1.19.0) (2026-07-03)

### Added

- **Persistent custom codes**: device codes placed in
  `<config>/smartir_custom_codes/<platform>/<code>.json` survive integration
  updates and take priority over the bundled/downloaded codes (resolution order:
  custom → bundled → download)
- Config flow UI to set up devices from the interface (replaces YAML configuration)
- Options and reconfigure flows with modern selectors (number/boolean/text/entity)
- Diagnostics download support
- Repair issue raised when a device code cannot be loaded, guiding the user to reconfigure
- System health panel (configured device count, code-database reachability)
- Quality Scale tracking (`quality_scale.yaml`, Gold) and complete strict typing
- Exhaustive pytest suite across every module

### Changed

- **Modular architecture**: split into `api/` (controllers, code database,
  typed exceptions) and `devices/` (one entity per device type) on top of a
  shared `SmartIREntity` base and setup helper
- Entities modernized (`_attr_*`, `DeviceInfo`, `MediaPlayerDeviceClass`,
  `HVACMode`/`MediaPlayerState` enums, translatable errors)
- `unique_id` re-keyed onto the config entry id (schema v2); existing devices
  are migrated automatically without losing history or automations
- Repository tooling: CI, pre-commit (prek), issue/PR templates, Renovate

### Fixed

- **Command reliability**: IR/RF commands are now sent with `blocking=True` and
  retried (3 attempts, 0.4 s backoff) so a transient WiFi packet loss on the
  controller (e.g. a Broadlink RM mini) no longer drops a command silently
- Entities revert optimistic state and raise `HomeAssistantError` when a command
  ultimately fails, so the dashboard never shows a state the device never reached
- The controller selected in the config flow is now actually honored (it was
  silently ignored in favor of the code file's controller)
- Config-flow deprecation removed: reconfigure no longer double-reloads the entry
  (would have broken in HA 2026.12)
- Version reported by the integration is now consistent across all files

### Removed

- Dead, never-wired hub/sensor scaffolding and an accidentally committed 256 KB
  device-code cache file

## [1.18.1]

### Added

- Baseline release inherited from upstream smartHomeHub/SmartIR

[1.18.1]: https://github.com/foXaCe/SmartIR/releases/tag/v1.18.1
