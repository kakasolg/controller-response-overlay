import http.client
import json
import threading

import pytest

from cro.reader import Reader
from cro.server import HOST, Hub, make_server
from cro.xinput import PadState


@pytest.fixture
def served():
    pads = {0: PadState(1, 0x1000, 0, 255, 0, 0, 0, 0)}
    reader = Reader(lambda slot: pads.get(slot))
    reader.tick()
    hub = Hub(reader, "test")
    srv = make_server(hub, port=0, page=b"<html>page</html>")
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield hub, srv.server_address[1]
    hub.close()
    srv.shutdown()
    srv.server_close()


def get(port, path, host=None):
    c = http.client.HTTPConnection(HOST, port, timeout=5)
    c.request("GET", path, headers={"Host": host or f"127.0.0.1:{port}"})
    r = c.getresponse()
    return r.status, r.read()


def test_binds_loopback_only(served):
    hub, port = served
    assert HOST == "127.0.0.1"


def test_state_is_json(served):
    hub, port = served
    status, body = get(port, "/state")
    s = json.loads(body)
    assert status == 200
    assert s["source"] == "test" and s["visible"] is True
    assert s["pads"]["0"]["btn"] == 0x1000 and s["pads"]["0"]["rt"] == 255


def test_page(served):
    hub, port = served
    assert get(port, "/?layout=compact") == (200, b"<html>page</html>")


def test_foreign_host_is_refused(served):
    hub, port = served
    assert get(port, "/state", host=f"evil.example:{port}")[0] == 403
    assert get(port, "/state", host=f"localhost:{port}")[0] == 200


def test_unknown_path(served):
    hub, port = served
    assert get(port, "/warp")[0] == 404


def test_events_stream_pushes_snapshots(served):
    hub, port = served
    c = http.client.HTTPConnection(HOST, port, timeout=5)
    c.request("GET", "/events", headers={"Host": f"127.0.0.1:{port}"})
    r = c.getresponse()
    assert r.status == 200 and r.getheader("Content-Type") == "text/event-stream"
    first = r.fp.readline()
    assert first.startswith(b"data: ")
    assert json.loads(first[6:])["visible"] is True
    r.fp.readline()                                    # blank line between events
    hub.toggle_visible()
    second = r.fp.readline()
    assert json.loads(second[6:])["visible"] is False
    c.close()


def test_second_server_on_a_busy_port_fails(served):
    hub, port = served
    with pytest.raises(OSError):
        make_server(Hub(None, "second"), port=port, page=b"x")


def test_restart_on_same_port_after_an_open_stream_closes():
    hub = Hub(None, "first")
    srv = make_server(hub, port=0, page=b"x")
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    c = http.client.HTTPConnection(HOST, port, timeout=5)
    c.request("GET", "/events", headers={"Host": f"127.0.0.1:{port}"})
    r = c.getresponse()
    r.fp.readline()                                    # stream is open
    hub.close()                                        # server ends the stream first -> its side goes to TIME_WAIT
    srv.shutdown()
    srv.server_close()
    c.close()
    again = make_server(Hub(None, "restarted"), port=port, page=b"x")
    again.server_close()
