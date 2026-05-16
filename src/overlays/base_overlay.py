"""Base class for fullscreen overlays managed by GamepadWatcher."""

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

from input.gamepad_watcher import GamepadWatcher


class BaseOverlay(QWidget):
    """
    Base class for fullscreen overlays (ConfirmDialog, VolumeOverlay, etc.).

    Manages:
      - window flags (FramelessWindowHint, WindowStaysOnTopHint, Tool)
      - gamepad lifetime cycle (push/pop_handler)
      - pause() / resume() methods used by Desktop
      - notifies Desktop (parent) about being open so it can hide its chrome
        (topbar + tile bar) for the duration of the overlay

    Subclass should:
      1. Call super().__init__(gamepad, self._handle_pad, parent)
      2. Build the UI
      3. At the end of __init__ call self._show() (optionally play a sound before that)
      4. Call self._notify_closed() inside its close path so the Desktop
         chrome is restored.
    """

    def __init__(
        self,
        gamepad: GamepadWatcher,
        handler: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._gamepad           = gamepad
        self._handler           = handler
        self._closed            = False
        self._is_child          = parent is not None
        self._chrome_hidden     = False

        if self._is_child:
            # Render inside the parent's Wayland surface — no new xdg_toplevel.
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        else:
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setWindowTitle("Kasual Overlay")

        self.setStyleSheet("background-color: rgba(0, 0, 0, 150);")

    def _show(self) -> None:
        """Registers the gamepad handler and displays the overlay."""
        self._gamepad.push_handler(self._handler)
        if self._is_child:
            self._notify_opened()
            self.setGeometry(self.parent().rect())
            self.show()
            self.raise_()
        else:
            self.showFullScreen()
        self.activateWindow()
        self.setFocus()

    def pause(self) -> None:
        """Temporarily hides the overlay (e.g. when Desktop is being minimized)."""
        if not self._closed:
            self._gamepad.pop_handler(self._handler)
            self.hide()

    def resume(self) -> None:
        """Restores the overlay after a pause."""
        if not self._closed:
            self._show()

    def _notify_opened(self) -> None:
        """Tell the Desktop parent to hide its chrome while we're shown."""
        if self._chrome_hidden:
            return
        parent = self.parent()
        if hasattr(parent, "enter_overlay_mode"):
            parent.enter_overlay_mode()
            self._chrome_hidden = True

    def _notify_closed(self) -> None:
        """Tell the Desktop parent it may show its chrome again."""
        if not self._chrome_hidden:
            return
        parent = self.parent()
        if hasattr(parent, "exit_overlay_mode"):
            parent.exit_overlay_mode()
        self._chrome_hidden = False
