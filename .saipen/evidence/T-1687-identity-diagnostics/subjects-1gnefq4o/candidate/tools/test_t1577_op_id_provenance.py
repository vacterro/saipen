"""Hand-authored `[op: ...]` provenance (T-1577).

The `[op: ...]` LOG tag is a bracket someone typed until T-1282 started
comparing it against the journaled operation records on the checkout. That
gate answers ONE question -- "does this id name a record on THIS disk" -- and
it answers it only for ids above the resolved floor, so it never reaches the
half that decides the outcome of a ticket.

Measured on AUDAPACK (30.09.26): 3978 op ids in the active LOG across 21
shapes, of which the census found `checkpoint-qq2-saitranslate-<stamp>`,
bare 32-hex ids with no class, and `buildcp<stamp>` -- none of which resolve,
all of them at or below the resolved floor, so T-1282 keeps them WARN. That is
the correct severity for history. It is the wrong answer for the CURRENT
cycle, because `verification_evidence`, `bulk_verification_evidence` and
`regression_evidence` all decide on `event["text"]` and `taxonomy` and never
once read `op_id`: a hand-authored `transition to VERIFY` followed by a
hand-authored `PASS conf: high` is accepted today as proof that the phase
happened.

So the ticket has two halves, and both are pinned here:

- PROVENANCE. One grammar owner (`journal.op_id_provenance`). An id is
  canonical when its class is in the registry (`journal.OP_CLASSES`) and its
  body is hex of a width THAT class's writer emits -- 8 is not a shortcut,
  `subs.py` truncates to 8 and `uuid4_hex()` did until 17.08.26. The first
  cut checked the width alone, and the independent review (E-11028)
  reproduced the hole: `verify-<32 hex>` read as canonical although no writer
  mints `verify-`. Every other present id is hand-authored, and the writers
  are scanned so the registry cannot fall behind them. Nothing consults the
  ledger to DECIDE; the ledger only chooses WARN or FAIL in the validator,
  reusing T-1282's resolved floor so sealed and pre-floor history stays
  readable.
- EVIDENCE. A hand-authored event is not phase evidence and not closure
  evidence: it can neither open a VERIFY cycle nor satisfy one, in the single
  and the bulk classifier alike, and it cannot anchor a regression pair.
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import journal  # noqa: E402
from saipen_engine.log import (  # noqa: E402
    bulk_verification_evidence,
    read_history_events,
    regression_evidence,
    verification_evidence,
)
from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402

VALIDATOR = ROOT / "tools" / "validate.py"
SCENARIO = ROOT / "tests" / "scenarios" / "userperson-valid" / ".saipen"

TICKET = "T-901"

#: 31 hex, not 32. The writer bodies are 8, 12, 16, 20 or 32 hex (measured
#: over all 8574 operation records on AUDAPACK, 30.09.26); a 31-hex body is
#: outside every one of them, which is what a hand-typed id looks like.
SCOUT = "scout-7a1b2c3d4e5f60718293a4b5c6d7e8f"
BUILD = "build-1f2e3d4c5b6a7081928374655647382"
VERIFY = "verify-a0b1c2d3e4f5061728394a5b6c7d8e9"

#: The review's reproduction (E-11028): a writer's WIDTH under a class no
#: writer mints. A width-only grammar reads every one of these as canonical.
UNREGISTERED_VERIFY = "verify-a0b1c2d3e4f5061728394a5b6c7d8e9f"
UNREGISTERED_CLASSES = (
    # Measured in the field (40 SAIPEN projects, 01.10.26), every one with a
    # 32-hex body and none with a writer in this repository's history.
    "verify-",
    "scout-",
    "build-",
    "ship-",
    "dec-",
    "decision-",
    "unblock-",
    "plan-",
    "hygiene-",
    "goal_tickets-bump-0to45-",
    "markhunt-triage-verify-",
)

#: Real writer shapes, including the three a naive 32-hex rule would red.
CANONICAL_CHECKPOINT = "checkpoint-0f1e2d3c4b5a69788796a5b4c3d2e1f0"
CANONICAL_TRANSITION = "transition-11a2b3c4d5e6f708192a3b4c5d6e7f80"
LEGACY_EIGHT_HEX = "sub-collect-1a2b3c4d"
LEGACY_TIMESTAMP = "reconcile-20260927110107892326"
LEGACY_DOTTED = "debt.snapshot-0f1e2d3c4b5a"
RECEIPT_TWELVE = "receipt-a1b2c3d4e5f6"
SOURCE_THIRTY_TWO = "source.requirement_add-0f1e2d3c4b5a69788796a5b4c3d2e1f0"
#: `uuid4_hex()` returned eight hex until 17.08.26 (SAIPEN LOG-011:13).
EIGHT_HEX_ERA = "transition-3a187e34"
GOAL_INGRESS = "goal-0f1e2d3c4b5a6978"
REVERIFY_DOT = "reverify.0f1e2d3c4b5a"

PASS_TEXT = "PASS conf: high -- core gate 0 FAIL with 34 warnings; ruff clean"
BOUNDARY_TEXT = "transition to VERIFY -- work done"


def _line(event: int, op_id: str | None, text: str, taxonomy: str = "RUN") -> str:
    tag = f" [op: {op_id}]" if op_id else ""
    return (
        f"- 30.09.26 12:{event % 60:02d} [E-{event}] [T-{TICKET[2:]}] "
        f"[agent: auda]{tag} {taxonomy}: {text}\n"
    )


def _events(*rows: tuple[str | None, str]) -> list[dict]:
    """Parse real LOG lines through the real parser (no hand-built dicts)."""
    with tempfile.TemporaryDirectory(prefix="saipen-t1577-log-") as tmp:
        root = Path(tmp)
        (root / ".saipen").mkdir()
        text = "".join(_line(901 + index, op_id, body) for index, (op_id, body) in enumerate(rows))
        (root / ".saipen" / "LOG.md").write_text(text, encoding="utf-8")
        return list(read_history_events(root))


def provenance(op_id: str | None) -> str:
    """The grammar owner's answer, with an honest pre-fix fallback.

    Before T-1577 no owner existed to call, so the fixture reports what the
    pre-fix tree structurally can: a tag nothing classifies. The assertions
    below then FAIL on that -- a behavioural red with no collection error --
    instead of the module failing to import, which would be a broken verifier
    rather than evidence.
    """
    owner = getattr(journal, "op_id_provenance", None)
    return owner(op_id) if owner is not None else "absent"


class GrammarOwner(unittest.TestCase):
    """One owner decides, and it is the same owner for every caller."""

    def test_the_three_hand_written_ids_are_hand_authored(self) -> None:
        for op_id in (SCOUT, BUILD, VERIFY):
            self.assertEqual(provenance(op_id), "hand_authored", op_id)

    def test_real_writer_shapes_stay_canonical(self) -> None:
        for op_id in (
            CANONICAL_CHECKPOINT,
            CANONICAL_TRANSITION,
            LEGACY_EIGHT_HEX,
            LEGACY_TIMESTAMP,
            LEGACY_DOTTED,
            RECEIPT_TWELVE,
            SOURCE_THIRTY_TWO,
            EIGHT_HEX_ERA,
            GOAL_INGRESS,
            REVERIFY_DOT,
        ):
            self.assertEqual(provenance(op_id), "canonical", op_id)

    def test_an_unregistered_class_is_hand_authored_at_every_writer_width(self) -> None:
        """The review's reproduction: the class is the claim, not the width."""
        self.assertEqual(provenance(UNREGISTERED_VERIFY), "hand_authored")
        for prefix in UNREGISTERED_CLASSES:
            for width in (8, 12, 16, 20, 32):
                op_id = prefix + "0123456789abcdef" * 2
                op_id = op_id[: len(prefix) + width]
                self.assertEqual(provenance(op_id), "hand_authored", op_id)

    def test_a_registered_class_at_a_width_its_writer_never_emits(self) -> None:
        for op_id in (
            "checkpoint-a1b2c3d4e5f6",  # 12: no checkpoint writer ever cut to 12
            "claim-0f1e2d3c4b5a6978",  # 16
            "sub-collect-0f1e2d3c4b5a69788796a5b4c3d2e1f0",  # subs.py emits 8
            "receipt-0f1e2d3c4b5a69788796a5b4c3d2e1f0",  # conformance emits 12
            "reconcile-0f1e2d3c4b5a69788796a5b4c3d2e1f0",  # a stamp is 20
            "Transition-11a2b3c4d5e6f708192a3b4c5d6e7f80",  # case is part of it
            "transition-11A2B3C4D5E6F708192A3B4C5D6E7F80",
        ):
            self.assertEqual(provenance(op_id), "hand_authored", op_id)

    def test_the_carrier_ids_really_carry_thirty_one_hex(self) -> None:
        # Pinned so the fixture cannot drift into canonical shape by accident.
        for op_id in (SCOUT, BUILD, VERIFY):
            self.assertEqual(len(op_id.rsplit("-", 1)[1]), 31, op_id)

    def test_a_missing_tag_is_absent_not_hand_authored(self) -> None:
        """An untagged event is a different question (T-110), not this one."""
        for op_id in (None, ""):
            self.assertEqual(provenance(op_id), "absent", op_id)

    def test_other_typos_stay_hand_authored(self) -> None:
        for op_id in (
            "0f1e2d3c4b5a69788796a5b4c3d2e1f0",  # bare hex, no class
            "checkpoint",  # no body at all
            "checkpoint-zzz",  # class, no hex
            "buildcp20260910011340",  # no separator
            "board-compact-a1b2",  # 4-hex body: no writer emits one
            "checkpoint-qq2-saitranslate-20260919T2220Z",  # timestamp body
        ):
            self.assertEqual(provenance(op_id), "hand_authored", op_id)


