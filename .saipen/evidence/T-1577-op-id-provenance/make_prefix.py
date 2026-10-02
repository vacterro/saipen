"""Build the T-1577 pre-fix SUBJECTS from the live tree (VERIFY-ORACLE-01).

The three subject files carry a large uncommitted T-1572-era delta, so
`HEAD:` is NOT their pre-fix content. The pre-fix subject is defined instead
as "the live tree with exactly the T-1577 hunks removed", and this script
performs those removals by exact string replacement, asserting that each one
applied exactly once -- so a subject that silently drifts into the post-fix
tree cannot be produced.

Run from the project root: python .saipen/evidence/T-1577-op-id-provenance/make_prefix.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / ".saipen" / "evidence" / "T-1577-op-id-provenance" / "pre-fix"
OUT.mkdir(parents=True, exist_ok=True)

JOURNAL_BLOCK = '''#: The body widths the writers in this repository actually emit (T-1577).'''

LOG_FILTERS = '''            and not _hand_authored(ev)
'''

def cut(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[:start] + text[end:]


def write(name: str, text: str) -> None:
    (OUT / name).write_text(text, encoding="utf-8")
    print(f"{name}: {len(text)} bytes")


journal = (ROOT / "tools" / "saipen_engine" / "journal.py").read_text(encoding="utf-8")
journal = cut(
    journal, JOURNAL_BLOCK, "def resolvable_op_ids(root: Path | str) -> set[str]:",

)
assert JOURNAL_BLOCK not in journal
write("journal.py", journal)

log_text = (ROOT / "tools" / "saipen_engine" / "log.py").read_text(encoding="utf-8")
log_text = cut(
    log_text, "def _hand_authored(event: dict) -> bool:",
    "def regression_evidence(ticket_id: str, events: list[dict]) -> tuple[bool, str]:",

)
for fragment, replacement, expected in (
    (LOG_FILTERS, "", 1),
    ("        if _hand_authored(ev):\n            continue\n", "", 2),
    (
        "        if _hand_authored(ev):\n"
        "            continue  # T-1577: same IGNORED rule the single-ticket path applies\n",
        "",
        1,
    ),
    (
        "            if not _hand_authored(ev) and _is_verify_boundary(ev):\n",
        "            if _is_verify_boundary(ev):\n",
        1,
    ),
):
    assert log_text.count(fragment) == expected, (fragment, log_text.count(fragment))
    log_text = log_text.replace(fragment, replacement)
assert "_hand_authored" not in log_text
write("log.py", log_text)

validate_text = (ROOT / "tools" / "validate.py").read_text(encoding="utf-8")
validate_text = cut(
    validate_text,
    "    # T-1577: T-1282 above proves an id resolves to a record.",
    "    # [gate-closure] (NITRO dogfood IV, T-602)",

)
assert "T-1577: T-1282 above" not in validate_text
assert "op_id_provenance as _op_id_provenance" not in validate_text
write("validate.py", validate_text)