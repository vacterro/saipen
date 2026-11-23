"""REVIEW probe for T-1654, independent of the ticket's test module.

Random surroundings, random old blocks, random line endings: after one repair
the bytes before the opening marker and after the closing marker are the ones
written, the block is the current one, the verdict is CURRENT and a second
repair writes nothing. A file whose markers are not one pair is never written.

usage: review_property_probe.py <repo> [cases] [seed]
"""

import os
import random
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
CASES = int(sys.argv[2]) if len(sys.argv) > 2 else 400
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 1654
sys.path.insert(0, str(REPO / "tools"))
from saipen_engine import project_block as pb  # noqa: E402

BEGIN, END = pb.BEGIN, pb.END
rng = random.Random(SEED)
NAMES = [name for name in pb.INSTRUCTION_FILES if name != ".clinerules"]


def noise(limit: int) -> bytes:
    """Bytes that never contain a whole marker but often contain pieces of one."""
    pieces = [
        b"<!-- SAIPEN:", b"BEGIN -->", b"SAIPEN:END", b"<!--", b"-->", b"\r\n", b"\n", b"\r",
        b"\xef\xbb\xbf", b"\xe4\xf5\xfc", b"\x00", b"clone github.com/x/saipen ", b"C:\\Users\\a\\b ",
        b"## heading ", b"plain words ", bytes([rng.randrange(256)]),
    ]
    out = b"".join(rng.choice(pieces) for _ in range(rng.randrange(0, limit)))
    while BEGIN in out or END in out:
        out = out.replace(BEGIN, b"<!-- SAIPEN_BEGIN -->").replace(END, b"<!-- SAIPEN_END -->")
    return out


def old_block(newline: bytes) -> bytes:
    kind = rng.randrange(5)
    if kind == 0:
        body = [b"## saipen protocol (any agent)", b"Path missing? clone github.com/vacterro/saipen."]
    elif kind == 1:
        body = [b"## saipen protocol (project block 1)", b"edited by hand"]
    elif kind == 2:
        body = []
    elif kind == 3:
        body = [noise(12).replace(b"\r", b" ").replace(b"\n", b" ")]
    else:
        body = [b"## saipen protocol (project block 7)", b"Read C:\\Users\\x\\BOOT.md"]
    return newline.join([BEGIN, *body, END])


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="saipen-t1654-review-"))
    broken: list[str] = []
    written = refused = 0
    try:
        for case in range(CASES):
            project = base / f"p{case}"
            (project / ".saipen").mkdir(parents=True)
            name = rng.choice(NAMES)
            path = project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            newline = rng.choice([b"\n", b"\r\n"])
            prefix, suffix = noise(14), noise(14)
            malformed = rng.randrange(6) == 0
            if malformed:
                shape = rng.randrange(3)
                middle = [BEGIN + b"\nx\n", b"x\n" + END, old_block(newline) + b"\n" + old_block(newline)][shape]
            else:
                middle = old_block(newline)
            body = prefix + middle + suffix
            path.write_bytes(body)
            first = pb.repair(project)
            data = path.read_bytes()
            if malformed:
                refused += 1
                if data != body or first["written"] or first["ok"]:
                    broken.append(f"case {case}: a malformed file was written or accepted")
                continue
            style = b"\r\n" if b"\r\n" in middle else b"\n"
            expected = prefix + pb.current_block(style) + suffix
            if data != expected:
                broken.append(f"case {case}: bytes outside the markers or the block differ")
                continue
            if not first["ok"] or first["code"] != pb.CODE_REPAIRED:
                broken.append(f"case {case}: verdict {first['code']} after a repair")
            stamp = path.stat().st_mtime_ns
            again = pb.repair(project)
            if again["written"] or path.read_bytes() != expected or path.stat().st_mtime_ns != stamp:
                broken.append(f"case {case}: a second repair wrote")
            if pb.status(project)["code"] != pb.CODE_CURRENT:
                broken.append(f"case {case}: status is not CURRENT after the repair")
            leftovers = [item.name for item in path.parent.iterdir() if item.name.endswith(".tmp")]
            if leftovers:
                broken.append(f"case {case}: temporary file left behind {leftovers}")
            written += 1
    finally:
        shutil.rmtree(base, True)
    print(f"seed {SEED}: {CASES} cases, {written} repaired, {refused} malformed and left alone, "
          f"{len(broken)} broken")
    for line in broken[:10]:
        print("  " + line)
    return 1 if broken else 0


if __name__ == "__main__":
    os.environ.pop("ZAICODE_HOME", None)
    sys.exit(main())
