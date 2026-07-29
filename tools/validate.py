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
# RFC § 1.10's closed command list. Was a local inside Core's own next_action
# branch, so it existed only when Core's next_action happened to start with
# "saipen " -- the moment the subSaipen check reused it against a Core state
# that said WAIT, it was simply not defined. A vocabulary two checks share is
# a module constant, not a variable one of them happens to have built.
SAIPEN_COMMANDS = frozenset({
    "set", "init", "continue", "goal", "plan", "clean", "translate",
    "markhunt", "prepare", "ship", "validate", "status", "stop", "sub"})
failures = []
warnings = {}

# Longest BOM first: UTF-32LE opens with the same two bytes as UTF-16LE.
_BOMS = (
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)


def _bomless_utf16(raw):
    """Name the UTF-16 flavour of a BOM-less file, or None.

    The obvious test does not work: UTF-16LE ASCII is every other byte NUL and
    NUL is valid UTF-8, so `.decode("utf-8")` SUCCEEDS and hands back a string
    full of NULs that matches no pattern. Test the byte shape instead.
    """
    if len(raw) < 4 or b"\x00" not in raw:
        return None
    head = raw[:4096]
    head = head[:len(head) - len(head) % 2]
    half = len(head) // 2
    if not half:
        return None
    even, odd = head[0::2].count(0), head[1::2].count(0)
    if odd > half * 0.3 and even < half * 0.1:
        return "utf-16-le"
    if even > half * 0.3 and odd < half * 0.1:
        return "utf-16-be"
    return None


def encoding_of(path):
    """Name the encoding of a `.saipen/` file, without decoding it."""
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return "unreadable"
    for bom, enc in _BOMS:
        if raw.startswith(bom):
            return enc
    bomless = _bomless_utf16(raw)
    if bomless:
        return bomless + " (no BOM)"
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return "not-utf-8"
    return "utf-8"


