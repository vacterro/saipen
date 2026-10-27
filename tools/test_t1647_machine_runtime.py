"""T-1647 / SRC-188: an account that cannot read the operator's install still runs SAIPEN.

A managed Windows account could open and write the project it was granted and
could run nothing of SAIPEN: `STATE.saipen_home` named a path in another
user's tree, both launchers named an interpreter installed for that user
alone, and no interpreter existed machine-wide. The engine read ACCESS_DENIED
as a dead home, so its route was `rebind-home`, which adopts whatever engine
is running -- how a public clone of another version would have become the
project's home for every account.

Pinned here, with real access lists where the platform has them:

- a home this account may not read is INACCESSIBLE, not dead: refused under
  its own code, with no rebind route, and never rebound;
- the machine runtime is a projection that proves the source generation, is
  written with least privilege, carries relocatable launchers and, when the
  installer's interpreter is private, an interpreter of its own;
- under that runtime the unreadable home is covered: the project routes,
  checkpoints, and keeps its recorded pointer;
- the same holds for a process the kernel does not answer as this account
  (`AnotherPrincipalTests`): it is denied what the operator alone may read,
  runs the machine launcher, works the project it was granted, and can change
  nothing of the runtime it runs.
"""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_t1614_future_gate as H  # noqa: E402
from saipen_engine import state as ST  # noqa: E402
from saipen_engine.registry import command_reference_path  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

WINDOWS = os.name == "nt"
ENGINE = TOOLS / "saipen.py"
ENV_ROOT = "SAIPEN_MACHINE_ROOT"
DENIED = "CROSS_USER_RUNTIME_UNAVAILABLE"


def setUpModule() -> None:
    isolate_host_session()


def machine():
    from saipen_engine import machine_runtime

    return machine_runtime


def deny_this_account(path: Path) -> None:
    """Make `path` what another user's install looks like from here: the
    inheritance is cut and only SYSTEM is granted."""
    subprocess.run(
        ["icacls", str(path), "/inheritance:r", "/grant:r", "*S-1-5-18:(OI)(CI)F", "/Q"],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["icacls", str(path / "*"), "/reset", "/T", "/C", "/Q"], capture_output=True, check=False
    )


def reset_access(path: Path) -> None:
    subprocess.run(["icacls", str(path), "/reset", "/T", "/C", "/Q"], capture_output=True)


def an_install(target: Path) -> Path:
    """A SAIPEN install of its own at `target`: this tree's shipped surface,
    laid out the way an agent home holds it. It is what a project records as
    its home and what a machine runtime is projected from -- the two are the
    same install, or the runtime stands in for nothing."""
    target.mkdir(parents=True)
    machine()._project_surface(ROOT, target)
    return target


# ------------------------------------------------ a principal that is not us

#: What a fresh local standard account holds as well. Everything else in this
#: account's token -- its own SID first -- is made deny-only for the process
#: `run_as` starts, so the kernel answers that process as it would answer
#: another account: an entry that grants THIS account grants it nothing.
_SHARED_SIDS = frozenset(
    {
        "S-1-1-0",  # Everyone
        "S-1-2-0",  # LOCAL
        "S-1-2-1",  # CONSOLE LOGON
        "S-1-5-4",  # INTERACTIVE
        "S-1-5-11",  # Authenticated Users
        "S-1-5-15",  # This Organization
        "S-1-5-113",  # Local account
        "S-1-5-32-545",  # BUILTIN\Users
    }
)
#: The logon session, the authentication package and the integrity label: none
#: of them names who the account is.
_SHARED_PREFIXES = ("S-1-5-5-", "S-1-5-64-", "S-1-16-")
_USERS = "*S-1-5-32-545"


def _shared_with_any_account(sid: str) -> bool:
    if sid in _SHARED_SIDS or sid.startswith(_SHARED_PREFIXES):
        return True
    # The machine's own "None" group: every local account's primary group.
    return sid.startswith("S-1-5-21-") and sid.endswith("-513")


class _SidAndAttributes(ctypes.Structure):
    _fields_ = (("Sid", ctypes.c_void_p), ("Attributes", ctypes.c_ulong))


class _StartupInfo(ctypes.Structure):
    _fields_ = (
        ("cb", ctypes.c_ulong),
        ("lpReserved", ctypes.c_wchar_p),
        ("lpDesktop", ctypes.c_wchar_p),
        ("lpTitle", ctypes.c_wchar_p),
        ("dwX", ctypes.c_ulong),
        ("dwY", ctypes.c_ulong),
        ("dwXSize", ctypes.c_ulong),
        ("dwYSize", ctypes.c_ulong),
        ("dwXCountChars", ctypes.c_ulong),
        ("dwYCountChars", ctypes.c_ulong),
        ("dwFillAttribute", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("wShowWindow", ctypes.c_ushort),
        ("cbReserved2", ctypes.c_ushort),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", ctypes.c_void_p),
        ("hStdOutput", ctypes.c_void_p),
        ("hStdError", ctypes.c_void_p),
    )


class _ProcessInformation(ctypes.Structure):
    _fields_ = (
        ("hProcess", ctypes.c_void_p),
        ("hThread", ctypes.c_void_p),
        ("dwProcessId", ctypes.c_ulong),
        ("dwThreadId", ctypes.c_ulong),
    )


def _win():
    """advapi32 and kernel32 with the signatures this file calls."""
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    handle, dword, pointer = ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER
    kernel.GetCurrentProcess.restype = handle
    kernel.CloseHandle.argtypes = (handle,)
    kernel.LocalFree.argtypes = (handle,)
    kernel.WaitForSingleObject.argtypes = (handle, dword)
    kernel.WaitForSingleObject.restype = dword
    kernel.GetExitCodeProcess.argtypes = (handle, pointer(dword))
    advapi.OpenProcessToken.argtypes = (handle, dword, pointer(handle))
    advapi.GetTokenInformation.argtypes = (handle, ctypes.c_int, handle, dword, pointer(dword))
    advapi.ConvertSidToStringSidW.argtypes = (handle, pointer(ctypes.c_wchar_p))
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = (
        ctypes.c_wchar_p,
        dword,
        pointer(handle),
        handle,
    )
    advapi.GetSecurityDescriptorDacl.argtypes = (
        handle,
        pointer(ctypes.c_int),
        pointer(handle),
        pointer(ctypes.c_int),
    )
    advapi.SetTokenInformation.argtypes = (handle, ctypes.c_int, handle, dword)
    advapi.SetKernelObjectSecurity.argtypes = (handle, dword, handle)
    advapi.CreateRestrictedToken.argtypes = (
        handle,
        dword,
        dword,
        handle,
        dword,
        handle,
        dword,
        handle,
        pointer(handle),
    )
    advapi.CreateProcessAsUserW.argtypes = (
        handle,
        ctypes.c_wchar_p,
        handle,
        handle,
        handle,
        ctypes.c_int,
        dword,
        handle,
        ctypes.c_wchar_p,
        pointer(_StartupInfo),
        pointer(_ProcessInformation),
    )
    return advapi, kernel


def _token_information(advapi, token, kind: int):
    size = ctypes.c_ulong(0)
    advapi.GetTokenInformation(token, kind, None, 0, ctypes.byref(size))
    data = ctypes.create_string_buffer(size.value)
    if not advapi.GetTokenInformation(token, kind, data, size, ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    return data


def _sid_text(advapi, kernel, sid) -> str:
    text = ctypes.c_wchar_p()
    if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(text)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return str(text.value)
    finally:
        kernel.LocalFree(ctypes.cast(text, ctypes.c_void_p))


def another_principal_token():
    """A primary token the kernel does not answer as this account.

    It is this account's own token with the account's SID, and every group a
    fresh local account does not hold, turned deny-only, and with every
    privilege but traversal removed. Nothing is borrowed from another account
    and no credential is used: what remains is `Users`, `Authenticated Users`
    and `Everyone`, which is what a managed account shares with the operator.
    """
    advapi, kernel = _win()
    own = ctypes.c_void_p()
    # assign primary | duplicate | query | adjust default | adjust session id,
    # and read control | write DAC for the token object's own access list
    wanted = 0x0001 | 0x0002 | 0x0008 | 0x0080 | 0x0100 | 0x00020000 | 0x00040000
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), wanted, ctypes.byref(own)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        user = _token_information(advapi, own, 1)
        groups = _token_information(advapi, own, 2)
        count = ctypes.c_ulong.from_buffer(groups).value
        held = (_SidAndAttributes * count).from_buffer(groups, ctypes.sizeof(ctypes.c_void_p))
        deny = [_SidAndAttributes.from_buffer(user).Sid]
        session = None
        for entry in held:
            if entry.Attributes & 0xC0000000 == 0xC0000000:
                session = _sid_text(advapi, kernel, entry.Sid)  # the logon session
                continue
            if entry.Attributes & (0x20 | 0x40):
                continue  # the integrity label
            if not _shared_with_any_account(_sid_text(advapi, kernel, entry.Sid)):
                deny.append(entry.Sid)
        disabled = (_SidAndAttributes * len(deny))()
        for slot, sid in zip(disabled, deny):
            slot.Sid, slot.Attributes = sid, 0
        other = ctypes.c_void_p()
        # 0x1: DISABLE_MAX_PRIVILEGE -- traversal is the one privilege left.
        made = advapi.CreateRestrictedToken(
            own, 0x1, len(deny), disabled, 0, None, 0, None, ctypes.byref(other)
        )
        if not made:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            _own_what_it_creates(advapi, kernel, other, session)
        except OSError:
            kernel.CloseHandle(other)
            raise
        return other
    finally:
        kernel.CloseHandle(own)


def _own_what_it_creates(advapi, kernel, token, session: str | None) -> None:
    """Let the principal open its own token, processes and console.

    An account owns the objects it creates through its own SID. This token's
    SID is deny-only, so that door is shut: without another one its processes
    cannot read their own token and no console attaches to them. The logon
    session's SID is the door -- it names this session, is on no file, and so
    opens nothing of the operator's.
    """
    holder = session or "BU"
    descriptor = ctypes.c_void_p()
    made = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        f"D:(A;;GA;;;SY)(A;;GA;;;{holder})", 1, ctypes.byref(descriptor), None
    )
    if not made:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        present, defaulted, dacl = ctypes.c_int(0), ctypes.c_int(0), ctypes.c_void_p()
        advapi.GetSecurityDescriptorDacl(
            descriptor, ctypes.byref(present), ctypes.byref(dacl), ctypes.byref(defaulted)
        )
        default = ctypes.c_void_p(dacl.value)
        # 6: TokenDefaultDacl -- what the processes it starts are created with.
        if not advapi.SetTokenInformation(token, 6, ctypes.byref(default), ctypes.sizeof(default)):
            raise ctypes.WinError(ctypes.get_last_error())
        # 0x4: DACL_SECURITY_INFORMATION -- the token object itself.
        if not advapi.SetKernelObjectSecurity(token, 0x4, descriptor):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.LocalFree(descriptor)


