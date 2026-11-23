"""T-1966 AC-01: a genuine ZAICODE hook restarts an absent service and seals.

MEASURED defect (2026-10-30). The operator's authority service held no live
process: `broker.json` named pid 28988, which was gone, and the last
`broker.log` line was 05:09:59Z. In that window this project recorded five
consecutive genuine operator prompts as `witness: model_supplied` with no
`operator_origin`, and nothing appeared on the operator's surface to say so.
The same window shows another bound project sealing normally at 01:43Z, so the
transport works while the service is up; the defect is the gap, not the
sealing.

Two things are pinned here, and the second is what makes the first mean
something:

* the ZAICODE caller SHAPE is admitted under the shipped policy for that host
  (`hosts.zaicode` in the protocol registry: no signer requirement, and
  `max_shells: 0` because the host starts its hook itself with `shell: false`);
* a KILLED service is replaced by the next prompt, and that prompt is then
  sealed -- not merely "a process answered";
* a DIFFERENT shape (the same command reached through a shell the host did not
  start for it) is refused, so the positive case is not the broker answering
  yes to everything.

What this does NOT claim: a live ZAICODE `UserPromptSubmit` event. The stand-in
is a copy of this interpreter named `zaicode.exe`, started the way the host
starts a hook (argv, no shell), on a disposable per-user profile. That is the
same substitution `test_host_fixture` states for the Claude path, and the live
half stays T-1859 AC-01.
"""

from __future__ import annotations

import contextlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _entry in (str(TOOLS), str(ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from saipen_engine import host_authority_broker as HB  # noqa: E402
from saipen_engine import host_authority_identity as HI  # noqa: E402
from saipen_engine import operator_task  # noqa: E402

WINDOWS = os.name == "nt"
PYTHON_HOME = str(Path(sys.executable).resolve().parent)
HOST_NAME = "zaicode.exe" if WINDOWS else "zaicode"
HOOK = ROOT / "extensions" / "adapters" / "zaicode" / "saipen-guard.py"

#: Runs UNDER the stand-in host image: the host starts its hook directly, argv
#: with no shell, which is what the registry's `hook_surface_note` says ZAICODE
#: does (`shell: false`). It relays the hook's stdout unchanged.
DRIVER = r'''
import json, subprocess, sys
spec = json.loads(sys.argv[1])
event = sys.stdin.buffer.read()
proc = subprocess.run(spec["argv"], input=event, capture_output=True, cwd=spec["cwd"],
                      env=spec["env"], timeout=spec["timeout"])
sys.stdout.buffer.write(proc.stdout)
sys.stderr.buffer.write(proc.stderr)
sys.exit(proc.returncode)
'''


def host_stand_in(tmp: Path) -> Path | None:
    """A process image named like ZAICODE, or None where that is impossible."""
    target = Path(tmp) / "simhost"
    target.mkdir(parents=True, exist_ok=True)
    binary = target / HOST_NAME
    source = Path(sys.executable).resolve()
    try:
        shutil.copy2(source, binary)
        for pattern in ("python3*.dll", "python3*.zip", "vcruntime*.dll"):
            for item in source.parent.glob(pattern):
                with contextlib.suppress(OSError, shutil.SameFileError):
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


def platform_shell() -> list[str]:
    """The shell a host's own tool would wrap a command with, as argv."""
    if WINDOWS:
        for candidate in (
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Git" / "bin" / "bash.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
            / "Git" / "bin" / "bash.exe",
        ):
            if candidate.is_file():
                return [str(candidate), "-c"]
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c"]
    return ["/bin/sh", "-c"]


def isolate_profile(test: unittest.TestCase, tmp: Path) -> Path:
    """Move the per-user runtime root somewhere disposable.

    The hook's own command line has no `--runtime` (the shipped ZAICODE
    registration carries only `--host`, `--saipen-root` and `--home`), so the
    endpoint it meets is whatever `Path.home()` names. A test that wants the
    DEFAULT endpoint must therefore move the profile, not pass a flag the
    artifact would ignore.
    """
    profile = tmp / "userprofile"
    profile.mkdir(parents=True, exist_ok=True)
    patcher = mock.patch.dict(
        os.environ,
        {
            "USERPROFILE": str(profile),
            "HOME": str(profile),
            "HOMEDRIVE": "",
            "HOMEPATH": "",
        },
    )
    patcher.start()
    test.addCleanup(patcher.stop)
    return profile


class TheZaicodSurface(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.host = host_stand_in(self.tmp)
        if self.host is None:
            self.skipTest("no stand-in host interpreter on this platform")
        self.driver = self.tmp / "host_driver.py"
        self.driver.write_text(DRIVER, encoding="utf-8")
        # The project the operator's prompt names, and a home whose registry
        # declares where this host's hook lives.
        self.profile = isolate_profile(self, self.tmp)
        self.runtime = self.profile / ".saipen" / "authority"
        self.home = self.tmp / "home"
        (self.home / ".zcode" / "hooks").mkdir(parents=True, exist_ok=True)
        self.installed_hook = self.home / ".zcode" / "hooks" / "saipen-guard.py"
        shutil.copy2(HOOK, self.installed_hook)
        self.project = self.tmp / "project"
        (self.project / ".saipen").mkdir(parents=True, exist_ok=True)
        # The broker's own project scope reads a lineage from this carrier and
        # fails closed without one: a project lacking it is a project it cannot
        # bind an operator event to at all.
        (self.project / ".saipen" / "IDENTITY.md").write_text(
            "---\nproject_lineage: lineage-0123456789abcdef0123456789abcdef\n---\n",
            encoding="utf-8",
        )
        # `converge_target` is required beside `execution_intent: converge`;
        # without it the engine's own parser answers CORRUPT and the broker has
        # no task scope to bind the event to.
        (self.project / ".saipen" / "STATE.md").write_text(
            "---\nphase: SCOUT\nagent: fixture\ntask: none\n"
            "next_action: PHASE SCOUT T-1\nblocker: none\ntransition_from: PLAN\n"
            "saipen_version: 8\nmode: full\nupdated: 2026-10-30T00:00:00Z\n"
            "execution_intent: converge\nconverge_target: done\n---\n",
            encoding="utf-8",
        )

    # ------------------------------------------------------------ helpers

    def hook_argv(self) -> list[str]:
        """The shipped registration's spelling. No `--runtime`: the artifact
        does not read one, and a test that passed it would be measuring its own
        flag rather than the endpoint the host's hook actually meets."""
        return [
            sys.executable, "-c", HI.HOOK_BOOTSTRAP, str(self.installed_hook),
            "--host", "zaicode",
            "--saipen-root", str(ROOT),
            "--home", str(self.home),
        ]

    def run_hook(self, *, via: str = "host", session: str = "sess-t1966") -> dict:
        """One `UserPromptSubmit` for this project, started `via`.

        `host` is the shape that matters: the stand-in starts the hook itself,
        argv with no shell -- exactly the registry's `shell: false`. `wrapped`
        is the control: a shell around it, which the host never does for its
        own hook.
        """
        argv = self.hook_argv()
        if via == "host":
            spec_argv = argv
        elif via == "wrapped":
            # A POSIX shell needs the argv as one shell string with the paths
            # in their forward-slash spelling; `list2cmdline` is cmd.exe's
            # grammar and would strip every backslash on the way through.
            spelled = [item.replace("\\", "/") if WINDOWS else item for item in argv]
            spec_argv = [*platform_shell(), "true && " + shlex.join(spelled)]
        else:
            raise ValueError(f"unknown via {via!r}")
        # `turnId` as the host sends it: the broker refuses an event with no
        # bounded identity, and an id-less delivery is exactly that. Measured
        # on this project: every genuine prompt carries one.
        payload = {
            "session_id": session,
            "cwd": str(self.project),
            "hook_event_name": "UserPromptSubmit",
            "prompt": "cc",
            "turnId": f"turn-{session}",
        }
        child_env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SAIPEN_") and key != "PYTHONHOME"
        }
        spec = {
            "argv": spec_argv,
            "cwd": str(self.project),
            "env": child_env,
            "timeout": 120,
        }
        proc = subprocess.run(
            [str(self.host), str(self.driver), json.dumps(spec)],
            input=json.dumps(payload).encode("utf-8"),
            capture_output=True,
            check=False,
            timeout=180,
            env={**os.environ, "PYTHONHOME": PYTHON_HOME},
        )
        out = proc.stdout.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0 and not out:
            raise AssertionError(
                f"hook run failed rc={proc.returncode}: "
                + proc.stderr.decode("utf-8", errors="replace")[-800:]
            )
        return json.loads(out) if out else {}

    def envelopes(self) -> list[dict]:
        directory = operator_task.ingress_cache_dir(self.project)
        rows = []
        for path in sorted(Path(directory).glob("*.json")):
            with contextlib.suppress(OSError, ValueError):
                rows.append(json.loads(path.read_text(encoding="utf-8")))
        return rows

    def start_service(self) -> dict:
        """Bring the endpoint up the way an earlier prompt would have, so the
        case below can KILL a real service rather than start from nothing."""
        from saipen_engine import host_authority_client as HC

        HC.ensure(ROOT, runtime=self.runtime, force=True, wait=20.0)
        self.assertTrue(HB.health(self.runtime), "the fixture service did not come up")
        return HB.read_status(self.runtime) or {}

    def stop_service(self) -> None:
        stored = HB.read_status(self.runtime) or {}
        pid = stored.get("pid")
        with contextlib.suppress(Exception):
            HB.request({"op": "shutdown"}, runtime=self.runtime, timeout=2.0)
        deadline = time.time() + 12.0
        while time.time() < deadline and HB.health(self.runtime, timeout=0.3):
            time.sleep(0.2)
        if isinstance(pid, int) and HB._pid_alive(pid):
            with contextlib.suppress(OSError, TypeError, ValueError):
                os.kill(pid, 9)

    # -------------------------------------------------------------- cases

    def test_the_shipped_zaicode_policy_requires_no_signer_and_no_shell(self):
        """The positive case below is only meaningful under the real policy."""
        settings = HB.settings(host="zaicode")
        self.assertEqual(settings.get("host_signers"), [])
        self.assertEqual(settings.get("max_shells"), 0)
        self.assertEqual(settings.get("host_images"), ["zaicode.exe"])

    def test_a_killed_service_is_replaced_by_the_next_prompt_which_seals(self):
        """AC-01: kill the service, then drive the hook.

        This is the measured defect's own shape: the service died at
        2026-10-30T05:09:59Z and every prompt after it was admitted unsealed.
        The criterion asks for the restart AND the seal, because a process that
        answers again proves nothing about the operator's authority having
        reached the project.
        """
        self.addCleanup(self.stop_service)
        before = self.start_service()
        self.assertTrue(before.get("pid"), before)
        # Kill it outright: a graceful shutdown would leave a record the next
        # hook could still read as a live service, and that is the other bug.
        self.stop_service()
        self.assertFalse(HB.health(self.runtime), "the fixture service survived the kill")

        reply = self.run_hook()
        self.assertTrue(HB.health(self.runtime), "the hook did not restart the service")
        started = HB.read_status(self.runtime) or {}
        self.assertTrue(started.get("pid"), started)
        self.assertNotEqual(started.get("pid"), before.get("pid"), "the SAME process answered")
        # The point of the case: not "a process answered" but "the operator's
        # prompt carries a broker-sealed origin".
        self.assertTrue(reply.get("sealed"), reply)
        self.assertTrue(reply.get("authenticated"), reply)
        self.assertEqual((reply.get("seal") or {}).get("stage"), "sealed", reply)
        sealed = [row for row in self.envelopes() if isinstance(row.get("operator_origin"), dict)]
        self.assertTrue(sealed, "no envelope carries an operator origin")
        self.assertEqual(sealed[-1].get("witness"), operator_task.WITNESS_CARRIER)
        origin = sealed[-1]["operator_origin"]
        self.assertEqual(origin.get("kind"), "operator-origin")
        self.assertEqual(origin.get("action"), "continue")

    def test_the_hook_reached_through_a_shell_is_not_the_host_invocation(self):
        """Control: the same command through a shell the host did not start.

        Without this, the positive case could be the broker admitting anything
        that mentions the hook path.
        """
        self.addCleanup(self.stop_service)
        reply = self.run_hook(via="wrapped", session="sess-wrapped")
        self.assertFalse(reply.get("sealed"), reply)
        notice = str(reply.get("systemMessage") or "")
        self.assertIn("NOT authenticated", notice, reply)
        sealed = [row for row in self.envelopes() if isinstance(row.get("operator_origin"), dict)]
        self.assertFalse(sealed, "a wrapped call sealed an operator origin")


if __name__ == "__main__":
    unittest.main()