#: Prefixes the writer scan below sees that are not op ids at all.
NOT_OP_IDS = {
    "ded-": "the STYLE contract fingerprint (state.py), a STATE field",
    "lineage-": "the project lineage id (paths.py)",
    "producer-integrate-": (
        "a run_mutation receipt id whose body is <identity>-<head>; producer.py "
        "never renders it onto a LOG line"
    ),
}

_HEX_EXPR = (
    r"(?:uuid4_hex\(\)|uuid\.uuid4\(\)|__import__\(\"uuid\"\)|hash_bytes\(|"
    r"hashlib\.|_hex8\(\)|digest\[|dt\.datetime|datetime\.datetime)"
)
#: `"<prefix>" + <hex producer>`, the shape every literal writer uses.
_LITERAL_WRITER = re.compile(r'"([a-z][a-z0-9_.-]*[-.])"\)?\s*\+\s*' + _HEX_EXPR)
#: `f"<prefix>{<hex producer>...}"`.
_FSTRING_WRITER = re.compile(r'f"([a-z][a-z0-9_.-]*[-.])\{(?:uuid|_hex8|hash_bytes|uuid4_hex)')
#: The first literal of an `op_id = ...` statement, whatever follows it --
#: unless a NAME is spliced in next (`"attempt-" + action + "-"`), which is a
#: named class `_minted_dynamic_prefixes` expands instead.
_OP_ID_ASSIGNMENT = re.compile(
    r'\b(?:op_id|operation_id|epoch_op_id)\s*=\s*\(*\s*"([a-z][a-z0-9_.-]*[-.])"'
    r"(?!\s*\+\s*[a-z_]+\s*\+)"
)


