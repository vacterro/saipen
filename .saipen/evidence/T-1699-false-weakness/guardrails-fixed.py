"""Inject the alleged bad frame without relying on an optional Markdown title."""
from pathlib import Path


def unnumbered(root):
    path = Path(root) / ".saipen/LOG.md"
    before = path.read_bytes()
    payload = b"- 10.10.26 [T-1] RUN: ticket finished via SAIOPS -- completion (from SHIP)\n"
    path.write_bytes(payload + before)
    assert path.read_bytes().startswith(payload), "hostile fixture payload did not land"
