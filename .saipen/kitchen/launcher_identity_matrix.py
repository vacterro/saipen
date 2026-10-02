"""Phase D matrix: canonical identity vs textual resemblance (read-only)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from saipen_engine.guard_events import _saipen_cli_verb  # noqa: E402

POSITIVE = [
    "saipen recover",
    "saipen status",
    "saipen transition VERIFY",
    "saipen checkpoint RUN foo",
    "saipen",
]
NEGATIVE = [
    "foo-saipen recover",
    "saipen-malicious recover",
    "./saipen recover",
    "python tools/saipen.py recover",
    "python " + "C:" + chr(92) + "x" + chr(92) + "saipen.py recover",
    "powershell -File saipen.ps1 recover",
    "cmd /c saipen recover",
    "bash -lc 'saipen recover'",
    "FOO=1 saipen recover",
    "saipen recover; rm -f .saipen/STATE.md",
    "saipen recover && echo x",
    "saipen recover | cat",
    "echo saipen recover",
    "saipen unknownverb",
    "saipen recover > out.txt",
]

bad = 0
for command in POSITIVE:
    verb = _saipen_cli_verb(command)
    ok = verb is not None
    bad += not ok
    print(("PASS " if ok else "FAIL "), "canonical    :", repr(command), "->", verb)
for command in NEGATIVE:
    verb = _saipen_cli_verb(command)
    ok = verb is None
    bad += not ok
    print(("PASS " if ok else "FAIL "), "not-canonical:", repr(command), "->", verb)
print("matrix failures:", bad)
