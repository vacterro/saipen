"""Incremental parser for the SAIPAL report transport (PERF-004 / SRC-338:R027).

`json.load` builds the entire document before any of it can be inspected, so a
report near the transport spool ceiling doubles peak memory and cannot be
validated until it is fully materialised. This module walks the response once,
decoding small top-level fields individually and handing each finding to a
caller-supplied sink as it completes.

What that buys:

* the response is validated *while* it is read, so a truncated or malformed
  payload is refused instead of half-accepted;
* only one top-level value is buffered at a time, so the envelope is never
  held alongside a second full copy of the document;
* the caller decides what to do with each finding (keep, count, page, discard),
  which is what makes "only new qualified findings" possible without
  materialising the corpus twice.

The supported shape is exactly what the SAIPAL backend emits: one JSON object
with string keys. Anything else is a protocol error, never a guess.
"""

from __future__ import annotations

import json

MAX_REPORT_VALUE_BYTES = 4 * 1024 * 1024
REPORT_STREAM_CHUNK_CHARS = 64 * 1024

_WHITESPACE = " \t\r\n"


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"Non-finite JSON value: {value}")


class _Cursor:
    """A sliding-window character cursor over a text stream.

    The window is compacted whenever it is refilled, so the document prefix is
    released as soon as it has been consumed.
    """

    def __init__(self, stream, chunk_chars: int) -> None:
        self._stream = stream
        self._chunk = chunk_chars
        self.text = ""
        self.pos = 0
        self.eof = False
        self._decoder = json.JSONDecoder(
            object_pairs_hook=_object_pairs,
            parse_constant=_reject_constant,
        )

    def more(self) -> bool:
        if self.eof:
            return False
        chunk = self._stream.read(self._chunk)
        if not chunk:
            self.eof = True
            return False
        self.text = self.text[self.pos :] + chunk
        self.pos = 0
        return True

    def peek(self):
        """Skip whitespace and return the next character, or None at EOF."""
        while True:
            while self.pos < len(self.text) and self.text[self.pos] in _WHITESPACE:
                self.pos += 1
            if self.pos < len(self.text):
                return self.text[self.pos]
            if not self.more():
                return None

    def take(self, char: str, *, context: str) -> None:
        if self.peek() != char:
            raise ValueError(f"Backend payload is missing {char!r} {context}")
        self.pos += 1

    def string(self) -> str:
        """Decode the JSON string at the cursor."""
        while True:
            start = self.pos
            text = self.text
            escaped = False
            index = start + 1
            end = None
            while index < len(text):
                ch = text[index]
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    end = index
                    break
                index += 1
            if end is not None:
                raw = text[start : end + 1]
                if len(raw) > MAX_REPORT_VALUE_BYTES:
                    raise ValueError("Backend object key exceeds the declared value bound")
                self.pos = end + 1
                return json.loads(raw)
            if len(text) - start > MAX_REPORT_VALUE_BYTES:
                raise ValueError("Backend object key exceeds the declared value bound")
            if not self.more():
                raise ValueError("Backend payload ended inside a key")

    def value(self):
        """Decode exactly one JSON value, bounded by MAX_REPORT_VALUE_BYTES.

        The decode window is grown from the cursor's live buffer by shifting
        the cursor forward as it fills. ``more()`` compacts the buffer, so the
        cursor position (not a saved window) is the only stable handle across a
        refill -- reading a stale slice after compaction starts decoding in the
        middle of the document.
        """
    def value(self):
        """Decode exactly one JSON value, bounded by MAX_REPORT_VALUE_BYTES.

        ``raw_decode`` is given the live buffer AND the cursor index, so no
        slice is made: slicing ``text[start:]`` per finding copies the whole
        remaining document, which made peak memory scale with the report and
        defeated the point of streaming it. The bound therefore applies to how
        far the cursor has to advance, not to the size of the buffer behind it.
        """
        while True:
            if self.peek() is None:
                raise ValueError("Backend payload ended before a value")
            start = self.pos
            try:
                value, end = self._decoder.raw_decode(self.text, start)
            except json.JSONDecodeError:
                if len(self.text) - start > MAX_REPORT_VALUE_BYTES:
                    raise ValueError("Backend value exceeds the declared value bound") from None
                if not self.more():
                    raise ValueError("Backend payload ended inside a value") from None
                # more() compacted the buffer to start at the value.
                continue
            self.pos = end
            return value

    def consume_array(self, on_item) -> int:
        """Decode an array, calling ``on_item`` per element; return the count.

        Elements are decoded one at a time, so the array itself is never
        materialised by this method. ``on_item`` must not raise to signal a
        refusal it expects to explain; it raises only for a real protocol or
        policy failure.
        """
        self.take("[", context="before the findings array")
        count = 0
        if self.peek() == "]":
            self.pos += 1
            return count
        while True:
            on_item(self.value())
            count += 1
            ch = self.peek()
            if ch == ",":
                self.pos += 1
                continue
            if ch == "]":
                self.pos += 1
                return count
            raise ValueError("Backend array element is not followed by ',' or ']'")

    def finish(self) -> None:
        if self.peek() is not None:
            raise ValueError("Backend payload has trailing content")


