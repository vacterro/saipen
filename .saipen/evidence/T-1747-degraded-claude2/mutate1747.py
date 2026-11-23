"""Mutation controls for T-1747: each mutation must turn a named test red."""
import json, os, re, subprocess, sys
from pathlib import Path

post = Path(sys.argv[1]); live = Path(sys.argv[2]); profile = sys.argv[3]
NL = chr(10)
FILES = {
    "saipen.py": "tools/saipen.py",
    "host_authority_client.py": "tools/saipen_engine/host_authority_client.py",
    "host_taxonomy.py": "tools/saipen_engine/host_taxonomy.py",
    "protocol_admission.py": "tools/saipen_engine/protocol_admission.py",
    "runtime_bootstrap.py": "tools/saipen_engine/runtime_bootstrap.py",
    "host_integration.py": "tools/saipen_engine/host_integration.py",
}

def norm(text):
    return text.replace(chr(13) + NL, NL)

base = {name: norm((live / rel).read_bytes().decode("utf-8")) for name, rel in FILES.items()}

def write(texts):
    for name, rel in FILES.items():
        (post / rel).write_bytes(texts[name].encode("utf-8"))

def run():
    env = dict(os.environ)
    for key in [k for k in env if k.startswith("SAIPEN")]:
        del env[key]
    env.update(USERPROFILE=profile, HOME=profile, PYTHONUTF8="1", CLAUDE_CONFIG_DIR=profile + "/.claude")
    proc = subprocess.run([sys.executable, "-B", "-m", "unittest", "test_t1747_degraded_profile"],
                          cwd=str(post / "tools"), env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300)
    reds = sorted(set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", proc.stderr, re.M)))
    ran = re.search(r"Ran (\d+) tests", proc.stderr)
    return reds, int(ran.group(1)) if ran else 0

MUTATIONS = [
    ("M1 notice keeps the table sentence", "host_authority_client.py",
     "            taxonomy.step_summary(taxonomy.as_step(item.get(\"step\")))" + NL + "            or item.get(\"summary\")",
     "            item.get(\"summary\")",
     "test_a_foreign_profile_hook_is_named_instead_of_a_silent_service"),
    ("M2 scoped repair never printed", "host_authority_client.py",
     "    if repair and action == taxonomy.REPAIR:", "    if False:",
     "test_the_short_marker_carries_the_scoped_command_too"),
    ("M3 scoped repair replaces every action", "host_authority_client.py",
     "    if repair and action == taxonomy.REPAIR:", "    if repair:",
     "test_a_scoped_repair_never_replaces_another_action"),
    ("M4 second profile gets the bare command", "protocol_admission.py",
     "    if ctx.host != \"claude\" or ctx.profile is None:", "    if True:",
     "test_a_second_profile_is_repaired_by_name"),
    ("M5 default profile gets a scoped command", "protocol_admission.py",
     "    if selected == os.path.normcase(os.path.abspath(base / \".claude\")):", "    if False:",
     "test_the_default_profile_and_other_hosts_keep_the_bare_command"),
    ("M6 host repair drops the flag again", "saipen.py",
     "        if sub == \"repair\" and dry_run:", "        if False:",
     "test_host_repair_answers_a_dry_run_with_the_doctor_report"),
    ("M7 writers without a plan run under the flag", "saipen.py",
     "    _writer = _install_surface_writer(args) if dry_run else None", "    _writer = None",
     "test_writers_with_no_plan_refuse_a_dry_run"),
    ("M8 a dry run refuses a real repair too", "saipen.py",
     "        if sub == \"repair\" and dry_run:", "        if sub == \"repair\":",
     "test_host_repair_without_the_flag_still_repairs"),
    ("M9 one identity step loses its sentence", "host_taxonomy.py",
     "    \"HOOK_NOT_FOUND\": \"No SAIPEN hook invocation was found above this process.\"," + NL, "",
     "test_every_identity_step_has_its_own_sentence"),
    ("M10 the cap may cut the command", "host_authority_client.py",
     "    return head[: max(0, 900 - len(tail))] + tail", "    return (head + tail)[:900]",
     "test_the_cap_is_never_spent_on_the_command"),
    ("M11 host mode writes under the flag", "saipen.py",
     "        if dry_run and positional:", "        if False:",
     "test_host_mode_refuses_whatever_precedes_its_value"),
    ("M12 freshness judged on the default profile", "runtime_bootstrap.py",
     "    return None if _norm(selected) == _norm(home / \".claude\") else selected", "    return None",
     "test_prelaunch_measures_and_resyncs_the_profile_the_host_starts_with"),
    ("M13 the default profile treated as a second one", "runtime_bootstrap.py",
     "    return None if _norm(selected) == _norm(home / \".claude\") else selected", "    return selected",
     "test_prelaunch_without_a_carrier_keeps_the_default_profile"),
    ("M14 the doctor keeps the table sentence", "host_integration.py",
     "    summary = taxonomy.step_summary(step) or (", "    summary = None or (",
     "test_a_foreign_profile_hook_is_named_by_the_doctor"),
]
report = {"control": [], "mutations": []}
write(base)
for rep in range(2):
    reds, ran = run(); report["control"].append({"ran": ran, "reds": reds})
bad = 0
for label, name, old, new, expect in MUTATIONS:
    assert base[name].count(old) == 1, (label, base[name].count(old))
    texts = dict(base); texts[name] = base[name].replace(old, new); write(texts)
    results = [run()[0] for _ in range(2)]
    ok = results[0] == results[1] and expect in results[0]
    bad += 0 if ok else 1
    report["mutations"].append({"mutation": label, "expected_red": expect, "detected": expect in results[0], "stable": results[0] == results[1], "reds": results[0]})
write(base)
report["undetected_or_unstable"] = bad
print(json.dumps(report, indent=1))
