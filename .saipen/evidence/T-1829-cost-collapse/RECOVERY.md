# Exact Git object recovery — 2026-10-20 continuation

Publication is blocked by missing original Git history. This is not a source or
test PASS, and the campaign remains incomplete. `RECOVERY.json` contains the
measurements and preservation checks at checkpoint E-16888.

This continuation recovered 134 original objects: 109 trees, 24 blobs and one
commit. Together with the preceding 393-blob repair, all 527 admitted objects
were reread through Git and their full preimages independently rehashed. Only
objects whose complete payload reproduced an already requested original SHA1
were admitted. No synthetic replacement commit, history graft or ref rewrite
was made.

The recovered commit is `7145548211d2ee3ca9babf5e8b251960ea8f0527`. Its exact
preimage combines the retained T-1298 private-index tree and the original reflog
identity, timestamp, parent and message. The commit hash matches the original;
its parent `380b30f6374f31e37d10919d1a4ded36be9dc598` remains unavailable.
Private reconstruction copies preserved all four original auxiliary indices.
Directory candidates are cached under `.saipen/cache/`; every actual admission
still checks the complete object preimage. Cache files grant no authority.

There are currently 112 visible missing objects. Recovering a tree or commit can
expose additional missing descendants, so the frontier count is not a subtraction
from the original 507. The current exact frontier is in `RECOVERY.json` and
`head-connectivity-final-recovery.txt`.

HEAD, every original ref, and the exact staged entries match the pre-recovery
backup. One directory pass observed changed index file bytes while all staged
entries, HEAD and refs remained identical; it correctly stopped. The metadata
writer is unknown. Recovery never rewrote the original index, and full index
byte equality is not claimed. Later passes revalidated their own index bytes.
At the object-recovery checkpoint the product fingerprint was
`872b291b3570fe30cdc268eba74cfae5d5f97be91ad7bea320b5dbc743a24d0f`.
Subsequent T-1842 protocol compaction creates a different source generation;
this recovery report does not certify that later product revision.

All three existing pack/index pairs pass `git verify-pack`. Exact candidates
from the existing workspace, Git scratch/lost-found files, four retained private
indices, two registered machine-runtime generations and the installed skill
yield no further match for the current frontier. The one-entry `.saipen` root
substitution hypothesis was tested against 46,052 actual candidate tree IDs and
rejected; no guessed payload was admitted.

Normal authenticated remote probes were repeated. GitHub refuses with HTTP 403
and the explicit suspended-account diagnostic. GitLab advertises only main at
`4f03d79f7ec8da4f3ad458128cc7da81e5ee5dce`; an ordinary request for the missing
parent in the isolated recovery clone returns `upload-pack: not our ref`.
There was no credential or provider bypass. Exact outputs are preserved in
`remote-recovery-current.json` and `gitlab-object-fetch-current.json`.

Required external input: an intact original repository/object backup containing
the missing parent and remaining objects, or restored normal access to the
original remote. Inspect that source read-only, import only verified original
objects, rerun connectivity, then resume final batch attribution and the gate
order in `ACCEPTANCE.md`. An expensive unchanged full suite cannot repair history
and has not been repeated. All eleven mission clauses remain unclosed.
