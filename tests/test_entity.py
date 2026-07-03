"""Tests for the shared SmartIR entity base and platform setup helper."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
import pytest

from custom_components.smartir.api.exceptions import DeviceDataError, DeviceDataNotFound
from custom_components.smartir.const import DOMAIN
from custom_components.smartir.entity import SmartIREntity, async_setup_smartir_platform


class _DummyEntity(SmartIREntity):
    """Minimal concrete entity used to exercise the shared base class."""

    PLATFORM = "climate"


@pytest.fixture
def entry(make_config_entry, hass: HomeAssistant, make_smartir_data):
    """Return a config entry with runtime_data already populated (as __init__.py would)."""
    config_entry = make_config_entry(device_type="climate")
    config_entry.add_to_hass(hass)
    config_entry.runtime_data = make_smartir_data(entry_id=config_entry.entry_id)
    return config_entry


class TestAsyncSetupSmartirPlatform:
    """Tests for async_setup_smartir_platform."""

    async def test_success_adds_entity(
        self, hass: HomeAssistant, entry, mock_climate_device_data: dict[str, Any], mock_controller: MagicMock
    ) -> None:
        """On success, a single entity is added and no repair issue is left behind."""
        async_add_entities = MagicMock()

        with (
            patch(
                "custom_components.smartir.entity.async_load_device_data",
                AsyncMock(return_value=mock_climate_device_data),
            ),
            patch("custom_components.smartir.entity.get_controller", return_value=mock_controller),
        ):
            await async_setup_smartir_platform(hass, entry, async_add_entities, "climate", _DummyEntity)

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], _DummyEntity)

        issue = ir.async_get(hass).async_get_issue(DOMAIN, f"device_data_{entry.entry_id}")
        assert issue is None

    async def test_controller_type_override(
        self, hass: HomeAssistant, entry, mock_climate_device_data: dict[str, Any], mock_controller: MagicMock
    ) -> None:
        """The config-entry controller type overrides the JSON supportedController."""
        async_add_entities = MagicMock()

        with (
            patch(
                "custom_components.smartir.entity.async_load_device_data",
                AsyncMock(return_value=mock_climate_device_data),
            ),
            patch("custom_components.smartir.entity.get_controller", return_value=mock_controller) as mock_get,
        ):
            await async_setup_smartir_platform(hass, entry, async_add_entities, "climate", _DummyEntity)

        entities = async_add_entities.call_args[0][0]
        assert entities[0]._supported_controller == "Broadlink"
        assert mock_get.call_args[0][1] == "Broadlink"

    async def test_device_data_not_found_creates_issue_and_raises(self, hass: HomeAssistant, entry) -> None:
        """A DeviceDataNotFound surfaces a repair issue and raises ConfigEntryNotReady."""
        async_add_entities = MagicMock()

        with (
            patch(
                "custom_components.smartir.entity.async_load_device_data",
                AsyncMock(side_effect=DeviceDataNotFound("nope")),
            ),
            pytest.raises(ConfigEntryNotReady),
        ):
            await async_setup_smartir_platform(hass, entry, async_add_entities, "climate", _DummyEntity)

        issue = ir.async_get(hass).async_get_issue(DOMAIN, f"device_data_{entry.entry_id}")
        assert issue is not None
        assert issue.translation_key == "device_data_unavailable"
        async_add_entities.assert_not_called()

    async def test_device_data_error_creates_issue_and_raises(self, hass: HomeAssistant, entry) -> None:
        """A DeviceDataError (invalid JSON) also surfaces a repair issue and raises."""
        async_add_entities = MagicMock()

        with (
            patch(
                "custom_components.smartir.entity.async_load_device_data",
                AsyncMock(side_effect=DeviceDataError("invalid json")),
            ),
            pytest.raises(ConfigEntryNotReady),
        ):
            await async_setup_smartir_platform(hass, entry, async_add_entities, "climate", _DummyEntity)

        issue = ir.async_get(hass).async_get_issue(DOMAIN, f"device_data_{entry.entry_id}")
        assert issue is not None

    async def test_success_deletes_stale_issue(
        self, hass: HomeAssistant, entry, mock_climate_device_data: dict[str, Any], mock_controller: MagicMock
    ) -> None:
        """A stale repair issue from a previous failed setup is cleared on success."""
        issue_id = f"device_data_{entry.entry_id}"
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="device_data_unavailable",
            translation_placeholders={"code": "1000", "platform": "climate"},
        )
        assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None

        async_add_entities = MagicMock()
        with (
            patch(
                "custom_components.smartir.entity.async_load_device_data",
                AsyncMock(return_value=mock_climate_device_data),
            ),
            patch("custom_components.smartir.entity.get_controller", return_value=mock_controller),
        ):
            await async_setup_smartir_platform(hass, entry, async_add_entities, "climate", _DummyEntity)

        assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


class TestSmartIREntityBase:
    """Tests for the SmartIREntity base class."""

    def _make_entity(self, hass, data, device_data, controller):
        with patch("custom_components.smartir.entity.get_controller", return_value=controller):
            return _DummyEntity(hass, data, device_data)

    def test_unique_id_and_device_info(
        self, hass: HomeAssistant, make_smartir_data, mock_climate_device_data, mock_controller: MagicMock
    ) -> None:
        """unique_id and device_info are derived from the entry id and device-code data."""
        data = make_smartir_data(entry_id="abc123", device_code=1000, name="Living Room AC")
        entity = self._make_entity(hass, data, mock_climate_device_data, mock_controller)

        assert entity.unique_id == "abc123_climate"
        device_info = entity.device_info
        assert device_info["identifiers"] == {(DOMAIN, "abc123")}
        assert device_info["name"] == "Living Room AC"
        assert device_info["manufacturer"] == "Test Manufacturer"
        assert device_info["model"] == "Model A, Model B"
        assert "climate/1000.json" in device_info["configuration_url"]

    def test_device_info_model_unknown_without_supported_models(
        self, hass: HomeAssistant, make_smartir_data, mock_climate_device_data, mock_controller: MagicMock
    ) -> None:
        """The model falls back to 'Unknown' when supportedModels is empty."""
        device_data = {**mock_climate_device_data, "supportedModels": []}
        data = make_smartir_data(entry_id="abc123")
        entity = self._make_entity(hass, data, device_data, mock_controller)

        assert entity.device_info["model"] == "Unknown"

    def test_command_error_wraps_exception(
        self, hass: HomeAssistant, make_smartir_data, mock_climate_device_data, mock_controller: MagicMock
    ) -> None:
        """_command_error returns a translatable HomeAssistantError carrying the original message."""
        data = make_smartir_data(entry_id="abc123")
        entity = self._make_entity(hass, data, mock_climate_device_data, mock_controller)

        err = entity._command_error(Exception("boom"))
        assert err.translation_domain == DOMAIN
        assert err.translation_key == "command_failed"
        assert err.translation_placeholders == {"error": "boom"}

    def test_extra_state_attributes(
        self, hass: HomeAssistant, make_smartir_data, mock_climate_device_data, mock_controller: MagicMock
    ) -> None:
        """extra_state_attributes exposes the shared device-code metadata."""
        data = make_smartir_data(entry_id="abc123", device_code=1000)
        entity = self._make_entity(hass, data, mock_climate_device_data, mock_controller)

        attrs = entity.extra_state_attributes
        assert attrs["device_code"] == 1000
        assert attrs["manufacturer"] == "Test Manufacturer"
        assert attrs["supported_models"] == ["Model A", "Model B"]
        assert attrs["supported_controller"] == "Broadlink"
        assert attrs["commands_encoding"] == "Base64"

    def test_get_controller_called_with_resolved_parameters(
        self, hass: HomeAssistant, make_smartir_data, mock_climate_device_data, mock_controller: MagicMock
    ) -> None:
        """get_controller is invoked with the device's controller/encoding/data/delay."""
        data = make_smartir_data(entry_id="abc123", controller_data="remote.blaster", delay=1.5)

        with patch(
            "custom_components.smartir.entity.get_controller", return_value=mock_controller
        ) as mock_get_controller:
            _DummyEntity(hass, data, mock_climate_device_data)

        mock_get_controller.assert_called_once_with(hass, "Broadlink", "Base64", "remote.blaster", 1.5)
