# Scenarios

194 behavioral conformance scenarios (CONFORMANCE.md rows 1-194). Each tests a specific SAIPEN invariant.

## Core scenarios (1-30)

| # | Scenario | Invariant |
|---|---|---|
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

## Advanced scenarios (31-99)

| # | Scenario | Invariant |
|---|---|---|
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

## Guardian scenarios (100-194)

| # | Scenario | Invariant |
|---|---|---|
| 100 | A cited version must exist in the release ledger, not m... | A cited version must exist in the release ledger, not merely sit below `VERSION`. The future... |
| 101 | The release ledger's two halves are compared without re... | The release ledger's two halves are compared without repeating known history forever. Tagged... |
| 102 | "Latest" on GitHub means highest version, not most rece... | "Latest" on GitHub means highest version, not most recently pushed. `release.yml` left `make... |
| 103 | A check that reads external state refuses to run on a P... | A check that reads external state refuses to run on a PARTIAL view of it. The release-ledger... |
| 104 | The UI palette has one name and every document uses it | The UI palette has one name and every document uses it. `UI.md` names **Vintage Golden** as... |
| 105 | The palette-name guard holds a LIST of superseded names... | The palette-name guard holds a LIST of superseded names, not one. The first name it enforced... |
| 106 | Workspace hygiene is checked, not merely asserted -- RF... | Workspace hygiene is checked, not merely asserted -- RFC § 1.7 forbids `saipen set` from cop... |
| 107 | RFC § 1.8's no-rush rule -- a raw backlog MUST NOT be i... | **Behavioral, not machine-checkable, and stated rather than silent**: RFC § 1.8's no-rush ru... |
| 108 | RFC § 2.3's completion rule -- the agent MUST finish th... | **Behavioral, not machine-checkable, and stated rather than silent**: RFC § 2.3's completion... |
| 109 | Every RFC section that states a MUST is claimed by a CO... | Every RFC section that states a MUST is claimed by a CONFORMANCE row. The doc-coverage check... |
| 110 | Every release tag is swept against its own `VERSION` fi... | Every release tag is swept against its own `VERSION` file, not just the one being pushed. `r... |
| 111 | An exemption list is rechecked, not trusted | An exemption list is rechecked, not trusted. `tools/audit_tags.py` FAILs if a tag listed as... |
| 112 | A mangled `.saipen/` file is diagnosed, not fatal | A mangled `.saipen/` file is diagnosed, not fatal. `STATE.md` is the first thing this valida... |
| 113 | A state written by a NEWER schema than the validator un... | A state written by a NEWER schema than the validator understands no longer passes silently.... |
| 114 | `mode: read-only` means two different things and both d... | `mode: read-only` means two different things and both documents now say so. Core's is a **ca... |
| 115 | `HUNT -> DONE` is legal for a subSaipen and only for one | `HUNT -> DONE` is legal for a subSaipen and only for one. RFC § 1.6 routes `HUNT` to `ADD`/`... |
| 116 | A subSaipen's `STATE.md` is held to the same rules as C... | A subSaipen's `STATE.md` is held to the same rules as Core's. PROTOCOL.md § 1 says "same `ST... |
| 117 | A fixture whose validator CRASHED is reported as a cras... | A fixture whose validator CRASHED is reported as a crash, not as a failure for the wrong rea... |
| 118 | No tool reads a module-level name before the line that... | No tool reads a module-level name before the line that assigns it. `tools/validate.py` is a... |
| 119 | `requires:` is held to RFC § 1.3's capability vocabulary | `requires:` is held to RFC § 1.3's capability vocabulary. The field was type-checked as an a... |
| 120 | `saipen_version` is compared to the protocol generation... | `saipen_version` is compared to the protocol generation actually installed. It was type-chec... |
| 121 | A warning that states a count lists that many, or says... | A warning that states a count lists that many, or says how many it hid. The release-ledger w... |
| 122 | The installed pre-commit hook is not from an older gene... | The installed pre-commit hook is not from an older generation. In a consuming project the ho... |
| 123 | The hook says so when it validates NOTHING | The hook says so when it validates NOTHING. Reaching its final `exit 0` means neither `valid... |
| 124 | The reply-language rule lives in the kernel, not behind... | The reply-language rule lives in the kernel, not behind an escalation. `STYLE.md` carried it... |
| 125 | The ban on ambient language signals names the repositor... | The ban on ambient language signals names the repository itself. `STYLE.md` forbade inferrin... |
| 126 | Every translated locale has a guide and every guide has... | Every translated locale has a guide and every guide has a locale. The two sides name Estonia... |
| 127 | RFC § 1.2's STATE freshness marker is enforced | RFC § 1.2's STATE freshness marker is enforced. `last_event` exists to catch a `STATE.md` th... |
| 128 | it works at SECTION granularity | **Stated limit of the rule-coverage check**: it works at SECTION granularity. Every RFC sect... |
| 129 | TEMPLATE's placeholders cannot escape into a live subSa... | TEMPLATE's placeholders cannot escape into a live subSaipen. The shipped template carries `a... |
| 130 | RFC § 1.4's claim fields are checked, not merely spelle... | RFC § 1.4's claim fields are checked, not merely spelled correctly. `claim_time` was a recog... |
| 131 | Warnings print their category | Warnings print their category. It appeared only in the "... and N more" roll-up, so every in... |
| 132 | `review_passes` enforces the two-pass cap mechanically,... | `review_passes` enforces the two-pass cap mechanically, which is the reason RFC § 1.2 says t... |
| 133 | The human digest is the shape `phases/ship.md` promises... | The human digest is the shape `phases/ship.md` promises, and is not from another era. That d... |
| 134 | MARKHUNT's closure manifest is read | MARKHUNT's closure manifest is read. `phases/markhunt.md` specifies `.saipen/kitchen/markhun... |
| 135 | A `no-git` head pair must be a PAIR | A `no-git` head pair must be a PAIR. `markhunt.md` permits the literal `no-git` in both `hea... |
| 136 | The canonical validator's checks are proved still able... | The canonical validator's checks are proved still able to go red, not just the portable floo... |
| 137 | Every case in that audit must be evidence | Every case in that audit must be evidence. A case whose expected text already appears in the... |
| 138 | The portable floor no longer claims conformance in the... | The portable floor no longer claims conformance in the canonical validator's words. Both hal... |
| 139 | A tool that shells out picks a real `bash`, never `sh` | A tool that shells out picks a real `bash`, never `sh`. `tools/audit_parity.py` fell into bo... |
| 140 | A precondition names what it saw | A precondition names what it saw. That same failure printed "one of the two tools rejects an... |
| 141 | The closed ticket-field list is stated in the document... | The closed ticket-field list is stated in the document that owns it. `tools/validate.py` has... |
| 142 | § 1.10's command surface is compared against the tool's... | § 1.10's command surface is compared against the tool's copy -- the seventh such set, after... |
| 143 | it proves a cited section EXISTS, never that the sectio... | **Stated limit of the citation checker**: it proves a cited section EXISTS, never that the s... |
| 144 | No gitlink is committed inside `.saipen/` | No gitlink is committed inside `.saipen/`. A subSaipen's kitchen is a sandbox and may legiti... |
| 145 | A row cannot keep claiming an enforcement that is gone | A row cannot keep claiming an enforcement that is gone. This table only ever grew -- 144 row... |
| 146 | RFC § 1.6's retry rule -- a repeated attempt MUST be ab... | **Behavioral, not machine-checkable, and stated rather than silent**: RFC § 1.6's retry rule... |
| 147 | BUILD looks for existing code before writing new code:... | BUILD looks for existing code before writing new code: this project's own, then the standard... |
| 148 | `agent:` has a definition, so § 1.4's comparison has tw... | `agent:` has a definition, so § 1.4's comparison has two sides. Every concurrency rule in th... |
| 149 | Installed skill copies carry `VERSION` | Installed skill copies carry `VERSION`. RFC § 1.2 says `<saipen_home>/VERSION` is the single... |
| 150 | Skill-copy refreshes are replacements, not overlays | Skill-copy refreshes are replacements, not overlays. `Copy-Item -Recurse -Force` and `cp -r`... |
| 151 | Installed validators do not mix their own install tree... | Installed validators do not mix their own install tree with the project's release ledger. Wh... |
| 152 | SHIP preflight has a repair loop | SHIP preflight has a repair loop. SHIP requires 100% green, but its DFA row allowed only `DO... |
| 153 | The release ledger observes git tags once and reuses th... | The release ledger observes git tags once and reuses that snapshot for both phantom-version... |
| 154 | SHIP publishes the intended release tag by exact ref, n... | SHIP publishes the intended release tag by exact ref, never by selecting all annotated tags... |
| 155 | A guard about script behavior executes the script | A guard about script behavior executes the script. The injector distribution/order block in... |
| 156 | Checkpoint paths are bound to one dynamically resolved... | Checkpoint paths are bound to one dynamically resolved project root, never ambient cwd. A re... |
| 157 | A canonical mutation never disappears because normal pr... | A canonical mutation never disappears because normal protocol maintenance changed the storag... |
| 158 | `last_event` has a migration boundary instead of becomi... | `last_event` has a migration boundary instead of becoming required overnight. A missing mark... |
| 159 | A tag audit that has enumerated tags fails closed if it... | A tag audit that has enumerated tags fails closed if its `git cat-file --batch` process exit... |
| 160 | Bootstrap install and uninstall reports preserve proces... | Bootstrap install and uninstall reports preserve process truth and user-owned config bytes.... |
| 161 | Export archives belong to the project that owns `.saipe... | Export archives belong to the project that owns `.saipen/`, never to ambient cwd. Git invoca... |
| 162 | The Unix crew launcher reports accepted terminal launch... | The Unix crew launcher reports accepted terminal launches, not merely installed launcher nam... |
| 163 | Generated Python bytecode is neither source nor a distr... | Generated Python bytecode is neither source nor a distributable skill artifact. Repository i... |
| 164 | Shell bootstrap content predicates distinguish match, a... | Shell bootstrap content predicates distinguish match, absence, and process/read failure. `gr... |
| 165 | The historical tag audit distinguishes an absent Git ex... | The historical tag audit distinguishes an absent Git executable from a launched enumeration... |
| 166 | The shell portable floor's LOG filter treats an empty s... | The shell portable floor's LOG filter treats an empty set of malformed lines as success whil... |
| 167 | The installed POSIX pre-commit hook may itself run unde... | The installed POSIX pre-commit hook may itself run under `/bin/sh`, but its no-Python portab... |
| 168 | A re-authorization is countable, or it expires at the n... | A re-authorization is countable, or it expires at the next crash. Bare `saipen goal` resets... |
| 169 | The chat voice & compression rule lives in the kernel,... | The chat voice & compression rule lives in the kernel, not behind an escalation. `STYLE.md`... |
| 170 | Files the protocol APPENDS to end on a line boundary | Files the protocol APPENDS to end on a line boundary. An append to a file that stops mid-lin... |
| 171 | A shortcut resolves to a command the command surface ac... | A shortcut resolves to a command the command surface actually defines. The table's right-han... |
| 172 | An empty board at `DONE` goes to `HUNT`, and only one d... | An empty board at `DONE` goes to `HUNT`, and only one document decides it. RFC § 1.11 step 5... |
| 173 | Bare `saipen goal` resets the safety-valve counters ONL... | Bare `saipen goal` resets the safety-valve counters ONLY against a tripped valve. Resetting... |
| 174 | A resume names what is stuck | A resume names what is stuck. Every `## BLOCKED` ticket, any untriaged `[MARKHUNT]` finding,... |
| 175 | A shortcut's stated rationale describes the table it go... | A shortcut's stated rationale describes the table it governs. Earlier prose successively cla... |
| 176 | A command named after a phase carries the phase switch'... | A command named after a phase carries the phase switch's checkpoint duty, and membership in... |
| 177 | A shortcut typed in Cyrillic resolves to the same shortcut | A shortcut typed in Cyrillic resolves to the same shortcut. On a Russian layout the visually... |
| 178 | Every shortcut in RFC § 1.10 activates the SAIPEN skill... | Every shortcut in RFC § 1.10 activates the SAIPEN skill before the RFC is available, includi... |
| 179 | A canonical mutation must change its target bytes befor... | A canonical mutation must change its target bytes before its result can count as evidence. T... |
| 180 | A stray Windows device-name entry must not disable the... | A stray Windows device-name entry must not disable the audits meant to diagnose the reposito... |
| 181 | Shortcut translations have one reviewed source per lang... | Shortcut translations have one reviewed source per language, not two independent chances for... |
| 182 | Chat language has one boot-critical precedence on every... | Chat language has one boot-critical precedence on every surface a weak model may load first.... |
| 183 | Shortcut routes are assignments, not suggestions | Shortcut routes are assignments, not suggestions. Merely proving that a route names some val... |
| 184 | Package shortcuts are two-stage and ready-gated | Package shortcuts are two-stage and ready-gated. `ee`/`qq` prepare the complete translation/... |
| 185 | WARN-slug ownership is release-history data, not prose | WARN-slug ownership is release-history data, not prose. The release ledger baseline now carr... |
| 186 | The bootloader pointer survives being parsed, and the v... | The bootloader pointer survives being parsed, and the validator is not the judge of that. `s... |
| 187 | `saipen plan <text>` and bare `saipen plan` are differe... | `saipen plan <text>` and bare `saipen plan` are different commands, and both documents say s... |
| 188 | The voice contract carries a value, so skipping it stop... | The voice contract carries a value, so skipping it stops being silent. `STYLE.md` has been a... |
| 189 | The Pick Rule decides, and the board can be checked aga... | The Pick Rule decides, and the board can be checked against it. `needs:` had two guards from... |
| 190 | A hunt skip names a commit that exists | A hunt skip names a commit that exists. `phases/hunt.md` permits skipping the six-category s... |
| 191 | Reply language is a setting, not a deduction | Reply language is a setting, not a deduction. Four documents carried one precedence rule --... |
| 192 | A runtime-manifest entry names a file the repository ha... | A runtime-manifest entry names a file the repository has, not one this disk has. The complet... |
| 193 | The reply-language default is announced where a new rea... | The reply-language default is announced where a new reader lands. `reply_language:` ships as... |
| 194 | A guide opens with why the thing exists, before any mec... | A guide opens with why the thing exists, before any mechanics. Guides were filed under Artif... |

> Дед voice quote TBD.
