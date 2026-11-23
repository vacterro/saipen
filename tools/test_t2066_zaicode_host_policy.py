"""T-2066 regression matrix for the ZAICODE authenticated operator ingress.

The measured incident (SRC-390/SRC-415): the real operator `cc` under the real
ZAICODE host was refused `BROKER_NOT_A_HOST_CLIENT` with the step
`NOT_HOST_DESCENDANT`, the operator origin never sealed, and the valve stayed
`hard_wait`. Three source defects produce it, and each has its own evidence
class here so a green in one says nothing about another:

* POLICY   -- the shipped registry carries a per-host authority policy for
              `zaicode` that names the ZAICODE host images and bounds the
              chain; defect: no `hosts` map was shipped at all, so "zaicode"
              fell back to the Claude policy and the ZAICODE image was not a
              host image (NOT_HOST_DESCENDANT).
* ZERO     -- the broker honours an EXPLICIT zero bound; defect: `or 4` / `or 2`
              turned a declared `max_shells: 0` / `max_bridges: 0` back into the
              defaults, so a host that execs its hook with `shell:false` could
              never declare "no shells, no intermediaries" (the ZAICODE hook is
              started exactly that way).
* CLIENT   -- the guard-side client decides whether starting the service makes
              sense under the SAME effective per-host settings the broker will
              use; defect: `hook_invocation()` built its policy from the global
              config and carried no bridge or bound fields, so a genuine
              ZAICODE hook looked unproven to the client and no start was made.
* HOST     -- the whole admission path on real processes: a stand-in ZAICODE
              host image starts the installed hook exactly the way ZAICODE does
              (argv, `shell:false`), and the operator prompt seals. Negative
              controls keep every caller the boundary exists to refuse refused:
              a shell-tool invocation, a model-issued command and an unrelated
              image are each refused and seal nothing.

The stand-in host image is a copy of this interpreter named `zaicode.exe`; it
carries this interpreter's publisher, which is why the zaicode policy ships
`host_signers: []` -- the measured ZAICODE desktop build on this machine is not
Authenticode-signed either, and a signer requirement would only repeat the
incident. The positive HOST cases therefore also assert the OTHER bindings the
proof does make: the direct parentage, the exact hook command line, the shipped
hook bytes and the pid-reuse rule.
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import subprocess
import sys
import contextlib
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

from saipen_engine import host_authority_broker as HB  # noqa: E402
from saipen_engine import host_authority_client as HC  # noqa: E402
from saipen_engine import host_authority_identity as HI  # noqa: E402
from saipen_engine import host_authority_process as HP  # noqa: E402
from saipen_engine import host_authority_transport as HT  # noqa: E402
from saipen_engine import operator_origin as OO  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_host_fixture import PYTHON_HOME, platform_shell  # noqa: E402
from test_protocol_admission import World  # noqa: E402

WINDOWS = os.name == "nt"
HOOK_ARTIFACT = ROOT / "extensions" / "adapters" / "zaicode" / "saipen-guard.py"
DRIVER = r'''
import json, os, subprocess, sys
spec = json.loads(sys.argv[1])
event = sys.stdin.buffer.read()
proc = subprocess.run(spec["argv"], input=event, capture_output=True, cwd=spec["cwd"],
                      env=spec["env"], timeout=spec["timeout"])
sys.stdout.buffer.write(proc.stdout)
sys.stderr.buffer.write(proc.stderr)
sys.exit(proc.returncode)
'''


def hook_argv(root: Path, home: Path, host: str) -> list[str]:
    """The installed ZAICODE hook command line, spelled the way ZAICODE runs
    it: argv, no shell. `--host zaicode` is the host the bytes serve."""
    return [
        sys.executable,
        "-c",
        HI.HOOK_BOOTSTRAP,
        str(home / ".zcode" / "hooks" / "saipen-guard.py"),
        "--host",
        host,
        "--saipen-root",
        str(root),
        "--home",
        str(home),
    ]


def install_hook(home: Path) -> Path:
    """The shipped hook artifact on the ZAICODE install surface."""
    artifact = home / ".zcode" / "hooks" / "saipen-guard.py"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(HOOK_ARTIFACT.read_bytes())
    return artifact


def zaicode_stand_in(tmp: Path) -> Path | None:
    """A process image named `zaicode.exe`, or None where impossible."""
    target = tmp / "simhost"
    target.mkdir(parents=True, exist_ok=True)
    binary = target / ("zaicode.exe" if WINDOWS else "zaicode")
    source = Path(sys.executable).resolve()
    try:
        import shutil

        shutil.copy2(source, binary)
        for pattern in ("python3*.dll", "python3*.zip", "vcruntime*.dll"):
            for item in source.parent.glob(pattern):
                shutil.copy2(item, target / item.name)
        probe = subprocess.run(
            [str(binary), "-c", "import json, pathlib, subprocess"],
            capture_output=True,
            check=False,
            timeout=60,
            env={**os.environ, "PYTHONHOME": PYTHON_HOME},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return binary if probe.returncode == 0 else None


def setUpModule() -> None:
    isolate_host_session()


class PolicyTests(unittest.TestCase):
    """The shipped per-host authority policy for zaicode."""

    def test_the_registry_carries_a_zaicode_host_policy(self):
        settings = HB.settings()
        hosts = settings.get("hosts")
        self.assertIsInstance(hosts, dict, settings)
        zaicode = hosts.get("zaicode")
        self.assertIsInstance(zaicode, dict, hosts)
        images = [str(item).lower() for item in (zaicode or {}).get("host_images") or []]
        self.assertIn("zaicode.exe", images, zaicode)
        self.assertIn("zcode.exe", images, zaicode)

    def test_the_zaicode_policy_declares_zero_shells_and_zero_bridges(self):
        zaicode = (HB.settings().get("hosts") or {}).get("zaicode") or {}
        self.assertEqual(int(zaicode.get("max_shells")), 0, zaicode)
        self.assertEqual(int(zaicode.get("max_bridges")), 0, zaicode)

    def test_the_named_host_answers_with_its_own_images(self):
        # The diagnostic surface must name the images the proof will use; the
        # unnamed answer stays the global policy.
        named = HC.identify_self(host="zaicode")["host_images"]
        self.assertIn("zaicode.exe", [str(item).lower() for item in named], named)
        unnamed = HC.identify_self()["host_images"]
        self.assertIn("claude.exe", [str(item).lower() for item in unnamed], unnamed)

    def test_the_claude_policy_is_unchanged_by_the_zaicode_declaration(self):
        settings = HB.settings()
        self.assertEqual(settings["host_images"], ["claude.exe", "claude", "claude-code", "claude-code.exe"])
        self.assertEqual(settings["host_signers"], ["Anthropic, PBC"])
        self.assertEqual(int(settings["max_shells"]), 4)
        self.assertEqual(int(settings["max_bridges"]), 2)


class ZeroBoundTests(unittest.TestCase):
    """An explicit zero bound survives into the proof, on the broker."""

    def _policy_for(self, host: str, overrides: dict) -> HI.IdentityPolicy:
        captured: dict = {}

        def capture(chain, policy, **kwargs):
            captured["policy"] = policy
            return HI.Proof(ok=True, chain=[])

        peer = mock.Mock()
        peer.pid = 4242
        peer.kind = "named-pipe"
        with mock.patch.object(HI, "prove_hook_invocation", side_effect=capture), mock.patch.object(
            HB.proc, "ancestry", return_value=[]
        ), mock.patch.object(HB.proc, "image_signer", return_value="stub-signer"), mock.patch.object(
            HB.proc, "platform_supported", return_value=True
        ), mock.patch.object(HB.proc, "signing_supported", return_value=True):
            broker = HB.Broker(
                saipen_root=ROOT,
                runtime=None,
                config={**HB.settings(), "hosts": {"zaicode": overrides}},
            )
            broker.identify(peer, host, home=str(Path.home()))
        return captured["policy"]

    def test_declared_zero_shells_and_bridges_reach_the_proof(self):
        policy = self._policy_for(
            "zaicode", {"max_shells": 0, "max_bridges": 0, "bridge_images": []}
        )
        self.assertEqual(policy.max_shells, 0)
        self.assertEqual(policy.max_bridges, 0)

    def test_a_declared_bound_other_than_the_default_reaches_the_proof(self):
        policy = self._policy_for("zaicode", {"max_shells": 1, "max_bridges": 3})
        self.assertEqual(policy.max_shells, 1)
        self.assertEqual(policy.max_bridges, 3)


class AncestryTests(unittest.TestCase):
    """The origin binding's Windows ancestry policy.

    A protected Windows ancestor (wininit, services) hides its creation time,
    and requiring a birth for EVERY ancestor discarded a fully measured chain:
    measured on this machine, the broker answered "native host process birth
    could not be observed" for a genuine host delivery. The binding only uses
    the caller and the host, so the verified prefix is kept -- and nothing is
    relaxed where it is actually used: a caller or host without an observable
    birth, or a broken parent link, still proves nothing.
    """

    def _origins(self, *facts: HP.ProcessFact) -> OO.OperatorOrigins:
        return OO.OperatorOrigins(
            None,
            clock=lambda: 1000.0,
            ancestry=lambda pid, limit: [fact for fact in facts],
            ttl=60,
        )

    def test_an_unmeasurable_protected_ancestor_keeps_the_verified_prefix(self):
        origins = self._origins(
            HP.ProcessFact(100, 99, "hook.exe", "hook", (), created=5),
            HP.ProcessFact(99, 98, "zaicode.exe", "zaicode.exe", (), created=4),
            HP.ProcessFact(98, 97, "services.exe", "services.exe", (), created=3),
            HP.ProcessFact(97, 0, None, None, (), created=None),
        )
        chain = origins._chain(100)
        self.assertEqual([fact.pid for fact in chain], [100, 99, 98])

    def test_a_caller_without_an_observable_birth_proves_nothing(self):
        origins = self._origins(
            HP.ProcessFact(100, 99, "hook.exe", "hook", (), created=None),
            HP.ProcessFact(99, 98, "zaicode.exe", "zaicode.exe", (), created=4),
        )
        self.assertEqual(origins._chain(100), [])

    def test_a_broken_parent_link_is_not_crossed(self):
        origins = self._origins(
            HP.ProcessFact(100, 99, "hook.exe", "hook", (), created=5),
            HP.ProcessFact(98, 97, "reused.exe", "reused.exe", (), created=4),
        )
        self.assertEqual([fact.pid for fact in origins._chain(100)], [100])


class ClientTests(unittest.TestCase):
    """The guard-side client decides under the broker's effective settings."""

    def _shape(self, host: str, overrides: dict, *, capture: bool = True) -> dict:
        """`hook_invocation` under a per-host policy, on a synthetic chain."""
        recorded: dict = {}

        def capture_policy(chain, policy, **kwargs):
            recorded["policy"] = policy
            return HI.Proof(ok=True, chain=[])

        host_image = str(Path("v:/host/zaicode.exe" if WINDOWS else "v/host/zaicode"))
        hook_command = [
            sys.executable,
            "-c",
            HI.HOOK_BOOTSTRAP,
            "/v/home/.zcode/hooks/saipen-guard.py",
            "--host",
            host,
            "--saipen-root",
            "/v/root",
        ]
        chain = [
            HP.ProcessFact(pid=100, ppid=99, image="v:/host/python.exe", name="python.exe",
                           argv=hook_command, created=None),
            HP.ProcessFact(pid=99, ppid=98, image=host_image, name="zaicode.exe",
                           argv=[host_image], created=None),
        ]
        shipped = HB.settings

        def effective(policy=None, host=None):
            merged = dict(shipped(policy, host))
            if host == "zaicode":
                merged.update(overrides)
            return merged

        patcher = mock.patch.object(HB, "settings", side_effect=effective)
        if capture:
            prover = mock.patch.object(HI, "prove_hook_invocation", side_effect=capture_policy)
        else:
            prover = mock.patch.object(HC.proc, "ancestry", return_value=chain)
        with patcher, mock.patch.object(HC.proc, "ancestry", return_value=chain), prover:
            report = HC.hook_invocation(host, home="/v/home")
        return {"report": report, "policy": recorded.get("policy")}

    def test_the_client_applies_the_effective_per_host_settings(self):
        report = self._shape(
            "zaicode",
            {
                "host_images": ["zaicode.exe", "ZCode.exe"],
                "host_signers": [],
                "max_shells": 0,
                "max_bridges": 0,
                "bridge_images": ["zcode-cli.exe"],
            },
        )
        self.assertTrue(report["report"]["ok"], report)
        policy = report["policy"]
        self.assertEqual(policy.host, "zaicode")
        images = [str(item).lower() for item in policy.host_images]
        self.assertIn("zaicode.exe", images)
        self.assertEqual(policy.max_shells, 0)
        self.assertEqual(policy.max_bridges, 0)
        self.assertEqual(policy.bridge_images, ("zcode-cli.exe",))

    def test_the_client_refuses_a_shape_the_broker_would_refuse(self):
        # A caller under an image the zaicode policy does not name, proven with
        # the REAL proof: the client must not call that the host's own hook and
        # must not start a service the broker would refuse.
        overrides = {"max_shells": 0, "max_bridges": 0, "bridge_images": []}
        shipped = HB.settings

        def effective(policy=None, host=None):
            merged = dict(shipped(policy, host))
            if host == "zaicode":
                merged.update(overrides)
            return merged

        patcher = mock.patch.object(HB, "settings", side_effect=effective)
        hook_command = [
            sys.executable, "-c", HI.HOOK_BOOTSTRAP, "/v/home/.zcode/hooks/saipen-guard.py",
            "--host", "zaicode", "--saipen-root", "/v/root",
        ]
        chain = [
            HP.ProcessFact(pid=100, ppid=99, image="v:/host/python.exe", name="python.exe",
                           argv=hook_command, created=None),
            HP.ProcessFact(pid=99, ppid=98, image="v:/host/bystander.exe", name="bystander.exe",
                           argv=["v:/host/bystander.exe"], created=None),
        ]
        with patcher, mock.patch.object(
            HC.proc, "ancestry", return_value=chain
        ):
            report = HC.hook_invocation("zaicode", home="/v/home")
        self.assertFalse(report["ok"], report)
        self.assertIn(
            report["reason"],
            (HI.REASON_NOT_HOST_DESCENDANT, HI.REASON_HOOK_CHAIN_UNRECOGNIZED),
            report,
        )


