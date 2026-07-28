#!/usr/bin/env python
"""saipen conformance validator (canonical).

Stdlib only -- no pip installs, ever. Run from a project root (the
directory containing .saipen/):

    python <saipen-home>/tools/validate.py [--strict]

Covers every check tests/validate.sh / validate.ps1 perform (those two
are the frozen portable floor for hosts without Python -- new checks land
here only), plus checks the shell pair structurally can't do well:
E-### monotonicity/uniqueness, parent-reference resolution, ticket-line
grammar, unknown BOARD fields, UTC enforcement on `updated`.

STATE.md's shape is validated against extensions/schemas/state.schema.json
directly (required/enum/type subset of JSON Schema, interpreted natively).
The schema is the machine-readable mirror of the field list, never a second
opinion about it: RFC § 1.2's required set is normative, and the schema's
`required` array is deliberately narrower because it cannot express the two
conditional members (`transition_from` except on fresh INIT; the goal
counters only under `goal_mode: true`). Those two are checked below in code,
so "absent from `required`" here means "checked elsewhere", not "optional".

Severity model: violations of RFC.md MUSTs fail (exit 1). Drift that lives
in immutable history (LOG.md is append-only -- a nonstandard taxonomy or
ticket-ref written months ago cannot be fixed without rewriting history,
which RFC forbids) warns instead. --strict promotes warnings to failures.
"""

import datetime
import io
import json
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from pathlib import Path

STRICT = "--strict" in sys.argv[1:]
USE_COLOR = sys.stdout.isatty()

CURRENT_SCHEMA_VERSION = 1

# extensions/subs/PROTOCOL.md § 2 status table -- the normative list for
# the extension (RFC § 1.9). Named rather than inlined so the cross-doc
# check can compare it against the table and the schema enum.
OUTBOX_STATUSES = ("ready", "draft", "blocked", "reviewed", "stale")
failures = []
warnings = {}


def color(code, text):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def ok(msg):
    print(color("32", f"PASS: {msg}"))


def fail(msg):
    failures.append(msg)
    print(color("31", f"FAIL: {msg}"))


def warn(category, msg):
    """Warnings are grouped by category and summarized at the end -- a
    style-drift pattern repeated 300 times in immutable history is one
    finding, not 300 lines of noise drowning the failures."""
    warnings.setdefault(category, []).append(msg)


# ---------------------------------------------------------------- frontmatter

def parse_frontmatter(text):
    """Parse the YAML subset STATE.md actually uses: scalar `key: value`
    lines and simple `- item` lists. Returns (dict, error-or-None)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "no opening --- frontmatter fence"
    fields = {}
    current_list_key = None
    for line in lines[1:]:
        if line.strip() == "---":
            return fields, None
        if not line.strip():
            continue
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item and current_list_key:
            fields[current_list_key].append(coerce(item.group(1).strip()))
            continue
        kv = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if not kv:
            return None, f"unparseable frontmatter line: {line!r}"
        key, raw = kv.group(1), kv.group(2).strip()
        if raw == "":
            fields[key] = []
            current_list_key = key
        else:
            fields[key] = coerce(raw)
            current_list_key = None
    return None, "no closing --- frontmatter fence"


def coerce(raw):
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    if raw in ("true", "false"):
        return raw == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    return raw


TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
}


def check_against_schema(fields, schema, label):
    """Interpret the required/enum/type/additionalProperties subset of JSON Schema.
    That subset is everything state.schema.json actually uses -- if the schema ever
    grows past it, extend this, don't silently skip."""
    props = schema.get("properties", {})
    additional_forbidden = schema.get("additionalProperties") is False
    for req in schema.get("required", []):
        if req not in fields:
            fail(f"{label} missing required field: {req}")
    for key, value in fields.items():
        if key not in props:
            msg = f"{label} has field the schema doesn't know: " \
                  f"{key} (retired or misspelled?)"
            if additional_forbidden:
                fail(msg)
            else:
                warn("unknown-field", msg)
            continue
        spec = props[key]
        expected = spec.get("type")
        if expected in TYPE_CHECKS and not TYPE_CHECKS[expected](value):
            fail(f"{label} field {key}: expected {expected}, got "
                 f"{type(value).__name__} ({value!r})")
        if "enum" in spec and value not in spec["enum"]:
            fail(f"{label} field {key}: {value!r} not one of "
                 f"{'|'.join(spec['enum'])}")


# --------------------------------------------------------------------- STATE

print(color("36", "saipen conformance validation starting (tools/validate.py)..."))

state_path = Path(".saipen/STATE.md")
if not state_path.is_file():
    fail("STATE.md missing")
    print(color("31", "Cannot continue without STATE.md."))
    sys.exit(1)

schema_path = Path(__file__).resolve().parent.parent / "extensions" / "schemas" / "state.schema.json"
if not schema_path.is_file():
    fail(f"state.schema.json not found at {schema_path} -- SAIPEN home clone incomplete")
    sys.exit(1)
schema = json.loads(schema_path.read_text(encoding="utf-8"))

state, err = parse_frontmatter(state_path.read_text(encoding="utf-8-sig"))
if state is None:
    fail(f"STATE.md frontmatter: {err}")
    sys.exit(1)

before = len(failures)
check_against_schema(state, schema, "STATE.md")

# RFC § 1.2: updated MUST be ISO-8601 UTC specifically (Z or +00:00).
updated = state.get("updated")
if isinstance(updated, str):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00)", updated):
        fail(f"STATE.md updated must be ISO-8601 UTC (Z or +00:00), got: {updated!r} "
             f"-- Recovery's staleness comparison miscompares across timezones otherwise (RFC § 1.2)")

# RFC § 1.2: blocker MUST be non-empty when phase: BLOCKED.
if state.get("phase") == "BLOCKED" and state.get("blocker") in ("", "none", None):
    fail("STATE.md phase: BLOCKED but blocker is empty/none -- a blocked state "
         "with no stated reason is not conformant (RFC § 1.2)")

# Hard invariant: DONE -> task MUST be "none" (or empty — "none" preferred).
# RFC § 1.2: DONE is the terminal/no-active-ticket phase; a DONE state claiming
# a concrete task is a logic error (someone forgot to clear it).
if state.get("phase") == "DONE" and state.get("task") not in ("none", "", None):
    fail(f"STATE.md phase: DONE but task is {state['task']!r} -- DONE must "
         f"have task: none (no active ticket in terminal state)")

# RFC § 1.2 + § 1.5: DONE is a terminal phase; WAIT from DONE is legal ONLY
# for safety valve (§ 2.4) or explicit human brake. The board-empty drift
# check below (RFC § 2.1) handles the ZERO-PROMPT case; this catches the
# simpler "DONE with a concrete WAIT that isn't a valve" mistake directly.
_na_done = state.get("next_action", "") if isinstance(
    state.get("next_action"), str) else ""
if state.get("phase") == "DONE" and _na_done.startswith("WAIT:") \
        and "safety valve" not in _na_done.lower() \
        and not _na_done.lower().startswith("wait: user brake"):
    warn("done-wait", "STATE.md phase: DONE but next_action is WAIT -- "
         "DONE with WAIT is legal only for the § 2.4 safety valve or "
         "'WAIT: user brake -- <reason>' (RFC § 1.2); otherwise DONE "
         "should transition to SCOUT/PLAN/HUNT per RFC § 1.6 / § 2.1")

# Hard invariant: goal_mode: false -> goal_waves/goal_tickets MUST be absent.
if state.get("goal_mode") is False:
    for counter in ("goal_waves", "goal_tickets"):
        if counter in state and state[counter] is not None:
            fail(f"STATE.md goal_mode: false but {counter} is present "
                 f"({state[counter]!r}) -- counters MUST be cleared when "
                 f"goal_mode is off (RFC § 2.4 Exit)")

# schema_version invariant: must be >= CURRENT_SCHEMA_VERSION.
# Absence is tolerated for legacy pre-v1 states (warn, not fail), but a
# present value below current means the schema is outdated.
sv = state.get("schema_version")
if sv is None:
    warn("schema-version",
         "STATE.md has no schema_version -- legacy pre-v1 format. "
         "Set schema_version: 1 at next checkpoint.")
elif not isinstance(sv, int) or sv < CURRENT_SCHEMA_VERSION:
    fail(f"STATE.md schema_version is {sv!r}, expected >= "
         f"{CURRENT_SCHEMA_VERSION} -- state format may be incompatible "
         f"with current validator")

if len(failures) == before:
    ok("STATE.md schema valid (checked against state.schema.json)")

# RFC § 1.6 phase transition validation. transition_from tracks the
# previous phase; check every non-self transition against the table.
VALID_TRANSITIONS = {
    "INIT": ["PLAN", "BLOCKED"],
    "PLAN": ["SCOUT", "BUILD", "DONE", "BLOCKED"],
    "SCOUT": ["BUILD", "BLOCKED"],
    "BUILD": ["VERIFY", "BLOCKED"],
    "VERIFY": ["REVIEW", "SCOUT", "BUILD", "BLOCKED"],
    "REVIEW": ["SHIP", "BUILD", "SCOUT", "BLOCKED"],
    "SHIP": ["DONE", "BLOCKED"],
    "DONE": ["SCOUT", "PLAN", "HUNT", "BLOCKED"],
    "VALIDATE": ["SCOUT", "PLAN", "DONE", "BLOCKED"],
    "HUNT": ["ADD", "PLAN", "SCOUT", "BLOCKED"],
    "MARKHUNT": ["DONE", "BLOCKED"],
    "ADD": ["BUILD", "PLAN", "SCOUT", "DONE", "BLOCKED"],
    "CLEAN": ["DONE", "BLOCKED"],
    "TRANSLATE": ["DONE", "BLOCKED"],
    "PREPARE": ["DONE", "BLOCKED"],
    "BLOCKED": ["PLAN", "SCOUT", "DONE"],
}
# These seven phases are entered by explicit user command from ANY phase
# (RFC § 1.6/§ 1.10) -- the transition table's FROM row doesn't restrict them.
# PLAN joined in v7.92.0: § 2.4's goal-mode Entry mandates a PLAN for the new
# objective from wherever the pivot happens, so `saipen goal` out of REVIEW
# (whose row allows only SHIP/BUILD/SCOUT/BLOCKED) was an invalid state
# produced by following the protocol exactly. Caught on a live pivot.
# NOTE: SHIP is deliberately absent. `saipen ship` is recognized from any
# phase as a COMMAND (RFC § 1.10), but `phase: SHIP` is reachable only from
# REVIEW -- § 1.10 says so in as many words while this set said otherwise
# from v7.83.0 to v7.94.0. A command is not a transition.
ANY_FROM = {"VALIDATE", "MARKHUNT", "CLEAN", "TRANSLATE", "PREPARE", "PLAN"}

