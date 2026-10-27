"""The machine-scoped SAIPEN runtime: one read-only copy every account can run (T-1647).

The defect this ends (SRC-188, measured): a SAIPEN-managed project stayed
executable only for accounts that could read the operator's private profile.
A managed Windows account could read and write the project it was granted and
could run nothing of SAIPEN -- `STATE.saipen_home` named a path in another
user's tree, the launchers named an interpreter installed for that user alone
(`...\\AppData\\Local\\Programs\\Python\\...`), and no machine-wide interpreter
existed. The agent's only moves were to ask for an ACL, clone a public copy of
some other version, or edit BOARD by hand.

One owner, three facts:

* **Projection.** `install` copies the shipped runtime surface -- exactly the
  files `runtime_surface` digests, so the copy proves the SAME generation
  identity as its source -- into `<root>/runtime/<generation>/`, an
  interpreter into `<root>/python/<version>/` when the accounts have none of
  their own, and two relocatable launchers into `<root>/bin/`. Nothing in the
  result names a user profile.
* **Registration.** `<root>/registration.json` names the current generation,
  the protocol major and the launcher. It is the machine authority a process
  resolves instead of guessing a path.
* **Least privilege.** The root is written with inheritance cut: the installer
  and the system own it, every other account may read and execute and nothing
  else. A runtime another account can write is BROKEN, never READY.

`<root>` is `%ProgramData%\\SAI\\SAIPEN` on Windows. Other platforms report
`MACHINE_RUNTIME_UNSUPPORTED` until they have a measured layout; an explicit
`SAIPEN_MACHINE_ROOT` relocates the root for a diagnostic or a test and grants
nothing -- it only changes where THIS process looks.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import runtime_surface

SCHEMA = 1
KIND = "saipen-machine-runtime"
REGISTRATION = "registration.json"
ENV_ROOT = "SAIPEN_MACHINE_ROOT"
RUNTIME_DIR = "runtime"
PYTHON_DIR = "python"
BIN_DIR = "bin"
WINDOWS_LAUNCHER = "saipen.cmd"
POSIX_LAUNCHER = "saipen"
_REGISTRATION_MAX = 64 * 1024

CODE_READY = "MACHINE_RUNTIME_READY"
CODE_ABSENT = "MACHINE_RUNTIME_ABSENT"
CODE_STALE = "MACHINE_RUNTIME_STALE"
CODE_BROKEN = "MACHINE_RUNTIME_BROKEN"
CODE_UNSUPPORTED = "MACHINE_RUNTIME_UNSUPPORTED"
CODE_INSTALLED = "MACHINE_RUNTIME_INSTALLED"
CODE_CURRENT = "MACHINE_RUNTIME_CURRENT"
CODE_REMOVED = "MACHINE_RUNTIME_REMOVED"
CODE_FAILED = "MACHINE_RUNTIME_INSTALL_FAILED"

INSTALL_ACTION = "saipen host machine install"

#: Well-known SIDs, so nothing here depends on a localized account name.
SID_SYSTEM = "S-1-5-18"
SID_ADMINISTRATORS = "S-1-5-32-544"
SID_USERS = "S-1-5-32-545"
SID_AUTHENTICATED = "S-1-5-11"
SID_EVERYONE = "S-1-1-0"
SID_CREATOR_OWNER = "S-1-3-0"

#: SDDL aliases for the SIDs above (an ACE names either form).
_SDDL_ALIAS = {
    "SY": SID_SYSTEM,
    "BA": SID_ADMINISTRATORS,
    "BU": SID_USERS,
    "AU": SID_AUTHENTICATED,
    "WD": SID_EVERYONE,
    "CO": SID_CREATOR_OWNER,
}
#: Access-mask bits that let a principal change what the directory holds.
_WRITE_BITS = (
    0x00000002  # FILE_WRITE_DATA / add file
    | 0x00000004  # FILE_APPEND_DATA / add subdirectory
    | 0x00000010  # FILE_WRITE_EA
    | 0x00000040  # FILE_DELETE_CHILD
    | 0x00000100  # FILE_WRITE_ATTRIBUTES
    | 0x00010000  # DELETE
    | 0x00040000  # WRITE_DAC
    | 0x00080000  # WRITE_OWNER
    | 0x10000000  # GENERIC_ALL
    | 0x40000000  # GENERIC_WRITE
)
#: SDDL right mnemonics that carry one of those bits.
_WRITE_RIGHTS = frozenset({"GA", "GW", "FA", "FW", "SD", "WD", "WO", "DC", "LC", "SW", "WP", "DT"})
_ACE_RE = re.compile(r"\(([^()]*)\)")
_RUNTIME_REL_RE = re.compile(rf"{RUNTIME_DIR}/[0-9a-f]{{16}}")

#: Interpreter library members the engine never loads; left out of a bundle.
_PYTHON_LIB_SKIP = frozenset(
    {"site-packages", "test", "idlelib", "tkinter", "ensurepip", "turtledemo", "lib2to3"}
)
_PYTHON_DLL_SKIP_PREFIXES = ("tcl", "tk", "_tkinter")


class MachineRuntimeError(RuntimeError):
    """An install step that could not be completed; the message is the diagnostic."""


# ------------------------------------------------------------------ location


def default_root(env: dict | None = None) -> Path | None:
    """Where the machine runtime lives on this host, or None when unsupported."""
    source = os.environ if env is None else env
    explicit = str(source.get(ENV_ROOT) or "").strip()
    if explicit:
        return Path(explicit)
    if os.name != "nt":
        return None
    base = str(source.get("ProgramData") or source.get("ALLUSERSPROFILE") or "").strip()
    return Path(base or r"C:\ProgramData") / "SAI" / "SAIPEN"


def read_registration(root: Path | str | None) -> dict | None:
    """The registration under `root`, or None. Bounded; never raises."""
    if root is None:
        return None
    path = Path(root) / REGISTRATION
    try:
        if not path.is_file() or path.stat().st_size > _REGISTRATION_MAX:
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("kind") != KIND:
        return None
    if payload.get("schema") != SCHEMA or not isinstance(payload.get("runtime"), str):
        return None
    # The runtime is a generation directory of this root and nothing else: a
    # registration never points the launcher's engine anywhere it likes.
    if not _RUNTIME_REL_RE.fullmatch(payload["runtime"]):
        return None
    return payload


def runtime_home(root: Path | str, registration: dict) -> Path:
    """The engine home the registration names (flattened layout)."""
    return Path(root) / str(registration.get("runtime") or "")


def _same_dir(left: Path | str, right: Path | str) -> bool:
    def norm(value: Path | str) -> str:
        return os.path.normcase(os.path.abspath(str(value)))

    return norm(left) == norm(right)


def executing(engine_root: Path | str | None = None, env: dict | None = None) -> dict | None:
    """The registration that covers the engine running this call, or None.

    A path fact, cheap enough for every command: the running engine sits where
    the registration says the current runtime is. Whether that runtime's bytes
    still prove the registered generation is `status`'s question.
    """
    root = default_root(env)
    registration = read_registration(root)
    if root is None or registration is None:
        return None
    here = Path(engine_root) if engine_root else Path(__file__).resolve().parents[2]
    if not _same_dir(here, runtime_home(root, registration)):
        return None
    return {**registration, "root": str(root), "home": str(runtime_home(root, registration))}


def current_generation_for(home: object, env: dict | None = None) -> Path | None:
    """The CURRENT generation directory when `home` names any generation
    directory of the registered machine runtime, else None (T-1743).

    Generation directories are versions of one stable install: the root's
    registration says which is current and older ones are pruned on upgrade.
    A project that recorded one of them recorded the machine runtime, not a
    version of it, so it follows the registration instead of dying with it.
    """
    text = str(home or "").strip()
    if not text:
        return None
    root = default_root(env)
    registration = read_registration(root)
    if root is None or registration is None:
        return None
    try:
        parent = Path(os.path.abspath(text)).parent
    except (OSError, ValueError):
        return None
    if not _same_dir(parent, Path(root) / RUNTIME_DIR):
        return None
    current = runtime_home(root, registration)
    return current if current.is_dir() else None


def projects(registration: dict | None, home: object) -> bool:
    """Was this machine runtime projected from `home`?

    A machine runtime stands in for ONE source: the install it was projected
    from, and the agent homes the installing operator proved at install time
    are projections of that same source (`projected_homes`, T-1743). A
    project whose recorded home is some other install is not this runtime's
    to serve -- that would be a substitution, whatever the versions say. A
    comparison of recorded paths: the home itself is, by the very case this
    exists for, unreadable.
    """
    recorded = str((registration or {}).get("source_root") or "").strip()
    wanted = str(home or "").strip()
    if not (recorded and wanted):
        return False
    if _same_dir(recorded, wanted):
        return True
    root = str((registration or {}).get("root") or "").strip()
    if root and _same_dir(Path(os.path.abspath(wanted)).parent, Path(root) / RUNTIME_DIR):
        # One of this runtime's own generations (current_generation_for).
        return True
    homes = (registration or {}).get("projected_homes") or ()
    return isinstance(homes, list) and any(
        isinstance(item, str) and item.strip() and _same_dir(item, wanted) for item in homes
    )


def _expand_surface(surface: str, env: dict | None) -> str | None:
    """A registry skill surface for the installing account, or None when it
    names a variable this environment does not set (no path on this host)."""
    names = os.environ if env is None else env
    text = surface
    if text.startswith("~"):
        profile = names.get("USERPROFILE") or names.get("HOME")
        if not profile:
            return None
        text = profile + text[1:]

    def value(match: re.Match) -> str:
        found = names.get(match.group(1) or match.group(2) or match.group(3))
        return found if found is not None else match.group(0)

    text = re.sub(r"\$\{(\w+)\}|\$(\w+)|%(\w+)%", value, text)
    return None if "$" in text or re.search(r"%\w+%", text) else text


def projected_homes(origin: Path | str, env: dict | None = None) -> list[str]:
    """The agent homes the installing account can PROVE follow `origin`.

    A home qualifies only when it is one of the adapter registry's declared
    skill surfaces for this account AND its own install stamp
    (`.saipen_runtime.json`) names `origin` as its canonical source. Read by
    the operator at install time -- the one moment an account that can read
    those homes is present -- so a managed account that cannot read them later
    can still be told, truthfully, that this runtime serves them.
    """
    source = Path(origin)
    try:
        registry = json.loads(
            (source / "extensions" / "adapters" / "registry.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return []
    found: dict[str, str] = {}
    for adapter in registry.get("adapters") or []:
        for surface in (adapter or {}).get("skill_surfaces") or []:
            expanded = _expand_surface(surface, env) if isinstance(surface, str) else None
            if not expanded:
                continue
            home = Path(expanded)
            try:
                stamp = json.loads((home / ".saipen_runtime.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            declared = str((stamp or {}).get("canonical_source_root") or "").strip()
            if declared and _same_dir(declared, source) and not _same_dir(home, source):
                found.setdefault(os.path.normcase(os.path.abspath(home)), os.path.abspath(home))
    return sorted(found.values())


# ---------------------------------------------------------------------- ACL


def _sddl(path: Path) -> str | None:
    """The DACL of `path` as SDDL, or None where the platform has none."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        descriptor = ctypes.c_void_p()
        # SE_FILE_OBJECT = 1, DACL_SECURITY_INFORMATION = 4
        failed = advapi32.GetNamedSecurityInfoW(
            ctypes.c_wchar_p(str(path)), 1, 4, None, None, None, None, ctypes.byref(descriptor)
        )
        if failed or not descriptor:
            return None
        try:
            text = ctypes.c_wchar_p()
            ok = advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW(
                descriptor, 1, 4, ctypes.byref(text), None
            )
            if not ok or not text.value:
                return None
            value = str(text.value)
            kernel32.LocalFree(ctypes.cast(text, wintypes.HLOCAL))
            return value
        finally:
            kernel32.LocalFree(ctypes.cast(descriptor, wintypes.HLOCAL))
    except (OSError, AttributeError, ValueError):
        return None


