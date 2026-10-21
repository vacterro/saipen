"""One owned process group/job, including descendants whose launcher exited."""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path


class _WindowsJob:
    def __init__(self):
        import ctypes
        from ctypes import wintypes

        self.ctypes = ctypes
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            "SetInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                         wintypes.DWORD], wintypes.BOOL),
            "AssignProcessToJobObject": ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
            "QueryInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                           wintypes.DWORD, ctypes.c_void_p], wintypes.BOOL),
            "TerminateJobObject": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
            "CreateToolhelp32Snapshot": ([wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE),
            "Thread32First": ([wintypes.HANDLE, ctypes.c_void_p], wintypes.BOOL),
            "Thread32Next": ([wintypes.HANDLE, ctypes.c_void_p], wintypes.BOOL),
            "OpenThread": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            "ResumeThread": ([wintypes.HANDLE], wintypes.DWORD),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = arguments, result

        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                        ("flags", wintypes.DWORD), ("minimum", ctypes.c_size_t),
                        ("maximum", ctypes.c_size_t), ("active", wintypes.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                        ("scheduling", wintypes.DWORD)]

        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", ctypes.c_ulonglong * 6),
                        ("memory", ctypes.c_size_t * 4)]

        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Extended()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits),
                                                ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign_and_resume(self, process):
        ctypes = self.ctypes
        from ctypes import wintypes

        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

        class Thread(ctypes.Structure):
            _fields_ = (("size", wintypes.DWORD), ("usage", wintypes.DWORD),
                        ("tid", wintypes.DWORD), ("pid", wintypes.DWORD),
                        ("base", wintypes.LONG), ("delta", wintypes.LONG),
                        ("flags", wintypes.DWORD))

        snapshot = self.api.CreateToolhelp32Snapshot(4, 0)  # TH32CS_SNAPTHREAD
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = Thread()
            entry.size = ctypes.sizeof(entry)
            more = self.api.Thread32First(snapshot, ctypes.byref(entry))
            while more:
                if entry.pid == process.pid:
                    thread = self.api.OpenThread(2, False, entry.tid)  # THREAD_SUSPEND_RESUME
                    if not thread:
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        previous = self.api.ResumeThread(thread)
                        if previous == 0xFFFFFFFF:
                            raise ctypes.WinError(ctypes.get_last_error())
                        if previous == 1:
                            return
                    finally:
                        self.api.CloseHandle(thread)
                more = self.api.Thread32Next(snapshot, ctypes.byref(entry))
            raise OSError("suspended child has no observable initial thread")
        finally:
            self.api.CloseHandle(snapshot)

    def pids(self):
        ctypes = self.ctypes
        from ctypes import wintypes

        class Processes(ctypes.Structure):
            _fields_ = (("assigned", wintypes.DWORD), ("count", wintypes.DWORD),
                        ("ids", ctypes.c_size_t * 4096))

        record = Processes()
        if not self.api.QueryInformationJobObject(self.handle, 3, ctypes.byref(record),
                                                  ctypes.sizeof(record), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return list(record.ids[:record.count])

    def terminate(self):
        if self.handle and not self.api.TerminateJobObject(self.handle, 1):
            raise self.ctypes.WinError(self.ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


class ProcessTree:
    """Launch before any descendant can escape ownership; close reaps the group."""

    def __init__(self):
        self.job = _WindowsJob() if os.name == "nt" else None
        self.process = None
        self._guard_pipe = None
        self._guard_dir = None
        self._guard_info = None
        self._closed = False

    def start(self, *args, **kwargs):
        on_started = kwargs.pop("on_started", None)
        text_flag = kwargs.pop("text", None)
        universal_flag = kwargs.pop("universal_newlines", None)
        if (text_flag is not None and universal_flag is not None
                and bool(text_flag) != bool(universal_flag)):
            raise subprocess.SubprocessError("text and universal_newlines must agree")
        text_mode = text_flag or universal_flag
        encoding = kwargs.pop("encoding", None)
        errors = kwargs.pop("errors", None)
        if encoding not in (None, "utf-8", "utf8") or errors not in (None, "replace"):
            raise ValueError("host text output uses UTF-8 with replacement decoding")
        environment = kwargs.get("env")
        environment = os.environ if environment is None else environment
        guarded = self.job is None and environment.get("SAIPEN_CANONICAL_TEST_CHILD") == "1"
        ready = None
        read_pipe = None
        if guarded:
            if len(args) != 1 or not isinstance(args[0], (list, tuple)) or not args[0]:
                raise ValueError("guarded verification requires native argv")
            if kwargs.get("shell"):
                raise ValueError("guarded verification does not use a command shell")
            if not Path("/proc/self/fd").is_dir():
                raise ValueError(
                    "verification owner guard requires the supported POSIX proc runtime"
                )
        try:
            if guarded:
                self._guard_dir = tempfile.TemporaryDirectory(prefix="saipen-process-guard-")
                ready = Path(self._guard_dir.name) / "reader-ready"
                self._guard_info = Path(self._guard_dir.name) / "guardian.json"
                command = [os.fsdecode(value) for value in args[0]]
                executable = os.fsdecode(kwargs.pop("executable", None) or command[0])
                read_pipe, self._guard_pipe = os.pipe()
                args = ((sys.executable, "-I", "-S", "-B",
                         str(Path(__file__).with_name("verification_bootstrap.py")),
                         str(os.getpid()), str(read_pipe), str(ready), str(self._guard_info),
                         executable, *command),)
                kwargs["pass_fds"] = tuple(set(kwargs.get("pass_fds") or ()) | {read_pipe})
            if self.job:
                # Assign the suspended root before it can start its shim's children.
                kwargs["creationflags"] = kwargs.get("creationflags", 0) | 4 | 0x08000000
            else:
                kwargs["start_new_session"] = True
            kwargs.setdefault("stdin", subprocess.DEVNULL)
            options = dict()
            options.update(kwargs)
            if text_mode or encoding or errors:
                self.process = subprocess.Popen(*args, text=True, encoding="utf-8",
                                                errors="replace", **options)
            else:
                self.process = subprocess.Popen(*args, **options)
            if self.job:
                self.job.assign_and_resume(self.process)
            if on_started is not None:
                on_started(self.process)
            if ready is not None:
                ready.write_bytes(b"owned reader registered")
        except BaseException:
            if self.process is not None:
                self.process.kill()
                self.process.wait(timeout=10)
            self.close()
            raise
        finally:
            if read_pipe is not None:
                os.close(read_pipe)
        return self.process

    def pids(self):
        if self.job:
            return self.job.pids()
        if self.process is None:
            return []
        owned = self.group_pids(self.process.pid)
        if self._guard_info is not None:
            with contextlib.suppress(OSError, ValueError, KeyError, TypeError):
                guardian = json.loads(self._guard_info.read_text(encoding="utf-8"))
                if guardian.get("group") == self.process.pid:
                    owned = [pid for pid in owned if pid != guardian["pid"]]
        return owned

    @staticmethod
    def group_pids(group):
        """Observe a POSIX owned process group, including orphaned descendants."""
        if not Path("/proc").is_dir():
            report = subprocess.run(["ps", "-axo", "pid=,pgid=,stat="],
                                    stdin=subprocess.DEVNULL, capture_output=True,
                                    text=True, encoding="utf-8", errors="replace",
                                    check=True, timeout=10)
            return [int(parts[0]) for line in report.stdout.splitlines()
                    if len(parts := line.split()) == 3
                    and int(parts[1]) == group and not parts[2].startswith("Z")]
        found = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            with contextlib.suppress(OSError, ValueError, IndexError):
                fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                if fields[0] != "Z" and int(fields[2]) == group:
                    found.append(int(entry.name))
        return found

    def terminate(self):
        if self.job:
            self.job.terminate()
        elif self.process is not None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(self.process.pid, signal.SIGKILL)

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self.job:
            self.job.close()
        else:
            self.terminate()
        if self._guard_pipe is not None:
            os.close(self._guard_pipe)
            self._guard_pipe = None
        if self._guard_dir is not None:
            self._guard_dir.cleanup()
            self._guard_dir = None
        if self.process is not None:
            with contextlib.suppress(subprocess.TimeoutExpired):
                self.process.wait(timeout=10)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def run(*args, timeout=None, check=False, capture_output=False, input=None, **kwargs):
    """Run a host command with owned cleanup and explicit UTF-8 text output."""
    if capture_output:
        if "stdout" in kwargs or "stderr" in kwargs:
            raise ValueError("capture_output conflicts with stdout/stderr")
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if input is not None:
        if "stdin" in kwargs:
            raise ValueError("input conflicts with stdin")
        kwargs["stdin"] = subprocess.PIPE
    with ProcessTree() as tree:
        process = tree.start(*args, **kwargs)
        try:
            stdout, stderr = process.communicate(input, timeout=timeout)
        except BaseException:
            tree.terminate()
            process.communicate(timeout=10)
            raise
        if check and process.returncode:
            raise subprocess.CalledProcessError(process.returncode, process.args,
                                                output=stdout, stderr=stderr)
        return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
