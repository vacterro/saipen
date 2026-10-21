"""Retired SAIPEN host hook. SAIPEN was uninstalled; this file gates nothing.

A host application that was running when SAIPEN was uninstalled keeps the hook
command it loaded at start. A session started before hook commands carried
their own missing-file guard would run that command against a file that is
gone, the interpreter would exit with status 2, and the host would read that
as a hook that BLOCKS the event: every prompt of a session whose only fault is
predating the uninstall. This file stands where the hook stood so that command
exits 0 and does nothing.

Safe to delete once no such session is running. The installer replaces it and
the uninstaller removes it when no host application is alive.
"""

SAIPEN_RETIRED_HOST_HOOK = True