t_from = state.get("transition_from")
t_current = state.get("phase")

# Invariant: transition_from absent on non-INIT → FAIL.
# Absence tolerated only for fresh INIT bootstrap.
if t_from is None:
    if t_current != "INIT":
        fail("STATE.md missing transition_from -- required on all "
             "non-INIT states to validate phase transitions (RFC § 1.6)")
    else:
        warn("transition-from", "STATE.md phase: INIT but transition_from "
             "is absent -- set transition_from: INIT at next checkpoint "
             "to make it explicit")

if t_from and t_current:
    if t_from == t_current:
        if t_from not in VALID_TRANSITIONS and t_from not in ANY_FROM:
            fail(f"STATE.md self-transition at {t_from} but {t_from!r} is not "
                 f"a known phase -- must be one of the 16 enum values (RFC § 1.6)")
    elif t_current not in ANY_FROM:
        allowed = VALID_TRANSITIONS.get(t_from, [])
        if t_current not in allowed:
            fail(f"STATE.md invalid phase transition: {t_from} -> {t_current} "
                 f"(RFC § 1.6). Allowed from {t_from}: {', '.join(allowed)}")
        if t_from not in VALID_TRANSITIONS and t_from not in ANY_FROM:
            fail(f"STATE.md transition_from has unknown phase: {t_from!r} "
                 f"-- must be one of the 16 enum values (RFC § 1.6)")

# RFC § 1.3 mode/phase restrictions.
# NOTE: `no-publish` + `SHIP` is NOT checked here, deliberately. It used to
# be, and that check outlived the rule: v7.66.0 made SHIP reachable under
# `no-publish` (git-dependent steps are skipped, the local ones still run,
# STATE -> DONE) precisely because banning the phase outright left a git-less
# project unable to close any ticket at all -- `phases/review.md` makes SHIP
# mandatory before DONE. What `no-publish` actually forbids is the push/tag
# *steps*, which no `STATE.md` field can witness, so there is nothing here to
# assert. Re-adding a phase-level ban would hard-FAIL a legal state and, via
# tools/install_hook.py's pre-commit wiring, block that project's commits.
mode, phase = state.get("mode"), state.get("phase")
next_action = state.get("next_action")
if isinstance(next_action, str):
    vague_next_action = re.compile(
        r"\b(continue work|proceed|do next|review stuff|keep going|"
        r"maybe|if needed|ask if needed)\b",
        re.IGNORECASE)
    executable_prefixes = ("WAIT:", "saipen ", "PHASE ", "RUN:", "RESUME:")
    if vague_next_action.search(next_action):
        fail(f"STATE.md next_action is vague, not executable: {next_action!r} "
             f"(RFC § 1.2)")
    if not next_action.startswith(executable_prefixes):
        warn("next-action-shape",
             f"STATE.md next_action does not start with WAIT:/saipen /PHASE "
             f"/RUN:/RESUME:: {next_action!r} (RFC § 1.2)")
    # RFC § 1.2 (v7.93.0): WAIT carries a category token from a closed set of
    # seven. The stopping agent is the twin of § 1.11's guessing agent -- a
    # vague "WAIT: need more context" is shape-identical to a real gate, passes
    # every other check here, and parks the project on a question nobody can
    # answer. The token is what separates them mechanically, and it also tells
    # the human what kind of answer unblocks it.
    WAIT_CATEGORIES = ("manual-verify", "destructive-op", "first-publish",
                       "user brake", "blocked", "safety valve", "init")
    if next_action.startswith("WAIT:"):
        body = next_action[len("WAIT:"):].strip().lower()
        if not any(body.startswith(c) for c in WAIT_CATEGORIES):
            fail(f"STATE.md next_action is a WAIT with no category token -- "
                 f"RFC § 1.2 requires 'WAIT: <category> -- <question>' where "
                 f"category is one of {'/'.join(WAIT_CATEGORIES)}; got "
                 f"{next_action!r}")

    if "?" in next_action and not next_action.startswith("WAIT:"):
        fail(f"STATE.md next_action asks a question outside WAIT:: "
             f"{next_action!r} (RFC § 1.2)")
    # The prefix check above proves the shape, not the vocabulary: "saipen
    # hunt" passes it while naming a command RFC 1.10 does not define, and a
    # cold agent is then required to decline it and stop -- TEST-001 failing
    # on a state that looked perfectly valid. HUNT/ADD/BUILD etc. are phases
    # reached autonomously (1.6, 2.1), never words a user or a next_action
    # may invoke. Caught live in v7.89.0 on this repo's own STATE.md.
    if next_action.startswith("saipen "):
        verb = next_action[len("saipen "):].split()[0].strip('."\'') if \
            len(next_action.split()) > 1 else ""
        # 1.10's closed list. `saipen` bare (== continue) has no verb.
        known = {"set", "init", "continue", "goal", "plan", "clean",
                 "translate", "markhunt", "prepare", "ship", "validate",
                 "status", "stop", "sub"}
        if verb and verb not in known:
            fail(f"STATE.md next_action invokes 'saipen {verb}', which RFC "
                 f"§ 1.10 does not define -- a cold agent MUST decline an "
                 f"unrecognized command and stop, so this state fails "
                 f"TEST-001. Phases like HUNT/ADD are reached autonomously "
                 f"(§ 2.1), never invoked by name")

if phase in ("SCOUT", "BUILD", "VERIFY", "REVIEW", "SHIP") \
        and state.get("task") in ("none", "", None):
    if not (isinstance(next_action, str)
            and "ticket-less maintenance" in next_action.lower()):
        warn("taskless-active-phase",
             f"STATE.md phase {phase} has task: none -- active ticket phases "
             f"SHOULD name a T-### unless next_action explains a ticket-less "
             f"maintenance exception (RFC § 1.2)")
# RFC § 1.3: read-only cannot write, so every phase whose work product is a
# file write is unreachable. INIT (creates .saipen/) and PLAN (writes tickets
# onto BOARD.md) joined in v7.93.0 -- they were always unreachable in
# principle, but the enumeration named only four and read as exhaustive.
READ_ONLY_BANNED_PHASES = ("INIT", "PLAN", "ADD", "BUILD", "SHIP", "CLEAN",
                           "TRANSLATE")
if mode == "read-only" and phase in READ_ONLY_BANNED_PHASES:
    fail(f"mode: read-only MUST NOT enter {phase} -- that phase's work "
         f"product is a file write (RFC § 1.3)")

# RFC § 2.4 safety-valve ceilings. Named rather than inlined so the trip check
# below and any future reader see the same two numbers the RFC states.
GOAL_WAVE_CAP = 3
GOAL_TICKET_CAP = 20

# RFC § 2.4: goal_mode: true requires both persisted counters.
if state.get("goal_mode") is True:
    missing_counters = [c for c in ("goal_waves", "goal_tickets")
                        if not TYPE_CHECKS["integer"](state.get(c))]
    for counter in missing_counters:
        fail(f"goal_mode: true but {counter} counter missing -- safety valve "
             f"can't survive a restart without it (RFC § 2.4)")
    if not missing_counters:
        ok("goal_mode counters present")

        # RFC § 2.4: goal_mode: true with a counter at or over its cap IS the
        # tripped-valve state -- there is no separate flag. A resuming agent
        # MUST re-state the stop rather than continue, so the tripped state has
        # to be visible in STATE.md itself, not just in whatever the last agent
        # happened to remember. Shipped as prose in v7.86.0 with nothing
        # checking it, which is precisely the "restart walks past the valve"
        # failure the persisted counters exist to prevent (v7.92.0).
        waves, ticks = state.get("goal_waves"), state.get("goal_tickets")
        if waves >= GOAL_WAVE_CAP or ticks >= GOAL_TICKET_CAP:
            na = state.get("next_action", "") or ""
            if not na.startswith("WAIT:") or "safety valve" not in na.lower():
                fail(f"goal_mode: true with goal_waves={waves}/"
                     f"goal_tickets={ticks} is the tripped safety valve "
                     f"(caps {GOAL_WAVE_CAP}/{GOAL_TICKET_CAP}), but "
                     f"next_action={na!r} -- RFC § 2.4 requires "
                     f"next_action: WAIT: safety valve reached (N waves / "
                     f"M tickets) -- run 'saipen goal' to continue")
            # phase: BLOCKED here would satisfy § 2.4's Exit list and flip
            # goal_mode to false, making the bare `saipen goal` that the WAIT
            # line tells the user to run illegal under § 1.10 -- the valve
            # destroying its own continuation path.
            if state.get("phase") == "BLOCKED":
                fail("tripped safety valve MUST NOT set phase: BLOCKED -- "
                     "that is a § 2.4 Exit condition, so it clears goal_mode "
                     "and makes bare `saipen goal` (the documented way to "
                     "continue) illegal under § 1.10. Leave phase as-is")

# ------------------------------------------------------------------ SUBSAIPEN

# extensions/subs/PROTOCOL.md § 8: a subSaipen's STATE.md is the identical
# shape to Core's own, checked against the same schema -- never a separate
# restricted copy (that would relax Core's single source of truth for no
# real gain; see PROTOCOL.md § 1's own "procedural, not technical lock"
# stance on subSaipen enforcement generally).
subs_root = Path(".saipen/extensions/subs")
if not subs_root.is_dir():
    subs_root = Path("extensions/subs")  # legacy root-level location (RFC § 1.9)

