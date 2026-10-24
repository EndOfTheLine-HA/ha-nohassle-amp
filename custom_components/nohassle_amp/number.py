"""Bass, treble and balance sliders for Monoprice 6-Zone Amplifier zones.

Local addition to the core integration. Values come from the ZoneStatus the
media_player poll caches in runtime_data, so these entities add no serial
queries; changing one sends a single command to the amp.
"""

from dataclasses import dataclass
import time
from typing import override

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MonopriceConfigEntry, MonopriceRuntimeData
from .const import DOMAIN, SIGNAL_ZONE_UPDATED

PARALLEL_UPDATES = 1

# A poll that raced a slider change can briefly report the old value; ignore
# cache updates for this long after a change so the slider doesn't jump back.
SET_GRACE_SECONDS = 3


@dataclass(frozen=True, kw_only=True)
class MonopriceNumberDescription(NumberEntityDescription):
    """Describes a Monoprice zone number."""

    status_attr: str
    setter: str
    # amp value = displayed value + offset
    offset: int


NUMBERS: tuple[MonopriceNumberDescription, ...] = (
    MonopriceNumberDescription(
        key="bass",
        name="Bass",
        icon="mdi:speaker",
        native_min_value=-7,
        native_max_value=7,
        native_step=1,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        status_attr="bass",
        setter="set_bass",
        offset=7,
    ),
    MonopriceNumberDescription(
        key="treble",
        name="Treble",
        icon="mdi:music-clef-treble",
        native_min_value=-7,
        native_max_value=7,
        native_step=1,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        status_attr="treble",
        setter="set_treble",
        offset=7,
    ),
    MonopriceNumberDescription(
        key="balance",
        name="Balance",
        icon="mdi:scale-balance",
        native_min_value=-10,
        native_max_value=10,
        native_step=1,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        status_attr="balance",
        setter="set_balance",
        offset=10,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MonopriceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up bass/treble/balance numbers for each enabled zone."""
    ent_reg = er.async_get(hass)

    entities = []
    for i in range(1, 4):
        for j in range(1, 7):
            zone_id = (i * 10) + j
            zone_uid = f"{config_entry.entry_id}_{zone_id}"
            player_id = ent_reg.async_get_entity_id(
                MEDIA_PLAYER_DOMAIN, DOMAIN, zone_uid
            )
            if player_id is None:
                # Zone not registered yet: follow the media_player default of
                # only enabling the first amp's zones.
                if zone_id > 20:
                    continue
            elif (player := ent_reg.async_get(player_id)) and player.disabled:
                continue
            entities.extend(
                MonopriceZoneNumber(
                    config_entry.runtime_data,
                    config_entry.entry_id,
                    zone_id,
                    description,
                )
                for description in NUMBERS
            )

    async_add_entities(entities)


class MonopriceZoneNumber(NumberEntity):
    """Bass, treble or balance control for one amplifier zone."""

    entity_description: MonopriceNumberDescription
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        runtime_data: MonopriceRuntimeData,
        namespace: str,
        zone_id: int,
        description: MonopriceNumberDescription,
    ) -> None:
        """Initialize the number."""
        self.entity_description = description
        self._runtime_data = runtime_data
        self._zone_id = zone_id
        self._signal = SIGNAL_ZONE_UPDATED.format(namespace, zone_id)
        self._last_set = 0.0
        self._zone_on = False
        self._attr_unique_id = f"{namespace}_{zone_id}_{description.key}"
        # Same identifiers as the zone's media_player so it lands on that device.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{namespace}_{zone_id}")},
            manufacturer="Monoprice",
            model="6-Zone Amplifier",
            name=f"Zone {zone_id}",
        )

    @property
    @override
    def available(self) -> bool:
        """Return True when the zone has been polled and is powered on.

        The amp ignores bass/treble/balance for zones that are off, so the
        slider is unavailable rather than silently snapping back.
        """
        return self._zone_on and self._attr_native_value is not None

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to zone poll updates."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._handle_zone_update)
        )
        self._read_cached_status()

    @callback
    def _read_cached_status(self, update_value: bool = True) -> bool:
        """Load power and value from the cached zone status, if any."""
        status = self._runtime_data.zone_status.get(self._zone_id)
        if status is None:
            return False
        self._zone_on = status.power
        if update_value:
            description = self.entity_description
            self._attr_native_value = (
                getattr(status, description.status_attr) - description.offset
            )
        return True

    @callback
    def _handle_zone_update(self) -> None:
        """Handle a fresh poll of this zone."""
        # Keep tracking power during the grace period, but don't let a poll
        # that raced a slider change overwrite the new value.
        in_grace = time.monotonic() - self._last_set < SET_GRACE_SECONDS
        if self._read_cached_status(update_value=not in_grace):
            self.async_write_ha_state()

    @override
    def set_native_value(self, value: float) -> None:
        """Send the new value to the amp."""
        description = self.entity_description
        amp_value = round(value) + description.offset
        getattr(self._runtime_data.client, description.setter)(self._zone_id, amp_value)
        self._last_set = time.monotonic()
        self._attr_native_value = amp_value - description.offset
        self.schedule_update_ha_state()
