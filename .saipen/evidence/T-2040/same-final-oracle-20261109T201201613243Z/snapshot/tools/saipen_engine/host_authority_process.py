"""OS-derived process identity: who is on the other end of the authority socket.

The host-authority broker authenticates a client by asking the OPERATING SYSTEM
who that client is -- its image, its command line, its start time and its
parent chain -- and by trusting nothing the client says about itself. That
distinction is the whole point of this module. A request may carry a project, a
session, a host name and a claimed adapter identity, and every one of those
fields is a string the caller chose; process identity is not, because the
caller cannot set it.

This module supplies identity only. It proves nothing by itself, grants nothing
and authenticates nobody: `host_authority_identity` decides what a chain proves,
and the broker decides what to do about it.

Every function here is bounded and read-only. Nothing spawns, kills, signals or
writes; an unreadable process is reported as unknown rather than guessed at, and
an unknown client is a client the broker refuses. Failures never raise: a
diagnostic that crashes is worse than one that says "unavailable".
"""

from __future__ import annotations

import contextlib
import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

#: Buffer bound for one image path. Windows' own maximum is far below this.
IMAGE_MAX = 32768
#: Bound for one command line read from another process.
COMMAND_LINE_MAX = 65536

#: Windows access right: enough to read image, times and command line.
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_TH32CS_SNAPPROCESS = 0x2
_INVALID_HANDLE_VALUE = -1
_PROCESS_BASIC_INFORMATION = 0
_PROCESS_COMMAND_LINE_INFORMATION = 60


@dataclass(frozen=True)
class ProcessFact:
    """One observed process. A field is None when the platform would not say."""

    pid: int
    ppid: int | None
    image: str | None
    name: str | None
    #: The process's own argument vector, parsed by the platform's rules.
    argv: tuple[str, ...] | None = None
    #: A monotonic-per-boot start stamp; only ever compared with another one.
    created: int | None = None


def _normalize_image(raw: str) -> str:
    return raw.replace("\\", "/").strip().lower()


def _basename(image: str | None) -> str | None:
    if not image:
        return None
    tail = image.rsplit("/", 1)[-1]
    return tail or None


def _strip_exe(name: str) -> str:
    return name[:-4] if name.endswith(".exe") else name


