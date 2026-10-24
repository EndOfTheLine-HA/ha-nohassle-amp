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

If your amplifier is set up under the **Monoprice** integration (Home Assistant's
built-in one, No Hassle AV 0.2.x, or ha-monoprice-tone-controls), this integration
can take it over and keep **every entity ID, the history, custom names, areas,
disabled zones and your input names**.

1. Make a full Home Assistant backup.
2. Install this integration through HACS and restart Home Assistant.
3. Open **Settings > Devices & services > Add integration > No Hassle AV
   Amplifier** and choose **Import the existing amplifier**.
4. The amplifier is unavailable for a moment while its entities and devices move
   and the old entry is removed. Check that your zones and sliders are back with
   their old names.
5. If you used ha-monoprice-tone-controls, uninstall it in HACS afterwards. It is
   no longer needed.

Do not delete entities that show as unavailable or "no longer provided" while this
happens; they come back. If the old Monoprice entry cannot be removed
automatically, the log says so and it can be deleted from **Settings > Devices &
services** after the import.

Anything of yours that calls `monoprice.snapshot` or `monoprice.restore` must call
`nohassle_amp.snapshot` or `nohassle_amp.restore` instead. Entity IDs are
unchanged, so dashboards and automations that use the zones keep working.

## Development and validation

See [AUDIT.md](AUDIT.md). CI runs the tests on Home Assistant 2026.9.4 and
2026.10.2, plus Ruff, HACS validation and Hassfest. Tests use simulated amplifier
responses; one test opens a local TCP socket to check that the serial connection is
really released.

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
