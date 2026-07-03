# Development

## Setup

```bash
pipx install prek   # Rust pre-commit runner (drop-in)
scripts/setup       # installs dev dependencies + git hooks
```

Or open the repository in the provided [.devcontainer](../.devcontainer/).

## Common tasks

| Command | Description |
|---------|-------------|
| `scripts/lint` | Run ruff check + format check |
| `scripts/test` | Run the pytest suite with coverage |
| `scripts/develop` | Launch a local Home Assistant with the integration mounted |
| `prek run --all-files` | Run all pre-commit hooks |

## Testing

Tests use [`pytest-homeassistant-custom-component`](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component).

```bash
pytest tests/ -v
```

## Releasing

Releases are automated with **release-please** — see [`scripts/release`](../scripts/release).
Push conventional commits to `main`; merge the generated Release PR to publish.

## Architecture

See [ARCHITECTURE.md](../ARCHITECTURE.md).
