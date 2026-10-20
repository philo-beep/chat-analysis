"""Small, short-lived in-memory reuse of fully validated private analyses.

Keys include account/database, exact input, business date, model settings, prompt,
and the entire owner's profile revision. No cache is written to disk.
"""
from collections import OrderedDict
import copy
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from datetime import datetime, timedelta, timezone

_entries = OrderedDict()
_lock = threading.Lock()
TTL_SECONDS = 120
MAX_ENTRIES = 16
MAX_BYTES = 2 * 1024 * 1024


def key(owner_id, text, image, mime):
    if owner_id is None or os.environ.get('FOLLOWUP_CACHE_ENABLED', 'true').lower() == 'false':
        return None
    import database
    from ai_service import load_settings, ROOT
    settings = load_settings()
    with database._connect() as conn:
        revision = [tuple(row) for row in conn.execute(
            'SELECT id,identity_key,version,updated_at FROM customer_profiles WHERE owner_id=? ORDER BY id', (owner_id,))]
    fingerprint = (str(Path(database.DB_PATH).resolve()), owner_id, text, mime,
        hashlib.sha256(image or b'').hexdigest(),
        datetime.now(timezone(timedelta(hours=8))).date().isoformat(), settings.base_url, settings.model,
        settings.reasoning_effort, settings.quality_review, settings.max_tokens,
        hashlib.sha256(settings.api_key.encode()).hexdigest(),
        hashlib.sha256((ROOT/'prompts/analysis.txt').read_bytes()).hexdigest(), revision)
    return hashlib.sha256(json.dumps(fingerprint, ensure_ascii=False).encode()).hexdigest()


def get(cache_key):
    if cache_key is None:
        return None
    with _lock:
        item = _entries.get(cache_key)
        if item is None:
            return None
        if time.monotonic()-item[0] > TTL_SECONDS:
            _entries.pop(cache_key, None)
            return None
        _entries.move_to_end(cache_key)
        return copy.deepcopy(item[1])


def put(cache_key, value):
    if cache_key is None:
        return
    size = len(json.dumps(value, ensure_ascii=False).encode())
    if size > MAX_BYTES:
        return
    with _lock:
        now = time.monotonic()
        for expired in [k for k,v in _entries.items() if now-v[0] > TTL_SECONDS]:
            _entries.pop(expired, None)
        _entries[cache_key] = (now, copy.deepcopy(value), size)
        _entries.move_to_end(cache_key)
        while len(_entries) > MAX_ENTRIES or sum(v[2] for v in _entries.values()) > MAX_BYTES:
            _entries.popitem(last=False)


def clear():
    with _lock:
        _entries.clear()
