"""SAILEARN GPU Librarian optional consumer (T-1796, SRC-256).

Gives SAIPEN continuation, orient, and diagnostic workflows access to
SAILEARN's verified local knowledge index without altering SAIPEN authority.

Rules (SRC-256):
- Bounded, read-only, default enabled if index is present, can be disabled via
  SAIPEN_LIBRARIAN=off.
- Purely advisory: every result carries an explicit ADVISORY label. It never
  touches STATE, BOARD, LOG, tickets, phases, receipts, or validation.
- Zero mandatory dependencies: works if sailearn is importable or present at
  V:/---SAILEARN---/src; if absent or disabled, fails soft with a reason code.
- Source freshness re-verification: re-checks live source digests so stale or
  changed files are explicitly surfaced (VERIFIED vs CHANGED vs ABSENT vs
  SUPERSEDED).
- Deterministic continuation: timeouts or missing index preserve the original
  deterministic continuation path byte-for-byte.
- Resource & usefulness metrics: reports duration, hits, verification status,
  and usefulness witness.
"""

from __future__ import annotations

import contextlib
import os
import sys
import time
from pathlib import Path
from typing import Any

ENV_SWITCH = "SAIPEN_LIBRARIAN"
ADVISORY_LABEL = "ADVISORY (local GPU librarian; semantic suggestion, not protocol authority)"
DEFAULT_TIMEOUT_S = 2.0
MAX_QUERY_CHARS = 1000
MAX_LIMIT = 5

# Common durable home candidates
_CANDIDATE_HOMES = (
    Path(r"V:\___VAC\__K\__STATE\SAILEARN_HOME"),
    Path(r"V:\__STATE\SAILEARN_HOME"),
)
_CANDIDATE_SAILEARN_SRC = Path(r"V:\---SAILEARN---\src")
_CANDIDATE_SAILEARN_VENV = Path(r"V:\---SAILEARN---\.venv\Lib\site-packages")


def is_enabled() -> tuple[bool, str]:
    """(enabled, reason) from environment or default."""
    val = os.environ.get(ENV_SWITCH, "").strip().lower()
    if val in ("0", "off", "false", "no", "disabled"):
        return False, "env_disabled"
    if val in ("1", "on", "true", "yes", "enabled"):
        return True, "env_enabled"
    return True, "default"


def _ensure_sailearn_imported() -> bool:
    """Attempts to import sailearn.librarian, trying known local paths if needed."""
    if "sailearn.librarian.query" in sys.modules:
        return True
    try:
        __import__("sailearn.librarian.query")

        return True
    except ImportError:
        pass

    try:
        src_exists = _CANDIDATE_SAILEARN_SRC.is_dir()
    except OSError:
        src_exists = False
    if src_exists:
        src_str = str(_CANDIDATE_SAILEARN_SRC)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)
        try:
            venv_exists = _CANDIDATE_SAILEARN_VENV.is_dir()
        except OSError:
            venv_exists = False
        if venv_exists:
            venv_str = str(_CANDIDATE_SAILEARN_VENV)
            if venv_str not in sys.path:
                sys.path.insert(0, venv_str)
        try:
            __import__("sailearn.librarian.query")
            return True
        except ImportError:
            return False
    return False


def resolve_home(explicit_home: Path | str | None = None) -> Path | None:
    """Finds the durable SAILEARN_HOME directory."""
    if explicit_home is not None:
        p = Path(explicit_home)
        try:
            if p.is_dir():
                return p
        except OSError:
            pass
        return None

    env_home = os.environ.get("SAILEARN_HOME", "").strip()
    if env_home:
        p = Path(env_home)
        try:
            if p.is_dir():
                return p
        except OSError:
            pass

    for candidate in _CANDIDATE_HOMES:
        try:
            if candidate.is_dir():
                return candidate
        except OSError:
            continue
    return None


def resolve_index(home: Path | None = None) -> Path | None:
    """Finds the index.json path within SAILEARN_HOME."""
    resolved_home = resolve_home(home)
    if not resolved_home:
        return None
    idx = resolved_home / "librarian" / "index.json"
    if idx.is_file():
        return idx
    return None


