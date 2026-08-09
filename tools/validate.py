#!/usr/bin/env python
"""saipen conformance validator (canonical).

Stdlib only -- no pip installs, ever. Run from anywhere inside the project,
or name the owning root explicitly:

    python <saipen-home>/tools/validate.py [--strict] [--project-root PATH]
                                           [--gate CONTEXT]

`--gate` names WHY the validator is running, because producer readiness and
Core conformance are different questions and one severity for both is what put
an unrelated Core commit behind regenerating every producer in the project:

    (omitted) / --gate core      Core/project structural conformance.
    --gate ship                  Everything needed to ship THIS tree safely.
                                 Unrelated producer readiness is NOT required.
    --gate collect:<producer>    That producer's OUTBOX must parse and be
                                 complete, ready, fresh, role-current and
                                 identity-verified. Other producers stay soft.
    --gate converge              Core plus CONVERGE.md stage M's fresh EE/QQ.

Under the soft gates a producer defect is a visible WARN naming the producer
and the gate that would fail it -- soft, never silent. The validator is
read-only under every gate: it never edits an OUTBOX into the shape it wanted
to find (T-568).

Covers every check tests/validate.sh / validate.ps1 perform (those two
are the frozen portable floor for hosts without Python -- new checks land
here only), plus checks the shell pair structurally can't do well:
E-### monotonicity/uniqueness, parent-reference resolution, ticket-line
grammar, unknown BOARD fields, UTC enforcement on `updated`.

STATE.md's shape is validated against extensions/schemas/state.schema.json
directly (required/enum/type/minimum/items subset of JSON Schema, interpreted
natively; `audit_schema_keywords` FAILs on any keyword the schema uses and no
enforcer here interprets, so the subset can never silently fall behind).
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

Guards rule: a check's red-test MUST break the BEHAVIOR, not the wording.
If the only way to make a check FAIL is to edit the text it greps, the check
tests the text and the thing it claims to protect is unprotected. Do not use
source-text assertions (e.g. naive string inclusion) to verify runtime logic.
"""

import datetime
from saipen_engine.phases import (ANY_FROM, TICKET_BEARING_PHASES,
                                  VALID_TRANSITIONS,
                                  transition_legal)
import hashlib
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from freshness import (FreshnessError, compute_generic_role_revision,
                       compute_role_revision,
                       compute_source_identity)
from userperson import validate_profile as _validate_userperson_profile
from improve import validate_report as _validate_improve_report
# NITRO M1: the shared mechanical parsers. validate.py and the engine consume
# the SAME implementation by construction -- no parser drift (T-578).
from saipen_engine.board import TICKET_RE
from saipen_engine.log import LOG_RE
from saipen_engine.state import parse_frontmatter

def _read_rfc(p):
    core = p.parent / "CORE.md"
    maint = p.parent / "MAINTENANCE.md"
    if core.is_file() and maint.is_file():
        return core.read_text(encoding="utf-8-sig") + "\n" + maint.read_text(encoding="utf-8-sig")
    return p.read_text(encoding="utf-8-sig")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

USE_COLOR = sys.stdout.isatty()

# extensions/subs/PROTOCOL.md § 2 status table -- the normative list for
# the extension (RFC § 1.9). Named rather than inlined so the cross-doc
# check can compare it against the table and the schema enum.
OUTBOX_STATUSES = ("ready", "draft", "blocked", "reviewed", "stale")

# The SAIPEN home this file ships from, derived from its own location rather
# than from cwd -- the validator runs inside a consuming project, where cwd is
# that project and the protocol lives elsewhere. Declared up here with the
# other constants because it was computed 1700 lines down, beside its first
# consumer, and the fourth use-before-define NameError of this session was a
# check spliced above that line. tools/audit_order.py caught this one.
_tools_parent = Path(__file__).resolve().parent.parent

# RFC § 1.2's voice marker. `last_event` is checkable because its value comes
# from evidence living OUTSIDE STATE.md; the caveman-дед contract had no such
# value, which made "read STYLE.md before any output" the one boot MUST no
# artifact could witness -- a live DeepSeek session read BOOT.md, RFC.md and
# the phase docs and never opened STYLE.md at all. T-404 and T-405 removed the
# contradiction that permitted it; neither could prove the read afterwards,
# because a read leaves no trace. This does not prove it either -- nothing
# can -- it removes the silence: the duty now has a value attached, and a
# value can be wrong out loud. Derived from STYLE.md's own text so it cannot
# be memorized once and reused after the contract changes, and declared in
# STYLE.md alone so that copying it IS opening the file.
_STYLE_TOKEN_RE = re.compile(r"`style_contract:\s*(ded-[0-9a-f]{8})`")
# STYLE.md's reply-language setting. Closed on purpose: the whole point of
# replacing a precedence rule with a knob is that the knob has no room for
# interpretation, and an open set would put the reasoning right back.
REPLY_LANGUAGES = ("et", "en", "ru", "auto")
_STYLE_LEAK_DOCS = ("RFC.md", "BOOT.md", "SKILL.md", "UI.md", "CONFORMANCE.md")


def home_doc(name):
    """A shipped protocol doc, in either layout SAIPEN is ever installed as.

    The repository keeps them under `saipen/`; `bootstrap/inject.*` flattens
    that folder into the skill root, so an installed validator resolving only
    the repository shape finds nothing. The 13h contract checks quietly SKIP
    a missing file and were therefore vacuous in every install; this one
    FAILs, and would have turned every injected install red.
    """
    for candidate in (_tools_parent / "saipen" / name, _tools_parent / name):
        if candidate.is_file():
            return candidate
    return None


def style_contract_token(text):
    """STYLE.md's marker token, computed from the file minus its own claim.

    The declaration line is excluded so the token is a function of the
    contract, not of itself -- including it would make every value
    self-invalidating and no value ever reachable.
    """
    body = "\n".join(ln for ln in text.replace("\r\n", "\n").split("\n")
                     if "style_contract:" not in ln).strip()
    return "ded-" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]


def _parse_gate(raw):
    """Validate a --gate value, returning (kind, producer-or-None).

    Closed set, no guessing: an unrecognized gate exits 2 rather than falling
    back to the default, because a typo'd `--gate collect:saiwki` that silently
    ran the SOFT gate would report green on exactly the package the caller
    asked to hard-check. Failing loudly on the spelling is the only reading
    that cannot approve an uninspected package."""
    if raw in ("ship", "converge", "core"):
        return raw, None
    if raw.startswith("collect:"):
        producer = raw.split(":", 1)[1]
        if re.fullmatch(r"[a-z][a-z0-9_-]*", producer or ""):
            return "collect", producer
        print(f"FAIL: --gate collect:<producer> needs a producer name, got "
              f"{producer!r}")
        sys.exit(2)
    print(f"FAIL: unknown --gate {raw!r} -- one of: core (default), ship, "
          f"collect:<producer>, converge")
    sys.exit(2)


def _parse_cli(argv):
    strict = False
    project_root = None
    gate, gate_producer = "core", None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--strict":
            strict = True
        elif arg == "--project-root":
            i += 1
            if i >= len(argv):
                print("FAIL: --project-root requires a path")
                sys.exit(2)
            project_root = argv[i]
        elif arg.startswith("--project-root="):
            project_root = arg.split("=", 1)[1]
            if not project_root:
                print("FAIL: --project-root requires a path")
                sys.exit(2)
        elif arg == "--gate":
            i += 1
            if i >= len(argv):
                print("FAIL: --gate requires a context")
                sys.exit(2)
            gate, gate_producer = _parse_gate(argv[i])
        elif arg.startswith("--gate="):
            gate, gate_producer = _parse_gate(arg.split("=", 1)[1])
        else:
            print(f"FAIL: unknown argument: {arg}")
            sys.exit(2)
        i += 1
    return strict, project_root, gate, gate_producer


def _git_from(cwd, *args):
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            check=False)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return result.returncode, result.stdout.strip()


def _nearest_checkpoint_root(start):
    for candidate in (start, *start.parents):
        if (candidate / ".saipen").is_dir():
            return candidate
    return None


def _resolve_project_root(start, explicit):
    """Resolve the one root whose checkpoint files this run may inspect.

    Explicit selection is intentional and therefore overrides cwd. Implicit
    Git selection follows the common directory so a linked worktree reaches
    the main worktree's gitignored `.saipen/` instead of inventing a second
    one. Non-Git projects use the nearest ancestor carrying `.saipen/`;
    validation separately diagnoses a missing or corrupt STATE.md there.
    """
    if explicit is not None:
        root = Path(explicit).expanduser()
        if not root.is_absolute():
            root = start / root
        root = root.resolve()
        if not root.is_dir():
            return None, "explicit --project-root is not a directory: " + str(root)
        if not (root / ".saipen").is_dir():
            return None, ("explicit --project-root has no .saipen/ directory: "
                          + str(root))
        return root, "explicit"

    rc, top_text = _git_from(start, "rev-parse", "--show-toplevel")
    if rc == 0 and top_text:
        worktree_root = Path(top_text).resolve()
        common_rc, common_text = _git_from(start, "rev-parse", "--git-common-dir")
        candidates = []
        if common_rc == 0 and common_text:
            common_dir = Path(common_text)
            if not common_dir.is_absolute():
                common_dir = start / common_dir
            common_dir = common_dir.resolve()
        # The ACTIVE worktree is asked first, the main worktree second. A
        # linked worktree normally has no `.saipen/` of its own -- the folder
        # is gitignored, so a fresh one starts without it -- and that common
        # case still falls through to the shared state below. But when a
        # linked worktree DOES carry one, somebody put it there deliberately,
        # and asking git-common first meant the validator read a different
        # tree than the agent was editing: a linked worktree whose local
        # STATE.md said `phase: NOT-A-PHASE` validated EXIT=0, reporting the
        # main repository. Green for the wrong tree is the one answer this
        # resolver must never give.
        candidates.append((worktree_root, "git-worktree"))
        if common_rc == 0 and common_text:
            if common_dir.name.lower() == ".git":
                candidates.append((common_dir.parent, "git-common"))
        seen = set()
        for root, source in candidates:
            key = os.path.normcase(str(root))
            if key in seen:
                continue
            seen.add(key)
            if (root / ".saipen").is_dir():
                return root, source
        return None, ("cwd belongs to Git worktree " + str(worktree_root)
                      + " but its owning repository has no .saipen/; "
                      "refusing to guess or create a second .saipen/. Run from "
                      "the intended project or pass --project-root PATH")

    root = _nearest_checkpoint_root(start)
    if root is not None:
        return root, "ancestor"
    return None, ("cwd has no owning .saipen/; refusing to guess or "
                  "create one. Run from the intended project or pass "
                  "--project-root PATH")


STRICT, _requested_root, GATE, GATE_PRODUCER = _parse_cli(sys.argv[1:])
PROJECT_ROOT, PROJECT_ROOT_SOURCE = _resolve_project_root(
    Path.cwd().resolve(), _requested_root)
if PROJECT_ROOT is None:
    print(f"FAIL: {PROJECT_ROOT_SOURCE}")
    sys.exit(1)
os.chdir(PROJECT_ROOT)


def _git(*args):
    """Run git, returning (returncode, stdout). Never raises: this file runs
    from a pre-commit hook and in projects that are not repositories at all."""
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True,
                           check=False)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return r.returncode, r.stdout


# Git object-ID lengths: 40 hex for SHA-1, 64 for SHA-256 (`git init
# --object-format=sha256`, stable since 2.42). Abbreviations run from Git's own
# 4-character floor upward. The old `[0-9a-f]{7,40}` pattern was wrong at BOTH
# ends: it could not match a SHA-256 repository's OIDs, and being unanchored it
# did not simply skip them -- it matched the first 40 characters of a 64-hex OID
# and handed a truncated string to a comparison that then read as a DIFFERENT
# commit. Silent truncation is worse than no match (T-566).
OID_RE = r"[0-9a-f]{4,64}"


def canonical_commit(ref):
    """Resolve a commit reference to its full OID, or None if it does not resolve.

    Two references to one commit at different abbreviation lengths are the same
    commit, and only Git can say so: `b8b086d` and `b8b086d6cf9b...` compare
    unequal as strings, and `startswith` gets the common case right while
    quietly accepting a 7-character prefix that resolves to nothing, or to a
    different object in a repository large enough to collide at that length.
    Both readings were live in the ccc ship-HEAD proof -- the equality rung
    concluded the revision HAD changed whenever the LOG abbreviated it, which is
    exactly backwards: the check exists to catch a SHIP that changed nothing.

    Returns None rather than raising, and callers MUST treat None as evidence
    that does not resolve (a FAIL), never as "unknown, carry on" -- an
    unresolvable reference is precisely the state this proof must reject.
    """
    if not ref or not re.fullmatch(OID_RE, ref):
        return None
    # `^{commit}` makes the resolution type-exact: a tag or tree whose name
    # happens to abbreviate the same way is not a commit and must not pass.
    rc, out = _git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if rc != 0:
        return None
    resolved = out.strip()
    return resolved if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", resolved) else None


# RFC § 1.10's closed command list. Was a local inside Core's own next_action
# branch, so it existed only when Core's next_action happened to start with
# "saipen " -- the moment the subSaipen check reused it against a Core state
# that said WAIT, it was simply not defined. A vocabulary two checks share is
# a module constant, not a variable one of them happens to have built.
SAIPEN_COMMANDS = frozenset({
    "set", "init", "continue", "goal", "plan", "clean", "translate",
    "markhunt", "prepare", "collect", "ship", "validate", "test", "status",
    "stop", "sub", "hunt", "crew", "userperson", "improve"})
# RFC § 1.2: `PHASE <phase-enum> [T-###]` takes the ticket ref for exactly the
# five ticket-bearing phases and omits it for every other one. The rule had no
# witness, and the constitution's own worked example (§ 2.2, translating ADD's
# RETURN) wrote `PHASE PLAN T-###` -- the form the rule forbids, in the one
# place § 1.2 warns about by name: "an example that fails the rule below is
# worse than no example". Deliberately a hand-kept constant plus a drift check
# against § 1.2's sentence, the same shape the phase enum uses.

_PHASE_NA_RE = re.compile(
    r"^PHASE\s+([A-Za-z_-]+)(?:\s+(T-\d+))?(?:\s+\[[^\]]*\])?\s*$")


def _phase_next_action_error(value):
    """RFC § 1.2's `PHASE` pairing rule, or None when the value obeys it.

    Shared by Core and subSaipen states on purpose: the protocol has twice
    shipped a rule enforced on only one of the two, in both directions.
    """
    m = _PHASE_NA_RE.match(value.strip())
    if not m:
        return (f"{value!r} is not a legal `PHASE <phase-enum> [T-###]` -- "
                f"the argument is one uppercase phase plus at most a ticket "
                f"ref, and nothing but the optional [...] progress tag may "
                f"follow it")
    ph, ref = m.group(1), m.group(2)
    if ph != ph.upper():
        return (f"{value!r} writes the phase in lower case -- RFC § 1.2 takes "
                f"the uppercase § 1.6 enum value, and the phase doc is loaded "
                f"from its lowercased name, not from what the state says")
    _five = "/".join(sorted(TICKET_BEARING_PHASES))
    if ph in TICKET_BEARING_PHASES and not ref:
        return (f"{value!r} enters ticket-bearing phase {ph} with no T-### -- "
                f"RFC § 1.2 REQUIRES the ref for {_five}, and a cold agent "
                f"cannot act on a phase with no subject")
    if ph not in TICKET_BEARING_PHASES and ref:
        return (f"{value!r} attaches {ref} to {ph}, which is not one of the "
                f"five ticket-bearing phases ({_five}) -- RFC § 1.2 omits the "
                f"ref for every other phase; name the ticket in `task:`")
    return None
EXPECTED_SHORTCUT_ROUTES = {
    "gg": "`saipen goal`",
    "hh": "`saipen hunt`",
    "cc": "`saipen continue`",
    "ccc": "`saipen continue` with `converge_target: ship`, then `saipen ship`, then stages J-M",
    "ss": "`saipen stop`",
    "sss": "`saipen status`",
    "dd": "`saipen plan`",
    "aa": "`saipen markhunt`",
    "qq": "`saipen prepare saiwiki`",
    "qqq": "`saipen collect saiwiki` then `saipen ship`",
    "ee": "`saipen prepare saitranslate`",
    "eee": "`saipen collect saitranslate` then `saipen ship`",
    "pp": "`saipen sub spawn saipython`",
    "tt": "`saipen test`",
    "sc": "`saipen crew`",
}
PACKAGE_HANDOFF_FIELDS = {
    "status", "producer", "source_head", "source_tree_fingerprint",
    "role_revision", "coverage", "payload", "verified", "instructions",
}
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

# parse_frontmatter and coerce moved to saipen_engine/state (NITRO M1); this
# validator imports them so the two can never drift.

TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
}


# Every JSON Schema keyword this file is allowed to meet, and who enforces it.
# The three sets are exhaustive by construction: `audit_schema_keywords` below
# FAILs on anything outside their union, so a keyword added to a schema without
# an enforcer can never again be interpreted as satisfied. That silent-skip is
# what T-565 closed -- `minimum` sat in state.schema.json on four fields while
# the docstring here said the interpreted subset "is everything the schema
# actually uses", so `goal_waves: -1` passed the gate and handed the § 2.4
# safety valve a budget below its own floor.
SCHEMA_KEYWORDS_ENFORCED = frozenset({"type", "enum", "minimum", "items"})
# Annotations. They constrain nothing, so nothing needs to enforce them.
# `default` is deliberately here: JSON Schema `default` is documentation of an
# omitted value, never an instruction to supply one, and a validator that
# "applied" it would be inventing state nobody wrote.
SCHEMA_KEYWORDS_ANNOTATION = frozenset({"description", "default", "title",
                                        "$schema", "x-current-schema-version"})
# Structural keywords: they carry subschemas rather than constraints, so the
# walk descends through them instead of demanding an enforcer for them.
SCHEMA_KEYWORDS_STRUCTURAL = frozenset({"properties"})
# Enforced by a DEDICATED check elsewhere in this file, each mapped to the rule
# that owns it. An entry here is a claim that a stricter or more specific check
# exists, and it is deliberately NOT machine-verified: the only mechanical proof
# available would assert on this file's own source text, which this module's
# Guards rule rejects outright. What the audit guarantees is narrower and still
# worth having -- a keyword can never be *silently* unenforced, only explicitly
# delegated by someone who had to name its owner to get past the gate.
SCHEMA_KEYWORDS_DELEGATED = {
    # `format: date-time` would accept a local-time stamp. RFC § 1.2 requires
    # UTC specifically, so the dedicated check below is the stricter one.
    "format": "STATE.md `updated` ISO-8601 UTC check (RFC § 1.2)",
    # Top-level `if`/`then` expresses "goal counters required under
    # execution_intent: goal". Enforced by the § 2.4 counter check, which also
    # owns the cap/trip semantics a generic reading could not express.
    "if": "execution_intent: goal counter presence (RFC § 2.4)",
    "then": "execution_intent: goal counter presence (RFC § 2.4)",
    # additionalProperties: false is enforced unconditionally below -- an
    # unknown field is always a FAIL, never a branch on this keyword.
    "additionalProperties": "unknown-field FAIL in check_against_schema",
    # The required array is read directly by check_against_schema.
    "required": "required-field FAIL in check_against_schema",
}


def audit_schema_keywords(schema, label):
    """FAIL on any JSON Schema keyword no enforcer in this file interprets.

    Runs once against the SCHEMA, not against an instance: the subject is a
    static artifact, so auditing it per instance would only repeat one answer.
    Without this, extending a schema is silently a no-op for the validator --
    the failure mode is invisible precisely because nothing complains."""
    known = (SCHEMA_KEYWORDS_ENFORCED | SCHEMA_KEYWORDS_ANNOTATION
             | frozenset(SCHEMA_KEYWORDS_DELEGATED))
    unknown = []

    def visit(node, where):
        if not isinstance(node, dict):
            return
        # A keyword having an enforcer is only half the guarantee: `type` is
        # enforced through TYPE_CHECKS, which knows four of JSON Schema's seven
        # types, so `type: number` would pass the keyword audit and still be
        # interpreted by nobody. The VALUE has to be in range too. `object` is
        # the one exemption, and only at the top level, where the instance is a
        # parsed frontmatter mapping by construction -- there is no other value
        # parse_frontmatter can return.
        _t = node.get("type")
        if isinstance(_t, str) and _t not in TYPE_CHECKS \
                and not (_t == "object" and not where):
            unknown.append((where, f"type: {_t}"))
        for kw, sub in node.items():
            if kw in SCHEMA_KEYWORDS_STRUCTURAL:
                # A `properties` map's KEYS are field names, never keywords.
                for name, spec in (sub or {}).items():
                    visit(spec, f"{where}.{name}" if where else name)
                continue
            if kw not in known:
                unknown.append((where, kw))
            elif kw == "items":
                # `items` holds a subschema whose own keywords need enforcers.
                visit(sub, f"{where}[]" if where else "[]")
            # `if`/`then` are delegated as ONE unit to the § 2.4 counter check,
            # which owns the whole conditional. Descending into them would
            # demand an enforcer for `const`, a keyword this validator never
            # interprets on its own and never needs to.

    visit(schema, "")
    if unknown:
        for where, kw in unknown:
            fail(f"{label} declares {kw!r}"
                 f"{f' on field {where}' if where else ' at the top level'} "
                 f"that tools/validate.py does not interpret -- the schema "
                 f"believes it constrains something the gate never checks. "
                 f"Implement it in check_against_schema, or map it to the "
                 f"dedicated check that owns it in SCHEMA_KEYWORDS_DELEGATED")
    else:
        ok(f"{label} states nothing the validator ignores "
           f"({len(SCHEMA_KEYWORDS_ENFORCED)} keywords enforced natively, "
           f"{len(SCHEMA_KEYWORDS_DELEGATED)} delegated, "
           f"{len(TYPE_CHECKS)} types interpreted)")


def check_against_schema(fields, schema, label):
    """Interpret the required/enum/type/minimum/items/additionalProperties subset
    of JSON Schema. `audit_schema_keywords` proves that subset still covers every
    keyword the schema uses -- extending one without the other is a FAIL, not a
    silent skip."""
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
        # `minimum` gates the floor of every counter STATE persists. Unenforced,
        # `goal_waves: -1` reads as valid and hands § 2.4's safety valve four
        # waves of budget instead of three; `last_event: 0` claims a LOG event
        # that cannot exist, which is the number § 1.5 Recovery replays from.
        # Booleans are excluded because Python orders True above 0 and a
        # boolean in an integer field is already a type FAIL above -- comparing
        # it again would report the same defect twice under two names.
        if "minimum" in spec and isinstance(value, (int, float)) \
                and not isinstance(value, bool) and value < spec["minimum"]:
            fail(f"{label} field {key}: {value!r} is below the schema minimum "
                 f"{spec['minimum']}")
        # Array element types. `requires:` is the § 1.3 capability handshake,
        # and the vocabulary check below skips non-strings silently, so an
        # element of the wrong type was invisible at both rungs.
        if "items" in spec and isinstance(value, list):
            item_type = (spec["items"] or {}).get("type")
            if item_type in TYPE_CHECKS:
                for idx, item in enumerate(value):
                    if not TYPE_CHECKS[item_type](item):
                        fail(f"{label} field {key}[{idx}]: expected "
                             f"{item_type}, got {type(item).__name__} "
                             f"({item!r})")


# --------------------------------------------------------------------- STATE

print(color("36", "saipen conformance validation starting (tools/validate.py)..."))
print(f"Project root: {PROJECT_ROOT} ({PROJECT_ROOT_SOURCE})")

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
CURRENT_SCHEMA_VERSION = schema.get("x-current-schema-version")
if not isinstance(CURRENT_SCHEMA_VERSION, int) or CURRENT_SCHEMA_VERSION < 1:
    fail("state.schema.json x-current-schema-version must be a positive integer")
    sys.exit(1)

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

# STATE.md must end in a newline. A file whose last byte is not `\n` fails
# the "read to the end" contract: an append that lands mid-line extends the
# frontmatter fence instead of adding a new key, and the portable grep floor
# matches nothing past the last line break. (Blind-spot fixture 11.)
_state_raw = state_path.read_bytes()
if _state_raw and not _state_raw.endswith(b"\n"):
    fail("STATE.md does not end in a newline -- a later append would extend "
         "the last line instead of adding one, and the portable floor's "
         "line-based greps would miss the final field. Add the trailing "
         "newline at the next checkpoint")

# Only root VERSION may exist. A nested duplicate under saipen/ (the
# protocol home) is a second version source that two checks would disagree
# about (goal blind spot 8).
if Path("saipen").is_dir():
    _dup_version = Path("saipen/VERSION")
    if _dup_version.is_file():
        fail("saipen/VERSION is a nested duplicate of the root VERSION file -- "
             "one version source means one file. Delete the nested copy; the "
             "root VERSION is canonical")

state, err = parse_frontmatter(read_doc(state_path))
if state is None:
    fail(f"STATE.md frontmatter: {err}")
    sys.exit(1)

audit_schema_keywords(schema, "state.schema.json")

before = len(failures)
check_against_schema(state, schema, "STATE.md")

# RFC § 2.4: ONE canonical persisted execution-intent enum. The
# legacy `goal_mode` boolean stays READ-compatible during migration only: it
# maps deterministically (true -> goal, false -> normal) and MUST be dropped
# at the next checkpoint. A state carrying BOTH fields is corrupt -- after the
# first canonical checkpoint there is exactly one source of truth. All later
# checks read the effective intent from `state["execution_intent"]`.
_INTENT_VALUES = ("normal", "goal", "converge")
if "execution_intent" in state and "goal_mode" in state:
    fail("STATE.md carries BOTH execution_intent and legacy goal_mode -- "
         "after migration there is exactly one source of truth; the next "
         "checkpoint MUST drop goal_mode for execution_intent (RFC § 2.4)")
elif "goal_mode" in state:
    _legacy_intent = "goal" if state.get("goal_mode") is True else "normal"
    if _legacy_intent == "goal":
        warn("goal-mode-legacy",
             "STATE.md still carries legacy goal_mode: true -- readable and "
             "migrated to execution_intent: goal, but the next checkpoint "
             "MUST drop goal_mode (RFC § 2.4)")
    state["execution_intent"] = _legacy_intent
    state.pop("goal_mode", None)
elif "execution_intent" not in state:
    state["execution_intent"] = "normal"
intent = state.get("execution_intent", "normal")
if intent not in _INTENT_VALUES:
    fail(f"STATE.md execution_intent is {intent!r} -- the closed set is "
         f"normal/goal/converge (RFC § 2.4)")
converge_target = state.get("converge_target")
if converge_target is not None and intent != "converge":
    fail(f"STATE.md converge_target is {converge_target!r} while "
         f"execution_intent is {intent!r} -- the ccc routing discriminator "
         "exists only during convergence")

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
# RFC § 1.2's fixed WAIT wordings for `phase: DONE`. Three of them, and
# the count lives in § 1.2 alone -- the MARKHUNT brake was added as a third
# after both phase docs had stated it for releases while this file carved it
# out of one check and not the other, so a doc-following agent produced a
# state one half of the tool called drift.
def _done_wait_whitelisted(value):
    low = value.lower()
    return ("safety valve" in low
            or low.startswith("wait: user brake")
            or "untriaged markhunt findings" in low)


_na_done = state.get("next_action", "") if isinstance(
    state.get("next_action"), str) else ""
if state.get("phase") == "DONE" and _na_done.startswith("WAIT:") \
        and not _done_wait_whitelisted(_na_done):
    warn("done-wait", "STATE.md phase: DONE but next_action is WAIT -- "
         "DONE with WAIT is legal only for the § 2.4 safety valve, "
         "'WAIT: user brake -- <reason>', or the untriaged-MARKHUNT "
         "brake (RFC § 1.2); otherwise DONE "
         "should transition to SCOUT/PLAN/HUNT per RFC § 1.6 / § 2.1")

# Hard invariant: intent != goal -> goal_waves/goal_tickets MUST be absent.
if intent != "goal":
    for counter in ("goal_waves", "goal_tickets"):
        if counter in state and state[counter] is not None:
            fail(f"STATE.md execution_intent: {intent} but {counter} is present "
                 f"({state[counter]!r}) -- counters MUST be cleared when no "
                 f"goal is running (RFC § 2.4 Exit)")

# RFC § 1.7's bootloader pointer has to survive being parsed, and this file
# is the wrong judge of that: `parse_frontmatter` above reads the YAML SUBSET
# STATE.md uses, strips quotes, and never processes escape sequences -- so a
# corrupted pointer looks perfect to every check here while a real YAML reader
# sees something else entirely. `"V:\___VAC\__K"` written with single
# backslashes parses, in PyYAML, to a value where each separator became
# U+00A0 -- five path separators eaten as escapes. It shipped that way
# through three releases because the schema types the field `string` and
# corruption is a string, and because the validator is more permissive than
# the format it claims to validate. So check the escaping rule itself, with no
# parser and no dependency: inside a double-quoted scalar, a backslash only
# ever legally introduces another backslash or one of YAML's escape letters.
# In a PATH the only defensible escape is a doubled backslash. `\_` is a
# perfectly legal YAML escape -- it yields U+00A0 -- which is precisely how
# this corruption passed for three releases: legal, and wrong.
for _key in ("saipen_home",):
    _raw = next((ln for ln in read_doc(state_path).splitlines()
                 if ln.startswith(f"{_key}:")), None)
    if _raw is None or '"' not in _raw:
        continue
    _body = _raw[_raw.index('"') + 1:_raw.rindex('"')]
    _bad, _i = [], 0
    while _i < len(_body):
        if _body[_i] == "\\":
            _nxt = _body[_i + 1] if _i + 1 < len(_body) else ""
            if _nxt != "\\":
                _bad.append("\\" + _nxt)
            _i += 2
        else:
            _i += 1
    if _bad:
        fail(f"STATE.md {_key} is a double-quoted scalar whose backslashes are "
             f"not escaped ({', '.join(_bad[:4])}) -- a YAML reader consumes "
             f"each as an escape sequence, so RFC § 1.7's bootloader pointer "
             f"resolves to a path that cannot exist. This file's own subset "
             f"parser cannot see it: double every backslash inside the quotes")

# schema_version is the migration boundary for checkpoint semantics. Absence
# and v1 remain readable so installing a newer SAIPEN cannot trap an existing
# project. The next checkpoint upgrades them to v2, whose `last_event` marker
# makes STATE the checkable commit pointer promised by RFC section 1.5.
sv = state.get("schema_version")
if sv is None:
    warn("schema-version",
         "STATE.md has no schema_version -- legacy pre-v1 format. "
         f"At the next checkpoint set schema_version: {CURRENT_SCHEMA_VERSION}, "
         "last_event to the current LOG tail (omit last_event only while LOG "
         "is empty), and style_contract to saipen/STYLE.md's boot marker.")
elif not isinstance(sv, int) or sv < 1:
    fail(f"STATE.md schema_version is {sv!r}, expected a positive integer")
elif sv < CURRENT_SCHEMA_VERSION:
    warn("schema-version",
         f"STATE.md schema_version is legacy v{sv}. At the next checkpoint "
         f"set schema_version: {CURRENT_SCHEMA_VERSION}, last_event to the "
         "current LOG tail (omit last_event only while LOG is empty), and "
         "style_contract to saipen/STYLE.md's boot marker.")
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

# The voice marker, gated exactly the way `last_event` is: REQUIRED once the
# state is at the current revision, exempt while it is readable legacy, and
# always enforced when present. A missing STYLE.md fails loud instead of
# passing vacuously -- a marker check that cannot reach its own source of
# truth is the same "check reporting on data it cannot evaluate" defect the
# schema-version block above names.
_STYLE_PATH = home_doc("STYLE.md")
if _STYLE_PATH is None:
    fail(f"STYLE.md not found under {_tools_parent} -- the chat-voice "
         f"contract has no source of truth on this install, so STATE.md's "
         f"style_contract marker cannot be checked at all (RFC § 1.2)")
else:
    _style_text = _STYLE_PATH.read_text(encoding="utf-8-sig")
    _style_expected = style_contract_token(_style_text)
    _style_declared = _STYLE_TOKEN_RE.findall(_style_text)
    if len(_style_declared) != 1:
        fail(f"{_STYLE_PATH.name} declares {len(_style_declared)} boot markers, "
             f"expected exactly one line reading `style_contract: "
             f"{_style_expected}` -- zero leaves every checkpoint with nothing "
             f"to copy, two leaves it a choice (RFC § 1.2)")
    elif _style_declared[0] != _style_expected:
        fail(f"{_STYLE_PATH.name} declares style_contract "
             f"{_style_declared[0]} but its text hashes to {_style_expected} "
             f"-- the contract changed and its marker did not, so every state "
             f"carrying the old value would validate against a voice nobody "
             f"is bound by. Set the declaration to {_style_expected}")
    # The token is worth something only while STYLE.md is the sole place to
    # find it: a value reachable from BOOT.md is copyable by an agent that
    # never opened the contract, which is precisely the session this ticket
    # exists to catch.
    _style_leaks = [
        _n for _n in _STYLE_LEAK_DOCS
        if home_doc(_n) is not None
        and _style_expected in home_doc(_n).read_text(encoding="utf-8-sig")
    ]
    if _style_leaks:
        fail(", ".join(_style_leaks) + " carries STYLE.md's "
             f"marker value {_style_expected}; it MUST appear in STYLE.md "
             f"alone, or the checkpoint can copy it without ever reading the "
             f"contract it stands for (RFC § 1.2)")
    _sc = state.get("style_contract")
    if sv == CURRENT_SCHEMA_VERSION and _sc is None:
        fail(f"STATE.md schema_version {CURRENT_SCHEMA_VERSION} requires "
             f"style_contract: {_style_expected} -- RFC § 1.2's voice marker, "
             f"declared at the top of saipen/STYLE.md. Legacy states below "
             f"v{CURRENT_SCHEMA_VERSION} may omit it only until their next "
             f"checkpoint (RFC § 1.2, § 1.5)")
    elif _sc is not None and _sc != _style_expected:
        fail(f"STATE.md style_contract is {_sc!r} but the installed STYLE.md's "
             f"marker is {_style_expected} -- this checkpoint was written "
             f"against a different voice contract than the one installed, so "
             f"the agent that wrote it did not read the current STYLE.md "
             f"(RFC § 1.2)")

# RFC § 1.6 phase transition validation. transition_from tracks the
# previous phase; check every non-self transition against the table.

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
        # The category bounds what KIND of stop this is; nothing bounded what
        # came after it, so `next_action` became a scratchpad -- and a stop
        # instruction carrying notes is one the next agent reads as a queue.
        # Live on this repository: a `user brake` whose body ran three
        # sentences of handoff status and ended by naming a ticket as still
        # open "for a future run", after which the next agent scouted that
        # ticket instead of honouring the brake. One sentence. The boundary is
        # a period followed by whitespace and then a capital or a backtick, so
        # a version string (`v7.176.0`) and a lowercase "e.g." do not trip it,
        # while a genuine second sentence does. The trailing `[...]` progress
        # tag § 1.2 permits is stripped first -- it is not prose.
        _wait_body = re.sub(r"\s*\[[^\]]*\]\s*$", "",
                            next_action[len("WAIT:"):].strip())
        _second = re.search(r"\.\s+(?=[A-Z`])", _wait_body)
        if _second:
            fail(f"STATE.md next_action is a WAIT whose body starts a second "
                 f"sentence at offset {_second.start()} -- RFC § 1.2 bounds it "
                 f"to one. Session status belongs in "
                 f".saipen/kitchen/digest.md and queued work belongs on "
                 f"BOARD.md; a stop instruction carrying either is one the "
                 f"next agent executes as a work queue: {next_action!r}")

    if "?" in next_action and not next_action.startswith("WAIT:"):
        fail(f"STATE.md next_action asks a question outside WAIT:: "
             f"{next_action!r} (RFC § 1.2)")
    # The prefix check above proves the shape, not the vocabulary: "saipen
    # refactor" passes it while naming a command RFC 1.10 does not define,
    # and a cold agent is then required to decline it and stop -- TEST-001 failing
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

    if next_action.startswith("PHASE "):
        _phase_err = _phase_next_action_error(next_action)
        if _phase_err:
            fail(f"STATE.md next_action {_phase_err}")

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

