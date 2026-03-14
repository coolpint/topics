import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


TELEGRAM_TEXT_LIMIT = 3500


def _chunk_message(text: str, limit: int = TELEGRAM_TEXT_LIMIT) -> list[str]:
    content = text.strip()
    if len(content) <= limit:
        return [content]
    chunks = []
    remaining = content
    while len(remaining) > limit:
        split_at = remaining.rfind("\n\n", 0, limit)
        if split_at < limit // 2:
            split_at = remaining.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    if len(chunks) == 1:
        return chunks
    total = len(chunks)
    return ["({}/{}) {}".format(index, total, chunk) for index, chunk in enumerate(chunks, start=1)]


def send_message(bot_token: str, chat_id: str, text: str) -> None:
    if not bot_token or not chat_id:
        raise ValueError("Telegram bot token and chat id are required.")
    for chunk in _chunk_message(text):
        payload = json.dumps(
            {
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        request = Request(
            "https://api.telegram.org/bot{}/sendMessage".format(bot_token),
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=20) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                "Telegram send failed with HTTP {}: {}".format(exc.code, detail or exc.reason)
            ) from exc
        if not body.get("ok"):
            raise RuntimeError("Telegram send failed: {}".format(body))
