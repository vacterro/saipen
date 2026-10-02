"""One-shot: add SRC-027 normalized requirements via the canonical CLI."""
import subprocess, sys, json

REQS = [
    ("R001", "invariant",
     "Three-way target recovery classifier: one canonical helper classify_target(current_hash, before_hash, after_hash) returns ALREADY_APPLIED when current==after, PENDING when current==before, CONFLICT otherwise; the three-way logic is centralized and never duplicated across resume, apply or conformance paths; before_hash==after_hash no-op target classifies deterministically as already-satisfied; missing-file creation and deletion states classify through the existing document and hash model with no second sentinel scheme --verification unit tests cover all three outcomes plus the no-op and missing-file shapes through the one helper"),
    ("R002", "invariant",
     "Recovery reconstructs progress from live target bytes, not from stale progress_index, applied_frontier or target.applied markers: targets are inspected in canonical operation order, every target classified, and the effective applied frontier rebuilt from actual target states; a legal prefix materialization resumes at the first pending target; non-prefix materialization such as BEFORE AFTER BEFORE fails closed with RECOVERY_CONFLICT unless the existing operation contract proves that state a legal crash shape --verification fixture matrix covers AFTER AFTER AFTER, AFTER AFTER BEFORE, AFTER BEFORE BEFORE, AFTER THIRD BEFORE and BEFORE AFTER BEFORE with deterministic outcomes"),
    ("R003", "invariant",
     "Journal metadata repair is idempotent and goes through the canonical journal writer: already-applied targets get target.applied=true and the effective progress and frontier agree with the real materialized prefix; semantically identical project files are never rewritten merely to satisfy the journal; no ad-hoc write_text JSON edits where Journal owns persistence; a crash during the bookkeeping repair is safely repeatable --verification instrumentation proves repair writes touch only recovery journal state and a mid-repair crash re-run converges"),
    ("R004", "requirement",
     "All-targets-already-applied recovery performs zero semantic replays: canonical post-apply verification runs, on success the operation advances through the ordinary legal terminal state machine to the current protocol terminal state, ordinary settlement and compaction run, and an exact retry returns the existing idempotent success result instead of creating another operation; no special terminal state is invented and verification is never bypassed because hashes match --verification ProTrail-shaped fixture converges to the normal committed terminal state and second recovery performs no new writes"),
    ("R005", "requirement",
     "Partial already-applied prefix resume: for a legal prefix recovery repairs journal progress, applies only the pending suffix targets, never rewrites materialized targets, then completes verification and commit; recovery must never depend on replay being harmless --verification write-instrumented fixture proves target 1 and 2 are not physically written and exactly target 3 is applied"),
    ("R006", "invariant",
     "Real conflicts stay conflicts: any target whose current hash is neither before_hash nor after_hash yields a deterministic RECOVERY_CONFLICT with operation_id, target path, expected before_hash, expected after_hash, actual hash, target index and recovered applied frontier reported; zero additional mutations after the conflict is discovered and remaining targets are untouched; CAS before_hash safety for fresh APPLY is not weakened --verification hostile fixture preserves unexpected bytes, returns the canonical conflict family and leaves conformance non-green"),
    ("R007", "requirement",
     "Status convergence rule: after successful recovery operation.json, progress.json and per-target applied markers agree through one canonical transition finalizer; a successful recovery never leaves PREPARED operation.json beside a terminal progress.json --verification split-brain regression asserts representation agreement after recovery"),
    ("R008", "invariant",
     "Conformance keeps detecting unresolved recovery debt: PREPARED plus targets equal to after_hash is not permanently valid; before recovery conformance may report debt, canonical recovery reconciles, after recovery conformance passes; the validator does not become an alternative recovery engine and mutation and validation authority stay separated --verification conformance regression shows debt before recovery and PASS only after canonical recovery"),
    ("R009", "requirement",
     "Deterministic fault-injection regressions around one multi-target operation covering crashes before PREPARED is durable, after PREPARED before first write, after target bytes before target journal progress, after journal progress, after all bytes before final frontier, after all applied before VERIFY, after VERIFY before terminal, and after terminal before settlement; every crash restarts recovery from disk with no duplicate semantic mutation, no target regression, deterministic final state, idempotent exact retry and convergence to the terminal committed state while third-state conflicts stay conflicts --verification fault-injection test matrix enumerates every listed window with restart-from-disk assertions"),
    ("R010", "requirement",
     "Exact ProTrail incident regression fixture: three-target operation with PREPARED operation metadata, stale journal target markers, interrupted or CONFLICT progress state, and all three live targets exactly equal to after_hash; canonical recovery asserts zero project target rewrites, all three targets ALREADY_APPLIED, journal metadata convergence, ordinary terminal committed state, normal settlement, no new writes on second recovery, idempotent exact retry success, and conformance PASS; the fixture fails on the pre-fix implementation --verification test constructs the unrepaired incident journal and asserts the full convergence list"),
    ("R011", "requirement",
     "Repeated recovery idempotence: recover(recover(x)) equals recover(x) for canonical semantic state at every recoverable state, with no duplicate receipts, no extra event ids, no target rewrite solely because recovery runs again and no journal state regression --verification idempotence test runs recovery at least twice per recoverable fixture state"),
    ("R012", "invariant",
     "Terminal settlement interaction preserved: a durable committed operation stays committed even if bounded receipt settlement cleanup fails; exact retry still locates canonical terminal authority and returns idempotent success; existing Journal terminal-settlement semantics are reused, no second path --verification settlement-failure regression asserts committed authority and idempotent retry"),
    ("R013", "requirement",
     "One semantic recovery implementation: startup or continue recovery, any explicit recovery command and any conformance-triggered recovery workflow all use the same classifier and reconciliation path; consolidation is limited to establishing that single path with no broad CLI redesign --verification entry-point regression drives recovery through each canonical entry point and asserts identical outcomes"),
    ("R014", "requirement",
     "Targeted recovery and journal tests pass first, then the complete repository test suite with exact PASS FAIL SKIPPED counts reported and environmental skips never converted to PASS; canonical project validation or conformance runs on a clean fixture --verification test transcript reports journal unit, recovery, mutation apply, source requirement add, conformance validate, idempotent retry and hostile fault-injection counts"),
    ("R015", "non-goal",
     "No journal schema redesign, no database, no validator auto-heal of arbitrary corruption, no deletion of recovery evidence, no weakening of before_hash CAS for normal fresh APPLY, no treating unexpected target content as success, no ProTrail special-casing, no manual recovery JSON patches, no new recovery commands unless no canonical entry point exists --verification diff inspection confirms none of the forbidden changes"),
]

def run(args):
    r = subprocess.run([sys.executable, "tools/saipen.py", *args, "--json"],
                       capture_output=True, text=True)
    try:
        out = json.loads(r.stdout)
    except Exception:
        out = {"ok": False, "raw": r.stdout[-400:], "err": r.stderr[-400:]}
    code = out.get("code")
    print(args[2] if len(args) > 2 else args[1], "->", code, "ok" if out.get("ok") else out.get("detail", "")[:160])
    return out.get("ok") or code in ("SOURCE_DUPLICATE",)

for rid, cls, text in REQS:
    run(["source", "req", "SRC-027", rid, cls, text])
