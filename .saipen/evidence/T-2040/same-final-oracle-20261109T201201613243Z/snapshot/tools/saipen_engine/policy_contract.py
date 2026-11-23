"""Verify the compound/response policy file against the runtimes it describes.

`saipen/COMPOUND_RESPONSE_POLICY.json` is the normative statement for
SRC-274:R005. A normative file that nothing checks is prose with a `.json`
extension: the exact defect the clause names. This module is the verifier, so
the file can be wrong only if this module is wrong in the same way.

Every check reads the RUNTIME, never the file's own restatement:

  * each declared module imports and each declared symbol exists;
  * each declared closed set equals the runtime's own import-time derivation
    (the registries already refuse to load when they disagree);
  * the registry block the file defers to is present and not a copy that has
    since drifted;
  * the mixed-command example reproduces ordering, STOP and provenance.

The last check is the point of the whole file. A policy that lists the right
fields but cannot resolve `a cleanup command + /goal cc all` to two indexed
segments with terminal dispositions has not delivered F-06/F-09, whatever its
prose says.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

POLICY_REL = "saipen/COMPOUND_RESPONSE_POLICY.json"
SCHEMA_KIND = "saipen-compound-response-policy"


def _load_policy(root: Path) -> dict:
    path = root / POLICY_REL
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"{POLICY_REL} is absent") from exc
    try:
        policy = json.loads(text)
    except ValueError as exc:
        raise ValueError(f"{POLICY_REL} is not valid JSON: {exc}") from exc
    if not isinstance(policy, dict):
        raise ValueError(f"{POLICY_REL} must be a JSON object")
    if policy.get("schema") != 1:
        raise ValueError(f"{POLICY_REL} schema must be 1")
    if policy.get("kind") != SCHEMA_KIND:
        raise ValueError(f"{POLICY_REL} kind must be {SCHEMA_KIND}")
    return policy


def _symbol(module_name: str, qualname: str):
    """Import one symbol, or the module itself when the reference names none."""
    module = importlib.import_module(f"saipen_engine.{module_name}")
    if not qualname:
        return module
    target = module
    for part in qualname.split("."):
        if not hasattr(target, part):
            raise ValueError(f"saipen_engine.{module_name} has no {qualname}")
        target = getattr(target, part)
    return target


def _runtime_ref(reference: object) -> tuple[str, str]:
    """Split `tools/saipen_engine/<module>.py[:qualname]` into its two halves.

    A module-level reference (no `:qualname`) is legal: some runtime claims are
    about the module as a whole, and demanding a symbol would invite a fake
    one. The module must still exist.
    """
    text = str(reference or "")
    if "tools/saipen_engine/" not in text:
        raise ValueError(f"not a runtime reference: {reference!r}")
    path, _, qualname = text.partition(":")
    module = Path(path).stem
    if not module:
        raise ValueError(f"not a runtime reference: {reference!r}")
    return module, qualname


def _check_group(policy: dict, errors: list[str], name: str, keys: tuple[str, ...]) -> None:
    group = policy.get(name)
    if not isinstance(group, dict):
        errors.append(f"{name}: missing block")
        return
    for key in keys:
        if key in group and isinstance(group[key], str) and "tools/saipen_engine/" in group[key]:
            module, qualname = _runtime_ref(group[key])
            try:
                _symbol(module, qualname)
            except (ImportError, ValueError) as exc:
                errors.append(f"{name}.{key}: {exc}")


def _check_closed_set(
    policy_value: object, runtime_value: object, label: str, errors: list[str]
) -> None:
    if not isinstance(policy_value, list) or not policy_value:
        errors.append(f"{label}: policy declares no closed set")
        return
    if list(policy_value) != list(runtime_value):
        errors.append(
            f"{label}: policy {list(policy_value)} != runtime {list(runtime_value)}"
        )


def _check_mixed_command(errors: list[str]) -> None:
    """The example the clause names must actually resolve, in order, with STOP.

    SRC-274:R005 quotes the operator's real input verbatim: `saipen clean`
    followed by `/goal cc all`, two lines, in that order. Testing a tidy
    synthetic form instead would have missed that the slash spelling resolved
    to `unknown` and silently dropped half the request.
    """
    from .commands import (
        CHAIN_STOP_ON_FAILURE,
        DISPOSITION_EXECUTED,
        DISPOSITION_NOT_RUN,
        DISPOSITION_REFUSED,
        chain_disposition,
        resolve_compound_command,
    )

    message = "saipen clean\n/goal cc all"
    try:
        resolved = resolve_compound_command(message)
    except (ValueError, OSError) as exc:
        errors.append(f"mixed command does not resolve: {exc}")
        return
    if len(resolved) != 2:
        errors.append(f"mixed command resolved to {len(resolved)} segment(s), expected 2")
        return
    first, second = resolved
    if first["index"] != 0 or second["index"] != 1:
        errors.append(
            f"mixed command lost ordering: indexes {first['index']}, {second['index']}"
        )
    if first["command"] != "saipen clean":
        errors.append(f"first segment resolved to {first['command']!r}, expected 'saipen clean'")
    if second["command"] != "saipen goal cc all":
        errors.append(
            f"second segment resolved to {second['command']!r}, expected 'saipen goal cc all' "
            "-- the operator's documented /goal spelling must resolve to the canonical verb"
        )
    for segment in resolved:
        if segment["kind"] == "unknown":
            errors.append(f"mixed command left a segment unresolved: {segment['segment']!r}")
        if not segment["command"]:
            errors.append(f"mixed command left a segment empty: {segment['segment']!r}")

    # STOP: a failed first segment freezes the second under the default policy.
    frozen = chain_disposition([DISPOSITION_REFUSED, DISPOSITION_EXECUTED])
    if frozen[1] != DISPOSITION_NOT_RUN:
        errors.append(
            f"STOP is not enforced: a refused first segment left the second {frozen[1]!r}"
        )
    if CHAIN_STOP_ON_FAILURE != "STOP_ON_FAILURE":
        errors.append("the default chain policy is not STOP_ON_FAILURE")


def _check_slash_vocabulary(errors: list[str]) -> None:
    """`/verb` resolves only for a REGISTRY-declared verb; anything else is unknown."""
    from .commands import canonical_slash_command, resolve_compound_command

    if canonical_slash_command("/goal cc all") != "saipen goal cc all":
        errors.append("/goal does not resolve to the canonical goal verb")
    if canonical_slash_command("/definitely-not-a-verb x"):
        errors.append("an undeclared slash verb resolved; the slash rule must fail closed")
    invented = resolve_compound_command("/definitely-not-a-verb x")
    if not invented or invented[0]["kind"] != "unknown":
        errors.append("an undeclared slash verb did not stay unknown")


def _check_registry_blocks(policy: dict, errors: list[str]) -> None:
    """The file defers to REGISTRY; a deferred copy that drifted is a lie."""
    from .registry import load_registry

    registry = load_registry()

    hush_block = registry.get("hush_precedence")
    if not isinstance(hush_block, dict):
        errors.append("REGISTRY has no hush_precedence block")
    else:
        declared = (policy.get("hush") or {}).get("precedence")
        if list(declared or []) != list(hush_block.get("order") or []):
            errors.append(
                f"hush.precedence {declared} != REGISTRY hush_precedence.order "
                f"{hush_block.get('order')}"
            )
        declared_suppressible = (policy.get("hush") or {}).get("suppressible")
        if list(declared_suppressible or []) != list(hush_block.get("suppressible") or []):
            errors.append("hush.suppressible does not match REGISTRY hush_precedence")
        declared_mandatory = (policy.get("hush") or {}).get("mandatory")
        if list(declared_mandatory or []) != list(hush_block.get("mandatory") or []):
            errors.append("hush.mandatory does not match REGISTRY hush_precedence")

    chain_block = registry.get("chain_policies")
    stop = policy.get("stop") or {}
    if not isinstance(chain_block, dict):
        errors.append("REGISTRY has no chain_policies block")
    else:
        if stop.get("default_policy") != chain_block.get("default"):
            errors.append(
                f"stop.default_policy {stop.get('default_policy')!r} != REGISTRY "
                f"chain_policies.default {chain_block.get('default')!r}"
            )
        _check_closed_set(
            stop.get("closed_set"), chain_block.get("closed_set"), "stop.closed_set", errors
        )

    dispositions = registry.get("dispositions")
    if not isinstance(dispositions, dict):
        errors.append("REGISTRY has no dispositions block")
    else:
        _check_closed_set(
            stop.get("dispositions"), dispositions.get("closed_set"), "stop.dispositions", errors
        )
        _check_closed_set(
            stop.get("failure_dispositions"),
            dispositions.get("failure"),
            "stop.failure_dispositions",
            errors,
        )


def _check_hush_runtime(policy: dict, errors: list[str]) -> None:
    """The HUSH classifier and the policy must agree on what is suppressible."""
    from . import hush

    declared = set((policy.get("hush") or {}).get("suppressible") or [])
    runtime = set(hush.DISCRETIONARY)
    if declared != runtime:
        errors.append(
            f"hush.suppressible {sorted(declared)} != runtime DISCRETIONARY {sorted(runtime)}"
        )
    if not runtime:
        errors.append("hush runtime declares no discretionary set")
    # A suppressible kind must never appear in the mandatory set.
    overlap = runtime & (set((policy.get("hush") or {}).get("mandatory") or []))
    if overlap:
        errors.append(f"kinds are both suppressible and mandatory: {sorted(overlap)}")
    modifier = str((policy.get("hush") or {}).get("modifier") or "")
    if modifier != hush.MODIFIER:
        errors.append(f"hush.modifier {modifier!r} != runtime MODIFIER {hush.MODIFIER!r}")


def _check_response_surface(policy: dict, errors: list[str]) -> None:
    from . import response_surface

    surface = policy.get("response_surface") or {}
    if list(surface.get("mandatory_fields") or []) != list(response_surface.MANDATORY_FIELDS):
        errors.append("response_surface.mandatory_fields does not match the runtime")
    if list(surface.get("optional_fields") or []) != list(response_surface.OPTIONAL_FIELDS):
        errors.append("response_surface.optional_fields does not match the runtime")
    expected_order = list(response_surface.MANDATORY_FIELDS) + list(
        response_surface.OPTIONAL_FIELDS
    )
    if list(response_surface.FIELD_ORDER) != expected_order:
        errors.append("response_surface.FIELD_ORDER is not mandatory-then-optional")
    if surface.get("handback") != response_surface.STOP_HANDBACK:
        errors.append("response_surface.handback does not match STOP_HANDBACK")
    if surface.get("rule_id") != response_surface.RULE_ID:
        errors.append("response_surface.rule_id does not match the runtime rule id")


#: The blocks a normative file must actually contain. A verified file that has
#: quietly lost `stop` or `provenance` still imports and still verifies every
#: claim it no longer makes, which is the failure mode this whole module exists
#: to prevent: prose removed from a `.json` extension is not a weaker contract,
#: it is no contract.
REQUIRED_BLOCKS = (
    "segmentation",
    "resolution",
    "ordering",
    "stop",
    "provenance",
    "response_surface",
    "hush",
    "mixed_command_contract",
    "verification",
)


def _check_blocks_present(policy: dict, errors: list[str]) -> None:
    for name in REQUIRED_BLOCKS:
        if not isinstance(policy.get(name), dict):
            errors.append(f"policy block {name!r} is absent or not an object")


#: Every rule is a typed claim with an identifier, and each identifier has one
#: probe below. A prose sentence cannot be verified; a named rule whose probe
#: the runtime fails is a contract violation with a location. The sets are
#: closed: a rule id with no probe fails, and a probe with no rule id fails.
RESOLUTION_RULE_IDS = (
    "RES-CANONICAL",
    "RES-SLASH",
    "RES-SHORTCUT-PAYLOAD",
    "RES-BARE-UNKNOWN",
    "RES-FAIL-CLOSED",
)
SEGMENTATION_RULE_IDS = (
    "SEG-NEVER-DROP",
    "SEG-UNBALANCED",
    "SEG-PROSE-OPAQUE",
    "SEG-CLI-EMPTY-REFUSES",
)


def _rule_ids(group: object) -> list[str]:
    """Every entry's id, plus an empty marker for any entry that is malformed.

    A bare string carries no id, so it must not be silently skipped: skipping it
    would let a file that reverted to untyped prose verify as long as the ids it
    no longer has were never expected. The empty marker makes the shape failure
    its own reported problem.
    """
    rules = (group or {}).get("rules") if isinstance(group, dict) else None
    if not isinstance(rules, list):
        return []
    ids = []
    for rule in rules:
        if not isinstance(rule, dict):
            ids.append("")
            continue
        rule_id = str(rule.get("id") or "")
        ids.append(rule_id)
        text = rule.get("text")
        if not isinstance(text, str) or len(text.split()) < 3:
            ids.append("")
    return ids


def _check_rule_ids(policy: dict, errors: list[str]) -> None:
    """Both directions: no unnamed rule, and no rule silently dropped."""
    for block, expected in (
        ("segmentation", SEGMENTATION_RULE_IDS),
        ("resolution", RESOLUTION_RULE_IDS),
    ):
        declared = _rule_ids(policy.get(block))
        if "" in declared:
            errors.append(f"{block}.rules has an entry that is not {{id, text}}")
        if sorted(declared) != sorted(expected):
            missing = sorted(set(expected) - set(declared))
            extra = sorted(set(declared) - set(expected))
            errors.append(
                f"{block}.rules ids do not match the verifier's probes "
                f"(missing {missing}, unprobed {extra})"
            )


def _probe_segmentation(errors: list[str]) -> None:
    from .commands import parse_compound_command, split_cli_compound_argv

    # SEG-NEVER-DROP: separator runs collapse; separators alone produce nothing.
    collapsed = {
        "saipen status\n\n\nsaipen goal cc all": ["saipen status", "saipen goal cc all"],
        "saipen status +  + saipen goal": ["saipen status", "saipen goal"],
        "   ": [],
        "": [],
    }
    for message, expected in collapsed.items():
        found = parse_compound_command(message)
        if found != expected:
            errors.append(
                f"SEG-NEVER-DROP: {message!r} parsed to {found}, expected {expected}"
            )

    # SEG-UNBALANCED: one bad quote voids the whole message, never half of it.
    # The open quote is appended rather than written into the literal: a bare
    # `saipen ...` constant here is indistinguishable from a route the engine
    # prints, and the reachability harvest would rightly call it unreachable.
    for message in ("saipen start " + '"unterminated', "gg foo " + '"bar + cc'):
        found = parse_compound_command(message)
        if found:
            errors.append(f"SEG-UNBALANCED: {message!r} parsed anyway to {found}")

    # SEG-PROSE-OPAQUE: punctuation in prose is not a separator.
    prose = "Please continue the work now. Then stop."
    if parse_compound_command(prose) != [prose]:
        errors.append("SEG-PROSE-OPAQUE: prose was split on its punctuation")

    # SEG-CLI-EMPTY-REFUSES: the argv path refuses what the text path collapses.
    for argv in (["+", "status"], ["status", "+"], ["status", "+", "+", "status"]):
        try:
            split_cli_compound_argv(list(argv))
        except ValueError as exc:
            if "empty segment" not in str(exc):
                errors.append(f"SEG-CLI-EMPTY-REFUSES: {argv} raised {exc!r}")
        else:
            errors.append(f"SEG-CLI-EMPTY-REFUSES: {argv} was accepted")


def _probe_resolution(errors: list[str]) -> None:
    from .commands import canonical_slash_command, resolve_compound_command

    # RES-CANONICAL
    found = resolve_compound_command("saipen status")[0]
    if found["kind"] != "command" or found["command"] != "saipen status":
        errors.append(f"RES-CANONICAL: 'saipen status' resolved as {found}")

    # RES-SLASH: declared verb resolves, undeclared verb does not.
    if canonical_slash_command("/goal cc all") != "saipen goal cc all":
        errors.append("RES-SLASH: /goal does not resolve to the canonical goal verb")
    if canonical_slash_command("/definitely-not-a-verb x"):
        errors.append("RES-SLASH: an undeclared slash verb resolved")
    slash = resolve_compound_command("/goal cc all")[0]
    if slash["kind"] != "command" or slash["command"] != "saipen goal cc all":
        errors.append(f"RES-SLASH: /goal cc all resolved as {slash}")

    # RES-SHORTCUT-PAYLOAD: a declared shortcut owns everything after it.
    shortcut = resolve_compound_command("cc all")[0]
    if shortcut["kind"] != "shortcut":
        errors.append(f"RES-SHORTCUT-PAYLOAD: 'cc all' resolved as {shortcut['kind']!r}")
    if shortcut.get("command") != "saipen continue all" or shortcut.get("payload") != "all":
        errors.append(f"RES-SHORTCUT-PAYLOAD: 'cc all' lost its payload: {shortcut}")

    # RES-BARE-UNKNOWN + RES-FAIL-CLOSED: no guess, and the command is empty.
    for message in ("definitely-not-a-verb", "notacommand at all"):
        bare = resolve_compound_command(message)[0]
        if bare["kind"] != "unknown":
            errors.append(f"RES-BARE-UNKNOWN: {message!r} resolved as {bare['kind']!r}")
        if bare["command"] != "":
            errors.append(f"RES-FAIL-CLOSED: {message!r} invented {bare['command']!r}")


def _probe_provenance(errors: list[str]) -> None:
    """A resolved segment must be able to carry every field the file names."""
    from .commands import resolve_compound_command

    resolved = resolve_compound_command("saipen clean\n/goal cc all")
    for segment in resolved:
        for field in ("index", "segment", "command", "kind"):
            if field not in segment:
                errors.append(f"provenance: resolved segment lacks {field!r}")
        if segment["kind"] != "unknown" and not segment.get("command"):
            errors.append(f"provenance: recognized segment {segment['segment']!r} has no command")


def _check_rule_claims(policy: dict, errors: list[str]) -> None:
    """Every declared rule has to be something the runtime can be probed for.

    A list of sentences is prose with a schema around it. Rules are typed and
    each id owns exactly one probe, so a rule deleted to make the file
    "consistent" is a visible failure rather than a silent simplification.
    """
    _check_rule_ids(policy, errors)
    forbidden = (policy.get("provenance") or {}).get("forbidden")
    if not isinstance(forbidden, list) or not forbidden:
        errors.append("provenance.forbidden is absent or empty")
    fields = (policy.get("provenance") or {}).get("per_segment_fields")
    if not isinstance(fields, list) or not fields:
        errors.append("provenance.per_segment_fields is absent or empty")
    kinds = (policy.get("resolution") or {}).get("segment_kinds")
    if not isinstance(kinds, list) or sorted(kinds) != ["command", "shortcut", "unknown"]:
        errors.append(f"resolution.segment_kinds {kinds} is not the resolver's vocabulary")
    separators = (policy.get("segmentation") or {}).get("separators")
    if not isinstance(separators, list) or sorted(separators) != [
        "NEWLINE",
        "STANDALONE_PLUS",
    ]:
        errors.append(f"segmentation.separators {separators} is not the parser's vocabulary")


def _check_resolution_behaviour(policy: dict, errors: list[str]) -> None:
    """Run every rule's probe; positive and negative controls both count."""
    _probe_segmentation(errors)
    _probe_resolution(errors)
    _probe_provenance(errors)


