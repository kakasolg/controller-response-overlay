"""Polls the XInput slots and keeps the latest state of each. Holds nothing but what it read.

Connected slots are read every tick; empty slots only every RESCAN_S — Microsoft's XInputGetState notes advise against
polling an empty slot every frame. A failed read on a connected slot drops it at once (its lamp goes gray).

Time points: `seen` is when *this process* read the value (time.monotonic). It is not when the controller sent it and
not when the game read it — neither is observable here. Polling also misses states that come and go between two reads;
`missed` counts them from dwPacketNumber gaps (debug only, and only as far as the driver advances that number per change).
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from .xinput import MAX_SLOTS, GetState, PadState

# ── 임시값 (Phase 1, 근거 등급: 임시 제안값 — 정책 상수 아님) ──────────────
POLL_HZ = 120.0       # 연결된 slot 읽기 주기
RESCAN_S = 2.0        # 빈 slot 다시 확인 주기
STALE_S = 1.0         # 이만큼 성공한 읽기가 없으면 gray (읽기 스레드가 멈춘 경우 등)


class Reader:
    def __init__(self, get_state: GetState, clock: Callable[[], float] = time.monotonic,
                 rescan_s: float = RESCAN_S, stale_s: float = STALE_S):
        self._get = get_state
        self._clock = clock
        self._rescan_s = rescan_s
        self._stale_s = stale_s
        self._lock = threading.Lock()
        self._pads: dict[int, dict] = {}            # slot → {"state": PadState, "seen": t, "missed": n}
        self._next_scan = [0.0] * MAX_SLOTS

    def _read(self, slot: int) -> Optional[PadState]:
        try:
            return self._get(slot)
        except Exception:
            return None

    def tick(self) -> bool:
        """One pass over the slots. → True if anything visible changed (a value, a connect, a disconnect)."""
        now = self._clock()
        changed = False
        for slot in range(MAX_SLOTS):
            with self._lock:
                connected = slot in self._pads
            if not connected and now < self._next_scan[slot]:
                continue
            st = self._read(slot)
            with self._lock:
                if st is None:
                    if connected:
                        del self._pads[slot]
                        changed = True
                    self._next_scan[slot] = now + self._rescan_s
                    continue
                prev = self._pads.get(slot)
                if prev is None:
                    self._pads[slot] = {"state": st, "seen": now, "missed": 0}
                    changed = True
                    continue
                prev["seen"] = now
                if st != prev["state"]:
                    gap = (st.pkt - prev["state"].pkt) % 2 ** 32
                    if gap > 1:
                        prev["missed"] += gap - 1
                    prev["state"] = st
                    changed = True
        return changed

    def snapshot(self) -> dict[str, dict]:
        """{slot: fields} for connected slots, JSON-ready. status: green = data arriving, gray = stale."""
        now = self._clock()
        with self._lock:
            out = {}
            for slot, p in sorted(self._pads.items()):
                s = p["state"]
                out[str(slot)] = {"status": "green" if now - p["seen"] <= self._stale_s else "gray",
                                  "btn": s.btn, "lt": s.lt, "rt": s.rt, "lx": s.lx, "ly": s.ly, "rx": s.rx, "ry": s.ry,
                                  "pkt": s.pkt, "missed": p["missed"]}
            return out

    def run(self, on_change: Callable[[], None], stop: threading.Event, hz: float = POLL_HZ) -> None:
        """Poll until stop is set. Pacing uses time.sleep (high-resolution on Windows since Python 3.11)."""
        period = 1.0 / hz
        nxt = time.monotonic()
        while not stop.is_set():
            try:
                if self.tick():
                    on_change()
            except Exception:
                pass                                    # a bad pass must not end the loop; stale data turns gray anyway
            nxt += period
            delay = nxt - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:
                nxt = time.monotonic()
