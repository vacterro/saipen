<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: tools/saipen_engine/gc.py, evidence lifecycle, LOG citation grammar, verification evidence
status: active
trigger: a collector treats a LOG citation as a replacement for the JSON payload it points at
evidence: T-2049, .saipen/evidence/core-unit/d2c23352301d9b07-20261112T052511797715Z.json, tools/test_gc.py
supersedes: none

# A LOG citation is a pointer, never a replacement for the JSON payload

The LOG's `record:<path> sha256:<hex>` line proves a record existed and pins its bytes; it does not carry the record's content. A collector that reclaims the file because the LOG cites it destroys proof that consumers (ship_gate, publication_gate, compatible_records) still read.

Why:
The GC engine's first live run deleted 738 evidence JSON records, 576 of them never git-tracked and therefore unrecoverable. The classification was correct for raw execution payloads, where the citation is a compact receipt, but wrong for canonical verification proof, where the file IS the artifact. The fix keeps core-unit/focused-unit PASS records whenever they are cited and past grace; the citation remains a pointer and the payload stays on disk. The distinction is not the citation, it is whether a consumer reads the file.