def split_windows_command_line(text: str) -> list[str]:
    """Split a Windows command line the way the C runtime does.

    The program name is read by its own rule (a quoted span or up to the first
    whitespace, with no backslash escaping); every later argument follows the
    documented backslash-and-quote rule. Pure, so it behaves identically on
    every platform and can be tested without a process.
    """
    args: list[str] = []
    length = len(text)
    index = 0
    while index < length and text[index] in " \t":
        index += 1
    if index >= length:
        return args
    if text[index] == '"':
        end = text.find('"', index + 1)
        if end < 0:
            end = length
        args.append(text[index + 1 : end])
        index = min(end + 1, length)
    else:
        start = index
        while index < length and text[index] not in " \t":
            index += 1
        args.append(text[start:index])
    while True:
        while index < length and text[index] in " \t":
            index += 1
        if index >= length:
            break
        current: list[str] = []
        quoted = False
        while index < length:
            char = text[index]
            if char == "\\":
                run = 0
                while index < length and text[index] == "\\":
                    run += 1
                    index += 1
                if index < length and text[index] == '"':
                    current.append("\\" * (run // 2))
                    if run % 2:
                        current.append('"')
                        index += 1
                else:
                    current.append("\\" * run)
            elif char == '"':
                if quoted and index + 1 < length and text[index + 1] == '"':
                    current.append('"')
                    index += 2
                else:
                    quoted = not quoted
                    index += 1
            elif char in " \t" and not quoted:
                break
            else:
                current.append(char)
                index += 1
        args.append("".join(current))
    return args


# ---------------------------------------------------------------- Windows


def _windows_api():
    """The kernel32/ntdll calls this module needs, or None off Windows."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:  # pragma: no cover - a platform without ctypes
        return None
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    except (AttributeError, OSError):
        return None

    class _PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    class _BASIC(ctypes.Structure):
        _fields_ = [
            ("ExitStatus", ctypes.c_void_p),
            ("PebBaseAddress", ctypes.c_void_p),
            ("AffinityMask", ctypes.c_void_p),
            ("BasePriority", ctypes.c_void_p),
            ("UniqueProcessId", ctypes.c_void_p),
            ("InheritedFromUniqueProcessId", ctypes.c_void_p),
        ]

    class _UNICODE_STRING(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.USHORT),
            ("MaximumLength", wintypes.USHORT),
            ("Buffer", ctypes.c_void_p),
        ]

    try:
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.GetProcessTimes.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        ]
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
        kernel32.Process32FirstW.restype = wintypes.BOOL
        kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
        kernel32.Process32NextW.restype = wintypes.BOOL
    except (AttributeError, TypeError):
        return None
    query = None
    try:
        ntdll = ctypes.WinDLL("ntdll")
        query = ntdll.NtQueryInformationProcess
        query.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.ULONG,
            ctypes.POINTER(wintypes.ULONG),
        ]
        query.restype = ctypes.c_long
    except (AttributeError, OSError, TypeError):
        query = None
    return {
        "ctypes": ctypes,
        "wintypes": wintypes,
        "kernel32": kernel32,
        "entry": _PROCESSENTRY32W,
        "basic": _BASIC,
        "ustring": _UNICODE_STRING,
        "query": query,
    }


_WINDOWS = _windows_api()


def _windows_snapshot() -> list[tuple[int, int, str]]:
    """(pid, parent pid, exe name) for every process, or [] when unreadable."""
    if _WINDOWS is None:
        return []
    ctypes, kernel32, entry_type = _WINDOWS["ctypes"], _WINDOWS["kernel32"], _WINDOWS["entry"]
    found: list[tuple[int, int, str]] = []
    handle = None
    try:
        handle = kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
        if not handle or handle == _INVALID_HANDLE_VALUE:
            return []
        entry = entry_type()
        entry.dwSize = ctypes.sizeof(entry_type)
        if not kernel32.Process32FirstW(handle, ctypes.byref(entry)):
            return []
        while True:
            found.append(
                (
                    int(entry.th32ProcessID),
                    int(entry.th32ParentProcessID),
                    str(entry.szExeFile).lower(),
                )
            )
            if not kernel32.Process32NextW(handle, ctypes.byref(entry)):
                break
    except (OSError, ValueError, OverflowError, ctypes.ArgumentError):
        return []
    finally:
        if handle and handle != _INVALID_HANDLE_VALUE:
            with contextlib.suppress(OSError, ValueError, ctypes.ArgumentError):
                kernel32.CloseHandle(handle)
    return found


def _windows_fact(pid: int) -> ProcessFact | None:
    if _WINDOWS is None:
        return None
    ctypes, wintypes = _WINDOWS["ctypes"], _WINDOWS["wintypes"]
    kernel32, query = _WINDOWS["kernel32"], _WINDOWS["query"]
    handle = None
    image = None
    parent = None
    argv = None
    created = None
    try:
        handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            buffer = ctypes.create_unicode_buffer(IMAGE_MAX)
            size = wintypes.DWORD(IMAGE_MAX)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                image = _normalize_image(buffer.value) if buffer.value else None
            born = wintypes.FILETIME()
            unused = [wintypes.FILETIME() for _ in range(3)]
            if kernel32.GetProcessTimes(
                handle, ctypes.byref(born), *[ctypes.byref(item) for item in unused]
            ):
                created = (int(born.dwHighDateTime) << 32) | int(born.dwLowDateTime)
            if query is not None:
                basic = _WINDOWS["basic"]()
                returned = wintypes.ULONG(0)
                if (
                    query(
                        handle,
                        _PROCESS_BASIC_INFORMATION,
                        ctypes.byref(basic),
                        ctypes.sizeof(basic),
                        ctypes.byref(returned),
                    )
                    == 0
                ):
                    parent = int(basic.InheritedFromUniqueProcessId or 0)
                needed = wintypes.ULONG(0)
                query(handle, _PROCESS_COMMAND_LINE_INFORMATION, None, 0, ctypes.byref(needed))
                if 0 < needed.value <= COMMAND_LINE_MAX * 2 + 64:
                    raw = ctypes.create_string_buffer(needed.value)
                    if (
                        query(
                            handle,
                            _PROCESS_COMMAND_LINE_INFORMATION,
                            raw,
                            needed.value,
                            ctypes.byref(needed),
                        )
                        == 0
                    ):
                        text_ref = _WINDOWS["ustring"].from_buffer(raw)
                        if text_ref.Buffer and text_ref.Length:
                            line = ctypes.wstring_at(text_ref.Buffer, text_ref.Length // 2)
                            argv = tuple(split_windows_command_line(line))
    except (OSError, ValueError, OverflowError, ctypes.ArgumentError):
        pass
    finally:
        if handle:
            with contextlib.suppress(OSError, ValueError, ctypes.ArgumentError):
                kernel32.CloseHandle(handle)
    if parent is None:
        for found_pid, found_parent, _name in _windows_snapshot():
            if found_pid == pid:
                parent = found_parent
                break
    if image is None and parent is None:
        return None
    return ProcessFact(
        pid=pid, ppid=parent, image=image, name=_basename(image), argv=argv, created=created
    )


# ---------------------------------------------------------------- POSIX


def _proc_available() -> bool:
    try:
        return os.path.isdir("/proc") and os.path.exists("/proc/self/stat")
    except OSError:
        return False


def _posix_fact(pid: int) -> ProcessFact | None:
    image = None
    parent = None
    argv = None
    created = None
    try:
        target = os.readlink(f"/proc/{pid}/exe")
        # A deleted binary reads as "... (deleted)"; the identity is still the path.
        image = _normalize_image(target) if target else None
    except OSError:
        image = None
    try:
        raw = Path(f"/proc/{pid}/stat").read_bytes()[:4096]
        text = raw.decode("utf-8", errors="replace")
        # `comm` may contain spaces and parentheses, so the fields start after
        # the LAST ')' of the line.
        pivot = text.rfind(")")
        fields = text[pivot + 1 :].split() if pivot >= 0 else []
        if len(fields) >= 2:
            parent = int(fields[1])
        if len(fields) >= 20:
            created = int(fields[19])
    except (OSError, ValueError):
        pass
    try:
        blob = Path(f"/proc/{pid}/cmdline").read_bytes()[:COMMAND_LINE_MAX]
        if blob:
            argv = tuple(
                part.decode("utf-8", errors="replace") for part in blob.rstrip(b"\0").split(b"\0")
            )
    except OSError:
        argv = None
    if pid == os.getpid() and parent is None:
        parent = os.getppid()
    if image is None and parent is None:
        return None
    return ProcessFact(
        pid=pid, ppid=parent, image=image, name=_basename(image), argv=argv, created=created
    )


# ---------------------------------------------------------------- public


def platform_supported() -> bool:
    """Can this platform report process identity at all? Never raises."""
    try:
        if sys.platform == "win32":
            return _WINDOWS is not None
        return _proc_available()
    except Exception:
        return False


def process_fact(pid: int) -> ProcessFact | None:
    """One observed process, or None when it cannot be observed."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    try:
        if sys.platform == "win32":
            return _windows_fact(pid)
        return _posix_fact(pid)
    except Exception:
        return None


def _windows_environment(pid: int) -> str | None:
    """Bounded read of process parameters; unavailable layouts fail as unknown.

    PEB/RTL offsets are architecture-specific Windows implementation details.
    The result is consumed locally for one named value, never logged or returned.
    """
    if _WINDOWS is None or _WINDOWS["query"] is None:
        return None
    ctypes, wintypes = _WINDOWS["ctypes"], _WINDOWS["wintypes"]
    kernel32, query = _WINDOWS["kernel32"], _WINDOWS["query"]
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION | 0x10, False, pid)
    if not handle:
        return None
    try:
        read = kernel32.ReadProcessMemory
        read.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        read.restype = wintypes.BOOL

        def memory(address: int, size: int) -> bytes | None:
            buffer = ctypes.create_string_buffer(size)
            count = ctypes.c_size_t()
            if read(handle, address, buffer, size, ctypes.byref(count)) and count.value == size:
                return buffer.raw
            return None

        basic = _WINDOWS["basic"]()
        returned = wintypes.ULONG()
        if query(handle, 0, ctypes.byref(basic), ctypes.sizeof(basic), ctypes.byref(returned)):
            return None
        width = ctypes.sizeof(ctypes.c_void_p)
        peb = int(basic.PebBaseAddress or 0)
        wow = ctypes.c_void_p()
        if (query(handle, 26, ctypes.byref(wow), ctypes.sizeof(wow), ctypes.byref(returned)) == 0
                and wow.value):
            width, peb = 4, int(wow.value)
        if not peb or width not in (4, 8):
            return None
        pointer = memory(peb + (0x20 if width == 8 else 0x10), width)
        if pointer is None:
            return None
        parameters = int.from_bytes(pointer, "little")
        pointer = memory(parameters + (0x80 if width == 8 else 0x48), width) if parameters else None
        if pointer is None:
            return None
        address = int.from_bytes(pointer, "little")
        if not address:
            return None
        collected = bytearray()
        for _ in range(33):
            size = 4096 - address % 4096
            block = memory(address, size)
            if block is None:
                return None
            collected.extend(block)
            # UTF-16 termination must be aligned; raw substring matching can
            # mistake the last ASCII letter plus its zero high byte for it.
            for offset in range(0, len(collected) - 3, 2):
                if collected[offset:offset + 4] == b"\0\0\0\0":
                    return collected[:offset].decode("utf-16-le", errors="strict")
            address += size
        return None
    except (OSError, ValueError, OverflowError, UnicodeError, ctypes.ArgumentError):
        return None
    finally:
        kernel32.CloseHandle(handle)


def environment_value(pid: int, name: str) -> tuple[bool, str | None]:
    """One OS-observed variable; (False, None) means unavailable, not absent."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0 or not name or "=" in name:
        return False, None
    try:
        if sys.platform == "win32":
            text = _windows_environment(pid)
            if text is None:
                return False, None
        else:
            with Path(f"/proc/{pid}/environ").open("rb") as stream:
                blob = stream.read(131073)
            if len(blob) > 131072:
                return False, None
            text = blob.decode("utf-8", errors="strict")
        for item in text.split("\0"):
            key, separator, value = item.partition("=")
            matches = key.casefold() == name.casefold() if sys.platform == "win32" else key == name
            if separator and matches:
                return True, value
        return True, None
    except (OSError, UnicodeError, ValueError):
        return False, None


def ancestry(pid: int, limit: int = 16) -> list[ProcessFact]:
    """Self, then parent, then grandparent... bounded, cycle-safe, never raising."""
    chain: list[ProcessFact] = []
    seen: set[int] = set()
    current: int | None = pid
    try:
        bound = int(limit)
    except (TypeError, ValueError):
        bound = 16
    if bound < 1:
        return chain
    while current and current > 0 and current not in seen and len(chain) < bound:
        seen.add(current)
        fact = process_fact(current)
        if fact is None:
            break
        chain.append(fact)
        current = fact.ppid
        if current in (0, 1):
            break
    return chain


def _matches(name: str | None, image: str | None, wanted: str) -> bool:
    target = wanted.replace("\\", "/").strip().lower()
    if not target:
        return False
    if "/" in target:
        return image is not None and image == target
    if name is None:
        return False
    return name == target or _strip_exe(name) == _strip_exe(target)


def host_ancestor(
    pid: int, host_images: Sequence[str], limit: int = 16
) -> ProcessFact | None:
    """The nearest ancestor (or the process itself) named like a host application.

    A NAME match only: it answers "is a host application above this process"
    for a diagnostic. It authenticates nobody and starts nothing -- the shape
    proof in `host_authority_identity` decides both.
    """
    try:
        wanted = [str(item) for item in host_images if str(item).strip()]
    except TypeError:
        return None
    if not wanted:
        return None
    from .host_authority_identity import retired_image

    for fact in ancestry(pid, limit):
        # A host that updated itself runs under a renamed image (T-1650).
        started_as = retired_image(fact.image, fact.pid)
        for candidate in wanted:
            if _matches(fact.name, fact.image, candidate):
                return fact
            if started_as and _matches(_basename(started_as), started_as, candidate):
                return fact
    return None


def any_live(host_images: Sequence[str]) -> bool | None:
    """Is any process named like a host application alive right now?

    None when the platform cannot enumerate processes: the caller then keeps
    its conservative default instead of acting on a guess.
    """
    try:
        wanted = {_strip_exe(str(item).replace("\\", "/").rsplit("/", 1)[-1].strip().lower())
                  for item in host_images if str(item).strip()}
    except TypeError:
        return None
    if not wanted:
        return False
    try:
        if sys.platform == "win32":
            listing = _windows_snapshot()
            if not listing:
                return None
            return any(_strip_exe(name) in wanted for _pid, _parent, name in listing)
        if not _proc_available():
            return None
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                name = os.path.basename(os.readlink(f"/proc/{entry}/exe")).lower()
            except OSError:
                continue
            if _strip_exe(name) in wanted:
                return True
        return False
    except Exception:
        return None


def describe(pid: int, limit: int = 16) -> dict:
    """A JSON-safe identity report for diagnostics. Never raises."""
    supported = platform_supported()
    chain: list[dict] = []
    detail: str | None = None
    try:
        for fact in ancestry(pid, limit):
            chain.append(
                {"pid": fact.pid, "ppid": fact.ppid, "image": fact.image, "name": fact.name}
            )
    except Exception as exc:  # pragma: no cover - defensive only
        detail = f"identity read failed: {type(exc).__name__}"
    if supported and not chain and detail is None:
        detail = "the OS reported no identity for this process"
    if not supported:
        detail = "process identity is unavailable on this platform"
    return {"supported": supported, "pid": pid, "chain": chain, "detail": detail}


# ------------------------------------------------------------ code signing

_SIGNER_CACHE: dict[tuple[str, int, int], str | None] = {}
_SIGNER_LOCK = threading.Lock()


def signing_supported() -> bool:
    """Can this platform report the publisher of an image file?"""
    return sys.platform == "win32" and _WINDOWS is not None


def _authenticode_signer(path: str) -> str | None:
    """The Authenticode publisher of a file whose signature VERIFIES, else None.

    The whole file is hashed by the operating system, so a signature block
    pasted onto other bytes names nobody. Revocation and network retrieval are
    switched off: an offline machine must reach the same answer.
    """
    import ctypes
    from ctypes import wintypes

    try:
        wintrust = ctypes.WinDLL("wintrust", use_last_error=True)
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    except (AttributeError, OSError):
        return None

    class _GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    class _FILE_INFO(ctypes.Structure):
        _fields_ = [
            ("cbStruct", wintypes.DWORD),
            ("pcwszFilePath", wintypes.LPCWSTR),
            ("hFile", wintypes.HANDLE),
            ("pgKnownSubject", ctypes.c_void_p),
        ]

    class _DATA(ctypes.Structure):
        _fields_ = [
            ("cbStruct", wintypes.DWORD),
            ("pPolicyCallbackData", ctypes.c_void_p),
            ("pSIPClientData", ctypes.c_void_p),
            ("dwUIChoice", wintypes.DWORD),
            ("fdwRevocationChecks", wintypes.DWORD),
            ("dwUnionChoice", wintypes.DWORD),
            ("pFile", ctypes.POINTER(_FILE_INFO)),
            ("dwStateAction", wintypes.DWORD),
            ("hWVTStateData", wintypes.HANDLE),
            ("pwszURLReference", wintypes.LPCWSTR),
            ("dwProvFlags", wintypes.DWORD),
            ("dwUIContext", wintypes.DWORD),
            ("pSignatureSettings", ctypes.c_void_p),
        ]

    class _PROVIDER_CERT(ctypes.Structure):
        _fields_ = [("cbStruct", wintypes.DWORD), ("pCert", ctypes.c_void_p)]

    try:
        verify = wintrust.WinVerifyTrust
        verify.argtypes = [wintypes.HANDLE, ctypes.POINTER(_GUID), ctypes.c_void_p]
        verify.restype = ctypes.c_long
        state_data = wintrust.WTHelperProvDataFromStateData
        state_data.argtypes = [wintypes.HANDLE]
        state_data.restype = ctypes.c_void_p
        chain_signer = wintrust.WTHelperGetProvSignerFromChain
        chain_signer.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        chain_signer.restype = ctypes.c_void_p
        chain_cert = wintrust.WTHelperGetProvCertFromChain
        chain_cert.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        chain_cert.restype = ctypes.c_void_p
        name_of = crypt32.CertGetNameStringW
        name_of.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.LPWSTR,
            wintypes.DWORD,
        ]
        name_of.restype = wintypes.DWORD
    except (AttributeError, TypeError):
        return None

    # WINTRUST_ACTION_GENERIC_VERIFY_V2
    action = _GUID(
        0x00AAC56B,
        0xCD44,
        0x11D0,
        (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE),
    )
    info = _FILE_INFO(ctypes.sizeof(_FILE_INFO), path, None, None)
    data = _DATA()
    data.cbStruct = ctypes.sizeof(_DATA)
    data.dwUIChoice = 2  # WTD_UI_NONE
    data.fdwRevocationChecks = 0  # WTD_REVOKE_NONE
    data.dwUnionChoice = 1  # WTD_CHOICE_FILE
    data.pFile = ctypes.pointer(info)
    data.dwStateAction = 1  # WTD_STATEACTION_VERIFY
    data.dwProvFlags = 0x1000 | 0x10  # cache-only retrieval, no revocation check
    signer = None
    try:
        status = verify(None, ctypes.byref(action), ctypes.byref(data))
        if status == 0 and data.hWVTStateData:
            provider = state_data(data.hWVTStateData)
            entry = chain_signer(provider, 0, False, 0) if provider else None
            cert = chain_cert(entry, 0) if entry else None
            if cert:
                context = ctypes.cast(cert, ctypes.POINTER(_PROVIDER_CERT)).contents.pCert
                size = name_of(context, 4, 0, None, None, 0)  # CERT_NAME_SIMPLE_DISPLAY_TYPE
                if 1 < size < 1024:
                    buffer = ctypes.create_unicode_buffer(size)
                    name_of(context, 4, 0, None, buffer, size)
                    signer = buffer.value or None
    except (OSError, ValueError, ctypes.ArgumentError):
        signer = None
    finally:
        with contextlib.suppress(OSError, ValueError, ctypes.ArgumentError):
            data.dwStateAction = 2  # WTD_STATEACTION_CLOSE
            verify(None, ctypes.byref(action), ctypes.byref(data))
    return signer


def image_signer(path: str | None) -> str | None:
    """The verified publisher of an image file, or None.

    None covers every way of not knowing: an unsigned file, a signature that
    does not verify, an unreadable file and a platform with no such notion.
    Memoised by path, size and mtime -- verifying hashes the whole image, which
    for a large host binary is a noticeable fraction of a second.
    """
    if not path or not signing_supported():
        return None
    native = str(path).replace("/", "\\")
    try:
        status = os.stat(native)
    except OSError:
        return None
    key = (native.lower(), int(status.st_size), int(status.st_mtime_ns))
    with _SIGNER_LOCK:
        if key in _SIGNER_CACHE:
            return _SIGNER_CACHE[key]
    try:
        signer = _authenticode_signer(native)
    except Exception:
        signer = None
    with _SIGNER_LOCK:
        if len(_SIGNER_CACHE) > 64:
            _SIGNER_CACHE.clear()
        _SIGNER_CACHE[key] = signer
    return signer


__all__ = [
    "COMMAND_LINE_MAX",
    "IMAGE_MAX",
    "ProcessFact",
    "ancestry",
    "any_live",
    "describe",
    "host_ancestor",
    "image_signer",
    "platform_supported",
    "process_fact",
    "signing_supported",
    "split_windows_command_line",
]
