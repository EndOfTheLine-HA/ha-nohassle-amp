# No Hassle AV Amplifier for Home Assistant

Control a Monoprice-compatible 6-zone amplifier (up to three chained, 18 zones)
from Home Assistant, with **bass, treble and balance** controls for every zone.
It is the amplifier half of the No Hassle AV pair; the HDMI matrix is a separate
integration, [No Hassle AV](https://github.com/EndOfTheLine-HA/ha-nohassle-av).

## What you get

- One **media player per zone**: power, volume, mute and source selection, with
  your own input names.
- **Bass, treble and balance** sliders on each zone's device page. They show the
  amplifier's own settings from the zone poll Home Assistant already makes, so they
  add no extra serial traffic; changing one sends a single command.
- **Save amplifier state** and **Restore amplifier state** services
  (`nohassle_amp.snapshot` and `nohassle_amp.restore`).
- Zones you do not use can be disabled, and the sliders go unavailable while a
  zone is off, because the amplifier ignores them then.

It talks to the amplifier over a serial device or a serial-over-IP address. Tested
against simulated amplifier responses; see [AUDIT.md](AUDIT.md) for what has and
has not been verified.

## Install

1. In HACS, open **Custom repositories** and add
   `https://github.com/EndOfTheLine-HA/ha-nohassle-amp` as an **Integration**.
2. Download **No Hassle AV Amplifier**, then restart Home Assistant.
3. Open **Settings > Devices & services > Add integration > No Hassle AV
   Amplifier** and enter the amplifier's connection address and input names.

Home Assistant **2026.9.4 or newer** is required.

**Do not run two integrations on one amplifier.** The serial port allows a single
connection, so Home Assistant's built-in Monoprice integration, the older
No Hassle AV 0.2.x, or the temporary ha-monoprice-tone-controls repository must not
control the same amplifier at the same time. Moving from one of those is below.

## Moving from the Monoprice integration

This integration does not read, move or remove another integration's entries,
devices or entities, so moving an amplifier set up under the **Monoprice**
integration (Home Assistant's built-in one, No Hassle AV 0.2.x, or
ha-monoprice-tone-controls) is a new setup:

1. Note your input names, then remove the old entry under **Settings > Devices &
   services**. If you used ha-monoprice-tone-controls, uninstall it in HACS.
2. Restart Home Assistant so the serial port is free, then follow **Install** above.
3. Set your areas, disabled zones and any custom names or entity IDs again, and
   check the dashboards and automations that use the zones.

Anything of yours that calls `monoprice.snapshot` or `monoprice.restore` must call
`nohassle_amp.snapshot` or `nohassle_amp.restore` instead.

**To keep your entity IDs and history,** version 0.1.0 can still import the old
entry:

1. Make a full Home Assistant backup.
2. In HACS, open **No Hassle AV Amplifier**, choose **Redownload** and pick **0.1.0**.
3. Restart Home Assistant, then open **Add integration > No Hassle AV Amplifier**
   and choose **Import the existing amplifier**.
4. Check that your zones and sliders still have their old names, then update to
   the latest version.

## Upgrading

**From 0.1.0:** update in HACS and restart Home Assistant. An amplifier whose import
to 0.1.0 finished keeps its entity IDs, names and history. Check first that the
amplifier and its entities work. 0.2.0 cannot finish an import that was interrupted;
if the log says an import may not have finished, install 0.1.0, restart, then update
again.

## Development and validation

See [AUDIT.md](AUDIT.md). CI runs the tests on Home Assistant 2026.9.4 and
2026.10.2, plus Ruff, HACS validation and Hassfest. Tests use simulated amplifier
responses; one test opens a local TCP socket to check that the serial connection is
really released.

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
