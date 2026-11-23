"""Capture exact tracked-to-pre-fix deltas, with no model or green attribution."""
import ast
import difflib
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
stage = sys.argv[1] if len(sys.argv) > 1 else "scoped-predecessor-delta"
OUTPUT = HERE / (stage + ".json")
if OUTPUT.exists():
    raise SystemExit("Existing predecessor evidence is immutable")
owners = ["audit_manifest.py", "paths.py", "host_bootstrap.py", "machine_runtime.py",
          "protocol_admission.py", "admission.py", "reconcile.py", "init_project.py",
          ]
head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                      check=True, capture_output=True).stdout.decode().strip()
rows = {}
patches = []
for name in owners:
    relative = "tools/saipen_engine/" + name
    tracked = subprocess.run(["git", "show", head + ":" + relative], cwd=ROOT,
                             capture_output=True, check=False)
    preserved = HERE / "production-before" / relative
    path = preserved if preserved.is_file() else ROOT / relative
    if not path.is_file():
        rows[relative] = {"scope": "requested path absent; no replacement guessed"}
        continue
    current = path.read_bytes()
    old = tracked.stdout if tracked.returncode == 0 else None
    changed_symbols = []
    if old is not None:
        def symbols(raw):
            tree = ast.parse(raw.decode("utf-8-sig"))
            return {node.name: ast.dump(node, include_attributes=False)
                    for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        before_symbols, after_symbols = symbols(old), symbols(current)
        changed_symbols = sorted(name for name in before_symbols.keys() | after_symbols.keys()
                                 if before_symbols.get(name) != after_symbols.get(name))
        patches.extend(difflib.unified_diff(old.decode("utf-8-sig").replace("\r\n", "\n").splitlines(keepends=True),
                                           current.decode("utf-8-sig").replace("\r\n", "\n").splitlines(keepends=True),
                                           fromfile=head + ":" + relative,
                                           tofile="preserved-pre-T1712:" + relative))
    rows[relative] = {
        "tracked_head_sha256": hashlib.sha256(old).hexdigest() if old is not None else None,
        "pre_fix_sha256": hashlib.sha256(current).hexdigest(),
        "identical_bytes": old == current,
        "preserved_before_path": str(path.relative_to(ROOT)),
        "changed_top_level_symbols": changed_symbols,
    }
patch = "".join(patches).encode("utf-8")
(HERE / (stage + ".patch")).write_bytes(patch)
result = {"tracked_head": head, "owners": rows,
          "patch_sha256": hashlib.sha256(patch).hexdigest(),
          "patch_rendering": "CRLF folded to LF for readable diff; raw identities above remain exact",
          "limits": "HEAD is a tracked reference, not a proven last verified predecessor. "
                    "Preserved pre-T1712 bytes exclude this Work's repairs. "
                    "Uncommitted deltas have no inferred model, timestamp or author."}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"tracked_head": head,
                  "changed_symbols": {key: value.get("changed_top_level_symbols")
                                      for key, value in rows.items()},
                  "patch_bytes": len(patch), "evidence": str(OUTPUT)}))
