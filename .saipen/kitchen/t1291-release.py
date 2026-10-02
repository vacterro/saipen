"""Prepare the reviewed feature's release metadata using the shared inventory."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine.release_contract import version_metadata_paths

previous = (ROOT / "VERSION").read_text().strip()
version = "7.254.0"
if previous != "7.253.0":
    raise SystemExit(f"Expected 7.253.0, found {previous}; re-evaluate release metadata")
updates = {}
for rel in version_metadata_paths(ROOT):
    path = ROOT / rel
    if not path.name.startswith("README"):
        continue
    raw = path.read_bytes()
    badge = f"**v{previous}**".encode()
    if raw.count(badge) != 1:
        raise SystemExit(f"Expected one current badge in {rel}")
    updates[path] = raw.replace(badge, f"**v{version}**".encode(), 1)
changelog = ROOT / "CHANGELOG.md"
raw = changelog.read_bytes()
entry = (
    "## 7.254.0 -- 2026-09-05 -- Retrieve Durable Project Lessons (T-1291, SRC-020)\n\n"
    "Optional KNOWLEDGE cards carry a reusable claim, its Why, evidence, and retrieval scope. "
    "Cold decision context receives only matching active cards; existing free-form knowledge remains valid.\n\n"
    "- Add a stdlib card parser, structural validation, explicit supersession, seven-criterion promotion gate, "
    "deterministic index projection, and knowledge status/index/retrieve commands.\n"
    "- Keep manually authored INDEX.md valid and refuse to overwrite it. Reject incoherent supersession "
    "during fallback retrieval and return CLI failures for invalid cards.\n"
    "- Preserve legacy documents; dogfood three existing lessons. The generated index is 4882 bytes. "
    "Same-checkpoint unrelated cold context remains 3809 bytes / 979 repository-counted tokens. "
    "Freshness still reads the tree internally; context selection is bounded.\n"
    "- Verify 1170 unit tests (one skip), 39 focused knowledge tests, four pre-fix red/post-fix green "
    "review regressions, and the canonical validator/audit/scenario/lint gates. "
    "T-1292 tracks the missing permanent audit_checks control for the new structured validator check.\n"
    "- SRC-020 has ten verified actionable clauses. Full implementation evidence and limitations: "
    ".saipen/kitchen/t1291-review.md.\n\n"
).encode()
match = re.search(rb"(?m)^## ", raw)
if match is None:
    raise SystemExit("No changelog version anchor")
updates[changelog] = raw[:match.start()] + entry + raw[match.start():]
updates[ROOT / "VERSION"] = (version + "\n").encode()
for path, content in updates.items():
    path.write_bytes(content)
print(f"Prepared v{version}: {len(updates)} metadata files")
