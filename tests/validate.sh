#!/bin/bash
# saipen conformance validator -- FROZEN portable floor (v7.24.0).
# Kept for hosts without Python; new checks land only in tools/validate.py
# (the canonical validator). Don't extend this file.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}saipen conformance validation starting...${NC}"

# 1. Check STATE.md
if [ ! -f ".saipen/STATE.md" ]; then
    echo -e "${RED}FAIL: STATE.md missing${NC}"
    exit 1
fi
grep -qE "phase:[[:space:]]+(INIT|PLAN|SCOUT|BUILD|VERIFY|REVIEW|SHIP|DONE|BLOCKED|VALIDATE|HUNT|MARKHUNT|ADD|CLEAN|TRANSLATE|PREPARE)" .saipen/STATE.md || { echo -e "${RED}FAIL: STATE.md missing valid phase${NC}"; exit 1; }
grep -q "task:" .saipen/STATE.md || { echo -e "${RED}FAIL: STATE.md missing task${NC}"; exit 1; }
grep -q "next_action:" .saipen/STATE.md || { echo -e "${RED}FAIL: STATE.md missing next_action${NC}"; exit 1; }
grep -q "blocker:" .saipen/STATE.md || { echo -e "${RED}FAIL: STATE.md missing blocker${NC}"; exit 1; }
grep -q "agent:" .saipen/STATE.md || { echo -e "${RED}FAIL: STATE.md missing agent${NC}"; exit 1; }
grep -q "updated:" .saipen/STATE.md || { echo -e "${RED}FAIL: STATE.md missing updated${NC}"; exit 1; }
grep -qE "mode:[[:space:]]+(full|read-only|no-publish|manual-verify)" .saipen/STATE.md || { echo -e "${RED}FAIL: STATE.md missing mode, or mode isn't one of full|read-only|no-publish|manual-verify${NC}"; exit 1; }
# saipen_version + transition_from complete RFC § 1.2's nine-field required set.
# They were absent here until v7.96.0, so a host without Python got a PASS on a
# state tools/validate.py FAILs -- a floor that is more permissive than the
# thing it stands in for is worse than no floor. transition_from carries § 1.2's
# fresh-INIT exception: no previous phase exists to name there.
grep -qE "saipen_version:[[:space:]]+[0-9]+" .saipen/STATE.md || { echo -e "${RED}FAIL: STATE.md missing saipen_version (RFC § 1.2)${NC}"; exit 1; }
if ! grep -qE "phase:[[:space:]]+INIT" .saipen/STATE.md; then
    grep -q "transition_from:" .saipen/STATE.md || { echo -e "${RED}FAIL: STATE.md missing transition_from -- required on all non-INIT states (RFC § 1.2)${NC}"; exit 1; }
fi
echo -e "${GREEN}PASS: STATE.md schema valid${NC}"

# 1b2. mode/phase basic compatibility (RFC § 1.3) -- not the full matrix,
# just the restriction stated normatively in prose. The old no-publish/SHIP
# ban was REMOVED here, not merely left out: v7.66.0 made SHIP reachable
# under no-publish (git steps skipped, local ones still run) because banning
# the phase left a git-less project unable to close any ticket. This file is
# frozen against NEW checks; correcting one that now contradicts the RFC is
# a bug fix, not an extension.
if grep -qE "mode:[[:space:]]+read-only" .saipen/STATE.md && grep -qE "phase:[[:space:]]+(INIT|PLAN|ADD|BUILD|SHIP|CLEAN|TRANSLATE)" .saipen/STATE.md; then
    echo -e "${RED}FAIL: mode: read-only MUST NOT enter INIT/PLAN/ADD/BUILD/SHIP/CLEAN/TRANSLATE (RFC § 1.3)${NC}"
    exit 1
fi

# 1b. goal_mode: true requires the persisted safety-valve counters (RFC § 2.4)
if grep -qE "goal_mode:[[:space:]]+true" .saipen/STATE.md; then
    grep -qE "goal_waves:[[:space:]]*[0-9]+" .saipen/STATE.md || { echo -e "${RED}FAIL: goal_mode: true but goal_waves counter missing -- safety valve can't survive a restart without it${NC}"; exit 1; }
    grep -qE "goal_tickets:[[:space:]]*[0-9]+" .saipen/STATE.md || { echo -e "${RED}FAIL: goal_mode: true but goal_tickets counter missing -- safety valve can't survive a restart without it${NC}"; exit 1; }
    echo -e "${GREEN}PASS: goal_mode counters present${NC}"
