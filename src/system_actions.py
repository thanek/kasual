"""Wspólne definicje akcji systemowych używane przez Desktop i HomeOverlay."""

# Mapowanie: typ akcji → (pytanie do potwierdzenia, polecenie systemowe lub None)
# None jako polecenie oznacza akcję "hide_desktop" (obsługiwaną przez wywołującego).
SYSTEM_ACTION_SPECS: dict[str, tuple[str, list[str] | None]] = {
    "sleep":        ("Czy na pewno chcesz uśpić system?",          ["systemctl", "suspend"]),
    "restart":      ("Czy na pewno chcesz zrestartować komputer?",  ["systemctl", "reboot"]),
    "shutdown":     ("Czy na pewno chcesz wyłączyć komputer?",      ["systemctl", "poweroff"]),
    "hide_desktop": ("Czy na pewno chcesz zminimalizować Pulpit?",  None),
}
