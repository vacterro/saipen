"""A disposable copy of the repository WITH its real project memory.

Usage: live_copy.py <repo> <dst>

The tree is copied without VCS and caches; `.saipen` is copied without the
bulky subtrees a ledger move never reads (evidence bodies, kitchen, caches,
translation and exchange stores). Nothing is written to <repo>.
"""
import os
import shutil
import stat
import sys
from pathlib import Path

src = Path(sys.argv[1]).resolve()
dst = Path(sys.argv[2]).resolve()
assert src != dst and src not in dst.parents, (src, dst)


def _writable(function, path, _info):
    """Git object files are read-only; clear the bit and retry the removal."""
    os.chmod(path, stat.S_IWRITE)
    function(path)


if dst.exists():
    shutil.rmtree(dst, onerror=_writable)
skip_tree = {
    ".git", ".saipen", "__pycache__", ".pytest_cache", ".ruff_cache",
    ".workbuddy-ai", ".codenomad", ".freebuff", ".claude",
}
shutil.copytree(
    src, dst, ignore=lambda d, names: [n for n in names if n in skip_tree or n.endswith(".pyc")]
)
skip_memory = {"cache", "tmp", "saitranslate", "exchange", "locks"}
shutil.copytree(
    src / ".saipen",
    dst / ".saipen",
    ignore=lambda d, names: [
        n
        for n in names
        if (Path(d) == src / ".saipen" and n in skip_memory)
        or n == ".git"
        or n.endswith((".tmp", ".lock"))
    ],
)
count = sum(1 for _ in (dst / ".saipen").rglob("*"))
print("copied", dst, "memory nodes", count)
