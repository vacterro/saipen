"""Bounded, protocol-aware collection of SAIPEN audit evidence.

WHY THIS EXISTS
---------------
AUDAPACK's Git inventory is built from ``git ls-files`` plus
``git ls-files --others --exclude-standard``. Git-ignored material is absent
by construction -- which is correct for caches and build output, and wrong
for protocol memory. A project carrying ``.saipen/*`` in ``.gitignore`` hid
its entire canonical lifecycle from the inventory, so a package could ship
``IDENTITY.md`` plus one stale active intake receipt and nothing able to
contradict it, while the archive manifest still reported
``accounting_reconciled: true`` -- because the missing files were never
DISCOVERED, so the invariant ``discovered == included + excluded + failed``
held over material nobody had looked at.

The fix is NOT to expose ``.saipen`` to Git. Publication visibility and
audit evidence are separate concerns, and widening ``.gitignore`` would put
private working memory one ``git add -A`` away from a public commit.

Instead SAIPEN declares its own evidence in ``.saipen/MANIFEST.json``
(``saipen audit manifest --write``) and this module collects exactly what
that contract names. Bounded by construction:

* one stat to find the manifest;
* only directories the manifest names are walked, each with its own cap;
* symlinked directories are never followed, so no path escapes the project;
* paths the contract marks non-exportable are refused even if a directory
  rule would otherwise sweep them.

No unrestricted walk of ignored trees is introduced, so packing cost for
projects without SAIPEN is unchanged.

WHAT DECIDES THE VERDICT
------------------------
Collection DISCOVERS evidence; the verdict is about the ARCHIVE. `evaluate`
therefore takes the set of paths that actually survived into the package, and
a snapshot is COMPLETE only when every artifact the contract requires is in
that set:

* the mandatory documents (STATE/BOARD/LOG/IDENTITY);
* conditional material the contract makes required BECAUSE IT EXISTS
  (`.saipen/logs/**` and friends) -- discovery is not inclusion, so an
  explicit exclude, a hard-safety rule or a policy omission downstream of
  collection all count as the evidence being absent;
* the contract document itself, so the verdict stays re-derivable from the
  archive alone.

Optional material that is omitted is REPORTED and never degrades authority,
because the contract already declared its absence honest. A containment cap
hit on conditional material does degrade authority: that is required evidence
left behind rather than a policy choice about optional bulk.

CITED EVIDENCE (SRC-054)
------------------------
Directory rules only find what the contract names, so a surface the contract
forgot was never discovered and its loss could never be counted: Problip's
archive read COMPLETE with 142 of 142 evidence files while the PERF-001 proof
its LOG and archived coverage cited was not in it. Collection therefore also
reads the closure records the contract declares as citation carriers and
treats every cited path as required evidence -- collected when it exists,
reported as omitted when the archive lacks it or the disk never had it.

A citation is the project-relative token ``<memory_root>/<surface>/<path>``
inside a declared carrier. A token that continues a longer path (another
project's absolute path) is not one, and source bodies and derived contracts
are never carriers, because they quote the user. A citation can only ADD a
requirement, so stray prose fails closed; the remedy for a citation of proof
that will never exist is a file at that path saying so.

A contract that predates the ``references`` block gets the rules SAIPEN
publishes since SRC-054 (``rules_source: consumer_default``); otherwise every
project whose installed protocol has not regenerated its manifest yet would
keep reproducing the false COMPLETE.

CONTRACT VERSIONS (SUPPORTED_CONTRACT_VERSIONS)
----------------------------------------------
The protocol owns the contract and bumps ``contract_version`` when its SHAPE
changes. This consumer therefore keeps an explicit supported set and one
parser per version (``parse_contract_v1`` / ``parse_contract_v2``), rather than
a single parser with a magic constant: a version it does not implement is
refused -- by the contract's own ``compatibility`` policy -- instead of being
reinterpreted through the newest shape it happens to know.

What v2 added over v1 was taken from the real generator's output, not
inferred: the contract/generator version, and ``quarantine/`` in
``evidence.non_exportable`` (``V2_NON_EXPORTABLE_BASELINE``). Everything else
-- ``required``, ``compatibility``, ``references``, the mandatory-file objects,
the bounded conditional/optional directory rules -- is identical in both, so
both versions are read by shared code and differ only where the contract
differs. A document that declares one version is never read through the
other's rules.

FORWARD COMPATIBILITY (MILESTONE K)
-----------------------------------
A newer-than-implemented contract is no longer hard-failed merely for being
numerically newer. ``check_capabilities`` probes whether every capability this
consumer depends on for safe inventory and packaging is structurally present:
project identity, include/exclude rules, credential protection, inventory root,
evidence requirements, and integrity semantics. A document that passes is
admitted as ``COMPATIBLE_DEGRADED`` and read through the newest implemented
parser (additive unknown metadata is tolerated and preserved, never rewritten).
Only a newer contract that DROPS or RESHAPES a required capability is refused
as ``INCOMPATIBLE_UNSAFE``, with the exact missing capability reported.

A REFUSED version is a CONSUMER defect, not a project defect: the operator's
project is fine and ``saipen audit manifest --write`` would only rewrite the
same newer contract. ``contract_unknown_detail`` is the single wording for
older-than-implemented refusals; ``check_capabilities_detail`` covers the
forward-compatibility cases. Callers (the packing gate, the operator message)
reuse those rather than inventing repair advice that does not repair anything.
"""

from __future__ import annotations

import json
import os
import re
import stat as stat_module
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

#: Where SAIPEN publishes its contract, relative to the project root.
MANIFEST_REL = ".saipen/MANIFEST.json"

#: Protocol memory root. Its mere presence is what makes a project "SAIPEN".
MEMORY_ROOT = ".saipen"

#: The contract shapes this consumer implements, as an EXPLICIT set. A manifest
#: declaring a version outside it is refused rather than reinterpreted (its own
#: `compatibility` block asks for exactly that, and `contract_unknown_detail`
#: is the one place the refusal is worded) -- UNLESS the forward-compatibility
#: probe admits it in a degraded but safe state.
#:
#: Ownership stays visible per version: `_CONTRACT_PARSERS` dispatches to
#: `parse_contract_v1` / `parse_contract_v2`, so learning a new shape can never
#: silently re-read an old document through the newest parser.
SUPPORTED_CONTRACT_VERSIONS = (1, 2)

#: The newest implemented contract. Its own name because callers and tests ask
#: "what is current?" far more often than "what is the whole set?".
SUPPORTED_CONTRACT_VERSION = max(SUPPORTED_CONTRACT_VERSIONS)


class ManifestAdmission:
    """Outcome of capability-based contract admission.

    The forward-compatibility probe classifies a newer-than-implemented contract
    into exactly one of three mutually exclusive states:

    NATIVE: this consumer implements the contract's shape directly.
    COMPATIBLE_DEGRADED: the contract is newer than implemented, but every
        capability AUDAPACK depends on for safe inventory and packaging is
        structurally present and understood, so the document is read through
        the newest implemented parser that still applies. Unknown additive
        metadata is tolerated and preserved rather than rewritten.
    INCOMPATIBLE_UNSAFE: the newer contract contains semantics this consumer
        cannot safely reconstruct (exclusion rules it did not author,
        credential-protection changes, identity shifts, integrity alterations)
        -- hard-fail.
    """

    NATIVE = "NATIVE"
    COMPATIBLE_DEGRADED = "COMPATIBLE_DEGRADED"
    INCOMPATIBLE_UNSAFE = "INCOMPATIBLE_UNSAFE"


#: Capabilities this consumer depends on for safe inventory and packaging.
#: A newer contract that still declares all of these is admitted in a degraded
#: state; a newer contract that MISSES one (or moves it to a shape this
#: consumer cannot interpret) is INCOMPATIBLE_UNSAFE. These are the minimum
#: that must remain derivable without trusting unknown semantics.
REQUIRED_CAPABILITIES = (
    "project_identity_understood",
    "include_exclude_rules_understood",
    "credential_protection_rules_understood",
    "inventory_root_understood",
    "evidence_requirements_understood",
    "integrity_semantics_understood",
)

#: Exclusions contract v2 ADDED to `evidence.non_exportable`, established from
#: what the real generator writes rather than inferred from prose: the two
#: published shapes differ by the contract/generator version and by
#: `quarantine/` alone. A v2 manifest is held to these IN ADDITION to whatever
#: it declares, so a drifted or hand-edited v2 document cannot export a surface
#: its own version bans. Deliberately NOT applied to v1 -- a v1 document is
#: read exactly as it declares itself (see `parse_contract_v1`).
V2_NON_EXPORTABLE_BASELINE = ("quarantine",)

#: The export precedence this consumer knows how to apply, in order, exactly as
#: SAIPEN's generator publishes it in `evidence.precedence` (contract v3,
#: T-1452). Interpreting this ONE known additive declaration is not a claim of
#: native v3 support: a v3 document is still admitted COMPATIBLE_DEGRADED.
EXPORT_PRECEDENCE = (
    "transient_segment_or_filename",
    "nested_instance_state",
    "declared_durable_path",
    "non_exportable_prefix",
    "directory_rule",
)

#: Bound on each declared structural-class list; a longer list is malformed.
EXPORT_CLASS_LIST_LIMIT = 256

