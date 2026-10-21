"""HOST-INTEGRATION-01 acceptance (T-1624): a host that can run is not locked out.

The incident: a hardening of protocol admission made Claude Code unusable. The
prompt was blocked before the model saw it (`HOST_AUTHORITY_UNAVAILABLE`), no
recovery was offered, the injector said "provenance verified" while the launcher
said `CANONICAL_RUNTIME_SOURCE_UNPROVEN`, and `saipen launch claude` did not
exist for a host that had a prompt-blocking hook.

Evidence classes, kept apart on purpose (a green in one says nothing about
another):

* CONTROL    -- the six red controls of the incident, A..F.
* TABLE      -- the failure taxonomy and the one decision table.
* IDENTITY   -- what the separated authority accepts as "the host's own hook",
                on synthetic process chains, on this process and on the
                platform's code-signing answer.
* TRANSPORT  -- the endpoint under concurrency, a second server, an impostor.
* HOOK       -- the Claude Code hook artifact when its engine cannot be run,
                paired against the FROZEN pre-fix hook on the same oracle.
* INSTALL    -- stage, verify, activate; rollback; uninstall; reinstall.
* STATE      -- the host state model, the capability contract, doctor, repair.
* HOST       -- real processes: a stand-in host, the installed hook, a broker.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _entry in (str(TOOLS), str(ROOT), str(ROOT / "bootstrap")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

import install_host_guard  # noqa: E402
from saipen_engine import host_authority_broker as HB  # noqa: E402
from saipen_engine import host_authority_client as HC  # noqa: E402
from saipen_engine import host_authority_identity as HI  # noqa: E402
from saipen_engine import host_authority_process as HP  # noqa: E402
from saipen_engine import host_authority_transport as HT  # noqa: E402
from saipen_engine import host_integration as HG  # noqa: E402
from saipen_engine import host_launch  # noqa: E402
from saipen_engine import host_taxonomy as TX  # noqa: E402
from saipen_engine import protocol_admission as PA  # noqa: E402
from saipen_engine import runtime_bootstrap  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_host_fixture import HostFixture, platform_shell  # noqa: E402
from test_protocol_admission import World, guard  # noqa: E402

HOOK = ROOT / "extensions" / "adapters" / "claude" / "saipen-guard.py"
FROZEN = ROOT / "tests" / "fixtures" / "t1624-lockout"
WINDOWS = os.name == "nt"
#: The uninstaller's own transports: Windows PowerShell 5.1, which every
#: Windows 10 machine has, and PowerShell 7 where it is installed. Their JSON
#: readers differ, so each one runs the uninstaller on its own.
WINDOWS_POWERSHELL = shutil.which("powershell") if WINDOWS else None
POWERSHELL_7 = shutil.which("pwsh") if WINDOWS else None


def setUpModule() -> None:
    isolate_host_session()


def load_hook(path: Path = HOOK):
    spec = importlib.util.spec_from_file_location("saipen_guard_t1624_" + path.parent.name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_hook(
    artifact: Path, saipen_root: Path, home: Path, event: dict, *, cwd: Path, runtime: Path
) -> tuple[dict | None, float]:
    """One event through a hook artifact; (answer, wall seconds)."""
    started = time.perf_counter()
    proc = subprocess.run(
        [
            sys.executable, str(artifact), "--host", "claude", "--saipen-root", str(saipen_root),
            "--home", str(home), "--runtime", str(runtime),
        ],
        input=json.dumps(event).encode("utf-8"),
        capture_output=True,
        cwd=str(cwd),
        check=False,
        timeout=180,
        env={key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")},
    )
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    return (json.loads(out) if out else None), time.perf_counter() - started


class Scratch(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def bare_project(self, name: str = "project") -> Path:
        project = self.tmp / name
        (project / ".saipen").mkdir(parents=True)
        (project / ".saipen" / "STATE.md").write_text("---\nphase: DONE\n---\n", encoding="utf-8")
        return project


# --------------------------------------------------------------------- CONTROL


class IncidentControls(Scratch):
    """The six red controls. Each names its expected outcome in its title."""

    def world(self, mode: str | None) -> World:
        (self.tmp / f"w-{mode}").mkdir()
        return World(self.tmp / f"w-{mode}", mode=mode)

    def prompt(self, world: World) -> dict:
        return guard(
            world.project,
            {"hook_event_name": "UserPromptSubmit", "user_prompt": "hi"},
            world.home,
            authority=world.authority,
        )

    def test_control_a_strict_blocks_with_a_recovery_attempt_and_an_exact_action(self):
        world = self.world("strict")
        out = self.prompt(world)
        self.assertEqual(out["decision"], "block")
        reason = out["reason"]
        self.assertIn("HOST_AUTHORITY_UNAVAILABLE", reason)
        self.assertIn("automatic recovery attempted [connect", reason)
        self.assertIn("Do this: saipen host repair", reason)
        # Nothing answered on this endpoint and nothing was started for it. The
        # real host printed "state answered" here, a service that was not up.
        self.assertIn("state unanswered", reason)
        self.assertNotIn("state answered", reason)
        # The dead end the operator was shown is gone for good.
        self.assertNotIn("a separated host authority is required", reason)
        self.assertNotIn("separated-host authority is required", reason)

    def test_control_b_degraded_allowed_lets_the_prompt_reach_the_model_unverified(self):
        world = self.world(None)  # no policy file at all: the product default
        out = self.prompt(world)
        self.assertNotIn("decision", out, "the prompt must reach the model")
        context = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("=== BOOT.md sha256:", context, "the protocol is still delivered")
        self.assertIn(PA.DEGRADED_MARKER, out["systemMessage"])
        verdict = PA.establish(world.ctx())
        self.assertEqual(verdict["state"], PA.STATE_DEGRADED)
        self.assertFalse(verdict["verified"], "no mechanical-admission claim")
        self.assertNotIn("token", verdict)
        self.assertFalse(PA._ledger_path(world.project, "session-1").exists())
        self.assertEqual(
            TX.decide(TX.MODE_DEGRADED, verdict["problems"]), TX.DECISION_ALLOW_DEGRADED
        )

    def test_control_c_a_foreign_project_binding_blocks_under_degraded_allowed(self):
        world = self.world(None)
        (self.tmp / "other").mkdir()
        other = World(self.tmp / "other", mode=None)
        from saipen_engine.paths import project_lineage_identity

        carriers = {
            "SAIPEN_PROJECT_ROOT": str(world.project),
            "SAIPEN_PROJECT_LINEAGE": project_lineage_identity(other.project),
        }
        verdict = PA.establish(world.ctx(event_cwd=world.project, carriers=carriers))
        self.assertEqual(verdict["state"], PA.STATE_REFUSED)
        self.assertEqual(verdict["failure"], "BINDING_FOREIGN_PROJECT")
        self.assertEqual(TX.decide(TX.MODE_DEGRADED, verdict["problems"]), TX.DECISION_BLOCK)
        self.assertIn("Do this:", PA.diagnostic(verdict))

    def test_control_d_a_forged_capability_blocks_under_degraded_allowed(self):
        world = self.world(None)
        verdict = PA.establish(world.ctx(), transport="hook:UserPromptSubmit:" + "0" * 64)
        self.assertEqual(verdict["state"], PA.STATE_REFUSED)
        self.assertEqual(verdict["failure"], "CAPABILITY_FORGED")
        self.assertEqual(TX.decide(TX.MODE_DEGRADED, verdict["problems"]), TX.DECISION_BLOCK)
        self.assertFalse((world.project / PA.LEDGER_DIR).exists())

    def test_control_e_the_runtime_check_agrees_with_the_installer_about_the_source(self):
        # A canonical source checkout proves itself by its architecture: no
        # installer ever wrote a marker INTO the checkout, and the documented
        # check said `CANONICAL_RUNTIME_SOURCE_UNPROVEN` right after an install
        # that had printed "provenance verified".
        self.assertIsNone(runtime_bootstrap.read_provenance(ROOT))
        self.assertEqual(runtime_bootstrap.canonical_source_root(ROOT), ROOT.resolve())
        report = runtime_bootstrap.check_freshness()
        self.assertTrue(report["ok"])
        self.assertNotEqual(report["code"], "CANONICAL_RUNTIME_SOURCE_UNPROVEN")
        source = HG._source_facts()
        self.assertTrue(source["proven"], source)
        self.assertEqual(source["kind"], "source-checkout")
        # An INSTALLED projection is the other shape: it carries the runtime and
        # not the clone markers, and without the installer's marker it is
        # unproven -- named as a failure with an action, not a contradiction.
        projection = self.tmp / "projection"
        (projection / "tools" / "saipen_engine").mkdir(parents=True)
        (projection / "VERSION").write_text("0.0.0\n", encoding="utf-8")
        with self.assertRaises(runtime_bootstrap.CanonicalSourceUnproven) as caught:
            runtime_bootstrap.canonical_source_root(projection)
        self.assertIn("run the canonical injector once", str(caught.exception))
        entry = TX.get("CANONICAL_RUNTIME_SOURCE_UNPROVEN")
        self.assertTrue(entry.degradable, "an unproven source never blocks a prompt")
        self.assertEqual(entry.operator_action, TX.REPAIR)

    def test_control_f_claude_has_a_declared_launch_and_a_real_recovery_path(self):
        contract = HG.capability_matrix()["claude"]
        self.assertEqual(contract["launch"]["mode"], HG.LAUNCH_NATIVE_OR_LAUNCHER)
        self.assertIn("native Claude Code launch", contract["launch"]["routine"])
        self.assertIn("launch claude", contract["launch"]["launcher_command"])
        # No imaginary launcher capability: what the registry declares is what
        # the launcher supports, both ways.
        self.assertEqual(host_launch.SUPPORTED_HOSTS, host_launch.registry_launch_hosts())
        self.assertEqual(host_launch.SUPPORTED_HOSTS.get("claude"), "claude")
        self.assertEqual(
            sorted(host_launch.SUPPORTED_HOSTS),
            sorted(
                host for host, item in HG.capability_matrix().items()
                if item["launch"]["executable"]
            ),
        )
        # The recovery path is a command that exists, needs no project, and
        # answers in its schema.
        for verb in ("doctor", "mode"):
            proc = subprocess.run(
                [sys.executable, str(TOOLS / "saipen.py"), "host", verb, "--json",
                 "--home", str(self.tmp)],
                capture_output=True, cwd=str(self.tmp), check=False, timeout=180,
            )
            payload = json.loads(proc.stdout.decode("utf-8"))
            self.assertIn(payload["code"], ("HOST_DOCTOR", "HOST_MODE"), payload)
        self.assertEqual(contract["auto_recovery"], HG.RECOVERY_AUTHORITY)
        self.assertEqual(contract["degraded_mode"], HG.DEGRADED_DEFAULT)


# ----------------------------------------------------------------------- TABLE


class TaxonomyTests(unittest.TestCase):
    def test_every_failure_is_fully_described_and_belongs_to_one_family(self):
        codes = TX.codes()
        self.assertEqual(len(codes), len(set(codes)))
        for row in TX.table():
            with self.subTest(code=row["code"]):
                self.assertIn(row["family"], TX.FAMILIES)
                self.assertIn(row["severity"], TX.SEVERITIES)
                self.assertIsInstance(row["recoverable"], bool)
                self.assertIsInstance(row["degradable"], bool)
                for field in ("auto_recovery", "operator_action", "fallback", "summary"):
                    self.assertTrue(str(row[field]).strip(), field)
                self.assertRegex(row["code"], r"^[A-Z][A-Z0-9_]*$")
                # A blocking failure always names a real action.
                if not row["degradable"]:
                    self.assertNotEqual(row["operator_action"], "none")
        self.assertEqual({row["family"] for row in TX.table()}, set(TX.FAMILIES))

    def test_the_codes_the_incident_named_are_classified(self):
        for code in (
            "CANONICAL_RUNTIME_SOURCE_UNPROVEN",
            "HOST_AUTHORITY_UNAVAILABLE",
            "HOST_LAUNCH_REFUSED",
            "HOST_RUNTIME_STALE",
            "PLUGIN_RESTART_REQUIRED",
        ):
            self.assertTrue(TX.known(code), code)
            self.assertTrue(TX.get(code).degradable, code)

    def test_policy_is_decided_from_registered_codes_only(self):
        degradable = TX.problem("transport", "AUTHORITY_UNREACHABLE", "x")
        forged = TX.problem("transport", "CAPABILITY_FORGED", "x")
        self.assertEqual(TX.decide("degraded", [degradable]), TX.DECISION_ALLOW_DEGRADED)
        self.assertEqual(TX.decide("strict", [degradable]), TX.DECISION_BLOCK)
        self.assertEqual(TX.decide("degraded", [degradable, forged]), TX.DECISION_BLOCK)
        self.assertEqual(TX.decide("strict", [], admitted=True), TX.DECISION_ADMIT)
        self.assertEqual(TX.decide("degraded", [], admitted=True), TX.DECISION_ADMIT)
        self.assertEqual(TX.decide("degraded", [forged], admitted=True), TX.DECISION_BLOCK)
        # Unclassified is never waved through, and cannot even be built.
        self.assertEqual(TX.decide("degraded", [{"reason": "harmless"}]), TX.DECISION_BLOCK)
        self.assertEqual(TX.decide("degraded", ["harmless"]), TX.DECISION_BLOCK)
        with self.assertRaises(KeyError):
            TX.problem("x", "NOT_A_REGISTERED_CODE", "y")

    def test_the_default_policy_is_degraded_allowed_and_spellings_normalize(self):
        self.assertEqual(TX.DEFAULT_MODE, TX.MODE_DEGRADED)
        for spelling in ("degraded", "DEGRADED_ALLOWED", "degraded-allowed", " Degraded Allowed "):
            self.assertEqual(TX.normalize_mode(spelling), TX.MODE_DEGRADED, spelling)
        self.assertEqual(TX.normalize_mode("STRICT"), TX.MODE_STRICT)
        for junk in ("", None, "permissive", "off", 0):
            self.assertIsNone(TX.normalize_mode(junk), junk)

    def test_broker_wire_codes_map_to_a_class_and_never_to_a_pass(self):
        self.assertEqual(TX.from_broker("BROKER_CAPABILITY_INVALID"), "CAPABILITY_FORGED")
        self.assertEqual(TX.from_broker("BROKER_CAPABILITY_REPLAY"), "CAPABILITY_REPLAYED")
        self.assertEqual(TX.from_broker("BROKER_BINDING_MISMATCH"), "CAPABILITY_BINDING_MISMATCH")
        self.assertEqual(
            TX.from_broker(HB.CODE_NOT_AUTHENTICATED), "AUTHORITY_CLIENT_UNPROVEN"
        )
        self.assertEqual(
            TX.from_broker(HB.CODE_IDENTITY_UNAVAILABLE), "AUTHORITY_IDENTITY_UNSUPPORTED"
        )
        for unknown in ("", None, "SOMETHING_NEW"):
            self.assertEqual(TX.from_broker(unknown), "AUTHORITY_FAULT")
        for code in ("CAPABILITY_FORGED", "CAPABILITY_REPLAYED", "CAPABILITY_EXPIRED",
                     "CAPABILITY_BINDING_MISMATCH", "BINDING_FOREIGN_PROJECT", "BINDING_CONFLICT"):
            self.assertFalse(TX.get(code).degradable, code)

    def test_a_refusal_names_exactly_one_operator_action(self):
        problems = [
            TX.problem("host", "HOOK_STALE", "x"),
            TX.problem("transport", "CAPABILITY_FORGED", "y"),
        ]
        # The blocking failure's action leads, whatever the order.
        self.assertIn("SAIPEN_ADMISSION_TRANSPORT", TX.first_action(problems))
        self.assertEqual(TX.first_action([problems[0]]), TX.REPAIR)
        self.assertEqual(TX.first_action([]), TX.DOCTOR)
        verdict = PA._refusal(problems)
        self.assertEqual(len(verdict["actions"]), 1)
        text = PA.diagnostic(verdict)
        self.assertEqual(text.count("Do this:"), 1)
        self.assertLessEqual(len(text), PA._MAX_DIAGNOSTIC)

    def test_an_answer_from_another_generation_is_one_typed_failure_not_a_guess(self):
        foreign = [{"component": "host", "reason": "host claude hook is not installed and current"}]
        typed = PA._typed(foreign)
        self.assertEqual([item["code"] for item in typed], ["AUTHORITY_GENERATION_MISMATCH"])
        self.assertTrue(TX.degradable(typed))
        current = [TX.problem("host", "HOOK_STALE", "x")]
        self.assertEqual(PA._typed(current), current)


# -------------------------------------------------------------------- IDENTITY

F = HP.ProcessFact
PY = "c:/py/python.exe"
GUARD = "C:/Users/v/.claude/hooks/saipen-guard.py"
RUNTIME = "C:/Users/v/.claude/skills/saipen"
HOOK_COMMAND = f"C:/Py/python.exe {GUARD} --host claude --saipen-root {RUNTIME}"
HOOK_ARGV = (r"C:\Py\python.exe", GUARD, "--host", "claude", "--saipen-root", RUNTIME)
ENGINE_ARGV = (
    r"C:\Py\python.exe", r"C:\Users\v\.claude\skills\saipen\tools\saipen.py", "admission",
)
BASH_INNER = F(30, 20, "c:/program files/git/usr/bin/bash.exe", "bash.exe",
               (r"C:\Program Files\Git\bin\..\usr\bin\bash.exe", "-c", HOOK_COMMAND), 300)
BASH_OUTER = F(20, 10, "c:/program files/git/bin/bash.exe", "bash.exe",
               (r"C:\Program Files\Git\bin\bash.exe", "-c", HOOK_COMMAND), 200)
HOST = F(10, 1, "c:/users/v/.local/bin/claude.exe", "claude.exe", ("claude.exe",), 100)
HOOK_PROC = F(40, 30, PY, "python.exe", HOOK_ARGV, 400)
ENGINE_PROC = F(50, 40, PY, "python.exe", ENGINE_ARGV, 500)
WRAPPED = (
    "source /c/snap.sh 2>/dev/null || true && "
    "eval 'python tools/saipen.py admission establish'"
)
TOOL_INNER = F(31, 21, "c:/program files/git/usr/bin/bash.exe", "bash.exe",
               ("bash.exe", "-c", WRAPPED), 300)
TOOL_OUTER = F(21, 10, "c:/program files/git/bin/bash.exe", "bash.exe",
               ("bash.exe", "-c", WRAPPED), 200)
POLICY = HI.IdentityPolicy(
    host="claude",
    host_images=("claude.exe", "claude"),
    hook_artifacts=(GUARD,),
    host_signers=("Anthropic, PBC",),
)


class IdentityProofTests(unittest.TestCase):
    """`prove_hook_invocation` on chains shaped like the measured real ones
    (Claude Code 2.1.290 on Windows: host -> bin/bash -c CMD -> usr/bin/bash -c
    CMD -> hook -> engine)."""

    def prove(self, chain, policy=POLICY, signer="Anthropic, PBC", current=True):
        return HI.prove_hook_invocation(
            chain,
            policy,
            signer_of=lambda _path: signer,
            artifact_current=lambda _path: current,
        )

    def assert_refused(self, chain, reason, **kwargs):
        proof = self.prove(chain, **kwargs)
        self.assertFalse(proof.ok, proof.detail)
        self.assertEqual(proof.reason, reason, proof.detail)
        self.assertTrue(proof.detail)

    def test_the_hosts_own_hook_invocation_is_proven(self):
        for chain in (
            [ENGINE_PROC, HOOK_PROC, BASH_INNER, BASH_OUTER, HOST],
            [HOOK_PROC, BASH_INNER, BASH_OUTER, HOST],
            [HOOK_PROC, HOST],  # a host that starts its hook without a shell
        ):
            proof = self.prove(chain)
            self.assertTrue(proof.ok, proof.detail)
            self.assertEqual((proof.host_pid, proof.hook_pid), (10, 40))
            self.assertEqual(proof.hook_root, RUNTIME)
            self.assertEqual(proof.host_signer, "Anthropic, PBC")

    def test_a_command_run_through_the_hosts_shell_tool_is_not_the_hook(self):
        cli = F(60, 31, PY, "python.exe", (PY, "tools/saipen.py", "admission", "establish"), 600)
        imported = F(61, 31, PY, "python.exe", (PY, "-c", "import protocol_admission"), 600)
        for peer in (cli, imported):
            self.assert_refused([peer, TOOL_INNER, TOOL_OUTER, HOST], HI.REASON_HOOK_NOT_FOUND)

    def test_replaying_the_hook_command_from_a_tool_shell_is_refused(self):
        nested = F(32, 31, "c:/program files/git/usr/bin/bash.exe", "bash.exe",
                   ("bash.exe", "-c", HOOK_COMMAND), 350)
        hook = F(41, 32, PY, "python.exe", HOOK_ARGV, 450)
        engine = F(51, 41, PY, "python.exe", ENGINE_ARGV, 550)
        self.assert_refused(
            [engine, hook, nested, TOOL_INNER, TOOL_OUTER, HOST],
            HI.REASON_HOOK_CHAIN_UNRECOGNIZED,
        )
        direct = F(42, 31, PY, "python.exe", HOOK_ARGV, 450)
        self.assert_refused(
            [direct, TOOL_INNER, TOOL_OUTER, HOST], HI.REASON_HOOK_CHAIN_UNRECOGNIZED
        )

    def test_an_interpreter_renamed_after_the_host_is_refused_by_its_signer(self):
        chain = [ENGINE_PROC, HOOK_PROC, BASH_INNER, BASH_OUTER, HOST]
        for signer in ("Python Software Foundation", None, ""):
            self.assert_refused(chain, HI.REASON_HOST_IMAGE_UNVERIFIED, signer=signer)
        # Where the platform has no signer notion the policy requires none.
        unsigned = HI.IdentityPolicy(
            host="claude", host_images=("claude",), hook_artifacts=(GUARD,), host_signers=()
        )
        self.assertTrue(self.prove(chain, policy=unsigned, signer=None).ok)

    def test_the_hook_must_be_the_shipped_bytes_and_declare_the_same_host(self):
        chain = [ENGINE_PROC, HOOK_PROC, BASH_INNER, BASH_OUTER, HOST]
        self.assert_refused(chain, HI.REASON_HOOK_ARTIFACT_MISMATCH, current=False)
        other = F(40, 30, PY, "python.exe",
                  (r"C:\Py\python.exe", GUARD, "--host", "opencode", "--saipen-root", RUNTIME), 400)
        self.assert_refused([other, BASH_INNER, BASH_OUTER, HOST], HI.REASON_HOOK_HOST_MISMATCH)

    def test_the_script_is_the_first_argument_and_only_the_engine_may_follow(self):
        option = F(43, 30, PY, "python.exe",
                   (PY, "-X", GUARD, "evil.py", "--host", "claude", "--saipen-root", RUNTIME), 400)
        self.assert_refused([option, BASH_INNER, BASH_OUTER, HOST], HI.REASON_HOOK_NOT_FOUND)
        foreign = F(52, 40, PY, "python.exe", (PY, r"C:\elsewhere\tools\saipen.py"), 500)
        self.assert_refused(
            [foreign, HOOK_PROC, BASH_INNER, BASH_OUTER, HOST], HI.REASON_HOOK_NOT_FOUND
        )

    def test_the_bootstrap_spelling_is_the_hook_and_no_other_dash_c_program_is(self):
        # What the installer writes now: the artifact behind HOOK_BOOTSTRAP.
        argv = (r"C:\Py\python.exe", "-c", HI.HOOK_BOOTSTRAP, GUARD,
                "--host", "claude", "--saipen-root", RUNTIME)
        command = shlex.join(["C:/Py/python.exe", *argv[1:]])
        hook = F(40, 30, PY, "python.exe", argv, 400)
        inner = F(30, 20, "c:/program files/git/usr/bin/bash.exe", "bash.exe",
                  ("bash.exe", "-c", command), 300)
        outer = F(20, 10, "c:/program files/git/bin/bash.exe", "bash.exe",
                  ("bash.exe", "-c", command), 200)
        for chain in ([ENGINE_PROC, hook, inner, outer, HOST], [hook, inner, outer, HOST]):
            proof = self.prove(chain)
            self.assertTrue(proof.ok, proof.detail)
            self.assertEqual((proof.hook_pid, proof.hook_root), (40, RUNTIME))
        self.assertEqual(HI.hook_script(argv), GUARD)
        self.assertEqual(HI.hook_script(HOOK_ARGV), GUARD)
        # ANY other program after `-c` names nothing as its script, however it
        # spells the hook's path and flags after it.
        for program in ("import evil", HI.HOOK_BOOTSTRAP + ";import evil", ""):
            forged = (PY, "-c", program, GUARD, "--host", "claude", "--saipen-root", RUNTIME)
            self.assertIsNone(HI.hook_script(forged))
            peer = F(44, 30, PY, "python.exe", forged, 400)
            self.assert_refused([peer, inner, outer, HOST], HI.REASON_HOOK_NOT_FOUND)
        self.assertIsNone(HI.hook_script((PY, "-c", HI.HOOK_BOOTSTRAP, "--host", "claude")))
        for quote in ("'", '"'):
            self.assertNotIn(quote, HI.HOOK_BOOTSTRAP)

    def test_a_reused_parent_pid_and_an_unrelated_process_are_refused(self):
        newer = F(10, 1, "c:/users/v/.local/bin/claude.exe", "claude.exe", ("claude.exe",), 999)
        self.assert_refused([HOOK_PROC, BASH_INNER, BASH_OUTER, newer], HI.REASON_PARENT_REUSED)
        shell = F(71, 1, "c:/windows/explorer.exe", "explorer.exe", ("explorer.exe",), 50)
        other = F(70, 71, PY, "python.exe", (PY, "x.py"), 700)
        self.assert_refused([other, shell], HI.REASON_NOT_HOST_DESCENDANT)
        self.assert_refused([], HI.REASON_IDENTITY_UNAVAILABLE)

    def test_a_posix_host_and_shell_follow_the_same_rule(self):
        policy = HI.IdentityPolicy(
            host="claude", host_images=("claude",),
            hook_artifacts=("/home/v/.claude/hooks/saipen-guard.py",),
        )
        command = (
            "/usr/bin/python3 /home/v/.claude/hooks/saipen-guard.py --host claude "
            "--saipen-root /home/v/.claude/skills/saipen"
        )
        host = F(10, 1, "/usr/local/bin/claude", "claude", ("claude",), 100)
        shell = F(20, 10, "/bin/sh", "sh", ("/bin/sh", "-c", command), 200)
        hook = F(40, 20, "/usr/bin/python3.11", "python3.11", tuple(command.split()), 400)
        self.assertTrue(self.prove([hook, shell, host], policy=policy, signer=None).ok)
        wrapped = F(20, 10, "/bin/sh", "sh", ("/bin/sh", "-c", "cd /x && " + command), 200)
        self.assert_refused(
            [hook, wrapped, host], HI.REASON_HOOK_CHAIN_UNRECOGNIZED, policy=policy, signer=None
        )


class ProcessIdentityTests(unittest.TestCase):
    def test_the_windows_command_line_is_split_by_the_platform_rule(self):
        cases = {
            r'"C:\Program Files\Git\bin\bash.exe" -c "C:/Py/python.exe C:/h/g.py --host claude"': [
                r"C:\Program Files\Git\bin\bash.exe", "-c",
                "C:/Py/python.exe C:/h/g.py --host claude",
            ],
            r'a.exe "b c" d\"e "f\\" g': ["a.exe", "b c", 'd"e', "f\\", "g"],
            r'x.exe "a ""q"" b"': ["x.exe", 'a "q" b'],
            "": [],
            "   solo.exe   ": ["solo.exe"],
        }
        for text, expected in cases.items():
            self.assertEqual(HP.split_windows_command_line(text), expected, text)

    def test_this_process_reports_its_own_command_line_start_and_parent(self):
        if not HP.platform_supported():
            self.skipTest("this platform does not report process identity")
        fact = HP.process_fact(os.getpid())
        self.assertIsNotNone(fact)
        self.assertEqual(fact.pid, os.getpid())
        self.assertTrue(fact.argv, "the command line of a live process must be readable")
        self.assertIsNotNone(fact.created)
        chain = HP.ancestry(os.getpid(), 6)
        self.assertGreaterEqual(len(chain), 2)
        # A parent never starts after its child.
        self.assertLessEqual(chain[1].created, chain[0].created)
        self.assertIsNone(HP.process_fact(0))
        self.assertIsNone(HP.process_fact(-5))
        self.assertEqual(HP.ancestry(os.getpid(), 0), [])

    def test_the_signer_of_this_interpreter_is_not_the_hosts(self):
        if not HP.signing_supported():
            self.assertIsNone(HP.image_signer(sys.executable))
            return
        signer = HP.image_signer(sys.executable)
        self.assertNotIn(signer, HB.HOST_SIGNERS, "an interpreter is never the host")
        self.assertIsNone(HP.image_signer(str(HOOK)), "an unsigned file names nobody")
        self.assertIsNone(HP.image_signer(str(ROOT / "no-such-file.exe")))
        self.assertEqual(HP.image_signer(sys.executable), signer, "memoised, same answer")


# ------------------------------------------------------------------- TRANSPORT


class TransportTests(Scratch):
    def serve(self, name: str, handler, stop: threading.Event) -> threading.Thread:
        thread = threading.Thread(
            target=HT.serve, kwargs={"name": name, "handler": handler, "stop": stop}, daemon=True
        )
        thread.start()
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                HT.request(name, {"op": "ready"}, timeout=0.5)
                return thread
            except HT.TransportError:
                time.sleep(0.02)
        raise AssertionError("endpoint never came up")

    def endpoint(self, tag: str) -> str:
        digest = hashlib.sha256((str(self.tmp) + tag).encode()).hexdigest()[:20]
        return HT.endpoint("t1624-" + digest)

    def test_concurrent_clients_are_all_served_and_none_is_told_absent(self):
        name = self.endpoint("busy")
        stop = threading.Event()

        def slow(payload, _peer):
            time.sleep(0.03)
            return {"ok": True, "echo": payload.get("n")}

        thread = self.serve(name, slow, stop)
        self.addCleanup(thread.join, 5)
        self.addCleanup(stop.set)
        results: list = []
        errors: list = []

        def client(n: int) -> None:
            try:
                results.append(HT.request(name, {"n": n}, timeout=20.0)["echo"])
            except HT.TransportError as exc:
                errors.append(exc.kind)

        threads = [threading.Thread(target=client, args=(n,)) for n in range(24)]
        for item in threads:
            item.start()
        for item in threads:
            item.join(60)
        self.assertEqual(errors, [], "a busy service must never read as an absent one")
        self.assertEqual(sorted(results), list(range(24)))

    def test_a_second_server_cannot_join_a_served_endpoint(self):
        if not WINDOWS:
            self.skipTest("first-instance exclusivity is the named-pipe rule")
        name = self.endpoint("exclusive")
        stop = threading.Event()
        thread = self.serve(name, lambda payload, peer: {"ok": True, "who": "first"}, stop)
        self.addCleanup(thread.join, 5)
        self.addCleanup(stop.set)
        with self.assertRaises(HT.TransportError) as caught:
            HT.serve(name, lambda payload, peer: {"ok": True, "who": "second"},
                     stop=threading.Event(), max_requests=1)
        self.assertEqual(caught.exception.kind, "bind")
        self.assertEqual(HT.request(name, {"op": "x"}, timeout=5.0)["who"], "first")

    def test_an_endpoint_served_by_something_else_is_an_impostor_not_the_service(self):
        name = self.endpoint("squat")
        stop = threading.Event()
        # Anything can serve a NAME. This one answers "ADMITTED" to everybody.
        thread = self.serve(
            name, lambda payload, peer: {"ok": True, "state": "ADMITTED", "permitted": True}, stop
        )
        self.addCleanup(thread.join, 5)
        self.addCleanup(stop.set)
        seen: list = []

        def verify(pid):
            seen.append(pid)
            return HC.server_trusted(pid)

        with self.assertRaises(HT.TransportError) as caught:
            HT.request(name, {"op": "admission"}, timeout=5.0, verify_server=verify)
        self.assertEqual(caught.exception.kind, "impostor")
        if HT.peer_supported():
            self.assertEqual(seen, [os.getpid()], "the OS names who serves the endpoint")
        self.assertFalse(HC.server_trusted(os.getpid()), "a test runner is not the service")
        self.assertFalse(HC.server_trusted(None))
        self.assertEqual(HC._unanswered("impostor"), "AUTHORITY_IMPOSTOR")
        self.assertIn(
            HC._norm(ROOT / "tools" / "authority_service.py"), HC.trusted_service_entries()
        )


# ------------------------------------------------------------------------ HOOK


class HookFailOpenTests(Scratch):
    """The one rule the hook holds itself: an engine that cannot be run."""

    def setUp(self) -> None:
        super().setUp()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.runtime = self.tmp / "authority-runtime"
        self.project = self.bare_project()
        self.plain = self.tmp / "plain"
        self.plain.mkdir()
        self.event = {
            "hook_event_name": "UserPromptSubmit", "cwd": str(self.project), "session_id": "s-1",
        }

    def hook(self, artifact: Path, root: Path, event: dict | None = None, cwd: Path | None = None):
        return run_hook(
            artifact, root, self.home, event or self.event,
            cwd=cwd or self.project, runtime=self.runtime,
        )[0]

    def broken_runtime(self, body: str) -> Path:
        root = self.tmp / ("runtime-" + hashlib.sha256(body.encode()).hexdigest()[:8])
        (root / "tools").mkdir(parents=True)
        (root / "tools" / "saipen.py").write_text(body, encoding="utf-8")
        return root

    def test_paired_oracle_the_frozen_hook_blocks_and_the_repaired_hook_does_not(self):
        # ONE oracle, two subjects: a prompt in a SAIPEN project whose runtime is
        # missing, under the default policy, must reach the model.
        identity = json.loads((FROZEN / "subject.json").read_text(encoding="utf-8"))
        frozen = FROZEN / "saipen-guard.py"
        self.assertEqual(hashlib.sha256(frozen.read_bytes()).hexdigest(), identity["sha256"])
        missing = self.tmp / "no-runtime"
        proc = subprocess.run(
            [sys.executable, str(frozen), "--host", "claude", "--saipen-root", str(missing),
             "--home", str(self.home)],
            input=json.dumps(self.event).encode("utf-8"),
            capture_output=True, cwd=str(self.project), check=False, timeout=120,
        )
        before = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual(before["decision"], "block", "the pre-fix subject locks the host out")
        self.assertIn("No reply is permitted", before["reason"])
        after = self.hook(HOOK, missing)
        self.assertNotIn("decision", after, "the repaired subject does not")
        self.assertIn("Model access works", after["systemMessage"])
        # ... and the installer's gate refuses to activate the frozen subject.
        verdict = install_host_guard.self_test(frozen, "claude")
        self.assertFalse(verdict["ok"], verdict)

    def test_every_way_of_not_getting_an_answer_degrades_under_the_default_policy(self):
        cases = {
            "runtime not found": self.tmp / "absent",
            "runtime failed": self.broken_runtime(
                "raise SystemExit('boom: half-written engine')\n"
            ),
            "runtime answer is not an object": self.broken_runtime("print('[1, 2]')\n"),
            "SyntaxError": self.broken_runtime("def broken(:\n"),
        }
        for expected, root in cases.items():
            with self.subTest(case=expected):
                out = self.hook(HOOK, root)
                self.assertNotIn("decision", out, out)
                message = out["systemMessage"]
                self.assertIn(expected, message, "the reason names what actually happened")
                self.assertIn("degraded mode", message)
                self.assertIn("ENGINE_UNREACHABLE", message)
                self.assertIn("host repair", message)
                self.assertIn(PA.DEGRADED_MARKER, message)
                # The model is told the same thing the operator is.
                self.assertEqual(out["hookSpecificOutput"]["additionalContext"], message)
                self.assertNotIn("ADMITTED", message)

    def test_strict_blocks_the_same_failure_with_one_exact_action(self):
        HC.set_authority_mode("strict", self.home)
        out = self.hook(HOOK, self.tmp / "absent")
        self.assertEqual(out["decision"], "block")
        self.assertIn("STRICT", out["reason"])
        self.assertIn("host repair", out["reason"])
        self.assertIn("host mode degraded", out["reason"])
        # A damaged policy file is STRICT, exactly as the engine reads it.
        HC.mode_path(self.home).write_text("{not json", encoding="utf-8")
        self.assertEqual(self.hook(HOOK, self.tmp / "absent")["decision"], "block")

    def raw(
        self,
        arguments: list[str],
        event: dict | None = None,
        *,
        cwd: Path | None = None,
        bootstrap: bool = False,
    ) -> tuple[int, dict | None]:
        """One event through the hook on an EXACT command line; (status, answer).

        The process home is this test's: a command line that cannot be read
        names no `--home`, and the operator's own policy and health record must
        not be what such a case reads and writes.
        """
        head = [sys.executable, str(HOOK)]
        if bootstrap:
            head = [sys.executable, "-c", HI.HOOK_BOOTSTRAP, str(HOOK)]
        env = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
        env["USERPROFILE"] = env["HOME"] = str(self.home)
        proc = subprocess.run(
            [*head, *arguments],
            input=json.dumps(event or self.event).encode("utf-8"),
            capture_output=True, cwd=str(cwd or self.project), check=False, timeout=180, env=env,
        )
        out = proc.stdout.decode("utf-8", errors="replace").strip()
        return proc.returncode, (json.loads(out) if out else None)

    def test_an_answer_that_is_no_admission_verdict_is_an_engine_that_did_not_answer(self):
        # The engine refuses its own command line in its general schema
        # (`ok`/`code`/`detail`, no `permitted`), and so does a runtime of
        # another generation. Read as a verdict, the missing key was a refusal:
        # the prompt was blocked under the DEFAULT policy with an empty reason.
        cases = {
            "--session is required": self.broken_runtime(
                "import json\n"
                "print(json.dumps({'ok': False, 'code': 'VALIDATION_FAILED',"
                " 'detail': '--session is required'}))\n"
                "raise SystemExit(2)\n"
            ),
            "no verdict": self.broken_runtime("print('{}')\n"),
            "permitted is not a boolean": self.broken_runtime(
                "import json\nprint(json.dumps({'permitted': 'false', 'state': 'ADMITTED'}))\n"
            ),
        }
        for expected, root in cases.items():
            with self.subTest(case=expected):
                out = self.hook(HOOK, root)
                self.assertIsNotNone(out, "an answer nobody can read is never passed in silence")
                self.assertNotIn("decision", out, out)
                message = out["systemMessage"]
                self.assertIn("not an admission verdict", message)
                self.assertIn(expected, message, "the reason names what the engine said")
                self.assertIn("ENGINE_UNREACHABLE", message)
                self.assertIn("host repair", message)
                self.assertIn(PA.DEGRADED_MARKER, message)
                self.assertEqual(out["hookSpecificOutput"]["additionalContext"], message)
        HC.set_authority_mode("strict", self.home)
        blocked = self.hook(HOOK, cases["no verdict"])
        self.assertEqual(blocked["decision"], "block")
        self.assertIn("host repair", blocked["reason"])

    def test_a_host_event_without_a_session_id_reaches_the_model_through_the_real_engine(self):
        # The same class on the real engine, not a stand-in: an event that
        # carries no session id makes `admission establish` refuse its
        # arguments. That is not a verdict about this prompt.
        (self.tmp / "w").mkdir()
        world = World(self.tmp / "w", mode=None)
        event = {"hook_event_name": "UserPromptSubmit", "cwd": str(world.project)}
        out, _took = run_hook(
            HOOK, ROOT, world.home, event, cwd=world.project, runtime=world.runtime
        )
        self.assertNotIn("decision", out, out)
        self.assertIn("--session is required", out["systemMessage"])
        self.assertIn(PA.DEGRADED_MARKER, out["systemMessage"])

    def test_a_refusal_never_reaches_the_operator_without_a_reason_and_an_action(self):
        silent = self.broken_runtime(
            "import json\n"
            "print(json.dumps({'permitted': False, 'state': 'REFUSED',"
            " 'failure': 'BINDING_CONFLICT'}))\n"
        )
        out = self.hook(HOOK, silent)
        self.assertEqual(out["decision"], "block", "a real refusal still refuses")
        self.assertIn("BINDING_CONFLICT", out["reason"])
        self.assertIn("host doctor", out["reason"])
        start = self.hook(HOOK, silent, {**self.event, "hook_event_name": "SessionStart"})
        self.assertNotIn("decision", start)
        self.assertIn("host doctor", start["systemMessage"])

    def test_a_command_line_the_hook_cannot_read_is_never_an_exit_status_that_blocks(self):
        # A host snapshots hook commands at start, so a session can hold the
        # command of one generation while the artifact is another's. argparse
        # answers an unknown or missing argument with status 2, and a host
        # reads status 2 from a hook as "block this event".
        absent = self.tmp / "absent"
        root = ["--saipen-root", str(absent)]
        home = ["--home", str(self.home)]
        for bootstrap in (False, True):
            with self.subTest(case="flag of another generation", bootstrap=bootstrap):
                status, out = self.raw(
                    ["--host", "claude", "--flag-of-another-generation", "x", *home, *root],
                    bootstrap=bootstrap,
                )
                self.assertEqual(status, 0)
                # Read past: the event is handled exactly as without the flag.
                self.assertIn("runtime not found", out["systemMessage"])
                self.assertEqual(HG.read_health("claude", self.home)["unread_arguments"], 2)
        unreadable = (
            ("names no --saipen-root", ["--host", "claude", *home]),
            ("names no --saipen-root", ["--host", "claude", *home, "--saipen-root"]),
            ("names host 'codex'", ["--host", "codex", *home, *root]),
            # What argparse itself still refuses: no value can be salvaged, so
            # the policy and the health record are the process home's.
            ("ignored explicit argument", ["--host", "claude", *root, "--self-test=1"]),
        )
        outside = {**self.event, "cwd": str(self.plain)}
        stop = {**self.event, "hook_event_name": "Stop", "last_assistant_message": "ok"}
        for expected, arguments in unreadable:
            with self.subTest(case=expected, policy="default"):
                HC.mode_path(self.home).unlink(missing_ok=True)
                status, out = self.raw(arguments)
                self.assertEqual(status, 0)
                self.assertNotIn("decision", out, out)
                self.assertIn("hook command line", out["systemMessage"])
                self.assertIn(expected, out["systemMessage"])
                self.assertIn("ENGINE_UNREACHABLE", out["systemMessage"])
                self.assertIn("host repair", out["systemMessage"])
                self.assertEqual(self.raw(arguments, outside, cwd=self.plain), (0, None))
                status, out = self.raw(arguments, stop)
                self.assertEqual(status, 0)
                self.assertNotIn("decision", out)
                self.assertIn("CLAUDE_STOP_GATE_UNAVAILABLE", out["systemMessage"])
            with self.subTest(case=expected, policy="strict"):
                # STRICT is the operator's and is not downgraded by a fault:
                # it blocks through the hook's own answer, with the action.
                HC.set_authority_mode("strict", self.home)
                status, out = self.raw(arguments)
                self.assertEqual(status, 0)
                self.assertEqual(out["decision"], "block")
                self.assertIn("host repair", out["reason"])
                self.assertEqual(self.raw(arguments, outside, cwd=self.plain), (0, None))

    def test_a_slow_engine_is_a_bounded_failure_the_hook_decides(self):
        module = load_hook()
        slow = self.broken_runtime("import time\ntime.sleep(30)\n")
        started = time.perf_counter()
        with self.assertRaises(module.EngineUnreachable) as caught:
            module._run_engine(slow, self.project, ["admission", "status"], stdin=None, timeout=1)
        self.assertLess(time.perf_counter() - started, 15)
        self.assertIn("did not answer within 1s", str(caught.exception))
        # The hook's own budget stays below the timeout the installer writes, so
        # the hook -- never the host's kill -- decides what a slow engine means.
        timeouts = {event: seconds for event, _matcher, seconds in install_host_guard.CLAUDE_EVENTS}
        self.assertLess(module.ADMISSION_TIMEOUT_SECONDS, timeouts["UserPromptSubmit"])
        self.assertLess(module.ADMISSION_TIMEOUT_SECONDS, timeouts["SessionStart"])
        self.assertLess(module.CHECK_TIMEOUT_SECONDS, timeouts["Stop"])

    def test_events_that_cannot_block_never_try_to_and_nothing_fires_outside_a_project(self):
        HC.set_authority_mode("strict", self.home)
        absent = self.tmp / "absent"
        start = self.hook(HOOK, absent, {**self.event, "hook_event_name": "SessionStart"})
        self.assertNotIn("decision", start)
        self.assertIn("ENGINE_UNREACHABLE", start["systemMessage"])
        stop = self.hook(
            HOOK, absent,
            {**self.event, "hook_event_name": "Stop", "last_assistant_message": "ok"},
        )
        self.assertNotIn("decision", stop)
        self.assertIn("CLAUDE_STOP_GATE_UNAVAILABLE", stop["systemMessage"])
        outside = {**self.event, "cwd": str(self.plain)}
        self.assertIsNone(self.hook(HOOK, absent, outside, cwd=self.plain))
        self.assertIsNone(self.hook(HOOK, absent, {"hook_event_name": "PreToolUse"}))

    def test_the_hook_leaves_a_health_record_the_doctor_can_read(self):
        self.hook(HOOK, self.tmp / "absent")
        record = HG.read_health("claude", self.home)
        self.assertEqual(record["state"], "DEGRADED")
        self.assertEqual(record["code"], "ENGINE_UNREACHABLE")
        self.assertEqual(record["event"], "UserPromptSubmit")
        self.assertIsInstance(record["elapsed_ms"], int)
        self.assertNotIn("prompt", json.dumps(record), "the record never carries the prompt")

    def test_the_prompt_path_stays_inside_its_latency_budget(self):
        # Measured on the operator's machine before the repair: 0.7-0.9 s per
        # prompt, most of it re-hashing the shipped runtime twice. The budget
        # is generous so a loaded machine does not flap, and still far below
        # what the lockout cost.
        (self.tmp / "w").mkdir()
        world = World(self.tmp / "w", mode=None)
        event = {"hook_event_name": "UserPromptSubmit", "cwd": str(world.project),
                 "session_id": "perf-1"}
        timings = []
        for _ in range(4):
            out, took = run_hook(
                HOOK, ROOT, world.home, event, cwd=world.project, runtime=world.runtime
            )
            self.assertNotIn("decision", out)
            timings.append(took)
        self.assertLess(statistics.median(timings[1:]), 3.0, timings)
        outside = {"hook_event_name": "UserPromptSubmit", "cwd": str(self.plain),
                   "session_id": "perf-2"}
        quick = [
            run_hook(HOOK, ROOT, world.home, outside, cwd=self.plain, runtime=world.runtime)[1]
            for _ in range(3)
        ]
        self.assertLess(min(quick), 1.0, "a prompt outside any project costs one interpreter start")


# --------------------------------------------------------------------- INSTALL


class InstallerTests(Scratch):
    def setUp(self) -> None:
        super().setUp()
        self.home = self.tmp / "home"
        (self.home / ".claude").mkdir(parents=True)
        self.settings = self.home / ".claude" / "settings.json"
        self.artifact = self.home / ".claude" / "hooks" / "saipen-guard.py"
        self.operator = {
            "theme": "dark",
            "hooks": {
                "UserPromptSubmit": [
                    {"hooks": [{"type": "command", "command": "printf operator-hook"}]}
                ],
                "PreToolUse": [
                    {"matcher": "Grep", "hooks": [{"type": "command", "command": "other-tool"}]}
                ],
            },
        }
        self.settings.write_text(json.dumps(self.operator, indent=2) + "\n", encoding="utf-8")

    def owned(self) -> list[tuple[str, dict]]:
        data = json.loads(self.settings.read_text(encoding="utf-8"))
        found = []
        for event, groups in (data.get("hooks") or {}).items():
            for group in groups:
                for hook in group["hooks"]:
                    if "saipen-guard.py" in str(hook.get("command")):
                        found.append((event, hook))
        return found

    def source_with(self, guard_bytes: bytes) -> Path:
        """A source root whose shipped hook is `guard_bytes` and nothing else differs."""
        source = self.tmp / ("source-" + hashlib.sha256(guard_bytes).hexdigest()[:10])
        target = source / "extensions" / "adapters"
        (target / "claude").mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "extensions" / "adapters" / "registry.json", target / "registry.json")
        (target / "claude" / "saipen-guard.py").write_bytes(guard_bytes)
        return source

    def test_install_stages_verifies_activates_and_keeps_the_operators_config(self):
        result = install_host_guard.install("claude", self.home, ROOT)
        self.assertTrue(result["current"], result)
        self.assertEqual(result["problems"], [])
        self.assertEqual(result["activation"]["step"], "activated")
        self.assertEqual(
            sorted(event for event, _hook in self.owned()),
            sorted(event for event, _m, _t in install_host_guard.CLAUDE_EVENTS),
        )
        data = json.loads(self.settings.read_text(encoding="utf-8"))
        self.assertEqual(data["theme"], "dark")
        commands = json.dumps(data)
        self.assertIn("printf operator-hook", commands)
        self.assertIn("other-tool", commands)
        self.assertFalse(self.artifact.with_name(self.artifact.name + ".staged").exists())
        # Idempotent: a second install changes no byte and reports it.
        before = (self.settings.read_bytes(), self.artifact.read_bytes())
        again = install_host_guard.install("claude", self.home, ROOT)
        self.assertEqual(again["activation"]["step"], "already-current")
        self.assertEqual((self.settings.read_bytes(), self.artifact.read_bytes()), before)
        self.assertEqual(len(self.owned()), len(install_host_guard.CLAUDE_EVENTS))
        checked = install_host_guard.install("claude", self.home, ROOT, check=True)
        self.assertTrue(checked["current"])

    def test_a_hook_that_would_lock_the_host_out_is_never_activated(self):
        install_host_guard.install("claude", self.home, ROOT)
        good = (self.settings.read_bytes(), self.artifact.read_bytes())
        # The frozen pre-fix hook is exactly a hook that blocks without its engine.
        broken = self.source_with((FROZEN / "saipen-guard.py").read_bytes())
        result = install_host_guard.install("claude", self.home, broken)
        self.assertFalse(result["activation"]["activated"])
        self.assertEqual(result["activation"]["code"], "INSTALL_PREFLIGHT_FAILED")
        self.assertFalse(result["current"])
        self.assertTrue(
            any(item.startswith("install-preflight-failed") for item in result["problems"])
        )
        self.assertEqual((self.settings.read_bytes(), self.artifact.read_bytes()), good,
                         "the working hook generation is untouched")
        self.assertFalse(self.artifact.with_name(self.artifact.name + ".staged").exists())
        # A hook that does not even start is refused the same way.
        dead = self.source_with(b"raise SystemExit(3)\n")
        refused = install_host_guard.install("claude", self.home, dead)
        self.assertEqual(refused["activation"]["step"], "start")
        self.assertEqual(self.artifact.read_bytes(), good[1])

    def test_the_self_test_names_which_property_failed(self):
        self.assertTrue(install_host_guard.self_test(HOOK, "claude")["ok"])
        noisy = self.tmp / "noisy.py"
        anchor ="    if project is None:\n        # No SAIPEN project"
        self.assertIn(anchor, HOOK.read_text(encoding="utf-8"), "the red control's anchor moved")
        noisy.write_text(
            HOOK.read_text(encoding="utf-8").replace(
                anchor, "    if project is None:\n        print('{}')\n        # No SAIPEN project"
            ),
            encoding="utf-8",
        )
        self.assertEqual(install_host_guard.self_test(noisy, "claude")["step"], "outside-project")
        self.assertEqual(
            install_host_guard.self_test(FROZEN / "saipen-guard.py", "claude")["ok"], False
        )

        def variant(name: str, *swaps: tuple[str, str]) -> Path:
            text = HOOK.read_text(encoding="utf-8")
            for old, new in swaps:
                self.assertIn(old, text, "the red control's anchor moved")
                text = text.replace(old, new)
            path = self.tmp / name
            path.write_text(text, encoding="utf-8")
            return path

        # Two more ways a hook locks its host out, each refused by name: an
        # engine answer that is no verdict read as a refusal, and a command
        # line it cannot read answered with the exit status a host calls block.
        believing = variant(
            "believing.py",
            ('if verb == "establish" and not isinstance(verdict.get("permitted"), bool):',
             "if False:"),
        )
        self.assertEqual(
            install_host_guard.self_test(believing, "claude")["step"], "engine-off-schema"
        )
        exiting = variant(
            "exiting.py",
            ('parser.add_argument("--saipen-root", type=Path, nargs="?")',
             'parser.add_argument("--saipen-root", type=Path)'),
            ("raise CommandLineFault(message)", "argparse.ArgumentParser.error(self, message)"),
        )
        self.assertEqual(
            install_host_guard.self_test(exiting, "claude")["step"], "foreign-command-line"
        )

    def test_the_previous_generation_is_kept_and_rollback_restores_it(self):
        older = HOOK.read_bytes() + b"\n# an older generation\n"
        install_host_guard.install("claude", self.home, self.source_with(older))
        self.assertEqual(self.artifact.read_bytes(), older)
        install_host_guard.install("claude", self.home, ROOT)
        kept = install_host_guard.previous_artifact(self.artifact)
        self.assertEqual(kept.read_bytes(), older)
        rolled = install_host_guard.rollback("claude", self.home, ROOT)
        self.assertTrue(rolled["rolled_back"], rolled)
        self.assertEqual(self.artifact.read_bytes(), older)
        self.assertEqual(kept.read_bytes(), HOOK.read_bytes(), "rollback is itself reversible")
        kept.unlink()
        self.assertFalse(install_host_guard.rollback("claude", self.home, ROOT)["rolled_back"])

    def test_uninstall_restores_plain_claude_and_the_cycle_repeats(self):
        original = self.settings.read_bytes()
        for _cycle in range(2):
            install_host_guard.install("claude", self.home, ROOT)
            self.assertTrue(self.owned())
            removed = install_host_guard.uninstall("claude", self.home, ROOT)
            self.assertEqual(removed["removed_hooks"], len(install_host_guard.CLAUDE_EVENTS))
            self.assertTrue(removed["artifact_removed"])
            self.assertEqual(self.owned(), [])
            self.assertEqual(
                json.loads(self.settings.read_text(encoding="utf-8")), self.operator,
                "nothing of the operator's is lost and nothing of SAIPEN's is left",
            )
            self.assertFalse(self.artifact.exists())
            self.assertFalse(install_host_guard.previous_artifact(self.artifact).exists())
        self.assertEqual(json.loads(original), self.operator)
        # Uninstalling twice, and uninstalling what was never installed, is safe.
        again = install_host_guard.uninstall("claude", self.home, ROOT)
        self.assertEqual(again["removed_hooks"], 0)

    def test_uninstall_after_a_partial_install_leaves_nothing_behind(self):
        install_host_guard.install("claude", self.home, ROOT)
        data = json.loads(self.settings.read_text(encoding="utf-8"))
        data["hooks"].pop("Stop")
        data["hooks"].pop("SessionStart")
        self.settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        check = install_host_guard.install("claude", self.home, ROOT, check=True)
        self.assertFalse(check["current"])
        self.assertIn("config-entry-missing:Stop", check["problems"])
        # Repair is the same install; then a clean removal.
        self.assertTrue(install_host_guard.install("claude", self.home, ROOT)["current"])
        install_host_guard.uninstall("claude", self.home, ROOT)
        self.assertEqual(self.owned(), [])

    def as_the_host_runs_it(self, command: str, *, shell: list[str] | None = None):
        """One UserPromptSubmit through a configured hook command, started the
        way a host starts it: the platform shell and the command string."""
        self.runs = getattr(self, "runs", 0) + 1
        project = self.bare_project(f"hosted-{self.runs}")
        event = {"hook_event_name": "UserPromptSubmit", "cwd": str(project), "session_id": "s"}
        # The configured command names no `--home` -- that is the spelling under
        # test -- so the PROFILE the child resolves is this test's. With the
        # operator's, the hook asked the operator's live authority service and
        # replaced the operator's health record with a fixture's (T-1634).
        env = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
        env.update(USERPROFILE=str(self.home), HOME=str(self.home), HOMEDRIVE="", HOMEPATH="")
        return subprocess.run(
            [*(shell or platform_shell()), command],
            input=json.dumps(event).encode("utf-8"),
            capture_output=True,
            cwd=str(project),
            check=False,
            timeout=120,
            env=env,
        )

    def legacy_command(self) -> str:
        """The pre-bootstrap spelling: the artifact as the interpreter's script."""
        return shlex.join(
            item.replace("\\", "/")
            for item in (
                sys.executable, str(self.artifact), "--host", "claude",
                "--saipen-root", str(self.tmp / "no-runtime"),
            )
        )

    def test_a_missing_hook_file_cannot_block_the_host(self):
        # Measured on Claude Code 2.1.291: a hook command whose script is gone
        # exits 2 and the host blocks EVERY prompt with the interpreter's
        # "can't open file". The command the installer writes must do nothing
        # instead -- whoever removed the file, and whenever the host loaded it.
        install_host_guard.install("claude", self.home, ROOT, verify=False)
        configured = next(hook["command"] for event, hook in self.owned()
                          if event == "UserPromptSubmit")
        self.assertIn(HI.HOOK_BOOTSTRAP, configured)
        self.artifact.unlink()
        ran = self.as_the_host_runs_it(configured)
        self.assertEqual((ran.returncode, ran.stdout, ran.stderr), (0, b"", b""))
        # The pre-fix subject, on the same oracle: exit status 2.
        self.assertEqual(self.as_the_host_runs_it(self.legacy_command()).returncode, 2)
        # Both spellings a Codex entry carries, each through its own shell.
        posix, windows = install_host_guard.command_pair("codex", self.artifact, ROOT)
        self.assertEqual(self.as_the_host_runs_it(posix).returncode, 0)
        if WINDOWS:
            # cmd.exe takes its command as ONE raw line; an argv list would be
            # re-quoted by this interpreter with escapes cmd does not read.
            raw = subprocess.run(
                f'{os.environ.get("COMSPEC", "cmd.exe")} /d /s /c "{windows}"',
                input=b"{}",
                capture_output=True,
                cwd=str(self.tmp),
                check=False,
                timeout=120,
            )
            self.assertEqual((raw.returncode, raw.stdout, raw.stderr), (0, b"", b""))
        # With the artifact back the SAME command runs the hook again.
        install_host_guard.install("claude", self.home, ROOT, verify=False)
        self.assertIsNone(HG.read_health("claude", self.home))
        self.assertEqual(self.as_the_host_runs_it(configured).returncode, 0)
        # ... in THIS test's profile: the hook that just ran is the one that
        # left a health record here, so it did not leave one in the operator's.
        record = HG.read_health("claude", self.home)
        self.assertIsNotNone(record, "the fixture hook wrote its record outside the fixture")
        self.assertEqual(Path(record["hook"]), self.artifact.resolve())
        checked = install_host_guard.install("claude", self.home, ROOT, check=True)
        self.assertTrue(checked["current"], checked["problems"])

    def test_uninstall_under_a_live_host_leaves_an_inert_stand_in(self):
        # A session that was running at uninstall time keeps the command it
        # loaded -- one written before the bootstrap names the artifact as the
        # interpreter's script, so the file must stay harmless, not vanish.
        install_host_guard.install("claude", self.home, ROOT, verify=False)
        result = install_host_guard.uninstall("claude", self.home, ROOT, live_host=True)
        self.assertEqual((result["artifact_removed"], result["artifact_retired"]), (True, True))
        self.assertEqual(self.owned(), [])
        self.assertTrue(install_host_guard.is_retired(self.artifact))
        ran = self.as_the_host_runs_it(self.legacy_command())
        self.assertEqual((ran.returncode, ran.stdout, ran.stderr), (0, b"", b""))
        # A reinstall replaces the stand-in and never keeps it as a generation
        # to roll back to; a later uninstall with no host alive removes it all.
        self.assertTrue(install_host_guard.install("claude", self.home, ROOT)["current"])
        self.assertFalse(install_host_guard.is_retired(self.artifact))
        self.assertFalse(install_host_guard.previous_artifact(self.artifact).exists())
        install_host_guard.uninstall("claude", self.home, ROOT, live_host=True)
        gone = install_host_guard.uninstall("claude", self.home, ROOT, live_host=False)
        self.assertEqual((gone["removed_hooks"], gone["artifact_retired"]), (0, False))
        self.assertFalse(self.artifact.exists())
        # A fixture home is never probed for the machine's own hosts, whatever
        # the environment calls "home": liveness is asked of the profile the
        # operating system records, and this is not it.
        install_host_guard.install("claude", self.home, ROOT, verify=False)
        redirected = {"USERPROFILE": str(self.home), "HOME": str(self.home)}
        with mock.patch.dict(os.environ, redirected):
            plain = install_host_guard.uninstall("claude", self.home, ROOT)
        self.assertFalse(plain["artifact_retired"])
        self.assertFalse(self.artifact.exists())
        self.assertNotEqual(install_host_guard.machine_profile(), self.home)

    def uninstall_without_python(
        self, shell: str, *, host_alive: bool = False
    ) -> subprocess.CompletedProcess:
        """The canonical Windows uninstaller on a machine with no interpreter."""
        env = {key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")}
        env.pop("ZAICODE_HOME", None)
        env.update(
            HOME=str(self.home),
            USERPROFILE=str(self.home),
            LOCALAPPDATA=str(self.home / "AppData" / "Local"),
            SAIPEN_UNINSTALL_SKIP_TASK="1",
            # Unset by default ON PURPOSE: this home is not the machine's
            # profile, so the uninstaller must not consult the machine's
            # processes for it -- even when the suite itself runs under a host.
            **({"SAIPEN_UNINSTALL_HOST_ALIVE": "1"} if host_alive else {}),
            # Named and absent: the interpreter the hooks were installed with
            # has been uninstalled.
            SAIPEN_PYTHON=str(self.tmp / "uninstalled" / "python.exe"),
        )
        return subprocess.run(
            [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(ROOT / "bootstrap" / "uninstall.ps1")],
            env=env,
            cwd=str(self.tmp),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=240,
            check=False,
        )

    @unittest.skipUnless(WINDOWS_POWERSHELL, "Windows PowerShell transport unavailable")
    def test_the_emergency_uninstall_needs_no_python(self):
        self.emergency_uninstall(WINDOWS_POWERSHELL)

    @unittest.skipUnless(POWERSHELL_7, "PowerShell 7 transport unavailable")
    def test_the_emergency_uninstall_needs_no_python_under_powershell_7(self):
        self.emergency_uninstall(POWERSHELL_7)

    def emergency_uninstall(self, shell: str) -> None:
        # The uninstaller is the operator's way OUT, and it resolved its
        # interpreter with a terminating error: on a machine without Python --
        # where an installed hook cannot start either -- it removed nothing.
        operator_bytes = self.settings.read_bytes()
        foreign = {"type": "command", "command": "echo user-hook"}
        shared = {
            "codex": (
                self.home / ".codex" / "hooks.json",
                {"hooks": {"Stop": [{"hooks": [foreign]}]}},
            ),
            "gemini": (
                self.home / ".gemini" / "settings.json",
                {"theme": "user", "hooks": {"BeforeTool": [{"matcher": "x", "hooks": [foreign]}]}},
            ),
        }
        for config, data in shared.values():
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        (self.home / ".kiro").mkdir()
        for host in ("claude", "codex", "gemini", "kiro"):
            install_host_guard.install(host, self.home, ROOT, verify=False)
        self.assertEqual(len(self.owned()), len(install_host_guard.CLAUDE_EVENTS))
        # The operator edits the Gemini file AFTER the install: it can no
        # longer be put back from the installer's backup, only cleaned.
        gemini, _ = shared["gemini"]
        edited = json.loads(gemini.read_text(encoding="utf-8"))
        edited["post_install_setting"] = "keep"
        gemini.write_text(json.dumps(edited) + "\n", encoding="utf-8")
        before_uninstall = gemini.read_bytes()
        (self.artifact.with_name(self.artifact.name + ".previous")).write_bytes(b"# older\n")
        health = HG.health_path("claude", self.home)
        health.parent.mkdir(parents=True, exist_ok=True)
        health.write_text("{}", encoding="utf-8")
        # An installed runtime: one owned file untouched, one edited by its
        # owner, one the operator added.
        skill = self.home / ".claude" / "skills" / "saipen"
        (skill / "tools").mkdir(parents=True)
        (skill / "tools" / "owned.py").write_bytes(b"shipped\n")
        (skill / "SKILL.md").write_bytes(b"shipped skill\n")
        ledger = {
            "schema_version": 1,
            "files": {
                "tools/owned.py": hashlib.sha256(b"shipped\n").hexdigest(),
                "SKILL.md": hashlib.sha256(b"shipped skill\n").hexdigest(),
            },
        }
        (skill / ".saipen_install.json").write_text(json.dumps(ledger), encoding="utf-8")
        (skill / "SKILL.md").write_bytes(b"shipped skill\nmy annotation\n")
        (skill / "my-note.txt").write_bytes(b"KEEP\n")
        instruction = self.home / ".claude" / "CLAUDE.md"
        instruction.write_bytes(
            b"my rules\r\n\r\n<!-- SAIPEN:BEGIN -->\r\nblock\r\n<!-- SAIPEN:END -->\r\n"
        )

        proc = self.uninstall_without_python(shell)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("No working Python interpreter", proc.stdout)
        self.assertIn("guard hook removed natively", proc.stdout)
        self.assertNotIn("FAILED", proc.stdout)

        # Claude: nothing of the guard is left, and the operator's file is the
        # bytes it was before SAIPEN ever touched it.
        self.assertEqual(self.owned(), [])
        self.assertEqual(self.settings.read_bytes(), operator_bytes)
        self.assertFalse(self.artifact.exists())
        self.assertFalse(self.artifact.with_name(self.artifact.name + ".previous").exists())
        self.assertFalse(health.exists())
        for host, (config, original) in shared.items():
            with self.subTest(host=host):
                now = json.loads(config.read_text(encoding="utf-8"))
                self.assertNotIn("saipen-guard", json.dumps(now))
                expected = dict(original)
                if host == "gemini":
                    expected["post_install_setting"] = "keep"
                    kept = config.with_name(config.name + ".uninstalled.bak")
                    self.assertEqual(kept.read_bytes(), before_uninstall)
                self.assertEqual(now, expected)
        # Kiro's hook file was SAIPEN's alone: it is gone, not left empty.
        kiro = self.home / next(
            item for item in HG.load_registry()["adapters"] if item["id"] == "kiro"
        )["hook_config_surface"].removeprefix("~/")
        self.assertFalse(kiro.exists())
        # The runtime: owned and unchanged goes; edited and unknown stay.
        self.assertFalse((skill / "tools").exists())
        self.assertFalse((skill / ".saipen_install.json").exists())
        self.assertEqual((skill / "SKILL.md").read_bytes(), b"shipped skill\nmy annotation\n")
        self.assertEqual((skill / "my-note.txt").read_bytes(), b"KEEP\n")
        self.assertEqual(instruction.read_bytes(), b"my rules\r\n")
        # Idempotent: a second run on the cleaned machine changes nothing.
        again = self.uninstall_without_python(shell)
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(self.settings.read_bytes(), operator_bytes)
        # The same native path under a LIVE host: the hook file becomes the
        # inert stand-in instead of vanishing under a session that loaded it.
        install_host_guard.install("claude", self.home, ROOT, verify=False)
        live = self.uninstall_without_python(shell, host_alive=True)
        self.assertEqual(live.returncode, 0, live.stdout + live.stderr)
        self.assertEqual(self.owned(), [])
        self.assertTrue(install_host_guard.is_retired(self.artifact))
        self.assertEqual(self.as_the_host_runs_it(self.legacy_command()).returncode, 0)
        cleared = self.uninstall_without_python(shell)
        self.assertEqual(cleared.returncode, 0, cleared.stdout + cleared.stderr)
        self.assertFalse(self.artifact.exists())

    def test_the_interpreter_is_a_variable_and_a_missing_one_is_named(self):
        install_host_guard.install("claude", self.home, ROOT)
        text = self.settings.read_text(encoding="utf-8")
        interpreter = install_host_guard.interpreter_of(self.owned()[0][1]["command"])
        self.assertTrue(interpreter)
        # The SAME hook, checked by a process running under another interpreter
        # path: still current. A broker started with `pythonw` read it stale.
        other = self.tmp / "elsewhere" / Path(sys.executable).name
        with mock.patch.object(sys, "executable", str(other)):
            self.assertTrue(
                install_host_guard.install("claude", self.home, ROOT, check=True)["current"]
            )
        # An interpreter that is gone cannot start the hook: named, not "stale".
        gone = str(self.tmp / "uninstalled" / "python.exe").replace("\\", "/")
        self.settings.write_text(text.replace(interpreter, gone), encoding="utf-8")
        check = install_host_guard.install("claude", self.home, ROOT, check=True)
        self.assertFalse(check["current"])
        self.assertTrue(
            any(item.startswith("hook-interpreter-missing") for item in check["problems"]),
            check["problems"],
        )

    def another_spelling_of_this_interpreter(self) -> str:
        """The interpreter running this test under a second, equally real path."""
        here = Path(sys.executable)
        if WINDOWS:
            # One file, two spellings: the launcher writes `python.EXE`, the
            # installer's own process reports `python.exe`.
            return str(here.with_name(here.stem + here.suffix.swapcase()))
        link = self.tmp / "another-python"
        link.symlink_to(here)
        return str(link)

    def test_the_interpreter_is_a_variable_in_the_cmd_spelling_too(self):
        # T-1634. Codex, Gemini and Kiro entries carry the cmd.exe spelling: an
        # unquoted backslash path. `interpreter_missing` read only the POSIX
        # split of a command, which strips those backslashes, so the installed
        # interpreter read as gone, "the same modulo the interpreter" could
        # never hold, and a hook checked under another spelling of the SAME
        # Python was stale for ever. Measured: the doctor answered
        # config-entry-differs where the installer answered current, and
        # `saipen host repair` ended incomplete on every run.
        spelled = subprocess.list2cmdline([sys.executable, "-c", "pass", "a b"])
        self.assertFalse(install_host_guard.interpreter_missing(spelled))
        self.assertEqual(
            os.path.normcase(install_host_guard.interpreter_of(spelled)),
            os.path.normcase(sys.executable),
        )
        gone = subprocess.list2cmdline([str(self.tmp / "gone" / "python.exe"), "-c", "pass"])
        self.assertTrue(install_host_guard.interpreter_missing(gone))
        other = self.another_spelling_of_this_interpreter()
        self.assertNotEqual(other, sys.executable)
        self.assertTrue(Path(other).is_file())
        for host in ("codex", "gemini", "kiro"):
            with self.subTest(host=host):
                (self.home / f".{host}").mkdir(exist_ok=True)
                installed = install_host_guard.install(host, self.home, ROOT, verify=False)
                self.assertTrue(installed["current"], installed["problems"])
                with mock.patch.object(sys, "executable", other):
                    check = install_host_guard.install(host, self.home, ROOT, check=True)
                self.assertEqual(check["problems"], [])
                self.assertTrue(check["current"])

    def test_the_hook_delegates_to_the_installed_runtime_only_when_it_is_proven(self):
        entry = {
            "hook_delegate": "installed_runtime",
            "install": {"skill": "~/.claude/skills/saipen"},
        }
        installed = self.home / ".claude" / "skills" / "saipen"
        self.assertEqual(install_host_guard.delegated_root(entry, self.home, ROOT), ROOT)
        installed.mkdir(parents=True)
        with mock.patch.object(install_host_guard, "same_runtime_generation", return_value=False):
            self.assertEqual(install_host_guard.delegated_root(entry, self.home, ROOT), ROOT)
        with mock.patch.object(install_host_guard, "same_runtime_generation", return_value=True):
            self.assertEqual(install_host_guard.delegated_root(entry, self.home, ROOT), installed)
            undeclared = {"install": {"skill": "~/.claude/skills/saipen"}}
            self.assertEqual(install_host_guard.delegated_root(undeclared, self.home, ROOT), ROOT)
        registry = HG.load_registry()
        declared = [a["id"] for a in registry["adapters"] if a.get("hook_delegate")]
        self.assertEqual(declared, ["claude"])


# ----------------------------------------------------------------------- STATE


def facts(**overrides) -> dict:
    """Observed facts of a healthy, installed, mechanical host; override to taste."""
    base = {
        "id": "claude",
        "name": "Claude Code",
        "contract": {
            "mechanical_admission": True,
            "admission_enforcement": "MECHANICAL",
            "response_enforcement": "MECHANICAL",
            "separated_authority": True,
        },
        "installable": True,
        "observable": True,
        "host_present": True,
        "host_home": "~/.claude",
        "runtime": {
            "declared": True, "installed": True, "generation": "gen-a", "current": True,
            "diff": [], "launcher_problems": [], "provenance_problems": [], "staging": [],
            "path": "x",
        },
        "hook": {
            "declared": True, "installed": True, "status": "current", "problems": [],
            "installed_at": time.time() - 100, "delegated_root": "x",
        },
        "instruction": "current",
        "health": {"state": "ADMITTED", "at": time.time(), "code": None},
        "authority": {"identity_supported": True, "running": True, "generation_current": True,
                      "mode": "degraded"},
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = {**base[key], **value}
        else:
            base[key] = value
    return base


class StateModelTests(unittest.TestCase):
    def state(self, **overrides) -> str:
        return HG.derive_state(facts(**overrides))[0]

    def test_each_state_is_reached_from_the_facts_that_define_it(self):
        self.assertEqual(self.state(), HG.STATE_HEALTHY_VERIFIED)
        self.assertEqual(self.state(host_present=False), HG.STATE_UNINSTALLED)
        self.assertEqual(
            self.state(runtime={"installed": False}, hook={"installed": False}),
            HG.STATE_UNINSTALLED,
        )
        self.assertEqual(
            self.state(runtime={"installed": False, "staging": [".saipen.saipen-stage-1"]},
                       hook={"installed": False}),
            HG.STATE_INSTALLING,
        )
        self.assertEqual(self.state(runtime={"generation": None}), HG.STATE_BROKEN)
        self.assertEqual(self.state(hook={"status": "unknown"}), HG.STATE_BROKEN)
        self.assertEqual(
            self.state(hook={"status": "stale", "problems": ["hook-interpreter-missing:x"]}),
            HG.STATE_BROKEN,
        )
        self.assertEqual(
            self.state(runtime={"current": False, "diff": ["a"]}), HG.STATE_STALE_RUNTIME
        )
        self.assertEqual(self.state(hook={"status": "stale"}), HG.STATE_STALE_RUNTIME)
        self.assertEqual(self.state(instruction="absent"), HG.STATE_STALE_RUNTIME)
        self.assertEqual(
            self.state(authority={"generation_current": False}), HG.STATE_STALE_RUNTIME
        )
        self.assertEqual(self.state(health=None), HG.STATE_INSTALLED_UNVERIFIED)
        self.assertEqual(
            self.state(health={"state": "DEGRADED", "code": "AUTHORITY_UNREACHABLE"},
                       authority={"running": False}),
            HG.STATE_AUTHORITY_UNAVAILABLE,
        )
        self.assertEqual(
            self.state(health={"state": "DEGRADED", "code": "AUTHORITY_UNREACHABLE"}),
            HG.STATE_RECOVERING,
        )
        self.assertEqual(
            self.state(health={"state": "DEGRADED", "code": "ENGINE_UNREACHABLE"}),
            HG.STATE_DEGRADED_UNVERIFIED,
        )
        self.assertEqual(
            self.state(authority={"identity_supported": False}), HG.STATE_AUTHORITY_UNAVAILABLE
        )
        self.assertEqual(
            self.state(health={"state": "REFUSED", "code": "CAPABILITY_FORGED"}), HG.STATE_BROKEN
        )
        reached = {
            HG.STATE_HEALTHY_VERIFIED, HG.STATE_UNINSTALLED, HG.STATE_INSTALLING, HG.STATE_BROKEN,
            HG.STATE_STALE_RUNTIME, HG.STATE_INSTALLED_UNVERIFIED, HG.STATE_AUTHORITY_UNAVAILABLE,
            HG.STATE_RECOVERING, HG.STATE_DEGRADED_UNVERIFIED,
        }
        self.assertEqual(reached, set(HG.STATES), "every state of the model is reachable")

    def test_a_hook_that_exists_is_not_a_healthy_host(self):
        # Installed and current, never observed: not healthy, and not broken.
        state, reasons, action = HG.derive_state(facts(health=None))
        self.assertEqual(state, HG.STATE_INSTALLED_UNVERIFIED)
        self.assertIsNone(action)
        self.assertIn("no prompt has been observed", reasons[0])
        # Evidence older than the installed hook is evidence about another hook.
        stale = facts(health={"state": "ADMITTED", "at": time.time() - 5000},
                      hook={"installed_at": time.time()})
        self.assertEqual(HG.derive_state(stale)[0], HG.STATE_INSTALLED_UNVERIFIED)

    def test_a_health_record_of_another_hook_file_is_not_evidence_about_this_host(self):
        # T-1634, measured on the operator's machine: a fixture hook that ran
        # with the operator's profile replaced the health record, and a host
        # that was HEALTHY_VERIFIED a minute earlier read AUTHORITY_UNAVAILABLE.
        # The record names the hook file that wrote it; only the INSTALLED
        # hook's record is evidence about this installation.
        installed = str(Path.home() / ".claude" / "hooks" / "saipen-guard.py")
        fixture = str(Path(tempfile.gettempdir()) / "tmpx" / "home" / ".claude" / "hooks"
                      / "saipen-guard.py")
        foreign = {"state": "DEGRADED", "code": "AUTHORITY_CLIENT_UNPROVEN", "at": time.time(),
                   "hook": fixture}
        state, reasons, action = HG.derive_state(facts(health=foreign, hook={"path": installed}))
        self.assertEqual(state, HG.STATE_INSTALLED_UNVERIFIED)
        self.assertIsNone(action, "nothing is wrong with a host nobody has observed")
        self.assertIn("no prompt has been observed", reasons[0])
        # Not believed in the other direction either: no health from a stranger.
        admitted = {**foreign, "state": "ADMITTED", "code": None}
        self.assertEqual(
            self.state(health=admitted, hook={"path": installed}), HG.STATE_INSTALLED_UNVERIFIED
        )
        # A record that does not say which hook wrote it proves nothing.
        anonymous = {"state": "ADMITTED", "at": time.time(), "code": None}
        self.assertEqual(
            self.state(health=anonymous, hook={"path": installed}), HG.STATE_INSTALLED_UNVERIFIED
        )
        # The installed hook's own record is evidence, in any spelling of its path.
        spelled = installed.replace("\\", "/").upper() if WINDOWS else installed
        own = {"state": "ADMITTED", "at": time.time(), "code": None, "hook": spelled}
        self.assertEqual(
            self.state(health=own, hook={"path": installed}), HG.STATE_HEALTHY_VERIFIED
        )

    def test_a_marker_or_a_declaration_is_not_mechanical_admission(self):
        observed = facts(health=None)
        self.assertEqual(
            HG.effective_admission(observed, HG.STATE_INSTALLED_UNVERIFIED), "MECHANICAL_UNOBSERVED"
        )
        self.assertEqual(HG.effective_admission(facts(), HG.STATE_HEALTHY_VERIFIED), "MECHANICAL")
        degraded = facts(health={"state": "DEGRADED", "code": "ENGINE_UNREACHABLE"})
        self.assertEqual(
            HG.effective_admission(degraded, HG.STATE_DEGRADED_UNVERIFIED), "DEGRADED_UNVERIFIED"
        )
        strict = facts(authority={"mode": "strict"})
        self.assertEqual(
            HG.effective_admission(strict, HG.STATE_AUTHORITY_UNAVAILABLE), "BLOCKING_STRICT"
        )
        advisory = facts(
            contract={"mechanical_admission": False, "admission_enforcement": "ADVISORY"}
        )
        self.assertEqual(HG.derive_state(advisory)[0], HG.STATE_INSTALLED_UNVERIFIED)
        self.assertEqual(
            HG.effective_admission(advisory, HG.STATE_INSTALLED_UNVERIFIED), "ADVISORY"
        )
        stale_hook = facts(hook={"status": "stale"})
        self.assertEqual(HG.effective_response(stale_hook, HG.STATE_STALE_RUNTIME), "INACTIVE")


class CapabilityContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = HG.load_registry()
        self.matrix = HG.capability_matrix()

    def test_no_registered_host_has_an_undeclared_cell(self):
        self.assertEqual(sorted(self.matrix), sorted(a["id"] for a in self.registry["adapters"]))
        for host, contract in self.matrix.items():
            with self.subTest(host=host):
                self.assertEqual(HG.contract_gaps(contract), [])
                self.assertNotIn(HG.UNDECLARED, json.dumps(contract))
        declared = self.registry["capability_contract"]
        self.assertEqual(sorted(declared["cells"]), sorted(HG.CONTRACT_FIELDS))

    def test_no_host_claims_more_than_its_files_can_do(self):
        values = self.registry["capability_contract"]
        for adapter in self.registry["adapters"]:
            contract = self.matrix[adapter["id"]]
            with self.subTest(host=adapter["id"]):
                self.assertIn(contract["auto_recovery"], values["auto_recovery_values"])
                self.assertIn(contract["degraded_mode"], values["degraded_mode_values"])
                if contract["mechanical_admission"]:
                    self.assertTrue((ROOT / contract["host_authority_source"]).is_file())
                    self.assertTrue(contract["prompt_blocking"])
                    self.assertEqual(contract["auto_recovery"], HG.RECOVERY_AUTHORITY)
                # Policy applies at each physical interception boundary:
                # Claude prompts and the proven native OpenCode tool gate.
                self.assertEqual(
                    contract["prompt_blocking"]
                    or (
                        adapter["id"] == "opencode"
                        and contract["tool_interception"] == "BLOCKING"
                    ),
                    contract["degraded_mode"] == HG.DEGRADED_DEFAULT,
                )
                if contract["auto_recovery"] == HG.RECOVERY_AUTHORITY:
                    self.assertTrue((ROOT / adapter["admission_recovery"]).is_file())
                if contract["launch"]["executable"]:
                    self.assertIn(adapter["id"], host_launch.SUPPORTED_HOSTS)
                    self.assertTrue((ROOT / adapter["launch_implementation"]).is_file())
                if adapter.get("hook_artifact"):
                    self.assertTrue((ROOT / adapter["hook_artifact"]).is_file())

    def test_the_cross_host_asymmetry_is_a_recorded_capability_difference(self):
        # During the incident Claude was blocked while FreeBuff and ZAICODE
        # kept working. That was not enforcement drift: only one host has a
        # hook that CAN block a prompt, and the contract says so.
        blocking = sorted(host for host, item in self.matrix.items() if item["prompt_blocking"])
        self.assertEqual(blocking, ["claude"])
        for host in ("freebuff", "zaicode", "zcode-production", "codebuddy"):
            self.assertEqual(self.matrix[host]["prompt_interception"], "NONE")
            self.assertEqual(self.matrix[host]["admission_enforcement"], "ADVISORY")
            self.assertEqual(self.matrix[host]["degraded_mode"], HG.DEGRADED_NOT_APPLICABLE)
        # OpenCode shares gap policy; interception is still at the tool gate.
        self.assertEqual(self.matrix["opencode"]["degraded_mode"], HG.DEGRADED_DEFAULT)
        self.assertFalse(self.matrix["opencode"]["prompt_blocking"])
        self.assertEqual(self.matrix["codex"]["admission_enforcement"], "UNAVAILABLE")


class DoctorTests(Scratch):
    """Doctor and repair against a disposable profile: never the operator's."""

    def setUp(self) -> None:
        super().setUp()
        self.profile = self.tmp / "profile"
        self.profile.mkdir()
        patcher = mock.patch.dict(
            os.environ,
            {"USERPROFILE": str(self.profile), "HOME": str(self.profile), "HOMEDRIVE": "",
             "HOMEPATH": ""},
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def host(self, report: dict, host: str) -> dict:
        return next(item for item in report["hosts"] if item["id"] == host)

    def test_a_machine_with_no_host_is_a_clean_doctor_with_nothing_to_do(self):
        report = HG.doctor(home=self.profile)
        self.assertTrue(report["ok"], report["problems"])
        self.assertEqual(report["code"], "HOST_DOCTOR")
        self.assertEqual(report["policy"]["source"], "default")
        self.assertEqual(report["policy"]["label"], "DEGRADED_ALLOWED")
        self.assertFalse(report["authority"]["running"])
        self.assertEqual({item["state"] for item in report["hosts"]}, {HG.STATE_UNINSTALLED})
        self.assertIsNone(report["next_action"])
        text = HG.render(report)
        self.assertIn("nothing to do", text)
        self.assertIn("SAIPEN source  proven", text)
        self.assertNotIn("Traceback", text)

    def test_a_present_host_without_saipen_and_a_half_install_are_told_apart(self):
        (self.profile / ".claude").mkdir()
        report = HG.doctor(home=self.profile, only="claude")
        claude = self.host(report, "claude")
        self.assertEqual(claude["state"], HG.STATE_UNINSTALLED)
        self.assertEqual(claude["action"], TX.REPAIR)
        self.assertEqual(claude["admission"], "NONE")
        # The hook alone, with no runtime behind it: broken, not "installed".
        install_host_guard.install("claude", self.profile, ROOT, verify=False)
        claude = self.host(HG.doctor(home=self.profile, only="claude"), "claude")
        self.assertEqual(claude["state"], HG.STATE_BROKEN)
        self.assertIn("runtime it needs is missing", " ".join(claude["reasons"]))
        self.assertEqual(claude["response_enforcement"], "INACTIVE")
        self.assertIn("claude", HG.render(HG.doctor(home=self.profile)))

    def test_a_retired_hook_file_is_not_an_installation(self):
        # What an uninstall leaves under a live host is inert. Read as "a hook
        # is installed and its runtime is missing" it would be BROKEN, and
        # repair would reinstall the host the operator just removed.
        (self.profile / ".claude").mkdir()
        install_host_guard.install("claude", self.profile, ROOT, verify=False)
        install_host_guard.uninstall("claude", self.profile, ROOT, live_host=True)
        artifact = self.profile / ".claude" / "hooks" / "saipen-guard.py"
        self.assertTrue(install_host_guard.is_retired(artifact))
        claude = self.host(HG.doctor(home=self.profile, only="claude"), "claude")
        self.assertEqual(claude["state"], HG.STATE_UNINSTALLED)
        self.assertFalse(claude["installed"])
        self.assertEqual(claude["admission"], "NONE")

    def installed_copy(self, adapter: dict, installer_source: str | None = None) -> Path:
        """The installed runtime copy of one host, as far as a hook check reads
        it: the registry, the shipped hook, and the installer module."""
        runtime = HG._expand(adapter["install"]["skill"])
        for relative in ("extensions/adapters/registry.json", adapter["hook_artifact"]):
            (runtime / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, runtime / relative)
        (runtime / "tools").mkdir(exist_ok=True)
        module = runtime / "tools" / "install_host_guard.py"
        if installer_source is None:
            shutil.copyfile(TOOLS / "install_host_guard.py", module)
        else:
            module.write_text(installer_source, encoding="utf-8")
        return runtime

    def doctor_as_a_process(self, host: str) -> dict:
        """The doctor the way the operator runs it: its own interpreter, with
        nothing of this test process already imported."""
        proc = subprocess.run(
            [sys.executable, "-B", str(TOOLS / "saipen.py"), "host", "doctor", "--host", host,
             "--home", str(self.profile), "--json"],
            capture_output=True, stdin=subprocess.DEVNULL, cwd=str(self.tmp), check=False,
            timeout=300,
            env={key: value for key, value in os.environ.items() if not key.startswith("SAIPEN_")},
        )
        report = json.loads(proc.stdout.decode("utf-8"))
        return self.host(report, host)

    def test_the_doctor_judges_a_hook_with_its_own_installer_not_the_inspected_copy(self):
        # T-1634. The hook check imported `install_host_guard` from the runtime
        # UNDER INSPECTION: the code that decided "current" belonged to the
        # installation being judged, so a stale or damaged copy judged itself,
        # and a repair's own re-check ran the code it had just replaced.
        adapter = next(a for a in HG.load_registry(ROOT)["adapters"] if a["id"] == "codex")
        HG._expand(adapter["install"]["home"]).mkdir(parents=True)
        self.installed_copy(
            adapter, "raise RuntimeError('the runtime under inspection was executed')\n"
        )
        self.assertTrue(
            install_host_guard.install("codex", self.profile, ROOT, verify=False)["current"]
        )
        seen = self.doctor_as_a_process("codex")
        self.assertEqual(seen["hook"], "current", seen["facts"]["hook"])
        self.assertEqual(seen["facts"]["hook"]["problems"], [])

    def test_the_policy_command_shows_sets_and_clears_without_a_project(self):
        self.assertEqual(HG.mode(None, home=self.profile)["source"], "default")
        self.assertEqual(HG.mode("strict", home=self.profile)["mode"], "strict")
        self.assertEqual(HG.mode(None, home=self.profile)["label"], "STRICT")
        self.assertEqual(HG.mode("degraded_allowed", home=self.profile)["mode"], "degraded")
        self.assertEqual(HG.mode("default", home=self.profile)["source"], "default")
        self.assertFalse(HC.mode_path(self.profile).exists())
        self.assertFalse(HG.mode("loose", home=self.profile)["ok"])
        HC.mode_path(self.profile).parent.mkdir(parents=True, exist_ok=True)
        HC.mode_path(self.profile).write_text("{", encoding="utf-8")
        report = HG.doctor(home=self.profile)
        self.assertIn("POLICY_INVALID", [item["code"] for item in report["problems"]])
        self.assertEqual(report["policy"]["label"], "STRICT")

    def test_the_operator_commands_carry_a_declared_effect_class(self):
        # The three commands were in the registry and in the CLI and in no row
        # of the effect table, so the guard and the host adapters judged all of
        # them by the verb's default: a reinstall of every host and a write of
        # the admission policy read as DIAGNOSTIC -- a write nobody classified.
        from saipen_engine import command_effects as CE
        from saipen_engine.registry import load_registry

        declared = load_registry()["host_integration"]["commands"]
        self.assertEqual(declared, ["host doctor", "host repair", "host mode"])
        table = json.loads(
            (ROOT / "saipen" / "COMMAND_EFFECTS.json").read_text(encoding="utf-8-sig")
        )["verbs"]["host"]["subcommands"]
        for command in declared:
            self.assertIn(command.split()[1], table)
        self.assertEqual(CE.classify_invocation("host", ["doctor"]), CE.DIAGNOSTIC)
        self.assertEqual(
            CE.classify_invocation("host", ["doctor", "--host", "claude", "--json"]),
            CE.DIAGNOSTIC,
        )
        self.assertEqual(CE.classify_invocation("host", ["repair"]), CE.RECOVERY)
        # Showing the policy reads; every spelling that SETS it is a write, and
        # the table knows exactly the spellings the policy owner accepts.
        self.assertEqual(CE.classify_invocation("host", ["mode"]), CE.DIAGNOSTIC)
        self.assertEqual(set(table["mode"]["actions"]), {*TX.MODE_ALIASES, "default"})
        for spelling in (*TX.MODE_ALIASES, "default"):
            with self.subTest(spelling=spelling):
                self.assertEqual(CE.classify_invocation("host", ["mode", spelling]), CE.RECOVERY)
        # Neither is ordinary project work: a host whose integration is broken
        # must reach its own repair without a prepared fleet.
        for effect in (CE.DIAGNOSTIC, CE.RECOVERY):
            self.assertFalse(CE.fleet_preflight_required(effect))

    def test_repair_leaves_absent_hosts_alone_and_reports_what_it_did(self):
        with mock.patch.object(runtime_bootstrap, "_invoke_installer") as installer:
            report = HG.repair(home=self.profile)
        installer.assert_not_called()
        self.assertEqual(report["code"], "HOST_REPAIRED")
        self.assertEqual(report["steps"], [])
        self.assertTrue(report["ok"])
        # A present, uninstalled host is not silently installed either: repair
        # restores what was installed, it does not decide to install a host.
        (self.profile / ".claude").mkdir()
        with mock.patch.object(runtime_bootstrap, "_invoke_installer") as installer:
            report = HG.repair(home=self.profile, only="claude")
        installer.assert_not_called()
        self.assertEqual(report["remaining"], [])

    def test_repair_runs_the_one_canonical_installer_for_a_broken_host_only(self):
        (self.profile / ".claude").mkdir()
        (self.profile / ".codex").mkdir()
        install_host_guard.install("claude", self.profile, ROOT, verify=False)
        calls: list = []

        def installer(source, host, *, profile=None):
            self.assertEqual(profile, self.profile / ".claude")
            calls.append((Path(source), host))
            return subprocess.CompletedProcess(
                [], 1, stdout="Claude Code skill FAILED\n", stderr=""
            )

        with mock.patch.object(runtime_bootstrap, "_invoke_installer", side_effect=installer):
            report = HG.repair(home=self.profile)
        self.assertEqual(calls, [(ROOT.resolve(), "claude")])
        self.assertEqual(report["code"], "REPAIR_INCOMPLETE")
        self.assertFalse(report["ok"])
        step = report["steps"][0]
        self.assertEqual(
            (step["step"], step["code"]), ("install:claude", "BOOTSTRAP_INSTALL_FAILED")
        )
        self.assertEqual([item["id"] for item in report["remaining"]], ["claude"])
        self.assertIn("repair incomplete: claude BROKEN", HG.render(report))


# ------------------------------------------------------------------------ HOST


class HostConcurrencyTests(Scratch):
    """Several windows, several projects, one authority: no crossover."""

    def setUp(self) -> None:
        super().setUp()
        (self.tmp / "a").mkdir()
        (self.tmp / "b").mkdir()
        self.one = World(self.tmp / "a", mode="strict")
        self.two = World(self.tmp / "b", mode="strict")
        # One host home and one authority serve both projects, as on a real machine.
        self.host = HostFixture(
            self.tmp, home=self.one.home, project=self.one.project, authority=self.one.authority
        )
        self.addCleanup(self.host.close)
        if not self.host.available:
            self.skipTest("no stand-in host interpreter on this platform")

    def record(self, project: Path, session: str) -> dict:
        return json.loads(PA._ledger_path(project, session).read_text(encoding="utf-8"))

    def test_concurrent_first_prompts_in_two_projects_are_all_admitted_separately(self):
        jobs = [(self.one.project, f"window-{n}") for n in range(3)]
        jobs += [(self.two.project, f"window-{n}") for n in range(3)]
        answers: dict = {}
        errors: list = []

        def prompt(project: Path, session: str) -> None:
            try:
                answers[(str(project), session)] = self.host.run(
                    {"hook_event_name": "UserPromptSubmit", "user_prompt": "hi"},
                    session=session, cwd=project,
                )
            except Exception as exc:
                errors.append(repr(exc))

        threads = [threading.Thread(target=prompt, args=job) for job in jobs]
        for item in threads:
            item.start()
        for item in threads:
            item.join(240)
        self.assertEqual(errors, [])
        self.assertEqual(len(answers), len(jobs))
        capabilities = set()
        for (project, session), out in answers.items():
            self.assertNotIn("decision", out, (project, session, out))
            self.assertIn("=== BOOT.md sha256:", out["hookSpecificOutput"]["additionalContext"])
            record = self.record(Path(project), session)
            self.assertEqual(record["session"], session)
            capabilities.add(record["capability"])
        self.assertEqual(len(capabilities), len(jobs), "one capability per session, never shared")
        # A capability minted for one project and session verifies nowhere else.
        mine = self.record(self.one.project, "window-0")["capability"]
        base = {"host": "claude", "model": "", "provider": PA.provider_fingerprint()}
        own = HB.request(
            {"op": "verify", "project": str(self.one.project), "session": "window-0",
             "capability": mine, **base},
            runtime=self.host.runtime,
        )
        self.assertTrue(own["ok"], own)
        for project, session in ((self.two.project, "window-0"), (self.one.project, "window-1")):
            crossed = HB.request(
                {"op": "verify", "project": str(project), "session": session,
                 "capability": mine, **base},
                runtime=self.host.runtime,
            )
            self.assertFalse(crossed["ok"])
            self.assertEqual(crossed["code"], HB.CODE_BINDING_MISMATCH)

    def test_an_authority_restart_while_sessions_exist_readmits_each_once(self):
        self.host.prompt(session="window-0")
        before = self.record(self.one.project, "window-0")
        self.host.stop_broker()
        self.host.start_broker()
        again = self.host.prompt(session="window-0")
        self.assertNotIn("decision", again)
        self.assertIn("=== BOOT.md", again["hookSpecificOutput"]["additionalContext"])
        after = self.record(self.one.project, "window-0")
        self.assertNotEqual(after["capability"], before["capability"])
        self.assertNotEqual(after["provenance"]["kid"], before["provenance"]["kid"])
        settled = self.host.prompt(session="window-0")
        self.assertNotIn("=== BOOT.md", settled["hookSpecificOutput"]["additionalContext"])

    def test_the_identity_memo_is_bounded_and_notices_a_changed_hook(self):
        now = [1000.0]
        self.host.stop_broker()
        self.host.clock = lambda: now[0]
        self.host.config["identity_cache_seconds"] = 30
        self.host.start_broker()
        self.assertNotIn("decision", self.host.prompt(session="memo"))
        memo = dict(self.host.broker._identity_memo)
        self.assertTrue(memo, "identities are remembered between prompts")
        now[0] += 5
        self.host.prompt(session="memo")
        self.assertEqual(
            self.host.broker._identity_memo, memo, "and not re-derived within the window"
        )
        now[0] += 60
        self.host.prompt(session="memo")
        self.assertGreater(self.host.broker._identity_born, 1000.0, "the window is bounded")
        # A hook whose bytes are no longer the shipped ones is refused at once:
        # the artifact check reads the file, it is never served from the memo.
        self.host.hook_path().write_bytes(self.host.hook_path().read_bytes() + b"\n# edited\n")
        refused = self.host.prompt(session="memo-2")
        self.assertEqual(refused["decision"], "block")
        self.assertIn(HI.REASON_HOOK_ARTIFACT_MISMATCH, refused["reason"])


if __name__ == "__main__":
    unittest.main()
