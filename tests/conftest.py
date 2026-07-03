"""Fixtures for SmartIR tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
import pytest

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
def mock_climate_device_data() -> dict[str, Any]:
    """Create mock climate device data."""
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": ["Model A", "Model B"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "minTemperature": 16,
        "maxTemperature": 30,
        "precision": 1,
        "operationModes": ["off", "cool", "heat", "auto"],
        "fanModes": ["auto", "low", "medium", "high"],
        "swingModes": ["off", "vertical"],
        "commands": {
            "off": "test_off_command",
            "cool": {
                "16": {"auto": "test_cool_16_auto"},
                "24": {"auto": "test_cool_24_auto"},
            },
        },
    }


@pytest.fixture
def mock_fan_device_data() -> dict[str, Any]:
    """Create mock fan device data."""
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": ["Fan Model A"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "speed": ["off", "low", "medium", "high"],
        "commands": {
            "off": "test_off_command",
            "low": "test_low_command",
            "medium": "test_medium_command",
            "high": "test_high_command",
        },
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
def mock_aiofiles() -> Generator[MagicMock]:
    """Mock aiofiles for device code loading."""
    with patch("aiofiles.open") as mock_open:
        yield mock_open


@pytest.fixture
def mock_downloader() -> Generator[AsyncMock]:
    """Mock the Helper.downloader function."""
    with patch(
        "custom_components.smartir.Helper.downloader",
        new_callable=AsyncMock,
    ) as mock_dl:
        yield mock_dl
