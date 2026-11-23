"""Read-only logical-role and duplicate inventory; no deletion or migration."""
from __future__ import annotations
import collections
import hashlib
import json
import os
import stat
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
MEM=ROOT/".saipen"
groups=collections.defaultdict(list)
totals=collections.Counter()
skipped=[]
for directory, dirs, files in os.walk(MEM, followlinks=False):
    kept=[]
    for name in dirs:
        p=Path(directory)/name
        info=p.lstat()
        if p.is_symlink() or getattr(info,"st_file_attributes",0)&0x400:
            skipped.append(p.relative_to(ROOT).as_posix())
        else:
            kept.append(name)
    dirs[:]=kept
    for name in files:
        p=Path(directory)/name
        try:
            info=p.lstat()
            if not stat.S_ISREG(info.st_mode) or p.is_symlink():
                skipped.append(p.relative_to(ROOT).as_posix())
                continue
        except OSError:
            continue
        rel=p.relative_to(MEM).as_posix()
        top=rel.split("/",1)[0]
        totals[top]+=info.st_size
        if 0<info.st_size<=32*1024*1024:
            groups[info.st_size].append(p)
budget=128*1024*1024
processed=0
duplicates=[]
for size, paths in sorted(groups.items(),reverse=True):
    if len(paths)<2 or processed+size*len(paths)>budget:
        continue
    by_hash=collections.defaultdict(list)
    for p in paths:
        try:
            raw=p.read_bytes()
            if len(raw)!=size:
                continue
        except OSError:
            continue
        processed+=len(raw)
        by_hash[hashlib.sha256(raw).hexdigest()].append(p.relative_to(ROOT).as_posix())
    for digest, matches in by_hash.items():
        if len(matches)>1:
            duplicates.append({"sha256":digest,"size":size,"paths":matches,
                               "logical_duplicate_bytes":size*(len(matches)-1)})
result={
 "scope":"metadata inventory plus size-filtered SHA256 duplicates within a fixed read budget",
 "logical_bytes_by_top_level":dict(totals),"logical_total_bytes":sum(totals.values()),
 "duplicate_read_budget":budget,"duplicate_bytes_hashed":processed,
 "duplicate_groups":duplicates,"potential_identical_bytes":sum(x["logical_duplicate_bytes"] for x in duplicates),
 "skipped_link_or_special_paths":skipped,
 "actual_saving_bytes":0,"migration_or_deletion_performed":False,
 "roles":[
  {"role":"ACTIVE STATE","basis":"CORE File Model exact STATE/BOARD/LOG paths","physical_retention":"UNKNOWN pending operator storage-root decision"},
  {"role":"IMMUTABLE EVIDENCE","basis":"CORE EVIDENCE-RETENTION-01 and Source lifecycle, not directory-name heuristics","physical_retention":"UNKNOWN pending decision; retain all proof"},
  {"role":"DERIVED INDEX","basis":"KNOWLEDGE INDEX generated/deletable contract; runtime rebuilds it from active cards","caveat":"does not make original cards or source receipts disposable"},
  {"role":"DISPOSABLE CACHE","basis":"only producer-confirmed reconstructable entries or run-owned ephemera","caveat":"live inflight markers and unresolved records cannot be bulk-deleted as cache"},
  {"role":"HISTORICAL ARCHIVE","basis":"SOURCES archive/tombstone hash/reference lifecycle and sealed LOG authority","caveat":"preserve hashes, ownership, original attribution and lookup references"}
 ],
 "decision":"No dedup migration: exact byte equality alone does not prove compatible readers, immutable aliases, rollback or crash-safe reference updates. Unknown ownership/retention remains protected."
}
(OUT/"storage-inventory.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:result[k] for k in ("logical_total_bytes","duplicate_bytes_hashed","potential_identical_bytes","actual_saving_bytes","migration_or_deletion_performed")}))

