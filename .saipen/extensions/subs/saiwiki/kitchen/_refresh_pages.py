"""saiwiki FORCE-FRESH page refresh (W-047).

Applies the drift corrections the current source tree requires, as exact
text replacements with an assertion per edit: a replacement that matches
nothing, or matches twice, is a hard failure -- a producer never guesses.

Every edit below names the canonical owner it mirrors:

  * screen 1: `saipen start` is THE entry command (BOOT.md Entry table,
    COMMANDS.md canonical table)
  * screen 2: command semantics are owned by COMMANDS.md / REGISTRY.json,
    never by CORE prose (CORE § 1.10, BOOT.md step 7)
  * screen 3: cold route, project binding and host-search-fault rules
    (BOOT.md step 2, REGISTRY.json cold_agent_truth)
  * screen 4: the 1200-character live BOARD record cap and
    `BOARD_RECORD_OVERSIZE` (CORE)
  * screen 5: retirement as a third terminal verdict and
    `saipen ticket retire` (CORE, COMMANDS.md, OPS.md)
  * screen 6: producer status truth for this namespace (W-047 / SAIT-030)

The script touches only `.saipen/extensions/subs/saiwiki/kitchen/wiki/`,
which is this producer's own payload. It never writes the main tree, and it
performs no integration, commit, tag, push or remote write.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RE_PRESENT_CACHE: dict[str, tuple[re.Pattern[str], re.Pattern[str]]] = {}


def is_present(text: str, new: str, cache: dict, name: str) -> bool:
    """True when this already-refreshed text carries the intended result.

    The check is newline-agnostic for the same reason the anchor is: a page
    may gain the inserted block in either style, and a re-run must not
    duplicate it. The cache is keyed by the inserted block itself, not by the
    page, because one page carries several edits.
    """
    if new in cache:
        pat = cache[new]
    else:
        pat = re.compile("\r?\n".join(re.escape(part) for part in new.split("\n")))
        cache[new] = pat
    return pat.search(text) is not None

ROOT = Path(__file__).resolve().parents[5]
WIKI = ROOT / ".saipen" / "extensions" / "subs" / "saiwiki" / "kitchen" / "wiki"

NEW_START_TUTORIAL = """## 16. One command opens a task (current tree)

New actionable input goes to START first; `status`, `continue`, `source`,
`recover` and any seat negotiation run only when START names one:

```text
$ saipen start 'flaky upload retry on second submit'
STARTED   -> load_path: .saipen/phases/build.md   action: BUILD T-1401
```

If the shell cannot carry the task text, START computes the transport that
does and names it verbatim:

```text
next: saipen start --hex 666c616b7920e280a6      (hex-encoded UTF-8)
next: saipen start --file .saipen/intake/task.txt (write the text verbatim)
```

`--receipt SRC-###` resumes an unconsumed source receipt instead of minting a
second ticket for the same request. The task text is never reworded to get
past a refusal: a refusal names the exact command to run.
"""

NEW_GS_TASK_SECTION = """## Start a new task

New actionable input goes to `saipen start` FIRST -- not `status`, `continue`,
`source`, `recover` or a seat/role negotiation. START performs the capture, the
recovery preflight, the seat and the claim itself and returns the phase plus
the action to run now.

| Situation | First command |
|---|---|
| New actionable user input | `saipen start '<the task, one line>'` |
| No new user input | `saipen continue` |
| Status request / diagnostic need | `saipen status --json` |

Its answer always names what to do next:

- `STARTED` -- read `load_path`, execute `action` now. Nothing else first.
- `next: <command>` -- run it, then `saipen start --receipt SRC-###`.
- `next: saipen start --hex <hex>` -- the shell could not carry the task text,
  so run exactly that.
- `next: saipen start --file <path>` -- write the task text VERBATIM to a UTF-8
  file with your write tool (no shell, no quoting), then run it.

Never reword the user's task to get past a refusal.

