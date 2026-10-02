import sys, unittest, inspect, textwrap
sys.path.insert(0, r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\tools")
import saipen_engine.log as L, saipen_engine.operations as O
import test_log_tail_quarantine as T
T.setUpModule()
orig_src = inspect.getsource(L.foreign_tail_cut)
def run(names):
    suite = unittest.TestSuite(T.QuarantineLogTailTests(n) for n in names)
    r = unittest.TextTestRunner(verbosity=0, stream=open("nul","w")).run(suite)
    return len(r.failures) + len(r.errors)
def mutate(old, new):
    src = orig_src.replace(old, new)
    assert src != orig_src, old
    ns = dict(L.__dict__); exec(src, ns); L.foreign_tail_cut = ns["foreign_tail_cut"]
# M1: drop the above-tail refusal
mutate("if declared > last_event:", "if False:")
print("M1 above-tail check removed ->", run(["test_a_suffix_id_above_the_tail_is_never_cut"]), "red")
# M2: drop the prefix-contract proof
mutate("remaining = snapshot_contract_errors(clean)", "remaining = []")
print("M2 prefix proof removed ->", run(["test_damage_before_the_tail_still_refuses"]), "red")
# M3: anchor on the LAST occurrence instead of the first
mutate("for index, line in enumerate(lines)\n", "for index, line in reversed(list(enumerate(lines)))\n")
print("M3 last-occurrence anchor ->", run(["test_the_cut_keeps_the_ledger_and_records_itself"]), "red")
