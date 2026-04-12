"""System action dispatch — single source of truth for all topbar/home-menu actions."""

import subprocess
from collections.abc import Callable

from PyQt6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication

# All system actions — used by Desktop (topbar) and HomeOverlay (menu).
# Each entry: type, label (translatable), icon (qtawesome), color (topbar button background).
ACTION_DEFS: list[dict] = [
    {"type": "volume", "label": QT_TRANSLATE_NOOP("Kasual", "Volume"), "icon": "fa5s.volume-up", "color": "#3b4252"},
    {"type": "sleep", "label": QT_TRANSLATE_NOOP("Kasual", "Sleep"), "icon": "fa5s.moon", "color": "#4c566a"},
    {"type": "restart", "label": QT_TRANSLATE_NOOP("Kasual", "Restart"), "icon": "fa5s.redo-alt", "color": "#5e81ac"},
    {"type": "shutdown", "label": QT_TRANSLATE_NOOP("Kasual", "Shut Down"), "icon": "fa5s.power-off",
     "color": "#bf616a"},
    {"type": "hide_desktop", "label": QT_TRANSLATE_NOOP("Kasual", "Minimize Desktop"), "icon": "fa5s.window-minimize",
     "color": "#d580ff"},
]

# Mapping: action type → (confirmation question, system command)
_CONFIRMED_ACTIONS: dict[str, tuple[str, list[str]]] = {
    "sleep": (QT_TRANSLATE_NOOP("Kasual", "Are you sure you want to sleep?"), ["systemctl", "suspend"]),
    "restart": (QT_TRANSLATE_NOOP("Kasual", "Are you sure you want to restart?"), ["systemctl", "reboot"]),
    "shutdown": (QT_TRANSLATE_NOOP("Kasual", "Are you sure you want to shut down?"), ["systemctl", "poweroff"]),
}


def execute_action(
        action_type: str,
        *,
        on_volume: Callable[[], None] | None = None,
        on_hide_desktop: Callable[[], None] | None = None,
        show_confirm: Callable[[str, Callable[[], None]], None] | None = None,
) -> None:
    """Execute a system action by type.

    Callbacks:
        on_volume       — called when action_type == "volume"
        on_hide_desktop — called when action_type == "hide_desktop"
        show_confirm    — called with (question, on_confirmed) for sleep/restart/shutdown
    """
    if action_type == "volume":
        if on_volume:
            on_volume()
        return
    if action_type == "hide_desktop":
        if on_hide_desktop:
            on_hide_desktop()
        return
    if action_type not in _CONFIRMED_ACTIONS or show_confirm is None:
        return
    question_src, cmd = _CONFIRMED_ACTIONS[action_type]
    question = QCoreApplication.translate("Kasual", question_src)
    show_confirm(question, lambda c=cmd: subprocess.Popen(c))
