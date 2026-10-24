"""Move an amplifier from the `monoprice` domain to `nohassle_amp`.

Before 0.1.0 the amp, with or without tone controls, ran as a `monoprice` entry
(the temporary ha-monoprice-tone-controls repository, an earlier No Hassle AV, or
Home Assistant's built-in integration). The new entry is created by the import
(or user) config flow; this module then moves the old entry's devices and entities
across and removes it, so entity IDs, history, custom names, areas, voice-exposure
options and disabled flags all carry over.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .connection import close_client
from .const import (
    CONF_MIGRATED_FROM,
    CONF_NOT_FIRST_RUN,
    CONF_SOURCES,
    DOMAIN,
    LEGACY_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@callback
def legacy_amp_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    """Old amplifier entries (not the HDMI matrix) that have not been migrated."""
    return [
        entry
        for entry in hass.config_entries.async_entries(LEGACY_DOMAIN)
        if entry.data.get("device_type") != "matrix" and CONF_PORT in entry.data
    ]


def legacy_entry_data(entry: ConfigEntry) -> dict:
    """Data for the new entry, taken from an old amplifier entry."""
    data = {
        CONF_PORT: entry.data[CONF_PORT],
        CONF_SOURCES: dict(entry.data.get(CONF_SOURCES, {})),
        CONF_MIGRATED_FROM: entry.entry_id,
    }
    if entry.data.get(CONF_NOT_FIRST_RUN):
        data[CONF_NOT_FIRST_RUN] = True
    return data


def legacy_entry_options(entry: ConfigEntry) -> dict:
    """The old entry's options, which hold any custom input names."""
    return dict(entry.options)


async def async_finish_migration(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Take over the old entry's devices and entities, then remove the old entry.

    Safe to run again: if the old entry is already gone, only the marker is
    cleared.
    """
    legacy_id = entry.data[CONF_MIGRATED_FROM]
    legacy = hass.config_entries.async_get_entry(legacy_id)

    if legacy is not None:
        # The old entry holds the serial port. Take its connection first: unloading
        # drops the entry's data, but only garbage collection would close the port,
        # and the new entry cannot open it while it is held.
        runtime_data = getattr(legacy, "runtime_data", None)
        client = getattr(runtime_data, "client", None)

        # Entities can only change integration while they are not loaded.
        if legacy.state is ConfigEntryState.LOADED and not (
            await hass.config_entries.async_unload(legacy_id)
        ):
            raise ConfigEntryError(
                f"Could not unload {legacy.title}, so it cannot be moved yet"
            )
        if client is not None:
            await hass.async_add_executor_job(close_client, client)

        # Order matters: entities first, then the devices. Moving a device to
        # another config entry removes any of its entities still registered to the
        # old one.
        moved = _move_entities(hass, legacy_id, entry)
        devices = _move_devices(hass, legacy_id, entry)
        try:
            await hass.config_entries.async_remove(legacy_id)
        except Exception:  # noqa: BLE001 - the move above must not be undone by this
            # Removing the old entry loads the old integration's code. If that
            # fails, everything has already moved; leave an empty old entry for the
            # user to delete rather than failing this setup.
            _LOGGER.warning(
                "Moved amplifier %s, but could not remove its old %s entry; "
                "delete it from Settings > Devices & services",
                entry.title,
                LEGACY_DOMAIN,
                exc_info=True,
            )
        _LOGGER.info(
            "Moved amplifier %s (%d devices, %d entities) from %s to %s",
            entry.title,
            devices,
            moved,
            LEGACY_DOMAIN,
            DOMAIN,
        )

    data = {
        key: value for key, value in entry.data.items() if key != CONF_MIGRATED_FROM
    }
    hass.config_entries.async_update_entry(entry, data=data)


def _move_devices(hass: HomeAssistant, legacy_id: str, entry: ConfigEntry) -> int:
    """Re-home every zone device so its ID, area, name and disabled state are kept."""
    registry = dr.async_get(hass)
    prefix = f"{legacy_id}_"
    moved = 0
    for device in dr.async_entries_for_config_entry(registry, legacy_id):
        identifiers = set()
        for domain, identifier in device.identifiers:
            if domain == LEGACY_DOMAIN and identifier.startswith(prefix):
                identifier = f"{entry.entry_id}_{identifier.removeprefix(prefix)}"
                domain = DOMAIN
            identifiers.add((domain, identifier))
        # One call: a device belongs to a single config entry. The older
        # add_config_entry_id / remove_config_entry_id pair is deprecated, and
        # remove_config_entry_id on its own deletes the device.
        registry.async_update_device(
            device.id,
            new_config_entry_id=entry.entry_id,
            new_identifiers=identifiers,
        )
        moved += 1
    return moved


def _move_entities(hass: HomeAssistant, legacy_id: str, entry: ConfigEntry) -> int:
    """Move every entity of the old entry, rewriting its unique ID prefix."""
    registry = er.async_get(hass)
    prefix = f"{legacy_id}_"
    moved = 0
    for entity in er.async_entries_for_config_entry(registry, legacy_id):
        unique_id = entity.unique_id
        if unique_id.startswith(prefix):
            unique_id = f"{entry.entry_id}_{unique_id.removeprefix(prefix)}"
        registry.async_update_entity_platform(
            entity.entity_id,
            DOMAIN,
            new_config_entry_id=entry.entry_id,
            new_unique_id=unique_id,
        )
        moved += 1
    return moved