# The SHIPPED library copies get checked too, not just this project's live
# instances. They are what `saipen sub spawn` copies from and what the
# injector distributes into every platform's skill folder, so a defect there
# propagates to every user -- strictly higher blast radius than one project's
# own working state. This was a real blind spot: extensions/subs/saipython/
# shipped carrying one machine's absolute `saipen_home` (and a live timestamp
# where its siblings had the placeholder) for several releases, because
# nothing ever walked that path. Deduped, since in the home repo `subs_root`
# already IS extensions/subs.
# Only the SAIPEN home actually ships a library -- fingerprinted the same way
# the distribution self-check below is, and for the same reason: a consuming
# project may legitimately keep its subs at root-level `extensions/subs/`
# (RFC § 1.9's legacy location), where a concrete `saipen_home` is not a
# defect but exactly what `saipen sub spawn` is required to write. Treating
# that as "a shipped template" hard-FAILED such a project and, via
# tools/install_hook.py's pre-commit wiring, blocked its commits -- caught by
# testing this path right after shipping the check, not by reasoning about it.
IS_SAIPEN_HOME = (Path("saipen").is_dir() and Path("bootstrap").is_dir()
                  and Path("VERSION").is_file() and Path("README.md").is_file())

sub_state_files = sorted(
    p for p in subs_root.glob("*/STATE.md") if p.parent.name != "TEMPLATE")
library_subs = Path("extensions/subs")
if (IS_SAIPEN_HOME and library_subs.is_dir()
        and library_subs.resolve() != subs_root.resolve()):
    sub_state_files += sorted(
        p for p in library_subs.glob("*/STATE.md") if p.parent.name != "TEMPLATE")

if sub_state_files:
    subs_ok = True
    for sp in sub_state_files:
        sub_state, err = parse_frontmatter(sp.read_text(encoding="utf-8-sig"))
        if sub_state is None:
            fail(f"{sp} frontmatter: {err}")
            subs_ok = False
            continue
        before_sub = len(failures)
        check_against_schema(sub_state, schema, str(sp))
        if sub_state.get("mode") != "read-only":
            fail(f"{sp} mode is {sub_state.get('mode')!r}, MUST be read-only "
                 f"(extensions/subs/PROTOCOL.md § 1)")
        if sub_state.get("phase") in ("BUILD", "SHIP", "CLEAN", "TRANSLATE"):
            fail(f"{sp} phase {sub_state.get('phase')} is unreachable under "
                 f"mode: read-only (RFC § 1.3) -- a subSaipen MUST NOT enter it")
        # A shipped template must not carry one machine's absolute path: it
        # is copied verbatim to every user, where that path does not exist.
        # Only the placeholder (or the field being absent) is legal here.
        if IS_SAIPEN_HOME and sp.parts[0] == "extensions" \
                and sub_state.get("saipen_home"):
            fail(f"{sp} carries a concrete saipen_home "
                 f"({sub_state['saipen_home']!r}) -- this file ships to every "
                 f"user and is copied by `saipen sub spawn`; a machine-specific "
                 f"path here leaks the author's layout and hands users a dead "
                 f"pointer. Use \"\" and let spawn fill it in (PROTOCOL.md § 7)")
        # RFC § 1.2: subSaipen next_action MUST follow same prefix rules as Core.
        sub_na = sub_state.get("next_action")
        if isinstance(sub_na, str):
            sub_vague = re.compile(
                r"\b(continue work|proceed|do next|review stuff|keep going|"
                r"maybe|if needed|ask if needed)\b", re.IGNORECASE)
            if sub_vague.search(sub_na):
                fail(f"{sp} next_action is vague, not executable: {sub_na!r} "
                     f"(RFC § 1.2)")
            if not sub_na.startswith(executable_prefixes):
                fail(f"{sp} next_action does not start with WAIT:/saipen /PHASE "
                     f"/RUN:/RESUME:: {sub_na!r} (RFC § 1.2)")
            if sub_na.startswith("WAIT:"):
                body = sub_na[len("WAIT:"):].strip().lower()
                if not any(body.startswith(c) for c in WAIT_CATEGORIES):
                    fail(f"{sp} next_action is WAIT with no category token -- "
                         f"must be one of {'/'.join(WAIT_CATEGORIES)}; got "
                         f"{sub_na!r}")
            if "?" in sub_na and not sub_na.startswith("WAIT:"):
                fail(f"{sp} next_action asks a question outside WAIT:: "
                     f"{sub_na!r} (RFC § 1.2)")
        if len(failures) > before_sub:
            subs_ok = False
    if subs_ok:
        ok(f"subSaipen STATE.md shape valid ({len(sub_state_files)} checked, "
           f"live + shipped library)")

# --------------------------------------------------------------------- BOARD

board_path = Path(".saipen/BOARD.md")
if not board_path.is_file():
    fail("BOARD.md missing")
    sys.exit(1)

REQUIRED_HEADINGS = ["## DOING", "## TODO", "## DONE", "## BLOCKED"]
KNOWN_FIELDS = {"needs", "owner", "claim_time", "blocker", "verify", "review_passes"}
TICKET_RE = re.compile(r"^- \[([ x/])\] (T-\d+)\s+(.*)$")
PIPE_SENTINEL = "\x00"

board_lines = board_path.read_text(encoding="utf-8-sig").splitlines()
headings_seen = []
tickets = {}          # id -> {"section", "line_no", "checkbox", "needs", "fields"}
section = None

for line_no, line in enumerate(board_lines, 1):
    if line.startswith("## "):
        section = line.strip()
        headings_seen.append(section)
        continue
    if not line.strip():
        continue
    if line.lstrip().startswith("- ["):
        m = TICKET_RE.match(line.strip().replace("\\|", PIPE_SENTINEL))
        if not m:
            fail(f"BOARD.md:{line_no} ticket-ish line doesn't match RFC § 1.2 shape "
                 f"`- [ ] T-### description`: {line.strip()!r}")
            continue
        checkbox, tid, rest = m.groups()
        if section not in REQUIRED_HEADINGS:
            fail(f"BOARD.md:{line_no} ticket {tid} sits under "
                 f"{section or 'no heading'} -- not one of the four RFC sections")
        if tid in tickets:
            fail(f"BOARD.md:{line_no} duplicate ticket ID {tid} (first at line "
                 f"{tickets[tid]['line_no']}) -- a status change must move the "
                 f"line (cut+paste), never copy it (RFC § 1.2)")
            continue
        parts = [p.strip() for p in rest.split(" | ")]
        needs, fields = [], {}
        for part in parts[1:]:
            fm = re.match(r"^([a-z_]+):\s*(.*)$", part)
            if not fm or fm.group(1) not in KNOWN_FIELDS:
                fail(f"BOARD.md:{line_no} ticket {tid} has unrecognized field "
                     f"{part!r} -- RFC § 1.2's field list is closed "
                     f"(needs/owner/claim_time/blocker/verify); a literal | in "
                     f"the description must be escaped as \\|")
                continue
            fields[fm.group(1)] = fm.group(2)
            if fm.group(1) == "needs":
                needs = re.findall(r"T-\d+", fm.group(2))
        tickets[tid] = {"section": section, "line_no": line_no,
                        "checkbox": checkbox, "needs": needs, "fields": fields,
                        "raw": line}

for heading in REQUIRED_HEADINGS:
    if heading not in headings_seen:
        fail(f"BOARD.md missing required section heading: {heading}")
if all(h in headings_seen for h in REQUIRED_HEADINGS):
    ok("BOARD.md has all required section headings")

for heading in REQUIRED_HEADINGS:
    count = headings_seen.count(heading)
    if count > 1:
        fail(f"BOARD.md has duplicate section heading {heading} ({count} times) "
             f"-- duplicate status buckets split the work surface (RFC § 1.2)")

if not any(f.startswith("BOARD.md") and "duplicate" in f for f in failures):
    ok("BOARD.md no duplicate tickets")

dangling = []
for tid, t in tickets.items():
    for ref in t["needs"]:
        if ref not in tickets:
            dangling.append(f"{tid} needs nonexistent {ref} (line {t['line_no']})")
if dangling:
    fail("BOARD.md dangling needs: reference(s): " + "; ".join(dangling) +
         " -- leaves the Pick Rule permanently unsatisfiable with zero signal")
else:
    ok("BOARD.md no dangling needs: references")

# Kahn's algorithm; whatever can't be removed forms a cycle.
remaining = dict(tickets)
progress = True
while remaining and progress:
    progress = False
    for tid in list(remaining):
        if not any(ref in remaining for ref in remaining[tid]["needs"]):
            del remaining[tid]
            progress = True
if remaining:
    fail("BOARD.md contains cyclic needs: dependencies involving: "
         + ", ".join(sorted(remaining)))
else:
    ok("BOARD.md acyclic")

