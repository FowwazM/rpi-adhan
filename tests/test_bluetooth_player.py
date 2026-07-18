from adhan.models import HealthState, MediaRef
from adhan.players.bluetooth import BluetoothPlayer
from tests.fakes import RecordingRunner

MEDIA = MediaRef("/media/adhan.mp3", "http://h/adhan.mp3")


def test_play_sets_volume_then_plays_to_sink():
    runner = RecordingRunner(sinks_output="42\tadhan_combined\tmodule\tformat\tRUNNING\n")
    player = BluetoothPlayer("adhan_combined", runner=runner)
    r = player.play(MEDIA, 0.4)
    assert r.success
    cmds = [" ".join(c) for c in runner.commands]
    assert any("set-sink-volume adhan_combined 40%" in c for c in cmds)
    assert any("paplay --device=adhan_combined /media/adhan.mp3" in c for c in cmds)


def test_health_ok_when_sink_present():
    runner = RecordingRunner(sinks_output="42\tadhan_combined\tx\ty\tRUNNING\n")
    assert BluetoothPlayer("adhan_combined", runner=runner).health_check().state is HealthState.OK


def test_health_unreachable_when_sink_absent():
    runner = RecordingRunner(sinks_output="42\tother_sink\tx\ty\tRUNNING\n")
    assert (
        BluetoothPlayer("adhan_combined", runner=runner).health_check().state
        is HealthState.UNREACHABLE
    )


def test_play_failure_returns_error():
    runner = RecordingRunner(sinks_output="42\tadhan_combined\tx\ty\tRUNNING\n", fail_on="paplay")
    r = BluetoothPlayer("adhan_combined", runner=runner).play(MEDIA, 0.4)
    assert not r.success
