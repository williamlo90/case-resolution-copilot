import hashlib
import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_within(root: Path, path: Path) -> Path:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError(f"Path escapes benchmark data root: {path}")
    return resolved_path


def atomic_write_bytes(root: Path, path: Path, content: bytes) -> None:
    destination = ensure_within(root, path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    ensure_within(root, temporary)
    try:
        temporary.write_bytes(content)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_json(root: Path, path: Path, value: Any) -> None:
    atomic_write_bytes(root, path, canonical_json_bytes(value) + b"\n")


def write_jsonl(root: Path, path: Path, records: Iterable[BaseModel]) -> int:
    serialized = [
        canonical_json_bytes(record.model_dump(mode="json", exclude_none=True))
        for record in records
    ]
    content = b"\n".join(serialized)
    if serialized:
        content += b"\n"
    atomic_write_bytes(root, path, content)
    return len(serialized)


def read_jsonl[T](path: Path, adapter: TypeAdapter[T]) -> list[T]:
    records: list[T] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(adapter.validate_json(stripped))
            except Exception as exc:
                raise ValueError(f"Invalid JSONL record at {path}:{line_number}: {exc}") from exc
    return records


def relative_manifest_path(root: Path, path: Path) -> str:
    return ensure_within(root, path).relative_to(root.resolve()).as_posix()
