"""T-1553: the response contract must activate in the SAME session as `saipen init`.

The observed field regression: a host that starts in a NON-SAIPEN project, runs
`saipen init`, and then completes operationally could still return a long
free-form report. Root cause in the OpenCode adapter: the bootstrap binding was
resolved once when the plugin factory was instantiated and the final-response
gate read that frozen value, so a session whose cached binding was
`NOT_SAIPEN_PROJECT` kept response enforcement disabled for its whole life --
even after the live project had become a SAIPEN project.

TWO carriers drive the REAL plugin artifact through the real node module runtime
and a REAL spawned guard, and they are deliberately NOT the same claim:

* `RealLauncherInit` proves **REAL_CLI_LAUNCHER_INIT_E2E_SAME_TURN_PROVED**.
  The `saipen init` command is admitted through the real
  `tool.execute.before`, the host shell then executes the ACTUAL installed
  `bin/saipen.cmd init` through the OS command interpreter, and the final
  response of THAT SAME TURN is gated. This is the true CLI end-to-end carrier.
* `RealInitSameTurn` proves **REAL_CANONICAL_INIT_EFFECT_SAME_TURN_PROVED**
  only: the same turn, same admission path, same gate, but the INIT effect is
  reached by importing `saipen_engine.init_project.bootstrap_project` in a
  spawned interpreter rather than by running the launcher. It is the
  canonical-effect regression and is never quoted as launcher end-to-end.
* `MaterializationRebind` proves **MATERIALIZATION_REBIND_PROVED** only: bytes
  appearing in `.saipen/` mid-session upgrade a frozen binding. It is the
  lower-level binding-refresh regression and is never quoted as the real init
  behaviour.

All three use the same driver, the same admission path and the same oracle;
only what materializes the project differs.

    plugin created against a plain directory      -> binding NOT_SAIPEN_PROJECT
    [handshake: the host executes the real init]
    admitted canonical command runs in session    -> the turn is operational
    final response, free-form report              -> MUST be rejected
    final response, canonical control surface     -> MUST pass
    a later free-form report in the same session  -> MUST still be rejected

The subject is `SAIPEN_OPENCODE_PLUGIN_UNDER_TEST` when set, otherwise the
repository artifact. That is the VERIFY-ORACLE-01 pre-fix control: point the
identical fixture, oracle and assertions at a copy of the un-repaired adapter
and the free-form escapes must be admitted.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from saipen_engine.paths import identity_file_content, new_project_lineage  # noqa: E402

from saipen_engine.response_surface import (  # noqa: E402
    DETAIL_MODE_AUDIT,
    DETAIL_MODE_BOUNDARY,
    DETAIL_MODE_HANDOFF,
    DETAIL_MODE_NONE,
    DETAIL_MODE_REPORT,
    DETAIL_MODES,
    FIELD_CHAR_BUDGETS,
    FIELD_LINE_BUDGETS,
    ORDINARY_RESPONSE_CHAR_BUDGET,
    classify_final_response,
    detail_mode_for_request,
    response_errors,
)

from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

def setUpModule() -> None:
    # An outer host session must never bind this module's disposable fixtures.
    isolate_host_session()

PLUGIN = Path(
    os.environ.get(
        "SAIPEN_OPENCODE_PLUGIN_UNDER_TEST",
        str(REPO / "extensions" / "adapters" / "opencode" / "saipen-guard.js"),
    )
)
NODE = shutil.which("node")
PYTHON = shutil.which("python") or shutil.which("python3")

#: T-1556 #4: the ACTUAL installed CLI launcher of this tree, in the only form
#: this host can execute. `host_bootstrap._launcher` reports it as
#: `direct_launcher`; the carrier below runs THAT FILE, not a stand-in.
LAUNCHER = REPO / "bin" / ("saipen.cmd" if os.name == "nt" else "saipen")
LAUNCHER_USABLE = LAUNCHER.is_file() and (os.name == "nt" or os.access(LAUNCHER, os.X_OK))

#: The exact field-regression shape: an operational completion reported as
#: free-form prose with section headings and bullets.
FREE_FORM = """SAIMASTER init complete. Wave 1 built everything the operator asked for.

What was done:
- created .saipen/STATE.md, BOARD.md and LOG.md from the canonical templates
- bound the project identity and recorded the seat
- confirmed the guard is reachable from the host shell

Tests:
- 42 focused tests pass
- ruff clean

Backlog:
- wire the response gate into the remaining hosts
- re-check the distribution stamp
"""

#: A valid EXEC-RESPONSE-01 surface for the same terminal moment. A real
#: `saipen init` ends in WAIT -- the fresh STATE carries
#: `WAIT: init -- provide the first project goal or raw backlog`, so the
#: canonical automation block reports an operator action as DUE and a surface
#: claiming `OPERATOR ACTION: NONE` is genuinely invalid here. The VALIDATION
#: field must also begin with the project's CURRENT validation token (the
#: canonical status reports `NOT_RUN` for this fixture), and STATUS must name
#: the current phase.
VALID_SURFACE = """STATUS
WAIT -- init complete; project bound, phase PLAN
RESULT
canonical control surface returned after the mid-session init
BLOCKER
NONE
OPERATOR ACTION
provide the first project goal or raw backlog
NEXT EXACT ACTION
NONE
VALIDATION
NOT_RUN -- focused carrier green
"""

#: The canonical INIT command a user issues in a non-SAIPEN directory. The
#: adapter must ADMIT it (classification NON_SAIPEN) and must mark the turn
#: operational, which is what makes the response gate apply at all.
INIT_COMMAND = "saipen init"

DRIVER = r"""
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";

const [pluginPath, requestPath] = process.argv.slice(2);
const request = JSON.parse(fs.readFileSync(requestPath, "utf8"));
const module = await import(pathToFileURL(pluginPath).href);
const factory = module.SaipenGuard || module.default;

function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

const results = [];