#: Export-decision rule names (`export_decision`). "" means exportable by
#: default (no rule spoke). The first four are also the names the contract's
#: own `evidence.precedence` publishes; `EXPORT_RULE_CAPTURED_PROFILE` is this
#: consumer's own step (T-275) and has no counterpart in the contract, which
#: declares no notion of a captured runtime profile.
EXPORT_RULE_TRANSIENT = "transient_segment_or_filename"
EXPORT_RULE_NESTED_INSTANCE = "nested_instance_state"
EXPORT_RULE_DURABLE = "declared_durable_path"
EXPORT_RULE_PREFIX = "non_exportable_prefix"
EXPORT_RULE_CAPTURED_PROFILE = "captured_profile_store"

#: Total ceiling across every declared directory, independent of the caps the
#: manifest itself sets. A hostile or mistaken manifest must not be able to
#: turn packing into a full-disk walk.
GLOBAL_FILE_CEILING = 20000

#: Manifest bytes we are willing to read. The contract is a small declarative
#: document; anything larger is malformed, not generous.
MANIFEST_MAX_BYTES = 256 * 1024

# Snapshot statuses, ordered from best to worst.
STATUS_COMPLETE = "COMPLETE"
STATUS_COMPLETE_WITH_OPTIONAL_OMISSIONS = "COMPLETE_WITH_OPTIONAL_OMISSIONS"
STATUS_PROTOCOL_INCOMPLETE = "PROTOCOL_INCOMPLETE"
STATUS_MANIFEST_ABSENT = "PROTOCOL_MANIFEST_ABSENT"
STATUS_MANIFEST_MALFORMED = "PROTOCOL_MANIFEST_MALFORMED"
STATUS_CONTRACT_UNKNOWN = "PROTOCOL_CONTRACT_UNKNOWN"
#: The contract is newer than implemented but its required capabilities are
#: still structurally present and understood; the document is read through the
#: newest applicable parser with additive unknown fields tolerated. PACK may
#: proceed in a degraded mode.
STATUS_COMPATIBLE_DEGRADED = "COMPATIBLE_DEGRADED"
STATUS_NOT_SAIPEN = "NOT_SAIPEN"


def contract_unknown_detail(version: Any = None) -> str:
    """The ONE wording for a contract version this collector cannot safely read.

    Deliberately says what to do about it. A version ahead of this consumer is
    a consumer defect, not a project defect, and the remediation must not be
    the missing-manifest advice: `saipen audit manifest --write` writes the
    version the installed protocol implements, so regenerating a newer
    manifest reproduces the newer manifest rather than downgrading it.

    Note: a newer contract whose required capabilities are still present is
    NOT unknown -- it is admitted via ``check_capabilities`` in a degraded but
    safe state. This wording is reserved for genuinely unsafe admissions.
    """
    implemented = ", ".join(f"v{v}" for v in SUPPORTED_CONTRACT_VERSIONS)
    if isinstance(version, int) and not isinstance(version, bool) and version > SUPPORTED_CONTRACT_VERSION:
        return (
            f"SAIPEN manifest contract v{version} is newer than this AUDAPACK "
            f"collector (implements {implemented}) and contains semantics this "
            "consumer cannot safely reconstruct. Update AUDAPACK contract "
            "support; regenerating the manifest will not downgrade it."
        )
    return (
        f"SAIPEN manifest declares contract_version {version}; this AUDAPACK "
        f"collector implements {implemented} and refuses to reinterpret a "
        "contract shape it does not implement."
    )


def _cap_project_identity(document: dict) -> bool:
    """project_identity_understood: a stable identity surface exists."""
    return isinstance(document.get("required"), list)


def _cap_include_exclude_rules(document: dict) -> bool:
    """include_exclude_rules_understood: non_exportable + tier rules are
    structurally recognisable as exclusion rules (list of strings/dicts)."""
    evidence = document.get("evidence")
    if not isinstance(evidence, dict):
        return False
    ne = evidence.get("non_exportable")
    if ne is not None and not isinstance(ne, list):
        return False
    mandatory = evidence.get("mandatory")
    if mandatory is not None and not isinstance(mandatory, list):
        return False
    for tier in ("conditional", "optional"):
        rules = evidence.get(tier)
        if rules is None:
            continue
        if not isinstance(rules, list):
            return False
        for item in rules:
            if not isinstance(item, dict) or "path" not in item:
                return False
    return True


def _cap_credential_protection(document: dict) -> bool:
    """credential_protection_rules_understood: non_exportable is a list of
    refusable paths (strings), never a shape this consumer cannot interpret."""
    evidence = document.get("evidence", {})
    ne = evidence.get("non_exportable", [])
    if not isinstance(ne, list):
        return False
    for entry in ne:
        if not isinstance(entry, str):
            return False
    return True


def _cap_inventory_root(document: dict) -> bool:
    """inventory_root_understood: memory_root is a safe project-relative path."""
    memory_root = document.get("memory_root")
    if memory_root is None:
        return True
    if not isinstance(memory_root, str):
        return False
    rel = _norm_rel(memory_root)
    return rel is not None


def _cap_evidence_requirements(document: dict) -> bool:
    """evidence_requirements_understood: required + mandatory are lists of
    path strings, so the consumer can still derive the required evidence set."""
    required = document.get("required")
    if required is not None:
        if not isinstance(required, list) or not all(isinstance(x, str) for x in required):
            return False
    evidence = document.get("evidence", {})
    mandatory = evidence.get("mandatory")
    if mandatory is not None:
        if not isinstance(mandatory, list):
            return False
        for item in mandatory:
            if not isinstance(item, dict) or "path" not in item:
                return False
    return True


def _cap_integrity_semantics(document: dict) -> bool:
    """integrity_semantics_understood: the contract version is an integer and
    the generator field is a string we can structurally validate."""
    version = document.get("contract_version")
    if isinstance(version, bool) or not isinstance(version, int):
        return False
    generator = document.get("generator")
    if not isinstance(generator, str):
        return False
    return True


#: Capability -> probe function. Every probe must stay conservative: when in
#: doubt, return False so the admission hard-blocks rather than silently
#: trusting unknown semantics.
_CAPABILITY_PROBES = (
    ("project_identity_understood", _cap_project_identity),
    ("include_exclude_rules_understood", _cap_include_exclude_rules),
    ("credential_protection_rules_understood", _cap_credential_protection),
    ("inventory_root_understood", _cap_inventory_root),
    ("evidence_requirements_understood", _cap_evidence_requirements),
    ("integrity_semantics_understood", _cap_integrity_semantics),
)


def check_capabilities(document: dict) -> tuple[str, list[str]]:
    """Forward-compatibility probe for a newer-than-implemented contract.

    Returns ``(ManifestAdmission.NATIVE, [])`` when the document is within the
    implemented set, ``(ManifestAdmission.COMPATIBLE_DEGRADED, missing)`` when
    every required capability is structurally present (so the document CAN be
    safely read degraded), or ``(ManifestAdmission.INCOMPATIBLE_UNSAFE, missing)``
    when a required capability is missing or takes a shape this consumer
    cannot interpret.

    The probe never parses evidence rules -- it only checks that the SHAPE the
    rules would take is one this consumer already knows how to read. A newer
    contract that moved ``non_exportable`` from a list of strings to, say,
    objects would fail ``credential_protection_rules_understood`` and be hard
    blocked, because exclusion semantics changed.

    Forward-compatibility applies only to NEWER versions: an older-than-
    implemented version is a different shape this consumer does not natively
    read, and must NOT be silently reinterpreted through the newest parser.
    """
    version = document.get("contract_version")
    if not (isinstance(version, int) and not isinstance(version, bool)):
        return ManifestAdmission.INCOMPATIBLE_UNSAFE, ["integrity_semantics_understood"]
    if version in SUPPORTED_CONTRACT_VERSIONS:
        return ManifestAdmission.NATIVE, []
    if version < SUPPORTED_CONTRACT_VERSION:
        # Older than implemented: not a forward-compat case. The consumer
        # does not implement this shape and must not reinterpret it.
        return ManifestAdmission.INCOMPATIBLE_UNSAFE, list(REQUIRED_CAPABILITIES)
    missing: list[str] = []
    admission = ManifestAdmission.COMPATIBLE_DEGRADED
    for name, probe in _CAPABILITY_PROBES:
        if not probe(document):
            missing.append(name)
            admission = ManifestAdmission.INCOMPATIBLE_UNSAFE
    return admission, missing


def check_capabilities_detail(version: int, admission: str, missing: list[str]) -> str:
    """Operator-facing detail for a forward-compatibility admission."""
    implemented = ", ".join(f"v{v}" for v in SUPPORTED_CONTRACT_VERSIONS)
    if admission == ManifestAdmission.NATIVE:
        return (
            f"SAIPEN manifest contract v{version} is a supported contract; "
            f"AUDAPACK implements {implemented}."
        )
    if admission == ManifestAdmission.COMPATIBLE_DEGRADED:
        return (
            f"SAIPEN manifest contract v{version} is newer than this AUDAPACK "
            f"collector (implements {implemented}), but all required inventory "
            "and security capabilities are structurally present; PACK proceeds "
            "in compatible-degraded mode. Unknown additive metadata is preserved."
        )
    if version < SUPPORTED_CONTRACT_VERSION:
        return (
            f"SAIPEN manifest declares contract_version {version}; this AUDAPACK "
            f"collector implements {implemented} and refuses to reinterpret a "
            "contract shape it does not implement."
        )
    return (
        f"SAIPEN manifest contract v{version} is newer than this AUDAPACK "
        f"collector (implements {implemented}) and lacks the following "
        f"required capability/capabilities this collector cannot reconstruct "
        f"without trusting unknown semantics: {', '.join(missing)}. "
        "Admission: INCOMPATIBLE_UNSAFE. PACK is blocked to avoid violating "
        "a security or integrity boundary."
    )

