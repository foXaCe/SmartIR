"""Tests for the SmartIR config and options flow."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest

from custom_components.smartir.const import DOMAIN

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


def _schema_keys(result: dict) -> set[str]:
    """Return the field names of a shown form's schema."""
    return {str(key) for key in result["data_schema"].schema}


class TestUserStep:
    """Tests for async_step_user."""

    async def test_shows_form(self, hass: HomeAssistant) -> None:
        """The first step asks for the device type."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert "device_type" in _schema_keys(result)

    async def test_advances_to_controller_step(self, hass: HomeAssistant) -> None:
        """Selecting a device type advances to the controller step."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"device_type": "climate"})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "controller"


class TestControllerStep:
    """Tests for async_step_controller."""

    async def test_shows_form(self, hass: HomeAssistant) -> None:
        """The controller step asks for the controller type."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"device_type": "fan"})
        assert result["step_id"] == "controller"
        assert "controller" in _schema_keys(result)

    async def test_advances_to_device_config_step(self, hass: HomeAssistant) -> None:
        """Selecting a controller advances to the device_config step."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"device_type": "fan"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"controller": "broadlink"})
        assert result["step_id"] == "device_config"


class TestDeviceConfigStep:
    """Tests for async_step_device_config."""

    async def _to_device_config(self, hass: HomeAssistant, device_type: str, controller: str) -> dict:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"device_type": device_type})
        return await hass.config_entries.flow.async_configure(result["flow_id"], {"controller": controller})

    async def test_climate_schema_includes_temperature_and_humidity(self, hass: HomeAssistant) -> None:
        """The climate device_config schema includes temperature/humidity sensor fields."""
        result = await self._to_device_config(hass, "climate", "broadlink")
        keys = _schema_keys(result)
        assert {"temperature_sensor", "humidity_sensor", "power_sensor", "power_sensor_restore_state"} <= keys

    async def test_fan_schema_excludes_temperature_and_humidity(self, hass: HomeAssistant) -> None:
        """The fan device_config schema has no temperature/humidity sensor fields."""
        result = await self._to_device_config(hass, "fan", "broadlink")
        keys = _schema_keys(result)
        assert "temperature_sensor" not in keys
        assert "humidity_sensor" not in keys
        assert "power_sensor_restore_state" not in keys
        assert "power_sensor" in keys

    async def test_description_placeholder_help_url(self, hass: HomeAssistant) -> None:
        """The help URL placeholder points at the right platform's codes directory."""
        result = await self._to_device_config(hass, "fan", "broadlink")
        assert "device_code_help_url" in result["description_placeholders"]
        assert result["description_placeholders"]["device_code_help_url"].endswith("/codes/fan")

    async def test_controller_not_found_error(self, hass: HomeAssistant) -> None:
        """An unavailable controller entity surfaces the controller_not_found error."""
        result = await self._to_device_config(hass, "fan", "mqtt")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device_code": 5000, "controller_data": "remote.does_not_exist"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"controller_data": "controller_not_found"}

    async def test_full_flow_creates_entry(self, hass: HomeAssistant, mock_remote_entity) -> None:
        """A full user flow creates an entry with a coerced int device_code and stable unique_id."""
        result = await self._to_device_config(hass, "climate", "broadlink")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Living Room AC",
                "device_code": 1000,
                "controller_data": "remote.test_remote",
                "delay": 0.5,
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Living Room AC (Broadlink)"
        assert result["data"]["device_code"] == 1000
        assert isinstance(result["data"]["device_code"], int)
        assert result["data"]["controller"] == "broadlink"
        assert result["data"]["device_type"] == "climate"
        assert result["result"].unique_id == "smartir_climate_1000_remote.test_remote"
        assert result["result"].version == 2

    async def test_default_name_generated_when_missing(self, hass: HomeAssistant, mock_remote_entity) -> None:
        """A missing name falls back to 'SmartIR {device type label}'."""
        result = await self._to_device_config(hass, "light", "mqtt")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device_code": 42, "controller_data": "remote.test_remote"},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"]["name"] == "SmartIR Light"

    async def test_optional_sensors_included_when_provided(self, hass: HomeAssistant, mock_remote_entity) -> None:
        """Optional sensor fields are only present in the created entry's data when supplied."""
        result = await self._to_device_config(hass, "climate", "broadlink")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "device_code": 1234,
                "controller_data": "remote.test_remote",
                "temperature_sensor": "sensor.temp",
                "humidity_sensor": "sensor.humidity",
                "power_sensor": "sensor.power",
                "power_sensor_restore_state": True,
            },
        )
        assert result["data"]["temperature_sensor"] == "sensor.temp"
        assert result["data"]["humidity_sensor"] == "sensor.humidity"
        assert result["data"]["power_sensor"] == "sensor.power"
        assert result["data"]["power_sensor_restore_state"] is True

    async def test_optional_sensors_absent_when_not_provided(self, hass: HomeAssistant, mock_remote_entity) -> None:
        """Optional sensor fields are absent from the created entry's data when not supplied."""
        result = await self._to_device_config(hass, "fan", "broadlink")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device_code": 1234, "controller_data": "remote.test_remote"},
        )
        assert "temperature_sensor" not in result["data"]
        assert "power_sensor" not in result["data"]

    async def test_abort_if_unique_id_already_configured(self, hass: HomeAssistant, mock_remote_entity) -> None:
        """Configuring the exact same device/controller/code twice aborts the second time."""
        for _ in range(2):
            result = await self._to_device_config(hass, "climate", "broadlink")
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"device_code": 1000, "controller_data": "remote.test_remote"},
            )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


