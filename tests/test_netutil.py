from adhan import netutil


def test_get_lan_ip_uses_getsockname(monkeypatch):
    class FakeSocket:
        def connect(self, addr):
            pass

        def getsockname(self):
            return ("192.168.1.42", 12345)

        def close(self):
            pass

    monkeypatch.setattr(netutil.socket, "socket", lambda *a, **k: FakeSocket())
    assert netutil.get_lan_ip() == "192.168.1.42"


def test_get_lan_ip_falls_back_on_oserror(monkeypatch):
    class FakeSocket:
        def connect(self, addr):
            raise OSError("network unreachable")

        def close(self):
            pass

    monkeypatch.setattr(netutil.socket, "socket", lambda *a, **k: FakeSocket())
    assert netutil.get_lan_ip() == "127.0.0.1"
