import importlib
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol, cast


class _WindowsLockingModule(Protocol):
    LK_NBLCK: int
    LK_UNLCK: int

    def locking(self, file_descriptor: int, mode: int, byte_count: int, /) -> None: ...


class _PosixLockingModule(Protocol):
    LOCK_EX: int
    LOCK_NB: int
    LOCK_UN: int

    def flock(self, file_descriptor: int, operation: int, /) -> None: ...


@contextmanager
def exclusive_run_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        if path.stat().st_size == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            _lock_file_descriptor(handle.fileno())
        except OSError as exc:
            raise RuntimeError(
                "Another AI benchmark prediction process already holds this run lock."
            ) from exc
        try:
            yield
        finally:
            handle.seek(0)
            _unlock_file_descriptor(handle.fileno())
    finally:
        handle.close()


def _lock_file_descriptor(file_descriptor: int) -> None:
    if os.name == "nt":
        windows_locking = cast(
            _WindowsLockingModule,
            importlib.import_module("msvcrt"),
        )
        windows_locking.locking(file_descriptor, windows_locking.LK_NBLCK, 1)
        return

    posix_locking = cast(
        _PosixLockingModule,
        importlib.import_module("fcntl"),
    )
    posix_locking.flock(
        file_descriptor,
        posix_locking.LOCK_EX | posix_locking.LOCK_NB,
    )


def _unlock_file_descriptor(file_descriptor: int) -> None:
    if os.name == "nt":
        windows_locking = cast(
            _WindowsLockingModule,
            importlib.import_module("msvcrt"),
        )
        windows_locking.locking(file_descriptor, windows_locking.LK_UNLCK, 1)
        return

    posix_locking = cast(
        _PosixLockingModule,
        importlib.import_module("fcntl"),
    )
    posix_locking.flock(file_descriptor, posix_locking.LOCK_UN)