def _writer_sources() -> list[Path]:
    return sorted(
        path
        for path in (ROOT / "tools").rglob("*.py")
        if not path.name.startswith("test_") and "__pycache__" not in path.parts
    )


def _minted_literal_prefixes() -> dict[str, str]:
    """Every literal op-id prefix a writer mints, with one place it does."""
    found: dict[str, str] = {}
    for path in _writer_sources():
        text = path.read_text(encoding="utf-8")
        for pattern in (_LITERAL_WRITER, _FSTRING_WRITER, _OP_ID_ASSIGNMENT):
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                found.setdefault(match.group(1), f"{path.relative_to(ROOT)}:{line}")
    return found


def _call_name(node: ast.Call) -> str:
    func = node.func
    return func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")


def _minted_dynamic_prefixes() -> dict[str, str]:
    """The prefixes a writer builds from a NAME rather than a literal.

    `_state_only_plan(root, "<operation>", ...)` and `build_plan(operation=...)`
    mint `<operation>-<hex>` when no `op_id=` is passed; `_journaled_write`
    (improve.py) mints `<kind>-<hex>`; `_plan_attempt` mints
    `attempt-<open|close>-<hex>`; `_plan_directive` mints `<kind>-intake-`.
    """
    from saipen_engine.state import STATE_CONVERGE_TARGETS

    found: dict[str, str] = {}

    def names(node: ast.expr | None) -> list[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]
        if isinstance(node, ast.JoinedStr):
            head = "".join(part.value for part in node.values if isinstance(part, ast.Constant))
            if head == "finalize_":
                return [head + target for target in STATE_CONVERGE_TARGETS]
        return []

    for path in _writer_sources():
        text = path.read_text(encoding="utf-8")
        where = str(path.relative_to(ROOT))
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.Call):
                continue
            keywords = {kw.arg: kw.value for kw in node.keywords}
            name = _call_name(node)
            if name == "_state_only_plan" and "op_id" not in keywords:
                operation = node.args[1] if len(node.args) > 1 else keywords.get("operation")
            elif name == "build_plan" and "op_id" not in keywords:
                operation = keywords.get("operation")
            elif name == "_journaled_write":
                operation = node.args[2] if len(node.args) > 2 else keywords.get("kind")
            else:
                continue
            for value in names(operation):
                found.setdefault(value + "-", f"{where}:{node.lineno}")
        if '("attempt-" + action + "-")' in text:
            for action in ("open", "close"):  # attempt_lifecycle's closed set
                found.setdefault(f"attempt-{action}-", where)
        kinds = re.search(r"if kind not in (\{[^}]*\}):", text)
        if 'f"{kind}-intake-"' in text and kinds:
            for kind in ast.literal_eval(kinds.group(1)):
                found.setdefault(f"{kind}-intake-", where)
    return found


