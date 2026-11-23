"""Throwaway: can a seeded run_scenarios crew project host the native review chain?"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from saipen_engine import operations, subs
from saipen_engine import focused_unit
from freshness import compute_source_identity

raw = tempfile.mkdtemp(prefix="t2040-exp-")
root = Path(raw) / "pre"
(root / ".saipen").mkdir(parents=True)
home = Path(raw) / "home"
(home / "extensions" / "subs" / "TEMPLATE" / "kitchen").mkdir(parents=True)
(home / "saipen").mkdir(parents=True)
(home / "saipen" / "BOOT.md").write_text("# probe installed protocol\n", encoding="utf-8")
(home / "extensions" / "subs" / "TEMPLATE" / "STATE.md").write_text(
    "---\nphase: PLAN\ntask: none\nnext_action: \"saipen plan\"\nblocker: none\n"
    "agent: <name>\nsaipen_version: 7\nschema_version: 3\nstyle_contract: ded-probe\n"
    "saipen_home: \"\"\nmode: read-only\ntransition_from: INIT\n"
    "updated: 2026-01-01T00:00:00Z\n---\n", encoding="utf-8")
(home / "extensions" / "subs" / "TEMPLATE" / "BOARD.md").write_text(
    "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n\n## BLOCKED\n", encoding="utf-8")
(home / "extensions" / "subs" / "TEMPLATE" / "LOG.md").write_text("# Log\n", encoding="utf-8")
(home / "extensions" / "subs" / "TEMPLATE" / "kitchen" / "OUTBOX.md").write_text(
    "# OUTBOX\n", encoding="utf-8")
# minimal role charter set (mirrors run_scenarios seeding)
from freshness import compute_role_revision
_charter = (
    "# {name} -- role\n\n```yaml\nrole_kind: {role_kind}\n"
    'write_scope: ".saipen/extensions/subs/{name}/"\ntrigger: "probe"\n'
    "collect_policy: {collect_policy}\ndone_condition: \"probe\"\n"
    'freshness_inputs: ["source_head", "source_tree_fingerprint", "role_revision"]\n'
    'output_contract: "PROTOCOL.md \u00a7 2 complete package"\n'
    'role_revision: "sha256:probe-{name}"\n```\n')
for _name in ("saihunt", "saitest", "saipython", "saiui", "saitranslate", "saiwiki"):
    _producer = _name in ("saitranslate", "saiwiki")
    _path = home / "extensions" / "subs" / f"{_name}.md"
    _path.write_text(_charter.format(name=_name,
        role_kind="PRODUCER" if _producer else "SCOUT",
        collect_policy="explicit" if _producer else "core-review"), encoding="utf-8")
    _path.write_text(_path.read_text(encoding="utf-8").replace(
        f'role_revision: "sha256:probe-{_name}"',
        f'role_revision: "{compute_role_revision(_path)}"'), encoding="utf-8")
for _shared in ("PROTOCOL.md", "README.md", "crew.md"):
    (home / "extensions" / "subs" / _shared).write_text(
        f"# {_shared}\nprobe shared content\n", encoding="utf-8")

(root / ".saipen" / "STATE.md").write_text(
    '---\nphase: DONE\ntask: none\nnext_action: "saipen continue"\nblocker: ""\n'
    "transition_from: SHIP\nsaipen_version: 7\nschema_version: 3\nstyle_contract: "
    'ded-probe\nsaipen_home: "' + home.as_posix() + '"\nagent: probe\nmode: full\n'
    'updated: "2026-08-13T00:00:00Z"\n---\n', encoding="utf-8")
(root / ".saipen" / "LOG.md").write_text("# Log\n", encoding="utf-8")
(root / ".saipen" / "BOARD.md").write_text(
    "# Board\n\n## DOING\n\n## TODO\n\n## DONE\n\n## BLOCKED\n", encoding="utf-8")
(root / ".saipen" / "extensions").mkdir(exist_ok=True)

print("spawn:", subs.sub_spawn(root, "saihunt", home.as_posix()).to_dict())
state_path = root / subs.SUBS_REL / "saihunt" / "STATE.md"
text = state_path.read_text(encoding="utf-8").replace("phase: PLAN", "phase: DONE").replace(
    "transition_from: INIT", "transition_from: PLAN")
state_path.write_text(text, encoding="utf-8")

(root / "tools").mkdir(exist_ok=True)
(root / "tools/test_review.py").write_text(
    "import unittest\nclass Review(unittest.TestCase):\n"
    "    def test_premise(self): self.assertEqual(2 + 2, 4)\n", encoding="utf-8")

source = compute_source_identity(root)
revision = subs.current_local_role_revision(root, "saihunt", home.as_posix())
outbox = root / subs.SUBS_REL / "saihunt" / "kitchen/OUTBOX.md"
outbox.write_text(
    "# OUTBOX\n\n## HUNT-900: complete evidence\n"
    "- **status:** ready\n- **producer:** saihunt\n"
    f"- **source_head:** {source.source_head}\n"
    f"- **source_tree_fingerprint:** {source.source_tree_fingerprint}\n"
    f"- **role_revision:** {revision}\n- **coverage:** complete role surface\n"
    "- **payload:** []\n- **verified:** PASS -- probe\n"
    "- **instructions:** Core reviews evidence\n", encoding="utf-8")
package = subs.parse_outbox(outbox.read_text(encoding="utf-8"), "saihunt").packages[0]
collected = subs.sub_collect(root, "saihunt", agent="probe")
print("collect:", collected.code, collected.ok)
ticket = collected.data["tickets"][0]["ticket"]
print("ticket:", ticket)
print("claim:", operations.apply_claim(root, ticket, "probe").to_dict())
for phase in ("BUILD", "VERIFY"):
    r = operations.transition_phase(root, phase, "probe", ticket)
    print(f"transition {phase}:", r.ok, r.code, r.message)
record = focused_unit.run_focused(root, ["test_review.py"], timeout=60)
print("focused:", record["verdict"], record.get("problem"))
relative = focused_unit.RECORD_DIR_REL + "/exp-review.json"
p = root / relative
p.parent.mkdir(parents=True, exist_ok=True)
body = (json.dumps(record) + "\n").encode("utf-8")
p.write_bytes(body)
citation = f"record:{relative} sha256:{hashlib.sha256(body).hexdigest()}"
ex = operations.checkpoint(root, "probe", "RUN", ticket,
                           f"{focused_unit.MARKER} PASS conf: high ran:1 {citation}")
print("executed:", ex.ok, ex.code, ex.message)
bindings = subs._package_review_bindings(package, collected.op_id)
rev = operations.checkpoint(root, "probe", "RUN", ticket,
    "review -> PASS conf: high -- premise disproven: the hypothesis is refuted; "
    + "; ".join(f"{k}={v}" for k, v in bindings.items()) + "; " + citation)
print("review:", rev.ok, rev.code, rev.message)
proof, problem = subs._independent_core_review(root, package, ticket, collected.op_id,
                                               tuple(subs._iter_operation_records(root)))
print("proof:", proof, problem)
for phase in ("REVIEW", "SHIP"):
    r = operations.transition_phase(root, phase, "probe", ticket)
    print(f"transition {phase}:", r.ok, r.code, r.message)
fin = operations.finish_ticket(root, ticket, "probe", closure_mode="finding_invalidated",
                               invalidation_evidence=proof["review_event"] if proof else "E-0")
print("finish:", fin.ok, fin.code, fin.message)
disposed = subs.sub_disposition(root, "saihunt", package.package_id, agent="probe")
print("dispose:", disposed.ok, disposed.code, disposed.message)
