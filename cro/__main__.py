"""Controller Response Overlay — Phase 1: read-only controller viewer.

  python -m cro                 read XInput, serve http://127.0.0.1:47820/
  python -m cro --demo          fake pad (no controller needed, any OS)
  python -m cro --port 47821    another port

Open the URL in a browser, or add it as an OBS Browser Source. Ctrl+Shift+F10 hides / shows the overlay.
"""
from __future__ import annotations

import argparse
import sys
import threading

from . import demo, hotkey, xinput
from .reader import POLL_HZ, Reader
from .server import DEFAULT_PORT, HOST, Hub, make_server

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _lower_priority() -> None:
    """Below-normal priority for this process only, so the overlay yields to the game under load."""
    if sys.platform != "win32":
        return
    import ctypes
    k = ctypes.windll.kernel32
    k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)          # BELOW_NORMAL_PRIORITY_CLASS


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m cro", description="Read-only controller overlay (Phase 1).")
    ap.add_argument("--demo", action="store_true", help="fake pad instead of XInput")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--hz", type=float, default=POLL_HZ, help=f"poll rate for connected slots (default {POLL_HZ:g})")
    ap.add_argument("--no-hotkey", action="store_true", help=f"don't watch {hotkey.COMBO_NAME}")
    a = ap.parse_args(argv)

    if a.demo:
        get_state, source = demo.source(), "demo"
    else:
        get_state = xinput.load()
        source = "xinput" if get_state is not None else "none"
    reader = Reader(get_state) if get_state is not None else None
    hub = Hub(reader, source)
    stop = threading.Event()

    try:
        srv = make_server(hub, a.port)
    except OSError as e:
        print(f"cannot listen on {HOST}:{a.port} — {e}")
        return 2

    if reader is not None:
        threading.Thread(target=reader.run, args=(hub.bump, stop, a.hz), daemon=True, name="cro-reader").start()
    if not a.no_hotkey and hotkey.available():
        threading.Thread(target=hotkey.watch, args=(hub.toggle_visible, stop), daemon=True, name="cro-hotkey").start()
    _lower_priority()

    url = f"http://{HOST}:{a.port}/"
    print(f"source: {source}" + ("  (no XInput here — the lamp stays gray; try --demo)" if source == "none" else ""))
    print(f"overlay:  {url}")
    print(f"compact:  {url}?layout=compact")
    print(f"streamer: {url}?layout=streamer   (OBS Browser Source)")
    if not a.no_hotkey and hotkey.available():
        print(f"hide/show: {hotkey.COMBO_NAME}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        hub.close()
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
