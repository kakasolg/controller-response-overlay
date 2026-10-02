import threading

from cro import demo, hotkey


def test_demo_unplugs_once_per_cycle():
    assert demo.pattern(1.0) is not None
    assert demo.pattern(demo.CYCLE_S - demo.UNPLUG_S / 2) is None
    assert demo.pattern(demo.CYCLE_S + 1.0) is not None


def test_demo_values_fit_xinput_ranges():
    for i in range(600):
        v = demo.pattern(i * 0.05)
        if v is None:
            continue
        btn, lt, rt, lx, ly, rx, ry = v
        assert 0 <= lt <= 255 and 0 <= rt <= 255
        assert all(-32768 <= a <= 32767 for a in (lx, ly, rx, ry))


def test_demo_only_slot_zero_and_packet_advances_on_change():
    t = [0.0]
    get = demo.source(clock=lambda: t[0])
    assert get(1) is None
    a = get(0)
    t[0] = 0.5
    b = get(0)
    assert b.pkt == a.pkt + 1


def test_hotkey_fires_once_per_press():
    stop = threading.Event()
    presses = []
    # combo down for 3 polls, up, down again → 2 presses
    script = iter([True] * 3 + [False] + [True] * 2)

    def step():
        try:
            return next(script)
        except StopIteration:
            stop.set()
            return False

    state = {"down": False, "n": 0}

    def is_down(vk):
        if vk == hotkey.COMBO[0]:
            state["down"] = step()
        return state["down"]

    hotkey.watch(lambda: presses.append(1), stop, poll_s=0, is_down=is_down)
    assert len(presses) == 2
