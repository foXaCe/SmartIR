"""Tests for the device-code downloader helper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
import pytest

from custom_components.smartir import Helper


def _mock_session(status: int, chunks: list[bytes]):
    response = MagicMock()
    response.status = status
    response.request_info = MagicMock()
    response.history = ()

    async def _iter(_size):
        for chunk in chunks:
            yield chunk

    response.content.iter_chunked = _iter
    session = MagicMock()
    session.get.return_value.__aenter__ = AsyncMock(return_value=response)
    session.get.return_value.__aexit__ = AsyncMock(return_value=False)
    return session


async def test_downloader_writes_file(hass: HomeAssistant, tmp_path) -> None:
    """A 200 response is streamed to the destination path (dir created)."""
    dest = tmp_path / "codes" / "climate" / "1000.json"
    session = _mock_session(200, [b'{"a":', b"1}"])

    with patch("custom_components.smartir.async_get_clientsession", return_value=session):
        await Helper.downloader(hass, "https://example.com/1000.json", str(dest))

    assert dest.read_text() == '{"a":1}'


async def test_downloader_raises_on_http_error(hass: HomeAssistant, tmp_path) -> None:
    """A non-200 response raises a ClientResponseError."""
    import aiohttp

    dest = tmp_path / "missing.json"
    session = _mock_session(404, [])

    with (
        patch("custom_components.smartir.async_get_clientsession", return_value=session),
        pytest.raises(aiohttp.ClientResponseError),
    ):
        await Helper.downloader(hass, "https://example.com/missing.json", str(dest))
