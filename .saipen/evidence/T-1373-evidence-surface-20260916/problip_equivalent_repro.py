"""SRC-054 end-to-end reproduction on a Problip-equivalent fixture.

Real bytes, real commands. Problip's current protocol memory -- its
pre-SRC-054 MANIFEST.json, the LOG and archived coverage that cite the PERF-001
proof, and the proof file itself -- is copied into a disposable git worktree
outside every repository. The fixture is driven only through the real SAIPEN
CLI of the given checkout and packed only through AUDAPACK's real
``pack_single`` with the operator's packing configuration. Problip is read,
never written: its protocol memory is hashed before and after, and so are the
SAIPEN checkout's own canonical files, because a fixture that leaks writes into
a real ledger succeeds against the wrong project and fails nothing.

Checks (each one PASS/FAIL, exit status 1 on any FAIL):

  A  fixture starts from Problip's exact pre-SRC-054 contract (no evidence/)
  B  lifecycle `continue` regenerates it and evidence/ is declared
  C  pack 1 contains the proof, source/archive sha256 equal, COMPLETE
  D  an older protocol rewrites the pre-SRC-054 contract; lifecycle `recover`
     restores evidence/; read-only `status` changes nothing
  E  pack 2 still contains the proof, COMPLETE
  F  the proof excluded from the ZIP -> PROTOCOL_INCOMPLETE, omission cites
     the closure records
  G  pre-SRC-054 contract the gate does not regenerate -> the proof is
     collected through its citation anyway, COMPLETE
  H  the proof deleted on disk -> PROTOCOL_INCOMPLETE, evidence_absent_on_disk
  I  a project without evidence/ enrolls and packs COMPLETE, no new obligation
  J  the historical Problip archive, re-judged by the repaired accounting, is
     not COMPLETE (it lacks the cited proof)
  K  read-only `saipen audit manifest` on live Problip reports the upgrade
     the next lifecycle run performs
  L  no write reached Problip or the SAIPEN checkout's canonical files

Usage:
  python problip_equivalent_repro.py --work <empty scratch dir> [--json out.json]
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve()
DEFAULT_SAIPEN = HERE.parents[3]
DEFAULT_AUDAPACK = Path(r"V:\___VAC\__K\__CODE\_PY\_AUDAPACK")
DEFAULT_PROBLIP = Path(r"V:\___VAC\__K\__CODE\_PY\_PROBLIP")
#: The pre-SRC-054 contract this reproduction starts from. It is PINNED, not
#: read from the live Problip project: once the fix migrated that project the
#: live bytes stopped being a pre-fix starting point, and an oracle whose
#: known-bad input is whatever the world currently holds stops measuring the
#: change. Regenerate it with the PRE-FIX producer (git show HEAD before
#: T-1373) if it is ever lost.
DEFAULT_PRE_FIX_MANIFEST = HERE.parent / "problip-pre-src054-manifest.json"
DEFAULT_HISTORICAL = Path(
    r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\__TO_AUDIT\_PROBLIP_16.09.26-T22-56-13.zip"
)
AUDAPACK_CONFIG = Path(os.environ.get("LOCALAPPDATA", "")) / "AUDAPACK" / "config" / "config.json"

PROOF_REL = ".saipen/evidence/PERF-001_WINDOWS_EVIDENCE.md"
EXPECTED_PROOF_SHA256 = "7856719211E999FA47B0C8D21B3F6615BE12AFE0E73D4E4DDDD97D5242C14C9C"
HOST_SESSION_VARIABLES = (
    "SAIPEN_PROJECT_ROOT",
    "SAIPEN_PROJECT_LINEAGE",
    "SAIPEN_AGENT",
    "SAIPEN_CAPABILITY",
    "SAIPEN_HOST_ENFORCEMENT",
    "SAIPEN_RUNTIME_INFO",
    "SAIPEN_SKILL_ROOT",
    "SAIPEN_GUARD_STARTUP_PROBE",
)

RESULTS: list[dict] = []


def check(code: str, ok: bool, detail: str) -> bool:
    RESULTS.append({"check": code, "result": "PASS" if ok else "FAIL", "detail": detail})
    print(f"{code} {'PASS' if ok else 'FAIL'} -- {detail}")
    return ok


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def tree_digest(root: Path, skip: tuple[str, ...] = ()) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if any(rel == s or rel.startswith(s + "/") for s in skip):
            continue
        try:
            if path.is_file() and not path.is_symlink():
                out[rel] = sha256(path.read_bytes())
        except OSError:
            out[rel] = "UNREADABLE"
    return out


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )


def saipen(saipen_root: Path, project: Path, *args: str) -> dict:
    """The real CLI of the checkout under test, bound explicitly to the fixture."""
    env = {k: v for k, v in os.environ.items() if k not in HOST_SESSION_VARIABLES}
    env.update({"PWD": str(project), "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    proc = subprocess.run(
        [sys.executable, str(saipen_root / "tools" / "saipen.py"), "--project-root", str(project), "--json", *args],
        cwd=str(project),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=300,
    )
    try:
        payload = json.loads(proc.stdout)
    except ValueError:
        payload = {"_stdout": proc.stdout[-800:], "_stderr": proc.stderr[-800:]}
    payload["_rc"] = proc.returncode
    return payload


def manifest(project: Path) -> dict:
    return json.loads((project / ".saipen" / "MANIFEST.json").read_text(encoding="utf-8"))


def declares_evidence(doc: dict) -> bool:
    return any(rule.get("path") == "evidence" for rule in doc["evidence"]["conditional"])


def set_saipen_home(project: Path, home: Path) -> None:
    state = project / ".saipen" / "STATE.md"
    lines = state.read_text(encoding="utf-8").splitlines(keepends=True)
    home_text = str(home).replace("\\", "\\\\")
    state.write_text(
        "".join(
            f'saipen_home: "{home_text}"\n' if line.startswith("saipen_home:") else line
            for line in lines
        ),
        encoding="utf-8",
    )


def touch_newer(path: Path, *others: Path) -> None:
    newest = max(p.stat().st_mtime_ns for p in others)
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, max(st.st_mtime_ns, newest) + 2_000_000))


def packing_config(PackingConfig, **overrides):
    data = {}
    try:
        data = json.loads(AUDAPACK_CONFIG.read_text(encoding="utf-8")).get("packing", {})
    except (OSError, ValueError):
        pass
    names = {f.name for f in dataclasses.fields(PackingConfig)}
    kwargs = {k: v for k, v in data.items() if k in names}
    kwargs.update(overrides)
    return PackingConfig(**kwargs)


def pack(project: Path, out: Path, stem: str, **overrides):
    from audapack.config import PackingConfig
    from audapack.packing import MANIFEST_FILENAME, pack_single

    out.mkdir(parents=True, exist_ok=True)
    packing = packing_config(PackingConfig, output_dir=str(out), delete_old=False, **overrides)
    result = pack_single(
        source_path=project,
        output_dir=out,
        archive_stem=stem,
        excludes=set(packing.excludes),
        delete_old=False,
        include_timestamp=False,
        manifest_meta={"project_name": stem},
        packing=packing,
    )
    if not result.success:
        return result, None, None, None
    with zipfile.ZipFile(result.output_path) as zf:
        names = set(zf.namelist())
        snapshot = json.loads(zf.read(MANIFEST_FILENAME))["saipen_snapshot"]
        proof = zf.read(PROOF_REL) if PROOF_REL in names else None
        contract = json.loads(zf.read(".saipen/MANIFEST.json"))
    return result, snapshot, proof, contract


#: A snapshot is authoritative as COMPLETE or as COMPLETE_WITH_OPTIONAL_OMISSIONS:
#: the optional tier exists so that absent supporting material is honest instead
#: of degrading. Pinning the verdict to the first spelling made an unrelated
#: nested `.git/` under an optional surface read as a failure of the evidence
#: contract, so the checks below assert the invariant that matters -- no
#: REQUIRED omission -- and let the optional tier say what it is for.
COMPLETE_STATUSES = ("COMPLETE", "COMPLETE_WITH_OPTIONAL_OMISSIONS")


def build_fixture(
    problip: Path, fixture: Path, saipen_root: Path, *, pre_fix_manifest: bytes | None = None
) -> None:
    fixture.mkdir(parents=True)
    shutil.copytree(
        problip / ".saipen",
        fixture / ".saipen",
        ignore=shutil.ignore_patterns("locks", "recovery"),
    )
    if pre_fix_manifest is not None:
        # The live project migrates exactly once; the starting contract is
        # pinned so this reproduction keeps starting where the defect was.
        (fixture / ".saipen" / "MANIFEST.json").write_bytes(pre_fix_manifest)
    shutil.copy2(problip / ".gitignore", fixture / ".gitignore")
    (fixture / "README.md").write_text("Problip-equivalent fixture (SRC-054)\n", encoding="utf-8")
    set_saipen_home(fixture, saipen_root)
    git(fixture, "init", "-q")
    git(fixture, "add", "-A")
    git(fixture, "commit", "-q", "-m", "fixture")


def build_plain_project(project: Path, saipen_root: Path) -> None:
    sys.path.insert(0, str(saipen_root / "tools"))
    from saipen_engine.journal import ensure_project_lineage

    sp = project / ".saipen"
    sp.mkdir(parents=True)
    (sp / "STATE.md").write_text(
        "---\nphase: DONE\ntask: none\nnext_action: \"saipen continue\"\nblocker: \"\"\n"
        "transition_from: DONE\nsaipen_version: 8\nschema_version: 3\nlast_event: 1\n"
        "style_contract: ded-4ae736e4\n"
        f"saipen_home: \"{str(saipen_root).replace(chr(92), chr(92) * 2)}\"\n"
        "agent: tester\nmode: full\nupdated: \"2026-09-16T00:00:00Z\"\nexecution_intent: normal\n---\n",
        encoding="utf-8",
    )
    (sp / "BOARD.md").write_text("## DOING\n## TODO\n## DONE\n## BLOCKED\n", encoding="utf-8")
    (sp / "LOG.md").write_text("- 16.09.26 00:00 [E-001] [agent: tester] RUN: fixture -> PASS\n", encoding="utf-8")
    ensure_project_lineage(project)
    (project / "app.py").write_text("print('x')\n", encoding="utf-8")
    (project / ".gitignore").write_text(".saipen/\n", encoding="utf-8")
    git(project, "init", "-q")
    git(project, "add", "-A")
    git(project, "commit", "-q", "-m", "plain")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--saipen-root", type=Path, default=DEFAULT_SAIPEN)
    parser.add_argument("--audapack-root", type=Path, default=DEFAULT_AUDAPACK)
    parser.add_argument("--problip-root", type=Path, default=DEFAULT_PROBLIP)
    parser.add_argument("--historical-archive", type=Path, default=DEFAULT_HISTORICAL)
    parser.add_argument("--pre-fix-manifest", type=Path, default=DEFAULT_PRE_FIX_MANIFEST)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    for key in HOST_SESSION_VARIABLES:
        os.environ.pop(key, None)
    sys.path.insert(0, str(args.audapack_root))
    from audapack import saipen_evidence as se

    work = args.work.resolve()
    if work.exists() and any(work.iterdir()):
        print(f"--work must be empty or absent: {work}")
        return 2
    work.mkdir(parents=True, exist_ok=True)

    problip_before = tree_digest(args.problip_root / ".saipen", skip=("locks",))
    canonical = [args.saipen_root / ".saipen" / name for name in ("STATE.md", "BOARD.md", "LOG.md", "MANIFEST.json")]
    saipen_before = {str(p): sha256(p.read_bytes()) if p.is_file() else None for p in canonical}

    pre_fix_bytes = args.pre_fix_manifest.read_bytes()
    source_proof = (args.problip_root / PROOF_REL).read_bytes()
    check(
        "0",
        sha256(source_proof) == EXPECTED_PROOF_SHA256,
        f"Problip proof sha256 {sha256(source_proof)[:16]}.. matches the recorded closure hash",
    )

    fixture = work / "_PROBLIP_EQ"
    build_fixture(args.problip_root, fixture, args.saipen_root, pre_fix_manifest=pre_fix_bytes)
    doc = manifest(fixture)
    check("A", not declares_evidence(doc) and "references" not in doc,
          "fixture starts from Problip's pre-SRC-054 contract: conditional="
          + ",".join(rule["path"] for rule in doc["evidence"]["conditional"]))

    cont = saipen(args.saipen_root, fixture, "continue")
    doc = manifest(fixture)
    check("B", declares_evidence(doc) and "references" in doc,
          f"`saipen continue` rc={cont['_rc']} audit_manifest="
          f"{(cont.get('audit_manifest') or {}).get('code')} -> conditional="
          + ",".join(rule["path"] for rule in doc["evidence"]["conditional"]))

    result, snapshot, proof, contract = pack(fixture, work / "out1", "_PROBLIP_EQ_1")
    check(
        "C",
        bool(result.success) and proof is not None and sha256(proof) == sha256(source_proof)
        and snapshot["status"] in COMPLETE_STATUSES and not snapshot["required_evidence_omitted"]
        and snapshot["omitted_required"] == [] and declares_evidence(contract),
        f"pack 1 success={result.success} proof_in_zip={proof is not None} "
        f"sha_equal={proof is not None and sha256(proof) == sha256(source_proof)} "
        f"status={snapshot and snapshot['status']} collected/in_archive="
        f"{snapshot and snapshot['evidence_files_collected']}/{snapshot and snapshot['evidence_files_in_archive']} "
        f"cited={snapshot and snapshot['evidence_citations']['cited_files']}",
    )

    (fixture / ".saipen" / "MANIFEST.json").write_bytes(pre_fix_bytes)
    rec = saipen(args.saipen_root, fixture, "recover")
    restored = declares_evidence(manifest(fixture))
    before_status = (fixture / ".saipen" / "MANIFEST.json").read_bytes()
    stat = saipen(args.saipen_root, fixture, "status")
    unchanged = (fixture / ".saipen" / "MANIFEST.json").read_bytes() == before_status
    check("D", restored and unchanged,
          f"older-protocol rewrite then `saipen recover` rc={rec['_rc']} audit_manifest="
          f"{(rec.get('audit_manifest') or {}).get('code')} evidence_declared={restored}; "
          f"`saipen status` rc={stat['_rc']} left the manifest byte-identical={unchanged}")

    result, snapshot, proof, _ = pack(fixture, work / "out2", "_PROBLIP_EQ_2")
    check("E", bool(result.success) and proof == source_proof and snapshot["status"] in COMPLETE_STATUSES
          and snapshot["omitted_required"] == [],
          f"pack 2 success={result.success} proof_in_zip={proof is not None} status={snapshot and snapshot['status']}")

    result, snapshot, proof, _ = pack(fixture, work / "out3", "_PROBLIP_EQ_EXCLUDED", always_exclude=[PROOF_REL])
    omitted = {item["path"]: item for item in (snapshot or {}).get("omitted_required", [])}
    check(
        "F",
        bool(result.success) and proof is None and snapshot["status"] == se.STATUS_PROTOCOL_INCOMPLETE
        and snapshot["required_evidence_omitted"] and PROOF_REL in omitted,
        f"proof excluded: status={snapshot and snapshot['status']} required_evidence_omitted="
        f"{snapshot and snapshot['required_evidence_omitted']} omission={omitted.get(PROOF_REL)}",
    )

    (fixture / ".saipen" / "MANIFEST.json").write_bytes(pre_fix_bytes)
    touch_newer(fixture / ".saipen" / "MANIFEST.json",
                *[fixture / ".saipen" / n for n in ("STATE.md", "BOARD.md", "LOG.md", "IDENTITY.md")])
    result, snapshot, proof, contract = pack(fixture, work / "out4", "_PROBLIP_EQ_LEGACY")
    check(
        "G",
        bool(result.success) and not declares_evidence(contract) and proof == source_proof
        and snapshot["status"] in COMPLETE_STATUSES and snapshot["omitted_required"] == []
        and snapshot["evidence_citations"]["rules_source"] == se.RULES_CONSUMER_DEFAULT,
        f"pre-SRC-054 contract packed as-is: proof_in_zip={proof is not None} status={snapshot and snapshot['status']} "
        f"rules={snapshot and snapshot['evidence_citations']['rules_source']} cited_by="
        f"{snapshot and snapshot['evidence_citations']['cited_by'].get(PROOF_REL)}",
    )

    (fixture / PROOF_REL).unlink()
    saipen(args.saipen_root, fixture, "audit", "manifest", "--write")
    result, snapshot, proof, _ = pack(fixture, work / "out5", "_PROBLIP_EQ_DANGLING")
    omitted = {item["path"]: item for item in (snapshot or {}).get("omitted_required", [])}
    check(
        "H",
        bool(result.success) and snapshot["status"] == se.STATUS_PROTOCOL_INCOMPLETE
        and omitted.get(PROOF_REL, {}).get("reason") == se.REASON_EVIDENCE_ABSENT,
        f"proof deleted on disk: status={snapshot and snapshot['status']} omission={omitted.get(PROOF_REL)}",
    )

    plain = work / "plain"
    build_plain_project(plain, args.saipen_root)
    cont = saipen(args.saipen_root, plain, "continue")
    result, snapshot, _, contract = pack(plain, work / "out6", "PLAIN")
    check(
        "I",
        bool(result.success) and declares_evidence(contract) and snapshot["status"] == se.STATUS_COMPLETE
        and snapshot["omitted_required"] == [] and not (plain / ".saipen" / "evidence").exists(),
        f"no evidence dir: continue rc={cont['_rc']} status={snapshot and snapshot['status']} "
        f"omitted={snapshot and snapshot['omitted_required']}",
    )

    historical_names = set(zipfile.ZipFile(args.historical_archive).namelist())
    collection = se.collect_for_inventory(args.problip_root)
    rejudged = se.evaluate(collection, included=historical_names)
    omitted = {item["path"]: item for item in rejudged["omitted_required"]}
    check(
        "J",
        PROOF_REL not in historical_names and rejudged["status"] == se.STATUS_PROTOCOL_INCOMPLETE
        and rejudged["required_evidence_omitted"] and PROOF_REL in omitted,
        f"{args.historical_archive.name} (shipped COMPLETE) re-judged: status={rejudged['status']} "
        f"omission={omitted.get(PROOF_REL)}",
    )

    # The live projection must REPORT the contract the project actually holds
    # and rewrite nothing. Asserting a fixed verdict here measured the world on
    # one evening instead of the code: this project was STALE until the fix
    # migrated it, and a check that can only pass before its own fix lands is
    # not a check. The declared verdict is compared against the on-disk
    # contract, so a producer that calls an old contract current, or a new one
    # stale, is still caught -- in either world.
    live_before = (args.problip_root / ".saipen" / "MANIFEST.json").read_bytes()
    live = saipen(args.saipen_root, args.problip_root, "audit", "manifest")
    live_after = (args.problip_root / ".saipen" / "MANIFEST.json").read_bytes()
    on_disk = json.loads(live_before.decode("utf-8"))
    declares_new_contract = declares_evidence(on_disk) and "references" in on_disk
    declared = live.get("declared")
    enrollment = (live.get("enrollment") or {}).get("code")
    current = ("CURRENT", "AUDIT_MANIFEST_CURRENT")
    expected = current if declares_new_contract else ("STALE", "AUDIT_MANIFEST_PLAN")
    check(
        "K",
        live["_rc"] == 0 and live_after == live_before and (declared, enrollment) == expected,
        f"live Problip read-only projection: on-disk contract declares evidence+references="
        f"{declares_new_contract} -> declared={declared} enrollment={enrollment} "
        f"rc={live['_rc']} manifest_unchanged={live_after == live_before}",
    )

    problip_after = tree_digest(args.problip_root / ".saipen", skip=("locks",))
    saipen_after = {str(p): sha256(p.read_bytes()) if p.is_file() else None for p in canonical}
    changed = sorted(set(problip_before.items()) ^ set(problip_after.items()))
    check(
        "L",
        not changed and saipen_before == saipen_after,
        f"Problip .saipen files changed={len(changed)}; SAIPEN checkout canonical files unchanged="
        f"{saipen_before == saipen_after}",
    )

    failed = [r for r in RESULTS if r["result"] != "PASS"]
    if args.json:
        args.json.write_text(json.dumps({"results": RESULTS, "failed": len(failed)}, indent=1), encoding="utf-8")
    print(f"TOTAL {len(RESULTS) - len(failed)}/{len(RESULTS)} PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
