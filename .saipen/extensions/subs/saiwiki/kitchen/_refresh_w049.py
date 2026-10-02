"""saiwiki FORCE-FRESH page refresh (W-049).

Mirrors the current-tree truth that moved after W-048's binding
(a1e9c09f -> 6c6e2a45, 71 commits). Exact text replacements with one
assertion per edit: zero or double anchor match is a hard failure.

Mirrored owners:

  * BOOT.md: transport resolved via SAIPEN_ENTRY.json / `host entry`,
    STYLE + EXECUTION loaded together at bootstrap, SAIPEN_AUTO_RECALL kick
  * COMMANDS.md: telegrams block, queued user Source, `saipen autonomy`,
    `saipen gpu`, host/rebind-home, source append family, handoff,
    work reverify, ticket resolve-external / reasoning / repair-metadata,
    sub reconcile, validate as conformance front door
  * CORE.md: QUALITY > TIME (QUALITY-TIME-01), superseded_verified closure
  * RUNTIME.md: AUTO_RECALL / AUTO_KICK, unattended supervisor,
    installed-runtime freshness
  * extensions/subs/crew.md: crew record-run epoch proof
  * tools/audit_checks.py: FULL_CASE_COUNT 229 -> 242; measured test
    inventory 139/2791 -> 224 modules / 3793 methods

Touches only kitchen/wiki/ (this producer's own payload). No integration,
commit, tag, push or remote write.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RE_PRESENT_CACHE: dict[str, re.Pattern[str]] = {}

ROOT = Path(__file__).resolve().parents[5]
WIKI = ROOT / ".saipen" / "extensions" / "subs" / "saiwiki" / "kitchen" / "wiki"


def is_present(text: str, new: str) -> bool:
    if new not in RE_PRESENT_CACHE:
        RE_PRESENT_CACHE[new] = re.compile(
            "\r?\n".join(re.escape(part) for part in new.split("\n"))
        )
    return RE_PRESENT_CACHE[new].search(text) is not None


# ---- Home.md: command table additions (COMMANDS.md canonical table) --------
HOME_TABLE_AFTER_VALIDATE = (
    "| `saipen validate` | Conformance checker (structural precheck, then the canonical validator; VALID only on CURRENT_PASS) |\n"
    "| `saipen improve [action]` | Bounded self-improvement cycles |\n"
    "| `saipen improve reconcile <cycle>` | Strict-cycle finite exit: classify every seat, execute lossless transitions, terminalize COMPLETE/SUPERSEDED/BLOCKED_EXTERNAL |\n"
    "| `saipen status` | Project status dashboard |\n"
    "| `saipen autonomy` | Read-only supervisor verdict: RUN_WORK, ADOPT_WORKER, REPLACE_WORKER, AWAIT_WORKER, OPERATOR_ACTION_DUE, NO_PROGRESS_LOOP, AMBIGUOUS_AUTHORITY, IDLE |\n"
    "| `saipen autonomy recall` | Read-only turn-entry decision for a replaced or cold agent (AUTO_RECALL / AUTO_KICK) |\n"
    "| `saipen gpu [status\\|on\\|off\\|index\\|recall <text>\\|triage]` | Idle-local-GPU advisory lane (default OFF); writes only `.saipen/cache/`, never truth |\n"
    "| `saipen host bootstrap / activation / entry` | Read-only runtime binding diagnostics; `entry` proves the transport or names the failure |\n"
    "| `saipen rebind-home --auto \\| <path>` | Converge a dead persisted home onto a proven runtime |\n"
    "| `saipen handoff <T-###> --to <agent>` | Owner- or operator-authorized live claim transfer, same Work and phase |\n"
    "| `saipen work reverify <T-###>` | Re-verify already-DONE Work against the CURRENT tree; one immutable RV-NNNNNN receipt, DONE stays |\n"
    "| `saipen ticket resolve-external <T-###> ...` | Close BLOCKED Work implemented by an external authority (immutable EX-NNNNNN receipt) |\n"
    "| `saipen ticket reasoning <T-###> ...` | Canonical writer for strict-sweep reasoning gates |\n"
    "| `saipen ticket repair-metadata <T-###> ...` | Migrate malformed legacy metadata on historical DONE Work (immutable MR-NNNNNN receipt) |\n"
    "| `saipen source retire / link / append / apply-append / appends / recover / reconcile / quarantine` | Receipt-only source lifecycle: retirement, multi-work membership, operational handoff appends, contradiction reconciliation, body quarantine |\n"
    "| `saipen sub reconcile <role> --authority <SRC-###>` | Producer-owned terminal reconciliation of a DONE producer's stale projection |\n"
)

HOME_TABLE_VALIDATE_OLD = (
    "| `saipen validate` | Run conformance checker |\n"
    "| `saipen crew` | The whole circuit: hunt, reproduce, intake, build, translate, document, ship |\n"
    "| `saipen test` | Run the declared suite, report PASS/FAIL |\n"
    "| `saipen status` | Read-only board report |\n"
)

# ---- Home.md: current-tree truth bullets -----------------------------------
HOME_NEW_BULLETS = """- **Transport is resolved, never guessed** (current tree): `saipen <command>` is LOGICAL -- run it as `bin/saipen.cmd` / `bin/saipen` per `SAIPEN_ENTRY.json` beside BOOT.md; `saipen host entry` proves the transport or names the failure. A failed `python -m saipen` or `where saipen` proves nothing.
- **QUALITY > TIME** (current tree): no model, tier, session or incarnation weakens acceptance or enters Work truth -- no cheaper DONE. Missing durable progress is failure; elapsed time is not.
- **Telegrams never route** (current tree): every `continue`/`cc`/`status` JSON answer carries `telegrams` -- unread SAIMAIL counts when `SAIMAIL_WORKSPACE` is set and `saimail-local` is on PATH. A nonzero count is reported; reading is an explicit decision. A telegram never routes, creates Work or skips a WAIT.
- **A replaced agent recalls its execution** (current tree): `saipen autonomy recall` is the read-only turn-entry decision for a successor with no private memory -- RECOVER > USER_INPUT > OPERATOR_WAIT > AUTO_KICK > RUN_CONTINUE > ORDINARY; a kick means run `saipen continue --json` before any chat.
- **Unattended runs are supervised, not trusted** (current tree): `supervisor.decide` names ONE verdict, `worker.supervise` acts on it -- lease generations, heartbeats, fenced crashes, QUALITY > TIME idle bounds; no failure class writes canonical state, only the agent incarnation changes.
- **Queued user input wakes by itself** (current tree): a request captured while the seat was busy is started by the next canonical poll through `saipen start --receipt SRC-###` -- the operator never retypes the command.
- **Legitimate old Work can close superseded-verified** (current tree): old Work implemented and verified through a later DONE Work closes as `superseded_verified` under an explicit DONE successor, exact old-target PASS evidence and operator authority -- a local terminal closure, never a retirement or publication claim.
- **Crew sensor stages prove their epoch** (current tree): `saipen crew record-run <ROLE>` binds only ready/reviewed packages carrying the live source triple and role revision, and only a journal-written `crew_run` receipt counts."""

# ---- Home.md: inventory re-measured ----------------------------------------
HOME_INVENTORY_OLD = (
    "- **Current tree inventory** (measured at this package's source binding, HEAD over v8.0.1): "
    "139 `tools/test_*.py` modules declaring 2791 test methods, and the validator mutation-control "
    "harness declares its 229 full-sweep controls -- the release gate still runs the full sweep, "
    "and a scoped run is never release evidence."
)
HOME_INVENTORY_NEW = (
    "- **Current tree inventory** (measured at this package's source binding, HEAD 6c6e2a45 over v8.0.1): "
    "224 `tools/test_*.py` modules declaring 3793 test methods, and the mutation-control harness "
    "declares 242 full-sweep controls (`audit_checks.FULL_CASE_COUNT`) -- the release gate still "
    "runs the full sweep, and a scoped run never prints the \"N of\" total, so it is never release evidence."
)

# ---- Phases.md: new phase-level checks -------------------------------------
PHASES_NEW_CHECKS = """- **QUALITY > TIME governs every phase** (current tree): QUALITY-TIME-01 -- no model, tier, session or incarnation weakens acceptance or enters Work truth; missing durable progress is failure, elapsed time is not, within NO_PROGRESS/budget/host bounds.
- **An old ticket can close superseded-verified** (current tree): legitimate old Work implemented and verified through a later DONE Work closes as `closure_mode: superseded_verified` on the preserved DONE row -- PLAN fails closed unless the exact old-target PASS event is owned by the DONE successor, the relation is acyclic, and an ACTIVE operator-ingress receipt grants the exact pair; it is a local terminal verdict, never a retirement or a publication claim.
- **A replaced successor opens with a recall, not a question** (current tree): `saipen autonomy recall` answers the turn-entry decision for a cold or replaced agent (RECOVER > USER_INPUT > OPERATOR_WAIT > AUTO_KICK > RUN_CONTINUE > ORDINARY); a kick means `saipen continue --json` before any chat, and a message becomes historical only when a canonical `saipen` command consumed it.
- **DONE Work can be re-verified against the current tree** (current tree): `saipen work reverify <T-###>` writes ONE immutable `RV-NNNNNN` receipt and keeps DONE; only an EXECUTED contract is current-tree closure evidence -- an attested-only contract is recorded but never proof.
"""

# ---- Getting-Started.md: transport + entry truth ---------------------------
GS_TRANSPORT = """
**Transport is resolved, never guessed.** `saipen <command>` is LOGICAL: run it
as `bin/saipen.cmd` (Windows) / `bin/saipen` from the SAIPEN home's root, per
`SAIPEN_ENTRY.json` beside BOOT.md. `<launcher> host entry --json` proves the
transport or names the failure; `python -m saipen`, `where`/`which saipen` and a
hand-built interpreter path are never transports.
"""

GS_BOOTSTRAP_OLD = (
    "No install? Paste one line to any agent:\n"
    "> `Read <clone>/saipen/BOOT.md first, then <clone>/saipen/CORE.md + <clone>/saipen/STYLE.md`\n"
)
GS_BOOTSTRAP_NEW = (
    "No install? Paste one line to any agent:\n"
    "> `Read <clone>/saipen/BOOT.md first, then <clone>/saipen/CORE.md + <clone>/saipen/STYLE.md + <clone>/saipen/EXECUTION.md`\n"
)

# ---- SubSaipen.md: producer rows -------------------------------------------
SUB_ROW_OLD = (
    "| **saiwiki** | Wiki producer | FORCE-FRESH maintains all 9 wiki pages. W-047 is prepared against the current source triple (HEAD 5d79ae78); "
    "the Scenarios mirror stays at 257 canonical rows, digest sha256:43ab86d596572a90, and the entry/binding/cap/retirement truth of the current tree is mirrored — ready in OUTBOX, not integrated or pushed. |"
)
SUB_ROW_NEW = (
    "| **saiwiki** | Wiki producer | FORCE-FRESH maintains all 9 wiki pages. W-049 is prepared against the current source triple (HEAD 6c6e2a45); "
    "the Scenarios mirror stays at 257 canonical rows, digest sha256:43ab86d596572a90, and the transport/telegrams/autonomy/QUALITY>TIME/supersession truth of the current tree is mirrored — ready in OUTBOX, not integrated or pushed. |"
)
SUB_ROW_SAIT_OLD = (
    "| **saitranslate** | Translation producer | Builds complete locale packages in its own namespace. SAIT-030 is the latest package (32/32 locales at HEAD 71455482) and is stale against the current tree; collect refuses it until a fresh `ee` run rebinds. |"
)
SUB_ROW_SAIT_NEW = (
    "| **saitranslate** | Translation producer | Builds complete locale packages in its own namespace. SAIT-030 is the latest package (32/32 locales) and is stale against the current tree; collect refuses it until a fresh `ee` run rebinds. |"
)
SUB_CREW_ROW = (
    "| **crew circuit** | Convergence circuit | A sensor stage (SC-2..SC-5) also needs proof the role ran in THIS crew epoch: `saipen crew record-run <ROLE>` binds only ready/reviewed packages carrying the live source triple and role revision, and only a journal-written `crew_run` receipt counts. |"
)

# ---- Use-Cases.md: three new cases -----------------------------------------
USE_CASES_NEW = """
## 20. A replaced model keeps the execution (T-1446)

