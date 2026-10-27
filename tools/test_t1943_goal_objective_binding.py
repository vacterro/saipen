"""T-1943/SRC-342 R003: a goal proof binds the OBJECTIVE, never the command line.

MEASURED defect, 2026-10-27. `operator_origin.OperatorOrigins.issue` hashed the
raw request text into `goal_target`:

    goal_target = goal_ingress_identity(redact_credentials(text).strip(), project)

while `operations.goal_entry` persists the identity of the objective it actually
records:

    ingress = goal_ingress_identity(safe_objective, _identity(root))

`prepare_goal` then requires the reservation to equal
`{**grant_fields(source), "goal_ingress": known["goal_target"]}`, so the two had
to agree. They never could:

    $ gg cc all                -> broker goal-bdb95747918031a7 / CLI goal-ca391cacb96efa10
    $ saipen goal cc all       -> broker goal-925b77977992433b / CLI goal-ca391cacb96efa10
    $ /goal gg cc all          -> broker goal-943cf5a873083e2b / CLI goal-ca391cacb96efa10

Every accepted spelling of the SAME objective produced a DIFFERENT proof target,
so an operator's native goal entry could be sealed and then refused at the
reservation step. The failure is order-dependent and silent: the hook reported a
seal and the engine reported a refusal, which is why no existing test caught it.

WHY ONE PARSER. The fix could have taught the broker the four accepted shapes --
that is exactly the second parser SRC-342 R002 forbids. Instead the grammar
moved to `cold_recovery.goal_objective_text`, the ZAICODE hook delegates to it,
and the broker calls the same function. There is now one answer to "what
objective did this operator declare?" for the whole host surface.

These cases pin the property, not the implementation: equal objective means
equal proof target, across every accepted spelling; and every non-goal shape
yields none, so nothing is promoted by accident. They call the real functions --
no mock stands between the assertion and the arithmetic.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.cold_recovery import (  # noqa: E402
    GOAL_ROUTE,
    goal_ingress_identity,
    goal_objective_text,
)

PROTOCOL_DIR = REPO / "saipen"
PROJECT = r"v:\___vac\__k\__code\_ai_stuff_agentic\_saipen"


def objective_of(text: str) -> str | None:
    return goal_objective_text(text, protocol_dir=PROTOCOL_DIR)


def target_of(text: str) -> str | None:
    objective = objective_of(text)
    return goal_ingress_identity(objective, PROJECT) if objective is not None else None


class TheObjectiveIsWhatGetsBound(unittest.TestCase):
    """The defect itself: four spellings, one objective, one proof target."""

    ACCEPTED = (
        "gg cc all",
        "saipen goal cc all",
        "saipen gg cc all",
        "/goal gg cc all",
        "/saipen goal cc all",
    )

    def test_every_accepted_spelling_declares_the_same_objective(self) -> None:
        for text in self.ACCEPTED:
            with self.subTest(text=text):
                self.assertEqual(objective_of(text), "cc all")

    def test_every_accepted_spelling_produces_the_objective_target(self) -> None:
        """The regression: pre-fix each spelling hashed its own command line."""
        expected = goal_ingress_identity("cc all", PROJECT)
        for text in self.ACCEPTED:
            with self.subTest(text=text):
                self.assertEqual(
                    target_of(text),
                    expected,
                    f"{text!r} bound a target the CLI cannot match",
                )

    def test_no_accepted_spelling_binds_the_raw_command_line(self) -> None:
        """Naming the old bug directly, so a regression cannot be subtle."""
        objective_target = goal_ingress_identity("cc all", PROJECT)
        for text in self.ACCEPTED:
            with self.subTest(text=text):
                raw_target = goal_ingress_identity(text, PROJECT)
                self.assertNotEqual(raw_target, objective_target, "fixture no longer discriminating")
                self.assertNotEqual(target_of(text), raw_target)

    def test_the_target_is_stable_across_whitespace(self) -> None:
        self.assertEqual(target_of("gg   cc    all"), target_of("gg cc all"))
        self.assertEqual(target_of("  gg cc all  "), target_of("gg cc all"))


class NothingIsPromotedByAccident(unittest.TestCase):
    """Every shape that is NOT a goal entry yields None, not a guess."""

    NOT_GOALS = (
        "",
        "   ",
        "gg",
        "saipen goal",
        "/goal",
        "/saipen goal",
        "goal cc all",                 # bare `goal` is prose, not a command
        "goal of this task is X",
        "the goal is to ship this",
        "cc all",                      # the objective alone is not an entry
        "cc",
        "saipen continue",
        "unknownshortcut do a thing",
        "g cc all",                    # near-miss token
        "ggg cc all",
    )

    def test_these_are_not_goal_entries(self) -> None:
        for text in self.NOT_GOALS:
            with self.subTest(text=text):
                self.assertIsNone(objective_of(text), f"{text!r} was promoted to a goal")

    def test_a_multiline_handoff_is_not_a_goal_entry(self) -> None:
        """SRC-342 section 4: prose beginning with a shortcut stays prose.

        The measured hazard: a real handoff report opens with `gg <one line>`
        and then continues for dozens of lines. Flattening it with
        `" ".join(split())` turned the whole document into the objective, so a
        report that merely OPENED with the shortcut minted a persistent
        campaign whose scope was an entire essay. This is the exact shape
        section 4 lists under "multiline handoff beginning with `gg` ... -> no
        new authority".
        """
        text = (
            "gg the importer is broken\n"
            "\n"
            "Here is what I measured and what I want changed: ...\n"
        )
        self.assertIsNone(
            objective_of(text),
            "a multiline document was promoted because its first line was a "
            "shortcut; the objective would be the whole handoff",
        )

    def test_a_cli_history_newline_does_not_disqualify_a_command(self) -> None:
        """The control for the rule above: one trailing newline is not a document."""
        self.assertEqual(objective_of("gg cc all\n"), "cc all")
        self.assertEqual(objective_of("gg cc all\r\n"), "cc all")
        self.assertEqual(objective_of("\n\ngg cc all\n\n"), "cc all")

    def test_the_hook_refuses_the_same_multiline_body(self) -> None:
        """The hook's fallback must not be a second, looser grammar."""
        import importlib.util

        hook_path = REPO / "extensions" / "adapters" / "zaicode" / "saipen-guard.py"
        spec = importlib.util.spec_from_file_location("saipen_guard_multiline", hook_path)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        text = "gg fix it\n\nand also do this other thing\n"
        self.assertIsNone(hook._goal_objective_local(text))
        self.assertEqual(hook.declared_action(text), "continue")

    def test_an_unknown_shortcut_is_not_resolved_by_similarity(self) -> None:
        """The registry is authoritative; no fuzzy matching, no word list."""
        self.assertIsNone(objective_of("hh something"), "hh routes to hunt, not goal")
        self.assertEqual(GOAL_ROUTE, "saipen goal")