def status(explicit_home: Path | str | None = None) -> dict[str, Any]:
    """Read-only inspection of the librarian consumer status."""
    enabled, switch_reason = is_enabled()
    home = resolve_home(explicit_home)
    index_file = resolve_index(home)
    importable = _ensure_sailearn_imported()

    if not enabled:
        return {
            "ok": True,
            "available": False,
            "reason": "DISABLED",
            "switch": switch_reason,
            "home": str(home) if home else None,
            "index": str(index_file) if index_file else None,
        }

    if not importable:
        return {
            "ok": True,
            "available": False,
            "reason": "SAILEARN_MODULE_UNAVAILABLE",
            "switch": switch_reason,
            "home": str(home) if home else None,
            "index": str(index_file) if index_file else None,
        }

    if not home or not index_file:
        return {
            "ok": True,
            "available": False,
            "reason": "INDEX_NOT_FOUND",
            "switch": switch_reason,
            "home": str(home) if home else None,
            "index": str(index_file) if index_file else None,
        }

    size_bytes = 0
    with contextlib.suppress(OSError):
        size_bytes = index_file.stat().st_size

    return {
        "ok": True,
        "available": True,
        "reason": "READY",
        "switch": switch_reason,
        "home": str(home),
        "index": str(index_file),
        "index_size_bytes": size_bytes,
        "advisory": ADVISORY_LABEL,
    }


def query(
    text: str,
    *,
    home: Path | str | None = None,
    limit: int = 3,
    cross_project: bool = False,
    exclude_lineage: str | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    """Safe, bounded query against the local knowledge index. Never raises."""
    stat = status(home)
    if not stat.get("available"):
        return {
            "ok": True,
            "available": False,
            "reason": stat.get("reason"),
            "hits": [],
            "metrics": {"duration_ms": 0.0, "hits_count": 0, "useful": False},
        }

    cleaned_text = str(text or "").strip()[:MAX_QUERY_CHARS]
    if not cleaned_text:
        return {
            "ok": True,
            "available": True,
            "reason": "EMPTY_QUERY",
            "hits": [],
            "metrics": {"duration_ms": 0.0, "hits_count": 0, "useful": False},
        }

    limit = max(1, min(limit, MAX_LIMIT))
    start_time = time.perf_counter()

    try:
        from sailearn.librarian.query import Retriever  # type: ignore[import-untyped]

        r = Retriever(Path(stat["home"]))
        if cross_project:
            ans = r.similar_incidents(cleaned_text, limit=limit, exclude_lineage=exclude_lineage)
        else:
            ans = r.answer(cleaned_text, limit=limit)

        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        hits_out = []
        for h in ans.hits:
            cite = h.citation
            hits_out.append(
                {
                    "record_id": h.record_id,
                    "score": round(float(h.score), 3),
                    "method": h.method,
                    "text_preview": (h.text or "").strip()[:300],
                    "source_path": cite.source_path,
                    "lineage": cite.lineage,
                    "citation_state": cite.state,
                    "citation_detail": cite.detail,
                    "stale": cite.stale,
                    "observed_at": cite.observed_at,
                    "authority": cite.authority,
                    "live_sha256": cite.live_sha256,
                }
            )

        verified_count = sum(1 for h in hits_out if h["citation_state"] == "VERIFIED")
        stale_count = sum(1 for h in hits_out if h["stale"] or h["citation_state"] == "SUPERSEDED")

        return {
            "ok": True,
            "available": True,
            "reason": "OK",
            "advisory": ADVISORY_LABEL,
            "query": cleaned_text,
            "method": ans.method,
            "vocabulary": ans.vocabulary,
            "hits": hits_out,
            "metrics": {
                "duration_ms": duration_ms,
                "hits_count": len(hits_out),
                "verified_count": verified_count,
                "stale_count": stale_count,
                "useful": len(hits_out) > 0,
            },
        }
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        return {
            "ok": True,
            "available": False,
            "reason": f"QUERY_ERROR: {type(exc).__name__}",
            "detail": str(exc)[:200],
            "hits": [],
            "metrics": {"duration_ms": duration_ms, "hits_count": 0, "useful": False},
        }


def format_advisory(retrieval_payload: dict[str, Any]) -> str:
    """Renders a concise, human-readable advisory card."""
    if not retrieval_payload.get("available") or not retrieval_payload.get("hits"):
        return ""

    hits = retrieval_payload.get("hits", [])
    metrics = retrieval_payload.get("metrics", {})
    lines = [
        f"{ADVISORY_LABEL}",
        f"Retrieved {len(hits)} reference(s) "
        f"({metrics.get('verified_count', 0)} verified, "
        f"{metrics.get('stale_count', 0)} superseded):",
    ]
    for i, h in enumerate(hits, 1):
        state_tag = f"[{h['citation_state']}]"
        score = h.get("score", 0.0)
        path = h.get("source_path", "unknown")
        lines.append(f"  {i}. {state_tag} (score {score}) {path}")
        preview = h.get("text_preview", "").replace("\n", " ").strip()
        if preview:
            lines.append(f'     "{preview[:120]}..."')
    return "\n".join(lines)