**Scenario:** The host swaps the model mid-Work. The successor has no private memory.

> saipen autonomy recall

Answers the turn-entry decision from STATE/BOARD/LOG plus the host carrier: `execution_epoch` anchored on the claim event (a model change writes no claim, so it cannot move the epoch), `replacement_detected`, and ONE decision -- RECOVER > USER_INPUT > OPERATOR_WAIT > AUTO_KICK > RUN_CONTINUE > ORDINARY. A kick means run `saipen continue --json` before any chat. Work, Source, checkpoint and epoch survive every failure class; only the agent incarnation changes.

## 21. Done work, re-proven on today's tree (T-1434)

**Scenario:** A ticket closed DONE three releases ago. The tree moved. Is it still true?

> saipen work reverify T-1202 --verification "python -B tools/validate.py --gate core:PASS"

Writes ONE immutable `RV-NNNNNN` receipt bound to the run, keeps DONE, never rewrites history. An EXECUTED contract is current-tree closure evidence; an attested-only contract is recorded but is never proof.

## 22. Telegrams advise, never command (T-1497)

**Scenario:** Another agent left mail in the SAIMAIL workspace. Does it steer the run?

No. Every `continue`/`cc`/`status` JSON answer carries `telegrams` -- unread COUNTS only, when `SAIMAIL_WORKSPACE` is set and `saimail-local` is on PATH. A nonzero count is reported; reading is `read_command`, opening is an explicit decision. A telegram never routes, creates Work or skips a WAIT.
"""

EDITS: list[tuple[str, str, str]] = [
    # Home.md
    (
        "Home.md",
        HOME_TABLE_VALIDATE_OLD,
        "| `saipen validate` | Conformance front door: structural precheck, then the canonical validator; VALID only on CURRENT_PASS |\n"
        "| `saipen crew` | The whole circuit: hunt, reproduce, intake, build, translate, document, ship |\n"
        "| `saipen test` | Run the declared suite, report PASS/FAIL |\n"
        "| `saipen status` | Read-only board report |\n"
        "| `saipen autonomy` | Read-only supervisor verdict (RUN_WORK, ADOPT_WORKER, REPLACE_WORKER, AWAIT_WORKER, OPERATOR_ACTION_DUE, NO_PROGRESS_LOOP, AMBIGUOUS_AUTHORITY, IDLE) |\n"
        "| `saipen autonomy recall` | Read-only turn-entry decision for a replaced/cold agent (AUTO_RECALL / AUTO_KICK) |\n"
        "| `saipen gpu [status\\|on\\|off\\|index\\|recall\\|triage]` | Idle-local-GPU advisory lane, default OFF; writes only `.saipen/cache/`, never truth |\n"
        "| `saipen host bootstrap / activation / entry` | Runtime binding diagnostics; `entry` proves the transport or names the failure |\n"
        "| `saipen rebind-home --auto \\| <path>` | Converge a dead persisted home onto a proven runtime |\n"
        "| `saipen handoff <T-###> --to <agent>` | Live claim transfer, same Work and phase |\n"
        "| `saipen work reverify <T-###>` | Re-verify DONE Work against the CURRENT tree (immutable RV-NNNNNN receipt) |\n"
        "| `saipen ticket resolve-external <T-###> ...` | Close BLOCKED Work implemented externally (EX-NNNNNN receipt) |\n"
        "| `saipen ticket reasoning <T-###> ...` | Canonical writer for strict-sweep reasoning gates |\n"
        "| `saipen ticket repair-metadata <T-###> ...` | Migrate legacy metadata on DONE Work (MR-NNNNNN receipt) |\n"
        "| `saipen source retire / link / append / apply-append / appends / recover / reconcile / quarantine` | Receipt-only source lifecycle: retirement, membership, handoff appends, reconciliation, quarantine |\n"
        "| `saipen sub reconcile <role> --authority <SRC-###>` | Producer-owned terminal reconciliation |\n"
        "| `saipen improve` | Meta-control audit: status / sweep / verify / clean; `improve reconcile <cycle>` is the strict-cycle finite exit |\n",
    ),
    (
        "Home.md",
        HOME_INVENTORY_OLD,
        HOME_INVENTORY_NEW,
    ),
    (
        "Home.md",
        "- **A distinct stop key** (v8.0.0)",
        HOME_NEW_BULLETS + "\n- **A distinct stop key** (v8.0.0)",
    ),
    # Getting-Started.md
    (
        "Getting-Started.md",
        GS_BOOTSTRAP_OLD,
        GS_BOOTSTRAP_NEW,
    ),
    (
        "Getting-Started.md",
        "An unowned cwd fails instead of guessing or creating a second memory tree.\n",
        "An unowned cwd fails instead of guessing or creating a second memory tree.\n"
        + GS_TRANSPORT,
    ),
    # Phases.md
    (
        "Phases.md",
        "- **Retirement is a third terminal verdict** (current tree): `saipen ticket retire` removes misrouted Work from schedulable Work under a registered reason, evidence resolving to a canonical event or owned artifact, and an operator authority receipt whose own text grants the Work -- never DONE, never a fabricated completion.\n",
        "- **Retirement is a third terminal verdict** (current tree): `saipen ticket retire` removes misrouted Work from schedulable Work under a registered reason, evidence resolving to a canonical event or owned artifact, and an operator authority receipt whose own text grants the Work -- never DONE, never a fabricated completion.\n"
        + PHASES_NEW_CHECKS,
    ),
    # SubSaipen.md
    (
        "SubSaipen.md",
        SUB_ROW_OLD,
        SUB_ROW_NEW,
    ),
    (
        "SubSaipen.md",
        SUB_ROW_SAIT_OLD,
        SUB_ROW_SAIT_NEW,
    ),
    # Use-Cases.md
    (
        "Use-Cases.md",
        "## 19. Knowing what proves each promise (v7.243.0+)",
        USE_CASES_NEW + "\n## 19. Knowing what proves each promise (v7.243.0+)",
    ),
]


def apply_edits() -> list[str]:
    touched: list[str] = []
    for name, old, new in EDITS:
        path = WIKI / name
        raw = path.read_bytes()
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig")
        if is_present(text, new):
            continue  # idempotent re-run
        pattern = re.compile("\r?\n".join(re.escape(part) for part in old.split("\n")))
        present = list(pattern.finditer(text))
        if not present:
            raise SystemExit(f"REFRESH_FAILED {name}: anchor not found: {old[:60]!r}")
        if len(present) != 1:
            raise SystemExit(f"REFRESH_FAILED {name}: anchor matched {len(present)} times: {old[:60]!r}")
        nl = "\r\n" if "\r\n" in present[0].group(0) else "\n"
        new_p = new.replace("\n", nl)
        text = text[: present[0].start()] + new_p + text[present[0].end():]
        path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
        if name not in touched:
            touched.append(name)
    return touched


if __name__ == "__main__":
    changed = apply_edits()
    print("refreshed:", ", ".join(changed) if changed else "(no change; already fresh)")
    sys.exit(0)
