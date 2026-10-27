"""A replaced OpenCode plugin keeps asking the guard it can still reach (T-1688).

Defect class: one allowance for three different gaps. A missing guard and a
missing interpreter leave nothing to ask, so the operator's policy is the whole
answer. A replaced plugin is different in kind: its guard and its interpreter
are still there, and the refusals that are facts about the target or the actor
do not depend on which plugin generation forwarded the event. Returning ahead
of the round trip dropped those refusals for every running session until the
host restarted.

The cases run the real plugin through Node. The protected-path cases use the
real guard; the answer-shape cases use a stand-in guard so each answer the
previous generation might receive is named exactly.
"""

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

from test_guard_hostile_matrix import active_project  # noqa: E402
from test_hermetic_env import HOST_SESSION_VARIABLES, isolate_host_session  # noqa: E402

NODE = shutil.which("node")
PLUGIN = ROOT / "extensions/adapters/opencode/saipen-guard.js"
EXECUTED = "HOST_TOOL_EXECUTED"
#: Larger than the plugin's bounded guard event (MAX_EVENT_BYTES, 256 KiB).
OVERSIZE = "x" * (300 * 1024)


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
  const system = { system: [] };
  await hooks["experimental.chat.system.transform"]({ sessionID: item.id }, system);
  const result = { id: item.id, outcome: "allowed", message: "", system: system.system };
  try {
    await hooks["tool.execute.before"](
      { tool: "write", sessionID: item.id },
      { args: { filePath: item.target, content: item.content } },
    );
    // The host executes the tool only when the hook returns.
    fs.mkdirSync(item.target_parent, { recursive: true });
    fs.writeFileSync(item.target, item.content);
  } catch (error) {
    result.outcome = "blocked";
    result.message = String(error.message || error);
  }
  results.push(result);
  for (const [key, value] of Object.entries(saved)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
}
process.stdout.write(JSON.stringify(results));
'''

#: A stand-in guard. The binding probe forwards a `read` event and gets a
#: neutral answer; the tool under test gets the one answer its case names.
STAND_IN = r'''
import json
import sys

ANSWER = {answer!r}
event = json.loads(sys.stdin.read() or "{{}}") if "guard" in sys.argv else {{}}
if event.get("tool_name") != "write":
    print(json.dumps({{"admitted": True, "code": "NOT_SAIPEN_PROJECT"}}))
    raise SystemExit(0)
if ANSWER == "garbage":
    print("this is not a guard verdict")
    raise SystemExit(3)
if ANSWER == "silent":
    raise SystemExit(1)
