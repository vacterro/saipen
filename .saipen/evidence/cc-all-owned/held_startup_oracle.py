"""Four fixed native checks of the holder fixture under delayed real startup.

The three existing test bodies and one independent readiness check are fixed.
Only the holder-fixture implementation varies. No live product/test edit occurs.
"""
import ast
import ctypes
from ctypes import wintypes
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

assert os.name == "nt"
import _winapi

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import core_unit

version = sys.argv[1]
assert version in ("before", "candidate")
path = HERE / ("held_fixture." + version + ".py")
before_source = (HERE / "held_fixture.before.py").read_text(encoding="utf-8")
subject_source = path.read_text(encoding="utf-8")

def test_bodies(source):
    cls = next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef) and node.name == "HeldSandboxTests")
    return "\n".join(ast.dump(node, include_attributes=False) for node in cls.body
                     if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"))

assert test_bodies(subject_source) == test_bodies(before_source)
spec = importlib.util.spec_from_file_location("ccall_held_subject", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.ResumeThread.argtypes = [wintypes.HANDLE]
kernel.ResumeThread.restype = wintypes.DWORD
real_popen = subprocess.Popen
real_create = _winapi.CreateProcess
real_close = _winapi.CloseHandle
delayed = []
resume_errors = []

def delayed_popen(command, *args, **kwargs):
    if not (len(command) >= 3 and command[1] == "-c" and command[2] == module.HeldSandboxTests.HOLD):
        return real_popen(command, *args, **kwargs)
    handles = []
    def create(*args):
        result = real_create(*args)
        handles.append(result[1])
        return result
    def close(handle):
        if handle not in handles:
            real_close(handle)
    kwargs["creationflags"] = kwargs.get("creationflags", 0) | 0x00000004 | subprocess.CREATE_NO_WINDOW
    with patch.object(_winapi, "CreateProcess", create), patch.object(_winapi, "CloseHandle", close):
        child = real_popen(command, *args, **kwargs)
    assert len(handles) == 1
    def resume():
        if child.poll() is None:
            previous = kernel.ResumeThread(handles[0])
            if previous != 1:
                resume_errors.append((previous, ctypes.get_last_error()))
    timer = threading.Timer(2.0, resume)
    timer.start()
    delayed.append((child, timer, handles[0]))
    return child

class NativeStartupControl(unittest.TestCase):
    def test_holder_is_ready_before_any_destructive_reclaim(self):
        fixture = module.HeldSandboxTests("test_a_held_sandbox_is_reported_then_swept_once_its_owner_is_gone")
        temporary = Path(tempfile.mkdtemp(prefix="ccall-held-oracle-"))
        assert temporary.resolve().parent == Path(tempfile.gettempdir()).resolve()
        assert temporary.name.startswith("ccall-held-oracle-")
        self.addCleanup(core_unit.reclaim, temporary)
        self.addCleanup(fixture.doCleanups)
        directory = temporary / "holder"
        directory.mkdir()
        holder = fixture.hold(directory)
        self.assertIsNone(holder.poll())
        self.assertFalse(core_unit.reclaim(directory), "unready holder allowed its directory to be removed")
        self.assertTrue(directory.exists())

suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(module.HeldSandboxTests),
                           unittest.defaultTestLoader.loadTestsFromTestCase(NativeStartupControl)])
transcript = io.StringIO()
try:
    with patch.object(subprocess, "Popen", delayed_popen):
        result = unittest.TextTestRunner(stream=transcript, verbosity=2).run(suite)
finally:
    for child, timer, handle in delayed:
        timer.cancel()
        timer.join(timeout=5)
        if child.poll() is None:
            child.kill()
        child.wait(timeout=30)
        real_close(handle)
assert result.testsRun == 4, result.testsRun
assert not result.skipped, result.skipped
assert not resume_errors, resume_errors
verifier = hashlib.sha256(Path(__file__).read_bytes() + test_bodies(before_source).encode()
                          + (ROOT / "tools/saipen_engine/core_unit.py").read_bytes()
                          + b"native CREATE_SUSPENDED; resume-delay=2.0; timeout=180").hexdigest()
record = {"version": version, "scope": "unclaimed preparation; holder fixture only",
          "verifier": verifier, "subject": hashlib.sha256(path.read_bytes()).hexdigest(),
          "ran": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
          "skipped": len(result.skipped), "passed": result.wasSuccessful(),
          "delayed_real_children": len(delayed), "resume_errors": resume_errors,
          "transcript": transcript.getvalue()}
(HERE / ("held-startup-" + version + ".json")).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: record[key] for key in record if key != "transcript"}))
raise SystemExit(0 if result.wasSuccessful() else 1)
