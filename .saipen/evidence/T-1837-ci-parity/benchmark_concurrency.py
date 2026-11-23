"""Bounded real mechanism corpus: compare workers, never certify the live suite."""
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

source = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(source / "tools"))
from saipen_engine import core_unit, test_runner

parser = argparse.ArgumentParser()
parser.add_argument("--output", required=True)
args = parser.parse_args()
modules = ["test_hermetic_env.py", "test_t1472_core_unit_shards.py",
           "test_t1505_core_unit_sandbox_reclaim.py", "test_t1830_verification_observations.py"]
record = {"scope": "frozen reduced real copy/shard/cleanup/membership corpus; not production suite",
          "runtime": sys.version, "platform": sys.platform, "modules": modules,
          "memory_peak_bytes": None, "memory_note": "not measured; no CI memory sizing inferred",
          "measurements": []}
with tempfile.TemporaryDirectory(prefix="saipen-ci-benchmark-") as directory:
    corpus = Path(directory) / "corpus"
    tools = corpus / "tools"
    tools.mkdir(parents=True)
    shutil.copytree(source / "tools/saipen_engine", tools / "saipen_engine",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in modules:
        shutil.copy2(source / "tools" / name, tools / name)
    # Run the same full discovery in this closed, explicitly reduced corpus.
    inventory_code = (
        "import unittest,json; "
        "s=unittest.TestLoader().discover('tools',pattern='test_*.py'); "
        "flatten=lambda s:[t for x in s for t in (flatten(x) if isinstance(x,unittest.TestSuite) else [x])]; "
        "print(json.dumps([(t.id(),type(t).__module__) for t in flatten(s)],separators=(',',':')))"
    )
    inventory_run = subprocess.run([sys.executable, "-B", "-c", inventory_code], cwd=corpus,
                                   capture_output=True, text=True, encoding="utf-8", check=True)
    inventory = json.loads(inventory_run.stdout)
    inventory_digest = hashlib.sha256(json.dumps(inventory, ensure_ascii=True,
        separators=(",", ":")).encode()).hexdigest()
    fingerprint = core_unit.tree_fingerprint(corpus)
    record.update(source_fingerprint=fingerprint, inventory_sha256=inventory_digest,
                  inventory=inventory, source_files=sum(p.is_file() for p in corpus.rglob("*")),
                  source_bytes=sum(p.stat().st_size for p in corpus.rglob("*") if p.is_file()))
    for jobs in (1, 2, 4):
        started = time.perf_counter()
        result = test_runner._unit_family_report(corpus, jobs=jobs)
        elapsed = time.perf_counter() - started
        proof = result.get("membership_proof")
        valid = (result["status"] == "PASS" and result.get("ran") == len(inventory)
                 and result.get("fingerprint") == fingerprint
                 and core_unit.tree_fingerprint(corpus) == fingerprint
                 and (jobs == 1 or proof == {"inventory_sha256": inventory_digest,
                                            "occurrences": len(inventory)}))
        measured = {"requested_jobs": jobs, "actual_jobs": result.get("jobs"),
                    "wall_s": round(elapsed, 6), "ran": result.get("ran"),
                    "status": result["status"], "same_scope_verified": valid,
                    "timings_s": result.get("timings_s"),
                    "discovery_process_s": result.get("discovery_process_s"),
                    "empty_shards": result.get("empty_shards", [])}
        record["measurements"].append(measured)
        Path(args.output + f".jobs{jobs}.json").write_text(json.dumps(result, indent=2) + "\n")
        Path(args.output).write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(measured), flush=True)
        if not valid:
            raise SystemExit("bounded corpus failed; do not infer a performance gain")
