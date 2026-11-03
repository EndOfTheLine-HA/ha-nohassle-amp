"""Isolated Home Assistant with a simulated amplifier. No test opens a serial port."""

from __future__ import annotations

from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pymonoprice import ZoneStatus
import pytest

from homeassistant import loader
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)


@pytest.fixture
async def hass(tmp_path):
    source = Path(__file__).parents[1] / "custom_components" / "nohassle_amp"
    shutil.copytree(
        source,
        tmp_path / "custom_components" / "nohassle_amp",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    instance = HomeAssistant(str(tmp_path))
    instance.config_entries = ConfigEntries(instance, {})
    # The manifest depends on `usb` for the serial port picker. A real install has
    # it running; a bare test instance cannot start its web server, so mark it up.
    instance.config.components.add("usb")
    # media_player depends on the web server and registers a view with it.
    instance.config.components.add("http")
    instance.http = Mock()
    loader.async_setup(instance)
    dr.async_setup(instance)
    await ar.async_load(instance, load_empty=True)
    await dr.async_load(instance, load_empty=True)
    await er.async_load(instance, load_empty=True)
    yield instance
    await instance.async_stop(force=True)


class FakeAmp:
    """Stands in for pymonoprice.Monoprice. Zone 11 is on, the rest are off."""

    def __init__(self) -> None:
        self._port = SimpleNamespace(close=Mock())
        for setter in (
            "set_power",
            "set_mute",
            "set_volume",
            "set_source",
            "set_bass",
            "set_treble",
            "set_balance",
            "restore_zone",
        ):
            setattr(self, setter, Mock())

    def zone_status(self, zone: int) -> ZoneStatus:
        # treble/bass 7 and balance 10 are the middle of their ranges.
        return ZoneStatus(zone, False, zone == 11, False, False, 10, 7, 7, 10, 1, True)


@pytest.fixture
def amp():
    """The simulated amplifier every new entry connects to."""
    fake = FakeAmp()
    with patch("custom_components.nohassle_amp.get_monoprice", return_value=fake):
        yield fake
