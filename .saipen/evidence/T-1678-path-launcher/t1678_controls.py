"""T-1678: a red control per property of the PATH launcher owner.

Usage: t1678_controls.py <tree> <copy>

<tree> holds the built tools/, tests/, saipen/, extensions/, bootstrap/ and
bin/. They are copied to <copy>; the unmutated control and every single
mutation run the test module three times, and a test red in only some
repetitions is reported.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

tree = Path(sys.argv[1]).resolve()
copy = Path(sys.argv[2]).resolve()
assert tree != copy and not copy.exists(), copy

MODULE = "test_t1678_path_launcher"
PL = "tools/saipen_engine/path_launcher.py"
HG = "tools/saipen_engine/host_integration.py"
OWN = "bootstrap/install_ownership.py"
INJECT = "bootstrap/inject.ps1"
UNINSTALL = "bootstrap/uninstall.ps1"

INSTALLER = "test_powershell_installer_owns_the_path_launcher_and_uninstall_removes_it"
MUTATIONS = [
    ("M1 the installer does not install the launcher",
     [(INJECT, '  [void]$report.Add(@("PATH launcher", $launcherRow))\n', "")],
     [INSTALLER]),
    ("M2 the uninstaller does not remove it",
     [(UNINSTALL, 'Report "PATH launcher" (Remove-PathLauncher $h)\n', "")],
     [INSTALLER]),
    ("M3 host repair has no launcher step",
     [(HG, "        launcher_step = refresh_path_launcher(canonical, home)\n",
       "        launcher_step = None\n")],
     ["test_doctor_reports_a_missing_launcher_and_repair_writes_it",
      "test_doctor_reports_a_stale_hand_copy_and_repair_replaces_it_with_an_owned_one"]),
    ("M4 the doctor does not report the launcher",
     [(HG, '        "path_launcher": path_launcher_view(canonical, home),\n', "")],
     ["test_doctor_reports_a_missing_launcher_and_repair_writes_it",
      "test_doctor_reports_a_stale_hand_copy_and_repair_replaces_it_with_an_owned_one",
      "test_a_profile_whose_path_names_no_declared_directory_gets_no_repair_step"]),
    ("M5 a foreign launcher counts as adoptable",
     [(PL, "        elif proof[\"ok\"]:\n            report[\"files\"][name] = \"unowned-proving\"\n",
       "        elif True:\n            report[\"files\"][name] = \"unowned-proving\"\n")],
     ["test_a_foreign_launcher_is_never_touched"]),
    ("M6 the engine removes a launcher someone edited",
     [(PL, "        if _digest(path) == expected:\n", "        if path.exists():\n")],
     ["test_removal_takes_only_what_is_still_as_written"]),
    ("M7 the uninstaller follows a record outside the declared directories",
     [(OWN, "            or path.parent.resolve() not in allowed\n", "")],
     ["test_the_uninstaller_refuses_a_record_that_names_a_file_elsewhere"]),
    ("M8 a declared directory PATH does not name is used anyway",
     [(PL, "        if _norm(candidate) in entries:\n", "        if True:\n")],
     ["test_no_declared_directory_on_path_writes_nothing_and_names_the_one_to_add",
      "test_a_profile_whose_path_names_no_declared_directory_gets_no_repair_step"]),
    ("M9 shadowing goes unreported",
     [(PL, "    if which is None or Path(_norm(which)).parent != Path(_norm(directory)):\n",
       "    if False:\n")],
     ["test_a_saipen_earlier_on_path_is_reported_as_shadowing"]),
]


def ignore(_directory: str, names: list[str]) -> list[str]:
    return [n for n in names if n in {"__pycache__", ".ruff_cache"} or n.endswith(".pyc")]


for part in ("tools", "tests", "saipen", "extensions", "bootstrap", "bin"):
    shutil.copytree(tree / part, copy / part, ignore=ignore)
for name in ("VERSION",):
    shutil.copy2(tree / name, copy / name)


def edit(edits):
    originals = {}
    for rel, old, new in edits:
        target = copy / rel
        raw = target.read_bytes()
        originals.setdefault(rel, raw)
        newline = "\r\n" if b"\r\n" in raw else "\n"
        text = raw.decode("utf-8")
        old, new = old.replace("\n", newline), new.replace("\n", newline)
        assert text.count(old) == 1, (rel, text.count(old), old[:70])
        target.write_bytes(text.replace(old, new).encode("utf-8"))
    return originals


def restore(originals):
    for rel, raw in originals.items():
        (copy / rel).write_bytes(raw)


def run():
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", MODULE],
        cwd=str(copy / "tools"), env=env, stdin=subprocess.DEVNULL, capture_output=True,
        timeout=1800, check=False,
    )
    out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
    reds = frozenset(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", out, flags=re.MULTILINE))
    ran = re.search(r"^Ran (\d+) tests?", out, flags=re.MULTILINE)
    return proc.returncode, reds, ran.group(1) if ran else "?"


ok = True
seen = [run() for _ in range(3)]
green = all(rc == 0 and not reds for rc, reds, _ in seen)
print(f"control (unmutated): {'green' if green else 'RED'} x3, ran {seen[0][2]}")
ok &= green
for title, edits, expected in MUTATIONS:
    originals = edit(edits)
    try:
        seen = [run() for _ in range(3)]
    finally:
        restore(originals)
    always = frozenset.intersection(*(reds for _, reds, _ in seen))
    sometimes = frozenset.union(*(reds for _, reds, _ in seen)) - always
    caught = set(expected) <= always
    ok &= caught and not sometimes
    print(f"{title}: {'detected' if caught else 'MISSED'} 3/3 by {sorted(always)}"
          + (f"; flaky {sorted(sometimes)}" if sometimes else ""))
shutil.rmtree(copy, ignore_errors=True)
print("held:", ok)
raise SystemExit(0 if ok else 1)
