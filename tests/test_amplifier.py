"""Amplifier entities, tone controls, setup, config flow and unload."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from serialx import SerialException

from custom_components.nohassle_amp.const import DOMAIN
from custom_components.nohassle_amp.media_player import MonopriceZone
from custom_components.nohassle_amp.number import NUMBERS, MonopriceZoneNumber
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.helpers import entity_registry as er

from .conftest import FakeAmp

PORT = "socket://192.0.2.20:4999"  # documentation address, never a real amplifier
SOURCES = [{1: "Input 1"}, {"Input 1": 1}, ["Input 1"]]


def test_unique_ids_are_pinned():
    """These formats are what the amp migration rewrites the prefix of.

    The same shape as Home Assistant's built-in Monoprice integration, so an
    amplifier imported from it keeps every entity.
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
        assert result["step_id"] == "manual"  # no old amplifier, no menu
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
    """Against the real library, not a fake: the migration depends on this.

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
