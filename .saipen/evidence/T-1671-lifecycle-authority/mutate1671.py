"""Red controls for the T-1671/T-1672 lifecycle-authority gate.

Usage: mutate1671.py <repo> <copy>

VERIFY-ORACLE-01: a gate that cannot fail is not a gate. The copy is a
disposable tree without the repository's .git and .saipen. Each mutation
removes ONE property the Work delivers; the named tests of
tools/test_t1671_lifecycle_authority.py must go red in every repetition, and a
test red in some repetitions only is reported as unstable. The unmutated
control and every mutation run three times (template: mutate1304.py; a control
run once counts a coin flip).
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
copy = Path(sys.argv[2]).resolve()
assert repo != copy and repo not in copy.parents and not copy.exists(), copy

ROOT_ONLY = {".git", ".saipen", ".workbuddy-ai", ".codenomad", ".freebuff", ".claude",
             "future_gate", "audit", "locales", "guides"}
ANYWHERE = {"__pycache__", ".pytest_cache", ".ruff_cache"}


def ignore(directory: str, names: list[str]) -> list[str]:
    at_root = Path(directory).resolve() == repo
    return [
        n for n in names
        if n in ANYWHERE or n.endswith(".pyc") or (at_root and n in ROOT_ONLY)
    ]


shutil.copytree(repo, copy, ignore=ignore)

MODULE = "test_t1671_lifecycle_authority"
LA = "tools/saipen_engine/lifecycle_authority.py"
OPS = "tools/saipen_engine/operations.py"
REC = "tools/saipen_engine/reconcile.py"
CLI = "tools/saipen.py"
VAL = "tools/validate.py"

TYPED = "test_a_typed_completion_is_refused_by_every_entry_and_writes_nothing"
RECOVERY = "test_recovery_reopens_the_typed_closure_and_keeps_every_original_byte"
MARKER = "test_a_marker_moved_by_hand_alone_is_reconciled_by_one_journaled_event"
LEDGERLESS = "test_a_checkout_without_a_ledger_is_unavailable_not_accused"
U_UNAVAILABLE = "test_no_ledger_and_no_resolvable_event_are_both_unavailable"
U_NOTE = "test_a_canonical_closure_with_a_later_typed_note_is_authorized"
U_EPOCH = "test_a_closure_before_a_fresh_claim_does_not_back_a_typed_completion"
U_FORGED = "test_an_id_in_the_registered_grammar_with_no_record_is_part_of_the_head"
U_TARGET = "test_a_ticket_named_only_as_a_target_is_still_named"
LAW_OPS = "test_ops_names_no_manual_fallback"
LAW_BLOCK = "test_the_activation_block_forbids_the_hand_checkpoint_it_used_to_order"

UNAUTHORIZED_IF = 'if lifecycle["status"] == _lifecycle_authority.UNAUTHORIZED:\n'
STATUS_IF = 'if _lifecycle["status"] == _lifecycle_authority.UNAUTHORIZED:\n        _emit(\n'
VALIDATOR_IF = 'if _lifecycle["status"] == _lifecycle_authority.UNAUTHORIZED:\n            fail(\n'

MUTATIONS = [
    (
        "M1 the loader no longer refuses an unauthorized head",
        OPS,
        [(UNAUTHORIZED_IF, "if False:\n")],
        [TYPED, MARKER],
    ),
    (
        "M2 status projects the typed state as healthy",
        CLI,
        [(STATUS_IF, "if False:\n        _emit(\n")],
        [TYPED, MARKER],
    ),
    (
        "M3 the validator says nothing about it",
        VAL,
        [(VALIDATOR_IF, "if False:\n            fail(\n")],
        [TYPED],
    ),
    (
        "M4 reconciliation plans no repair for it",
        REC,
        [(
            "    if not verdict or verdict.get(\"status\") != _la.UNAUTHORIZED:\n        return plan\n",
            "    if True:\n        return plan\n",
        )],
        [RECOVERY, MARKER],
    ),
    (
        "M5 the floor believes any tag, resolved or not",
        LA,
        [("        if resolves(event.get(\"op_id\")):\n", "        if event.get(\"op_id\"):\n")],
        [U_FORGED],
    ),
    (
        "M6 a closure before a fresh claim still backs the ticket",
        LA,
        [(
            "    return any(number >= epoch for number in closures)\n",
            "    return bool(closures)\n",
        )],
        [U_EPOCH],
    ),
    (
        "M7 a marker above the floor is no finding",
        LA,
        [(
            "and not isinstance(last_event, bool) and last_event > floor:\n",
            "and not isinstance(last_event, bool) and False:\n",
        )],
        [TYPED, MARKER, U_NOTE, U_FORGED],
    ),
    (
        "M8 a typed completion is no finding",
        LA,
        [(
            "        if not isinstance(row, dict) or row.get(\"section\") != \"## DONE\":\n",
            "        if True:\n",
        )],
        [TYPED, RECOVERY, U_EPOCH, U_FORGED, U_TARGET],
    ),
    (
        "M9 the recovery keeps no copy of the typed bytes",
        REC,
        [("    if gap or authority[\"trace\"]:\n", "    if gap:\n")],
        [RECOVERY],
    ),
    (
        "M10 a checkout with no resolvable event is accused",
        LA,
        [(
            "    if floor is None:\n        return verdict\n",
            "    if floor is None:\n        floor = 0\n",
        )],
        [U_UNAVAILABLE],
    ),
    (
        "M11 a ticket named only as a target is not named",
        LA,
        [(
            "        tickets = {event.get(\"ticket\")} | set(_TARGET_RE.findall(event.get(\"text\") or \"\"))\n",
            "        tickets = {event.get(\"ticket\")}\n",
        )],
        [U_TARGET],
    ),
    (
        "M12 finish_ticket loses its refusal guard",
        OPS,
        [("\n\n@_state_guard\ndef finish_ticket(\n", "\n\ndef finish_ticket(\n")],
        [TYPED],
    ),
    (
        "M13 OPS 8 licenses the manual protocol again",
        "saipen/OPS.md",
        [(
            "None (SRC-192: an executor without `saipen` typed STATE, BOARD and LOG by\n",
            "If Python is unavailable, use the documented manual protocol; an executor\n"
            "typed STATE, BOARD and LOG by\n",
        )],
        [LAW_OPS],
    ),
    (
        "M14 the activation block orders the hand checkpoint again",
        "saipen/ACTIVATION_BLOCK.md",
        [(
            "BOARD, LOG change only via `saipen`. No route to it: stop, report\n",
            "checkpoint BOARD + STATE after every ticket, LOG line after every run.\n",
        )],
        [LAW_BLOCK],
    ),
]


def edit(rel: str, edits: list[tuple[str, str]], label: str) -> bytes:
    """Apply exact single-occurrence edits to the copy; return the copy's prior bytes."""
    target = copy / rel
    original = target.read_bytes()
    newline = "\r\n" if b"\r\n" in original else "\n"
    text = original.decode("utf-8")
    for old, new in edits:
        old, new = old.replace("\n", newline), new.replace("\n", newline)
        assert text.count(old) == 1, (label, text.count(old), old[:70])
        text = text.replace(old, new)
    target.write_bytes(text.encode("utf-8"))
    return original