# Evidence tiers. Which tier an artifact belongs to decides what its ABSENCE
# means: `mandatory` and `conditional` are the contract's required set, so a
# required artifact that does not survive into the archive is an incomplete
# snapshot; `optional` absence is honest and merely reported.
TIER_CONTRACT = "contract"
TIER_MANDATORY = "mandatory"
TIER_CONDITIONAL = "conditional"
TIER_OPTIONAL = "optional"
#: A file a declared closure record cites by path. Required like conditional
#: evidence, but found by reading the citation rather than by a directory rule.
TIER_CITED = "cited"

#: Where the citation rules of a verdict came from.
RULES_FROM_CONTRACT = "contract"
RULES_CONSUMER_DEFAULT = "consumer_default"

#: Hard ceilings a contract's own citation bounds are clamped to.
CITATION_BYTES_CEILING = 64 * 1024 * 1024
CITATION_TOTAL_BYTES_CEILING = 256 * 1024 * 1024
#: Files taken from one cited directory when no directory rule declares a cap.
CITED_DIR_MAX_FILES = 4000
#: Carriers recorded per citation in the report; the verdict never needs more.
CITED_BY_LIMIT = 5
#: A quoted citation may contain spaces; this bounds how far a quote is followed.
QUOTED_CITATION_MAX_CHARS = 512

#: Reason vocabulary for a REQUIRED artifact that did not survive. The first
#: two are produced here; the rest are the inventory policy's own reasons
#: (``configured_ignore`` for an explicit operator exclude, ``secret_policy``
#: for hard safety, ``tracked_deleted``, ``untracked_git_directory`` ...), so a
#: reviewer reads one vocabulary whichever stage removed the file.
REASON_EVIDENCE_ABSENT = "evidence_absent_on_disk"
REASON_EVIDENCE_UNREADABLE = "evidence_unreadable"
REASON_EVIDENCE_NOT_INVENTORIED = "evidence_not_in_inventory"
REASON_EVIDENCE_UNSUPPORTED = "unsupported_special_file"
REASON_DIR_TRUNCATED = "evidence_directory_truncated_at_cap"

#: Inventory-classification reasons owned by the SAIPEN contract (used by the
#: source inventory when Git itself enumerated memory-root material). The
#: contract -- not a noise heuristic -- is what refuses these, so the reason
#: names the authority.
REASON_SAIPEN_NON_EXPORTABLE = "saipen_non_exportable"
REASON_SAIPEN_UNDECLARED = "saipen_undeclared"


@dataclass
class DirRule:
    path: str          # relative to the memory root, e.g. "intake"
    recursive: bool
    max_files: int
    tier: str          # "conditional" | "optional"


@dataclass
class CarrierRule:
    """One closure record, or directory of them, whose citations must resolve."""

    path: str          # relative to the memory root, e.g. "LOG.md"
    kind: str          # "file" | "dir"
    recursive: bool = False
    suffix: str = ""
    max_files: int = 0


@dataclass
class CitationRules:
    surfaces: list[str]
    carriers: list[CarrierRule]
    max_carrier_bytes: int
    max_total_bytes: int
    max_references: int
    source: str = RULES_FROM_CONTRACT


def default_citation_rules() -> CitationRules:
    """The rules `saipen audit manifest` publishes since SRC-054."""
    return CitationRules(
        surfaces=["evidence"],
        carriers=[
            CarrierRule("STATE.md", "file"),
            CarrierRule("BOARD.md", "file"),
            CarrierRule("LOG.md", "file"),
            CarrierRule("logs", "dir", True, ".md", 4000),
            CarrierRule("intake/coverage", "dir", False, ".json", 8000),
            CarrierRule("archive/source", "dir", False, ".coverage.json", 8000),
        ],
        max_carrier_bytes=8 * 1024 * 1024,
        max_total_bytes=64 * 1024 * 1024,
        max_references=20000,
        source=RULES_CONSUMER_DEFAULT,
    )


def _positive_int(raw: Any, ceiling: int) -> Optional[int]:
    if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
        return None
    return min(raw, ceiling)


def _parse_citation_rules(raw: Any) -> Optional[CitationRules]:
    """The contract's `references` block, normalised, or None when malformed.

    Malformed is refused rather than defaulted: a contract that tries to
    declare its citations and gets the shape wrong must not silently fall back
    to rules it did not state.
    """
    if not isinstance(raw, dict):
        return None
    surfaces_raw = raw.get("surfaces")
    carriers_raw = raw.get("carriers")
    if not isinstance(surfaces_raw, list) or not isinstance(carriers_raw, list):
        return None
    surfaces = [_norm_rel(item) for item in surfaces_raw]
    if not surfaces or any(item is None for item in surfaces):
        return None
    carriers: list[CarrierRule] = []
    for item in carriers_raw:
        if not isinstance(item, dict):
            return None
        rel = _norm_rel(item.get("path"))
        kind = item.get("kind")
        if rel is None or kind not in ("file", "dir"):
            return None
        if kind == "file":
            carriers.append(CarrierRule(rel, "file"))
            continue
        cap = _positive_int(item.get("max_files"), GLOBAL_FILE_CEILING)
        suffix = item.get("suffix", "")
        recursive = item.get("recursive", False)
        if cap is None or not isinstance(suffix, str) or not isinstance(recursive, bool):
            return None
        carriers.append(CarrierRule(rel, "dir", recursive, suffix, cap))
    bounds = (
        _positive_int(raw.get("max_carrier_bytes"), CITATION_BYTES_CEILING),
        _positive_int(raw.get("max_total_bytes"), CITATION_TOTAL_BYTES_CEILING),
        _positive_int(raw.get("max_references"), GLOBAL_FILE_CEILING),
    )
    if any(bound is None for bound in bounds):
        return None
    return CitationRules(surfaces, carriers, *bounds, source=RULES_FROM_CONTRACT)


@dataclass
class SaipenContract:
    """What the protocol declared, already normalised and bounded."""

    detected: bool = False
    status: str = STATUS_NOT_SAIPEN
    contract_version: Optional[int] = None
    protocol_version: str = ""
    generated_at: str = ""
    generator: str = ""
    memory_root: str = MEMORY_ROOT
    mandatory: list[str] = field(default_factory=list)   # root-relative rels
    #: The contract's OWN `required` closure, resolved to memory-root-relative
    #: paths and unioned into `mandatory` (see `_parse_required`).
    required: list[str] = field(default_factory=list)
    dirs: list[DirRule] = field(default_factory=list)
    non_exportable: list[str] = field(default_factory=list)
    #: Structural transient classes (`evidence.non_exportable_segments`,
    #: `_filenames`, `_suffixes`) and the nested-instance filenames, matched at
    #: ANY depth below the memory root. Empty when the document declares none
    #: (every v1/v2 document), so older contracts read exactly as before.
    transient_segments: tuple = ()
    transient_filenames: tuple = ()
    transient_suffixes: tuple = ()
    nested_instance_files: tuple = ()
    #: `evidence.precedence` as declared (empty when absent).
    precedence: tuple = ()
    #: True only when the declared precedence is exactly the ordering this
    #: consumer implements (`EXPORT_PRECEDENCE`). Only then may a declared
    #: durable path outrank a generic `non_exportable` prefix; any other
    #: declaration keeps the stricter prefix semantics.
    durable_precedence: bool = False
    citations: Optional[CitationRules] = None
    #: `compatibility.unknown_contract_version` as declared ("" when the
    #: document declares none). Only a policy this consumer can actually
    #: honour is accepted; anything else is malformed, not ignored.
    compatibility_policy: str = ""
    #: Forward-compatibility admission verdict. NATIVE when the contract is
    #: within the implemented set, COMPATIBLE_DEGRADED when newer but all
    #: required capabilities are structurally present, INCOMPATIBLE_UNSAFE when
    #: it cannot be safely read. (MILESTONE K.)
    admission: str = ManifestAdmission.NATIVE
    #: The capabilities that failed the forward-compat probe, when admitted
    #: degraded or unsafe. Empty when NATIVE or COMPATIBLE_DEGRADED.
    admission_missing: list[str] = field(default_factory=list)
    detail: str = ""


@dataclass
class EvidenceCollection:
    """The bounded result of walking exactly what the contract named.

    Every discovered path is tagged with the contract TIER that named it, so
    the verdict can later say what the loss of that particular file means
    instead of treating all evidence as one undifferentiated list.
    """

    contract: SaipenContract
    paths: list[str] = field(default_factory=list)
    mandatory_found: list[str] = field(default_factory=list)
    mandatory_missing: list[str] = field(default_factory=list)
    conditional_found: list[str] = field(default_factory=list)
    optional_found: list[str] = field(default_factory=list)
    truncated_dirs: list[str] = field(default_factory=list)
    truncated_conditional: list[str] = field(default_factory=list)
    truncated_optional: list[str] = field(default_factory=list)
    unreadable: list[str] = field(default_factory=list)
    tier_of: dict = field(default_factory=dict)   # rel -> tier constant
    # Citation discovery (SRC-054).
    cited_files: list[str] = field(default_factory=list)     # cited, on disk
    cited_dirs: list[str] = field(default_factory=list)
    cited_missing: list[str] = field(default_factory=list)   # cited, absent
    cited_ignored: list[str] = field(default_factory=list)   # absent, no file shape
    cited_required: list[str] = field(default_factory=list)  # files the archive must hold
    cited_by: dict = field(default_factory=dict)             # rel -> carrier rels
    carriers_scanned: int = 0
    carrier_bytes_scanned: int = 0
    citation_truncated: bool = False
    unreadable_carriers: list[str] = field(default_factory=list)
    #: True when the global walk budget ran out, i.e. `paths` is an INCOMPLETE
    #: picture of what the contract declared. A consumer that treats `paths` as
    #: an allowlist must not do so while this is set: an unfinished walk is not a
    #: declaration that the rest of the memory root is private.
    budget_exhausted: bool = False


