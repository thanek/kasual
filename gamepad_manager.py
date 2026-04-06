import logging
import threading
import time
from typing import Callable

from PyQt6.QtCore import pyqtSignal, QObject
from evdev import InputDevice, ecodes, list_devices

logger = logging.getLogger(__name__)

STICK_THRESHOLD = 10000   # zakres osi analogowej: -32768..32767
STICK_RESET     = 6000    # histereza – poniżej tej wartości oś jest "w centrum"


class GamepadManager(QObject):
    """
    Czyta eventy pada w wątku tła i przekazuje do aktywnego handlera (stos LIFO).

    Sygnały:
        _raw(str)              – wątek tła → GUI: zdarzenie nawigacyjne
        connected_changed(bool)– zmiana stanu połączenia
        menu_requested()       – przycisk Home/BTN_MODE lub F1 → pokaż menu główne
    """

    _raw               = pyqtSignal(str)
    connected_changed  = pyqtSignal(bool)
    menu_requested     = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._handlers: list[Callable[[str], None]] = []
        self._lock     = threading.Lock()
        self._device: InputDevice | None = None
        self._grabbed  = False
        self._grab_requested   = False
        self._ungrab_requested = False

        self._raw.connect(self._dispatch)
        threading.Thread(target=self._loop, daemon=True).start()

    # ── Publiczne API ──────────────────────────────────────────────────────

    def push_handler(self, handler: Callable[[str], None]) -> None:
        with self._lock:
            if handler in self._handlers:
                self._handlers.remove(handler)
            self._handlers.append(handler)

    def pop_handler(self, handler: Callable[[str], None]) -> None:
        with self._lock:
            if handler in self._handlers:
                self._handlers.remove(handler)

    def inject(self, event: str) -> None:
        """Wstrzyknij zdarzenie nawigacyjne (np. z klawiatury) do aktywnego handlera."""
        self._dispatch(event)

    def grab(self) -> None:
        with self._lock:
            self._grab_requested   = True
            self._ungrab_requested = False

    def ungrab(self) -> None:
        with self._lock:
            self._ungrab_requested = True
            self._grab_requested   = False

    # ── Wewnętrzne ─────────────────────────────────────────────────────────

    def _dispatch(self, event: str) -> None:
        with self._lock:
            handler = self._handlers[-1] if self._handlers else None
        if handler:
            handler(event)

    def _apply_grab_requests(self, device: InputDevice) -> None:
        with self._lock:
            do_grab   = self._grab_requested
            do_ungrab = self._ungrab_requested
            self._grab_requested   = False
            self._ungrab_requested = False

        if do_grab and not self._grabbed:
            try:
                device.grab()
                self._grabbed = True
                logger.info("grab() – pad ekskluzywny")
            except Exception as e:
                logger.error("grab() failed: %s", e)
        elif do_ungrab and self._grabbed:
            try:
                device.ungrab()
                self._grabbed = False
                logger.info("ungrab() – pad zwolniony")
            except Exception as e:
                logger.error("ungrab() failed: %s", e)

    def _loop(self) -> None:
        device: InputDevice | None = None
        was_connected = False
        held: set[int] = set()
        stick = {"x": None, "y": None}   # aktywny kierunek gałki

        while True:
            if device is None:
                held.clear()
                stick["x"] = stick["y"] = None
                self._grabbed = False
                for path in list_devices():
                    try:
                        d = InputDevice(path)
                        if self._is_gamepad(d):
                            device = d
                            logger.info("Podłączono: %s", device.name)
                            if not was_connected:
                                was_connected = True
                                self.connected_changed.emit(True)
                            break
                        else:
                            d.close()
                    except Exception:
                        pass

            if device:
                try:
                    for ev in device.read_loop():
                        self._apply_grab_requests(device)
                        self._translate(ev, held, stick)
                except OSError:
                    logger.info("Pad odłączony")
                    self._grabbed = False
                    device = None
                    was_connected = False
                    self.connected_changed.emit(False)
            else:
                time.sleep(1)

    def _translate(self, ev, held: set[int], stick: dict) -> None:
        if ev.type == ecodes.EV_KEY:
            if ev.value == 1:       # wciśnięcie
                held.add(ev.code)
                if ev.code == ecodes.BTN_SOUTH:
                    self._raw.emit("select")
                elif ev.code == ecodes.BTN_EAST:
                    self._raw.emit("cancel")
                elif ev.code == ecodes.BTN_WEST:
                    self._raw.emit("close")
                elif ev.code == ecodes.BTN_MODE:
                    # Home / Guide button – zawsze emituj, niezależnie od handlera
                    self.menu_requested.emit()
                elif ev.code == ecodes.BTN_TL and ecodes.BTN_MODE in held:
                    # Alternatywne combo: BTN_TL wciśnięty gdy BTN_MODE trzymany
                    self.menu_requested.emit()
            elif ev.value == 0:     # zwolnienie
                held.discard(ev.code)

        elif ev.type == ecodes.EV_ABS:
            if ev.code == ecodes.ABS_HAT0X:
                if   ev.value == -1: self._raw.emit("left")
                elif ev.value ==  1: self._raw.emit("right")
            elif ev.code == ecodes.ABS_HAT0Y:
                if   ev.value == -1: self._raw.emit("up")
                elif ev.value ==  1: self._raw.emit("down")
            # Lewa gałka analogowa
            elif ev.code == ecodes.ABS_X:
                self._handle_stick_axis(ev.value, "x", "left", "right", stick)
            elif ev.code == ecodes.ABS_Y:
                self._handle_stick_axis(ev.value, "y", "up", "down", stick)

    def _handle_stick_axis(
        self,
        value: int,
        axis: str,
        neg_event: str,
        pos_event: str,
        stick: dict,
    ) -> None:
        if value < -STICK_THRESHOLD and stick[axis] != neg_event:
            stick[axis] = neg_event
            self._raw.emit(neg_event)
        elif value > STICK_THRESHOLD and stick[axis] != pos_event:
            stick[axis] = pos_event
            self._raw.emit(pos_event)
        elif abs(value) < STICK_RESET:
            stick[axis] = None

    @staticmethod
    def _is_gamepad(device: InputDevice) -> bool:
        try:
            caps = device.capabilities()
            if ecodes.EV_KEY not in caps:
                return False
            keys = caps[ecodes.EV_KEY]
            gamepad_buttons = [
                ecodes.BTN_SOUTH, ecodes.BTN_EAST,
                ecodes.BTN_NORTH, ecodes.BTN_WEST,
                ecodes.BTN_START, ecodes.BTN_SELECT,
            ]
            has_hat = (
                ecodes.EV_ABS in caps
                and any(ax in caps[ecodes.EV_ABS]
                        for ax in [ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y])
            )
            return (
                any(b in keys for b in gamepad_buttons) or has_hat
            ) and ecodes.KEY_A not in keys
        except Exception:
            return False
