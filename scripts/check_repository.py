"""Fail CI if runtime artifacts, private environment files or obvious tokens enter Git."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def check():
    result = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True)
    paths = [p for p in result.stdout.decode().split("\0") if p]
    forbidden = []
    token_pattern = re.compile(
        rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|sk-ant-[A-Za-z0-9_-]{40,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
    )
    for filename in paths:
        path = Path(filename)
        if any(p in ("outputs", "cache", "data") for p in path.parts) or (
            path.name.startswith(".env") and path.name != ".env.example"
        ):
            forbidden.append(filename + " (runtime/private file)")
        if path.is_file() and token_pattern.search(path.read_bytes()):
            forbidden.append(filename + " (possible credential)")
    # Names across all reachable commits catch accidental deletion-before-push cases.
    history = subprocess.run(
        ["git", "log", "--all", "--pretty=format:", "--name-only"], capture_output=True, check=True
    ).stdout.decode()
    for filename in history.splitlines():
        if filename.startswith(("outputs/", "cache/", "data/")) or filename in (
            ".env",
            ".env.local",
        ):
            forbidden.append(filename + " (history)")
    objects = (
        subprocess.run(["git", "rev-list", "--objects", "--all"], capture_output=True, check=True)
        .stdout.decode()
        .splitlines()
    )
    for item in objects:
        parts = item.split(" ", 1)
        if len(parts) != 2:
            continue
        oid, name = parts
        kind = subprocess.run(
            ["git", "cat-file", "-t", oid], capture_output=True, check=True
        ).stdout.strip()
        if kind == b"blob":
            content = subprocess.run(
                ["git", "cat-file", "blob", oid], capture_output=True, check=True
            ).stdout
            if token_pattern.search(content):
                forbidden.append(name + " (possible credential in history)")
    if forbidden:
        raise SystemExit("\n".join(sorted(set(forbidden))))
    print(f"Repository hygiene checks passed for {len(paths)} tracked paths.")


if __name__ == "__main__":
    check()
