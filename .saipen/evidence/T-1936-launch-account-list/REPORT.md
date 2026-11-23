# T-1936 — `saipen launch --list`: read-only provider/account discovery

FG-0046 (SRC-184) bounded slice, promoted under SRC-341:

> read-only account discovery — `saipen launch --list` names provider, alias,
> profile directory, installed, authenticated and managed/direct for every
> Claude, Codex and Antigravity account on the machine, reading no secret

## What was actually wrong

Not a missing feature — a dispatch defect. `saipen/COMMANDS.md` and SRC-184 both
document `saipen launch --list`, but the `launch` branch in `tools/saipen.py`
answered `ACTOR_UNBOUND` before it ever looked at the arguments:

```python
if command == "launch":
    if _AGENT_OVERRIDE is None:
        _emit({"code": "ACTOR_UNBOUND", ...}); return 1
```

So the command the source told the operator to run refused with a demand for a
SAIPEN seat. Listing which accounts exist on the machine is a read-only question
about the machine; it is not an act as one of those accounts, and it must not
require authority to act as one.

## What was built

### `tools/saipen_engine/account_list.py`

A projection over surfaces that already exist, deliberately not a second
account registry:

| fact | source |
|---|---|
| which providers SAIPEN knows | `extensions/adapters/registry.json` |
| every Claude profile on the machine | `claude_profiles.discover` (T-1635) |
| installed / managed runtime | the adapter's declared `install.skill` |
| direct route | `shutil.which(launch_executable)` |

The one thing the module adds is the row shape SRC-184 asks for: provider,
alias, account number, profile directory, installed, authenticated,
launchability, managed, direct, identity, plan, limits.

Three deliberate positions:

- **`authenticated` is marker presence, never contents.** The probe tests
  `exists()` on the provider's own marker (`.credentials.json`/`.claude.json`
  for Claude, `auth.json` for Codex, `oauth_creds.json` for Gemini) and reports
  which marker it looked at. No file is opened.
- **A missing marker is `unknown`, not `no`.** A provider may authenticate by a
  route this read-only probe cannot see; guessing `no` there would change the
  operator's next action on a false premise.
- **`plan` and `limits` are `unknown`.** SRC-184 makes UNKNOWN a launchable
  state; these probes are not implemented and are never guessed.

Aliases are minted only from a number the directory really carries
(`.claude-account2` → `cl2`, `.codex-account3free` → `cx3`), and the canonical
key of a row is provider + profile directory. SRC-184 forbids treating an alias
as identity.

### `tools/saipen.py`

The `--list` branch now answers before the seat requirement. Starting a host
still requires a seat — pinned by its own test, so the read-only exemption
cannot leak into the mutating route.

## Live measurement on this host

```
cl1  claude       account=1  installed=True  auth=marker-present MANAGED_AVAILABLE    C:\Users\vac34\.claude
cl2  claude       account=2  installed=True  auth=marker-present MANAGED_AVAILABLE    C:\Users\vac34\.claude-account2
cx1  codex        account=1  installed=True  auth=marker-present MANAGED_AVAILABLE    C:\Users\vac34\.codex
cx2  codex        account=2  installed=True  auth=marker-present MANAGED_AVAILABLE    C:\Users\vac34\.codex-account2
cx3  codex        account=3  installed=True  auth=marker-present MANAGED_AVAILABLE    C:\Users\vac34\.codex-account3free
gm1  gemini       account=1  installed=True  auth=unknown       MANAGED_AVAILABLE    C:\Users\vac34\.gemini
```

This is exactly the gap FG-0046 recorded: T-1635 gave `host doctor` the ability
to see `~/.claude-account2`, but nothing named the accounts or their aliases.
`cl2`, `cx2` and `cx3` now have rows. The `antigravity` row answers
`DIRECT_UNSAFE` because its adapter declares no `launch_executable` — a measured
statement, not a claim the account is broken.

## Proof