# RFC § 2.1 ZERO-PROMPT AUTO-TRANSITION: DONE + empty TODO + no MARKHUNT
# blockers = MUST auto-transition HUNT->ADD, never WAIT at DONE.
if state.get("phase") == "DONE" and state.get("goal_mode") is not True:
    open_todos = sum(1 for t in tickets.values()
                     if t["section"] == "## TODO" and t["checkbox"] in (" ", ""))
    markhunt_blocked = bool(re.search(
        r"## BLOCKED.*?\[MARKHUNT\]", board_path.read_text("utf-8-sig"),
        re.DOTALL))
    next_action = state.get("next_action", "")
    if open_todos == 0 and not markhunt_blocked and next_action.startswith("WAIT:"):
        # RFC § 1.2 allows exactly two WAITs in this exact state, both in a
        # fixed wording so they are machine-separable from drift: the § 2.4
        # safety valve, and the user's own explicit brake. Free-prose "waiting
        # for something" is indistinguishable from a previous agent asking the
        # user what to do next -- which § 2.1 forbids outright -- so it is
        # treated as drift. WARN until v7.92.0; promoted to FAIL once § 1.11
        # gained the UNBLOCK exception that tells an agent what to do instead
        # (auto-transition DONE -> HUNT), because a warning still leaves a weak
        # model sitting on a deadlocked board waiting for a human who was never
        # asked a real question.
        low = next_action.lower()
        if "safety valve" not in low and not low.startswith("wait: user brake"):
            fail(f"phase: DONE, empty ## TODO, no [MARKHUNT] blockers, "
                 f"but next_action={next_action!r} -- RFC § 2.1 says bare "
                 f"command + empty board MUST auto-transition HUNT->ADD. "
                 f"The only legal WAITs here are the § 2.4 safety valve and "
                 f"'WAIT: user brake -- <reason>' (RFC § 1.2); anything else "
                 f"deadlocks the board (§ 1.11 UNBLOCK exception)")

# RFC § 1.2 board soft cap. BOARD.md is read on every cold start (§ 1.1,
# BOOT.md's fast path), so its size is a real per-session cost -- same reasoning
# as the LOG cap below, minus the sealing machinery (the board is prunable,
# not append-only; phases/clean.md's scrub is the mechanism). WARN only:
# an oversized board is hygiene debt, never corruption.
board_kb = board_path.stat().st_size / 1024
if board_kb > 16:
    done_chars = sum(len(bl) for bl in board_lines
                     if bl.startswith("- [x]"))
    warn("board-soft-cap",
         f"BOARD.md is {board_kb:.0f} KB (soft cap ~16 KB), of which "
         f"{done_chars / 1024:.0f} KB is closed-ticket text -- that content "
         f"already lives in LOG.md/CHANGELOG.md, so scrub ## DONE at the next "
         f"CLEAN (RFC § 1.2, phases/clean.md step 1)")

for tid, t in tickets.items():
    if t["section"] == "## BLOCKED" and "blocker" not in t["fields"]:
        warn("blocked-no-blocker", f"BOARD.md:{t['line_no']} ticket {tid} is in "
             f"## BLOCKED with no | blocker: field -- facts + dead ends belong "
             f"on the ticket (RFC § 1.2)")
    # RFC § 1.2 (rule stated v7.93.0): the section IS the status, the checkbox
    # is how a human skims it. A board where they disagree answers "is this
    # done" differently depending on which one the reader trusts. FAIL, not
    # WARN -- there is no legacy shape here to tolerate, only a mistake.
    if t["checkbox"] == "x" and t["section"] != "## DONE":
        fail(f"BOARD.md:{t['line_no']} ticket {tid} is checked [x] but sits "
             f"under {t['section']} -- checkbox and section disagree; [x] "
             f"belongs only under ## DONE (RFC § 1.2)")
    if t["checkbox"] == "/" and t["section"] != "## DOING":
        fail(f"BOARD.md:{t['line_no']} ticket {tid} is [/] in-progress but "
             f"sits under {t['section']} -- in-progress work belongs only "
             f"under ## DOING (RFC § 1.2)")
    if t["checkbox"] in (" ", "") and t["section"] in ("## DONE", "## DOING"):
        fail(f"BOARD.md:{t['line_no']} ticket {tid} has an open [ ] checkbox "
             f"under {t['section']} -- open boxes belong under ## TODO or "
             f"## BLOCKED (RFC § 1.2)")

# RFC § 1.11: at most one ticket in ## DOING per agent. Shipped as prose in
# v7.86.0 with nothing enforcing it until v7.90.0 -- which is exactly the
# ticket-hopping this invariant exists to stop (claim T-12, drift, claim
# T-27, drift), and the resulting half-owned tickets are unreadable after the
# fact. Cheap to check, so it is checked.
# phases/markhunt.md: every finding is recorded with its evidence cited
# inline -- `| blocker: unvetted audit -- <file:line or command output>`.
# "No cite, no ticket" is the rule that stops MARKHUNT from becoming a
# generator of confident-sounding vibes; unenforced until v7.91.0.
for tid, t in tickets.items():
    if "[MARKHUNT]" not in t.get("raw", ""):
        continue
    blocker = t["fields"].get("blocker", "")
    tail = blocker.split("unvetted audit", 1)[-1].lstrip(" -–—")  # noqa: RUF001 -- en dash deliberate; markdown uses both
    if len(tail.strip()) < 10:
        fail(f"BOARD.md:{t['line_no']} {tid} is a [MARKHUNT] finding whose "
             f"| blocker: cites no evidence -- phases/markhunt.md requires a "
             f"real file:line or command output per finding ('no cite, no "
             f"ticket'), not a bare 'unvetted audit'")

doing = [tid for tid, t in tickets.items() if t["section"] == "## DOING"]
if len(doing) > 1:
    fail(f"BOARD.md has {len(doing)} tickets in ## DOING ({', '.join(sorted(doing))}) "
         f"-- RFC § 1.11 allows at most one per agent. Finish, block, or demote "
         f"one to ## TODO with a LOG line before claiming another")
else:
    ok(f"BOARD.md at most one ## DOING ticket ({len(doing)} claimed)")

# ----------------------------------------------------------------------- LOG

# Segmented, append-only (RFC § 1.2): sealed older segments live in
# .saipen/logs/LOG-NNN.md, the active tail in .saipen/LOG.md. Checks run over
# the whole sequence in NNN order (segments first, active last) so E-### stays
# globally monotonic and [parent: E-###] resolves across segment boundaries.
log_seg_dir = Path(".saipen/logs")
log_segments = sorted(log_seg_dir.glob("LOG-*.md")) if log_seg_dir.is_dir() else []
active_log = Path(".saipen/LOG.md")
log_files = [p for p in ([*log_segments, active_log]) if p.is_file()]

# A gate that cannot fail is not a gate (phases/verify.md). Until v7.75.0 this
# whole block hung off `if log_files:` -- so a `.saipen/` with NO `LOG.md` at
# all skipped every LOG check and the run printed "Agent is conformant". That
# is the "suite that collected 0 tests" case exactly: the instrument was never
# connected. `STATE.md` and `BOARD.md` absence both FAIL above; `LOG.md` is
# equally required by RFC § 1.2 and is what § 1.5 Recovery rebuilds from, so
# its absence is if anything worse. An EMPTY LOG.md is fine and normal -- a
# fresh `INIT` writes exactly that (`phases/init.md`) -- absent is not.
if not active_log.is_file():
    fail("LOG.md missing -- RFC § 1.2 requires it, and § 1.5 Recovery has "
         "nothing to rebuild from without it (an empty LOG.md is legal, as "
         "phases/init.md writes on a fresh project; an absent one is not)")

