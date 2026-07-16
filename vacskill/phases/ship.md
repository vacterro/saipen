# Phase: SHIP

## SHIP -> PUBLISH

Only on `vacskill ship`, or repo has `origin` AND LOG shows prior ship.
Never auto-publish unopted project. Needs 100% green.

1. README beautiful: pitch, features, install, usage, version + changelog link.
2. Version bump (micro -> 3.2.1, feature -> 3.2.0, breaking -> major).
3. .gitignore covers junk + secrets. Empty tmp/, strip debug prints.
4. CHANGELOG.md newest-top. Push.
5. `git tag -a vVERSION -m "line"` + push tags.
6. First publish: confirm name + public/private with user.
7. LOG: `RUN: ship vX.Y.Z -> pushed HASH`.

After SHIP: STATE -> DONE.