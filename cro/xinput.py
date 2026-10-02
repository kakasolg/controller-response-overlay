"""XInput, read-only.

The only XInput function this package binds is XInputGetState: no vibration, no enable/disable, and no device is
created, opened exclusively or hidden. Values come back raw — no deadzone, no rounding, no rescaling.

XInput cannot tell a physical pad from a virtual one (virtual-pad drivers, Steam Input and remappers all look like an
Xbox 360 pad), so nothing here claims a source. The overlay shows "slot n · source unknown".
"""
from __future__ import annotations

import ctypes
import sys
from typing import Callable, NamedTuple, Optional

ERROR_SUCCESS = 0
MAX_SLOTS = 4
AXIS_MAX = 32767
TRIGGER_MAX = 255
LEFT_DEADZONE = 7849          # XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE — drawn for reference only, never applied
RIGHT_DEADZONE = 8689         # XINPUT_GAMEPAD_RIGHT_THUMB_DEADZONE

BUTTONS = {"up": 0x0001, "down": 0x0002, "left": 0x0004, "right": 0x0008, "start": 0x0010, "back": 0x0020,
           "ls": 0x0040, "rs": 0x0080, "lb": 0x0100, "rb": 0x0200, "a": 0x1000, "b": 0x2000, "x": 0x4000, "y": 0x8000}


class _GAMEPAD(ctypes.Structure):
    _fields_ = [("wButtons", ctypes.c_ushort), ("bLeftTrigger", ctypes.c_ubyte), ("bRightTrigger", ctypes.c_ubyte),
                ("sThumbLX", ctypes.c_short), ("sThumbLY", ctypes.c_short),
                ("sThumbRX", ctypes.c_short), ("sThumbRY", ctypes.c_short)]


class _STATE(ctypes.Structure):
    _fields_ = [("dwPacketNumber", ctypes.c_uint32), ("Gamepad", _GAMEPAD)]


class PadState(NamedTuple):
    pkt: int          # dwPacketNumber — advances when the pad's state changes; not a hardware report counter
    btn: int
    lt: int
    rt: int
    lx: int
    ly: int
    rx: int
    ry: int


GetState = Callable[[int], Optional[PadState]]     # slot → state, or None when nothing is connected there


def load() -> Optional[GetState]:
    """A read function for this machine's XInput, or None (not Windows / no XInput DLL)."""
    if sys.platform != "win32":
        return None
    fn = None
    for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            fn = getattr(ctypes.windll, name).XInputGetState
            break
        except (AttributeError, OSError):
            continue
    if fn is None:
        return None
    fn.argtypes = [ctypes.c_uint32, ctypes.POINTER(_STATE)]
    fn.restype = ctypes.c_uint32

    def get_state(slot: int) -> Optional[PadState]:
        st = _STATE()
        if fn(slot, ctypes.byref(st)) != ERROR_SUCCESS:
            return None
        g = st.Gamepad
        return PadState(st.dwPacketNumber, g.wButtons, g.bLeftTrigger, g.bRightTrigger,
                        g.sThumbLX, g.sThumbLY, g.sThumbRX, g.sThumbRY)

    return get_state