class TestReconfigureFlow:
    """Tests for async_step_reconfigure."""

    def _make_entry(self, hass: HomeAssistant):
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        entry = MockConfigEntry(
            domain=DOMAIN,
            version=2,
            unique_id="smartir_climate_1000_remote.test_remote",
            data={
                "device_type": "climate",
                "controller": "broadlink",
                "name": "Living Room AC",
                "device_code": 1000,
                "controller_data": "remote.test_remote",
                "delay": 0.5,
            },
        )
        entry.add_to_hass(hass)
        return entry

    async def test_shows_form_with_current_values(self, hass: HomeAssistant, mock_remote_entity) -> None:
        """The reconfigure form is pre-filled with the entry's current data."""
        entry = self._make_entry(hass)
        result = await entry.start_reconfigure_flow(hass)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"
        keys = _schema_keys(result)
        assert {"device_code", "controller_data", "delay"} <= keys

    async def test_controller_not_found_error(self, hass: HomeAssistant, mock_remote_entity) -> None:
        """An unavailable controller entity surfaces the controller_not_found error."""
        entry = self._make_entry(hass)
        result = await entry.start_reconfigure_flow(hass)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device_code": 1000, "controller_data": "remote.does_not_exist", "delay": 0.5},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"controller_data": "controller_not_found"}

    async def test_updates_entry_and_aborts(self, hass: HomeAssistant, mock_remote_entity) -> None:
        """A valid reconfigure updates the entry data and aborts with reconfigure_successful."""
        entry = self._make_entry(hass)
        result = await entry.start_reconfigure_flow(hass)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device_code": 2000, "controller_data": "remote.test_remote", "delay": 1.0},
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert entry.data["device_code"] == 2000
        assert isinstance(entry.data["device_code"], int)
        assert entry.data["delay"] == 1.0
        # Fields not part of the reconfigure schema are preserved.
        assert entry.data["name"] == "Living Room AC"


class TestOptionsFlow:
    """Tests for SmartIROptionsFlow."""

    def _make_entry(self, hass: HomeAssistant):
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        entry = MockConfigEntry(
            domain=DOMAIN,
            version=2,
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
        return entry

    async def test_shows_form_prefilled(self, hass: HomeAssistant) -> None:
        """The options form pre-fills current values, including climate-only sensor fields."""
        entry = self._make_entry(hass)
        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        keys = _schema_keys(result)
        assert {"temperature_sensor", "humidity_sensor"} <= keys

    async def test_update_creates_entry(self, hass: HomeAssistant) -> None:
        """Submitting options creates an entry with the coerced device_code."""
        entry = self._make_entry(hass)
        result = await hass.config_entries.options.async_init(entry.entry_id)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"device_code": 5678, "delay": 1.0},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"]["device_code"] == 5678
        assert isinstance(result["data"]["device_code"], int)

    async def test_fan_options_exclude_temperature_fields(self, hass: HomeAssistant) -> None:
        """A fan entry's options schema has no temperature/humidity fields."""
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        entry = MockConfigEntry(
            domain=DOMAIN,
            version=2,
            data={"device_type": "fan", "controller": "xiaomi", "device_code": 1, "controller_data": "remote.x"},
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)
        keys = _schema_keys(result)
        assert "temperature_sensor" not in keys
        assert "humidity_sensor" not in keys
