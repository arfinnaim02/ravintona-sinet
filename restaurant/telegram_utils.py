# restaurant/telegram_utils.py

from __future__ import annotations

import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from django.conf import settings
from django.core.cache import cache

CACHE_KEY_CHAT_ID = "telegram_group_chat_id_v1"
TELEGRAM_MAX_LEN = 4096  # Telegram message hard limit


def safe(v) -> str:
    """Safe text for Telegram plain messages."""
    if v is None:
        return "-"
    s = str(v).strip()
    return s if s else "-"


def _api_url() -> str:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
    token = token.strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing in settings")
    return f"https://api.telegram.org/bot{token}/sendMessage"


def _get_chat_id() -> str:
    cached = cache.get(CACHE_KEY_CHAT_ID)
    if cached:
        return str(cached).strip()

    chat_id = getattr(settings, "TELEGRAM_GROUP_CHAT_ID", "") or ""
    chat_id = str(chat_id).strip()
    if not chat_id:
        raise ValueError("TELEGRAM_GROUP_CHAT_ID is missing in settings")
    return chat_id


def _remember_chat_id(new_chat_id: str) -> None:
    new_chat_id = str(new_chat_id).strip()
    if not new_chat_id:
        return

    try:
        cache.set(CACHE_KEY_CHAT_ID, new_chat_id, None)
    except Exception:
        pass

    try:
        setattr(settings, "TELEGRAM_GROUP_CHAT_ID", new_chat_id)
    except Exception:
        pass


def _truncate(text: str) -> str:
    text = str(text)
    if len(text) <= TELEGRAM_MAX_LEN:
        return text
    # keep head, add note
    return text[:4000] + "\n…(trimmed)"


def _send_once(text: str, chat_id: str) -> dict:
    payload = {
        "chat_id": str(chat_id),
        "text": _truncate(text),
        "disable_web_page_preview": True,
    }

    data = json.dumps(payload).encode("utf-8")
    req = Request(
        _api_url(),
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8", errors="replace")

    try:
        j = json.loads(raw)
    except Exception:
        raise RuntimeError(f"Telegram returned non-JSON: {raw}") from None

    if not j.get("ok"):
        raise RuntimeError(f"Telegram error: {j}") from None

    return j


def send_telegram_message(text: str, kind: str = "general") -> None:
    """
    Sends a Telegram message.
    Auto-fixes 'group upgraded to supergroup' (migrate_to_chat_id).
    """
    chat_id = _get_chat_id()

    try:
        _send_once(text, chat_id)
        return

    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")

        migrate_to = None
        try:
            j = json.loads(body)
            migrate_to = (j.get("parameters") or {}).get("migrate_to_chat_id")
        except Exception:
            j = None

        if e.code == 400 and migrate_to:
            new_chat_id = str(migrate_to).strip()
            _remember_chat_id(new_chat_id)
            _send_once(text, new_chat_id)
            return

        raise RuntimeError(f"Telegram HTTP {e.code}: {body}") from None


def maps_link(lat: float, lng: float) -> str:
    return f"https://www.google.com/maps?q={lat},{lng}"