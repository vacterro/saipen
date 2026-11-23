"""One bounded full-state copy/discovery experiment, never suite evidence."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

home = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(home / "tools"))
from saipen_engine import core_unit, test_runner

parser = argparse.ArgumentParser()
parser.add_argument("--output", required=True)
parser.add_argument("--frozen")
parser.add_argument("--expected")
args = parser.parse_args()
output = Path(args.output).resolve()
temp_root = Path(tempfile.gettempdir()).resolve()
owned = []
report = {"scope": "full-state copy and discovery observation; not verification acceptance",
          "executed_suite": False, "runtime": sys.version, "platform": sys.platform,
          "stages": {}, "cleanup": []}


def save():
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def make_owner(project):
    owner = core_unit.new_sandbox_root(project).resolve()
    if owner.parent != temp_root or not owner.name.startswith(core_unit.SANDBOX_PREFIX):
        raise RuntimeError("new sandbox is outside the intended temporary root")
    owned.append(owner)
    return owner


def inventory(root):
    started = time.perf_counter()
    entries, total = [], 0
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries.append([relative, "symlink", os.readlink(path)])
        elif path.is_file():
            content = path.read_bytes()
            total += len(content)
            entries.append([relative, "file", len(content), hashlib.sha256(content).hexdigest()])
    # Path ordering differs by host (Windows folds case). Compare the exact
    # same ordered relative-name/content entries on every platform.
    entries.sort(key=lambda row: tuple(row[0].split("/")))
    digest = hashlib.sha256(json.dumps(entries, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
    return {"files_or_links": len(entries), "bytes": total, "sha256": digest,
            "inventory_wall_s": round(time.perf_counter() - started, 6)}


def equal_inventory(left, right):
    return all(left[key] == right[key] for key in ("files_or_links", "bytes", "sha256"))


def hardlink_witness(owner):
    directory = owner / "private-hardlink-witness"
    directory.mkdir()
    original, worker = directory / "source", directory / "worker"
    original.write_bytes(b"original")
    try:
        os.link(original, worker)
        worker.write_bytes(b"worker mutation")
        return {"supported": True, "source_before": "original",
                "source_after": original.read_text(encoding="utf-8"),
                "worker_after": worker.read_text(encoding="utf-8"),
                "source_changed": original.read_bytes() != b"original",
                "decision": "reject shared mutable hardlinks; original was modified"}
    except OSError as exc:
        return {"supported": False, "error": str(exc), "decision": "no hardlink optimization established"}


def linux_path(path):
    # Native argv and forward slashes avoid WSL's default shell consuming
    # Windows backslashes. Validate this transport before any expensive copy.
    translated = subprocess.run(
        ["wsl.exe", "-d", "saipen-ubuntu", "--exec", "wslpath", "-u", path.as_posix()],
        capture_output=True, text=True, encoding="utf-8", check=True, timeout=30)
    return translated.stdout.strip()


try:
    linux_script = None
    if not args.frozen and os.name == "nt":
        linux_script = linux_path(Path(__file__).resolve())
        linux_path(temp_root)
    source = Path(args.frozen).resolve() if args.frozen else home
    owner = make_owner(source)
    project = owner / "project"
    began = time.perf_counter()
    if args.frozen:
        shutil.copytree(source, project, symlinks=True)
        copy_metrics = None
    else:
        copy_metrics = core_unit.copy_tree_consistent(source, project, test_runner._ignore_copy)
    report["stages"]["first_copy_wall_s"] = round(time.perf_counter() - began, 6)
    report["copy_metrics"] = copy_metrics
    print("first full-state copy complete: " + json.dumps(report["stages"]), flush=True)
    frozen_inventory = inventory(project)
    report["input_inventory"] = frozen_inventory
    if args.expected:
        expected = json.loads(Path(args.expected).read_text(encoding="utf-8"))["input_inventory"]
        report["matches_windows_frozen_input"] = equal_inventory(expected, frozen_inventory)
        if not report["matches_windows_frozen_input"]:
            raise RuntimeError("native copy is not the same frozen full input")
    report["source_fingerprint"] = core_unit.tree_fingerprint(project)
    if not args.frozen and core_unit.tree_fingerprint(source) != report["source_fingerprint"]:
        raise RuntimeError("live source changed while capturing the measurement")
    print("full input inventory: " + json.dumps(frozen_inventory), flush=True)
    save()

    second_owner = make_owner(source)
    second = second_owner / "project"
    began = time.perf_counter()
    shutil.copytree(project, second, symlinks=True)
    report["stages"]["private_worker_clone_wall_s"] = round(time.perf_counter() - began, 6)
    copied_inventory = inventory(second)
    report["private_worker_inventory"] = copied_inventory
    report["private_clone_exact"] = equal_inventory(frozen_inventory, copied_inventory)
    if not report["private_clone_exact"]:
        raise RuntimeError("private worker clone differs from the frozen input")
    report["hardlink_witness"] = hardlink_witness(second_owner)
    print("private clone proved exact: " + json.dumps(report["stages"]), flush=True)
    save()

    declared = core_unit.family()
    bounded = test_runner.TestFamily(declared.name, declared.command, 180)
    began = time.perf_counter()
    discovery = core_unit._run_shard(project, bounded, ("tools", "test_*.py"),
                                   {"include": [], "include_import_errors": True}, owner)
    report["stages"]["discovery_probe_wall_s"] = round(time.perf_counter() - began, 6)
    manifest = discovery.get("manifest") or {}
    report["discovery"] = {
        "purpose": "full real discovery, select only import failures; no suite acceptance",
        "status": discovery["status"], "exit_code": discovery.get("exit_code"),
        "discovered_occurrences": manifest.get("discovered"),
        "discovery_wall_s": manifest.get("discovery_s"),
        "inventory_sha256": manifest.get("inventory_sha256"),
        "import_error_indices": manifest.get("import_error_indices"),
        "ran_import_error_cases": discovery.get("ran"), "red": discovery.get("red"),
    }
    output.with_suffix(".discovery.json").write_text(json.dumps(discovery, indent=2) + "\n", encoding="utf-8")
    print("discovery observation: " + json.dumps(report["discovery"]), flush=True)
    save()

    if not args.frozen and os.name == "nt":
        native_output = output.with_name(output.stem + "-linux.json")
        command = ["wsl.exe", "-d", "saipen-ubuntu", "--exec", "python3", "-B", linux_script,
                   "--output", linux_path(native_output), "--frozen", linux_path(project), "--expected", linux_path(output)]
        print("measuring the same frozen full input on native Linux", flush=True)
        native = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=900)
        report["native_linux_launch"] = {"exit_code": native.returncode,
                                         "stdout": native.stdout, "stderr": native.stderr}
        save()
        native.check_returncode()
        report["native_linux_report"] = str(native_output.relative_to(home))
        save()
except BaseException as exc:
    report["experiment_error"] = {"type": type(exc).__name__, "detail": str(exc)}
    save()
    raise
finally:
    for directory in reversed(owned):
        if directory.parent != temp_root or not directory.name.startswith(core_unit.SANDBOX_PREFIX):
            raise RuntimeError("refusing cleanup outside this run's verified temporary roots")
        began = time.perf_counter()
        reclaimed = core_unit.reclaim(directory)
        report["cleanup"].append({"path": str(directory), "removed": reclaimed,
                                  "wall_s": round(time.perf_counter() - began, 6)})
        print("owned cleanup: " + json.dumps(report["cleanup"][-1]), flush=True)
    save()
