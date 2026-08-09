"""Document I/O with encoding/BOM/newline metadata retention.

Reads never die on a `.saipen/` file's encoding (a decode error must not kill
the whole run). The engine additionally retains the representation facts so a
mutation can preserve encoding/BOM/newline/final-newline unless an explicit
migration owns the change (OPS.md / NITRO M1).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_BOMS = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)


def _bomless_utf16(raw: bytes):
    """Name the UTF-16 flavour of a BOM-less file, or None.

    NUL is valid UTF-8, so `.decode("utf-8")` succeeds on UTF-16LE ASCII and
    hands back a NUL-filled string that matches no pattern. Test the byte
    shape instead.
    """
    if len(raw) < 4 or b"\x00" not in raw:
        return None
    head = raw[:4096]
    head = head[:len(head) - len(head) % 2]
    half = len(head) // 2
    if not half:
        return None
    even, odd = head[0::2].count(0), head[1::2].count(0)
    if odd > half * 0.3 and even < half * 0.1:
        return "utf-16-le"
    if even > half * 0.3 and odd < half * 0.1:
        return "utf-16-be"
    return None


def encoding_of(path: Path | str) -> str:
    """Name the encoding of a file, without decoding it."""
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return "unreadable"
    for bom, enc in _BOMS:
        if raw.startswith(bom):
            return enc
    bomless = _bomless_utf16(raw)
    if bomless:
        return bomless + " (no BOM)"
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return "not-utf-8"
    return "utf-8"


def _decode(raw: bytes) -> str:
    for bom, enc in _BOMS:
        if raw.startswith(bom):
            return raw[len(bom):].decode(enc, errors="replace")
    bomless = _bomless_utf16(raw)
    if bomless:
        return raw.decode(bomless, errors="replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("cp1251")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace")


@dataclass(frozen=True)
class Document:
    """Decoded text plus the representation facts needed to write it back."""

    text: str
    encoding: str
    bom: bytes = b""
    newline: str = "\n"
    final_newline: bool = True
    raw_hash: str = ""

    @property
    def lines(self) -> list[str]:
        return self.text.splitlines()


def read_document(path: Path | str) -> Document:
    """Read a file and record its encoding/BOM/newline/final-newline facts."""
    path = Path(path)
    raw = path.read_bytes() if path.is_file() else b""
    text = _decode(raw)
    newline = "\n"
    for candidate in ("\r\n", "\r", "\n"):
        if candidate in text:
            newline = candidate
            break
    final_newline = bool(text) and text.endswith(("\n", "\r"))
    return Document(
        text=text,
        encoding=encoding_of(path),
        bom=next((b for b, _ in _BOMS if raw.startswith(b)), b""),
        newline=newline,
        final_newline=final_newline,
        raw_hash=__import__("hashlib").sha256(raw).hexdigest()[:16],
    )


def write_document(path: Path | str, doc: Document, new_text: str) -> None:
    """Write a document preserving its representation facts.

    Atomic: sibling temp + os.replace. The newline convention, BOM and final
    newline of the original are preserved unless the caller migrates them.
    """
    path = Path(path)
    body = new_text
    if doc.newline != "\n":
        body = body.replace("\n", doc.newline)
    raw = body
    if not raw.endswith(doc.newline) and doc.final_newline:
        raw += doc.newline
    payload = raw.encode("utf-8")
    if doc.bom:
        payload = doc.bom + payload
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def read_doc(path: Path | str) -> str:
    """Compat shim: the decoded text, newline-normalised like the validator.

    New consumers use read_document to keep representation facts.
    """
    return read_document(path).text.replace("\r\n", "\n").replace("\r", "\n")
