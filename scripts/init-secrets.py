#!/usr/bin/env python3
"""Initialize named-volume state without exposing credentials to other users."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

SECRET_DIR = Path(os.environ.get("VA_SECRET_DIR", "/run/academy-secrets"))
HARNESS_KEY = SECRET_DIR / "harness.key"


def ensure_dir(path: Path, mode: int, uid: int | None = None, gid: int | None = None) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, mode)
    if uid is not None and gid is not None:
        os.chown(path, uid, gid)


def write_secret() -> None:
    ensure_dir(SECRET_DIR, 0o750, 0, 1001)
    if not HARNESS_KEY.exists():
        value = secrets.token_urlsafe(48) + "\n"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(HARNESS_KEY, flags, 0o440)
        try:
            os.write(fd, value.encode("ascii"))
        finally:
            os.close(fd)
    os.chown(HARNESS_KEY, 0, 1001)
    os.chmod(HARNESS_KEY, 0o440)


def main() -> None:
    write_secret()
    ensure_dir(Path("/var/lib/academy"), 0o770, 1001, 1001)
    ensure_dir(Path("/var/lib/academy-progress"), 0o770, 1001, 1001)
    ensure_dir(Path("/home/kali"), 0o755, 1000, 1000)
    # Keep a small, non-secret marker useful to diagnostics.
    marker = Path("/var/lib/academy-progress/.initialized")
    marker.write_text("initialized\n", encoding="utf-8")
    os.chown(marker, 1001, 1001)
    os.chmod(marker, 0o660)
    print("academy volumes initialized")


if __name__ == "__main__":
    main()