def _owner(path: Path) -> str | None:
    """The owner of `path` as a SID string, or None when it cannot be read
    (and on a platform this module sets no access lists on)."""
    if os.name != "nt":
        return None
    try:
        import ctypes

        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.LocalFree.argtypes = (ctypes.c_void_p,)
        advapi32.ConvertSidToStringSidW.argtypes = (
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_wchar_p),
        )
        sid, descriptor = ctypes.c_void_p(), ctypes.c_void_p()
        # SE_FILE_OBJECT = 1, OWNER_SECURITY_INFORMATION = 1
        failed = advapi32.GetNamedSecurityInfoW(
            ctypes.c_wchar_p(str(path)),
            1,
            1,
            ctypes.byref(sid),
            None,
            None,
            None,
            ctypes.byref(descriptor),
        )
        if failed or not descriptor:
            return None
        try:
            text = ctypes.c_wchar_p()
            if not advapi32.ConvertSidToStringSidW(sid, ctypes.byref(text)) or not text.value:
                return None
            value = str(text.value)
            kernel32.LocalFree(ctypes.cast(text, ctypes.c_void_p))
            return value
        finally:
            kernel32.LocalFree(descriptor)
    except (OSError, AttributeError, ValueError):
        return None


def foreign_owners(root: Path, trusted: set, *, limit: int = 3) -> list[str]:
    """Entries of `root`, itself first, that none of `trusted` owns.

    The owner of an object may rewrite its access list whatever that list
    says. A root, or one file in it, that another account created before the
    install is therefore that account's to re-grant at any moment -- and the
    access list alone reads clean until it does. Unreadable is not proven:
    it is reported, never assumed. Bounded: the first few are the diagnosis.
    """
    if os.name != "nt":
        return []
    found: list[str] = []

    def judge(path: Path, shown: str) -> bool:
        owner = _owner(path)
        if owner is None or owner not in trusted:
            found.append(f"{shown} ({owner or 'owner unreadable'})")
        return len(found) >= limit

    if judge(root, "the runtime root"):
        return found
    for folder, folders, files in os.walk(root):
        for name in (*folders, *files):
            path = Path(folder) / name
            if judge(path, str(path.relative_to(root))):
                return found
    return found


