"""Atajos de teclado globales con RegisterHotKey (no requiere permisos de admin)."""

import ctypes
import threading
from ctypes import wintypes

from .winapi import kernel32, user32

MODIFIERS = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "win": 0x8}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

NAMED_KEYS = {
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B,
    "printscreen": 0x2C, "prtsc": 0x2C, "pause": 0x13,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
}
NAMED_KEYS.update({f"f{i}": 0x6F + i for i in range(1, 25)})


def parse(combo: str) -> tuple[int, int]:
    """'ctrl+shift+1' -> (modificadores, código de tecla virtual)."""
    mods, vk = 0, None
    for part in combo.lower().replace(" ", "").split("+"):
        if part in MODIFIERS:
            mods |= MODIFIERS[part]
        elif part in NAMED_KEYS:
            vk = NAMED_KEYS[part]
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
        else:
            raise ValueError(f"Tecla no reconocida: {part!r} en {combo!r}")
    if vk is None:
        raise ValueError(f"Falta la tecla principal en {combo!r}")
    return mods, vk


class HotkeyListener(threading.Thread):
    """Registra los atajos y llama a su callback (desde este hilo)."""

    def __init__(self, bindings: dict[str, callable]):
        super().__init__(daemon=True, name="hotkeys")
        self.bindings = bindings
        self.failed: list[str] = []
        self._ready = threading.Event()
        self._thread_id = None

    def start(self):
        super().start()
        self._ready.wait(2)
        return self.failed

    def run(self):
        self._thread_id = kernel32.GetCurrentThreadId()
        callbacks = {}
        for i, (combo, cb) in enumerate(self.bindings.items(), start=1):
            try:
                mods, vk = parse(combo)
            except ValueError:
                self.failed.append(combo)
                continue
            if user32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, vk):
                callbacks[i] = cb
            else:
                self.failed.append(combo)  # probablemente ya lo usa otra app
        self._ready.set()

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam in callbacks:
                try:
                    callbacks[msg.wParam]()
                except Exception:  # un fallo no debe matar el listener
                    pass
        for i in callbacks:
            user32.UnregisterHotKey(None, i)

    def stop(self):
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
