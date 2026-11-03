"""No Hassle AV Amplifier: a 6-zone Monoprice-protocol amp with tone controls.

Derived from Home Assistant Core's Monoprice integration (see NOTICE), with bass,
treble and balance added per zone.
"""

from dataclasses import dataclass, field
import logging
from typing import Any

from pymonoprice import Monoprice, get_monoprice
from serialx import SerialException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .connection import close_client
from .const import CONF_IMPORT_MARKER, CONF_NOT_FIRST_RUN, DOMAIN
from .services import async_setup_services

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.NUMBER]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type MonopriceConfigEntry = ConfigEntry[MonopriceRuntimeData]


@dataclass
class MonopriceRuntimeData:
    """Data stored in the config entry for an amplifier."""

    client: Monoprice
    first_run: bool
    # Latest ZoneStatus per zone id, written by the media_player poll and read
    # by the number entities so bass/treble/balance add no serial queries.
    zone_status: dict[int, Any] = field(default_factory=dict)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MonopriceConfigEntry) -> bool:
    """Set up one amplifier from a config entry."""
    if entry.data.get(CONF_IMPORT_MARKER):
        _LOGGER.warning(
            "%s was created by an import from an earlier version that may not have "
            "finished, and this version cannot finish it. If its entities show as "
            "no longer provided, install version 0.1.0, restart Home Assistant, then "
            "update again",
            entry.title,
        )

    port = entry.data[CONF_PORT]

    try:
        monoprice = await hass.async_add_executor_job(get_monoprice, port)
    except SerialException as err:
        _LOGGER.error("Error connecting to Monoprice controller at %s", port)
        raise ConfigEntryNotReady from err

    # double negative to handle absence of value
    first_run = not bool(entry.data.get(CONF_NOT_FIRST_RUN))

    if first_run:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_NOT_FIRST_RUN: True}
        )

    entry.async_on_unload(entry.add_update_listener(_update_listener))

    entry.runtime_data = MonopriceRuntimeData(
        client=monoprice,
        first_run=first_run,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MonopriceConfigEntry) -> bool:
    """Unload a config entry and release the serial port."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    await hass.async_add_executor_job(close_client, entry.runtime_data.client)

    return True


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
