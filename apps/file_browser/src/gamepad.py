"""Gamepad input for File Browser — context-aware: browse mode and media mode."""

import threading
import time

from evdev import InputDevice, UInput, ecodes, list_devices
from evdev import ecodes as e


_ui = UInput()
_TRIGGER_THRESHOLD = 200
_DEAD_ZONE = 0.15
_REPEAT_DELAY = 0.35
_REPEAT_INTERVAL = 0.08


def _press(key: int) -> None:
    _ui.write(e.EV_KEY, key, 1)
    _ui.write(e.EV_KEY, key, 0)
    _ui.syn()


def find_pad(names: list[str], timeout: float = 10.0) -> InputDevice:
    """Waits for gamepad with given name appearance, max timeout seconds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for path in list_devices():
            try:
                d = InputDevice(path)
                if d.name in names:
                    return d
                d.close()
            except Exception:
                pass
        time.sleep(0.2)
    raise RuntimeError(f"Pad not found among: {names}")


def _normalize(value: int, info) -> float:
    if info is None:
        return 0.0
    center = (info.min + info.max) / 2
    half = (info.max - info.min) / 2
    if half == 0:
        return 0.0
    raw = (value - center) / half
    if abs(raw) < _DEAD_ZONE:
        return 0.0
    sign = 1.0 if raw > 0 else -1.0
    return sign * (abs(raw) - _DEAD_ZONE) / (1.0 - _DEAD_ZONE)


class PadListener(threading.Thread):
    """
    Context-aware gamepad translator.

    Browse mode:
        A (BTN_SOUTH)  → Enter
        B (BTN_EAST)   → Escape
        Y (BTN_NORTH)  → H
        X (BTN_WEST)   → S   (sort menu)
        LB (BTN_TL)    → Up   (prev item)
        RB (BTN_TR)    → Down (next item)
        LT (ABS_Z)     → Up   (prev item)
        RT (ABS_RZ)    → Down (next item)
        D-pad          → arrows

    Media mode:
        B  (BTN_EAST)  → Escape    (exit / reset zoom)
        LB (BTN_TL)    → Page Up   (prev file)
        RB (BTN_TR)    → Page Down (next file)
        X  (BTN_WEST)  → R         (rotate CW, image mode)
        LT (ABS_Z)     → Minus     (zoom out, image mode)
        RT (ABS_RZ)    → Equal     (zoom in, image mode)
        Right stick    → pan       (.stick property, image mode)
        Left stick Y   → zoom      (.left_y property, image mode)
    """

    def __init__(self, gamepad: InputDevice, window=None):
        super().__init__(daemon=True)
        self._gamepad = gamepad
        self._window = window
        self._mode = 'browse'
        self._trigger_active = {e.ABS_Z: False, e.ABS_RZ: False}
        self._repeat_stop: threading.Event | None = None
        self._stick_x = 0.0
        self._stick_y = 0.0
        self._left_y = 0.0
        try:
            self._rx_info = gamepad.absinfo(e.ABS_RX)
        except Exception:
            self._rx_info = None
        try:
            self._ry_info = gamepad.absinfo(e.ABS_RY)
        except Exception:
            self._ry_info = None
        try:
            self._ly_info = gamepad.absinfo(e.ABS_Y)
        except Exception:
            self._ly_info = None

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._stick_x = 0.0
        self._stick_y = 0.0
        self._left_y = 0.0
        self._trigger_active[e.ABS_Z] = False
        self._trigger_active[e.ABS_RZ] = False
        self._stop_repeat()

    def _start_repeat(self, key: int) -> None:
        self._stop_repeat()
        stop = threading.Event()
        self._repeat_stop = stop
        def _loop():
            if stop.wait(timeout=_REPEAT_DELAY):
                return
            while not stop.is_set():
                _press(key)
                stop.wait(timeout=_REPEAT_INTERVAL)
        threading.Thread(target=_loop, daemon=True).start()

    def _stop_repeat(self) -> None:
        if self._repeat_stop is not None:
            self._repeat_stop.set()
            self._repeat_stop = None

    @property
    def stick(self) -> tuple[float, float]:
        return (self._stick_x, self._stick_y)

    @property
    def left_y(self) -> float:
        return self._left_y

    def run(self) -> None:
        for ev in self._gamepad.read_loop():
            if self._window is not None and not self._window.isActiveWindow():
                continue

            if self._mode == 'browse':
                if ev.type == ecodes.EV_KEY and ev.value == 1:
                    match ev.code:
                        case ecodes.BTN_SOUTH: _press(e.KEY_ENTER)
                        case ecodes.BTN_EAST:  _press(e.KEY_ESC)
                        case ecodes.BTN_NORTH: _press(e.KEY_H)
                        case ecodes.BTN_WEST:  _press(e.KEY_S)
                        case ecodes.BTN_TL:    _press(e.KEY_UP)
                        case ecodes.BTN_TR:    _press(e.KEY_DOWN)
                elif ev.type == ecodes.EV_ABS:
                    match ev.code:
                        case ecodes.ABS_HAT0X:
                            if ev.value == -1:
                                _press(e.KEY_LEFT);  self._start_repeat(e.KEY_LEFT)
                            elif ev.value == 1:
                                _press(e.KEY_RIGHT); self._start_repeat(e.KEY_RIGHT)
                            else:
                                self._stop_repeat()
                        case ecodes.ABS_HAT0Y:
                            if ev.value == -1:
                                _press(e.KEY_UP);   self._start_repeat(e.KEY_UP)
                            elif ev.value == 1:
                                _press(e.KEY_DOWN); self._start_repeat(e.KEY_DOWN)
                            else:
                                self._stop_repeat()
                        case e.ABS_Z:
                            active = ev.value > _TRIGGER_THRESHOLD
                            if active and not self._trigger_active[e.ABS_Z]:
                                _press(e.KEY_UP)
                            self._trigger_active[e.ABS_Z] = active
                        case e.ABS_RZ:
                            active = ev.value > _TRIGGER_THRESHOLD
                            if active and not self._trigger_active[e.ABS_RZ]:
                                _press(e.KEY_DOWN)
                            self._trigger_active[e.ABS_RZ] = active

            else:  # media mode
                if ev.type == ecodes.EV_KEY and ev.value == 1:
                    match ev.code:
                        case ecodes.BTN_SOUTH: _press(e.KEY_ENTER)
                        case ecodes.BTN_EAST:  _press(e.KEY_ESC)
                        case ecodes.BTN_NORTH: _press(e.KEY_H)
                        case ecodes.BTN_WEST:  _press(e.KEY_R)
                        case ecodes.BTN_TL:    _press(e.KEY_PAGEUP)
                        case ecodes.BTN_TR:    _press(e.KEY_PAGEDOWN)
                elif ev.type == ecodes.EV_ABS:
                    match ev.code:
                        case ecodes.ABS_HAT0X:
                            if ev.value < 0:
                                _press(e.KEY_LEFT);  self._start_repeat(e.KEY_LEFT)
                            elif ev.value > 0:
                                _press(e.KEY_RIGHT); self._start_repeat(e.KEY_RIGHT)
                            else:
                                self._stop_repeat()
                        case e.ABS_RX:
                            self._stick_x = _normalize(ev.value, self._rx_info)
                        case e.ABS_RY:
                            self._stick_y = _normalize(ev.value, self._ry_info)
                        case e.ABS_Y:
                            self._left_y = _normalize(ev.value, self._ly_info)
                        case e.ABS_Z:
                            active = ev.value > _TRIGGER_THRESHOLD
                            if active and not self._trigger_active[e.ABS_Z]:
                                _press(e.KEY_MINUS)
                            self._trigger_active[e.ABS_Z] = active
                        case e.ABS_RZ:
                            active = ev.value > _TRIGGER_THRESHOLD
                            if active and not self._trigger_active[e.ABS_RZ]:
                                _press(e.KEY_EQUAL)
                            self._trigger_active[e.ABS_RZ] = active