class TheNativeAuthorizeGoalSpelling(unittest.TestCase):
    """SRC-342 section 4: `saipen goal authorize --file <capsule>` is a GRANT.

    Measured before the fix: the canonical parser read `authorize --file
    <path>` as the OBJECTIVE of a new goal, so the hook sealed `action = goal`
    and the capsule was never verified. That is a grant silently converted into
    an entry -- the operator asked for persistence on an existing goal and got a
    differently-scoped campaign instead.

    Two spellings must reach the same place: the capsule document pasted as the
    message, and the path form. Both resolve to the SAME bytes, which is the
    only thing `authorize_goal_continuation` compares against the live binding.
    """

    CAPSULE = (
        '{\n'
        '  "kind": "saipen-goal-continuation",\n'
        '  "goal_ingress": "goal-0123456789abcdef"\n'
        '}\n'
    )

    @staticmethod
    def hook():
        import importlib.util

        hook_path = REPO / "extensions" / "adapters" / "zaicode" / "saipen-guard.py"
        spec = importlib.util.spec_from_file_location("saipen_guard_authorize", hook_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_the_file_form_is_an_authorization_not_an_objective(self) -> None:
        hook = self.hook()
        for text in (
            "saipen goal authorize --file c.json",
            "/saipen goal authorize --file c.json",
        ):
            with self.subTest(text=text):
                self.assertEqual(hook.declared_action(text, REPO), "authorize-goal")
                self.assertIsNone(
                    objective_of(text),
                    "the CLI's authorization spelling was read as an objective",
                )
                self.assertIsNone(hook._goal_objective(text, REPO))

    def test_a_hostile_or_malformed_path_is_never_an_authorization(self) -> None:
        hook = self.hook()
        for text in (
            "saipen goal authorize --file ../../../etc/passwd",
            "saipen goal authorize --file C:/Windows/win.ini",
            "saipen goal authorize --file",
            "saipen goal authorize --file a.json extra",
            "saipen goal authorize c.json",
        ):
            with self.subTest(text=text):
                self.assertEqual(hook.declared_action(text, REPO), "continue")
                self.assertIsNone(hook.grant_capsule_text(text, REPO))

    def test_both_spellings_resolve_to_the_same_exact_bytes(self) -> None:
        import tempfile

        hook = self.hook()
        with tempfile.TemporaryDirectory() as spare:
            project = Path(spare)
            (project / "c.json").write_bytes(self.CAPSULE.encode("utf-8"))
            inline = hook.grant_capsule_text(self.CAPSULE, project)
            from_file = hook.grant_capsule_text(
                "saipen goal authorize --file c.json", project
            )
        self.assertEqual(inline, self.CAPSULE)
        self.assertEqual(
            from_file,
            self.CAPSULE,
            "the path form must hand the stored bytes on unchanged; a re-encoded "
            "document would fail the broker's exact-bytes comparison",
        )

    def test_a_missing_capsule_file_authorizes_nothing(self) -> None:
        import tempfile

        hook = self.hook()
        with tempfile.TemporaryDirectory() as spare:
            project = Path(spare)
            self.assertIsNone(
                hook.grant_capsule_text("saipen goal authorize --file absent.json", project)
            )
            # The classification still says what the operator asked for; only
            # the bytes are absent, and the hook reports that rather than
            # silently downgrading the action to `continue`.
            self.assertEqual(
                hook.declared_action("saipen goal authorize --file absent.json", project),
                "authorize-goal",
            )


class TheHookAndTheBrokerReadTheSameBytes(unittest.TestCase):
    """ONE parser: the hook delegates to the function the broker calls."""

    def test_the_hook_helper_returns_the_canonical_objective(self) -> None:
        import importlib.util

        hook_path = REPO / "extensions" / "adapters" / "zaicode" / "saipen-guard.py"
        spec = importlib.util.spec_from_file_location("saipen_guard_t1943", hook_path)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        for text in ("gg cc all", "saipen goal cc all", "/goal gg cc all"):
            with self.subTest(text=text):
                self.assertEqual(hook._goal_objective(text, REPO), objective_of(text))
                self.assertEqual(hook.declared_action(text, REPO), "goal")

    def test_the_hook_still_refuses_prose_and_continuation(self) -> None:
        import importlib.util

        hook_path = REPO / "extensions" / "adapters" / "zaicode" / "saipen-guard.py"
        spec = importlib.util.spec_from_file_location("saipen_guard_t1943b", hook_path)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        for text in ("goal of this task is X", "cc", "cc all", ""):
            with self.subTest(text=text):
                self.assertEqual(hook.declared_action(text, REPO), "continue")

    def test_the_broker_uses_the_shared_function_not_a_copy(self) -> None:
        """Structural: the broker must import the parser, never re-implement it."""
        source = (TOOLS / "saipen_engine" / "operator_origin.py").read_text(encoding="utf-8-sig")
        self.assertIn("goal_objective_text", source)
        self.assertIn("goal_ingress_identity(", source)
        # The bug's exact shape: hashing `text` directly into the target.
        self.assertNotIn(
            "goal_ingress_identity(redact_credentials(text).strip()",
            source,
            "the broker is hashing the raw command line again",
        )


class TheRedControlReproducesTheOldTarget(unittest.TestCase):
    """The pre-fix expression, run here so the regression can go red.

    `test_no_accepted_spelling_binds_the_raw_command_line` asserts only that
    the CURRENT code differs from the raw-line hash. That would still pass if
    the parser were deleted and `issue()` started hashing something else. This
    case computes the old target explicitly and asserts the suites above would
    have caught it: the old value differs from the new one, and the new one is
    the objective's. A future regression to the old expression therefore fails
    a test that names exactly what went wrong.
    """

    def test_the_old_expression_produced_a_different_target(self) -> None:
        objective_target = goal_ingress_identity("cc all", PROJECT)
        for text in TheObjectiveIsWhatGetsBound.ACCEPTED:
            with self.subTest(text=text):
                old_target = goal_ingress_identity(text, PROJECT)  # pre-fix expression
                self.assertNotEqual(old_target, objective_target)
                self.assertEqual(target_of(text), objective_target)

    def test_the_old_expression_would_fail_the_primary_assertion(self) -> None:
        """Simulates the pre-fix value entering the primary assertion."""
        expected = goal_ingress_identity("cc all", PROJECT)
        simulated_pre_fix = goal_ingress_identity("gg cc all", PROJECT)
        self.assertNotEqual(
            simulated_pre_fix,
            expected,
            "the control is vacuous: old and new targets agree, so nothing was bound",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
