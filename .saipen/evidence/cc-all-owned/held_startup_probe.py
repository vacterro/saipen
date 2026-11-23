"""Observe native Windows directory holding before and after child startup.

Only an owned disposable child and directory are affected. Native API contract:
https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags
https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-resumethread
"""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

assert os.name == "nt"
import _winapi

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import core_unit

kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.ResumeThread.argtypes = [wintypes.HANDLE]
kernel.ResumeThread.restype = wintypes.DWORD
real_create = _winapi.CreateProcess
real_close = _winapi.CloseHandle
threads = []

def create(*args):
    result = real_create(*args)
    threads.append(result[1])
    return result

def close(handle):
    if handle not in threads:
        real_close(handle)

temporary = Path(tempfile.mkdtemp(prefix="ccall-held-startup-"))
directory = temporary / "holder"
directory.mkdir()
assert temporary.resolve().parent == Path(tempfile.gettempdir()).resolve()
assert directory.resolve().parent == temporary.resolve()
child = None
try:
    with patch.object(_winapi, "CreateProcess", create), patch.object(_winapi, "CloseHandle", close):
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; print('READY',flush=True); time.sleep(30)"],
            cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=0x00000004 | subprocess.CREATE_NO_WINDOW,
        )
    assert len(threads) == 1
    reclaimed_before_start = core_unit.reclaim(directory)
    if not directory.exists():
        directory.mkdir()
    resumed = kernel.ResumeThread(threads[0])
    assert resumed == 1, (resumed, ctypes.get_last_error())
    ready = child.stdout.readline()
    assert ready == b"READY\r\n" or ready == b"READY\n", ready
    reclaimed_after_ready = core_unit.reclaim(directory)
    result = {"reclaimed_before_primary_thread_started": reclaimed_before_start,
              "child_ready": True, "reclaimed_after_ready": reclaimed_after_ready,
              "resume_previous_suspend_count": resumed,
              "only_owned_disposable_process_and_directory": True}
    (HERE / "held-startup-probe.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
finally:
    if child is not None:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=30)
        child.stdout.close()
        child.stderr.close()
    for handle in threads:
        real_close(handle)
    assert temporary.resolve().parent == Path(tempfile.gettempdir()).resolve()
    assert temporary.name.startswith("ccall-held-startup-")
    assert core_unit.reclaim(temporary)
