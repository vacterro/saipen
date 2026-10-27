<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: installer, subprocess, user profile, HOME, USERPROFILE, PATH launcher, Windows Bash
trigger: an installer invokes a child that chooses a user home, or a host test redirects only HOME
status: active
evidence: T-1683, tools/test_t1683_launcher_profile.py, .saipen/evidence/T-1683-launcher-profile/pair.json, bootstrap/inject.sh, bootstrap/inject.ps1
supersedes: none

# Pass the selected profile to the child explicitly

When an installer invokes the PATH launcher owner, pass `--home` using the same profile anchor the installer used for its other destinations; a test that redirects `HOME` must also account for a child runtime that chooses `USERPROFILE` on Windows.

Why:
Bash's selected `HOME` and Windows Python's `Path.home()` can name different profiles. A full test family installed its sandbox skill under the former and rewrote the operator's owned PATH launchers under the latter. The owner accepted the write because those launchers were legitimately owned; only the profile selection was wrong. The held red/green shell controls give both profiles owned canaries and prove that only the selected profile changes, without risking the operator's profile.
