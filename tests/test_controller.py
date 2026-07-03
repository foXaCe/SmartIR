"""Tests for SmartIR controller module."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
import pytest

from custom_components.smartir.controller import (
    BroadlinkController,
    ESPHomeController,
    LookinController,
    MQTTController,
    UnsupportedControllerError,
    UnsupportedEncodingError,
    XiaomiController,
    get_controller,
)


def test_get_controller_broadlink(hass: HomeAssistant) -> None:
    """Test getting a Broadlink controller."""
    controller = get_controller(
        hass,
        "Broadlink",
        "Base64",
        "remote.test",
        0.5,
    )
    assert isinstance(controller, BroadlinkController)


def test_get_controller_xiaomi(hass: HomeAssistant) -> None:
    """Test getting a Xiaomi controller."""
    controller = get_controller(
        hass,
        "Xiaomi",
        "Pronto",
        "remote.test",
        0.5,
    )
    assert isinstance(controller, XiaomiController)


def test_get_controller_mqtt(hass: HomeAssistant) -> None:
    """Test getting a MQTT controller."""
    controller = get_controller(
        hass,
        "MQTT",
        "Raw",
        "smartir/command",
        0.5,
    )
    assert isinstance(controller, MQTTController)


def test_get_controller_lookin(hass: HomeAssistant) -> None:
    """Test getting a LOOKin controller."""
    controller = get_controller(
        hass,
        "LOOKin",
        "Pronto",
        "192.168.1.100",
        0.5,
    )
    assert isinstance(controller, LookinController)


def test_get_controller_esphome(hass: HomeAssistant) -> None:
    """Test getting an ESPHome controller."""
    controller = get_controller(
        hass,
        "ESPHome",
        "Raw",
        "send_ir_command",
        0.5,
    )
    assert isinstance(controller, ESPHomeController)


def test_get_controller_unsupported(hass: HomeAssistant) -> None:
    """Test getting an unsupported controller raises exception."""
    with pytest.raises(UnsupportedControllerError, match="is not supported"):
        get_controller(
            hass,
            "UnsupportedController",
            "Base64",
            "remote.test",
            0.5,
        )


def test_broadlink_invalid_encoding(hass: HomeAssistant) -> None:
    """Test Broadlink controller with invalid encoding."""
    with pytest.raises(UnsupportedEncodingError, match="encoding is not supported"):
        BroadlinkController(
            hass,
            "Broadlink",
            "InvalidEncoding",
            "remote.test",
            0.5,
        )


def test_xiaomi_invalid_encoding(hass: HomeAssistant) -> None:
    """Test Xiaomi controller with invalid encoding."""
    with pytest.raises(UnsupportedEncodingError, match="encoding is not supported"):
        XiaomiController(
            hass,
            "Xiaomi",
            "Base64",  # Not supported by Xiaomi
            "remote.test",
            0.5,
        )


def test_mqtt_invalid_encoding(hass: HomeAssistant) -> None:
    """Test MQTT controller with invalid encoding."""
    with pytest.raises(UnsupportedEncodingError, match="encoding is not supported"):
        MQTTController(
            hass,
            "MQTT",
            "Base64",  # Not supported by MQTT
            "smartir/command",
            0.5,
        )


def test_broadlink_controller_properties(hass: HomeAssistant) -> None:
    """Test Broadlink controller properties."""
    controller = BroadlinkController(
        hass,
        "Broadlink",
        "Base64",
        "remote.test",
        0.5,
    )
    assert controller._encoding == "Base64"
    assert controller._controller_data == "remote.test"
    assert controller._delay == 0.5


def test_mqtt_controller_properties(hass: HomeAssistant) -> None:
    """Test MQTT controller properties."""
    controller = MQTTController(
        hass,
        "MQTT",
        "Raw",
        "smartir/command",
        0.5,
    )
    assert controller._encoding == "Raw"
    assert controller._controller_data == "smartir/command"


def test_lookin_controller_properties(hass: HomeAssistant) -> None:
    """Test LOOKin controller properties."""
    controller = LookinController(
        hass,
        "LOOKin",
        "Raw",
        "192.168.1.100",
        0.5,
    )
    assert controller._encoding == "Raw"
    assert controller._controller_data == "192.168.1.100"


def test_esphome_controller_properties(hass: HomeAssistant) -> None:
    """Test ESPHome controller properties."""
    controller = ESPHomeController(
        hass,
        "ESPHome",
        "Raw",
        "send_ir_command",
        0.5,
    )
    assert controller._encoding == "Raw"
    assert controller._controller_data == "send_ir_command"


def test_lookin_invalid_encoding(hass: HomeAssistant) -> None:
    """Test LOOKin controller with invalid encoding."""
    with pytest.raises(UnsupportedEncodingError, match="encoding is not supported"):
        LookinController(
            hass,
            "LOOKin",
            "Base64",  # Not supported by LOOKin
            "192.168.1.100",
            0.5,
        )


def test_esphome_invalid_encoding(hass: HomeAssistant) -> None:
    """Test ESPHome controller with invalid encoding."""
    with pytest.raises(UnsupportedEncodingError, match="encoding is not supported"):
        ESPHomeController(
            hass,
            "ESPHome",
            "Base64",  # Not supported by ESPHome
            "send_ir_command",
            0.5,
        )
