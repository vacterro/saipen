"""T-1759: only a reader that repairs an unauthorized head may look past it.

`operations._read` refuses an unauthorized lifecycle head so that no later
operation builds on it and buries it under a new floor (T-1671). A reader
looks past the refusal by naming the class in `observe=`, and the readers that
do are the ones that repair or quarantine that head.

On 2026-10-13 a session working on another project edited the engine in place:
`reconcile.resolve_duplicate_id` named the class too. An operator's
duplicate-id decision then committed over a hand-typed closure, and the
lifecycle verdict turned from UNAUTHORIZED to AUTHORIZED with the typed rows
still on the BOARD (.saipen/evidence/foreign-edit-20261014-reconcile/).

Two halves: the behaviour on that shape, and the closed list of readers that
name the class, so the next widening fails here instead of shipping.

T-1761 widened it once, on purpose: the refusal left a typed head that also
duplicated an id with no way out, so the decision reads past the head again
and carries what it read past. The behaviour case pins that nothing is buried.
"""

from __future__ import annotations

import ast
import shutil
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_t1671_lifecycle_authority as typed  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

from saipen_engine import lifecycle_authority, operations, reconcile  # noqa: E402
from saipen_engine.board import duplicate_records  # noqa: E402

DUPLICATE = (
    "- [ ] T-050 [P2] first record of the duplicated id | verify: probe\n"
    "- [ ] T-050 [P2] second record of the duplicated id | verify: probe\n"
)

#: Every reader that names the lifecycle class, and why it may: each one
#: repairs or quarantines the head it looks at. A new entry is a design
#: decision about recovery authority, never a convenience.
LIFECYCLE_OBSERVERS = {
    ("saipen_engine/reconcile.py", "reconcile_protocol_state"),
    ("saipen_engine/reconcile.py", "_foreign_tail_route"),
    ("saipen_engine/operations.py", "quarantine_log_tail"),
    # T-1761: the duplicate-id decision is what every later repair waits for.
    # It may look because it carries the rows that head closed into its own
    # event (`lifecycle_authority.carry_note`), so nothing is buried under it.
    ("saipen_engine/reconcile.py", "resolve_duplicate_id"),
}


def setUpModule() -> None:
    isolate_host_session()


def _names_the_class(expression: ast.expr) -> bool:
    """Could this `observe=` value carry the lifecycle class?

    Fails closed: a value is free of the class only when it is built from
    string constants and from tuples `operations` defines, and none of them
    holds it. Anything this cannot resolve counts as naming it.
    """
    if isinstance(expression, ast.Constant):
        return expression.value == lifecycle_authority.OBSERVABLE
    if isinstance(expression, ast.Starred):
        return _names_the_class(expression.value)
    if isinstance(expression, ast.Tuple):
        return any(_names_the_class(item) for item in expression.elts)
    if isinstance(expression, ast.Name):
        value = getattr(operations, expression.id, None)
        if isinstance(value, tuple):
            return lifecycle_authority.OBSERVABLE in value
    return True


def _lifecycle_observers() -> set:
    found = set()
    sources = [*sorted((TOOLS / "saipen_engine").glob("*.py")), TOOLS / "saipen.py",
               TOOLS / "validate.py"]
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(function):
                if not isinstance(node, ast.Call):
                    continue
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name != "_read":
                    continue
                for keyword in node.keywords:
                    if keyword.arg == "observe" and _names_the_class(keyword.value):
                        found.add((path.relative_to(TOOLS).as_posix(), function.name))
    return found


class DuplicateDecisionOnATypedHeadTests(unittest.TestCase):
    def setUp(self):
        self.root = typed._project()
        self.addCleanup(shutil.rmtree, self.root, True)
        board = self.root / ".saipen" / "BOARD.md"
        text = board.read_text(encoding="utf-8")
        self.assertEqual(text.count("## TODO\n"), 1, text)
        board.write_text(
            text.replace("## TODO\n", "## TODO\n" + DUPLICATE), encoding="utf-8", newline="\n"
        )

    def decide(self) -> dict:
        board = (self.root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        records = duplicate_records(board, "T-050")
        self.assertEqual(len(records), 2, records)
        return reconcile.resolve_duplicate_id(
            self.root, typed.AGENT, "T-050", records[0]["digest"], records[1]["digest"]
        )

    def verdict(self) -> str:
        docs, _state, _board, _tail = operations._read(
            self.root, observe=operations.TYPED_HEAD_QUARANTINE_OBSERVABLE
        )
        return docs["_lifecycle"]["status"]

    def rows(self) -> list:
        docs, _state, _board, _tail = operations._read(
            self.root, observe=operations.TYPED_HEAD_QUARANTINE_OBSERVABLE
        )
        return sorted({f["ticket"] for f in docs["_lifecycle"]["findings"] if f.get("ticket")})

    def test_the_decision_over_a_typed_head_buries_nothing(self):
        # T-1759 pinned a refusal here; T-1761 found that refusal left no way
        # out. The decision executes, and what made the head unauthorized is
        # still judged afterwards: looking past is allowed, burying is not.
        typed._type_the_lifecycle(self.root)
        self.assertEqual(self.verdict(), lifecycle_authority.UNAUTHORIZED)
        typed_rows = self.rows()
        self.assertEqual(typed_rows, ["T-001"])
        answer = self.decide()
        self.assertTrue(answer.get("ok"), answer)
        self.assertEqual(answer.get("code"), "DUPLICATE_ID_RESOLVED", answer)
        self.assertEqual(self.verdict(), lifecycle_authority.UNAUTHORIZED)
        self.assertEqual(self.rows(), typed_rows)

    def test_the_decision_executes_on_a_head_operations_wrote(self):
        # The control: the same duplicate, no typed lifecycle. Without it the
        # case above could pass on a decision that never executes at all.
        self.assertNotEqual(self.verdict(), lifecycle_authority.UNAUTHORIZED)
        answer = self.decide()
        self.assertTrue(answer.get("ok"), answer)
        self.assertEqual(answer.get("code"), "DUPLICATE_ID_RESOLVED", answer)


class LifecycleObserverContractTests(unittest.TestCase):
    def test_only_repairing_readers_name_the_lifecycle_class(self):
        self.assertEqual(_lifecycle_observers(), LIFECYCLE_OBSERVERS)

    def test_the_detector_sees_an_aliased_name(self):
        # The incident spelled the class through a local alias; a detector
        # that reads only the literal would have missed it.
        for source in (
            "_read(root, observe=(*REPAIR_OBSERVABLE, _LIFECYCLE_OBSERVABLE))",
            "_read(root, observe=TYPED_HEAD_QUARANTINE_OBSERVABLE)",
            "_read(root, observe=('state', 'lifecycle_authority'))",
            "_read(root, observe=something_computed())",
        ):
            with self.subTest(source=source):
                call = ast.parse(source).body[0].value
                self.assertTrue(_names_the_class(call.keywords[0].value))
        for source in (
            "_read(root, observe=REPAIR_OBSERVABLE)",
            "_read(root, observe=('log',))",
            "_read(root, observe=TAIL_QUARANTINE_OBSERVABLE)",
        ):
            with self.subTest(source=source):
                call = ast.parse(source).body[0].value
                self.assertFalse(_names_the_class(call.keywords[0].value))


if __name__ == "__main__":
    unittest.main()
