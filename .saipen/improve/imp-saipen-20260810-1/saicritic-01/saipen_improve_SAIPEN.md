agent: claude
role: critic
model_or_runtime: deepseek-reasoner
project: SAIPEN
saipen_version: 7.221.0
protocol_fingerprint: ded-4ae736e4
source_head: 39098bf
source_tree_fingerprint: saicritic-cycle-1
context_scope: tools/saipen_engine, tools/improve.py, tools/validate.py, saipen/CORE.md, saipen/IMPROVE.md
context_available: complete
report_status: complete

# SAICRITIC -- NITRO dogfood IV + Improve wave self-critique (T-603)

Full self-critique of the Improve mechanical layer against the four proof
levels: UNIT (operation locally correct), COMPOSITION (predecessor/successor
chain), CANONICAL (repository invariants), GATE (the required semantic gates
actually occurred). Every claim below is classified with FRESH evidence from
the current wave's gate suite (run_scenarios 68 improve + 171 nitro-integrity,
validate PASS, audit 240/240, parity 240/240).

IMP-001 [P0] [PROTOCOL_VIOLATION] [reproduced] [ticket]
expected: the five saipen improve routes registered in CORE 1.10 and the
  validator surface are executable commands
actual: `saipen improve status` exits "unknown command: improve"; the CLI
  (tools/saipen.py) has no improve route
evidence: `python tools/saipen.py improve status --json` -> exit 2,
  "unknown command: improve"; T-554's verify clause ("all five verbs resolve
  in 1.10 and in validate.py's command surface check") is satisfied at the
  DOC/validator level only -- resolution is not execution
four_level: UNIT PROVEN (command-surface check + [improve-command-family] red
  controls); COMPOSITION N/A; CANONICAL PROVEN (validator green); GATE NOT
  PROVEN (the command cannot run, so its claimed behavior is not executable
  evidence)
recurrence: recurs across any protocol surface that registers a command
  without wiring the executor -- the register-then-implement split must be
  one act or the validator must fail a registered-but-unexecuted route
weak_model: a weak but compliant model reads "all five verbs resolve" and
  records the wave PASS without ever executing the command -- the fix must
  make an unexecutable registered route a validator FAIL, never prose

IMP-002 [P1] [LOGIC_ERROR] [reproduced] [ticket]
expected: the SubSaipen write boundary (a seat writes only inside its own
  home) is mechanically enforced on every path
actual: the boundary is enforced at admission (safeid containment, T-588)
  and stated as a doc marker ([improve-boundary], T-557), but no validator
  scan continuously proves a sub's artifacts never target main-project
  canonical files after admission
evidence: red control 7's named checks are the spawn-time path-escape probes
  plus the [improve-boundary] doc-drift marker -- neither scans a settled
  sub's OUTBOX/kitchen for main-project references
four_level: UNIT PROVEN (spawn containment); COMPOSITION N/A; CANONICAL
  PROVEN (validator green); GATE PARTIAL (admission-only enforcement, no
  continuous scan). The T-557 verify-bar claim that red control 7 is
  mechanical is itself ACCIDENTAL_SUCCESS: it is mechanical at admission
  only, and the continuous guarantee was never verified
weak_model: a weak but compliant model could believe "writes only inside its
  own home" is continuously enforced because admission refuses escapes;
  recording the boundary as a checked artifact overstates the continuous
  gate

IMP-003 [P2] [PROJECT_VIOLATION] [observed] [note]
expected: saipen improve verify (delta-only, no recursion) and saipen
  improve clean (archive-with-provenance) are executable
actual: both are spec + validator doc markers only (red 17/18/23); the
  delta-only/no-recursion/refuses-unswept guarantees are prose + markers,
  not running code -- the same register-without-executor gap as IMP-001
evidence: no improve route exists in tools/saipen.py; the [improve-boundary]
  markers enforce the DOCUMENT statements, not the behavior
four_level: UNIT N/A; COMPOSITION N/A; CANONICAL PROVEN (validator green);
  GATE NOT PROVEN (the commands cannot run)