def _trusted_owners(installer: str | None) -> set:
    trusted = {SID_SYSTEM, SID_ADMINISTRATORS}
    if installer:
        trusted.add(installer)
    return trusted


def _unanchored_installer(installer: str | None, canonical: Path | str | None) -> str | None:
    """Why the installer the registration names is nobody's to trust, or None.

    The registration is a file in the runtime: an account that reached the
    root first can write one that names itself. So the name counts only when
    it is an account the asker already relies on -- the asker, the owner of
    the install the asker is running (`canonical`), Administrators or SYSTEM.
    """
    if os.name != "nt" or not installer:
        return None
    anchors = {SID_SYSTEM, SID_ADMINISTRATORS}
    asker = _current_sid()
    if asker:
        anchors.add(asker)
    if canonical is not None:
        owner = _owner(Path(canonical))
        if owner:
            anchors.add(owner)
    if installer in anchors:
        return None
    return f"the machine runtime was installed by another account ({installer})"


def _current_sid() -> str | None:
    """The SID of the account running this process, read from its own token:
    no program is looked up on PATH to answer who is asking."""
    if os.name != "nt":
        return None
    try:
        import ctypes

        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle, dword = ctypes.c_void_p, ctypes.c_ulong
        kernel32.GetCurrentProcess.restype = handle
        kernel32.CloseHandle.argtypes = (handle,)
        kernel32.LocalFree.argtypes = (handle,)
        advapi32.OpenProcessToken.argtypes = (handle, dword, ctypes.POINTER(handle))
        advapi32.GetTokenInformation.argtypes = (
            handle,
            ctypes.c_int,
            handle,
            dword,
            ctypes.POINTER(dword),
        )
        advapi32.ConvertSidToStringSidW.argtypes = (handle, ctypes.POINTER(ctypes.c_wchar_p))
        token = handle()
        # TOKEN_QUERY = 0x0008
        if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
            return None
        try:
            size = dword(0)
            advapi32.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))  # TokenUser
            data = ctypes.create_string_buffer(size.value)
            if not advapi32.GetTokenInformation(token, 1, data, size, ctypes.byref(size)):
                return None
            text = ctypes.c_wchar_p()
            sid = handle.from_buffer(data).value
            if not advapi32.ConvertSidToStringSidW(sid, ctypes.byref(text)) or not text.value:
                return None
            value = str(text.value)
            kernel32.LocalFree(ctypes.cast(text, handle))
            return value
        finally:
            kernel32.CloseHandle(token)
    except (OSError, AttributeError, ValueError):
        return None


