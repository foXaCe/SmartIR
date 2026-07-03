"""Tests for SmartIR config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smartir.const import CONTROLLER_TYPES, DEVICE_TYPES, DOMAIN


@pytest.fixture
def mock_setup_entry() -> AsyncMock:
    """Mock async_setup_entry."""
    with patch(
        "custom_components.smartir.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


class TestSmartIRConfigFlow:
    """Tests for SmartIRConfigFlow."""

    async def test_step_user_show_form(self, hass: HomeAssistant) -> None:
        """Test user step shows form on empty input."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert "device_type" in result["data_schema"].schema

    async def test_step_user_select_climate(
        self,
        hass: HomeAssistant,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test user step with climate device type."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"device_type": "climate"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "controller"

    async def test_step_user_select_fan(
        self,
        hass: HomeAssistant,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test user step with fan device type."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"device_type": "fan"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "controller"

    async def test_step_user_select_media_player(
        self,
        hass: HomeAssistant,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test user step with media_player device type."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"device_type": "media_player"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "controller"

    async def test_step_user_select_light(
        self,
        hass: HomeAssistant,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test user step with light device type."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"device_type": "light"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "controller"


class TestControllerStep:
    """Tests for controller selection step."""

    async def test_step_controller_show_form(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test controller step shows form on navigation."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"device_type": "climate"},
        )

        # After selecting device_type, we should be on controller step
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "controller"

    async def test_step_controller_select_broadlink(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test controller step with Broadlink selection."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"device_type": "climate"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"controller": "broadlink"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "device_config"

    async def test_step_controller_select_xiaomi(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test controller step with Xiaomi selection."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"device_type": "fan"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"controller": "xiaomi"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "device_config"

    async def test_step_controller_select_mqtt(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test controller step with MQTT selection."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"device_type": "light"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"controller": "mqtt"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "device_config"


class TestDeviceConfigStep:
    """Tests for device configuration step."""

    async def test_step_device_config_show_form(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test device_config step shows form on navigation."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"device_type": "climate"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"controller": "broadlink"},
        )

        # After selecting controller, we should be on device_config step
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "device_config"


class TestFullConfigFlow:
    """Tests for complete config flow."""

    async def test_full_flow_climate_broadlink(
        self,
        hass: HomeAssistant,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test complete flow for climate device with Broadlink controller."""
        hass.states.async_set("remote.test_remote", "on")

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device_type": "climate"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "controller"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"controller": "broadlink"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "device_config"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Test Climate",
                "device_code": 1234,
                "controller_data": "remote.test_remote",
                "delay": 0.5,
            },
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "Test Climate (Broadlink)"
        assert result["data"]["device_type"] == "climate"
        assert result["data"]["controller"] == "broadlink"
        assert result["data"]["device_code"] == 1234
        assert result["data"]["controller_data"] == "remote.test_remote"

    async def test_full_flow_fan_xiaomi(
        self,
        hass: HomeAssistant,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test complete flow for fan device with Xiaomi controller."""
        hass.states.async_set("remote.test_remote", "on")

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device_type": "fan"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"controller": "xiaomi"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Test Fan",
                "device_code": 5678,
                "controller_data": "remote.test_remote",
            },
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"]["device_type"] == "fan"
        assert result["data"]["controller"] == "xiaomi"

    async def test_full_flow_light_mqtt(
        self,
        hass: HomeAssistant,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test complete flow for light device with MQTT controller."""
        hass.states.async_set("remote.test_remote", "on")

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device_type": "light"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"controller": "mqtt"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Test Light",
                "device_code": 9999,
                "controller_data": "remote.test_remote",
            },
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"]["device_type"] == "light"
        assert result["data"]["controller"] == "mqtt"

    async def test_full_flow_media_player_esphome(
        self,
        hass: HomeAssistant,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test complete flow for media_player device with ESPHome controller."""
        hass.states.async_set("remote.test_remote", "on")

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device_type": "media_player"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"controller": "esphome"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Test TV",
                "device_code": 1111,
                "controller_data": "remote.test_remote",
            },
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"]["device_type"] == "media_player"
        assert result["data"]["controller"] == "esphome"

    async def test_full_flow_with_optional_sensors(
        self,
        hass: HomeAssistant,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test complete flow with optional sensors for climate."""
        hass.states.async_set("remote.test_remote", "on")
        hass.states.async_set("sensor.temp", "22")
        hass.states.async_set("sensor.humidity", "65")
        hass.states.async_set("sensor.power", "100")

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device_type": "climate"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"controller": "broadlink"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Test AC",
                "device_code": 1234,
                "controller_data": "remote.test_remote",
                "delay": 1.0,
                "temperature_sensor": "sensor.temp",
                "humidity_sensor": "sensor.humidity",
                "power_sensor": "sensor.power",
                "power_sensor_restore_state": True,
            },
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"]["delay"] == 1.0


class TestSmartIROptionsFlow:
    """Tests for SmartIROptionsFlow."""

    async def test_options_flow_show_form(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test options flow shows form."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Climate (Broadlink)",
            data={
                "device_type": "climate",
                "controller": "broadlink",
                "name": "Test Climate",
                "device_code": 1234,
                "controller_data": "remote.test_remote",
            },
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

    async def test_options_flow_update(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test options flow updates configuration."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Climate (Broadlink)",
            data={
                "device_type": "climate",
                "controller": "broadlink",
                "name": "Test Climate",
                "device_code": 1234,
                "controller_data": "remote.test_remote",
            },
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "device_code": 5678,
                "delay": 1.0,
            },
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    async def test_options_flow_climate_with_sensors(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test options flow for climate with sensors."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Climate (Broadlink)",
            data={
                "device_type": "climate",
                "controller": "broadlink",
                "name": "Test Climate",
                "device_code": 1234,
                "controller_data": "remote.test_remote",
                "temperature_sensor": "sensor.temp",
                "humidity_sensor": "sensor.humidity",
            },
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

    async def test_options_flow_fan(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test options flow for fan device."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Fan (Xiaomi)",
            data={
                "device_type": "fan",
                "controller": "xiaomi",
                "name": "Test Fan",
                "device_code": 5678,
                "controller_data": "remote.test_remote",
            },
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"


class TestConfigFlowHelpers:
    """Tests for config flow helper functionality."""

    async def test_device_code_help_url_climate(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test device code help URL for climate."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"device_type": "climate"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"controller": "broadlink"},
        )

        assert "device_code_help_url" in result["description_placeholders"]
        assert "climate" in result["description_placeholders"]["device_code_help_url"]

    async def test_device_code_help_url_fan(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test device code help URL for fan."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"device_type": "fan"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"controller": "broadlink"},
        )

        assert "device_code_help_url" in result["description_placeholders"]
        assert "fan" in result["description_placeholders"]["device_code_help_url"]

    async def test_default_name_generation(
        self,
        hass: HomeAssistant,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test default name is generated when not provided."""
        hass.states.async_set("remote.test_remote", "on")

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device_type": "climate"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"controller": "broadlink"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "device_code": 1234,
                "controller_data": "remote.test_remote",
            },
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        # Name should be generated from DEVICE_TYPES
        assert "name" in result["data"]