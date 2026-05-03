#!/bin/bash
set -e
cd "$(dirname "$0")"

REQ_HASH=$(md5 -q requirements.txt 2>/dev/null || md5sum requirements.txt | cut -d' ' -f1)
HASH_FILE=".venv/.req_hash"

if [ ! -d .venv ] || [ "$(cat "$HASH_FILE" 2>/dev/null)" != "$REQ_HASH" ]; then
    [ ! -d .venv ] && python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
    echo "$REQ_HASH" > "$HASH_FILE"
fi

exec .venv/bin/python -u src/main.py
