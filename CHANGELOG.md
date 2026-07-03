# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.19.0](https://github.com/foXaCe/SmartIR/compare/smartir-v1.18.1...smartir-v1.19.0) (2026-07-03)


### Added

* :sparkles: Support for Kendal Split Inverter (YKR-T/121E remote) ([#1315](https://github.com/foXaCe/SmartIR/issues/1315)) ([e83ca13](https://github.com/foXaCe/SmartIR/commit/e83ca13b53eb181874764f554a95f0b5fa95ecce))
* add climate 1029 ([#658](https://github.com/foXaCe/SmartIR/issues/658)) ([ef62936](https://github.com/foXaCe/SmartIR/commit/ef6293626f42de84044e0e2b1b408ac269c848e4))
* Add climate support for Mitsubish Electric MSXY-FP10VG/MSXY-FP13VG/MSXY-FP18VG ([#975](https://github.com/foXaCe/SmartIR/issues/975)) ([4499b41](https://github.com/foXaCe/SmartIR/commit/4499b41e4f03cc15b0b647ac3092b151b9d3a32d))
* add codes for beko BPEU 120 ac ([#1191](https://github.com/foXaCe/SmartIR/issues/1191)) ([c717bd5](https://github.com/foXaCe/SmartIR/commit/c717bd5cd822fb23ecbdf68531a382ed741c2746))
* add quiet mode for Senville SENA/12HF/IZ ([#834](https://github.com/foXaCe/SmartIR/issues/834)) ([ec69090](https://github.com/foXaCe/SmartIR/commit/ec6909094b0b84023cb1ecb8d632e7140318e575))
* add support for Yamaha YAS-109 soundbar ([#1163](https://github.com/foXaCe/SmartIR/issues/1163)) ([a82c7de](https://github.com/foXaCe/SmartIR/commit/a82c7de53b8e25392dff1cf761e8c0ba1e670669))
* add tadiran tac-297 support ([#1088](https://github.com/foXaCe/SmartIR/issues/1088)) ([5ec5215](https://github.com/foXaCe/SmartIR/commit/5ec5215398c97abb3a1763880690f1e6718b7506))
* add torando master 35 control codes ([#1097](https://github.com/foXaCe/SmartIR/issues/1097)) ([9c13686](https://github.com/foXaCe/SmartIR/commit/9c13686669e7b4368e7d2e9653edcd2ff6226f84))
* Add Xiaomi IR codes for Mitsubishi AC units ([#1079](https://github.com/foXaCe/SmartIR/issues/1079)) ([e9d75da](https://github.com/foXaCe/SmartIR/commit/e9d75da64dc0ea33bf924f504d200799c7d6b3a4))
* Added new codes for control fan modes ([#905](https://github.com/foXaCe/SmartIR/issues/905)) ([b898857](https://github.com/foXaCe/SmartIR/commit/b898857011404a204f274d073adffbf6ae31d4bf))
* modular overhaul (api/+devices/), Gold quality scale, persistent custom codes ([#9](https://github.com/foXaCe/SmartIR/issues/9)) ([789afa8](https://github.com/foXaCe/SmartIR/commit/789afa81cf7ba680b9327cfb01a89ecd6a60ed47))
* quality-scale remediation (Bronze compliance, reconfigure, tests) ([#7](https://github.com/foXaCe/SmartIR/issues/7)) ([bf65f17](https://github.com/foXaCe/SmartIR/commit/bf65f17b2fdb8aa85ab10d0a93ea8a45a465ec4f))
* Sharp Aquos TV remote, add: dry mode to AR-JE5 (1286.json) ([#1150](https://github.com/foXaCe/SmartIR/issues/1150)) ([470fb4d](https://github.com/foXaCe/SmartIR/commit/470fb4de7dc246309f138e9ee1280e9cdeb2fd2b))


### Fixed

* reliable IR/RF command delivery (blocking + retry) + local brand icons ([#8](https://github.com/foXaCe/SmartIR/issues/8)) ([8849490](https://github.com/foXaCe/SmartIR/commit/8849490bdb5d32c516efb37a8b2c947e680ce1f4))

## [Unreleased]

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

[Unreleased]: https://github.com/foXaCe/SmartIR/compare/v1.18.1...HEAD
[1.18.1]: https://github.com/foXaCe/SmartIR/releases/tag/v1.18.1
