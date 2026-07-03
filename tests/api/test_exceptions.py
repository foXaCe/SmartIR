"""Tests for the SmartIR typed exception hierarchy."""

from __future__ import annotations

import pytest

from custom_components.smartir.api.exceptions import (
    CommandConversionError,
    CommandSendError,
    DeviceDataError,
    DeviceDataNotFound,
    SmartIRControllerError,
    SmartIRError,
    UnsupportedControllerError,
    UnsupportedEncodingError,
)


class TestExceptionHierarchy:
    """Verify the inheritance relationships between the typed exceptions."""

    def test_device_data_error_is_smartir_error(self) -> None:
        """DeviceDataError derives from SmartIRError."""
        assert issubclass(DeviceDataError, SmartIRError)

    def test_device_data_not_found_is_device_data_error(self) -> None:
        """DeviceDataNotFound derives from DeviceDataError (and thus SmartIRError)."""
        assert issubclass(DeviceDataNotFound, DeviceDataError)
        assert issubclass(DeviceDataNotFound, SmartIRError)

    def test_controller_error_is_smartir_error(self) -> None:
        """SmartIRControllerError derives from SmartIRError."""
        assert issubclass(SmartIRControllerError, SmartIRError)

    @pytest.mark.parametrize(
        "exc_cls",
        [UnsupportedControllerError, UnsupportedEncodingError, CommandConversionError, CommandSendError],
    )
    def test_controller_error_subclasses(self, exc_cls: type[Exception]) -> None:
        """All controller-related errors derive from SmartIRControllerError."""
        assert issubclass(exc_cls, SmartIRControllerError)
        assert issubclass(exc_cls, SmartIRError)

    def test_smartir_error_is_exception(self) -> None:
        """SmartIRError itself derives from the builtin Exception."""
        assert issubclass(SmartIRError, Exception)


class TestExceptionRaising:
    """Verify the exceptions carry their message and can be caught by a base class."""

    def test_device_data_not_found_message(self) -> None:
        """A DeviceDataNotFound carries its message and is catchable as DeviceDataError."""
        with pytest.raises(DeviceDataError, match="code 1000 missing"):
            raise DeviceDataNotFound("code 1000 missing")

    def test_device_data_error_message(self) -> None:
        """A DeviceDataError carries its message and is catchable as SmartIRError."""
        with pytest.raises(SmartIRError, match="bad json"):
            raise DeviceDataError("bad json")

    def test_command_send_error_catchable_as_controller_error(self) -> None:
        """A CommandSendError is catchable as SmartIRControllerError."""
        with pytest.raises(SmartIRControllerError, match="failed after 3 attempts"):
            raise CommandSendError("failed after 3 attempts")

    def test_unsupported_encoding_error_catchable_as_smartir_error(self) -> None:
        """An UnsupportedEncodingError is catchable as the SmartIRError base."""
        with pytest.raises(SmartIRError):
            raise UnsupportedEncodingError("nope")
