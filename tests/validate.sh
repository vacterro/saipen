#!/bin/bash
# asp conformance validator

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}asp conformance validation starting...${NC}"

# 1. Check STATE.md
if [ ! -f ".asp/STATE.md" ]; then
    echo -e "${RED}FAIL: STATE.md missing${NC}"
    exit 1
fi
grep -qE "phase:[[:space:]]+(INIT|PLAN|SCOUT|BUILD|VERIFY|REVIEW|SHIP|DONE|BLOCKED|VALIDATE)" .asp/STATE.md || { echo -e "${RED}FAIL: STATE.md missing valid phase${NC}"; exit 1; }
grep -q "task:" .asp/STATE.md || { echo -e "${RED}FAIL: STATE.md missing task${NC}"; exit 1; }
grep -q "next_action:" .asp/STATE.md || { echo -e "${RED}FAIL: STATE.md missing next_action${NC}"; exit 1; }
grep -q "blocker:" .asp/STATE.md || { echo -e "${RED}FAIL: STATE.md missing blocker${NC}"; exit 1; }
grep -q "agent:" .asp/STATE.md || { echo -e "${RED}FAIL: STATE.md missing agent${NC}"; exit 1; }
grep -q "updated:" .asp/STATE.md || { echo -e "${RED}FAIL: STATE.md missing updated${NC}"; exit 1; }
echo -e "${GREEN}PASS: STATE.md schema valid${NC}"

# 2. Check BOARD.md (cycles are complex in pure bash, doing basic syntax check)
if [ ! -f ".asp/BOARD.md" ]; then
    echo -e "${RED}FAIL: BOARD.md missing${NC}"
    exit 1
fi
echo -e "${GREEN}PASS: BOARD.md exists (acyclic check requires powershell/python wrapper currently)${NC}"

# 3. Check LOG.md
if [ -f ".asp/LOG.md" ]; then
    grep -vE "^#" .asp/LOG.md | grep -vE "^$" | grep -qE "^-[[:space:]]+\[E-[0-9]+\]([[:space:]]+\[parent:[[:space:]]+E-[0-9]+\])?" || {
        BAD_LINES=$(grep -vE "^#" .asp/LOG.md | grep -vE "^$" | grep -vE "^-[[:space:]]+\[E-[0-9]+\]([[:space:]]+\[parent:[[:space:]]+E-[0-9]+\])?")
        if [ -n "$BAD_LINES" ]; then
            echo -e "${RED}FAIL: LOG.md entry violates Graph Event format${NC}"
            exit 1
        fi
    }
    echo -e "${GREEN}PASS: LOG.md format valid${NC}"
fi

# 4. Check KNOWLEDGE/
if [ -d ".asp/KNOWLEDGE" ]; then
    if grep -rE "^-[[:space:]]+[0-9]{2,4}[-/.][0-9]{2}[-/.][0-9]{2}.*(RUN|DEC|H):" .asp/KNOWLEDGE/ >/dev/null 2>&1; then
        echo -e "${RED}FAIL: KNOWLEDGE/ leak: found event journal syntax${NC}"
        exit 1
    fi
    echo -e "${GREEN}PASS: KNOWLEDGE/ clean${NC}"
fi

echo -e "${GREEN}Validation complete. Agent is conformant.${NC}"
