"""SRC-274:R005 -- the compound/response policy is one schema with a verifier.

The clause asks for F-06 (compound-input resolver) and F-09 (response/HUSH
contract) as ONE normative machine-readable schema with a verifiable resolver,
"rather than repeated prose". Three runtimes already existed and three prose
documents already explained them; nothing checked that the four agreed, and the
operator's real mixed input `saipen clean` + `/goal cc all` resolved its second
half to `unknown`.

What these controls hold:

  schema_is_loadable          the file parses, is schema 1, and names itself
  fields_match_runtime        every declared set equals the runtime's own
                              import-time derivation (never a second copy)
  runtimes_are_present        every declared module and symbol imports
  registry_blocks_agree       the blocks the file defers to are not stale copies
  mixed_command_orders        `saipen clean` then `/goal cc all` resolves to
                              two indexed segments in input order
  slash_fails_closed          an undeclared `/verb` stays unknown
  stop_freezes_later          a refused first segment leaves the second NOT_RUN
  hush_keeps_mandatory       no suppressible kind is also mandatory
  verifier_notices_drift      a deliberately wrong claim makes verify refuse

Run standalone:
    python tools/test_t1855_compound_policy.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import hush, policy_contract, response_surface  # noqa: E402
from saipen_engine.commands import (  # noqa: E402
    CHAIN_STOP_ON_FAILURE,
    DISPOSITION_EXECUTED,
    DISPOSITION_NOT_RUN,
    DISPOSITION_REFUSED,
    canonical_slash_command,
    chain_disposition,
    resolve_compound_command,
)
from saipen_engine.registry import load_registry  # noqa: E402

ROOT = TOOLS.parent
POLICY = ROOT / "saipen" / "COMPOUND_RESPONSE_POLICY.json"


class PolicySchemaTests(unittest.TestCase):
    """The file is the contract; these hold it to the runtimes it names."""

    def test_schema_is_loadable(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertEqual(policy["schema"], 1)
        self.assertEqual(policy["kind"], "saipen-compound-response-policy")
        self.assertEqual(policy["owner_clause"], "SRC-274:R005")
        self.assertEqual(set(policy["sources"]), {"F-06", "F-09"})

    def test_the_verifier_accepts_the_shipped_policy(self):
        result = policy_contract.verify(ROOT)
        self.assertTrue(result["ok"], result["problems"])
        self.assertEqual(result["code"], "POLICY_VERIFIED")

    def test_hush_sets_match_the_runtime(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))["hush"]
        self.assertEqual(set(policy["suppressible"]), set(hush.DISCRETIONARY))
        self.assertFalse(set(policy["suppressible"]) & set(policy["mandatory"]))

    def test_the_registry_hush_block_agrees_with_the_policy(self):
        block = load_registry()["hush_precedence"]
        policy = json.loads(POLICY.read_text(encoding="utf-8"))["hush"]
        self.assertEqual(policy["precedence"], block["order"])
        self.assertEqual(policy["suppressible"], block["suppressible"])
        self.assertEqual(policy["mandatory"], block["mandatory"])

    def test_the_response_surface_matches_the_policy(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))["response_surface"]
        self.assertEqual(policy["mandatory_fields"], list(response_surface.MANDATORY_FIELDS))
        self.assertEqual(policy["optional_fields"], list(response_surface.OPTIONAL_FIELDS))
        self.assertEqual(policy["handback"], response_surface.STOP_HANDBACK)

    def test_the_declared_runtimes_are_present(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        for group_name in ("segmentation", "resolution", "ordering", "stop",
                           "response_surface", "hush", "verification"):
            group = policy[group_name]
            for key, reference in group.items():
                if not isinstance(reference, str) or "tools/saipen_engine/" not in reference:
                    continue
                module, qualname = policy_contract._runtime_ref(reference)
                with self.subTest(group=group_name, key=key):
                    policy_contract._symbol(module, qualname)


class MixedCommandTests(unittest.TestCase):
    """R005's own example, verbatim: a cleanup command then /goal cc all."""

    def test_the_clause_example_resolves_in_order(self):
        resolved = resolve_compound_command("saipen clean\n/goal cc all")
        self.assertEqual(len(resolved), 2, resolved)
        self.assertEqual([s["index"] for s in resolved], [0, 1])
        self.assertEqual(resolved[0]["command"], "saipen clean")
        self.assertEqual(resolved[1]["command"], "saipen goal cc all")
        self.assertTrue(all(s["kind"] == "command" for s in resolved))

    def test_the_plus_separator_gives_the_same_two_segments(self):
        resolved = resolve_compound_command("saipen clean + /goal cc all")
        self.assertEqual([s["command"] for s in resolved],
                         ["saipen clean", "saipen goal cc all"])

    def test_an_undeclared_slash_verb_stays_unknown(self):
        self.assertEqual(canonical_slash_command("/definitely-not-a-verb x"), "")
        resolved = resolve_compound_command("/definitely-not-a-verb x")
        self.assertEqual(resolved[0]["kind"], "unknown")

    def test_stop_freezes_every_later_segment(self):
        frozen = chain_disposition([DISPOSITION_REFUSED, DISPOSITION_EXECUTED])
        self.assertEqual(frozen[1], DISPOSITION_NOT_RUN)
        self.assertEqual(CHAIN_STOP_ON_FAILURE, "STOP_ON_FAILURE")

    def test_every_segment_carries_a_terminal_disposition(self):
        """Provenance: no recognized segment may be silently dropped."""
        resolved = resolve_compound_command("saipen clean\n/goal cc all")
        dispositions = [DISPOSITION_REFUSED, DISPOSITION_EXECUTED]
        frozen = chain_disposition(dispositions)
        self.assertEqual(len(frozen), len(resolved))
        self.assertEqual(frozen, [DISPOSITION_REFUSED, DISPOSITION_NOT_RUN])
        for segment, disposition in zip(resolved, frozen):
            self.assertTrue(segment["command"])
            self.assertTrue(disposition)


