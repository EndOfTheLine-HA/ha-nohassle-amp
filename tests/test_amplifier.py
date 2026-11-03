"""Amplifier entities, tone controls, setup, config flow and unload."""

from __future__ import annotations

import logging
from types import MappingProxyType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from serialx import SerialException

from custom_components.nohassle_amp.const import DOMAIN
from custom_components.nohassle_amp.media_player import MonopriceZone
from custom_components.nohassle_amp.number import NUMBERS, MonopriceZoneNumber
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryState,
)
from homeassistant.data_entry_flow import UnknownStep
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import FakeAmp

PORT = "socket://192.0.2.20:4999"  # documentation address, never a real amplifier
OLD_PORT = "socket://192.0.2.21:4999"  # documentation address, as above
SOURCES = [{1: "Input 1"}, {"Input 1": 1}, ["Input 1"]]


def add_entry(hass, domain, data):
    entry = ConfigEntry(
        domain=domain,
        title=PORT,
        data=data,
        options={},
        source=SOURCE_USER,
        unique_id=None,
        version=1,
        minor_version=1,
        discovery_keys=MappingProxyType({}),
        subentries_data=[],
    )
    hass.config_entries._entries[entry.entry_id] = entry
    return entry


@pytest.fixture
def old_amp(hass):
    """An amplifier left under the built-in integration, with its registries."""
    entry = add_entry(hass, "monoprice", {"port": OLD_PORT, "sources": {}})
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("monoprice", f"{entry.entry_id}_11")},
        name="Zone 11",
    )
    entity = er.async_get(hass).async_get_or_create(
        "media_player",
        "monoprice",
        f"{entry.entry_id}_11",
        config_entry=entry,
        device_id=device.id,
        suggested_object_id="old_zone_11",
    )
    return entry, device, entity


def assert_old_amp_untouched(hass, old_amp):
    entry, device, entity = old_amp
    assert hass.config_entries.async_get_entry(entry.entry_id) is entry
    assert dr.async_get(hass).async_get(device.id) == device
    assert er.async_get(hass).async_get(entity.entity_id) == entity


def import_warnings(caplog):
    return [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING
        and "may not have finished" in record.getMessage()
    ]


def test_unique_ids_are_pinned():
    """Existing installs are keyed on these formats.

    The same shape as Home Assistant's built-in Monoprice integration, so an
    amplifier imported by 0.1.0 kept every entity.
    """
    runtime = SimpleNamespace(client=Mock(), zone_status={})
    zone = MonopriceZone(runtime.client, SOURCES, "entry-1", 11, runtime)
    assert zone.unique_id == "entry-1_11"
    assert zone.device_info["identifiers"] == {(DOMAIN, "entry-1_11")}
    assert {description.key for description in NUMBERS} == {"bass", "treble", "balance"}
    for description in NUMBERS:
        number = MonopriceZoneNumber(runtime, "entry-1", 11, description)
        assert number.unique_id == f"entry-1_11_{description.key}"
        # Tone controls share their zone's device.
        assert number.device_info["identifiers"] == {(DOMAIN, "entry-1_11")}


def test_tone_controls_send_one_command_with_the_amp_offset():
    amp = Mock()
    runtime = SimpleNamespace(client=amp, zone_status={})
    for description in NUMBERS:
        number = MonopriceZoneNumber(runtime, "entry-1", 11, description)
        number.schedule_update_ha_state = Mock()
        number.set_native_value(0)
        getattr(amp, description.setter).assert_called_with(11, description.offset)


def test_zone_power_reaches_the_amp():
    amp = Mock()
    runtime = SimpleNamespace(client=amp, zone_status={})
    zone = MonopriceZone(amp, SOURCES, "entry-1", 11, runtime)
    zone.turn_on()
    amp.set_power.assert_called_with(11, True)


async def test_manual_setup_creates_a_working_amplifier(hass, amp):
    with patch("custom_components.nohassle_amp.config_flow.get_monoprice"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"port": PORT, "source_1": "TV"}
        )
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    entry = result["result"]
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data["sources"] == {"1": "TV"}
    assert entry.data["not_first_run"] is True  # set by the first run
    assert entry.runtime_data.first_run is True  # a new amplifier detects its zones
    assert hass.states.get("media_player.zone_11").state == "on"
    assert hass.states.get("media_player.zone_12").state == "off"
    assert hass.states.get("number.zone_11_bass").state == "0"
    assert hass.services.has_service(DOMAIN, "snapshot")
    assert er.async_get(hass).async_get("media_player.zone_11").unique_id == (
        f"{entry.entry_id}_11"
    )


