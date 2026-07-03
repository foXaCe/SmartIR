"""Tests for the SmartIR integration setup/unload/options lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import pytest

from custom_components.smartir import CONFIG_SCHEMA, async_setup_entry, async_unload_entry, async_update_options
from custom_components.smartir.const import DOMAIN


class TestConfigSchema:
    """Tests for the module-level CONFIG_SCHEMA."""

    def test_accepts_empty_config(self) -> None:
        """An empty configuration.yaml passes through untouched."""
        assert CONFIG_SCHEMA({}) == {}

    def test_yaml_domain_key_does_not_raise(self) -> None:
        """A (unsupported) YAML block for the domain is logged, not rejected."""
        config = {DOMAIN: {}}
        assert CONFIG_SCHEMA(config) == config


class TestAsyncSetupEntry:
    """Tests for async_setup_entry (direct calls, not via config_entries)."""

    async def test_not_ready_when_controller_missing(self, hass: HomeAssistant, make_config_entry) -> None:
        """A configured but unavailable controller entity blocks setup with ConfigEntryNotReady."""
        entry = make_config_entry(controller_data="remote.does_not_exist")
        entry.add_to_hass(hass)

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)

    async def test_not_ready_via_config_entries(self, hass: HomeAssistant, make_config_entry) -> None:
        """Setting up through hass.config_entries schedules a retry."""
        entry = make_config_entry(controller_data="remote.does_not_exist")
        entry.add_to_hass(hass)

        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY

    async def test_missing_controller_data_skips_availability_check(
        self, hass: HomeAssistant, make_config_entry, mock_climate_device_data, mock_controller
    ) -> None:
        """An empty controller_data does not trigger the 'must exist' check."""
        entry = make_config_entry(controller_data="")
        entry.add_to_hass(hass)

        with (
            patch(
                "custom_components.smartir.entity.async_load_device_data",
                AsyncMock(return_value=mock_climate_device_data),
            ),
            patch("custom_components.smartir.entity.get_controller", return_value=mock_controller),
        ):
            assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

    async def test_runtime_data_populated_from_config(
        self, hass: HomeAssistant, mock_remote_entity, make_config_entry, mock_climate_device_data, mock_controller
    ) -> None:
        """runtime_data reflects the config entry's data with proper defaults/coercion."""
        entry = make_config_entry(
            device_type="climate",
            controller_type="broadlink",
            device_code="1234",
            controller_data="remote.test_remote",
            temperature_sensor="sensor.temp",
            humidity_sensor="sensor.humidity",
            power_sensor="sensor.power",
            power_sensor_restore_state=True,
        )
        entry.add_to_hass(hass)

        with (
            patch(
                "custom_components.smartir.entity.async_load_device_data",
                AsyncMock(return_value=mock_climate_device_data),
            ),
            patch("custom_components.smartir.entity.get_controller", return_value=mock_controller),
        ):
            assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        data = entry.runtime_data
        assert data.device_type == "climate"
        assert data.controller_type == "broadlink"
        assert data.device_code == 1234
        assert isinstance(data.device_code, int)
        assert data.controller_data == "remote.test_remote"
        assert data.temperature_sensor == "sensor.temp"
        assert data.humidity_sensor == "sensor.humidity"
        assert data.power_sensor == "sensor.power"
        assert data.power_sensor_restore_state is True
        assert data.delay == 0.5
        assert data.entry_id == entry.entry_id
        assert data.unique_id == entry.unique_id
        assert data.extra == {}

    async def test_default_name_and_delay_when_missing(
        self, hass: HomeAssistant, mock_remote_entity, mock_climate_device_data, mock_controller
    ) -> None:
        """A missing name/delay fall back to their computed/default values."""
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        entry = MockConfigEntry(
            domain=DOMAIN,
            version=2,
            data={"device_type": "climate", "controller": "broadlink", "controller_data": "remote.test_remote"},
        )
        entry.add_to_hass(hass)

        with (
            patch(
                "custom_components.smartir.entity.async_load_device_data",
                AsyncMock(return_value=mock_climate_device_data),
            ),
            patch("custom_components.smartir.entity.get_controller", return_value=mock_controller),
        ):
            assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.runtime_data.name == "SmartIR Climate"
        assert entry.runtime_data.delay == 0.5
        assert entry.runtime_data.device_code == 0

    async def test_extra_includes_device_class_and_source_names_when_present(self, hass: HomeAssistant) -> None:
        """The 'extra' dict only contains device_class/source_names if provided."""
        hass.states.async_set("remote.test_remote", "on", {})
        entry = MagicMock()
        entry.data = {
            "device_type": "media_player",
            "controller": "broadlink",
            "controller_data": "remote.test_remote",
            "device_code": 1,
            "device_class": "speaker",
            "source_names": {"HDMI 1": "Apple TV"},
        }
        entry.options = {}
        entry.entry_id = "entry-extra"
        entry.unique_id = "uid-extra"
        entry.async_on_unload = MagicMock()
        entry.add_update_listener = MagicMock(return_value=MagicMock())

        with patch.object(hass.config_entries, "async_forward_entry_setups", new=AsyncMock()) as forward:
            assert await async_setup_entry(hass, entry)

        forward.assert_called_once_with(entry, ["media_player"])
        assert entry.runtime_data.extra == {"device_class": "speaker", "source_names": {"HDMI 1": "Apple TV"}}

    async def test_extra_empty_when_absent(self, hass: HomeAssistant) -> None:
        """The 'extra' dict is empty when device_class/source_names are absent."""
        entry = MagicMock()
        entry.data = {"device_type": "fan", "controller_data": ""}
        entry.options = {}
        entry.entry_id = "entry-noextra"
        entry.unique_id = None
        entry.async_on_unload = MagicMock()
        entry.add_update_listener = MagicMock(return_value=MagicMock())

        with patch.object(hass.config_entries, "async_forward_entry_setups", new=AsyncMock()):
            assert await async_setup_entry(hass, entry)

        assert entry.runtime_data.extra == {}

    async def test_options_override_data(self, hass: HomeAssistant) -> None:
        """Options take precedence over data when merging the effective config."""
        entry = MagicMock()
        entry.data = {"device_type": "fan", "controller_data": "", "device_code": 1}
        entry.options = {"device_code": 2}
        entry.entry_id = "entry-opts"
        entry.unique_id = None
        entry.async_on_unload = MagicMock()
        entry.add_update_listener = MagicMock(return_value=MagicMock())

        with patch.object(hass.config_entries, "async_forward_entry_setups", new=AsyncMock()):
            assert await async_setup_entry(hass, entry)

        assert entry.runtime_data.device_code == 2