fi

# 2. Check BOARD.md exists, then real cycle detection via Kahn's algorithm
# (repeatedly remove tickets whose needs: are all already resolved; if a
# pass removes nothing but tickets remain, they form a cycle). Written
# without associative arrays -- macOS ships bash 3.2 as /bin/bash by
# default and declare -A needs bash 4+.
if [ ! -f ".saipen/BOARD.md" ]; then
    echo -e "${RED}FAIL: BOARD.md missing${NC}"
    exit 1
fi

PAIRS=""
while IFS= read -r line; do
    [ -z "$line" ] && continue
    tid=$(echo "$line" | grep -oE 'T-[0-9]+' | head -1)
    needs=$(echo "$line" | grep -oE 'needs:[^|]*' | sed 's/needs://' | grep -oE 'T-[0-9]+' | tr '\n' ',')
    PAIRS="${PAIRS}${tid}|${needs}
"
done <<< "$(grep -oE '\- \[[ x/]\] T-[0-9]+.*' .saipen/BOARD.md || true)"

REMAINING=$(echo "$PAIRS" | grep -oE '^T-[0-9]+' | sort -u || true)
PROGRESS=1
while [ -n "$REMAINING" ] && [ "$PROGRESS" -eq 1 ]; do
    PROGRESS=0
    NEXT_REMAINING=""
    for tid in $REMAINING; do
        needs_csv=$(echo "$PAIRS" | grep "^${tid}|" | head -1 | cut -d'|' -f2)
        blocked=0
        for need in $(echo "$needs_csv" | tr ',' ' '); do
            if echo "$REMAINING" | tr ' ' '\n' | grep -qx "$need"; then
                blocked=1
                break
            fi
        done
        if [ "$blocked" -eq 1 ]; then
            NEXT_REMAINING="$NEXT_REMAINING $tid"
        else
            PROGRESS=1
        fi
    done
    REMAINING=$(echo "$NEXT_REMAINING" | xargs || true)
done
if [ -n "$REMAINING" ]; then
    echo -e "${RED}FAIL: BOARD.md contains cyclic needs: dependencies involving: $REMAINING${NC}"
    exit 1
fi
echo -e "${GREEN}PASS: BOARD.md acyclic${NC}"

# 2b. Check BOARD.md for duplicate ticket IDs -- a status change that
# copied a ticket line instead of moving it (RFC § 1.2) leaves the same
# T-### appearing twice, either within one section or across two.
DUPE_IDS=$(grep -oE '\- \[[ x/]\] T-[0-9]+' .saipen/BOARD.md | grep -oE 'T-[0-9]+' | sort | uniq -d || true)
if [ -n "$DUPE_IDS" ]; then
    echo -e "${RED}FAIL: BOARD.md has duplicate ticket ID(s): $(echo "$DUPE_IDS" | tr '\n' ' ') -- a status change must move the line (cut+paste), never copy it${NC}"
    exit 1
fi
echo -e "${GREEN}PASS: BOARD.md no duplicate tickets${NC}"

# 2c. Check BOARD.md for dangling needs: references -- worse than a cycle:
# a needs: pointing at a T-### that doesn't exist anywhere on the board
# leaves the Pick Rule permanently unsatisfiable with zero diagnostic signal.
ALL_IDS=$(grep -oE '\- \[[ x/]\] T-[0-9]+' .saipen/BOARD.md | grep -oE 'T-[0-9]+' | sort -u)
NEEDS_REFS=$(grep -oE 'needs:[^|]*' .saipen/BOARD.md | sed 's/needs://' | tr ',' '\n' | grep -oE 'T-[0-9]+' | sort -u)
DANGLING=""
for ref in $NEEDS_REFS; do
    echo "$ALL_IDS" | grep -qx "$ref" || DANGLING="$DANGLING $ref"