def read_doc(path):
    """Read a `.saipen/` file without dying on its encoding.

    `read_text(encoding="utf-8-sig")` raises on a UTF-16 file, and because the
    very first thing this validator reads is `.saipen/STATE.md`, that raise
    killed the whole run: a Python traceback, zero FAILs, and not one other
    check performed. The project could have ten defects and the only thing
    reported was a decode error nobody can act on -- from a pre-commit hook, at
    that. Diagnose the encoding (below) and keep checking everything else.
    """
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return ""
    for bom, enc in _BOMS:
        if raw.startswith(bom):
            text = raw[len(bom):].decode(enc, errors="replace")
            break
    else:
        bomless = _bomless_utf16(raw)
        if bomless:
            text = raw.decode(bomless, errors="replace")
        else:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                # cp1251 before a never-failing fallback: these files are
                # frequently Russian, and latin-1 first would mean cp1251 is
                # never reached and Cyrillic always arrives as mojibake.
                try:
                    text = raw.decode("cp1251")
                except UnicodeDecodeError:
                    text = raw.decode("utf-8", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


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
    for req in schema.get("required", []):
        if req not in fields:
            fail(f"{label} missing required field: {req}")
    for key, value in fields.items():
        if key not in props:
            # Always a FAIL. This branched on additionalProperties until
            # v7.101.0 and warned when it was not False -- an arm that could
            # never execute: both call sites pass state.schema.json, which
            # sets additionalProperties: false, so the `unknown-field` warn
            # category could not appear in any output ever produced. Found by
            # auditing which warn categories can actually fire. A branch
            # nobody can reach is decoration, and a warning nobody can see is
            # indistinguishable from a check that is not there.
            fail(f"{label} has field the schema doesn't know: "
                 f"{key} (retired or misspelled?)")
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

# Encoding is diagnosed before anything is parsed, on all three checkpoint
# files. A UTF-16 or BOM-carrying `.saipen/` file is what PowerShell 5.1's
# `Set-Content`/`Out-File` produce by default (KNOWLEDGE/traps.md), and the
# consequences differ by tool in a way that hides the cause: this validator
# used to die on a traceback at the first read, the portable `grep` floor
# matches nothing and reports missing fields, and a BOM alone breaks `^---`
# so the frontmatter silently parses as empty. One named FAIL beats three
# unrelated symptoms.
for _cf in (state_path, Path(".saipen/BOARD.md"), Path(".saipen/LOG.md")):
    if not _cf.is_file():
        continue
    _enc = encoding_of(_cf)
    if _enc != "utf-8":
        fail(f"{_cf.as_posix()} is {_enc}, not plain UTF-8. Every other SAIPEN "
             f"tool reads it byte-wise and will fail differently: the portable "
             f"floor greps and finds no fields, a BOM alone breaks the "
             f"frontmatter match. Rewrite it as UTF-8 without a BOM -- never "
             f"with PowerShell Set-Content (KNOWLEDGE/traps.md)")

state, err = parse_frontmatter(read_doc(state_path))
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
elif sv > CURRENT_SCHEMA_VERSION:
    # ">= current" was written from the wrong end. A state NEWER than this
    # validator is not reassuring: it may carry required fields this file has
    # never heard of, or the same field names with changed meaning, and every
    # PASS below is then a claim with nothing behind it. `schema_version: 99`
    # validated clean at exit 0 until now, which is the same defect class as
    # the release-ledger check running on half a ledger -- a check reporting
    # on data it cannot evaluate. WARN rather than FAIL: FAIL would block
    # every commit in a project the moment the protocol bumps its schema,
    # including during the bump itself, and the point is to stop the silent
    # PASS, not to stop the work.
    warn("schema-version",
         f"STATE.md schema_version is {sv}, but this validator only "
         f"understands {CURRENT_SCHEMA_VERSION} -- it was written by a newer "
         f"SAIPEN than the one installed here. Every PASS below covers only "
         f"the rules this version knows; update saipen_home before trusting "
         f"a clean run")

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
    # FAIL, not WARN. RFC § 1.2 says next_action MUST begin with one of these
    # five, and the identical check on a subSaipen's STATE (below) has always
    # FAILed -- so the protocol was stricter about a read-only worker's state
    # than about the one a cold agent actually boots from. The vague-phrase
    # regex above is a blacklist and evadable by construction: `fix the thing`,
    # `ship it` and `look at the board` all passed clean at exit 0 until
    # v7.101.0, each of them a state TEST-001 cannot execute. The prefix rule
    # is the whitelist; it has to carry the weight.
    if not next_action.startswith(executable_prefixes):
        fail(f"STATE.md next_action does not start with WAIT:/saipen /PHASE "
             f"/RUN:/RESUME:: {next_action!r} -- not executable, so a cold "
             f"agent cannot boot from it (RFC § 1.2, CONFORMANCE TEST-001)")
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
        if verb and verb not in SAIPEN_COMMANDS:
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
# A subSaipen's `read-only` is a SCOPE lock, not Core's capability lock: it
# writes its own STATE/BOARD/LOG/kitchen freely and is barred only from the
# shared tree, so the ban is the phases whose work product lands OUTSIDE its
# folder. Four, not seven. PLAN and ADD are reachable and expected --
# PROTOCOL.md § 5's backpressure note and TEMPLATE/STATE.md's default
# next_action both have a subSaipen planning its own backlog, which the
# capability reading forbids outright. These two lists had always differed
# here while PROTOCOL.md § 1 claimed the contracts were "identical", so a
# conformant reader and a conformant run disagreed about PLAN. Both are named
# now and the drift detector compares them against that paragraph.
SUB_READ_ONLY_BANNED_PHASES = ("BUILD", "SHIP", "CLEAN", "TRANSLATE")

if mode == "read-only" and phase in READ_ONLY_BANNED_PHASES:
    fail(f"mode: read-only MUST NOT enter {phase} -- that phase's work "
         f"product is a file write (RFC § 1.3)")

# RFC § 1.3's handshake names the capability vocabulary: filesystem, git,
# shell, python. Nothing had ever checked the values, so a typo
# (`requires: [pyhton]`) reads as an unknown capability -- and § 1.3 says an
# unmapped entry "is not a licence to ignore it", meaning the agent must
# degrade to the nearest mode describing what is lost. It cannot do that for a
# capability that does not exist, so the typo silently removes the requirement
# instead of tightening it. WARN, not FAIL: the vocabulary is explicitly open
# to entries with no mapping, and a project MAY legitimately require something
# this list has not learned yet -- but it gets said out loud.
KNOWN_CAPABILITIES = ("filesystem", "git", "shell", "python")
_req = state.get("requires")
if isinstance(_req, list):
    _unknown = [c for c in _req
                if isinstance(c, str) and c.strip()
                and c.strip() not in KNOWN_CAPABILITIES]
    if _unknown:
        warn("requires-vocabulary",
             f"STATE.md requires: names {_unknown} -- not in RFC § 1.3's "
             f"handshake vocabulary ({'/'.join(KNOWN_CAPABILITIES)}). An "
             f"unmapped entry is not ignorable: the agent MUST degrade to the "
             f"mode describing what is lost, which it cannot do for a "
             f"capability nobody defines. Check for a typo")

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

# `saipen_version` is the protocol MAJOR this state was written against. It was
# type-checked as an integer and compared to nothing, so a project declaring 6
# while running against a v7 home was executing v7 rules over a v6 state with
# no signal anywhere.
if IS_SAIPEN_HOME and Path("VERSION").is_file():
    _sv_major = state.get("saipen_version")
    try:
        _home_major = int(Path("VERSION").read_text(
            encoding="utf-8-sig").strip().split(".")[0])
    except (ValueError, OSError):
        _home_major = None
    if isinstance(_sv_major, int) and _home_major is not None             and _sv_major != _home_major:
        warn("saipen-version-major",
             f"STATE.md saipen_version is {_sv_major} but saipen_home is at "
             f"major {_home_major} -- this state was written against a "
             f"different protocol generation, and every rule below is being "
             f"applied to it regardless")

sub_state_files = sorted(
    # TEMPLATE included here too -- the shipped-library walk below stopped
    # skipping it in v7.101.0 and this half had the same hole.
    p for p in subs_root.glob("*/STATE.md"))
library_subs = Path("extensions/subs")
if (IS_SAIPEN_HOME and library_subs.is_dir()
        and library_subs.resolve() != subs_root.resolve()):
    # TEMPLATE included, not skipped. `saipen sub spawn` copies it verbatim,
    # so it is the source every instance inherits -- and excluding it is
    # exactly why it shipped a `next_action` with no legal prefix, meaning
    # every spawned subSaipen was born failing RFC § 1.2 until v7.101.0.
    # The one file exempted from the check was the one the check existed
    # to protect.
    sub_state_files += sorted(library_subs.glob("*/STATE.md"))

if sub_state_files:
    subs_ok = True
    for sp in sub_state_files:
        sub_state, err = parse_frontmatter(read_doc(sp))
        if sub_state is None:
            fail(f"{sp} frontmatter: {err}")
            subs_ok = False
            continue
        before_sub = len(failures)
        check_against_schema(sub_state, schema, str(sp))
        if sub_state.get("mode") != "read-only":
            fail(f"{sp} mode is {sub_state.get('mode')!r}, MUST be read-only "
                 f"(extensions/subs/PROTOCOL.md § 1)")
        if sub_state.get("phase") in SUB_READ_ONLY_BANNED_PHASES:
            fail(f"{sp} phase {sub_state.get('phase')} is unreachable for a "
                 f"subSaipen -- its work product lands outside the subSaipen's "
                 f"own folder (extensions/subs/PROTOCOL.md § 1)")
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
            # The prefix proves the shape, not the vocabulary. Core has had
            # this since v7.89.0; a sub's STATE went without it, so
            # `saipen hunt` in a sub validated clean while naming a command
            # § 1.10 does not define -- a state its own cold agent is required
            # to decline.
            if sub_na.startswith("saipen "):
                _rest = sub_na[len("saipen "):].split()
                _verb = _rest[0].strip('."\'') if _rest else ""
                if _verb and _verb not in SAIPEN_COMMANDS:
                    fail(f"{sp} next_action invokes 'saipen {_verb}', which RFC "
                         f"§ 1.10 does not define -- its cold agent MUST "
                         f"decline an unrecognized command and stop")

        # PROTOCOL.md § 1 says a subSaipen is a normal SAIPEN instance: "same
        # STATE.md/BOARD.md/LOG.md shape, same phase enum (RFC § 1.6), same LOG
        # skeleton (RFC § 1.2)". The schema call above covers eight required
        # fields and the phase enum. These four were Core-only, so the PASS
        # line below claimed a shape it had not checked -- the same inversion
        # v7.101.0 fixed in the other direction, when the prefix rule was
        # stricter for a read-only worker than for the state a cold agent boots
        # from. Parity in both directions or the message is a lie.
        _sub_tf = sub_state.get("transition_from")
        _sub_ph = sub_state.get("phase")
        if _sub_tf is None:
            if _sub_ph != "INIT":
                fail(f"{sp} missing transition_from -- RFC § 1.2's ninth "
                     f"required field, absent only for a fresh INIT")
        elif _sub_tf not in VALID_TRANSITIONS and _sub_tf not in ANY_FROM:
            fail(f"{sp} transition_from {_sub_tf!r} is not one of the 16 phase "
                 f"enum values (RFC § 1.6)")
        elif _sub_ph and _sub_tf != _sub_ph and _sub_ph not in ANY_FROM:
            _allowed = list(VALID_TRANSITIONS.get(_sub_tf, []))
            # RFC § 1.6 routes HUNT to ADD/PLAN/SCOUT/BLOCKED because for Core
            # a clean sweep still has to decide what work it creates. A
            # reporting subSaipen's deliverable is its OUTBOX, and the "add"
            # step happens in the MAIN project during collect (PROTOCOL.md § 4),
            # so HUNT -> DONE is its real, honest terminus. saihunt had been
            # sitting in exactly that state since its first sweep, truthfully,
            # and no check had ever looked at a sub's transitions to notice.
            if _sub_tf == "HUNT":
                _allowed.append("DONE")
            if _sub_ph not in _allowed:
                fail(f"{sp} {_sub_tf} -> {_sub_ph} is not in the transition "
                     f"table ({_sub_tf} allows "
                     f"{'/'.join(_allowed) or 'nothing'}) (RFC § 1.6)")

        _sub_up = sub_state.get("updated")
        if isinstance(_sub_up, str) and not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00)",
                _sub_up):
            fail(f"{sp} updated must be ISO-8601 UTC (Z or +00:00), got "
                 f"{_sub_up!r} -- Recovery miscompares staleness across "
                 f"timezones otherwise (RFC § 1.2)")

        if sub_state.get("goal_mode") is True:
            for _c in ("goal_waves", "goal_tickets"):
                if not TYPE_CHECKS["integer"](sub_state.get(_c)):
                    fail(f"{sp} goal_mode: true but {_c} is missing -- "
                         f"PROTOCOL.md documents `saipen goal` for an "
                         f"unattended sub run, so § 2.4's valve applies here "
                         f"too and cannot survive a restart without it")

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