def _norm_rel(raw: Any) -> Optional[str]:
    """Normalise a contract-declared relative path, or refuse it.

    Refuses absolute paths, drive letters, and any ``..``/``.`` segment, so
    a manifest can never reach outside the project it lives in.
    """
    if not isinstance(raw, str):
        return None
    text = raw.strip().replace("\\", "/")
    if not text:
        return None
    if text.startswith("/"):
        return None
    if len(text) >= 2 and text[1] == ":":
        return None
    parts = [seg for seg in text.split("/") if seg]
    if not parts or any(seg in ("..", ".") for seg in parts):
        return None
    return "/".join(parts)


def read_contract_from_document(document: dict) -> SaipenContract:
    """Parse a contract from an in-memory document dict (test helper).

    This bypasses disk I/O and is useful for testing forward-compatibility
    without creating temp directories.
    """
    if not isinstance(document, dict):
        return SaipenContract(detected=True, status=STATUS_MANIFEST_MALFORMED, detail="document is not a dict")
    if document.get("kind") != "saipen_audit_manifest":
        return SaipenContract(detected=True, status=STATUS_MANIFEST_MALFORMED, detail="not a saipen_audit_manifest")
    version = document.get("contract_version")
    if isinstance(version, bool) or not isinstance(version, int):
        return SaipenContract(detected=True, status=STATUS_MANIFEST_MALFORMED, detail="contract_version not an integer")
    memory_root = _norm_rel(document.get("memory_root")) or MEMORY_ROOT
    base = SaipenContract(
        detected=True,
        contract_version=version,
        protocol_version=str(document.get("protocol_version") or ""),
        generated_at=str(document.get("generated_at") or ""),
        generator=str(document.get("generator") or ""),
        memory_root=memory_root,
    )
    error = _parse_compatibility(base, document)
    if error:
        base.status = STATUS_MANIFEST_MALFORMED
        base.detail = error
        return base
    if version in SUPPORTED_CONTRACT_VERSIONS:
        return _CONTRACT_PARSERS[version](base, document, memory_root)
    admission, missing = check_capabilities(document)
    base.admission = admission
    base.admission_missing = missing
    if admission == ManifestAdmission.COMPATIBLE_DEGRADED:
        newest = SUPPORTED_CONTRACT_VERSION
        parsed = _CONTRACT_PARSERS[newest](base, document, memory_root)
        parsed.admission = admission
        parsed.admission_missing = missing
        parsed.detail = check_capabilities_detail(version, admission, missing)
        return parsed
    base.status = STATUS_CONTRACT_UNKNOWN
    base.detail = check_capabilities_detail(version, admission, missing)
    return base


def detect(source_root: Path) -> bool:
    """True when a real (non-symlinked) protocol memory root is present."""
    memory = source_root / MEMORY_ROOT
    try:
        if memory.is_symlink():
            return False
        return memory.is_dir()
    except OSError:
        return False