class DriftDetectionTests(unittest.TestCase):
    """A verifier that cannot fail is not a verifier."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="saipen-t1855-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "PROJECT"
        (self.root / "saipen").mkdir(parents=True)
        shutil.copyfile(POLICY, self.root / "saipen" / POLICY.name)

    def _mutate(self, mutate) -> dict:
        data = json.loads(POLICY.read_text(encoding="utf-8"))
        mutate(data)
        (self.root / "saipen" / POLICY.name).write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
        return policy_contract.verify(self.root)

    def test_a_wrong_hush_set_is_refused(self):
        def mutate(data):
            data["hush"]["suppressible"] = ["preamble"]

        result = self._mutate(mutate)
        self.assertFalse(result["ok"])
        self.assertTrue(any("suppressible" in p for p in result["problems"]), result)

    def test_a_wrong_field_order_is_refused(self):
        def mutate(data):
            data["response_surface"]["mandatory_fields"] = ["STATUS"]

        result = self._mutate(mutate)
        self.assertFalse(result["ok"])
        self.assertTrue(any("mandatory_fields" in p for p in result["problems"]), result)

    def test_a_missing_runtime_is_refused(self):
        def mutate(data):
            data["segmentation"]["runtime"] = "tools/saipen_engine/no_such_module.py:parse"

        result = self._mutate(mutate)
        self.assertFalse(result["ok"])
        self.assertTrue(any("no_such_module" in p for p in result["problems"]), result)

    def test_a_schema_of_the_wrong_kind_is_refused(self):
        def mutate(data):
            data["kind"] = "something-else"

        result = self._mutate(mutate)
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "POLICY_INVALID")

    def test_an_absent_policy_file_is_refused(self):
        (self.root / "saipen" / POLICY.name).unlink()
        result = policy_contract.verify(self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "POLICY_INVALID")


class RuleProbeTests(unittest.TestCase):
    """Every rule is typed and owns a probe; neither side may drift alone.

    The first draft of the policy listed sentences. A verifier that only counts
    them accepts any text at all, so a rule could be flipped to its opposite and
    the file still said POLICY_VERIFIED -- prose with a schema around it, which
    is the exact defect R005 names. Rules are therefore {id, text}, each id has
    exactly one probe below, and both directions are closed sets.
    """

    def setUp(self):
        self.policy = json.loads(POLICY.read_text(encoding="utf-8"))

    def test_resolution_rules_carry_the_verifier_ids(self):
        ids = [rule["id"] for rule in self.policy["resolution"]["rules"]]
        self.assertEqual(ids, list(policy_contract.RESOLUTION_RULE_IDS))

    def test_segmentation_rules_carry_the_verifier_ids(self):
        ids = [rule["id"] for rule in self.policy["segmentation"]["rules"]]
        self.assertEqual(ids, list(policy_contract.SEGMENTATION_RULE_IDS))

    def test_every_rule_has_text(self):
        for block in ("resolution", "segmentation"):
            for rule in self.policy[block]["rules"]:
                with self.subTest(block=block, id=rule["id"]):
                    self.assertGreaterEqual(len(rule["text"].split()), 3)

    def test_the_never_drop_rule_matches_the_parser(self):
        """SEG-NEVER-DROP: a separator run collapses instead of emitting blanks."""
        from saipen_engine.commands import parse_compound_command

        self.assertEqual(parse_compound_command("   "), [])
        self.assertEqual(
            parse_compound_command("saipen status\n\n\nsaipen goal cc all"),
            ["saipen status", "saipen goal cc all"],
        )
        self.assertEqual(
            parse_compound_command("saipen status +  + saipen goal"),
            ["saipen status", "saipen goal"],
        )

    def test_the_cli_empty_segment_rule_is_the_argv_path(self):
        """SEG-CLI-EMPTY-REFUSES: what the text path collapses, argv refuses.

        These are two different rules over two different inputs, which is why
        one sentence could not state both: the earlier wording claimed refusal
        for `parse_compound_command`, which in fact collapses a doubled plus.
        """
        from saipen_engine.commands import split_cli_compound_argv

        self.assertEqual(split_cli_compound_argv(["status", "+", "status"]),
                         [["status"], ["status"]])
        for argv in (["+", "status"], ["status", "+"], ["status", "+", "+", "status"]):
            with self.subTest(argv=argv), self.assertRaisesRegex(ValueError, "empty segment"):
                split_cli_compound_argv(list(argv))

    def test_the_shortcut_payload_rule_holds(self):
        resolved = resolve_compound_command("cc all")[0]
        self.assertEqual(resolved["kind"], "shortcut")
        self.assertEqual(resolved["command"], "saipen continue all")
        self.assertEqual(resolved["payload"], "all")

    def test_the_fail_closed_rule_holds(self):
        for message in ("definitely-not-a-verb", "notacommand at all"):
            with self.subTest(message=message):
                segment = resolve_compound_command(message)[0]
                self.assertEqual(segment["kind"], "unknown")
                self.assertEqual(segment["command"], "")


class RuleDriftTests(unittest.TestCase):
    """The typed-rule contract fails in both directions."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="saipen-t1855-rules-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "PROJECT"
        (self.root / "saipen").mkdir(parents=True)
        shutil.copyfile(POLICY, self.root / "saipen" / POLICY.name)

    def _verify(self, mutate) -> dict:
        data = json.loads(POLICY.read_text(encoding="utf-8"))
        mutate(data)
        (self.root / "saipen" / POLICY.name).write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
        return policy_contract.verify(self.root)

    def test_a_deleted_rule_is_refused(self):
        result = self._verify(lambda data: data["resolution"]["rules"].pop())
        self.assertFalse(result["ok"])
        self.assertTrue(any("RES-" in p for p in result["problems"]), result)

    def test_a_renamed_rule_is_refused(self):
        def mutate(data):
            data["resolution"]["rules"][0]["id"] = "RES-BOGUS"

        result = self._verify(mutate)
        self.assertFalse(result["ok"])
        self.assertTrue(any("RES-BOGUS" in p for p in result["problems"]), result)

    def test_rules_that_are_bare_strings_are_refused(self):
        def mutate(data):
            data["resolution"]["rules"] = ["a rule with enough words"] * 5

        result = self._verify(mutate)
        self.assertFalse(result["ok"])
        self.assertIn("not {id, text}", " ".join(result["problems"]))

    def test_a_missing_policy_block_is_refused(self):
        for block in policy_contract.REQUIRED_BLOCKS:
            with self.subTest(block=block):
                result = self._verify(lambda data, name=block: data.pop(name))
                self.assertFalse(result["ok"])
                self.assertTrue(any(block in p for p in result["problems"]), result)


if __name__ == "__main__":
    unittest.main()