def parse_report(stream, on_finding=None, *, chunk_chars: int = REPORT_STREAM_CHUNK_CHARS):
    """Parse one report response, calling ``on_finding`` per finding.

    Returns ``(envelope, finding_count)``. ``envelope`` holds every top-level
    field except ``findings``. A backend REFUSAL legitimately has no findings:
    ``ok: false`` with a typed status is the backend saying it could not
    produce a report, so that case returns a count of 0 rather than failing as
    a protocol error.
    """
    cursor = _Cursor(stream, chunk_chars)
    envelope: dict = {}
    seen: set[str] = set()
    found_findings = False
    count = 0

    cursor.take("{", context="to open the response object")
    if cursor.peek() == "}":
        cursor.pos += 1
    else:
        while True:
            if cursor.peek() != '"':
                raise ValueError("Backend payload has a non-string object key")
            key = cursor.string()
            if key in seen:
                raise ValueError(f"Duplicate JSON field: {key}")
            seen.add(key)
            cursor.take(":", context="after a key")
            if key == "findings":
                found_findings = True
                if cursor.peek() != "[":
                    raise ValueError("Backend report findings must be a list")
                count = cursor.consume_array(on_finding or (lambda _row: None))
            else:
                envelope[key] = cursor.value()
            ch = cursor.peek()
            if ch == ",":
                cursor.pos += 1
                continue
            if ch == "}":
                cursor.pos += 1
                break
            raise ValueError("Backend object member is not followed by ',' or '}'")

    if not found_findings and envelope.get("ok") is not False:
        raise ValueError("Backend report is missing its findings field")
    cursor.finish()
    return envelope, count


def iter_report_findings(stream, *, chunk_chars: int = REPORT_STREAM_CHUNK_CHARS):
    """Yield the report's findings one at a time, validating the whole response.

    PERF-004 Phase B: pagination must not hold the corpus. ``parse_report`` needs
    a sink that cannot suspend, so a page-by-page consumer had no choice but to
    collect every row first. This walks the same document with the same cursor
    and hands each finding out as it completes.

    Validation order matters: findings may appear before the rest of the
    envelope, so a caller that stops early has not proven the response. Phase A
    (``parse_report`` with a validating sink over the same spool) is therefore
    required before any of these rows may be published; this generator is the
    delivery pass over bytes that already passed it.
    """
    cursor = _Cursor(stream, chunk_chars)
    envelope: dict = {}
    seen: set[str] = set()
    found_findings = False

    cursor.take("{", context="to open the response object")
    if cursor.peek() == "}":
        cursor.pos += 1
    else:
        while True:
            if cursor.peek() != '"':
                raise ValueError("Backend payload has a non-string object key")
            key = cursor.string()
            if key in seen:
                raise ValueError(f"Duplicate JSON field: {key}")
            seen.add(key)
            cursor.take(":", context="after a key")
            if key == "findings":
                found_findings = True
                if cursor.peek() != "[":
                    raise ValueError("Backend report findings must be a list")
                cursor.take("[", context="before the findings array")
                if cursor.peek() == "]":
                    cursor.pos += 1
                else:
                    while True:
                        yield cursor.value()
                        ch = cursor.peek()
                        if ch == ",":
                            cursor.pos += 1
                            continue
                        if ch == "]":
                            cursor.pos += 1
                            break
                        raise ValueError(
                            "Backend array element is not followed by ',' or ']'"
                        )
            else:
                envelope[key] = cursor.value()
            ch = cursor.peek()
            if ch == ",":
                cursor.pos += 1
                continue
            if ch == "}":
                cursor.pos += 1
                break
            raise ValueError("Backend object member is not followed by ',' or '}'")

    if not found_findings and envelope.get("ok") is not False:
        raise ValueError("Backend report is missing its findings field")
    cursor.finish()


def read_report(stream, *, max_findings: int | None = None):
    """Materialise a report as ``(envelope, findings_list)``.

    ``max_findings`` refuses an oversized corpus while parsing rather than
    after building it, so the refusal costs one finding, not one report.
    """
    collected: list = []

    def sink(row) -> None:
        if max_findings is not None and len(collected) >= max_findings:
            raise ValueError(
                f"Backend report exceeds the declared finding bound ({max_findings})"
            )
        collected.append(row)

    envelope, count = parse_report(stream, sink)
    return envelope, collected