if log_files:
    # Date prefix optional to allow pre-STYLE.md history; new entries carry one.
    # [agent: <id>] is a MAY field for writer identity (RFC § 1.2, v7.27.0).
    LOG_RE = re.compile(
        r"^- (?:\d{2}[./]\d{2}[./]\d{2} \d{2}:\d{2} )?"
        r"\[E-(\d+)\]"
        r"(?: \[parent: E-(\d+)\])?"
        r"(?: \[(T-[^\]]*)\])?"
        r"(?: \[agent: [^\]]+\])?"
        r" ([A-Z]+): (.*)$")
    seen_ids = {}
    prev_id = 0
    log_ok = True
    timestamp_events = []
    for lf in log_files:
        for line_no, line in enumerate(lf.read_text(encoding="utf-8-sig").splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            loc = f"{lf.as_posix()}:{line_no}"
            if "\ufffd" in line:
                fail(f"{loc} contains U+FFFD replacement character -- repair "
                     f"the corrupted text explicitly and LOG the repair")
                log_ok = False
            m = LOG_RE.match(line)
            if not m:
                fail(f"{loc} violates the Event Graph skeleton "
                     f"(RFC § 1.2): {line[:100]!r}")
                log_ok = False
                continue
            eid, parent, ticket, taxonomy, content = m.groups()
            eid = int(eid)
            ts = re.match(r"^- (\d{2})\.(\d{2})\.(\d{2}) (\d{2}):(\d{2}) ", line)
            if ts:
                try:
                    timestamp_events.append((
                        datetime.datetime(
                            2000 + int(ts.group(3)), int(ts.group(2)),
                            int(ts.group(1)), int(ts.group(4)), int(ts.group(5)),
                            tzinfo=datetime.timezone.utc),
                        eid, loc))
                except ValueError:
                    fail(f"{loc} has unparseable LOG timestamp")
                    log_ok = False
            if eid in seen_ids:
                fail(f"{loc} E-{eid:03d} reused (first at "
                     f"{seen_ids[eid]}) -- Event IDs MUST be unique (RFC § 1.2)")
                log_ok = False
            elif eid < prev_id:
                fail(f"{loc} E-{eid:03d} after E-{prev_id:03d} -- IDs MUST "
                     f"increase monotonically across segments (RFC § 1.2)")
                log_ok = False
            seen_ids[eid] = loc
            prev_id = max(prev_id, eid)
            if parent is not None and int(parent) not in seen_ids:
                fail(f"{loc} parent E-{int(parent):03d} doesn't exist "
                     f"earlier in the sequence -- dangling parent breaks the graph "
                     f"Recovery depends on (RFC § 1.2)")
                log_ok = False
            # History is append-only and immutable -- style drift in old lines
            # can't be fixed without rewriting history, so it warns, not fails.
            if taxonomy not in ("RUN", "DEC", "H"):
                warn("log-taxonomy", f"{loc} taxonomy {taxonomy!r} isn't "
                     f"RUN/DEC/H -- non-conformant for new entries (RFC § 1.2)")
            # T-none is a legal explicit no-ticket marker (RFC § 1.2, v7.24.0).
            if ticket is not None and ticket != "T-none" \
                    and not re.fullmatch(r"T-\d+", ticket):
                warn("log-ticket-ref", f"{loc} ticket ref [{ticket}] "
                     f"isn't numeric T-### or the literal T-none (RFC § 1.2)")
    if log_ok:
        ok(f"LOG.md format valid (skeleton, E-### unique + monotonic, parents "
           f"resolve; {len(log_files)} segment(s))")

    # RFC § 2.4 requires every goal counter bump to leave `DEC: goal_waves N->M`
    # (or goal_tickets), because § 1.5 Recovery rebuilds the counters by
    # COUNTING those lines. v7.87.0 fixed the three phase docs that bump a
    # counter without naming the line; nothing verified the result until
    # v7.90.0. A non-zero counter with no matching line anywhere means the
    # crash-recovery path has nothing to count -- the valve silently loses its
    # budget on exactly the long unattended runs it protects. WARN, not FAIL:
    # states predating v7.87.0 legitimately carry counters with no lines, and
    # a sealed segment may hold the lines for a very old run.
    if state.get("goal_mode") is True:
        all_log = "\n".join(p.read_text(encoding="utf-8-sig") for p in log_files)
        for counter in ("goal_waves", "goal_tickets"):
            if isinstance(state.get(counter), int) and state[counter] > 0 \
                    and f"DEC: {counter}" not in all_log:
                warn("goal-counter-untraced",
                     f"STATE.md {counter} is {state[counter]} but no "
                     f"'DEC: {counter} N->M' line exists in any LOG segment -- "
                     f"§ 1.5 Recovery rebuilds this counter by counting those "
                     f"lines, so a crash losing STATE.md loses the safety-valve "
                     f"budget with it (RFC § 2.4)")

    documented_inversions = any(
        "observed historical timestamp inversions" in
        p.read_text(encoding="utf-8-sig", errors="replace")
        for p in log_files)
    for prev, current in zip(timestamp_events, timestamp_events[1:]):
        prev_dt, prev_eid, _ = prev
        cur_dt, cur_eid, cur_loc = current
        if cur_dt < prev_dt and (prev_dt - cur_dt).total_seconds() > 300:
            if not documented_inversions:
                warn("log-timestamp-inversion",
                     f"{cur_loc} timestamp moves backwards by "
                     f"{(prev_dt - cur_dt).total_seconds() / 60:.0f}m "
                     f"from E-{prev_eid:03d} to E-{cur_eid:03d}; historical "
                     f"inversions must be documented with a DEC line (RFC § 1.2)")

    now = datetime.datetime.now(datetime.timezone.utc)
    for log_dt, eid, loc in timestamp_events:
        if (log_dt - now).total_seconds() > 10800:
            fail(f"{loc} timestamp for E-{eid:03d} is more than 3h in the "
                 f"future from current UTC -- LOG timestamps MUST be real UTC "
                 f"time (RFC § 1.2)")

    # RFC § 1.2 segmentation soft cap (~300 lines / ~64 KB). Without a signal
    # here the rule is purely aspirational -- nothing ever tells an agent the
    # active tail has outgrown what § 1.1's "read the tail" can cheaply load.
    # WARN, never FAIL: an oversized log is a hygiene debt, not corruption,
    # and sealing is a CLEAN-time action, not something to force mid-ticket.
    if active_log.is_file():
        active_lines = len(active_log.read_text(encoding="utf-8-sig").splitlines())
        active_kb = active_log.stat().st_size / 1024
        if active_lines > 300 or active_kb > 64:
            warn("log-soft-cap",
                 f"{active_log.as_posix()} is {active_lines} lines / "
                 f"{active_kb:.0f} KB, past the ~300 line / ~64 KB soft cap -- "
                 f"seal it into .saipen/logs/LOG-<NNN>.md at the next "
                 f"checkpoint (RFC § 1.2, phases/clean.md)")

    # A third timestamp check lived here (feae149, CONFORMANCE 42) and was
    # removed in v7.93.0 as dead and wrong on both counts.
    #
    # Dead: its regex was `^(\d{2})\.` against lines that begin `- DD.MM.YY`,
    # so `^` never matched and `last_ts` was always None. It had never fired
    # once. That is also why nothing noticed the second problem:
    #
    # Wrong: it compared abs(now - last_entry) and WARNed past 3h, which
    # collapses two opposite faults into one verdict. A timestamp in the
    # FUTURE is corruption -- every later event inherits a broken clock -- and
    # RFC § 1.2 rates it FAIL; that case is already handled correctly above,
    # per-event, signed, at FAIL severity. A timestamp in the PAST is just a
    # project nobody touched today, which RFC § 1.2 says nothing against and
    # `saipen status` reports as staleness rather than corruption. Had the
    # regex worked, every repo idle for an afternoon would have warned.
    #
    # What RFC § 1.2 actually asks for is exactly the two checks that remain:
    # signed >3h future = FAIL (above), and >5min backwards between
    # consecutive events = WARN unless a DEC documents it (above).

# ------------------------------------------------------------ SUBSAIPEN OUTBOX

# `kitchen/OUTBOX.md` is the ONLY channel out of a subSaipen
# (extensions/subs/PROTOCOL.md § 1), and until v7.91.0 nothing validated it --
# a malformed entry became a bad collect in silence. Two contracts are
# mechanically checkable, so they are checked; the third (is the finding TRUE)
# is not, and no amount of tooling will make it so.
outbox_ok = True
outbox_seen = 0
for ob in sorted(Path(".").glob(".saipen/extensions/subs/*/kitchen/OUTBOX.md")):
    text = ob.read_text(encoding="utf-8-sig")
    # Entries are `## <ID>: description` followed by bold-field lines (§ 2).
    entries = re.split(r"^## (?=[A-Z]+-\d+)", text, flags=re.MULTILINE)[1:]
    for e in entries:
        outbox_seen += 1
        eid = e.split(":", 1)[0].strip()
        loc = f"{ob.as_posix()} [{eid}]"
        status = re.search(r"\*\*status:\*\*\s*([a-z]+)", e)
        status = status.group(1) if status else None
        if status is None:
            fail(f"{loc} has no **status:** -- the main agent cannot tell "
                 f"whether this is collectable (PROTOCOL.md § 2)")
            outbox_ok = False
            continue
        if status not in OUTBOX_STATUSES:
            fail(f"{loc} status {status!r} is not one of "
                 f"ready/draft/blocked/reviewed/stale (PROTOCOL.md § 2)")
            outbox_ok = False
        if status == "ready":
            for field in ("summary", "critical"):
                if not re.search(rf"\*\*{field}:\*\*", e):
                    fail(f"{loc} is status: ready but has no **{field}:** -- "
                         f"collect reads that field to decide what to do with "
                         f"it (PROTOCOL.md § 2)")
                    outbox_ok = False
            # Fixer-type entry: carries a patch, so § 9 requires provenance.
            if re.search(r"\*\*patch:\*\*", e):
                for field in ("base_head", "verified"):
                    if not re.search(rf"\*\*{field}:\*\*", e):
                        fail(f"{loc} hands over a patch as ready but has no "
                             f"**{field}:** -- a patch with no {field} is a "
                             f"diff nobody can re-check before applying "
                             f"(PROTOCOL.md § 9)")
                        outbox_ok = False
if outbox_seen and outbox_ok:
    ok(f"subSaipen OUTBOX entries well-formed ({outbox_seen} checked)")

# ----------------------------------------------------------------- KNOWLEDGE

knowledge = Path(".saipen/KNOWLEDGE")
if knowledge.is_dir():
    leak_re = re.compile(r"^-\s+[0-9]{2,4}[-/.][0-9]{2}[-/.][0-9]{2}.*(RUN|DEC|H):")
    leaked = False
    for f in knowledge.rglob("*"):
        if f.is_file():
            for line_no, line in enumerate(
                    f.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
                if leak_re.match(line):
                    fail(f"KNOWLEDGE/ leak: {f.relative_to(knowledge)}:{line_no} "
                         f"contains event journal syntax -- histories live in LOG.md only")
                    leaked = True
    if not leaked:
        ok("KNOWLEDGE/ clean")

# ------------------------------------------------- home-repo-only self-check

# Only applies in the saipen repo's own clone root. Fingerprint deliberately
# does NOT require saipen/RFC.md itself to exist (see the loud FAIL just
# below for why) -- but it MUST stay specific enough that an ordinary
# consuming project never trips it. `saipen/` + VERSION + README.md alone was
# not: a real false positive, caught by testing this exact case, is any
# project that happens to keep a `saipen/` folder next to a VERSION file and
# a README -- extremely ordinary, and (via tools/install_hook.py's pre-commit
# wiring) it would have hard-FAILED and blocked that project's commits with a
# message about a stray clone that never happened. `bootstrap/` is the
# discriminator: home-only, at the root, and untouched by the nested-clone
# corruption this check exists to catch (that incident replaced `saipen/`
# alone).
if (Path("saipen").is_dir() and Path("bootstrap").is_dir()
        and Path("VERSION").is_file() and Path("README.md").is_file()):
    if not Path("saipen/RFC.md").is_file():
        fail("saipen/RFC.md missing even though this looks like the SAIPEN "
             "home repo (saipen/ + VERSION + README.md all present) -- a "
             "real incident: a stray `git clone` of this same repo landing "
             "at saipen/ instead of its own directory replaced this whole "
             "subtree with a nested repo (its real content survived one "
             "level deeper, at saipen/saipen/), and every check below this "
             "line silently skipped instead of failing loud. Check for a "
             "foreign saipen/.git before assuming plain file corruption.")
    else:
        repo_version = Path("VERSION").read_text(encoding="utf-8-sig").strip()
        if f"**v{repo_version}**" not in Path("README.md").read_text(encoding="utf-8-sig"):
            fail(f"README.md badge doesn't match VERSION ({repo_version}) -- "
                 f"this has drifted before, update the badge")
        else:
            ok("README.md badge matches VERSION")

        conformance_path = Path("saipen/CONFORMANCE.md")
        if conformance_path.is_file():
            row_ids = []
            for line_no, line in enumerate(
                    conformance_path.read_text(encoding="utf-8-sig").splitlines(), 1):
                m = re.match(r"^\|\s*(\d+)\s*\|", line)
                if m:
                    row_ids.append((int(m.group(1)), line_no))
            duplicate_ids = sorted({rid for rid, _ in row_ids
                                    if sum(1 for other, _ in row_ids
                                           if other == rid) > 1})
            for rid in duplicate_ids:
                lines = [str(line_no) for other, line_no in row_ids
                         if other == rid]
                fail(f"CONFORMANCE.md duplicate row ID {rid} at lines "
                     f"{', '.join(lines)} -- row references must be unique")
            for (prev_rid, prev_line), (rid, line_no) in zip(row_ids, row_ids[1:]):
                if rid <= prev_rid:
                    fail(f"CONFORMANCE.md row IDs not monotonically increasing: "
                         f"{prev_rid} at line {prev_line}, then {rid} at line "
                         f"{line_no}")
            if row_ids and not duplicate_ids:
                ok(f"CONFORMANCE.md row IDs unique + monotonic ({len(row_ids)} rows)")

        text_targets = [
            Path("saipen/RFC.md"),
            Path("saipen/BOOT.md"),
            Path("saipen/CONFORMANCE.md"),
            *sorted(Path("saipen/phases").glob("*.md")),
        ]
        split_terms = [
            (re.compile(r"\bM\s+US\s+T\b", re.IGNORECASE), "MUST"),
            (re.compile(r"\bSH\s+OULD\b", re.IGNORECASE), "SHOULD"),
            (re.compile(r"\bM\s+AY\b", re.IGNORECASE), "MAY"),
            (re.compile(r"\ba\s+uthorization\b"), "authorization"),
            (re.compile(r"\bs\s+pa\s+wned\b"), "spawned"),
            (re.compile(r"\bdeli\s+berately\b"), "deliberately"),
            (re.compile(r"\bcomp\s+arison\b"), "comparison"),
        ]
        text_ok = True
        for doc in text_targets:
            if not doc.is_file():
                continue
            text = doc.read_text(encoding="utf-8-sig", errors="replace")
            if "\ufffd" in text:
                fail(f"{doc.as_posix()} contains U+FFFD replacement character")
                text_ok = False
            # Mojibake that is NOT U+FFFD. A section sign decoded as
            # cp1251 and re-encoded round-trips as perfectly valid UTF-8,
            # so the replacement-character check above can never see it.
            # Nine sat in this file's own FAIL messages until v7.99.0 --
            # found by a linter, not by this check.
            if "\u0412\u00a7" in text:
                fail(f"{doc.as_posix()} carries a cp1251-mangled section "
                     f"sign -- valid UTF-8, so the U+FFFD check above "
                     f"cannot catch it")
                text_ok = False
            if text.count("```") % 2:
                fail(f"{doc.as_posix()} has an odd number of fenced code markers")
                text_ok = False
            for pattern, expected in split_terms:
                if pattern.search(text):
                    fail(f"{doc.as_posix()} contains split text artifact for "
                         f"{expected!r}")
                    text_ok = False
        if text_ok:
            ok("core docs text lint clean (no U+FFFD/split keywords/fence drift)")

        # Distribution integrity -- the v7.22.3/v7.25.0 bug class, machine-checked.
        # Five separate times this repo promised a file in one place and never
        # wired its delivery in another; each was found by archaeology. These
        # three checks make the whole class a validator FAIL instead.

        # A. RFC's phase enum <-> phases/ docs, both directions.
        rfc_text = Path("saipen/RFC.md").read_text(encoding="utf-8-sig")
        enum_line = next((rl for rl in rfc_text.splitlines()
                          if rl.startswith("**Phase enum**")), None)
        if enum_line is None:
            fail("RFC.md: '**Phase enum**' line not found -- the phase-docs "
                 "integrity check anchors on it")
        else:
            phase_names = [t for t in re.findall(r"`([A-Z-]+)`", enum_line)
                           if re.fullmatch(r"[A-Z]+", t)]
            enum_ok = True
            for name in phase_names:
                if not Path(f"saipen/phases/{name.lower()}.md").is_file():
                    fail(f"RFC.md phase enum names {name} but "
                         f"saipen/phases/{name.lower()}.md doesn't exist -- "
                         f"the state machine has a door drawn on the map with "
                         f"no room behind it")
                    enum_ok = False
            for doc in Path("saipen/phases").glob("*.md"):
                if doc.stem.upper() not in phase_names:
                    warn("orphan-phase-doc", f"saipen/phases/{doc.name} has no "
                         f"entry in RFC.md's phase enum -- dead doc or missing "
                         f"enum value?")
            if enum_ok:
                ok(f"phase enum <-> phases/ docs in sync ({len(phase_names)} phases)")

        # B. Every runtime file the protocol references must exist in the home.
        manifest = [
            "saipen/BOOT.md", "saipen/SKILL.md", "saipen/UI.md", "saipen/STYLE.md",
            "saipen/CONFORMANCE.md",
            "tools/validate.py", "tools/install_hook.py", "tools/uninstall_hook.py",
            "tools/run_scenarios.py",
            "tests/validate.sh", "tests/validate.ps1",
            "extensions/schemas/state.schema.json",
            "extensions/templates/STATE.md", "extensions/templates/BOARD.md",
            "extensions/templates/LOG.md",
        ]
        manifest_missing = [f for f in manifest if not Path(f).is_file()]
        for f in manifest_missing:
            fail(f"runtime manifest file missing from the home: {f}")
        if not manifest_missing:
            ok(f"runtime manifest complete ({len(manifest)} files)")

        # C. Both injector scripts must actually distribute every runtime dir
        # AND every always-loaded root doc. The per-file names matter as much
        # as the dirs: CONFORMANCE.md was referenced by BOOT.md (loaded on
        # every cold start) and phases/validate.md while no injector copied
        # it, so every injected platform had a dangling pointer -- the same
        # v7.22.3/v7.25.0 class this check exists to catch, just at file
        # rather than directory granularity.
        dist_tokens = ["phases", "tools", "extensions/schemas",
                       "extensions/templates", "extensions/subs", "tests",
                       "BOOT.md", "SKILL.md", "RFC.md", "STYLE.md", "UI.md",
                       "CONFORMANCE.md"]
        wiring_ok = True
        for script in ("bootstrap/inject.ps1", "bootstrap/inject.sh"):
            if not Path(script).is_file():
                fail(f"{script} missing")
                wiring_ok = False
                continue
            normalized = Path(script).read_text(encoding="utf-8-sig").replace("\\", "/")
            for token in dist_tokens:
                if token not in normalized:
                    fail(f"{script} never references {token} -- Copy-Skill "
                         f"wiring broken, skill copies won't receive it "
                         f"(the exact v7.22.3/v7.25.0 bug class)")
                    wiring_ok = False
        if wiring_ok:
            ok("injector distributes every runtime dir + root doc "
               "(phases/tools/tests/schemas/templates/subs, BOOT/SKILL/RFC/"
               "STYLE/UI/CONFORMANCE, both scripts)")

# --------------------------------------------------- adapters cross-reference

# Every adapter file references `saipen/` paths that must exist. A stale
# reference misleads users on that platform about how to install or use SAIPEN.
# Unlike the injector-distribution check above (which ensures every file IS
# shipped), this ensures every claimed path actually EXISTS in the home repo.
adapter_dir = Path("extensions/adapters")
if adapter_dir.is_dir():
    adapter_ok = True
    for doc in sorted(adapter_dir.glob("*.md")):
        text = doc.read_text(encoding="utf-8-sig")
        for m in re.finditer(r"`([^`]+)`", text):
            ref = m.group(1)
            if "saipen/" not in ref or ".saipen/" in ref:
                continue
            # Strip path prefixes like `<clone>/` or `~/.claude/skills/saipen/`
            clean = ref.split("saipen/", 1)[1] if "saipen/" in ref else ref
            # If it's a file reference (has extension), check it exists
            if "." in clean and clean.endswith(".md"):
                target = Path("saipen") / clean
                if not target.is_file() and not target.with_suffix("").is_dir():
                    fail(f"extensions/adapters/{doc.name} references "
                         f"{ref!r} ({target.as_posix()}) which does not exist "
                         f"-- stale cross-reference (v7.22.3 bug class)")
                    adapter_ok = False
    if adapter_ok:
        ok("adapter cross-references valid (checking saipen/ paths in all "
           f"{len(list(adapter_dir.glob('*.md')))} adapters)")

# -------------------------------------------------------- translation drift

# Check version-badge consistency across all locale README_*.md files.
# Only runs when `.saipen/saitranslate/kitchen/` exists.
# IS_SAIPEN_HOME, not just kitchen.is_dir(): VERSION lives in the SAIPEN home
# and never in a consuming project. Gated on the directory alone, this read
# raised an unhandled FileNotFoundError in any project that had ever run
# `saipen translate` -- a crash with a traceback instead of a verdict, in the
# one layout every actual user of SAIPEN runs. Found by installing into a
# sandbox HOME and running the copy, which nothing had ever done.
kitchen = Path(".saipen/saitranslate/kitchen")
if IS_SAIPEN_HOME and kitchen.is_dir():
    repo_version = Path("VERSION").read_text(encoding="utf-8-sig").strip()
    stale = []
    for locale_dir in sorted(kitchen.iterdir()):
        if not locale_dir.is_dir():
            continue
        readme = locale_dir / f"README_{locale_dir.name.upper()}.md"
        if not readme.is_file():
            # not every locale has a README -- skip silently
            continue
        content = readme.read_text(encoding="utf-8-sig")
        if f"**v{repo_version}**" not in content:
            stale.append(readme.name)
    if stale:
        fail(f"translation README badge drift: {len(stale)} locale(s) still"
             f" show an old version -- {', '.join(sorted(stale))}")
    else:
        ok(f"all {len([d for d in kitchen.iterdir() if d.is_dir()])} locale"
           f" README badges match VERSION ({repo_version})")

# ------------------------------------------------ subSaipen liveness signals

# Two things about a subSaipen that were invisible until v7.99.0, both found by
# reading the four live instances by hand rather than by any check:
#
#   1. A sub that was spawned and never ran looks identical to a healthy one in
#      MANIFEST.md. saipython sat with 5 open tickets, 0 done and an empty
#      OUTBOX for a full day; nothing said so.
#   2. `ready` OUTBOX entries are the sub's whole output, and they are only
#      seen when somebody remembers to run collect. saitranslate's SAIT-002 sat
#      `ready` after its work had already been collected and its main-board
#      ticket closed -- harmless here (PROTOCOL § 4 orders the writes so the
#      worst case is a duplicate ticket, never a lost finding), but nothing
#      surfaced it either way.
#
# Both are WARN. Neither is a broken file; both are work or rot a human should
# see, which is what a warning is for.
_subs_root = Path(".saipen/extensions/subs")
if _subs_root.is_dir():
    _idle, _ready_total = [], 0
    for _sub in sorted(_subs_root.iterdir()):
        if not _sub.is_dir() or _sub.name == "TEMPLATE":
            continue
        _board = _sub / "BOARD.md"
        _outbox = _sub / "kitchen" / "OUTBOX.md"
        _obtext = _outbox.read_text(encoding="utf-8-sig") if _outbox.is_file() else ""
        _ready = _obtext.count("**status:** ready")
        _ready_total += _ready
        if _board.is_file():
            _btext = _board.read_text(encoding="utf-8-sig")
            _open = len(re.findall(r"^- \[ \]", _btext, re.MULTILINE))
            _done = len(re.findall(r"^- \[x\]", _btext, re.MULTILINE))
            if _open and not _done and not _obtext.strip().count("## "):
                _idle.append(f"{_sub.name} ({_open} open, 0 done, empty OUTBOX)")
    if _idle:
        warn("subsaipen-never-ran",
             "subSaipen spawned but never run: " + "; ".join(_idle) +
             " -- indistinguishable from a working one in MANIFEST.md until "
             "someone opens its board")
    if _ready_total:
        warn("subsaipen-uncollected",
             f"{_ready_total} subSaipen OUTBOX entr(y/ies) sit at `status: "
             f"ready` -- that is a finding waiting on `saipen sub collect`, "
             f"visible only when someone runs it (extensions/subs/PROTOCOL.md § 4)")
    if not _idle and not _ready_total:
        ok("subSaipen liveness clean (none idle, no uncollected findings)")

# --------------------------------------------- claims that git can adjudicate

# A STATE that says "pushed" while commits sit local-only is exactly what
# v7.98.0 shipped: next_action read "shipped, committed, pushed. CI green"
# while three commits -- two of them changes to CI itself -- had never left the
# machine. Nothing could contradict it, because nothing looked. git can.
#
# Only claims about PUSHING are checked. "committed" is already visible in the
# log, and "CI green" belongs to a service this validator does not call.

def _unpushed_count():
    """Commits on HEAD absent from the tracking remote, or None if unknowable."""
    try:
        r = subprocess.run(["git", "rev-list", "--count", "@{u}..HEAD"],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None          # no git on this host (RFC § 1.3 no-publish)
    if r.returncode != 0:
        return None          # no upstream configured, or not a repo
    try:
        return int(r.stdout.strip())
    except ValueError:
        return None


_claim = (state.get("next_action") or "")
if "push" in _claim.lower():
    _ahead = _unpushed_count()
    if _ahead is None:
        warn("push-claim-unverifiable",
             "STATE.md next_action claims something about pushing, but git "
             "cannot confirm it here (no repo, no upstream, or no git). The "
             "claim stands unverified rather than verified")
    elif _ahead > 0:
        fail(f"STATE.md next_action claims a push ({_claim[:70]!r}) but "
             f"{_ahead} commit(s) are not on the upstream branch. A claim the "
             f"repository itself contradicts is worse than no claim: the next "
             f"agent reads it as done and never looks (RFC § 1.11)")
    else:
        ok("STATE.md push claim matches the repository")

# ------------------------------------------------- cross-document drift (§ 1.1)

# The five-copies bug class, mechanized. RFC § 1.2's required field set lived
# in five documents at once and all five disagreed (v7.92.0); the from-any-phase
# set lived in three and all three disagreed (v7.93.0). Each was found by a
# human reading two files side by side, which is not a strategy -- it is luck
# with extra steps. RFC.md is normative (§ 1.1), so every set below is PARSED
# OUT OF RFC.md and compared against every other copy of it in the tree.
#
# A missing anchor is a FAIL, never a skip. If someone rewords RFC past these
# patterns, this checker must be updated deliberately -- a drift detector that
# silently stops detecting is worse than none, because it still reports PASS.

def _ticks(text):
    """Backticked tokens, in order, deduped."""
    seen, out = set(), []
    for tok in re.findall(r"`([^`]+)`", text):
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def _rfc_sentence(label, pattern, text):
    m = re.search(pattern, text)
    if not m:
        fail(f"cross-doc check '{label}' cannot find its anchor in RFC.md -- "
             f"the wording moved. Update tools/validate.py deliberately; a "
             f"drift check that silently stops checking still prints PASS")
        return None
    return m.group(1)


def _compare(label, rfc_set, other_set, other_name):
    missing = rfc_set - other_set
    extra = other_set - rfc_set
    if missing or extra:
        bits = []
        if missing:
            bits.append(f"in RFC.md but not {other_name}: {sorted(missing)}")
        if extra:
            bits.append(f"in {other_name} but not RFC.md: {sorted(extra)}")
        fail(f"cross-doc drift [{label}] -- {'; '.join(bits)}. RFC.md is "
             f"normative (§ 1.1); bring {other_name} to it, or change RFC "
             f"deliberately and update both")
        return False
    return True

# Two layouts, both legitimate. In the SAIPEN home the protocol lives in
# saipen/ next to tools/; the injector flattens it, so an installed copy has
# RFC.md as tools/'s sibling. Assuming only the first made every cross-doc
# check FAIL with "SAIPEN home clone incomplete" on every installed copy --
# a validator that only works in its own development repo.
_tools_parent = Path(__file__).resolve().parent.parent
rfc_path = _tools_parent / "saipen" / "RFC.md"
if not rfc_path.is_file():
    rfc_path = _tools_parent / "RFC.md"
boot_path = rfc_path.parent / "BOOT.md"
conf_path = rfc_path.parent / "CONFORMANCE.md"
if not rfc_path.is_file():
    fail(f"RFC.md not found at {rfc_path} -- SAIPEN home clone incomplete")
else:
    rfc = rfc_path.read_text(encoding="utf-8-sig")
    drift_ok = True

    # 1. Required STATE field set: RFC § 1.2 vs schema properties.
    s = _rfc_sentence("required-set",
                      r"\*\*STATE\.md\*\*: MUST contain frontmatter: (.+?)\.\s",
                      rfc)
    if s is None:
        drift_ok = False
    else:
        rfc_required = set(_ticks(s))
        # The schema legitimately defines MORE properties than RFC requires
        # (optional fields), so this is a subset test, not equality: every
        # field RFC calls required must at least exist in the schema.
        unknown = rfc_required - set(schema.get("properties", {}))
        if unknown:
            fail(f"cross-doc drift [required-set] -- RFC § 1.2 requires "
                 f"{sorted(unknown)}, which state.schema.json does not define "
                 f"as properties at all, so nothing validates them")
            drift_ok = False

    # 2. Phase enum: RFC § 1.6 vs schema enum vs the transition table here.
    s = _rfc_sentence("phase-enum", r"\*\*Phase enum\*\*: (.+?)\. These", rfc)
    if s is None:
        drift_ok = False
    else:
        rfc_phases = set(_ticks(s))
        schema_phases = set(schema["properties"]["phase"]["enum"])
        drift_ok &= _compare("phase-enum", rfc_phases, schema_phases,
                             "state.schema.json phase enum")
        drift_ok &= _compare("phase-enum", rfc_phases,
                             set(VALID_TRANSITIONS) | {"INIT"},
                             "validate.py VALID_TRANSITIONS")

    # 3. From-any-phase set: RFC § 1.6 vs ANY_FROM here.
    s = _rfc_sentence("any-from", r"\*\*From-any-phase set\*\*: (.+?)\.\n", rfc)
    if s is None:
        drift_ok = False
    else:
        drift_ok &= _compare("any-from", set(_ticks(s)), ANY_FROM,
                             "validate.py ANY_FROM")

    # 4. read-only banned phases: RFC § 1.3 vs the tuple here.
    s = _rfc_sentence("read-only-bans",
                      r"\*\*Read-only banned phases\*\*: (.+?)\. The agent", rfc)
    if s is None:
        drift_ok = False
    else:
        drift_ok &= _compare("read-only-bans", set(_ticks(s)),
                             set(READ_ONLY_BANNED_PHASES),
                             "validate.py READ_ONLY_BANNED_PHASES")

    # 5. next_action prefixes: RFC § 1.2 vs the tuple here.
    s = _rfc_sentence("next-action-prefixes",
                      r"`next_action` MUST begin with one of (.+?)\.\s\*\*", rfc)
    if s is None:
        drift_ok = False
    else:
        rfc_prefixes = {p.strip() for p in _ticks(s)}
        drift_ok &= _compare("next-action-prefixes", rfc_prefixes,
                             {p.strip() for p in executable_prefixes},
                             "validate.py executable_prefixes")

    # 6. WAIT categories: RFC § 1.2 vs the tuple here.
    s = _rfc_sentence("wait-categories",
                      r"is one of exactly seven words: (.+?)\.\s", rfc)
    if s is None:
        drift_ok = False
    else:
        drift_ok &= _compare("wait-categories", set(_ticks(s)),
                             set(WAIT_CATEGORIES), "validate.py WAIT_CATEGORIES")

    # 7. BOOT.md and CONFORMANCE.md MUST NOT re-list the required field set --
    #    that is exactly how v7.92.0's five disagreeing copies happened. They
    #    are allowed to name it and point at § 1.2, never to enumerate it.
    for doc_path, doc_name in ((boot_path, "BOOT.md"), (conf_path, "CONFORMANCE.md")):
        if not doc_path.is_file():
            continue
        doc = doc_path.read_text(encoding="utf-8-sig")
        for m in re.finditer(r"[^.\n]*`saipen_version`[^.\n]*", doc):
            frag = m.group()
            named = {t for t in _ticks(frag)}
            if len({"phase", "task", "next_action", "blocker", "agent",
                    "saipen_version", "mode", "updated"} & named) >= 4:
                fail(f"cross-doc drift [required-set] -- {doc_name} enumerates "
                     f"the STATE required fields again ({sorted(named)[:5]}...). "
                     f"RFC § 1.2 is the only place that list may exist; refer "
                     f"to it instead (this is the v7.92.0 five-copies defect)")
                drift_ok = False

    # 8. Every `WAIT:` a shipped doc tells an agent to WRITE must carry a
    #    category from § 1.2's closed set. v7.93.0 made the category mandatory
    #    and enforced it on STATE.md, but left three phase docs (blocked.md,
    #    build.md, clean.md) prescribing category-less WAITs -- so an agent
    #    following its own phase doc verbatim produced a state this validator
    #    then FAILed. Rules propagate to the docs that emit them, or they are
    #    only enforced against agents that never read the docs.
    doc_roots = [rfc_path.parent / "phases", _tools_parent / "extensions"]
    prescribed = re.compile('next_action:\\s*`?WAIT:\\s*([^`\\n<]{0,40})')
    bad_waits = []
    for root in doc_roots:
        if not root.is_dir():
            continue
        for doc in sorted(root.rglob("*.md")):
            for m in prescribed.finditer(doc.read_text(encoding="utf-8-sig")):
                body = m.group(1).strip().lower()
                if not any(body.startswith(c) for c in WAIT_CATEGORIES):
                    bad_waits.append(f"{doc.as_posix()}: WAIT: {m.group(1).strip()[:40]!r}")
    for b in bad_waits:
        fail(f"cross-doc drift [wait-categories] -- shipped doc prescribes a "
             f"`WAIT:` with no § 1.2 category token: {b}")
    if bad_waits:
        drift_ok = False

    # 9. guides/ teach the same shape to a human. They are not in the injector
    #    manifest and no agent boots from them, so this is a WARN rather than a
    #    FAIL -- but it is the same drift: 33 guides went on teaching the
    #    pre-v7.93.0 `WAIT: <question>` form through two releases that changed
    #    it, because nothing looked there. Core owns en/ru/et/ded; the other
    #    locales are subSaipen translation work by standing rule, so this
    #    warns for all and blocks none.
    guides = _tools_parent / "guides"
    if guides.is_dir():
        stale_guides = []
        for doc in sorted(guides.glob("GUIDE_*.md")):
            body = doc.read_text(encoding="utf-8-sig")
            for m in re.finditer(r"`WAIT:\s*([^`]{0,40})`", body):
                arg = m.group(1).strip().lower()
                if arg.startswith("<") and "--" not in arg:
                    stale_guides.append(doc.name)
                    break
        if stale_guides:
            warn("guide-wait-shape",
                 f"{len(stale_guides)} guide(s) still teach `WAIT: <question>` "
                 f"without \u00a7 1.2's category token: "
                 f"{', '.join(stale_guides[:6])}"
                 f"{' ...' if len(stale_guides) > 6 else ''}")

    # 9b. board.schema.json / log.schema.json are described as "descriptive
    #     reference, unread by any agent" -- which is exactly why nothing ever
    #     compared them to the RFC. Both had drifted: log's schema left
    #     `event_id` out of `required` though RFC § 1.2 calls [E-###] a MUST on
    #     every line, and capped `content` at 120 characters, which declared 54
    #     of this repo's own 72 live LOG lines invalid. A schema nobody reads
    #     is not harmless; it is a lie waiting for the first tool built on it.
    _schema_dir = _tools_parent / "extensions" / "schemas"
    _log_schema = _schema_dir / "log.schema.json"
    if _log_schema.is_file():
        _ls = json.loads(_log_schema.read_text(encoding="utf-8"))["items"]
        if "event_id" not in _ls.get("required", []):
            fail("cross-doc drift [schemas] -- log.schema.json does not require "
                 "`event_id`, but RFC § 1.2 makes [E-###] a MUST on every line")
            drift_ok = False
        _cap = _ls.get("properties", {}).get("content", {}).get("maxLength")
        if _cap is not None:
            fail(f"cross-doc drift [schemas] -- log.schema.json caps `content` "
                 f"at {_cap} characters; RFC § 1.2 sets no length limit and "
                 f"STYLE.md's commentary voice routinely exceeds it")
            drift_ok = False
    _board_schema = _schema_dir / "board.schema.json"
    if _board_schema.is_file():
        _bs = json.loads(_board_schema.read_text(encoding="utf-8"))["items"]
        _missing = sorted(KNOWN_FIELDS - set(_bs.get("properties", {})))
        if _missing:
            fail(f"cross-doc drift [schemas] -- board.schema.json does not "
                 f"describe {_missing}, which RFC § 1.2 recognises as ticket "
                 f"fields and this validator already parses")
            drift_ok = False

    # 9c. OUTBOX status vocabulary, three ways: PROTOCOL.md's own table,
    #     outbox.schema.json's enum, and the tuple this file checks against.
    #     All three disagreed until v7.100.0 -- the table listed four while the
    #     document's own prose (§ 4, § 9) told agents to write a fifth, and both
    #     implementations already accepted it. The validator even cited
    #     "PROTOCOL.md § 2" in its error message while enforcing a superset of
    #     what § 2 said.
    _proto = _tools_parent / "extensions" / "subs" / "PROTOCOL.md"
    _outbox_schema = _schema_dir / "outbox.schema.json"
    if _proto.is_file() and _outbox_schema.is_file():
        _ptext = _proto.read_text(encoding="utf-8-sig")
        _table = set(re.findall(r"^\| `([a-z]+)` \|", _ptext, re.MULTILINE))
        _os = json.loads(_outbox_schema.read_text(encoding="utf-8"))
        _enum = set(_os.get("items", _os).get("properties", {})
                    .get("status", {}).get("enum", []))
        _code = set(OUTBOX_STATUSES)
        if not (_table == _enum == _code):
            fail(f"cross-doc drift [outbox-status] -- PROTOCOL.md table "
                 f"{sorted(_table)}, outbox.schema.json enum {sorted(_enum)}, "
                 f"validate.py {sorted(_code)}. The table is normative for the "
                 f"extension (RFC § 1.9); the other two must match it")
            drift_ok = False

    # 10. The portable floor (tests/validate.sh, tests/validate.ps1) is what a
    #     host without Python runs INSTEAD of this file. It is frozen against
    #     new checks -- never against corrections -- so its data must still
    #     match RFC. Until v7.96.0 it required 7 of § 1.2's 9 fields and knew
    #     none of the read-only bans added in v7.93.0/v7.94.0, so it handed out
    #     PASS on states this file FAILs. A floor more permissive than the
    #     thing it substitutes for is worse than no floor.
    #
    #     Both halves below are matched precisely, not by bare word presence:
    #     the first version of this check looked for "INIT" anywhere in the
    #     file and could therefore never fail, because the phase enum lists it
    #     a few lines above. A check that cannot go red is decoration.
    floor = [_tools_parent / "tests" / "validate.sh",
             _tools_parent / "tests" / "validate.ps1"]
    for script in floor:
        if not script.is_file():
            fail(f"portable floor missing: {script.as_posix()} (CONFORMANCE § 1)")
            drift_ok = False
            continue
        body = script.read_text(encoding="utf-8-sig")

        # required fields: each must appear as an actual `field:` probe
        missing_fields = sorted(f for f in rfc_required if (f + ":") not in body)
        if missing_fields:
            fail(f"cross-doc drift [portable-floor] -- {script.name} never "
                 f"probes {missing_fields}, which RFC § 1.2 requires; a host "
                 f"without Python would PASS a state this validator FAILs")
            drift_ok = False

        # read-only bans: parse the phases out of the script's own message
        m = re.search(r"read-only MUST NOT enter ([A-Z/]+)", body)
        if not m:
            fail(f"cross-doc drift [portable-floor] -- {script.name} has no "
                 f"recognizable read-only ban message; RFC § 1.3's ban cannot "
                 f"be compared against it")
            drift_ok = False
        else:
            floor_bans = set(m.group(1).split("/"))
            missing_bans = sorted(set(READ_ONLY_BANNED_PHASES) - floor_bans)
            if missing_bans:
                fail(f"cross-doc drift [portable-floor] -- {script.name} does "
                     f"not ban read-only from {missing_bans} (RFC § 1.3)")
                drift_ok = False

    if drift_ok and not failures:
        ok("cross-doc sets agree (required fields, phase enum, from-any-phase, "
           "read-only bans, next_action prefixes, WAIT categories; no re-listing "
           "in BOOT/CONFORMANCE)")


# ------------------------------------------------------------------- summary

warn_total = sum(len(msgs) for msgs in warnings.values())
for category, msgs in warnings.items():
    for msg in msgs[:2]:
        print(color("33", f"WARN: {msg}"))
    if len(msgs) > 2:
        print(color("33", f"WARN: ... and {len(msgs) - 2} more [{category}] "
                    f"warnings like the above"))

if STRICT:
    for msgs in warnings.values():
        failures.extend(msgs)

if failures:
    print(color("31", f"Validation FAILED: {len(failures)} problem(s)"
                + (f", {warn_total} warning(s)" if warn_total and not STRICT else "")))
    sys.exit(1)
print(color("32", "Validation complete. Agent is conformant."
            + (f" ({warn_total} warning(s))" if warn_total else "")))