board_lines = read_doc(board_path).splitlines()
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
        r"## BLOCKED.*?\[MARKHUNT\]", read_doc(board_path),
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
    sealed_dateless = []
    prev_id = 0
    log_ok = True
    timestamp_events = []
    for lf in log_files:
        # Sealed segments are immutable (append-only, RFC § 1.2); the active
        # log is still the writer's to get right. Severity below splits on it.
        is_active_log = (lf == active_log)
        for line_no, line in enumerate(read_doc(lf).splitlines(), 1):
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
            # RFC § 1.2 makes DATE mandatory, but LOG_RE has always accepted a
            # dateless line and 125 of them sit in the sealed LOG-001, where
            # append-only forbids a rewrite. So: FAIL in the active log, where
            # the line is still the writer's to get right, and WARN in sealed
            # history, which is immutable by design. Same severity split this
            # file already applies to nonstandard taxonomies.
            if ts is None:
                if is_active_log:
                    fail(f"{loc} has no DATE -- RFC § 1.2 makes it mandatory, "
                         f"and without it this line contributes nothing to the "
                         f"timestamp checks below")
                    log_ok = False
                else:
                    sealed_dateless.append(loc)
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
        all_log = "\n".join(read_doc(p) for p in log_files)
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
    # A zero harvest means both timestamp checks below iterate over nothing and
    # pass in silence -- the exact shape of the check that lay dead from
    # feae149 until v7.99.0. If there are entries but no parsed timestamps at
    # all, the parser and the log have diverged and the checks are decoration.
    # One finding for the whole sealed population, not one per line: warn()'s
    # own rule is that a pattern repeated hundreds of times in immutable
    # history is a single finding, and 125 lines of it every run is how people
    # learn to scroll past warnings.
    if sealed_dateless:
        warn("log-missing-date",
             f"{len(sealed_dateless)} sealed LOG entr(y/ies) predate the "
             f"mandatory DATE (earliest {sealed_dateless[0]}). Immutable by "
             f"append-only; new entries are FAILed instead")

    if seen_ids and not timestamp_events:
        fail("LOG has entries but not one parseable timestamp -- the "
             "inversion and future-timestamp checks below would both pass by "
             "iterating over nothing")
        log_ok = False

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
        active_lines = len(read_doc(active_log).splitlines())
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
    text = read_doc(ob)
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

        # The mojibake half of this lint applies to any shipped text, not just
        # the four core docs -- corruption does not respect a curated list.
        # KNOWLEDGE/, extensions/ and the fixture READMEs were outside it until
        # v7.103.0, so an arrow mangled in traps.md sat unseen by the very
        # check whose subject traps.md documents.
        text_targets = [
            Path("saipen/RFC.md"),
            Path("saipen/BOOT.md"),
            Path("saipen/CONFORMANCE.md"),
            Path("saipen/SKILL.md"),
            Path("saipen/STYLE.md"),
            *sorted(Path("saipen/phases").glob("*.md")),
            *sorted(Path(".saipen/KNOWLEDGE").glob("*.md")),
            *sorted(Path("extensions").rglob("*.md")),
            *sorted(Path("tests/scenarios").glob("*/README.md")),
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
            # KNOWLEDGE/traps.md documents three shapes of this corruption and
            # this check knew only one until v7.103.0 -- the em-dash and arrow
            # forms were exactly as invisible as the section sign had been.
            # Same "fixed where it was noticed, not everywhere it applies"
            # shape as the seven adapters.
            for _seq, _what in (("\u0412\u00a7", "section sign"),
                                ("\u0432\u0403\u201c", "em dash"),
                                ("\u0432\u0402\u201d", "em dash"),
                                ("\u0432\u2020'", "arrow"),
                                ("\u0421\u040f", "non-breaking space")):
                if _seq in text:
                    fail(f"{doc.as_posix()} carries a cp1251-mangled {_what} "
                         f"-- valid UTF-8, so the U+FFFD check above cannot "
                         f"catch it")
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
            # RFC.md was absent from this list until v7.101.0 -- the manifest of
            # "every runtime file the protocol references" omitted the
            # constitution itself. Other checks would have noticed its absence,
            # but a completeness list that skips the most important item is not
            # a completeness list.
            "saipen/RFC.md",
            "saipen/BOOT.md", "saipen/SKILL.md", "saipen/UI.md", "saipen/STYLE.md",
            "saipen/CONFORMANCE.md",
            "tools/validate.py", "tools/install_hook.py", "tools/uninstall_hook.py",
            "tools/run_scenarios.py", "tools/audit_floor.py",
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
    stale, absent, checked = [], [], 0
    for locale_dir in sorted(kitchen.iterdir()):
        if not locale_dir.is_dir():
            continue
        readme = locale_dir / f"README_{locale_dir.name.upper()}.md"
        if not readme.is_file():
            # A missing README used to be skipped in silence while the success
            # line still counted DIRECTORIES -- so deleting one left the run
            # reporting "all 32 badges match" having checked 31. Absence of a
            # check is not a passing check (v7.101.0).
            absent.append(locale_dir.name)
            continue
        checked += 1
        content = readme.read_text(encoding="utf-8-sig")
        if f"**v{repo_version}**" not in content:
            stale.append(readme.name)
    if absent:
        warn("locale-readme-absent",
             f"{len(absent)} locale director(y/ies) carry no README to check: "
             f"{', '.join(sorted(absent)[:8])} -- the badge check silently "
             f"skips them, so their version is unverified, not verified")
    if stale:
        fail(f"translation README badge drift: {len(stale)} locale(s) still"
             f" show an old version -- {', '.join(sorted(stale))}")
    else:
        ok(f"{checked} locale README badge(s) match VERSION ({repo_version})")

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
    # A count is a copy too. `checkpoint-self-confirmation/README.md` said "all
    # eight required fields" for eight releases after the set became nine --
    # the enumeration check below could not see it, because it enumerates
    # nothing. Any shipped doc that states how many required fields there are
    # is asserting a number that moves without it.
    _count_re = re.compile(
        r"\b(all\s+)?(five|six|seven|eight|nine|ten|\d+)\s+required\s+fields?\b",
        re.IGNORECASE)
    _count_docs = [boot_path, conf_path]
    _count_docs += sorted((_tools_parent / ".saipen" / "KNOWLEDGE").glob("*.md"))
    _scen = _tools_parent / "tests" / "scenarios"
    if _scen.is_dir():
        _count_docs += sorted(_scen.glob("*/README.md"))
    for _doc in _count_docs:
        if not _doc.is_file():
            continue
        _m = _count_re.search(_doc.read_text(encoding="utf-8-sig"))
        if _m:
            fail(f"cross-doc drift [required-set] -- {_doc.name} states a COUNT "
                 f"of required fields ({_m.group(0)!r}). RFC § 1.2 is the only "
                 f"place the set is written down, and a count drifts the same "
                 f"way an enumeration does")
            drift_ok = False

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
    #    Every prescribed `next_action:` is checked, not only the WAIT ones.
    #    Restricting it to WAITs is how `phases/done.md` came to endorse
    #    `next_action: wait for user command` and how the shipped subSaipen
    #    TEMPLATE shipped `read the main project, ...` -- both with no legal
    #    prefix at all, so every doc-following agent produced a state this
    #    validator rejects. Found by a one-off sweep in v7.101.0 and fixed by
    #    hand; a one-off sweep is not a guard, which is the same "fixed where
    #    noticed, not everywhere it applies" shape as the seven adapters.
    doc_roots = [rfc_path.parent / "phases", _tools_parent / "extensions",
                 _tools_parent / ".saipen" / "KNOWLEDGE"]
    prescribed = re.compile('next_action:\\s*`?"?([^`"\\n]{3,60})')
    bad_actions, bad_waits = [], []
    for root in doc_roots:
        if not root.is_dir():
            continue
        for doc in sorted(root.rglob("*.md")):
            for m in prescribed.finditer(doc.read_text(encoding="utf-8-sig")):
                val = m.group(1).strip()
                if val.startswith("<") or val.startswith("..."):
                    continue          # a placeholder, not a prescription
                if not val.startswith(executable_prefixes):
                    bad_actions.append(f"{doc.as_posix()}: {val[:45]!r}")
                elif val.startswith("WAIT:"):
                    body = val[len("WAIT:"):].strip().lower()
                    if not (body.startswith("<") or
                            any(body.startswith(c) for c in WAIT_CATEGORIES)):
                        bad_waits.append(f"{doc.as_posix()}: {val[:45]!r}")
    for b in bad_actions:
        fail(f"cross-doc drift [prescribed-next-action] -- shipped doc "
             f"prescribes a `next_action` with none of § 1.2's five legal "
             f"prefixes, so an agent obeying it writes a state this validator "
             f"FAILs: {b}")
    for b in bad_waits:
        fail(f"cross-doc drift [wait-categories] -- shipped doc prescribes a "
             f"`WAIT:` with no § 1.2 category token: {b}")
    if bad_actions or bad_waits:
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
        # The root GUIDE.md is a separate document from guides/GUIDE_EN.md and
        # sat outside this walk entirely, so it went on teaching the
        # pre-v7.93.0 `WAIT: <question>` shape through v7.95.0's sweep of all
        # 33 locale guides. A directory glob is not a document inventory.
        _guide_docs = sorted(guides.glob("GUIDE_*.md"))
        _root_guide = _tools_parent / "GUIDE.md"
        if _root_guide.is_file():
            _guide_docs.append(_root_guide)
        for doc in _guide_docs:
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
    #     All three disagreed until v7.101.0 -- the table listed four while the
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

    # 11. Coverage accounting. Every check above answers "do these two agree?".
    #     None answered "is everything even being looked at?" -- and twice in a
    #     row that was the actual defect: the scenario READMEs escaped the
    #     re-enumeration guard, and the root GUIDE.md escaped the guides/ sweep,
    #     both because a directory glob only ever sees what lives inside it.
    #
    #     So the protocol's document surface is declared here, and any shipped
    #     markdown that matches no entry FAILs. Adding a doc then forces a
    #     deliberate choice: put it under a check, or exempt it and say why.
    #     `.saipen/` is excluded wholesale -- that is this project's own working
    #     memory, data rather than protocol text.
    COVERED = [
        ("saipen/RFC.md",            "source of truth for six cross-doc sets"),
        ("saipen/BOOT.md",           "re-enumeration + required-field-count checks"),
        ("saipen/CONFORMANCE.md",    "re-enumeration + count + row-ID checks"),
        ("saipen/phases/*.md",       "phase-enum sync + prescribed-WAIT category check"),
        ("extensions/**/*.md",       "prescribed-WAIT category check"),
        ("guides/GUIDE_*.md",        "guide WAIT-shape check"),
        ("GUIDE.md",                 "guide WAIT-shape check"),
        ("tests/scenarios/*/README.md", "required-field-count check + expect/reason parsing"),
        ("tests/scenarios/*/.saipen/*.md", "run_scenarios.py runs this validator against each fixture"),
        ("README.md",                "version-badge check"),
        # KNOWLEDGE/ is excluded from the .saipen/ blanket on purpose: RFC
        # § 1.2 makes it durable truth an agent reads before planning, not
        # inert project data. Blanketing it cost nine releases of traps.md
        # teaching a WAIT-at-DONE rule that had been superseded.
        (".saipen/KNOWLEDGE/*.md", "citation + required-field-count checks"),
    ]
    # EXEMPT means "no rule-CONTENT check applies", never "nothing looks at it".
    # Citations are verified across every shipped document below, exempt or
    # not: a pointer at a section or file that no longer exists is wrong
    # wherever it sits. The v7.101.0 wording implied the weaker thing, and five
    # of the seven entries here in fact name protocol files -- three of them
    # (SKILL.md, STYLE.md, UI.md) are shipped into every install by the
    # injector, and SKILL.md is the entry point that tells a skill-reading
    # platform which file to read first.
    EXEMPT = [
        ("saipen/SKILL.md",   "reading-order entry point for skill platforms; its file references are citation-checked, it states no rule of its own"),
        ("saipen/STYLE.md",   "chat voice; shipped, and its RFC reference is citation-checked, but the voice itself is not machine-checkable"),
        ("saipen/UI.md",      "visual spec for UI work, disjoint from the state protocol"),
        ("SPEC.md",           "design intent and rationale, deliberately not normative"),
        ("CHANGELOG.md",      "history; never read by an agent, never a rule source"),
        ("CHANGELOG_ARCHIVE.md", "sealed history, same as above"),
        ("CONTRIBUTING.md",   "human process, not agent-facing"),
        ("SECURITY.md",       "disclosure policy, not agent-facing"),
        ("CODE_OF_CONDUCT.md", "human conduct, not agent-facing"),
        (".github/**/*.md",   "issue/PR templates, not agent-facing"),
        (".github/*.md",      "issue/PR templates, not agent-facing"),
    ]
    if IS_SAIPEN_HOME:
        import fnmatch
        home = Path(".")
        surface = sorted(
            q.as_posix() for q in home.rglob("*.md")
            if (not q.as_posix().startswith(".saipen/")
                or q.as_posix().startswith(".saipen/KNOWLEDGE/"))
            and ".git/" not in q.as_posix())
        patterns = [g for g, _ in COVERED] + [g for g, _ in EXEMPT]
        unclassified = [
            d for d in surface
            if not any(fnmatch.fnmatch(d, g) for g in patterns)]
        if unclassified:
            fail(f"coverage gap -- {len(unclassified)} shipped document(s) are "
                 f"read by no check and declared exempt by none: "
                 f"{', '.join(unclassified[:6])}"
                 f"{' ...' if len(unclassified) > 6 else ''}. Put each under a "
                 f"check or add it to EXEMPT with a reason")
            drift_ok = False
        else:
            ok(f"doc coverage accounted for ({len(surface)} shipped documents, "
               f"{len(COVERED)} checked patterns, {len(EXEMPT)} exempt)")

    # 12. Citations resolve. Nearly every shipped document points into RFC by
    #     section number or at a phase doc by filename, and both move: sections
    #     get renumbered, phase docs get renamed. Neither leaves a mark on the
    #     citing document, so a pointer can rot into a reference to a rule that
    #     no longer exists while the sentence around it still reads fine.
    #     This is the same class as the adapter cross-reference check, applied
    #     to the two things every doc actually cites.
    _rfc_text = rfc_path.read_text(encoding="utf-8-sig")
    _sections = set(re.findall(r"^###\s+(\d+\.\d+)(?![\d.])", _rfc_text, re.MULTILINE))
    _phase_dir = rfc_path.parent / "phases"
    _phase_docs = {q.name for q in _phase_dir.glob("*.md")} if _phase_dir.is_dir() else set()
    if not _sections or not _phase_docs:
        fail("cross-doc drift [citations] -- could not read RFC's section "
             "headings or the phases/ directory, so citation checking would "
             "silently pass over everything")
        drift_ok = False
    else:
        _cite_docs = []
        # Every shipped document, exempt or not -- see the EXEMPT note above.
        for _pat in ("saipen/*.md", "saipen/phases/*.md", "extensions/**/*.md",
                     "tests/scenarios/*/README.md", "*.md",
                     ".saipen/KNOWLEDGE/*.md", ".github/**/*.md"):
            _cite_docs += list(_tools_parent.glob(_pat))
        _dangling = []
        for _doc in sorted(set(_cite_docs)):
            if not _doc.is_file() or "CHANGELOG" in _doc.name:
                continue
            _body = _doc.read_text(encoding="utf-8-sig", errors="replace")
            for _s in sorted(set(re.findall(r"\u00a7\s*(\d+\.\d+)", _body))):
                if _s not in _sections:
                    _dangling.append(f"{_doc.name} cites RFC \u00a7 {_s}")
            for _d in sorted(set(re.findall(r"phases/([a-z_]+\.md)", _body))):
                if _d not in _phase_docs:
                    _dangling.append(f"{_doc.name} cites phases/{_d}")
            # Named protocol files rot the same way. SKILL.md alone points a
            # cold platform at five of them; if one is renamed, every such
            # pointer becomes a dead end with no other symptom. Scope is
            # exactly these six plus extensions/subs/PROTOCOL.md -- the files
            # the protocol itself names. An arbitrary `Foo.md` reference is
            # somebody else's filename and deliberately not adjudicated here.
            for _f in sorted(set(re.findall(
                    r"\b(RFC|BOOT|STYLE|UI|CONFORMANCE|SKILL)\.md\b", _body))):
                if not (rfc_path.parent / f"{_f}.md").is_file():
                    _dangling.append(f"{_doc.name} cites {_f}.md")
            if "extensions/subs/PROTOCOL.md" in _body and not (
                    _tools_parent / "extensions" / "subs" / "PROTOCOL.md").is_file():
                _dangling.append(f"{_doc.name} cites extensions/subs/PROTOCOL.md")
        if _dangling:
            fail(f"cross-doc drift [citations] -- {len(_dangling)} dangling "
                 f"reference(s): {'; '.join(_dangling[:5])}"
                 f"{' ...' if len(_dangling) > 5 else ''}")
            drift_ok = False

    # 13. No document may cite a version that has not shipped. Writing
    #     a not-yet-shipped version into a rationale is easy and reads as fact; if
    #     the release never happens, or the number slips, every such line is a
    #     promise the repository cannot keep. The bound is VERSION itself.
    if IS_SAIPEN_HOME:
        _cur = Path("VERSION").read_text(encoding="utf-8-sig").strip()
        try:
            _cur_t = tuple(int(x) for x in _cur.split("."))
        except ValueError:
            _cur_t = None
        if _cur_t:
            _future = {}
            for _doc in sorted(set(_cite_docs)):
                if not _doc.is_file() or "CHANGELOG" in _doc.name:
                    continue
                _body = _doc.read_text(encoding="utf-8-sig", errors="replace")
                # Explicit character class, not a word boundary: the first
                # version of this line reached the file as a literal BACKSPACE
                # on both ends -- the escape was consumed before the raw prefix
                # applied. It matched nothing and said nothing. Sixth escape
                # trap of the session, in the tool written right after that
                # trap was recorded in KNOWLEDGE.
                for _v in set(re.findall(r"(?:^|[\s(\[])v(\d+\.\d+\.\d+)",
                                         _body, re.MULTILINE)):
                    try:
                        if tuple(int(x) for x in _v.split(".")) > _cur_t:
                            _future.setdefault(_v, set()).add(_doc.name)
                    except ValueError:
                        continue
            if _future:
                _bits = [f"v{v} in {', '.join(sorted(d)[:3])}"
                         for v, d in sorted(_future.items())]
                fail(f"cross-doc drift [future-version] -- {len(_future)} "
                     f"version(s) cited above VERSION ({_cur}): "
                     f"{'; '.join(_bits[:4])}. A citation to a release that "
                     f"has not happened is a promise the repo cannot keep")
                drift_ok = False

    # 13b. A version BELOW VERSION is not the same as a version that happened.
    #      The bound above assumes the sequence is dense, and it is not: one
    #      number was skipped entirely -- no tag, no CHANGELOG entry, no commit
    #      whose VERSION ever said it -- while twenty-four lines across
    #      CONFORMANCE, PROTOCOL.md, this file and the PowerShell floor named it
    #      as the release they shipped in. Every one of them was below VERSION,
    #      so the check above certified them all. The ledger, not the ordering,
    #      is what says a release exists.
    if IS_SAIPEN_HOME:
        _ledger = set()
        _chg = _tools_parent / "CHANGELOG.md"
        if _chg.is_file():
            _ledger |= set(re.findall(
                r"^## (\d+\.\d+\.\d+)",
                _chg.read_text(encoding="utf-8-sig"), re.MULTILINE))
        _tag_list = set()
        try:
            _r = subprocess.run(["git", "tag", "-l", "v*"],
                                capture_output=True, text=True, check=False)
            if _r.returncode == 0:
                _tag_list = {ln.strip()[1:] for ln in _r.stdout.splitlines()
                             if ln.strip().startswith("v")}
        except (OSError, subprocess.SubprocessError):
            pass
        _ledger |= _tag_list

        def _rel(p):
            try:
                return p.relative_to(_tools_parent).as_posix()
            except ValueError:
                return p.name

        def _tup(v):
            try:
                return tuple(int(x) for x in v.split("."))
            except ValueError:
                return None

        _known = {t for t in (_tup(v) for v in _ledger) if t}
        # A PARTIAL ledger is worse than no ledger: it turns every release
        # recorded only in the missing half into a phantom. That is not
        # hypothetical -- this check shipped without the guard and CI reddened
        # on the first run, because `actions/checkout` clones shallow and
        # fetches no tags, so two legitimately-tagged releases with no
        # CHANGELOG entry read as never having happened. The instrument was
        # broken, not the subject, and it took a whole release to say so.
        # Both halves present, or the check does not run.
        _tags_seen = bool(_tag_list)
        if not _tags_seen:
            warn("release-ledger",
                 "git tag list unavailable or empty -- the release ledger has "
                 "only its CHANGELOG half, so the phantom-version check is "
                 "skipped rather than run against incomplete data")
        if _known and _tags_seen:
            # Below the oldest entry the ledger simply has no memory -- those
            # citations predate both files and cannot be decided here. Silence
            # there is honest; silence above it was the defect.
            _floor = min(_known)
            # Wider than _cite_docs, which is markdown only. A version
            # citation rots the same way inside a JSON schema, the validator
            # itself or the portable floor -- and all three carried the
            # phantom number. Third time in one day that a check was right
            # about content and wrong about coverage.
            _ver_docs = list(_cite_docs)
            for _pat in ("extensions/schemas/*.json", "tools/*.py",
                         "tests/*.sh", "tests/*.ps1",
                         "tests/scenarios/*/*.md"):
                _ver_docs += list(_tools_parent.glob(_pat))
            _phantom = {}
            for _doc in sorted(set(_ver_docs)):
                if not _doc.is_file() or "CHANGELOG" in _doc.name:
                    continue
                _body = _doc.read_text(encoding="utf-8-sig", errors="replace")
                for _v in set(re.findall(r"(?:^|[\s(\[])v(\d+\.\d+\.\d+)",
                                         _body, re.MULTILINE)):
                    _t = _tup(_v)
                    if _t and _t >= _floor and _t not in _known:
                        # Path, not name: this repo has ten README.md, and the
                        # first run of this check reported "README.md" for a
                        # cluster of nine scenario fixtures.
                        _phantom.setdefault(_v, set()).add(_rel(_doc))
            if _phantom:
                _bits = [f"v{v} in {', '.join(sorted(d)[:3])}"
                         for v, d in sorted(_phantom.items())]
                fail(f"cross-doc drift [phantom-version] -- "
                     f"{len(_phantom)} version(s) cited that are inside the "
                     f"release ledger's range but absent from it (no tag, no "
                     f"CHANGELOG entry): {'; '.join(_bits[:4])}. Below VERSION "
                     f"is not the same as shipped")
                drift_ok = False

            # The ledger's two halves are themselves a cross-document pair and
            # nothing had ever compared them. WARN, not FAIL: closing a
            # historical divergence means either rewriting CHANGELOG or pushing
            # a backdated tag, and a backdated tag push publishes a release.
            # The divergence is a fact the repo should carry, not a gate.
            _chg_v = set()
            if _chg.is_file():
                _chg_v = {t for t in (_tup(v) for v in re.findall(
                    r"^## (\d+\.\d+\.\d+)",
                    _chg.read_text(encoding="utf-8-sig"), re.MULTILINE)) if t}
            _tag_v = set()
            try:
                _r = subprocess.run(["git", "tag", "-l", "v*"],
                                    capture_output=True, text=True, check=False)
                if _r.returncode == 0:
                    _tag_v = {t for t in (_tup(ln.strip()[1:])
                                          for ln in _r.stdout.splitlines()
                                          if ln.strip().startswith("v")) if t}
            except (OSError, subprocess.SubprocessError):
                pass

            def _vs(versions):
                # The count above and this list have to agree, or the message
                # states ten and shows eight with nothing saying so -- a small
                # lie in a warning is still a warning nobody can act on.
                _s = sorted(versions)
                _out = ", ".join("v" + ".".join(map(str, v)) for v in _s[:8])
                if len(_s) > 8:
                    _out += f", and {len(_s) - 8} more"
                return _out

            if _chg_v and _tag_v:
                # Compare only where both halves have memory. Below either
                # floor one of them simply wasn't being kept yet, and calling
                # that a divergence would be noise, not a finding.
                _overlap = max(min(_chg_v), min(_tag_v))
                _no_entry = {v for v in _tag_v if v >= _overlap} - _chg_v
                _no_tag = {v for v in _chg_v if v >= _overlap} - _tag_v
                if _no_entry:
                    warn("release-ledger",
                         f"{len(_no_entry)} release(s) carry a git tag but no "
                         f"CHANGELOG entry: {_vs(_no_entry)}")
                if _no_tag:
                    warn("release-ledger",
                         f"{len(_no_tag)} release(s) have a CHANGELOG entry "
                         f"but no git tag: {_vs(_no_tag)}")

    # 13c. The palette has one name, and every document uses it. UI.md's
    #      palette was renamed to Wintage Golden and declared the default; the
    #      old name lived in 46 files, two of them shipped root docs and the
    #      rest locale copies. A rename that lands in the defining document and
    #      nowhere else is the shape this repo keeps re-finding -- the 33
    #      guides teaching a superseded WAIT form, the root GUIDE.md outside
    #      the glob, seven adapters pointing at the constitution. The old
    #      literal is assembled here rather than written out, because
    #      CONFORMANCE.md is itself scanned and a rule that trips on its own
    #      illustration is one nobody can keep.
    def _rel_doc(_p):
        try:
            return _p.relative_to(_tools_parent).as_posix()
        except ValueError:
            return _p.name

    _ui = _tools_parent / "saipen" / "UI.md"
    if _ui.is_file():
        _ui_body = _ui.read_text(encoding="utf-8-sig")
        _palette = "Vintage Golden"
        # Every name the palette has HAD. Assembled from fragments so this
        # file, CONFORMANCE.md and the row describing the rename can all
        # discuss it without tripping it -- the fifth rule this session that
        # had to stop quoting its own illustration. Grows by one entry per
        # rename; the second was a one-letter correction shipped an hour
        # after the first, which is exactly why this is a list and not a
        # constant.
        _superseded = ("Dark" + " Golden", "Win" + "tage Golden")
        if _palette not in _ui_body:
            fail(f"UI.md no longer names its palette {_palette!r} -- the "
                 f"palette name is normative and every other document "
                 f"references it")
            drift_ok = False
        _stale_name = []
        for _doc in sorted(set(_cite_docs)):
            # CHANGELOG is history and records what the name WAS. A rule that
            # forces a rewrite of the past is a rule that gets disabled the
            # first time it is inconvenient.
            if not _doc.is_file() or "CHANGELOG" in _doc.name:
                continue
            _txt = _doc.read_text(encoding="utf-8-sig", errors="replace")
            if any(_s in _txt for _s in _superseded):
                _stale_name.append(_rel_doc(_doc))
        if _stale_name:
            fail(f"cross-doc drift [palette-name] -- {len(_stale_name)} "
                 f"document(s) still name the superseded palette instead of "
                 f"{_palette!r}: {', '.join(_stale_name[:5])}"
                 f"{' ...' if len(_stale_name) > 5 else ''}")
            drift_ok = False

    # 13c2. PROTOCOL.md § 1's four-phase subSaipen ban agrees with the tool.
    #       This pair spent its whole life disagreeing: the document said the
    #       contract was "identical" to RFC § 1.3's seven-phase capability ban
    #       while the tool enforced four, so a reader who obeyed the document
    #       would never PLAN and every real subSaipen did. The seventh set the
    #       drift detector carries, and the first one added because a document
    #       was STRICTER than the tool rather than looser.
    _pp = _tools_parent / "extensions" / "subs" / "PROTOCOL.md"
    if _pp.is_file():
        _pt = _pp.read_text(encoding="utf-8-sig")
        _m = re.search(
            r"A subSaipen MUST NOT transition to ([^.]+?)\.", _pt, re.DOTALL)
        if not _m:
            fail("cross-doc drift [sub-ban] -- PROTOCOL.md no longer states "
                 "the subSaipen phase ban in the form the drift check parses "
                 "('A subSaipen MUST NOT transition to ...'). A missing anchor "
                 "is a failure, not a skip")
            drift_ok = False
        else:
            _doc_ban = set(re.findall(r"`([A-Z]+)`", _m.group(1)))
            if _doc_ban != set(SUB_READ_ONLY_BANNED_PHASES):
                fail(f"cross-doc drift [sub-ban] -- PROTOCOL.md § 1 bans "
                     f"{sorted(_doc_ban)} but validate.py enforces "
                     f"{sorted(SUB_READ_ONLY_BANNED_PHASES)}")
                drift_ok = False
        if "scope" not in _pt.lower():
            fail("cross-doc drift [sub-ban] -- PROTOCOL.md § 1 no longer "
                 "distinguishes a subSaipen's SCOPE lock from Core's "
                 "capability lock; without that sentence the two phase bans "
                 "read as an unexplained contradiction again")
            drift_ok = False

    # 13f. The installed pre-commit hook is not from an older generation.
    #      In a consuming project the hook is the ONLY thing that gates a
    #      commit, and its text is baked into `.git/hooks/pre-commit` at install
    #      time -- it never updates itself. So a hook installed twenty releases
    #      ago goes on running whatever logic it was born with, and nothing said
    #      so. Exactly the failure `KNOWLEDGE/traps.md` records for the
    #      injector's skill copies, which need a re-inject after every pull; the
    #      hook had no equivalent signal at all. Parsed out of install_hook.py
    #      rather than imported, because that module does its work at import.
    _hook = Path(".git/hooks/pre-commit")
    _installer = _tools_parent / "tools" / "install_hook.py"
    if _hook.is_file() and _installer.is_file():
        _cur = re.search(r"^HOOK_VERSION\s*=\s*(\d+)",
                         _installer.read_text(encoding="utf-8-sig"), re.MULTILINE)
        _got = re.search(r"saipen-hook-version:\s*(\d+)",
                         read_doc(_hook))
        if _cur:
            if _got is None:
                warn("hook-generation",
                     f"the installed pre-commit hook carries no version stamp "
                     f"-- it predates v7.113.0 and cannot be compared. Re-run "
                     f"tools/install_hook.py to pick up the current one "
                     f"(generation {_cur.group(1)})")
            elif int(_got.group(1)) != int(_cur.group(1)):
                warn("hook-generation",
                     f"the installed pre-commit hook is generation "
                     f"{_got.group(1)}; the installer ships generation "
                     f"{_cur.group(1)}. The hook never updates itself -- "
                     f"re-run tools/install_hook.py")

    # 13d. RFC § 1.7 Workspace Hygiene, mechanically. `saipen set` writes a
    #      bootloader that POINTS at the canonical home; it must never copy the
    #      protocol into the project, and phase transitions must load from
    #      `saipen_home` by absolute path. A copied `phases/` or `tools/` under
    #      `.saipen/` is the failure this forbids: it goes stale the moment the
    #      home moves, and nothing in the project would ever say so.
    #      `extensions/subs/` is NOT a copy -- those are the project's own
    #      subSaipen instances, which is why the ban names directories rather
    #      than blanketing `.saipen/`.
    _sd = Path(".saipen")
    if _sd.is_dir():
        _copied = [n for n in ("phases", "tools", "tests", "schemas",
                               "adapters", "templates")
                   if (_sd / n).is_dir()]
        _copied += [n for n in ("RFC.md", "BOOT.md", "SKILL.md", "STYLE.md",
                                "UI.md", "CONFORMANCE.md")
                    if (_sd / n).is_file()]
        if _copied:
            fail(f"RFC § 1.7 -- .saipen/ carries {', '.join(sorted(_copied))}, "
                 f"which belong to saipen_home. `saipen set` writes a "
                 f"bootloader that POINTS at the home; a copy goes stale the "
                 f"moment the home moves and nothing here would say so")
            drift_ok = False

    # 13e. Every RFC section that states a MUST is claimed by CONFORMANCE.
    #      The doc-coverage check answers "is any check looking at this file?".
    #      Nothing answered the same question one level up, about RULES, and
    #      three sections turned out to state nine MUSTs between them with no
    #      row claiming any of them -- not disputed, not exempted, simply
    #      unaccounted for. A behavioral rule no validator can test still gets
    #      a row saying so; the row is how the protocol admits the limit
    #      instead of leaving a silent hole.
    _rfc_p = _tools_parent / "saipen" / "RFC.md"
    _conf_p = _tools_parent / "saipen" / "CONFORMANCE.md"
    if _rfc_p.is_file() and _conf_p.is_file():
        _rfc_b = _rfc_p.read_text(encoding="utf-8-sig")
        _must_by_sec, _cur_sec = {}, None
        for _ln in _rfc_b.splitlines():
            _h = re.match(r"^#{2,4}\s*§?\s*(\d+\.\d+)\s", _ln)
            if _h:
                _cur_sec = _h.group(1)
                _must_by_sec.setdefault(_cur_sec, 0)
                continue
            if _cur_sec:
                _must_by_sec[_cur_sec] += len(re.findall(r"\bMUST\b", _ln))
        _claimed = set(re.findall(r"§\s*(\d+\.\d+)",
                                  _conf_p.read_text(encoding="utf-8-sig")))
        _unclaimed = sorted((s for s, c in _must_by_sec.items()
                             if c and s not in _claimed),
                            key=lambda s: [int(x) for x in s.split(".")])
        if _unclaimed:
            _bits = [f"§ {s} ({_must_by_sec[s]} MUST)" for s in _unclaimed]
            fail(f"rule coverage -- {len(_unclaimed)} RFC section(s) state a "
                 f"MUST that no CONFORMANCE row cites: {', '.join(_bits)}. "
                 f"Every MUST is either enforced or has a row saying why it "
                 f"cannot be")
            drift_ok = False

    # 14. Every adapter names the cold-start kernel. An adapter that sends a
    #     cold agent straight at RFC.md inverts the 2-tier design: the
    #     constitution is ~100 KB and BOOT.md is under 4, and BOOT is all a
    #     bare `saipen continue` needs. T-204 fixed two adapters and nobody
    #     checked the other seven, which went on pointing at RFC alone until
    #     v7.102.0.
    _adapters = sorted((_tools_parent / "extensions" / "adapters").glob("*.md"))
    if _adapters:
        _no_kernel = [a.name for a in _adapters
                      if "BOOT.md" not in a.read_text(encoding="utf-8-sig")]
        if _no_kernel:
            fail(f"cross-doc drift [adapters] -- {len(_no_kernel)} adapter(s) "
                 f"never name BOOT.md and point a cold agent straight at the "
                 f"constitution: {', '.join(_no_kernel)}")
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
