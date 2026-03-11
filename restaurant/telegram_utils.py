# restaurant/telegram_utils.py

from __future__ import annotations

import json
from typing import Iterable
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from django.conf import settings
from django.core.cache import cache


CACHE_KEY_CHAT_ID = "telegram_group_chat_id_v1"
TELEGRAM_MAX_LEN = 4096  # Telegram hard limit


def safe(v) -> str:
    """Safe text for Telegram plain messages."""
    if v is None:
        return "-"
    s = str(v).strip()
    return s if s else "-"


def _bot_token() -> str:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
    token = token.strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing in settings")
    return token


def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{_bot_token()}/{method}"


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
    return text[:4000] + "\n…(trimmed)"


def tg_request(method: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = Request(
        _api_url(method),
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")

        migrate_to = None
        try:
            j = json.loads(raw)
            migrate_to = (j.get("parameters") or {}).get("migrate_to_chat_id")
        except Exception:
            j = None

        if e.code == 400 and migrate_to and payload.get("chat_id"):
            new_chat_id = str(migrate_to).strip()
            _remember_chat_id(new_chat_id)

            retry_payload = dict(payload)
            retry_payload["chat_id"] = new_chat_id
            return tg_request(method, retry_payload)

        raise RuntimeError(f"Telegram HTTP {e.code}: {raw}") from None

    try:
        j = json.loads(raw)
    except Exception:
        raise RuntimeError(f"Telegram returned non-JSON: {raw}") from None

    if not j.get("ok"):
        raise RuntimeError(f"Telegram error: {j}") from None

    return j


def send_telegram_message(text: str, kind: str = "general") -> None:
    """
    Backward-compatible plain message sender.
    """
    payload = {
        "chat_id": _get_chat_id(),
        "text": _truncate(text),
        "disable_web_page_preview": True,
    }
    tg_request("sendMessage", payload)


def send_telegram_message_full(
    *,
    text: str,
    chat_id: str | None = None,
    reply_markup: dict | None = None,
    disable_web_page_preview: bool = True,
) -> dict:
    """
    Send Telegram message and return Telegram API result.
    """
    payload = {
        "chat_id": str(chat_id or _get_chat_id()).strip(),
        "text": _truncate(text),
        "disable_web_page_preview": bool(disable_web_page_preview),
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    return tg_request("sendMessage", payload)


def edit_telegram_message_text(
    *,
    chat_id: str,
    message_id: int,
    text: str,
    reply_markup: dict | None = None,
    disable_web_page_preview: bool = True,
) -> dict:
    payload = {
        "chat_id": str(chat_id).strip(),
        "message_id": int(message_id),
        "text": _truncate(text),
        "disable_web_page_preview": bool(disable_web_page_preview),
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    return tg_request("editMessageText", payload)


def answer_callback_query(
    callback_query_id: str,
    text: str = "",
    show_alert: bool = False,
) -> dict:
    payload = {
        "callback_query_id": str(callback_query_id),
        "text": str(text or ""),
        "show_alert": bool(show_alert),
    }
    return tg_request("answerCallbackQuery", payload)


def maps_link(lat: float, lng: float) -> str:
    return f"https://www.google.com/maps?q={lat},{lng}"


def delivery_status_label(status: str) -> str:
    mapping = {
        "pending": "Pending",
        "accepted": "Accepted",
        "preparing": "Preparing",
        "out_for_delivery": "Out for delivery",
        "delivered": "Delivered",
        "cancelled": "Cancelled",
    }
    return mapping.get(str(status or "").strip(), safe(status))


def get_allowed_telegram_user_ids() -> set[int]:
    raw = getattr(settings, "ADMIN_TELEGRAM_USER_IDS", "") or ""
    out: set[int] = set()

    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except Exception:
            continue

    return out


def telegram_user_is_allowed(user_id: int | None) -> bool:
    if user_id is None:
        return False
    return int(user_id) in get_allowed_telegram_user_ids()


def build_delivery_status_keyboard(order_id: int, current_status: str) -> dict:
    """
    Inline keyboard for delivery order status management.
    callback_data format:
      do:<order_id>:<target_status>
    """
    rows = [
        [("Pending", "pending"), ("Accepted", "accepted")],
        [("Preparing", "preparing"), ("Out for delivery", "out_for_delivery")],
        [("Delivered", "delivered"), ("Cancelled", "cancelled")],
    ]

    inline_keyboard = []
    current_status = str(current_status or "").strip()

    for row in rows:
        btn_row = []
        for label, value in row:
            text = f"✅ {label}" if value == current_status else label
            btn_row.append(
                {
                    "text": text,
                    "callback_data": f"do:{int(order_id)}:{value}",
                }
            )
        inline_keyboard.append(btn_row)

    return {"inline_keyboard": inline_keyboard}


def build_delivery_order_message(order) -> str:
    """
    Builds the Telegram delivery order text with addons.
    Expects:
      order.items.prefetch_related('addon_snapshots')
    """
    items_lines = []

    for it in order.items.all():
        items_lines.append(
            f"• {safe(it.name)} × {it.qty} = € {(it.unit_price * it.qty):.2f}"
        )

        addon_rows = list(it.addon_snapshots.all())
        for addon in addon_rows:
            addon_label = f"   - {safe(addon.group_name)}: {safe(addon.option_name)}"
            try:
                addon_price = float(addon.option_price or 0)
            except Exception:
                addon_price = 0.0

            if addon_price > 0:
                addon_label += f" (+€ {addon_price:.2f})"
            items_lines.append(addon_label)

    items_text = "\n".join(items_lines) if items_lines else "—"

    last_actor = safe(getattr(order, "telegram_last_action_by", ""))
    last_at = getattr(order, "telegram_last_action_at", None)
    if last_at:
        try:
            last_at_text = last_at.strftime("%Y-%m-%d %H:%M")
        except Exception:
            last_at_text = safe(last_at)
    else:
        last_at_text = "-"

    return (
        f"🛵 DELIVERY ORDER\n\n"
        f"Order: #{order.id}\n"
        f"Status: {delivery_status_label(order.status)}\n"
        f"Name: {safe(order.customer_name)}\n"
        f"Phone: {safe(order.customer_phone)}\n"
        f"Payment: {safe(order.get_payment_method_display())}\n"
        f"Address: {safe(order.address_label)}\n"
        f"Extra: {safe(order.address_extra)}\n"
        f"Distance: {float(order.distance_km or 0):.2f} km\n"
        f"Subtotal: € {float(order.subtotal or 0):.2f}\n"
        f"Delivery fee: € {float(order.delivery_fee or 0):.2f}\n"
        f"Total: € {float(order.total or 0):.2f}\n"
        f"Coupon: {safe(order.coupon_code)} (-€ {float(order.coupon_discount or 0):.2f})\n"
        f"Note: {safe(order.customer_note)}\n"
        f"Map: {maps_link(order.lat, order.lng)}\n\n"
        f"Items:\n{items_text}\n\n"
        f"Last Telegram Action By: {last_actor}\n"
        f"Last Telegram Action At: {last_at_text}"
    )
