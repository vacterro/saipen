"""Real native OpenCode gap admission with explicit policy and conflict controls."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import host_authority_client, host_taxonomy  # noqa: E402
from saipen_engine.paths import project_lineage_identity  # noqa: E402
from test_guard_hostile_matrix import active_project  # noqa: E402
from test_hermetic_env import HOST_SESSION_VARIABLES, isolate_host_session  # noqa: E402

NODE = shutil.which("node")
PLUGIN = ROOT / "extensions/adapters/opencode/saipen-guard.js"


def setUpModule() -> None:
    isolate_host_session()


DRIVER = r'''
import fs from "node:fs";
import { pathToFileURL } from "node:url";
const request = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const results = [];
for (const item of request.cases) {
  const saved = {};
  for (const [key, value] of Object.entries(item.env)) {
    saved[key] = process.env[key];
    if (value === null) delete process.env[key];
    else process.env[key] = String(value);
  }
  const { default: factory } = await import(pathToFileURL(item.plugin).href);
  const hooks = await factory({ worktree: item.project, directory: item.project });
  if (item.stale) fs.appendFileSync(item.plugin, "\n// next installed generation\n");
  const before = { system: [] };
  await hooks["experimental.chat.system.transform"]({ sessionID: item.id }, before);
  if (item.policy_change) fs.writeFileSync(item.policy_path, item.policy_change);
  const result = { id: item.id, outcome: "allowed", message: "", before: before.system };
  try {
    await hooks["tool.execute.before"](
      { tool: item.tool || "write", sessionID: item.id }, item.output,
    );
    if (item.effect) fs.writeFileSync(item.effect, "HOST_TOOL_EXECUTED");
  } catch (error) {
    result.outcome = "blocked";
    result.message = String(error.message || error);
  }
  const after = { system: [] };
  await hooks["experimental.chat.system.transform"]({ sessionID: item.id }, after);
  result.after = after.system;
  results.push(result);
  for (const [key, value] of Object.entries(saved)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
}
process.stdout.write(JSON.stringify(results));
'''


@unittest.skipUnless(NODE, "native Node runtime unavailable")
class NativePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="saipen-t1628-policy-")
        cls.tmp = Path(cls.temporary.name)
        cls.project = active_project()
        cls.foreign = active_project()
        cls.snapshot = {
            str(path.relative_to(cls.project)): path.read_bytes()
            for path in (cls.project / ".saipen").rglob("*") if path.is_file()
        }
        cases = []
        cls.effects = {}
        cls.policy_expectations = {}

        def case(identifier, gap, mode=None, *, tool="write", invalid=None,
                 foreign=False, malformed=False, change=False, ambient=False, legitimate=False):
            profile = cls.tmp / identifier / "profile"
            (profile / ".saipen").mkdir(parents=True)
            policy = profile / ".saipen/authority.json"
            if mode is not None:
                policy.write_text(json.dumps({"mode": mode}), encoding="utf-8-sig")
            if invalid == "bytes":
                policy.write_bytes(b'\xff{"mode":"degraded"}')
            elif invalid == "json":
                policy.write_text("{bad", encoding="utf-8")
            elif invalid == "mode":
                policy.write_text('{"mode":"unchecked"}', encoding="utf-8")
            elif invalid == "directory":
                policy.mkdir()
            cls.policy_expectations[identifier] = host_authority_client.policy(profile)
            plugin = profile.parent / "saipen-guard.mjs"
            shutil.copyfile(PLUGIN, plugin)
            effect = cls.project / "src" / (identifier + ".txt")
            cls.effects[identifier] = effect
            env = {name: None for name in HOST_SESSION_VARIABLES}
            env.update({
                "SAIPEN_SKILL_ROOT": str(ROOT if gap != "missing" else profile / "absent"),
                "SAIPEN_PYTHON": sys.executable,
                "USERPROFILE": str(profile), "HOME": str(profile),
            })
            if gap == "python":
                env.update({"SAIPEN_PYTHON": "saipen-missing-python", "PATH": ""})
            if foreign:
                env.update({"SAIPEN_PROJECT_ROOT": str(cls.project),
                            "SAIPEN_PROJECT_LINEAGE": "lineage-" + "0" * 32})
            if ambient:
                env.update({"SAIPEN_PROJECT_ROOT": str(cls.foreign),
                            "SAIPEN_PROJECT_LINEAGE": project_lineage_identity(cls.foreign)})
            if legitimate:
                env.update({"SAIPEN_PROJECT_ROOT": str(cls.project),
                            "SAIPEN_PROJECT_LINEAGE": project_lineage_identity(cls.project)})
            cases.append({
                "id": identifier, "project": str(cls.project), "plugin": str(plugin),
                "env": env, "stale": gap == "stale", "tool": tool,
                "output": {} if malformed else {
                    "args": {"filePath": str(effect), "content": "HOST_TOOL_EXECUTED"}},
                "effect": str(effect) if tool == "write" else None,
                "policy_path": str(policy),
                "policy_change": '{"mode":"strict"}' if change else None,
            })

        for gap in ("missing", "python", "stale"):
            for mode in (None, "degraded", "strict"):
                case(f"{gap}-{mode or 'default'}", gap, mode)
            case(f"{gap}-read", gap, "strict", tool="read")
        for invalid in ("bytes", "json", "mode", "directory"):
            case("invalid-" + invalid, "missing", invalid=invalid)
        for index, alias in enumerate(("DEGRADED ALLOWED", "degraded-allowed")):
            case(f"alias-{index}", "missing", alias)
        case("live-policy", "missing", change=True)
        for mode in ("degraded", "strict"):
            case("foreign-stale-" + mode, "stale", mode, foreign=True)
            case("foreign-healthy-" + mode, "healthy", mode, foreign=True)
            case("malformed-" + mode, "missing", mode, malformed=True)
            for gap in ("missing", "python"):
                case("foreign-" + gap + "-" + mode, gap, mode, foreign=True)
                case("ambient-" + gap + "-" + mode, gap, mode, ambient=True)
        for gap in ("missing", "python"):
            case("legitimate-" + gap, gap, legitimate=True)
        driver = cls.tmp / "driver.mjs"
        driver.write_text(DRIVER, encoding="utf-8")
        request = cls.tmp / "request.json"
        request.write_text(json.dumps({"cases": cases}), encoding="utf-8")
        env = dict(os.environ)
        for name in HOST_SESSION_VARIABLES:
            env.pop(name, None)
        result = subprocess.run(
            [NODE, str(driver), str(request)], cwd=cls.project, env=env,
            capture_output=True, text=True, encoding="utf-8", timeout=240,
        )
        if result.returncode:
            cls.temporary.cleanup()
            raise AssertionError(result.stderr)
        cls.results = {item["id"]: item for item in json.loads(result.stdout)}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def gap(self, identifier, stage="before") -> dict:
        messages = self.results[identifier][stage]
        found = [message for message in messages if message.startswith("SAIPEN_HOST_INTEGRATION ")]
        self.assertEqual(len(found), 1, messages)
        return json.loads(found[0].splitlines()[0].split(" ", 1)[1])

    def allowed(self, identifier) -> None:
        record = self.results[identifier]
        self.assertEqual(record["outcome"], "allowed", record)
        self.assertEqual(self.effects[identifier].read_text(), "HOST_TOOL_EXECUTED")
        marker = self.gap(identifier)
        self.assertEqual(marker["status"], "UNVERIFIED")
        self.assertEqual(marker["decision"], "ALLOW_DEGRADED")

    def blocked(self, identifier) -> dict:
        record = self.results[identifier]
        self.assertEqual(record["outcome"], "blocked", record)
        self.assertFalse(self.effects[identifier].exists(), record)
        return record

    def test_default_permits_all_three_gaps_with_physical_marker_and_effect(self):
        for gap in ("missing", "python", "stale"):
            with self.subTest(gap=gap):
                self.allowed(gap + "-default")
                self.assertEqual(self.gap(gap + "-default")["policy_source"], "default")

    def test_explicit_degraded_permits_the_same_three_gaps(self):
        for gap in ("missing", "python", "stale"):
            with self.subTest(gap=gap):
                self.allowed(gap + "-degraded")
                self.assertEqual(self.gap(gap + "-degraded")["policy_source"], "operator")

    def test_strict_refuses_all_three_gaps_with_the_single_taxonomy_action(self):
        for gap in ("missing", "python", "stale"):
            identifier = gap + "-strict"
            with self.subTest(gap=gap):
                record = self.blocked(identifier)
                marker = self.gap(identifier)
                self.assertEqual(marker["decision"], "BLOCK")
                self.assertEqual(record["message"].count("next:"), 1)
                expected = host_taxonomy.get(marker["failure_code"]).operator_action
                self.assertEqual(marker["operator_action"], expected)
                self.assertIn("next: " + expected, record["message"])

    def test_bad_policy_uses_strict_and_names_its_policy_repair(self):
        for kind in ("bytes", "json", "mode", "directory"):
            identifier = "invalid-" + kind
            with self.subTest(kind=kind):
                record = self.blocked(identifier)
                marker = self.gap(identifier)
                self.assertEqual(marker["policy"], "STRICT")
                self.assertEqual(marker["policy_source"], "invalid")
                self.assertIn("next: saipen host mode degraded", record["message"])

    def test_native_policy_reads_match_python_including_bom_and_aliases(self):
        for identifier, expected in self.policy_expectations.items():
            if identifier.startswith("foreign-healthy"):
                continue
            with self.subTest(case=identifier):
                marker = self.gap(identifier)
                self.assertEqual(marker["policy"], host_taxonomy.MODE_LABELS[expected["mode"]])
                self.assertEqual(marker["policy_source"], expected["source"])

    def test_recognized_aliases_do_not_become_silent_strict_policy(self):
        for identifier in ("alias-0", "alias-1"):
            self.allowed(identifier)

    def test_policy_change_is_seen_by_the_same_live_factory(self):
        record = self.blocked("live-policy")
        self.assertEqual(self.gap("live-policy")["decision"], "ALLOW_DEGRADED")
        self.assertEqual(self.gap("live-policy", "after")["decision"], "BLOCK")
        self.assertIn("saipen host repair", record["message"])

    def test_known_foreign_lineage_blocks_even_a_degradable_stale_plugin(self):
        for mode in ("degraded", "strict"):
            record = self.blocked("foreign-stale-" + mode)
            self.assertIn("PROJECT_LINEAGE_MISMATCH", record["message"])

    def test_foreign_lineage_still_blocks_the_healthy_guard(self):
        for mode in ("degraded", "strict"):
            record = self.blocked("foreign-healthy-" + mode)
            self.assertIn("PROJECT_LINEAGE_MISMATCH", record["message"])

    def test_known_lineage_contradiction_blocks_without_guard_or_interpreter(self):
        for gap in ("missing", "python"):
            for mode in ("degraded", "strict"):
                identifier = "foreign-" + gap + "-" + mode
                with self.subTest(case=identifier):
                    record = self.blocked(identifier)
                    self.assertIn("PROJECT_LINEAGE_MISMATCH", record["message"])
                    self.assertEqual(self.gap(identifier)["decision"], "BLOCK")

    def test_observed_foreign_project_contradiction_blocks_in_both_modes(self):
        for gap in ("missing", "python"):
            for mode in ("degraded", "strict"):
                identifier = "ambient-" + gap + "-" + mode
                with self.subTest(case=identifier):
                    record = self.blocked(identifier)
                    self.assertIn("PROJECT_BINDING_AMBIGUOUS", record["message"])
                    self.assertEqual(self.gap(identifier)["failure_code"], "BINDING_CONFLICT")

    def test_legitimate_carrier_remains_degradable_and_does_not_gain_admission(self):
        for gap in ("missing", "python"):
            identifier = "legitimate-" + gap
            self.allowed(identifier)
            message = self.results[identifier]["before"][0]
            binding = json.loads(message.splitlines()[0].split(" ", 1)[1])
            self.assertEqual(binding["binding_code"], "GUARD_UNREACHABLE")
            self.assertIsNone(binding.get("project_root"))

    def test_unreadable_tool_payload_never_uses_the_gap_allowance(self):
        for mode in ("degraded", "strict"):
            record = self.blocked("malformed-" + mode)
            self.assertIn("SAIPEN_GUARD_PAYLOAD_INVALID", record["message"])

    def test_exact_diagnostics_remain_usable_under_strict(self):
        for gap in ("missing", "python", "stale"):
            record = self.results[gap + "-read"]
            self.assertEqual(record["outcome"], "allowed", record)

    def test_native_execution_does_not_write_project_control_memory(self):
        current = {
            str(path.relative_to(self.project)): path.read_bytes()
            for path in (self.project / ".saipen").rglob("*") if path.is_file()
        }
        self.assertEqual(current, self.snapshot)

    def test_compiled_facet_is_exactly_the_current_canonical_decision_table(self):
        from saipen_engine.native_host_policy import BEGIN, END, fragment

        text = PLUGIN.read_text(encoding="utf-8")
        first = text.index(BEGIN)
        last = text.index(END, first) + len(END)
        self.assertEqual(text[first:last], fragment())


if __name__ == "__main__":
    unittest.main()