class TestAsyncUnloadEntry:
    """Tests for async_unload_entry and the full setup/unload cycle."""

    async def test_full_setup_and_unload_cycle(
        self, hass: HomeAssistant, mock_remote_entity, make_config_entry, mock_climate_device_data, mock_controller
    ) -> None:
        """A fully set-up entry can be unloaded, removing its entity."""
        entry = make_config_entry()
        entry.add_to_hass(hass)

        with (
            patch(
                "custom_components.smartir.entity.async_load_device_data",
                AsyncMock(return_value=mock_climate_device_data),
            ),
            patch("custom_components.smartir.entity.get_controller", return_value=mock_controller),
        ):
            assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.NOT_LOADED

    async def test_async_unload_entry_uses_runtime_device_type(self, hass: HomeAssistant) -> None:
        """async_unload_entry unloads the platform matching runtime_data.device_type."""
        entry = MagicMock()
        entry.runtime_data = MagicMock(device_type="fan")

        with patch.object(hass.config_entries, "async_unload_platforms", new=AsyncMock(return_value=True)) as unload:
            assert await async_unload_entry(hass, entry)

        unload.assert_called_once_with(entry, ["fan"])


class TestAsyncUpdateOptions:
    """Tests for async_update_options."""

    async def test_reloads_the_entry(self, hass: HomeAssistant) -> None:
        """async_update_options triggers a config-entry reload."""
        entry = MagicMock()
        entry.entry_id = "entry-reload"

        with patch.object(hass.config_entries, "async_reload", new=AsyncMock()) as reload_mock:
            await async_update_options(hass, entry)

        reload_mock.assert_awaited_once_with("entry-reload")
