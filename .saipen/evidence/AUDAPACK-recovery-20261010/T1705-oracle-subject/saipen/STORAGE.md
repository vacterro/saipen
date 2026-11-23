# SAIPEN Storage Safety Contract

<!-- RULE-OWNER: STORE-SAFETY-01 -->

Defect class: sole-copy durable state placed under an auto-cleaned HOME or
scratch root. This contract prevents silent loss of model lineage, registry
entries, evidence and project history when temporary storage disappears.

## Classes and lifetimes

`DURABLE` is canonical project state that must survive process exit and reboot:
protocol state, registries, adapters, model cards, accepted checkpoints,
lineage, evidence, deliverables and expensive persistent state. It requires an
explicit owner, stable path, trusted durable root and recovery policy. No
durable path may be under an effective ephemeral root. The operator, not path
spelling, decides which non-temporary roots are trusted.

`EPHEMERAL` means **safe to delete at any instant**. It may hold scratch
checkpoints, staging, test files and other disposable intermediates. It must
never be the only authoritative copy of important data or a canonical registry
target. `CACHE` may be discarded without correctness loss; rebuilding it may
cost time, but it holds no unique truth. `EXTERNAL` is user-owned data outside
SAIPEN ownership; SAIPEN may inspect it but may not move or delete it without
an explicit contract.

Stores with `REBOOT`, `PROJECT` or `PERMANENT` lifetime require `DURABLE`.
`RUN` and `SESSION` stores may be ephemeral. Optional scratch failure does not
block a project that can proceed without it or use a durable fallback.

## Machine policy and project declarations

The existing SAIPEN user configuration home owns `STORAGE_POLICY.json` with
`durable_roots`, user-defined `ephemeral_roots` and optional `scratch_root`.
OS `TEMP`, `TMP`, `TMPDIR` and the platform temporary directory are always
ephemeral. Custom cleanup roots must be registered explicitly. Classification
expands environment variables, normalizes relative paths and slashes, resolves
existing links/reparse targets where possible, and compares by platform path
identity. An ephemeral match wins over a durable match. An unknown path never
silently gains durable trust.

Each project may declare named stores in `.saipen/STORES.json`; the declaration
includes class, lifetime, resolved path, owner and recovery class. Its own
canonical file must be durable when declaring durable stores. The engine
validates the live machine policy against the declaration at use time. A
project may keep durable data in project-local ignored state or in a configured
machine-wide root. Neither location is assumed safe merely from its name.

`saipen storage status` shows policy and effective ephemeral roots.
`saipen storage durable show|set|add|remove <root>` manages trusted roots.
`saipen storage ephemeral show|add|remove <root>` manages custom cleanup roots.
`saipen storage scratch show|set <root>|unset` manages optional scratch.
`saipen storage classify <path> <class>` explains a path decision.
`saipen storage store declare <name> <class> <path> <lifetime> <owner> <recovery>`
declares a project store; `store list` shows declarations.

## Canonical publication and recovery

`saipen storage promote <id> <source> <store> [--sha256 <digest>]` copies a file
or complete directory tree to a digest-named object under a declared durable
store, verifies names, content hashes and size, then atomically replaces the
project `STORAGE_REGISTRY.json` pointer. The source remains untouched. A crash
before pointer replacement leaves the old registry valid; an orphan verified
object is not canonical.
An ephemeral source path in provenance is explicitly marked transient and is
never the canonical pointer. New promotions are blocked while existing
canonical records are invalid; migrate legacy references first.
Promotion from scratch is mandatory before a checkpoint, model or evidence
becomes authoritative. A `RECONSTRUCTABLE` artifact also requires
`--rebuild-command <command>` as provenance. `saipen storage migrate <id>
<store>` copies an existing registered artifact to durable storage, verifies
its recorded hash, updates the pointer atomically and records `migrated_from`.
It never silently relocates unrelated user files.

`saipen storage verify` checks every declared store and registered artifact.
The Core validator, fast transactional checker and ticket completion gate also
check projects carrying storage declarations or a storage registry. A canonical
artifact under an ephemeral root, outside its store, missing or hash-mismatched
is a hard failure. A missing record remains in the registry: absence is not a
fresh installation. The finding names the exact artifact, path and recovery
class (`RECONSTRUCTABLE`, `PARTIAL`, `UNRECOVERABLE`); reconstructable records
carry the recorded rebuild command. Rebuilds require actual source evidence;
unrecoverable history is reported, never fabricated.

The storage registry is an engine-managed reference surface. Projects with
their own registries must verify every canonical path against the same policy
and ensure required artifacts exist in durable storage before promotion or
completion. Merely declaring a store does not inspect a third-party registry.