print(json.dumps({{"admitted": False, "code": ANSWER}}))
raise SystemExit(1)
'''


@unittest.skipUnless(NODE, "native Node runtime unavailable")
class StalePluginGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="saipen-t1688-stale-")
        cls.tmp = Path(cls.temporary.name)
        cls.project = active_project()
        cls.canonical = {
            name: (cls.project / ".saipen" / name).read_bytes()
            for name in ("LOG.md", "BOARD.md", "STATE.md")
        }
        cls.targets: dict[str, Path] = {}
        cls.contents: dict[str, str] = {}
        cases = []

        def case(identifier, target, *, mode=None, stand_in=None, stale=True, lost=None,
                 content=EXECUTED):
            home = cls.tmp / identifier
            profile = home / "profile"
            (profile / ".saipen").mkdir(parents=True)
            if mode is not None:
                (profile / ".saipen/authority.json").write_text(
                    json.dumps({"mode": mode}), encoding="utf-8"
                )
            plugin = home / "saipen-guard.mjs"
            shutil.copyfile(PLUGIN, plugin)
            skill = ROOT
            if stand_in is not None:
                skill = home / "skill"
                (skill / "tools").mkdir(parents=True)
                (skill / "tools/saipen.py").write_text(
                    STAND_IN.format(answer=stand_in), encoding="utf-8"
                )
            env = {name: None for name in HOST_SESSION_VARIABLES}
            env.update({
                "SAIPEN_SKILL_ROOT": str(skill),
                "SAIPEN_PYTHON": sys.executable,
                "USERPROFILE": str(profile),
                "HOME": str(profile),
            })
            if lost == "guard":
                env["SAIPEN_SKILL_ROOT"] = str(home / "absent")
            elif lost == "python":
                env.update({"SAIPEN_PYTHON": "saipen-missing-python", "PATH": ""})
            cls.targets[identifier] = target
            cls.contents[identifier] = content
            cases.append({
                "id": identifier,
                "project": str(cls.project),
                "plugin": str(plugin),
                "env": env,
                "stale": stale,
                "target": str(target),
                "target_parent": str(target.parent),
                "content": content,
            })

        memory = cls.project / ".saipen"
        case("protected-default", memory / "LOG.md")
        case("protected-degraded", memory / "BOARD.md", mode="degraded")
        case("protected-strict", memory / "STATE.md", mode="strict")
        case("ordinary-default", cls.project / "src" / "ordinary-default.txt")
        case("ordinary-degraded", cls.project / "src" / "ordinary-degraded.txt", mode="degraded")
        outside = cls.tmp / "effects"
        case("answer-terminal", outside / "terminal.txt", stand_in="PATH_ESCAPES_PROJECT")
        case("answer-ownership", outside / "ownership.txt", stand_in="OWNERSHIP_CONFLICT")
        case("answer-refusal", outside / "refusal.txt", stand_in="NO_ACTIVE_WORK")
        case("answer-garbage", outside / "garbage.txt", stand_in="garbage")
        case("answer-silent", outside / "silent.txt", stand_in="silent")
        case("healthy-refusal", outside / "healthy.txt", stand_in="NO_ACTIVE_WORK", stale=False)
        case("stale-and-no-guard", outside / "no-guard.txt", lost="guard")
        case("stale-and-no-python", outside / "no-python.txt", lost="python")
        case("no-guard-oversize", outside / "no-guard-oversize.txt", lost="guard", stale=False,
             content=OVERSIZE)
        case("stale-oversize", cls.project / "src" / "stale-oversize.txt", content=OVERSIZE)

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

    def marker(self, identifier) -> dict:
        found = [
            message for message in self.results[identifier]["system"]
            if message.startswith("SAIPEN_HOST_INTEGRATION ")
        ]
        self.assertEqual(len(found), 1, self.results[identifier]["system"])
        return json.loads(found[0].splitlines()[0].split(" ", 1)[1])

    def blocked(self, identifier, code) -> None:
        record = self.results[identifier]
        self.assertEqual(record["outcome"], "blocked", record)
        self.assertIn(f"SAIPEN_GUARD_REFUSAL: {code}:", record["message"])
        self.assertIn("the host tool did not execute", record["message"])

    def degraded(self, identifier, gap="PLUGIN_RESTART_REQUIRED") -> None:
        record = self.results[identifier]
        self.assertEqual(record["outcome"], "allowed", record["message"])
        self.assertEqual(
            self.targets[identifier].read_text(encoding="utf-8"), self.contents[identifier]
        )
        marker = self.marker(identifier)
        self.assertEqual(marker["adapter_code"], gap)
        self.assertEqual(marker["status"], "UNVERIFIED")
        self.assertEqual(marker["decision"], "ALLOW_DEGRADED")

    def test_a_replaced_plugin_still_refuses_a_protected_canonical_path(self):
        for identifier, name in (("protected-default", "LOG.md"),
                                 ("protected-degraded", "BOARD.md")):
            with self.subTest(case=identifier):
                self.blocked(identifier, "PROTECTED_CANONICAL_NAMESPACE")
                self.assertEqual(
                    (self.project / ".saipen" / name).read_bytes(), self.canonical[name]
                )
                # The gap is still reported: the refusal is the guard's, the
                # generation mismatch stays UNVERIFIED and degradable.
                self.assertEqual(self.marker(identifier)["decision"], "ALLOW_DEGRADED")

    def test_ordinary_work_still_proceeds_unverified_under_a_replaced_plugin(self):
        for identifier in ("ordinary-default", "ordinary-degraded"):
            with self.subTest(case=identifier):
                self.degraded(identifier)

    def test_every_target_or_actor_refusal_survives_the_gap_with_its_own_code(self):
        for identifier, code in (("answer-terminal", "PATH_ESCAPES_PROJECT"),
                                 ("answer-ownership", "OWNERSHIP_CONFLICT")):
            with self.subTest(case=identifier):
                self.blocked(identifier, code)
                self.assertFalse(self.targets[identifier].exists())

    def test_any_other_answer_of_the_previous_generation_degrades(self):
        # A refusal about project state, an answer that is not a verdict and no
        # answer at all are what generation drift produces. Blocking on them
        # is the lockout the default policy exists to prevent.
        for identifier in ("answer-refusal", "answer-garbage", "answer-silent"):
            with self.subTest(case=identifier):
                self.degraded(identifier)

    def test_a_replaced_plugin_with_nothing_left_to_ask_degrades_as_before(self):
        # The replaced plugin is reported first, so it can hide a guard or an
        # interpreter that is gone as well. The round trip then cannot be made,
        # which is one more unreadable answer and degrades like the others.
        for identifier in ("stale-and-no-guard", "stale-and-no-python"):
            with self.subTest(case=identifier):
                self.degraded(identifier)

    def test_a_gap_with_nothing_to_ask_builds_no_event(self):
        # No guard means no round trip and therefore no bounded event: a
        # payload a current plugin would refuse as too large to forward still
        # proceeds here, exactly as it did before the replaced plugin learned
        # to keep asking. An uninstalled guard must not go on refusing work.
        self.degraded("no-guard-oversize", gap="SAIPEN_GUARD_UNINSTALLED")

    def test_padding_the_payload_does_not_buy_the_allowance(self):
        # The previous generation keeps its own payload rule. Otherwise an
        # event too large to forward would skip the very question this gap
        # still can ask.
        record = self.results["stale-oversize"]
        self.assertEqual(record["outcome"], "blocked", record["message"])
        self.assertIn("SAIPEN_GUARD_EVENT_OVERFLOW", record["message"])
        self.assertFalse(self.targets["stale-oversize"].exists())

    def test_strict_refuses_the_replaced_plugin_before_any_round_trip(self):
        record = self.results["protected-strict"]
        self.assertEqual(record["outcome"], "blocked", record)
        self.assertIn(
            "SAIPEN_GUARD_REFUSAL: PLUGIN_RESTART_REQUIRED: UNVERIFIED STRICT", record["message"]
        )
        self.assertIn("next: restart the host application", record["message"])
        self.assertEqual(
            (self.project / ".saipen/STATE.md").read_bytes(), self.canonical["STATE.md"]
        )

    def test_a_current_plugin_keeps_its_ordinary_refusal(self):
        # Control for the stand-in: without the gap the same answer refuses, so
        # the degrading cases above are about the gap and not about the guard.
        # Which refusal a current plugin words it as is not this test's claim.
        record = self.results["healthy-refusal"]
        self.assertEqual(record["outcome"], "blocked", record)
        self.assertIn("the host tool did not execute", record["message"])
        self.assertFalse(self.targets["healthy-refusal"].exists())
        self.assertNotIn(
            "SAIPEN_HOST_INTEGRATION",
            "".join(message[:32] for message in record["system"]),
        )


if __name__ == "__main__":
    unittest.main()
