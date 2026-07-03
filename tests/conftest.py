"""Fixtures for SmartIR tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smartir.const import (
    CONF_CONTROLLER_DATA,
    CONF_CONTROLLER_TYPE,
    CONF_DEVICE_CODE,
    CONF_DEVICE_TYPE,
    CONF_NAME,
    DOMAIN,
    SmartIRData,
)

pytest_plugins = ("pytest_homeassistant_custom_component",)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: bool) -> None:
    """Enable custom integrations in all tests."""
    return


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.smartir.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_controller() -> MagicMock:
    """Create a mock IR/RF controller with an AsyncMock send()."""
    controller = MagicMock()
    controller.send = AsyncMock()
    return controller


@pytest.fixture
def mock_climate_device_data() -> dict[str, Any]:
    """Create a full climate device-code fixture (all modes/fans/swings/temps)."""
    modes = ["cool", "heat", "auto", "dry", "fan_only"]
    fans = ["auto", "low", "medium", "high"]
    swings = ["off", "vertical"]
    temps = [str(t) for t in range(16, 31)]
    commands: dict[str, Any] = {"off": "test_off_command", "on": "test_on_command"}
    for mode in modes:
        commands[mode] = {
            fan: {swing: {temp: f"cmd_{mode}_{fan}_{swing}_{temp}" for temp in temps} for swing in swings}
            for fan in fans
        }
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": ["Model A", "Model B"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "minTemperature": 16,
        "maxTemperature": 30,
        "precision": 1,
        "operationModes": modes,
        "fanModes": fans,
        "swingModes": swings,
        "commands": commands,
    }


@pytest.fixture
def mock_climate_device_data_no_swing() -> dict[str, Any]:
    """Create climate device data without swing modes."""
    modes = ["cool", "heat"]
    fans = ["auto", "low", "high"]
    temps = [str(t) for t in range(18, 29)]
    commands: dict[str, Any] = {"off": "test_off_command"}
    for mode in modes:
        commands[mode] = {fan: {temp: f"cmd_{mode}_{fan}_{temp}" for temp in temps} for fan in fans}
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": ["Model C"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "minTemperature": 18,
        "maxTemperature": 28,
        "precision": 1,
        "operationModes": modes,
        "fanModes": fans,
        "commands": commands,
    }


@pytest.fixture
def mock_fan_device_data() -> dict[str, Any]:
    """Create fan device data without direction/oscillate (uses the 'default' direction)."""
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": ["Fan Model A"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "speed": ["low", "medium", "high"],
        "commands": {
            "off": "test_off_command",
            "default": {
                "low": "test_low_command",
                "medium": "test_medium_command",
                "high": "test_high_command",
            },
        },
    }


@pytest.fixture
def mock_fan_device_data_full() -> dict[str, Any]:
    """Create fan device data with direction and oscillate support."""
    return {
        "manufacturer": "Test Fan Manufacturer",
        "supportedModels": ["Fan Model C"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "speed": ["low", "medium", "high"],
        "commands": {
            "off": "cmd_off",
            "oscillate": "cmd_oscillate",
            "forward": {"low": "cmd_forward_low", "medium": "cmd_forward_medium", "high": "cmd_forward_high"},
            "reverse": {"low": "cmd_reverse_low", "medium": "cmd_reverse_medium", "high": "cmd_reverse_high"},
        },
    }


@pytest.fixture
def mock_light_device_data() -> dict[str, Any]:
    """Create light device data with color temp, brightness and night light."""
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": ["Light Model A", "Light Model B"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "brightness": [10, 50, 100],
        "colorTemperature": [2700, 4000, 6500],
        "commands": {
            "on": "cmd_on",
            "off": "cmd_off",
            "brighten": "cmd_brighten",
            "dim": "cmd_dim",
            "colder": "cmd_colder",
            "warmer": "cmd_warmer",
            "night": "cmd_night",
        },
    }


@pytest.fixture
def mock_light_device_data_brightness_only() -> dict[str, Any]:
    """Create light device data supporting brightness only (no color temp)."""
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": ["Light Model C"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "brightness": [10, 50, 100],
        "colorTemperature": [],
        "commands": {"on": "cmd_on", "off": "cmd_off", "brighten": "cmd_brighten", "dim": "cmd_dim"},
    }


@pytest.fixture
def mock_light_device_data_night_only() -> dict[str, Any]:
    """Create light device data supporting a night light only (no brighten/dim)."""
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": ["Light Model E"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "brightness": [],
        "colorTemperature": [],
        "commands": {"on": "cmd_on", "off": "cmd_off", "night": "cmd_night"},
    }


@pytest.fixture
def mock_light_device_data_onoff_only() -> dict[str, Any]:
    """Create light device data supporting only on/off."""
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": ["Light Model D"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "brightness": [],
        "colorTemperature": [],
        "commands": {"on": "cmd_on", "off": "cmd_off"},
    }


@pytest.fixture
def mock_media_player_device_data() -> dict[str, Any]:
    """Create media player device data with a full command set."""
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": ["Model A", "Model B"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "commands": {
            "off": "cmd_off",
            "on": "cmd_on",
            "previousChannel": "cmd_previous_channel",
            "nextChannel": "cmd_next_channel",
            "volumeDown": "cmd_volume_down",
            "volumeUp": "cmd_volume_up",
            "mute": "cmd_mute",
            "sources": {
                "HDMI 1": "cmd_hdmi1",
                "HDMI 2": "cmd_hdmi2",
                "Channel 0": "cmd_channel_0",
                "Channel 1": "cmd_channel_1",
                "Channel 2": "cmd_channel_2",
                "Channel 3": "cmd_channel_3",
                "Channel 4": "cmd_channel_4",
                "Channel 5": "cmd_channel_5",
                "Channel 6": "cmd_channel_6",
                "Channel 7": "cmd_channel_7",
                "Channel 8": "cmd_channel_8",
                "Channel 9": "cmd_channel_9",
            },
        },
    }


@pytest.fixture
def mock_media_player_device_data_minimal() -> dict[str, Any]:
    """Create media player device data without optional commands."""
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": [],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "commands": {},
    }


@pytest.fixture
def mock_remote_entity(hass: HomeAssistant) -> None:
    """Create a mock remote entity."""
    hass.states.async_set("remote.test_remote", "on", {"friendly_name": "Test Remote"})


@pytest.fixture
def mock_temperature_sensor(hass: HomeAssistant) -> None:
    """Create a mock temperature sensor."""
    hass.states.async_set(
        "sensor.test_temperature",
        "22.5",
        {"friendly_name": "Test Temperature", "device_class": "temperature", "unit_of_measurement": "°C"},
    )


@pytest.fixture
def mock_power_sensor(hass: HomeAssistant) -> None:
    """Create a mock power sensor."""
    hass.states.async_set(
        "sensor.test_power",
        "100",
        {"friendly_name": "Test Power", "device_class": "power", "unit_of_measurement": "W"},
    )


@pytest.fixture
def make_smartir_data() -> Any:
    """Return a factory building a SmartIRData with sensible defaults."""

    def _make(**overrides: Any) -> SmartIRData:
        defaults: dict[str, Any] = {
            "device_type": "climate",
            "controller_type": "broadlink",
            "name": "Test Device",
            "device_code": 1000,
            "controller_data": "remote.test_remote",
            "entry_id": "test_entry_id",
            "delay": 0.5,
        }
        defaults.update(overrides)
        return SmartIRData(**defaults)

    return _make


@pytest.fixture
def make_config_entry() -> Any:
    """Return a factory building a v2 MockConfigEntry for SmartIR."""

    def _make(
        device_type: str = "climate", controller_type: str = "broadlink", **data_overrides: Any
    ) -> MockConfigEntry:
        data: dict[str, Any] = {
            CONF_DEVICE_TYPE: device_type,
            CONF_CONTROLLER_TYPE: controller_type,
            CONF_NAME: "Test Device",
            CONF_DEVICE_CODE: 1000,
            CONF_CONTROLLER_DATA: "remote.test_remote",
        }
        data.update(data_overrides)
        return MockConfigEntry(
            domain=DOMAIN,
            version=2,
            data=data,
            unique_id=f"smartir_{device_type}_1000_remote.test_remote",
        )

    return _make


@pytest.fixture
def setup_smartir_entry(hass: HomeAssistant) -> Any:
    """Return a factory that sets up a SmartIR config entry with device data/controller mocked."""

    async def _setup(
        entry: MockConfigEntry,
        device_data: dict[str, Any],
        controller: MagicMock | None = None,
    ) -> tuple[bool, MagicMock]:
        used_controller = controller or MagicMock(send=AsyncMock())
        entry.add_to_hass(hass)
        with (
            patch(
                "custom_components.smartir.entity.async_load_device_data",
                AsyncMock(return_value=device_data),
            ),
            patch(
                "custom_components.smartir.entity.get_controller",
                return_value=used_controller,
            ),
        ):
            result = await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
        return result, used_controller

    return _setup
