"""POSIX verification bootstrap: ownership handshake and parent-death cleanup.

Executed with isolated Python (-I -S); no project/site code runs before the
parent records its reader. The guardian holds no verifier stdio or user FDs.
It observes an owned pipe, never verdicts, tickets or operator authority.
"""
from __future__ import annotations

import contextlib
import json
import os
import signal
import sys
import time
from pathlib import Path


def remove_guard_files(ready, info):
    """Remove only this launcher's private handshake files, never a tree."""
    for name in (ready, info):
        with contextlib.suppress(OSError):
            Path(name).unlink()
    with contextlib.suppress(OSError):
        Path(info).parent.rmdir()


def main(arguments):
    parent, descriptor, ready, info, executable, *command = arguments
    parent, descriptor = int(parent), int(descriptor)
    if not command or os.getppid() != parent:
        remove_guard_files(ready, info)
        return 125
    group = os.getpgrp()
    if group != os.getpid():
        return 126  # Never signal a group not created for this verifier.
    os.set_inheritable(descriptor, False)
    guardian = os.fork()
    if guardian == 0:
        # A guardian retaining stdout/stderr would prevent communicate() from
        # reaching EOF after the actual verifier exits. User pass_fds must not
        # remain held by the guardian either.
        descriptors = [int(name) for name in os.listdir("/proc/self/fd") if name.isdigit()]
        for other in descriptors:
            if other != descriptor:
                with contextlib.suppress(OSError):
                    os.close(other)
        try:
            while os.read(descriptor, 1):
                pass
        finally:
            remove_guard_files(ready, info)
            with contextlib.suppress(ProcessLookupError):
                os.killpg(group, signal.SIGKILL)
        os._exit(0)
    Path(info).write_text(json.dumps({"pid": guardian, "group": group}), encoding="utf-8")
    while not Path(ready).exists():
        if os.getppid() != parent:
            return 125
        time.sleep(0.01)
    if os.getppid() != parent:
        return 125
    os.execvpe(executable, command, os.environ)
    return 127


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
