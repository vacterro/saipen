"""T-1298 R005 corrected repair: canonical build/verify checkpoints + coverage."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import intake, operations  # noqa: E402

BUILD_TEXT = (
    "build -> durable operation identity authority for SRC-025:R005 (W2-001 corrected). "
    "audit_enqueue.py: new strictly decoded per-operation records under "
    ".saipen/intake/audit_operations/ (filename op-<sha256(producer + ' ' + op-id)>.json, "
    "never a user-controlled path component; fields schema_version/producer/"
    "producer_operation_id/producer_item_id/layer/sha256/created_at/state; states "
    "RESERVED/COMMITTED/ABORTED; ABORTED is the explicit refused-placement terminal that "
    "keeps the id spent without a poisoned reservation or deleted evidence). enqueue now: "
    "reads the durable record under the allocator lock and fails closed on "
    "OPERATION_RECORD_CORRUPT; rebuilds the allocator projection from durable records "
    "after allocator loss and recovers the SAME layer for the same operation (allocator "
    "loss can no longer allocate a second layer for the same producer_operation_id); "
    "refuses NEEDS_REPAIR when binding history exists but no durable identity can prove "
    "or refute a retry; treats a record-less operation as genuinely new only when the "
    "durable era is active (records exist), preserving genuine genesis (manual audit/99.md "
    "+ first API op -> fresh layer 100); refuses AUTHORITY_CONFLICT when the record and a "
    "healthy allocator disagree on layer or digest, when an ABORTED record coexists with a "
    "live allocation, or when a backfill would overwrite a disagreeing record; re-projects "
    "a durable record the projection lost (crash after identity reservation, before "
    "projection write) and finishes the SAME layer; backfills missing records from a valid "
    "allocator under the same lock with exact readback (one-time migration when the "
    "authority directory is absent, idempotent, identity never altered); promotes "
    "COMMITTED to whichever authority lags. Refused placement marks the record ABORTED and "
    "stays retryable with the spent number never reused. saipen.py audit enqueue --dry-run "
    "consults the same identity authority (corrupt record refuses the plan). Docs: "
    "saipen/SOURCES.md producer-enqueue contract no longer claims the allocator is the "
    "sole durable operation identity authority; saipen/REGISTRY.json audit_enqueue "
    "projection records the authority directory and record states. Red controls first: "
    "AllocatorLoss suite pre-fix ran 7 failures + 6 errors, with the exact control "
    "op-1 body X -> layer 1, allocator deleted, retry SAME op -> layer 2 idempotent=false "
    "reproduced on the live v8.0.0 code path."
)

VERIFY_TEXT = (
    "VERIFY PASS conf: high -- SRC-025:R005 corrected verification. Key property: retry of "
    "the same producer_operation_id after allocator loss can no longer allocate a second "
    "layer. Focused R005 matrix in tools/test_audit_enqueue.py AllocatorLoss (18 cases): "
    "same op + same bytes + allocator loss recovers layer 1 idempotently and rematerializes "
    "the projection; same op + different bytes after loss CONFLICT; different op same bytes "
    "stays independent (layer 2, idempotent=false); different producer same op id stays "
    "distinct; virgin manual 99 + first API op -> layer 100; consumed layer represented "
    "only by binding recovers the original delivered identity (binding_state DELETED); "
    "corrupt record, filename/key mismatch, and record-vs-allocator disagreement all fail "
    "closed with no layer created; crash after durable reservation before projection "
    "recovers the reserved layer 10; crash after placement before commit promotes BOTH "
    "authorities to COMMITTED; refused placement -> ABORTED record, retry fresh, spent "
    "number never reused; repeated recovery idempotent and byte-stable; equal-digest "
    "layers never select identity by digest order (op-2 recovers its own layer 2); valid "
    "pre-existing allocator backfills durable records with exact readback. Pre-fix red: "
    "7 failures + 6 errors, exact duplicate dispatch reproduced. Suites: 3 transport suites "
    "174 OK; transport-loop/ingest/dogfood/provenance/envelope 37 OK; combined 7 suites "
    "211 OK; full unittest discover 1271 OK 1 skipped. Ruff clean on "
    "audit_enqueue.py, saipen.py, test_audit_enqueue.py. Live tools/validate.py 0 FAIL "
    "with 27 known warnings. Live CLI reproduction on a scratch project: op-1 layer 1; "
    "allocator deleted; retry SAME op-1 -> ok=true layer=1 idempotent=true (audit/1.md "
    "only); op-2 same body -> layer 2 idempotent=false; manual audit/99.md + first API op "
    "identical bytes -> layer 100 with 99.md untouched. audit_checks --changed on the five "
    "changed paths selected zero controls and hit the already-known T-1287/PERF-004 "
    "ThreadPoolExecutor crash -- recorded, not fixed in this repair. E-5893 is not reused "
    "as R005 evidence; R006-R009 remain VERIFIED and their tests untouched as regression "
    "guards; no release, no CHANGELOG."
)

results = []
build = operations.checkpoint(ROOT, "codex-astra", "RUN", "T-1298", BUILD_TEXT)
print(build)
if not build.get("ok"):
    sys.exit(1)
results.append(build.data.get("event_id"))

to_verify = operations.transition_phase(
    ROOT, "VERIFY", "codex-astra", ticket_id="T-1298",
    event_text="Corrected R005 implementation complete; verification gates next",
)
print(to_verify)
if not to_verify.get("ok"):
    sys.exit(1)
results.append(to_verify.data.get("event_id"))

verify = operations.checkpoint(ROOT, "codex-astra", "RUN", "T-1298", VERIFY_TEXT)
print(verify)
if not verify.get("ok"):
    sys.exit(1)
results.append(verify.data.get("event_id"))

disp = intake.set_disposition(
    ROOT,
    "SRC-025",
    "R005",
    "VERIFIED",
    evidence=str(verify.data.get("event_id")),
    verification=(
        "unittest:tools.test_audit_enqueue AllocatorLoss 18-case R005 matrix (pre-fix "
        "7 FAIL + 6 ERROR red controls) + tools.test_audit_enqueue_boundary + "
        "tools.test_audit_inbox 174 OK; transport-loop/ingest families 37 OK; combined "
        "211 OK; full unittest discover 1271 OK 1 skip; ruff PASS; tools/validate.py 0 "
        "FAIL 27 known warnings; live CLI repro: same-op retry after allocator loss "
        "recovers layer 1 idempotently, never a second layer"
    ),
)
print(disp)
if not disp.get("ok"):
    sys.exit(1)

to_build = operations.transition_phase(
    ROOT, "BUILD", "codex-astra", ticket_id="T-1298",
    event_text=(
        "SRC-025:R005 corrected VERIFIED; R006-R009 remain VERIFIED; SRC-025 still open: "
        "R001-R004 (CORE) and R010-R013 (PERF) UNKNOWN; T-1298 stays active"
    ),
)
print(to_build)
if not to_build.get("ok"):
    sys.exit(1)
results.append(to_build.data.get("event_id"))
print("EVENTS", results)