def run() -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", MODULE],
        cwd=str(copy / "tools"), env=env, stdin=subprocess.DEVNULL, capture_output=True,
        timeout=1800, check=False,
    )
    return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", errors="replace")


def red_names(out: str) -> frozenset[str]:
    return frozenset(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", out, flags=re.MULTILINE))


REPEAT = 3
for attempt in range(REPEAT):
    code, out = run()
    ran = re.search(r"Ran (\d+) tests", out)
    print(f"CONTROL {attempt + 1}/{REPEAT} unmutated copy: exit {code}, "
          f"{ran.group(0) if ran else out[-300:]}", flush=True)
    assert code == 0, out[-3000:]

undetected = 0
unstable = 0
unexpected = 0
for label, rel, edits, expected in MUTATIONS:
    original = edit(rel, edits, label)
    runs = [run() for _ in range(REPEAT)]
    (copy / rel).write_bytes(original)
    reds = [red_names(out) for _code, out in runs]
    always = frozenset.intersection(*reds)
    sometimes = frozenset.union(*reds) - always
    missing = sorted(set(expected) - always)
    detected = bool(always) and all(code != 0 for code, _out in runs) and not missing
    undetected += 0 if detected else 1
    unstable += 1 if sometimes else 0
    extra = sorted(always - set(expected))
    unexpected += 1 if extra else 0
    print(f"{label}: {'DETECTED' if detected else 'NOT DETECTED'} in {REPEAT} of {REPEAT}",
          flush=True)
    for name in sorted(always):
        print(f"      red: {name}" + ("" if name in expected else "  (not named for this mutation)"))
    for name in missing:
        print(f"      EXPECTED RED, STAYED GREEN: {name}")
    for name in sorted(sometimes):
        print(f"      UNSTABLE (red in some of {REPEAT} runs only): {name}")
print(f"restored; mutations {len(MUTATIONS)}, undetected {undetected}, "
      f"mutations with an unstable test {unstable}, "
      f"mutations with a red test not named for them {unexpected}")
raise SystemExit(1 if undetected or unstable else 0)
