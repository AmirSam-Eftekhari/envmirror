import json

from envmirror.errors import OutputError, SnapshotError
from envmirror.models.snapshot import Snapshot
from envmirror.snapshot_io import parse_snapshot, read_snapshot, write_text_atomic
from helpers import make_snapshot, snapshot_dict
import pytest


def test_roundtrip_is_lossless():
    snap = make_snapshot()
    again, warnings = parse_snapshot(snap.to_json())
    assert again.model_dump() == snap.model_dump()
    assert warnings == []


def test_serialization_is_deterministic_and_sorted():
    a, b = make_snapshot().to_json(), make_snapshot().to_json()
    assert a == b and a.endswith("\n")
    top = list(json.loads(a))
    assert top == sorted(top)


def test_unknown_top_level_fields_are_ignored_with_warning():
    raw = snapshot_dict()
    raw["future_field"] = {"x": 1}
    snap, warnings = parse_snapshot(json.dumps(raw))
    assert "future_field" not in snap.to_json()
    assert any("future_field" in w for w in warnings)


def test_newer_major_schema_is_rejected_with_actionable_message():
    with pytest.raises(SnapshotError, match="newer"):
        parse_snapshot(json.dumps(snapshot_dict(schema_version="2.0")))


def test_newer_minor_schema_is_accepted():
    snap, _ = parse_snapshot(json.dumps(snapshot_dict(schema_version="1.7")))
    assert snap.schema_version == "1.7"


@pytest.mark.parametrize("text", ["{not json", "", "[]", "42", "null"])
def test_malformed_or_wrong_top_level_json(text):
    with pytest.raises(SnapshotError):
        parse_snapshot(text)


def test_duplicate_keys_rejected():
    with pytest.raises(SnapshotError, match="duplicate"):
        parse_snapshot('{"schema_version": "1.0", "schema_version": "1.0"}')


def test_deeply_nested_json_is_rejected_not_crashing():
    with pytest.raises(SnapshotError):
        parse_snapshot("[" * 100000)


def test_missing_required_fields_reported():
    raw = snapshot_dict()
    del raw["system"]
    with pytest.raises(SnapshotError, match="system"):
        parse_snapshot(json.dumps(raw))


def test_found_detection_without_version_is_rejected():
    raw = snapshot_dict(runtimes={"node": {"status": "found", "version": None}})
    with pytest.raises(SnapshotError):
        parse_snapshot(json.dumps(raw))


def test_error_messages_do_not_echo_input_values():
    raw = snapshot_dict(created_at="SECRET-VALUE-123")
    with pytest.raises(SnapshotError) as info:
        parse_snapshot(json.dumps(raw))
    assert "SECRET-VALUE-123" not in str(info.value)


def test_control_characters_in_strings_rejected():
    raw = snapshot_dict(packages={"python": {"evil\x1b[31m": "1.0"}})
    with pytest.raises(SnapshotError):
        parse_snapshot(json.dumps(raw))


def test_bad_timestamp_rejected():
    with pytest.raises(SnapshotError):
        parse_snapshot(json.dumps(snapshot_dict(created_at="yesterday")))


def test_read_missing_file(tmp_path):
    with pytest.raises(SnapshotError, match="not found"):
        read_snapshot(tmp_path / "nope.json")


def test_read_directory(tmp_path):
    with pytest.raises(SnapshotError, match="regular file"):
        read_snapshot(tmp_path)


def test_read_invalid_utf8(tmp_path):
    path = tmp_path / "bad.json"
    path.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(SnapshotError, match="UTF-8"):
        read_snapshot(path)


def test_read_oversized_file(tmp_path, monkeypatch):
    path = tmp_path / "big.json"
    path.write_text(make_snapshot().to_json(), encoding="utf-8")
    monkeypatch.setattr("envmirror.snapshot_io.MAX_SNAPSHOT_BYTES", 10)
    with pytest.raises(SnapshotError, match="larger"):
        read_snapshot(path)


def test_read_accepts_utf8_bom_and_spaces_in_path(tmp_path):
    folder = tmp_path / "My Snapshots"
    folder.mkdir()
    path = folder / "machine a (old).json"
    path.write_bytes(b"\xef\xbb\xbf" + make_snapshot().to_json().encode("utf-8"))
    snap, _ = read_snapshot(path)
    assert isinstance(snap, Snapshot)


def test_write_atomic_roundtrip_and_no_temp_files_left(tmp_path):
    target = tmp_path / "out dir"
    target.mkdir()
    path = target / "snap shot.json"
    write_text_atomic(path, "hello")
    assert path.read_text(encoding="utf-8") == "hello"
    assert [p.name for p in target.iterdir()] == ["snap shot.json"]


def test_write_to_missing_directory_fails_cleanly(tmp_path):
    with pytest.raises(OutputError, match="does not exist"):
        write_text_atomic(tmp_path / "missing" / "x.json", "x")


def test_write_to_directory_path_fails_cleanly(tmp_path):
    with pytest.raises(OutputError, match="directory"):
        write_text_atomic(tmp_path, "x")


def test_unsupported_older_major_is_rejected(machine_a):
    import json

    from envmirror.errors import SnapshotError
    from envmirror.snapshot_io import parse_snapshot

    raw = json.loads(machine_a.read_text(encoding="utf-8"))
    raw["schema_version"] = "0.9"
    try:
        parse_snapshot(json.dumps(raw))
    except SnapshotError as exc:
        assert "older than supported" in str(exc)
    else:
        raise AssertionError("unsupported older schema major was accepted")
