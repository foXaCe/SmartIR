"""Tests for SmartIR diagnostics."""

from __future__ import annotations

from custom_components.smartir.diagnostics import async_get_config_entry_diagnostics


class TestDiagnostics:
    """Tests for async_get_config_entry_diagnostics."""

    async def test_redacts_sensitive_data(
        self, hass, mock_remote_entity, make_config_entry, mock_climate_device_data, setup_smartir_entry
    ) -> None:
        """controller_data, unique_id and entry_id are redacted; other fields are not."""
        entry = make_config_entry(
            device_type="climate",
            controller_data="remote.test_remote",
            temperature_sensor="sensor.temp",
        )
        await setup_smartir_entry(entry, mock_climate_device_data)

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["config_entry"]["entry_id"] == "**REDACTED**"
        assert result["config_entry"]["unique_id"] == "**REDACTED**"
        assert result["config_entry"]["data"]["controller_data"] == "**REDACTED**"
        assert result["runtime_data"]["controller_data"] == "**REDACTED**"
        assert result["runtime_data"]["unique_id"] == "**REDACTED**"

        # Non-sensitive fields survive untouched.
        assert result["config_entry"]["domain"] == "smartir"
        assert result["config_entry"]["version"] == 2
        assert result["runtime_data"]["device_type"] == "climate"
        assert result["runtime_data"]["temperature_sensor"] == "sensor.temp"
        assert result["integration_info"]["domain"] == "smartir"
        assert result["integration_info"]["device_code"] == 1000

    async def test_none_unique_id_is_not_redacted(
        self, hass, mock_remote_entity, mock_climate_device_data, setup_smartir_entry
    ) -> None:
        """A None unique_id (no CONF_UNIQUE_ID / entry.unique_id set) is left as None."""
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        from custom_components.smartir.const import DOMAIN

        entry = MockConfigEntry(
            domain=DOMAIN,
            version=2,
            data={"device_type": "climate", "controller": "broadlink", "controller_data": "remote.test_remote"},
            unique_id=None,
        )
        await setup_smartir_entry(entry, mock_climate_device_data)

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["runtime_data"]["unique_id"] is None
        assert result["config_entry"]["unique_id"] is None
