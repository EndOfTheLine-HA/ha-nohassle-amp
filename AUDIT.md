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
  integration. Existing installs are keyed on these formats.
- Tone controls read the zone status the media player already caches; setting one
  sends a single command with the amplifier's offset.
- A new amplifier is detected as a first run; an entry that has already run is not,
  so its 18 zones are not polled over serial before being added.
- A second entry for a connection that is already configured is refused.
- A serial port that is busy at setup is retried.
- Unloading releases the serial port.
- An amplifier entry left under the `monoprice` domain, with its devices and
  entities, is not changed by adding an amplifier here or by an unfinished import
  marker.

## No import from other integrations

Version 0.1.0 could import an amplifier entry from the `monoprice` domain, moving
its devices and entities and removing the old entry. Version 0.2.0 removes that
import after review feedback that an integration should leave another integration's
entries alone. Nothing in this integration now reads, moves or removes another
integration's config entries, devices or entities. An entry that still carries the
marker of an import that did not finish gets a warning in the log and is otherwise
set up normally. Version 0.1.0 stays available for anyone who needs the import.

## Serial connection

serialx opens the port exclusively and releases it only when the Python object is
destroyed; `pymonoprice` has no `close()`, so `connection.close_client` closes its
private port when the entry unloads. A test against the real library, over a local
TCP socket, shows the connection is released while the object is still alive.

## Deliberate exclusions

- No HDMI matrix code (it lives in `ha-nohassle-av`).
- Not a replacement for Home Assistant's built-in Monoprice integration: it has its
  own domain, and the two must not control the same amplifier.

## Validation boundary

Automated tests use simulated amplifier responses. **Version 0.2.0 has not been run
on a real amplifier.** CI runs Ruff, the tests on Home Assistant 2026.9.4 and
2026.10.2, HACS validation and Hassfest. Long-term behaviour with every amplifier
firmware is not claimed.
