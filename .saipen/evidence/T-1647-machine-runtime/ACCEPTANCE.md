# T-1647 / SRC-188 -- what was built, what was measured, what is owed

## Measured on this machine before any change (2026-10-06)

- Managed accounts: `antigravity_b` (SID ...-1008), `SAIAG_9fabb0d5` (...-1019).
  SAI Accounts grants each one `(OI)(CI)(M)` on the workdirs listed in
  `C:\ProgramData\SAI\Accounts\grants.json` (eight grants) and nothing else.
- The home every project records (`V:\...\_SAIPEN`) carries no entry for a
  managed account, and its parents carry no `Users` entry: unreadable to them.
- The only Python is a per-user install (access list: the operator, SYSTEM,
  Administrators). `C:\Windows\py.exe` finds no interpreter for another
  account. Both `bin/` launchers name that interpreter by absolute path.
- `C:\ProgramData\SAI` is readable and executable by `Users`, fully controlled
  by the operator, and inherits one entry that lets `Users` add files.

## The engine defects, each reproduced with a real access list

| asked of the pre-fix engine | answered |
|---|---|
| `persisted_home_error` on a home this account is denied | raises `PermissionError [WinError 5]` |
| `checkpoint`, `continue`, `rebind-home --auto` on that project | exit 1 with a traceback |
| `rebind-home <this checkout>` | `HOME_REBOUND`: the project's pointer is rewritten |
| any command on a project this account may not read | exit 1 with a traceback at `_valid_saipen_dir` |
| `checkpoint` on a project granted for reading only | exit 1 with a traceback at the writer lock |

The third row is how a public clone of another version would have become the
project's home for every account.

## What the slice does

