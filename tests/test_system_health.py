"""Tests for SmartIR system health."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.smartir.system_health import _CODE_DB_CHECK_URL, async_register, system_health_info


class TestAsyncRegister:
    """Tests for async_register."""

    def test_registers_info_callback(self, hass: HomeAssistant) -> None:
        """async_register wires system_health_info into the registration object."""
        register = MagicMock()

        async_register(hass, register)

        register.async_register_info.assert_called_once_with(system_health_info)


class TestSystemHealthInfo:
    """Tests for system_health_info."""

    async def test_reports_zero_configured_devices(self, hass: HomeAssistant) -> None:
        """No config entries means configured_devices is 0."""
        with patch(
            "custom_components.smartir.system_health.system_health.async_check_can_reach_url",
            MagicMock(return_value=True),
        ):
            result = await system_health_info(hass)

        assert result["configured_devices"] == 0

    async def test_counts_configured_entries(self, hass: HomeAssistant, make_config_entry) -> None:
        """Each config entry added to hass is counted."""
        entry_one = make_config_entry(device_type="climate")
        entry_two = make_config_entry(device_type="fan")
        entry_one.add_to_hass(hass)
        entry_two.add_to_hass(hass)

        with patch(
            "custom_components.smartir.system_health.system_health.async_check_can_reach_url",
            MagicMock(return_value=True),
        ):
            result = await system_health_info(hass)

        assert result["configured_devices"] == 2

    async def test_code_database_reachable_uses_check_url(self, hass: HomeAssistant) -> None:
        """The reachability check targets the code-database health-check URL."""
        with patch(
            "custom_components.smartir.system_health.system_health.async_check_can_reach_url",
            AsyncMock(return_value="ok"),
        ) as mock_check:
            result = await system_health_info(hass)

        mock_check.assert_called_once_with(hass, _CODE_DB_CHECK_URL)
        assert await result["code_database_reachable"] == "ok"