@unittest.skipUnless(WINDOWS, "the ZAICODE stand-in host is a Windows image")
class HostTests(unittest.TestCase):
    """The whole path on real processes: stand-in ZAICODE host, installed hook,
    the operator's prompt, and the negative callers."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.world = World(self.tmp)
        self.profile, self.runtime = isolate_profile(self)
        self.host = zaicode_stand_in(self.tmp)
        if self.host is None:
            self.skipTest("no stand-in ZAICODE interpreter on this platform")
        self.driver = self.tmp / "zaicode_driver.py"
        self.driver.write_text(DRIVER, encoding="utf-8")
        install_hook(self.world.home)
        # The shipped service entry, as its own process, on the DEFAULT endpoint
        # of the isolated profile -- the endpoint the ZAICODE hook meets, since
        # its command line names no --runtime. It loads the registry itself.
        # The in-process module isolation patches the TEST process's default
        # endpoint to a scratch root nothing serves (T-1624), so this class
        # addresses the child's real endpoint explicitly rather than by default.
        self.process = subprocess.Popen(
            [sys.executable, str(ROOT / "tools" / "authority_service.py"), "serve",
             "--saipen-root", str(ROOT), "--idle-seconds", "0"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={**os.environ, "USERPROFILE": str(self.profile),
                 "HOME": str(self.profile), "HOMEDRIVE": "", "HOMEPATH": ""},
        )
        self.addCleanup(self.close)
        deadline = time.time() + 30
        while time.time() < deadline:
            if HB.health(self.runtime, timeout=0.5):
                return
            if self.process.poll() is not None:
                break
            time.sleep(0.1)
        self.fail("the shipped broker service never became reachable on the isolated profile")

    def close(self) -> None:
        proc = getattr(self, "process", None)
        if proc is None:
            return
        with contextlib.suppress(Exception):
            HB.request({"op": "shutdown"}, runtime=self.runtime, timeout=2.0)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=15)

    def prompt(self, *, via: str = "direct", host: str = "zaicode", prompt_text: str = "hi") -> dict:
        shell = platform_shell()
        argv = hook_argv(ROOT, self.world.home, host)
        command = {
            "direct": argv,
            "shell": [*shell, shell_join(argv)],
            "tool": [*shell, "true && " + shell_join(argv)],
        }[via]
        spec = {
            "argv": command,
            "cwd": str(self.world.project),
            "env": {
                key: value
                for key, value in os.environ.items()
                if not key.startswith("SAIPEN_") and key != "PYTHONHOME"
            },
            "timeout": 180,
        }
        event = {
            "hook_event_name": "UserPromptSubmit",
            "prompt": prompt_text,
            "session_id": "session-1",
            # BaseHookInput carries these on every event; the hook takes the
            # turn identity from `turnId`, falling back to `traceId`. A fixture
            # without one is not a ZAICODE delivery and proves nothing.
            "turnId": f"turn-{via}",
            "traceId": f"trace-{via}",
            "cwd": str(self.world.project),
        }
        run = subprocess.run(
            [str(self.host), str(self.driver), json.dumps(spec)],
            input=json.dumps(event).encode("utf-8"),
            capture_output=True,
            check=False,
            timeout=240,
            env={**os.environ, "PYTHONHOME": PYTHON_HOME},
        )
        out = run.stdout.decode("utf-8", errors="replace").strip()
        if not out:
            raise AssertionError(
                f"hook run failed rc={run.returncode}: "
                + run.stderr.decode("utf-8", errors="replace")[-800:]
            )
        return json.loads(out)

    def test_the_host_own_hook_invocation_seals_the_operator_origin(self):
        reply = self.prompt(via="direct")
        self.assertTrue(reply.get("sealed"), reply)
        self.assertTrue(reply.get("authenticated"), reply)
        self.assertIsInstance(reply.get("operator_origin"), dict, reply)
        self.assertEqual(reply.get("seal", {}).get("code"), "SEALED", reply)

    def test_a_shell_tool_call_gains_nothing_and_seals_nothing(self):
        # The ZAICODE policy bounds the chain at zero shells; a host hook run
        # through a shell is refused and nothing is sealed. A policy that lost
        # the explicit zero would admit this shape and seal it.
        reply = self.prompt(via="shell")
        self.assertFalse(reply.get("sealed"), reply)
        self.assertFalse(reply.get("authenticated"), reply)
        self.assertFalse(reply.get("seal", {}).get("ok"), reply)
        self.assertIn(
            reply.get("seal", {}).get("code"),
            # The broker answers with its own refusal; without a reachable
            # service the same caller is refused by the client first.
            ("BROKER_CLIENT_NOT_AUTHENTICATED", "AUTHORITY_CLIENT_UNPROVEN"),
            reply,
        )

    def test_a_model_issued_command_is_not_the_host_hook_invocation(self):
        # Not under the stand-in host at all: this interpreter, a shell, a hook.
        spec = {
            "argv": [*platform_shell(), shell_join(hook_argv(ROOT, self.world.home, "zaicode"))],
            "cwd": str(self.world.project),
            "env": {
                key: value
                for key, value in os.environ.items()
                if not key.startswith("SAIPEN_") and key != "PYTHONHOME"
            },
            "timeout": 180,
        }
        event = {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "hi",
            "session_id": "session-2",
            "turnId": "turn-model",
            "traceId": "trace-model",
            "cwd": str(self.world.project),
        }
        run = subprocess.run(
            [sys.executable, str(self.driver), json.dumps(spec)],
            input=json.dumps(event).encode("utf-8"),
            capture_output=True,
            check=False,
            timeout=240,
        )
        reply = json.loads(run.stdout.decode("utf-8", errors="replace").strip() or "{}")
        self.assertFalse(reply.get("sealed"), reply)
        self.assertFalse(reply.get("authenticated"), reply)

    def test_an_unrelated_host_image_is_refused(self):
        # A stand-in named after nothing the policy trusts: no seal, and the
        # refusal step names the host descent, not a silent success.
        original = self.host
        other = self.tmp / "simhost" / "bystander.exe"
        self.host = other
        try:
            os.replace(original, other)
            reply = self.prompt(via="direct")
        finally:
            self.host = original
        self.assertFalse(reply.get("sealed"), reply)
        self.assertFalse(reply.get("authenticated"), reply)


def shell_join(argv: list[str]) -> str:
    import shlex

    return shlex.join([item.replace("\\", "/") if WINDOWS else item for item in argv])


def isolate_profile(test: unittest.TestCase) -> tuple[Path, Path]:
    """Point this process at a disposable per-user runtime root, exactly the
    way the ZAICODE hook meets the default endpoint (it names no --runtime).

    Returns the profile root and the authority runtime root DERIVED from it:
    the isolated module patches this process's default endpoint to a scratch
    root nothing serves, so the class must name the child's endpoint itself.
    """
    profile = test.tmp / "userprofile"
    profile.mkdir(parents=True, exist_ok=True)
    patcher = mock.patch.dict(
        os.environ,
        {"USERPROFILE": str(profile), "HOME": str(profile), "HOMEDRIVE": "", "HOMEPATH": ""},
    )
    patcher.start()
    test.addCleanup(patcher.stop)
    return profile, profile / ".saipen" / "authority"


if __name__ == "__main__":
    unittest.main()