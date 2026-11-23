"""Apply the T-1771 change to tools/saipen_engine/regression_execution.py.

    python -B apply_t1771.py <root> [--check]

`execute_pair` derives the request clause of every linked request receipt
that has none yet (`intake.ensure_request_clause`, the same derivation the
closure path performs) BEFORE it binds the receipts' Contract digests, so the
finish that follows the measurement no longer moves the binding it checks.
A Contract changed for any other reason after the measurement still refuses
STALE_REGRESSION_EVIDENCE. Additive only; refuses unless every anchor is
found exactly once. Keeps line endings.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
SUBJECT = ROOT / "tools/saipen_engine/regression_execution.py"

CALL_ANCHOR = (
    '        if str(board["tickets"][ticket].get("fields", {}).get("regression")) != "required":\n'
    "            return ops._refuse(\n"
    '                "INCOMPLETE_TICKET", "declare the regression requirement before execution"\n'
    "            )\n"
    "        binding = _binding(root, ticket, agent, docs, state)\n"
)
CALL_NEW = (
    '        if str(board["tickets"][ticket].get("fields", {}).get("regression")) != "required":\n'
    "            return ops._refuse(\n"
    '                "INCOMPLETE_TICKET", "declare the regression requirement before execution"\n'
    "            )\n"
    '        if not dry_run and state.get("phase") == "VERIFY":\n'
    "            if _derive_request_clauses(root, board, ticket):\n"
    "                docs, state, board, tail = ops._read(root)\n"
    "        binding = _binding(root, ticket, agent, docs, state)\n"
)

DEF_ANCHOR = "@ops._state_guard\ndef execute_pair(project_root, ticket, agent, contract_path, *, dry_run=False):\n"
DEF_ADD = '''def _derive_request_clauses(root, board, ticket):
    """Derive the request clause a linked request receipt still lacks (T-1771).

    The binding below freezes each linked receipt's Contract digest. A receipt
    captured by `saipen user-request` holds no clause until its request clause
    is derived, and the closure path derives it (`ensure_request_clause`) --
    after the measurement -- so the first finish moved the binding it checked
    and refused STALE_REGRESSION_EVIDENCE, with no way back to VERIFY but a
    rebuild (_SAIRELAY T-8; SRC-248 R004). The clause is the operator's own
    request text and is derived the same way wherever it is derived; deriving
    it before the binding is taken measures the Contract the finish will read.
    Returns whether anything was written.
    """
    from . import intake

    fields = board["tickets"][ticket].get("fields", {})
    derived = False
    for receipt_id in sorted(set(re.findall(r"SRC-\\d+", str(fields.get("source_receipts", ""))))):
        contract = intake._read_contract(root, receipt_id) or {}
        if contract.get("clauses"):
            continue
        result = intake.ensure_request_clause(root, receipt_id)
        derived = derived or result.get("code") == "REQUIREMENT_ADDED"
    return derived


'''


def main() -> int:
    raw = SUBJECT.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if "def _derive_request_clauses(" in text:
        print("ALREADY_APPLIED")
        return 0
    for anchor in (CALL_ANCHOR, DEF_ANCHOR):
        if text.count(anchor) != 1:
            print(f"ABORT: anchor found {text.count(anchor)} times: {anchor.strip()[:60]!r}")
            return 1
    text = text.replace(CALL_ANCHOR, CALL_NEW).replace(DEF_ANCHOR, DEF_ADD + DEF_ANCHOR)
    if "--check" in sys.argv:
        print("CHECK OK: anchors match once; nothing written")
        return 0
    SUBJECT.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print(f"patched {SUBJECT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
