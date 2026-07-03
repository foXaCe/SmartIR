"""Tests for the v1 → v2 config entry migration (unique_id / device identifier)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smartir import async_migrate_entry
from custom_components.smartir.const import DOMAIN

OLD_UNIQUE_ID = "smartir_climate_1000_remote.test"


async def test_migrate_v1_to_v2(hass: HomeAssistant) -> None:
    """A v1 entry migrates its entity unique_id and device identifier to the v2 scheme."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={
            "device_type": "climate",
            "controller": "broadlink",
            "name": "Living Room AC",
            "device_code": 1000,
            "controller_data": "remote.test",
        },
        unique_id=OLD_UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, OLD_UNIQUE_ID)},
    )
    entity = ent_reg.async_get_or_create(
        "climate",
        DOMAIN,
        OLD_UNIQUE_ID,
        config_entry=entry,
        device_id=device.id,
    )

    assert await async_migrate_entry(hass, entry)
    await hass.async_block_till_done()

    # Entry bumped to v2.
    assert entry.version == 2

    # Entity unique_id re-keyed onto the entry id; the entity_id is preserved.
    migrated_entity = ent_reg.async_get(entity.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.unique_id == f"{entry.entry_id}_climate"

    # Device identifier re-keyed onto the entry id; the device row is preserved.
    migrated_device = dev_reg.async_get(device.id)
    assert migrated_device is not None
    assert migrated_device.identifiers == {(DOMAIN, entry.entry_id)}


async def test_migrate_v2_is_noop(hass: HomeAssistant) -> None:
    """Migrating an already-v2 entry is a no-op that succeeds."""
    entry = MockConfigEntry(domain=DOMAIN, version=2, data={"device_type": "fan"})
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 2


async def test_migrate_future_version_refused(hass: HomeAssistant) -> None:
    """A future (unknown) schema version cannot be downgraded."""
    entry = MockConfigEntry(domain=DOMAIN, version=3, data={"device_type": "fan"})
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is False
