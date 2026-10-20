"""Reviewed, synthetic demo fixtures; never a cache of users' conversations.

Call only for an explicitly requested demo. Exact source/byte matching remains
mandatory: changing a customer name, whitespace, pixels or image metadata falls
back to the normal model pipeline. This module neither saves data nor calls LLMs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

from ai_service import validate_result


DATA = Path(__file__).resolve().parent / 'demo_data'
IMAGE_SHA256 = '6a11bf601a1439f071b445c06ce6c82302aabd5a821cb337e7d39d359467f721'
CUSTOMER_PREFIX = '客户名称：演示客户\n'


def _reference_date():
    return datetime.now(timezone(timedelta(hours=8))).date()


def get_demo_analysis(text: str, image_bytes: bytes | None = None,
                      image_mime: str | None = None) -> dict | None:
    """Return {result: seven-field AIOutput, transcript: str}, or no match.

    The caller must set is_sample=True, skip customer profile persistence and
    require an explicit demo opt-in. Text fixture dates remain literal dates in
    the source. Screenshot relative dates are clearly inferred and confirmed.
    """
    if not isinstance(text, str):
        return None
    if image_bytes is not None:
        if (text not in ('', CUSTOMER_PREFIX) or image_mime != 'image/png'
                or sha256(image_bytes).hexdigest() != IMAGE_SHA256):
            return None
        transcript = (DATA / 'image-transcript.txt').read_text(encoding='utf-8')
        raw = (DATA / 'image-result.json').read_text(encoding='utf-8')
        today = _reference_date()
        delivery = today.replace(month=11, day=20)
        if delivery < today:
            delivery = delivery.replace(year=delivery.year + 1)
        raw = raw.replace('{{tomorrow}}', (today + timedelta(days=1)).isoformat())
        raw = raw.replace('{{delivery_date}}', delivery.isoformat())
        result = json.loads(raw)
        source = f'{text}{transcript}'
    else:
        source_text = (DATA / 'text-source.txt').read_text(encoding='utf-8')
        if text not in (source_text, CUSTOMER_PREFIX + source_text):
            return None
        transcript = ''
        source = text
        result = json.loads((DATA / 'text-result.json').read_text(encoding='utf-8'))
    # Use exactly the live schema and literal evidence checks, with no bypass.
    validated = validate_result(result, source)
    validated.pop('is_sample', None)
    return {'result': validated, 'transcript': transcript}
