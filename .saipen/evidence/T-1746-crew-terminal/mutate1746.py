"""Mutation controls for T-1746: each mutation must turn a named test red."""
import json, os, re, subprocess, sys
from pathlib import Path

post = Path(sys.argv[1])
live = Path(sys.argv[2])
profile = sys.argv[3]
ENG = post / "tools" / "saipen_engine"
FILES = ["release.py", "crew.py", "operations.py"]
NL = chr(10)

def norm(text):
    return text.replace(chr(13) + NL, NL)

def pristine():
    out = {}
    for name in FILES:
        out[name] = norm((live / "tools" / "saipen_engine" / name).read_bytes().decode("utf-8"))
    return out

def run():
    env = dict(os.environ)
    for key in [k for k in env if k.startswith("SAIPEN")]:
        del env[key]
    env.update(USERPROFILE=profile, HOME=profile, PYTHONUTF8="1",
               CLAUDE_CONFIG_DIR=profile + "/.claude")
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "test_t1746_crew_terminal_outcome"],
        cwd=str(post / "tools"), env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=600)
    reds = sorted(set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", proc.stderr, re.M)))
    ran = re.search(r"Ran (\d+) tests", proc.stderr)
    return reds, int(ran.group(1)) if ran else 0

MUTATIONS = [
    ("M01 versionless route never admitted", "release.py",
     "    return state.get(\"execution_intent\") == \"converge\" and state.get(\"converge_target\") == \"crew\"",
     "    return False",
     "test_versionless_ticketless_epoch_closes_locally"),
    ("M02 ticketless epoch never owned", "release.py",
     "    epoch_owned = bool(crew_epoch) and not cohort_id and mode == \"no-publish\"",
     "    epoch_owned = False",
     "test_a_ticketless_epoch_of_a_versioned_project_keeps_its_version"),
    ("M03 scope compared by the 16-hex token", "release.py",
     "    return release_scope_matches(live, expected)",
     "    return _quick_hash(live) == expected",
     "test_a_scope_deferred_with_full_identities_is_not_read_as_changed"),
    ("M04 completion chosen from STATE.mode", "crew.py",
     "    mode = release.mode or \"full\"",
     "    mode = snapshot.state.get(\"mode\") or \"full\"",
     "test_the_verdict_names_a_local_closure_under_a_persisted_full_mode"),
    ("M05 receipt ticket not compared with the epoch", "crew.py",
     "    if epoch is not None and (release.ticket or \"\") != (epoch.ticket or \"\"):",
     "    if False:",
     "test_a_receipt_naming_a_ticket_the_epoch_does_not_own_cannot_certify"),
    ("M06 carrier never checked against the durable epoch", "release.py",
     "    if durable is None:" + NL + "        return None" + NL + "    if durable[\"op_id\"] != crew_epoch:",
     "    if True:" + NL + "        return None" + NL + "    if durable[\"op_id\"] != crew_epoch:",
     "test_a_carrier_naming_a_ticket_the_epoch_does_not_own_is_refused"),
    ("M07 plan epoch not rechecked at apply", "release.py",
     "        if crew_context[\"crew_epoch\"] != plan.crew_epoch or (",
     "        if False and (",
     "test_a_ticket_that_appears_between_plan_and_apply_writes_nothing"),
    ("M08 second closure admitted", "release.py",
     "            if settled[\"status\"] == \"ok\":",
     "            if False:",
     "test_a_second_closure_of_a_verified_epoch_is_refused"),
    ("M09 aborted sibling counted", "release.py",
     "        if record.get(\"status\") == \"ABORTED\":",
     "        if False:",
     "test_a_refused_local_validation_does_not_poison_the_epoch"),
    ("M10 gate always project-local", "release.py",
     "    if local.is_file():" + NL + "        return [sys.executable, str(local), \"--gate\", gate]",
     "    if True:" + NL + "        return [sys.executable, str(local), \"--gate\", gate]",
     "test_a_managed_project_is_judged_by_the_runtimes_validator"),
    ("M11 producer edge not recorded", "crew.py",
     "    edge = _producer_integration_edge(snapshot, role)" + NL + "    if edge is None:" + NL + "        return []",
     "    edge = None" + NL + "    if edge is None:" + NL + "        return []",
     "test_an_integrated_producer_is_recorded_by_its_integration_edge"),
    ("M12 same-instant defers not judged", "crew.py",
     "            other[0] == key[0] and other[1] != key[1] and approved != expected",
     "            False and approved != expected",
     "test_two_defers_of_one_instant_approving_different_bytes_are_ambiguous"),
    ("M13 no source recheck before the local closure", "release.py",
     "        drift = _source_identity_drift(root, plan)" + NL + "        if drift:" + NL + "            return _release_failure(\"PREFLIGHT\", drift)" + NL + "        return {\"ok\": True}",
     "        return {\"ok\": True}",
     "test_a_foreign_source_change_between_plan_and_apply_writes_nothing"),
    ("M14 any ticketless receipt admitted", "release.py",
     "    if not record.get(\"ticket_id\") and not (mode == \"no-publish\" and record.get(\"crew_epoch\")):",
     "    if False:",
     "test_admission_of_a_ticketless_receipt_needs_a_local_epoch_closure"),
    ("M15 local closure worded as shipped", "release.py",
     "            published=plan.mode != \"no-publish\",",
     "            published=True,",
     "test_versionless_ticketless_epoch_closes_locally"),
    ("M16 versionless publication not refused at plan", "release.py",
     "    if version_refusal is not None and mode != \"no-publish\":",
     "    if False:",
     "test_missing_version_never_reaches_a_publication"),
    ("M17 ticketless publication refused under the old sentence", "release.py",
     "            if not crew_carrier[\"ticket_id\"] and mode != \"no-publish\":",
     "            if False:",
     "test_a_ticketless_epoch_cannot_publish_and_is_told_why"),
    ("M18 full-mode evidence never asked for HEAD proof", "crew.py",
     "    if snapshot.source_id is None:" + NL + "        return False, \"source identity unavailable\"",
     "    if False:" + NL + "        return False, \"source identity unavailable\"",
     "test_a_persisted_no_publish_mode_cannot_waive_the_proof_of_a_publication"),
]

def write(texts):
    for name, text in texts.items():
        (ENG / name).write_bytes(text.encode("utf-8"))

base = pristine()
report = {"control": [], "mutations": []}
write(base)
for rep in range(2):
    reds, ran = run()
    report["control"].append({"ran": ran, "reds": reds})
bad = 0
for label, name, old, new, expect in MUTATIONS:
    assert base[name].count(old) == 1, (label, base[name].count(old))
    texts = dict(base)
    texts[name] = base[name].replace(old, new)
    write(texts)
    results = []
    for rep in range(2):
        reds, ran = run()
        results.append(reds)
    stable = results[0] == results[1]
    detected = expect in results[0] and expect in results[1]
    if not (stable and detected):
        bad += 1
    report["mutations"].append({"mutation": label, "expected_red": expect, "detected": detected,
                                "stable": stable, "reds": results[0], "reds_second": results[1] if not stable else "same"})
write(base)
report["undetected_or_unstable"] = bad
print(json.dumps(report, indent=1))
