"""Typed SAIPAL backend adapter for SAIPEN autonomous campaign (Block 4 & Block 5).

Logical interface:
- probe()
- discover()
- start_or_resume()
- checkpoint()
- collect_findings()
- collect_publication_receipts()
- get_dispositions()
- classify_retry()
- get_next_eligibility()

Result classifications:
- ANALYSIS_PROGRESS
- NEW_QUALIFIED_FINDINGS
- NO_NEW_EVIDENCE
- STAGED_PUBLICATION
- DELIVERED_PUBLICATION
- SOURCE_NOT_ENROLLED
- RUNTIME_UNAVAILABLE
- AUTHORITY_REQUIRED
- ANALYSIS_BLOCKED
- RETRYABLE_FAILURE
- PERMANENT_FAILURE
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from . import audit_enqueue, paths

# Result classifications
ANALYSIS_PROGRESS = "ANALYSIS_PROGRESS"
NEW_QUALIFIED_FINDINGS = "NEW_QUALIFIED_FINDINGS"
NO_NEW_EVIDENCE = "NO_NEW_EVIDENCE"
STAGED_PUBLICATION = "STAGED_PUBLICATION"
DELIVERED_PUBLICATION = "DELIVERED_PUBLICATION"
SOURCE_NOT_ENROLLED = "SOURCE_NOT_ENROLLED"
RUNTIME_UNAVAILABLE = "RUNTIME_UNAVAILABLE"
AUTHORITY_REQUIRED = "AUTHORITY_REQUIRED"
ANALYSIS_BLOCKED = "ANALYSIS_BLOCKED"
RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
PERMANENT_FAILURE = "PERMANENT_FAILURE"

DEFAULT_SAIPAL_PATHS = [
    Path(r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPAL"),
]


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SaipalAdapter:
    """Logical and execution backend connecting SAIPEN campaign to SAIPAL."""

    def __init__(self, saipal_home: Path | str | None = None) -> None:
        self.saipal_home = Path(saipal_home).resolve() if saipal_home else self._resolve_home()

    def _resolve_home(self) -> Path | None:
        env_home = os.environ.get("SAIPAL_HOME")
        if env_home and Path(env_home).is_dir():
            return Path(env_home).resolve()
        for candidate in DEFAULT_SAIPAL_PATHS:
            if (candidate / "tools" / "saipal.py").is_file():
                return candidate
        return None

    def _resolve_cli(self) -> tuple[Path | None, Path | None]:
        if not self.saipal_home:
            return None, None
        cli_tool = self.saipal_home / "tools" / "saipal.py"
        dot_saipal = self.saipal_home / ".saipal"
        if cli_tool.is_file() and dot_saipal.is_dir():
            return cli_tool, dot_saipal
        return None, None

    def _run_cmd(self, subcommand: str, *args: str) -> dict:
        cli, home = self._resolve_cli()
        if not cli or not home:
            return {"ok": False, "status": RUNTIME_UNAVAILABLE, "error": "SAIPAL installation not found"}
        cmd = [sys.executable, str(cli), "--json", "--home", str(home), subcommand, *args]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30.0)
            if res.returncode != 0:
                err_text = res.stderr or res.stdout
                return {
                    "ok": False,
                    "status": RETRYABLE_FAILURE if "busy" in err_text.lower() else PERMANENT_FAILURE,
                    "error": err_text.strip(),
                    "returncode": res.returncode,
                }
            try:
                data = json.loads(res.stdout)
                if isinstance(data, dict) and data.get("ok") is False:
                    return {
                        "ok": False,
                        "status": data.get("status", PERMANENT_FAILURE),
                        "error": data.get("error", data.get("detail", "SAIPAL backend reported failure")),
                        "data": data,
                    }
                return {"ok": True, "data": data}
            except json.JSONDecodeError:
                return {
                    "ok": False,
                    "status": PERMANENT_FAILURE,
                    "error": f"Invalid JSON returned: {res.stdout[:500]}",
                }
        except subprocess.TimeoutExpired:
            return {"ok": False, "status": RETRYABLE_FAILURE, "error": "SAIPAL command timed out"}
        except OSError as exc:
            return {"ok": False, "status": RUNTIME_UNAVAILABLE, "error": str(exc)}

    def probe(self) -> dict:
        """Prove SAIPAL runtime binding, readiness and environment health."""
        cli, home = self._resolve_cli()
        if not cli or not home:
            return {
                "ok": False,
                "status": RUNTIME_UNAVAILABLE,
                "detail": f"SAIPAL installation not found at {self.saipal_home}",
            }
        outcome = self._run_cmd("status")
        if not outcome["ok"]:
            return {
                "ok": False,
                "status": outcome.get("status", RUNTIME_UNAVAILABLE),
                "detail": outcome.get("error", "Failed to query SAIPAL status"),
            }
        data = outcome["data"]
        return {
            "ok": True,
            "status": "BOUND",
            "home": str(home),
            "episodes": data.get("episodes", 0),
            "events_indexed": data.get("events_indexed", 0),
            "phase": data.get("phase", "UNKNOWN"),
            "next_action": data.get("next_action", ""),
        }

    def start_or_resume(self) -> dict:
        """Advance or resume the next unit in forensic analysis."""
        return self._run_cmd("next")

    def collect_findings(self, *, qualified_only: bool = False) -> list[dict]:
        """Collect findings from SAIPAL report."""
        outcome = self._run_cmd("report")
        if not outcome["ok"]:
            return []
        findings = outcome["data"].get("findings", [])
        if qualified_only:
            return [
                f for f in findings
                if str(f.get("state", "")).upper() in ("QUALIFIED", "CONFIRMED")
            ]
        return findings

    def discover(self, project_root: Path | str | None = None) -> dict:
        """Execute forensic discovery check and classify results."""
        probe_res = self.probe()
        if not probe_res["ok"]:
            return probe_res

        root = Path(project_root).resolve() if project_root else None

        # Check queue: if there are pending sessions, drive actual analysis slice
        status_out = self._run_cmd("status")
        if status_out["ok"]:
            st_data = status_out["data"]
            queue = st_data.get("queue", {})
            if queue.get("hot", 0) > 0 or queue.get("cold", 0) > 0:
                slice_res = self.start_or_resume()
                if slice_res["ok"]:
                    return {
                        "ok": True,
                        "status": ANALYSIS_PROGRESS,
                        "detail": "SAIPAL analysis slice executed.",
                        "slice": slice_res.get("data"),
                    }
                else:
                    err_msg = str(slice_res.get("error", ""))
                    return {
                        "ok": False,
                        "status": self.classify_retry(err_msg),
                        "error": slice_res.get("error"),
                    }

        outcome = self._run_cmd("report")
        if not outcome["ok"]:
            return {
                "ok": False,
                "status": outcome.get("status", PERMANENT_FAILURE),
                "detail": outcome.get("error"),
            }
        data = outcome["data"]
        findings = data.get("findings", [])

        qualified = [
            f for f in findings
            if str(f.get("state", "")).upper() in ("QUALIFIED", "CONFIRMED")
        ]

        # Deduplicate unchanged evidence via watermark
        if root:
            watermark_file = root / ".saipen" / "campaign" / "saipal_watermark.json"
            report_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
            last_hash = None
            if watermark_file.is_file():
                try:
                    last_hash = json.loads(watermark_file.read_text(encoding="utf-8")).get("report_hash")
                except Exception:
                    pass
            if last_hash == report_hash and not qualified:
                return {
                    "ok": True,
                    "status": NO_NEW_EVIDENCE,
                    "detail": "No new evidence; unchanged SAIPAL report deduplicated.",
                }
            watermark_file.parent.mkdir(parents=True, exist_ok=True)
            paths.safe_atomic_write_bytes(
                watermark_file,
                (json.dumps({"report_hash": report_hash, "updated_at": _utc_now()}, indent=2) + "\n").encode("utf-8"),
                kind="saipal watermark",
                ownership_root=root,
            )

        if qualified:
            return {
                "ok": True,
                "status": NEW_QUALIFIED_FINDINGS,
                "findings": qualified,
                "total_findings": len(findings),
            }

        return {
            "ok": True,
            "status": NO_NEW_EVIDENCE,
            "detail": "No qualified findings or new drift detected.",
        }

    def checkpoint(self, project_root: Path | str) -> dict:
        """Save or retrieve forensic scan checkpoint in project state."""
        root = Path(project_root).resolve()
        cp_file = root / ".saipen" / "campaign" / "saipal_checkpoint.json"
        if cp_file.is_file():
            try:
                return json.loads(cp_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        return {}

    def save_checkpoint(self, project_root: Path | str, payload: dict) -> None:
        root = Path(project_root).resolve()
        cp_file = root / ".saipen" / "campaign" / "saipal_checkpoint.json"
        cp_file.parent.mkdir(parents=True, exist_ok=True)
        paths.safe_atomic_write_bytes(
            cp_file,
            (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            kind="saipal checkpoint",
            ownership_root=root,
        )

    def collect_publication_receipts(self, project_root: Path | str) -> list[dict]:
        """Read publication receipts recorded locally."""
        root = Path(project_root).resolve()
        receipts_file = root / ".saipen" / "campaign" / "saipal_receipts.jsonl"
        if not receipts_file.is_file():
            return []
        receipts = []
        try:
            with open(receipts_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            receipts.append(json.loads(line))
                        except (json.JSONDecodeError, ValueError):
                            continue
        except OSError:
            pass
        return receipts

    def get_dispositions(self, project_root: Path | str) -> list[dict]:
        """Read recorded maintainer dispositions."""
        root = Path(project_root).resolve()
        disp_file = root / ".saipen" / "campaign" / "dispositions.jsonl"
        if not disp_file.is_file():
            return []
        dispositions = []
        try:
            with open(disp_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            dispositions.append(json.loads(line))
                        except (json.JSONDecodeError, ValueError):
                            continue
        except OSError:
            pass
        return dispositions

    def classify_retry(self, error: str) -> str:
        """Classify if an error code or message is retryable."""
        err_lower = str(error).lower()
        if any(term in err_lower for term in ("lock", "busy", "timeout", "rate limit", "429")):
            return RETRYABLE_FAILURE
        return PERMANENT_FAILURE

    def get_next_eligibility(self, project_root: Path | str, interval_seconds: float = 300.0) -> dict:
        """Check if periodic discovery is due based on checkpoint."""
        cp = self.checkpoint(project_root)
        last_run = cp.get("last_run_at")
        if not last_run:
            return {"due": True, "seconds_remaining": 0.0}
        try:
            last_dt = _dt.datetime.fromisoformat(last_run.replace("Z", "+00:00"))
            now_dt = _dt.datetime.now(_dt.timezone.utc)
            elapsed = (now_dt - last_dt).total_seconds()
            if elapsed >= interval_seconds:
                return {"due": True, "seconds_remaining": 0.0}
            return {"due": False, "seconds_remaining": round(interval_seconds - elapsed, 1)}
        except Exception:
            return {"due": True, "seconds_remaining": 0.0}

    VALID_DISPOSITIONS = frozenset(
        {
            "NOT_REPRODUCED",
            "DUPLICATE",
            "FALSE_POSITIVE",
            "REJECTED",
            "DEFERRED",
            "BLOCKED",
            "VERIFIED",
            "REPAIRED",
            "RECURRED",
            "REGRESSION_FAILED",
        }
    )

    def deliver_finding_to_audit_inbox(
        self,
        project_root: Path | str,
        finding: dict,
        *,
        publication_authorized: bool = False,
    ) -> dict:
        """Deliver one qualified finding through SAIPEN's canonical audit enqueue API."""
        root = Path(project_root).resolve()
        fid = str(finding.get("finding_id") or "PAL-UNKNOWN")
        state_str = str(finding.get("state") or "").upper()
        if state_str not in ("QUALIFIED", "CONFIRMED"):
            return {
                "ok": False,
                "status": "NOT_QUALIFIED",
                "detail": f"Finding {fid} has unconfirmed state '{finding.get('state')}'; publication refused.",
                "finding_id": fid,
            }

        # Provenance: finding qualification proof must be present
        qual_proof = (
            finding.get("qualification_receipt")
            or finding.get("qualification_proof")
            or finding.get("qualification_certificate")
        )
        if not qual_proof:
            return {
                "ok": False,
                "status": "NOT_QUALIFIED",
                "error": f"Finding {fid} lacks immutable qualification receipt or proof; publication refused.",
                "finding_id": fid,
            }

        if not publication_authorized:
            return {
                "ok": False,
                "status": STAGED_PUBLICATION,
                "detail": f"Finding {fid} publication not authorized (STAGE_ONLY). Requires explicit grant.",
                "finding_id": fid,
            }

        # Check authentic artifact: original immutable audit markdown body is mandatory
        audit_body = finding.get("audit_body") or finding.get("audit_artifact")
        if not audit_body:
            return {
                "ok": False,
                "status": "ARTIFACT_MISSING",
                "error": f"Finding {fid} has no original immutable audit artifact; reconstruction from summary fields is prohibited.",
                "finding_id": fid,
            }

        expected_digest = finding.get("artifact_digest")
        if not expected_digest:
            return {
                "ok": False,
                "status": "ARTIFACT_DIGEST_MISSING",
                "error": f"Finding {fid} missing required immutable artifact digest.",
                "finding_id": fid,
            }

        actual_digest = hashlib.sha256(audit_body.encode("utf-8")).hexdigest()
        if actual_digest != expected_digest:
            return {
                "ok": False,
                "status": "ARTIFACT_DIGEST_MISMATCH",
                "error": f"Audit artifact digest mismatch: expected {expected_digest}, got {actual_digest}",
                "finding_id": fid,
            }

        if not (root / ".saipen").is_dir():
            return {
                "ok": False,
                "status": "DESTINATION_NOT_READY",
                "error": f"Project root {root} has no valid .saipen infrastructure.",
                "finding_id": fid,
            }

        op_id = f"saipal-{fid.lower()}"
        res = audit_enqueue.enqueue(
            root,
            producer="saipal",
            body=audit_body,
            producer_operation_id=op_id,
            producer_item_id=fid,
        )
        if not res.get("ok"):
            return {
                "ok": False,
                "status": PERMANENT_FAILURE,
                "error": res.get("reason", "Enqueue refused"),
                "detail": res,
            }

        receipt = {
            "finding_id": fid,
            "operation_id": op_id,
            "layer": res.get("layer"),
            "digest": res.get("digest"),
            "idempotent": res.get("idempotent", False),
            "delivered_at": _utc_now(),
        }

        # Record receipt atomically
        receipts_file = root / ".saipen" / "campaign" / "saipal_receipts.jsonl"
        receipts_file.parent.mkdir(parents=True, exist_ok=True)
        with open(receipts_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(receipt, sort_keys=True) + "\n")

        return {
            "ok": True,
            "status": DELIVERED_PUBLICATION,
            "finding_id": fid,
            "receipt": receipt,
        }

    def record_maintainer_disposition(
        self,
        project_root: Path | str,
        finding_id: str,
        *,
        disposition: str,
        task_id: str,
        closure_commit: str = "",
        verification_evidence: str | dict = "",
        source_receipt: str = "",
        notes: str = "",
    ) -> dict:
        """Record a closed-loop maintainer disposition for a finding."""
        root = Path(project_root).resolve()
        disp_upper = str(disposition).upper()
        if disp_upper not in self.VALID_DISPOSITIONS:
            return {
                "ok": False,
                "status": "DISPOSITION_INVALID",
                "error": f"Disposition '{disposition}' not in valid vocabulary: {sorted(self.VALID_DISPOSITIONS)}",
            }

        if disp_upper == "VERIFIED":
            # 1. Verify task exists on board and is DONE
            board_file = root / ".saipen" / "BOARD.md"
            if not board_file.is_file():
                return {
                    "ok": False,
                    "status": "DISPOSITION_UNVERIFIED",
                    "error": f"Cannot verify disposition: {board_file} does not exist",
                }
            board_txt = board_file.read_text(encoding="utf-8")
            done_section = board_txt.partition("## DONE")[2]
            if f"- [x] {task_id}" not in done_section and f"[x] {task_id}" not in done_section:
                return {
                    "ok": False,
                    "status": "DISPOSITION_UNVERIFIED",
                    "error": f"Task {task_id} is not in terminal DONE state under ## DONE on board",
                }

            # 2. Verification evidence must substantiate repair
            if not verification_evidence:
                return {
                    "ok": False,
                    "status": "DISPOSITION_UNVERIFIED",
                    "error": "VERIFIED disposition requires verifiable verification_evidence",
                }
            if isinstance(verification_evidence, str) and verification_evidence.strip().upper() == "PASS":
                return {
                    "ok": False,
                    "status": "DISPOSITION_UNVERIFIED",
                    "error": "Generic 'PASS' string is not valid verification execution evidence",
                }

            # 3. If closure commit is declared and git repository is present, verify commit exists
            if closure_commit and (root / ".git").exists():
                try:
                    p = subprocess.run(
                        ["git", "-C", str(root), "cat-file", "-t", closure_commit],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if p.returncode != 0 or p.stdout.strip() != "commit":
                        return {
                            "ok": False,
                            "status": "DISPOSITION_UNVERIFIED",
                            "error": f"Closure commit '{closure_commit}' not found in git repository",
                        }
                except OSError as exc:
                    return {
                        "ok": False,
                        "status": "DISPOSITION_UNVERIFIED",
                        "error": f"Could not verify closure commit via git: {exc}",
                    }

        record = {
            "finding_id": str(finding_id),
            "task_id": str(task_id),
            "disposition": disp_upper,
            "closure_commit": str(closure_commit),
            "verification_evidence": verification_evidence if isinstance(verification_evidence, dict) else str(verification_evidence),
            "source_receipt": str(source_receipt),
            "notes": str(notes),
            "recorded_at": _utc_now(),
        }
        disp_file = root / ".saipen" / "campaign" / "dispositions.jsonl"
        disp_file.parent.mkdir(parents=True, exist_ok=True)
        with open(disp_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")
        return {"ok": True, "status": "DISPOSITION_RECORDED", "disposition": record}
