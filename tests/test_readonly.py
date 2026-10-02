"""Phase 1 invariants that can be checked from the source: the package never writes to a controller, never injects
input, never hooks the keyboard, never touches another process and never changes focus."""
import re
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "cro"
SOURCES = sorted(p for p in PKG.rglob("*") if p.suffix in (".py", ".html"))

FORBIDDEN = [
    "XInputSetState", "XInputEnable",                         # vibration / enable — writes to the XInput stack
    "vgamepad", "ViGEm", "vigem",                              # virtual controllers
    "SendInput", "keybd_event", "mouse_event",                 # synthetic input
    "SetWindowsHook", "RegisterHotKey",                        # hooks / consuming hotkeys
    "SetForegroundWindow", "SetFocus", "AttachThreadInput",    # focus changes
    "OpenProcess", "ReadProcessMemory", "WriteProcessMemory", "pymem",   # other processes
    "CreateFileW", "hid_write", "HidD_Set",                    # opening devices / output reports
]


def test_sources_found():
    assert any(p.name == "xinput.py" for p in SOURCES)
    assert any(p.name == "overlay.html" for p in SOURCES)


def test_no_forbidden_calls():
    hits = [f"{p.relative_to(PKG)}: {name}" for p in SOURCES for name in FORBIDDEN
            if name in p.read_text(encoding="utf-8")]
    assert hits == []


def test_only_xinput_get_state_is_bound():
    names = set()
    for p in SOURCES:
        names |= set(re.findall(r"XInput[A-Za-z]+", p.read_text(encoding="utf-8")))
    assert names <= {"XInputGetState"}


def test_nothing_is_written_to_disk():
    pattern = re.compile(r"""open\([^)]*["'][wax]|write_text|write_bytes|\.mkdir\(""")
    hits = [str(p.relative_to(PKG)) for p in SOURCES if p.suffix == ".py" and pattern.search(p.read_text(encoding="utf-8"))]
    assert hits == []
