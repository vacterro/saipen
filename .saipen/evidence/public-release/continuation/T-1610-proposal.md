# T-1610: returned audit archive references

Observed request: SRC-172. The agent already had twelve actionable clauses,
but asked for the original FastPrompter ZIP's absolute local path after
searching the workspace and ordinary download directories.

The ZIP mentioned by a returned SAIHANDOFF describes the auditor's input.
Its filename alone creates neither a requirement to retrieve it nor proof
that its old sender-side path exists on this agent's host. Preserve and
normalize the supplied handoff; implement and verify its clauses against the
bound current repository. First identify whether a clause actually requires
historical archive bytes, attachments or an exact snapshot comparison.

Only required bytes trigger a bounded autonomous lookup: an explicit path,
actual host attachment carrier, exporter-recorded bundle path, and the named
export/inbox directory in the proven project/silo context. FastPrompter's
current main.py stores records with path/target_dir in silo_bundle_history;
read this metadata without invoking cleanup methods that mutate the profile.
Markdown escapes may be normalized for lookup while the exact source remains
unchanged. A sender-side sandbox path is a transport reference, not a local
Windows path. Matching a basename never proves exact snapshot identity.

If required bytes remain unavailable, preserve that clause as blocked with
the exact missing evidence, continue independent clauses, and claim no
verification based on absent bytes. Do not ask for the original ZIP's local
location or make that question a prerequisite for otherwise runnable work.

Proposed owners: BOOT cold-start pointer and SOURCES source-role policy.
No new archive format, private-path export, full-disk search or fabricated
attachment mapping is needed for this instruction defect. Review the policy
against executable repository gates and a decision matrix covering complete
handoff/no ZIP, essential missing payload, exact-snapshot requirement,
relocated host attachment, escaped basename and conflicting same-name ZIPs.
