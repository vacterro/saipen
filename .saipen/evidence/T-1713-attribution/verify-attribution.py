"""Independent bounded forensic verification; never edit Git or canonical history."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PREPARED = ROOT / ".saipen/evidence/AG3-runtime-20261011"
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.attempt import build_attempts
from saipen_engine.core_unit import tree_fingerprint
from saipen_engine.log import read_history_snapshot
from saipen_engine.state import parse_state


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    run = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, timeout=60)
    if run.returncode:
        raise RuntimeError(run.stderr.decode("utf-8", errors="replace"))
    return run


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def replay(stage, filename, old_paths):
    subject = PREPARED / "historical-subjects" / filename
    name = "saipen_engine.t1713_" + stage + "_" + filename.replace("-", "_").replace(".", "_")
    module = load(name, subject)
    module.safe_atomic_write_bytes = old_paths.safe_atomic_write_bytes
    with tempfile.TemporaryDirectory(prefix="saipen-t1713-history-") as temporary:
        ancestor = Path(temporary).resolve()
        if not ancestor.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise RuntimeError("historical fixture escaped its temporary scope")
        root = ancestor / "project"
        memory = root / ".saipen"
        memory.mkdir(parents=True)
        for basename in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md"):
            (memory / basename).write_text("fixture\n", encoding="utf-8")
        before = {p.name: p.read_bytes() for p in memory.iterdir()}
        denied = PermissionError(13, "Access is denied", str(ancestor))
        denied.winerror = 5
        original = Path.lstat

        def lstat(path, *args, **kwargs):
            if path == ancestor:
                raise denied
            return original(path, *args, **kwargs)

        with patch.object(Path, "lstat", lstat):
            try:
                module.ensure(root, protocol_dir=ROOT / "saipen")
            except Exception as exc:
                if not isinstance(exc, ValueError) or getattr(exc.__context__, "winerror", None) != 5:
                    raise RuntimeError("historical boundary no longer reproduces the measured cause") from exc
                frames = [{"function": frame.name, "line": frame.lineno,
                           "file": frame.filename}
                          for frame in traceback.extract_tb(exc.__traceback__)]
                if not {"ensure", "write", "safe_atomic_write_bytes"} <= {f["function"] for f in frames}:
                    raise RuntimeError("the historical fault missed the claimed lifecycle boundary")
                result = {"subject": filename, "exception_type": type(exc).__name__,
                          "message": str(exc), "cause_winerror": 5, "frames": frames}
            else:
                raise RuntimeError("historical subject unexpectedly contained the denial")
        if before != {p.name: p.read_bytes() for p in memory.iterdir()}:
            raise RuntimeError("historical replay changed its canonical fixture bytes")
        result["canonical_fixture_unchanged"] = True
        return result


def main():
    stage = sys.argv[1]
    if stage not in {"verify", "review"}:
        raise SystemExit("expected verify or review")
    output = HERE / (stage + "-attribution.json")
    if output.exists():
        raise SystemExit("existing phase evidence is immutable")
    state = parse_state((ROOT / ".saipen/STATE.md").read_text(encoding="utf-8"))
    if state.get("task") != "T-1713" or state.get("phase") != stage.upper():
        raise SystemExit("the forensic Work does not own this phase")
    fingerprint = tree_fingerprint(ROOT)
    snapshot = read_history_snapshot(ROOT, lean=True)
    if snapshot.illegal_lines:
        raise RuntimeError("canonical history has illegal lines")
    original = json.loads((PREPARED / "history.json").read_text(encoding="utf-8"))
    provenance = json.loads((PREPARED / "attribution-provenance.json").read_text(encoding="utf-8"))
    delta = json.loads((PREPARED / "scoped-predecessor-delta-normalized.json").read_text(encoding="utf-8"))
    asset_names = ["history.json", "history-supplement.json", "attribution-provenance.json",
                   "scoped-predecessor-delta-normalized.json", "scoped-predecessor-delta-normalized.patch",
                   "OPERATOR-ATTRIBUTION-CLARIFICATION.md", "CLOSURE.md"]
    assets = {name: sha((PREPARED / name).read_bytes()) for name in asset_names}
    commits = {}
    for commit in ("dbbfad94688515d604b54e2c97dc92aa5fa7eab1",
                   "8f91d779cc4d65f6e1db952eee58db7fb3b14a78",
                   "b2343541e3ebe939bc583408a173c54aeb57939b",
                   "c138bfd8aa89ec82728587dd7c9ae43e9a69b7c3",
                   "c7e25f9281934de8f38da26d2dd599f358c77f79"):
        value = git("show", "-s", "--format=%H%n%aI%n%an%n%s", commit).stdout.decode("utf-8").splitlines()
        if value[0] != commit:
            raise RuntimeError("Git did not resolve the exact historical commit")
        commits[commit] = {"author_time": value[1], "git_author": value[2], "subject": value[3]}
    subjects = {}
    for filename, expected in original["subjects"].items():
        raw = git("show", expected["commit"] + ":" + expected["git_path"]).stdout
        if sha(raw) != expected["sha256"] or (PREPARED / "historical-subjects" / filename).read_bytes() != raw:
            raise RuntimeError("historical subject identity moved: " + filename)
        subjects[filename] = expected
    old_paths = load("saipen_engine.t1713_" + stage + "_old_paths",
                     PREPARED / "historical-subjects/paths-dbbfad946.py")
    reproductions = [replay(stage, filename, old_paths)
                     for filename in ("manifest-8f91d779.py", "manifest-c7e25f92.py")]
    last_manifest = git("log", "-1", "--format=%H", "--", "tools/saipen_engine/audit_manifest.py").stdout.decode().strip()
    if last_manifest != "c7e25f9281934de8f38da26d2dd599f358c77f79":
        raise RuntimeError("new manifest Git history requires another forensic assessment")
    predecessors = {}
    for relative, expected in delta["owners"].items():
        before_path = ROOT / expected["preserved_before_path"]
        if sha(before_path.read_bytes()) != expected["pre_fix_sha256"]:
            raise RuntimeError("preserved pre-repair bytes moved: " + relative)
        entry = git("ls-tree", delta["tracked_head"], "--", relative).stdout.strip()
        actual = sha(git("show", delta["tracked_head"] + ":" + relative).stdout) if entry else None
        if actual != expected["tracked_head_sha256"]:
            raise RuntimeError("tracked predecessor operand mismatch: " + relative)
        predecessors[relative] = {"tracked_sha256": actual,
                                  "pre_repair_sha256": expected["pre_fix_sha256"],
                                  "tracked_operand_available": actual is not None,
                                  "equal_bytes": actual == expected["pre_fix_sha256"]}
    patch_path = PREPARED / "scoped-predecessor-delta-normalized.patch"
    if sha(patch_path.read_bytes()) != delta["patch_sha256"]:
        raise RuntimeError("bounded predecessor patch moved")
    attempts, errors = build_attempts(snapshot.events)
    if errors:
        raise RuntimeError("Attempt history is invalid: " + str(errors))
    model_records = [value for value in attempts.values() if value.get("runtime_provenance") is not None]
    if model_records:
        raise RuntimeError("new model provenance requires an actual attribution assessment")
    sealed = {}
    for relative, expected in provenance["sealed_log_hashes"].items():
        actual = sha((ROOT / relative).read_bytes())
        if actual != expected:
            raise RuntimeError("an inspected sealed segment changed: " + relative)
        sealed[relative] = actual
    owner_1171 = git("show", "dbbfad94688515d604b54e2c97dc92aa5fa7eab1:.saipen/BOARD.md").stdout.decode("utf-8-sig")
    owner_1171 = [line for line in owner_1171.splitlines() if " T-1171 " in line]
    if owner_1171 != original["T1171_committed_board"]:
        raise RuntimeError("historical ownership claim moved")
    memory_hashes = {name: sha((ROOT / (".saipen/" + name)).read_bytes())
                     for name in ("STATE.md", "BOARD.md", "LOG.md")}
    if read_history_snapshot(ROOT, lean=True).hash != snapshot.hash:
        raise RuntimeError("canonical history moved during read-only forensic verification")
    if tree_fingerprint(ROOT) != fingerprint:
        raise RuntimeError("production tree moved during forensic verification")
    for name, expected in assets.items():
        if sha((PREPARED / name).read_bytes()) != expected:
            raise RuntimeError("prepared evidence changed during verification")
    result = {"ok": True, "stage": stage, "work": "T-1713", "tree_fingerprint": fingerprint,
              "history_tail": snapshot.tail, "history_hash": snapshot.hash,
              "parsed_events": len(snapshot.events), "attempts": len(attempts),
              "model_bound_attempts": len(model_records), "assets": assets,
              "commits": commits, "subjects": subjects, "historical_reproductions": reproductions,
              "last_manifest_file_commit": last_manifest, "bounded_predecessors": predecessors,
              "matrix_sha256": sha((HERE / "MATRIX.md").read_bytes()),
              "sealed_log_hashes": sealed, "T1171_committed_board": owner_1171,
              "canonical_readback_hashes": memory_hashes,
              "limits": "Only exact manifest/helper subjects were executed, with current stdlib and explicit current protocol_dir. "
                        "Git author and canonical seats are not model authentication. HEAD is a tracked reference, "
                        "not an authenticated previous Gemini verified predecessor. machine_runtime.py has no tracked HEAD operand. "
                        "The operator explicitly confirms the missing model window/predecessor remains unknown. "
                        "No production, foreign consumer, ACL, Git index or sealed-history mutation."}
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "stage": stage, "history_events": len(snapshot.events),
                      "historical_reproductions": len(reproductions), "bounded_owners": len(predecessors),
                      "missing_tracked_operands": [p for p, v in predecessors.items() if not v["tracked_operand_available"]],
                      "model_bound_attempts": 0, "record": str(output), "tree_fingerprint": fingerprint}))


if __name__ == "__main__":
    main()
