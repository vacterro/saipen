"""Whose words a receipt actually holds, and who says so.

MEASURED, 2026-09-17, nine-condition field matrix on installed generation
f3d2104a. `long_file_task` was handed a 520-byte request over twelve lines with
four explicit constraints. It ran `saipen start` with a 46-character substitute
it wrote itself, minted `T-1` and `SRC-001`, changed `src/app.py`, and every
gate read green. T-1372's obligation never armed, because that mechanism records
what a transport refusal REFUSED and nothing refused anything: the session never
attempted the literal ingress at all.

The defect class this ends: **the operator's request reaches the protocol only
through the model's own hands, and the receipt says nothing about that.**
`source_authority: exact` is a true statement about BYTES -- the stored body is
the body we were handed, unredacted -- and it was being read as a statement
about WORDS.

So the receipt records its witness. Three values, and the difference between
them is who compared what:

* ``operator_carrier`` -- something outside the session declared the task's
  digest (a launcher, a harness, an operator), and the text that arrived
  matches it. A mismatch is refused, not recorded.
* ``transport_obligation`` -- a transport refusal recorded these exact bytes
  and they arrived (INGRESS-AUTHORITY-01, T-1372).
* ``model_supplied`` -- nobody compared anything. The text is what the session
  typed, and the receipt says so instead of implying more.

`model_supplied` is not a failure and is not refused: most sessions have no
carrier, and inventing one would be the fabrication this module exists to stop.
It is a fact a reader can act on, and a matrix can count.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

#: The operator's task digest, declared by whoever launched this session.
ENV_TASK_SHA256 = "SAIPEN_TASK_SHA256"

#: The operator's task text on disk, when a launcher can write a file but not a
#: digest. Read-only, bounded; the digest is computed from its bytes.
ENV_TASK_FILE = "SAIPEN_TASK_FILE"

#: A task file past this size is not a task, and reading it unbounded would let
#: an environment variable point the engine at anything on the disk.
MAX_TASK_FILE_BYTES = 256 * 1024

WITNESS_CARRIER = "operator_carrier"
WITNESS_OBLIGATION = "transport_obligation"
WITNESS_MODEL = "model_supplied"

CODE_MISMATCH = "INGRESS_TASK_MISMATCH"
CODE_CARRIER_INVALID = "INGRESS_TASK_CARRIER_INVALID"

_SHA256 = re.compile(r"[0-9a-f]{64}")


def declared(env: dict | None = None) -> dict | None:
    """What this session was LAUNCHED with, or None when nobody said.

    Returns ``{"digest": ..., "source": ENV_TASK_SHA256|ENV_TASK_FILE}`` or an
    ``{"error": ...}`` record. A malformed carrier is an error rather than an
    absence: an environment that meant to declare the task and failed must not
    read as an environment that never declared one.
    """
    from .pending_ingress import ingress_digest

    env = os.environ if env is None else env
    raw = (env.get(ENV_TASK_SHA256) or "").strip().lower()
    if raw:
        if not _SHA256.fullmatch(raw):
            return {"error": f"{ENV_TASK_SHA256} is not a 64-character sha256 hex digest"}
        return {"digest": raw, "source": ENV_TASK_SHA256}
    path_raw = (env.get(ENV_TASK_FILE) or "").strip()
    if not path_raw:
        return None
    path = Path(path_raw)
    try:
        if path.stat().st_size > MAX_TASK_FILE_BYTES:
            return {"error": f"{ENV_TASK_FILE} is larger than {MAX_TASK_FILE_BYTES} bytes"}
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, ValueError) as exc:
        return {"error": f"{ENV_TASK_FILE} is not a readable UTF-8 file: {exc}"}
    return {"digest": ingress_digest(text), "source": ENV_TASK_FILE}


def witness(text: str, *, obligation_met: bool = False, env: dict | None = None) -> dict:
    """How this request's fidelity was established, or why it is refused.

    ``{"witness": ..., "compared_digest": ...}`` when the ingress may proceed;
    ``{"code": ..., "detail": ...}`` when an operator carrier contradicts the
    text that arrived.
    """
    from .pending_ingress import ingress_digest

    supplied = ingress_digest(text)
    record = declared(env)
    if record and record.get("error"):
        return {
            "code": CODE_CARRIER_INVALID,
            "detail": (
                str(record["error"])
                + ". The session declares an operator task it cannot prove, so this "
                "ingress is refused rather than recorded as unwitnessed. Fix the "
                "carrier or unset it"
            ),
            "canonical_next_command": "saipen start --file <path>",
        }
    if record:
        if record["digest"] != supplied:
            return {
                "code": CODE_MISMATCH,
                "detail": (
                    "this session was launched with a task whose sha256 is "
                    + record["digest"]
                    + " (declared by "
                    + record["source"]
                    + ") and the text supplied to the ingress has digest "
                    + supplied
                    + ". A receipt built from it would carry the session's words under "
                    "the operator's authority. Carry the operator's own bytes -- "
                    "`saipen start --file <path>` needs no shell quoting -- or have "
                    "the operator restate the request"
                ),
                "declared_digest": record["digest"],
                "supplied_digest": supplied,
                "canonical_next_command": "saipen start --file <path>",
            }
        return {
            "witness": WITNESS_CARRIER,
            "compared_digest": supplied,
            "declared_by": record["source"],
        }
    if obligation_met:
        return {"witness": WITNESS_OBLIGATION, "compared_digest": supplied}
    return {
        "witness": WITNESS_MODEL,
        "compared_digest": supplied,
        "note": (
            "no operator carrier and no transport obligation: the stored bytes are "
            "what this session supplied, and nothing compared them with what the "
            "operator wrote"
        ),
    }


__all__ = [
    "CODE_CARRIER_INVALID",
    "CODE_MISMATCH",
    "ENV_TASK_FILE",
    "ENV_TASK_SHA256",
    "MAX_TASK_FILE_BYTES",
    "WITNESS_CARRIER",
    "WITNESS_MODEL",
    "WITNESS_OBLIGATION",
    "declared",
    "witness",
]