class RegistryCoversEveryWriter(unittest.TestCase):
    """A writer cannot mint a class the grammar has never heard of.

    The registry is only as good as its agreement with the writers, so the
    writers are read, not remembered: a new `"<class>-" + uuid4_hex()` fails
    here until its class is registered in the same change.
    """

    def registry(self) -> dict:
        return getattr(journal, "OP_CLASSES", {})

    def assert_registered(self, minted: dict[str, str]) -> None:
        missing = {
            prefix: where
            for prefix, where in minted.items()
            if prefix not in self.registry() and prefix not in NOT_OP_IDS
        }
        self.assertEqual(missing, {}, "writer mints an unregistered op class")

    def test_every_literal_writer_class_is_registered(self) -> None:
        minted = _minted_literal_prefixes()
        # The scan must still SEE the writers, or it proves nothing.
        for anchor in ("claim-", "transition-", "sub-collect-", "reconcile-", "reverify."):
            self.assertIn(anchor, minted)
        self.assert_registered(minted)

    def test_every_named_writer_class_is_registered(self) -> None:
        minted = _minted_dynamic_prefixes()
        for anchor in ("goal-", "valve-", "finalize_done-", "attempt-open-", "cut-intake-"):
            self.assertIn(anchor, minted)
        self.assert_registered(minted)

    def test_every_registered_class_has_a_live_writer(self) -> None:
        """The converse: registering `verify-` would launder every typed id.

        A class earns its place by a writer that mints it today, so the
        registry can neither be padded with a hand-typed class nor keep one
        whose writer is gone.
        """
        registry = self.registry()
        self.assertTrue(registry)
        minted = {**_minted_literal_prefixes(), **_minted_dynamic_prefixes()}
        self.assertEqual(sorted(set(registry) - set(minted)), [])

    def test_no_registered_class_is_an_unregistered_one_in_disguise(self) -> None:
        registry = self.registry()
        self.assertTrue(registry)
        for prefix in UNREGISTERED_CLASSES:
            self.assertNotIn(prefix, registry)
        for prefix, widths in registry.items():
            self.assertRegex(prefix, r"^[a-z][a-z0-9_.-]*[-.]$")
            self.assertTrue(widths and all(8 <= width <= 32 for width in widths), prefix)


