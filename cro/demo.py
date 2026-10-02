"""A fake pad for --demo: develop or preview the page with no controller (or on any OS).

Slot 0 only. Left stick circles, right stick sweeps, triggers ramp, buttons take turns, and every CYCLE_S the pad
"unplugs" for UNPLUG_S so the gray lamp can be seen too.
"""
from __future__ import annotations

import math
import time
from typing import Callable, Optional

from .xinput import BUTTONS, GetState, PadState

CYCLE_S = 30.0
UNPLUG_S = 3.0
BUTTON_ORDER = ("a", "b", "x", "y", "lb", "rb", "up", "right", "down", "left", "back", "start", "ls", "rs")
BUTTON_HOLD_S = 0.4


def pattern(t: float) -> Optional[tuple]:
    """(btn, lt, rt, lx, ly, rx, ry) at time t, or None while unplugged."""
    if t % CYCLE_S >= CYCLE_S - UNPLUG_S:
        return None
    name = BUTTON_ORDER[int(t / BUTTON_HOLD_S) % len(BUTTON_ORDER)]
    btn = BUTTONS[name] if (t % BUTTON_HOLD_S) < BUTTON_HOLD_S * 0.7 else 0
    lt = int(255 * ((t / 3.0) % 1.0))
    rt = int(255 * max(0.0, math.sin(t * 1.3)))
    lx, ly = int(28000 * math.cos(t)), int(28000 * math.sin(t))
    rx, ry = int(32767 * math.sin(t / 2.5)), int(12000 * math.sin(t * 0.7))
    return btn, lt, rt, lx, ly, rx, ry


def source(clock: Callable[[], float] = time.monotonic) -> GetState:
    t0 = clock()
    last: list = [None, 0]                       # [last values, packet number]

    def get_state(slot: int) -> Optional[PadState]:
        if slot != 0:
            return None
        v = pattern(clock() - t0)
        if v is None:
            return None
        if v != last[0]:
            last[0] = v
            last[1] += 1
        return PadState(last[1], *v)

    return get_state
