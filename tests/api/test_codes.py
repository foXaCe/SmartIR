"""Tests for the SmartIR device-code database access and IR-code conversion helpers."""

from __future__ import annotations

import json
import os
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from homeassistant.core import HomeAssistant
import pytest

from custom_components.smartir.api.codes import (
    _async_resolve_codes_path,
    async_download_code,
    async_load_device_data,
    lirc2broadlink,
    pronto2lirc,
)
from custom_components.smartir.api.exceptions import DeviceDataError, DeviceDataNotFound
from custom_components.smartir.const import CUSTOM_CODES_DIR


def _aiofiles_write_context() -> MagicMock:
    """Build a mock async context manager compatible with aiofiles.open(mode='wb')."""
    mock_file = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_file)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    return mock_ctx, mock_file


def _aiofiles_read_context(content: str) -> MagicMock:
    """Build a mock async context manager returning ``content`` on read()."""
    mock_file = AsyncMock()
    mock_file.read = AsyncMock(return_value=content)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_file)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    return mock_ctx


def _mock_session(status: int, chunks: list[bytes]) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.request_info = MagicMock()
    response.history = ()

    async def _iter(_size: int):
        for chunk in chunks:
            yield chunk

    response.content.iter_chunked = _iter
    session = MagicMock()
    session.get.return_value.__aenter__ = AsyncMock(return_value=response)
    session.get.return_value.__aexit__ = AsyncMock(return_value=False)
    return session


class TestAsyncDownloadCode:
    """Tests for async_download_code."""

    async def test_writes_file_in_chunks(self, hass: HomeAssistant, tmp_path) -> None:
        """A 200 response is streamed to the destination path, creating the parent dir."""
        dest = tmp_path / "codes" / "climate" / "1000.json"
        session = _mock_session(200, [b'{"a":', b"1}"])
        mock_ctx, mock_file = _aiofiles_write_context()

        with (
            patch("custom_components.smartir.api.codes.async_get_clientsession", return_value=session),
            patch("custom_components.smartir.api.codes.aiofiles.open", return_value=mock_ctx),
        ):
            await async_download_code(hass, "https://example.com/1000.json", str(dest))

        assert os.path.isdir(dest.parent)
        assert mock_file.write.await_count == 2
        mock_file.write.assert_any_await(b'{"a":')
        mock_file.write.assert_any_await(b"1}")

    async def test_raises_on_http_error(self, hass: HomeAssistant, tmp_path) -> None:
        """A non-200 response raises a ClientResponseError."""
        dest = tmp_path / "missing.json"
        session = _mock_session(404, [])

        with (
            patch("custom_components.smartir.api.codes.async_get_clientsession", return_value=session),
            pytest.raises(aiohttp.ClientResponseError),
        ):
            await async_download_code(hass, "https://example.com/missing.json", str(dest))