class PhaseEvidence(unittest.TestCase):
    def test_an_unregistered_class_pass_is_not_phase_evidence(self) -> None:
        events = _events(
            (CANONICAL_TRANSITION, BOUNDARY_TEXT),
            (UNREGISTERED_VERIFY, PASS_TEXT),
        )
        ok, reason = verification_evidence(TICKET, events)
        self.assertFalse(ok, reason)
        self.assertEqual(bulk_verification_evidence(events, [TICKET])[TICKET], (ok, reason))

    def test_a_hand_authored_pass_is_not_phase_evidence(self) -> None:
        events = _events(
            (CANONICAL_CHECKPOINT, BOUNDARY_TEXT),
            (VERIFY, PASS_TEXT),
        )
        ok, reason = verification_evidence(TICKET, events)
        self.assertFalse(ok, reason)

    def test_a_hand_authored_boundary_opens_no_cycle(self) -> None:
        """The boundary is itself evidence of the transition (CORE-001)."""
        events = _events(
            (VERIFY, BOUNDARY_TEXT),
            (CANONICAL_CHECKPOINT, PASS_TEXT),
        )
        ok, reason = verification_evidence(TICKET, events)
        self.assertFalse(ok, reason)
        self.assertIn("boundary", reason.lower())

    def test_canonical_evidence_still_verifies(self) -> None:
        events = _events(
            (CANONICAL_TRANSITION, BOUNDARY_TEXT),
            (CANONICAL_CHECKPOINT, PASS_TEXT),
        )
        ok, reason = verification_evidence(TICKET, events)
        self.assertTrue(ok, reason)

    def test_the_bulk_classifier_agrees_byte_for_byte(self) -> None:
        for rows in (
            ((CANONICAL_CHECKPOINT, BOUNDARY_TEXT), (VERIFY, PASS_TEXT)),
            ((VERIFY, BOUNDARY_TEXT), (CANONICAL_CHECKPOINT, PASS_TEXT)),
            (
                (CANONICAL_TRANSITION, BOUNDARY_TEXT),
                (CANONICAL_CHECKPOINT, PASS_TEXT),
            ),
        ):
            events = _events(*rows)
            single = verification_evidence(TICKET, events)
            bulk = bulk_verification_evidence(events, [TICKET])[TICKET]
            self.assertEqual(single, bulk, rows)

    def test_a_hand_authored_fail_is_not_a_veto_either(self) -> None:
        """Filtered means IGNORED, not merely distrusted.

        A hand-authored line may neither pass a cycle nor block one; a class
        the grammar does not know is not a verdict in either direction. The
        canonical line still decides, and the validator still WARNs about it.
        """
        events = _events(
            (CANONICAL_TRANSITION, BOUNDARY_TEXT),
            (VERIFY, "verify -> FAIL core gate red"),
            (CANONICAL_CHECKPOINT, PASS_TEXT),
        )
        ok, reason = verification_evidence(TICKET, events)
        self.assertTrue(ok, reason)
        self.assertEqual(reason, PASS_TEXT)


class ClosureEvidence(unittest.TestCase):
    def _pair(self, op_id: str) -> list[dict]:
        return _events(
            (CANONICAL_TRANSITION, BOUNDARY_TEXT),
            (
                op_id,
                "REGRESSION-EVIDENCE FAIL "
                "verifier:aaaaaaaabbbbbbbbccccccccdddddddd subject:1111111122222222"
                "3333333344444444 -- run",
            ),
            (
                op_id,
                "REGRESSION-EVIDENCE PASS "
                "verifier:aaaaaaaabbbbbbbbccccccccdddddddd subject:5555555566666666"
                "7777777788888888 -- run",
            ),
        )

    def test_a_hand_authored_anchor_is_not_closure_evidence(self) -> None:
        ok, reason = regression_evidence(TICKET, self._pair(BUILD))
        self.assertFalse(ok, reason)

    def test_a_canonical_anchor_still_closes(self) -> None:
        ok, reason = regression_evidence(TICKET, self._pair(CANONICAL_CHECKPOINT))
        self.assertTrue(ok, reason)


