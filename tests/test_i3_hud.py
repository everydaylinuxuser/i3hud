import json
import tempfile
from pathlib import Path

from i3_hud import (
    collect_bindings,
    deduplicate_entries,
    load_hud_settings,
    pick_primary_modifier,
    save_hud_config,
)


def test_collect_bindings_parses_i3_config_and_hud_overrides():
    with tempfile.TemporaryDirectory() as tmp:
        config_path = Path(tmp) / "config"
        config_path.write_text(
            """
            set $mod Mod4
            bindsym $mod+Return exec alacritty
            bindsym $mod+Shift+q kill
            bindsym XF86AudioRaiseVolume exec pactl raise
            """
        )

        hud_path = Path(tmp) / "hud_config.json"
        hud_path.write_text(
            json.dumps(
                {
                    "Terminal": "Mod4 + Return",
                    "Close window": "Mod4 + Shift + q",
                    "Volume up": "XF86AudioRaiseVolume",
                }
            )
        )

        bindings = collect_bindings(config_path, hud_path)

        assert "Terminal" in bindings
        assert bindings["Terminal"] == "Mod4 + Return"
        assert "Close window" in bindings
        assert bindings["Close window"] == "Mod4 + Shift + q"
        assert "Volume up" in bindings
        assert bindings["Volume up"] == "XF86AudioRaiseVolume"


def test_deduplicate_entries_keeps_first_shortcut_for_same_binding():
    entries = {
        "Terminal": "Mod4 + Return",
        "Other action": "mod4 + return",
        "Volume up": "XF86AudioRaiseVolume",
    }

    deduped = deduplicate_entries(entries)

    assert list(deduped.keys()) == ["Terminal", "Volume up"]
    assert deduped["Terminal"] == "Mod4 + Return"
    assert "Other action" not in deduped


def test_pick_primary_modifier_uses_most_common_modifier():
    bindings = {
        "Terminal": "Mod4 + Return",
        "Launcher": "Mod4 + Space",
        "Alt browser": "Mod1 + b",
        "Volume up": "XF86AudioRaiseVolume",
    }

    assert pick_primary_modifier(bindings) == "Mod4"


def test_modifier_setting_survives_binding_sync_without_becoming_a_binding():
    with tempfile.TemporaryDirectory() as tmp:
        config_path = Path(tmp) / "config"
        config_path.write_text("set $mod Mod4\nbindsym $mod+Return exec terminal\n")
        hud_path = Path(tmp) / "hud_config.json"
        save_hud_config(hud_path, {"Terminal": "Mod4 + Return"}, {"modifier": "Mod1"})

        bindings = collect_bindings(config_path, hud_path)

        assert bindings == {"Terminal": "Mod4 + Return"}
        assert load_hud_settings(hud_path) == {"modifier": "Mod1"}
