"""T-1650 on real operating-system facts: rename the image of a RUNNING process.

Usage: python e2e_rename.py <saipen home holding tools/>

Does what a self-updating host does. A harmless system executable is copied to
a scratch directory as `claude.exe` and started; while it runs, its image file
is renamed to `claude.exe.old.<ms>.<pid>` -- once with its own pid, once (a
second process) with a pid that is not its own. Then the home's own process
module is asked what the platform reports, and the identity module whether
that process is the registered host. Nothing is mocked.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

home = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(home / "tools"))

from saipen_engine import host_authority_identity as identity  # noqa: E402
from saipen_engine import host_authority_process as proc  # noqa: E402

if os.name != "nt":
    raise SystemExit(json.dumps({"skipped": "the rename shape is a Windows updater behaviour"}))

IMAGES = ["claude.exe", "claude"]
source = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "ping.exe"
tmp = Path(tempfile.mkdtemp(prefix="saipen-t1650-"))
out: dict = {"home": home.name}
children = []
try:
    for label, own_pid in (("own_pid", True), ("other_pid", False)):
        folder = tmp / label
        folder.mkdir()
        image = folder / "claude.exe"
        shutil.copyfile(source, image)
        child = subprocess.Popen(
            [str(image), "-n", "30", "127.0.0.1"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        children.append(child)
        time.sleep(0.4)
        before = proc.process_fact(child.pid)
        suffix_pid = child.pid if own_pid else child.pid + 100000
        retired = folder / f"claude.exe.old.1791313812470.{suffix_pid}"
        os.replace(image, retired)  # what the updater does to its running image
        shutil.copyfile(source, image)  # ... and the new image it puts in its place
        time.sleep(0.2)
        after = proc.process_fact(child.pid)
        matcher = getattr(identity, "_host_matches", None)
        out[label] = {
            "reported_before": (before.name if before else None),
            "reported_after": (after.name if after else None)
            and after.name.replace(str(suffix_pid), "<pid>" if own_pid else "<other pid>"),
            "old_rule_recognises": identity._name_matches(after.image, IMAGES) if after else None,
            "new_rule_recognises": matcher(after, IMAGES) if (matcher and after) else None,
        }
finally:
    for child in children:
        child.kill()
        child.wait(10)
    shutil.rmtree(tmp, ignore_errors=True)
print(json.dumps(out))