def writable_by_others(sddl: str | None, owner_sid: str | None) -> list[str]:
    """Principals other than the system, administrators and the owner that an
    ALLOW entry lets change the directory. Empty means least privilege holds.

    Pure: it reads an SDDL string, so the rule is tested without touching a
    real ACL. Inherit-only entries count -- they are the rights a child gets.
    """
    if not sddl or "D:" not in sddl:
        return []
    trusted = {SID_SYSTEM, SID_ADMINISTRATORS, SID_CREATOR_OWNER}
    if owner_sid:
        trusted.add(owner_sid)
    found: list[str] = []
    for body in _ACE_RE.findall(sddl.split("D:", 1)[1]):
        fields = body.split(";")
        if len(fields) < 6 or fields[0] != "A":
            continue
        principal = _SDDL_ALIAS.get(fields[5], fields[5])
        if principal in trusted:
            continue
        rights = fields[2]
        if rights.lower().startswith("0x"):
            try:
                writes = bool(int(rights, 16) & _WRITE_BITS)
            except ValueError:
                writes = True
        else:
            writes = any(rights[i : i + 2] in _WRITE_RIGHTS for i in range(0, len(rights), 2))
        if writes and principal not in found:
            found.append(principal)
    return found


def harden(root: Path, owner_sid: str | None = None) -> list[str]:
    """Cut inheritance on `root` and grant read/execute to other accounts only.

    Returns the problems that remain (empty on success, and on a platform with
    no ACLs to set). Uses SIDs so a localized system answers the same.
    """
    if os.name != "nt":
        return []
    owner = owner_sid or _current_sid()
    grants = [f"*{SID_SYSTEM}:(OI)(CI)F", f"*{SID_ADMINISTRATORS}:(OI)(CI)F"]
    if owner:
        grants.append(f"*{owner}:(OI)(CI)F")
    grants.append(f"*{SID_USERS}:(OI)(CI)RX")
    # The root alone carries explicit entries; everything under it inherits.
    # Applying the same entries to every child would strip a file's inherited
    # access and then fail to grant container flags to it, leaving the file
    # readable by nobody.
    steps = [["icacls", str(root), "/inheritance:r", "/grant:r", *grants, "/Q"]]
    if any(root.iterdir()):
        steps.append(["icacls", str(root / "*"), "/reset", "/T", "/C", "/Q"])
    for argv in steps:
        try:
            proc = subprocess.run(
                argv, capture_output=True, stdin=subprocess.DEVNULL, timeout=900, check=False
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return [f"the access list of {root} could not be set: {exc}"]
        if proc.returncode != 0:
            tail = proc.stdout.decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
            return [f"icacls refused to set the access list of {root}: {tail[0][:160]}"]
    return [
        f"{principal} can still write under {root}"
        for principal in writable_by_others(_sddl(root), owner)
    ]


# ------------------------------------------------------------------ launchers


def render_launchers(runtime_rel: str, python_rel: str | None, python_abs: str | None) -> dict:
    """The bytes of both launchers. Relocatable: every path is relative to the
    launcher's own directory, except an interpreter the installer was told to
    use where it already is."""
    engine = f"{runtime_rel}/tools/saipen.py"
    if python_rel:
        win_python = '"%~dp0..\\' + python_rel.replace("/", "\\") + '"'
        sh_python = '"$here/../' + python_rel + '"'
    else:
        win_python = '"' + str(python_abs) + '"'
        sh_python = '"' + str(python_abs).replace("\\", "/") + '"'
    windows = "@echo off\r\n" + win_python + ' "%~dp0..\\' + engine.replace("/", "\\") + '" %*\r\n'
    posix = (
        "#!/bin/sh\n"
        'here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n'
        "exec " + sh_python + ' "$here/../' + engine + '" "$@"\n'
    )
    return {WINDOWS_LAUNCHER: windows.encode("utf-8"), POSIX_LAUNCHER: posix.encode("utf-8")}


def _launcher_facts(root: Path, registration: dict) -> dict:
    expected = render_launchers(
        str(registration.get("runtime")),
        registration.get("python") if registration.get("python_bundled") else None,
        registration.get("python") if not registration.get("python_bundled") else None,
    )
    problems = []
    for name, payload in expected.items():
        path = root / BIN_DIR / name
        try:
            if path.read_bytes() != payload:
                problems.append(f"{BIN_DIR}/{name} does not name the registered runtime")
        except OSError:
            problems.append(f"{BIN_DIR}/{name} is missing")
    return {
        "windows": str(root / BIN_DIR / WINDOWS_LAUNCHER),
        "posix": str(root / BIN_DIR / POSIX_LAUNCHER),
        "ok": not problems,
        "problems": problems,
    }


# ---------------------------------------------------------------- interpreter


def _python_tag() -> str:
    bits = "64" if sys.maxsize > 2**32 else "32"
    return "{}.{}.{}-{}".format(*sys.version_info[:3], bits)


def _under(path: Path, parent: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(os.path.abspath(parent))
        return True
    except ValueError:
        return False


def interpreter_is_private(executable: str | None = None, env: dict | None = None) -> bool:
    """Does the running interpreter live in a user profile other accounts cannot
    read? The measured case: a per-user install under `%LOCALAPPDATA%`."""
    source = os.environ if env is None else env
    target = Path(executable or sys.executable)
    for key in ("USERPROFILE", "HOME"):
        profile = str(source.get(key) or "").strip()
        if profile and _under(target, Path(profile)):
            return True
    return False


def _bundle_python(root: Path) -> str:
    """Copy the base interpreter's standard library and binaries; return its
    registered relative path. Idempotent: an existing complete copy is kept."""
    base = Path(sys.base_prefix)
    name = "python.exe" if os.name == "nt" else Path(sys.executable).name
    if not (base / name).is_file() or not (base / "Lib" / "os.py").is_file():
        raise MachineRuntimeError(
            f"the running interpreter under {base} is not a layout that can be copied; "
            "pass --python with an interpreter every account can execute"
        )
    target = root / PYTHON_DIR / _python_tag()
    relative = f"{PYTHON_DIR}/{_python_tag()}/{name}"
    if (target / name).is_file() and (target / "Lib" / "os.py").is_file():
        return relative
    staging = target.with_name(target.name + f".staging-{os.getpid()}")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        for entry in sorted(base.iterdir()):
            if entry.is_file() and entry.suffix.lower() in (".exe", ".dll", ".txt"):
                if entry.name.lower() == "news.txt":
                    continue
                shutil.copy2(entry, staging / entry.name)
        dlls = base / "DLLs"
        if dlls.is_dir():
            (staging / "DLLs").mkdir()
            for entry in sorted(dlls.iterdir()):
                if entry.is_file() and not entry.name.lower().startswith(_PYTHON_DLL_SKIP_PREFIXES):
                    shutil.copy2(entry, staging / "DLLs" / entry.name)

        def skip(directory: str, names: list[str]) -> set[str]:
            top = Path(directory) == base / "Lib"
            return {
                item
                for item in names
                if item == "__pycache__" or (top and item in _PYTHON_LIB_SKIP)
            }

        shutil.copytree(base / "Lib", staging / "Lib", ignore=skip)
        os.replace(staging, target)
    except OSError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise MachineRuntimeError(f"the interpreter could not be copied: {exc}") from exc
    return relative


def _python_runs(executable: Path) -> str | None:
    """None when `executable` imports what the engine needs; else why not."""
    try:
        proc = subprocess.run(
            [str(executable), "-I", "-c", "import ctypes, hashlib, json, sqlite3, subprocess"],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"{executable} could not be started: {exc}"
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or ["no output"]
        return f"{executable} cannot import the standard library: {tail[0][:160]}"
    return None


# -------------------------------------------------------------------- status


def _version(home: Path) -> str | None:
    try:
        return (home / "VERSION").read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def status(
    root: Path | str | None = None,
    *,
    canonical: Path | str | None = None,
    env: dict | None = None,
    prove: bool = True,
) -> dict:
    """What the machine runtime is, from its own bytes. Read-only.

    `canonical` is the runtime the caller holds as current (the operator's
    source); with it the answer can be STALE. An account that cannot read the
    source asks without it and learns whether the projection is intact.
    `saipen_runtime_ready` is the one fact an account manager consumes.
    """
    base = Path(root) if root is not None else default_root(env)
    view: dict = {
        "ok": False,
        "code": CODE_UNSUPPORTED,
        "root": str(base) if base else None,
        "saipen_runtime_ready": False,
        "reasons": [],
        "action": None,
    }
    if base is None:
        view["reasons"] = ["no machine runtime location is defined for this platform"]
        return view
    registration = read_registration(base)
    if registration is None:
        present = (base / REGISTRATION).exists()
        view.update(
            code=CODE_BROKEN if present else CODE_ABSENT,
            reasons=[
                "the registration is unreadable or of another schema"
                if present
                else "no machine runtime is installed"
            ],
            action=INSTALL_ACTION,
        )
        return view
    home = runtime_home(base, registration)
    reasons: list[str] = []
    generation = runtime_surface.runtime_generation_identity(home) if prove else None
    if not home.is_dir():
        reasons.append(f"the registered runtime directory is missing: {registration['runtime']}")
    elif prove and generation is None:
        reasons.append("the runtime cannot prove any generation (files missing or unreadable)")
    elif prove and generation != registration.get("generation"):
        reasons.append("the runtime bytes are not the registered generation")
    launcher = _launcher_facts(base, registration)
    reasons.extend(launcher["problems"])
    python_path = (
        base / str(registration.get("python"))
        if registration.get("python_bundled")
        else Path(str(registration.get("python") or ""))
    )
    python_ok = bool(registration.get("python")) and python_path.is_file()
    if not python_ok:
        reasons.append(f"the registered interpreter is missing: {registration.get('python')}")
    elif registration.get("python_bundled") and not _under(python_path, base):
        python_ok = False
        reasons.append("the registered interpreter is not inside the runtime root")
    elif not registration.get("python_bundled") and interpreter_is_private(str(python_path), env):
        reasons.append(
            f"the registered interpreter is inside a user profile ({python_path}); "
            "other accounts cannot execute it"
        )
    sddl = _sddl(base)
    installer = registration.get("installed_by")
    writers = writable_by_others(sddl, installer)
    reasons.extend(f"{principal} can write under the runtime root" for principal in writers)
    # Whoever owns an entry may rewrite its access list, so the list is only
    # as good as the owners; and the installer the registration names is one
    # more account's claim until something the asker already trusts backs it.
    owners = foreign_owners(base, _trusted_owners(installer)) if prove else []
    reasons.extend(
        f"{entry} is owned by an account that can rewrite its access list" for entry in owners
    )
    stranger = _unanchored_installer(installer, canonical)
    if stranger:
        reasons.append(stranger)
    view.update(
        registration=registration,
        home=str(home),
        generation=registration.get("generation"),
        generation_proven=bool(prove and generation == registration.get("generation")),
        saipen_version=registration.get("saipen_version"),
        state_schema=registration.get("state_schema"),
        launcher=launcher,
        python={
            "path": str(python_path),
            "bundled": bool(registration.get("python_bundled")),
            "ok": python_ok,
        },
        acl={
            "checked": sddl is not None,
            "writable_by": writers,
            "foreign_owners": owners,
            "installed_by": installer,
        },
        source="MACHINE_RUNTIME",
    )
    if reasons:
        view.update(code=CODE_BROKEN, reasons=reasons, action=INSTALL_ACTION)
        return view
    if canonical is not None:
        wanted = runtime_surface.runtime_generation_identity(canonical)
        view["canonical_generation"] = wanted
        view["current"] = wanted is not None and wanted == registration.get("generation")
        if not view["current"]:
            view.update(
                code=CODE_STALE,
                reasons=["the machine runtime is not the generation of the canonical source"],
                action=INSTALL_ACTION,
            )
            return view
    view.update(ok=True, code=CODE_READY, saipen_runtime_ready=True)
    return view


# ------------------------------------------------------------------- install


def _project_surface(source: Path, target: Path) -> None:
    """Copy the shipped surface of `source` into `target`, flattened."""
    manifest_path, _source_layout = runtime_surface._layout(source)
    for declared, path in runtime_surface.runtime_surface_items(source):
        landing = target / runtime_surface.installed_relpath(declared)
        landing.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, landing)
    shutil.copyfile(manifest_path, target / runtime_surface.MANIFEST_NAME)
    for name in ("VERSION",):
        extra = source / name
        if extra.is_file() and not (target / name).exists():
            shutil.copyfile(extra, target / name)


def _write_atomic(path: Path, payload: bytes) -> None:
    staging = path.with_name(path.name + f".{os.getpid()}.staging")
    staging.write_bytes(payload)
    os.replace(staging, path)


def _state_schema(home: Path) -> int | None:
    try:
        schema = json.loads(
            (home / "extensions" / "schemas" / "state.schema.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    value = schema.get("x-current-schema-version")
    return value if isinstance(value, int) else None


def install(
    source: Path | str,
    root: Path | str | None = None,
    *,
    python: str | None = None,
    bundle_python: bool | None = None,
    env: dict | None = None,
    clock=time.time,
) -> dict:
    """Project `source` as the machine runtime and register it. Idempotent.

    Order is crash-safe: a new generation and a new interpreter are complete
    directories before anything names them, the launchers move in one replace
    each, and the registration is written last. The previous generation stays
    on disk as the rollback target; older ones are removed.
    """
    base = Path(root) if root is not None else default_root(env)
    if base is None:
        return {
            "ok": False,
            "code": CODE_UNSUPPORTED,
            "detail": "no machine runtime location is defined for this platform",
        }
    origin = Path(source)
    try:
        generation = runtime_surface.require_runtime_generation_identity(origin)
    except (OSError, RuntimeError, ValueError) as exc:
        return {
            "ok": False,
            "code": CODE_FAILED,
            "detail": f"the source cannot prove a runtime generation: {exc}",
        }
    if _under(origin, base):
        # Run from its own launcher it would name itself as its source, and
        # nothing would follow the operator's install any more.
        return {
            "ok": False,
            "code": CODE_FAILED,
            "root": str(base),
            "detail": "the source is the machine runtime itself; install it from the SAIPEN "
            "home it projects",
        }
    previous = read_registration(base)
    owner = _current_sid()
    tag = generation.split(":", 1)[-1][:16]
    runtime_rel = f"{RUNTIME_DIR}/{tag}"
    target = base / RUNTIME_DIR / tag
    try:
        base.mkdir(parents=True, exist_ok=True)
        # Before a byte goes in: a root another account made is that account's
        # to re-grant after any hardening, so it is not projected into.
        taken = foreign_owners(base, _trusted_owners(owner), limit=1)
        if taken and taken[0].startswith("the runtime root"):
            raise MachineRuntimeError(
                f"{base} exists and is not this installer's: {taken[0]}; "
                "remove that directory, then install again"
            )
        problems = harden(base, owner)
        if problems:
            raise MachineRuntimeError("; ".join(problems))
        if runtime_surface.runtime_generation_identity(target) != generation:
            staging = target.with_name(target.name + f".staging-{os.getpid()}")
            shutil.rmtree(staging, ignore_errors=True)
            shutil.rmtree(target, ignore_errors=True)
            staging.mkdir(parents=True)
            _project_surface(origin, staging)
            if runtime_surface.runtime_generation_identity(staging) != generation:
                shutil.rmtree(staging, ignore_errors=True)
                raise MachineRuntimeError(
                    "the projected runtime does not prove the source generation"
                )
            os.replace(staging, target)
        bundled = interpreter_is_private(env=env) if bundle_python is None else bundle_python
        if python:
            bundled = False
            python_value = str(Path(python))
            python_path = Path(python_value)
        elif bundled:
            python_value = _bundle_python(base)
            python_path = base / python_value
        else:
            python_value = str(Path(sys.executable))
            python_path = Path(python_value)
        fault = _python_runs(python_path)
        if fault:
            raise MachineRuntimeError(fault)
        (base / BIN_DIR).mkdir(exist_ok=True)
        launchers = render_launchers(
            runtime_rel, python_value if bundled else None, None if bundled else python_value
        )
        for name, payload in launchers.items():
            _write_atomic(base / BIN_DIR / name, payload)
        registration = {
            "schema": SCHEMA,
            "kind": KIND,
            "generation": generation,
            "runtime": runtime_rel,
            "saipen_version": _version(target),
            "state_schema": _state_schema(target),
            "python": python_value,
            "python_bundled": bool(bundled),
            "launcher": {
                "windows": f"{BIN_DIR}/{WINDOWS_LAUNCHER}",
                "posix": f"{BIN_DIR}/{POSIX_LAUNCHER}",
            },
            "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(clock())),
            "installed_by": owner,
            # The source this projection follows: `host repair` refreshes the
            # machine runtime only from here, so another checkout or a test
            # tree at another path never rewrites it.
            "source_root": os.path.abspath(str(origin)),
            # T-1743: injector homes proven to follow the same source; the
            # projects() test serves a project that records one of them.
            "projected_homes": projected_homes(origin, env),
            "previous": (
                {key: previous.get(key) for key in ("generation", "runtime", "saipen_version")}
                if previous and previous.get("generation") != generation
                else (previous or {}).get("previous")
            ),
        }
        body = json.dumps(registration, indent=2, sort_keys=True) + "\n"
        _write_atomic(base / REGISTRATION, body.encode("utf-8"))
        keep = {tag}
        kept_previous = str((registration.get("previous") or {}).get("runtime") or "")
        if kept_previous:
            keep.add(kept_previous.rsplit("/", 1)[-1])
        for entry in (base / RUNTIME_DIR).iterdir():
            if entry.is_dir() and entry.name not in keep:
                shutil.rmtree(entry, ignore_errors=True)
        problems = harden(base, owner)
        if problems:
            raise MachineRuntimeError("; ".join(problems))
    except (OSError, MachineRuntimeError) as exc:
        return {"ok": False, "code": CODE_FAILED, "root": str(base), "detail": str(exc)}
    unchanged = bool(previous) and previous.get("generation") == generation
    report = status(base, canonical=origin, env=env)
    return {
        **report,
        "ok": report.get("code") == CODE_READY,
        "code": (
            (CODE_CURRENT if unchanged else CODE_INSTALLED)
            if report.get("code") == CODE_READY
            else report.get("code")
        ),
        "changed": not unchanged,
    }


def follows(source: Path | str, root: Path | str | None = None, env: dict | None = None) -> bool:
    """Is the installed machine runtime the projection of `source`?"""
    base = Path(root) if root is not None else default_root(env)
    registration = read_registration(base)
    recorded = str((registration or {}).get("source_root") or "")
    return bool(recorded) and _same_dir(recorded, source)


def launcher_path(root: Path | str | None = None, env: dict | None = None) -> str | None:
    """The launcher of an installed machine runtime for this platform's shell,
    or None when none is registered. A fact for a diagnostic to name."""
    base = Path(root) if root is not None else default_root(env)
    if base is None or read_registration(base) is None:
        return None
    return str(base / BIN_DIR / (WINDOWS_LAUNCHER if os.name == "nt" else POSIX_LAUNCHER))


def remove(
    root: Path | str | None = None,
    *,
    env: dict | None = None,
    engine_root: Path | str | None = None,
) -> dict:
    """Delete the machine runtime. Only a directory that carries a registration
    of this kind is removed: a wrong path is refused, never emptied -- and not
    by the runtime itself, which would delete the interpreter it is running."""
    base = Path(root) if root is not None else default_root(env)
    if base is None:
        return {"ok": False, "code": CODE_UNSUPPORTED, "detail": "no machine runtime location"}
    if not base.exists():
        return {"ok": True, "code": CODE_ABSENT, "root": str(base), "removed": False}
    here = Path(engine_root) if engine_root else Path(__file__).resolve().parents[2]
    if _under(here, base):
        return {
            "ok": False,
            "code": CODE_FAILED,
            "root": str(base),
            "detail": "the machine runtime does not remove itself; remove it from the SAIPEN "
            "home it projects",
        }
    if read_registration(base) is None:
        return {
            "ok": False,
            "code": CODE_BROKEN,
            "root": str(base),
            "detail": "no machine runtime registration here; nothing was removed",
        }
    with contextlib.suppress(OSError):
        (base / REGISTRATION).unlink()
    shutil.rmtree(base, ignore_errors=True)
    return {
        "ok": not base.exists(),
        "code": CODE_REMOVED if not base.exists() else CODE_BROKEN,
        "root": str(base),
        "removed": not base.exists(),
    }


__all__ = [
    "CODE_ABSENT",
    "CODE_BROKEN",
    "CODE_CURRENT",
    "CODE_FAILED",
    "CODE_INSTALLED",
    "CODE_READY",
    "CODE_REMOVED",
    "CODE_STALE",
    "CODE_UNSUPPORTED",
    "ENV_ROOT",
    "INSTALL_ACTION",
    "MachineRuntimeError",
    "default_root",
    "executing",
    "follows",
    "foreign_owners",
    "harden",
    "install",
    "interpreter_is_private",
    "launcher_path",
    "projects",
    "read_registration",
    "remove",
    "render_launchers",
    "runtime_home",
    "status",
    "writable_by_others",
]