def run_as(token, command: str, cwd: Path, env: dict, scratch: Path, timeout: int = 240):
    """Run one `cmd.exe` command line under `token`: (exit code, stdout, stderr)."""
    import msvcrt

    advapi, kernel = _win()
    scratch.mkdir(parents=True, exist_ok=True)
    captured = []
    for prefix in ("out-", "err-"):
        descriptor, name = tempfile.mkstemp(prefix=prefix, dir=str(scratch))
        os.close(descriptor)
        captured.append(Path(name))
    out_path, err_path = captured
    system32 = Path(os.environ.get("SYSTEMROOT", "C:/Windows")) / "System32"
    block = "".join(
        f"{key}={value}\0" for key, value in sorted(env.items(), key=lambda kv: kv[0].upper())
    )
    block += "\0"
    with open(os.devnull, "rb") as nul, open(out_path, "wb") as out, open(err_path, "wb") as err:
        startup = _StartupInfo()
        startup.cb = ctypes.sizeof(startup)
        startup.dwFlags = 0x100  # STARTF_USESTDHANDLES
        handles = []
        for stream in (nul, out, err):
            handle = msvcrt.get_osfhandle(stream.fileno())
            os.set_handle_inheritable(handle, True)
            handles.append(handle)
        startup.hStdInput, startup.hStdOutput, startup.hStdError = handles
        started = _ProcessInformation()
        line = ctypes.create_unicode_buffer(f'"{system32 / "cmd.exe"}" /d /s /c "{command}"')
        # 0x08000000 CREATE_NO_WINDOW | 0x00000400 CREATE_UNICODE_ENVIRONMENT
        created = advapi.CreateProcessAsUserW(
            token,
            str(system32 / "cmd.exe"),
            line,
            None,
            None,
            1,
            0x08000000 | 0x00000400,
            (ctypes.c_wchar * len(block))(*block),
            str(cwd),
            ctypes.byref(startup),
            ctypes.byref(started),
        )
        if not created:
            raise ctypes.WinError(ctypes.get_last_error())
    try:
        if kernel.WaitForSingleObject(started.hProcess, timeout * 1000) != 0:
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(started.dwProcessId)],
                capture_output=True,
                check=False,
            )
            kernel.WaitForSingleObject(started.hProcess, 10000)
            return -1, b"", f"no exit within {timeout} s".encode()
        code = ctypes.c_ulong(0)
        kernel.GetExitCodeProcess(started.hProcess, ctypes.byref(code))
        return code.value, out_path.read_bytes(), err_path.read_bytes()
    finally:
        kernel.CloseHandle(started.hThread)
        kernel.CloseHandle(started.hProcess)
        for path in (out_path, err_path):
            path.unlink(missing_ok=True)


def only_this_account(path: Path) -> None:
    """Make `path` the operator's private tree: this account and SYSTEM, no
    inheritance -- what a per-user install or a profile looks like."""
    own = machine()._current_sid()
    subprocess.run(
        [
            "icacls",
            str(path),
            "/inheritance:r",
            "/grant:r",
            f"*{own}:(OI)(CI)F",
            "*S-1-5-18:(OI)(CI)F",
            "/Q",
        ],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["icacls", str(path / "*"), "/reset", "/T", "/C", "/Q"], capture_output=True, check=False
    )


def grant_users_modify(path: Path) -> None:
    """The grant an account manager gives a managed account on its workdir."""
    subprocess.run(
        ["icacls", str(path), "/grant", f"{_USERS}:(OI)(CI)M", "/Q"],
        capture_output=True,
        check=True,
    )