class TestAsyncLoadDeviceData:
    """Tests for async_load_device_data."""

    async def test_loads_existing_file_without_downloading(self, hass: HomeAssistant) -> None:
        """When the cached file already exists, no download is attempted."""
        payload = {"manufacturer": "Test"}
        with (
            patch("custom_components.smartir.api.codes.os.path.isfile", return_value=True),
            patch("custom_components.smartir.api.codes.async_download_code", new_callable=AsyncMock) as mock_download,
            patch(
                "custom_components.smartir.api.codes.aiofiles.open",
                return_value=_aiofiles_read_context(json.dumps(payload)),
            ),
        ):
            result = await async_load_device_data(hass, "climate", 1000)

        mock_download.assert_not_called()
        assert result == payload

    async def test_downloads_when_file_missing(self, hass: HomeAssistant) -> None:
        """The file is downloaded when not present in the local cache."""
        payload = {"manufacturer": "Test"}
        with (
            patch("custom_components.smartir.api.codes.os.path.isfile", return_value=False),
            patch("custom_components.smartir.api.codes.async_download_code", new_callable=AsyncMock) as mock_download,
            patch(
                "custom_components.smartir.api.codes.aiofiles.open",
                return_value=_aiofiles_read_context(json.dumps(payload)),
            ),
        ):
            result = await async_load_device_data(hass, "climate", 1000)

        mock_download.assert_called_once()
        args = mock_download.call_args[0]
        assert args[0] is hass
        assert args[1] == "https://raw.githubusercontent.com/foXaCe/SmartIR/main/codes/climate/1000.json"
        assert result == payload

    async def test_download_client_error_raises_not_found(self, hass: HomeAssistant) -> None:
        """An aiohttp.ClientError during download raises DeviceDataNotFound."""
        with (
            patch("custom_components.smartir.api.codes.os.path.isfile", return_value=False),
            patch(
                "custom_components.smartir.api.codes.async_download_code",
                new_callable=AsyncMock,
                side_effect=aiohttp.ClientError("network unreachable"),
            ),
            pytest.raises(DeviceDataNotFound, match="Could not download"),
        ):
            await async_load_device_data(hass, "climate", 1000)

    async def test_download_os_error_raises_not_found(self, hass: HomeAssistant) -> None:
        """An OSError during download raises DeviceDataNotFound."""
        with (
            patch("custom_components.smartir.api.codes.os.path.isfile", return_value=False),
            patch(
                "custom_components.smartir.api.codes.async_download_code",
                new_callable=AsyncMock,
                side_effect=OSError("disk full"),
            ),
            pytest.raises(DeviceDataNotFound),
        ):
            await async_load_device_data(hass, "climate", 1000)

    async def test_invalid_json_raises_device_data_error(self, hass: HomeAssistant) -> None:
        """Malformed JSON content raises DeviceDataError."""
        with (
            patch("custom_components.smartir.api.codes.os.path.isfile", return_value=True),
            patch(
                "custom_components.smartir.api.codes.aiofiles.open",
                return_value=_aiofiles_read_context("not valid json"),
            ),
            pytest.raises(DeviceDataError, match="Invalid device-code file"),
        ):
            await async_load_device_data(hass, "climate", 1000)

    async def test_file_read_os_error_raises_device_data_error(self, hass: HomeAssistant) -> None:
        """An OSError while reading the cached file raises DeviceDataError."""
        with (
            patch("custom_components.smartir.api.codes.os.path.isfile", return_value=True),
            patch("custom_components.smartir.api.codes.aiofiles.open", side_effect=OSError("boom")),
            pytest.raises(DeviceDataError),
        ):
            await async_load_device_data(hass, "climate", 1000)


