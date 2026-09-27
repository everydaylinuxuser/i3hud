#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Dict, Iterable, Optional

HUD_SETTINGS_KEY = "_settings"

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:  # pragma: no cover
    tk = None


def read_i3_variables(config_path: Path) -> Dict[str, str]:
    variables: Dict[str, str] = {}
    if not config_path.exists():
        return variables

    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.match(r"set\s+\$([A-Za-z0-9_]+)\s+(.+)", line)
        if match:
            name, value = match.groups()
            variables[name] = value.strip()
    return variables


def format_binding(binding: str, variables: Optional[Dict[str, str]] = None) -> str:
    variables = variables or {}
    cleaned = binding.strip()
    for name, value in variables.items():
        cleaned = cleaned.replace(f"${name}", value)

    # Strip leading modifiers like --release and extra spaces.
    cleaned = cleaned.replace("--release", "").strip()

    if not cleaned:
        return ""

    parts = [part.strip() for part in cleaned.split("+") if part.strip()]
    formatted = " + ".join(part for part in parts if part)
    return formatted


def infer_action(command: str) -> str:
    action = command.strip()
    action = action.replace("exec", "", 1).strip()
    action = action.replace("--no-startup-id", "", 1).strip()
    action = action.replace("&&", " • ").strip()
    if not action:
        return "Unknown action"
    return action


def parse_bindings(config_path: Path) -> Dict[str, str]:
    bindings: Dict[str, str] = {}
    if not config_path.exists():
        return bindings

    variables = read_i3_variables(config_path)
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        try:
            tokens = shlex.split(line, posix=True)
        except ValueError:
            continue

        if not tokens or tokens[0] not in {"bindsym", "bindcode"}:
            continue

        if len(tokens) < 3:
            continue

        if tokens[0] == "bindsym":
            binding = tokens[1]
            command = " ".join(tokens[2:])
        else:
            if tokens[1] == "--release":
                binding = tokens[2]
                command = " ".join(tokens[3:])
            else:
                binding = tokens[1]
                command = " ".join(tokens[2:])

        if not binding:
            continue

        pretty_binding = format_binding(binding, variables)
        action = infer_action(command)
        bindings[action] = pretty_binding

    return bindings


