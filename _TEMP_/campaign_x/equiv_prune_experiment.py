"""Wave B: findings-equivalence proof for pruning the frozen live-repo copy.

Method (single frozen copy -- findings immune to live-tree drift):
  1. freeze HOME once with the module's existing ignore hook (full surface);
  2. build source-layout and flat-layout homes from the manifest surface;
  3. capture findings with BOTH layouts on the FULL frozen copy;
  4. delete .saipen/evidence, .saipen/worktrees, .saipen/archive from the copy;
  5. capture findings with BOTH layouts again on the PRUNED copy;
  6. compare problem_keys (severity, detail_hash) per layout + ruleset fp.

If both layout comparisons are identical full-vs-pruned, the pruned trees are
measured-inert for this oracle and the production edit is justified.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import test_validator_layout_parity as vlp  # noqa: E402

PRUNE = (".saipen/evidence", ".saipen/worktrees", ".saipen/archive")


def keys(doc: dict) -> set[tuple[str, str]]:
    return {(p.get("severity", ""), p.get("detail_hash", "")) for p in doc.get("problems", [])}


def count_files(root: Path) -> tuple[int, int]:
    files = 0
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file():
                files += 1
                total += path.stat().st_size
        except OSError:
            continue
    return files, total


def capture(home: Path, project: Path, out: Path) -> dict:
    comp = vlp._capture_findings(home, project, out)
    assert out.is_file(), "no artifact: " + comp.stderr[-2000:]
    return json.loads(out.read_text(encoding="utf-8"))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="saipen-equiv-"))
    frozen = tmp / "live-project"
    t0 = time.perf_counter()
    shutil.copytree(vlp.HOME, frozen, ignore=vlp._ignore_runtime_state(vlp.HOME))
    copy_wall = time.perf_counter() - t0
    full_files, full_bytes = count_files(frozen)
    print(f"freeze: {copy_wall:.1f}s  files={full_files}  MB={full_bytes/1e6:.0f}", flush=True)

    source = tmp / "source-home"
    flat = tmp / "flat-home"
    source.mkdir(); flat.mkdir()
    vlp._build_home(source, flatten=False)
    vlp._build_home(flat, flatten=True)

    docs = {}
    for label, home in (("source", source), ("flat", flat)):
        t = time.perf_counter()
        doc = capture(home, frozen, tmp / f"full-{label}.json")
        docs[f"full-{label}"] = doc
        print(f"capture full/{label}: {time.perf_counter()-t:.1f}s problems={len(doc['problems'])}", flush=True)

    pruned_bytes = 0
    for rel in PRUNE:
        target = frozen / rel
        if target.is_dir():
            shutil.rmtree(target)
    pruned_files, pruned_bytes_total = count_files(frozen)
    print(f"pruned copy: files={pruned_files} MB={pruned_bytes_total/1e6:.0f}", flush=True)

    for label, home in (("source", source), ("flat", flat)):
        t = time.perf_counter()
        doc = capture(home, frozen, tmp / f"pruned-{label}.json")
        docs[f"pruned-{label}"] = doc
        print(f"capture pruned/{label}: {time.perf_counter()-t:.1f}s problems={len(doc['problems'])}", flush=True)

    report = {}
    ok = True
    for label in ("source", "flat"):
        full_doc, pruned_doc = docs[f"full-{label}"], docs[f"pruned-{label}"]
        same = keys(full_doc) == keys(pruned_doc)
        # extra strictness: identical problem details (fingerprint-independent)
        det_full = sorted((p.get("rule_id"), p.get("detail")) for p in full_doc.get("problems", []))
        det_pruned = sorted((p.get("rule_id"), p.get("detail")) for p in pruned_doc.get("problems", []))
        same_details = det_full == det_pruned
        report[label] = {
            "problem_keys_equal": same,
            "rule_and_detail_equal": same_details,
            "full_problems": len(full_doc.get("problems", [])),
            "pruned_problems": len(pruned_doc.get("problems", [])),
            "full_ruleset_fp": full_doc.get("ruleset_fingerprint"),
            "pruned_ruleset_fp": pruned_doc.get("ruleset_fingerprint"),
        }
        ok = ok and same
        print(label, json.dumps(report[label]), flush=True)
    # cross-layout parity in each phase (the oracle's own assertion)
    report["parity_full"] = keys(docs["full-source"]) == keys(docs["full-flat"])
    report["parity_pruned"] = keys(docs["pruned-source"]) == keys(docs["pruned-flat"])
    print("parity full:", report["parity_full"], " parity pruned:", report["parity_pruned"], flush=True)
    print("EQUIVALENCE:", "PROVEN" if ok and report["parity_pruned"] else "REFUTED", flush=True)
    shutil.rmtree(tmp, ignore_errors=True)


main()