def read_contract(source_root: Path) -> SaipenContract:
    """Read ``.saipen/MANIFEST.json`` with one stat and one bounded read."""
    if not detect(source_root):
        return SaipenContract(detected=False, status=STATUS_NOT_SAIPEN)

    path = source_root.joinpath(*MANIFEST_REL.split("/"))
    try:
        st = path.lstat()
    except OSError:
        return SaipenContract(
            detected=True,
            status=STATUS_MANIFEST_ABSENT,
            detail=(
                "no .saipen/MANIFEST.json; run `saipen audit manifest --write` "
                "in the project so the packager can learn what its evidence is"
            ),
        )
    if stat_module.S_ISLNK(st.st_mode) or not stat_module.S_ISREG(st.st_mode):
        return SaipenContract(
            detected=True,
            status=STATUS_MANIFEST_MALFORMED,
            detail=".saipen/MANIFEST.json is not a regular file",
        )
    if st.st_size > MANIFEST_MAX_BYTES:
        return SaipenContract(
            detected=True,
            status=STATUS_MANIFEST_MALFORMED,
            detail=f".saipen/MANIFEST.json is {st.st_size} bytes (cap {MANIFEST_MAX_BYTES})",
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        return SaipenContract(
            detected=True,
            status=STATUS_MANIFEST_MALFORMED,
            detail=f".saipen/MANIFEST.json unreadable: {exc}",
        )
    if not isinstance(data, dict) or data.get("kind") != "saipen_audit_manifest":
        return SaipenContract(
            detected=True,
            status=STATUS_MANIFEST_MALFORMED,
            detail=(
                "a .saipen/MANIFEST.json that does not declare "
                "kind=saipen_audit_manifest is not this contract"
            ),
        )

    version = data.get("contract_version")
    if isinstance(version, bool) or not isinstance(version, int):
        return SaipenContract(
            detected=True,
            status=STATUS_MANIFEST_MALFORMED,
            detail="contract_version is missing or not an integer",
        )
    memory_root = _norm_rel(data.get("memory_root")) or MEMORY_ROOT
    base = SaipenContract(
        detected=True,
        contract_version=version,
        protocol_version=str(data.get("protocol_version") or ""),
        generated_at=str(data.get("generated_at") or ""),
        generator=str(data.get("generator") or ""),
        memory_root=memory_root,
    )
    # Envelope first, dispatch second: version ownership belongs to an explicit
    # set, and a version outside it is answered by the contract's own
    # compatibility policy -- never by the newest parser.
    error = _parse_compatibility(base, data)
    if error:
        base.status = STATUS_MANIFEST_MALFORMED
        base.detail = error
        return base
    if version not in SUPPORTED_CONTRACT_VERSIONS:
        # FORWARD-COMPATIBILITY PROBE (MILESTONE K). A newer contract that still
        # carries every capability this consumer depends on is admitted in a
        # degraded but safe state and read through the newest applicable parser;
        # additive unknown fields are tolerated and preserved. Only a newer
        # contract that drops or reshapes a required capability is hard-blocked.
        admission, missing = check_capabilities(data)
        base.admission = admission
        base.admission_missing = missing
        if admission == ManifestAdmission.COMPATIBLE_DEGRADED:
            # v3 is read through the v2 parser: the v3 shape is a strict
            # superset of v2 in every field AUDAPACK depends on. Its additive
            # export classes (non_exportable_segments/_filenames/_suffixes,
            # nested_instance_files, precedence) are parsed by the shared
            # `_parse_export_classes` and applied by `export_decision`; the
            # admission stays COMPATIBLE_DEGRADED because interpreting that one
            # known declaration is not native v3 support.
            newest = SUPPORTED_CONTRACT_VERSION
            parsed = _CONTRACT_PARSERS[newest](base, data, memory_root)
            parsed.admission = admission
            parsed.admission_missing = missing
            parsed.detail = check_capabilities_detail(version, admission, missing)
            return parsed
        base.status = STATUS_CONTRACT_UNKNOWN
        base.detail = check_capabilities_detail(version, admission, missing)
        return base
    return _CONTRACT_PARSERS[version](base, data, memory_root)


def _parse_compatibility(base: SaipenContract, data: dict) -> Optional[str]:
    """Honour `compatibility`, or refuse to read the document.

    The block declares how a consumer must treat a version it does not
    implement. This consumer already does the only thing it publishes
    (``refuse``), so a matching declaration is accepted, an absent block is
    tolerated (it is metadata, not evidence), and any OTHER policy -- or a
    block that is not an object -- is refused. Silently ignoring a
    compatibility policy would be reading a document on terms its author
    explicitly ruled out.
    """
    raw = data.get("compatibility")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return "manifest compatibility block is not an object"
    policy = raw.get("unknown_contract_version")
    if policy is None:
        return None
    if not isinstance(policy, str) or policy != "refuse":
        return (
            f"manifest compatibility.unknown_contract_version {policy!r} is not "
            "a policy this consumer implements (only 'refuse')"
        )
    base.compatibility_policy = policy
    return None


def _parse_evidence(base: SaipenContract, data: dict, memory_root: str) -> Optional[str]:
    """Fill the evidence rules every implemented contract version declares."""
    evidence = data.get("evidence")
    if not isinstance(evidence, dict):
        return "manifest has no evidence object"

    for item in evidence.get("mandatory") or []:
        raw = item.get("path") if isinstance(item, dict) else item
        rel = _norm_rel(raw)
        if rel:
            base.mandatory.append(f"{memory_root}/{rel}")

    for tier in ("conditional", "optional"):
        for item in evidence.get(tier) or []:
            if not isinstance(item, dict):
                continue
            rel = _norm_rel(item.get("path"))
            if not rel:
                continue
            try:
                cap = int(item.get("max_files", 0))
            except (TypeError, ValueError):
                continue
            if cap <= 0:
                continue
            base.dirs.append(
                DirRule(
                    path=rel,
                    recursive=bool(item.get("recursive", False)),
                    max_files=min(cap, GLOBAL_FILE_CEILING),
                    tier=tier,
                )
            )

    for raw in evidence.get("non_exportable") or []:
        rel = _norm_rel(raw)
        if rel:
            base.non_exportable.append(f"{memory_root}/{rel}")

    error = _parse_export_classes(base, evidence)
    if error:
        return error

    if not base.mandatory:
        return "manifest declares no mandatory evidence"
    return None


def _parse_name_list(evidence: dict, key: str, *, suffix: bool = False):
    """One declared structural-class list, normalised once, or an error string.

    Absent means "declares none". A present value must be a bounded list of
    single path components (a suffix may not contain a separator either), so a
    malformed declaration can neither widen nor silently narrow the export set.
    """
    raw = evidence.get(key)
    if raw is None:
        return ()
    if not isinstance(raw, list) or len(raw) > EXPORT_CLASS_LIST_LIMIT:
        return f"manifest evidence.{key} is not a bounded list"
    names: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item or len(item) > 255:
            return f"manifest evidence.{key} entry {item!r} is not a name"
        if "/" in item or "\\" in item or (not suffix and item in (".", "..")):
            return f"manifest evidence.{key} entry {item!r} is not a single path component"
        if item not in names:
            names.append(item)
    return tuple(names)


def _parse_export_classes(base: SaipenContract, evidence: dict) -> Optional[str]:
    """Read the additive export-classification declarations (contract v3).

    Restrictive classes (transient segments/filenames/suffixes, nested
    instance state) are honoured whenever declared: applying them can only
    narrow what leaves the project. The single LOOSENING rule -- a declared
    durable path outranking a generic `non_exportable` prefix -- is enabled
    only when `evidence.precedence` is exactly the ordering implemented here.
    """
    parsed = {}
    for key, attr, suffix in (
        ("non_exportable_segments", "transient_segments", False),
        ("non_exportable_filenames", "transient_filenames", False),
        ("non_exportable_suffixes", "transient_suffixes", True),
        ("nested_instance_files", "nested_instance_files", False),
        ("precedence", "precedence", False),
    ):
        value = _parse_name_list(evidence, key, suffix=suffix)
        if isinstance(value, str):
            return value
        parsed[attr] = value
    for attr, value in parsed.items():
        setattr(base, attr, value)
    base.durable_precedence = base.precedence == EXPORT_PRECEDENCE
    return None


def _parse_required(base: SaipenContract, data: dict, memory_root: str) -> Optional[str]:
    """Honour the contract's own `required` closure.

    Both implemented versions publish it, relative to the manifest's own
    directory, and SAIPEN's own note on the field says it exists so a packager
    with a ``required`` closure gets the mandatory documents "through
    machinery it already has". It is therefore a REQUIREMENT DECLARATION, and
    reading it as decoration would let a document that names a path in
    `required` while omitting it from `evidence.mandatory` pack without it.
    Resolved as a UNION with `evidence.mandatory`: either list can only add.
    """
    raw = data.get("required")
    if raw is None:
        return None
    if not isinstance(raw, list):
        return "manifest required block is not a list"
    for item in raw:
        rel = _norm_rel(item)
        if rel is None:
            return f"manifest required entry {item!r} is not a project-relative path"
        full = f"{memory_root}/{rel}"
        if full not in base.required:
            base.required.append(full)
        if full not in base.mandatory:
            base.mandatory.append(full)
    return None


def _finish_contract(base: SaipenContract, data: dict, memory_root: str) -> SaipenContract:
    """The tail every implemented contract version shares verbatim."""
    for parse in (_parse_evidence, _parse_required):
        error = parse(base, data, memory_root)
        if error:
            base.status = STATUS_MANIFEST_MALFORMED
            base.detail = error
            return base

    if "references" in data:
        base.citations = _parse_citation_rules(data.get("references"))
        if base.citations is None:
            base.status = STATUS_MANIFEST_MALFORMED
            base.detail = "manifest references block is malformed"
            return base
    else:
        base.citations = default_citation_rules()

    base.status = STATUS_COMPLETE  # provisional; collect() decides the truth
    return base


def parse_contract_v1(base: SaipenContract, data: dict, memory_root: str) -> SaipenContract:
    """Contract v1: the shape SAIPEN published before the v2 bump.

    Byte-for-byte the consumer semantics that existed before the version split
    -- same evidence inventory, same non-exportable protection, same citation
    handling, same verdict -- because a v1 document must keep packing exactly
    as it did rather than being re-read through v2's rules. v1 projects are
    NOT forced to regenerate: the contract stays theirs to declare.
    """
    return _finish_contract(base, data, memory_root)


def parse_contract_v2(base: SaipenContract, data: dict, memory_root: str) -> SaipenContract:
    """Contract v2: v1 plus the exclusion v2 added.

    The delta between the published shapes is small and was taken from the
    real generator's output, not inferred: contract/generator version and
    `quarantine/` in `evidence.non_exportable`. So v2 is read exactly like v1
    and THEN held to the v2 baseline exclusions -- a v2 document that drifted,
    or that was hand-edited to drop one, still cannot export it.
    """
    result = _finish_contract(base, data, memory_root)
    if result.status != STATUS_COMPLETE:
        return result
    for rel in V2_NON_EXPORTABLE_BASELINE:
        full = f"{memory_root}/{rel}"
        if full not in result.non_exportable:
            result.non_exportable.append(full)
    return result


#: Version -> parser. The single place an implemented contract version is
#: bound to the code that reads it.
_CONTRACT_PARSERS = {
    1: parse_contract_v1,
    2: parse_contract_v2,
}


#: T-274: reproducible browser/app store subtrees. A SAIPEN evidence directory
#: can hold a captured browser profile -- a soak run's session, with a
#: ``Cache/Cache_Data`` blob of megabytes that says nothing about the project and
#: is regenerated by launching the browser again. It is transient by the same
#: argument as the contract's own transient list, so it is refused wherever it
#: sits INSIDE the memory root (never anywhere else), stays a NAMED omission in
#: the manifest, and cannot re-enter through a profile path Git tracks.
_REPRODUCIBLE_CACHE_SEGMENTS = frozenset(
    {
        "cache",
        "cache_data",
        "code cache",
        "gpucache",
        "gpu cache",
        "shadercache",
        "dawncache",
        "grshadercache",
        "dawn webgpu cache",
        "service worker",
        # T-275: the spellings Chromium actually writes. The declared set held
        # the readable forms above ("dawncache", "dawn webgpu cache"), which a
        # directory name never matches -- 100 entries (10.6 MB) of exactly this
        # class survived T-274's real archive because of the space.
        "dawngraphitecache",
        "dawnwebgpucache",
        # T-299: the layout npm actually writes under a cache root. A probe
        # that points npm_config_cache at a kitchen tmp-control directory
        # ships the whole blob store (~20.7 MB compressed) in every audit
        # bundle. Content-addressed blobs say nothing about the project and
        # are regenerated by running npm again, so they are transient by the
        # same argument as the browser caches above. Matched case-insensitively
        # by export_decision, inside the memory root only.
        "_cacache",
        "content-v2",
        "index-v5",
    }
)


#: T-275: a CAPTURED RUNTIME PROFILE directory. A soak/capture run leaves a
#: whole machine profile behind: the agent's own ``.zcode`` store (session
#: database, rollout transcripts, plugin caches), ``.zaicode``, ``.gemini``,
#: ``AppData``, a Chromium ``session/`` tree with Cookies and local storage,
#: and the router/account state files beside them. That is the machine that ran
#: the capture, not evidence ABOUT the project: on T-274's own acceptance
#: archive it was 940 files and 21.6 MB, six of them ``rollout/*.jsonl``
#: transcripts and four ``zaicode-router-key.json`` / ``zaicode-account-proxy
#: .json`` per capture.
#:
#: It shipped because ``evidence`` is a RECURSIVE conditional directory, so
#: every path below it is a ``declared_durable_path`` and outranks a generic
#: ban. The refusal therefore names the CONTAINER: enumerating the individual
#: stores would leak whichever store the next release adds, and the whole
#: subtree is machine state either way. The capture harness writes the
#: directory as ``profile-<token>`` or plain ``profile``.
_CAPTURED_PROFILE_DIR = "profile"
_CAPTURED_PROFILE_PREFIX = "profile-"


def _captured_profile_at(parts: list) -> int:
    """Index of the captured-profile directory in *parts*, or -1.

    The last segment is never the marker: a captured profile is a directory,
    and only a segment with children below it can be one -- which is also what
    keeps an evidence FILE named ``profile-notes.md`` out of the ban.
    """
    for index, part in enumerate(parts[:-1]):
        if part == _CAPTURED_PROFILE_DIR or (
            part.startswith(_CAPTURED_PROFILE_PREFIX) and len(part) > len(_CAPTURED_PROFILE_PREFIX)
        ):
            return index
    return -1


def _declared_durable(tail: str, contract: SaipenContract) -> bool:
    """Is memory-root-relative *tail* a path the contract declares durable?

    Mirrors SAIPEN's own `_declared_durable`: a root-level mandatory document,
    or a file inside a CONDITIONAL directory rule (recursive rules cover the
    whole subtree, non-recursive ones only direct children). Optional
    directories are discretionary material and never outrank a ban.
    """
    if "/" not in tail and f"{contract.memory_root}/{tail}" in contract.mandatory:
        return True
    for rule in contract.dirs:
        if rule.tier != TIER_CONDITIONAL:
            continue
        if tail == rule.path:
            return True
        if tail.startswith(rule.path + "/"):
            return rule.recursive or "/" not in tail[len(rule.path) + 1:]
    return False


def export_decision(rel: str, contract: SaipenContract) -> tuple[bool, str]:
    """THE exportability decision for a project-relative path: (exportable, rule).

    One owner, applied in `EXPORT_PRECEDENCE` order, so the collector, cited
    evidence, the inventory reclassification and the final snapshot cannot
    disagree about the same file:

    1. captured runtime profile subtree -> banned (T-275)
    2. transient segment / filename / suffix -> banned
    3. nested instance STATE/BOARD/LOG/IDENTITY below the root -> banned
    4. declared durable path (only under the known precedence) -> exportable
    5. generic `non_exportable` prefix -> banned
    6. anything else -> exportable here; directory rules decide collection.

    Governs SAIPEN export policy only. AUDAPACK hard safety (secret policy)
    and an operator's explicit `always_exclude` are applied by the inventory
    BEFORE this, and stay authoritative over it.
    """
    root = contract.memory_root + "/"
    tail = rel[len(root):] if rel.startswith(root) else ""
    if tail:
        parts = tail.split("/")
        last = parts[-1]
        if _captured_profile_at(parts) >= 0:
            return False, EXPORT_RULE_CAPTURED_PROFILE
        if (
            any(part in contract.transient_segments for part in parts)
            or any(part.lower() in _REPRODUCIBLE_CACHE_SEGMENTS for part in parts)
            or last in contract.transient_filenames
            or (contract.transient_suffixes and last.endswith(contract.transient_suffixes))
        ):
            return False, EXPORT_RULE_TRANSIENT
        if len(parts) > 1 and last in contract.nested_instance_files:
            return False, EXPORT_RULE_NESTED_INSTANCE
        if contract.durable_precedence and _declared_durable(tail, contract):
            return True, EXPORT_RULE_DURABLE
    for banned in contract.non_exportable:
        if rel == banned or rel.startswith(banned.rstrip("/") + "/"):
            return False, EXPORT_RULE_PREFIX
    return True, ""


def _is_non_exportable(rel: str, contract: SaipenContract) -> bool:
    return not export_decision(rel, contract)[0]


def is_non_exportable(rel: str, contract: SaipenContract) -> bool:
    """Public alias: is *rel* inside a surface the contract bans from export?"""
    return _is_non_exportable(rel, contract)


_CITATION_SEP = r"[\\/]+"
_CITATION_SEGMENT = r"[\w.\-+@=~]+"

#: Characters that turn a token into a PATTERN rather than a path. A citation
#: must name a path; a wildcard expression names a family, and the literal
#: prefix in front of it is not evidence.
_CITATION_WILDCARDS = ("*", "?", "[")


def _citation_pattern(memory_root: str, surfaces: list[str]) -> "re.Pattern[str]":
    """``<memory_root>/<surface>/<path>`` that does not continue a longer path.

    Either separator is accepted, a leading ``./`` is tolerated, and the path
    ends at the first character a SAIPEN evidence name does not use, so
    whitespace, quotes, brackets and sentence punctuation all terminate it.
    """

    def spelled(rel: str) -> str:
        return _CITATION_SEP.join(re.escape(part) for part in rel.split("/"))

    surface_alternatives = "|".join(spelled(s) for s in sorted(surfaces, key=len, reverse=True))
    return re.compile(
        r"(?<![\w.\-+@=~/\\])(?:\.[\\/]+)?"
        + spelled(memory_root)
        + _CITATION_SEP
        + r"(?P<surface>" + surface_alternatives + r")"
        + r"(?P<tail>(?:" + _CITATION_SEP + _CITATION_SEGMENT + r")*)"
    )


def _citation_tail(tail: str) -> Optional[str]:
    """The cited path below its surface, or None when it names no file.

    A trailing sentence period is not part of the name. A ``.`` or ``..``
    segment is an escape attempt, never a citation of this surface.
    """
    parts = [part for part in re.split(_CITATION_SEP, tail) if part]
    if parts:
        parts[-1] = parts[-1].rstrip(".")
        if not parts[-1]:
            parts.pop()
    if not parts or any(part.strip(".") == "" for part in parts):
        return None
    return "/".join(parts)


def _names_absent_file(rel: str) -> bool:
    """Does an ABSENT cited token name a file, or is it directory-ambiguous?

    Only a file-shaped token can be required when the disk does not hold it.
    A token whose final segment carries no dot cannot be told apart from a
    directory name, and the directory semantics of the same tier add only the
    files a cited directory ACTUALLY holds -- an empty or later-cleaned
    directory contributes nothing. Treating such a token as an omitted file
    made an intentional, canonically journaled cleanup (CLEAN's removal of an
    empty-directory residue) degrade every later archive forever, which is an
    inconsistency inside the tier, not fail-closed strictness: the same token
    would have required nothing while the directory existed. A token WITH an
    extension names a file, and its absence stays a required omission -- the
    Problip class this tier exists for.
    """
    final = rel.rsplit("/", 1)[-1].strip(".")
    return "." in final


def _json_strings(document: Any) -> list[str]:
    strings: list[str] = []
    stack = [document]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            strings.append(item)
        elif isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return strings


def _carrier_files(source_root: Path, contract: SaipenContract, result: EvidenceCollection):
    """Yield ``(rel, path)`` for every carrier file the citation rules name, bounded."""
    rules = contract.citations
    memory = source_root.joinpath(*contract.memory_root.split("/"))
    for carrier in rules.carriers:
        base = memory.joinpath(*carrier.path.split("/"))
        if carrier.kind == "file":
            yield f"{contract.memory_root}/{carrier.path}", base
            continue
        try:
            if base.is_symlink() or not base.is_dir():
                continue
        except OSError:
            continue
        found: list[Path] = []
        stack = [base]
        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as it:
                    entries = sorted(it, key=lambda e: e.name)
            except OSError:
                result.unreadable_carriers.append(Path(current).relative_to(source_root).as_posix())
                continue
            for entry in entries:
                try:
                    if entry.is_symlink():
                        if entry.name.lower().endswith(carrier.suffix.lower()):
                            # A linked closure record is not one this project wrote.
                            result.unreadable_carriers.append(
                                Path(entry.path).relative_to(source_root).as_posix()
                            )
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if carrier.recursive:
                            stack.append(Path(entry.path))
                        continue
                except (OSError, ValueError):
                    continue
                if entry.name.lower().endswith(carrier.suffix.lower()):
                    found.append(Path(entry.path))
        found.sort()
        if len(found) > carrier.max_files:
            result.citation_truncated = True
            found = found[: carrier.max_files]
        for path in found:
            yield path.relative_to(source_root).as_posix(), path


def _discover_citations(source_root: Path, contract: SaipenContract, result: EvidenceCollection, cancelled) -> dict:
    """``{cited rel: [carrier rel, ...]}`` read from the declared closure records.

    Bounded by the contract: carrier count per directory, bytes per carrier,
    bytes in total and distinct citations. Hitting any bound marks discovery
    truncated, which the verdict treats as incomplete.
    """
    rules = contract.citations
    pattern = _citation_pattern(contract.memory_root, rules.surfaces)
    found: dict[str, list[str]] = {}
    total = 0
    for carrier_rel, path in _carrier_files(source_root, contract, result):
        if cancelled():
            break
        try:
            st = path.lstat()
        except OSError:
            continue  # an absent carrier cites nothing
        if stat_module.S_ISLNK(st.st_mode) or not stat_module.S_ISREG(st.st_mode):
            result.unreadable_carriers.append(carrier_rel)
            continue
        if st.st_size > rules.max_carrier_bytes or total + st.st_size > rules.max_total_bytes:
            result.citation_truncated = True
            continue
        try:
            data = path.read_bytes()
        except OSError:
            result.unreadable_carriers.append(carrier_rel)
            continue
        total += len(data)
        result.carriers_scanned += 1
        result.carrier_bytes_scanned += len(data)
        text = data.decode("utf-8-sig", errors="replace")
        if carrier_rel.lower().endswith(".json"):
            try:
                chunks = _json_strings(json.loads(text))
            except ValueError:
                result.unreadable_carriers.append(carrier_rel)
                continue
        else:
            chunks = [text]
        for chunk in chunks:
            for match in pattern.finditer(chunk):
                # A token the author wrote as a PATTERN -- `.saipen/evidence/
                # RAPORT-*` -- names a family, not a path: the prefix the
                # scanner can see is not a file anyone could ever hold, and
                # requiring the literal prefix degraded every archive whose
                # prose described a glob. The wildcard IS the claim; the
                # family's members are collected by their directory rule.
                if chunk[match.end():match.end() + 1] in _CITATION_WILDCARDS:
                    continue
                tail = _citation_tail(match.group("tail"))
                if tail is None:
                    continue
                surface = "/".join(part for part in re.split(_CITATION_SEP, match.group("surface")) if part)
                rel = f"{contract.memory_root}/{surface}/{tail}"
                carriers = found.get(rel)
                if carriers is None:
                    if len(found) >= rules.max_references:
                        result.citation_truncated = True
                        return found
                    carriers = found[rel] = []
                if carrier_rel not in carriers and len(carriers) < CITED_BY_LIMIT:
                    carriers.append(carrier_rel)
    return found


def _on_disk_case(source_root: Path, rel: str, listings: dict) -> str:
    """``rel`` spelled the way the directory entries spell it, where that is unambiguous.

    A citation written in another case resolves to the same file on a
    case-insensitive filesystem, and a candidate under the citation's spelling
    beside the directory rule's candidate is a case collision the inventory
    refuses the whole pack over.
    """
    parts = rel.split("/")
    current = source_root
    spelled: list[str] = []
    for index, part in enumerate(parts):
        key = str(current)
        if key not in listings:
            try:
                with os.scandir(current) as it:
                    listings[key] = [entry.name for entry in it]
            except OSError:
                listings[key] = None
        names = listings[key]
        if names is None:
            return "/".join(spelled + parts[index:])
        if part not in names:
            folded = [name for name in names if name.lower() == part.lower()]
            if len(folded) == 1:
                part = folded[0]
        spelled.append(part)
        current = current / part
    return "/".join(spelled)


def _cited_dir_files(source_root: Path, base: Path, cap: int) -> tuple[list[str], bool]:
    """Files under a cited directory, sorted and capped; symlinked dirs never entered."""
    files: list[str] = []
    stack = [base]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError:
            continue
        for entry in entries:
            try:
                if not entry.is_symlink() and entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
                    continue
                files.append(Path(entry.path).relative_to(source_root).as_posix())
            except (OSError, ValueError):
                continue
    files.sort()
    return files[:cap], len(files) > cap


def collect(source_root: Path, contract: SaipenContract, cancel_event=None) -> EvidenceCollection:
    """Walk exactly what the contract named. Never more.

    Returns source-relative POSIX paths. Symlinks are reported (the caller
    validates them like any other entry) but symlinked DIRECTORIES are never
    descended, so collection cannot leave the project tree.
    """
    result = EvidenceCollection(contract=contract)
    if not contract.detected or contract.status in (
        STATUS_MANIFEST_ABSENT,
        STATUS_MANIFEST_MALFORMED,
        STATUS_CONTRACT_UNKNOWN,
        STATUS_NOT_SAIPEN,
    ):
        return result
    # STATUS_COMPATIBLE_DEGRADED is treated as collectable: the contract was
    # read through a degraded path but all evidence rules are structurally
    # present. The snapshot will report admission=COMPATIBLE_DEGRADED.

    def cancelled() -> bool:
        return cancel_event is not None and cancel_event.is_set()

    # NOTE ON ORDER: mandatory documents are stat'ed first, then the declared
    # directories are walked in contract order with per-directory caps. Nothing
    # outside the contract is ever opened, so a project that ignores a 60 MB
    # working tree still costs exactly what its own declaration names.

    seen: set[str] = set()
    budget = GLOBAL_FILE_CEILING

    def add(rel: str, tier: str = "") -> bool:
        nonlocal budget
        if rel in seen or _is_non_exportable(rel, contract):
            return False
        if budget <= 0:
            result.budget_exhausted = True
            return False
        seen.add(rel)
        result.paths.append(rel)
        budget -= 1
        if tier:
            result.tier_of[rel] = tier
        return True

    # The contract travels with the evidence it governs: a reviewer must be
    # able to re-derive the verdict from the archive alone.
    add(MANIFEST_REL, TIER_CONTRACT)

    for rel in contract.mandatory:
        full = source_root.joinpath(*rel.split("/"))
        try:
            st = full.lstat()
        except OSError:
            result.mandatory_missing.append(rel)
            continue
        if stat_module.S_ISLNK(st.st_mode) or not stat_module.S_ISREG(st.st_mode):
            # A mandatory document that is not a real file cannot be trusted
            # as evidence; say so rather than packing whatever it points at.
            result.mandatory_missing.append(rel)
            result.unreadable.append(rel)
            continue
        result.mandatory_found.append(rel)
        add(rel, TIER_MANDATORY)

    for rule in contract.dirs:
        if cancelled():
            break
        base_rel = f"{contract.memory_root}/{rule.path}"
        base = source_root.joinpath(*base_rel.split("/"))
        try:
            if base.is_symlink() or not base.is_dir():
                continue
        except OSError:
            continue
        taken = 0
        stack = [base]
        truncated = False
        while stack:
            if cancelled():
                break
            current = stack.pop()
            try:
                with os.scandir(current) as it:
                    entries = sorted(it, key=lambda e: e.name)
            except OSError:
                result.unreadable.append(
                    Path(current).relative_to(source_root).as_posix()
                )
                continue
            for entry in entries:
                if taken >= rule.max_files:
                    truncated = True
                    break
                try:
                    entry_rel = Path(entry.path).relative_to(source_root).as_posix()
                    if entry.is_symlink():
                        if add(entry_rel, rule.tier):
                            taken += 1
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if rule.recursive:
                            stack.append(Path(entry.path))
                        continue
                except (OSError, ValueError):
                    continue
                if add(entry_rel, rule.tier):
                    taken += 1
            if truncated:
                break
        if truncated:
            result.truncated_dirs.append(base_rel)
            # A cap is a containment bound, not a policy: hitting it on
            # CONDITIONAL evidence means required material was left behind,
            # while hitting it on OPTIONAL material is a reported omission.
            # Both are recorded; only the first may degrade authority.
            if rule.tier == TIER_CONDITIONAL:
                result.truncated_conditional.append(base_rel)
            else:
                result.truncated_optional.append(base_rel)

    # Cited evidence (SRC-054): what closure records name must travel even
    # when no directory rule found it, and its absence must be countable.
    if contract.citations is not None and not cancelled():
        cap_by_surface = {rule.path: rule.max_files for rule in contract.dirs}

        def require(rel: str, carriers: list[str]) -> None:
            if rel not in result.cited_by:
                result.cited_by[rel] = list(carriers)
            if rel not in result.cited_required:
                result.cited_required.append(rel)
            if rel in seen or _is_non_exportable(rel, contract):
                return  # already collected, or refused and reported by the verdict
            if not add(rel, TIER_CITED):
                result.citation_truncated = True

        prefix = contract.memory_root + "/"
        listings: dict = {}
        resolved: dict[str, list[str]] = {}
        for raw, raw_carriers in _discover_citations(source_root, contract, result, cancelled).items():
            carriers_for = resolved.setdefault(_on_disk_case(source_root, raw, listings), [])
            for carrier in raw_carriers:
                if carrier not in carriers_for and len(carriers_for) < CITED_BY_LIMIT:
                    carriers_for.append(carrier)
        for rel, carriers in sorted(resolved.items()):
            if cancelled():
                break
            full = source_root.joinpath(*rel.split("/"))
            try:
                st = full.lstat()
            except OSError:
                result.cited_by[rel] = list(carriers)
                if _names_absent_file(rel):
                    result.cited_missing.append(rel)
                else:
                    result.cited_ignored.append(rel)
                continue
            if stat_module.S_ISDIR(st.st_mode):
                result.cited_dirs.append(rel)
                result.cited_by[rel] = list(carriers)
                surface = next(
                    (s for s in contract.citations.surfaces if rel[len(prefix):].startswith(s + "/")),
                    "",
                )
                files, truncated = _cited_dir_files(
                    source_root, full, cap_by_surface.get(surface, CITED_DIR_MAX_FILES)
                )
                if truncated:
                    result.citation_truncated = True
                for file_rel in files:
                    require(file_rel, carriers)
                continue
            if not (stat_module.S_ISREG(st.st_mode) or stat_module.S_ISLNK(st.st_mode)):
                result.unreadable.append(rel)
                continue
            result.cited_files.append(rel)
            require(rel, carriers)

    result.conditional_found = sorted(
        rel for rel, tier in result.tier_of.items() if tier == TIER_CONDITIONAL
    )
    result.optional_found = sorted(
        rel for rel, tier in result.tier_of.items() if tier == TIER_OPTIONAL
    )
    return result


def evaluate(
    collection: EvidenceCollection,
    *,
    included: Optional[set] = None,
    reason_for=None,
) -> dict[str, Any]:
    """The machine-readable snapshot verdict.

    FAIL CLOSED: a project that IS a SAIPEN project and cannot produce the
    evidence its contract requires is reported PROTOCOL_INCOMPLETE. It is never
    silently downgraded to a healthy-looking package, because a reviewer
    reading a healthy package trusts what it does not contain.

    ``included`` is the FINAL package view: the set of source-relative paths
    that actually survived into the archive. When it is supplied, the verdict
    is decided by what the archive CONTAINS rather than by what the collector
    once found. That distinction is the whole point: discovery succeeding says
    nothing about an explicit exclude, a hard-safety rule, a fidelity budget
    trim or a size policy removing the file afterwards, and a "complete"
    verdict over an archive that lost required evidence is a lie a reviewer
    cannot detect from the archive itself.

    The rule, in one sentence:

        required = mandatory(contract) + conditional(discovered, because the
        contract makes a PRESENT artifact required); an archive missing any
        required artifact is never authoritative.

    ``reason_for(rel)`` lets the inventory name WHY a particular file was
    dropped (its own reason vocabulary), so the omission is actionable instead
    of merely counted. Optional evidence is reported and never degrades the
    verdict -- the contract said its absence is honest.
    """
    contract = collection.contract
    if not contract.detected:
        return {
            "detected": False,
            "status": STATUS_NOT_SAIPEN,
            "contract_version": None,
            "authoritative_state": False,
        }

    status = contract.status
    # If the contract was admitted as COMPATIBLE_DEGRADED (newer than
    # implemented but all capabilities structurally present), the status
    # becomes STATUS_COMPATIBLE_DEGRADED instead of STATUS_COMPLETE. Missing
    # evidence still degrades to PROTOCOL_INCOMPLETE. (MILESTONE K)
    if status == STATUS_COMPLETE and contract.admission == ManifestAdmission.COMPATIBLE_DEGRADED:
        status = STATUS_COMPATIBLE_DEGRADED
    final_view = included is not None

    def _reason(rel: str) -> str:
        if reason_for is None:
            return ""
        try:
            return str(reason_for(rel) or "")
        except Exception:  # pragma: no cover - a reason is never load-bearing
            return ""

    required: list[dict[str, Any]] = []
    optional_omitted: list[dict[str, Any]] = []
    mandatory_included = list(collection.mandatory_found)
    #: Queried by the package manifest: a mandatory document the ARCHIVE lacks
    #: is "missing" from the snapshot whatever removed it, while
    #: `omitted_required` says which stage did.
    mandatory_missing = list(collection.mandatory_missing)

    if final_view:
        final = set(included or ())
        mandatory_included = [rel for rel in contract.mandatory if rel in final]
        mandatory_missing = [rel for rel in contract.mandatory if rel not in final]
        for rel in contract.mandatory:
            if rel in final:
                continue
            if rel in collection.mandatory_missing:
                reason = REASON_EVIDENCE_ABSENT
            elif rel in collection.unreadable:
                reason = REASON_EVIDENCE_UNREADABLE
            else:
                reason = _reason(rel) or REASON_EVIDENCE_NOT_INVENTORIED
            required.append({"path": rel, "tier": TIER_MANDATORY, "reason": reason})
        for rel in collection.conditional_found:
            if rel in final:
                continue
            required.append(
                {
                    "path": rel,
                    "tier": TIER_CONDITIONAL,
                    "reason": _reason(rel) or REASON_EVIDENCE_NOT_INVENTORIED,
                }
            )
        # The contract itself is required evidence: without it a reviewer can
        # neither reproduce nor audit the verdict it is reading.
        if MANIFEST_REL not in final:
            required.append(
                {
                    "path": MANIFEST_REL,
                    "tier": TIER_CONTRACT,
                    "reason": _reason(MANIFEST_REL) or REASON_EVIDENCE_NOT_INVENTORIED,
                }
            )
        # A cited file the archive lacks is omitted whichever rule found it;
        # one entry per file, naming the closure records that cite it.
        for entry in required:
            if entry["path"] in collection.cited_by:
                entry["cited_by"] = list(collection.cited_by[entry["path"]])
        reported = {entry["path"] for entry in required}
        for rel in collection.cited_required:
            if rel in final or rel in reported:
                continue
            required.append(
                {
                    "path": rel,
                    "tier": TIER_CITED,
                    "reason": _reason(rel) or REASON_EVIDENCE_NOT_INVENTORIED,
                    "cited_by": list(collection.cited_by.get(rel, [])),
                }
            )
        for rel in collection.optional_found:
            if rel in final:
                continue
            optional_omitted.append(
                {
                    "path": rel,
                    "tier": TIER_OPTIONAL,
                    "reason": _reason(rel) or REASON_EVIDENCE_NOT_INVENTORIED,
                }
            )

    # Cited evidence that never existed cannot be in ANY archive, so it is an
    # omission in both views: the closure claims proof the snapshot lacks.
    for rel in collection.cited_missing:
        required.append(
            {
                "path": rel,
                "tier": TIER_CITED,
                "reason": REASON_EVIDENCE_ABSENT,
                "cited_by": list(collection.cited_by.get(rel, [])),
            }
        )

    if status == STATUS_COMPLETE:
        if collection.mandatory_missing or collection.unreadable:
            status = STATUS_PROTOCOL_INCOMPLETE
        elif collection.truncated_conditional:
            status = STATUS_PROTOCOL_INCOMPLETE
        elif collection.citation_truncated or collection.unreadable_carriers:
            # A citation discovery that stopped early cannot certify the rest.
            status = STATUS_PROTOCOL_INCOMPLETE
        elif required:
            status = STATUS_PROTOCOL_INCOMPLETE
        elif optional_omitted or collection.truncated_optional:
            status = STATUS_COMPLETE_WITH_OPTIONAL_OMISSIONS
    elif status == STATUS_COMPATIBLE_DEGRADED:
        # COMPATIBLE_DEGRADED: treated like COMPLETE for the verdict, but the
        # admission metadata is preserved. If evidence is missing, degrade to
        # PROTOCOL_INCOMPLETE.
        if collection.mandatory_missing or collection.unreadable:
            status = STATUS_PROTOCOL_INCOMPLETE
        elif collection.truncated_conditional:
            status = STATUS_PROTOCOL_INCOMPLETE
        elif collection.citation_truncated or collection.unreadable_carriers:
            status = STATUS_PROTOCOL_INCOMPLETE
        elif required:
            status = STATUS_PROTOCOL_INCOMPLETE
        # optional_omitted is allowed in COMPATIBLE_DEGRADED

    authoritative = status in (
        STATUS_COMPLETE,
        STATUS_COMPLETE_WITH_OPTIONAL_OMISSIONS,
        STATUS_COMPATIBLE_DEGRADED,
    )
    final_set = set(included or ())
    evidence_in_archive = (
        sum(1 for rel in collection.paths if rel in final_set)
        if final_view
        else len(collection.paths)
    )
    rules = contract.citations
    citations = {
        "rules_source": rules.source if rules is not None else None,
        "surfaces": list(rules.surfaces) if rules is not None else [],
        "carriers_scanned": collection.carriers_scanned,
        "carrier_bytes_scanned": collection.carrier_bytes_scanned,
        "cited_files": sorted(collection.cited_files),
        "cited_dirs": sorted(collection.cited_dirs),
        "cited_missing_on_disk": sorted(collection.cited_missing),
        "cited_ignored": sorted(collection.cited_ignored),
        "cited_required": len(collection.cited_required),
        "cited_in_archive": (
            sum(1 for rel in collection.cited_required if rel in final_set)
            if final_view
            else None
        ),
        "cited_by": {rel: list(carriers) for rel, carriers in sorted(collection.cited_by.items())},
        "truncated": collection.citation_truncated,
        "unreadable_carriers": sorted(collection.unreadable_carriers),
    }
    return {
        "detected": True,
        "status": status,
        "authoritative_state": authoritative,
        "contract_version": contract.contract_version,
        "protocol_version": contract.protocol_version,
        "manifest_generated_at": contract.generated_at,
        "generator": contract.generator,
        "verdict_basis": (
            "final_archive_content" if final_view else "discovery_only"
        ),
        "admission": contract.admission,
        "admission_missing": contract.admission_missing,
        "evidence_files_collected": len(collection.paths),
        "evidence_files_in_archive": evidence_in_archive,
        "mandatory_declared": list(contract.mandatory),
        "required_declared": list(contract.required),
        "compatibility": contract.compatibility_policy,
        "mandatory_included": mandatory_included,
        "mandatory_missing": mandatory_missing,
        "truncated_dirs": list(collection.truncated_dirs),
        "truncated_required_dirs": list(collection.truncated_conditional),
        "truncated_optional_dirs": list(collection.truncated_optional),
        "unreadable": list(collection.unreadable),
        "required_evidence_omitted": bool(required),
        "omitted_required": required,
        "omitted_optional": optional_omitted,
        "evidence_citations": citations,
        "non_exportable": list(contract.non_exportable),
        "detail": contract.detail,
    }


def collect_for_inventory(source_root: Path, cancel_event=None) -> EvidenceCollection:
    """One call for inventory builders: read the contract, then collect."""
    return collect(source_root, read_contract(source_root), cancel_event=cancel_event)


__all__ = [
    "MANIFEST_REL",
    "MEMORY_ROOT",
    "ManifestAdmission",
    "SUPPORTED_CONTRACT_VERSION",
    "SUPPORTED_CONTRACT_VERSIONS",
    "V2_NON_EXPORTABLE_BASELINE",
    "REQUIRED_CAPABILITIES",
    "contract_unknown_detail",
    "check_capabilities",
    "check_capabilities_detail",
    "read_contract_from_document",
    "STATUS_COMPLETE",
    "STATUS_COMPLETE_WITH_OPTIONAL_OMISSIONS",
    "STATUS_PROTOCOL_INCOMPLETE",
    "STATUS_MANIFEST_ABSENT",
    "STATUS_MANIFEST_MALFORMED",
    "STATUS_CONTRACT_UNKNOWN",
    "STATUS_COMPATIBLE_DEGRADED",
    "STATUS_NOT_SAIPEN",
    "TIER_CONTRACT",
    "TIER_MANDATORY",
    "TIER_CONDITIONAL",
    "TIER_OPTIONAL",
    "TIER_CITED",
    "RULES_FROM_CONTRACT",
    "RULES_CONSUMER_DEFAULT",
    "CarrierRule",
    "CitationRules",
    "default_citation_rules",
    "REASON_EVIDENCE_ABSENT",
    "REASON_EVIDENCE_UNREADABLE",
    "REASON_EVIDENCE_NOT_INVENTORIED",
    "REASON_EVIDENCE_UNSUPPORTED",
    "REASON_DIR_TRUNCATED",
    "REASON_SAIPEN_NON_EXPORTABLE",
    "REASON_SAIPEN_UNDECLARED",
    "is_non_exportable",
    "export_decision",
    "EXPORT_PRECEDENCE",
    "DirRule",
    "SaipenContract",
    "EvidenceCollection",
    "detect",
    "read_contract",
    "read_contract_from_document",
    "parse_contract_v1",
    "parse_contract_v2",
    "collect",
    "collect_for_inventory",
    "evaluate",
]
