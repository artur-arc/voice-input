#!/bin/bash
set -e
cd "$(dirname "$0")"

# Load .env if present
[ -f .env ] && set -a && source .env && set +a

echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] run.sh: starting voice-input" >&2

REQ_HASH=$(md5 -q requirements.txt 2>/dev/null || md5sum requirements.txt | cut -d' ' -f1)
HASH_FILE=".venv/.req_hash"

if [ ! -d .venv ] || [ "$(cat "$HASH_FILE" 2>/dev/null)" != "$REQ_HASH" ]; then
    [ ! -d .venv ] && python3 -m venv .venv
    if ! .venv/bin/pip install -q -r requirements.txt; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] run.sh: pip install failed" >&2
        exit 1
    fi
    echo "$REQ_HASH" > "$HASH_FILE"
fi

exec .venv/bin/python -u src/main.py
