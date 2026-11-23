"""Restore captured cache bytes only when all user staging is exactly unchanged."""
import hashlib
import json
import os
import struct
from pathlib import Path

evidence = Path(__file__).resolve().parent
root = evidence.parents[2]
index = (root / ".git/index").resolve()
assert index.parent == (root / ".git").resolve()
original = (evidence / "original-index.bin").read_bytes()
observed = index.read_bytes()


def split(raw):
    signature, version, count = struct.unpack(">4sII", raw[:12])
    assert signature == b"DIRC" and version == 2
    assert hashlib.sha1(raw[:-20]).digest() == raw[-20:]
    offset = 12
    for _ in range(count):
        start = offset
        offset = raw.index(b"\0", offset + 62) + 1
        offset = start + ((offset - start + 7) // 8) * 8
    prefix = raw[:offset]
    extensions = {}
    while offset < len(raw) - 20:
        name, size = struct.unpack(">4sI", raw[offset:offset + 8])
        assert name not in extensions
        offset += 8
        extensions[name] = raw[offset:offset + size]
        offset += size
    assert offset == len(raw) - 20
    return prefix, extensions


before, old = split(original)
after, current = split(observed)
assert before == after, "staged entries or stat metadata changed; refuse restoration"
cache = {b"UNTR", b"FSMN"}
assert {k: v for k, v in old.items() if k not in cache} == {
    k: v for k, v in current.items() if k not in cache
}, "non-cache extension changed; refuse restoration"
lock = index.with_name(index.name + ".lock")
with lock.open("xb") as stream:
    assert index.read_bytes() == observed, "concurrent index change"
    stream.write(original)
    stream.flush()
    os.fsync(stream.fileno())
os.replace(lock, index)
record = {
    "restored_cache_extensions": ["UNTR", "FSMN"],
    "all_8824_index_entries_byte_identical": True,
    "TREE_extension_byte_identical": True,
    "observed_sha256": hashlib.sha256(observed).hexdigest(),
    "restored_sha256": hashlib.sha256(index.read_bytes()).hexdigest(),
}
(evidence / "index-restoration.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record))