# RFC § 1.4: `agent:` names the seat and is inherited, never invented. Every
# concurrency rule in that section compares it against "itself", and a
# placeholder makes both sides meaningless -- one reached this repository's own
# LOG reading `[agent: id]`. The stability rule itself is behavioural (nothing
# here can tell a genuine handover from a renamed seat), but a placeholder is
# mechanical and is the shape that actually escapes.
AGENT_PLACEHOLDERS = ("id", "<name>", "agentid", "unknown", "agent", "name",
                      "todo", "tbd", "your-agent-id", "<agent>", "none")
# A seat is the tool driving the project, and RFC 1.4 derives it from the
# agent home the protocol was loaded from. A MODEL name is the thing that
# changes underneath that seat, so a value carrying one is a renamed seat by
# construction -- the false alarm 1.4 names, where the next session sees a
# stranger because the model was upgraded. This repository's own history
# carries `claude-opus`, `claude-sonnet-5`, `gemini-pro` and
# `antigravity-gemini` for what were two actors. Closed list, extended
# deliberately rather than guessed from shape: matching on digits or hyphens
# would fail ordinary tool names.
MODEL_TOKENS = ("opus", "sonnet", "haiku", "gpt", "gemini", "llama",
                "deepseek", "flash", "mistral", "qwen", "grok", "turbo",
                "4o", "o1", "o3")
# `none` was the one placeholder shaped like a real answer. `phases/init.md`
# and the shipped template both ORDERED it, so every project ever bootstrapped
# was born with an identity § 1.4 cannot compare -- and unlike `<name>` it
# reads as a deliberate value rather than as a slot nobody filled. INIT is
# executed by a real agent, so the first canonical checkpoint records that
# agent's seat; an English sentinel is not a third state with defined
# comparison semantics, it is an undefined one wearing a word.
_ag = state.get("agent")
if isinstance(_ag, str) and _ag.strip().lower() in AGENT_PLACEHOLDERS:
    fail(f"STATE.md agent is {_ag!r} -- a placeholder, not a seat name. RFC "
         f"§ 1.4 compares this field against itself to decide whether another "
         f"agent is live, and a placeholder makes that comparison meaningless "
         f"in both directions")
_ag_tok = [m for m in MODEL_TOKENS
           if isinstance(_ag, str) and m in _ag.strip().lower()]
if _ag_tok:
    fail(f"STATE.md agent is {_ag!r}, which carries the model token "
         f"{_ag_tok[0]!r} -- RFC 1.4 makes the seat the agent home the "
         f"protocol was loaded from (`.claude` -> `claude`), not the model "
         f"build running in it. A model name renames the seat on every "
         f"upgrade, which is the false alarm that check exists to prevent")

# RFC § 2.4 safety-valve ceilings. Named rather than inlined so the trip check
# below and any future reader see the same two numbers the RFC states.
GOAL_WAVE_CAP = 3
GOAL_TICKET_CAP = 20
# T-401: releases a WARN slug must survive before it needs a live owner ticket.
# The baseline's first/last seen fields are the age data; a slug still emitted
# after this many consecutive releases MUST be named by a live BOARD ticket.
WARN_OWNER_SPAN = 3

# RFC § 2.4: execution_intent: goal requires both persisted counters.
if intent == "goal":
    missing_counters = [c for c in ("goal_waves", "goal_tickets")
                        if not TYPE_CHECKS["integer"](state.get(c))]
    for counter in missing_counters:
        fail(f"execution_intent: goal but {counter} counter missing -- safety "
             f"valve can't survive a restart without it (RFC § 2.4)")
    if not missing_counters:
        ok("goal execution_intent counters present")

        # RFC § 2.4: intent=goal with a counter at or over its cap IS the
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
                fail(f"execution_intent: goal with goal_waves={waves}/"
                     f"goal_tickets={ticks} is the tripped safety valve "
                     f"(caps {GOAL_WAVE_CAP}/{GOAL_TICKET_CAP}), but "
                 f"next_action={na!r} -- RFC § 2.4 requires "
                 f"next_action: WAIT: safety valve reached (N waves / "
                 f"M tickets) -- run 'saipen goal' to continue")
            # phase: BLOCKED here would satisfy § 2.4's Exit list and flip the
            # intent back to normal, making the bare `cc` that the WAIT line
            # tells the user to run refuse to resume under § 1.10 -- the valve
            # destroying its own continuation path.
            if state.get("phase") == "BLOCKED":
                fail("tripped safety valve MUST NOT set phase: BLOCKED -- "
                     "that is a § 2.4 Exit condition, so it clears the goal "
                     "intent and makes bare `cc` (the documented way to "
                     "continue) illegal under § 1.10. Leave phase as-is")

# RFC § 1.2 + § 2.4 (intent-aware valve wording, T-539): the safety-valve
# pause's resume key must match the intent that owns it. Under
# `execution_intent: goal` the fixed § 1.2 form (`run 'saipen goal' to
# continue`) applies. Under `execution_intent: converge` it MUST read
# `run 'cc' to continue` and MUST NOT read `run 'saipen goal'` -- there
# `saipen goal` is a NEW objective, a substitution not a continuation,
# while bare `cc` is the only legal resume. The two wordings once lived in
# different documents and a weak agent copied the goal wording into a
# converge pause; this makes the pairing enforced rather than prose.
if intent == "converge" and isinstance(next_action, str) \
        and next_action.startswith("WAIT:") \
        and "safety valve" in next_action.lower():
    if "run 'saipen goal'" in next_action.lower():
        fail("converge safety-valve pause names the goal resume key -- "
             "under execution_intent: converge the pause MUST read "
             "`-- run 'cc' to continue`, never `run 'saipen goal'`, "
             "which there is a NEW objective, not a continuation "
             "(RFC § 1.2, § 2.4)")
    elif "run 'cc'" not in next_action.lower():
        fail("converge safety-valve pause carries no resume key -- the "
             "§ 1.2 form under execution_intent: converge ends "
             "`-- run 'cc' to continue`, never `run 'saipen goal'`")
    else:
        ok("converge safety-valve pause names the cc resume key")

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
# Project-root relative, and deliberately: `os.chdir(PROJECT_ROOT)` runs
# before this, so these four questions ask "is the PROJECT under validation
# the SAIPEN home", which is what every gated check below means. It was
# briefly changed to ask the tool's own location instead and 29 scenario
# fixtures went red, because that is a different question with a different
# answer -- the tool ships from a home while validating somebody else's
# project almost always.
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
        # PROTOCOL.md § 1: a subSaipen is a normal SAIPEN instance, so § 1.2's
        # schema rule reaches it too -- legacy is readable and WARNs, and the
        # NEXT checkpoint must upgrade. Core's own state has been checked
        # since v1 of this field and a sub's never was, which is how all four
        # live instances came to sit at the version the shipped TEMPLATE was
        # frozen at. WARN, not FAIL: the upgrade is that sub's own duty at its
        # own next checkpoint, not something another agent performs on it.
        _sub_sv = sub_state.get("schema_version")
        if isinstance(_sub_sv, int) and _sub_sv < CURRENT_SCHEMA_VERSION:
            warn("subsaipen-legacy-schema",
                 f"{sp} schema_version is legacy v{_sub_sv} while current is "
                 f"{CURRENT_SCHEMA_VERSION} -- this sub writes the current "
                 f"schema plus style_contract at its next checkpoint "
                 f"(RFC § 1.2)")
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
        # TEMPLATE ships placeholders that `saipen sub spawn` is documented to
        # replace: `agent: <name>`, an empty `saipen_home`, and a fixed
        # `updated:` PROTOCOL.md § 6 calls "a placeholder like the other two,
        # not a value to partially edit". The reverse of the check above,
        # which stops a concrete path leaking INTO the shipped template --
        # nothing stopped a placeholder surviving OUT of it into a live
        # subSaipen. It matters concretely: RFC § 1.4 decides concurrency by
        # comparing `agent:` against itself, and a spawned worker still called
        # `<name>` makes every liveness comparison meaningless.
        if sp.parts[0] != "extensions":
            _tmpl = _tools_parent / "extensions" / "subs" / "TEMPLATE" / "STATE.md"
            if _tmpl.is_file():
                _tf, _ = parse_frontmatter(read_doc(_tmpl))
                for _k in ("agent", "updated"):
                    _pv = (_tf or {}).get(_k)
                    if _pv and sub_state.get(_k) == _pv:
                        fail(f"{sp} still carries TEMPLATE's placeholder "
                             f"{_k}: {_pv!r} -- `saipen sub spawn` replaces it "
                             f"at spawn (PROTOCOL.md § 6). A live subSaipen "
                             f"named {_pv!r} defeats RFC § 1.4's concurrency "
                             f"comparison, which is agent-against-agent")

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
            if sub_na.startswith("PHASE "):
                _sub_phase_err = _phase_next_action_error(sub_na)
                if _sub_phase_err:
                    fail(f"{sp} next_action {_sub_phase_err}")

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

        if sub_state.get("execution_intent") == "goal":
            for _c in ("goal_waves", "goal_tickets"):
                if not TYPE_CHECKS["integer"](sub_state.get(_c)):
                    fail(f"{sp} execution_intent: goal but {_c} is missing -- "
                         f"PROTOCOL.md documents a goal run for an "
                         f"unattended sub, so § 2.4's valve applies here "
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
KNOWN_FIELDS = {"needs", "owner", "claim_time", "blocker", "verify",
                "review_passes", "verify_attempts"}
# The cap number belongs to phases/verify.md, so it is read from there rather
# than copied here. A missing anchor is a FAIL at the check below, never a
# silent fallback: a cap this file guessed would be a second source of truth,
# which is the drift § 1.2 already had to kill five times over.
_verify_doc = _tools_parent / "saipen" / "phases" / "verify.md"
if not _verify_doc.is_file():
    _verify_doc = _tools_parent / "phases" / "verify.md"
_vc = re.search(r"Cap: (\d+) dead hypotheses OR (\d+) failed fix cycles",
                _verify_doc.read_text(encoding="utf-8-sig")
                if _verify_doc.is_file() else "")
VERIFY_FIX_CYCLE_CAP = int(_vc.group(2)) if _vc else None
# TICKET_RE moved to saipen_engine/board (NITRO M1); imported above.
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
        # RFC § 1.4 claim fields. `claim_time` is compared against a 15-minute
        # window to decide whether a ticket is live or forfeitable, and it was
        # recognised as a known field NAME and never once looked at. Without a
        # zone marker that comparison miscompares across agents in different
        # timezones -- the identical argument § 1.2 already makes for
        # `updated`, which is checked. A fixture shipped a zone-less
        # `claim_time` for releases and nothing noticed.
        _ct = fields.get("claim_time")
        if _ct and not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00)",
                _ct.strip()):
            fail(f"BOARD.md:{line_no} ticket {tid} claim_time {_ct!r} is not "
                 f"ISO-8601 UTC (Z or +00:00) -- § 1.4 decides a live claim "
                 f"from a 15-minute window, and a stamp with no zone is not "
                 f"comparable across agents (RFC § 1.4)")
        # RFC § 1.2 says review_passes exists so phases/review.md enforces its
        # two-pass cap "mechanically instead of from memory". The field name
        # was recognised and the number never read, which leaves the cap
        # exactly where the RFC says it should not be: in memory.
        _rp = fields.get("review_passes")
        if _rp is not None:
            _rps = _rp.strip()
            if not _rps.isdigit():
                fail(f"BOARD.md:{line_no} ticket {tid} review_passes "
                     f"{_rp!r} is not a number (RFC § 1.2)")
            elif int(_rps) > 2:
                fail(f"BOARD.md:{line_no} ticket {tid} has review_passes "
                     f"{_rps} -- phases/review.md caps re-litigating one "
                     f"finding at two passes, and this field exists so that "
                     f"cap is mechanical rather than remembered")

        # Same argument as review_passes, one phase over. `phases/verify.md`
        # caps a ticket at 3 dead hypotheses or 2 failed fix cycles and its
        # hysteresis rule appends each round to `| blocker:` rather than
        # overwriting it -- which preserves the history as prose nothing can
        # sum, so a ticket could take a fresh full budget on every visit with
        # no artifact showing it. The cap number lives in verify.md; this
        # reads it from there rather than carrying a second copy.
        _va = fields.get("verify_attempts")
        if _va is not None:
            _vas = _va.strip()
            if not _vas.isdigit():
                fail(f"BOARD.md:{line_no} ticket {tid} verify_attempts "
                     f"{_va!r} is not a number (RFC § 1.2)")
            elif VERIFY_FIX_CYCLE_CAP is None:
                fail("cross-doc drift [verify-cap] -- phases/verify.md's "
                     "'Cap: N dead hypotheses OR M failed fix cycles' "
                     "sentence moved, so verify_attempts has no cap to "
                     "check against. Update tools/validate.py "
                     "deliberately; a cap this file guessed would be a "
                     "second source of truth")
            elif int(_vas) >= VERIFY_FIX_CYCLE_CAP and not fields.get("blocker"):
                fail(f"BOARD.md:{line_no} ticket {tid} has verify_attempts "
                     f"{_vas} against phases/verify.md's cap of "
                     f"{VERIFY_FIX_CYCLE_CAP} failed fix cycles, but carries "
                     f"no | blocker: -- at the cap the ticket moves to "
                     f"## BLOCKED with the facts and dead ends on it, and "
                     f"this field exists so that is mechanical rather than "
                     f"remembered")

        # An owner with no claim_time, or the reverse, is half a claim:
        # § 1.4 reads liveness from BOTH, so either alone is undecidable.
        if bool(fields.get("owner")) != bool(_ct):
            warn("half-claim",
                 f"BOARD.md:{line_no} ticket {tid} carries "
                 f"{'owner but no claim_time' if fields.get('owner') else 'claim_time but no owner'}"
                 f" -- § 1.4 decides liveness from the pair, so one "
                 f"alone cannot be judged live or stale")

        # NITRO dogfood II (T-590): a TODO/DOING ticket whose verify is a bare
        # placeholder is canonical work with no DONE proof. The SAIOPS
        # ticket-quality boundary made placeholders a FAIL rather than a
        # silent no-op: a weak model can no longer create mechanically perfect
        # tickets whose completion can never be proven. Absence of the field
        # is not flagged (legacy fixtures may omit it); a PRESENT placeholder
        # -- including the old `verify: verify: TBD` double-prefix -- is.
        if section in ("## TODO", "## DOING") and "verify" in fields:
            _vf = fields.get("verify", "").strip().lower()
            _placeholder = (not _vf or _vf in ("tbd", "todo", "placeholder",
                                               "verify: tbd", "verify: todo",
                                               "verify: verify: tbd")
                            or _vf.startswith("verify: verify:"))
            if _placeholder:
                fail(f"BOARD.md:{line_no} ticket {tid} carries a placeholder "
                     f"verify ({fields.get('verify', '').strip()!r}) -- a "
                     f"ticket needs a real DONE proof, not TBD/TODO/empty "
                     f"(NITRO dogfood II, T-590)")

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

# RFC § 1.11's Pick Rule, the satisfaction half. Dangling and cyclic references
# were both checked from the start; whether a claimed ticket's dependencies are
# actually DONE was not, so the DAG decided nothing. § 1.11 records that two
# phrasings of "workable" once coexisted and a ticket with unsatisfied `needs:`
# passed one and failed the other -- an ambiguity resolved in prose while the
# board stayed unable to show it had been resolved at all. A claim is the only
# moment this is decidable from the board alone: `## TODO` order is advisory
# until someone picks, and a ticket already in `## DOING` names its own
# violation. `## BLOCKED` is deliberately exempt -- a blocked ticket is not a
# claim, and § 1.2 sends dependency problems there on purpose.
_unsatisfied = []
for tid, t in tickets.items():
    if t["section"] != "## DOING":
        continue
    for ref in t["needs"]:
        _dep = tickets.get(ref)
        if _dep is not None and _dep["section"] != "## DONE":
            _unsatisfied.append(f"{tid} needs {ref}, which is under "
                                f"{_dep['section']} (line {t['line_no']})")
if _unsatisfied:
    fail("BOARD.md claims work whose dependencies are not done: "
         + "; ".join(_unsatisfied)
         + " -- RFC § 1.11's Pick Rule makes a ticket workable only when all "
           "its needs: are DONE, so this claim was not the agent's to make and "
           "the DAG decided nothing")
else:
    ok("BOARD.md claimed tickets have their needs: satisfied")

# The other half of § 1.11's Pick Rule: `next_action` is the pre-computed pick,
# so it has to name the ticket the rule would choose. Filing a new ticket at
# the front of `## TODO` (§ 1.10's `dd <text>` contract) silently invalidates
# a `PHASE ... T-###` written earlier, and nothing said so -- this repository's
# own board carried `PHASE SCOUT T-417` under four newer tickets and validated
# clean. A cold agent then executes the stale pick and works the wrong ticket
# while believing it followed the rule. Only checked when nothing is claimed:
# a `## DOING` ticket is the pick, and § 1.11 puts finishing it first.
_na_pick = re.match(r"PHASE\s+\w+\s+(T-\d+)", str(state.get("next_action", "")))
if _na_pick:
    _named = _na_pick.group(1)
    _t = tickets.get(_named)
    if _t is None:
        fail(f"STATE.md next_action names {_named}, which is on no board "
             f"section -- the pre-computed pick points at nothing, so the "
             f"cold agent BOOT.md sends here has no ticket to execute "
             f"(RFC § 1.2, § 1.11)")
    elif _t["section"] in ("## DONE", "## BLOCKED"):
        fail(f"STATE.md next_action names {_named}, which sits under "
             f"{_t['section']} -- finished and blocked tickets are not "
             f"executable, and § 1.11's Pick Rule selects from ## TODO "
             f"(## BLOCKED is excluded on purpose)")
    else:
        _unmet = [r for r in _t["needs"]
                  if tickets.get(r, {}).get("section") != "## DONE"]
        if _unmet:
            fail(f"STATE.md next_action names {_named}, whose needs: "
                 + ", ".join(_unmet) + " are not DONE -- § 1.11 makes a "
                 "ticket workable only when every dependency is finished, so "
                 "this pick was never the rule's to make")
        _owner = _t["fields"].get("owner")
        if _owner and state.get("agent") and _owner != state.get("agent"):
            fail(f"STATE.md next_action names {_named}, claimed by "
                 f"{_owner!r} while this state's agent is "
                 f"{state.get('agent')!r} -- executing another agent's claim "
                 f"is the concurrency collision § 1.4 exists to prevent")
# Session-level BLOCKED is "no ticket anywhere on the board is workable", and
# nothing checked the second half. A session halted with a full board looks
# exactly like a legitimate stop: `phase: BLOCKED`, a `WAIT: blocked --`
# naming a real obstacle, and nobody coming. Observed with 18 workable
# `## TODO` tickets and a blocker about translating 29 locales -- which is
# subSaipen work by `phases/translate.md`'s split, so it is a TICKET-level
# block (a `## BLOCKED` line naming its owner) and never a reason to stop
# Core. The two are different states that share a word, and conflating them
# parks a project that had eighteen things to do.
_blocked_workable = [
    tid for tid, t in tickets.items()
    if t["section"] == "## TODO" and t["checkbox"] in (" ", "")
    and all(tickets.get(r, {}).get("section") == "## DONE" for r in t["needs"])
] if state.get("phase") == "BLOCKED" else []
if _blocked_workable:
    fail(f"STATE.md phase: BLOCKED while {len(_blocked_workable)} workable "
         f"## TODO ticket(s) exist (topmost {min(_blocked_workable)}) -- "
         f"session-level BLOCKED is reserved for when no ticket anywhere on "
         f"the board is workable. A block that belongs to one ticket goes on "
         f"THAT ticket's line in `## BLOCKED` with its owner named, and Core "
         f"keeps working the rest")
# RFC 2.4's Exit list makes `phase: BLOCKED` an exit condition, so the two
# cannot both be true: a blocked session is not a running goal.
if state.get("phase") == "BLOCKED" and intent == "goal":
    fail("STATE.md carries phase: BLOCKED with execution_intent: goal -- RFC "
         "2.4's Exit list names BLOCKED as an exit, so the goal intent MUST "
         "be cleared there. Left set, a resume walks straight back into an "
         "autonomous run the block was supposed to stop")

if _na_pick and not any(t["section"] == "## DOING" for t in tickets.values()):
    _named = _na_pick.group(1)
    _workable = [
        (t["line_no"], tid) for tid, t in tickets.items()
        if t["section"] == "## TODO"
        and all(tickets.get(r, {}).get("section") == "## DONE" for r in t["needs"])
    ]
    _top = min(_workable)[1] if _workable else None
    if _top is not None and _named != _top:
        fail(f"STATE.md next_action picks {_named}, but the topmost workable "
             f"## TODO ticket is {_top} -- board order is priority (RFC "
             f"§ 1.11), so a ticket filed above the named one makes this pick "
             f"stale. Repoint next_action or move the line")
    elif _top is not None:
        ok(f"next_action picks the topmost workable ticket ({_top})")