"""

NEW_BINDING_PARAGRAPH = """**Binding order (current tree):** explicit target wins, then a verified
host/session carrier (`SAIPEN_PROJECT_ROOT`, validated against optional
`SAIPEN_PROJECT_LINEAGE` and `.saipen/IDENTITY.md`), then the Git worktree root,
then the nearest ancestor carrying `.saipen/`. Never search for protocol files:
`saipen status --json` reports a `cold_route` block naming the bound root,
`protocol_dir`, `boot`, `style`, `phase_module` and the memory files with
`search_required: false`. A host search fault -- a ripgrep error, for example --
is a host fault and never a SAIPEN binding failure; `saipen search --hex
<hex-encoded-utf8>` is the canonical read-only transport and still works while
protocol state is invalid. Zero matches is a normal result, never a failure to
retry. Actor binding is separate: `SAIPEN_AGENT` is an optional explicit actor
carrier, and a host session id is never a seat.
"""

NEW_PHASE_CHECKS = """- **One command opens a task** (current tree): new actionable input goes to `saipen start` first -- capture, recovery preflight, seat and claim in one step -- and its answer is `STARTED`, `next: <command>`, or the exact `--hex`/`--file` transport when the shell cannot carry the text. `status`, `continue`, `source`, `recover` and seat negotiation run only when START names one, and a refusal is never answered by rewording the task.
- **A host search fault is not a binding failure** (current tree): `saipen status --json` publishes a deterministic `cold_route` (`search_required: false`), a verified host/session root carrier outranks cwd, a host session id is never a seat, and `saipen search --hex` keeps a read-only bounded search available while protocol state is invalid.
- **A live BOARD record is capped** (current tree): a newly created or updated live record holds at most 1200 characters. Historical longer rows stay valid and are never rewritten to meet the cap; a canonical writer touching oversized material externalizes it or refuses with `BOARD_RECORD_OVERSIZE`, so intent is never silently truncated.
- **Retirement is a third terminal verdict** (current tree): `saipen ticket retire` removes misrouted Work from schedulable Work under a registered reason, evidence resolving to a canonical event or owned artifact, and an operator authority receipt whose own text grants the Work -- never DONE, never a fabricated completion.
"""

NEW_HOME_BULLETS = """- **One command opens a task** (current tree): `saipen start '<task>'` performs the capture, the recovery preflight, the seat and the claim itself and answers with the action to run now -- `STARTED`, or `next: <command>`, or the exact `--hex`/`--file` transport when the shell cannot carry the text. START runs FIRST for new input; `status`, `continue`, `source` and `recover` run only when START names one. The user's task is never reworded to get past a refusal.
- **A host search fault is not a SAIPEN failure** (current tree): the cold route comes from a deterministic `cold_route` block (`saipen status --json`, `search_required: false`), a verified host/session root carrier (`SAIPEN_PROJECT_ROOT`, optional `SAIPEN_PROJECT_LINEAGE` plus `.saipen/IDENTITY.md`) outranks cwd, and `saipen search --hex <hex-utf8>` is the canonical read-only search transport that still works while protocol state is invalid. A ripgrep error is a host fault; zero matches is a normal result.
- **A seat is not a host session id** (current tree): `SAIPEN_AGENT` is an optional explicit actor carrier, and a host identity is never a seat -- the explicit launcher refuses a seat that names the host it is launching.
- **A live BOARD record is capped, never truncated** (current tree): new and updated live records hold at most 1200 characters, older longer rows stay valid data, and a writer touching oversized material externalizes it or refuses with `BOARD_RECORD_OVERSIZE`.
- **Retirement is a third terminal verdict** (current tree): Work minted into the wrong project leaves schedulable Work through `saipen ticket retire`, which demands a registered reason, evidence that resolves to a canonical event or owned artifact, and an operator authority receipt whose own text grants the Work. Nothing is fabricated to call it DONE.
- **Current tree inventory** (measured at this package's source binding, HEAD over v8.0.1): 139 `tools/test_*.py` modules declaring 2791 test methods, and the validator mutation-control harness declares its 229 full-sweep controls -- the release gate still runs the full sweep, and a scoped run is never release evidence."""

EDITS: list[tuple[str, str, str]] = [
    # ---- Home.md -----------------------------------------------------------
    (
        "Home.md",
        "```\nUser  ->  /saipen continue\nAgent ->  reads STATE.md (phase, task, next_action, mode, human_note)",
        "```\nNEW TASK     ->  saipen start '<the task, one line>'\nNO NEW INPUT ->  /saipen continue\nAgent ->  reads STATE.md (phase, task, next_action, mode, human_note)",
    ),
    (
        "Home.md",
        "## 27 commands, full surface\n\n| Command | Effect |\n|---|---|\n"
        "| `saipen set` / `saipen init` | Bootstrap .saipen/ |\n"
        "| `saipen continue` / bare `saipen` | Resume from STATE |",
        "## Commands, full surface\n\n"
        "The table below is the public surface. The closed machine vocabulary lives\n"
        "in `REGISTRY.json`; internal recovery and diagnostic verbs (`recover`,\n"
        "`claim`, `transition`, `checkpoint`, `attempt`, `scope`, `next`,\n"
        "`permissions`, `explain-next`, `first-publish-confirm`, `rebind-home`) are\n"
        "reached by refusals and by START, not typed by hand.\n\n"
        "| Command | Effect |\n|---|---|\n"
        "| `saipen set` / `saipen init` | Bootstrap .saipen/ |\n"
        "| `saipen start '<task>' [--file PATH] [--hex HEX] [--receipt SRC-###]` | THE entry command for a new actionable task: capture, recovery preflight, seat and claim, then the action to run now |\n"
        "| `saipen continue` / bare `saipen` | Resume from STATE |",
    ),
    (
        "Home.md",
        "| `saipen ship` | Version bump, tag, push |\n| `saipen hunt` | Run the HUNT sweep now |",
        "| `saipen ship` | Version bump, tag, push |\n"
        "| `saipen push` | Push the committed release to the remote |\n"
        "| `saipen hunt` | Run the HUNT sweep now |",
    ),
    (
        "Home.md",
        "| `saipen acceptance <T-###>` | Read-only verdict per promised criterion: SATISFIED/FAILED/UNVERIFIED/CONTESTED |\n",
        "| `saipen acceptance <T-###>` | Read-only verdict per promised criterion: SATISFIED/FAILED/UNVERIFIED/CONTESTED |\n"
        "| `saipen context orient [--handoff JSON]` | Read-only bounded orientation: measured STATE / current-ticket / LOG-tail projection, never mtime authority |\n"
        "| `saipen brief` | Generated handoff carrying identity, lineage and event provenance |\n"
        "| `saipen search <pattern>` | Read-only bounded search; `--hex <hex-utf8>` still works while protocol state is invalid |\n"
        "| `saipen knowledge [status\\|index\\|retrieve]` | Project knowledge index and retrieval |\n"
        "| `saipen audit [status\\|inspect\\|ingest]` | Audit-layer transport and residue report |\n"
        "| `saipen ticket retire <T-###> --reason <CODE> --evidence <E-###\\|PATH> --authority <SRC-###>` | Canonical retirement of misrouted Work: a third terminal verdict, never DONE |\n"
        "| `saipen cohort [status\\|ship] <C-###>` | Batch publication authority |\n"
        "| `saipen sub <verb> <name>` | SubSaipen spawn / adopt / sync / collect |\n"
        "| `saipen user-request <text>` | Capture a new actionable user request as a durable source receipt |\n"
        "| `saipen hush <task>` | Change narration only; nothing about safety, lifecycle or evidence |\n"
        "| `saipen --agent <seat> launch opencode -- [args]` | Optional explicit-actor host launch; a missing seat fails ACTOR_UNBOUND |\n",
    ),
    (
        "Home.md",
        "**Shortcuts** (full 19-key table in [CORE § 1.10](https://github.com/vacterro/saipen/blob/main/saipen/CORE.md#110-command-surface)):",
        "**Shortcuts** (full 19-key table in [COMMANDS.md § Shortcut table](https://github.com/vacterro/saipen/blob/main/saipen/COMMANDS.md#shortcut-table); `CORE § 1.10` carries only the routing rules and names `COMMANDS.md` as the owner):",
    ),
    (
        "Home.md",
        "- **Audit closure on the current v7.248.0 tree**: canonical Ruff is clean, 945 tests pass (tools/), all 229 validator mutation controls still go red on their own conditions, executable scenarios pass, and the active changelog is compacted to its 10 newest releases.",
        NEW_HOME_BULLETS,
    ),
    # ---- Getting-Started.md ------------------------------------------------
    (
        "Getting-Started.md",
        "No install? Paste one line to any agent:\n> `Read <clone>/saipen/BOOT.md first, then <clone>/saipen/CORE.md + <clone>/saipen/STYLE.md`\n",
        "No install? Paste one line to any agent:\n> `Read <clone>/saipen/BOOT.md first, then <clone>/saipen/CORE.md + <clone>/saipen/STYLE.md`\n\n"
        + NEW_GS_TASK_SECTION,
    ),
    (
        "Getting-Started.md",
        "| `saipen` / `saipen continue` | Any time | Resume: read STATE, execute next_action |\n",
        "| `saipen` / `saipen continue` | Any time | Resume: read STATE, execute next_action |\n"
        "| `saipen start '<task>'` | New task | THE entry command: capture + recovery preflight + seat + claim in one step |\n"
        "| `saipen context orient [--handoff JSON]` | Zero context | Bounded read-only orientation with measured bytes |\n"
        "| `saipen brief` | Any | Generated handoff with identity, lineage and event provenance |\n"
        "| `saipen search <pattern>` | Any | Read-only bounded search (`--hex` works while state is invalid) |\n"
        "| `saipen audit [status\\|inspect\\|ingest]` | Any | Audit-layer transport and residue report |\n"
        "| `saipen ticket retire <T-###> ...` | Misrouted Work | Retire, never finish: needs reason + evidence + an operator receipt that grants it |\n"
        "| `saipen sub <verb> <name>` | Any | SubSaipen spawn / adopt / sync / collect |\n"
        "| `saipen push` | SHIP | Push the committed release |\n"
        "| `saipen user-request <text>` | Any | Capture a new actionable user request as a source receipt |\n"
        "| `saipen hush <task>` | Any | Narration only; no lifecycle or safety effect |\n",
    ),
    (
        "Getting-Started.md",
        "An unowned cwd fails instead of guessing or creating a second memory tree.\n",
        "An unowned cwd fails instead of guessing or creating a second memory tree.\n\n" + NEW_BINDING_PARAGRAPH,
    ),
    # ---- Tutorials.md ------------------------------------------------------
    (
        "Tutorials.md",
        "The full 19-key table lives in [CORE § 1.10](https://github.com/vacterro/saipen/blob/main/saipen/CORE.md#110-command-surface).",
        "The full 19-key table lives in [COMMANDS.md § Shortcut table](https://github.com/vacterro/saipen/blob/main/saipen/COMMANDS.md#shortcut-table) -- `CORE § 1.10` keeps the routing rules and points there.",
    ),
    (
        "Tutorials.md",
        "## WAIT category cheat sheet",
        NEW_START_TUTORIAL + "\n## WAIT category cheat sheet",
    ),
    # ---- Phases.md ---------------------------------------------------------
    (
        "Phases.md",
        "All phases have -> BLOCKED available (universal).\n",
        "All phases have -> BLOCKED available (universal). DONE and BLOCKED are not\n"
        "the only terminal verdicts: misrouted Work is RETIRED through `saipen ticket\n"
        "retire`, never finished and never marked DONE (current tree).\n",
    ),
    (
        "Phases.md",
        "## ДED Voice: phases rant",
        NEW_PHASE_CHECKS + "\n## ДED Voice: phases rant",
    ),
    # ---- SubSaipen.md ------------------------------------------------------
    (
        "SubSaipen.md",
        "| **saiwiki** | Wiki producer | FORCE-FRESH maintains all 9 wiki pages. W-044 is prepared against the current v8.0.1 source tree (HEAD 35ca656e); 257 scenarios rebuilt by canonical ID and reverified by digest sha256:43ab86d596572a90 — ready in OUTBOX, not integrated or pushed. |",
        "| **saiwiki** | Wiki producer | FORCE-FRESH maintains all 9 wiki pages. W-047 is prepared against the current source triple (HEAD 5d79ae78); the Scenarios mirror stays at 257 canonical rows, digest sha256:43ab86d596572a90, and the entry/binding/cap/retirement truth of the current tree is mirrored — ready in OUTBOX, not integrated or pushed. |",
    ),
    (
        "SubSaipen.md",
        "| **saitranslate** | Translation producer | Builds complete locale packages in its own namespace. SAIT-028 is the latest package but stale against the v8.0.1 tree; collect refuses it until a fresh `ee` run rebinds. |",
        "| **saitranslate** | Translation producer | Builds complete locale packages in its own namespace. SAIT-030 is the latest package (32/32 locales at HEAD 71455482) and is stale against the current tree; collect refuses it until a fresh `ee` run rebinds. |",
    ),
]


def apply_edits() -> list[str]:
    touched: list[str] = []
    for name, old, new in EDITS:
        path = WIKI / name
        raw = path.read_bytes()
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig")
        # A page may mix line endings inside one anchor (the wiki clone is
        # CRLF-authored, later hand edits left LF regions), so a literal match
        # is not enough: each newline in the anchor matches either style, and
        # the inserted text adopts the style the anchor actually used.
        # Order matters: most edits INSERT a block whose text still contains
        # the anchor line verbatim, so testing the anchor first would find it
        # inside the block this script already wrote and insert a second copy.
        # The result is tested before the anchor, which makes a re-run a no-op.
        if is_present(text, new, RE_PRESENT_CACHE, name):
            continue  # already refreshed -- idempotent re-run
        pattern = re.compile("\r?\n".join(re.escape(part) for part in old.split("\n")))
        present = list(pattern.finditer(text))
        if not present:
            raise SystemExit(f"REFRESH_FAILED {name}: anchor not found")
        if len(present) != 1:
            raise SystemExit(f"REFRESH_FAILED {name}: anchor matched {len(present)} times")
        nl = "\r\n" if "\r\n" in present[0].group(0) else "\n"
        new_p = new.replace("\n", nl)
        text = text[: present[0].start()] + new_p + text[present[0].end() :]
        path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
        if name not in touched:
            touched.append(name)
    return touched


if __name__ == "__main__":
    changed = apply_edits()
    print("refreshed:", ", ".join(changed) if changed else "(no change; already fresh)")
    sys.exit(0)