class TestCustomCodesResolution:
    """Tests for the custom → bundled → download resolution order."""

    async def test_custom_dir_takes_priority(self, hass: HomeAssistant) -> None:
        """When both custom and bundled files exist, the custom one wins with no download."""
        with (
            patch("custom_components.smartir.api.codes.os.path.isfile", return_value=True),
            patch("custom_components.smartir.api.codes.async_download_code", new_callable=AsyncMock) as mock_dl,
        ):
            path = await _async_resolve_codes_path(hass, "climate", 1293)

        assert path == hass.config.path(CUSTOM_CODES_DIR, "climate", "1293.json")
        mock_dl.assert_not_called()

    async def test_bundled_fallback_when_no_custom(self, hass: HomeAssistant) -> None:
        """Without a custom file, the bundled file is used and nothing is downloaded."""
        with (
            patch(
                "custom_components.smartir.api.codes.os.path.isfile",
                side_effect=lambda p: CUSTOM_CODES_DIR not in p,
            ),
            patch("custom_components.smartir.api.codes.async_download_code", new_callable=AsyncMock) as mock_dl,
        ):
            path = await _async_resolve_codes_path(hass, "climate", 1293)

        assert CUSTOM_CODES_DIR not in path
        assert path.endswith("codes/climate/1293.json")
        mock_dl.assert_not_called()

    async def test_download_fallback_when_neither(self, hass: HomeAssistant) -> None:
        """Without a custom or bundled file, the code is downloaded into the bundled cache."""
        with (
            patch("custom_components.smartir.api.codes.os.path.isfile", return_value=False),
            patch("custom_components.smartir.api.codes.async_download_code", new_callable=AsyncMock) as mock_dl,
        ):
            path = await _async_resolve_codes_path(hass, "fan", 2000)

        mock_dl.assert_called_once()
        assert CUSTOM_CODES_DIR not in path

    async def test_custom_path_resolved_via_hass_config_path(self, hass: HomeAssistant) -> None:
        """The custom directory path is built through hass.config.path (never hardcoded)."""
        with (
            patch.object(hass.config, "path", wraps=hass.config.path) as mock_config_path,
            patch(
                "custom_components.smartir.api.codes.os.path.isfile",
                side_effect=lambda p: CUSTOM_CODES_DIR in p,
            ),
            patch("custom_components.smartir.api.codes.async_download_code", new_callable=AsyncMock),
        ):
            await _async_resolve_codes_path(hass, "climate", 1293)

        mock_config_path.assert_any_call(CUSTOM_CODES_DIR, "climate", "1293.json")

    @pytest.mark.parametrize("platform", ["climate", "fan", "media_player"])
    async def test_applies_to_all_platforms(self, hass: HomeAssistant, platform: str) -> None:
        """Custom resolution applies to every platform through the shared helper."""
        with (
            patch(
                "custom_components.smartir.api.codes.os.path.isfile",
                side_effect=lambda p: CUSTOM_CODES_DIR in p,
            ),
            patch("custom_components.smartir.api.codes.async_download_code", new_callable=AsyncMock) as mock_dl,
        ):
            path = await _async_resolve_codes_path(hass, platform, 1)

        assert path == hass.config.path(CUSTOM_CODES_DIR, platform, "1.json")
        mock_dl.assert_not_called()

    async def test_end_to_end_custom_priority_loads_custom_content(self, hass: HomeAssistant) -> None:
        """async_load_device_data returns the custom file's content when present."""
        payload = {"manufacturer": "Custom vendor"}
        with (
            patch(
                "custom_components.smartir.api.codes.os.path.isfile",
                side_effect=lambda p: CUSTOM_CODES_DIR in p,
            ),
            patch("custom_components.smartir.api.codes.async_download_code", new_callable=AsyncMock) as mock_dl,
            patch(
                "custom_components.smartir.api.codes.aiofiles.open",
                return_value=_aiofiles_read_context(json.dumps(payload)),
            ),
        ):
            result = await async_load_device_data(hass, "climate", 1293)

        assert result == payload
        mock_dl.assert_not_called()


class TestPronto2Lirc:
    """Tests for the pronto2lirc conversion helper."""

    def test_converts_known_pronto_code(self) -> None:
        """A well-formed Pronto code converts to the expected LIRC pulses."""
        pronto = bytearray.fromhex("000000710001000000600018")
        assert pronto2lirc(pronto) == [2617, 654]

    def test_invalid_preamble_raises(self) -> None:
        """A Pronto code not starting with 0000 raises ValueError."""
        pronto = bytearray.fromhex("0001006D0001000100100020")
        with pytest.raises(ValueError, match="should start with 0000"):
            pronto2lirc(pronto)

    def test_mismatched_pulse_count_raises(self) -> None:
        """A preamble declaring more pulses than actually present raises ValueError."""
        # codes[2]=2, codes[3]=0 declares 2*(2+0)=4 pulses, but only 2 are provided.
        pronto = bytearray.fromhex("000000710002000000600018")
        with pytest.raises(ValueError, match="preamble"):
            pronto2lirc(pronto)


class TestLirc2Broadlink:
    """Tests for the lirc2broadlink conversion helper."""

    def test_header_and_footer(self) -> None:
        """The packet starts with the Broadlink IR header and ends with the footer marker."""
        packet = lirc2broadlink([560, 560, 560, 1680])

        assert packet[0] == 0x26
        assert packet[1] == 0x00
        array_len = struct.unpack("<H", packet[2:4])[0]
        assert array_len == 4
        assert list(packet[4:8]) == [18, 18, 18, 55]
        assert packet[8:10] == bytearray([0x0D, 0x05])

    def test_padded_to_multiple_of_16(self) -> None:
        """The final packet is padded so that (len + 4) is a multiple of 16."""
        packet = lirc2broadlink([560, 560, 560, 1680])
        assert (len(packet) + 4) % 16 == 0
        assert len(packet) == 12

    def test_long_pulse_uses_three_byte_encoding(self) -> None:
        """A pulse >= 256 after scaling is encoded as a 0x00 marker plus a big-endian uint16."""
        packet = lirc2broadlink([100000])
        assert packet[4] == 0x00
        assert struct.unpack(">H", packet[5:7])[0] == 3283
