# SRC-227 / T-1728 local optional verification pool: bounded preflight

Status: QUEUED, P2. The exact request remains in SRC-227 and in `.saipen/tmp/operator-optional-verification-pool-20261012.txt`. Active recovery T-1726 was not preempted. No auxiliary job, consent setting, provider configuration change, model request or installed integration has been launched by this preflight.

Subsequent SRC-228 / T-1729 requests the operator-decision repair immediately after T-1726 fully completes. E-14721 canonically parks this optional Work as SEQUENCED_AFTER:T-1726,T-1729; E-14720 preserves the new mission's after-current boundary. No primary WAIT was introduced by this optional pool, and no task is closed by the queue bookkeeping.

The current operator explicitly grants continuing safe, bounded auxiliary verification for this installation until revocation. Historical T-1367/T-1446 and SRC-049/050/062 show usage; they are not the basis for a permanent permission. This new request supplies the permission within its stated privacy, ownership and resource bounds.

Read-only source inspection while the primary verification tree was frozen found these existing owners:

- `tools/userperson.py:user_config_home` / `user_config_home_resolved`: the one global user configuration resolver. It respects SAIPEN_USER_CONFIG_HOME and platform configuration roots, creates nothing during resolution, and does not use project memory or saipen_home as a fallback. `mutate_global_profile` already serializes local profile changes. Inspect this first for a local operator consent entry; do not create a second authorization engine or export consent in project protocol/defaults.
- `tools/saipen_engine/storage.py`: an existing installation-local policy pattern using the same resolver, `file_writer_lock`, bounded regular-file reads and `safe_atomic_write_bytes`. STORAGE_POLICY itself has a closed storage-only schema; adding model authorization to that unrelated file would conflate owners.
- `tools/saipen_engine/host_integration.py:mode` and host authority client/broker: admission policy is separate from optional model consent. The broker's policy.json override is explicitly diagnostic-only and production policy comes from its registry. Do not repurpose broker admission or weaken host trust to implement this pool.
- `saipen/RUNTIME.md` and `tools/saipen_engine/host_iteration.py`: fresh per-executor capability admission, bounded VERIFY_ONLY helper strategy, routing exhaustion and model-turn/goal-completion separation already exist. Runtime identity metadata is not consent and is not evidence of a historically observed model still being available.
- `tools/saipen_engine/worker.py`: existing bounded process-tree termination, slices and cancellation supervision. `take_authority` controls the primary worker and must not be called against another live task merely to run auxiliary verification. Reuse process/cancellation primitives without inheriting primary worker ownership.
- `tools/t1363_field_polygon.py`, `tools/t1446_field_soak.py`: existing OpenCode provider routing through sairoute/SAIFREN and disposable Git project helpers. The field harness explicitly records that a non-worktree fixture once allowed a host to bind to the live repository. Working directory alone is not a demonstrated isolation boundary. Historical model strings and endpoints are not current discovery results.
- `tools/test_t1619_iteration_boundary.py`: existing reference controller controls for fresh capability admission and exhausted routes, not a live provider proof.

The graph service returned Transport closed for discovery and coverage. Exact source fallback was used; no indexed generation or exhaustive architecture claim is available.

Implementation still due after the higher-priority recovery permits it:

1. Choose the closest existing local operator extension point after checking its semantics. Keep this consent local to the actual installation and disabled in public/default distributions. Provide explicit revocation and check it immediately before every launch.
2. Discover the configured runtime and available routed models at execution time with a bounded read-only discovery call. Reuse the actual configured provider route. Do not modify SAIFREN, SAIRoute, 9router or unrelated active sessions.
3. Admit only an owned optional verification job with bounded count/time/output/concurrency and existing cancellation behavior. Auxiliary model output must remain data, with no canonical completion or ownership authority.
4. Use verified disposable targets for any destructive control; exclude credentials, private evidence and unrestricted workspace contents from forwarded input. A tool-free model call is preferable for the first synthetic route proof, but its actual host enforcement must be inspected and tested rather than assumed from an agent name.
5. Record requested and observed provider/model identity separately, purpose, execution boundary, selected input provenance, result, contradictions and independent reproduction. If an intermediary does not expose the underlying model, record that identity as unknown rather than inventing it.
6. Exercise acceptance A-H, including disabled/unavailable behavior, revocation, hostile output, concurrency and one real bounded synthetic E2E request through the configured route. Unavailable/exhausted/unreliable auxiliary capacity must not introduce a primary WAIT or substitute for required executable/human evidence.

No new Core dependency or generic protocol extension has yet been shown necessary. Current uncertainty is the final local consent representation and the actual host's safe, tool-free routing boundary. These are engineering checks for the queued ticket, not a fresh operator permission question.
