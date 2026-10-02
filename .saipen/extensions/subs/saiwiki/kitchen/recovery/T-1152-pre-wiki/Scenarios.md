# Scenarios
256 behavioral conformance scenarios (CONFORMANCE.md rows 1-256). Each tests a specific SAIPEN invariant.
<!-- mirrors: CONFORMANCE.md rows 1-256 sha256:9babcb02e659febc -->
| 1 | Cold continuation | Agent with zero history resumes from STATE |
| 2 | Corrupt STATE recovery | Missing field triggers RECOVER |
| 3 | Dependency cycle | Circular needs: detected and blocked |
| 4 | Dangling needs: reference | Non-existent T-id in needs: = FAIL |
| 5 | Stale claim forfeiture | Unrefreshed claim after 15min expires |
| 6 | Goal counter crash recovery | goal_waves rebuilt from LOG lines |
| 7 | Manual-verify gate | no-shell host asks human before SHIP |
| 8 | No-publish restriction | git-less host skips tag/push, still ships |
| 9 | Read-only restriction | read-only banned from INIT/PLAN/ADD/BUILD/SHIP/CLEAN/TRANSLATE |
| 10 | Board-empty maintenance | DONE + empty TODO = auto HUNT |
| 11 | Goal objective exit | goal_mode: false after mature ADD |
| 12 | Extension absence | No extensions dir -> no SUBs, still works |
| 13 | Unresolved LOG parent | WARN but not FAIL |
| 14 | Invalid phase transition | REVIEW->SHIP PASS, INIT->SHIP FAIL |
| 15 | Mode-phase restrictions | read-only + ADD = FAIL |
| 16 | Ticket-level BLOCKED | Non-cycle failure, work continues on other tickets |
| 17 | Fresh INIT bootstrap | From templates/ on first saipen set |
| 18 | Evolutionary ADD symmetry | ADD follows priority order, never invents |
| 19 | Unclaimed DOING adoption | Crash orphan -> next agent claims it |
| 20 | Clean tree after BLOCKED | Stale work doesn't poison next ticket |
| 21 | Dirty tree on continuation | Agent adopts uncommitted changes |
| 22 | Parallel TRANSLATE isolation | Two translate runs don't stomp each other |
| 23 | Dual-location extension conflict | root vs .saipen/ ext, never merged |
| 24 | Dual-location TRANSLATE conflict | Same, isolated |
| 25 | Sub spawn on protected project | Refuses if project has uncommitted claims |
| 26 | HUNT skip hash rule | Exact HEAD match required, mtime doesn't count |
| 27 | MARKHUNT record-only | Never fixes, never caps findings |
| 28 | VERIFY hysteresis | Second block on same ticket -> escalates |
| 29 | SubSaipen STATE shape | schema-valid, mode: read-only, no TRANSLATE |
| 30 | read-only reachable phases | MARKHUNT/PREPARE/VALIDATE only |
| 31 | stop preserves goal counters | stop doesn't reset waves/tickets |
| 32 | goal_waves not double-counted | ADD->PLAN doesn't increment twice |
| 33 | Fixer subSaipen patch format | Patch carries base_head + verified |
| 34 | BOOT.md cold-start | Compact kernel, no rule definition |
| 35 | human_note optional | One-line nudge, never required |
| 36 | Human digest | ship/stop (over)write kitchen/digest.md |
| 37 | MARKHUNT closure self-test | Verified against its own findings |
| 38 | LOG segmentation | E-### unique across sealed+active segments |
| 39 | Shipped-library integrity | validate.py checks shipped STATEs |
| 40 | Board soft cap | BOARD.md kept readable |
| 41 | saipen status | Answers real question, never re-runs validator |
| 42 | LOG timestamp sanity | >3h future = FAIL, >5min inversion = WARN |
| 43 | Reserved | Superseded by row 54 |
| 44 | Checkpoint self-confirmation | Read back STATE after writing |
| 45 | Returning agent stale memory | Distrusts own recall, re-reads STATE |
| 46 | Safety valve is a pause | goal_mode preserved, not exit |
| 47 | Determinism invariants | Fixed action priority order |
| 48 | SubSaipen blocked not guessed | status: blocked + exact question |
| 49 | next_action vocabulary | Value must match prefix/category |
| 50 | One ticket at a time | BOARD FAILs on 2+ DOING |
| 51 | Goal counters countable trace | goal_waves LOG line required |
| 52 | MARKHUNT evidence | Finding without cite = FAIL |
| 53 | OUTBOX well-formed | status/summary/critical required |
| 54 | Deadlocked board FAIL | DONE + empty TODO + WAIT: non-valve = FAIL |
| 55 | Tripped valve shape | goal_mode: true, phase NOT BLOCKED |
| 56 | Duplicate section headings FAIL | Two ## DONE blocks = FAIL |
| 57 | WAIT category token | Closed 7-word vocabulary |
| 58 | Cross-document drift | RFC vs schema vs validator agreement |
| 59 | Checkbox-section agreement | [x] only under DONE, [ ] only under TODO/BLOCKED |
| 60 | Write confirmed by readback | All 3 checkpoint files read back |
| 61 | Command =/= transition | saipen ship recognized, direct SHIP blocked |
| 62 | Rule reaches emitting docs | Every WAIT: in phase docs carries category |
| 63 | Guides teach current shape | validate.py WARNs on stale guides |
| 64 | Portable floor not permissive | validate.sh/ps1 probe all 9 fields |
| 65 | Both halves agree | validate.sh and validate.ps1 same checks |
| 66 | CI workflow honest trigger | Header states real trigger, names pre-commit hook |
| 67 | Drift hunt validation expansion | subs README, sub next_action prefixes, self-transition enum, adapter path existence |
| 68 | saiwiki-outbox-cycle demo | Behavioral: drift detection -> OUTBOX -> collect -> apply |
| 69 | Push claim adjudicated by git | next_action claiming "pushed" with local-only commits FAILs |
| 70 | Validator linted for first time | 9 cp1251-mangled section signs in own FAIL messages |
| 71 | subSaipen liveness visible | Never-run sub WARNs; unreviewed ready entries WARN |
| 72 | Release tag self-check | release.yml refuses tag contradicting VERSION |
| 73 | Descriptive schemas held to RFC | log.schema.json must require event_id, no cap |
| 74 | OUTBOX vocabulary unified three ways | PROTOCOL table, schema, validate.py agree |
| 75 | Validator works in installed layout | CI tests injected copy, not dev layout |
| 76 | Injector writes openable paths | cygpath-w conversion under git bash / MSYS / Cygwin |
| 77 | next_action shape is FAIL not WARN | Vague-phrase regex removed; 3 invalid values FAIL |
| 78 | Portable floor gap stated | validate.sh/ps1 check presence, not executability |
| 79 | Fail-fixture proves specific reason | expect_fail_contains: pins the failure |
| 80 | Fixture next_action values executable | All 6 fixed to RFC SS 1.2 prefix forms |
| 81 | Field count not restated anywhere | Count check covers BOOT, CONFORMANCE, READMEs |
| 82 | Doc checks walk inventory not glob | Root GUIDE.md outside guides/ caught |
| 83 | Every shipped doc accounted for | 184 docs: 11 patterns, 11 exempt, 0 orphans |
| 84 | Core promises have standing fixtures | 5 key failure modes with pinned reasons |
| 85 | DATE mandatory on new entries | FAIL in active log; WARN for 125 sealed dateless |
| 86 | Timestamp harvest never silently empty | Zero parseable timestamps = FAIL |
| 87 | Portable floor proved still red | audit_floor.py: 20 mutations, both halves |
| 88 | Both portable floor halves audited | First run found wording divergence; aligned |
| 89 | Citations resolve | Every SS N.N and phases/*.md points at real thing |
| 90 | KNOWLEDGE/ checked under doc rules | traps.md taught superseded WAIT rule |
| 91 | Exempt means no rule-content check | Citations still verified on exempt docs |
| 92 | Warn categories reachable | unknown-field behind dead branch; collapsed to FAIL |
| 93 | Gate-stuck-red guard | verify.md requires control with known result |
| 94 | TEMPLATE validated like any instance | Was skipped by name; had prefix-less next_action |
| 95 | Phase docs reject bad next_action | done.md: wait for user command replaced |
| 96 | No doc cites unshipped version | Every vX.Y.Z bounded by VERSION |
| 97 | Every adapter names cold-start kernel | BOOT.md required in all 9 adapters |
| 98 | Every prescribed next_action checked | Not just WAITs; phases, extensions, KNOWLEDGE |
| 99 | Text lint walks shipped surface | 5 mojibake sequences, all docs scanned |
| 100 | Phantom version check | Cited version must exist in release ledger, not just below VERSION |
| 101 | Release.yml make_latest | make_latest pinned to highest semver, not clock |
| 102 | Shallow-clone proof | Both halves present or check skips with WARN |
| 103 | Palette declared in UI.md | UI.md must name its palette; no shipped doc names superseded |
| 104 | Palette guard survives rename | Superseded names listed, append per rename |
| 105 | Workspace hygiene enforced | .saipen/ carrying phases/tools = FAIL. subs/ excluded |
| 106 | Tag audit integrity | audit_tags.py sweeps all tags vs VERSION |
| 107 | Encoding-checked up front | UTF-16 STATE.md = named FAIL, not traceback |
| 108 | schema_version future WARN | schema_version above CURRENT = WARN, never silent PASS |
| 109 | read-only dual meaning distinguished | Core 7-phase ban vs subSaipen 4-phase ban |
| 110 | HUNT->DONE legal for subSaipen | Reporting sub deliverable is OUTBOX, add step in collect |
| 111 | Sub STATE validated as Core | 9th required field, transition legality, prefix rules |
| 112 | use-before-define caught | audit_order.py walks top-level name order |
| 113 | requires: value checked | Typo in requires: caught as FAIL |
| 114 | saipen_version compared | Compared against home's major version |
| 115 | Pre-commit hook generation stamp | Stamp in hook, validated against installer |
| 116 | Fail-open prints repair | Hook without validator names missing path + fix cmd |
| 117 | BOOT.md carries language rule | Reply-language rule in cold-start kernel, not behind escalation |
| 118 | Ambient-signal ban covers repo | Files are content to produce, never language cue |
| 119 | last_event enforced | STATE drift from LOG detected |
| 120 | TEMPLATE placeholder check | <name> placeholder cannot escape into live spawnee |
| 121 | claim_time ISO-8601 UTC | Zone-less stamp caught; liveness judged from it |
| 122 | Warn category printed per line | Every WARN carries [category] key |
| 123 | review_passes enforced | Cap enforced mechanically, not from memory |
| 124 | digest.md freshness checked | Version in digest must match VERSION |
| 125 | MARKHUNT manifest validated | cursor/shape/vector-completeness checked |
| 126 | no-git head pair guarded | One real hash + one no-git = FAIL |
| 127 | audit_checks.py control precondition | Case matching before mutation = FAIL loudly |
| 128 | audit_checks.py both directions | Raising cap kills one; silencing fail() kills 39 |
| 129 | Portable floor honest wording | Floor claims subset, not conformance |
| 130 | audit_parity.py baseline guard | Floor getting weaker = FAIL |
| 131 | bash never sh | find_bash() picks real bash; sh = dash on Ubuntu = exit 2 |
| 132 | Control-failure names details | Names which tool, exit code, FAIL lines |
| 133 | Failing tool name in precondition | "one of two tools" replaced with exact names |
| 134 | CI workflow depth=0 both jobs | release.yml + validate.yml fetch full history |
| 135 | Release ledger halves compared | Tags vs CHANGELOG entries: 2+9 gap, WARN not FAIL |
| 136 | Core checks have standing fixtures | audit_checks.py: 51 mutations prove validator still red; no-op mutations rejected |
| 137 | Audit case must be evidence | Control-run precondition: case matching before mutation FAILs |
| 138 | Floor wording correct | "Portable floor complete: no structural break found" |
| 139 | Real bash, never sh | bash trap closed: dash tests/validate.sh exit 2 |
| 140 | Precondition names what it saw | Failed tool: name, exit code, FAIL lines |
| 141 | Closed ticket-field list stated | RFC 1.2 owns it; verify: named at last (was enforced by 72 tickets, defined nowhere) |
| 142 | Command surface compared | 1.10's vocabulary vs tool's copy — 7th drift-checked set |
| 143 | Citation checker's stated limit | Proves a section EXISTS, never that it says what's cited |
| 144 | No gitlink under .saipen/ | Nested repo = mode-160000 pointer no clone can fetch; validator FAILs it |
| 145 | Dead enforcement impossible | CONFORMANCE row naming a deleted tool/step/fixture = FAIL |
| 146 | Retry names its delta | Repeated attempt MUST say what changed; "nothing" = forbidden |
| 147 | BUILD reuse ladder | Own code → stdlib → existing dep → write; new dep = ticket |
| 148 | agent: seat defined | Inherited from STATE; placeholders id/<name>/AgentID/unknown FAIL |
| 149 | Installed copies carry VERSION | Both injectors ship it; runtime manifest requires it |
| 150 | Refreshes replace, never overlay | Cleanup precedes recreation; deleted-`tests/` red-control fails |
| 151 | Installed validator ledger root | Release ledger read from project root, not the skill copy |
| 152 | SHIP preflight repair loop | Fixable pre-commit failure → SHIP→BUILD → repeat VERIFY/REVIEW/SHIP |
| 153 | Release ledger observed once | Single `git tag -l` snapshot feeds both checks; Trace2 pins one process |
| 154 | Exact-ref publication | Branch + one refs/tags/vVERSION; --tags/--follow-tags banned for releases |
| 155 | Guard executes the script | Injector/floor/ledger behavior run, not token-matched; source reads = syntax contracts only |
| 156 | Checkpoints bound to project root | Worktree/common-dir identity; linked worktrees, nearest-ancestor fallback, --project-root override |
| 157 | Sealed LOG mutation never skipped | Resolves active/newest sealed segment; unavailable mutation = fatal |
| 158 | last_event migration boundary | Schema v1 missing it WARNs; v2 with event-bearing LOG and no marker FAILs |
| 159 | Tag audit fails closed | Batch process nonzero/malformed/truncated/surplus = nonzero exit, no PASS; legal missing = warning |
| 160 | Bootstrap reports process truth | Failed read/backup/transform/copy/removal/write exits nonzero; config bytes preserved exactly |
| 161 | Exports belong to project owner | Archive beside .saipen/ owner; nested/foreign/linked-worktree paths all observed |
| 162 | Crew launcher truth | Nonzero launcher → fallback; exhausted → no Done.; three accepted → truthful claim |
| 163 | Bytecode is not a release artifact | Tracked caches forbidden; injectors clean installed trees; installed-bytecode red-control |
| 164 | Shell predicates fail closed | grep >1 fails operation; skill path removed as dir, symlink, or file |
| 165 | Lost enumeration is not a skip | Missing Git = loud SKIP; nonzero `git tag -l v*` = focused nonzero failure |
| 166 | LOG filter propagates failure | Read/filter error → FAIL before PASS; empty malformed set stays success |
| 167 | Hook resolves Bash | No-Python floor runs under resolved bash; missing Bash = focused dependency failure |
| 168 | Re-authorization survives crash | `DEC: goal reauthorized` required; § 1.5 counts newest marker; validator replays rebuild |
| 169 | Chat voice in the kernel | BOOT.md + RFC § 1.1 mandate STYLE.md before any output; cross-doc check 13j |
| 170 | Append targets end on a line boundary | Last byte read on all 21 targets; red control strips a fixture's final newline |
| 171 | Shortcut resolves to a defined command | Table's right-hand column parsed; red-test points hh at a phase; current assignment lives in row 183 |
| 172 | Empty DONE board goes to HUNT | One document decides; done.md defers to § 1.11; user-asked brake still legal |
| 173 | Bare goal resets only a tripped valve | Reset line names counters; WARN on this repo's own E-1468 (append-only history) |
| 174 | Resume names what is stuck | BLOCKED tickets, untriaged findings, live WAITs in the reply; report only |
| 175 | Rationale describes its table | Length has no global meaning; exact declared row governs; undeclared repeats are not inferred |
| 176 | Phase-named command checkpoints | Membership derived from phase docs; hunt red-tested; init excluded structurally |
| 177 | Cyrillic shortcut = same shortcut | Confusable-set normalization before matching; six rows have twins, seven have none |
| 178 | Every shortcut wakes the protocol | SKILL.md triggers exactly equal RFC table + confusable mapping; both drift halves red-tested |
| 179 | A no-op mutation is not evidence | apply_case rejects unchanged callable results; identity-mutation self-control |
| 180 | Root /nul ignored | Stray Windows device-name entry cannot disable audits; snapshots exclude it |
| 181 | Shortcut translations have one source | 32 locale sources feed mirrors and non-Core guides; keys, twins, order, links, and source equality guarded |
| 182 | Chat language and voice agree everywhere | Explicit EE/EN/RU prose wins; Russian repo only breaks bare/ambiguous ties; Estonian default; caveman-дед persists until explicit off switch |
| 183 | Shortcut destinations are exact assignments | All 13 routes pinned; valid-but-wrong `cc` fails; no global length magic |
| 184 | Package shortcuts are ready-gated | ee/qq prepare complete isolated handoffs; eee/qqq collect only ready output through gates and push; refusal writes nothing |

| 185 | WARN-slug ownership is release-history data, not prose | `tools/validate.py` |
| 186 | The bootloader pointer survives being parsed, and the validator is not the judge of that | `tools/validate.py` with no parser and no dependency; red control un-doubles the backslashes exactly as commit 4012bae d |
| 187 | `saipen plan <text>` and bare `saipen plan` are different commands, and both documents say so | `tools/validate.py` |
| 188 | The voice contract carries a value, so skipping it stops being silent | `tools/validate.py` |
| 189 | The Pick Rule decides, and the board can be checked against it | `tools/validate.py`; red control adds a claim plus its unfinished dependency to the board, so the mutation is board data |
| 190 | A hunt skip names a commit that exists | `tools/validate.py`, red-tested in `tools/run_scenarios.py` against a real repository rather than in `tools/audit_checks |
| 191 | Reply language is a setting, not a deduction | `tools/validate.py` |
| 192 | A runtime-manifest entry names a file the repository has, not one this disk has | `tools/validate.py`, red-tested in `tools/run_scenarios.py`, which builds a real repository and removes one manifest fil |
| 193 | The reply-language default is announced where a new reader lands | `tools/validate.py`, which also FAILs when fewer than the four always-present root documents resolve, so the check canno |
| 194 | A guide opens with why the thing exists, before any mechanics | `tools/validate.py` across the five Core-owned guides (en/et/ru/Дед); red control puts a command back into one opening |
| 195 | The validator never reports on a tree other than the one being edited | `tools/validate.py`, with both controls in `tools/run_scenarios.py` against real worktrees |
| 196 | Phase-transition EDGES agree in every copy, not just the names | `tools/validate.py`, which parses the table fence row-by-row and each phase doc's arrow-form exit lines with double-quot |
| 197 | A LOG entry records what happened, not what is about to | `tools/validate.py`, with the same severity split the DATE check uses |
| 198 | `## DONE` carries its evidence | `tools/validate.py` |
| 199 | A shipped conformance claim never outruns the board | `tools/validate.py` |
| 200 | The pre-commit hook's CI-status line ships with the tool it calls, and cannot block a commit | `tools/ci_status.py` is in `tools/validate.py`'s runtime manifest, which FAILs when a listed file is untracked, so the h |
| 201 | A bare repeated-letter shortcut is a command, never a greeting | `tools/validate.py` |
| 202 | Two sections gave opposite answers about the safety-valve budget, and one of them cited the other for the opposite of what it says | `tools/validate.py` |
| 203 | `PHASE <phase-enum> [T-###]` is paired, and both halves are checked | `tools/validate.py` |
| 204 | No shipped file instructs an agent to write a SUPERSEDED schema version | `tools/validate.py` |
| 205 | § 2.1's ZERO-PROMPT rule declares its exception list complete and names both carve-outs | `tools/validate.py` |
| 206 | A record another rule is required to READ has a form the reader can find | `tools/validate.py` on the ACTIVE log |
| 207 | A shortcut row's Notes describe the destination it actually routes to, bare form included | `tools/validate.py` |
| 208 | CLEAN's board scrub keeps the dependency graph intact | `tools/validate.py` |
| 209 | The MARKHUNT brake has a legal wording, and the deadlock check stops exempting whole situations from itself | `tools/validate.py` |
| 210 | `saipen hunt` can actually enter HUNT, and forcing a sweep forces one | `tools/validate.py` |
| 211 | The first-publish gate runs before the act it authorizes | `tools/validate.py` |
| 212 | The release tag is pushed only after the branch push has landed, and a published tag whose commit is on no remote branch is a defect the validator names | `tools/validate.py` |
| 213 | The ticket that passes REVIEW stays in `## DOING` through SHIP; it reaches `## DONE` only at the DONE phase after the push lands | `tools/validate.py` |
| 214 | VERIFY's retry cap is counted on the ticket, not in the agent's head | `tools/validate.py`; two red controls in `tools/audit_checks.py` |
| 215 | REVIEW re-runs the ticket's own `verify:` instead of reading VERIFY's claim of it | `tools/validate.py` |
| 216 | Three borrowed invariants land in the docs that emit them, each one sentence | `tools/validate.py` as five marker checks across three documents; five red controls in `tools/audit_checks.py`, each sof |
| 217 | A command the user just typed outranks the previous session's pre-computed `next_action`, and § 1.11's priority list says so in the list rather than around it | `tools/validate.py` |
| 218 | A shortcut row's Notes requirement is derived from the row's ROUTE, not from the key's name | `tools/validate.py`, which scans every shortcut row whose route names `saipen goal` and reports the offending keys by na |
| 219 | A `WAIT:` body is one sentence | `tools/validate.py` |
| 220 | Proposal Mode's halt has one legal form, and for six months it had none | `tools/validate.py` |
| 221 | A validator condition whose trigger spans more than one project file belongs in `tests/scenarios/`, and a fail-fixture must pin the reason it fails on | `tools/run_scenarios.py` |
| 222 | HUNT deletes only what it can prove recoverable, and its clean-result cache is keyed on a tree rather than a commit | Evidence class STRUCTURAL_ONLY, stated rather than dressed up |
| 223 | The PREPARE record names its producer | `tools/validate.py` in two places, and the second is not a marker |
| 224 | A multi-command message loses nothing, and the pair the shortcut table most invites now completes | Evidence class STRUCTURAL_ONLY, stated rather than dressed up |
| 225 | The seat is derived, not chosen: it is the agent home the protocol was loaded from | `tools/validate.py`, and this converts the half row 148 called behavioural |
| 226 | A MARKHUNT pass can still be counted after its findings are triaged | `tools/validate.py` in two places |
| 227 | `no-git` means git cannot be READ, and a genuinely git-less MARKHUNT closure is unproven rather than satisfied | `tools/validate.py` |
| 228 | The repository root is a closed set, because an unreferenced file is invisible to every other check here | `tools/validate.py` |
| 229 | `no-publish` is a permission, not an absence of git, and the release step is split so nothing is half-permitted | `tools/validate.py` |
| 230 | A ticket whose completion condition can never be met sits in `## BLOCKED`, not `## TODO` | `tools/validate.py` |
| 231 | A stale translation next to updated source has a signal | `tools/validate.py` at WARN, and the severity is a decision rather than a default |
| 232 | `## BLOCKED` also holds a ticket whose work another instance owns by rule | `tools/validate.py`, which requires RFC 1.2 to carry both halves of the rule |
| 233 | A new section names the defect class it eliminates, or it does not get written | `tools/validate.py` |
| 234 | The wiki Scenarios page mirrors CONFORMANCE by ID, and row-count equality is not the test | `tools/validate.py` at WARN, and SKIP when the page is absent |
| 235 | Two red controls that could not go red, found by running them rather than by reading them | Behavioral |
| 236 | A future-stamped LOG line is repaired, not waited out | `tools/validate.py` |
| 237 | A circuit stage hands the next stage a reproduction or a verdict, never a claim -- and the count of shortcut keys is derived, not written down | `tools/validate.py` |
| 238 | A move is destructive to whatever loads the moved file, and the deletion gate cannot see it | `tools/validate.py` |
| 239 | A habit claiming it has no counter-mechanism is its own defect | the citation check that already exists |
| 240 | CHANGELOG.md is ordered, unique, headed by the current version, and bounded -- all four were prose and none was checked | `tools/validate.py` |
| 241 | The installed validator and the repository validator agree about the same tree, because the flag that decides which one you are running is measured from the TOOL rather than from the shell | Evidence is the before/after measurement, run end-to-end |
| 242 | Session-level `BLOCKED` means no ticket anywhere on the board is workable, and only the first half was ever checked | `tools/validate.py` |
| 243 | A clean HUNT's destination is intent-aware: under `execution_intent: converge` it is stage F or stage I of `CONVERGE.md` and MUST NOT enter `ADD` (F routes to `CLEAN`, I routes into the closure sequence -- sync, fresh factories, finalize; ADD is invention, the one thing a converge run never does), while the `normal`/`goal` path keeps the `ADD` destination of MAINTENANCE § 2.1 | `tools/validate.py` |
| 244 | The safety-valve pause's resume key is intent-aware | `tools/validate.py` |
| 245 | CLEAN owns every proven-safe hygiene mutation and HUNT owns none of them -- the split ended the duplication where both phases could delete | ools/validate.py |
| 246 | Every shipped sai*.md role charter is machine-readable: a fenced YAML metadata block declaring role_kind (SCOUT/FIXER/PRODUCER/TOOL), write_scope, trigger, collect_policy (automatic/core-review/explicit), done_condition, freshness_inputs, output_contract, role_revision -- the eight keys a tool reads without parsing prose | tools/validate.py |
| 247 | Role freshness is recorded and compared, never trusted: a subSaipen's findings are only as trustworthy as the charter it ran under | tools/validate.py |
| 248 | Golden Default means Wintage's shipped 21-token `themes/goldendefault.json`, not any plausible dark-golden palette a model remembers | `tools/validate.py` |
| 249 | A nonempty `OUTBOX.md` may never disappear into a zero-iteration parser result | `tools/validate.py` before its entry loop and a mutation that appends zero-entry package prose to a canonical empty OUTB |
| 250 | Producer readiness and Core conformance are different questions, so the validator carries a gate context |  |
| 251 | SHIP stages before it gates |  |
| 252 | A schema keyword no enforcer interprets is a FAIL, not a silent skip |  |
| 253 | Commit identity is the full object ID, never the width someone wrote it at |  |
| 254 | No adapter, skill or injector may name RFC as a rule destination |  |
| 255 | `blocker:` is ticket-level status | Present and non-empty only under `## BLOCKED`; TODO/DOING/DONE+blocker and BLOCKED without blocker FAIL |
| 256 | Default Goal-Driven Execution | Goal-driven by default, runs to completion, no explicit /goal, cannot falsely report COMPLETE or stop early (CORE.md § 1.12) |

> "254 сценария. Каждый проверяет одно правило. Никаких 'ну, это редко бывает'. Тест упал — значит что-то сломалось. Тест прошёл — значит работает. Агент не гадает. Агент проверяет."