1. `tools/saipen_engine/machine_runtime.py` -- `saipen host machine
   [status|install|remove]`. `install` projects the running runtime into
   `%ProgramData%\SAI\SAIPEN\runtime\<generation>` (it proves the SAME
   `runtime_surface` identity as its source), copies an interpreter into
   `python\<version>` when the installer's is inside a user profile, writes two
   relocatable launchers into `bin\` and a `registration.json`, and cuts
   inheritance on the root: SYSTEM, Administrators and the installer full,
   `Users` read and execute, nobody else anything. `status` proves the
   generation from the bytes and reads the access list; a runtime another
   account can write is BROKEN. `saipen_runtime_ready` is the fact an account
   manager consumes.
2. A home this account may not read is INACCESSIBLE, not dead: refused as
   `CROSS_USER_RUNTIME_UNAVAILABLE` with no rebind route, and both rebind forms
   refuse it. Under the registered machine runtime it is covered: the project
   routes and checkpoints, and its recorded pointer is left unchanged
   (`INACCESSIBLE_BUT_REPLACED`).
3. `continue --json` hands out document paths of the runtime the account can
   read (`cold_route.runtime_source: MACHINE_RUNTIME`).
4. `saipen host doctor` shows the machine runtime; `saipen host repair`
   refreshes one that exists from the source it was projected from, never from
   another checkout; the run that refreshes agent homes (`tools/autoinject.py`)
   carries it along, and `--check` reports its drift without writing.
5. A project this account may not read is answered as that
   (`PROJECT_BINDING_INVALID`, "may not read ... needs a grant"); one granted
   for reading only refuses the write as `CAPABILITY_READ_ONLY`. Runtime access
   and project access stay two grants.
6. The injected block names the machine launcher for an unreadable home; BOOT
   and RUNTIME.md state the rule. RUNTIME.md pays for its section by
   shortening three passages; no rule was dropped.
7. The test harness points every fixture at a machine root that does not
   exist, so no test reads or refreshes the operator's real one.

## What the review pass added (the first REVIEW found a P1)

The first version read the access list and never the owner. `%ProgramData%\SAI`
lets `Users` create a subfolder, so an account that created
`%ProgramData%\SAI\SAIPEN` (or one entry in it) before the install would own
it, and an owner may rewrite an access list whatever the list says: the
runtime would have read READY while that account could re-grant itself write
access at any moment. Closed as follows:

- `status` walks the root and every entry: one owned by an account other than
  the installer, Administrators or SYSTEM is BROKEN (`acl.foreign_owners`).
- `install` refuses a root another account created, before projecting a byte.
- The installer a registration names is believed only when it is the asking
  account, the owner of the install the asker runs, Administrators or SYSTEM.
  A registration that names its own author is not a credential.
- A machine runtime stands in for ONE install, the one it was projected from
  (`source_root`). A project whose unreadable home is some other install is
  refused, with the projected source named, instead of being served from
  another install's bytes.
- `install` refuses a source inside the machine root (it would have become its
  own source), a registration may only name `runtime/<generation>`, and a
  bundled interpreter must lie inside the root.
- The asking account's SID is read from its own token; no program is looked up
  on PATH to answer who is asking.

Limit of the proof, stated: another account's ownership is simulated in the
tests at the single place the system is asked (`_owner`), because giving a
file to another account needs a privilege a test does not hold. The walk, the
refusal and the real owner lookup are exercised for real.

## Evidence in this directory

- `regression_pair.txt`, `red_half_tests.txt` -- the same 75-case module
  against the pre-fix subject (67 cases red and the second-principal class
  unable to start, the one control green on both sides) and the repaired
  subject (all green, none skipped).
- `machine_install.json`, `machine_status.json`, `machine_root_acl.txt` -- the
  runtime installed on this machine on 2026-10-07, read back.
- `e2e_another_principal.py` / `.txt` -- the SRC-188 scenario on the REAL
  machine runtime with the REAL operator profile, home and interpreter closed:
  twelve expectations, all held.

## Who asked: the second principal, and what it is not

`another_principal_token` (in `tools/test_t1647_machine_runtime.py`) starts a
process under the operator's own token with the operator's SID and every group
a fresh local account lacks turned deny-only, all privileges but traversal
removed. The kernel then decides every access list for `Users`,
`Authenticated Users` and `Everyone` only -- what a managed account shares
with the operator. No credential is used and nothing is borrowed from another
account. It is the same decision by the same kernel on the same access lists;
it is **not** a logon as `antigravity_b`.

## SRC-188, by section

| section | state |
|---|---|
| security invariant, least privilege | done; proven by the access list and by the second principal's refused reads and writes |
| account-independent runtime surface | done: architecture A, one machine-scoped read-only runtime with its own interpreter |
| launcher availability | done for every account at once: `%ProgramData%\SAI\SAIPEN\bin\saipen(.cmd)`, relocatable, no PATH. Open: the launcher is not on the machine PATH (needs elevation) |
| exact runtime compatibility, public repository is not authority | done: generation identity proven; the runtime serves only projects whose recorded home is the install it was projected from; the version guard refuses a newer project; rebind refused for an unreadable home |
| project portability, backward compatibility | done: the recorded pointer stays; ACCESS_DENIED is classified, never treated as corruption |
| BOOT / SKILL access | done in the runtime and the injected block. OPEN: a project that still carries the legacy project-level block (`## saipen protocol (any agent)`, measured in AUDAPACK `AGENTS.md`) is told to read the operator's skill directory and to clone the public repository; nothing refreshes or reports that block |
| no manual BOARD fallback | kept: every refusal still refuses |
| automatic recovery, question suppression | done in the engine: one code, one action, no rebind. Depends on the open row above for a project with the legacy block |
| regression: managed account | done with the second principal (above); the logon as the real account is the manual run below |
| security negative control | done: operator profile, home and interpreter stay closed before and after |
| version-mismatch control | done |
| multi-account matrix | operator and one equivalent principal measured; `antigravity_b` and a second managed SID are the manual run below |
| runtime upgrade | done: `host repair` and the agent-home refresh both follow the source; the previous generation is kept; drift reads STALE |
| doctor | done: machine row; per-project facts in `host bootstrap --json` |
| SAI Accounts integration, account creation / repair | NOT in this repository: SAI Accounts must read `saipen host machine status --json` (`saipen_runtime_ready`), run `saipen host machine install` when it is false, and stop reporting an account ready while it is false |

## The manual run that is still owed (a request, not a verdict)

As `antigravity_b`, in a granted project (for example AUDAPACK), with nothing
on PATH:

    C:\ProgramData\SAI\SAIPEN\bin\saipen.cmd host bootstrap --json
    C:\ProgramData\SAI\SAIPEN\bin\saipen.cmd continue --json
    type C:\Users\<operator>\.claude\CLAUDE.md

Expected: `HOST_BOOTSTRAP_BOUND` with `runtime_source: MACHINE_RUNTIME` and
`binding.legacy_saipen_home: INACCESSIBLE_BUT_REPLACED`; `continue` names the
project's current Work with a `load_path` under `C:\ProgramData\SAI\SAIPEN`;
the last command answers Access is denied.

## Reversal

`saipen host machine remove` deletes `%ProgramData%\SAI\SAIPEN` and nothing
else. No access list outside that directory was changed by this work.
