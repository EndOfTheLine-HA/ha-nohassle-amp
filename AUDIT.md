# Audit

## Privacy boundary

A private Home Assistant installation was used only to read the shape of the
amplifier's registry entries (counts, flags and identifier formats). This repository
excludes personal names, network addresses, serial device paths, configuration-entry
identifiers, room and source labels and entity inventories. Tests use placeholder
values and the documentation address 192.0.2.20.

## What this repository is

A copy of Home Assistant Core's `monoprice` integration (Apache-2.0) with a `number`
platform adding bass, treble and balance per zone, under its own domain
`nohassle_amp` so it does not replace a built-in integration. It continues the
temporary ha-monoprice-tone-controls repository, which kept the `monoprice` domain.

## Behaviour confirmed by tests

- Zone unique IDs are `<entry ID>_<zone>`, tone-control unique IDs are
  `<entry ID>_<zone>_<bass|treble|balance>`, and a zone's device identifier is
  `(nohassle_amp, "<entry ID>_<zone>")`. The same shape as the built-in
  integration, which is what the migration rewrites the prefix of.
- Tone controls read the zone status the media player already caches; setting one
  sends a single command with the amplifier's offset.
- A new amplifier is detected as a first run; an imported one is not, so its 18
  zones are not polled over serial before being added.
- A second entry for a connection that is already configured is refused.
- Unloading releases the serial port.

## Amplifier migration

An amplifier entry in the `monoprice` domain (HTTP matrix entries, which share that
domain, are excluded) is imported by the config flow, which creates a `nohassle_amp`
entry marked with the old entry's ID and copies its connection, input names
(`sources`), options and first-run flag. Before the serial port is opened, that
entry's setup:

1. Remembers the old entry's connection, unloads the old entry (entities can only
   change integration while not loaded) and fails without moving anything if the
   unload is refused.
2. Closes the old serial connection explicitly. serialx opens the port exclusively
   and releases it only when the Python object is destroyed; `pymonoprice` has no
   `close()`, so `connection.close_client` closes its private port. A test against
   the real library, over a local TCP socket, shows the connection is released
   while the object is still alive.
3. Moves every entity (disabled ones included) with
   `entity_registry.async_update_entity_platform`, rewriting the unique-ID prefix.
   Entity IDs, history, custom names, options and disabled flags are kept.
4. Moves every device with one `async_update_device` call (new entry ID and
   identifiers), keeping its ID, area, user-given name and disabled state. Entities
   move first because moving a device removes any of its entities still registered
   to the old entry.
5. Removes the old entry. A failure is logged and never undoes the move.
6. Clears the marker, then opens the port. If it is still held, setup raises
   `ConfigEntryNotReady` and Home Assistant retries; the migration is idempotent.

Tests run this on real isolated area, device and entity registries shaped like a
real install: 18 zone devices (12 disabled), 72 entities (48 disabled), a renamed
device in an area, a renamed entity and custom input names. Fourteen mutation checks
cover each ordering and API-use decision: devices before entities, no unload, no
close, no prefix rewrite, skipping disabled devices, marker kept, options dropped,
failed unload ignored, matrix entries counted, port not released on unload,
first-run flag dropped, existing-entry check dropped, migration after the port is
opened and removal failure not tolerated.

## Deliberate exclusions

- No HDMI matrix code (it lives in `ha-nohassle-av`).
- Not a replacement for Home Assistant's built-in Monoprice integration: it has its
  own domain, and the two must not control the same amplifier.

## Validation boundary

Automated tests use simulated amplifier responses. **The migration has not yet been
run on a real installation or a real serial connection.** What only a live run can
show is whether the old integration's process lets go of the port in time; the
explicit close and the retry are there to cover that. CI runs Ruff, the tests on Home
Assistant 2026.9.4 and 2026.10.2, HACS validation and Hassfest. Long-term behaviour
with every amplifier firmware is not claimed.
