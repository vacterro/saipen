"""A disposable HOST for admission tests (T-1624). Support module, no tests.

The separated authority admits one caller shape: the host application's own
hook invocation, proven from the operating system. A test that wants a
POSITIVE host case therefore has to put that shape on real processes; calling
the broker from the test interpreter is exactly the caller the boundary
refuses.

`HostFixture` builds the shape with nothing simulated on the proving side:

    stand-in host image          a copy of this interpreter named like the host
        +-- hook shell(s)        the platform shell, started with the hook command
              +-- hook           the INSTALLED hook artifact, real interpreter
                    +-- engine   the canonical CLI the hook starts

The pipe, the process identities, the command lines, the in-memory key and the
ledger are all real. Two things are test data and are stated as such: the
broker runs on an isolated endpoint, and its policy accepts the stand-in image
without a code signer -- the stand-in is signed by whoever built this
interpreter, which is precisely what the shipped policy rejects
(`test_t1624_host_integration` asserts that rejection separately).

`via` selects how the stand-in starts the hook:

    shell    through the platform shell with exactly the hook command (the host)
    direct   as a direct child, no shell (hosts that exec hooks themselves)
    tool     through a shell whose command WRAPS the hook command, the way a
             model's shell tool runs anything (must be refused)
    nested   the hook command re-run from inside such a tool shell (refused)
"""

from __future__ import annotations

import contextlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _entry in (str(TOOLS), str(ROOT), str(ROOT / "bootstrap")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from saipen_engine import host_authority_broker as HB  # noqa: E402
from saipen_engine import host_authority_identity as HI  # noqa: E402
from saipen_engine import host_authority_transport as HT  # noqa: E402

WINDOWS = os.name == "nt"
PYTHON_HOME = str(Path(sys.executable).resolve().parent)
HOST_NAME = "claude.exe" if WINDOWS else "claude"

#: Runs UNDER the stand-in host image. It starts the hook the way `via` says,
#: feeds it the event from its own stdin and relays the hook's answer.
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
    """A process image named like the host application, or None where impossible."""
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


def platform_shell() -> list[str] | None:
    """The shell a host would start a hook command with, as argv up to the command."""
    if WINDOWS:
        for candidate in (
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Git" / "bin" / "bash.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
            / "Git"
            / "bin"
            / "bash.exe",
        ):
            if candidate.is_file():
                return [str(candidate), "-c"]
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c"]
    return ["/bin/sh", "-c"]


class HostFixture:
    """One stand-in host, one isolated broker, one installed hook."""

    def __init__(
        self,
        tmp: Path,
        *,
        home: Path,
        project: Path,
        authority: Path | None = None,
        saipen_root: Path = ROOT,
        config: dict | None = None,
        clock=None,
        service: str = "thread",
    ) -> None:
        """`service` is where the broker lives: `thread` (in this process, the
        default), `process` (the shipped service entry as its own process on
        the fixture's explicit runtime root, with the fixture's policy file) or
        `none` (nothing is started; the caller decides)."""
        self.tmp = Path(tmp)
        self.home = Path(home)
        self.project = Path(project)
        self.authority = Path(authority) if authority is not None else None
        self.saipen_root = Path(saipen_root)
        self.runtime = self.tmp / "authority-runtime"
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.host = host_stand_in(self.tmp)
        self.driver = self.tmp / "host_driver.py"
        self.driver.write_text(DRIVER, encoding="utf-8")
        self.config = {
            **HB.settings(),
            # Test data, stated in the module docstring: the stand-in carries
            # this interpreter's publisher, not the host's.
            "host_signers": [],
            "identity_cache_seconds": 0,
            **(config or {}),
        }
        self.broker: HB.Broker | None = None
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None
        self.clock = clock
        self.process: subprocess.Popen | None = None
        #: False: the hook is started WITHOUT `--runtime`, so it meets the
        #: default per-user endpoint of whatever profile its environment names.
        self.explicit_endpoint = True
        #: True: the hook command is spelled the pre-bootstrap way.
        self.legacy_command = False
        if service == "thread":
            self.start_broker()
        elif service == "process":
            self.start_service_process()

    # ------------------------------------------------------------ broker

    def start_broker(self) -> None:
        self.stop = threading.Event()
        self.broker = HB.Broker(
            saipen_root=self.saipen_root,
            runtime=self.runtime,
            config=dict(self.config),
            clock=self.clock or HB._now,
        )
        self.thread = threading.Thread(
            target=HT.serve,
            kwargs={
                "name": HB.endpoint_name(self.runtime),
                "handler": self.broker.handle,
                "stop": self.stop,
            },
            daemon=True,
        )
        self.thread.start()
        deadline = time.time() + 15.0
        while time.time() < deadline:
            if HB.health(self.runtime, timeout=0.5):
                return
            time.sleep(0.05)
        raise AssertionError("the fixture broker never became reachable")

    def stop_broker(self) -> None:
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=5)
        deadline = time.time() + 5.0
        while time.time() < deadline and HB.health(self.runtime, timeout=0.2):
            time.sleep(0.05)

    def start_service_process(self) -> subprocess.Popen:
        """The shipped service entry, as its own process, on this fixture's
        explicit runtime root. An explicit root is the only place a policy file
        is read, and it is another endpoint than the operator's."""
        (self.runtime / HB.POLICY_OVERRIDE_NAME).write_text(
            json.dumps({"host_signers": [], "identity_cache_seconds": 0}), encoding="utf-8"
        )
        self.process = subprocess.Popen(
            [
                sys.executable,
                str(self.saipen_root / "tools" / "authority_service.py"),
                "serve",
                "--saipen-root",
                str(self.saipen_root),
                "--runtime",
                str(self.runtime),
                "--idle-seconds",
                "0",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 30.0
        while time.time() < deadline:
            if HB.health(self.runtime, timeout=0.5):
                return self.process
            if self.process.poll() is not None:
                break
            time.sleep(0.1)
        raise AssertionError("the fixture service process never became reachable")

    def stop_service_process(self, *, kill: bool = False) -> None:
        proc, self.process = self.process, None
        if proc is None:
            return
        if kill:
            proc.kill()
        else:
            with contextlib.suppress(Exception):
                HB.request({"op": "shutdown"}, runtime=self.runtime, timeout=2.0)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=15)
        deadline = time.time() + 5.0
        while time.time() < deadline and HB.health(self.runtime, timeout=0.2):
            time.sleep(0.05)

    def close(self) -> None:
        self.stop_service_process()
        self.stop_broker()

    # -------------------------------------------------------------- hook

    @property
    def available(self) -> bool:
        return self.host is not None

    def hook_path(self) -> Path:
        return self.home / ".claude" / "hooks" / "saipen-guard.py"

    def hook_argv(self, extra: list[str] | None = None) -> list[str]:
        # The installer's own spelling (`install_host_guard.hook_argv`): the
        # artifact behind the bootstrap. `legacy_command` is the plain script
        # form every installation made before the bootstrap still carries.
        head = (
            [sys.executable, str(self.hook_path())]
            if self.legacy_command
            else [sys.executable, "-c", HI.HOOK_BOOTSTRAP, str(self.hook_path())]
        )
        argv = [
            *head,
            "--host",
            "claude",
            "--saipen-root",
            str(self.saipen_root),
            "--home",
            str(self.home),
        ]
        if self.authority is not None:
            argv += ["--authority-root", str(self.authority)]
        if self.explicit_endpoint:
            argv += ["--runtime", str(self.runtime)]
        return argv + list(extra or [])

    def hook_command(self) -> str:
        """The hook command as ONE shell string, spelled the way the installer
        spells it for a host that runs hooks through a POSIX shell."""
        argv = [item.replace("\\", "/") if WINDOWS else item for item in self.hook_argv()]
        return shlex.join(argv)

    def _spawn_spec(self, via: str) -> list[str]:
        shell = platform_shell()
        if via == "direct":
            return self.hook_argv()
        if via == "shell":
            return [*shell, self.hook_command()]
        if via == "tool":
            # What a shell TOOL does to any command: its own bootstrap around it.
            return [*shell, "true && " + self.hook_command()]
        if via == "nested":
            inner = shlex.join([*[part.replace("\\", "/") for part in shell], self.hook_command()])
            return [*shell, "true && " + inner]
        raise ValueError(f"unknown via {via!r}")

    def run(
        self,
        event: dict,
        *,
        session: str = "session-1",
        via: str = "shell",
        cwd: Path | None = None,
        env: dict | None = None,
        timeout: int = 180,
    ) -> dict | None:
        """One hook event through the stand-in host. Returns the hook's JSON
        answer, or None when it printed nothing."""
        if self.host is None:
            raise AssertionError("no stand-in host interpreter on this platform")
        payload = {"session_id": session, "cwd": str(cwd or self.project), **event}
        child_env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SAIPEN_") and key != "PYTHONHOME"
        }
        child_env.update(env or {})
        spec = {
            "argv": self._spawn_spec(via),
            "cwd": str(cwd or self.project),
            "env": child_env,
            "timeout": timeout,
        }
        proc = subprocess.run(
            [str(self.host), str(self.driver), json.dumps(spec)],
            input=json.dumps(payload).encode("utf-8"),
            capture_output=True,
            check=False,
            timeout=timeout + 30,
            env={**os.environ, "PYTHONHOME": PYTHON_HOME},
        )
        out = proc.stdout.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0 and not out:
            raise AssertionError(
                f"hook run failed rc={proc.returncode}: "
                + proc.stderr.decode("utf-8", errors="replace")[-600:]
            )
        return json.loads(out) if out else None

    def prompt(self, **extra) -> dict | None:
        via = extra.pop("via", "shell")
        session = extra.pop("session", "session-1")
        return self.run(
            {"hook_event_name": "UserPromptSubmit", "user_prompt": "hi", **extra},
            session=session,
            via=via,
        )