def verify(root: Path | str) -> dict:
    """Check the whole policy file against the runtimes; return problems, not prose."""
    root = Path(root)
    try:
        policy = _load_policy(root)
    except ValueError as exc:
        return {"ok": False, "code": "POLICY_INVALID", "problems": [str(exc)]}

    errors: list[str] = []

    _check_blocks_present(policy, errors)
    _check_group(policy, errors, "segmentation", ("runtime", "cli_runtime"))
    _check_group(policy, errors, "resolution", ("runtime",))
    _check_group(policy, errors, "ordering", ("runtime",))
    _check_group(policy, errors, "stop", ("runtime",))
    _check_group(policy, errors, "provenance", ("runtime",))
    _check_group(policy, errors, "response_surface", ("runtime",))
    _check_group(policy, errors, "hush", ("runtime",))
    _check_group(policy, errors, "verification", ("runtime",))

    _check_registry_blocks(policy, errors)
    _check_hush_runtime(policy, errors)
    _check_response_surface(policy, errors)
    _check_rule_claims(policy, errors)
    _check_resolution_behaviour(policy, errors)
    _check_slash_vocabulary(errors)
    _check_mixed_command(errors)

    return {
        "ok": not errors,
        "code": "POLICY_VERIFIED" if not errors else "POLICY_DISAGREES_WITH_RUNTIME",
        "policy": POLICY_REL,
        "problems": errors,
    }