`tools/test_t1936_launch_account_list.py` — 12 tests, focused family PASS on
record `.saipen/evidence/focused-unit/a1465bdc4c11e631-20261026T210547723277Z.json`
(12 ran, 0 red).

| test | claim |
|---|---|
| `test_every_real_account_is_named_with_its_alias` | the five real accounts map to cl1/cl2/cx1/cx2/cx3 |
| `test_the_profile_directory_is_the_canonical_key` | provider+directory is unique; no profile listed twice |
| `test_no_secret_is_read_into_the_report` | sentinel value never appears in the report |
| `test_no_account_file_is_opened_at_all` | every `Path.read_text`/`read_bytes`/`open` is observed; none touches a marker |
| `test_a_marker_that_is_absent_is_unknown_never_no` | missing auth marker answers unknown |
| `test_discovery_writes_nothing_anywhere` | whole-tree digest identical before/after |
| `test_alias_needs_a_number_because_it_names_a_real_account` | `.claude-work` gets no invented alias |
| `test_managed_available_wins_when_a_runtime_is_installed` | fail-open order, step 1 |
| `test_without_a_managed_runtime_a_startable_direct_route_is_safe` | fail-open order, step 2 |
| `test_neither_route_proven_is_direct_unsafe` | fail-open order, step 3 |
| `test_list_needs_no_seat_and_reports_json` | the CLI wiring itself |
| `test_starting_a_host_still_requires_a_seat` | the exemption does not leak |

### The first version of one test was useless, and the red control found it

The first `test_no_secret_is_read_into_the_report` asserted only that the
sentinel did not APPEAR in the output. A red control that made the probe
`read_text()` every credentials file stayed GREEN — because the content was read
and discarded. SRC-184 forbids READING a secret, not merely publishing one, so
the test was rewritten to instrument `Path.read_text`, `Path.read_bytes` and
`Path.open` and fail on any access to a marker path. That control now fails as
required.

### Five executed red controls

Each mutation was applied to the real source, the named test run, and the source
restored; every one failed as required:

| # | mutation | caught by |
|---|---|---|
| 1 | probe reads the credentials file contents | `test_no_account_file_is_opened_at_all` |
| 2 | discovery creates `.saipen/accounts/` | `test_discovery_writes_nothing_anywhere` |
| 3 | unnumbered profile gets account 99 | `test_alias_needs_a_number_because_it_names_a_real_account` |
| 4 | `MANAGED_AVAILABLE` returned unconditionally | `test_without_a_managed_runtime_...` |
| 5 | `--list` branch disabled (the original defect) | `test_list_needs_no_seat_and_reports_json` |

### Neighbor suites sharing the launch surface

| suite | result |
|---|---|
| `test_t1635_claude_profiles` | 15 ran, OK |
| `test_opencode_bound_launch_smoke` | 6 ran, OK |
| `test_t1624_host_integration` | 70 ran, OK |
| `test_host_launch_net` | 8 ran, OK |
| `test_t1686_launch_policy` | 7 ran, OK |

## What this does NOT prove

- **No account was launched.** The slice is discovery only; `saipen launch cl2`
  is not implemented by this ticket and would need the alias→envelope route.
- **`authenticated` is presence, not validity.** A present marker may be
  expired; proving validity means asking the provider, which this read-only
  probe deliberately does not do.
- **`managed` is presence, not freshness.** Whether that runtime is the current
  generation is `host doctor`'s question; an account list that silently ran a
  freshness audit would blur two different questions.
- **Two new validator FAILs are inherited class, not new defects.** The
  `runtime manifest names a file git does not track` count moved 71 → 73
  because `account_list.py` and `test_t1936_launch_account_list.py` are new and
  no commit is authorized. All 73 clear by the same authorized commit.
- **Antigravity remains launch-unproven.** Its registry row declares no
  `launch_executable`, so the row answers `DIRECT_UNSAFE`. Wiring that adapter's
  executable is a separate change.