def load_hud_config(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {}

    if not isinstance(payload, dict):
        return {}

    cleaned: Dict[str, str] = {}
    for key, value in payload.items():
        if isinstance(value, str):
            cleaned[str(key)] = value.strip()
    return cleaned


def load_hud_settings(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {}

    if not isinstance(payload, dict) or not isinstance(payload.get(HUD_SETTINGS_KEY), dict):
        return {}
    return {
        str(key): value.strip()
        for key, value in payload[HUD_SETTINGS_KEY].items()
        if isinstance(value, str) and value.strip()
    }


def save_hud_config(path: Path, entries: Dict[str, str], settings: Dict[str, str]) -> None:
    payload = dict(entries)
    if settings:
        payload[HUD_SETTINGS_KEY] = settings
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def normalize_shortcut(shortcut: str) -> str:
    return " ".join(shortcut.strip().lower().split())


def prettify_shortcut(shortcut: str) -> str:
    if not shortcut:
        return ""

    display = shortcut.strip()
    replacements = {
        "Mod4": "Mod4",
        "Mod1": "Alt",
        "Control": "Ctrl",
        "Ctrl": "Ctrl",
        "Shift": "Shift",
        "Super_L": "Super",
        "Super_R": "Super",
        "Alt": "Alt",
        "Return": "Enter",
        "KP_Enter": "Enter",
        "space": "Space",
        "Escape": "Esc",
        "Left": "←",
        "Right": "→",
        "Up": "↑",
        "Down": "↓",
        "XF86AudioRaiseVolume": "Volume Up",
        "XF86AudioLowerVolume": "Volume Down",
        "XF86AudioMute": "Mute",
        "XF86AudioMicMute": "Mic Mute",
    }

    for token, label in replacements.items():
        display = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", label, display)

    display = display.replace("Mod40", "Mod4 + Win")
    display = display.replace("Mod4 + Win", "Mod4 + Win")

    for marker in [" + ", " +", "+ "]:
        if marker in display:
            parts = [part.strip() for part in display.split("+")]
            cleaned = " + ".join(part for part in parts if part)
            display = cleaned
            break

    display = re.sub(r"\s+", " ", display).strip()
    return display


def extract_modifier(shortcut: str) -> Optional[str]:
    if not shortcut:
        return None

    normalized = shortcut.strip()
    for label in ["Mod4", "Mod3", "Mod2", "Mod1", "Alt", "Ctrl", "Control", "Super", "Super_L", "Super_R", "Shift"]:
        if label in normalized:
            if label == "Mod4":
                return "Mod4"
            if label in {"Mod3", "Mod2", "Mod1"}:
                return label
            if label in {"Super_L", "Super_R"}:
                return "Super"
            return label
    if "Mod40" in normalized:
        return "Mod4"
    return None


def pick_primary_modifier(bindings: Dict[str, str]) -> str:
    counts: Dict[str, int] = {}
    for shortcut in bindings.values():
        modifier = extract_modifier(shortcut)
        if modifier:
            counts[modifier] = counts.get(modifier, 0) + 1
    if not counts:
        return "Mod4"
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def deduplicate_entries(entries: Dict[str, str]) -> Dict[str, str]:
    deduped: Dict[str, str] = {}
    seen: set[str] = set()
    for action, shortcut in entries.items():
        normalized = normalize_shortcut(shortcut)
        if not normalized:
            continue
        if normalized in seen:
            continue
        deduped[action] = shortcut
        seen.add(normalized)
    return deduped


def merge_hud_entries(parsed: Dict[str, str], overrides: Dict[str, str]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    seen: set[str] = set()

    for action, shortcut in dict(overrides).items():
        normalized = normalize_shortcut(shortcut)
        if not normalized:
            continue
        merged[action] = shortcut
        seen.add(normalized)

    for action, shortcut in dict(parsed).items():
        normalized = normalize_shortcut(shortcut)
        if not normalized or normalized in seen:
            continue
        if action in merged:
            continue
        merged[action] = shortcut
        seen.add(normalized)

    return dict(sorted(merged.items(), key=lambda item: item[0].lower()))


def resolve_config_path(config_path: str | Path) -> Path:
    resolved = Path(config_path).expanduser()
    if resolved.is_dir():
        candidate = resolved / "config"
        if candidate.exists():
            return candidate
    return resolved


def sync_hud_config(config_path: str | Path, hud_config_path: str | Path | None = None) -> Dict[str, str]:
    config_path = resolve_config_path(config_path)
    parsed = parse_bindings(config_path)
    if hud_config_path is None:
        return parsed

    hud_config_path = Path(hud_config_path).expanduser()
    overrides = load_hud_config(hud_config_path)
    settings = load_hud_settings(hud_config_path)
    merged = merge_hud_entries(parsed, overrides)

    save_hud_config(hud_config_path, merged, settings)

    return merged


def collect_bindings(config_path: str | Path, hud_config_path: str | Path | None = None) -> Dict[str, str]:
    config_path = resolve_config_path(config_path)
    if hud_config_path is None:
        return parse_bindings(config_path)

    hud_config_path = Path(hud_config_path).expanduser()
    synced = sync_hud_config(config_path, hud_config_path)
    return synced


def read_custom_config_entries(config_path: str | Path, hud_config_path: str | Path | None = None) -> Dict[str, str]:
    config_path = resolve_config_path(config_path)
    parsed = parse_bindings(config_path)

    if hud_config_path is None:
        return dict(parsed)

    hud_config_path = Path(hud_config_path).expanduser()
    override_entries = load_hud_config(hud_config_path)
    return merge_hud_entries(parsed, override_entries)


class ConfigEditorWindow:
    def __init__(self, config_path: str | Path, hud_config_path: str | Path, master: Optional[tk.Tk] = None, hud_window: Optional["HUDWindow"] = None):
        self.config_path = resolve_config_path(config_path)
        self.hud_config_path = Path(hud_config_path).expanduser()
        self.master = master or tk.Tk()
        self.hud_window = hud_window
        self.root = tk.Toplevel(self.master) if master is not None else self.master
        self.root.title("i3 HUD config editor")
        self.root.configure(bg="#0b1020")
        self.root.geometry("820x560")
        self.root.attributes("-topmost", True)
        self.root.minsize(700, 400)

        self.entry_vars = {}
        self._build_ui()

    def _build_ui(self):
        header = tk.Label(
            self.root,
            text="Edit HUD config",
            bg="#0b1020",
            fg="#f8fafc",
            font=("JetBrains Mono", 16, "bold"),
            anchor="w",
        )
        header.pack(fill="x", padx=18, pady=(18, 10))

        subtitle = tk.Label(
            self.root,
            text="Update the displayed action text and shortcut for each i3 binding. The save button writes this back to the JSON config.",
            bg="#0b1020",
            fg="#cbd5e1",
            wraplength=760,
            justify="left",
            font=("JetBrains Mono", 10),
        )
        subtitle.pack(fill="x", padx=18, pady=(0, 12))

        entries = read_custom_config_entries(self.config_path, self.hud_config_path)
        saved_modifier = load_hud_settings(self.hud_config_path).get("modifier")
        self.modifier_var = tk.StringVar(value=saved_modifier or pick_primary_modifier(entries))
        modifier_row = tk.Frame(self.root, bg="#111827", padx=12, pady=10)
        modifier_row.pack(fill="x", padx=18, pady=(0, 12))
        modifier_label = tk.Label(
            modifier_row,
            text="Modifier key",
            fg="#dbeafe",
            bg="#111827",
            font=("JetBrains Mono", 10, "bold"),
        )
        modifier_label.pack(side="left", padx=(0, 12))
        modifier_entry = tk.Entry(
            modifier_row,
            textvariable=self.modifier_var,
            bg="#0f172a",
            fg="#7dd3fc",
            insertbackground="#7dd3fc",
            width=20,
        )
        modifier_entry.pack(side="left")

        frame = tk.Frame(self.root, bg="#0b1020")
        frame.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        scroll = tk.Scrollbar(frame, orient="vertical")
        canvas = tk.Canvas(frame, bg="#0b1020", highlightthickness=0, yscrollcommand=scroll.set)
        scroll.config(command=canvas.yview)
        inner = tk.Frame(canvas, bg="#0b1020")
        canvas.create_window((0, 0), window=inner, anchor="nw")

        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        for index, (action, shortcut) in enumerate(entries.items()):
            row = tk.Frame(inner, bg="#111827" if index % 2 == 0 else "#0f172a", padx=12, pady=10)
            row.pack(fill="x", pady=4)

            action_var = tk.StringVar(value=action)
            shortcut_var = tk.StringVar(value=shortcut)
            self.entry_vars[action] = {"action": action_var, "shortcut": shortcut_var}

            action_label = tk.Label(row, text="Action", fg="#dbeafe", bg=row["bg"], font=("JetBrains Mono", 10, "bold"))
            action_label.grid(row=0, column=0, sticky="w", padx=(0, 8))
            action_entry = tk.Entry(row, textvariable=action_var, bg="#0f172a", fg="#f8fafc", insertbackground="#7dd3fc", width=48)
            action_entry.grid(row=0, column=1, sticky="ew", padx=(0, 18))

            shortcut_label = tk.Label(row, text="Shortcut", fg="#dbeafe", bg=row["bg"], font=("JetBrains Mono", 10, "bold"))
            shortcut_label.grid(row=0, column=2, sticky="w", padx=(0, 8))
            shortcut_entry = tk.Entry(row, textvariable=shortcut_var, bg="#0f172a", fg="#7dd3fc", insertbackground="#7dd3fc", width=26)
            shortcut_entry.grid(row=0, column=3, sticky="ew")

            row.columnconfigure(1, weight=1)
            row.columnconfigure(3, weight=1)

        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", on_configure)

        buttons = tk.Frame(self.root, bg="#0b1020")
        buttons.pack(fill="x", padx=18, pady=(0, 20))

        save_btn = tk.Button(buttons, text="Save config", command=self.save_changes, bg="#2563eb", fg="#eff6ff", font=("JetBrains Mono", 10, "bold"), relief="flat", padx=18, pady=8)
        save_btn.pack(side="right")

        close_btn = tk.Button(buttons, text="Close", command=self.root.destroy, bg="#1f2937", fg="#e2e8f0", font=("JetBrains Mono", 10), relief="flat", padx=14, pady=8)
        close_btn.pack(side="right", padx=(0, 10))

    def save_changes(self):
        entries: Dict[str, str] = {}
        for action_name, fields in self.entry_vars.items():
            new_action = fields["action"].get().strip()
            new_shortcut = fields["shortcut"].get().strip()
            if not new_action or not new_shortcut:
                continue
            entries[new_action] = new_shortcut

        modifier = self.modifier_var.get().strip() or pick_primary_modifier(entries)
        save_hud_config(
            self.hud_config_path,
            dict(sorted(entries.items(), key=lambda item: item[0].lower())),
            {"modifier": modifier},
        )

        if self.hud_window is not None:
            self.hud_window.reload_bindings()

        self.root.destroy()


class HUDWindow:
    def __init__(self, bindings: Dict[str, str], config_path: str | Path | None = None, hud_config_path: str | Path | None = None):
        self.root = tk.Tk() if tk is not None else None
        if self.root is None:
            raise RuntimeError("tkinter is required to display the i3 HUD")

        self.config_path = resolve_config_path(config_path) if config_path is not None else Path("~/.config/i3").expanduser()
        self.hud_config_path = Path(hud_config_path).expanduser() if hud_config_path is not None else Path("./i3_hud_config.json").expanduser()
        self.all_bindings = dict(sorted(bindings.items(), key=lambda item: item[0].lower()))
        self.visible_bindings = self.all_bindings
        self.root.title("i3 HUD")
        self.root.configure(bg="#0b1020")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.96)

        self.w = 780
        self.h = 520
        self.root.geometry(f"{self.w}x{self.h}+100+80")

        self.container = tk.Frame(self.root, bg="#0b1020", padx=18, pady=18)
        self.container.pack(fill="both", expand=True)

        title = tk.Label(
            self.container,
            text="i3 key bindings",
            bg="#0b1020",
            fg="#dbeafe",
            font=("JetBrains Mono", 18, "bold"),
            anchor="w",
        )
        title.pack(fill="x", pady=(0, 12))

        controls = tk.Frame(self.container, bg="#0b1020")
        controls.pack(fill="x", pady=(0, 12))

        close_button = tk.Button(
            controls,
            text="Close",
            bg="#475569",
            fg="#f8fafc",
            font=("JetBrains Mono", 10, "bold"),
            relief="flat",
            command=self.root.destroy,
        )
        close_button.pack(side="right")

        edit_button = tk.Button(
            controls,
            text="Edit config",
            bg="#1d4ed8",
            fg="#eff6ff",
            font=("JetBrains Mono", 10, "bold"),
            relief="flat",
            command=lambda: ConfigEditorWindow(self.config_path, self.hud_config_path, self.root, hud_window=self),
        )
        edit_button.pack(side="right", padx=(0, 10))

        self.modifier_name = load_hud_settings(self.hud_config_path).get("modifier") or pick_primary_modifier(self.all_bindings)
        modifier_frame = tk.Frame(self.container, bg="#0b1020")
        modifier_frame.pack(fill="x", pady=(0, 8))

        self.modifier_label = tk.Label(
            modifier_frame,
            text=f"Modifier: {self.modifier_name}",
            bg="#111827",
            fg="#7dd3fc",
            font=("JetBrains Mono", 12, "bold"),
            anchor="w",
            padx=12,
            pady=8,
        )
        self.modifier_label.pack(fill="x")

        self.search_var = tk.StringVar()
        search_label = tk.Label(
            self.container,
            text="Search",
            bg="#0b1020",
            fg="#cbd5e1",
            font=("JetBrains Mono", 10, "bold"),
            anchor="w",
        )
        search_label.pack(fill="x", pady=(0, 6))

        self.search_entry = tk.Entry(
            self.container,
            textvariable=self.search_var,
            bg="#121a2d",
            fg="#e2e8f0",
            insertbackground="#7dd3fc",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#334155",
            highlightcolor="#7dd3fc",
            state="normal",
            font=("JetBrains Mono", 10),
        )
        self.search_entry.pack(fill="x", pady=(0, 10))
        self.search_entry.bind("<KeyRelease>", self._schedule_search)
        self.search_entry.bind("<Button-1>", lambda event: self._focus_search())
        self.search_entry.bind("<FocusIn>", lambda event: None)

        self.scrollbar = tk.Scrollbar(self.container, orient="vertical", troughcolor="#0b1020", bg="#1e293b")
        self.canvas = tk.Canvas(self.container, bg="#0b1020", highlightthickness=0, yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.canvas.yview)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.listbox = tk.Frame(self.canvas, bg="#0b1020")
        self.canvas.create_window((0, 0), window=self.listbox, anchor="nw", width=self.w - 72)
        self.listbox.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.render_rows(self.all_bindings)
        self.root.bind("<Escape>", lambda event: self.root.destroy())
        self.root.bind("<Button-1>", lambda event: self._focus_search())
        self.root.after(100, self._focus_search)
        self.search_update_after = None

    def _focus_search(self):
        try:
            self.root.focus_set()
            self.search_entry.focus_set()
            self.search_entry.icursor(len(self.search_var.get()))
        except Exception:
            pass

    def _schedule_search(self, event=None):
        if self.search_update_after is not None:
            self.root.after_cancel(self.search_update_after)
        self.search_update_after = self.root.after(350, self._apply_search)

    def reload_bindings(self):
        self.all_bindings = collect_bindings(self.config_path, self.hud_config_path)
        self.search_var.set("")
        self.modifier_name = load_hud_settings(self.hud_config_path).get("modifier") or pick_primary_modifier(self.all_bindings)
        if hasattr(self, "modifier_label"):
            self.modifier_label.config(text=f"Modifier: {self.modifier_name}")
        self.render_rows(self.all_bindings)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _apply_search(self, event=None):
        query = self.search_var.get().strip().lower()
        if not query:
            self.render_rows(self.all_bindings)
            return

        filtered = {
            action: shortcut
            for action, shortcut in self.all_bindings.items()
            if query in action.lower() or query in shortcut.lower()
        }
        self.render_rows(filtered)

    def render_rows(self, bindings: Dict[str, str]):
        for widget in self.listbox.winfo_children():
            widget.destroy()

        if not bindings:
            empty = tk.Label(
                self.listbox,
                text="No matching shortcuts",
                bg="#0b1020",
                fg="#94a3b8",
                font=("JetBrains Mono", 11),
                pady=20,
            )
            empty.pack(fill="x")
            self.canvas.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            return

        for idx, (action, shortcut) in enumerate(dict(sorted(bindings.items(), key=lambda item: item[0].lower())).items()):
            row = tk.Frame(
                self.listbox,
                bg="#111827" if idx % 2 == 0 else "#0f172a",
                bd=0,
                highlightthickness=0,
                pady=10,
                padx=14,
            )
            row.pack(fill="x", pady=4)

            action_label = tk.Label(
                row,
                text=action,
                fg="#e2e8f0",
                bg=row["bg"],
                font=("JetBrains Mono", 11),
                anchor="w",
                justify="left",
            )
            action_label.pack(side="left", fill="x", expand=True)

            binding_label = tk.Label(
                row,
                text=prettify_shortcut(shortcut),
                fg="#7dd3fc",
                bg="#0f172a",
                font=("JetBrains Mono", 11, "bold"),
                bd=0,
                padx=12,
                pady=6,
                relief="flat",
            )
            binding_label.pack(side="right")

        self.canvas.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def run(self) -> None:
        self.root.mainloop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Display i3 bindsyms in a HUD overlay.")    
    parser.add_argument("--config", type=Path, default=Path("~/.config/i3-hud/i3_hud_config.json").expanduser(), help="Path to the i3 config file or the i3 config directory.")
    parser.add_argument("--hud-config", type=Path, default=Path("./i3_hud_config.json").expanduser(), help="JSON file containing action-to-keybinding overrides.")
    parser.add_argument("--dump", action="store_true", help="Print parsed bindings as JSON instead of opening the HUD window.")
    parser.add_argument("--edit-config", action="store_true", help="Open the on-screen editor for the HUD config instead of the main HUD overlay.")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.edit_config:
        try:
            editor = ConfigEditorWindow(args.config, args.hud_config)
            editor.root.mainloop()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0

    bindings = collect_bindings(args.config, args.hud_config)
    if not bindings:
        if args.dump:
            print("{}")
            return 0
        raise SystemExit("No i3 bindings were found in the config file.")

    if args.dump:
        print(json.dumps(bindings, indent=2, sort_keys=True))
        return 0

    try:
        HUDWindow(bindings, config_path=args.config, hud_config_path=args.hud_config).run()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