async def test_an_old_monoprice_amplifier_is_left_alone(hass, amp, old_amp):
    with patch("custom_components.nohassle_amp.config_flow.get_monoprice"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == "form" and result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"port": PORT}
        )
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert result["result"].state is ConfigEntryState.LOADED
    assert_old_amp_untouched(hass, old_amp)


async def test_there_is_no_import_step(hass, old_amp):
    entry, _, _ = old_amp
    with pytest.raises(UnknownStep):
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"legacy_entry_id": entry.entry_id},
        )
    assert_old_amp_untouched(hass, old_amp)


async def test_an_unfinished_import_marker_is_only_warned_about(
    hass, amp, old_amp, caplog
):
    """0.1.0 removes the marker when its import finishes. 0.2.0 cannot finish one."""
    old_entry, _, _ = old_amp
    entry = add_entry(
        hass,
        DOMAIN,
        {"port": PORT, "sources": {}, "migrated_from": old_entry.entry_id},
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED  # it still works
    assert len(import_warnings(caplog)) == 1
    assert "install version 0.1.0" in import_warnings(caplog)[0].getMessage()
    assert_old_amp_untouched(hass, old_amp)


async def test_an_existing_amplifier_is_not_a_first_run(hass, amp, caplog):
    """A first run would poll all 18 zones over serial before adding any of them."""
    entry = add_entry(
        hass, DOMAIN, {"port": PORT, "sources": {}, "not_first_run": True}
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.first_run is False
    assert import_warnings(caplog) == []


async def test_a_busy_port_is_retried(hass):
    entry = add_entry(hass, DOMAIN, {"port": PORT, "sources": {}})
    with patch(
        "custom_components.nohassle_amp.get_monoprice",
        side_effect=[SerialException("port busy"), FakeAmp()],
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY
        await hass.config_entries.async_reload(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED


async def test_a_second_entry_for_the_same_port_is_refused(hass, amp):
    with patch("custom_components.nohassle_amp.config_flow.get_monoprice"):
        first = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(first["flow_id"], {"port": PORT})
        second = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            second["flow_id"], {"port": PORT}
        )
    assert result["type"] == "abort" and result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("error", "expected"),
    [(SerialException("no port"), "cannot_connect"), (RuntimeError("boom"), "unknown")],
)
async def test_setup_errors_are_shown_to_the_user(hass, error, expected):
    with patch(
        "custom_components.nohassle_amp.config_flow.get_monoprice", side_effect=error
    ):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"port": PORT}
        )
    assert result["type"] == "form" and result["errors"] == {"base": expected}


async def test_unload_releases_the_serial_port(hass, amp):
    with patch("custom_components.nohassle_amp.config_flow.get_monoprice"):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"port": PORT}
        )
    entry = result["result"]
    assert await hass.config_entries.async_unload(entry.entry_id)
    amp._port.close.assert_called_once()
    assert entry.state is ConfigEntryState.NOT_LOADED


def test_a_client_without_a_port_closes_quietly():
    from custom_components.nohassle_amp.connection import close_client

    close_client(object())
    close_client(SimpleNamespace(_port=None))
    amp = FakeAmp()
    close_client(amp)
    amp._port.close.assert_called_once()


def test_close_client_releases_a_real_pymonoprice_connection():
    """Against the real library, not a fake: reloads depend on this.

    pymonoprice has no close(), so close_client uses its private port. If a future
    release renames it, this fails here instead of leaving the port held on a live
    amplifier.
    """
    import socket
    import threading

    from pymonoprice import get_monoprice

    from custom_components.nohassle_amp.connection import close_client

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    seen = {}

    def serve():
        connection, _ = server.accept()
        connection.settimeout(5)
        seen["closed"] = connection.recv(10) == b""  # b"" means the client hung up

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    amp = get_monoprice(f"socket://127.0.0.1:{server.getsockname()[1]}")
    close_client(amp)  # the object is still referenced: only an explicit close works
    thread.join(5)
    server.close()
    assert seen.get("closed") is True
