from cro.reader import Reader
from cro.xinput import PadState


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class FakePads:
    """slot → PadState or None; counts reads per slot."""

    def __init__(self):
        self.pads = {}
        self.reads = {i: 0 for i in range(4)}

    def __call__(self, slot):
        self.reads[slot] += 1
        return self.pads.get(slot)


def pad(pkt=1, btn=0, lt=0, rt=0, lx=0, ly=0, rx=0, ry=0):
    return PadState(pkt, btn, lt, rt, lx, ly, rx, ry)


def make(rescan=2.0, stale=1.0):
    clock, pads = Clock(), FakePads()
    return Reader(pads, clock=clock, rescan_s=rescan, stale_s=stale), clock, pads


def test_connect_shows_raw_values():
    r, clock, pads = make()
    pads.pads[0] = pad(lx=100, ly=-37, lt=3)          # inside the deadzone — must stay as read
    assert r.tick() is True
    s = r.snapshot()["0"]
    assert (s["status"], s["lx"], s["ly"], s["lt"]) == ("green", 100, -37, 3)


def test_unchanged_state_is_not_a_change():
    r, clock, pads = make()
    pads.pads[0] = pad()
    r.tick()
    clock.t += 0.01
    assert r.tick() is False


def test_empty_slots_are_rescanned_only_every_rescan_s():
    r, clock, pads = make(rescan=2.0)
    pads.pads[0] = pad()
    for _ in range(10):
        r.tick()
        clock.t += 0.1                                 # 1 s in total
    assert pads.reads[0] == 10
    assert pads.reads[1] == 1
    clock.t += 1.1
    r.tick()
    assert pads.reads[1] == 2


def test_disconnect_drops_the_slot_at_once():
    r, clock, pads = make()
    pads.pads[0] = pad()
    r.tick()
    del pads.pads[0]
    clock.t += 0.01
    assert r.tick() is True
    assert r.snapshot() == {}


def test_reconnect_is_picked_up_on_the_next_rescan():
    r, clock, pads = make(rescan=2.0)
    r.tick()
    pads.pads[2] = pad()
    clock.t += 0.5
    r.tick()
    assert r.snapshot() == {}
    clock.t += 1.6
    assert r.tick() is True
    assert "2" in r.snapshot()


def test_stale_reads_turn_gray():
    r, clock, pads = make(stale=1.0)
    pads.pads[0] = pad()
    r.tick()
    clock.t += 1.5                                     # no tick — e.g. the read thread stalled
    assert r.snapshot()["0"]["status"] == "gray"


def test_read_error_counts_as_not_connected():
    r, clock, pads = make()
    pads.pads[0] = pad()
    r.tick()

    def broken(slot):
        raise OSError("driver error")

    r._get = broken
    clock.t += 0.01
    assert r.tick() is True
    assert r.snapshot() == {}


def test_missed_counts_packet_number_gaps():
    r, clock, pads = make()
    pads.pads[0] = pad(pkt=10)
    r.tick()
    pads.pads[0] = pad(pkt=11, btn=1)
    r.tick()
    pads.pads[0] = pad(pkt=15, btn=0)                  # 3 states came and went between two reads
    r.tick()
    assert r.snapshot()["0"]["missed"] == 3


def test_packet_number_wraps():
    r, clock, pads = make()
    pads.pads[0] = pad(pkt=2 ** 32 - 1)
    r.tick()
    pads.pads[0] = pad(pkt=1, btn=1)
    r.tick()
    assert r.snapshot()["0"]["missed"] == 1