class ValidatorGate(unittest.TestCase):
    """The validator names the ids; the resolved floor decides the severity."""

    @staticmethod
    def _failed_with(out: str, op_id: str) -> list[str]:
        return [line for line in out.splitlines() if "FAIL" in line and op_id in line]

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="saipen-t1577-val-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "AUDAPACK"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        from test_fixture_support import restamp_live_style

        restamp_live_style(self.root / ".saipen")
        self.base = self._append((CANONICAL_CHECKPOINT, "checkpoint on disk"))
        # The one operation record on this checkout: it sets the floor.
        record = self.root / ".saipen" / "recovery" / "ops" / CANONICAL_CHECKPOINT
        record.mkdir(parents=True)
        (record / "operation.json").write_text("{}", encoding="utf-8")

    def _append(self, *rows: tuple[str | None, str]) -> int:
        path = self.root / ".saipen" / "LOG.md"
        last = max((ev["event"] for ev in read_history_events(self.root)), default=0)
        with path.open("a", encoding="utf-8") as handle:
            for index, (op_id, body) in enumerate(rows):
                handle.write(_line(last + 1 + index, op_id, body))
        return last + len(rows)

    def _run(self) -> str:
        done = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                "--project-root",
                str(self.root),
                "--gate",
                "core",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=hermetic_env(),
            timeout=300,
        )
        return done.stdout + done.stderr

    def test_a_hand_authored_id_above_the_floor_is_named_and_fails(self) -> None:
        self._append((VERIFY, PASS_TEXT))
        out = self._run()
        self.assertIn("hand-authored", out)
        self.assertTrue(self._failed_with(out, VERIFY), out)

    def test_an_unregistered_class_above_the_floor_is_named_and_fails(self) -> None:
        """The review's reproduction, end to end through the validator."""
        self._append((UNREGISTERED_VERIFY, PASS_TEXT))
        out = self._run()
        self.assertTrue(self._failed_with(out, UNREGISTERED_VERIFY), out)
        self.assertIn("unregistered class", out)

    def test_a_hand_authored_id_below_the_floor_only_warns(self) -> None:
        """History stays readable: the record that follows sets the floor."""
        self._append((SCOUT, PASS_TEXT))
        self._append((CANONICAL_CHECKPOINT, "later, resolvable"))
        out = self._run()
        self.assertFalse(self._failed_with(out, SCOUT), out)

    def test_a_hand_authored_id_that_resolves_is_not_claimed(self) -> None:
        """A real operation record outranks the shape: no false accusation."""
        forged = "checkpoint-qq2-stamp-repair-20260919T2220Z"
        record = self.root / ".saipen" / "recovery" / "ops" / forged
        record.mkdir(parents=True)
        (record / "operation.json").write_text("{}", encoding="utf-8")
        self._append((forged, PASS_TEXT))
        self._append((VERIFY, PASS_TEXT))
        out = self._run()
        self.assertFalse(self._failed_with(out, forged), out)
        self.assertTrue(self._failed_with(out, VERIFY), out)

    def test_no_ledger_means_unavailable_not_red(self) -> None:
        shutil.rmtree(self.root / ".saipen" / "recovery")
        self._append((VERIFY, PASS_TEXT))
        out = self._run()
        self.assertFalse(self._failed_with(out, VERIFY), out)

    # A DONE ticket whose whole VERIFY cycle was typed (AUDAPACK T-25 and
    # T-134..T-138, measured 01.10.26): the classifier now ignores that
    # evidence, so [closure-evidence] must tell history from a current claim
    # by the same resolved floor -- WARN below it, FAIL above it.

    def _typed_done_ticket(self) -> None:
        board = self.root / ".saipen" / "BOARD.md"
        text = board.read_text(encoding="utf-8")
        board.write_text(
            text.replace(
                "## DONE\n",
                f"## DONE\n- [x] {TICKET} [P2] closed on typed evidence | verify: proof\n",
            ),
            encoding="utf-8",
        )
        self._append(
            (UNREGISTERED_VERIFY, BOUNDARY_TEXT),
            (UNREGISTERED_VERIFY, PASS_TEXT),
        )

    @staticmethod
    def _closure_failed(out: str) -> list[str]:
        return [
            line
            for line in out.splitlines()
            if line.startswith("FAIL") and f"closure-evidence -- ticket {TICKET}" in line
        ]

    def test_a_typed_closure_below_the_floor_is_named_not_failed(self) -> None:
        self._typed_done_ticket()
        self._append((CANONICAL_CHECKPOINT, "later, resolvable"))
        out = self._run()
        self.assertEqual(self._closure_failed(out), [], out)
        warned = [
            line
            for line in out.splitlines()
            if "[hand-authored-closure-evidence]" in line and TICKET in line
        ]
        self.assertTrue(warned, out)

    def test_a_typed_closure_above_the_floor_still_fails(self) -> None:
        self._typed_done_ticket()
        out = self._run()
        self.assertTrue(self._closure_failed(out), out)
        self.assertNotIn("[hand-authored-closure-evidence]", out)


def setUpModule() -> None:
    isolate_host_session()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
