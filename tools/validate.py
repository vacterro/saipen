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
directly (required/enum/type subset of JSON Schema, interpreted natively) --
the schema file is the single source of truth for STATE's field list, not
a copy of it.

Severity model: violations of RFC.md MUSTs fail (exit 1). Drift that lives
in immutable history (LOG.md is append-only -- a nonstandard taxonomy or
ticket-ref written months ago cannot be fixed without rewriting history,
which RFC forbids) warns instead. --strict promotes warnings to failures.
"""

import json
import re
import sys
from pathlib import Path

STRICT = "--strict" in sys.argv[1:]
USE_COLOR = sys.stdout.isatty()

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
    """Interpret the required/enum/type subset of JSON Schema. That subset
    is everything state.schema.json actually uses -- if the schema ever
    grows past it, extend this, don't silently skip."""
    props = schema.get("properties", {})
    for req in schema.get("required", []):
        if req not in fields:
            fail(f"{label} missing required field: {req}")
    for key, value in fields.items():
        if key not in props:
            warn("unknown-field", f"{label} has field the schema doesn't know: "
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

if len(failures) == before:
    ok("STATE.md schema valid (checked against state.schema.json)")

# RFC § 1.3 mode/phase restrictions.
mode, phase = state.get("mode"), state.get("phase")
if mode == "no-publish" and phase == "SHIP":
    fail("mode: no-publish MUST NOT transition to SHIP (RFC § 1.3)")
if mode == "read-only" and phase in ("BUILD", "SHIP", "CLEAN", "TRANSLATE"):
    fail(f"mode: read-only MUST NOT enter {phase} (RFC § 1.3)")

# RFC § 2.4: goal_mode: true requires both persisted counters.
if state.get("goal_mode") is True:
    missing_counters = [c for c in ("goal_waves", "goal_tickets")
                        if not TYPE_CHECKS["integer"](state.get(c))]
    for counter in missing_counters:
        fail(f"goal_mode: true but {counter} counter missing -- safety valve "
             f"can't survive a restart without it (RFC § 2.4)")
    if not missing_counters:
        ok("goal_mode counters present")

# --------------------------------------------------------------------- BOARD

board_path = Path(".saipen/BOARD.md")
if not board_path.is_file():
    fail("BOARD.md missing")
    sys.exit(1)

REQUIRED_HEADINGS = ["## DOING", "## TODO", "## DONE", "## BLOCKED"]
KNOWN_FIELDS = {"needs", "owner", "claim_time", "blocker", "verify"}
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
                        "checkbox": checkbox, "needs": needs, "fields": fields}

for heading in REQUIRED_HEADINGS:
    if heading not in headings_seen:
        fail(f"BOARD.md missing required section heading: {heading}")
if all(h in headings_seen for h in REQUIRED_HEADINGS):
    ok("BOARD.md has all required section headings")

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

for tid, t in tickets.items():
    if t["section"] == "## BLOCKED" and "blocker" not in t["fields"]:
        warn("blocked-no-blocker", f"BOARD.md:{t['line_no']} ticket {tid} is in "
             f"## BLOCKED with no | blocker: field -- facts + dead ends belong "
             f"on the ticket (RFC § 1.2)")
    if t["checkbox"] == "x" and t["section"] != "## DONE":
        warn("checkbox-section", f"BOARD.md:{t['line_no']} ticket {tid} is "
             f"checked [x] but sits under {t['section']} -- checkbox and "
             f"section disagree")
    if t["checkbox"] == "/" and t["section"] not in ("## DOING",):
        warn("checkbox-section", f"BOARD.md:{t['line_no']} ticket {tid} is [/] "
             f"in-progress but sits under {t['section']} -- in-progress work "
             f"belongs under ## DOING")

# ----------------------------------------------------------------------- LOG

log_path = Path(".saipen/LOG.md")
if log_path.is_file():
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
    for line_no, line in enumerate(log_path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        m = LOG_RE.match(line)
        if not m:
            fail(f"LOG.md:{line_no} violates the Event Graph skeleton "
                 f"(RFC § 1.2): {line[:100]!r}")
            log_ok = False
            continue
        eid, parent, ticket, taxonomy, content = m.groups()
        eid = int(eid)
        if eid in seen_ids:
            fail(f"LOG.md:{line_no} E-{eid:03d} reused (first at line "
                 f"{seen_ids[eid]}) -- Event IDs MUST be unique (RFC § 1.2)")
            log_ok = False
        elif eid < prev_id:
            fail(f"LOG.md:{line_no} E-{eid:03d} after E-{prev_id:03d} -- IDs MUST "
                 f"increase monotonically (RFC § 1.2)")
            log_ok = False
        seen_ids[eid] = line_no
        prev_id = max(prev_id, eid)
        if parent is not None and int(parent) not in seen_ids:
            fail(f"LOG.md:{line_no} parent E-{int(parent):03d} doesn't exist "
                 f"earlier in the file -- dangling parent breaks the graph "
                 f"Recovery depends on (RFC § 1.2)")
            log_ok = False
        # History is append-only and immutable -- style drift in old lines
        # can't be fixed without rewriting history, so it warns, not fails.
        if taxonomy not in ("RUN", "DEC", "H"):
            warn("log-taxonomy", f"LOG.md:{line_no} taxonomy {taxonomy!r} isn't "
                 f"RUN/DEC/H -- non-conformant for new entries (RFC § 1.2)")
        # T-none is a legal explicit no-ticket marker (RFC § 1.2, v7.24.0).
        if ticket is not None and ticket != "T-none" \
                and not re.fullmatch(r"T-\d+", ticket):
            warn("log-ticket-ref", f"LOG.md:{line_no} ticket ref [{ticket}] "
                 f"isn't numeric T-### or the literal T-none (RFC § 1.2)")
    if log_ok:
        ok("LOG.md format valid (skeleton, E-### unique + monotonic, parents resolve)")

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

# Only applies in the saipen repo's own clone root (fingerprint: saipen/RFC.md
# next to VERSION) -- a consuming project's .saipen/ never has that.
if Path("saipen/RFC.md").is_file() and Path("VERSION").is_file() and Path("README.md").is_file():
    repo_version = Path("VERSION").read_text(encoding="utf-8-sig").strip()
    if f"**v{repo_version}**" not in Path("README.md").read_text(encoding="utf-8-sig"):
        fail(f"README.md badge doesn't match VERSION ({repo_version}) -- "
             f"this has drifted before, update the badge")
    else:
        ok("README.md badge matches VERSION")

    # Distribution integrity -- the v7.22.3/v7.25.0 bug class, machine-checked.
    # Five separate times this repo promised a file in one place and never
    # wired its delivery in another; each was found by archaeology. These
    # three checks make the whole class a validator FAIL instead.

    # A. RFC's phase enum <-> phases/ docs, both directions.
    rfc_text = Path("saipen/RFC.md").read_text(encoding="utf-8-sig")
    enum_line = next((l for l in rfc_text.splitlines()
                      if l.startswith("**Phase enum**")), None)
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
        "saipen/SKILL.md", "saipen/UI.md", "saipen/STYLE.md",
        "tools/validate.py", "tools/install_hook.py", "tools/uninstall_hook.py",
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

    # C. Both injector scripts must actually distribute every runtime dir.
    dist_tokens = ["phases", "tools", "extensions/schemas",
                   "extensions/templates", "tests"]
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
        ok("injector distributes every runtime dir "
           "(phases/tools/tests/schemas/templates, both scripts)")

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
