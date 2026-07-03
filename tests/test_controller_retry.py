"""Tests for the controller retry/blocking behaviour and climate revert."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.smartir.controller import (
    BROADLINK_CONTROLLER,
    SEND_ATTEMPTS,
    BroadlinkController,
    CommandSendError,
)


def _broadlink(hass) -> BroadlinkController:
    return BroadlinkController(hass, BROADLINK_CONTROLLER, "Base64", "remote.blaster", 0.1)


async def test_service_call_uses_blocking() -> None:
    """The service call is issued with blocking=True so errors propagate."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    ctrl = _broadlink(hass)

    await ctrl._async_call_with_retry("remote", "send_command", {"a": 1})

    hass.services.async_call.assert_awaited_once_with("remote", "send_command", {"a": 1}, blocking=True)


async def test_retry_succeeds_after_transient_failures() -> None:
    """Two transient failures then a success → command finally delivered, no raise."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock(side_effect=[HomeAssistantError("drop 1"), HomeAssistantError("drop 2"), None])
    ctrl = _broadlink(hass)

    with patch("custom_components.smartir.controller.asyncio.sleep", new=AsyncMock()) as sleep:
        await ctrl._async_call_with_retry("remote", "send_command", {})

    assert hass.services.async_call.await_count == 3
    assert sleep.await_count == 2  # backoff between the two retries


async def test_retry_raises_after_all_attempts_fail() -> None:
    """Every attempt fails → CommandSendError is raised after SEND_ATTEMPTS tries."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock(side_effect=HomeAssistantError("device unreachable"))
    ctrl = _broadlink(hass)

    with (
        patch("custom_components.smartir.controller.asyncio.sleep", new=AsyncMock()),
        pytest.raises(CommandSendError),
    ):
        await ctrl._async_call_with_retry("remote", "send_command", {})

    assert hass.services.async_call.await_count == SEND_ATTEMPTS


async def test_broadlink_send_retries_end_to_end() -> None:
    """A full Broadlink send() retries the underlying service call."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock(side_effect=[HomeAssistantError("x"), None])
    ctrl = _broadlink(hass)

    with patch("custom_components.smartir.controller.asyncio.sleep", new=AsyncMock()):
        await ctrl.send("JgABAA==")

    assert hass.services.async_call.await_count == 2
    # blocking must be set on the successful call
    assert hass.services.async_call.await_args.kwargs["blocking"] is True


async def test_climate_reverts_state_when_send_fails(hass) -> None:
    """Option (A): if the IR command fails, the entity reverts so the UI never lies."""
    from custom_components.smartir.climate import SmartIRClimate

    device_data = {
        "manufacturer": "M",
        "supportedModels": ["X"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "minTemperature": 16,
        "maxTemperature": 30,
        "precision": 1,
        "operationModes": ["cool", "heat"],
        "fanModes": ["auto"],
        "commands": {"off": "off", "cool": {"auto": {"16": "c"}}, "heat": {"auto": {"16": "h"}}},
    }
    config = {
        "name": "AC",
        "device_code": 1000,
        "controller_data": "remote.x",
        "delay": 0.1,
        "unique_id": "u",
    }
    controller = MagicMock()
    controller.send = AsyncMock(side_effect=CommandSendError("no link after retries"))

    with patch("custom_components.smartir.climate.get_controller", return_value=controller):
        entity = SmartIRClimate(hass, config, device_data)
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_hvac_mode("heat")

    # send failed → state reverts to the previous (OFF) value, not "heat"
    assert entity.hvac_mode == "off"
    entity.async_write_ha_state.assert_called()