done
if [ -n "$DANGLING" ]; then
    echo -e "${RED}FAIL: BOARD.md has dangling needs: reference(s):$DANGLING -- referenced ticket doesn't exist anywhere on the board${NC}"
    exit 1
fi
echo -e "${GREEN}PASS: BOARD.md no dangling needs: references${NC}"

# 2d. Check BOARD.md has all four required section headings (RFC § 1.2) --
# the ticket-shape/dangling/cycle checks above never verified the headings
# they scan under actually exist.
for heading in "## DOING" "## TODO" "## DONE" "## BLOCKED"; do
    grep -qxF "$heading" .saipen/BOARD.md || { echo -e "${RED}FAIL: BOARD.md missing required section heading: $heading${NC}"; exit 1; }
done
echo -e "${GREEN}PASS: BOARD.md has all required section headings${NC}"

# 3. Check LOG.md -- every non-empty, non-comment line MUST match (date
# prefix is optional to allow pre-STYLE.md history; new entries carry one).
# Absence is a FAIL, not a skip: RFC § 1.2 requires the file and § 1.5
# Recovery rebuilds from it, so "no LOG.md" silently reporting conformant was
# a gate that could not fail (phases/verify.md). Empty is legal (fresh INIT).
if [ ! -f ".saipen/LOG.md" ]; then
    echo -e "${RED}FAIL: LOG.md missing -- RFC § 1.2 requires it (an empty LOG.md is legal on a fresh project; an absent one is not)${NC}"
    exit 1
fi
if [ -f ".saipen/LOG.md" ]; then
    LOG_PATTERN="^-[[:space:]]+([0-9]{2}[.\/][0-9]{2}[.\/][0-9]{2}[[:space:]]+[0-9]{2}:[0-9]{2}[[:space:]]+)?\[E-[0-9]+\]([[:space:]]+\[parent:[[:space:]]+E-[0-9]+\])?"
    # Strip a leading UTF-8 BOM before matching. tools/validate.py reads with
    # utf-8-sig and never sees one; this floor did, so a BOM'd LOG.md failed
    # here while passing there -- the two validators disagreeing about the same
    # file. Bug fix, not a new check (this file is frozen against the latter).
    BAD_LINES=$(sed '1s/^\xef\xbb\xbf//' .saipen/LOG.md | grep -vE "^#" | grep -vE "^$" | grep -vE "$LOG_PATTERN" || true)
    if [ -n "$BAD_LINES" ]; then
        echo -e "${RED}FAIL: LOG.md entry violates Graph Event format:${NC}"
        echo "$BAD_LINES"
        exit 1
    fi
    echo -e "${GREEN}PASS: LOG.md format valid${NC}"
fi

# 4. Check KNOWLEDGE/
if [ -d ".saipen/KNOWLEDGE" ]; then
    if grep -rE "^-[[:space:]]+[0-9]{2,4}[-/.][0-9]{2}[-/.][0-9]{2}.*(RUN|DEC|H):" .saipen/KNOWLEDGE/ >/dev/null 2>&1; then
        echo -e "${RED}FAIL: KNOWLEDGE/ leak: found event journal syntax${NC}"
        exit 1
    fi
    echo -e "${GREEN}PASS: KNOWLEDGE/ clean${NC}"
fi

# 5. Self-check: README.md's version badge vs VERSION. Only applies when run
# from the saipen repo's own clone root (fingerprinted by saipen/RFC.md sitting
# next to VERSION -- a consuming project's .saipen/ never has that) -- this
# exact drift has now happened three times because it only ever gets caught by
# someone remembering a separate manual grep. Riding along on the validator
# that already runs before every ship means it's caught for free instead.
if [ -f "saipen/RFC.md" ] && [ -f "VERSION" ] && [ -f "README.md" ]; then
    REPO_VERSION=$(tr -d '[:space:]' < VERSION)
    if ! grep -qF "**v${REPO_VERSION}**" README.md; then
        echo -e "${RED}FAIL: README.md badge doesn't match VERSION (${REPO_VERSION}) -- this has drifted before, update the badge${NC}"
        exit 1
    fi
    echo -e "${GREEN}PASS: README.md badge matches VERSION${NC}"
fi

echo -e "${GREEN}Validation complete. Agent is conformant.${NC}"
