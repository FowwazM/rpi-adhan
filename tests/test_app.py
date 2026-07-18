from adhan.app import build_players
from adhan.config import BluetoothConfig, BluetoothSpeaker, CastOutput, OutputsConfig, ReliabilityConfig


def test_build_players_creates_cast_and_bluetooth_wrapped():
    outputs = OutputsConfig(
        cast=[CastOutput(name="Living")],
        bluetooth=BluetoothConfig(speakers=[BluetoothSpeaker(name="JBL", mac="AA:BB:CC:DD:EE:FF")]),
    )
    players = build_players(outputs, ReliabilityConfig(), combined_sink="adhan_combined")
    names = sorted(p.name for p in players)
    assert names == ["bluetooth:adhan_combined", "cast:Living"]


def test_build_players_no_bluetooth_when_no_speakers():
    outputs = OutputsConfig(cast=[CastOutput(name="Living")], bluetooth=BluetoothConfig(speakers=[]))
    players = build_players(outputs, ReliabilityConfig(), combined_sink="adhan_combined")
    assert [p.name for p in players] == ["cast:Living"]
