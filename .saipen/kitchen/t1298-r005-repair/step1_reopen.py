"""T-1298 R005 corrective history: canonical reopen checkpoint + coverage move."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import intake, operations  # noqa: E402

DESCRIPTION = (
    "SRC-025:R005 reopened UNKNOWN for corrected repair. E-5893's evidence remains "
    "historically real (163 transport suites, 241 focused, 1260 full unittest, Ruff, "
    "validate 0 FAIL) but its R005 conclusion was invalid: "
    "test_retry_after_the_allocator_is_lost_is_a_new_honest_dispatch codified duplicate "
    "dispatch of the SAME producer_operation_id after allocator loss (op-1 body X -> "
    "layer 1; allocator deleted; retry SAME op -> ok=true layer=2 idempotent=false; "
    "audit/1.md + audit/2.md). No binding history does NOT imply no producer-operation "
    "history: a live canonical audit layer may itself be API-created before the allocator "
    "was lost, so layer bytes alone cannot distinguish a virgin manual audit/99.md from "
    "an API-created layer whose allocator projection was lost. R006-R009 remain VERIFIED "
    "and are not reopened; R001-R004 and R010-R013 remain UNKNOWN. Repair scope: durable "
    "producer-operation identity authority under .saipen/intake/, red controls first, "
    "coverage moved canonically via source disp; no coverage JSON hand-edit; E-5893 not "
    "rewritten."
)

result = operations.checkpoint(
    ROOT,
    "codex-astra",
    "DEC",
    "T-1298",
    DESCRIPTION,
)
print(result)
if not result.get("ok"):
    sys.exit(1)

disp = intake.set_disposition(
    ROOT,
    "SRC-025",
    "R005",
    "UNKNOWN",
    evidence="E-5896",
    verification="reopened pending corrected R005 verification (durable operation identity)",
)
print(disp)
if not disp.get("ok"):
    sys.exit(1)
