# T-1603 scenario instrument repair

The complete inherited scenario run reached 44 of 44 groups and 1351 checks.
It ended with nine executable failures. Seven goal probes omitted the operator
carrier now required by T-1600; one recovery probe still expected the two
resolution classes that preceded T-1398; the ninth was the nested perf gate
reporting the same seven goal failures. The subject engine is not classified as
failed for correctly refusing model-supplied goal preemption.

Scope: `tools/run_scenarios.py` only. Use the existing
`test_fixture_support.witnessed_operator` for three explicit-operator fixtures.
Add carrier-free controls using the same literal objectives, active Work, idle
Work and preserved execution counters. Require the existing third resolution
class, `reconcile`, and measure canonical bytes before and after inspection.
Production code, baseline, timeouts and complete discovery remain unchanged.
Rollback: restore only the owned scenario bytes from `run_scenarios.before.py`, which were
saved before the edit; keep all unrelated dirty paths intact.

The fixed external driver `run_pair.py` SHA256
`3918c1b07d3f0e155fc27df1e679983656ee05a8772f4b0455d9ff6d8d20e46f`
judges the scenario implementation, not an engine implementation change. It
uses the same real engine and installed-home context for both subjects:

- Original subject `c3771799a05d88a387d66a59ffbd348ec8656e9b77b3617d3f32114ca439a42e`:
  227 checks, eight failures (`red.json`, `red.txt`).
- Repaired subject `786e69f7d96cf857ad0383dcae62484a0a3906104491c72ab9d6d56ec07b638b`:
  230 checks, zero failures (`green.json`, `green.txt`).
- Deliberate unsafe model authority: 39 checks, three real failures
  (`bad-authority.json`, `bad-authority.txt`).
- Deliberate removal of `reconcile` from the real inspection result: 191
  checks, one real failure (`bad-conflict.json`, `bad-conflict.txt`).

The four subject production/helper hashes are identical across the pair.
These controls establish that the changed instrument can accept correct
behavior and reject both defect classes. They do not spend the old scenario
failure as proof of an engine repair. The first attempted driver import used
its physical evidence path as HOME and crashed before collecting controls; it
is not regression evidence. The fixed driver binds the same installed HOME.

Those aggregate gates were outstanding at BUILD. Their later terminal results
are recorded in `VERIFY.md`; this BUILD note is not their authority.