for (const item of request.cases) {
  const record = { id: item.id, steps: [], exports: Object.keys(module), hooks: [] };
  const context = { worktree: item.project, directory: item.project };
  const plugin = await factory(context);
  record.hooks = Object.keys(plugin || {});
  const systemHook = plugin["experimental.chat.system.transform"];
  const toolHook = plugin["tool.execute.before"];
  const textHook = plugin["experimental.text.complete"];

  async function systemStep() {
    const step = { kind: "system", outcome: "allowed", message: "", system: [] };
    try {
      const output = { system: [] };
      await systemHook({ sessionID: item.session }, output);
      step.system = output.system;
    } catch (error) {
      step.outcome = "blocked";
      step.message = String((error && error.message) || error);
    }
    record.steps.push(step);
  }

  // The host's own effect: the REAL canonical INIT, executed as a spawned
  // canonical process inside this same plugin instance and this same logical
  // host session. Nothing about the plugin is recreated or re-imported.
  function initStep(spec) {
    const step = { kind: "init", outcome: "allowed", message: "", stdout: "" };
    const code = [
      "import json, sys",
      `sys.path.insert(0, ${JSON.stringify(path.join(item.repo, "tools"))})`,
      "from saipen_engine.init_project import bootstrap_project",
      `print(json.dumps(bootstrap_project(${JSON.stringify(item.project)},`,
      `    agent=${JSON.stringify(item.agent || "test-agent")})))`,
    ].join("\n");
    const proc = spawnSync(process.env.SAIPEN_CARRIER_PYTHON || "python",
      ["-c", code], { encoding: "utf8", timeout: 120000, windowsHide: true });
    step.stdout = String((proc && proc.stdout) || "");
    if (!proc || proc.status !== 0) {
      step.outcome = "failed";
      step.message = String((proc && proc.stderr) || "init process did not run");
    } else {
      try { step.written = Object.keys(JSON.parse(step.stdout)); } catch (_e) { step.written = []; }
    }
    record.steps.push(step);
  }

  // T-1556 #4: the host's own effect at full strength -- the ACTUAL installed
  // CLI launcher, executed by the OS command interpreter, exactly as a user
  // typing `saipen init` in this directory would produce it. Nothing is
  // imported in-process and no canonical function is called directly.
  function launcherInitStep(spec) {
    const step = { kind: "init-launcher", outcome: "allowed", message: "", stdout: "" };
    const argv = [item.launcher, "init", "--project-root", item.project,
      "--agent", item.agent || "test-agent", "--json"];
    const proc = process.platform === "win32"
      ? spawnSync(process.env.ComSpec || "cmd.exe", ["/d", "/s", "/c", ...argv],
          { encoding: "utf8", timeout: 180000, windowsHide: true })
      : spawnSync(argv[0], argv.slice(1),
          { encoding: "utf8", timeout: 180000, windowsHide: true });
    step.stdout = String((proc && proc.stdout) || "");
    step.stderr = String((proc && proc.stderr) || "");
    if (!proc || proc.status !== 0) {
      step.outcome = "failed";
      step.message = step.stderr || step.stdout || "launcher init did not run";
    } else {
      try { step.payload = JSON.parse(step.stdout); } catch (_e) { step.payload = null; }
      if (!step.payload || step.payload.code !== "INIT_COMPLETED") {
        step.outcome = "failed";
        step.message = `launcher did not report INIT_COMPLETED: ${step.stdout.slice(0, 300)}`;
      }
    }
    record.steps.push(step);
  }

  async function toolStep(spec) {
    const step = { kind: "tool", outcome: "allowed", message: "" };
    try {
      await toolHook(spec.input, spec.output);
    } catch (error) {
      step.outcome = "blocked";
      step.message = String((error && error.message) || error);
    }
    record.steps.push(step);
  }

  async function textStep(spec) {
    const step = { kind: "text", outcome: "allowed", message: "" };
    try {
      await textHook(
        { sessionID: item.session },
        { text: spec.text, messageID: spec.messageID || null },
      );
    } catch (error) {
      step.outcome = "blocked";
      step.message = String((error && error.message) || error);
    }
    record.steps.push(step);
  }

  await systemStep();
  fs.writeFileSync(item.ready, JSON.stringify({ hooks: record.hooks }));
  const deadline = Date.now() + (item.wait_ms || 120000);
  while (!fs.existsSync(item.go)) {
    if (Date.now() > deadline) throw new Error("carrier handshake timed out");
    await sleep(100);
  }
  for (const spec of item.steps || []) {
    if (spec.kind === "tool") await toolStep(spec);
    else if (spec.kind === "text") await textStep(spec);
    else if (spec.kind === "init") initStep(spec);
    else if (spec.kind === "init-launcher") launcherInitStep(spec);
    else await systemStep();
  }
  results.push(record);
}

