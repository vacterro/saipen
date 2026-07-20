#!/usr/bin/env bash
# saipen state exporter (macOS/Linux)
set -u

PROJECT_ROOT="$(pwd)"
SAIPEN_DIR="$PROJECT_ROOT/.saipen"

if [ ! -d "$SAIPEN_DIR" ]; then
    echo "No .saipen directory found in $PROJECT_ROOT."
    exit 1
fi

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TAR_NAME="saipen_export_${TIMESTAMP}.tar.gz"

echo "saipen state exporter"
echo "------------------------------------------------------------"
echo "Archiving: $SAIPEN_DIR"
if ! tar -czf "$TAR_NAME" -C "$PROJECT_ROOT" .saipen; then
    echo "FAILED: tar exited non-zero"
    exit 1
fi
if [ ! -s "$TAR_NAME" ]; then
    echo "FAILED: archive missing or empty at $PROJECT_ROOT/$TAR_NAME after tar reported success"
    exit 1
fi
echo "Done. Export saved to: $PROJECT_ROOT/$TAR_NAME"
echo "------------------------------------------------------------"
