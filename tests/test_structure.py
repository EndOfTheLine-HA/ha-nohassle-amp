"""Repository checks for No Hassle AV Amplifier."""

from __future__ import annotations

import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "custom_components" / "nohassle_amp"


def test_metadata():
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert manifest["domain"] == PACKAGE.name == "nohassle_amp"
    # Hassfest rejects an exact pin of a package Home Assistant core depends on.
    assert manifest["requirements"] == ["pymonoprice>=0.6.1"]
    assert manifest["version"] == project["project"]["version"] == "0.2.0"


def test_it_does_not_replace_a_built_in_integration():
    """The HACS default catalog rejects integrations that override core ones."""
    assert [path.name for path in (ROOT / "custom_components").iterdir()] == [
        "nohassle_amp"
    ]


def test_nothing_touches_another_integration():
    """Setup and flows stay inside this domain, as the HACS review asked."""
    assert not (PACKAGE / "migration.py").exists()
    forbidden = (
        '"monoprice"',
        "legacy",
        "async_update_entity_platform",
        "async_update_device",
        "config_entries.async_remove",
    )
    for path in PACKAGE.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for word in forbidden:
            assert word not in text, f"{path.name}: {word}"
    strings = (PACKAGE / "strings.json").read_text(encoding="utf-8")
    assert "migrate" not in strings and "legacy" not in strings


def test_services_target_this_integration():
    services = (PACKAGE / "services.yaml").read_text(encoding="utf-8")
    assert services.count("integration: nohassle_amp") == 2
    assert "integration: monoprice" not in services


def test_english_translation_matches_source_strings():
    strings = json.loads((PACKAGE / "strings.json").read_text(encoding="utf-8"))
    english = json.loads(
        (PACKAGE / "translations" / "en.json").read_text(encoding="utf-8")
    )
    assert english == strings


def test_brand_icons_are_shipped():
    """HACS validation needs local brand assets for a custom integration."""
    for name in ("icon.png", "icon@2x.png"):
        assert (PACKAGE / "brand" / name).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_no_em_dashes_in_user_facing_text():
    files = [
        ROOT / "README.md",
        ROOT / "AUDIT.md",
        ROOT / "SECURITY.md",
        PACKAGE / "strings.json",
    ]
    for path in files:
        assert chr(0x2014) not in path.read_text(encoding="utf-8"), path.name