process.stdout.write(JSON.stringify(results));
"""


def _init_steps(free_form: str, valid: str) -> list[dict]:
    return [
        {"kind": "tool", "input": {"tool": "bash", "sessionID": "ses_t1553"},
         "output": {"args": {"command": INIT_COMMAND}}},
        {"kind": "init"},
        {"kind": "text", "text": free_form},
        {"kind": "text", "text": valid},
        {"kind": "text", "text": free_form},
    ]


def _spawn_carrier(case: dict, workdir: Path, env: dict):
    ready = workdir / "ready.json"
    go = workdir / "go"
    driver = workdir / "driver.mjs"
    driver.write_text(DRIVER, encoding="utf-8")
    request = workdir / "request.json"
    request.write_text(json.dumps({"cases": [{**case, "ready": str(ready), "go": str(go)}]}),
                        encoding="utf-8")
    proc = subprocess.Popen(
        [NODE, str(driver), str(PLUGIN), str(request)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    )
    try:
        deadline = time.time() + 180
        while not ready.exists():
            if proc.poll() is not None:
                stdout, stderr = proc.communicate()
                raise AssertionError(f"carrier exited before the handshake: {stdout!r} {stderr!r}")
            if time.time() > deadline:
                proc.kill()
                raise AssertionError("carrier never reached the init handshake")
            time.sleep(0.1)
        before = json.loads(ready.read_text(encoding="utf-8"))
        go.write_text("go", encoding="utf-8")
        stdout, stderr = proc.communicate(timeout=600)
    finally:
        if proc.poll() is None:
            proc.kill()
    if proc.returncode != 0:
        raise AssertionError(f"carrier failed: {stderr}")
    return before, json.loads(stdout)[0]


def _carrier_env() -> dict:
    env = {**os.environ}
    for carrier in ("SAIPEN_PROJECT_ROOT", "SAIPEN_PROJECT_LINEAGE", "SAIPEN_AGENT"):
        env.pop(carrier, None)
    env.pop("SAIPEN_GUARD_STARTUP_PROBE", None)
    env["SAIPEN_AGENT"] = "test-agent"
    env["SAIPEN_CARRIER_PYTHON"] = PYTHON or "python"
    # The guard resolves its canonical runtime through SAIPEN_SKILL_ROOT and
    # otherwise falls back to the INSTALLED skill copy. Left unset, this
    # regression test silently measured the installed runtime while claiming to
    # measure the repository artifact: a checker fix in this tree changed
    # nothing the carrier could see. Pin the runtime to the repository so the
    # oracle and the enforcement path are the same bytes.
    env["SAIPEN_SKILL_ROOT"] = str(REPO)
    return env


class _PluginCarrier(unittest.TestCase):
    """Shared real-plugin carrier. Subclasses choose what materializes `.saipen/`."""

    maxDiff = None

    def _run_carrier(self, steps: list[dict]):
        workdir = Path(tempfile.mkdtemp(prefix="saipen-t1553-carrier-"))
        self.addCleanup(lambda: shutil.rmtree(workdir, ignore_errors=True))
        project = workdir / "host-project"
        project.mkdir()
        (project / "app.py").write_text("print('ordinary project')\n", encoding="utf-8")
        case = {
            "id": "mid-session-init",
            "project": str(project),
            "repo": REPO.as_posix(),
            "agent": "test-agent",
            "session": "ses_t1553",
            "launcher": str(LAUNCHER),
            "steps": steps,
        }
        before, record = _spawn_carrier(case, workdir, _carrier_env())
        return before, record, project

    def assert_started_outside_saipen(self, before: dict, record: dict) -> None:
        system = record["steps"][0]
        self.assertEqual(system["kind"], "system")
        self.assertTrue(system["system"], record)
        self.assertIn(
            '"binding_code":"NOT_SAIPEN_PROJECT"',
            system["system"][0].replace(" ", ""),
            "the carrier must start OUTSIDE a SAIPEN project",
        )


def bootstrap_canonical_project(root: Path) -> None:
    """Hand-written canonical-looking bytes. MATERIALIZATION only.

    Kept for the lower-level binding-refresh regression. It is NOT the real
    INIT effect: the shapes here are the test's own strings, not the shipped
    templates filled by `saipen_engine.init_project`. Any claim about real
    `saipen init` behaviour must come from `RealLauncherInit` (launcher
    end-to-end) or `RealInitSameTurn` (the canonical INIT effect).
    """
    saipen = root / ".saipen"
    saipen.mkdir(parents=True, exist_ok=True)
    (saipen / "IDENTITY.md").write_text(
        identity_file_content(new_project_lineage()), encoding="utf-8"
    )
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (saipen / "STATE.md").write_text(
        "---\n"
        "phase: PLAN\n"
        "task: none\n"
        'next_action: "saipen continue"\n'
        'blocker: ""\n'
        "transition_from: INIT\n"
        "saipen_version: 8\n"
        "schema_version: 3\n"
        "last_event: 100\n"
        f"style_contract: {CURRENT_STYLE_CONTRACT}\n"
        "mode: full\n"
        f"updated: {stamp}\n"
        "agent: test-agent\n"
        f'saipen_home: "{REPO.as_posix()}"\n'
        "execution_intent: normal\n"
        "---\n",
        encoding="utf-8",
    )
    (saipen / "BOARD.md").write_text(
        "## DOING\n## TODO\n## DONE\n## BLOCKED\n", encoding="utf-8"
    )
    (saipen / "LOG.md").write_text(
        "- 28.09.26 00:00 [E-100] [agent: test-agent] RUN: init carrier fixture\n",
        encoding="utf-8",
    )


@unittest.skipUnless(NODE, "node runtime unavailable")
@unittest.skipUnless(PYTHON, "no python runtime for the guard round trip")
@unittest.skipUnless(LAUNCHER_USABLE, "installed CLI launcher not executable here")
class RealLauncherInit(_PluginCarrier):
    """REAL_CLI_LAUNCHER_INIT_E2E_SAME_TURN_PROVED: the launcher gates its own turn.

    The strongest of the three carriers and the only one that may be quoted as
    CLI end-to-end: the host shell runs the real `bin/saipen[.cmd] init` on the
    plain project directory, exactly as the operator's own keystroke would, and
    the very next final response in that same session is gated.
    """

    def _launcher_steps(self, free_form: str, valid: str) -> list[dict]:
        return [
            {"kind": "tool", "input": {"tool": "bash", "sessionID": "ses_t1553"},
             "output": {"args": {"command": INIT_COMMAND}}},
            {"kind": "init-launcher"},
            {"kind": "text", "text": free_form},
            {"kind": "text", "text": valid},
            {"kind": "text", "text": free_form},
        ]

    def test_the_installed_launcher_init_gates_its_own_turn(self):
        before, record, project = self._run_carrier(
            self._launcher_steps(FREE_FORM, VALID_SURFACE)
        )
        self.assert_started_outside_saipen(before, record)

        tool_step, init_step, first, valid, later = record["steps"][1:6]
        self.assertEqual(tool_step["outcome"], "allowed", tool_step)
        self.assertEqual(init_step["kind"], "init-launcher", init_step)
        self.assertEqual(
            init_step["outcome"], "allowed",
            f"the installed CLI launcher did not complete the init: {init_step.get('message')}",
        )
        # The launcher really ran, and it really wrote the canonical project.
        self.assertEqual((init_step.get("payload") or {}).get("code"), "INIT_COMPLETED")
        written = init_step["payload"]
        self.assertTrue(
            Path(written["project_root"]) / ".saipen" / "STATE.md",
            "the launcher must have written canonical STATE at the bound root",
        )
        self.assertIn("EXEC_RESPONSE_INVALID", first["message"])
        self.assertEqual(valid["outcome"], "allowed", valid)
        self.assertEqual(later["outcome"], "blocked", later)
        state = (project / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        self.assertIn("transition_from: INIT", state)

    def test_the_launcher_carrier_rejects_prose_before_status_too(self):
        escaped = "STATUS: done\n\n" + FREE_FORM
        _before, record, _project = self._run_carrier(
            self._launcher_steps(escaped, VALID_SURFACE)
        )
        first = record["steps"][3]
        self.assertEqual(first["outcome"], "blocked", first)
        self.assertIn("EXEC_RESPONSE_INVALID", first["message"])


@unittest.skipUnless(NODE, "node runtime unavailable")
@unittest.skipUnless(PYTHON, "no python runtime for the guard round trip")
class RealInitSameTurn(_PluginCarrier):
    """REAL_CANONICAL_INIT_EFFECT_SAME_TURN_PROVED: the canonical INIT effect.

    Same turn, same admission path, same gate as the launcher carrier -- but
    the INIT effect is reached by importing `bootstrap_project` in a spawned
    interpreter. That proves the canonical INIT effect is gated in the turn that
    produced it. It does NOT prove launcher/CLI end-to-end; `RealLauncherInit`
    says that, and only that.
    """

    def test_real_init_gates_the_final_response_of_its_own_turn(self):
        before, record, project = self._run_carrier(_init_steps(FREE_FORM, VALID_SURFACE))
        self.assert_started_outside_saipen(before, record)

        tool_step, init_step, first, valid, later = record["steps"][1:6]
        self.assertEqual(tool_step["kind"], "tool")
        self.assertEqual(
            tool_step["outcome"], "allowed",
            f"the canonical init command must be admitted from a non-SAIPEN cwd: {tool_step}",
        )
        self.assertEqual(
            init_step["kind"], "init", "the host must execute the real init effect"
        )
        self.assertEqual(
            init_step["outcome"], "allowed",
            f"the real canonical INIT did not run: {init_step.get('message')}",
        )
        self.assertIn("state", init_step.get("written") or [], init_step)
        self.assertIn("identity", init_step.get("written") or [], init_step)

        self.assertEqual(first["kind"], "text")
        self.assertEqual(
            first["outcome"], "blocked",
            "free-form operational prose escaped the EXEC-RESPONSE-01 gate after init",
        )
        self.assertIn("EXEC_RESPONSE_INVALID", first["message"])
        self.assertEqual(valid["outcome"], "allowed", f"a canonical surface must pass: {valid}")
        self.assertNotIn("EXEC_RESPONSE_INVALID", valid["message"])
        self.assertEqual(
            later["outcome"], "blocked", "the later turn in the same session stopped being enforced"
        )
        # The project really did become a SAIPEN project inside the session,
        # from the shipped templates rather than from test-authored strings.
        state = (project / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        self.assertIn(f"style_contract: {CURRENT_STYLE_CONTRACT}", state)
        self.assertIn("transition_from: INIT", state)

    def test_the_init_turn_is_gated_without_a_canonical_command_first(self):
        """The init turn is operational BECAUSE the project became bound.

        The other tests issue `saipen init` through `tool.execute.before`, which
        also marks the turn operational by the command path. Deleting the
        adapter's init-turn marking entirely left them green, so the marking was
        unproven. Here the host materializes the project and the final response
        arrives with NO tool event at all -- the only fact that marks this turn
        operational is the binding upgrade, which is the case the ticket names.
        """
        steps = [
            {"kind": "init"},
            {"kind": "text", "text": FREE_FORM},
            {"kind": "text", "text": VALID_SURFACE},
        ]
        _before, record, _project = self._run_carrier(steps)
        _init, first, valid = record["steps"][1:4]
        self.assertEqual(
            first["outcome"], "blocked",
            f"the init turn escaped the gate with no tool event: {first}",
        )
        self.assertIn("EXEC_RESPONSE_INVALID", first["message"])
        self.assertEqual(valid["outcome"], "allowed", f"a canonical surface must pass: {valid}")

    def test_prose_before_status_is_rejected_in_the_init_turn(self):
        escaped = "STATUS: done\n\n" + FREE_FORM
        _before, record, _project = self._run_carrier(_init_steps(escaped, VALID_SURFACE))
        first = record["steps"][3]
        self.assertEqual(first["outcome"], "blocked", first)
        self.assertIn("EXEC_RESPONSE_INVALID", first["message"])

    def test_a_replacement_model_is_still_enforced_immediately_after_init(self):
        """Matrix K: provider/model replacement in the same turn loses nothing.

        The gate must not depend on the incumbent's private memory: a fresh
        model request re-enters `experimental.chat.system.transform`, and the
        final response that follows it is still the init turn's response.
        """
        steps = _init_steps(FREE_FORM, VALID_SURFACE)
        steps.insert(2, {"kind": "system"})
        _before, record, _project = self._run_carrier(steps)
        _tool, _init, model_step, first, valid, later = record["steps"][1:7]
        self.assertEqual(model_step["kind"], "system")
        self.assertEqual(model_step["outcome"], "allowed", model_step)
        self.assertEqual(
            first["outcome"], "blocked",
            f"a replaced model escaped the gate on the init turn: {first}",
        )
        self.assertIn("EXEC_RESPONSE_INVALID", first["message"])
        self.assertEqual(valid["outcome"], "allowed", valid)
        self.assertEqual(later["outcome"], "blocked", later)

    def test_a_replacement_model_cannot_smuggle_free_form_later_either(self):
        steps = [
            {"kind": "tool", "input": {"tool": "bash", "sessionID": "ses_t1553"},
             "output": {"args": {"command": INIT_COMMAND}}},
            {"kind": "init"},
            {"kind": "text", "text": VALID_SURFACE},
            {"kind": "system"},
            {"kind": "text", "text": FREE_FORM},
        ]
        _before, record, _project = self._run_carrier(steps)
        # steps[0] is the plugin's own startup system step, so the five carrier
        # steps land at 1..5 and the free-form smuggling attempt is the LAST.
        tail = record["steps"][5]
        self.assertEqual(tail["outcome"], "blocked", tail)
        self.assertIn("EXEC_RESPONSE_INVALID", tail["message"])


@unittest.skipUnless(NODE, "node runtime unavailable")
@unittest.skipUnless(PYTHON, "no python runtime for the guard round trip")
class MaterializationRebind(_PluginCarrier):
    """MATERIALIZATION_REBIND_PROVED: a frozen binding upgrades when bytes appear.

    The lower-level regression, kept honest: it proves the adapter re-asks the
    canonical resolver instead of trusting its startup cache. It says nothing
    about a real `saipen init` -- `RealLauncherInit` and `RealInitSameTurn` say that.
    """

    def _run_materialized(self, free_form: str = FREE_FORM, valid: str = VALID_SURFACE):
        workdir = Path(tempfile.mkdtemp(prefix="saipen-t1553-materialized-"))
        self.addCleanup(lambda: shutil.rmtree(workdir, ignore_errors=True))
        project = workdir / "host-project"
        project.mkdir()
        case = {
            "id": "materialization-rebind",
            "project": str(project),
            "repo": REPO.as_posix(),
            "session": "ses_t1553",
            "steps": [
                {"kind": "tool", "input": {"tool": "bash", "sessionID": "ses_t1553"},
                 "output": {"args": {"command": "saipen status"}}},
                {"kind": "text", "text": free_form},
                {"kind": "text", "text": valid},
                {"kind": "text", "text": free_form},
            ],
        }
        ready = workdir / "ready.json"
        go = workdir / "go"
        driver = workdir / "driver.mjs"
        driver.write_text(DRIVER, encoding="utf-8")
        request = workdir / "request.json"
        request.write_text(json.dumps({"cases": [{**case, "ready": str(ready), "go": str(go)}]}),
                           encoding="utf-8")
        env = _carrier_env()
        proc = subprocess.Popen(
            [NODE, str(driver), str(PLUGIN), str(request)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        )
        try:
            deadline = time.time() + 180
            while not ready.exists():
                if proc.poll() is not None:
                    stdout, stderr = proc.communicate()
                    self.fail(f"carrier exited early: {stdout!r} {stderr!r}")
                if time.time() > deadline:
                    proc.kill()
                    self.fail("carrier never reached the handshake")
                time.sleep(0.1)
            before = json.loads(ready.read_text(encoding="utf-8"))
            # Test-authored bytes, NOT the canonical INIT effect.
            bootstrap_canonical_project(project)
            go.write_text("go", encoding="utf-8")
            stdout, stderr = proc.communicate(timeout=600)
        finally:
            if proc.poll() is None:
                proc.kill()
        self.assertEqual(proc.returncode, 0, stderr)
        return before, json.loads(stdout)[0], project

    def test_a_frozen_not_saipen_binding_upgrades_and_gates(self):
        before, record, _project = self._run_materialized()
        self.assert_started_outside_saipen(before, record)
        tool_step, first, valid, later = record["steps"][1:5]
        self.assertEqual(tool_step["outcome"], "allowed", tool_step)
        self.assertEqual(first["outcome"], "blocked", first)
        self.assertIn("EXEC_RESPONSE_INVALID", first["message"])
        self.assertEqual(valid["outcome"], "allowed", valid)
        self.assertEqual(later["outcome"], "blocked", later)

    def test_prose_before_status_is_rejected(self):
        escaped = "STATUS: done\n\n" + FREE_FORM
        _before, record, _project = self._run_materialized(free_form=escaped)
        first = record["steps"][2]
        self.assertEqual(first["outcome"], "blocked", first)
        self.assertIn("EXEC_RESPONSE_INVALID", first["message"])


def _surface(**fields) -> str:
    """Render one control surface from field content, in canonical order."""
    defaults = {
        "STATUS": "PLAN -- carrier",
        "RESULT": "one bounded result",
        "BLOCKER": "NONE",
        "OPERATOR ACTION": "NONE",
        "NEXT EXACT ACTION": "saipen continue",
        "VALIDATION": "NOT_RUN -- focused carrier green",
    }
    defaults.update(fields)
    order = ("STATUS", "RESULT", "BLOCKER", "OPERATOR ACTION", "NEXT EXACT ACTION",
             "VALIDATION", "DETAILS")
    return chr(10).join(
        f"{name}{chr(10)}{content}" for name, content in defaults.items()
        if name in order and content
    ) + chr(10)


class HostileResponseMatrix(unittest.TestCase):
    """T-1553 C/E: the ONE canonical checker, against the hostile shapes.

    The oracle is `response_surface.response_errors` /
    `classify_final_response` themselves -- the same authority every host gate
    calls -- so a host that trusts them cannot drift from the contract, and this
    matrix cannot pass while a host keeps its own laxer copy.
    """

    maxDiff = None

    def _reject(self, rendered: str, **context) -> list[str]:
        errors = response_errors(rendered, **context)
        klass, reasons = classify_final_response(
            rendered, operational_turn=True, **context
        )
        self.assertTrue(
            errors or reasons,
            f"the canonical checker accepted a hostile response:\n{rendered[:400]}",
        )
        self.assertNotEqual(
            klass, "VALID_BOUNDARY",
            f"classified VALID_BOUNDARY:{chr(10)}{rendered[:400]}"
        )
        # Both canonical verdicts are reasons to refuse; a caller that reads one
        # authority must not be able to call a hostile surface acceptable
        # because the other named it differently.
        return list(errors) + list(reasons)

    def _accept(self, rendered: str, **context) -> None:
        self.assertEqual(response_errors(rendered, **context), [], rendered[:400])
        klass, reasons = classify_final_response(
            rendered, operational_turn=True, **context
        )
        self.assertEqual(klass, "VALID_BOUNDARY", f"{klass}: {reasons}")

    # A -- an ordinary free-form operational report is not a boundary.
    def test_a_free_form_operational_report_is_rejected(self):
        errors = self._reject(FREE_FORM)
        self.assertTrue(any("control surface" in error for error in errors), errors)

    # B -- prose before STATUS.
    def test_b_prose_before_status_is_rejected(self):
        errors = self._reject("Everything went great.\n" + _surface())
        self.assertTrue(any("prose before STATUS" in error for error in errors), errors)

    # C -- RESULT over three content lines.
    def test_c_result_over_three_content_lines_is_rejected(self):
        errors = self._reject(_surface(RESULT="one\ntwo\nthree\nfour"))
        self.assertTrue(any("RESULT exceeds 3" in error for error in errors), errors)
        self.assertEqual(response_errors(_surface(RESULT="one\ntwo\nthree")), [])

    # D -- BLOCKER essay.
    def test_d_blocker_essay_is_rejected(self):
        errors = self._reject(
            _surface(BLOCKER="SOME_CODE -- first reason line\nand a second explanatory line")
        )
        self.assertTrue(any("BLOCKER exceeds 1" in error for error in errors), errors)

    def test_d_blocker_without_a_canonical_code_is_rejected(self):
        errors = self._reject(_surface(BLOCKER="the thing is very broken right now"))
        self.assertTrue(any("BLOCKER needs a canonical code" in e for e in errors), errors)

    # E -- OPERATOR ACTION essay.
    def test_e_operator_action_essay_is_rejected(self):
        errors = self._reject(_surface(**{"OPERATOR ACTION": "do this\nand then that"}))
        self.assertTrue(any("OPERATOR ACTION exceeds 1" in error for error in errors), errors)

    def test_e_operator_action_may_not_assign_agent_work(self):
        errors = self._reject(_surface(**{"OPERATOR ACTION": "run `saipen continue`"}))
        self.assertTrue(any("assign an agent command" in error for error in errors), errors)

    # F -- NEXT EXACT ACTION carrying more than one action.
    def test_f_next_exact_action_list_is_rejected(self):
        errors = self._reject(_surface(**{"NEXT EXACT ACTION": "- first\n- second"}))
        self.assertTrue(any("NEXT EXACT ACTION" in error for error in errors), errors)

    def test_f_next_exact_action_must_not_be_vague(self):
        errors = self._reject(_surface(**{"NEXT EXACT ACTION": "continue as appropriate"}))
        self.assertTrue(any("vague" in error for error in errors), errors)

    def test_f_next_exact_action_is_exactly_one_action(self):
        """T-1556: chaining, sequencing and a second command are not one action.

        `saipen validate && saipen continue`, `saipen validate; saipen continue`
        and `run tests then ship` all read as VALID_BOUNDARY before this.
        """
        for action in (
            "saipen validate && saipen continue",
            "saipen validate || saipen continue",
            "saipen validate; saipen continue",
            "saipen validate | saipen continue",
            "run tests then ship",
            "fix the guard and then re-run the carrier",
            "after that, close the ticket",
            "saipen validate saipen continue",
            "saipen frobnicate",
        ):
            with self.subTest(action=action):
                errors = self._reject(_surface(**{"NEXT EXACT ACTION": action}))
                self.assertTrue(
                    any("exactly one action" in error for error in errors), errors
                )

    def test_f_one_canonical_action_still_passes(self):
        for action in ("NONE", "saipen continue", "saipen continue --json",
                       "saipen validate --json"):
            with self.subTest(action=action):
                self._accept(_surface(**{"NEXT EXACT ACTION": action}))

    # G -- DETAILS as the overflow bucket the surface exists to remove.
    def test_g_details_cannot_be_an_unlimited_overflow_bucket(self):
        essay = chr(10).join(
            f"detail line {n}" for n in range(1, FIELD_LINE_BUDGETS["DETAILS"] + 2)
        )
        errors = self._reject(_surface(DETAILS=essay))
        self.assertTrue(any("DETAILS exceeds" in error for error in errors), errors)

    def test_g_six_line_result_plus_twenty_line_details_fails(self):
        """The exact hostile control: long RESULT AND long DETAILS together."""
        essay = chr(10).join(f"overflow {n}" for n in range(1, 21))
        errors = self._reject(_surface(RESULT="a\nb\nc\nd\ne\nf", DETAILS=essay))
        self.assertTrue(any("RESULT exceeds" in error for error in errors), errors)
        self.assertTrue(any("DETAILS exceeds" in error for error in errors), errors)

    # H -- the valid minimal control surface.
    def test_h_minimal_compact_control_surface_passes(self):
        self._accept(_surface())

    # T-1556 #2 -- a LINE COUNT is not a compactness contract. Every control
    # below was VALID_BOUNDARY while carrying a novel.
    def test_a_twelve_thousand_character_single_line_result_is_rejected(self):
        errors = self._reject(_surface(RESULT="x" * 12000))
        self.assertTrue(
            any(f"RESULT exceeds {FIELD_CHAR_BUDGETS['RESULT']}" in e for e in errors),
            errors,
        )

    def test_one_enormous_blocker_line_is_rejected(self):
        errors = self._reject(
            _surface(BLOCKER="SOME_CODE -- " + "reason " * 2000)
        )
        self.assertTrue(any("BLOCKER exceeds" in e for e in errors), errors)

    def test_eight_enormous_authorized_detail_lines_are_rejected(self):
        essay = chr(10).join("x" * 500 for _ in range(8))
        errors = self._reject(_surface(DETAILS=essay), detail_mode=DETAIL_MODE_REPORT)
        self.assertTrue(any("DETAILS exceeds" in e for e in errors), errors)

    def test_every_field_is_bounded_in_characters_not_only_in_lines(self):
        for field, budget in FIELD_CHAR_BUDGETS.items():
            with self.subTest(field=field):
                self.assertIsInstance(budget, int, field)
                self.assertGreater(budget, 0, field)
        self.assertEqual(
            set(FIELD_CHAR_BUDGETS), set(FIELD_LINE_BUDGETS) | {"STATUS"},
            "every line-budgeted field is also character-budgeted, plus STATUS",
        )

    def test_a_valid_normal_compact_response_still_passes(self):
        """The budgets must not have strangled the useful report."""
        self._accept(
            _surface(
                RESULT="Guard rebind fix landed in the OpenCode adapter\n"
                       "Response gate now re-resolves the live binding\n"
                       "154 focused tests green",
                VALIDATION="CURRENT_PASS -- focused suite green",
            )
        )

    def test_the_ordinary_total_ceiling_binds_where_the_field_budgets_do_not(self):
        """A ceiling that can never fire is decoration, not a contract."""
        self.assertLess(
            ORDINARY_RESPONSE_CHAR_BUDGET,
            sum(
                budget for name, budget in FIELD_CHAR_BUDGETS.items() if name != "DETAILS"
            ),
            "the whole-response ceiling must bind before every field can max out",
        )
        # Every field at its own legal maximum, and every one of them still
        # individually valid: only the total can refuse this.
        legal = _surface(
            STATUS="BUILD T-1556 " + "s" * (FIELD_CHAR_BUDGETS["STATUS"] - 14),
            RESULT="r" * FIELD_CHAR_BUDGETS["RESULT"],
            BLOCKER="SOME_CODE -- " + "b" * (
                FIELD_CHAR_BUDGETS["BLOCKER"] - len("SOME_CODE -- ")
            ),
            **{
                "OPERATOR ACTION": "o" * FIELD_CHAR_BUDGETS["OPERATOR ACTION"],
                "NEXT EXACT ACTION": "n" * FIELD_CHAR_BUDGETS["NEXT EXACT ACTION"],
                "VALIDATION": "CURRENT_PASS " + "v" * (
                    FIELD_CHAR_BUDGETS["VALIDATION"] - len("CURRENT_PASS ")
                ),
            },
        )
        errors = self._reject(legal)
        self.assertTrue(any("the whole response is" in e for e in errors), errors)
        # The per-field rules did not fire: only the total did.
        self.assertFalse([e for e in errors if "exceeds" in e], errors)

    def test_validation_bound_is_unchanged(self):
        errors = self._reject(_surface(VALIDATION="NOT_RUN -- a\nb\nc\nd\ne\nf"))
        self.assertTrue(any("VALIDATION exceeds 5" in error for error in errors), errors)

    # I and J are runtime facts of the plugin carrier -- the init turn and a
    # later turn of the same session -- so they live in `RealInitSameTurn` and
    # `MaterializationRebind`. A classifier cannot observe a session, and
    # restating them here would be a second, weaker oracle.

    # L -- the intentional detailed path stays open, and ONLY there.
    #
    # T-1556: the previous L control passed DETAILS with no authorization
    # context at all, which proved nothing about authorization -- it proved the
    # checker accepts the field. The mode is now a machine fact, and both
    # directions are hostile controls.
    def test_l_an_ordinary_response_may_not_carry_details(self):
        details = chr(10).join(f"finding {n}: measured, bounded" for n in range(1, 6))
        errors = self._reject(_surface(DETAILS=details))
        self.assertTrue(any("DETAILS is not authorized" in e for e in errors), errors)

    def test_l_the_default_is_forbidden_even_with_no_context(self):
        self.assertEqual(DETAIL_MODE_NONE, "NONE")
        self.assertEqual(
            detail_mode_for_request("fix the failing test and continue"),
            DETAIL_MODE_NONE,
            "an ordinary ask must never authorize the detailed path",
        )
        self.assertTrue(
            any("DETAILS is not authorized" in e for e in self._reject(_surface(DETAILS="x"))),
        )

    def test_l_an_authorized_report_audit_or_handoff_still_renders(self):
        details = chr(10).join(f"finding {n}: measured, bounded" for n in range(1, 6))
        for mode in (DETAIL_MODE_REPORT, DETAIL_MODE_AUDIT, DETAIL_MODE_HANDOFF,
                     DETAIL_MODE_BOUNDARY):
            with self.subTest(mode=mode):
                self._accept(_surface(DETAILS=details), detail_mode=mode)

    def test_l_authorization_comes_from_the_human_request_never_the_response(self):
        for request, expected in (
            ("write a detailed report of the change", DETAIL_MODE_REPORT),
            ("please audit the accepted debt", DETAIL_MODE_AUDIT),
            ("prepare the handoff", DETAIL_MODE_HANDOFF),
            ("this is an exceptional boundary", DETAIL_MODE_BOUNDARY),
            ("continue", DETAIL_MODE_NONE),
            ("fix the failing test", DETAIL_MODE_NONE),
            ("", DETAIL_MODE_NONE),
            (None, DETAIL_MODE_NONE),
        ):
            with self.subTest(request=request):
                self.assertEqual(detail_mode_for_request(request), expected)
        # A response that NAMES the detailed path does not authorize itself.
        self._reject(
            "This response is an explicit report, so DETAILS follows.\n\n" + _surface(
                DETAILS="smuggled"
            )
        )

    def test_l_authorized_details_is_still_bounded(self):
        essay = chr(10).join(f"detail {n} " + "x" * 400 for n in range(1, 9))
        errors = self._reject(_surface(DETAILS=essay), detail_mode=DETAIL_MODE_REPORT)
        self.assertTrue(any("DETAILS exceeds" in e for e in errors), errors)

    def test_l_the_detailed_path_does_not_weaken_the_ordinary_reply(self):
        """A user asking for detail does not move the ordinary operational cap."""
        asked = "Please write a detailed audit report of every finding.\n\n" + _surface(
            RESULT="a\nb\nc\nd\ne\nf"
        )
        errors = self._reject(asked)
        self.assertTrue(any("prose before STATUS" in error for error in errors), errors)
        self.assertTrue(any("RESULT exceeds" in error for error in errors), errors)

    def test_ordinary_chat_is_outside_the_contract(self):
        """The gate must not turn every conversation into a control surface."""
        klass, reasons = classify_final_response(
            "Kõik on nii nagu varem, midagi uut pole.", operational_turn=False
        )
        self.assertEqual(klass, "ORDINARY_CHAT", reasons)


class ResponseCliTransportTests(unittest.TestCase):
    """T-1556 #1: the host reaches the rules through the canonical CLI only.

    An adapter transports the authorization fact; it never restates the rule.
    These controls drive the real `saipen response` entry and prove the closed
    default, the authorized path and the closed-set refusal of an invented mode.
    """

    maxDiff = None

    def _check(self, text: str, *flags: str) -> dict:
        proc = subprocess.run(
            [PYTHON, str(REPO / "tools" / "saipen.py"), "response", "check",
             "--stdin", "--json", *flags],
            input=text, capture_output=True, text=True, timeout=120, cwd=str(REPO),
        )
        return json.loads(proc.stdout or "{}")

    def test_the_default_transport_refuses_details(self):
        answer = self._check(_surface(DETAILS="a bounded detail line"))
        self.assertEqual(answer["detail_mode"], DETAIL_MODE_NONE)
        self.assertFalse(answer["ok"], answer)
        self.assertTrue(
            any("DETAILS is not authorized" in e for e in answer["errors"]), answer
        )

    def test_the_explicit_authorized_path_passes(self):
        answer = self._check(
            _surface(DETAILS="a bounded detail line"), "--detail-mode", DETAIL_MODE_REPORT
        )
        self.assertEqual(answer["detail_mode"], DETAIL_MODE_REPORT)
        self.assertTrue(answer["ok"], answer)

    def test_the_human_request_is_classified_by_the_canonical_owner(self):
        answer = self._check(
            _surface(DETAILS="a bounded detail line"),
            "--request", "write a detailed report of the repair",
        )
        self.assertEqual(answer["detail_mode"], DETAIL_MODE_REPORT)
        self.assertTrue(answer["ok"], answer)
        ordinary = self._check(
            _surface(DETAILS="a bounded detail line"), "--request", "continue"
        )
        self.assertEqual(ordinary["detail_mode"], DETAIL_MODE_NONE)
        self.assertFalse(ordinary["ok"], ordinary)

    def test_an_invented_mode_is_refused_not_guessed(self):
        answer = self._check(_surface(), "--detail-mode", "BECAUSE_I_SAID_SO")
        self.assertFalse(answer["ok"], answer)
        self.assertIn("unknown --detail-mode", answer["detail"])

    def test_no_adapter_carries_a_second_copy_of_the_rules(self):
        """Review item 10: the budgets and the mode live in ONE module."""
        for adapter in (
            REPO / "extensions" / "adapters" / "opencode" / "saipen-guard.js",
            REPO / "extensions" / "adapters" / "codex" / "saipen-guard.py",
        ):
            with self.subTest(adapter=adapter.name):
                source = adapter.read_text(encoding="utf-8")
                self.assertNotIn("FIELD_CHAR_BUDGETS", source)
                self.assertNotIn("FIELD_LINE_BUDGETS", source)
                self.assertNotIn("ORDINARY_RESPONSE_CHAR_BUDGET", source)
                self.assertNotIn("DETAIL_MODE", source)
                self.assertNotIn("detail_mode_for_request", source)


class CompactnessContractCoherence(unittest.TestCase):
    """T-1553 D: STYLE and EXECUTION must not contradict each other again.

    STYLE used to cap an ordinary report at 5 lines (absolute max 8) while
    EXEC-RESPONSE-01 mandates six headings plus their values -- so the shortest
    vertically-rendered VALID response already exceeded the style budget. Two
    normative documents disagreed, and no amount of prompting fixes prose that
    contradicts itself. EXECUTION owns the response schema and therefore owns
    the operational compactness budget; STYLE owns the chat voice and must say
    so. These assertions fail if either half is edited back.
    """

    maxDiff = None

    def setUp(self):
        self.style = (REPO / "saipen" / "STYLE.md").read_text(encoding="utf-8-sig")
        self.execution = (REPO / "saipen" / "EXECUTION.md").read_text(encoding="utf-8-sig")

    def test_execution_owns_the_operational_compactness_budget(self):
        self.assertIn("COMPACTNESS BUDGET", self.execution)

    def test_execution_states_the_budget_over_field_content_not_labels(self):
        budget = self.execution.partition("COMPACTNESS BUDGET")[2][:1200]
        self.assertIn("CONTENT", budget.upper())
        self.assertIn("label", budget.lower())

    def test_execution_prose_matches_the_machine_copy(self):
        """The document and `FIELD_LINE_BUDGETS` are one contract, not two.

        Whitespace is normalized because the document wraps its own field
        names across lines; the numbers are what must not drift.
        """
        flat = " ".join(self.execution.split())
        for field, budget in FIELD_LINE_BUDGETS.items():
            self.assertIn(
                f"{field} <= {budget}", flat,
                f"EXECUTION.md does not state the enforced budget for {field}",
            )

    def test_execution_states_the_character_budgets_and_the_ceiling(self):
        """T-1556: a line count alone is not a contract, so the document owns
        the character budgets and the whole-response ceiling too."""
        flat = " ".join(self.execution.split())
        for field, budget in FIELD_CHAR_BUDGETS.items():
            self.assertIn(
                f"{field} <= {budget}", flat,
                f"EXECUTION.md does not state the character budget for {field}",
            )
        self.assertIn(str(ORDINARY_RESPONSE_CHAR_BUDGET), flat)

    def test_execution_states_the_details_authorization_rule(self):
        flat = " ".join(self.execution.split())
        self.assertIn("DETAILS AUTHORIZATION", flat)
        self.assertIn("detail_mode", flat)
        for mode in DETAIL_MODES:
            self.assertIn(mode, flat, f"EXECUTION.md omits the closed mode {mode}")

    def test_style_defers_to_execution_for_the_operational_surface(self):
        self.assertRegex(
            self.style, r"EXEC-RESPONSE-01",
            "STYLE must recognize the operational control surface",
        )
        self.assertRegex(
            self.style, r"(?is)compactness budget.*EXECUTION|EXECUTION.*compactness budget",
            "STYLE must defer the operational compactness budget to EXECUTION",
        )

    def test_style_does_not_cap_a_whole_operational_response(self):
        """No total physical-line cap may govern a mandatory six-field surface."""
        offenders = [
            line
            for line in self.style.splitlines()
            if "≤5 lines" in line or "<=5 lines" in line or "max 8 lines" in line
        ]
        for line in offenders:
            self.assertRegex(
                line, r"(?i)chat prose|voice|not the operational response|EXECUTION",
                f"STYLE re-declares a whole-response line cap: {line!r}",
            )


class InitCarrierClaimHonesty(unittest.TestCase):
    """T-1556 #4: the carrier claim must match what is actually exercised.

    The lower-level carrier calls `bootstrap_project` in a spawned interpreter.
    Calling that "the real `saipen init`, end to end" is exactly the kind of
    wording the rest of this file exists to prevent, so the CLI end-to-end claim
    now belongs to a carrier that runs the installed launcher, and it may only
    be claimed while that carrier actually runs.
    """

    maxDiff = None

    def test_the_launcher_carrier_is_not_silently_skipped_on_this_host(self):
        """A claim nobody exercised is not a claim. If the launcher carrier
        skips here, the end-to-end claim is unavailable, not proved."""
        if not LAUNCHER_USABLE:
            self.skipTest("installed CLI launcher not executable here; claim not made")
        self.assertTrue(
            any(
                "test_the_installed_launcher_init_gates_its_own_turn" in test.id()
                and RealLauncherInit in type(test).__mro__
                for test in unittest.defaultTestLoader.loadTestsFromTestCase(RealLauncherInit)
                if hasattr(test, "id")
            ),
            "the launcher carrier must exist and run",
        )

    def test_the_lower_level_carrier_does_not_claim_launcher_end_to_end(self):
        doc = (RealInitSameTurn.__doc__ or "")
        self.assertIn("REAL_CANONICAL_INIT_EFFECT_SAME_TURN_PROVED", doc)
        self.assertIn("does NOT prove launcher/CLI end-to-end", doc)
        self.assertNotIn("REAL_INIT" + "_SAME_TURN_PROVED", doc)

    def test_the_retired_claim_name_is_gone_from_the_module(self):
        # Assembled, not literal: this test file must not contain the retired
        # name even inside the control that forbids it.
        retired = "REAL_INIT" + "_SAME_TURN_PROVED"
        source = (REPO / "tools" / "test_t1553_mid_session_activation.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn(retired, source)
        self.assertIn("REAL_CLI_LAUNCHER_INIT_E2E_SAME_TURN_PROVED", source)


class HostResponseEnforcementClaims(unittest.TestCase):
    """T-1553 F: no host may claim response enforcement it cannot deliver.

    `declared_strength` answers "can this host refuse a TOOL". It says nothing
    about "can this host refuse the FINAL MESSAGE", and reading the first as the
    second is exactly how a single-host repair gets reported as global
    fail-closed enforcement. The registry therefore carries a SEPARATE
    `response_enforcement` claim per host, and these controls make that claim
    falsifiable instead of decorative.
    """

    maxDiff = None
    LEVELS = frozenset({"MECHANICAL", "ADVISORY", "UNAVAILABLE"})

    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(
            (REPO / "extensions" / "adapters" / "registry.json").read_text(encoding="utf-8")
        )

    def registry_entry(self, host: str) -> dict:
        for entry in self.registry["adapters"]:
            if entry["id"] == host:
                return entry
        self.fail(f"{host} is not in the adapter registry")

    def test_every_supported_host_declares_its_response_enforcement(self):
        for entry in self.registry["adapters"]:
            with self.subTest(host=entry["id"]):
                self.assertIn(entry.get("response_enforcement"), self.LEVELS, entry["id"])
                self.assertTrue(
                    str(entry.get("response_enforcement_note") or "").strip(),
                    f"{entry['id']} must say WHY it sits at that level",
                )

    def test_mechanical_requires_a_real_final_text_hook_in_the_declared_artifact(self):
        """A MECHANICAL claim is honest only with the host surface that carries
        the outgoing text, present in the artifact the registry names."""
        mechanical = [
            entry for entry in self.registry["adapters"]
            if entry["response_enforcement"] == "MECHANICAL"
        ]
        self.assertTrue(mechanical, "the registry must still be able to say MECHANICAL")
        for entry in mechanical:
            with self.subTest(host=entry["id"]):
                token = entry.get("response_hook")
                self.assertIsInstance(token, str, entry["id"])
                self.assertTrue(token.strip(), entry["id"])
                artifact = entry.get("hook_artifact")
                self.assertTrue(artifact, f"{entry['id']} claims MECHANICAL with no hook artifact")
                source = (REPO / artifact).read_text(encoding="utf-8")
                self.assertIn(token, source, f"{entry['id']} names a hook its artifact lacks")

    def test_declared_enforcement_gaps_stay_unavailable_not_merely_advisory(self):
        """A host with no enforcement surface at all is UNAVAILABLE. Upgrading
        it to ADVISORY would read as 'the contract is merely not enforced yet
        here', which is a stronger claim than the installation supports."""
        gaps = {
            entry["id"] for entry in self.registry["adapters"]
            if entry.get("declared_strength") == "ENFORCEMENT_GAP"
        }
        for entry in self.registry["adapters"]:
            if entry["id"] in gaps:
                with self.subTest(host=entry["id"]):
                    self.assertEqual(entry["response_enforcement"], "UNAVAILABLE", entry["id"])

    def test_status_reports_the_response_claim_separately(self):
        """The claim is a live, readable fact, never inferred from the tool
        admission strength a reader already saw."""
        from saipen_engine.admission import ADAPTER_REGISTRY, effective_strength

        self.assertIn("opencode", ADAPTER_REGISTRY)
        self.assertEqual(ADAPTER_REGISTRY["opencode"]["response_enforcement"], "MECHANICAL")
        self.assertNotEqual(
            effective_strength("opencode")["effective"],
            ADAPTER_REGISTRY["opencode"]["response_enforcement"],
            "the two claims are different facts and must stay separately declared",
        )

    def test_the_diagnostic_projection_actually_emits_the_claim(self):
        """A declaration nobody reads is decoration. The guard's status
        projection must carry the per-host response claim, so an operator
        asking "is this host fail-closed?" gets an answer, not an inference
        from the tool-admission column next to it."""
        proc = subprocess.run(
            [PYTHON, str(REPO / "tools" / "saipen.py"), "guard", "--action", "read", "--json"],
            capture_output=True, text=True, timeout=120, cwd=str(REPO),
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        adapters = json.loads(proc.stdout).get("adapters") or {}
        self.assertTrue(adapters, "the diagnostic projection must report the host inventory")
        self.assertEqual(set(adapters), {entry["id"] for entry in self.registry["adapters"]})
        for host, reported in adapters.items():
            with self.subTest(host=host):
                self.assertIn(reported.get("response_enforcement"), self.LEVELS)
                self.assertEqual(
                    reported["response_enforcement"],
                    self.registry_entry(host)["response_enforcement"],
                    f"{host} projection drifted from the registry declaration",
                )


class OperatorDueHandback(unittest.TestCase):
    """T-1553: an operator action that is DUE must be a legal handback.

    `automation.py` carries `operator_action_due` and `_response_cli` reads it
    into `operator_due`; both were unproven -- forcing either to False left the
    whole suite green, because no test ran a real project through the real CLI
    where the two disagree with each other. This one does exactly that: a real
    `saipen init`, then the canonical handback, through the real
    `response check --classify --auto-eligibility`. Routing says `cc` stays
    legal on a fresh project (R7) while the human owes the first goal, and both
    the plain and the classifying checker must accept the same surface.
    """

    maxDiff = None

    SURFACE = chr(10).join([
        "STATUS", "PLAN -- WAIT, init complete",
        "RESULT", "canonical handback after the real init",
        "BLOCKER", "NONE",
        "OPERATOR ACTION", "provide the first project goal",
        "NEXT EXACT ACTION", "NONE",
        "VALIDATION", "NOT_RUN -- fresh project",
    ]) + chr(10)

    def _fresh_project(self) -> Path:
        workdir = Path(tempfile.mkdtemp(prefix="saipen-t1553-init-"))
        self.addCleanup(lambda: shutil.rmtree(workdir, ignore_errors=True))
        project = workdir / "proj"
        project.mkdir()
        proc = subprocess.run(
            [PYTHON, str(REPO / "tools" / "saipen.py"), "init",
             "--project-root", str(project), "--agent", "test-agent", "--json"],
            capture_output=True, text=True, timeout=180, env=_carrier_env(),
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue((project / ".saipen" / "STATE.md").is_file())
        return project

    def _check(self, project: Path, surface: str, *flags: str) -> tuple[int, dict]:
        proc = subprocess.run(
            [PYTHON, str(REPO / "tools" / "saipen.py"), "response", "check", "--stdin",
             *flags, "--auto-eligibility", "--project-root", str(project), "--json"],
            input=surface, capture_output=True, text=True, timeout=180,
            env=_carrier_env(),
        )
        try:
            payload = json.loads(proc.stdout or "{}")
        except ValueError:
            payload = {"_raw": proc.stdout, "_err": proc.stderr}
        return proc.returncode, payload

    def test_the_classifying_checker_accepts_the_operator_due_handback(self):
        project = self._fresh_project()
        code, payload = self._check(project, self.SURFACE, "--classify")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload.get("class"), "VALID_BOUNDARY", payload)

    def test_both_checker_paths_agree_on_the_same_surface(self):
        """A surface the plain checker accepts may not be refused by --classify."""
        project = self._fresh_project()
        plain_code, plain = self._check(project, self.SURFACE)
        class_code, classified = self._check(project, self.SURFACE, "--classify")
        self.assertEqual(plain_code, class_code, {"plain": plain, "classify": classified})
        self.assertEqual(plain.get("ok"), classified.get("ok"))

    def test_a_waiving_surface_is_still_refused_on_the_same_project(self):
        """The control: the handback must NAME the operator action."""
        project = self._fresh_project()
        tail = self.SURFACE.split("NEXT EXACT ACTION", 1)[1]
        waiving = (

            "OPERATOR ACTION" + chr(10) + "NONE" + chr(10) + chr(10) + tail
        )
        self.assertNotEqual(waiving, self.SURFACE, "the control must differ from the surface")
        code, payload = self._check(project, waiving, "--classify")
        self.assertNotEqual(code, 0, payload)
        self.assertNotEqual(payload.get("class"), "VALID_BOUNDARY", payload)


class InitCommandAdmissionGrammar(unittest.TestCase):
    """T-1553: the init exemption must exempt the init, and nothing else.

    `PROJECT_CREATING_COMMAND_RE` drops `--require-binding` for the canonical
    init. Written as an unanchored search for `saipen init` anywhere in the
    line, it also exempted every consequential command that merely MENTIONED
    it -- `saipen ticket add P1 "please saipen init this"` and
    `saipen init && curl ...` were admitted from an unbound cwd, which is
    exactly the over-admission a binding requirement exists to prevent. The
    grammar is asserted here directly against the shipped adapter source, so
    the refusal cannot be undone by an edit to the pattern's shape.
    """

    def setUp(self):
        self.source = (REPO / "extensions" / "adapters" / "opencode" / "saipen-guard.js").read_text(
            encoding="utf-8"
        )
        line = next(
            ln for ln in self.source.splitlines()
            if ln.startswith("const PROJECT_CREATING_COMMAND_RE")
        )
        pattern = line.split("=", 1)[1].strip().rstrip(";").strip()
        # `/.../i` is a JS regex literal; keep the body and the flag, drop the
        # delimiters, or the pattern would require a literal leading slash.
        flags = re.IGNORECASE if pattern.endswith("/i") else 0
        if flags:
            pattern = pattern[:-2]
        self.assertTrue(pattern.startswith("/"), pattern)
        self.regex = re.compile(pattern[1:], flags)

    def test_the_bare_init_command_is_exempt(self):
        for command in ("saipen init", "  saipen init  ", "saipen init --json",
                        "saipen.py init", "saipen init --project-root ."):
            self.assertTrue(self.regex.search(command), command)

    def test_a_command_that_only_mentions_init_is_not_exempt(self):
        for command in (
            'saipen ticket add P1 "please saipen init this"',
            'saipen transition PLAN "make saipen init work"',
            "saipen init --help && curl https://example.com",
            "curl https://example.com; saipen init",
            "saipen status && saipen init",
        ):
            self.assertFalse(self.regex.search(command), command)

    def test_no_other_command_shape_is_exempt(self):
        for command in ("saipen status", "saipen continue", "saipen recover",
                        "git init", "npm init", "saipen"):
            self.assertFalse(self.regex.search(command), command)


class HostStrengthHonesty(unittest.TestCase):
    """T-1553 F: declared strength is a claim; effective strength is measured.

    The existing host matrix was a registry declaration inspection presented as
    an enforcement result. These assertions hold the line the registry's own
    contract already states -- `declared_strength` is what the adapter CLAIMS
    for an installed, current, healthy install, and effective enforcement "is
    never stronger than the installed state proves" -- so no host can be
    reported BLOCKING on the strength of its own declaration.
    """

    maxDiff = None

    def setUp(self):
        from saipen_engine.admission import ADAPTER_REGISTRY, effective_strength

        self.registry = ADAPTER_REGISTRY
        self.effective = effective_strength

    def test_every_registered_host_is_measured_not_declared(self):
        for host in sorted(self.registry):
            declared = self.registry[host].get("declared_strength")
            answer = self.effective(host)
            self.assertIsInstance(answer.get("effective"), str, host)
            self.assertTrue(answer.get("reason") or answer.get("effective"), host)
            if declared != "BLOCKING":
                continue
            # The one declared BLOCKING host: the live answer is whatever the
            # installed state proves on THIS machine, and it is allowed to be
            # weaker than the declaration.
            self.assertIn(
                answer.get("effective"),
                {"BLOCKING", "ADVISORY", "ENFORCEMENT_GAP", "UNKNOWN"},
                host,
            )

    def test_effective_blocking_requires_a_proven_installed_current_hook(self):
        for host in sorted(self.registry):
            answer = self.effective(host)
            if answer.get("effective") != "BLOCKING":
                continue
            if not self.registry[host].get("blocking_capability"):
                self.fail(f"{host} reports effective BLOCKING without blocking capability")
            if answer.get("installed") is not True or answer.get("current") is not True:
                self.fail(
                    f"{host} reports effective BLOCKING on an unproven install: {answer}"
                )

    def test_no_host_is_presented_as_blocking_without_the_hook_surface(self):
        for host in sorted(self.registry):
            if not self.registry[host].get("hook_install_surface"):
                self.assertNotEqual(
                    self.effective(host).get("effective"), "BLOCKING",
                    f"{host} has no hook surface and can never be effectively BLOCKING",
                )

    def _matrix_rows(self) -> dict[str, list[str]]:
        matrix = REPO / ".saipen" / "evidence" / "T-1553-host-enforcement-matrix" / "MATRIX.md"
        self.assertTrue(matrix.is_file(), f"missing the F evidence record: {matrix}")
        rows: dict[str, list[str]] = {}
        for line in matrix.read_text(encoding="utf-8").splitlines():
            if not line.startswith("| ") or line.startswith("| host ") or line.startswith("|---"):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            rows[cells[0].strip("*")] = cells
        return rows

    def test_the_matrix_records_every_registered_host_separately(self):
        rows = self._matrix_rows()
        for host in sorted(self.registry):
            self.assertIn(host, rows, f"the matrix omits registered host {host}")

    def test_the_matrix_declared_column_matches_the_registry(self):
        """The declared column is the stable claim; it must not drift."""
        rows = self._matrix_rows()
        for host, entry in self.registry.items():
            if host not in rows:
                continue
            cells = rows[host]
            if len(cells) < 2:
                continue
            if "declared=" in cells[1]:  # the prose list, not the table
                continue
            self.assertEqual(
                cells[1].strip("*"), entry.get("declared_strength"),
                f"the matrix misreports the DECLARED strength of {host}",
            )

    def test_the_matrix_never_claims_effective_blocking_against_the_engine(self):
        """The one claim that must never be wrong, checked against the engine."""
        rows = self._matrix_rows()
        for host, cells in rows.items():
            if len(cells) < 6:
                continue
            claimed = cells[5].strip("*")
            if claimed != "BLOCKING":
                continue
            self.assertEqual(
                self.effective(host).get("effective"), "BLOCKING",
                f"the matrix claims effective BLOCKING for {host}; the live engine "
                f"says {self.effective(host).get('effective')}",
            )

    def test_the_matrix_states_the_measured_not_the_declared_answer(self):
        matrix = (REPO / ".saipen" / "evidence" / "T-1553-host-enforcement-matrix" / "MATRIX.md")
        text = matrix.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?i)effective")
        self.assertRegex(text, r"(?i)live")
        self.assertRegex(
            text, r"(?i)not .{0,40}stronger than the installed state proves|"
                   r"never .{0,40}stronger than the installed state proves",
            "the matrix must restate the declared-is-a-claim contract",
        )
