"""Visibility hotkey — Ctrl+Shift+F10, read by polling GetAsyncKeyState (high bit only).

Polling doesn't consume the keys (the game still receives them) and installs no hook, so a stalled overlay can't slow
anyone's keyboard. Only these three keys are ever looked at.
"""
from __future__ import annotations

import sys
import threading
from typing import Callable, Optional

VK_CONTROL, VK_SHIFT, VK_F10 = 0x11, 0x10, 0x79
COMBO = (VK_CONTROL, VK_SHIFT, VK_F10)
COMBO_NAME = "Ctrl+Shift+F10"
POLL_S = 0.05


def available() -> bool:
    return sys.platform == "win32"


def _is_down(vk: int) -> bool:
    import ctypes
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


def watch(on_press: Callable[[], None], stop: threading.Event, poll_s: float = POLL_S,
          is_down: Optional[Callable[[int], bool]] = None) -> None:
    """Call on_press once per press of the whole combo (rising edge) until stop is set."""
    is_down = is_down or _is_down
    was = False
    while not stop.is_set():
        try:
            down = all(is_down(vk) for vk in COMBO)
        except Exception:
            down = False
        if down and not was:
            on_press()
        was = down
        stop.wait(poll_s)
