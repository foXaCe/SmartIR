"""Typed exceptions for the SmartIR integration."""

from __future__ import annotations


class SmartIRError(Exception):
    """Base exception for all SmartIR errors."""


class DeviceDataError(SmartIRError):
    """Raised when a device-code file cannot be loaded or parsed."""


class DeviceDataNotFound(DeviceDataError):
    """Raised when a device-code file cannot be found or downloaded."""


class SmartIRControllerError(SmartIRError):
    """Base exception for SmartIR controller errors."""


class UnsupportedControllerError(SmartIRControllerError):
    """Raised when an unsupported controller is requested."""


class UnsupportedEncodingError(SmartIRControllerError):
    """Raised when an unsupported encoding is used."""


class CommandConversionError(SmartIRControllerError):
    """Raised when command conversion fails."""


class CommandSendError(SmartIRControllerError):
    """Raised when sending a command fails after all retries."""