# RFC § 2.1 ZERO-PROMPT AUTO-TRANSITION: DONE + empty TODO + no MARKHUNT
# blockers = MUST auto-transition HUNT->ADD, never WAIT at DONE.
# The `goal_mode is not True` exemption this check carried switched it off
# in exactly the mode where a deadlocked board costs most: an unattended
# run parked on a WAIT nobody was asked. The tripped valve was always
# covered by the wording test below, so the exemption protected nothing it
# needed to. The MARKHUNT carve-out is no longer a blanket skip either --
# those findings have a fixed § 1.2 wording now, so the brake is checked
# like every other legal pause instead of exempted from checking.
if state.get("phase") == "DONE":
    open_todos = sum(1 for t in tickets.values()
                     if t["section"] == "## TODO" and t["checkbox"] in (" ", ""))
    next_action = state.get("next_action", "")
    if open_todos == 0 and next_action.startswith("WAIT:"):
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
        if not _done_wait_whitelisted(next_action):
            fail(f"phase: DONE, empty ## TODO, but "
                 f"next_action={next_action!r} -- RFC § 2.1 says bare "
                 f"command + empty board MUST auto-transition HUNT->ADD. "
                 f"The legal WAITs here are the § 2.4 safety valve, "
                 f"'WAIT: user brake -- <reason>', and the "
                 f"untriaged-MARKHUNT brake (RFC § 1.2); anything else "
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
    # A ticket in ## DONE is a completion claim, and until now it could be
    # made with no evidence at all: `verify:` was a recognised field nothing
    # required, so moving a line into ## DONE was enough to make the board
    # say the work was proven. Reproduced on this repository (E-1767): a
    # ticket went DOING -> DONE with "no verify -- not built work" and every
    # gate stayed green. DONE must mean the same thing on every board, and
    # what it means is "the verify: condition this ticket set for itself was
    # met" -- so the ticket has to say what met it. The field's CONTENT is
    # not judged here and cannot be: it is evidence for a human or a reviewer
    # to weigh, and the check that pretends to grade it would be the third
    # lie in the chain. Absence is what nothing could see before.
    if t["section"] == "## DONE" and not t["fields"].get("verify", "").strip():
        fail(f"BOARD.md:{t['line_no']} ticket {tid} sits under ## DONE with "
             f"no | verify: evidence -- ## DONE is a claim that the ticket's "
             f"own verify condition was met, and a claim with no evidence "
             f"attached is indistinguishable from one that was never tested "
             f"(RFC § 1.2). Closing without building it? Say so in verify: "
             f"and the board stops overstating what happened")

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

# T-573: STATE.task and ## DOING are ONE binding, not two files that may
# drift. The v7.215.0 crash checkpoint claimed task T-572 in a ticket-bearing
# phase while BOARD carried no ## DOING claim and T-572 sat in ## TODO, and
# the validator called that conformant -- the exact "STATE ahead of BOARD"
# interruption § 1.5 exists to catch. Recovery may observe an interrupted
# checkpoint, but canonical validation MUST reject it. One legitimate
# exception is another agent's live claim, which the Pick Rule refuses rather
# than mirrors in STATE (the multi-agent-claim-conflict fixture is
# `expect: pass` precisely because the observing agent has task: none while
# the claimed ticket sits in ## DOING under someone else's owner) -- so the
# binding is judged against the agent's OWN claim, not a stranger's.
if phase in TICKET_BEARING_PHASES:
    active_task = state.get("task")
    self_agent = state.get("agent")
    self_doing = [tid for tid in doing
                  if not tickets[tid]["fields"].get("owner", "")
                  or tickets[tid]["fields"].get("owner", "") == self_agent]
    if isinstance(active_task, str) and re.fullmatch(r"T-\d+", active_task):
        if active_task not in doing:
            fail(f"STATE.md task {active_task} is not the claimed ## DOING "
                 f"ticket ({', '.join(doing) or 'none'}) in ticket-bearing "
                 f"phase {phase} -- a TODO/DONE/BLOCKED ticket cannot be the "
                 f"active task; Recovery reconstructs the claim from BOARD "
                 f"and the LOG tail (RFC § 1.5, T-573)")
        _na = state.get("next_action", "")
        if isinstance(_na, str) and (_na.startswith("PHASE ")
                                     or _na.startswith("RESUME:")):
            _na_ticket = re.search(r"\bT-\d+\b", _na)
            if _na_ticket and _na_ticket.group(0) != active_task:
                fail(f"STATE.md next_action names {_na_ticket.group(0)} while "
                     f"task is {active_task} in ticket-bearing phase {phase} "
                     f"-- the pick must agree with the active task (RFC § 1.2, "
                     f"T-573)")
    elif active_task in ("none", "", None) and self_doing:
        fail(f"STATE.md task is none but ## DOING carries {self_doing[0]} "
             f"claimed by this agent or unclaimed -- STATE is behind BOARD; "
             f"Recovery adopts the BOARD claim (RFC § 1.5, T-573)")

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

# RFC § 2.1 + CONVERGE.md (intent-aware clean-HUNT routing, T-539): a clean
# HUNT's destination depends on the execution intent. Under `normal`/`goal` it
# enters ADD (MAINTENANCE § 2.1). Under `converge` a clean HUNT is stage F or
# stage I of CONVERGE.md and MUST NOT enter ADD -- F routes to CLEAN, I routes
# into the closure sequence (sync, fresh factories, finalize); ADD is
# invention, the one thing a converge run must never do (CONVERGE.md stage C).
# The marker is hunt.md's canonical clean-hunt line (`RUN: hunt -> clean
# @HASH`); a converge state that carries it and points next_action at ADD is
# the failed routing this pins. The normal intent MAY reference ADD -- that is
# the other half of the same rule and deliberately not checked here.
if intent == "converge" and log_files and isinstance(next_action, str):
    _clean_hunt_marker = any(
        "hunt -> clean @" in ln
        for p in log_files for ln in read_doc(p).splitlines())
    if _clean_hunt_marker:
        if re.search(r"\bADD\b", next_action):
            fail("converge clean-HUNT marker present but next_action names ADD "
                 "-- under execution_intent: converge a clean HUNT MUST NOT enter "
                 "ADD (CONVERGE.md stages F/I route it to CLEAN and the closure "
                 "sequence; ADD is invention, which converge never does). The "
                 "normal/goal path may still enter ADD per MAINTENANCE.md § 2.1")
        else:
            ok("converge clean-HUNT marker present, next_action avoids ADD")

if converge_target == "ship" and log_files:
    _ccc_lines = [line for path in log_files for line in read_doc(path).splitlines()]
    _ccc_markers = [(index, match.group(1))
                    for index, line in enumerate(_ccc_lines)
                    if (match := re.search(
                        rf"DEC: ccc converge target -> ship @({OID_RE})\b",
                        line))]
    if not _ccc_markers:
        fail("STATE.md converge_target: ship has no ccc entry marker -- a crash "
             "cannot recover the I -> SHIP -> J route without its LOG evidence")
    else:
        _ccc_start, _pre_ship_head = _ccc_markers[-1]
        _ship_result = next((
            (index, match.group(1))
            for index in range(_ccc_start + 1, len(_ccc_lines))
            if (match := re.search(
                rf"RUN: ship .* -> pushed ({OID_RE})\b",
                _ccc_lines[index]))
        ), None)
        _ship_at = _ship_result[0] if _ship_result else None
        _prepare_at = [index for index in range(_ccc_start + 1, len(_ccc_lines))
                       if ("RUN: prepare saitranslate -> done" in _ccc_lines[index]
                           or "RUN: prepare saiwiki -> done" in _ccc_lines[index])]
        if _prepare_at and (_ship_at is None or min(_prepare_at) < _ship_at):
            fail("ccc prepared EE/QQ before SHIP -- converge_target: ship MUST "
                 "run A-I, SHIP, then J-M so packages bind to the shipped HEAD")
        if _ship_result is not None:
            _shipped_head = _ship_result[1]
            # Canonicalize BOTH references before comparing either of them.
            # Every rung below is an identity question about commits, and a
            # commit's identity is its full OID, never the width someone
            # happened to write it at.
            _canon_shipped = canonical_commit(_shipped_head)
            _canon_pre_ship = canonical_commit(_pre_ship_head)
            _unresolved = [raw for raw, canon in
                           ((_pre_ship_head, _canon_pre_ship),
                            (_shipped_head, _canon_shipped)) if canon is None]
            # Distinguish "this reference is wrong" from "nothing here can
            # resolve any reference". Outside a repository the proof is not
            # failed, it is unperformable, and reporting the two the same way
            # is how a check earns a reputation for crying wolf. Inside one,
            # a reference that does not resolve is the finding.
            _ccc_in_repo = _git("rev-parse", "--is-inside-work-tree")[0] == 0
            if _unresolved and not _ccc_in_repo:
                warn("ccc-identity-unverifiable",
                     "ccc SHIP evidence cannot be canonicalized: this project "
                     "is not a Git repository, so no commit reference resolves "
                     "and the I -> SHIP -> J proof has nothing to compare")
            elif _unresolved:
                # An unresolvable reference is not a reason to skip the proof:
                # a ccc route whose LOG names commits this repository does not
                # have has no evidence at all, which is the state the check
                # exists to catch (T-528 closed the same shape for hunt marks).
                fail(f"ccc SHIP evidence names commit(s) this repository cannot "
                     f"resolve: {', '.join(repr(r) for r in _unresolved)} -- the "
                     f"I -> SHIP -> J proof compares commit identities, and a "
                     f"reference that resolves to nothing proves nothing")
            elif _canon_shipped == _canon_pre_ship:
                fail(f"ccc SHIP did not change source revision -- post-SHIP "
                     f"packages would bind to the same pre-SHIP source_head "
                     f"({_shipped_head} and {_pre_ship_head} are the same "
                     f"commit {_canon_shipped})")
            try:
                _ccc_identity = compute_source_identity(Path("."))
            except FreshnessError as exc:
                fail(f"ccc cannot verify shipped source_head: {exc}")
            else:
                _canon_current = canonical_commit(_ccc_identity.source_head)
                if _canon_shipped is not None and _canon_current is not None \
                        and _canon_shipped != _canon_current:
                    fail("ccc SHIP evidence does not match current source_head -- "
                         f"LOG says {_shipped_head!r} ({_canon_shipped}), current "
                         f"HEAD is {_ccc_identity.source_head!r}")

if log_files:
    # Date prefix optional to allow pre-STYLE.md history; new entries carry one.
    # [agent: <id>] is a MAY field for writer identity (RFC § 1.2, v7.27.0).
    # LOG_RE moved to saipen_engine/log (NITRO M1); imported above.
    # A LOG line records what HAPPENED. An entry written in the future tense
    # records an intention instead, and every later reader -- § 1.5's Recovery
    # rebuild, an audit, the next agent's cold start -- counts it as evidence
    # that the act occurred. "RUN: will ship the release" and "RUN: ship the
    # release -> pushed abc1234" are indistinguishable to a rebuild that only
    # knows the line exists. Nothing gated this, and an agent's default is to narrate
    # its plan (T-430).
    #
    # Scope is the FIRST CLAUSE, up to the first ` -- `, ` -> `, `; ` or `. `:
    # that span is where a line states what its event WAS. Later clauses are
    # commentary and may legitimately name someone else's future -- E-1679's
    # "the very rule T-409 is about to write down" describes a ticket's
    # content, not a claim that the writer did something. Measured against
    # every LOG this repository has (7 sealed segments, the active log and 4
    # subSaipen logs): zero first-clause hits, so the gate starts clean and
    # any hit is new drift rather than inherited history.
    FUTURE_TENSE_RE = re.compile(
        r"\b(will|won't|shall|going to|about to|plans? to|planning to|"
        r"intends? to|i'll|we'll|next step|next up)\b", re.IGNORECASE)
    FIRST_CLAUSE_RE = re.compile(r" -- | -> |; |\. ")
    seen_ids = {}
    conf_run_seen = False
    sealed_dateless = []
    sealed_future = []
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
            eid, parent, ticket, agent, op_id, taxonomy, content = \
                m.groups()
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
            # Future tense in the first clause: the line records a plan, not
            # an event. Same severity split the DATE check uses -- the active
            # log is still the writer's to get right, sealed history is
            # immutable by append-only and can only be reported.
            _future = FUTURE_TENSE_RE.search(
                FIRST_CLAUSE_RE.split(content)[0])
            if _future:
                if is_active_log:
                    fail(f"{loc} states its event in the future tense "
                         f"({_future.group(0)!r}) -- a LOG line records what "
                         f"happened, and an intention written as an event is "
                         f"counted as evidence the act occurred by every "
                         f"reader after you, including § 1.5 Recovery. Log it "
                         f"after doing it, or log the decision as a DEC about "
                         f"a ticket (RFC § 1.2)")
                    log_ok = False
                else:
                    sealed_future.append(f"{loc} ({_future.group(0)!r})")
            # § 1.2's fixed conformance-run form, the record § 1.10's
            # `saipen status` is ordered to report. Active log only: status
            # wants the LAST run, `BOOT.md`'s cold start reads the active tail
            # and nothing else, and a record sealed into cold storage is by
            # definition not the current answer. A freshly sealed log warns
            # until the next validator run, which is exactly the state where
            # status genuinely has nothing fresh to report.
            if is_active_log and re.match(
                    r"validate\.py\s*->\s*(PASS|FAIL)\b", content):
                conf_run_seen = True
            # MARKHUNT's closure rule tells a later reader to sum "this
            # pass's [MARKHUNT] tickets", and nothing recorded which they
            # were. Those tickets legitimately leave ## BLOCKED for ## TODO
            # with the tag and the `unvetted audit` blocker dropped, and a
            # dismissed one leaves the board entirely -- BOARD.md is not
            # append-only, LOG.md is. Four passes already ran here
            # (findings=3, 12, 6, 1) and not one can be re-checked. Active
            # log only: those four are sealed and immutable, so scoping the
            # check here makes it a clean FAIL with nothing to grandfather --
            # the same narrowing the conformance-record check took at E-1851.
            if (is_active_log and re.match(r"markhunt\s*->", content)
                    and "findings" in content
                    and "tickets=" not in content):
                fail(f"{loc} records a MARKHUNT pass with no `tickets=` "
                     f"list -- phases/markhunt.md requires the completion "
                     f"line to name every [MARKHUNT] ticket the pass wrote "
                     f"(or `tickets=none`). Without it the closure sum stops "
                     f"being checkable the moment triage moves those tickets "
                     f"off `## BLOCKED`, and a dismissed finding leaves no "
                     f"trace at all")
            # PREPARE wrote the same success event for `saitranslate`, for
            # `saiwiki` and for an unqualified main-project package alike, so
            # the LOG could not say which handoff became ready and two
            # prepares were indistinguishable rather than dedupable. The
            # producer is required now, with the literal `unqualified` for
            # "no producer requested". Live agents had already started writing
            # it in by hand, against the phase doc's own fixed format --
            # practice correcting a shape nobody had fixed. The source
            # revision is deliberately NOT required here: the handoff's own
            # `source_head:` carries it, and a second copy in an append-only
            # file goes stale against the one that gets refreshed.
            if re.match(r"prepare\s*->", content):
                fail(f"{loc} records a prepare with no producer -- RFC "
                     f"1.2's fixed-form rule and phases/prepare.md step 6 "
                     f"require `RUN: prepare <producer> -> done|FAILED`, "
                     f"where <producer> is the producer name or the literal "
                     f"`unqualified`. Unqualified, the record cannot say "
                     f"which handoff became ready, or which of two prepares "
                     f"this one was")
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
    # RFC section 1.2's STATE freshness marker. Schema v1 and absent schema
    # versions are readable legacy states; their warning above orders the next
    # checkpoint to migrate. Schema v2 is proof that checkpoint code knows the
    # marker, so an event-bearing LOG without it is corrupt. A fresh bootstrap
    # has an empty LOG and therefore no event to name.
    #
    # Note on how this survived: v7.108.0's rule-coverage check requires every
    # RFC section stating a MUST to be CITED by a CONFORMANCE row, and § 1.2 is
    # cited by dozens. Section granularity cannot see one unenforced MUST
    # inside a heavily-cited section. That limit is real and now demonstrated.
    _le = state.get("last_event")
    if sv == CURRENT_SCHEMA_VERSION and prev_id and _le is None:
        fail(f"STATE.md schema_version {CURRENT_SCHEMA_VERSION} requires "
             f"last_event because the LOG tail is E-{prev_id}. Legacy v1 "
             "may omit it only until its next checkpoint (RFC section 1.2, "
             "section 1.5)")
    if isinstance(_le, int) and _le < 1:
        fail(f"STATE.md last_event is E-{_le}, but event IDs start at E-1; "
             "omit the field only for a fresh empty LOG")
    elif isinstance(_le, int) and log_files:
        if _le > prev_id:
            fail(f"STATE.md last_event is E-{_le} but the LOG tail is "
                 f"E-{prev_id} -- higher than the log means corrupt, or a "
                 f"STATE carried over from an incompatible branch. Recovery "
                 f"rebuilds from the log and would chase an event that was "
                 f"never written (RFC § 1.2)")
        elif _le < prev_id:
            fail(f"STATE.md last_event is E-{_le} but the LOG tail is "
                 f"E-{prev_id} -- lower than the log means this STATE predates "
                 f"its own history: a checkpoint wrote LOG lines and did not "
                 f"finish updating STATE (RFC § 1.2, § 1.5)")

    if log_ok:
        ok(f"LOG.md format valid (skeleton, E-### unique + monotonic, parents "
           f"resolve; {len(log_files)} segment(s))")

    # NITRO integrity (T-584): after the migration boundary the covered
    # structural operations MUST carry mechanical provenance (`[op: ...]`),
    # so a manual structural edit that bypasses the engine is detectable.
    # Only SAIOPS-owned structural events are checked -- ordinary semantic
    # LOG entries stay unmarked. Historical pre-boundary events are exempt.
    # The boundary is SELF-ESTABLISHING: the first event ever written with an
    # `[op: ...]` marker. Every structural event at/after it must carry one;
    # anything older is pre-provenance history that cannot be rewritten.
    _provenance_markers = (
        "claimed via SAIOPS",
        "ticket added via SAIOPS",
        "ticket done via SAIOPS",
        "ticket block via SAIOPS",
        "ticket unblock via SAIOPS",
        "goal pivot",
        "goal reauthorized",
        "stop checkpoint",
        "transition to ",
        "transition",
    )
    _saio_ops = {"claim", "transition", "checkpoint", "ticket", "goal",
                 "valve", "stop"}
    _provenance_missing = []
    _first_op_event = None
    if log_ok:
        from saipen_engine.log import parse_log_line as _engine_log_parse
        _all_events = []
        for _lf in log_files:
            for _line_no, _line in enumerate(read_doc(_lf).splitlines(), 1):
                if not _line.strip() or _line.startswith("#"):
                    continue
                _ev = _engine_log_parse(_line)
                if _ev is None:
                    continue
                _all_events.append((_lf, _line_no, _ev))
        for _lf, _line_no, _ev in sorted(_all_events,
                                         key=lambda e: e[2]["event"]):
            if _ev["op_id"] and _first_op_event is None:
                _first_op_event = _ev["event"]
            if _first_op_event is None or _ev["event"] < _first_op_event:
                continue
            if _ev["op_id"]:
                continue
            _text = _ev["text"] or ""
            if _ev["taxonomy"] in ("DEC", "RUN") and any(
                    _mk in _text for _mk in _provenance_markers):
                _provenance_missing.append(
                    f"{_lf.as_posix()}:{_line_no} E-{_ev['event']}")
        if _provenance_missing:
            fail("mechanical provenance [saio] -- structural SAIOPS-owned "
                 "events after the first provenanced event "
                 f"(E-{_first_op_event}) lack `[op: ...]`, so a manual "
                 "structural edit cannot be distinguished from a mechanized "
                 "one: " + "; ".join(_provenance_missing[:6]) + " (T-584)")

    # [gate-closure] (NITRO dogfood IV, T-602): a ticket's DONE state is
    # evidence of the phase chain that produced it, NEVER of a legal-looking
    # final STATE. finish_ticket now REFUSEs every non-SHIP closure (the
    # primary mechanical gate), so this check is defense-in-depth against a
    # fabricated or skipped-gate closure event reaching the append-only LOG.
    # The boundary is SELF-ESTABLISHING, exactly like [saio]: the first
    # `ticket finished via SAIOPS -- completion (from SHIP)` event marks where
    # the gate fix is in force. Earlier non-SHIP finish events are the
    # recorded HISTORICAL skipped-gate closures (T-591/T-594/T-595 closed from
    # VERIFY by the pre-fix defect: ACCIDENTAL_SUCCESS with incomplete gate
    # proof, never rewritten). Any non-SHIP finish event at/after the boundary
    # is fabrication and FAILs.
    if log_ok:
        from saipen_engine.log import parse_log_line as _gate_parse
        _finish_re = re.compile(
            r"ticket finished via SAIOPS -- completion \(from (\w+)\)")
        _finish_evs = []
        for _lf in log_files:
            for _line_no, _line in enumerate(read_doc(_lf).splitlines(), 1):
                if not _line.strip() or _line.startswith("#"):
                    continue
                _ev = _gate_parse(_line)
                if _ev is None or _ev["taxonomy"] != "DEC":
                    continue
                _m = _finish_re.search(_ev.get("text") or "")
                if _m:
                    _finish_evs.append((_ev["event"], _m.group(1),
                                        _ev.get("ticket"), _lf, _line_no))
        _finish_evs.sort(key=lambda e: e[0])
        _gate_boundary = next((e for e in _finish_evs if e[1] == "SHIP"),
                              None)
        if _gate_boundary is not None:
            for _e in _finish_evs:
                if _e[1] != "SHIP" and _e[0] >= _gate_boundary[0]:
                    fail("gate-closure -- ticket "
                         f"{_e[2] or '?'} closed by a finish event naming "
                         f"actual phase {_e[1]} at/after the gate-fix "
                         f"boundary (first SHIP-finish E-{_gate_boundary[0]}); "
                         "a ticket must pass REVIEW -> SHIP before finish, and "
                         "skipped gates must never produce DONE (T-602)")

    # § 1.10 orders `saipen status` to report "the result of the last
    # tools/validate.py run if one is recorded in LOG.md" -- a duty handed out
    # before anything gave that record a shape, so the reader either grepped
    # prose and guessed or answered "none recorded" over a LOG that held the
    # answer. § 1.2 now fixes the form, exactly as § 2.4 fixed
    # `DEC: goal_waves N->M` so § 1.5's rebuild could count them. WARN, not
    # FAIL: a project may legitimately never have run the validator, and this
    # says so out loud instead of letting `status` invent an answer.
    if not conf_run_seen:
        warn("no-conformance-record",
             "no LOG line records a conformance run in § 1.2's fixed form "
             "(`RUN: validate.py -> PASS` or `-> FAIL`), so § 1.10's "
             "`saipen status` has nothing to report under Conformance and a "
             "cold agent must either guess from prose or say none exists")

    # `phases/hunt.md`'s skip condition: a sweep may be skipped only when the
    # newest `hunt -> clean @<HASH>` names the exact current HEAD. The hash is
    # the whole mechanism -- no hash, no skip, by construction -- and until now
    # nothing read it. The recorded incident is an agent that invented its own
    # substitute signal ("no source files changed"), was corrected, then
    # produced the identical substitution a second time dressed as compliance;
    # a fabricated skip has no resolvable commit behind it, and that is exactly
    # what this reads. Sealed segments WARN because append-only history cannot
    # be corrected; the active tail FAILs. Skipped whole where git is absent --
    # hunt.md already says a repo-less project can never satisfy the skip.
    # T-528 adds the second rung: the commit must have REACHED the remote, not
    # merely exist locally. db9d775 existed on exactly one machine and on no
    # remote branch, so the local run passed and CI -- a fresh clone against
    # the identical tree -- failed: local-green was not evidence of CI-green.
    # The mark is durable, so the commit it names must be durable too.
    # `git branch -r --contains` reads remote-tracking refs only (no network,
    # no fetch), so a stale ref is reported as what it is: not yet reached.
    # A project with no remote keeps the old local-existence behavior -- no
    # commit has reached anything there, and hunt.md's skip is unreachable.
    _hunt_marks = []
    for _lf in log_files:
        for _ln, _line in enumerate(_lf.read_text(encoding="utf-8-sig")
                                    .splitlines(), 1):
            for _h in re.findall(r"hunt -> clean @([0-9a-f]{7,40})\b", _line):
                _hunt_marks.append((_lf, _ln, _h))
    if _hunt_marks and _git("rev-parse", "--git-dir")[0] == 0:
        _remote_refs = _git("for-each-ref", "--format=%(refname)", "refs/remotes")
        _has_remote = _remote_refs[0] == 0 and bool(_remote_refs[1].strip())
        _bad_active, _bad_sealed, _stray_active, _stray_sealed = [], [], [], []
        _seen, _reach = {}, {}
        for _lf, _ln, _h in _hunt_marks:
            _loc = f"{_lf.as_posix()}:{_ln} @{_h}"
            if _h not in _seen:
                _seen[_h] = _git("cat-file", "-e", f"{_h}^{{commit}}")[0] == 0
            if not _seen[_h]:
                (_bad_active if _lf == active_log else _bad_sealed).append(_loc)
            elif _has_remote:
                if _h not in _reach:
                    _reach[_h] = bool(
                        _git("branch", "-r", "--contains", _h)[1].strip())
                if not _reach[_h]:
                    (_stray_active if _lf == active_log
                     else _stray_sealed).append(_loc)
        if _bad_active:
            fail("LOG.md records a clean hunt against commit(s) this "
                 "repository does not have: " + "; ".join(_bad_active)
                 + " -- `phases/hunt.md` skips a sweep only on an exact match "
                   "with HEAD, so a mark no commit backs is a skip nothing "
                   "earned")
        if _stray_active:
            fail("LOG.md records a clean hunt against commit(s) that sit on "
                 "no remote branch: " + "; ".join(_stray_active)
                 + " -- a hunt mark is durable, so the commit it names must "
                   "be durable too: a commit that only exists locally is "
                   "invisible to the next clone, which is how a red CI run "
                   "stays green on the machine that produced it")
        _sealed_bad = _bad_sealed + _stray_sealed
        if _sealed_bad:
            warn("hunt-mark-unresolvable",
                 f"{len(_sealed_bad)} sealed hunt mark(s) name commits this "
                 f"repository does not have or that never reached the remote "
                 f"(earliest {_sealed_bad[0]}). Immutable by append-only; "
                 f"new marks are FAILed instead")
        if not (_bad_active or _stray_active or _sealed_bad):
            ok(f"hunt skip marks resolve to real commits on the remote "
               f"({len(_hunt_marks)} checked)")

    # RFC § 2.4 requires every goal counter bump to leave `DEC: goal_waves N->M`
    # (or goal_tickets), because § 1.5 Recovery rebuilds the counters by
    # COUNTING those lines. v7.87.0 fixed the three phase docs that bump a
    # counter without naming the line; nothing verified the result until
    # v7.90.0. A non-zero counter with no matching line anywhere means the
    # crash-recovery path has nothing to count -- the valve silently loses its
    # budget on exactly the long unattended runs it protects. WARN, not FAIL:
    # states predating v7.87.0 legitimately carry counters with no lines, and
    # a sealed segment may hold the lines for a very old run.
    if intent == "goal":
        # Anchored to the taxonomy slot -- the token immediately after the
        # bracket group -- so a line that merely QUOTES the marker is not one.
        # Found in review: two `RUN:` lines describing this very rule matched
        # an unanchored pattern and became the newest marker themselves, which
        # would have dated the rebuild window from a sentence about the rule.
        # A re-authorization only means something against a tripped valve. The
        # line names the counters it cleared, so the claim checks itself: below
        # both caps, nothing was re-authorized and the reset just handed out a
        # fresh budget nobody asked for -- the failure that made the most
        # convenient shortcut unsafe to type (RFC § 2.4 Entry, v7.148.0).
        for _n, _m in enumerate(re.finditer(
                r"\]\s+DEC: goal reauthorized -- goal_waves (\d+)->0, "
                r"goal_tickets (\d+)->0", "\n".join(
                    ln for p in log_files for ln in read_doc(p).splitlines()))):
            _w, _t = int(_m.group(1)), int(_m.group(2))
            if _w < 3 and _t < 20:
                warn("goal-reauth-untripped",
                     f"a `DEC: goal reauthorized` line clears goal_waves {_w} "
                     f"and goal_tickets {_t}, both under § 2.4's 3/20 caps -- "
                     f"the valve had not tripped, so nothing needed "
                     f"re-authorizing and the reset granted a fresh budget "
                     f"instead (RFC § 2.4 Entry)")
                break

        _marker = re.compile(r"\]\s+DEC: goal (?:pivot|reauthorized)\b")
        _log_lines = [ln for p in log_files for ln in read_doc(p).splitlines()]
        _last_marker = max(
            (i for i, ln in enumerate(_log_lines) if _marker.search(ln)),
            default=None)

        for counter in ("goal_waves", "goal_tickets"):
            if not isinstance(state.get(counter), int):
                continue
            
            _start_idx = _last_marker + 1 if _last_marker is not None else 0
            rebuilt = sum(
                1 for ln in _log_lines[_start_idx:]
                for m in [re.search(rf"DEC: {counter} (\d+)->(\d+)", ln)]
                if m and int(m.group(2)) > int(m.group(1)))

            if _last_marker is not None:
                if rebuilt != state[counter]:
                    fail(f"STATE.md {counter} is {state[counter]} but replaying "
                         f"§ 1.5 Recovery from the newest goal marker rebuilds "
                         f"{rebuilt} -- a crash here would resume this run on the "
                         f"rebuilt number, not the one in STATE. Either a bump "
                         f"reached STATE without its `DEC: {counter} N->M` line, "
                         f"or a reset dropped the counter without the "
                         f"`DEC: goal reauthorized` line that makes the drop "
                         f"countable (RFC § 1.5, § 2.4)")
            else:
                if rebuilt == 0 and state[counter] > 0:
                    warn("goal-counter-untraced",
                         f"STATE.md {counter} is {state[counter]} but no "
                         f"'DEC: {counter} N->M' line exists in the accountable LOG -- "
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

    if sealed_future:
        warn("log-future-tense",
             f"{len(sealed_future)} sealed LOG entr(y/ies) state their event "
             f"in the future tense (earliest {sealed_future[0]}). Immutable "
             f"by append-only; new entries are FAILed instead")

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

    # The forward bound was 3h and that is why nothing ever caught the real
    # behaviour: an agent does not miss the clock by hours, it misses it by
    # twenty minutes, because reading the clock costs a tool call and writing
    # a plausible number costs nothing. Reproduced by this validator's own
    # author at E-1788..E-1793 -- stamps up to 37 minutes ahead of real UTC,
    # every line green (T-432). 5 minutes is the same slack the inversion
    # check above already allows for clock skew between machines, so there is
    # one number here with one meaning: clocks may disagree this much, and
    # past it the stamp was invented rather than read.
    LOG_CLOCK_SLACK = 300
    now = datetime.datetime.now(datetime.timezone.utc)
    for log_dt, eid, loc in timestamp_events:
        ahead = (log_dt - now).total_seconds()
        if ahead > LOG_CLOCK_SLACK:
            fail(f"{loc} timestamp for E-{eid:03d} is {ahead / 60:.0f}m ahead "
                 f"of real UTC (slack is {LOG_CLOCK_SLACK // 60}m) -- LOG "
                 f"timestamps MUST be real UTC time, and an event stamped at "
                 f"a minute that has not happened yet reorders everything a "
                 f"§ 1.5 rebuild reads off these stamps. Read the clock, do "
                 f"not estimate it: python -c \"import datetime;print("
                 f"datetime.datetime.now(datetime.timezone.utc).strftime("
                 f"'%d.%m.%y %H:%M'))\" (RFC § 1.2)")

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

# T-543: one shared implementation owns the current source identity. Failure
# is evidence, not an empty/partial digest: no ready package can validate when
# any required input could not be discovered, stat'ed, classified, or read.
try:
    _source_identity = compute_source_identity(Path("."))
except FreshnessError as exc:
    _source_identity = None
    fail("source freshness computation BLOCKED -- " + str(exc)
         + "; no package may become ready or be collected with unknown input")

_outbox_paths = set(Path(".").glob(".saipen/extensions/subs/*/kitchen/OUTBOX.md"))
_translate_outbox = Path(".saipen/saitranslate/kitchen/OUTBOX.md")
if _translate_outbox.is_file():
    _outbox_paths.add(_translate_outbox)

# ------------------------------------------------------- PRODUCER GATE (T-568)
#
# Producer readiness and Core conformance are two different questions, and
# answering them with one severity is what made an unrefreshed EE package block
# an unrelated Core commit. The rule the gate restores:
#
#     a producer's package must be complete, fresh and role-current WHEN IT IS
#     CONSUMED, or when the convergence closure explicitly requires it fresh --
#     never as a precondition for editing one Core line.
#
# So severity is a property of the ACTIVE GATE, not of the finding:
#
#   core (default) / ship   every producer finding is a visible WARN. Core
#                           ships on its own conformance.
#   collect:<producer>      that producer is hard. Malformed, incomplete,
#                           stale, wrong role_revision, wrong source identity
#                           and not-ready are each a FAIL. Other producers stay
#                           soft -- collecting saiwiki says nothing about
#                           saitranslate.
#   converge                every producer CONVERGE.md stage M requires fresh
#                           is hard, and a required package that is missing
#                           entirely is a FAIL too.
#
# The validator remains read-only under every gate: it reports what a package
# is, and never edits an OUTBOX into the shape it wanted to find.
#
# EE and QQ, named rather than discovered: `--gate converge` must not depend on
# which producer folders happen to exist in a given project, or a closure could
# pass by deleting the producer instead of refreshing it.
CONVERGE_REQUIRED_PRODUCERS = (("saitranslate", "EE"), ("saiwiki", "QQ"))


def _producer_of(path):
    """The producer that owns an OUTBOX, from its canonical location."""
    parts = path.as_posix().split("/")
    if "subs" in parts and len(parts) > parts.index("subs") + 1:
        return parts[parts.index("subs") + 1]
    # saitranslate's kitchen sits directly under `.saipen/` (T-504 layout).
    if len(parts) > 2 and parts[0] == ".saipen":
        return parts[1]
    return None


def producer_gate_is_hard(producer):
    if GATE == "collect":
        return producer == GATE_PRODUCER
    if GATE == "converge":
        return producer in {name for name, _ in CONVERGE_REQUIRED_PRODUCERS}
    return False


_producers_failed_hard = set()


def producer_problem(producer, slug, message):
    """Report a producer-package defect at the severity the active gate owns."""
    if producer_gate_is_hard(producer):
        _producers_failed_hard.add(producer)
        fail(message)
        return True
    warn(slug, f"{message} -- reported under `--gate {GATE}`, where this "
               f"producer is not being consumed; it FAILs under "
               f"`--gate collect:{producer}` and blocks nothing else")
    return False


def _role_contract_path(producer: str):
    candidates = (
        Path(".saipen/extensions/subs") / f"{producer}.md",
        Path("extensions/subs") / f"{producer}.md",
        _tools_parent / "extensions" / "subs" / f"{producer}.md",
    )
    return next((path for path in candidates if path.is_file()), None)


def _generic_protocol_path():
    candidates = (
        Path(".saipen/extensions/subs/PROTOCOL.md"),
        Path("extensions/subs/PROTOCOL.md"),
        _tools_parent / "extensions" / "subs" / "PROTOCOL.md",
    )
    return next((path for path in candidates if path.is_file()), None)


def _current_role_revision(producer: str):
    charter = _role_contract_path(producer)
    if charter is not None:
        return compute_role_revision(charter), charter
    protocol = _generic_protocol_path()
    if protocol is None:
        raise FreshnessError(
            f"no charter or generic PROTOCOL.md resolves for producer {producer!r}"
        )
    return compute_generic_role_revision(protocol), protocol


def _outbox_value(entry: str, field: str):
    return re.search(
        rf"(?:\*\*{re.escape(field)}:\*\*|^{re.escape(field)}:)\s*(\S+)",
        entry, flags=re.MULTILINE)


def _outbox_has_content(entry: str, field: str) -> bool:
    if _outbox_value(entry, field):
        return True
    return bool(re.search(
        rf"(?:\*\*{re.escape(field)}:\*\*|^{re.escape(field)}:)\s*\n"
        rf"[ \t]+(?:-\s+|\d+\.\s+|\S)", entry, flags=re.MULTILINE))


_producers_with_ready = set()
for ob in sorted(_outbox_paths):
    _prod_owner = _producer_of(ob)
    text = read_doc(ob)
    # Entries are `## <ID>: description` followed by bold-field lines (§ 2).
    _entry_heads = list(re.finditer(
        r"^## [A-Z]+-\d+:\s*\S.*$", text, flags=re.MULTILINE))
    entries = []
    if _entry_heads and text[:_entry_heads[0].start()].strip() == "# OUTBOX":
        _all_h2 = re.findall(r"^## .+$", text, flags=re.MULTILINE)
        if len(_entry_heads) == len(_all_h2):
            entries = [
                text[head.start() + 3:
                     _entry_heads[index + 1].start()
                     if index + 1 < len(_entry_heads) else len(text)]
                for index, head in enumerate(_entry_heads)
            ]
    frontmatter_only = False
    if not entries:
        frontmatter = re.fullmatch(r"---\s*\n(.*?)\n---\s*", text,
                                   flags=re.DOTALL)
        if frontmatter:
            entries = [frontmatter.group(1)]
            frontmatter_only = True
    if not entries and text.strip() != "# OUTBOX":
        producer_problem(
            _prod_owner, "producer-package-malformed",
            f"{ob.as_posix()} is nonempty but parses as zero OUTBOX entries -- "
            "malformed package text cannot be treated as an empty queue "
            "(PROTOCOL.md § 2)")
        outbox_ok = False
    for e in entries:
        outbox_seen += 1
        eid = "PACKAGE" if frontmatter_only else e.split(":", 1)[0].strip()
        loc = f"{ob.as_posix()} [{eid}]"
        status = _outbox_value(e, "status")
        status = status.group(1) if status else None
        if status is None:
            producer_problem(
                _prod_owner, "producer-package-malformed",
                f"{loc} has no **status:** -- the main agent cannot tell "
                f"whether this is collectable (PROTOCOL.md § 2)")
            outbox_ok = False
            continue
        if status not in OUTBOX_STATUSES:
            producer_problem(
                _prod_owner, "producer-package-malformed",
                f"{loc} status {status!r} is not one of "
                f"ready/draft/blocked/reviewed/stale (PROTOCOL.md § 2)")
            outbox_ok = False
        if status == "ready":
            _producers_with_ready.add(_prod_owner)
            for field in PACKAGE_HANDOFF_FIELDS:
                if not _outbox_has_content(e, field):
                    producer_problem(
                        _prod_owner, "producer-package-incomplete",
                        f"{loc} is status: ready but has no usable "
                        f"**{field}:** -- complete ready packages bind every "
                        f"handoff and freshness field (PROTOCOL.md § 2/§ 6)")
                    outbox_ok = False
            for field in ("summary", "critical"):
                if not _outbox_has_content(e, field):
                    producer_problem(
                        _prod_owner, "producer-package-incomplete",
                        f"{loc} is status: ready but has no **{field}:** -- "
                        f"collect reads that field to decide what to do with "
                        f"it (PROTOCOL.md § 2)")
                    outbox_ok = False
            # Fixer-type entry: carries a patch, so § 9 requires provenance.
            if re.search(r"\*\*patch:\*\*", e):
                for field in ("base_head", "verified"):
                    if not re.search(rf"\*\*{field}:\*\*", e):
                        producer_problem(
                            _prod_owner, "producer-package-incomplete",
                            f"{loc} hands over a patch as ready but has no "
                            f"**{field}:** -- a patch with no {field} is a "
                            f"diff nobody can re-check before applying "
                            f"(PROTOCOL.md § 9)")
                        outbox_ok = False
            # Role freshness is derived from effective charter content with
            # only the role_revision field removed. The declared value is
            # checked separately in the charter block; a package label never
            # becomes evidence merely because somebody bumped it by hand.
            _rr = _outbox_value(e, "role_revision")
            if _rr:
                _charter_rr = None
                _prod = _outbox_value(e, "producer")
                if _prod:
                    try:
                        _charter_rr, _cp = _current_role_revision(_prod.group(1))
                    except FreshnessError as exc:
                        producer_problem(
                            _prod_owner, "producer-package-stale",
                            f"{loc} cannot derive current role_revision: {exc}")
                        outbox_ok = False
                if _charter_rr is not None and _rr.group(1) != _charter_rr:
                    producer_problem(
                        _prod_owner, "producer-package-stale",
                        f"{loc} carries role_revision {_rr.group(1)!r} but "
                        f"the effective project-local "
                        f"{_prod.group(1) if _prod else '?'}.md charter derives "
                        f"{_charter_rr!r} -- produced under a "
                        f"superseded role, package is stale and MUST NOT be "
                        f"collected; the producer re-runs under the new "
                        f"charter (PROTOCOL.md § 6, T-542)")
                    outbox_ok = False
            # Source identity: HEAD binds committed bytes; the fingerprint
            # binds only the delta from that HEAD in Git mode. Both must match.
            _head = _outbox_value(e, "source_head")
            _fp = _outbox_value(e, "source_tree_fingerprint")
            if _source_identity is not None:
                if _head and _head.group(1) != _source_identity.source_head:
                    producer_problem(
                        _prod_owner, "producer-package-stale",
                        f"{loc} carries source_head {_head.group(1)!r} but "
                        f"current source_head is {_source_identity.source_head!r} "
                        f"-- package is stale and MUST NOT be collected")
                    outbox_ok = False
                if _fp and _fp.group(1) != _source_identity.source_tree_fingerprint:
                    producer_problem(
                        _prod_owner, "producer-package-stale",
                        f"{loc} carries source_tree_fingerprint "
                        f"{_fp.group(1)!r} but the current tree computes "
                        f"{_source_identity.source_tree_fingerprint!r} -- the "
                        f"tree changed since the "
                        f"package was produced (same HEAD or not), so it is "
                        f"stale and MUST NOT be collected (PROTOCOL.md § 6, "
                        f"T-543)")
                    outbox_ok = False
if outbox_seen and outbox_ok:
    ok(f"subSaipen OUTBOX entries well-formed ({outbox_seen} checked)")

# `--gate collect:<producer>` is the consumer's gate, so ABSENCE is a finding
# there too: collecting a producer that has published no ready package is the
# `Not ready: run ee first.` refusal (T-544), and a validator that stayed
# silent would let the caller read "no FAILs" as "safe to collect".
if GATE == "collect" and GATE_PRODUCER not in _producers_with_ready:
    fail(f"--gate collect:{GATE_PRODUCER} but no OUTBOX entry from that "
         f"producer is `status: ready` -- there is nothing to collect. Run the "
         f"producer's forced-fresh preparation first (CORE.md § 1.10 ee/qq)")
elif GATE == "collect" and GATE_PRODUCER not in _producers_failed_hard:
    ok(f"producer gate: {GATE_PRODUCER} has a ready package and every "
       f"completeness, freshness and role check above ran hard against it")

# CONVERGE.md stage M: the final freshness gate. Both required producers must
# have published a ready package, and every package check above ran hard for
# them. Missing entirely is a FAIL here and nowhere else -- outside the closure,
# a project with no wiki package is a project that has not run qq yet, which is
# not a defect.
if GATE == "converge":
    _missing = [f"{label} ({name})" for name, label in CONVERGE_REQUIRED_PRODUCERS
                if name not in _producers_with_ready]
    if _missing:
        fail(f"--gate converge but the closure's required producer package(s) "
             f"are missing or not ready: {', '.join(_missing)} -- CONVERGE.md "
             f"stages K/L/M require fresh EE and QQ bound to the current "
             f"source identity before the run may reach DONE")
    elif not _producers_failed_hard:
        ok("producer gate: both closure-required packages (EE, QQ) are ready "
           "and were checked hard for completeness, freshness and role currency")

# ------------------------------------------------------------ SAIUI CHARTER

saiui_charter = Path("extensions/subs/saiui.md")
saiui_mission = Path(".saipen/kitchen/SAIUI_SAISENT_MISSION.md")
saiui_ok = True

if IS_SAIPEN_HOME and saiui_charter.is_file():
    _charter = saiui_charter.read_text(encoding="utf-8-sig", errors="replace")

    # 1. Charter must reference canonical saipen/UI.md.
    if "saipen/UI.md" not in _charter:
        fail("saiui charter lost canonical saipen/UI.md reference -- "
             "the charter must load the one authoritative file by reference")
        saiui_ok = False

    if "Golden Default is the mandatory palette." not in _charter:
        fail("saiui charter lost the Golden Default mandate -- Vintage Golden "
             "is the design language, while UI.md's Wintage-derived Golden "
             "Default token set is the only palette")
        saiui_ok = False

    # 2. No copied palette or second palette.
    if re.search(r"(?i)(#[0-9a-f]{3,8}\s*;?\s*){3,}", _charter):
        fail("saiui charter contains a copied palette/token block -- "
             "colors must trace to saipen/UI.md, never be re-declared")
        saiui_ok = False
    if re.search(r"(?i)(second|alternate|alternative)\s+palette\s+(is|may|can|should|shall)",
                 _charter):
        fail("saiui charter declares a second palette -- "
             "Vintage Golden is the single canonical palette")
        saiui_ok = False

    # 3. Main-tree write ban must not be softened.
    if not re.search(r"(?i)never\s+write\s+.*main\s+(project\s+)?tree", _charter):
        fail("saiui charter softened or removed the main-tree write ban -- "
             "the charter must forbid main-project writes")
        saiui_ok = False

    # 4. Fixer pen/OUTBOX requirement must be present.
    if "kitchen/pen/" not in _charter or "OUTBOX.md" not in _charter:
        fail("saiui charter removed fixer pen or OUTBOX requirement -- "
             "the charter must bind to PROTOCOL.md § 9 fixer contract")
        saiui_ok = False

    if saiui_ok:
        _charter_ok = True
elif IS_SAIPEN_HOME:
    fail("saiui built-in role charter extensions/subs/saiui.md is missing -- "
         "a shipped built-in role must carry its canonical charter")
    saiui_ok = False
else:
    _charter_ok = False

if IS_SAIPEN_HOME:
    # 5. UI- prefix must be in the ticket namespace table.
    # 6. Bootstrap must mention sai*.md charters in copy list.
    # 7. Role adoption must load project-local charter.
    # 8. Sync must guard against touching live sub folders.
    _proto = Path("extensions/subs/PROTOCOL.md")
    if _proto.is_file():
        _proto_text = _proto.read_text(encoding="utf-8-sig", errors="replace")
        if not re.search(r"\|\s*`UI-`\s*\|", _proto_text):
            fail("saiui lacks explicit UI- prefix in PROTOCOL.md ticket table -- "
                 "built-in roles require a documented namespace")
            saiui_ok = False
        if "sai*.md" not in _proto_text:
            fail("PROTOCOL.md spawn/sync does not mention sai*.md built-in charters -- "
                 "first bootstrap would omit role charters")
            saiui_ok = False
        if not re.search(r"load\s+it\s+after\s+PROTOCOL\.md", _proto_text):
            fail("PROTOCOL.md bare-subname adoption lost charter-loading language -- "
                 "a subSaipen whose charter exists must load it on adoption")
            saiui_ok = False
        if not re.search(r"(?i)never\s+(touch|looks?\s+inside)\s+.*<name>",
                         _proto_text):
            fail("PROTOCOL.md sync lost the live-folder guard -- "
                 "sync must never touch any <name>/ folder")
            saiui_ok = False

    if saiui_ok:
        ok("saiui charter integrity verified (references UI.md, no second palette, "
           "write ban enforced, fixer contract present, UI- prefix documented, "
           "bootstrap includes charters)")

# ------------------------------------------------------- CHARTER METADATA

# T-541: every shipped sai*.md charter must declare its machine-readable
# metadata block -- the eight keys a tool can read without parsing prose.
# A charter missing the block, a role_kind outside the closed set, or a
# missing PRODUCER charter for a shipped producer is a contract break, not a
# documentation gap: outbox.schema.json and the freshness checks (T-542) read
# role_kind/collect_policy/role_revision from exactly this block.
_CHARTER_KEYS = ("role_kind", "write_scope", "trigger", "collect_policy",
                 "done_condition", "freshness_inputs", "output_contract",
                 "role_revision")
_CHARTER_ROLE_KINDS = ("SCOUT", "FIXER", "PRODUCER", "TOOL")
_CHARTER_COLLECT_POLICIES = ("automatic", "core-review", "explicit")
if IS_SAIPEN_HOME:
    _subs_dir = Path("extensions/subs")
    _charters = sorted(_subs_dir.glob("sai*.md")) if _subs_dir.is_dir() else []
    _bad_charters = []
    for _c in _charters:
        _ct = _c.read_text(encoding="utf-8-sig", errors="replace")
        _blocks = re.findall(r"```yaml\n(.*?)```", _ct, re.DOTALL)
        if not _blocks:
            _bad_charters.append(f"{_c.name}: no ```yaml metadata block")
            continue
        _block = "\n".join(_blocks)
        _missing = [k for k in _CHARTER_KEYS
                    if not re.search(rf"^{re.escape(k)}:", _block, re.MULTILINE)]
        if _missing:
            _bad_charters.append(f"{_c.name}: missing keys {', '.join(_missing)}")
            continue
        _rk = re.search(r"^role_kind:\s*(\S+)", _block, re.MULTILINE)
        _cp = re.search(r"^collect_policy:\s*(\S+)", _block, re.MULTILINE)
        if _rk and _rk.group(1) not in _CHARTER_ROLE_KINDS:
            _bad_charters.append(
                f"{_c.name}: role_kind {_rk.group(1)!r} not in "
                f"{'/'.join(_CHARTER_ROLE_KINDS)}")
        if _cp and _cp.group(1) not in _CHARTER_COLLECT_POLICIES:
            _bad_charters.append(
                f"{_c.name}: collect_policy {_cp.group(1)!r} not in "
                f"{'/'.join(_CHARTER_COLLECT_POLICIES)}")
        _required_policy = {
            "PRODUCER": "explicit",
            "SCOUT": "core-review",
            "FIXER": "core-review",
        }.get(_rk.group(1) if _rk else "")
        if (_required_policy is not None and _cp
                and _cp.group(1) != _required_policy):
            _bad_charters.append(
                f"{_c.name}: role_kind {_rk.group(1)} requires collect_policy "
                f"{_required_policy!r}, got {_cp.group(1)!r}")
        _fi = re.search(r"^freshness_inputs:\s*\[(.*?)\]", _block,
                        re.MULTILINE)
        _inputs = set(re.findall(r'["\']([a-z_]+)["\']',
                                 _fi.group(1) if _fi else ""))
        _required_inputs = {"source_head", "source_tree_fingerprint",
                            "role_revision"}
        if _inputs != _required_inputs:
            _bad_charters.append(
                f"{_c.name}: freshness_inputs {sorted(_inputs)} != "
                f"{sorted(_required_inputs)}")
        _oc = re.search(r"^output_contract:\s*[\"']?([^\n\"']+)",
                        _block, re.MULTILINE)
        if _oc is None or not re.search(
                r"PROTOCOL\.md § 2(?!\d)", _oc.group(1)):
            _bad_charters.append(
                f"{_c.name}: output_contract must cite PROTOCOL.md § 2")
        _local_field_names = set(re.findall(
            r"(?m)^- `([a-z_]+)(?::[^`]*)?`(?:\s|$)", _ct))
        if len(_local_field_names & PACKAGE_HANDOFF_FIELDS) >= 3:
            _bad_charters.append(
                f"{_c.name}: restates moving OUTBOX required fields instead "
                "of citing PROTOCOL.md § 2/§ 9")
        _declared = re.search(r"^role_revision:\s*[\"']?([^\s\"']+)",
                              _block, re.MULTILINE)
        try:
            _derived = compute_role_revision(_c)
        except FreshnessError as exc:
            _bad_charters.append(f"{_c.name}: {exc}")
        else:
            if _declared is None or _declared.group(1) != _derived:
                _bad_charters.append(
                    f"{_c.name}: declared role_revision "
                    f"{_declared.group(1) if _declared else None!r} != "
                    f"effective charter digest {_derived!r}")
    for _need, _kind in (("saiwiki.md", "PRODUCER"), ("saitranslate.md", "PRODUCER")):
        _cand = _subs_dir / _need
        _found_kind = False
        if _cand.is_file():
            _bl = re.findall(r"```yaml\n(.*?)```",
                             _cand.read_text(encoding="utf-8-sig", errors="replace"),
                             re.DOTALL)
            _found_kind = any(
                re.search(rf"^role_kind:\s*{_kind}\b", b, re.MULTILINE)
                for b in _bl)
        if not _found_kind:
            _bad_charters.append(
                f"{_need} must exist and declare role_kind {_kind}")
    if _bad_charters:
        fail("charter-metadata: " + "; ".join(_bad_charters)
             + " -- every shipped sai*.md must declare all eight metadata "
               "keys with role_kind/collect_policy from the closed sets "
               "(T-541)")
    else:
        ok(f"{len(_charters)} shipped sai*.md charter(s) declare the full "
           f"metadata block ({len(_CHARTER_KEYS)} keys, closed enums)")

    # T-543..T-547 hardening invariants. Runtime fingerprint behavior has
    # executable probes; these checks pin the command/cleanup/worker contracts
    # that have no universal agent runtime to execute for us.
    _hardening_docs = {
        "PROTOCOL.md": Path("extensions/subs/PROTOCOL.md"),
        "prepare.md": Path("saipen/phases/prepare.md"),
        "hunt.md": Path("saipen/phases/hunt.md"),
        "CORE.md": Path("saipen/CORE.md"),
    }
    _hardening_text = {
        name: path.read_text(encoding="utf-8-sig", errors="replace")
        for name, path in _hardening_docs.items() if path.is_file()
    }
    _hardening_required = {
        "PROTOCOL.md": (
            "git-delta-v1", "--exclude-standard", "path_length[uint64be]",
            "`except OSError: continue` escape hatch.",
            "Age MAY emit a warning.", "Repeated collects MAY leave reviewed",
            "unpreserved recovery evidence",
            "never MANIFEST, STATE, BOARD, LOG, kitchen, charter adoption, or lifecycle",
            "`collect_policy` is executable routing, not a label",
            "autonomous HUNT/continue/",
            "`core-review` creates normal Core work",
            "### 3.1 Built-in role charters",
        ),
        "prepare.md": (
            "Forced-fresh preparation", "deterministic cache contract",
            "source_head`, `source_tree_fingerprint`, `role_revision",
            "only this producer preparation writes replacement evidence",
        ),
        "hunt.md": (
            "EPHEMERAL WORKERS, not SubSaipen instances",
            "never enter `MANIFEST.md`",
            "never receive", "STATE/BOARD/LOG/kitchen or lifecycle state",
        ),
        "CORE.md": (
            "Core is a consumer", "MUST NOT edit, revalidate, refresh",
            "after the shipped revision", "against the shipped HEAD",
            "With `execution_intent: converge`, continue resumes convergence",
        ),
    }
    _hardening_missing = []
    for _doc_name, _markers in _hardening_required.items():
        _body = _hardening_text.get(_doc_name, "")
        for _marker in _markers:
            if _marker not in _body:
                _hardening_missing.append(f"{_doc_name}: {_marker!r}")
    if _hardening_missing:
        fail("freshness hardening contract drift -- missing "
             + "; ".join(_hardening_missing))
    else:
        ok("freshness hardening command/cleanup/worker contracts intact")

    # T-549 is the single hard barrier for the improve wave. The generic DAG
    # makes T-551 unworkable while T-549 is unresolved; every later improve
    # ticket already depends transitively on T-551. Visual order is irrelevant.
    _board_body = Path(".saipen/BOARD.md").read_text(
        encoding="utf-8-sig", errors="replace")
    _t549_done = bool(re.search(
        r"(?ms)^## DONE\s.*?^- \[x\] T-549\b", _board_body))
    _t551 = re.search(r"(?m)^- \[[ /x]\] T-551\b([^\n]*)", _board_body)
    _t551_needs = (set(re.findall(r"T-\d+", re.search(
        r"\| needs:\s*([^|]+)", _t551.group(1)).group(1)))
        if _t551 and re.search(r"\| needs:\s*([^|]+)", _t551.group(1))
        else set())
    if not _t549_done and "T-549" not in _t551_needs:
        fail("hardening wave barrier missing -- unresolved T-549 must make "
             "T-551 unworkable via `needs: T-549`; BOARD order cannot block "
             "the Pick Rule from entering T-551..T-561")
    elif not _t549_done and re.search(
            r"(?m)^- \[/\] T-55(?:1|[2-9])\b|^- \[/\] T-56[01]\b",
            _board_body):
        fail("hardening wave barrier breached -- an improve-wave ticket is "
             "DOING while T-549 remains unresolved")
    else:
        ok("T-549 hard barrier blocks the T-551..T-561 improve wave")

# CONVERGE.md owns the convergence stage ORDER. The failure this pins is not a
# missing file -- it is a sequence that quietly loses a stage or swaps two of
# them, which reads perfectly and produces a run that prepares its factories
# before the cleanup that invalidates them. The stages are checked by position,
# so a reordering fails even though every letter is still present.
if IS_SAIPEN_HOME:
    _conv = home_doc("CONVERGE.md")
    if not _conv.is_file():
        fail("[converge-contract] saipen/CONVERGE.md is missing -- INDEX.md and "
             "the phase docs point at it as the owner of the cc stage order")
    else:
        _conv_text = _conv.read_text(encoding="utf-8-sig", errors="replace")
        _stages = [
            ("A", "RECOVER"), ("B", "FINISH CURRENT WORK"),
            ("C", "EXHAUST REAL BOARD WORK"),
            ("D", "COLLECT ACTIONABLE SUBSAIPEN RESULTS"),
            ("E", "CANONICAL TEST / VALIDATE GATE"), ("F", "FORCED HUNT"),
            ("G", "CLEAN"), ("H", "POST-CLEAN TEST GATE"),
            ("I", "FINAL FORCED HUNT"), ("J", "SUBSAIPEN FACTORY SYNC"),
            ("K", "FRESH EE"), ("L", "FRESH QQ"),
            ("M", "FINAL FRESHNESS CHECK"),
        ]
        _positions, _absent = [], []
        for _letter, _title in _stages:
            _at = _conv_text.find(f"**{_letter}. {_title}.**")
            if _at < 0:
                _absent.append(f"{_letter}. {_title}")
            else:
                _positions.append((_letter, _at))
        if _absent:
            fail("[converge-contract] CONVERGE.md is missing stage(s): "
                 + "; ".join(_absent)
                 + " -- the contract is the whole order, and a run that cannot "
                   "read a stage skips it")
        elif [p for _, p in _positions] != sorted(p for _, p in _positions):
            fail("[converge-contract] CONVERGE.md states its stages out of "
                 "order: "
                 + " ".join(letter for letter, _ in
                            sorted(_positions, key=lambda pair: pair[1]))
                 + " -- preparing the producer packages before the cleanup and "
                   "hunts that invalidate them is the exact defect the order "
                   "exists to prevent")
        if "## The closure bar" not in _conv_text:
            fail("[converge-contract] CONVERGE.md carries no closure bar -- the "
                 "stage order says what to do and the bar is what says a run "
                 "may stop, which is the half a converge run gets wrong")
        if "Nothing that mutates main source may run after K." not in _conv_text:
            fail("[converge-contract] CONVERGE.md lost the ordering rule that "
                 "no main-source mutation may follow the producer preparation "
                 "-- without it the factories can be freshly built against a "
                  "tree the next stage changes")
        _closure_markers = (
            "no workable `## TODO` ticket",
            "canonical tests PASS against the tree",
            "no fresh critical scout or fixer OUTBOX",
            "CLEAN completed, or proved nothing safe remained",
            "final forced HUNT after CLEAN came back clean",
            "existing hunt -> clean marker cannot satisfy forced HUNT",
        )
        _missing_closure = [marker for marker in _closure_markers
                            if marker not in _conv_text]
        if _missing_closure:
            fail("[converge-contract] closure evidence drift -- missing "
                 + "; ".join(repr(marker) for marker in _missing_closure))
        if ("converge_target: ship" not in _conv_text
                or "CCC SHIP boundary between" not in _conv_text
                or "MUST NOT execute J, K, or L before SHIP" not in _conv_text):
            fail("[converge-contract] ccc lost its persisted I -> SHIP -> J "
                 "boundary -- plain cc would prepare EE/QQ before the ship that "
                 "changes their source_head")
        if not any("converge-contract" in problem for problem in failures):
            ok(f"convergence contract intact ({len(_stages)} stages in order, "
               "closure bar and post-K ordering rule present)")

# Target mission must not claim SAISENT was audited from this repo.
if saiui_mission.is_file():
    _mission = saiui_mission.read_text(encoding="utf-8-sig", errors="replace")
    if re.search(r"(?i)(SAISENT|target)\s+(was|has been|already)\s+(audited|checked|verified|patched)",
                 _mission):
        fail("SAIUI SAISENT mission claims the target was audited from this "
             "repository -- the mission must label findings as hypotheses to verify")
    elif "hypothes" in _mission.lower() and "VERIFY" in _mission:
        ok("SAIUI SAISENT mission labels findings as hypotheses to verify")

# ------------------------------------------------------------ KNOWLEDGE

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

# ------------------------------------------------- USERPERSON (T-574)

# Optional preference profile, OFF by default. Absence is silent -- no
# warning, no boot failure, no placeholder, no cold-start cost. When the
# file exists it must be well-formed, because `saipen userperson add` merges
# semantically and duplicate preference history is the failure mode that
# rule exists to stop.
_userperson_path = Path(".saipen/USERPERSON.md")
if _userperson_path.is_file():
    _up_errors = _validate_userperson_profile(
        _userperson_path.read_text(encoding="utf-8-sig"))
    if _up_errors:
        for _up_err in _up_errors:
            fail(f".saipen/USERPERSON.md {_up_err} -- the optional USERPERSON "
                 f"profile is active but malformed (T-574)")
    else:
        ok(".saipen/USERPERSON.md is a well-formed optional USERPERSON profile")

# ------------------------------------------------- IMPROVE (T-551..T-560)

# Improve reports are read-only evidence owned by seats; the validator checks
# their schema. Dispositions live in the Core-owned SWEEP ledger, never in the
# report. The roster is routing-only: carrying draft/complete/swept status
# would duplicate truth owned by the report and the sweep ledger.
_improve_root = Path(".saipen/improve")
if _improve_root.is_dir():
    for _report in sorted(_improve_root.rglob("saipen_improve_*.md")):
        _rtext = _report.read_text(encoding="utf-8-sig")
        if re.search(r"(?m)^saipen_home:\s*\S", _rtext):
            fail(f"improve report {_report} carries a machine-local "
                 f"saipen_home path in its header -- report identity uses "
                 f"saipen_version + protocol_fingerprint (T-555)")
        for _rerr in _validate_improve_report(_rtext):
            fail(f"improve report {_report}: {_rerr}")
    for _manifest in sorted(_improve_root.rglob("MANIFEST.md")):
        _mtext = _manifest.read_text(encoding="utf-8-sig")
        for _status_word in ("draft", "complete", "swept"):
            if re.search(rf"(?m)^status:\s*{_status_word}\b", _mtext):
                fail(f"improve cycle manifest {_manifest} carries "
                     f"{_status_word} status -- the roster owns routing only; "
                     f"report status is owned by the report and dispositions "
                     f"by the sweep ledger (T-570)")
                break

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

            # A CONFORMANCE row is shipped evidence: it says an invariant is
            # enforced NOW, and cites the ticket that landed it. A row citing
            # a ticket still sitting in ## TODO / ## BLOCKED is therefore two
            # documents contradicting each other -- one says shipped, the
            # other says not started -- and whichever the reader trusts, the
            # other is a lie. This is also the only mechanical witness this
            # repository has for the wider failure it keeps committing: work
            # landing in the tree with the board and LOG untouched.
            # Reproduced verbatim -- rows 193 and 196 shipped citing T-419 and
            # T-426 while both sat in ## TODO, their code already in the tree,
            # no LOG event for either. A ticket that is absent from the board
            # entirely is history, not a contradiction: ## DONE is pruned
            # deliberately (§ 1.2) and the rows outlive it.
            #
            # `## DOING` is exempt, and row 213 is why. T-466 established that
            # the ticket stays in `## DOING` through SHIP and reaches
            # `## DONE` only at the DONE phase once the push has landed --
            # so `## DOING` is precisely where a ticket sits while its own row
            # is in the tree waiting to be committed. Requiring `## DONE` here
            # made every ticket that adds a row unshippable: the pre-commit
            # hook runs this validator, the row cannot land before the ticket
            # closes, and the ticket cannot close before the push. Two shipped
            # rules, no legal state between them; hit live on the first row
            # written after T-466 shipped. Nothing is lost by the exemption --
            # the defect this check was built for had both tickets in
            # `## TODO`, and `## DOING` is capped at one claimed ticket in
            # total (§ 1.11), so it cannot hide a backlog of unbacked rows.
            _row_cites = []
            for _ln, _line in enumerate(
                    conformance_path.read_text(
                        encoding="utf-8-sig").splitlines(), 1):
                _rm = re.match(r"^\|\s*(\d+)\s*\|", _line)
                if not _rm:
                    continue
                for _cited in sorted(set(re.findall(r"\(T-\d+\)", _line))):
                    _tk = tickets.get(_cited.strip("()"))
                    if _tk and _tk["section"] not in ("## DONE", "## DOING"):
                        _row_cites.append(
                            f"row {_rm.group(1)} cites {_cited.strip('()')}, "
                            f"which is in {_tk['section']}")
            if _row_cites:
                fail("CONFORMANCE row cites unfinished work -- "
                     + "; ".join(_row_cites)
                     + ". The row says the invariant is enforced and the "
                       "board says the ticket has not been done: one of the "
                       "two is wrong, and a reader has no way to tell which. "
                       "Either the row shipped early, or work landed and the "
                       "board was never checkpointed (RFC § 1.5)")

        # The mojibake half of this lint applies to any shipped text, not just
        # the four core docs -- corruption does not respect a curated list.
        # KNOWLEDGE/, extensions/ and the fixture READMEs were outside it until
        # v7.103.0, so an arrow mangled in traps.md sat unseen by the very
        # check whose subject traps.md documents.
        text_targets = [
            Path("saipen/HABITS.md"),
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
        # A C0 control character in a shipped tool is invisible in every
        # reader an agent uses and changes what the code MEANS. Found live:
        # `tools/audit_checks.py` carried two `\x01` bytes where a regex
        # replacement wanted the literal backreference `\1`, so both
        # `verify_attempts` red controls substituted a SOH character instead
        # of the captured ticket line -- the mutation destroyed the line, the
        # validator FAILed on the shape rather than the cap, and the harness
        # scored them as passing controls for a release. Neither ruff nor the
        # doc lint above can see it: the file is valid UTF-8 and valid Python.
        # Tabs, newlines and carriage returns are the only C0 bytes that
        # legitimately appear.
        _ctl_ok = True
        _ctl = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
        # Swept across every shipped text file, not just tools/. The two
        # instances found when this widened were both in documents
        # DESCRIBING this exact defect: a sealed LOG segment and the
        # CHANGELOG archive each carried a raw 0x01 where the prose
        # meant the escape sequence. The bug bit the record of itself,
        # which is precisely how an invisible byte survives review.
        _ctl_targets = sorted((_tools_parent / "tools").glob("*.py"))
        for _sub in ("saipen", "extensions", ".saipen/logs"):
            _d = _tools_parent / _sub
            if _d.is_dir():
                _ctl_targets += sorted(_d.rglob("*.md"))
        _ctl_targets += [_p for _p in (_tools_parent / "CHANGELOG.md",
                                       _tools_parent / "CHANGELOG_ARCHIVE.md")
                         if _p.is_file()]
        for _tool in _ctl_targets:
            _hit = _ctl.search(_tool.read_text(encoding="utf-8",
                                               errors="replace"))
            if _hit:
                fail(f"{_tool.relative_to(_tools_parent).as_posix()} contains control character "
                     f"U+{ord(_hit.group()):04X} at offset {_hit.start()} -- "
                     f"invisible in every reader, valid UTF-8 and valid "
                     f"Python, and it silently changes what the code does "
                     f"(two red controls scored green on exactly this)")
                _ctl_ok = False
                text_ok = False
        if _ctl_ok:
            ok(f"no stray control characters in shipped text "
               f"({len(_ctl_targets)} files swept)")

        if text_ok:
            ok("core docs text lint clean (no U+FFFD/split keywords/fence drift)")

        # Distribution integrity -- the v7.22.3/v7.25.0 bug class, machine-checked.
        # Five separate times this repo promised a file in one place and never
        # wired its delivery in another; each was found by archaeology. These
        # structural checks make the remaining class a validator FAIL; actual
        # injector delivery is executed by tools/run_scenarios.py.

        # A. RFC's phase enum <-> phases/ docs, both directions.
        rfc_text = _read_rfc(Path("saipen/RFC.md"))
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

            # INDEX.md must carry the same phase set: the lazy-load index is
            # how a cold agent finds the current phase document, so an INDEX
            # that names a phase that doesn't exist (or omits one that does)
            # sends it to a dead file or hides a real one. (Goal blind spot
            # 6/7.) Parse the `- <name>.md:` lines under INDEX's phase
            # heading and require exact parity with the enum + files.
            _index_p = Path("saipen/INDEX.md")
            if _index_p.is_file():
                _idx = _index_p.read_text(encoding="utf-8-sig")
                _idx_phases = sorted(
                    re.findall(r"^- `([a-z]+)\.md`:", _idx, re.MULTILINE))
                _disk_phases = sorted(
                    p.stem for p in Path("saipen/phases").glob("*.md"))
                _idx_enum = sorted(n.lower() for n in phase_names)
                if _idx_phases != _idx_enum:
                    fail("INDEX.md phase list does not match the canonical "
                         f"phase enum -- INDEX names {len(_idx_phases)} phases, "
                         f"enum has {len(_idx_enum)}. Missing: "
                         f"{sorted(set(_idx_enum)-set(_idx_phases)) or 'none'}; "
                         f"phantom: {sorted(set(_idx_phases)-set(_idx_enum)) or 'none'}")
                    enum_ok = False
                elif _idx_phases != _disk_phases:
                    fail("INDEX.md phase list does not match the files under "
                         f"phases/ -- INDEX names {len(_idx_phases)}, disk has "
                         f"{len(_disk_phases)}. Missing: "
                         f"{sorted(set(_disk_phases)-set(_idx_phases)) or 'none'}; "
                         f"phantom: {sorted(set(_idx_phases)-set(_disk_phases)) or 'none'}")
                    enum_ok = False
                else:
                    ok(f"INDEX.md phase list matches enum + files "
                       f"({len(_idx_phases)} phases)")

            # T-552/T-561: Improve is a meta-control, never a phase. The
            # no-phase proof is mechanical: no phases/improve.md may exist, no
            # IMPROVE enum row may appear, and the canonical IMPROVE.md must
            # state it is not a phase. A `phases/improve.md` would be an
            # unofficial seventeenth phase hiding inside the phase directory.
            if Path("saipen/phases/improve.md").is_file():
                fail("cross-doc drift [improve-meta-control] -- "
                     "saipen/phases/improve.md exists; Improve is a "
                     "meta-control and must never become an unofficial "
                     "seventeenth phase (saipen/IMPROVE.md, T-552)")
                enum_ok = False
            if "IMPROVE" in phase_names:
                fail("cross-doc drift [improve-meta-control] -- the phase enum "
                     "contains IMPROVE; Improve is a meta-control and the "
                     "phase count must stay 16 (T-552)")
                enum_ok = False
            _ops_doc = Path("saipen/OPS.md")
            if not _ops_doc.is_file():
                fail("cross-doc drift [ops-owner] -- saipen/OPS.md is the "
                     "mechanical execution layer contract and is missing")
                enum_ok = False
            else:
                _ops_t = _ops_doc.read_text(encoding="utf-8-sig")
                if "PYTHON DEFINES HOW" not in _ops_t:
                    fail("cross-doc drift [ops-owner] -- saipen/OPS.md does "
                         "not state the mechanical boundary")
                    enum_ok = False
                # A shipped document the router never names is unreachable on
                # the cold path: the agent with a mechanical-operation question
                # reads CORE.md instead and never learns the OPS contract
                # exists. That is the RFC routing trap T-549 closed, one file
                # over -- so INDEX.md naming OPS.md is checked, not assumed.
                _index_doc = Path("saipen/INDEX.md")
                if _index_doc.is_file() and \
                        "OPS.md" not in _index_doc.read_text(
                            encoding="utf-8-sig"):
                    fail("cross-doc drift [ops-owner] -- saipen/INDEX.md does "
                         "not route to saipen/OPS.md; a mechanical-operation "
                         "question has no way to reach the OPS contract")
                    enum_ok = False

            _improve_doc = Path("saipen/IMPROVE.md")
            if not _improve_doc.is_file():
                fail("cross-doc drift [improve-meta-control] -- "
                     "saipen/IMPROVE.md is the single canonical Improve owner "
                     "and is missing (T-552)")
                enum_ok = False
            else:
                _imp_t = _improve_doc.read_text(encoding="utf-8-sig")
                if "meta-control" not in _imp_t.lower():
                    fail("cross-doc drift [improve-meta-control] -- "
                         "saipen/IMPROVE.md does not state that Improve is a "
                         "meta-control, not a phase")
                    enum_ok = False

        # T-553: Improve routing/status is DERIVED from the cycle manifest +
        # reports + SWEEP ledger -- never maintained as independent STATE
        # fields. A flat `improve_*` field survives only if a routing decision
        # cannot be answered by reading the manifest; finding text never
        # belongs in canonical STATE (findings live in seat reports under
        # .saipen/improve/, judgment in SWEEP.md).
        _imp_state_keys = [k for k in state if k.lower().startswith("improve")]
        if _imp_state_keys:
            fail("cross-doc drift [improve-state-purity] -- STATE.md carries "
                 "improve routing field(s) "
                 + ", ".join(sorted(_imp_state_keys))
                 + "; improve status is DERIVED from the cycle manifest + "
                 "reports + sweep ledger, never maintained as independent "
                 "STATE counters (T-553)")
        _state_finding = re.search(
            r"(?m)^(?:expected|actual|evidence):\s*\S|^IMP-\d+\b",
            read_doc(state_path))
        if _state_finding:
            fail("cross-doc drift [improve-state-purity] -- STATE.md carries "
                 "finding text (an expected/actual/evidence triple or an "
                 "IMP-### marker); findings live in seat reports under "
                 ".saipen/improve/, judgment lives in SWEEP.md -- never in "
                 "canonical STATE (T-553)")

        # B. Every runtime file the protocol references must exist in the home.
        # Canonical source is saipen/MANIFEST.json; the hardcoded list below
        # is the fallback for homes that predate the manifest (v7.190.0+).
        _manifest_json = _tools_parent / "saipen" / "MANIFEST.json"
        if _manifest_json.is_file():
            try:
                _mj = json.loads(_manifest_json.read_text("utf-8"))
                _mj_files = [f["src"] for f in _mj.get("files", [])]
                _phase_dir = _mj.get("phase_docs", {}).get("src_dir", "")
                for _pf in _mj.get("phase_docs", {}).get("files", []):
                    _mj_files.append(f"{_phase_dir}/{_pf}")
                manifest = _mj_files
            except (json.JSONDecodeError, KeyError, ValueError):
                fail("saipen/MANIFEST.json is present but unparseable — "
                     "the canonical manifest is corrupt")
                manifest = []
        else:
            manifest = [
                "VERSION",
                "saipen/RFC.md",
                "saipen/CORE.md", "saipen/MAINTENANCE.md",
                "saipen/BOOT.md", "saipen/SKILL.md", "saipen/UI.md", "saipen/STYLE.md",
                "saipen/CONFORMANCE.md", "saipen/INDEX.md", "saipen/HABITS.md",
                "tools/validate.py", "tools/install_hook.py", "tools/uninstall_hook.py",
                "tools/freshness.py",
                "tools/run_scenarios.py", "tools/audit_floor.py",
                "tools/ci_status.py",
                "tools/release_ledger_baseline.json",
                "tests/validate.sh", "tests/validate.ps1",
                "bootstrap/inject.sh", "bootstrap/inject.ps1",
                "extensions/schemas/state.schema.json",
                "extensions/templates/STATE.md", "extensions/templates/BOARD.md",
                "extensions/templates/LOG.md",
            ]
        manifest_missing = [f for f in manifest if not Path(f).is_file()]
        for f in manifest_missing:
            fail(f"runtime manifest file missing from the home: {f}")
        # Present on THIS disk is not the same as present in the repository,
        # and the gap is the whole failure: an untracked working-tree file
        # satisfies `is_file()` forever on the machine that created it, while
        # every clone -- CI included -- gets a home missing a runtime file.
        # Shipped exactly that way for three releases here: a manifest entry
        # for an uncommitted tool went green locally on every commit and red
        # on every CI run, and no local gate could see the difference.
        manifest_untracked = []
        if not manifest_missing and _git("rev-parse", "--git-dir")[0] == 0:
            for f in manifest:
                if not _git("ls-files", "--", f)[1].strip():
                    manifest_untracked.append(f)
        for f in manifest_untracked:
            fail(f"runtime manifest names a file git does not track: {f} -- it "
                 f"exists here and in no clone, so this home ships complete "
                 f"and every checkout of it does not. Commit the file or drop "
                 f"the manifest entry")
        if not manifest_missing and not manifest_untracked:
            ok(f"runtime manifest complete ({len(manifest)} files, all tracked)")

        # Injector behavior is executed by tools/run_scenarios.py for both
        # shells. This manifest owns only the structural question: are the two
        # entry-point scripts present? Reading their source cannot prove copy
        # order, stale-directory replacement, or installed artifacts.

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

    # RFC.md is a three-line compatibility stub since v7.190.0. Any adapter
    # or SKILL.md that assigns it normative authority sends a weak agent to
    # a file with no rules -- the RFC-stub-trap (goal blind spot 5). The
    # constitution lives in CORE.md; RFC.md is a redirect only.
    # The two shell injectors belong in this set and were missing from it for
    # three releases (T-529). They write the entry block into every agent's
    # global config -- ~/.claude/CLAUDE.md, ~/.config/opencode/AGENTS.md,
    # ~/.codex/AGENTS.md, ~/.gemini/GEMINI.md -- so they reach FURTHER than any
    # adapter does, and a glob restricted to `adapters/*.md` could never see
    # them. Checking the markdown that describes the boot path while skipping
    # the code that installs it is the same shape T-495 named.
    _rfc_stub_trap = []
    _trap_targets = [*sorted(adapter_dir.glob("*.md")),
                     Path("saipen/SKILL.md"),
                     Path("bootstrap/inject.sh"),
                     Path("bootstrap/inject.ps1")]
    for _doc in _trap_targets:
        if not _doc.is_file():
            continue
        _t = _doc.read_text(encoding="utf-8-sig")
        # `RFC\.md\s*\+` and `read[^.\n]*RFC\.md` are the boot-SET shapes, and
        # they are what the old pattern list could not see: the live text said
        # "read <home>/RFC.md + <home>/STYLE.md and follow them", where `follow`
        # trails RFC.md instead of preceding it, so `follow.*RFC\.md` never
        # matched the exact sentence this check exists to catch. Naming RFC.md
        # as a file to LOAD is the defect; naming it to say it holds no rules
        # is the fix, so the gap classes stay newline-bounded and dot-bounded
        # rather than banning the string outright.
        if re.search(r"RFC\.md.*is the constitution|RFC\.md.*full protocol|"
                     r"read.*RFC\.md.*constitution|RFC\.md.*authoritative|"
                     r"follow.*RFC\.md|"
                     r"RFC\.md\s*\+|read[^.\n]*RFC\.md", _t, re.IGNORECASE):
            _rfc_stub_trap.append(_doc.as_posix())
        # Every pattern above requires the literal `RFC.md`, and that is how
        # the drift survived a release: `saipen/SKILL.md` routed a reader to
        # bare "RFC" -- "it points into RFC only when a rule question comes
        # up", "read it right after BOOT.md, before RFC" -- naming the stub as
        # a rule DESTINATION with no file extension for the check to catch.
        # This rung is semantic rather than literal: a routing verb pointed at
        # RFC is the defect regardless of how the file is spelled. Mentioning
        # RFC to say it holds no rules stays legal, which is why the exemption
        # is scoped to the same sentence rather than to the whole document --
        # one redirect sentence elsewhere must not license a route here.
        for _seg in re.split(r"(?<=[.!?])\s+|\n", _t):
            if not re.search(r"\bRFC\b", _seg, re.IGNORECASE):
                continue
            if not re.search(
                    r"\b(?:read|go\s+to|open|consult|refer\s+to|load|"
                    r"points?\s+in(?:to)?|routes?\s+(?:in)?to|before|see)\b"
                    r"[^.\n]{0,40}\bRFC\b", _seg, re.IGNORECASE):
                continue
            if re.search(r"redirect|stub|compatibility|holds no rules|"
                         r"no rules|never|not a destination|superseded|"
                         r"successor|split", _seg, re.IGNORECASE):
                continue
            _rfc_stub_trap.append(f"{_doc.as_posix()} ({_seg.strip()[:80]})")
    if _rfc_stub_trap:
        fail("RFC-stub-trap: " + ", ".join(_rfc_stub_trap)
             + " assigns normative authority to the RFC.md compatibility "
               "stub. The constitution was split into CORE.md/MAINTENANCE.md "
               "in v7.190.0; adapters and injectors must load "
               "BOOT -> INDEX -> CORE instead")
        adapter_ok = False
    elif adapter_dir.is_dir():
        ok(f"no adapter or injector treats RFC.md as normative "
           f"({len(_trap_targets)} checked, RFC stub is redirect-only)")

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

    # A translated shortcut paragraph is small, but its consumers are not:
    # 32 locale sources, three root mirrors, 33 locale guides, plus the two
    # root entry docs. SAIT-008 wrote most of them directly and produced two
    # independently translated versions per language; visible grammar errors
    # appeared in the guide half immediately. Keep one locale source and make
    # every non-Core guide an exact link-adjusted consumer of it. This check
    # cannot judge prose quality, but it makes semantic loss, duplicate drift,
    # a stale mirror, or a second weak-model rewrite loud.
    _shortcut_tokens = ("`cc`", "`sss`", "`ss`",
                        "`\u0441\u0441`", "`\u0441\u0441\u0441`",
                        "`\u0430\u0430`", "`\u0435\u0435`",
                        "`\u0435\u0435\u0435`", "`\u0440\u0440`")

    # Resolved from `_tools_parent`, never from `rfc_path`: that name is
    # bound hundreds of lines BELOW this one, so reading it here raised
    # NameError and took the whole callout section down with it -- silently,
    # which is worse than the false PASS it replaced. Second time in one
    # session, and CONFORMANCE 118 is the invariant for exactly this.
    _sc_home = _tools_parent / "saipen"
    if not (_sc_home / "CORE.md").is_file():
        _sc_home = _tools_parent
    _shortcut_key_count = len(re.findall(
        r"^\| `[a-z]{2,3}` \| ",
        _read_rfc(_sc_home / "RFC.md"), re.MULTILINE))

    # T-537 gave `cc` a different destination, and this check could not see
    # it: every rung below counts keys, tokens, order and the link, so a
    # callout still telling the reader `cc` is the Goal Mode key passes while
    # describing a command the table no longer assigns to that row. The
    # rollout was therefore left half-finished in Core's OWN languages -- the
    # RU locale source, the EN guide and the JA guide kept the superseded
    # sentence while their siblings had moved -- and nothing failed.
    #
    # Scoped to the files Core owns. `phases/translate.md` gives the other 28
    # languages to saitranslate, so failing on them here would turn one
    # producer's backlog into a red gate on every Core commit; those stay
    # T-537's remainder.
    _core_callouts = {
        Path("README.md"), Path("README.ee.md"), Path("README.ded.md"),
        Path("README.ja.md"), Path("GUIDE.md"),
        Path("guides/GUIDE_EN.md"), Path("guides/GUIDE_EE.md"),
        Path("guides/GUIDE_DED.md"), Path("guides/GUIDE_JA.md"),
        Path("guides/GUIDE_RU.md"),
        kitchen / "en" / "README_EN.md", kitchen / "et" / "README_ET.md",
        kitchen / "ru" / "README_RU.md", kitchen / "ded" / "README_DED.md",
        kitchen / "ja" / "README_JA.md",
    }

    def _shortcut_callout(path, expected_link):
        if not path.is_file():
            fail(f"cross-doc drift [shortcut-callouts] -- missing {path}")
            return None
        _lines = path.read_text(encoding="utf-8-sig").splitlines()
        _matches = [(i, line) for i, line in enumerate(_lines)
                    if "#110-command-surface" in line and "`cc`" in line]
        if len(_matches) != 1:
            fail(f"cross-doc drift [shortcut-callouts] -- {path} has "
                 f"{len(_matches)} shortcut callouts; expected exactly one")
            return None
        _index, _line = _matches[0]
        # The count is DERIVED from the table, never a literal. It was
        # hardcoded `14`, so adding a 15th row left the check asserting a
        # number that had stopped being true and passing anyway -- the whole
        # 70-document rollout then had to be noticed by a human. A literal
        # here is a check that measures the day it was written.
        if str(_shortcut_key_count) not in _line:
            fail(f"cross-doc drift [shortcut-callouts] -- {path} does not "
                 f"name the complete {_shortcut_key_count}-key map")
        _missing = [token for token in _shortcut_tokens
                    if _line.count(token) != 1]
        if _missing:
            fail(f"cross-doc drift [shortcut-callouts] -- {path} callout "
                 "does not carry each canonical key exactly once: "
                 + ", ".join(_missing))
        if not _missing and not (_line.index("`cc`") < _line.index("`sss`")
                                 < _line.index("`ss`")):
            fail(f"cross-doc drift [shortcut-callouts] -- {path} no longer "
                 "orders continue, status, then stop like the canonical entry")
        if f"]({expected_link})" not in _line:
            fail(f"cross-doc drift [shortcut-callouts] -- {path} does not "
                 f"link to {expected_link}")
        if _index >= 40:
            fail(f"cross-doc drift [shortcut-callouts] -- {path} hides its "
                 f"shortcut entry at line {_index + 1}, outside the opening")
        if path in _core_callouts and re.search(r"goal mode", _line,
                                                re.IGNORECASE):
            fail(f"cross-doc drift [shortcut-callouts] -- {path} still "
                 "describes `cc` as the Goal Mode key, but § 1.10 routes it "
                 "to `saipen continue`; `gg` is the sole short route for a "
                 "new goal. A callout naming the wrong destination is the "
                 "same defect as a Notes column naming one")
        return _line

    _locale_sources = {}
    for _locale_dir in sorted(p for p in kitchen.iterdir() if p.is_dir()):
        _code = _locale_dir.name.upper()
        _source = _locale_dir / f"README_{_code}.md"
        _locale_sources[_code] = _shortcut_callout(
            _source, "saipen/RFC.md#110-command-surface")
    if len(_locale_sources) != 32:
        fail("cross-doc drift [shortcut-callouts] -- expected 32 locale "
             f"README sources, found {len(_locale_sources)}")

    _mirror_map = {
        Path("README.ded.md"): "DED",
        Path("README.ee.md"): "ET",
        Path("README.ja.md"): "JA",
    }
    for _mirror, _code in _mirror_map.items():
        _mirror_line = _shortcut_callout(
            _mirror, "saipen/RFC.md#110-command-surface")
        if (_mirror_line is not None and _locale_sources.get(_code) is not None
                and _mirror_line != _locale_sources[_code]):
            fail(f"cross-doc drift [shortcut-callouts] -- {_mirror} differs "
                 f"from locale source {_code}")

    _shortcut_callout(Path("README.md"),
                      "saipen/RFC.md#110-command-surface")
    _shortcut_callout(Path("GUIDE.md"),
                      "saipen/RFC.md#110-command-surface")
    _guide_paths = sorted(Path("guides").glob("GUIDE_*.md"))
    if len(_guide_paths) != 33:
        fail("cross-doc drift [shortcut-callouts] -- expected 33 locale "
             f"guides, found {len(_guide_paths)}")
    _core_guides = {"EN", "EE", "DED", "JA", "RU"}
    for _guide in _guide_paths:
        _code = _guide.stem[len("GUIDE_"):]
        _guide_line = _shortcut_callout(
            _guide, "../saipen/RFC.md#110-command-surface")
        if _code not in _core_guides:
            _source_line = _locale_sources.get(_code)
            _expected = (_source_line.replace(
                "](saipen/RFC.md#110-command-surface)",
                "](../saipen/RFC.md#110-command-surface)")
                         if _source_line is not None else None)
            if _guide_line is not None and _expected is not None \
                    and _guide_line != _expected:
                fail(f"cross-doc drift [shortcut-callouts] -- {_guide} "
                     f"differs from locale source {_code}")

    if not any("shortcut-callouts" in problem for problem in failures):
        ok("shortcut callouts aligned across 32 locale sources, 3 mirrors, "
           "33 locale guides, and both root entry docs")

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

# Role freshness, instance side (T-542): a live sub STATE predating the
# revision recording has no `role_revision` to compare -- WARN, never FAIL,
# because those instances are exactly the ones whose next adopt must re-record
# it. The FAIL half lives in the OUTBOX block above (a ready package bound to
# a superseded charter is stale).
if _subs_root.is_dir():
    _rrless, _rrmismatch = [], []
    for _d in sorted(_subs_root.iterdir()):
        if not _d.is_dir() or _d.name == "TEMPLATE":
            continue
        _st = _d / "STATE.md"
        if not _st.is_file():
            continue
        _stx = _st.read_text(encoding="utf-8-sig", errors="replace")
        if "role_revision" not in _stx:
            _rrless.append(_d.name)
            continue
        _inst_rr = re.search(r"^role_revision:\s*(\S+)", _stx, re.MULTILINE)
        _cp = _role_contract_path(_d.name)
        _charter_rr = None
        if _cp is not None:
            try:
                _charter_rr = compute_role_revision(_cp)
            except FreshnessError as exc:
                fail(f"cannot derive {_d.name} charter revision: {exc}")
        else:
            _protocol = _generic_protocol_path()
            if _protocol is not None:
                try:
                    _charter_rr = compute_generic_role_revision(_protocol)
                except FreshnessError as exc:
                    fail(f"cannot derive {_d.name} generic role revision: {exc}")
        if _inst_rr and _charter_rr is not None and _inst_rr.group(1) != _charter_rr:
            _rrmismatch.append(f"{_d.name} ({_inst_rr.group(1)} != charter {_charter_rr})")
    if _rrless:
        warn("sub-role-revision-legacy",
             "subSaipen STATE(s) predate role-revision recording: "
             + ", ".join(_rrless)
             + " -- re-record `role_revision` from the current charter at "
               "their next adopt (PROTOCOL.md § 6, T-542)")
    if _rrmismatch:
        warn("sub-role-revision-stale",
             "subSaipen STATE(s) carry an old role_revision: "
             + "; ".join(_rrmismatch)
             + " -- the instance revalidates against the current charter "
               "before reuse, and a ready OUTBOX it produced under the old "
               "revision is stale (PROTOCOL.md § 6, T-542)")

# ------------------------------------------- append targets end on a boundary

# Every file the protocol APPENDS to has to end on a line boundary, because an
# append to a file that stops mid-line does not add a line -- it extends the
# last one. `.saipen/LOG.md` reached this state (a literal `\n` written where a
# newline belonged) and every LOG mutation `tools/audit_checks.py` appends
# landed inside the final entry instead of after it: two of its red controls
# stopped being evidence while the suite still printed PASS. A BOARD.md ending
# on `## BLOCKED` costs the heading AND the next ticket in one write, and no
# structural check can see it, since the bytes never become a second line.
# Checked by reading the last byte -- the one thing no other check here does.
_append_targets = [Path(".saipen/STATE.md"), Path(".saipen/BOARD.md"),
                   Path(".saipen/LOG.md")]
_append_targets += sorted(Path(".saipen/logs").glob("LOG-*.md"))
_subs_root = Path(".saipen/extensions/subs")
if _subs_root.is_dir():
    _append_targets.append(_subs_root / "MANIFEST.md")
    for _sub in sorted(p for p in _subs_root.iterdir() if p.is_dir()):
        _append_targets += [_sub / "STATE.md", _sub / "BOARD.md", _sub / "LOG.md"]

_unterminated = []
for _t in _append_targets:
    if not _t.is_file():
        continue
    _raw = _t.read_bytes()
    if _raw and not _raw.endswith(b"\n"):
        _unterminated.append(f"{_t.as_posix()} ends {_raw[-40:]!r}")
if _unterminated:
    fail(f"{len(_unterminated)} protocol append target(s) end mid-line, so the "
         f"next append extends the last line instead of adding one: "
         + "; ".join(_unterminated[:3]))
elif any(t.is_file() for t in _append_targets):
    ok(f"append targets end on a line boundary "
       f"({sum(1 for t in _append_targets if t.is_file())} checked)")

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
rfc_path = _tools_parent / "saipen" / "RFC.md"
if not rfc_path.is_file():
    rfc_path = _tools_parent / "RFC.md"
boot_path = rfc_path.parent / "BOOT.md"
conf_path = rfc_path.parent / "CONFORMANCE.md"
if not rfc_path.is_file():
    fail(f"RFC.md not found at {rfc_path} -- SAIPEN home clone incomplete")
else:
    rfc = _read_rfc(rfc_path)
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

    # 1a. `saipen hunt` is a phase-switching command § 1.10 recognises from
    #     anywhere, and HUNT was missing from § 1.6's from-any-phase set, so
    #     the DFA's only route into it was DONE -> HUNT. Invoking the command
    #     from BUILD or REVIEW produced a transition the validator rejects
    #     while the agent did exactly what § 1.10 said -- the same two-halves
    #     disagreement CONFORMANCE 61 records for SHIP, one phase over. § 2.1
    #     compounded it by phrasing the halt as a precondition on HUNT itself
    #     rather than on the autonomous transition, and hunt.md's hash skip
    #     had no carve-out, making the one command for forcing a sweep a
    #     documented no-op on any unchanged tree.
    _s21_hunt_i = rfc.find("- **HUNT**: Transition to `HUNT`")
    _s21_hunt = rfc[_s21_hunt_i:_s21_hunt_i + 1600] if _s21_hunt_i >= 0 else ""
    if not _s21_hunt:
        fail("cross-doc check 'hunt-entry' cannot find RFC § 2.1's HUNT bullet "
             "-- update tools/validate.py deliberately; a drift check that "
             "silently stops checking still prints PASS")
        drift_ok = False
    elif "governs the AUTONOMOUS transition only" not in _s21_hunt:
        fail("cross-doc drift [hunt-entry] -- RFC § 2.1's HUNT bullet must say "
             "the halt requirement governs the autonomous transition only, and "
             "that `saipen hunt` enters from any phase regardless of board "
             "state. Read as a precondition on the command, it makes the one "
             "command for forcing a sweep refuse on nearly every board")
        drift_ok = False
    _hunt_doc = rfc_path.parent / "phases" / "hunt.md"
    if _hunt_doc.is_file():
        _hunt_t = _hunt_doc.read_text(encoding="utf-8-sig")
        if "does not apply -- run the full sweep" not in _hunt_t:
            fail("cross-doc drift [hunt-entry] -- phases/hunt.md must exempt an "
                 "explicit `saipen hunt` / `hh` from the hash skip. § 1.10 says "
                 "that command forces the sweep and skips nothing; honouring "
                 "the skip there makes it a no-op on any unchanged tree")
            drift_ok = False

    # `phases/ship.md` carried the first-publish gate at step 7, AFTER the
    # branch push at step 5 and the tag push at step 6 -- its own WAIT text
    # reading "before I push" about a push two steps behind it. On the one
    # run the gate exists for, the irreversible act preceded its
    # authorization; with no `origin` at all the push simply failed first and
    # dropped into generic push recovery, which never asks. RFC § 2.4's SHIP
    # exception and § 1.1's destructive gate both make the confirmation a
    # MUST, and ship.md is the doc that emits it.
    _ship_doc = rfc_path.parent / "phases" / "ship.md"
    if _ship_doc.is_file():
        _ship_t = _ship_doc.read_text(encoding="utf-8-sig")
        _gate = _ship_t.find("WAIT: first-publish")
        # Anchor updated with T-569's staging rewrite, which turned "then push
        # the branch" into a numbered step. Updated deliberately, exactly as
        # the failure message below demands, rather than left to go quiet.
        _push = _ship_t.find("**Push the branch.**")
        if _gate < 0 or _push < 0:
            fail("cross-doc drift [first-publish-order] -- phases/ship.md no "
                 "longer names both the first-publish gate and the branch "
                 "push; update tools/validate.py deliberately rather than "
                 "letting the ordering check quietly stop checking")
            drift_ok = False
        elif _gate > _push:
            fail("cross-doc drift [first-publish-order] -- phases/ship.md "
                 "places the first-publish confirmation AFTER the branch "
                 "push. A gate downstream of the act it authorizes is not a "
                 "gate: on a true first publish the one-way door opens before "
                 "the user is asked (RFC § 2.4 SHIP exception, § 1.1)")
            drift_ok = False
        if "Classify the remote BEFORE any external write" not in _ship_t:
            fail("cross-doc drift [first-publish-order] -- phases/ship.md must "
                 "classify the remote before any external write, so the "
                 "first-publish gate is decided while everything is still "
                 "local")
            drift_ok = False

        # T-569: the binding ship gate runs AFTER staging, and the staging is
        # explicit-path. Pinned BY POSITION rather than by presence, because
        # every piece of this was already in the document when the paradox was
        # live -- the gate existed, the commit existed, and the order between
        # them was the defect: a required runtime file added by the ticket
        # being shipped is untracked until it is staged, so a gate run before
        # staging could not be satisfied by any sequence the protocol
        # described. Three releases carried a MANIFEST entry that went green
        # locally and red in CI for exactly that reason.
        _stage_at = _ship_t.find("Stage ONLY the reviewed files this ship owns")
        _gate_at = _ship_t.find("Run `tools/validate.py --gate ship` NOW")
        _commit_at = _ship_t.find("Commit exactly the staged scope")
        if _stage_at < 0 or _gate_at < 0 or _commit_at < 0:
            fail("cross-doc drift [ship-stage-before-gate] -- phases/ship.md no "
                 "longer names the explicit staging step, the post-stage ship "
                 "gate, or the exact-scope commit. Update tools/validate.py "
                 "deliberately rather than letting the ordering check quietly "
                 "stop checking")
            drift_ok = False
        elif not _stage_at < _gate_at < _commit_at:
            fail("cross-doc drift [ship-stage-before-gate] -- phases/ship.md "
                 "must stage the reviewed files, THEN run the ship gate, THEN "
                 "commit. Gate before staging is the SHIP/MANIFEST paradox: a "
                 "required runtime file this ticket adds is untracked until it "
                 "is staged, so the gate can never be satisfied and the agent "
                 "has to invent an undocumented staging step (T-569)")
            drift_ok = False
        if ("**`git add .` and `git add -A` are\n      forbidden here**"
                not in _ship_t):
            fail("cross-doc drift [ship-stage-before-gate] -- phases/ship.md "
                 "must forbid blind `git add .`/`git add -A` in the staging "
                 "step. Staging by explicit path is what makes step 5's "
                 "'staged set equals reviewed scope' provable; a blind add "
                 "stages whatever else the tree is carrying and the proof "
                 "becomes a description of the accident (T-569)")
            drift_ok = False

        # T-467: the tag push is the SECOND command, and it must not run
        # until the branch push has landed. Step 7 used to push the tag
        # regardless of step 6's outcome, and a rejected branch push followed
        # by a successful tag push published a tag on a commit that is on no
        # remote branch -- twice here (E-1787, E-1882). Step 10's recovery
        # text claimed such a tag "by definition was never successfully
        # pushed", which holds only while the tag rides the branch push.
        _tag_landed = _ship_t.find("step 6b's branch push has LANDED")
        _tag_cmd = _ship_t.find("git push origin refs/tags/vVERSION")
        if _tag_landed < 0 or _tag_cmd < 0:
            fail("cross-doc drift [tag-after-branch] -- phases/ship.md no "
                 "longer names both the branch-landed gate and the tag push; "
                 "update tools/validate.py deliberately rather than letting "
                 "the ordering check quietly stop checking")
            drift_ok = False
        elif _tag_landed > _tag_cmd:
            fail("cross-doc drift [tag-after-branch] -- phases/ship.md "
                 "pushes the release tag before it gates on the branch push "
                 "having LANDED. A rejected branch push followed by a "
                 "successful tag push publishes a tag on a commit that is on "
                 "no remote branch -- E-1787, E-1882 (T-467)")
            drift_ok = False

        # T-466: the ticket that passes REVIEW is still in `## DOING` -- the
        # push has not happened. `PHASE SHIP T-###` is the legal next_action
        # this state emits, and the pick check accepts it precisely because a
        # claimed `## DOING` ticket IS the pick; it rejects the same string
        # the moment the ticket reaches `## DONE` ("finished and blocked
        # tickets are not executable"). Closing the ticket at REVIEW was the
        # repository habit that made § 1.2's own `PHASE` form unusable for
        # the one phase it names a ticket for (E-1879). review.md states the
        # rule once; ship.md cites it. Either anchor drifting away silently
        # reopens the defect, so this pin FAILs rather than skips.
        _review_doc = rfc_path.parent / "phases" / "review.md"
        _review_t = (_review_doc.read_text(encoding="utf-8-sig")
                     if _review_doc.is_file() else "")
        _rule_once = _review_t.find(
            "stays in `## DOING` through SHIP")
        _ship_cite = _ship_t.find(
            "The shipped ticket was still in `## DOING` when this phase "
            "began")
        if _rule_once < 0 or _ship_cite < 0:
            fail("cross-doc drift [ticket-stays-doing] -- phases/review.md "
                 "no longer states that the passed ticket stays in `## DOING` "
                 "through SHIP, or phases/ship.md no longer cites it. A ticket "
                 "closed at REVIEW makes `PHASE SHIP T-###` name a `## DONE` "
                 "ticket and fail the pick check twice over (E-1879, T-466); "
                 "update tools/validate.py deliberately rather than letting "
                 "the check quietly stop checking")
            drift_ok = False

    # REVIEW read the diff and took VERIFY's result as given, so a green claim
    # reached SHIP on the strength of the phase that produced it. Rosary's
    # generator/evaluator split, minus the second process: the evaluator
    # repeats the mandatory check rather than trusting the report.
    _review_doc = rfc_path.parent / "phases" / "review.md"
    if _review_doc.is_file():
        _review_t = _review_doc.read_text(encoding="utf-8-sig")
        if "do not read VERIFY's claim of" not in _review_t:
            fail("cross-doc drift [review-reruns-verify] -- phases/review.md "
                 "must re-run the ticket's own `verify:` rather than reading "
                 "VERIFY's claim of it. A phase reporting on its own work is "
                 "the one report nothing downstream can contradict")
            drift_ok = False

    # Rosary A4/A5/A1, each one sentence in the doc that emits it.
    _markers = [
        (rfc_path.parent / "phases" / "verify.md",
         "That order is cheapest-first",
         "phases/verify.md must say the ladder runs cheapest-first -- a parse "
         "error found by the full suite costs the whole suite to learn what "
         "the first rung says in a second"),
        (rfc_path.parent / "phases" / "verify.md",
         "ends the PASS claim for this pass",
         "phases/verify.md must say the first failed MANDATORY gate ends the "
         "PASS claim, so a green from a higher rung cannot read as repairing "
         "a red one below it"),
        (rfc_path.parent / "phases" / "verify.md",
         "Read the project's canonical commands from `KNOWLEDGE/`",
         "phases/verify.md must read the project's commands from KNOWLEDGE/ "
         "rather than re-deriving them, or executor and reviewer can each "
         "verify a different thing and both report green"),
        (rfc_path.parent / "phases" / "scout.md",
         "cited afterwards rather than",
         "phases/scout.md must write the harness and build commands into "
         "KNOWLEDGE/ once and cite them afterwards (RFC § 1.2 makes them "
         "durable truth)"),
        (rfc_path.parent / "BOOT.md",
         "Immediate means without asking, never without looking",
         "BOOT.md must say `next_action` is the previous session's "
         "pre-computed pick and is confirmed against BOARD.md where the "
         "validator cannot re-derive it -- the portable floor does not, since "
         "a grep cannot walk a needs: graph"),
    ]
    for _doc, _marker, _why in _markers:
        if _doc.is_file() and _marker not in _doc.read_text(encoding="utf-8-sig"):
            fail(f"cross-doc drift [borrowed-invariants] -- {_why}")
            drift_ok = False

    # 1a2. § 1.11's priority list had no entry for the user naming a command,
    #      so BOOT's "execute `next_action` immediately" and § 1.10's "a
    #      shortcut is a command, never a greeting" were two live MUSTs with
    #      no precedence between them -- and at a cold start BOOT is the file
    #      an agent reads first. It cost this repository the same `qq` twice:
    #      E-1913 lost it to a stale `PHASE SCOUT T-455`, and a second agent's
    #      session lost it to the same pick again. Both halves are pinned --
    #      the rule in § 1.11, the conditional in BOOT step 7 -- because
    #      either one alone restores the tie.
    _s111_i = rfc.find("### 1.11")
    _s111 = (rfc[_s111_i:rfc.find("## Part 2", _s111_i)]
             if _s111_i >= 0 else "")
    if not _s111:
        fail("cross-doc check 'command-outranks-pick' cannot find RFC § 1.11 "
             "-- update tools/validate.py deliberately; a drift check that "
             "silently stops checking still prints PASS")
        drift_ok = False
    else:
        if ("**OBEY**" not in _s111
                or "It supersedes `next_action`" not in _s111):
            fail("cross-doc drift [command-outranks-pick] -- RFC § 1.11's "
                 "priority list must carry the OBEY step stating that a "
                 "command the user just named supersedes `next_action`. "
                 "Without it the list has no entry for the commonest event in "
                 "a live project, and the previous session's pre-computed "
                 "pick silently beats the key the user actually pressed")
            drift_ok = False
        _boot_prio = rfc_path.parent / "BOOT.md"
        _boot_prio_t = (_boot_prio.read_text(encoding="utf-8-sig")
                        if _boot_prio.is_file() else "")
        if "the user's own message outranks the file" not in _boot_prio_t:
            fail("cross-doc drift [command-outranks-pick] -- BOOT.md step 7 "
                 "must say the user's own message outranks `next_action` and "
                 "defer to § 1.11's OBEY priority. Read as unconditional it "
                 "is the half a cold agent reaches first, which is exactly "
                 "how the command the user typed gets dropped")
            drift_ok = False

    # 1b14. The wiki Scenarios page mirrors CONFORMANCE by ID, and row-count
    #       equality is not the test. W-027 reported 180/180 with zero drift
    #       while rows 117-168 carried titles belonging to other IDs -- the
    #       page had been built by POSITION, so equal counts read as equal
    #       meaning. Counting proves nothing about which invariant a row
    #       names. The page carries the digest of the canonical id-to-title
    #       map it was built from, over the ID RANGE it claims to cover, so
    #       adding new rows below that range never invalidates it while
    #       editing a mirrored row's title always does. Same shape as the
    #       translation digest, and deliberately not a semantic comparison:
    #       nothing here can judge whether a paraphrase still means the same
    #       thing, and a checker pretending to would be a fresh false PASS.
    #
    #       WARN and SKIP-when-absent, both on purpose. The wiki kitchen is
    #       gitignored, so a fresh clone does not have the page at all and a
    #       FAIL would fire on a healthy checkout; and the mirror going stale
    #       is saiwiki's work to clear, not something a Core release should
    #       be gated on.
    _wiki_p = (_tools_parent / ".saipen" / "extensions" / "subs" / "saiwiki"
               / "kitchen" / "wiki" / "Scenarios.md")
    # Resolved from `_tools_parent`, not from `conformance_path`: that
    # name is bound further down this file, so reading it here crashed
    # the validator with a NameError in every scenario run -- the exact
    # class CONFORMANCE 118 names, "no tool reads a module-level name
    # before the line that assigns it", which did not catch it because
    # the live tree happened to reach the assignment first.
    _conf_p = _tools_parent / "saipen" / "CONFORMANCE.md"
    if _wiki_p.is_file() and _conf_p.is_file():
        _wt = _wiki_p.read_text(encoding="utf-8-sig")
        _ct = _conf_p.read_text(encoding="utf-8-sig")
        _wids = sorted(int(_m.group(1))
                       for _m in re.finditer(r"^\|\s*(\d+)\s*\|", _wt, re.MULTILINE))
        _cids = sorted(int(_m.group(1))
                       for _m in re.finditer(r"^\|\s*(\d+)\s*\|", _ct, re.MULTILINE))
        if _wids and _cids:
            _top = max(_wids)
            _cmap = {}
            for _m in re.finditer(r"^\|\s*(\d+)\s*\|\s*(.*?)\s*\|", _ct, re.MULTILINE):
                _n = int(_m.group(1))
                if _n <= _top:
                    _cmap[_n] = _m.group(2)
            _payload = chr(10).join("%d|%s" % (_k, _cmap[_k])
                                    for _k in sorted(_cmap))
            _want = hashlib.sha256(_payload.encode("utf-8")).hexdigest()[:16]
            _mk = re.search(
                r"<!-- mirrors: CONFORMANCE\.md rows 1-(\d+) sha256:([0-9a-f]+) -->",
                _wt)
            if _mk is None:
                warn("wiki-mirror-unstamped",
                     "the saiwiki Scenarios page carries no `mirrors:` marker, "
                     "so nothing distinguishes a page rebuilt from the "
                     "canonical rows from one whose row COUNT merely matches "
                     "-- which is how rows 117-168 once named other IDs while "
                     "the report read 180/180 with zero drift")
            elif _mk.group(2) != _want or int(_mk.group(1)) != _top:
                warn("wiki-mirror-stale",
                     f"the saiwiki Scenarios page mirrors CONFORMANCE rows "
                     f"1-{_mk.group(1)} at digest {_mk.group(2)}, and those "
                     f"canonical rows now digest to {_want} -- a mirrored "
                     f"row's title moved and the page did not follow")
            _gap = [_n for _n in _cids if _n > _top]
            if _gap:
                warn("wiki-mirror-behind",
                     f"CONFORMANCE carries {len(_gap)} row(s) above the "
                     f"page's highest mirrored ID {_top} (up to {max(_gap)}), "
                     f"so the wiki is behind by that many invariants. The "
                     f"digest above covers only what the page claims to "
                     f"mirror, which is why this is counted separately "
                     f"instead of hidden inside it")

    # 1b15. A future-stamped LOG line has a repair. The rule FAILed one and
    #       named no way out, so the only precedent was to wait for real time
    #       to pass -- affordable at E-1912's eleven minutes, not at E-2053's
    #       142, where it holds every gate red for two and a half hours while
    #       the line asserts work happened at a time it had not. Two honest
    #       agents diverge there and the waiting one is defending a false
    #       record.
    _core_doc = rfc_path.parent / "CORE.md"
    _core_t = (_core_doc.read_text(encoding="utf-8-sig")
               if _core_doc.is_file() else "")
    if _core_t and "An ahead-stamp is repaired, not waited out" not in _core_t:
        fail("cross-doc drift [ahead-stamp-repair] -- CORE.md must say a "
             "future-stamped LOG line is restamped to a defensible bound with "
             "a DEC naming the original, the replacement, and that the minute "
             "is inherited rather than measured. Without it the only sanctioned "
             "response is waiting, which keeps a false record and reds every "
             "gate until the clock catches up")
        drift_ok = False

    # 1b16. The circuit's hand-off contract. Every stage of `sc` already has
    #       a verdict vocabulary of its own; what was missing is the rule that
    #       a verdict is what travels. A user transcript shows the cost: an
    #       agent archived a file its own entry point imports at runtime, then
    #       reported "Production Ready" and "проверил: всё работает", and the
    #       next command anyone ran raised FileNotFoundError. The import rung
    #       of verify.md's ladder -- one command, second cheapest -- was never
    #       run, and a claim travelled where evidence belonged.
    _crew_doc = (_tools_parent / "extensions" / "subs" / "crew.md")
    _crew_t = (_crew_doc.read_text(encoding="utf-8-sig")
               if _crew_doc.is_file() else "")
    if _crew_t and ("A stage passes the next stage a reproduction or a "
                    "verdict. Never a claim." not in _crew_t):
        fail("cross-doc drift [circuit-handoff] -- extensions/subs/crew.md "
             "must state that a circuit stage hands the next stage a "
             "reproduction or a verdict and never a claim. Without it `sc` is "
             "a sequence of commands with the operator's memory between them, "
             "which is the arrangement that let \"Production Ready\" travel "
             "one stage ahead of an unrun import check")
        drift_ok = False

    # 1b17. Every stage of the `sc` circuit names a command that exists.
    #       The circuit table is prose, so a stage could name a verb nobody
    #       defined and nothing would notice -- which is precisely the
    #       fabricated-command failure a live transcript already produced,
    #       where an agent answered `hh` with a ten-row table naming six
    #       commands that appear nowhere in the surface. A circuit whose
    #       stages are unchecked is that table with more ceremony.
    if _crew_t:
        _stage_cmds = set(re.findall(r"`saipen ([a-z]+)[^`]*`",
                                     _crew_t.split("## `sc`")[-1]))
        _unknown = sorted(_stage_cmds - set(SAIPEN_COMMANDS))
        if _unknown:
            fail("cross-doc drift [circuit-stages] -- the `sc` circuit in "
                 f"extensions/subs/crew.md names command(s) {_unknown} that "
                 "RFC 1.10 does not define. A stage pointing at a verb nobody "
                 "wrote is the fabricated-command failure with a table around "
                 "it: the operator follows the circuit and hits a word the "
                 "protocol has never heard of")
            drift_ok = False

    # 1b18. A move is destructive to whatever loads the moved file, and the
    #       deletion gate cannot see it: the file is recoverable by
    #       construction -- it is right there in the new place -- while the
    #       program is broken anyway. Reproduced from a user session where
    #       "put the rest in the archive" moved a GUI module the entry point
    #       loads at runtime by absolute path, and the next command raised
    #       FileNotFoundError. The check is a grep before the move.
    # 1b19b. HUNT/CLEAN ownership split (T-540): CLEAN owns every proven-safe
    #        hygiene mutation, HUNT only detects and tickets. The pre-move
    #        reference sweep therefore lives in clean.md (the phase that moves
    #        and prunes), and hunt.md must state it mutates nothing -- a hunt.md
    #        that still carries deletion authority, or a clean.md that lost the
    #        sweep, is the duplication or the hole this split exists to close.
    if _hunt_t and "deletes, moves and renames nothing" not in _hunt_t:
        fail("cross-doc drift [hunt-no-mutation] -- phases/hunt.md must state "
             "it deletes, moves and renames nothing (detect/classify/ticket/"
             "report only), so the HUNT/CLEAN scopes cannot overlap (T-540): "
             "the deletion gate, the mass-deletion cap and the pre-move "
             "reference sweep all live in phases/clean.md")
        drift_ok = False
    _clean_doc = rfc_path.parent / "phases" / "clean.md"
    if (_clean_doc.is_file()
            and "needs a reference sweep first"
            not in _clean_doc.read_text(encoding="utf-8-sig")):
        fail("cross-doc drift [move-reference-sweep] -- phases/clean.md must "
             "carry the pre-move reference sweep (cite it before it prunes or "
             "relocates anything). CLEAN is the phase that moves files for "
             "tidiness, which is exactly the framing that makes the breakage "
             "invisible; HUNT no longer moves anything (T-540)")
        drift_ok = False

    # 1b20. CHANGELOG.md is ordered, unique, headed by the current version,
    #       and bounded. All four were prose and none was checked, so the
    #       file drifted into a state a reader could not use: 153 entries
    #       against its own stated "most recent ~10", one version present
    #       TWICE in two different heading formats, an entry for 7.192.0
    #       sitting above 7.196.0, the archive pointer buried in the middle
    #       of the newest entry, and 7.188.0's heading renumbered to 7.189.0
    #       by a bulk string replace -- so a released version had no entry
    #       while its tag existed. The top of the file is where anyone looks
    #       to answer "what shipped last", and it answered wrong.
    _cl = _tools_parent / "CHANGELOG.md"
    _ver_f = _tools_parent / "VERSION"
    if _cl.is_file():
        _cl_t = _cl.read_text(encoding="utf-8-sig")
        _archive_pointer = (
            "> Older entries live in [CHANGELOG_ARCHIVE.md]"
            "(CHANGELOG_ARCHIVE.md) -- this file keeps the most recent ~10.")
        if _archive_pointer not in _cl_t:
            fail("cross-doc drift [changelog-archive-pointer] -- CHANGELOG.md "
                 "must carry exactly the pointer line: "
                 f"{_archive_pointer!r}. The ~10 contract is the reason the "
                 "`changelog-unarchived` warning fires at an overflow; a "
                 "header edited to a looser number would silently make that "
                 "warning a lie")
            drift_ok = False
        _heads = re.findall(r"(?m)^## \[?(\d+)\.(\d+)\.(\d+)\]?", _cl_t)
        _tup = [tuple(int(x) for x in h) for h in _heads]
        if _tup != sorted(_tup, reverse=True):
            fail("cross-doc drift [changelog-order] -- CHANGELOG.md's version "
                 "headings are not in descending order. `phases/ship.md` says "
                 "newest-top and nothing checked it, so an older entry "
                 "prepended by one session pushed newer releases below it and "
                 "the head of the file stopped naming the last release")
            drift_ok = False
        if len(_tup) != len(set(_tup)):
            _dupes = sorted({t for t in _tup if _tup.count(t) > 1})
            fail(f"cross-doc drift [changelog-order] -- CHANGELOG.md carries "
                 f"more than one entry for {_dupes}. Two entries for one "
                 f"version is two accounts of what shipped, and a reader has "
                 f"no way to tell which is the release")
            drift_ok = False
        if _tup and _ver_f.is_file():
            _cur = tuple(int(x) for x in
                         _ver_f.read_text(encoding="utf-8").strip().split("."))
            if _tup[0] != _cur:
                fail(f"cross-doc drift [changelog-order] -- CHANGELOG.md's "
                     f"head entry is {_tup[0]} but VERSION is {_cur}. "
                     f"`phases/ship.md` step 3 requires them to agree before "
                     f"the tag is created, and the head entry is what a "
                     f"reader takes for the current release")
                drift_ok = False
        if len(_tup) > 12:
            warn("changelog-unarchived",
                 f"CHANGELOG.md carries {len(_tup)} version entries while it "
                 f"states it keeps the most recent ~10 -- the overflow belongs "
                 f"in CHANGELOG_ARCHIVE.md, moved verbatim the way LOG "
                 f"segments are sealed, so the top of the file stays the part "
                 f"anyone actually reads")

    # 1c. Shortcuts are resolved by reading § 1.10, never from memory.
    if _boot_prio.is_file():
        if "Memory is never a source for it" not in _boot_prio_t:
            fail("cross-doc drift [shortcut-memory-ban] -- BOOT.md step 7 "
                 "must order § 1.10's table read before acting on a shortcut "
                 "and explicitly state that memory is never a source for it. "
                 "An agent that believes it knows what a key means answers "
                 "from recall rather than reading the file")
            drift_ok = False
        if "a second copy drifts" not in _boot_prio_t:
            fail("cross-doc drift [shortcut-memory-ban] -- BOOT.md step 7 "
                 "must explicitly forbid duplicating § 1.10's table into BOOT. "
                 "A second copy drifts and defeats the read-the-source rule")
            drift_ok = False
        
    _s110_i = rfc.find("### 1.10")
    _s110 = (rfc[_s110_i:rfc.find("### 1.11", _s110_i)]
             if _s110_i >= 0 else "")
    if _s110:
        if "answering a row from recall is the same failure as inventing a command" not in _s110:
            fail("cross-doc drift [shortcut-memory-ban] -- RFC § 1.10 must state "
                 "that answering a row from recall is the same failure as "
                 "inventing a command, not a lesser one")
            drift_ok = False

    # 1b. CLEAN's board scrub has to keep the dependency graph intact. § 1.2
    #     answers a `needs:` pointing at a ticket that exists nowhere on the
    #     board with `## BLOCKED`, so a scrub with no inbound-reference guard
    #     lets the phase that keeps the board honest block a workable ticket,
    #     and the block reads as a dependency failure rather than as damage
    #     the scrub just did. Reproduced on this repository at E-1811.
    _clean_doc = rfc_path.parent / "phases" / "clean.md"
    if _clean_doc.is_file():
        _clean_t = _clean_doc.read_text(encoding="utf-8-sig")
        if "still names in `needs:` MUST NOT be pruned" not in _clean_t:
            fail("cross-doc drift [clean-scrub-guard] -- phases/clean.md's "
                 "board scrub must state that a `## DONE` ticket some live "
                 "ticket still names in `needs:` is never pruned. Without it "
                 "a conformant CLEAN manufactures the dangling reference "
                 "RFC § 1.2 answers with `## BLOCKED`")
            drift_ok = False

    # 1b2. The bootstrap identity. `phases/init.md` and the shipped template
    #      both ordered `agent: none`, which § 1.4 cannot compare against
    #      anything -- and unlike `<name>` it reads as a deliberate answer, so
    #      every project ever bootstrapped carried it and nothing said a word.
    #      Two halves: the phase doc must send INIT to its own seat name, and
    #      the template must ship a value a live state would be FAILed for, so
    #      the field cannot survive as-copied into the first checkpoint.
    _init_doc = rfc_path.parent / "phases" / "init.md"
    _init_t = (_init_doc.read_text(encoding="utf-8-sig")
               if _init_doc.is_file() else "")
    if _init_t and ("**never `none`**" not in _init_t
                    or "**Where the value comes from is not a choice**"
                    not in _init_t):
        fail("cross-doc drift [bootstrap-identity] -- phases/init.md must "
             "refuse `agent: none` at INIT and must keep saying, in the same "
             "breath, that refusing it does NOT define where the first seat "
             "name comes from. § 1.4 decides whether another agent is live by "
             "comparing that field against itself, so an undefined identity "
             "is meaningless in both directions -- and the value is DERIVED "
             "from the agent home the protocol was loaded from, never "
             "chosen, because 'write your own name' is the free choice that "
             "produced six names for three actors here")
        drift_ok = False
    _tmpl_state = _tools_parent / "extensions" / "templates" / "STATE.md"
    if _tmpl_state.is_file():
        _tm = re.search(r"^agent:\s*(.*)$",
                        _tmpl_state.read_text(encoding="utf-8-sig"),
                        re.MULTILINE)
        if (_tm is None
                or _tm.group(1).strip().lower() not in AGENT_PLACEHOLDERS):
            fail("cross-doc drift [bootstrap-identity] -- "
                 "extensions/templates/STATE.md must ship `agent:` as a value "
                 f"tools/validate.py rejects ({AGENT_PLACEHOLDERS[1]!r} is the "
                 "shipped one), so a copied template cannot reach a first "
                 "checkpoint with the field unfilled. It shipped `none`, which "
                 "passed every check while naming no seat at all")
            drift_ok = False

    # 1b3. CLEAN's deletion floors (moved from HUNT by T-540, which split the
    #      ownership: CLEAN mutates, HUNT only detects and tickets). Free
    #      deletion "capped at 5" read a quantity limit as a grant of
    #      authority: § 1.1 allows an unconfirmed destructive op only when the
    #      active ticket pre-authorizes it AND it is reversible. And the
    #      clean-result cache keyed on `HEAD` alone reused a verdict from a
    #      tree that no longer exists -- the same document rejects mtimes as
    #      insufficient three paragraphs from where its own key ignored every
    #      uncommitted byte.
    _hunt_doc = rfc_path.parent / "phases" / "hunt.md"
    _hunt_t = (_hunt_doc.read_text(encoding="utf-8-sig")
               if _hunt_doc.is_file() else "")
    _clean_doc = rfc_path.parent / "phases" / "clean.md"
    _clean_t = (_clean_doc.read_text(encoding="utf-8-sig")
                if _clean_doc.is_file() else "")
    if _clean_t:
        if ("deleted on proof of recovery" not in _clean_t
                or "mass-deletion gate, not a grant of authority" not in _clean_t):
            fail("cross-doc drift [clean-delete-proof] -- phases/clean.md must "
                 "carry the deletion gate that HUNT previously held: delete "
                 "only what it can prove recoverable (tracked at HEAD, or "
                 "regenerable by a named command) and say the 5-file cap is a "
                 "mass-deletion gate rather than authority to delete five "
                 "files. CLEAN is the only phase that mutates (T-540), so the "
                 "gate lives where the mutations do")
            drift_ok = False
    if _hunt_t:
        if "`git status --porcelain` prints nothing" not in _hunt_t:
            fail("cross-doc drift [hunt-clean-key] -- phases/hunt.md must "
                 "require a clean worktree before reusing a `hunt -> clean` "
                 "result. `HEAD` names a commit, not a tree, so the hash "
                 "alone lets a dirty tree inherit a verdict measured on a "
                 "different one -- and work commits at SHIP, not per "
                 "checkpoint, so that is the ordinary case")
            drift_ok = False

    # 1b4. The prepare record's shape. The duty to READ it (`saipen status`,
    #      dedup, attribution) existed before anything gave it a form, which
    #      is the `RUN: validate.py -> PASS|FAIL` argument one phase over.
    _prep_doc = rfc_path.parent / "phases" / "prepare.md"
    _prep_t = (_prep_doc.read_text(encoding="utf-8-sig")
               if _prep_doc.is_file() else "")
    if _prep_t and ("RUN: prepare <producer> -> done" not in _prep_t
                    or "the word `unqualified` is the" not in _prep_t):
        fail("cross-doc drift [prepare-record] -- phases/prepare.md step 6 "
             "must fix the completion and failure records as "
             "`RUN: prepare <producer> -> done|FAILED`, with `unqualified` "
             "named as the producer word when none was requested. "
             "Unqualified, one shape covers saitranslate, saiwiki and a "
             "main-project package alike, and no reader can tell which "
             "handoff became ready")
        drift_ok = False

    # 1b5. A multi-command message loses nothing. OBEY shipped saying such
    #      commands run in the order written and said nothing about a command
    #      whose preconditions are not met -- so the honest-looking outcome
    #      was to answer it in chat and forget it, which is the same loss the
    #      step exists to stop, one command later. And the pair the shortcut
    #      table most invites was dead by construction: bare `dd` ends
    #      Proposal Mode at `goal_mode: false`, where a bare goal key is not
    #      a command at all, so `dd cc` could never complete.
    _s111b = rfc[_s111_i:rfc.find("## Part 2", _s111_i)] if _s111_i >= 0 else ""
    if _s111b and "cannot execute now is written down, never dropped" not in _s111b:
        fail("cross-doc drift [command-not-dropped] -- RFC 1.11's OBEY step "
             "must say a command in a multi-command message that cannot "
             "execute now is recorded rather than dropped, and name where: "
             "`next_action` when it will be legal at the next continue, the "
             "top of `## TODO` when it will not. Ordering alone leaves the "
             "second command answerable in chat and forgotten")
        drift_ok = False
    if "One carve-out, and it is a pair rather than a loosening" not in rfc:
        fail("cross-doc drift [plan-goal-pair] -- RFC 1.10 must carve out the "
             "plan-then-bare-goal pair in the same message, which starts the "
             "plan just written. Without it the shortcut table invites "
             "`dd cc`, a combination that cannot complete: `dd` ends at "
             "`goal_mode: false` and the next key is not a command there. "
             "The carve-out is a PAIR, not a loosening of the bare form -- "
             "E-1468 was a lone key mid-run, which is unchanged")
        drift_ok = False

    # 1b6. MARKHUNT's pass accounting. The closure rule reads durable
    #      history; the record it reads had no ticket list, so triage erased
    #      the evidence it depends on. Pass identity is the completion line's
    #      own E-### -- no new ID scheme was needed for it.
    _mh_doc = rfc_path.parent / "phases" / "markhunt.md"
    _mh_t = (_mh_doc.read_text(encoding="utf-8-sig")
             if _mh_doc.is_file() else "")
    if _mh_t and ("`tickets=` is the pass's own" not in _mh_t
                  or "The pass identity is that line's own" not in _mh_t):
        fail("cross-doc drift [markhunt-pass-id] -- phases/markhunt.md must "
             "require the completion line to list the tickets the pass wrote "
             "and must name the line's own E-### as the pass identity. "
             "BOARD.md is not append-only: triage moves those tickets and "
             "dismissal removes them, so a closure rule that sums them off "
             "the board is unexecutable the moment anyone acts on the pass")
        drift_ok = False

    # 1b7. MARKHUNT's no-git closure. Two faults in one clause: it treated
    #      `mode: no-publish` as "git unavailable", which mislabels a host
    #      whose HEAD reads perfectly and switches the tree-movement check
    #      off for no reason; and on a genuinely git-less host it reported
    #      "satisfied automatically", which is a check claiming success for
    #      the one case where it measured nothing -- and an exhaustive pass
    #      spanning sessions is where movement is MOST likely.
    if _mh_t and ("means git cannot be READ, and nothing else" not in _mh_t
                  or "tree_movement=unverified" not in _mh_t):
        fail("cross-doc drift [markhunt-no-git] -- phases/markhunt.md must "
             "say `no-git` means git cannot be READ (so `mode: no-publish`, "
             "which blocks only publishing, still uses the real hash) and "
             "must declare a genuinely git-less closure unproven rather than "
             "satisfied. A check that reports success where it measured "
             "nothing is worse than one that says it could not measure")
        drift_ok = False

    # 1b8. The repository root is a closed set. Both orphans this session
    #      removed arrived the same way: `git add -A` during a checkpoint or
    #      release commit, in a change whose subject had nothing to do with
    #      them. `button33.wav`, an 8-bit mono WAV, rode in on the v7.176.0
    #      push-failure checkpoint; `.saipen/_scen_cand.md`, a 194-row
    #      snapshot of the wiki Scenarios page frozen 22 rows behind the
    #      live one, rode in on the Pick Rule check. Nothing referenced
    #      either, so nothing could ever contradict them -- an unreferenced
    #      file is invisible to every cross-doc check this validator has.
    #      `.gitignore` already carries three patterns added AFTER something
    #      leaked (`/nul`, the wiki gitlink, settings.local.json); each fixed
    #      one instance and left the class. The root is where accidents land
    #      and its contents are small, stable and deliberate, so a closed set
    #      catches the next one at the commit that adds it. Adding a real
    #      root file means adding it here, which is one line and a decision.
    ROOT_ALLOWED = {
        ".gitattributes", ".gitignore", "BROCHURE_DED.md", "CHANGELOG.md", "CHANGELOG_ARCHIVE.md",
        "CODE_OF_CONDUCT.md", "CONTRIBUTING.md", "GUIDE.md", "LICENSE",
        "README.ded.md", "README.ee.md", "README.ja.md", "README.md",
        "SECURITY.md", "SPEC.md", "THIRD_PARTY_NOTICES.md", "VERSION", "ruff.toml",
    }
    # Read the DIRECTORY, not the index. `git ls-files` was the first
    # attempt and it made the check unreachable wherever git is absent --
    # including the audit harness's own copy, where the red control then
    # could not go red and reported itself as not-evidence. The filesystem
    # is always there, and it also catches the file BEFORE the commit, which
    # is the moment that matters: `git add -A` is how both orphans arrived.
    # Git is still asked, when it answers, to drop anything gitignored, so a
    # developer's ignored scratch at the root stays silent.
    # `.git` is excluded structurally rather than allowlisted: it is not
    # project content, and in a LINKED worktree it is a FILE holding a gitdir
    # pointer rather than the directory it is in a normal clone. Reading the
    # directory therefore sees it in one layout and not the other -- the
    # install-layout blind spot T-413 names, reproduced here the moment this
    # check ran inside a scenario fixture's own worktree.
    # Gated to THIS repository's own clone. An installed agent home is a
    # FLATTENED copy -- `RFC.md` sits next to the tools rather than under
    # `saipen/` -- so its root legitimately holds a different file set, and
    # judging it against this one FAILs a healthy install. Caught by the
    # injector probes the first time this check ran, which is the same
    # install-layout blind spot T-413 names.
    _is_repo_clone = (_tools_parent / "saipen" / "RFC.md").is_file()
    _root_files = {p.name for p in _tools_parent.iterdir()
                   if _is_repo_clone and p.is_file() and p.name != ".git"}
    _ignored = subprocess.run(["git", "check-ignore", "--stdin"],
                              cwd=str(_tools_parent), input="\n".join(
                                  sorted(_root_files)),
                              capture_output=True, text=True)
    if _ignored.returncode in (0, 1):
        _root_files -= set(_ignored.stdout.split())
    _stray = sorted(_root_files - ROOT_ALLOWED)
    if _stray:
        fail("cross-doc drift [root-file-set] -- file(s) at the repository "
             f"root that the closed set does not name: {_stray}. Both orphans "
             "removed alongside this check arrived that way, on a "
             "`git add -A` in a commit about something else, and neither was "
             "referenced by any document or tool -- so no other check here "
             "could ever see them. A deliberate new root file is a one-line "
             "addition to ROOT_ALLOWED in tools/validate.py; a scratch file "
             "belongs in .gitignore, which this check honours")
        drift_ok = False

    # 1b9. SHIP's `no-publish` block fused a policy mode with an absence of
    #      git. It called the remote steps skippable because "no remote
    #      exists to publish to" and hardcoded `no git` into the mandatory
    #      LOG line, on a host that may have a repository, a remote and a
    #      readable HEAD -- a false record in an append-only file. Worse, it
    #      ordered "do step 6" and "skip the push half of step 6" together,
    #      and step 6 committed AND pushed: a mode that forbids committing
    #      told its reader to commit. Splitting the step into a local half
    #      and a git half is what makes the instruction followable at all.
    if _ship_t and ("It does NOT mean git is" not in _ship_t
                    or "(no-publish: <reason>)" not in _ship_t
                    or "6b. **GIT." not in _ship_t):
        fail("cross-doc drift [no-publish-split] -- phases/ship.md must say "
             "`no-publish` is a permission and not an absence of git, must "
             "record the real reason in the skipped-publish line rather than "
             "a hardcoded `no git`, and must keep the release step split "
             "into a LOCAL half and a GIT half. Fused, the block ordered a "
             "step that commits and pushes while calling it local, and told "
             "a mode that forbids committing to skip only the push")
        drift_ok = False

    # 1b10. A ticket whose completion condition can never be met belongs in
    #       `## BLOCKED`, not `## TODO`. In `## TODO` it is workable by every
    #       test the Pick Rule applies, so the board orders work nobody can
    #       finish -- and the two defensible responses (adopt it and produce
    #       nothing, or skip it and break the topmost-workable rule) are the
    #       divergence this section exists to remove.
    if ("That is also where a ticket goes when its completion" not in rfc
            or "The same section holds a ticket whose work another"
            not in rfc):
        fail("cross-doc drift [permanent-owner-section] -- RFC 1.2 must say "
             "that a ticket whose completion condition can never be met sits "
             "in `## BLOCKED` with the reason, not in `## TODO`. A permanent "
             "warning owner in `## TODO` passes every workability test the "
             "Pick Rule applies while its own `verify:` says closing it FAILs, "
             "and so does a ticket phases/translate.md gives to a dedicated "
             "instance while forbidding Core to grind through it")
        drift_ok = False

    # 1b11. Stale translation next to updated source. `phases/translate.md`
    #       states the duty and names the gap in the same breath: a stale
    #       translation is worse than none "since nothing signals they've
    #       gone wrong" -- and nothing did. Commit dates cannot serve: every
    #       release bumps the version badge in all 65 locale files, so they
    #       always look exactly as fresh as their source. The badge check
    #       measures the badge, not the prose, and reads like freshness.
    #
    #       Each locale source carries the digest of the English source it
    #       was translated FROM, with version strings normalised out so a
    #       badge bump moves nothing. This is `style_contract`'s shape one
    #       surface over: a scalar whose truth lives in another file, so the
    #       claim can be checked against evidence instead of believed.
    #
    #       WARN, not FAIL, and deliberately. The duty section 3 names is a
    #       SIGNAL -- Core edits English prose constantly and 29 of the 32
    #       languages are subSaipen work by rule, so a FAIL would gate every
    #       Core release on a translation pass and be switched off the first
    #       time it was inconvenient. A WARN that survives releases is then
    #       owned by a live ticket under T-401's rule, which is the existing
    #       route for known debt rather than a new one.
    _tr_dir = _tools_parent / ".saipen" / "saitranslate" / "kitchen"
    _en_src = _tools_parent / "README.md"
    if _tr_dir.is_dir() and _en_src.is_file():
        _want = hashlib.sha256(re.sub(
            r"\d+\.\d+\.\d+", "VERSION",
            _en_src.read_text(encoding="utf-8-sig")).encode("utf-8")
        ).hexdigest()
        _stale, _unstamped = [], []
        for _loc in sorted(_tr_dir.glob("*/README_*.md")):
            _m = re.search(r"<!-- source-digest: README\.md sha256:([0-9a-f]+) -->",
                           _loc.read_text(encoding="utf-8-sig"))
            if _m is None:
                _unstamped.append(_loc.parent.name)
            elif _m.group(1) != _want:
                _stale.append(_loc.parent.name)
        if _stale:
            warn("translation-stale",
                 f"{len(_stale)} locale README(s) carry a source digest that "
                 f"no longer matches README.md's normalised content "
                 f"({', '.join(_stale)}) -- the English prose moved and the "
                 f"translation did not follow. Version strings are normalised "
                 f"out, so a badge bump can never cause this")
        if _unstamped:
            warn("translation-unstamped",
                 f"{len(_unstamped)} locale README(s) carry no "
                 f"`source-digest` marker ({', '.join(_unstamped)}), so "
                 f"nothing can tell whether they followed the English source "
                 f"or were left behind")

    # 1b12. The translator has to know to restamp, or the marker rots into
    #       a permanent stale warning nobody can clear by translating.
    _tr_doc = rfc_path.parent / "phases" / "translate.md"
    _tr_t = (_tr_doc.read_text(encoding="utf-8-sig")
             if _tr_doc.is_file() else "")
    if _tr_t and "Something signals it now, and keeping that signal" not in _tr_t:
        fail("cross-doc drift [translation-digest] -- phases/translate.md "
             "must tell the translator to recompute and write the "
             "`source-digest` marker for the locales it actually translated. "
             "Without that the marker only ever ages, and section 3's own "
             "sentence about nothing signalling a stale translation stays "
             "true with a signal sitting right there")
        drift_ok = False

    # 1b13. The gate on new prose. A section that eliminates no defect class
    #       costs every agent that reads it, forever, and implies coverage
    #       that does not exist. Stated once in 1.1 and cited from the two
    #       phases where additions actually happen -- restating it in each
    #       would be the exact failure it names.
    if "names the defect class it eliminates" not in rfc:
        fail("cross-doc drift [prose-gate] -- RFC 1.1 must require a new "
             "section to name the defect class it eliminates. Without it, "
             "prose that forbids nothing is indistinguishable from prose that "
             "does, and the reader stops looking for a check that was never "
             "written")
        drift_ok = False
    for _d, _why in ((rfc_path.parent / "phases" / "build.md", "build.md"),
                     (rfc_path.parent / "phases" / "add.md", "add.md")):
        if (_d.is_file()
                and "names the defect class it eliminates"
                not in _d.read_text(encoding="utf-8-sig")):
            fail(f"cross-doc drift [prose-gate] -- phases/{_why} must cite "
                 "1.1's gate before its own addition ladder. The gate lives "
                 "in one place and is cited, never restated: two copies "
                 "drift, which is one of the three shapes the gate rejects")
            drift_ok = False

    # 1c. § 2.1's ZERO-PROMPT rule is a MUST, and its exception list has to
    #     carry every live carve-out or the MUST orders a violation. It named
    #     only `phase: BLOCKED` while § 1.3 bans `ADD` outright under
    #     `mode: read-only` -- so a read-only agent on a clean HUNT was
    #     ordered into a phase it may not enter, with each rule looking
    #     followed on its own. Same shape as § 1.3's own ban list (four phases
    #     presented as exhaustive) and § 1.6's from-any-phase set (five where
    #     § 1.10 had seven), both already fixed.
    _s21_i = rfc.find("### 2.1")
    _s21 = rfc[_s21_i:rfc.find("### 2.2", _s21_i)] if _s21_i >= 0 else ""
    if not _s21:
        fail("cross-doc check 'zero-prompt-exceptions' cannot find RFC § 2.1 "
             "-- update tools/validate.py deliberately; a drift check that "
             "silently stops checking still prints PASS")
        drift_ok = False
    elif ("MUST NOT enter `ADD` at all" not in _s21
            or "this list is the complete one" not in _s21):
        fail("cross-doc drift [zero-prompt-exceptions] -- RFC § 2.1's "
             "ZERO-PROMPT rule must declare its exception list complete and "
             "name the `mode: read-only` carve-out: read-only reaches HUNT "
             "report-only and MUST NOT enter ADD, which § 1.3 bans outright. "
             "Without it the MUST orders a phase the mode forbids")
        drift_ok = False

    # 2a. No shipped file instructs an agent to write a SUPERSEDED schema
    #     version. § 1.2's own legacy-upgrade sentence said "MUST upgrade to
    #     v2" long after the schema reached 3, so the single instruction for
    #     escaping legacy state ordered a value the validator immediately
    #     WARNs as legacy -- unreadable as a defect, because a version number
    #     reads as fact. Current is fine; ABOVE current is fine too, since
    #     that is how a doc describes a future-schema example. Only a
    #     superseded literal is rot. CHANGELOG.md is exempt for the same
    #     reason the palette guard exempts it: it records what the value WAS.
    _stale_schema = []
    _schema_roots = [rfc_path.parent / "phases",
                     _tools_parent / "extensions",
                     _tools_parent / ".saipen" / "KNOWLEDGE"]
    _schema_docs = [rfc_path,
                    rfc_path.parent / "CORE.md",
                    rfc_path.parent / "MAINTENANCE.md"] + [
        d for root in _schema_roots if root.is_dir()
        for d in sorted(root.rglob("*.md"))] + [
        p for p in [rfc_path.parent / "BOOT.md",
                    rfc_path.parent / "STYLE.md",
                    rfc_path.parent / "CONFORMANCE.md",
                    _tools_parent / "extensions" / "subs" / "TEMPLATE"
                    / "STATE.md",
                    _tools_parent / "extensions" / "templates"
                    / "STATE.md"] if p.is_file()]
    for _doc in _schema_docs:
        for _m in re.finditer(r"schema_version:\s*(\d+)",
                              _doc.read_text(encoding="utf-8-sig")):
            if 1 <= int(_m.group(1)) < CURRENT_SCHEMA_VERSION:
                _stale_schema.append(f"{_doc.as_posix()}: {_m.group(0)!r}")
    for _b in dict.fromkeys(_stale_schema):
        fail(f"cross-doc drift [stale-schema-version] -- {_b} names a "
             f"superseded schema version while the current one is "
             f"{CURRENT_SCHEMA_VERSION}. An agent obeying it writes state "
             f"this validator WARNs as legacy on the spot, and a shipped "
             f"template born there is born legacy (RFC § 1.2, § 1.5)")
        drift_ok = False

    # 2b. Ticket-bearing five: RFC § 1.2's `PHASE` pairing rule vs the copy
    #     this file enforces with. Same shape as the phase enum -- the list is
    #     hand-kept here and pinned to the sentence that owns it, so a
    #     deliberate change to § 1.2 fails loudly instead of leaving the
    #     validator quietly enforcing the previous protocol.
    s = _rfc_sentence(
        "ticket-bearing",
        r"names as ticket-bearing\*\* -- (.+?) -- and omitted", rfc)
    if s is None:
        drift_ok = False
    else:
        drift_ok &= _compare("ticket-bearing", set(_ticks(s)),
                             set(TICKET_BEARING_PHASES),
                             "validate.py TICKET_BEARING_PHASES")

    # 3. From-any-phase set: RFC § 1.6 vs ANY_FROM here.
    s = _rfc_sentence("any-from", r"\*\*From-any-phase set\*\*: (.+?)\.\n", rfc)
    if s is None:
        drift_ok = False
    else:
        drift_ok &= _compare("any-from", set(_ticks(s)), ANY_FROM,
                             "validate.py ANY_FROM")

    # 3b. Transition-table EDGES: RFC § 1.6's quick-reference table vs the
    #     DFA here. The phase-enum check above compares NAMES; nothing ever
    #     compared EDGES, so a phase doc could prescribe an exit the DFA
    #     rejects while both carried an official stamp (T-426). The table is
    #     a ```text fence, parsed row-by-row; the DFA is the enforced copy.
    _table_fence = re.search(r"```text\n((?:[A-Z]+ +-> .*\n)+)```", rfc)
    if _table_fence is None:
        fail("cross-doc drift [transition-table] -- RFC § 1.6's ```text "
             "transition table not found, so its edges cannot be compared "
             "to the DFA")
        drift_ok = False
    else:
        _rfc_edges = {}
        for _row in _table_fence.group(1).splitlines():
            _tm = re.match(r"^([A-Z]+) +-> (.+)$", _row)
            if not _tm:
                fail(f"cross-doc drift [transition-table] -- unparseable row "
                     f"in RFC § 1.6's table: {_row!r}")
                drift_ok = False
                continue
            _rfc_edges[_tm.group(1)] = {
                t.strip() for t in _tm.group(2).split("|")}
        _dfa_edges = {p: set(v) for p, v in VALID_TRANSITIONS.items()}
        if _rfc_edges != _dfa_edges:
            _diffs = []
            for _p in sorted(set(_rfc_edges) | set(_dfa_edges)):
                _a, _b = _rfc_edges.get(_p, set()), _dfa_edges.get(_p, set())
                if _a != _b:
                    _diffs.append(f"{_p}: RFC {sorted(_a)} vs DFA {sorted(_b)}")
            fail("cross-doc drift [transition-table] -- RFC § 1.6's table "
                 "disagrees with validate.py's DFA on edges: "
                 + "; ".join(_diffs)
                 + ". The DFA is the enforced copy; bring the table to it, "
                 "or change both deliberately")
            drift_ok = False

    # 3c. Phase-doc exit EDGES: each phases/*.md exit line (`STATE -> X` /
    #     `STATE.phase -> X`) may only name edges the DFA allows from that
    #     phase. A doc that prescribes an exit the DFA rejects is the third
    #     official copy of the transition table (T-426). Double-quoted spans
    #     are masked first: review.md's "There is no \"STATE -> DONE\" branch
    #     here" is a NEGATION, not a claim -- a parser that read it would flag
    #     the very edge the sentence denies. Targets are backticked-or-bare
    #     phase names in a comma/"or"/pipe list, optionally wrapped onto the
    #     next line (prepare.md writes `STATE.phase ->` then the target).
    _exit_re = re.compile(
        r"STATE(?:\.phase)?\s*->\s*"
        r"((?:`?[A-Z][A-Z0-9]*`?(?:\s*,\s+or\s+|\s*,\s*|"
        r"\s+or\s+|\s*\|\s*|\s+)?)+)")
    _exit_problems = []
    for _pd in sorted((rfc_path.parent / "phases").glob("*.md")):
        _ph = _pd.stem.upper()
        _allowed = set(VALID_TRANSITIONS.get(_ph, []))
        _body = _pd.read_text(encoding="utf-8-sig")
        _masked = re.sub(r'"[^"]*"', lambda m: " " * len(m.group(0)),
                         _body)
        for _em in _exit_re.finditer(_masked):
            for _t in re.findall(r"[A-Z][A-Z0-9]*", _em.group(1)):
                if _t not in _allowed:
                    _exit_problems.append(
                        f"{_pd.name} prescribes STATE -> {_t}, which the DFA "
                        f"does not allow from {_ph}")
    if _exit_problems:
        fail("cross-doc drift [phase-exit] -- " + "; ".join(_exit_problems)
             + ". A phase doc may only name edges that phase's DFA row "
             "allows; the phase doc is a copy, the DFA is enforced")
        drift_ok = False

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

    # Scenario READMEs are protocol prose too. The portable-floor check above
    # caught validate.sh/ps1 when they still banned read-only from four phases,
    # but two behavioral fixtures kept teaching that same dead list because
    # this block only guarded required-field counts there. A README that says
    # what `mode: read-only` MUST NOT enter is a copy of RFC § 1.3's moving
    # set; compare it or it rots quietly.
    if _scen.is_dir():
        _core_read_only_docs = []
        for _doc in sorted(_scen.glob("*/README.md")):
            _body = _doc.read_text(encoding="utf-8-sig")
            if "read-only" not in _body or "MUST NOT enter" not in _body:
                continue
            if "subSaipen" in _body or "subsaipen" in _body.lower():
                continue
            _body_norm = _body.replace("\n", " ")
            _m = re.search(r"read-only`?.{0,200}?MUST NOT enter\s+(.+?)(?:--|\.|$)",
                           _body_norm)
            if not _m:
                continue
            _doc_bans = set(re.findall(r"`([A-Z]+)`", _m.group(1)))
            if _doc_bans and _doc_bans != set(READ_ONLY_BANNED_PHASES):
                _core_read_only_docs.append(
                    f"{_doc.relative_to(_tools_parent).as_posix()} "
                    f"lists {sorted(_doc_bans)}")
        if _core_read_only_docs:
            fail("cross-doc drift [scenario-read-only-bans] -- scenario "
                 "README(s) re-list RFC § 1.3's Core read-only ban "
                 "incorrectly: " + "; ".join(_core_read_only_docs[:4]))
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
    #    The sweep above reads `next_action:` assignments only, and RFC.md is
    #    not one of its roots -- which is exactly how § 2.2's worked example
    #    came to spell out a `PHASE` form § 1.2 forbids, in running prose, in
    #    the constitution. Only the unambiguous direction is swept here: a
    #    ticket ref bolted onto a phase that does not take one. The other
    #    direction (a bare ticket-bearing phase) is legitimate prose all over
    #    these documents and is checked where it is actually a command, on
    #    STATE.md itself.
    _phase_ref_lit = re.compile(r"\bPHASE\s+([A-Z][A-Z_-]{2,})\s+T-(?:\d+|###)")
    for doc in [rfc_path, rfc_path.parent / "CORE.md",
                rfc_path.parent / "MAINTENANCE.md"] + [
                d for root in doc_roots if root.is_dir()
                             for d in sorted(root.rglob("*.md"))]:
        for m in _phase_ref_lit.finditer(doc.read_text(encoding="utf-8-sig")):
            if m.group(1) not in TICKET_BEARING_PHASES:
                fail(f"cross-doc drift [phase-ticket-ref] -- "
                     f"{doc.as_posix()} writes {m.group(0)!r}, attaching a "
                     f"ticket ref to a phase RFC § 1.2 says omits one. The "
                     f"ref belongs to "
                     f"{'/'.join(sorted(TICKET_BEARING_PHASES))} alone; every "
                     f"other phase names its ticket in `task:`. An example "
                     f"that fails its own rule is worse than no example")
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

    # 10. Portable-floor parity is behavioral. tools/audit_floor.py derives
    #     required fields and read-only phase bans from RFC.md, mutates a valid
    #     project for each value, and executes both floor scripts. This
    #     validator deliberately does not infer behavior from shell text.

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
        ("saipen/HABITS.md", "habit citation + counter-mechanism checks"),
        ("saipen/RFC.md",            "stub for backward compat"),
        ("saipen/CORE.md",           "source of truth for core cross-doc sets"),
        ("saipen/MAINTENANCE.md",    "source of truth for maintenance cross-doc sets"),
        ("saipen/BOOT.md",           "re-enumeration + required-field-count checks"),
        ("saipen/CONFORMANCE.md",    "re-enumeration + count + row-ID checks"),
        ("saipen/CONVERGE.md",       "convergence stage-order + closure-bar + post-K ordering checks"),
        ("saipen/IMPROVE.md",        "meta-control proof (no IMPROVE phase row, no phases/improve.md)"),
        ("saipen/OPS.md",            "mechanical-layer ownership doc (must state the semantic/mechanical boundary)"),
        ("saipen/phases/*.md",       "phase-enum sync + prescribed-WAIT category check"),
        ("extensions/**/*.md",       "prescribed-WAIT category check"),
        ("guides/GUIDE_*.md",        "guide WAIT-shape check"),
        ("GUIDE.md",                 "guide WAIT-shape check"),
        ("tests/scenarios/*/README.md", "required-field-count check + expect/reason parsing"),
        ("tests/scenarios/*/.saipen/*.md", "run_scenarios.py runs this validator against each fixture"),
        ("README*.md",                "version-badge check"),
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
        ("saipen/INDEX.md",   "lazy load index; acts as a table of contents, not a rule source"),
        ("saipen/SKILL.md",   "reading-order entry point for skill platforms; its file references and boot-critical voice/language metadata are checked directly"),
        ("saipen/STYLE.md",   "chat voice; persistence/language contracts and RFC citation are checked directly, while prose tone itself is not machine-checkable"),
        ("saipen/UI.md",      "visual spec for UI work, disjoint from the state protocol"),
        ("BROCHURE_DED.md",   "translated presentation brochure for saitranslate"),
        ("SPEC.md",           "design intent and rationale, deliberately not normative"),
        ("CHANGELOG.md",      "history; never read by an agent, never a rule source"),
        ("CHANGELOG_ARCHIVE.md", "sealed history, same as above"),
        ("CONTRIBUTING.md",   "human process, not agent-facing"),
        ("SECURITY.md",       "disclosure policy, not agent-facing"),
        ("CODE_OF_CONDUCT.md", "human conduct, not agent-facing"),
        ("THIRD_PARTY_NOTICES.md", "third-party provenance/attribution record, not a rule source"),
        (".github/**/*.md",   "issue/PR templates, not agent-facing"),
        (".github/*.md",      "issue/PR templates, not agent-facing"),
        ("tests/scenarios/README.md", "scenario format documentation, not a fixture"),
        (".pytest_cache/*.md", "generated tool cache, never a shipped document"),
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
    _rfc_text = _read_rfc(rfc_path)
    _section_paths = {
        "CORE": rfc_path.parent / "CORE.md",
        "MAINTENANCE": rfc_path.parent / "MAINTENANCE.md",
        "PROTOCOL": _tools_parent / "extensions" / "subs" / "PROTOCOL.md",
    }
    _section_sets = {}
    for _owner, _owner_path in _section_paths.items():
        _owner_text = (_owner_path.read_text(encoding="utf-8-sig")
                       if _owner_path.is_file() else "")
        _section_sets[_owner] = set(re.findall(
            r"^#{2,4}\s+§?\s*(\d+\.\d+)(?![\d.])", _owner_text,
            re.MULTILINE))
    _section_sets["RFC"] = (_section_sets["CORE"]
                            | _section_sets["MAINTENANCE"])
    _sections = _section_sets["RFC"]
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
            # Citation ownership is explicit. `CORE.md § x`,
            # `MAINTENANCE.md § x`, and `PROTOCOL.md § x` resolve only against
            # that document. An unqualified `§ x` is local to the document
            # carrying it; it is never silently reassigned to the old RFC
            # union. Documents with no numbered sections retain legacy bare
            # prose references without pretending the checker verified them.
            _qualified_spans = []
            for _cit in re.finditer(
                    r"\b(CORE|MAINTENANCE|PROTOCOL|RFC)\.md\s*§\s*"
                    r"(\d+\.\d+)", _body):
                _owner, _s = _cit.group(1), _cit.group(2)
                _qualified_spans.append(_cit.span())
                if _s not in _section_sets[_owner]:
                    _dangling.append(
                        f"{_doc.name} cites {_owner}.md § {_s}")
            _local_sections = set(re.findall(
                r"^#{2,4}\s+§?\s*(\d+\.\d+)(?![\d.])", _body,
                re.MULTILINE))
            if _local_sections:
                _local_families = {s.split(".", 1)[0]
                                   for s in _local_sections}
                for _cit in re.finditer(r"§\s*(\d+\.\d+)", _body):
                    if any(a <= _cit.start() < b for a, b in _qualified_spans):
                        continue
                    _s = _cit.group(1)
                    # Bare citations are local. Only a number in this
                    # document's own section family can therefore be checked
                    # as local; another family's legacy bare cross-reference
                    # is not silently reassigned to RFC and makes no verified
                    # claim. New cross-document references use a qualifier.
                    if (_s.split(".", 1)[0] in _local_families
                            and _s not in _local_sections):
                        _dangling.append(
                            f"{_doc.name} cites local § {_s}")
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
                    r"\b(RFC|CORE|MAINTENANCE|BOOT|STYLE|UI|CONFORMANCE|SKILL)\.md\b", _body))):
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
        # The ledger belongs to the project being validated, not necessarily
        # to the validator's install directory. Running an installed skill copy
        # against the SAIPEN home otherwise combines project git tags with a
        # missing installed CHANGELOG and creates false phantom releases.
        _changelog_files = tuple(
            path for path in (Path("CHANGELOG.md"), Path("CHANGELOG_ARCHIVE.md"))
            if path.is_file())

        def _changelog_versions():
            versions = set()
            for path in _changelog_files:
                versions |= set(re.findall(
                    r"^## (\d+\.\d+\.\d+)",
                    path.read_text(encoding="utf-8-sig"), re.MULTILINE))
            return versions

        _ledger |= _changelog_versions()
        _tag_list = set()
        _tag_problem = None
        try:
            _r = subprocess.run(["git", "tag", "-l", "v*"],
                                capture_output=True, text=True, check=False)
            if _r.returncode == 0:
                _tag_list = {ln.strip()[1:] for ln in _r.stdout.splitlines()
                             if ln.strip().startswith("v")}
            else:
                _tag_problem = f"git tag -l exited {_r.returncode}"
        except (OSError, subprocess.SubprocessError) as _e:
            _tag_problem = f"git tag -l failed: {_e}"
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
        # The baseline belongs to the release ledger but must be loadable
        # WITHOUT git: the ownership check below (T-401) is a changelog-age
        # fact, not a tag fact, and the audit harness copies the tree with no
        # .git. Loading it inside the `_tags_seen` gate below would make every
        # no-git run crash on NameError instead of skipping only the
        # tag-dependent halves.
        _baseline_path = _tools_parent / "tools" / "release_ledger_baseline.json"
        _baseline = None
        try:
            _baseline = json.loads(_baseline_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as _e:
            fail(f"release ledger baseline unreadable at {_baseline_path}: {_e}")
            drift_ok = False
        _baseline_tag_only = set()
        _baseline_changelog_only = set()
        if isinstance(_baseline, dict):
            if set(_baseline) != {"tag_only", "changelog_only", "warn_slugs"}:
                fail("release ledger baseline must contain exactly tag_only, "
                     "changelog_only and warn_slugs maps")
                drift_ok = False
            else:
                for _direction, _target in (
                        ("tag_only", _baseline_tag_only),
                        ("changelog_only", _baseline_changelog_only)):
                    _entries = _baseline[_direction]
                    if not isinstance(_entries, dict):
                        fail(f"release ledger baseline {_direction} must be a map")
                        drift_ok = False
                        continue
                    for _version, _evidence in _entries.items():
                        _version_t = _tup(_version)
                        if (not _version_t or not isinstance(_evidence, dict)
                                or not _evidence.get("commit")
                                or not _evidence.get("reason")):
                            fail(f"release ledger baseline {_direction} entry "
                                 f"{_version!r} lacks semver/commit/reason evidence")
                            drift_ok = False
                            continue
                        _target.add(_version_t)
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
            _tag_detail = f" ({_tag_problem})" if _tag_problem else ""
            warn("release-ledger",
                 "git tag list unavailable or empty -- the release ledger has "
                 "only its CHANGELOG half, so the phantom-version check is "
                 "skipped rather than run against incomplete data"
                 f"{_tag_detail}")
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
            _chg_v = {t for t in (_tup(v) for v in _changelog_versions()) if t}
            _tag_v = {t for t in (_tup(v) for v in _tag_list) if t}

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
                _raw_no_entry = {v for v in _tag_v if v >= _overlap} - _chg_v
                _raw_no_tag = {v for v in _chg_v if v >= _overlap} - _tag_v
                _stale_baseline = ((_baseline_tag_only - _raw_no_entry)
                                   | (_baseline_changelog_only - _raw_no_tag))
                if _stale_baseline:
                    fail("release ledger baseline is stale for: "
                         f"{_vs(_stale_baseline)}. The recorded divergence no "
                         "longer exists; remove its exception so the baseline "
                         "cannot become a permanent blind spot")
                    drift_ok = False
                _no_entry = _raw_no_entry - _baseline_tag_only
                _no_tag = _raw_no_tag - _baseline_changelog_only
                if _no_entry:
                    warn("release-ledger",
                         f"{len(_no_entry)} release(s) carry a git tag but no "
                         f"CHANGELOG entry: {_vs(_no_entry)}")
                if _no_tag:
                    warn("release-ledger",
                         f"{len(_no_tag)} release(s) have a CHANGELOG entry "
                         f"but no git tag: {_vs(_no_tag)}")
                if not _no_entry and not _no_tag and not _stale_baseline:
                    ok("release ledger has no unexpected divergence "
                       f"({len(_baseline_tag_only) + len(_baseline_changelog_only)} "
                       "historical exception(s) verified)")

        # 13c. An orphaned release tag. A v* tag exists locally whose commit
        #      is on no remote branch while the remote carries the same name.
        #      ship.md step 7 makes the tag push a separate command from the
        #      branch push, so a rejected branch push can still be followed by
        #      a successful tag push -- the tag lands on the remote pointing
        #      at a commit that is on no remote branch. Second occurrence in
        #      this repository: E-1787 (v7.171.0) and E-1882 (v7.176.0), and
        #      the recovery text's claim that such a tag was "by definition
        #      never successfully pushed" held only while the tag rode the
        #      branch push. The local half (a tag whose commit rides no
        #      refs/remotes branch) is cheap and network-free; the remote's
        #      tag set is read with ls-remote ONLY when a candidate exists,
        #      and where that cannot answer (no remote, offline) the check
        #      stands down rather than guess -- same fail-safe as the no-git
        #      gate above.
        _orphan_candidates = []
        if _tags_seen:
            _remote_branches = []
            try:
                _rb = subprocess.run(
                    ["git", "for-each-ref", "refs/remotes",
                     "--format=%(refname)"],
                    capture_output=True, text=True, check=False)
                if _rb.returncode == 0:
                    _remote_branches = [ln.strip() for ln in
                                        _rb.stdout.splitlines() if ln.strip()]
            except (OSError, subprocess.SubprocessError):
                _remote_branches = []
            if _remote_branches:
                for _tag in sorted(_tag_list):
                    _full = "v" + _tag
                    _rc = subprocess.run(
                        ["git", "rev-parse", f"{_full}^{{commit}}"],
                        capture_output=True, text=True, check=False)
                    if _rc.returncode != 0:
                        continue
                    _sha = _rc.stdout.strip()
                    _on_branch = False
                    for _br in _remote_branches:
                        _mb = subprocess.run(
                            ["git", "merge-base", "--is-ancestor", _sha, _br],
                            capture_output=True, check=False)
                        if _mb.returncode == 0:
                            _on_branch = True
                            break
                    if not _on_branch:
                        _orphan_candidates.append(_full)
        _orphan_tags = []
        if _orphan_candidates:
            _remote_names = []
            try:
                _rn = subprocess.run(["git", "remote"], capture_output=True,
                                     text=True, check=False)
                if _rn.returncode == 0:
                    _remote_names = [ln.strip() for ln in
                                     _rn.stdout.splitlines() if ln.strip()]
            except (OSError, subprocess.SubprocessError):
                _remote_names = []
            if _remote_names:
                try:
                    _lr = subprocess.run(
                        ["git", "ls-remote", "--tags", _remote_names[0]],
                        capture_output=True, text=True, check=False)
                except (OSError, subprocess.SubprocessError):
                    _lr = None
                if _lr is not None and _lr.returncode == 0:
                    _remote_tag_names = {
                        ln.split("\t")[-1].split("/")[-1]
                        for ln in _lr.stdout.splitlines()
                        if "\trefs/tags/" in ln}
                    _candidates = [t for t in _orphan_candidates
                                   if t in _remote_tag_names]
                    # A stale refs/remotes can flag a legitimately landed
                    # tag: the branch push succeeded but this clone has not
                    # fetched, so the commit sits on no *local* tracking
                    # ref while the remote branch tip moved past it. The
                    # remote itself can answer -- read its live branch heads
                    # (same round-trip family as --tags) and drop any
                    # candidate whose commit is provably on one: sha-equal to
                    # a head, or an ancestor of a head whose object this
                    # clone already holds.
                    _live_heads = []
                    try:
                        _lh = subprocess.run(
                            ["git", "ls-remote", "--heads",
                             _remote_names[0]],
                            capture_output=True, text=True, check=False)
                        if _lh.returncode == 0:
                            _live_heads = [ln.split("\t")[0]
                                           for ln in _lh.stdout.splitlines()
                                           if "\trefs/heads/" in ln]
                    except (OSError, subprocess.SubprocessError):
                        _live_heads = []
                    _orphan_tags = []
                    for _tag in _candidates:
                        _rc = subprocess.run(
                            ["git", "rev-parse", f"{_tag}^{{commit}}"],
                            capture_output=True, text=True, check=False)
                        if _rc.returncode != 0:
                            continue
                        _sha = _rc.stdout.strip()
                        if _sha in _live_heads:
                            continue
                        _landed = False
                        for _head in _live_heads:
                            _mb = subprocess.run(
                                ["git", "merge-base", "--is-ancestor",
                                 _sha, _head],
                                capture_output=True, check=False)
                            if _mb.returncode == 0:
                                _landed = True
                                break
                        if not _landed:
                            _orphan_tags.append(_tag)
        if _orphan_tags:
            fail("orphaned release tag(s) -- the remote carries "
                 f"{', '.join(_orphan_tags[:4])} but their commit(s) are on "
                 "no remote branch: a tag push succeeded while the branch "
                 "push it was supposed to ride did not land (E-1787, E-1882). "
                 "Repair by force-moving the tag to the release commit on "
                 "the branch, or deleting it from the remote and re-pushing "
                 "after the branch push lands")
            drift_ok = False

        # T-401: WARN slug ownership from release history. The baseline
        #      records each tracked slug's first/last seen release and its
        #      rationale; a slug STILL EMITTED this run that has survived
        #      WARN_OWNER_SPAN consecutive releases is standing debt and MUST
        #      be named by a live BOARD ticket. `## BLOCKED` counts: a ticket
        #      there is on the board, names the slug and has not been closed,
        #      and excluding it forced the permanent owners to sit in
        #      `## TODO` -- where the Pick Rule MUST take the topmost workable
        #      ticket, so the board ordered an agent to work something whose
        #      own `verify:` says closing it FAILs. Two honest agents then
        #      diverge: one adopts it and produces nothing, the other skips it
        #      and breaks the Pick Rule. `## DONE` still does not count -- that
        #      is a closure claim, which is the thing being guarded (T-427).
        #      Aging an
        #      unowned slug in the baseline DATA fails; the identical aged
        #      slug with a live naming ticket passes. The red control mutates
        #      baseline data, never validator wording.
        _warn_slugs = (_baseline.get("warn_slugs")
                       if isinstance(_baseline, dict) else None)
        if _warn_slugs is not None and not isinstance(_warn_slugs, dict):
            fail("release ledger baseline warn_slugs must be a map of "
                 "slug -> first/last seen + rationale")
            drift_ok = False
        elif isinstance(_warn_slugs, dict):
            _slugs_ok = True
            for _slug, _meta in _warn_slugs.items():
                if (not isinstance(_meta, dict)
                        or not _meta.get("first_seen")
                        or not _meta.get("last_seen")
                        or not _meta.get("rationale")):
                    fail(f"release ledger baseline warn_slugs entry {_slug!r} "
                         "needs first_seen, last_seen and rationale")
                    drift_ok = False
                    _slugs_ok = False
                    continue
                _ft = _tup(_meta["first_seen"])
                _lt = _tup(_meta["last_seen"])
                if not _ft or not _lt:
                    fail(f"release ledger baseline warn_slugs entry {_slug!r} "
                         "has non-semver first_seen/last_seen")
                    drift_ok = False
                    _slugs_ok = False
                    continue
                # Resolved slugs (not emitted this run) are history, not debt.
                if _slug not in warnings:
                    continue
                _age = sum(1 for v in _known if _ft <= v <= _lt)
                if _age < WARN_OWNER_SPAN:
                    continue
                _live_lines = [
                    board_lines[t["line_no"] - 1] for t in tickets.values()
                    if t["section"] in ("## DOING", "## TODO",
                                        "## BLOCKED")]
                if not any(_slug in ln for ln in _live_lines):
                    fail(f"warn ownership [release history] -- WARN slug "
                         f"`{_slug}` has survived {_age} consecutive releases "
                         f"but no live BOARD ticket names it; create an "
                         f"owning ticket or fix the warning (T-401)")
                    drift_ok = False
                    _slugs_ok = False
            if _slugs_ok:
                ok(f"warn slug ownership verified for {len(_warn_slugs)} "
                   "tracked slug(s)")


    # 13c. Vintage Golden is the design language; Golden Default is its one
    #      palette. UI.md owns the values, while this digest is the mechanical
    #      witness that prevents a plausible generic dark-golden set from being
    #      substituted under the same name. The stale-name list remains because
    #      historical palette renames once drifted across 46 shipped docs.
    def _rel_doc(_p):
        try:
            return _p.relative_to(_tools_parent).as_posix()
        except ValueError:
            return _p.name

    _ui = _tools_parent / "saipen" / "UI.md"
    if _ui.is_file():
        _ui_body = _ui.read_text(encoding="utf-8-sig")
        _design_language = "Vintage Golden"
        _palette = "Golden Default"
        # Every name the palette has HAD. Assembled from fragments so this
        # file, CONFORMANCE.md and the row describing the rename can all
        # discuss it without tripping it -- the fifth rule this session that
        # had to stop quoting its own illustration. Grows by one entry per
        # rename; the second was a one-letter correction shipped an hour
        # after the first, which is exactly why this is a list and not a
        # constant.
        _superseded = ("Dark" + " Golden", "Win" + "tage Golden")
        if _design_language not in _ui_body:
            fail(f"UI.md no longer names its design language "
                 f"{_design_language!r} -- palette and design language are "
                 "distinct contracts")
            drift_ok = False
        if _palette not in _ui_body:
            fail(f"UI.md no longer names its palette {_palette!r} -- the "
                 f"palette name is normative and every other document "
                 f"references it")
            drift_ok = False
        if "**Golden Default is the default palette.**" not in _ui_body:
            fail("UI.md lost the Golden Default default mandate -- merely "
                 "mentioning the palette does not make it the mandatory "
                 "default")
            drift_ok = False
        _token_names = (
            "background", "backgroundSoft", "surface", "surfaceRaised",
            "surfaceAlt", "borderDark", "borderHighlight", "bevelLight",
            "borderMuted", "textPrimary", "textSecondary", "textMuted",
            "accentTeal", "accentTealDeep", "success", "warning", "danger",
            "dangerText", "selection", "compareBack", "link",
        )
        _root_matches = re.findall(r":root\s*\{(.*?)\n\}", _ui_body, re.DOTALL)
        if len(_root_matches) != 1:
            fail("UI.md Golden Default token drift [ui-palette] -- no :root "
                 f"single-owner token block found (count={len(_root_matches)})")
            drift_ok = False
        else:
            _token_pairs = re.findall(
                r"--([A-Za-z][A-Za-z0-9]*):\s*(#[0-9A-Fa-f]{6})\s*;",
                _root_matches[0])
            _tokens = dict(_token_pairs)
            _all_custom_properties = re.findall(
                r"--([A-Za-z][A-Za-z0-9]*):\s*([^;\n]+)\s*;", _ui_body)
            _all_token_pairs = re.findall(
                r"--([A-Za-z][A-Za-z0-9]*):\s*(#[0-9A-Fa-f]{6})\s*;",
                _ui_body)
            _all_hex = re.findall(r"#[0-9A-Fa-f]{6}\b", _ui_body)
            if (_all_custom_properties != _token_pairs
                    or _all_token_pairs != _token_pairs
                    or len(_all_hex) != len(_token_names)):
                fail("UI.md Golden Default token drift [ui-palette] -- colour "
                     "custom-property declaration or raw hex exists outside the "
                     "single canonical :root block, or uses a non-#RRGGBB value")
                drift_ok = False
            elif (len(_token_pairs) != len(_token_names)
                    or tuple(_tokens) != _token_names):
                fail("UI.md Golden Default token drift [ui-palette] -- expected "
                     f"the closed 21-token Wintage order, got "
                     f"{len(_token_pairs)} entries: {tuple(_tokens)!r}")
                drift_ok = False
            else:
                _payload = "\n".join(
                    f"{name}={_tokens[name].upper()}" for name in _token_names)
                _palette_digest = hashlib.sha256(
                    _payload.encode("ascii")).hexdigest()
                _expected_palette_digest = (
                    "271ba26cd75948e8aeb866006f2c96d02dd25d1878028a6e3b15b3a34fe92979"
                )
                if _palette_digest != _expected_palette_digest:
                    fail("UI.md Golden Default token drift [ui-palette] -- "
                         "21-token map no longer matches Wintage "
                         "themes/goldendefault.json; got sha256:"
                         f"{_palette_digest}")
                    drift_ok = False
                else:
                    ok("Golden Default palette integrity verified (21 Wintage "
                       f"tokens, sha256:{_palette_digest[:16]})")
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
    #      hook had no equivalent signal at all. Static-contract exception:
    #      this reads one declarative generation constant; it does not claim
    #      the installer behaves correctly. Importing is unsafe because the
    #      module installs the hook at import time; installer behavior belongs
    #      in an executable sandbox probe if it is ever claimed here.
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

    # 13g. Every translated locale has a guide, and every guide has a locale.
    #      The two sides name Estonian differently -- `et` in
    #      `.saipen/saitranslate/kitchen/` (ISO 639-1, a language) and `EE` in
    #      `guides/` (ISO 3166, a country, chosen to sit beside the flag in a
    #      human-facing badge). Both conventions are defensible in their own
    #      role; what was missing is any statement of which governs where, so
    #      the sets diverged in silence and the first tool to join them would
    #      have dropped Estonian without a word. The alias is written down
    #      here, and the join is checked in both directions.
    LOCALE_GUIDE_ALIASES = {"et": "EE"}
    _kitchen = _tools_parent / ".saipen" / "saitranslate" / "kitchen"
    _guides = _tools_parent / "guides"
    if IS_SAIPEN_HOME and _kitchen.is_dir() and _guides.is_dir():
        _locales = {d.name for d in _kitchen.iterdir() if d.is_dir()}
        _guide_codes = {g.stem[len("GUIDE_"):].lower()
                        for g in _guides.glob("GUIDE_*.md")}
        _missing_guide = sorted(
            loc for loc in _locales
            if LOCALE_GUIDE_ALIASES.get(loc, loc).lower() not in _guide_codes)
        # English is the source language: it has a guide and no kitchen dir by
        # design, so it is the one legal asymmetry.
        _rev = {v.lower(): k for k, v in LOCALE_GUIDE_ALIASES.items()}
        _missing_locale = sorted(
            g for g in _guide_codes
            if g != "en" and _rev.get(g, g) not in _locales)
        if _missing_guide:
            fail(f"locale coverage -- {len(_missing_guide)} translated "
                 f"locale(s) have no guide: {', '.join(_missing_guide)}")
            drift_ok = False
        if _missing_locale:
            fail(f"locale coverage -- {len(_missing_locale)} guide(s) have no "
                 f"translated locale: {', '.join(_missing_locale)}. English is "
                 f"the source and is exempt by name")
            drift_ok = False

    # 13h. The reply-language and persistent-voice rules agree across every
    #      surface a weak model may load first.
    #      STYLE.md has carried it since v7.23.0, but BOOT.md -- the only file a
    #      bare `saipen continue` reads -- listed STYLE.md solely under "rule
    #      questions the phase doc doesn't answer". So an agent that boots and
    #      simply works never opened it, and the rule governing every response
    #      from the first token sat behind an escalation nobody escalates to.
    #      Twice observed: a session that went fully German off a bare command,
    #      and one that answered a Russian speaker in Ukrainian out of a
    #      repository that merely CONTAINS 33 translated guides. This is the one
    #      thing BOOT deliberately repeats rather than points at. SKILL.md is
    #      an even earlier discovery surface, so all four copies stay exact.
    _language_contract = (
        "Reply-language precedence: explicit current user prose "
        "(Estonian/English/Russian) > clearly Russian primary repository for "
        "bare/ambiguous input > Estonian default; another detected language "
        "uses English."
    )
    _voice_contract = (
        'Voice persistence: caveman-дед applies to every response until explicit '
        '"stop caveman" or "normal mode".'
    )
    _contract_docs = {
        name: _tools_parent / "saipen" / name
        for name in ("RFC.md", "BOOT.md", "STYLE.md", "SKILL.md")
    }
    for _name, _path in _contract_docs.items():
        if not _path.is_file():
            continue
        _text = _read_rfc(_path) if _name == "RFC.md" else _path.read_text(encoding="utf-8-sig")
        if _language_contract not in _text:
            fail(f"cross-doc drift [reply-language] -- {_name} no longer carries "
                 "the exact EE/EN/RU precedence: explicit prose first, Russian "
                 "repository only as a bare/ambiguous tie-breaker, then Estonian")
            drift_ok = False
        if _voice_contract not in _text:
            fail(f"cross-doc drift [chat-voice] -- {_name} no longer carries the "
                 "persistent caveman-дед duty and its two explicit off switches")
            drift_ok = False
        # The precedence rule above is now ONE of four values, not the rule. A
        # document that still presents it as the whole story sends an agent
        # into detection logic the setting exists to switch off, and the four
        # copies were already proven to drift apart when only one of them was
        # updated (T-404, T-405). Naming the setting is the cheap half; the
        # value itself is checked once, at its single source, below.
        if "reply_language" not in _text:
            fail(f"cross-doc drift [reply-language] -- {_name} describes the "
                 "precedence rule without naming STYLE.md's `reply_language:` "
                 "setting, so it reads as the whole rule instead of the "
                 "`auto` value of a setting that ships pinned to `et`")
            drift_ok = False
    # The setting itself, at its one source. A user changing the reply
    # language edits exactly this line and nothing else, which only holds
    # while the value is validated where it is declared: a typo'd value that
    # silently falls back to some default would put the agent in a language
    # the user did not choose and never told them.
    if _contract_docs["STYLE.md"].is_file():
        _style_doc = _contract_docs["STYLE.md"].read_text(encoding="utf-8-sig")
        _declared_lang = re.findall(r"^\*\*`reply_language:\s*([a-z]+)`\*\*\s*$",
                                    _style_doc, re.MULTILINE)
        if len(_declared_lang) != 1:
            fail(f"cross-doc drift [reply-language] -- STYLE.md declares "
                 f"{len(_declared_lang)} reply_language setting(s); it needs "
                 f"exactly one bold line reading `reply_language: <value>`, "
                 f"one of {'/'.join(REPLY_LANGUAGES)}. Zero leaves the agent "
                 f"guessing, two leave it choosing")
            drift_ok = False
        elif _declared_lang[0] not in REPLY_LANGUAGES:
            fail(f"cross-doc drift [reply-language] -- STYLE.md sets "
                 f"reply_language: {_declared_lang[0]}, which is not one of "
                 f"{'/'.join(REPLY_LANGUAGES)}. A value outside the closed set "
                 f"is corruption, not a hint: an agent that guesses what it "
                 f"meant answers in a language nobody chose")
            drift_ok = False

    # A default nobody is told about is not a setting, it is a surprise. The
    # agent answering in Estonian to someone who never asked for Estonian
    # reads as a broken tool, and the reader has no reason to suspect one line
    # in STYLE.md would fix it. Core writes en/ru/et + Дед by hand and the
    # Japanese root mirror plus the 32 locale copies are saitranslate's; the
    # check does not care who wrote a document, only that a reader who lands
    # on it is told (T-419). A locale reader is the one MOST likely to read
    # the Estonian answer as a bug, having arrived in a third language.
    # Resolved from the PROJECT being validated, not from the home the tool
    # ships from. Gated on IS_SAIPEN_HOME, which is project-relative, while
    # the paths were tool-relative -- so an installed validator run against
    # this repository counted the agent home's entry READMEs, found none, and
    # reported "only 0 resolved" about a project that has four. Absence in
    # the wrong directory misread as a violation in the right one.
    _entry_readmes = [
        Path(_n) for _n in
        ("README.md", "README.ee.md", "README.ded.md", "README.ja.md")
        if Path(_n).is_file()]
    _kitchen_dir = Path(".saipen") / "saitranslate" / "kitchen"
    if IS_SAIPEN_HOME and _kitchen_dir.is_dir():
        _entry_readmes += [
            _r for _d in sorted(_kitchen_dir.iterdir()) if _d.is_dir()
            for _r in [_d / f"README_{_d.name.upper()}.md"] if _r.is_file()]
    # Gated on IS_SAIPEN_HOME like the count below it, and for the same
    # reason: an entry README carrying the reply-language note is a SAIPEN
    # HOME artifact. Ungated, resolving these from the project made the check
    # demand the note from any project's own README.md -- ten scenario
    # fixtures went red saying "README.md never mentions reply_language:"
    # about a README that has no business mentioning it.
    _silent_readmes = [
        _p.name for _p in (_entry_readmes if IS_SAIPEN_HOME else [])
        if "reply_language" not in _p.read_text(encoding="utf-8-sig")
    ]
    if _silent_readmes:
        fail("cross-doc drift [reply-language] -- "
             + ", ".join(_silent_readmes)
             + " never mentions `reply_language:`, so a reader meets an "
               "Estonian answer with no way to know it is a setting or where "
               "to change it")
        drift_ok = False
    # An empty candidate list passes this check without reading anything --
    # the exact "suite that collected 0 tests" shape the locale badge check
    # was already bitten by. In the repository the four root entry documents
    # are always present, so a count below four means resolution broke, not
    # that the documents stopped needing the note.
    if IS_SAIPEN_HOME and len(_entry_readmes) < 4:
        fail(f"cross-doc drift [reply-language] -- only "
             f"{len(_entry_readmes)} entry README(s) resolved for the "
             f"reply-language note; the four root entry documents are always "
             f"present here, so this check just passed on nothing")
        drift_ok = False

    # STYLE.md's guide contract, the half that is structure rather than tone.
    # Guides used to fall under Artifacts ("boring on purpose") and opened in
    # the reader's assumed jargon, which only lands for a reader who already
    # knows the domain -- everyone else stops at line one. Tone is not
    # checkable; "the hook comes before the mechanics" is.
    # `phases/translate.md` § 2's default set: six that must always exist,
    # everywhere. Without a named default, "all 32 languages" degrades to
    # whichever ones a run reached, and no absence is a defect. Дед is in it
    # for the same reason English is -- caveman+Дед is SAIPEN's own voice,
    # not a garnish on someone else's.
    _default_guides = ("GUIDE.md", "guides/GUIDE_EN.md", "guides/GUIDE_RU.md",
                       "guides/GUIDE_EE.md", "guides/GUIDE_UK.md",
                       "guides/GUIDE_JA.md", "guides/GUIDE_DED.md")
    # Their existence is NOT re-checked here: the locale-coverage check
    # already FAILs when any guide disappears, so a second existence test
    # would kill no error class the first one leaves alive. What is new is
    # that the opening contract now covers all 34 guides, not just the default
    # six.
    _all_guides = ["GUIDE.md"] + [p.relative_to(_tools_parent).as_posix() for p in _tools_parent.glob("guides/GUIDE_*.md")]
    _core_guides = [_n for _n in _all_guides
                    if (_tools_parent / _n).is_file()]
    _cold_openings = []
    for _n in _core_guides:
        _gt = (_tools_parent / _n).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        _h1 = _gt.find("\n# ")
        if _h1 == -1:
            _cold_openings.append(f"{_n} (no title to open after)")
            continue
        _after = _gt[_gt.index("\n", _h1 + 1):].lstrip("\n")
        _first = _after.split("\n\n", 1)[0]
        if "`" in _first or _first.startswith("```"):
            _cold_openings.append(_n)
    if _cold_openings:
        fail("guide opening drift -- " + ", ".join(_cold_openings)
             + " starts with mechanics instead of prose. STYLE.md's guide "
               "contract puts the why-this-exists hook first, before any "
               "command, path or fence, for a reader who does not know the "
               "domain yet")
        drift_ok = False

    if _contract_docs["BOOT.md"].is_file():
        _bt = _contract_docs["BOOT.md"].read_text(encoding="utf-8-sig")
        if "Chat voice & compression" not in _bt:
            fail("cross-doc drift [chat-voice] -- BOOT.md no longer mandates "
                 "STYLE.md (caveman-дед) before output. It governs every response "
                 "from the first token, so deferring it to an escalation is too late")
            drift_ok = False
        # T-404: the before-output mandate and the on-demand rule-question list
        # must stay disjoint. Line 101 once filed STYLE.md under lazy "rule
        # questions the phase doc doesn't answer" while line 108 ordered it
        # before any output; a live session took the cheap reading and never
        # opened the file. A file BOOT names as required-before-output that also
        # appears on its on-demand list is that contradiction back.
        # The on-demand regex REQUIRES the `saipen/` prefix on purpose: the
        # bullet's own prose says "**`STYLE.md` is deliberately NOT on this
        # list**", so matching bare backticks would false-positive the green
        # control. Only prefixed refs count as list entries; the bare mention
        # is the deliberate-absence note.
        _btn = _bt.replace("\r\n", "\n")
        _on_bullet = next((b for b in _btn.split("\n- ")
                           if b.startswith("Rule questions")), "")
        _vo_bullet = next((b for b in _btn.split("\n- ")
                           if b.startswith("**Chat voice")), "")
        if not _on_bullet or not _vo_bullet:
            fail("cross-doc drift [chat-voice] -- BOOT.md lost one of the two "
                 "T-404 anchor bullets: the on-demand 'Rule questions' list or "
                 "the before-output 'Chat voice' mandate. The disjointness "
                 "check cannot see a contradiction it cannot parse, so it fails "
                 "loud instead of passing vacuously")
            drift_ok = False
        _refs = r"`(?:saipen/|<saipen_home>/)([A-Za-z0-9_]+\.md)`"
        _ondemand = set(re.findall(_refs, _on_bullet))
        _bootread = set(re.findall(_refs, _vo_bullet))
        _straddlers = sorted(_ondemand & _bootread)
        if _straddlers:
            fail("cross-doc drift [chat-voice] -- BOOT.md files "
                 + ", ".join(f"`{f}`" for f in _straddlers)
                 + " under on-demand 'rule questions' while ordering it "
                 "before any output; the lazy reading wins (T-404)")
            drift_ok = False
        # T-405: the read must live in the NUMBERED fast path -- the
        # execution order a cold agent actually walks -- not only in a
        # trailing "Anything else" bullet below it. T-404 proved the mandate
        # EXISTS, but the read was still a bullet a weak model could walk
        # past: steps 1-8 then next_action, never reaching the bottom of the
        # file. And the path must be self-locating: "<saipen_home>/STYLE.md"
        # needs saipen_home to resolve, which can be empty or dead, while
        # "the file in the same folder as this BOOT.md" needs nothing.
        _fp_start = _btn.find("## Fast path")
        _fp_end = _btn.find("## Anything else")
        if _fp_start == -1 or _fp_end == -1 or _fp_end <= _fp_start:
            fail("cross-doc drift [chat-voice] -- BOOT.md lost its "
                 "'## Fast path' or '## Anything else' heading; the fast-path "
                 "STYLE.md read cannot be located, so the check fails loud "
                 "instead of passing vacuously (T-405)")
            drift_ok = False
        else:
            # Narrowed to fast-path step 1 itself, not the whole region: the
            # numbered steps below it now legitimately mention STYLE.md (§ 1.2's
            # voice marker is validated at step 3 and written at step 9), and a
            # region-wide substring test counts those as the mandate. It then
            # passes while step 1 says something else entirely -- a check
            # satisfied by a neighbour is not a check on the thing it names.
            _fp_region = _btn[_fp_start:_fp_end]
            _s1 = _fp_region.find("\n1. ")
            _s2 = _fp_region.find("\n2. ")
            _fp_region = (_fp_region[_s1:_s2] if -1 < _s1 < _s2 else "")
            if not _fp_region:
                fail("cross-doc drift [chat-voice] -- BOOT.md's fast path has "
                     "no parseable step 1/step 2 boundary, so the STYLE.md "
                     "mandate cannot be located inside it; failing loud "
                     "instead of passing vacuously (T-405)")
                drift_ok = False
            elif "STYLE.md" not in _fp_region or "before any output" not in _fp_region:
                fail("cross-doc drift [chat-voice] -- BOOT.md's numbered fast "
                     "path no longer orders reading STYLE.md before any "
                     "output; a cold agent that walks the numbered steps and "
                     "stops never opens the file (T-405)")
                drift_ok = False
            elif "same folder as this" not in _fp_region:
                fail("cross-doc drift [chat-voice] -- the fast-path STYLE.md "
                     "read lost its self-locating reference ('the file in the "
                     "same folder as this BOOT.md'); a bare <saipen_home>/ "
                     "path needs resolution that can be empty or dead (T-405)")
                drift_ok = False

    # 13i. The human digest is the shape ship.md promises, and is not from
    #      another era. `phases/ship.md` says "(over)write ... exactly three
    #      short lines" -- `done:`/`remaining:`/`awaiting:` -- "overwrite every
    #      time", and `saipen stop` writes the same file. Nothing checked
    #      either half, and the live one was found naming a release 33 versions
    #      old: every ship since had skipped the write, in silence, including
    #      fourteen in the session that added this check. A snapshot nobody
    #      refreshes is worse than no snapshot, because it reads as current.
    _digest = Path(".saipen/kitchen/digest.md")
    if _digest.is_file():
        _dl = [ln for ln in read_doc(_digest).splitlines() if ln.strip()]
        _want = ("done:", "remaining:", "awaiting:")
        if len(_dl) != 3 or not all(
                _dl[i].strip().lower().startswith(_want[i]) for i in range(3)):
            fail(f"{_digest.as_posix()} must be exactly three lines -- "
                 f"done:/remaining:/awaiting: in that order (phases/ship.md, "
                 f"RFC § 1.10); got {len(_dl)} line(s)")
        elif IS_SAIPEN_HOME and Path("VERSION").is_file():
            _cur_v = Path("VERSION").read_text(encoding="utf-8-sig").strip()
            _cited = re.findall(r"v(\d+\.\d+\.\d+)", " ".join(_dl))
            if _cited and _cur_v not in _cited:
                _rc, _stdout = _git_from(os.getcwd(), "tag", "-l", f"v{_cur_v}")
                if _rc == 0 and not _stdout.strip():
                    pass
                else:
                    warn("digest-stale",
                         f"{_digest.as_posix()} names v{_cited[0]} while VERSION "
                         f"is {_cur_v} -- ship.md says overwrite it after every "
                         f"push, so this snapshot has been carried past at least "
                         f"one release that did not refresh it")

    # 13j. MARKHUNT's own closure manifest. `phases/markhunt.md` specifies it
    #      in full -- `vectors:` (which of scope categories 1-5 are done),
    #      `surface:`, `findings:`, `cursor: partial | done`, and
    #      `head_start:`/`head_end:` -- and states the self-test it exists for:
    #      the file IS MARKHUNT's closure check, "the thing HUNT gets from its
    #      exact hash-match skip and MARKHUNT historically lacked, leaving
    #      completeness pure self-report". No tool had ever opened it, so
    #      completeness was back to pure self-report by a different route.
    _mh = Path(".saipen/kitchen/markhunt_progress.md")
    if _mh.is_file():
        _mf = {}
        for _ln in read_doc(_mh).splitlines():
            _m = re.match(r"^([a-z_]+):\s*(.*)$", _ln.strip())
            if _m:
                _mf[_m.group(1)] = _m.group(2).strip()
        _need = ("vectors", "surface", "findings", "cursor",
                 "head_start", "head_end")
        _absent = [f for f in _need if f not in _mf]
        if _absent:
            fail(f"{_mh.as_posix()} is missing {', '.join(_absent)} -- "
                 f"phases/markhunt.md requires a manifest, not a note: this "
                 f"file IS the closure check, and a partial one cannot close "
                 f"anything")
        _cur = _mf.get("cursor")
        if _cur and _cur not in ("partial", "done"):
            fail(f"{_mh.as_posix()} cursor is {_cur!r} -- markhunt.md defines "
                 f"exactly `partial` and `done`")
        _hs, _he = _mf.get("head_start"), _mf.get("head_end")
        if _hs and _he:
            # markhunt.md allows the literal `no-git` in BOTH fields, and the
            # closure test then "is satisfied automatically". A mixed pair is
            # undefined by that wording: one real hash and one `no-git` would
            # skip the equality test on the strength of half a reason.
            if (_hs == "no-git") != (_he == "no-git"):
                fail(f"{_mh.as_posix()} has head_start={_hs!r} and "
                     f"head_end={_he!r} -- markhunt.md permits `no-git` in "
                     f"BOTH fields, never one. A mixed pair skips the "
                     f"head-equality closure test on half a reason")
        if _cur == "done":
            _vec = set(re.findall(r"\d+", _mf.get("vectors", "")))
            _missing_vec = sorted({"1", "2", "3", "4", "5"} - _vec)
            if _missing_vec:
                fail(f"{_mh.as_posix()} says cursor: done but vectors lists "
                     f"only {sorted(_vec)} -- markhunt.md: a missing vector "
                     f"means the surface is NOT exhausted, keep going rather "
                     f"than round up (categories {', '.join(_missing_vec)})")
        elif _cur == "partial" and state.get("phase") not in ("MARKHUNT",
                                                              "BLOCKED"):
            fail(f"{_mh.as_posix()} says cursor: partial while STATE.phase is "
                 f"{state.get('phase')} -- markhunt.md says an unfinished pass "
                 f"leaves phase: MARKHUNT with next_action: `saipen markhunt`. "
                 f"Moving on closed a pass the manifest says never finished")

    # 13k. Two more copied vocabularies compared against the document that
    #      owns them -- the seventh and eighth sets to get this treatment.
    #      `SAIPEN_COMMANDS` is § 1.10's command surface and `KNOWN_FIELDS` is
    #      § 1.2's closed ticket-field list. Both were copied into the tool
    #      and never checked against their source, and the second one hid a
    #      real hole: the tool has FAILed unknown ticket fields since the
    #      beginning with a message citing "§ 1.2's field list", `verify:`
    #      included, while § 1.2 named neither the list nor that field.
    #      `phases/plan.md` cited § 1.2 for it too, and 72 of this repo's own
    #      tickets carry it. The citation checker could not see this: it proves
    #      a cited section EXISTS, never that it says the thing being cited.
    _rfc_p2 = _tools_parent / "saipen" / "RFC.md"
    if _rfc_p2.is_file():
        _rfc_t = _read_rfc(_rfc_p2)
        _i = _rfc_t.find("### 1.10")
        _j = _rfc_t.find("### 1.11", _i)
        if _i < 0 or _j < 0:
            fail("cross-doc drift [commands] -- RFC § 1.10 not found; the "
                 "command surface cannot be compared, and a missing anchor is "
                 "a failure rather than a skip")
            drift_ok = False
        else:
            _doc_cmds = set(re.findall(r"`saipen ([a-z]+)", _rfc_t[_i:_j]))
            if _doc_cmds != set(SAIPEN_COMMANDS):
                fail(f"cross-doc drift [commands] -- RFC § 1.10 names "
                     f"{sorted(_doc_cmds)} but validate.py accepts "
                     f"{sorted(SAIPEN_COMMANDS)}")
                drift_ok = False

            # T-571: `saipen crew` carries exactly one execution meaning. The
            # future concurrent design has a distinct command name and must
            # never reuse `saipen crew`; the sequential row must state that it
            # is never the concurrent design, and the gated backlog must cite
            # the decision and carry the distinct command name. A command that
            # reads as both "runs nothing in parallel" and "multi-agent
            # concurrency" is precisely the ambiguity a weak model resolves
            # wrongly while believing it followed SAIPEN.
            _crew_row_m = re.search(r"`saipen crew` -- walk[^\n]*",
                                    _rfc_t[_i:_j])
            if _crew_row_m is None:
                fail("cross-doc drift [crew-naming] -- RFC § 1.10's `saipen "
                     "crew` row is missing; the sequential circuit must be "
                     "defined (T-571)")
                drift_ok = False
            else:
                _crew_row = _crew_row_m.group(0)
                if ("exactly one execution meaning" not in _crew_row
                        or "never the concurrent" not in _crew_row):
                    fail("cross-doc drift [crew-naming] -- RFC § 1.10's "
                         "`saipen crew` row does not state its single "
                         "execution meaning (strictly sequential, never the "
                         "concurrent multi-agent design) -- one command cannot "
                         "carry two execution meanings (T-571)")
                    drift_ok = False
            _crew_backlog = _tools_parent / ".saipen" / "KNOWLEDGE" / \
                "crew-v8-backlog.md"
            if _crew_backlog.is_file():
                _cb = _crew_backlog.read_text(encoding="utf-8-sig")
                if "T-571" not in _cb:
                    fail("cross-doc drift [crew-naming] -- the v8 Concurrent "
                         "Mode backlog does not cite T-571's naming decision; "
                         "the concurrent design must not silently reuse "
                         "`saipen crew`")
                    drift_ok = False
                if "`saipen concurrent`" not in _cb:
                    fail("cross-doc drift [crew-naming] -- the v8 Concurrent "
                         "Mode backlog must carry the distinct command name "
                         "`saipen concurrent`; one command cannot carry two "
                         "execution meanings")
                    drift_ok = False
                if "Crew Mode" in _cb:
                    fail("cross-doc drift [crew-naming] -- the v8 Concurrent "
                         "Mode backlog reintroduces the pre-T-571 name "
                         "'Crew Mode' for the concurrent design; the decision "
                         "renamed it Concurrent Mode with command "
                         "`saipen concurrent`")
                    drift_ok = False
            # Live BOARD tickets may not resurrect the decided-against name for
            # the concurrent design either (T-571's own historical DONE line is
            # exempt -- it describes the conflict it resolved).
            _live_crew = "\n".join(
                board_lines[t["line_no"] - 1] for t in tickets.values()
                if t["section"] in ("## DOING", "## TODO", "## BLOCKED"))
            if "Crew Mode" in _live_crew:
                fail("cross-doc drift [crew-naming] -- a live BOARD ticket "
                     "reintroduces the pre-T-571 name 'Crew Mode' for the "
                     "concurrent design; T-571 renamed it Concurrent Mode with "
                     "command `saipen concurrent`")
                drift_ok = False

            # The shortcut table's right-hand column is a promise that each
            # shortcut lands on a command this surface defines. Nothing read
            # that column until v7.148.0, and two rows had stopped being true:
            # `hh` pointed at HUNT, a PHASE with no command behind it, and `cc`
            # pointed at a "Full pipeline" that was not a command either -- and
            # quietly added commit+push to the most-typed key. The check reads
            # the table itself rather than any prose about it, so the rule and
            # the thing it governs cannot drift apart.
            # A command named after a phase switches into it, and § 1.10 makes
            # every such command checkpoint a claimed `## DOING` ticket first.
            # That list was hand-kept: `saipen hunt` joined the surface in
            # v7.148.0 and nobody added it, so for two releases `hh` was the
            # one phase switch that could leave half-finished work unwritten.
            # Derive the membership from the phase enum instead of trusting a
            # second copy -- a command whose name IS a phase belongs there.
            # `init` is the one exclusion and it is structural, not a taste
            # call: it creates `.saipen/` and there is no board to hold a
            # claimed ticket at the moment it runs.
            _switch_m = re.search(
                r"Any recognized phase-switching command \(([^)]*)\)",
                _rfc_t[_i:_j])
            if not _switch_m:
                fail("cross-doc drift [phase-switching] -- RFC § 1.10's "
                     "phase-switching sentence not found; the list that makes "
                     "these commands checkpoint cannot be compared")
                drift_ok = False
            else:
                _listed = set(re.findall(r"`([a-z]+)`", _switch_m.group(1)))
                # Resolved against the validator's own tree, not the cwd: a
                # fixture sandbox is a project root with a `.saipen/` and no
                # protocol docs, and a cwd-relative lookup made `_expected`
                # empty there and failed four conformant fixtures.
                _phases_dir = _tools_parent / "saipen" / "phases"
                _expected = {c for c in SAIPEN_COMMANDS
                             if (_phases_dir / f"{c}.md").is_file()} - {"init"}
                if _listed != _expected:
                    fail(f"cross-doc drift [phase-switching] -- RFC § 1.10 "
                         f"lists {sorted(_listed)} as phase-switching but the "
                         f"commands named after a phase are "
                         f"{sorted(_expected)}; a command that switches phase "
                         f"without this duty can drop a claimed ticket's "
                         f"checkpoint")
                    drift_ok = False

            _shortcut_rows = re.findall(
                r"^\| `([a-z]{2,3})` \| ([^|]+) \|",
                _rfc_t[_i:_j], re.MULTILINE)
            _shortcut_full_rows = re.findall(
                r"^\| `([a-z]{2,3})` \| ([^|]+) \| ([^|]*)\|",
                _rfc_t[_i:_j], re.MULTILINE)
            # `saipen plan` is two commands wearing one name, and only the
            # bare one was ever written down. A weak model reading the
            # Proposal-Mode paragraph answers `dd <text>` with four
            # inventions of its own -- a specific instruction silently
            # replaced by a menu. Both documents that describe the command
            # must carry the with-text half, and it must say where those
            # tickets land, because "priority" here means board position.
            _plan_doc = _tools_parent / "saipen" / "phases" / "plan.md"
            for _doc, _body in (("phases/plan.md", _plan_doc.read_text(encoding="utf-8-sig") if _plan_doc.is_file() else ""),):
                if not _body:
                    continue
                if "FRONT of `## TODO`" not in _body:
                    fail(f"cross-doc drift [plan-forms] -- {_doc} does not say "
                         f"that `saipen plan <text>` puts the user's own items "
                         f"at the front of `## TODO`. Board order is priority "
                         f"(§ 1.6), so a request filed behind existing work is "
                         f"a request denied politely")
                    drift_ok = False

            # Proposal Mode's halt had no legal expression. Step 4 ordered
            # `phase: DONE` plus a halt, forbade a `WAIT:` prefix as a § 1.2
            # violation, and forbade proceeding -- leaving only the four
            # prefixes that each mean "do this now", so the halt could be
            # written down only as an action the agent was forbidden to
            # perform, and a cold agent reading `PHASE SCOUT T-###` executes
            # it. The prohibition was also simply wrong: § 1.2 restricts
            # `WAIT:` to three fixed forms at `DONE` only when `## TODO` is
            # EMPTY, and Proposal Mode has just filled it.
            _plan_t = (_plan_doc.read_text(encoding="utf-8-sig")
                       if _plan_doc.is_file() else "")
            if _plan_t:
                # Pin the SEMANTICS, not the sentence. `validate.py` matches
                # the category token `user brake` and nothing beyond it, and
                # § 1.11's UNBLOCK reads the `WAIT:` prefix -- so mandating a
                # full sentence would make normative a string no machine
                # reads, guarded by a marker check and a red control that
                # both descend from that same sentence. The reason clause is
                # for the human. `tests/scenarios/proposal-mode-halt/` is the
                # behavioral half: it puts a real project in the state and
                # asserts the validator accepts it.
                _halt = ("category is `user brake`" in _plan_t
                         and "There is no parked `PHASE`" in _plan_t)
                _old = "Do NOT use a `WAIT:` prefix" in _plan_t
                if not _halt or _old:
                    fail("cross-doc drift [proposal-halt] -- phases/plan.md "
                         "step 4 must name the one legal Proposal-Mode halt, a "
                         "`WAIT: user brake` naming the choice, and must not "
                         "forbid a `WAIT:` there. § 1.2's three-form whitelist "
                         "governs `DONE` with an EMPTY `## TODO`, which is not "
                         "the state Proposal Mode produces; without the "
                         "wording the halt is expressible only as one of the "
                         "four prefixes that mean act now, which a cold agent "
                         "then acts on")
                    drift_ok = False

            _bad_routes = []
            for _sc, _route in _shortcut_rows:
                _named = set(re.findall(r"`saipen ([a-z]+)", _route))
                if not _named:
                    _bad_routes.append(f"`{_sc}` -> {_route.strip()!r} names no "
                                       f"`saipen <command>` at all")
                elif not _named <= set(SAIPEN_COMMANDS):
                    _bad_routes.append(
                        f"`{_sc}` -> {sorted(_named - set(SAIPEN_COMMANDS))}")
            if _bad_routes:
                fail("cross-doc drift [shortcuts] -- RFC § 1.10 shortcut(s) do "
                     "not resolve to a command the same section defines: "
                     + "; ".join(_bad_routes))
                drift_ok = False

            _actual_routes = {shortcut: route.strip()
                              for shortcut, route in _shortcut_rows}
            if (len(_actual_routes) != len(_shortcut_rows)
                    or _actual_routes != EXPECTED_SHORTCUT_ROUTES):
                _route_diffs = []
                for _shortcut in sorted(set(_actual_routes)
                                        | set(EXPECTED_SHORTCUT_ROUTES)):
                    _actual = _actual_routes.get(_shortcut, "<missing>")
                    _expected = EXPECTED_SHORTCUT_ROUTES.get(
                        _shortcut, "<undeclared>")
                    if _actual != _expected:
                        _route_diffs.append(
                            f"`{_shortcut}` is {_actual!r}, expected "
                            f"{_expected!r}")
                fail("cross-doc drift [shortcut-routes] -- assigned "
                     "destination changed: " + "; ".join(_route_diffs))
                drift_ok = False

            _shortcut_section = _rfc_t[_i:_j]
            if ("**Length has no global meaning.**" not in _shortcut_section
                    or "do not invent an undeclared repeated form"
                    not in _shortcut_section
                    or "Doubled is safe, tripled reaches a remote"
                    in _shortcut_section
                    or "never a greeting" not in _shortcut_section
                    or "MUST execute the exact row" not in _shortcut_section):
                fail("cross-doc drift [shortcut-rationale] -- length must "
                     "have no global cost meaning, undeclared repeated forms "
                     "must not be invented, and the repeated-letter paragraph "
                     "must say a shortcut is a command, never a greeting -- "
                     "receiving one means executing the exact row (or its "
                     "exact no-op), never answering with chat")
                drift_ok = False

            # A row's Notes column describes its destination, bare form
            # included. `cc`'s said "trigger goal mode" while § 1.10 forbids
            # bare `saipen goal` from setting the flag, touching a counter or
            # planning -- it replies with the usage line. The most-used key
            # promised an outcome the row cannot produce.
            #
            # Derived from the ROUTE, never from a key name. Fixing `cc` by
            # name closed the defect on one instance and left its twin: `gg`
            # routes to the same `saipen goal` and went on reading "Goal Mode
            # pivot / re-authorization" one row above the row that had just
            # been repaired -- a bare pivot the destination forbids, and a
            # re-authorization that only happens with § 2.4's valve tripped.
            # Keying on the route means a third row assigned to `saipen goal`
            # inherits the requirement instead of quietly escaping it.
            _goal_notes_bad = []
            for _sc, _route, _notes in _shortcut_full_rows:
                if "`saipen goal`" not in _route:
                    continue
                if "pivot needs text" not in _notes or "Bare" not in _notes:
                    _goal_notes_bad.append(f"`{_sc}`")
            if _goal_notes_bad or "trigger goal mode" in _shortcut_section:
                fail("cross-doc drift [shortcut-notes] -- every row routing to "
                     "`saipen goal` must say the pivot needs text and what its "
                     "BARE form does, which is a resume or the § 1.10 usage "
                     "line, never a pivot. Bare `saipen goal` MUST NOT set "
                     "goal_mode, write a counter or plan, so a Notes column "
                     "promising a bare pivot describes a command that does not "
                     "exist. Offending row(s): "
                     + (", ".join(_goal_notes_bad) or "none named; the "
                        "superseded literal is back in the section"))
                drift_ok = False

            _shortcut_notes = {shortcut: notes for shortcut, _, notes
                               in _shortcut_full_rows}
            _cc_required = (
                "enters convergence from `normal`",
                "resumes `execution_intent: goal`",
                "never asks for an objective",
                "`cc <args>` is not a goal",
            )
            _gg_required = (
                "NEW GOAL ONLY", "`gg <objective>`",
                "never a continuation alias",
            )
            _shortcut_semantic_missing = [
                f"cc:{fragment}" for fragment in _cc_required
                if fragment not in _shortcut_notes.get("cc", "")
            ] + [
                f"gg:{fragment}" for fragment in _gg_required
                if fragment not in _shortcut_notes.get("gg", "")
            ]
            if _shortcut_semantic_missing:
                fail("cross-doc drift [shortcut-semantics] -- "
                     + "; ".join(_shortcut_semantic_missing))
                drift_ok = False

            # § 1.10's `saipen stop` paragraph and § 2.4 Entry both describe
            # what a bare `saipen goal` does to the safety-valve counters, and
            # they gave opposite answers: § 1.10 said the reset is
            # unconditional -- while citing § 2.4 Entry, which makes it
            # conditional on the valve having tripped. Either branch is a real
            # failure. Unconditional hands a fresh 3-wave/20-ticket budget to
            # anyone who types the most convenient key mid-run (E-1468);
            # reading it the other way round would leave a tripped valve with
            # no way to clear. § 2.4 owns the rule and § 1.10 defers to it.
            if ("only when they are at or over the caps"
                    not in _rfc_t[_i:_j]
                    or "deliberately does NOT preserve the counters"
                    in _rfc_t[_i:_j]):
                fail("cross-doc drift [goal-counter-reset] -- RFC § 1.10's "
                     "`saipen stop` paragraph must defer to § 2.4 Entry and "
                     "say bare `saipen goal` resets goal_waves/goal_tickets "
                     "ONLY when they are at or over the caps. Asserting an "
                     "unconditional reset re-grants a full safety-valve "
                     "budget to a run nobody re-authorized (§ 2.4 Entry, "
                     "E-1468)")
                drift_ok = False

            _package_docs = {
                "RFC.md": _rfc_t,
                "phases/prepare.md": (_tools_parent / "saipen" / "phases"
                                      / "prepare.md").read_text(
                                          encoding="utf-8-sig"),
                "phases/translate.md": (_tools_parent / "saipen" / "phases"
                                        / "translate.md").read_text(
                                            encoding="utf-8-sig"),
                "extensions/subs/PROTOCOL.md": (
                    _tools_parent / "extensions" / "subs" / "PROTOCOL.md"
                ).read_text(encoding="utf-8-sig"),
            }
            _prepare_contract = re.search(
                r"Every collectable handoff MUST include these fields: "
                r"([^\n]+)", _package_docs["phases/prepare.md"])
            _prepare_fields = (set(re.findall(r"`([a-z_]+)`",
                                              _prepare_contract.group(1)))
                               if _prepare_contract else set())
            if _prepare_fields != PACKAGE_HANDOFF_FIELDS:
                fail("cross-doc drift [package-handoffs] -- PREPARE fields "
                     f"are {sorted(_prepare_fields)}, expected "
                     f"{sorted(PACKAGE_HANDOFF_FIELDS)}")
                drift_ok = False
            _outbox_schema = json.loads((
                _tools_parent / "extensions" / "schemas"
                / "outbox.schema.json").read_text(encoding="utf-8-sig"))
            _schema_package_fields = set(
                _outbox_schema.get("items", {}).get("properties", {}))
            _schema_missing = PACKAGE_HANDOFF_FIELDS - _schema_package_fields
            if _schema_missing:
                fail("cross-doc drift [package-handoffs] -- OUTBOX schema "
                     "misses complete-package field(s): "
                     + ", ".join(sorted(_schema_missing)))
                drift_ok = False
            _package_markers = {
                "RFC.md": ("Not ready: run ee first.",
                           "Not ready: run qq first.",
                           "No main-project file, checkpoint, Git ref, or "
                           "remote may change on that refusal."),
                "phases/prepare.md": ("saipen prepare saitranslate",
                                      "saipen prepare saiwiki",
                                      "MUST NOT integrate the payload"),
                "phases/translate.md": ("producer: saitranslate",
                                        "status: ready",
                                        "No ready handoff means no main "
                                        "write."),
                "extensions/subs/PROTOCOL.md": (
                    "Targeted complete-package path.",
                    "Not ready: run qq first.",
                    "The doubled `qq` never integrates, commits, tags, or "
                    "pushes."),
            }
            for _doc_name, _markers in _package_markers.items():
                _missing_markers = [marker for marker in _markers
                                    if marker not in _package_docs[_doc_name]]
                if _missing_markers:
                    fail("cross-doc drift [package-handoffs] -- "
                         f"{_doc_name} misses "
                         + ", ".join(repr(m) for m in _missing_markers))
                    drift_ok = False

            # Skill platforms decide whether to load SAIPEN from SKILL.md's
            # frontmatter before the RFC is available. A shortcut present
            # only in the RFC works by accident when `.saipen/` forces the
            # skill to load, then silently misses everywhere else. Derive the
            # Latin rows and their Cyrillic-confusable twins from the table.
            _skill_p = _tools_parent / "saipen" / "SKILL.md"
            if not _skill_p.is_file():
                fail("cross-doc drift [skill-triggers] -- saipen/SKILL.md is "
                     "missing; shortcut activation metadata cannot be checked")
                drift_ok = False
            else:
                _skill_t = _skill_p.read_text(encoding="utf-8-sig")
                _front = _skill_t.split("---", 2)
                _trigger_m = (re.search(r"shortcuts\s*\(([^)]*)\)", _front[1],
                                        re.DOTALL)
                              if len(_front) == 3 else None)
                if not _trigger_m:
                    fail("cross-doc drift [skill-triggers] -- SKILL.md "
                         "frontmatter has no `shortcuts (...)` trigger list")
                    drift_ok = False
                else:
                    _advertised = set(re.findall(
                        r"(?<!\w)(\w{2,3})(?!\w)", _trigger_m.group(1),
                        re.IGNORECASE))
                    _latin = {shortcut for shortcut, _ in _shortcut_rows}
                    _to_cyr = {"a": "\u0430", "e": "\u0435",
                               "o": "\u043e", "p": "\u0440",
                               "c": "\u0441", "y": "\u0443",
                               "x": "\u0445"}
                    _twins = {"".join(_to_cyr[ch] for ch in shortcut)
                              for shortcut in _latin
                              if all(ch in _to_cyr for ch in shortcut)}
                    _expected_triggers = _latin | _twins
                    _missing = sorted(_expected_triggers - _advertised)
                    _unexpected = sorted(_advertised - _expected_triggers)
                    if _missing:
                        fail("cross-doc drift [skill-triggers] -- SKILL.md "
                             "metadata misses RFC shortcut trigger(s): "
                             + ", ".join(_missing))
                        drift_ok = False
                    if _unexpected:
                        fail("cross-doc drift [skill-triggers] -- SKILL.md "
                             "metadata has non-RFC shortcut trigger(s): "
                             + ", ".join(_unexpected))
                        drift_ok = False

        _m = re.search(r"ticket-field list is closed.*?(?=\n- |\n#)",
                       _rfc_t, re.DOTALL)
        if not _m:
            fail("cross-doc drift [ticket-fields] -- RFC § 1.2 no longer "
                 "states the closed ticket-field list. It went unstated until "
                 "v7.122.0 while the tool rejected everything outside it and "
                 "cited § 1.2 for the rule")
            drift_ok = False
        else:
            _doc_fields = set(re.findall(r"`([a-z_]+):`", _m.group(0)))
            if _doc_fields != set(KNOWN_FIELDS):
                fail(f"cross-doc drift [ticket-fields] -- RFC § 1.2 lists "
                     f"{sorted(_doc_fields)} but validate.py accepts "
                     f"{sorted(KNOWN_FIELDS)}")
                drift_ok = False

    # 13l. Keep the one known Windows device-name artifact out of Git. This is
    #      an exact config identity contract: the behavioral half lives in
    #      audit_checks.py, which creates a real entry and copies the tree.
    #      A Git query cannot be used here because mutation audits deliberately
    #      copy the repository without `.git/` before running this validator.
    # The `.gitignore` that matters belongs to the PROJECT being validated,
    # not to the home the tool ships from. Reading it from `_tools_parent`
    # made an installed validator report "root `nul` is not excluded" about a
    # repository whose .gitignore excludes it on line 7 -- absence in the
    # agent home misread as a violation in the project. T-413's "resolve
    # paths one way only", in one line.
    _ignore_p = Path(".gitignore")
    _ignore_lines = (set(_ignore_p.read_text(encoding="utf-8-sig").splitlines())
                     if _ignore_p.is_file() else set())
    if IS_SAIPEN_HOME and "/nul" not in _ignore_lines:
        fail("cross-doc drift [root-device-ignore] -- root `nul` is not "
             "excluded by .gitignore; a real Windows device-name entry can "
             "pollute status and be staged by broad add commands")

    # 13m. No gitlink inside `.saipen/`. A subSaipen's kitchen is a sandbox
    #      and it may legitimately hold a CLONE of something -- saiwiki keeps
    #      the GitHub wiki there. `git add -A` turns a nested repository into a
    #      mode-160000 entry: a pointer to a commit no clone of this repository
    #      can fetch, carrying none of the content, and git says so in a hint
    #      that scrolls past in a wall of CRLF warnings. It landed in v7.122.0
    #      exactly that way, in the commit that shipped this file's previous
    #      check. Ignoring the path is the fix; noticing is what this is for.
    _rc, _out = _git("ls-files", "-s", ".saipen")
    if _rc == 0:
        _links = [ln.split("	", 1)[1] for ln in _out.splitlines()
                  if ln.startswith("160000")]
        if _links:
            fail(f"gitlink(s) committed inside .saipen/: {', '.join(_links)} "
                 f"-- a nested repository recorded as a bare commit pointer "
                 f"nobody can fetch, with none of its content. Add the path "
                 f"to .gitignore and `git rm --cached` it")

    # 13n. Every CONFORMANCE row's stated enforcement still exists.
    #      This table only ever grew -- 144 rows, not one retirement -- and
    #      nothing made a rule LOUD when the thing enforcing it went away. A
    #      row naming a deleted tool, a renamed CI step or a fixture that no
    #      longer exists reads exactly like a row that is enforced, which is
    #      the difference between a guarantee and a decoration. Row 78 sat
    #      wrong for releases and was only corrected because someone measured
    #      it by hand.
    #
    #      This is a syntax/identity contract, not a behavior claim: it proves
    #      that a row's named tool, fixture, or workflow step still exists.
    #      This is the mechanical half of retiring a rule: it cannot decide
    #      that a rule is obsolete, but it can refuse to let one keep claiming
    #      an enforcement that is gone. Then the choice -- restore it or retire
    #      the row -- has to be made by a person, out loud.
    _conf_p = _tools_parent / "saipen" / "CONFORMANCE.md"
    _wf_p = _tools_parent / ".github" / "workflows" / "validate.yml"
    if IS_SAIPEN_HOME and _conf_p.is_file():
        _conf_t = _conf_p.read_text(encoding="utf-8-sig")
        _wf_t = _wf_p.read_text(encoding="utf-8-sig") if _wf_p.is_file() else ""
        _step_names = set(re.findall(r"^\s*- name: (.+)$", _wf_t, re.MULTILINE))
        _fixtures = {d.name for d in (_tools_parent / "tests" / "scenarios").iterdir()
                     if d.is_dir()} if (_tools_parent / "tests" / "scenarios").is_dir() else set()
        _gone = []
        for _rid, _body, _how in re.findall(r"^\| (\d+) \| (.*?) \| (.*?) \|\s*$",
                                            _conf_t, re.MULTILINE):
            for _tool in set(re.findall(r"`(tools/[a-z_]+\.py|tests/validate\.(?:sh|ps1))`",
                                        _how)):
                if not (_tools_parent / _tool).is_file():
                    _gone.append(f"row {_rid} names {_tool}, which does not exist")
            for _step in set(re.findall(r"`([^`]+)` CI step", _how)):
                if _step_names and not any(_step.lower() in _s.lower()
                                           for _s in _step_names):
                    _gone.append(f"row {_rid} names a `{_step}` CI step, which "
                                 f"no workflow defines")
            for _fx in set(re.findall(r"`([a-z0-9]+(?:-[a-z0-9]+){1,})`", _body + " " + _how)):
                if _fixtures and _fx in _fixtures:
                    continue
                # Only names that LOOK like fixtures and match none: a
                # hyphenated lowercase token that is also not a mode, a WAIT
                # category or a filename. Anything else is ordinary prose.
                if _fx in ("read-only", "no-publish", "manual-verify",
                           "destructive-op", "first-publish", "user-brake",
                           "safety-valve", "utf-8-sig", "unknown-field",
                           "no-git", "fetch-depth", "pre-commit",
                           "utf-16-le", "utf-16-be", "utf-8"):
                    continue
                if "/" in _fx or "." in _fx:
                    continue
                if _fixtures and _fx.count("-") >= 2:
                    _gone.append(f"row {_rid} names fixture `{_fx}`, which "
                                 f"tests/scenarios/ does not contain")
        if _gone:
            fail(f"CONFORMANCE enforcement gone -- {len(_gone)} row(s) claim "
                 f"something that no longer exists: {'; '.join(sorted(set(_gone))[:4])}"
                 f"{' ...' if len(set(_gone)) > 4 else ''}. Restore it or retire "
                 f"the row; a rule enforced by nothing is a decoration")

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

        # 14. HABITS.md citations must be real.
    _habits_p = _tools_parent / "saipen" / "HABITS.md"
    _rfc_p = _tools_parent / "saipen" / "RFC.md"
    if _rfc_p.is_file() and _habits_p.is_file():
        _habits_b = _habits_p.read_text(encoding="utf-8-sig")
        _rfc_b = _read_rfc(_rfc_p)
        
        # Collect all RFC sections
        _rfc_sections = set()
        for _ln in _rfc_b.splitlines():
            _h = re.match(r"^#{2,4}\s*§?\s*(\d+\.\d+)\s", _ln)
            if _h:
                _rfc_sections.add(_h.group(1))
                
        # Check citations
        for _cit in re.finditer(r"RFC\.md\s*§\s*(\d+\.\d+)", _habits_b):
            if _cit.group(1) not in _rfc_sections:
                fail(f"HABITS.md cites non-existent RFC section {_cit.group(1)}")
                drift_ok = False
                
        for _tool in re.finditer(r"tools/[A-Za-z0-9_]+\.py", _habits_b):
            _tool_p = _tools_parent / _tool.group(0)
            if not _tool_p.is_file():
                fail(f"HABITS.md cites non-existent tool {_tool.group(0)}")
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
        _rfc_b = _read_rfc(_rfc_p)
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
        # T-404: an adapter that files STYLE.md as a rule-question escalation
        # ("loads alongside it") is the same lazy hole BOOT.md line 101 opened
        # -- a DeepSeek agent booting on its own adapter is told STYLE.md only
        # loads when a rule question comes up, and never opens it.
        _lazy_style = [a.name for a in _adapters
                       if "loads alongside" in a.read_text(encoding="utf-8-sig")]
        if _lazy_style:
            fail(f"cross-doc drift [adapters] -- {', '.join(_lazy_style)} "
                 f"file(s) STYLE.md as a rule-question escalation "
                 f"('loads alongside it'); STYLE.md is a boot-read, applied "
                 f"before any output")
            drift_ok = False

    if drift_ok and not failures:
        ok("cross-doc sets agree (required fields, phase enum, from-any-phase, "
           "read-only bans, next_action prefixes, WAIT categories, command "
           "surface, ticket fields; no stale re-listing in shipped docs)")


# ------------------------------------------------------------------- summary

warn_total = sum(len(msgs) for msgs in warnings.values())
for category, msgs in warnings.items():
    for msg in msgs[:2]:
        # The category is printed, not just carried. It used to appear only in
        # the "... and N more" roll-up, so every individual warning was
        # anonymous -- and matching on the invisible key is a trap
        # KNOWLEDGE/traps.md has recorded since the warn-coverage audit scored
        # 8 of 8 categories unreachable. It was recorded and then walked into
        # five more times, including twice while writing checks in this
        # session. A trap that keeps being hit after being written down is not
        # a discipline problem; it is a missing affordance. Now the key is on
        # screen, so grepping for it works and the trap has nothing to catch.
        print(color("33", f"WARN [{category}]: {msg}"))
    if len(msgs) > 2:
        print(color("33", f"WARN [{category}]: ... and {len(msgs) - 2} more "
                    f"like the above"))

if STRICT:
    for msgs in warnings.values():
        failures.extend(msgs)

if failures:
    print(color("31", f"Validation FAILED: {len(failures)} problem(s)"
                + (f", {warn_total} warning(s)" if warn_total and not STRICT else "")))
    sys.exit(1)
print(color("32", "Validation complete. Agent is conformant."
            + (f" ({warn_total} warning(s))" if warn_total else "")))
