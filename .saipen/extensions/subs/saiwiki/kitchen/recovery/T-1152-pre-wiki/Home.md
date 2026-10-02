# SAIPEN

**Continuation protocol for AI coding agents.** Project memory in plain markdown. Cold agent with zero history runs `/saipen continue`, reads STATE->BOARD->LOG tail, executes next_action, resumes in under a minute. Any vendor, any day.

**v7.226.0** | MIT | [Spec](https://github.com/vacterro/saipen/blob/main/SPEC.md) | [CORE](https://github.com/vacterro/saipen/blob/main/saipen/CORE.md) | [![CI](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)

---

## One command. Zero dependencies. Zero amnesia.

```
User  ->  /saipen continue
Agent ->  reads STATE.md (phase, task, next_action, mode, human_note)
Agent ->  reads BOARD.md (DOING / TODO / DONE / BLOCKED tickets)
Agent ->  reads active LOG.md tail (recent events)
Agent ->  executes next_action immediately
Agent ->  loads phase doc only when rules needed
Agent ->  Works.
```

## 18 commands, full surface

| Command | Effect |
|---|---|
| `saipen set` / `saipen init` | Bootstrap .saipen/ |
| `saipen continue` / bare `saipen` | Resume from STATE |
| `saipen goal <text>` | Pivot to objective, run to completion |
| `saipen plan [text]` | Plan / add tickets; with text the text IS the work |
| `saipen clean` | Deep repo scrub |
| `saipen translate` | Isolated translation build |
| `saipen markhunt` | Dry exhaustive audit (record only) |
| `saipen prepare [producer]` | Build a complete, fresh ready package; no integration or push |
| `saipen collect <producer>` | Integrate one ready package through Core gates |
| `saipen ship` | Version bump, tag, push |
| `saipen hunt` | Run the HUNT sweep now |
| `saipen validate` | Run conformance checker |
| `saipen crew` | The whole circuit: hunt, reproduce, intake, build, translate, document, ship |
| `saipen test` | Run the declared suite, report PASS/FAIL |
| `saipen status` | Read-only board report |
| `saipen stop` | Checkpoint + halt |
| `saipen userperson` | Optional preference meta-control, off by default |
| `saipen improve` | Meta-control audit: status / sweep / verify / clean |

**Shortcuts** (full 15-key table in [CORE § 1.10](https://github.com/vacterro/saipen/blob/main/saipen/CORE.md#110-command-surface)): `gg` = new goal only, `hh` = hunt, `cc` = continue/converge, `ccc` = continue-and-ship, `ss` = stop, `sss` = status, `dd` = plan, `aa` = markhunt, `ee`/`eee` = prepare/collect+push translations, `qq`/`qqq` = prepare/collect+push wiki, `pp` = saipython, `tt` = test, `sc` = crew. The tripled package keys refuse unless the doubled key already produced `status: ready`. Length has no global meaning; each row is an exact assignment. Cyrillic twins `сс`, `ссс`, `аа`, `ее`, `еее`, `рр` work too.

## Two layers

| Layer | Required | Purpose |
|---|---|---|
| Core | ✅ | Continue work safely |
| Maintenance | On top of Core | Evolve software with no tasking |

**Core state machine:** INIT -> PLAN -> SCOUT -> BUILD -> VERIFY -> REVIEW -> SHIP -> DONE | BLOCKED

**Autonomous evolution:** Empty board at DONE -> auto HUNT -> ADD -> HUNT... until mature or capped (3 waves / 20 tickets).

**Goal mode:** `saipen goal <objective>` - autonomous run with safety valve. Auto-pivots, auto-ships, auto-hunts. Stops at maturity or caps.

## Key features v7.226.0

- **WAIT categories** (v7.93.0): Closed 7-word vocabulary — `manual-verify`, `destructive-op`, `first-publish`, `user brake`, `blocked`, `safety valve`, `init`. Makes stopping mechanically distinguishable.
- **Cross-document drift detector** (v7.93.0): `tools/validate.py` parses 6 sets from CORE, FAILs on schema/validator/BOOT/CONFORMANCE disagreement.
- **Portable floor** (v7.94.0-97.0): `validate.sh` + `validate.ps1` probe all 9 CORE §1.2 fields, frozen against new checks. Audited by `tools/audit_floor.py` — 20 mutations, both halves proven red (v7.100.0).
- **SubSaipen protocol** (v7.91.0): OUTBOX validated (status/summary/critical), patch-with-evidence format, read-only workers. Sub liveness now machine-checked: never-run instances WARN, unreviewed findings WARN (v7.99.0).
- **Determinism invariants** (v7.86.0-92.0): fixed action priority, RECOVER/FINISH/START hierarchy, one-ticket-at-a-time.
- **CI gates pushes** (v7.98.0): validate.yml fires on push to main/master and pull_request, with concurrency group. Pre-commit hook remains the opt-in per-machine gate.
- **Drift hunt validation** (v7.98.0): validate.py expanded to subSaipen next_action, self-transition enum, adapter paths. Plus (v7.102.0): all 9 adapters now name BOOT.md — no cold agent pays 25x the necessary read.
- **SubSaipen production ready** (v7.98.0): 4 live instances running since v7.84.0.
- **Validator linted** (v7.99.0): 9 cp1251-mangled section signs found inside its own FAIL messages — valid UTF-8, invisible to its own U+FFFD check. Repaired; CI runs ruff. Push claims now verified against git — a next_action claiming "pushed" with local-only commits FAILs.
- **Doc inventory** (v7.100.0): 184 shipped documents accounted for. Every one under a check or exempt with a stated reason. No more orphan files at phantom paths.
- **Citation resolution** (v7.101.0): every § N.N and phases/<name>.md reference in a shipped doc must name something that exists. 103 docs scanned, zero dangling.
- **KNOWLEDGE/ under checks** (v7.101.0): traps.md and decisions.md both taught a WAIT-at-DONE rule superseded 9 releases earlier. No more blanketed exemptions for project data.
- **Mojibake lint** (v7.103.0): 5 cp1251 corruption sequences detected across every shipped doc, not a curated 4. Found a mangled arrow in traps.md — the very file documenting the corruption.
- **Phantom version check** (v7.104.0): cited versions must exist in release ledger (git tags + CHANGELOG), not merely sit below VERSION. Ledger halves compared.
- **Release.yml fix** (v7.105.0): `fetch-depth: 0` in CI — no more shallow-clone blind spots. `make_latest` pinned to highest semver.
- **Palette Vintage Golden** (v7.106.0-107.0): UI palette named, 18 tokens defined, 46 files renamed. Guard survives its own rename.
- **Nine unclaimed MUSTs** (v7.108.0): 3 CORE sections with 9 MUSTs and zero CONFORMANCE rows. Workspace hygiene now enforced mechanically.
- **Tag audit** (v7.109.0): `tools/audit_tags.py` sweeps every tag against VERSION. Found 4 pre-existing mismatches.
- **UTF-16 encoding crash** (v7.110.0): validator died on first UTF-16 STATE.md. All 3 checkpoint files encoding-checked up front. `schema_version` future-WARN.
- **read-only dual meaning** (v7.111.0): Core vs subSaipen read-only clarified — 7 banned phases vs 4. HUNT->DONE legal for subSaipen. Sub STATE checked against Core rules.
- **audit_order.py** (v7.112.0): catches use-before-define NameErrors invisible to ruff. `requires:` and `saipen_version` now meaningfully checked.
- **Hook generation stamp** (v7.113.0): pre-commit hook carries stamp, validator compares. Fail-open path now prints repair command.
- **BOOT.md language rule** (v7.114.0): reply-language rule moved into the cold-start kernel instead of sitting behind escalation. Its original bare-command default is superseded by v7.157.0's exact three-language precedence.
- **last_event + TEMPLATE check** (v7.115.0): STATE freshness marker enforced. TEMPLATE placeholders cannot escape into live instances.
- **claim_time validation** (v7.116.0): claim_time checked as ISO-8601 UTC. Half-claim (owner without time) warns. warn() prints category on every line.
- **review_passes + digest freshness** (v7.117.0): review_passes cap enforced. Digest named v7.83.0 — 33 releases stale.
- **MARKHUNT manifest** (v7.118.0): closure manifest validated — shape, cursor, vector completeness. no-git head pair must be a pair.
- **audit_checks.py** (v7.119.0): 41-mutation harness proving validator checks still go red. Control run is precondition.
- **Portable floor honest wording** (v7.120.0): floor stopped claiming conformance in validator's words. `tools/audit_parity.py` guards baseline.
- **bash vs sh trap** (v7.121.0): `find_bash()` picks real bash, never `sh`. Control-failure names which tool and exit code.
- **verify: finally defined** (v7.122.0): CORE 1.2 states the closed ticket-field list. `verify:` was enforced by the tool and carried by 72 tickets — named in no document.
- **No gitlink under .saipen/** (v7.123.0): nested repo = mode-160000 entry pointing at a commit no clone can fetch. Validator FAILs it. v7.122.0 shipped exactly that way.
- **A row can't claim dead enforcement** (v7.124.0): CONFORMANCE row naming a deleted tool/CI step/fixture = FAIL. 144 rows, zero retirements, now loud.
- **Retry owes an answer** (v7.124.0): a repeated attempt MUST name what changed. Honest answer "nothing" = retry forbidden.
- **BUILD reuse ladder** (v7.124.0): own code → stdlib → existing dep → write it. Adding a dependency is a ticket, not a build step.
- **agent: names the seat** (v7.125.0): inherited from STATE, never invented per session. Placeholders (`id`, `<name>`, `AgentID`, `unknown`) FAIL. Model upgrade ≠ new actor.
- **Installs carry VERSION** (v7.126.0): injectors ship it; runtime manifest makes forgetting it a FAIL. Refreshes replace managed dirs, never overlay.
- **Git Bash gets its tools** (v7.127.0): floor harnesses add Git `usr/bin` to child PATH only; System32 WSL stub rejected case-insensitively. 20/20 floor checks green on Windows.
- **SHIP preflight repair loop** (v7.128.0): fixable pre-commit failure → narrow SHIP→BUILD edge, then repeat VERIFY/REVIEW/SHIP. Release order explicit: prepare metadata → rerun validators → commit → push.
- **One observation, two checks** (v7.129.0): release ledger queries tags once, reuses the snapshot. Failure shows the real cause — no silent skip behind `except: pass`.
- **Publish the release you named** (v7.130.0): SHIP pushes branch + exact `refs/tags/vVERSION`. `--tags`/`--follow-tags` forbidden for releases.
- **Run the guard, not its spelling** (v7.131.0): injector/floor/ledger guards execute scripts; source reads stay for syntax contracts. Floor 27 cases, Git Trace2 observes real processes.
- **Bind memory before touching it** (v7.132.0): checkpoints bound to one resolved project root. Git worktree/common-dir identity; `--project-root` deliberately overrides cwd.
- **A skipped guard is a failed guard** (v7.133.0): LOG mutations resolve active or newest sealed segment; any unavailable mutation is fatal. 41/41 holds even with an empty active LOG.
- **Known history is not a permanent warning** (v7.134.0): release ledger suppressed historical exceptions with backfilled entries; validator reads both current and archived changelogs and fails when an exception goes stale.
- **STATE is a real commit pointer** (v7.135.0): `last_event` marker has a migration boundary — schema v1 missing it WARNs, schema v2 with event-bearing LOG and no marker FAILs.
- **A lost tag audit is not a passing tag audit** (v7.136.0): `git cat-file --batch` process failures exit nonzero with focused FAIL; only legal `<spec> missing` stays a warning.
- **Bootstrap success means the writes landed** (v7.137.0): injectors/uninstallers exit nonzero on failed backup/transform/removal/write; PowerShell block regex leaves user-owned whitespace untouched.
- **Exports belong to the project** (v7.138.0): archive written beside the `.saipen/` owner, never ambient cwd; Git worktree/common-dir identity, foreign Git repos rejected.
- **Crew launch success means three terminals accepted** (v7.139.0): Unix launcher observes each detach, falls through on failure, exits nonzero without `Done.` when launchers exhaust.
- **Bytecode is not a release artifact** (v7.140.0): tracked `__pycache__`/`*.py[cod]` forbidden; both injectors clean caches from installed trees before reporting success.
- **Shell predicates fail closed** (v7.141.0): grep status 1 selects absence; statuses above 1 return focused failure. Managed skill paths removed as file, symlink, or directory.
- **Tag enumeration failures are not skips** (v7.142.0): nonzero `git tag -l v*` is evidence loss, exits nonzero; only missing Git may SKIP loudly.
- **Portable LOG filtering propagates failure** (v7.143.0): empty malformed-line set is success; read/filter errors exit nonzero before any PASS or completion.
- **Hooks resolve Bash for the Bash floor** (v7.144.0): POSIX hook runs its no-Python floor through resolved `bash`; floor without Bash fails focused with a dependency message.
- **Crew launcher reports what happened** (v7.145.0): Windows `saipen_crew.bat` reads launch statuses, stops on refusal, names the failed window, exits nonzero.
- **Re-authorization survives the next crash** (v7.146.0): bare `saipen goal` writes `DEC: goal reauthorized`; § 1.5 counts from the newest marker; validator replays the rebuild, greps nothing.
- **A file that stops mid-line swallows the next write** (v7.147.0): all 21 append targets must end on a line boundary; validator reads the last byte. 46/46 mutations hold.
- **One key to maintain, one to reach a remote** (v7.148.0, historical assignment superseded): `cc` then meant `saipen continue`; current routes live only in CORE § 1.10.
- **The brake gets the short key** (v7.149.0): `ss` = `saipen stop`; `sss` = `saipen status` — length is collision order, not cost.
- **Length rationale kept honest** (v7.150.0, later tightened): key count has no global meaning; exact rows govern cost and routing.
- **A phase-named command carries the phase switch's duty** (v7.151.0): phase-switching list derived from phase docs; `saipen hunt` checkpoints a claimed ticket; `init` excluded structurally.
- **A shortcut typed in Cyrillic is the same shortcut** (v7.152.0): six current homoglyph twins normalize through the confusable set before matching; table stays Latin as canonical spelling.
- **Every shortcut can wake the protocol up** (v7.153.0): SKILL.md frontmatter must equal the CORE table plus confusable mapping; validator rejects both halves of drift; 50/50 mutations.
- **Shortcuts belong at the front door** (v7.154.0): README and guides surface `cc`/`sss`/`ss` near the opening and link to the canonical table; current callouts name 15 keys and six Cyrillic twins.
- **A no-op mutation is not evidence** (v7.155.0): harness rejects every callable whose output equals its input; identity-mutation self-control keeps the guard capable of failing. 50 canonical mutations fire.
- **Device names and weak translations get guards** (v7.156.0): root `/nul` cannot disable audit snapshots; 32 locale shortcut sources feed their mirrors and non-Core guides under exact parity checks. 52 canonical mutations fire.
- **One chat-language contract** (v7.157.0): CORE/BOOT/STYLE/SKILL share explicit EE/EN/RU prose > clearly Russian repo for bare/ambiguous input > Estonian default; unsupported detected language bridges through English. Caveman-дед persists until an explicit off switch. 54 canonical mutations fire.
- **Ready packages and exact shortcut routes** (v7.158.0): `ee`/`qq` prepare complete isolated translation/wiki handoffs; `eee`/`qqq` collect only fresh ready payloads through gates and push. All 13 routes are pinned, six Cyrillic twins wake the skill, and 59 canonical mutations fire.
- **The voice contract carries a value** (v7.159.0-160.0): STYLE.md declares a boot marker; a schema-3 STATE that skipped it is no longer indistinguishable from a compliant one — present-and-wrong FAILs, absent-at-current-schema FAILs.
- **The Pick Rule decides, and the board shows it** (v7.164.0): a `## DOING` ticket whose `needs:` names a ticket outside `## DONE` FAILs; `## BLOCKED` is exempt.
- **Reply language is a setting** (v7.166.0): `reply_language:` on one line, closed to `et`/`en`/`ru`/`auto`; a value outside the set FAILs instead of falling back.
- **The installed validator and the repository validator agree** (v7.198.0): the `IS_SAIPEN_HOME` flag is measured from the TOOL, not the shell — an installed run inside the repo no longer reports repository defects.
- **The user's command outranks the pre-computed pick** (v7.177.0): § 1.11 OBEY — a typed command supersedes `next_action` and clears a live WAIT; two live MUSTs with no precedence cost a bare `qq` twice.
- **A `WAIT:` body is one sentence** (v7.185.0-219.0): the category token bounds what kind of stop; a period+capital ends the body, and session notes belong in `kitchen/digest.md`, never the field.
- **The wiki mirrors CONFORMANCE by ID** (v7.190.0): row-count equality is not the test; a page rebuilt by position instead of ID is the defect (row 234).
- **`sc` walks the circuit** (v7.193.0-194.0): hunt → reproduce → intake → build → translate → document → ship; each stage hands the next a reproduction or a verdict, never a claim.
- **execution_intent replaces goal_mode** (v7.207.0): `goal`/`converge`/`normal` intents own the clean-HUNT destination and the valve resume key; converge pauses say `-- run 'cc' to continue`, never `saipen goal`.
- **HUNT detects, CLEAN mutates** (v7.212.0): the ownership split — HUNT finds and tickets, CLEAN deletes under proof-of-recovery gates; no phase does both.
- **Role charters become machine-readable** (v7.213.0): every shipped sai*.md opens with a YAML block — role_kind, write_scope, trigger, collect_policy, done_condition, freshness_inputs, output_contract, role_revision.
- **Role freshness is recorded and compared** (v7.214.0): `role_revision` at spawn/adopt and in every ready OUTBOX package; a mismatch makes the package stale, never collected.
- **Gate context** (v7.215.0): `--gate ship` / `--gate collect:<producer>` / `--gate converge` answer different questions; a stale producer package stops blocking an unrelated Core ship.
- **USERPERSON meta-control** (v7.217.0): optional preference file, off by default — `saipen userperson` onboarding, structured merge, reset with confirmation, role projections.
- **One name, one execution meaning** (v7.218.0): `saipen crew` stays the strictly sequential circuit; the future concurrent design is a separate command with its own name.
- **Isolated producer parallelism** (v7.226.0): `ee` and `qq` may prepare concurrently because each producer owns a separate lock, epoch, staging area, and content-hashed READY package. Same-producer prepares serialize; Core remains the sole main-tree writer. Integration classifies packages as CURRENT, COMPATIBLE_DRIFT, or STALE from exact read/write dependencies and never auto-rebases stale evidence. Full decision: [ADR-0001](https://github.com/vacterro/saipen/blob/main/KNOWLEDGE/ADR-0001-v7-producer-parallelism.md).
- **Work vs Attempt** (T-1148): the ticket is the durable Work; an Attempt (A-###) is one bounded execution episode. Attempt failure never touches Work identity — the successor closes the dangling episode honestly and re-claims the same ticket. Completion authority is structural: a candidate episode, its RUN lines and its own assertions are claims; only verification evidence recorded after the claim plus the independent VERIFY → REVIEW → SHIP gates admit a transition to DONE. `saipen brief` synthesizes a cold-handoff projection from canonical state.
- **NITRO integrity sweep** (v7.226.0): transactions are truthful (role + before/after hashes per target), recovery is conflict-safe, plan/apply share one op_id, committed retry is ALREADY_APPLIED, state changes are owned-field patches — the mechanical layer `status`/`next`/`ticket`/`sub`/`context` now runs on.
- **Audit closure on the current v7.226.0 tree**: FORCE-FRESH prepare no longer treats an old OUTBOX as proof a role ran; strict READY decoding binds payload bytes and identity; producer integration is journaled; receipt corruption propagates fail-closed; `qqq`/`eee` target only their named producer; crew loops and active READY history are bounded; release Git checks are batched without weakening literal-path or rollback guarantees.

## Quick Start

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

Paste to any agent: `Read <clone>/saipen/BOOT.md first (cold-start kernel), then <clone>/saipen/CORE.md + <clone>/saipen/STYLE.md`

> **Windows users:** inject.sh now converts paths via `cygpath -w` under git bash / MSYS / Cygwin — no more dead paths in CLAUDE.md that no Windows agent can open (v7.100.0).

## ДED Voice

> "Без SAIPEN: открываешь проект через неделю — 'кто тут? что за код? где я остановился?' С SAIPEN: 'привет, продолжай, T-42 в DOING, verify не было, чини.' Один чтение — и работаешь. Никакого 'расскажи что ты делал'. Никакого 'дай контекст'. Просто STATE.md открыл — и всё понял."

---

[GitHub](https://github.com/vacterro/saipen) | 32 locale guides | [Changelog](https://github.com/vacterro/saipen/blob/main/CHANGELOG.md)