class _Scratch(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saipen-t1647-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(reset_access, self.tmp)
        #: A profile the running interpreter is NOT inside, so an install that
        #: names it is judged on its merits and not on this machine's layout.
        self.env = {**os.environ, "USERPROFILE": str(self.tmp / "nobody"), "HOME": ""}
        self.env.pop(ENV_ROOT, None)

    def private_home(self) -> Path:
        home = self.tmp / "other-user" / "saipen-home"
        home.mkdir(parents=True)
        (home / "BOOT.md").write_text("# another user's install\n", encoding="utf-8")
        deny_this_account(home)
        return home

    def project_recording(self, home: Path, *, ticket: bool = True) -> tuple[Path, str | None]:
        base, project = H._project(intent="goal")
        self.addCleanup(shutil.rmtree, base, True)
        tid = H._add(project, "the current work of the managed account") if ticket else None
        state = project / ".saipen" / "STATE.md"
        recorded = 'saipen_home: "' + str(home).replace("\\", "\\\\") + '"'
        lines = [
            recorded if line.startswith("saipen_home:") else line
            for line in state.read_text(encoding="utf-8").splitlines()
        ]
        state.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return project, tid

    def recorded_home(self, project: Path) -> str:
        fields, _error = ST.parse_frontmatter(
            (project / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        )
        return str((fields or {}).get("saipen_home"))

    def ask(self, argv: list, project: Path, **env) -> dict:
        scrubbed = {
            key: value
            for key, value in self.env.items()
            if not key.upper().startswith(("SAIPEN", "PYTHON")) and key.upper() != "PATH"
        }
        scrubbed["PATH"] = str(Path(os.environ.get("SYSTEMROOT", "C:/Windows")) / "System32")
        proc = subprocess.run(
            [*argv, "--json"],
            capture_output=True,
            cwd=str(project),
            env={**scrubbed, **env},
            timeout=240,
            check=False,
        )
        try:
            return json.loads(proc.stdout.decode("utf-8", "replace"))
        except ValueError:
            return {
                "code": f"UNPARSED rc={proc.returncode}",
                "detail": (proc.stderr or proc.stdout).decode("utf-8", "replace")[-600:],
            }


# ----------------------------------------------------- the engine's own gates


@unittest.skipUnless(WINDOWS, "an access list that denies the owner needs icacls")
class UnreadableHomeIsNotDeadTests(_Scratch):
    """The three engine defects, on a real access list and no machine runtime."""

    def engine(self, *args: str) -> list:
        return [sys.executable, "-B", str(ENGINE), *args]

    def test_the_home_is_classified_inaccessible_and_names_no_rebind(self):
        home = self.private_home()
        with self.assertRaises(PermissionError):
            (home / "BOOT.md").read_bytes()
        problem = ST.persisted_home_error(str(home))
        self.assertIsNotNone(problem)
        self.assertIn(DENIED, problem)
        self.assertIn("never rebound", problem)
        self.assertEqual(ST.persisted_home_access(str(home))[0], ST.HOME_INACCESSIBLE)

    def test_a_mutation_is_refused_under_its_own_code(self):
        project, _tid = self.project_recording(self.private_home())
        answer = self.ask(
            self.engine("checkpoint", "DEC", "note", "--project-root", str(project)), project
        )
        self.assertFalse(answer.get("ok"), answer)
        self.assertEqual(answer.get("code"), DENIED, answer)
        self.assertNotIn("rebind-home", json.dumps(answer))

    def test_automatic_rebind_never_adopts_the_running_engine(self):
        home = self.private_home()
        project, _tid = self.project_recording(home)
        answer = self.ask(
            self.engine("rebind-home", "--auto", "--project-root", str(project)), project
        )
        self.assertEqual(answer.get("code"), DENIED, answer)
        self.assertEqual(self.recorded_home(project), str(home))

    def test_explicit_rebind_is_refused_as_well(self):
        home = self.private_home()
        project, _tid = self.project_recording(home)
        answer = self.ask(
            self.engine("rebind-home", str(ROOT), "--project-root", str(project)), project
        )
        self.assertEqual(answer.get("code"), DENIED, answer)
        self.assertEqual(self.recorded_home(project), str(home))

    def test_continue_refuses_instead_of_converging(self):
        home = self.private_home()
        project, _tid = self.project_recording(home)
        answer = self.ask(self.engine("continue", "--project-root", str(project)), project)
        self.assertEqual(answer.get("code"), DENIED, answer)
        self.assertEqual(self.recorded_home(project), str(home))


@unittest.skipUnless(WINDOWS, "an access list that denies the owner needs icacls")
class ProjectAccessTests(_Scratch):
    """Reading the runtime and working a project are two grants. A project
    this account was not granted is answered as that, by name: never by a
    traceback, and never as a project that lost its memory."""

    def engine(self, *args: str) -> list:
        return [sys.executable, "-B", str(ENGINE), *args]

    def project(self) -> Path:
        base, project = H._project(intent="goal")
        self.addCleanup(shutil.rmtree, base, True)
        self.addCleanup(reset_access, project)
        H._add(project, "work this account was not granted")
        return project

    def test_a_project_this_account_may_not_read_is_named_as_that(self):
        project = self.project()
        deny_this_account(project)
        for command in (("continue",), ("checkpoint", "DEC", "note"), ("status",)):
            answer = self.ask(self.engine(*command, "--project-root", str(project)), self.tmp)
            self.assertEqual(
                answer.get("code"), "SAIPEN_HOST_RUNTIME_UNAVAILABLE", (command, answer)
            )
            self.assertEqual(answer.get("failure_kind"), "permission_denied", answer)
            self.assertEqual(answer.get("stage"), "before_admission", answer)
            self.assertEqual(answer["os_error"]["winerror"], 5)
            self.assertNotIn("no .saipen", str(answer.get("detail")))

    def test_the_session_carrier_is_answered_the_same_way(self):
        project = self.project()
        deny_this_account(project)
        answer = self.ask(self.engine("continue"), self.tmp, SAIPEN_PROJECT_ROOT=str(project))
        self.assertEqual(answer.get("code"), "SAIPEN_HOST_RUNTIME_UNAVAILABLE", answer)
        self.assertEqual(answer.get("failure_kind"), "permission_denied", answer)
        self.assertEqual(answer.get("stage"), "before_admission", answer)

    def test_a_project_without_memory_keeps_its_own_answer(self):
        # The control: absence is still absence.
        empty = self.tmp / "no-project"
        empty.mkdir()
        answer = self.ask(self.engine("continue", "--project-root", str(empty)), self.tmp)
        self.assertEqual(answer.get("code"), "PROJECT_BINDING_INVALID", answer)
        self.assertIn("no .saipen", str(answer.get("detail")))

    def test_a_project_granted_for_reading_refuses_the_write_by_name(self):
        project = self.project()
        only_this_account(project)
        subprocess.run(
            [
                "icacls",
                str(project),
                "/grant:r",
                f"*{machine()._current_sid()}:(OI)(CI)RX",
                "/Q",
            ],
            capture_output=True,
            check=True,
        )
        log = project / ".saipen" / "LOG.md"
        before = log.read_bytes()
        answer = self.ask(
            self.engine("checkpoint", "DEC", "note", "--project-root", str(project)), self.tmp
        )
        self.assertEqual(answer.get("code"), "CAPABILITY_READ_ONLY", answer)
        self.assertIn("reading only", str(answer.get("detail")))
        self.assertEqual(log.read_bytes(), before)
        # Continue enrolls a missing manifest; that required write stays denied.
        route = self.ask(self.engine("continue", "--project-root", str(project)), self.tmp)
        self.assertFalse(route.get("ok"), route)
        self.assertEqual(route.get("code"), "SAIPEN_HOST_RUNTIME_UNAVAILABLE", route)
        self.assertEqual(route.get("failure_kind"), "permission_denied", route)
        self.assertEqual(log.read_bytes(), before)


class WriteProbeTests(unittest.TestCase):
    def test_a_writable_folder_is_not_refused_and_keeps_nothing(self):
        from saipen_engine import lock

        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(lock._refused_write(Path(folder)))
            self.assertEqual(os.listdir(folder), [])

    def test_a_folder_that_is_not_there_is_not_an_access_list(self):
        from saipen_engine import lock

        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(lock._refused_write(Path(folder) / "absent"))


class HomeAccessRuleTests(unittest.TestCase):
    """The classification itself, on any host."""

    def test_a_dead_pointer_keeps_its_code_and_its_route(self):
        missing = str(Path(tempfile.gettempdir()) / "saipen-t1647-not-there" / "home")
        code, detail, route = ST.home_refusal(missing)
        self.assertEqual((code, route), ("HOME_REQUIRED", "saipen rebind-home --auto"))
        self.assertIn("does not resolve", detail)

    def test_a_usable_or_unverifiable_home_is_no_refusal(self):
        self.assertIsNone(ST.home_refusal(str(ROOT)))
        self.assertIsNone(ST.home_refusal(""))
        self.assertIsNone(ST.home_refusal("relative/home"))

    def test_access_denied_at_the_first_look_is_inaccessible(self):
        absolute = str(ROOT.anchor or "/") + "users-other-profile/saipen"
        with mock.patch.object(ST.os, "stat", side_effect=PermissionError(13, "denied")):
            status, reason = ST.persisted_home_access(absolute)
        self.assertEqual(status, ST.HOME_INACCESSIBLE)
        self.assertIn(DENIED, reason)

    def test_the_machine_runtime_covers_an_unreadable_home_only(self):
        absolute = str(ROOT.anchor or "/") + "users-other-profile/saipen"
        denied = mock.patch.object(ST.os, "stat", side_effect=PermissionError(13, "denied"))
        with denied, mock.patch.object(ST, "machine_runtime_covers", return_value=True):
            self.assertIsNone(ST.home_refusal(absolute))
            self.assertIsNone(ST.persisted_home_error(absolute))
        missing = str(Path(tempfile.gettempdir()) / "saipen-t1647-not-there" / "home")
        with mock.patch.object(ST, "machine_runtime_covers", return_value=True):
            self.assertEqual(ST.home_refusal(missing)[0], "HOME_REQUIRED")


# ------------------------------------------------------------ least privilege


class WritableByOthersTests(unittest.TestCase):
    OWNER = "S-1-5-21-1-2-3-1002"

    def writers(self, sddl: str) -> list:
        return machine().writable_by_others(sddl, self.OWNER)

    def test_the_hardened_list_has_no_other_writer(self):
        sddl = (
            f"D:PAI(A;OICI;0x1200a9;;;BU)(A;OICI;FA;;;{self.OWNER})(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)"
        )
        self.assertEqual(self.writers(sddl), [])

    def test_the_inherited_right_to_add_files_is_a_writer(self):
        # What a folder under ProgramData inherits: Users may create children.
        sddl = "D:AI(A;OICIID;0x1200a9;;;BU)(A;CIID;DCLCRPCR;;;BU)(A;OICIID;FA;;;SY)"
        self.assertEqual(self.writers(sddl), ["S-1-5-32-545"])

    def test_modify_for_authenticated_users_is_a_writer(self):
        self.assertEqual(self.writers("D:(A;OICI;0x1301bf;;;AU)"), ["S-1-5-11"])

    def test_an_inherit_only_entry_counts(self):
        self.assertEqual(self.writers("D:(A;OICIIO;GA;;;WD)"), ["S-1-1-0"])

    def test_a_managed_account_named_by_sid_is_a_writer(self):
        sid = "S-1-5-21-1-2-3-1008"
        self.assertEqual(self.writers(f"D:(A;OICI;0x1301bf;;;{sid})"), [sid])

    def test_a_deny_entry_and_read_execute_are_not_writers(self):
        self.assertEqual(self.writers("D:(D;;FA;;;BU)(A;;0x1200a9;;;BU)(A;;FRFX;;;AU)"), [])


class LauncherTests(unittest.TestCase):
    def test_bundled_launchers_name_no_absolute_path(self):
        made = machine().render_launchers(
            "runtime/0123456789abcdef", "python/3.11.9-64/python.exe", None
        )
        windows = made["saipen.cmd"].decode("utf-8")
        posix = made["saipen"].decode("utf-8")
        self.assertIn('"%~dp0..\\python\\3.11.9-64\\python.exe"', windows)
        self.assertIn('"%~dp0..\\runtime\\0123456789abcdef\\tools\\saipen.py" %*', windows)
        self.assertNotIn(":\\", windows)
        self.assertIn('"$here/../python/3.11.9-64/python.exe"', posix)
        self.assertIn('"$here/../runtime/0123456789abcdef/tools/saipen.py" "$@"', posix)
        self.assertTrue(posix.startswith("#!/bin/sh\n"))

    def test_an_explicit_interpreter_is_named_where_it_is(self):
        made = machine().render_launchers("runtime/0123456789abcdef", None, r"C:\Python\python.exe")
        self.assertIn(
            '"C:\\Python\\python.exe" "%~dp0..\\runtime', made["saipen.cmd"].decode("utf-8")
        )
        self.assertIn('"C:/Python/python.exe" "$here/../runtime', made["saipen"].decode("utf-8"))


class LocationTests(unittest.TestCase):
    def test_a_runtime_stands_in_for_the_install_it_was_projected_from(self):
        registration = {"source_root": "V:\\Work\\SAIPEN"}
        self.assertTrue(machine().projects(registration, "V:\\Work\\SAIPEN"))
        if WINDOWS:
            self.assertTrue(machine().projects(registration, "v:/work/saipen/"))
        for other in ("V:\\Work\\OTHER", "", None):
            self.assertFalse(machine().projects(registration, other), other)
        self.assertFalse(machine().projects(None, "V:\\Work\\SAIPEN"))
        self.assertFalse(machine().projects({}, "V:\\Work\\SAIPEN"))

    def test_an_explicit_root_wins_and_grants_nothing_else(self):
        self.assertEqual(machine().default_root({ENV_ROOT: "X:/machine"}), Path("X:/machine"))

    @unittest.skipUnless(WINDOWS, "the measured layout is the Windows one")
    def test_the_windows_root_is_under_program_data(self):
        root = machine().default_root({"ProgramData": r"D:\PD"})
        self.assertEqual(root, Path(r"D:\PD") / "SAI" / "SAIPEN")

    def test_an_interpreter_inside_a_profile_is_private(self):
        profile = str(Path(tempfile.gettempdir()) / "profile")
        env = {"USERPROFILE": profile}
        inside = str(Path(profile) / "AppData" / "Python" / "python.exe")
        self.assertTrue(machine().interpreter_is_private(inside, env))
        self.assertFalse(
            machine().interpreter_is_private(str(Path(tempfile.gettempdir()) / "py.exe"), env)
        )


# ------------------------------------------------------------- the projection


class ProjectionTests(_Scratch):
    def install(self, source: Path = ROOT, **options) -> dict:
        options.setdefault("python", sys.executable)
        return machine().install(source, self.tmp / "machine", env=self.env, **options)

    def test_the_projection_proves_the_source_generation(self):
        from saipen_engine import runtime_surface

        report = self.install()
        self.assertEqual(report["code"], machine().CODE_INSTALLED, report)
        self.assertTrue(report["saipen_runtime_ready"])
        registration = machine().read_registration(self.tmp / "machine")
        self.assertEqual(
            registration["generation"], runtime_surface.runtime_generation_identity(ROOT)
        )
        home = machine().runtime_home(self.tmp / "machine", registration)
        self.assertEqual(
            runtime_surface.runtime_generation_identity(home), registration["generation"]
        )
        self.assertTrue((home / "BOOT.md").is_file())
        self.assertTrue((home / "tools" / "saipen.py").is_file())
        self.assertEqual(registration["saipen_version"], (ROOT / "VERSION").read_text().strip())
        self.assertIsInstance(registration["state_schema"], int)
        self.assertEqual(report["source"], "MACHINE_RUNTIME")

    def test_a_second_install_changes_nothing(self):
        self.install()
        before = (self.tmp / "machine" / "registration.json").read_bytes()
        again = self.install()
        self.assertEqual(again["code"], machine().CODE_CURRENT)
        self.assertFalse(again["changed"])
        after = json.loads((self.tmp / "machine" / "registration.json").read_text("utf-8"))
        self.assertEqual(after["generation"], json.loads(before)["generation"])

    def test_changed_runtime_bytes_are_broken_not_ready(self):
        self.install()
        registration = machine().read_registration(self.tmp / "machine")
        target = machine().runtime_home(self.tmp / "machine", registration) / "BOOT.md"
        target.write_bytes(target.read_bytes() + b"\n<!-- changed -->\n")
        status = machine().status(self.tmp / "machine", env=self.env)
        self.assertEqual(status["code"], machine().CODE_BROKEN)
        self.assertFalse(status["saipen_runtime_ready"])
        self.assertEqual(status["action"], "saipen host machine install")

    def test_another_canonical_generation_reads_stale(self):
        self.install()
        registration = machine().read_registration(self.tmp / "machine")
        newer = self.tmp / "newer-source"
        shutil.copytree(machine().runtime_home(self.tmp / "machine", registration), newer)
        (newer / "BOOT.md").write_bytes((newer / "BOOT.md").read_bytes() + b"\nnewer\n")
        status = machine().status(self.tmp / "machine", canonical=newer, env=self.env)
        self.assertEqual(status["code"], machine().CODE_STALE)
        self.assertFalse(status["saipen_runtime_ready"])
        # Without a canonical to compare against, the same projection is intact.
        self.assertEqual(
            machine().status(self.tmp / "machine", env=self.env)["code"], machine().CODE_READY
        )

    def test_an_upgrade_keeps_one_generation_to_fall_back_to(self):
        first = self.install()
        registration = machine().read_registration(self.tmp / "machine")
        old_home = machine().runtime_home(self.tmp / "machine", registration)
        generations = []
        source = old_home
        for step in ("second", "third"):
            newer = self.tmp / f"{step}-source"
            shutil.copytree(source, newer)
            (newer / "BOOT.md").write_bytes((newer / "BOOT.md").read_bytes() + step.encode())
            report = self.install(newer)
            self.assertEqual(report["code"], machine().CODE_INSTALLED, report)
            generations.append(report["generation"])
            source = newer
        registration = machine().read_registration(self.tmp / "machine")
        self.assertEqual(registration["generation"], generations[-1])
        self.assertEqual(registration["previous"]["generation"], generations[0])
        kept = sorted(entry.name for entry in (self.tmp / "machine" / "runtime").iterdir())
        self.assertEqual(len(kept), 2, kept)
        self.assertFalse(old_home.exists())
        launcher = (self.tmp / "machine" / "bin" / "saipen.cmd").read_text("utf-8")
        self.assertIn(registration["runtime"].replace("/", "\\"), launcher)
        self.assertNotEqual(first["generation"], generations[-1])

    def test_the_runtime_does_not_project_itself(self):
        # Asked from its own launcher, install would name the projection as
        # its own source and nothing would follow the operator's install.
        self.install()
        registration = self.tmp / "machine" / "registration.json"
        before = registration.read_bytes()
        inside = machine().runtime_home(
            self.tmp / "machine", machine().read_registration(self.tmp / "machine")
        )
        report = machine().install(inside, self.tmp / "machine", python=sys.executable)
        self.assertEqual(report["code"], machine().CODE_FAILED, report)
        self.assertIn("the machine runtime itself", report["detail"])
        self.assertEqual(registration.read_bytes(), before)

    def test_the_runtime_does_not_remove_itself(self):
        self.install()
        root = self.tmp / "machine"
        inside = machine().runtime_home(root, machine().read_registration(root))
        report = machine().remove(root, engine_root=inside)
        self.assertEqual(report["code"], machine().CODE_FAILED, report)
        self.assertIn("does not remove itself", report["detail"])
        self.assertTrue((root / "registration.json").is_file())
        if WINDOWS:
            # The same answer through its own launcher, where it matters.
            answer = self.ask(
                [
                    str(root / "bin" / "saipen.cmd"),
                    "host",
                    "machine",
                    "remove",
                    "--root",
                    str(root),
                ],
                self.tmp,
                **{ENV_ROOT: str(root)},
            )
            self.assertEqual(answer.get("code"), machine().CODE_FAILED, answer)
            self.assertTrue((root / "registration.json").is_file())
            self.assertEqual(machine().status(root, env=self.env)["code"], machine().CODE_READY)

    def test_remove_deletes_a_runtime_and_nothing_else(self):
        self.install()
        gone = machine().remove(self.tmp / "machine")
        self.assertEqual(gone["code"], machine().CODE_REMOVED)
        self.assertFalse((self.tmp / "machine").exists())
        bystander = self.tmp / "not-a-runtime"
        bystander.mkdir()
        (bystander / "keep.txt").write_text("keep", encoding="utf-8")
        refused = machine().remove(bystander)
        self.assertFalse(refused["ok"])
        self.assertTrue((bystander / "keep.txt").is_file())

    def test_an_interpreter_inside_the_installers_profile_is_not_ready(self):
        private_env = {**self.env, "USERPROFILE": str(Path(sys.executable).parent)}
        report = machine().install(
            ROOT, self.tmp / "machine", python=sys.executable, env=private_env
        )
        self.assertEqual(report["code"], machine().CODE_BROKEN, report)
        self.assertFalse(report["saipen_runtime_ready"])
        self.assertTrue(any("user profile" in reason for reason in report["reasons"]))

    @unittest.skipUnless(WINDOWS, "access lists are set and read through Windows")
    def test_the_root_is_written_with_least_privilege(self):
        self.install()
        root = self.tmp / "machine"
        sddl = machine()._sddl(root)
        self.assertTrue(sddl and sddl.startswith("D:P"), sddl)
        self.assertEqual(machine().writable_by_others(sddl, machine()._current_sid()), [])
        self.assertIn(";;;BU)", sddl)
        registration = machine().read_registration(root)
        inner = machine().runtime_home(root, registration) / "tools" / "saipen.py"
        self.assertEqual(
            machine().writable_by_others(machine()._sddl(inner), machine()._current_sid()), []
        )
        self.assertEqual(machine().status(root, env=self.env)["acl"]["writable_by"], [])

    @unittest.skipUnless(WINDOWS, "access lists are set and read through Windows")
    def test_a_root_others_can_write_is_broken(self):
        self.install()
        root = self.tmp / "machine"
        subprocess.run(
            ["icacls", str(root), "/grant", "*S-1-5-11:(OI)(CI)M", "/Q"],
            capture_output=True,
            check=True,
        )
        status = machine().status(root, env=self.env)
        self.assertEqual(status["code"], machine().CODE_BROKEN)
        self.assertEqual(status["acl"]["writable_by"], ["S-1-5-11"])

    @unittest.skipUnless(WINDOWS, "the bundled interpreter is the Windows layout")
    def test_a_bundled_interpreter_runs_with_nothing_else_on_the_machine(self):
        report = machine().install(ROOT, self.tmp / "machine", bundle_python=True, env=self.env)
        self.assertEqual(report["code"], machine().CODE_INSTALLED, report)
        registration = machine().read_registration(self.tmp / "machine")
        self.assertTrue(registration["python_bundled"])
        self.assertFalse(Path(registration["python"]).is_absolute())
        launcher = (self.tmp / "machine" / "bin" / "saipen.cmd").read_text("utf-8")
        self.assertNotIn(":\\", launcher)
        base, project = H._project()
        self.addCleanup(shutil.rmtree, base, True)
        answer = self.ask(
            [str(self.tmp / "machine" / "bin" / "saipen.cmd"), "host", "bootstrap"],
            project,
            **{ENV_ROOT: str(self.tmp / "machine")},
        )
        self.assertEqual(answer.get("code"), "HOST_BOOTSTRAP_BOUND", answer)
        self.assertTrue(
            str(answer.get("python") or "").lower().startswith(str(self.tmp / "machine").lower()),
            answer.get("python"),
        )


@unittest.skipUnless(WINDOWS, "owners are read through Windows")
class OwnershipTests(_Scratch):
    """The owner of an entry may rewrite its access list, so an access list
    that reads clean proves nothing about an entry another account owns. The
    other account is simulated at the one place the system is asked (`_owner`):
    making a file somebody else's needs a privilege a test does not hold."""

    FOREIGN = "S-1-5-21-111-222-333-1008"

    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "machine"

    def owned_by_another(self, *names: str):
        real = machine()._owner

        def owner(path):
            return self.FOREIGN if Path(path).name in names else real(path)

        return mock.patch.object(machine(), "_owner", side_effect=owner)

    def test_the_owner_is_read_from_the_system(self):
        mine = self.tmp / "mine.txt"
        mine.write_text("x", encoding="utf-8")
        self.assertIn(
            machine()._owner(mine), {machine()._current_sid(), machine().SID_ADMINISTRATORS}
        )
        self.assertIsNone(machine()._owner(self.tmp / "absent"))
        self.assertEqual(machine().foreign_owners(self.tmp, {machine()._owner(mine)}), [])

    def test_a_clean_install_has_no_foreign_owner(self):
        report = machine().install(ROOT, self.root, python=sys.executable, env=self.env)
        self.assertTrue(report["saipen_runtime_ready"], report)
        self.assertEqual(report["acl"]["foreign_owners"], [])
        self.assertEqual(report["acl"]["installed_by"], machine()._current_sid())

    def test_an_entry_another_account_owns_is_not_ready(self):
        machine().install(ROOT, self.root, python=sys.executable, env=self.env)
        with self.owned_by_another("saipen.cmd"):
            status = machine().status(self.root, env=self.env)
        self.assertEqual(status["code"], machine().CODE_BROKEN, status)
        self.assertFalse(status["saipen_runtime_ready"])
        self.assertEqual(status["acl"]["writable_by"], [])  # the list alone read clean
        self.assertEqual(len(status["acl"]["foreign_owners"]), 1)
        self.assertIn(self.FOREIGN, status["acl"]["foreign_owners"][0])
        self.assertTrue(any("rewrite its access list" in reason for reason in status["reasons"]))

    def test_a_root_another_account_made_is_not_projected_into(self):
        self.root.mkdir()
        with self.owned_by_another(self.root.name):
            report = machine().install(ROOT, self.root, python=sys.executable, env=self.env)
        self.assertEqual(report["code"], machine().CODE_FAILED, report)
        self.assertIn("is not this installer's", report["detail"])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_an_installer_nobody_vouches_for_is_not_ready(self):
        self.assertIn("another account", machine()._unanchored_installer(self.FOREIGN, None))
        self.assertIsNone(machine()._unanchored_installer(machine()._current_sid(), None))
        self.assertIsNone(machine()._unanchored_installer(machine().SID_ADMINISTRATORS, None))
        # The owner of the install the asker runs is an anchor.
        with mock.patch.object(machine(), "_owner", return_value=self.FOREIGN):
            self.assertIsNone(machine()._unanchored_installer(self.FOREIGN, ROOT))

    def test_a_runtime_that_names_its_own_installer_is_not_believed(self):
        # What an account that reached the root first would leave behind: it
        # owns everything and the registration says it installed it.
        machine().install(ROOT, self.root, python=sys.executable, env=self.env)
        registration = self.root / "registration.json"
        claimed = json.loads(registration.read_text(encoding="utf-8"))
        claimed["installed_by"] = self.FOREIGN
        registration.write_text(json.dumps(claimed), encoding="utf-8")
        with mock.patch.object(machine(), "_owner", return_value=self.FOREIGN):
            status = machine().status(self.root, env=self.env)
        self.assertEqual(status["code"], machine().CODE_BROKEN, status)
        self.assertEqual(status["acl"]["foreign_owners"], [])
        self.assertTrue(
            any("installed by another account" in reason for reason in status["reasons"])
        )

    def test_a_registration_cannot_point_the_engine_elsewhere(self):
        machine().install(ROOT, self.root, python=sys.executable, env=self.env)
        registration = self.root / "registration.json"
        good = json.loads(registration.read_text(encoding="utf-8"))
        for runtime in ("../../elsewhere", "runtime/../../x", "C:/elsewhere", "runtime/zz"):
            registration.write_text(json.dumps({**good, "runtime": runtime}), encoding="utf-8")
            self.assertIsNone(machine().read_registration(self.root), runtime)
            self.assertEqual(machine().status(self.root)["code"], machine().CODE_BROKEN)
        outside = {**good, "python_bundled": True, "python": "../python.exe"}
        (self.tmp / "python.exe").write_bytes(b"")
        registration.write_text(json.dumps(outside), encoding="utf-8")
        status = machine().status(self.root, env=self.env)
        self.assertIn(
            "the registered interpreter is not inside the runtime root", status["reasons"]
        )


# ------------------------------------------------------------------ end to end


@unittest.skipUnless(WINDOWS, "the scenario is two Windows accounts and an access list")
class ManagedAccountScenarioTests(_Scratch):
    """The SRC-188 incident with the machine runtime in place: a project whose
    recorded home this account is denied, worked through the machine launcher."""

    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "ProgramData" / "SAI" / "SAIPEN"
        # The operator's install, its projection, and then the access list
        # that makes the install another user's from where this test stands.
        self.home = an_install(self.tmp / "other-user" / "saipen-home")
        report = machine().install(self.home, self.root, python=sys.executable, env=self.env)
        self.assertTrue(report["saipen_runtime_ready"], report)
        deny_this_account(self.home)
        self.project, self.tid = self.project_recording(self.home)
        self.launcher = [str(self.root / "bin" / "saipen.cmd")]

    def through_machine(self, *args: str) -> dict:
        return self.ask([*self.launcher, *args], self.project, **{ENV_ROOT: str(self.root)})

    def test_the_binding_names_the_machine_runtime_and_keeps_the_pointer(self):
        answer = self.through_machine("host", "bootstrap")
        self.assertEqual(answer.get("code"), "HOST_BOOTSTRAP_BOUND", answer)
        self.assertEqual(answer.get("runtime_source"), "MACHINE_RUNTIME")
        binding = answer["binding"]
        self.assertTrue(binding["persisted_home_inaccessible"])
        self.assertFalse(binding["persisted_home_dead"])
        self.assertEqual(binding["legacy_saipen_home"], "INACCESSIBLE_BUT_REPLACED")
        self.assertNotIn("convergence_command", binding)
        # The machine launcher is the transport: no bridge is asked for.
        self.assertFalse(answer["bridge_required"])
        self.assertEqual(answer["launcher"]["transport"], "direct_launcher")
        self.assertEqual(Path(answer["launcher"]["windows"]), self.root / "bin" / "saipen.cmd")

    def test_continue_routes_the_current_work_with_readable_documents(self):
        answer = self.through_machine("continue")
        self.assertTrue(answer.get("ok"), answer)
        self.assertEqual(answer.get("action"), f"PHASE SCOUT {self.tid}")
        cold = answer["cold_route"]
        self.assertEqual(cold["runtime_source"], "MACHINE_RUNTIME")
        self.assertEqual(cold["recorded_saipen_home"], str(self.home))
        for path in (cold["boot"], answer["load_path"]):
            self.assertTrue(str(path).lower().startswith(str(self.root).lower()), path)
            self.assertTrue(Path(path).is_file(), path)

    def test_a_checkpoint_lands_and_the_recorded_home_is_untouched(self):
        answer = self.through_machine("checkpoint", "DEC", "note from the machine runtime")
        self.assertTrue(answer.get("ok"), answer)
        self.assertEqual(answer.get("code"), "CHECKPOINTED")
        self.assertEqual(self.recorded_home(self.project), str(self.home))
        log = (self.project / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("note from the machine runtime", log)

    def test_rebind_under_the_machine_runtime_writes_nothing(self):
        answer = self.through_machine("rebind-home", "--auto")
        self.assertEqual(answer.get("code"), "HOME_ALREADY_BOUND", answer)
        self.assertEqual(self.recorded_home(self.project), str(self.home))

    def test_an_explicit_rebind_is_refused_under_the_machine_runtime_as_well(self):
        answer = self.through_machine("rebind-home", f'"{ROOT}"')
        self.assertEqual(answer.get("code"), DENIED, answer)
        self.assertIn("stands in for it", str(answer.get("detail")))
        self.assertEqual(self.recorded_home(self.project), str(self.home))

    def test_the_denied_home_stays_denied(self):
        # The security control: the stand-in is a runtime, not a grant.
        self.assertTrue(self.through_machine("continue").get("ok"))
        with self.assertRaises(PermissionError):
            (self.home / "BOOT.md").read_bytes()
        self.assertEqual(ST.persisted_home_access(str(self.home))[0], ST.HOME_INACCESSIBLE)

    def test_a_runtime_projected_from_another_install_covers_nothing(self):
        # The same machine runtime, a project whose home is some other install
        # this account cannot read: serving it would be a substitution.
        other = self.tmp / "third-user" / "saipen-home"
        other.mkdir(parents=True)
        (other / "BOOT.md").write_text("# a third install\n", encoding="utf-8")
        deny_this_account(other)
        project, _tid = self.project_recording(other)
        machine_root = {ENV_ROOT: str(self.root)}
        answer = self.ask([*self.launcher, "checkpoint", "DEC", "note"], project, **machine_root)
        self.assertEqual(answer.get("code"), DENIED, answer)
        self.assertIn("projects", str(answer.get("detail")))
        self.assertIn("not that home", str(answer.get("detail")))
        # One step, and not the one that leads back here: this engine IS the
        # machine runtime, so "run the machine runtime" would be a circle.
        self.assertIn("This needs the operator", str(answer.get("detail")))
        self.assertNotIn("run SAIPEN through the machine runtime", str(answer.get("detail")))
        self.assertNotIn("note", (project / ".saipen" / "LOG.md").read_text("utf-8"))
        self.assertEqual(self.recorded_home(project), str(other))
        bound = self.ask([*self.launcher, "host", "bootstrap"], project, **machine_root)
        self.assertEqual(bound["binding"]["legacy_saipen_home"], "INACCESSIBLE_NOT_THIS_RUNTIME")

    def test_a_project_of_a_newer_protocol_is_not_served(self):
        state = self.project / ".saipen" / "STATE.md"
        text = state.read_text(encoding="utf-8")
        self.assertIn("saipen_version: 8", text)
        state.write_text(text.replace("saipen_version: 8", "saipen_version: 99"), encoding="utf-8")
        answer = self.through_machine("checkpoint", "DEC", "note")
        self.assertFalse(answer.get("ok"), answer)
        self.assertIn("newer than the running SAIPEN", json.dumps(answer))
        self.assertNotIn("note", (self.project / ".saipen" / "LOG.md").read_text("utf-8"))

    def test_without_any_machine_runtime_the_refusal_names_the_install_command(self):
        answer = self.ask(
            [
                sys.executable,
                "-B",
                str(ENGINE),
                "checkpoint",
                "DEC",
                "note",
                "--project-root",
                str(self.project),
            ],
            self.project,
            **{ENV_ROOT: str(self.tmp / "no-machine-runtime-here")},
        )
        self.assertEqual(answer.get("code"), DENIED, answer)
        self.assertIn("`saipen host machine install`", str(answer.get("detail")))

    def test_the_refusal_names_the_installed_launcher(self):
        answer = self.ask(
            [
                sys.executable,
                "-B",
                str(ENGINE),
                "checkpoint",
                "DEC",
                "note",
                "--project-root",
                str(self.project),
            ],
            self.project,
            **{ENV_ROOT: str(self.root)},
        )
        self.assertIn(str(self.root / "bin" / "saipen.cmd"), str(answer.get("detail")))

    def test_another_copy_of_the_engine_is_still_refused(self):
        # The control: the same project, the same denied home, an engine that
        # is not the registered machine runtime.
        answer = self.ask(
            [
                sys.executable,
                "-B",
                str(ENGINE),
                "checkpoint",
                "DEC",
                "note",
                "--project-root",
                str(self.project),
            ],
            self.project,
            **{ENV_ROOT: str(self.root)},
        )
        self.assertEqual(answer.get("code"), DENIED, answer)


@unittest.skipUnless(WINDOWS, "another principal is a Windows token")
class AnotherPrincipalTests(_Scratch):
    """SRC-188's fixture, asked by a process that is not this account to the
    kernel. `another_principal_token` says what it is and what it is not: the
    access lists here are decided by the system for a principal that holds
    `Users` and not the operator's SID, exactly as for a managed account; it
    is not a second Windows account, whose run needs that account's logon.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.base = Path(tempfile.mkdtemp(prefix="saipen-t1647-other-"))
        cls.addClassCleanup(shutil.rmtree, cls.base, True)
        cls.addClassCleanup(reset_access, cls.base)
        try:
            cls.token = another_principal_token()
        except OSError as exc:
            raise unittest.SkipTest(f"no restricted token on this system: {exc}") from exc
        cls.addClassCleanup(_win()[1].CloseHandle, cls.token)
        # What the operator alone may read: a profile file and the home every
        # project records.
        cls.secret = cls.base / "operator" / "profile" / "private.txt"
        cls.secret.parent.mkdir(parents=True)
        cls.secret.write_text("operator-only-7f3a\n", encoding="utf-8")
        cls.home = an_install(cls.base / "operator" / "saipen-home")
        only_this_account(cls.secret.parent)
        only_this_account(cls.home)
        # What the other account has of its own: a profile it may write.
        cls.profile = cls.base / "managed-profile"
        (cls.profile / "Temp").mkdir(parents=True)
        grant_users_modify(cls.profile)
        # The machine runtime, with its own interpreter: the installer's may
        # be one more thing only the operator can read.
        cls.root = cls.base / "ProgramData" / "SAI" / "SAIPEN"
        env = {**os.environ, "USERPROFILE": str(cls.base / "nobody"), "HOME": ""}
        env.pop(ENV_ROOT, None)
        report = machine().install(cls.home, cls.root, bundle_python=True, env=env)
        if not report.get("saipen_runtime_ready"):
            raise AssertionError(report)
        system_root = os.environ.get("SYSTEMROOT", "C:/Windows")
        cls.other_env = {
            "SystemRoot": system_root,
            "windir": system_root,
            "SystemDrive": os.environ.get("SYSTEMDRIVE", "C:"),
            "ComSpec": str(Path(system_root) / "System32" / "cmd.exe"),
            "PATH": str(Path(system_root) / "System32"),
            "PATHEXT": ".COM;.EXE;.BAT;.CMD",
            "ProgramData": os.environ.get("PROGRAMDATA", "C:/ProgramData"),
            "USERPROFILE": str(cls.profile),
            "APPDATA": str(cls.profile / "AppData" / "Roaming"),
            "LOCALAPPDATA": str(cls.profile / "AppData" / "Local"),
            "TEMP": str(cls.profile / "Temp"),
            "TMP": str(cls.profile / "Temp"),
            ENV_ROOT: str(cls.root),
        }
        # The stand-in must BE another principal before anything is concluded
        # from it: it starts, and the operator-only file is closed to it.
        code, _out, err = cls.shell("exit 0")
        if code != 0:
            raise unittest.SkipTest(f"a restricted process does not start here: {err[-200:]!r}")
        code, out, _err = cls.shell(f'type "{cls.secret}"')
        if code == 0 or b"7f3a" in out:
            raise unittest.SkipTest("this account's token cannot be made another principal here")

    @classmethod
    def shell(cls, command: str, cwd: Path | None = None) -> tuple:
        return run_as(cls.token, command, cwd or cls.profile, cls.other_env, cls.base / "captured")

    def setUp(self) -> None:
        super().setUp()
        self.project, self.tid = self.project_recording(self.home)
        grant_users_modify(self.project)
        self.launcher = self.root / "bin" / "saipen.cmd"

    def through_machine(self, *args: str, project: Path | None = None) -> dict:
        project = project or self.project
        code, out, err = self.shell(f'"{self.launcher}" {" ".join(args)} --json', cwd=project)
        try:
            return json.loads(out.decode("utf-8", "replace"))
        except ValueError:
            return {
                "code": f"UNPARSED rc={code}",
                "detail": (err or out).decode("utf-8", "replace")[-600:],
            }

    def test_what_the_operator_alone_may_read_stays_closed(self):
        # The negative control, before and after the runtime was used.
        self.assertIn("7f3a", self.secret.read_text(encoding="utf-8"))
        self.assertTrue(self.through_machine("continue").get("ok"))
        for private in (self.secret, self.home / "BOOT.md"):
            code, out, _err = self.shell(f'type "{private}"')
            self.assertNotEqual(code, 0, private)
            self.assertNotIn(b"7f3a", out)
        code, out, _err = self.shell(f'dir /b "{self.home}"')
        self.assertNotEqual(code, 0)
        self.assertNotIn(b"BOOT", out)

    def test_the_binding_is_the_machine_runtime(self):
        answer = self.through_machine("host", "bootstrap")
        self.assertEqual(answer.get("code"), "HOST_BOOTSTRAP_BOUND", answer)
        self.assertEqual(answer.get("runtime_source"), "MACHINE_RUNTIME")
        binding = answer["binding"]
        self.assertTrue(binding["persisted_home_inaccessible"])
        self.assertEqual(binding["legacy_saipen_home"], "INACCESSIBLE_BUT_REPLACED")
        self.assertFalse(answer["bridge_required"])
        for named in (answer.get("python"), answer["launcher"]["windows"]):
            self.assertTrue(str(named).lower().startswith(str(self.root).lower()), named)

    def test_the_current_work_is_resumed(self):
        answer = self.through_machine("continue")
        self.assertTrue(answer.get("ok"), answer)
        # The ticket this account's engine added: one lifecycle truth for both.
        self.assertEqual(answer.get("action"), f"PHASE SCOUT {self.tid}")
        cold = answer["cold_route"]
        self.assertEqual(cold["runtime_source"], "MACHINE_RUNTIME")
        for path in (cold["boot"], answer["load_path"]):
            self.assertTrue(str(path).lower().startswith(str(self.root).lower()), path)

    def test_a_checkpoint_lands_in_the_granted_project(self):
        answer = self.through_machine("checkpoint", "DEC", "note-from-another-principal")
        self.assertEqual(answer.get("code"), "CHECKPOINTED", answer)
        log = (self.project / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("note-from-another-principal", log)
        self.assertEqual(self.recorded_home(self.project), str(self.home))

    def test_the_runtime_it_runs_is_closed_to_its_writes(self):
        registration = self.root / "registration.json"
        before = registration.read_bytes()
        planted = self.root / "bin" / "planted.cmd"
        for command in (
            f'echo planted> "{planted}"',
            f'echo changed> "{registration}"',
            f'del /q "{self.launcher}"',
            f'mkdir "{self.root / "runtime" / "planted"}"',
        ):
            self.shell(command)
        self.assertFalse(planted.exists())
        self.assertFalse((self.root / "runtime" / "planted").exists())
        self.assertTrue(self.launcher.is_file())
        self.assertEqual(registration.read_bytes(), before)
        self.assertEqual(machine().status(self.root, env=self.env)["code"], machine().CODE_READY)

    def test_a_project_it_was_not_granted_is_not_worked(self):
        # Reading the runtime and writing a project are two grants.
        project, _tid = self.project_recording(self.home)
        only_this_account(project)
        log = project / ".saipen" / "LOG.md"
        before = log.read_bytes()
        answer = self.through_machine(
            "checkpoint",
            "DEC",
            "note-nobody-granted",
            "--project-root",
            f'"{project}"',
            project=self.profile,
        )
        self.assertEqual(answer.get("code"), "SAIPEN_HOST_RUNTIME_UNAVAILABLE", answer)
        self.assertEqual(answer.get("failure_kind"), "permission_denied", answer)
        self.assertEqual(log.read_bytes(), before)

    def test_a_project_granted_for_reading_refuses_required_manifest_write(self):
        project, _tid = self.project_recording(self.home)
        only_this_account(project)
        subprocess.run(
            ["icacls", str(project), "/grant", f"{_USERS}:(OI)(CI)RX", "/Q"],
            capture_output=True,
            check=True,
        )
        log = project / ".saipen" / "LOG.md"
        before = log.read_bytes()
        route = self.through_machine("continue", project=project)
        self.assertFalse(route.get("ok"), route)
        self.assertEqual(route.get("code"), "SAIPEN_HOST_RUNTIME_UNAVAILABLE", route)
        self.assertEqual(route.get("failure_kind"), "permission_denied", route)
        answer = self.through_machine("checkpoint", "DEC", "note-read-only", project=project)
        self.assertEqual(answer.get("code"), "CAPABILITY_READ_ONLY", answer)
        self.assertIn("reading only", str(answer.get("detail")))
        self.assertEqual(log.read_bytes(), before)


# --------------------------------------------------------------- the surfaces


class CommandSurfaceTests(_Scratch):
    def cli(self, *args: str) -> dict:
        proc = subprocess.run(
            [sys.executable, "-B", str(ENGINE), "host", "machine", *args, "--json"],
            capture_output=True,
            env=self.env,
            cwd=str(self.tmp),
            timeout=240,
            check=False,
        )
        return json.loads(proc.stdout.decode("utf-8", "replace"))

    def test_status_install_and_remove_through_the_cli(self):
        root = str(self.tmp / "machine")
        absent = self.cli("status", "--root", root)
        self.assertEqual(absent["code"], "MACHINE_RUNTIME_ABSENT")
        self.assertFalse(absent["saipen_runtime_ready"])
        self.assertEqual(absent["action"], "saipen host machine install")
        installed = self.cli("install", "--root", root, "--python", sys.executable)
        self.assertEqual(installed["code"], "MACHINE_RUNTIME_INSTALLED", installed)
        ready = self.cli("status", "--root", root)
        self.assertEqual(ready["code"], "MACHINE_RUNTIME_READY", ready)
        self.assertTrue(ready["saipen_runtime_ready"])
        self.assertTrue(ready["current"])
        self.assertEqual(self.cli("remove", "--root", root)["code"], "MACHINE_RUNTIME_REMOVED")

    def test_an_unknown_action_or_option_is_refused(self):
        self.assertEqual(self.cli("upgrade")["code"], "VALIDATION_FAILED")
        self.assertEqual(self.cli("status", "--force")["code"], "VALIDATION_FAILED")

    def test_the_effect_table_knows_which_actions_write(self):
        from saipen_engine import command_effects as CE

        self.assertEqual(CE.classify_invocation("host", ["machine"]), CE.DIAGNOSTIC)
        self.assertEqual(CE.classify_invocation("host", ["machine", "status"]), CE.DIAGNOSTIC)
        self.assertEqual(CE.classify_invocation("host", ["machine", "install"]), CE.RECOVERY)
        self.assertEqual(CE.classify_invocation("host", ["machine", "remove"]), CE.RECOVERY)

    def test_the_doctor_reports_the_machine_runtime(self):
        from saipen_engine import host_integration

        with mock.patch.dict(os.environ, {ENV_ROOT: str(self.tmp / "machine")}):
            view = host_integration.machine_runtime_view(ROOT)
            self.assertEqual(view["code"], "MACHINE_RUNTIME_ABSENT")
            self.assertFalse(view["saipen_runtime_ready"])
            self.assertIn(
                "machine        ABSENT",
                host_integration.render({"machine_runtime": view, "hosts": []}),
            )


class RepairFollowsTheSourceTests(_Scratch):
    """`saipen host repair` keeps an existing machine runtime on the generation
    of the source it was projected from, and touches no other."""

    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "machine"
        seeded = machine().install(ROOT, self.tmp / "seed", python=sys.executable, env=self.env)
        self.assertTrue(seeded["saipen_runtime_ready"], seeded)
        seed = machine().runtime_home(
            self.tmp / "seed", machine().read_registration(self.tmp / "seed")
        )
        self.source = self.tmp / "source"
        shutil.copytree(seed, self.source)
        patcher = mock.patch.dict(
            os.environ,
            {ENV_ROOT: str(self.root), "USERPROFILE": self.env["USERPROFILE"], "HOME": ""},
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def upgrade(self, tree: Path) -> None:
        (tree / "BOOT.md").write_bytes((tree / "BOOT.md").read_bytes() + b"upgraded")

    def refresh(self, tree: Path):
        from saipen_engine import host_integration

        return host_integration.refresh_machine_runtime(tree)

    def test_nothing_is_created_where_no_machine_runtime_exists(self):
        self.assertIsNone(self.refresh(self.source))
        self.assertFalse(self.root.exists())

    def test_a_runtime_follows_the_source_it_was_projected_from(self):
        self.assertTrue(machine().install(self.source, python=sys.executable)["ok"])
        self.assertIsNone(self.refresh(self.source))
        self.upgrade(self.source)
        self.assertEqual(machine().status(canonical=self.source)["code"], machine().CODE_STALE)
        step = self.refresh(self.source)
        self.assertEqual(step["step"], "machine:install")
        self.assertTrue(step["ok"], step)
        self.assertEqual(machine().status(canonical=self.source)["code"], machine().CODE_READY)
        self.assertIsNone(self.refresh(self.source))

    def test_another_checkout_never_rewrites_it(self):
        self.assertTrue(machine().install(self.source, python=sys.executable)["ok"])
        other = self.tmp / "other-checkout"
        shutil.copytree(self.source, other)
        self.upgrade(other)
        before = (self.root / "registration.json").read_bytes()
        self.assertIsNone(self.refresh(other))
        self.assertEqual((self.root / "registration.json").read_bytes(), before)

    def test_the_run_that_refreshes_agent_homes_carries_it_along(self):
        import autoinject

        self.assertIsNone(autoinject.converge_machine_runtime(self.source))
        self.assertFalse(self.root.exists())
        self.assertTrue(machine().install(self.source, python=sys.executable)["ok"])
        self.assertIsNone(autoinject.machine_runtime_drift(self.source))
        self.upgrade(self.source)
        # The read-only half says so and changes nothing.
        before = (self.root / "registration.json").read_bytes()
        self.assertIn("STALE: machine runtime", autoinject.machine_runtime_drift(self.source))
        self.assertEqual((self.root / "registration.json").read_bytes(), before)
        line = autoinject.converge_machine_runtime(self.source)
        self.assertTrue(line.startswith("machine runtime refreshed"), line)
        self.assertEqual(machine().status(canonical=self.source)["code"], machine().CODE_READY)
        self.assertIsNone(autoinject.converge_machine_runtime(self.source))

    def test_the_timer_run_reports_it_and_check_counts_it(self):
        import contextlib
        import io

        import autoinject

        def run(*argv: str, drift=None, refreshed=None) -> tuple:
            printed = io.StringIO()
            with contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.object(autoinject, "TARGETS", []))
                stack.enter_context(
                    mock.patch.object(autoinject, "machine_runtime_drift", return_value=drift)
                )
                converge = stack.enter_context(
                    mock.patch.object(
                        autoinject, "converge_machine_runtime", return_value=refreshed
                    )
                )
                stack.enter_context(contextlib.redirect_stdout(printed))
                code = autoinject.main(list(argv))
            return code, printed.getvalue(), converge.called

        code, text, wrote = run("--quiet-when-fresh", refreshed="machine runtime refreshed: X")
        self.assertEqual(code, 0)
        self.assertIn("machine runtime refreshed: X", text)
        self.assertTrue(wrote)
        # `--check` reads, never refreshes, and a drifted projection is stale.
        code, text, wrote = run("--check", drift="STALE: machine runtime R (S)")
        self.assertEqual(code, 1)
        self.assertIn("STALE: machine runtime R (S)", text)
        self.assertFalse(wrote)
        self.assertEqual(run("--check")[0], 0)


class HarnessIsolationTests(unittest.TestCase):
    def test_a_fixture_never_sees_the_real_machine_runtime(self):
        from test_hermetic_env import MACHINE_ROOT, hermetic_env, no_machine_runtime

        self.assertEqual(os.environ.get(MACHINE_ROOT), no_machine_runtime())
        self.assertFalse(Path(no_machine_runtime()).exists())
        self.assertEqual(hermetic_env({})[MACHINE_ROOT], no_machine_runtime())
        self.assertEqual(hermetic_env({}, **{MACHINE_ROOT: "X:/mine"})[MACHINE_ROOT], "X:/mine")
        self.assertIsNone(machine().executing())
        self.assertIsNone(machine().launcher_path())


class LawTextTests(unittest.TestCase):
    def flat(self, name: str) -> str:
        return " ".join((ROOT / "saipen" / name).read_text(encoding="utf-8").split())

    def test_the_injected_block_names_the_machine_launcher(self):
        block = self.flat("ACTIVATION_BLOCK.md")
        self.assertIn("run `%ProgramData%\\SAI\\SAIPEN\\bin\\saipen.cmd`", block)
        self.assertIn("never clone a public copy to continue Work", block)

    def test_boot_names_the_one_stand_in(self):
        boot = self.flat("BOOT.md")
        self.assertIn("Never search or try another home", boot)
        self.assertIn("an unreadable home has one stand-in, the machine runtime", boot)

    def test_runtime_states_the_rule_and_the_refusal(self):
        runtime = self.flat("RUNTIME.md")
        for phrase in (
            "ACCESS_DENIED must not read as a dead home",
            "saipen host machine [status|install|remove]",
            "`status` answers `saipen_runtime_ready`",
            "`host repair` refreshes it",
            "`STATE.saipen_home` it projects is covered and unchanged",
            "refuses `CROSS_USER_RUNTIME_UNAVAILABLE` and never rebinds it",
        ):
            self.assertIn(phrase, runtime)

    def test_the_command_and_the_code_are_registered(self):
        self.assertIn("\\|machine`", command_reference_path(ROOT / "saipen").read_text("utf-8"))
        registry = json.loads((ROOT / "saipen" / "REGISTRY.json").read_text("utf-8-sig"))
        self.assertIn(DENIED, registry["error_codes"])


if __name__ == "__main__":
    unittest.main()
