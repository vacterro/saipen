"""Observe one existing Windows process generation for at most 45 seconds."""

import ctypes
from ctypes import wintypes
from datetime import datetime
import json
import sys

pid = int(sys.argv[1])
expected = datetime.fromisoformat(sys.argv[2]).timestamp()
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.OpenProcess.restype = wintypes.HANDLE
kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
handle = kernel.OpenProcess(0x00101000, False, pid)
if not handle:
    print(json.dumps({"pid": pid, "handle_available": False,
                      "observation_error": ctypes.get_last_error()}))
    raise SystemExit(1)
try:
    times = [wintypes.FILETIME() for _ in range(4)]
    if not kernel.GetProcessTimes(handle, *[ctypes.byref(value) for value in times]):
        raise RuntimeError("process creation time unavailable")
    ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
    created = ticks / 10_000_000 - 11_644_473_600
    if abs(created - expected) > 0.01:
        raise RuntimeError("process generation mismatch")
    result = kernel.WaitForSingleObject(handle, 45000)
    if result not in (0, 258):
        raise RuntimeError("native wait failed")
    print(json.dumps({"pid": pid, "generation_verified": True,
                      "observed_terminal": result == 0}), flush=True)
finally:
    kernel.CloseHandle(handle)
