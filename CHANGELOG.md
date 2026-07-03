# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Config flow UI to set up devices from the interface (replaces YAML configuration)
- SmartIR Hub / central management support
- Diagnostics download support
- pytest test suite (climate, config flow, controller, init)

### Changed

- Modernized entities, config flow and controller internals
- Repository tooling: CI, pre-commit (prek), issue/PR templates, Renovate

### Fixed

- **Command reliability**: IR/RF commands are now sent with `blocking=True` and
  retried (3 attempts, 0.4 s backoff) so a transient WiFi packet loss on the
  controller (e.g. a Broadlink RM mini) no longer drops a command silently.
- Climate now reverts its state when a command ultimately fails after all
  retries, so the dashboard never shows a state the device did not reach.
- Config-flow bug where the selected temperature/humidity/power sensors were
  not persisted.

## [1.18.1]

### Added

- Baseline release inherited from upstream smartHomeHub/SmartIR

[Unreleased]: https://github.com/foXaCe/SmartIR/compare/v1.18.1...HEAD
[1.18.1]: https://github.com/foXaCe/SmartIR/releases/tag/v1.18.1
