"""Constants for the No Hassle AV Amplifier integration."""

DOMAIN = "nohassle_amp"

# Amp entries made before 0.1.0 live in this domain: the temporary
# ha-monoprice-tone-controls repository, an earlier No Hassle AV, or HA's built-in
# Monoprice integration.
LEGACY_DOMAIN = "monoprice"

CONF_MIGRATED_FROM = "migrated_from"
CONF_LEGACY_ENTRY_ID = "legacy_entry_id"

CONF_SOURCES = "sources"

CONF_SOURCE_1 = "source_1"
CONF_SOURCE_2 = "source_2"
CONF_SOURCE_3 = "source_3"
CONF_SOURCE_4 = "source_4"
CONF_SOURCE_5 = "source_5"
CONF_SOURCE_6 = "source_6"

CONF_NOT_FIRST_RUN = "not_first_run"

SERVICE_SNAPSHOT = "snapshot"
SERVICE_RESTORE = "restore"

# Fired (entry_id, zone_id) after a zone poll refreshes the cached ZoneStatus.
SIGNAL_ZONE_UPDATED = "nohassle_amp_zone_updated_{}_{}"
