"""Append one or more LOG.md lines, preserving the file's CRLF convention.

Usage: python tools/_log_append.py "line one" "line two" ...
Read-only otherwise: never rewrites existing bytes.
"""
from __future__ import annotations

import pathlib
import sys


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: _log_append.py <line> [<line> ...]")
        return 2
    path = pathlib.Path(".saipen/LOG.md")
    raw = path.read_bytes()
    newline = b"\r\n" if b"\r\n" in raw else b"\n"
    payload = raw
    if payload and not payload.endswith(newline):
        payload += newline
    for line in argv[1:]:
        payload += line.encode("utf-8") + newline
    path.write_bytes(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
