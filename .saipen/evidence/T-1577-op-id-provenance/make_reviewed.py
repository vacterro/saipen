"""Rebuild the REVIEWED T-1577 subjects: journal.py and validate.py as the review saw them.

The review (E-11028) reproduced that the width-only grammar accepted any
class path over a writer width -- `verify-<32 hex>` read as canonical. The
class registry replaced that grammar in place, so this script restores the
reviewed grammar block into a copy of the live journal.py (and the reviewed
FAIL message into a copy of validate.py) by exact string replacement,
asserting each replacement applies exactly once and keeping each file's own
line ends. The result is the third subject of run_pair.py: red on the class
assertions, while the pre-fix subject is red on everything.

Run from the project root: python .saipen/evidence/T-1577-op-id-provenance/make_reviewed.py

Frozen after its first complete run (01.10.26): the live validate.py then
gained the [closure-evidence] history exemption and the exempt-WARN count
fix, which a message-only revert would carry INTO the reviewed subject. The
produced bytes are pinned below and a rerun refuses to overwrite them:
  reviewed/journal.py  237511 B  sha256 c0bb3a3a80b73684... (= the reviewed
                       file's size on disk before the registry edit)
  reviewed/validate.py 563340 B  sha256 365d2cdc88afca44... (= the reviewed
                       file's size on disk at 00:54, before any edit here)
"""
import hashlib
import sys
from pathlib import Path

PINNED = {
    "journal.py": "c0bb3a3a80b736843fb980eb695501665b43a8088e562936e5440efcd44def7c",
    "validate.py": "365d2cdc88afca444d2cf4ca951e298e7704f280ba63c118be2202cb5eda8c2a",
}
_out = Path(__file__).resolve().parent / "reviewed"
if all(
    (_out / name).is_file()
    and hashlib.sha256((_out / name).read_bytes()).hexdigest() == digest
    for name, digest in PINNED.items()
):
    print("reviewed subjects already pinned; refusing to regenerate")
    sys.exit(0)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / ".saipen" / "evidence" / "T-1577-op-id-provenance" / "reviewed"
OUT.mkdir(parents=True, exist_ok=True)
CRLF = "\r\n"
LF = "\n"


def read_lf(path: Path) -> tuple[str, str]:
    """Text with LF line ends, plus the line end the file really uses."""
    raw = path.read_bytes().decode("utf-8")
    newline = CRLF if CRLF in raw else LF
    return raw.replace(CRLF, LF), newline


def write_as(path: Path, text: str, newline: str) -> None:
    """Write with the SAME line ends as the live file (subject bytes are hashed)."""
    data = text.replace(LF, newline).encode("utf-8")
    path.write_bytes(data)
    print(f"{path.name}: {len(data)} bytes")


REVIEWED_BLOCK = '''#: The body widths the writers in this repository actually emit (T-1577).
#: Measured over every operation record on AUDAPACK (30.09.26): 32 hex
#: (`uuid4().hex`, `operations.py`), 8 hex (`subs.py` truncates its hex to
#: eight), 12 hex (`conformance.py` receipts), 16 hex (`goal-`, `source.`),
#: and 20 digits (`reconcile-` timestamps). Nothing emits 31, and nothing
#: emits 4 -- which is precisely how a hand-typed id is recognised.
OP_ID_BODY_WIDTHS = frozenset({8, 12, 16, 20, 32})

#: One grammar owner for the `[op: ...]` LOG tag. `validate_op_id` above owns
#: which ids may become an OPERATION DIRECTORY; this owns which ids may be
#: believed when they appear on a LOG LINE. A class path keeps the older
#: multi-segment writers (`crew-run-`, `ticket-verify-`, `debt.snapshot-`)
#: inside the grammar instead of redding real history.
_OP_ID_GRAMMAR = re.compile(
    r"^[a-z][a-z0-9_.]*(?:-[a-z][a-z0-9_.]*)*-(?:%s)$"
    % "|".join(r"[0-9a-f]{%d}" % width for width in sorted(OP_ID_BODY_WIDTHS))
)


def op_id_provenance('''

journal, journal_nl = read_lf(ROOT / "tools" / "saipen_engine" / "journal.py")
start = journal.index("_HEX32 = frozenset({32})\n")
end = journal.index("def op_id_provenance(", start)
assert journal.count("_HEX32 = frozenset({32})\n") == 1
assert journal.count("def op_id_provenance(") == 1
journal = journal[:start] + REVIEWED_BLOCK + journal[end + len("def op_id_provenance("):]
LIVE_DOC = (
    "    at all -- is the id a registered class (`OP_CLASSES`) over a body width\n"
    "    that class's writer emits -- so every consumer of a LOG tag can ask it:\n"
    "    the validator when it reports, and `log.verification_evidence` when it\n"
    "    decides whether an event counts.\n"
)
REVIEWED_DOC = (
    "    at all -- does the id have the shape a writer emits -- so every consumer\n"
    "    of a LOG tag can ask it: the validator when it reports, and\n"
    "    `log.verification_evidence` when it decides whether an event counts.\n"
)
assert journal.count(LIVE_DOC) == 1
journal = journal.replace(LIVE_DOC, REVIEWED_DOC)
assert "OP_CLASSES" not in journal
write_as(OUT / "journal.py", journal, journal_nl)

# validate.py: only the FAIL message named the reviewed grammar.
LIVE_MESSAGE = (
    '                    "repository emits (unregistered class or body width, "\n'
    '                    "journal.OP_CLASSES) "\n'
)
REVIEWED_MESSAGE = (
    '                    "repository emits (measured body widths 8/12/16/20/32 hex) "\n'
)
validate, validate_nl = read_lf(ROOT / "tools" / "validate.py")
assert validate.count(LIVE_MESSAGE) == 1
validate = validate.replace(LIVE_MESSAGE, REVIEWED_MESSAGE)
write_as(OUT / "validate.py", validate, validate_nl)
