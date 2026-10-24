"""Moving an amplifier from the old `monoprice` domain, on real HA registries."""

from __future__ import annotations

from types import MappingProxyType, SimpleNamespace
from unittest.mock import patch

import pytest
from serialx import SerialException

from custom_components.nohassle_amp.const import CONF_MIGRATED_FROM, DOMAIN
from custom_components.nohassle_amp.migration import legacy_amp_entries
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryState,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from .conftest import ENABLED_ZONES, TONES, ZONES, FakeAmp

PORT = "socket://192.0.2.20:4999"  # documentation address, never a real amplifier
SOURCES = {str(i): str(i) for i in range(1, 7)}
OPTIONS = {
    "sources": {"1": "TV", "2": "Turntable", "3": "3", "4": "4", "5": "5", "6": "6"}
}


def add_entry(hass, domain, data, *, options=None, title=PORT):
    entry = ConfigEntry(
        domain=domain,
        title=title,
        data=data,
        options=options or {},
        source=SOURCE_USER,
        unique_id=None,
        version=1,
        minor_version=1,
        discovery_keys=MappingProxyType({}),
        subentries_data=[],
    )
    hass.config_entries._entries[entry.entry_id] = entry
    return entry


def legacy_keys():
    """(domain, unique-ID suffix, object ID, zone) for every old amp entity."""
    keys = [("media_player", str(zone), f"zone_{zone}", zone) for zone in ZONES]
    keys += [
        ("number", f"{zone}_{tone}", f"zone_{zone}_{tone}", zone)
        for zone in ZONES
        for tone in TONES
    ]
    return keys


@pytest.fixture
def legacy(hass):
    """An old amp entry shaped like a real install: 18 zone devices, 12 disabled."""
    entry = add_entry(
        hass,
        "monoprice",
        {"port": PORT, "sources": SOURCES, "not_first_run": True},
        options=OPTIONS,
    )
    devices = dr.async_get(hass)
    device_ids = {}
    for zone in ZONES:
        device = devices.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={("monoprice", f"{entry.entry_id}_{zone}")},
            manufacturer="Monoprice",
            model="6-Zone Amplifier",
            name=f"Zone {zone}",
        )
        if zone not in ENABLED_ZONES:
            devices.async_update_device(
                device.id, disabled_by=dr.DeviceEntryDisabler.USER
            )
        device_ids[zone] = device.id
    devices.async_update_device(
        device_ids[11], area_id="room_a", name_by_user="Speaker A"
    )
    entities = er.async_get(hass)
    for domain, suffix, object_id, zone in legacy_keys():
        entities.async_get_or_create(
            domain,
            "monoprice",
            f"{entry.entry_id}_{suffix}",
            config_entry=entry,
            device_id=device_ids[zone],
            suggested_object_id=object_id,
            disabled_by=(
                None if zone in ENABLED_ZONES else er.RegistryEntryDisabler.DEVICE
            ),
        )
    entities.async_update_entity("number.zone_11_bass", name="Custom bass")
    return entry, device_ids


async def import_legacy(hass, legacy_entry):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={"legacy_entry_id": legacy_entry.entry_id},
    )
    await hass.async_block_till_done()
    return result


def moved_count(hass, entry_id):
    return len(er.async_entries_for_config_entry(er.async_get(hass), entry_id))


async def test_import_moves_all_devices_and_entities(hass, amp, legacy):
    legacy_entry, device_ids = legacy
    result = await import_legacy(hass, legacy_entry)
    assert result["type"] == "create_entry"
    entry = result["result"]
    assert entry.state is ConfigEntryState.LOADED
    assert hass.config_entries.async_get_entry(legacy_entry.entry_id) is None

    # The new entry keeps the connection, the input names and the first-run flag.
    assert entry.title == legacy_entry.title
    assert entry.data == {"port": PORT, "sources": SOURCES, "not_first_run": True}
    assert CONF_MIGRATED_FROM not in entry.data
    assert entry.options == OPTIONS
    # An amplifier that was already running is not treated as a first run, which
    # would poll all 18 zones over serial before adding any of them.
    assert entry.runtime_data.first_run is False

    registry = er.async_get(hass)
    assert moved_count(hass, entry.entry_id) == 72
    disabled = 0
    for domain, suffix, object_id, zone in legacy_keys():
        entity = registry.async_get(f"{domain}.{object_id}")
        assert entity is not None, f"{domain}.{object_id} lost its entity ID"
        assert entity.platform == DOMAIN
        assert entity.config_entry_id == entry.entry_id
        assert entity.unique_id == f"{entry.entry_id}_{suffix}"
        assert entity.device_id == device_ids[zone]
        assert (entity.disabled_by is not None) == (zone not in ENABLED_ZONES)
        disabled += entity.disabled_by is not None
    assert disabled == 48  # 12 media players and 36 tone controls stay disabled
    assert registry.async_get("number.zone_11_bass").name == "Custom bass"

    devices = dr.async_get(hass)
    for zone, device_id in device_ids.items():
        device = devices.async_get(device_id)
        assert device is not None, f"zone {zone} device was lost"
        assert device.identifiers == {(DOMAIN, f"{entry.entry_id}_{zone}")}
        assert device.config_entry_id == entry.entry_id
        assert (device.disabled_by is not None) == (zone not in ENABLED_ZONES)
    renamed = devices.async_get(device_ids[11])
    assert (renamed.area_id, renamed.name_by_user) == ("room_a", "Speaker A")


