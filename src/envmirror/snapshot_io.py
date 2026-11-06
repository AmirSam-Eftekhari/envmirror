"""Reading and writing snapshot files safely."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .errors import OutputError, SnapshotError
from .models.snapshot import Snapshot, migrate_raw, top_level_unknown_fields

MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = value
    return result


def _clean(text: str, limit: int = 200) -> str:
    cleaned = "".join(ch if ch.isprintable() else "?" for ch in text)
    return cleaned if len(cleaned) <= limit else cleaned[:limit] + "..."


def parse_snapshot(text: str) -> tuple[Snapshot, list[str]]:
    """Parse and validate snapshot JSON text. Returns (snapshot, warnings)."""
    try:
        raw = json.loads(text, object_pairs_hook=_no_duplicates)
    except json.JSONDecodeError as exc:
        raise SnapshotError(f"Not valid JSON: {_clean(exc.msg)} (line {exc.lineno})") from exc
    except RecursionError as exc:
        raise SnapshotError("JSON is nested too deeply") from exc
    except ValueError as exc:
        raise SnapshotError(f"Not valid JSON: {_clean(str(exc))}") from exc
    if not isinstance(raw, dict):
        raise SnapshotError("A snapshot must be a JSON object at the top level")
    raw = migrate_raw(raw)
    try:
        snapshot = Snapshot.model_validate(raw)
    except ValidationError as exc:
        problems = []
        for err in exc.errors(include_input=False)[:10]:
            where = ".".join(str(p) for p in err["loc"]) or "<root>"
            problems.append(f"{_clean(where)}: {_clean(err['msg'])}")
        extra = "" if exc.error_count() <= 10 else f" (+{exc.error_count() - 10} more)"
        raise SnapshotError("Invalid snapshot: " + "; ".join(problems) + extra) from exc
    warnings = [f"Ignored unknown top-level field: {_clean(k)}" for k in top_level_unknown_fields(raw)]
    return snapshot, warnings


def read_snapshot(path: Path) -> tuple[Snapshot, list[str]]:
    """Load a snapshot file from disk with size and encoding checks."""
    try:
        if not path.exists():
            raise SnapshotError(f"File not found: {path}")
        if not path.is_file():
            raise SnapshotError(f"Not a regular file: {path}")
        if path.stat().st_size > MAX_SNAPSHOT_BYTES:
            raise SnapshotError(
                f"File is larger than {MAX_SNAPSHOT_BYTES // (1024 * 1024)} MB: {path}"
            )
        with path.open("rb") as handle:
            data = handle.read(MAX_SNAPSHOT_BYTES + 1)
        if len(data) > MAX_SNAPSHOT_BYTES:
            raise SnapshotError(
                f"File is larger than {MAX_SNAPSHOT_BYTES // (1024 * 1024)} MB: {path}"
            )
    except OSError as exc:
        raise SnapshotError(f"Cannot read {path}: {exc.strerror or exc}") from exc
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SnapshotError(f"File is not valid UTF-8: {path}") from exc
    return parse_snapshot(text)


def write_text_atomic(path: Path, text: str) -> None:
    """Write UTF-8 text atomically (temp file + replace)."""
    try:
        if path.is_dir():
            raise OutputError(f"Output path is a directory: {path}")
        parent = path.parent if str(path.parent) else Path(".")
        if not parent.is_dir():
            raise OutputError(f"Directory does not exist: {parent}")
        fd, tmp_name = tempfile.mkstemp(dir=parent, prefix=".envmirror-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            os.replace(tmp_name, path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
    except OSError as exc:
        raise OutputError(f"Cannot write {path}: {exc.strerror or exc}") from exc
