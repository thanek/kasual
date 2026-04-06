import logging
import subprocess
from typing import Callable

from PyQt6.QtWidgets import (
    QWidget, QPushButton, QVBoxLayout, QLabel, QFrame,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QKeyEvent, QPainter

import qtawesome as qta

from gamepad_manager import GamepadManager
from styles import Styles

logger = logging.getLogger(__name__)

_STATIC_ITEMS = [
    {"label": "  Uśpij system",        "icon": "fa5s.moon",      "action": "sleep"},
    {"label": "  Zrestartuj komputer",  "icon": "fa5s.redo-alt",  "action": "restart"},
    {"label": "  Zamknij system",       "icon": "fa5s.power-off", "action": "shutdown"},
    {"label": "  Anuluj",               "icon": "fa5s.times",     "action": "cancel"},
]


class HomeMenu(QWidget):
    """
    Overlay menu Home pokazywane jako dziecko Desktop (nie osobne okno).
    Wypełnia cały obszar rodzica ciemnym tłem; karta z opcjami jest wyśrodkowana.

    extra_items – lista dict z kluczami label, icon, callback; wstawiana
                  na szczycie listy (np. opcje dla działającej aplikacji).
    """

    closed = pyqtSignal()

    def __init__(
        self,
        gamepad: GamepadManager,
        parent: QWidget,
        extra_items: list[dict] | None = None,
    ):
        super().__init__(parent)
        self._gamepad = gamepad
        self._index   = 0
        self._done    = False

        # Zbuduj pełną listę pozycji: najpierw extra, potem statyczne
        self._items = list(extra_items or []) + list(_STATIC_ITEMS)
        n_extra = len(extra_items) if extra_items else 0

        # Wypełnij cały obszar rodzica
        self.resize(parent.size())
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QWidget()
        card.setFixedWidth(500)
        card.setStyleSheet("background-color: #1e2430; border-radius: 14px;")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(8)

        title = QLabel("Menu")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 28px; color: #88c0d0; font-weight: bold;"
            " background: transparent; padding-bottom: 8px;"
        )
        card_layout.addWidget(title)

        self._buttons: list[QPushButton] = []
        for i, item in enumerate(self._items):
            # Separator między sekcją extra a statyczną
            if i == n_extra and n_extra > 0:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet("color: #3b4252; background: #3b4252; margin: 4px 0;")
                sep.setFixedHeight(1)
                card_layout.addWidget(sep)

            btn = QPushButton(item["label"])
            btn.setMinimumHeight(62)
            btn.setIcon(qta.icon(item["icon"], color="white"))
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            card_layout.addWidget(btn)
            self._buttons.append(btn)

        shadow = QGraphicsDropShadowEffect(card)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 220))
        shadow.setBlurRadius(50)
        card.setGraphicsEffect(shadow)

        outer.addWidget(card)

        self._refresh_buttons()
        self._gamepad.push_handler(self._handle_pad)
        self.show()
        self.raise_()
        self.setFocus()

    # ── Tło (semi-transparentne, rysowane ręcznie) ─────────────────────────

    def paintEvent(self, _) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 170))

    # ── Handler pada ───────────────────────────────────────────────────────

    def _handle_pad(self, event: str) -> None:
        if event == "up":
            self._index = (self._index - 1) % len(self._items)
            self._refresh_buttons()
        elif event == "down":
            self._index = (self._index + 1) % len(self._items)
            self._refresh_buttons()
        elif event == "select":
            self._activate(self._index)
        elif event in ("cancel", "close"):
            self._close()

    # ── Klawiatura ─────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Up:
            self._index = (self._index - 1) % len(self._items)
            self._refresh_buttons()
        elif key == Qt.Key.Key_Down:
            self._index = (self._index + 1) % len(self._items)
            self._refresh_buttons()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._activate(self._index)
        elif key in (Qt.Key.Key_Escape, Qt.Key.Key_F1):
            self._close()

    # ── Akcje ──────────────────────────────────────────────────────────────

    def _activate(self, idx: int) -> None:
        item = self._items[idx]

        # Pozycja z callbackiem (extra_items)
        if "callback" in item:
            self._close()
            item["callback"]()
            return

        # Pozycje statyczne
        action = item["action"]
        if action == "cancel":
            self._close()
        elif action == "sleep":
            self._close()
            subprocess.Popen(["systemctl", "suspend"])
        elif action == "restart":
            self._close()
            subprocess.Popen(["systemctl", "reboot"])
        elif action == "shutdown":
            self._close()
            subprocess.Popen(["systemctl", "poweroff"])

    def _close(self) -> None:
        if self._done:
            return
        self._done = True
        self._gamepad.pop_handler(self._handle_pad)
        self.closed.emit()
        self.hide()
        self.deleteLater()

    # ── Styl ───────────────────────────────────────────────────────────────

    def _refresh_buttons(self) -> None:
        for i, btn in enumerate(self._buttons):
            btn.setStyleSheet(
                Styles.home_menu_item_selected() if i == self._index
                else Styles.home_menu_item_normal()
            )