async def test_moved_entities_are_live_under_the_new_integration(hass, amp, legacy):
    legacy_entry, _ = legacy
    await import_legacy(hass, legacy_entry)
    assert hass.states.get("media_player.zone_21") is None  # disabled stays disabled
    await async_update_entity(hass, "media_player.zone_11")
    await async_update_entity(hass, "media_player.zone_12")
    assert hass.states.get("media_player.zone_11").state == "on"
    assert hass.states.get("media_player.zone_12").state == "off"
    assert hass.states.get("number.zone_11_bass") is not None
    assert hass.services.has_service(DOMAIN, "snapshot")
    assert hass.services.has_service(DOMAIN, "restore")


async def test_old_connection_is_released_before_the_new_one_opens(hass, amp, legacy):
    legacy_entry, _ = legacy
    old = FakeAmp("old", amp.events)
    legacy_entry.runtime_data = SimpleNamespace(client=old)
    legacy_entry._async_set_state(hass, ConfigEntryState.LOADED, None)

    async def unload(entry_id):
        amp.events.append("unload old")
        legacy_entry._async_set_state(hass, ConfigEntryState.NOT_LOADED, None)
        return True

    with patch.object(hass.config_entries, "async_unload", side_effect=unload):
        result = await import_legacy(hass, legacy_entry)
    assert result["type"] == "create_entry"
    # The new entry can only open the exclusive serial port once the old one let go.
    assert amp.events[:3] == ["unload old", "close old", "open new"]


async def test_a_failed_unload_moves_nothing(hass, amp, legacy):
    legacy_entry, _ = legacy
    legacy_entry._async_set_state(hass, ConfigEntryState.LOADED, None)

    async def refuse(entry_id):
        return False

    with patch.object(hass.config_entries, "async_unload", side_effect=refuse):
        result = await import_legacy(hass, legacy_entry)
    entry = result["result"]
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert hass.config_entries.async_get_entry(legacy_entry.entry_id) is not None
    assert moved_count(hass, legacy_entry.entry_id) == 72
    assert "open new" not in amp.events


async def test_a_port_that_is_still_busy_is_retried_after_the_move(hass, legacy):
    legacy_entry, device_ids = legacy
    new = FakeAmp("new")
    with patch(
        "custom_components.nohassle_amp.get_monoprice",
        side_effect=[SerialException("port busy"), new],
    ):
        result = await import_legacy(hass, legacy_entry)
        entry = result["result"]
        assert entry.state is ConfigEntryState.SETUP_RETRY
        # The move is already done and must not be repeated or undone on retry.
        assert hass.config_entries.async_get_entry(legacy_entry.entry_id) is None
        assert CONF_MIGRATED_FROM not in entry.data
        assert moved_count(hass, entry.entry_id) == 72
        await hass.config_entries.async_reload(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert moved_count(hass, entry.entry_id) == 72
    assert (
        dr.async_get(hass).async_get(device_ids[11]).config_entry_id == entry.entry_id
    )


async def test_failed_old_entry_removal_does_not_break_the_new_entry(hass, amp, legacy):
    legacy_entry, _ = legacy
    with patch.object(
        hass.config_entries, "async_remove", side_effect=ImportError("pymonoprice")
    ):
        result = await import_legacy(hass, legacy_entry)
    entry = result["result"]
    assert entry.state is ConfigEntryState.LOADED
    assert CONF_MIGRATED_FROM not in entry.data
    # The move stands; only the empty old entry is left for the user to delete.
    assert moved_count(hass, entry.entry_id) == 72


async def test_second_import_is_a_no_op(hass, amp, legacy):
    legacy_entry, _ = legacy
    await import_legacy(hass, legacy_entry)
    again = await import_legacy(hass, legacy_entry)
    assert again["type"] == "abort" and again["reason"] == "legacy_not_found"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_existing_entry_for_the_same_port_blocks_the_import(hass, amp, legacy):
    legacy_entry, _ = legacy
    add_entry(hass, DOMAIN, {"port": PORT, "sources": SOURCES})
    result = await import_legacy(hass, legacy_entry)
    assert result["type"] == "abort" and result["reason"] == "already_configured"
    # Nothing was moved: the old entry and its entities are untouched.
    assert hass.config_entries.async_get_entry(legacy_entry.entry_id) is not None
    assert moved_count(hass, legacy_entry.entry_id) == 72


async def test_user_flow_offers_the_import_when_an_old_amp_exists(hass, amp, legacy):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "menu"
    assert result["menu_options"] == ["migrate", "manual"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "migrate"}
    )
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert moved_count(hass, result["result"].entry_id) == 72


async def test_an_old_matrix_entry_is_not_an_amplifier(hass):
    add_entry(
        hass,
        "monoprice",
        {"device_type": "matrix", "host": "192.0.2.10", "http_port": 80},
    )
    assert legacy_amp_entries(hass) == []
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "form" and result["step_id"] == "manual"
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={"legacy_entry_id": "does-not-exist"},
    )
    assert result["type"] == "abort" and result["reason"] == "legacy_not_found"
