# i3 HUD

This project reads the i3 configuration file, extracts key bindings, and displays them in a compact desktop-style HUD overlay.

## Features

- Parses `bindsym` entries from `~/.config/i3/config`
- Supports custom action-to-keybinding overrides in `i3_hud_config.json`
- Uses a dark, translucent, desktop-friendly layout
- Works without any third-party dependencies

## Run it

```bash
python3 i3_hud.py
```

To print the parsed bindings without opening the window:

```bash
python3 i3_hud.py --dump
```

To point at a different i3 config or override file:

```bash
python3 i3_hud.py --config ~/.config/i3/config --hud-config ./i3_hud_config.json
```

## Config format

The HUD config is a JSON object where each key is the action and each value is the key binding:

```json
{
  "_settings": {
    "modifier": "Mod4"
  },
  "Launch terminal": "Mod4 + Return",
  "Close active window": "Mod4 + Shift + q",
  "Open app launcher": "Mod4 + d"
}
```

The modifier value appears in the HUD's top modifier row. Change it in the **Modifier key** field in **Edit config**, or edit `_settings.modifier` directly in `i3_hud_config.json`. If it is not set, the HUD infers the most common modifier from the bindings.

## Add to I3 config as a toggle

Add the following lines to your I3 config file

```
for_window [title = "i3 Hud"] floating enable, move position center
bindsym $mod+Shift+h exec --nostartup-id ~/.local/bin/i3-hud-toggle

```

### Debian package
Create the following file in .local/bin/i3-hud-toggle

```
#!/bin/sh

if i3-msg -t get_tree | grep -q '"title":"i3 HUD"'; then
    i3-msg '[title="i3 HUD"] kill'
else
    i3-hud
fi

```

### Flatpak

```
#!/bin/sh

if i3-msg -t get_tree | grep -q '"title":"i3 HUD"'; then
    i3-msg '[title="i3 HUD"] kill'
else
    flatpak run com.github.com/everydaylinuxuser.i3hud
fi

```

Make the script executable

```
chmod +x ~/.local/bin/i3-hud-huddle
```

Restart I3
