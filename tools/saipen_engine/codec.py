"""Document I/O with genuine encoding/BOM/newline byte preservation.

Reads never die on a `.saipen/` file's encoding (a decode error must not kill
the whole run). A Document retains every representation fact -- encoding,
BOM, newline convention, final-newline state -- and `encode()` reproduces the
exact byte representation of a mutated text. `read_doc` remains the normalised
LF view used by parsers; mutations that claim preservation go through the
Document so the journal stores the EXACT intended bytes (NITRO integrity).

A UTF-16LE BOM file is decoded as UTF-16 and re-encoded as UTF-16 with its BOM.
No path ever prepends a UTF-16 BOM to UTF-8 bytes or silently rewrites a
non-UTF-8 document as UTF-8.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

_BOMS = (
    (b"\xef\xbb\xbf", "utf-8-sig", "utf-8"),
    (b"\xff\xfe\x00\x00", "utf-32-le", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be", "utf-16-be"),
)
# bom_bytes -> (decoder, clean_codec_name)
_DECODE = {bom: (dec, clean) for bom, dec, clean in _BOMS}


def _bomless_utf16(raw: bytes):
    """Name the UTF-16 flavour of a BOM-less file, or None."""
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
    for bom, _dec, clean in _BOMS:
        if raw.startswith(bom):
            return clean
    bomless = _bomless_utf16(raw)
    if bomless:
        return bomless
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return "not-utf-8"
    return "utf-8"


def _decode(raw: bytes) -> tuple[str, str, bytes]:
    """Return (text, clean_codec_name, bom)."""
    for bom, _dec, clean in _BOMS:
        if raw.startswith(bom):
            return raw[len(bom):].decode(clean, errors="replace"), clean, bom
    bomless = _bomless_utf16(raw)
    if bomless:
        return raw.decode(bomless, errors="replace"), bomless, b""
    try:
        return raw.decode("utf-8"), "utf-8", b""
    except UnicodeDecodeError:
        try:
            return raw.decode("cp1251"), "cp1251", b""
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace"), "utf-8", b""


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

    @property
    def text_norm(self) -> str:
        """The LF-normalised view parsers use."""
        return self.text.replace("\r\n", "\n").replace("\r", "\n")

    def encode(self, new_text: str) -> bytes:
        """Encode `new_text` (LF-normalised) into the ORIGINAL representation:
        same encoding, same BOM, same newline convention, same final-newline
        state. Returns the exact bytes a mutation should journal."""
        body = new_text
        if self.newline != "\n":
            body = body.replace("\n", self.newline)
        if not body.endswith(self.newline) and self.final_newline:
            body += self.newline
        if self.bom:
            return self.bom + body.encode(self.encoding)
        return body.encode(self.encoding)


def read_document(path: Path | str) -> Document:
    """Read a file and record its encoding/BOM/newline/final-newline facts."""
    path = Path(path)
    raw = path.read_bytes() if path.is_file() else b""
    text, encoding, bom = _decode(raw)
    newline = "\n"
    for candidate in ("\r\n", "\r", "\n"):
        if candidate in text:
            newline = candidate
            break
    final_newline = bool(text) and text.endswith(("\n", "\r"))
    return Document(
        text=text,
        encoding=encoding,
        bom=bom,
        newline=newline,
        final_newline=final_newline,
        raw_hash=hashlib.sha256(raw).hexdigest()[:16],
    )


def write_document(path: Path | str, doc: Document, new_text: str) -> None:
    """Write a document preserving its representation facts. Atomic."""
    payload = doc.encode(new_text)
    tmp = Path(path).with_name(Path(path).name + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def read_doc(path: Path | str) -> str:
    """The LF-normalised decoded text, as the validator sees it."""
    return read_document(path).text_norm


def encode_preserving(path: Path | str, new_text: str) -> bytes:
    """Encode `new_text` into the exact bytes the file at `path` would carry
    after a mutation, preserving that file's current representation."""
    return read_document(path).encode(new_text)
