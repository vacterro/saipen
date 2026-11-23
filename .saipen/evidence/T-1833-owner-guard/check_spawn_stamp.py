"""Fault injection: interruption of a public stamp write must preserve parseable ownership."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
with tempfile.TemporaryDirectory(prefix="t1833-stamp-") as temporary:
    stamp = Path(temporary) / "owner.json"
    stamp.write_text(json.dumps({"pid": 1, "spawn_phase": "COPYING"}), encoding="utf-8")
    code = f'''
import os,sys
from pathlib import Path
from unittest import mock
sys.path.insert(0,{str(ROOT / 'tools')!r})
from saipen_engine.test_runner import _note_spawn_start
stamp=Path({str(stamp)!r})
original=Path.write_text
def interrupted(path,*args,**kwargs):
    if path == stamp:
        with path.open('w', encoding='utf-8') as stream:
            stream.write('{{"spawn_')
            stream.flush()
        os._exit(91)
    return original(path,*args,**kwargs)
with mock.patch.object(Path,'write_text',interrupted):
    _note_spawn_start(stamp)
'''
    result = subprocess.run([sys.executable, "-B", "-c", code],
                            stdin=subprocess.DEVNULL, timeout=10, check=False)
    try:
        state = json.loads(stamp.read_text(encoding="utf-8"))
    except ValueError:
        print("FAIL: interrupted STARTING stamp is truncated; canonical recovery cannot read ownership")
        raise SystemExit(1) from None
    assert state["spawn_phase"] in {"COPYING", "STARTING"}, state
    print(f"PASS: ownership remains complete after write fault (child rc {result.returncode})")
