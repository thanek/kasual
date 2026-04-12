"""Wspólne definicje akcji systemowych używane przez Desktop i HomeOverlay."""

from PyQt6.QtCore import QT_TRANSLATE_NOOP

# Mapowanie: typ akcji → (pytanie do potwierdzenia, polecenie systemowe lub None)
# None jako polecenie oznacza akcję "hide_desktop" (obsługiwaną przez wywołującego).
# Pytania oznaczone QT_TRANSLATE_NOOP – tłumaczenie następuje w miejscu użycia
# przez QCoreApplication.translate("Kasual", question).
SYSTEM_ACTION_SPECS: dict[str, tuple[str, list[str] | None]] = {
    "sleep":        (QT_TRANSLATE_NOOP("Kasual", "Are you sure you want to sleep?"),            ["systemctl", "suspend"]),
    "restart":      (QT_TRANSLATE_NOOP("Kasual", "Are you sure you want to restart?"),          ["systemctl", "reboot"]),
    "shutdown":     (QT_TRANSLATE_NOOP("Kasual", "Are you sure you want to shut down?"),        ["systemctl", "poweroff"]),
    "hide_desktop": (QT_TRANSLATE_NOOP("Kasual", "Are you sure you want to minimize Desktop?"), None),
}
