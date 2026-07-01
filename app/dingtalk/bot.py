"""DingTalk Stream mode bot (using official SDK + direct send API).

Supports two modes:
1. Normal Q&A: handle_query via /chat pipeline
2. KB ingest: "kb: ..." prefix → conservative doctor-advice extraction → user confirms

The official SDK handles connection management and message reception.
For replies, we use the access_token (provided by the SDK) + direct
HTTP API call, because SDK's reply_markdown_card requires fields that
aren't present in CallbackMessage.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dingtalk_stream import (  # noqa: E402
    AckMessage,
    ChatbotHandler,
    Credential,
    DingTalkStreamClient,
)
from app.config import get_settings  # noqa: E402


logger = logging.getLogger("dingtalk-bot")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


CHATBOT_MESSAGE_TOPIC = "/v1.0/im/bot/messages/get"
KB_PREFIX = "kb:"

# Pending KB reviews: sender_id → {entry, original_text, expires_at}
_pending_reviews: dict[str, dict] = {}
_pending_lock = threading.Lock()
_PENDING_TTL_SECONDS = 3600  # 1 hour


async def send_oTo_message(app_key: str, sender_id: str, text: str, token: str) -> dict:
    """Send a single-chat message via the new DingTalk oToMessages API."""
    url = "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend"
    headers = {
        "x-acs-dingtalk-access-token": token,
        "Content-Type": "application/json",
    }
    payload = {
        "robotCode": app_key,
        "userIds": [sender_id],
        "msgKey": "sampleText",
        "msgParam": json.dumps({"content": [{"type": "text", "text": {"content": text}}]}, ensure_ascii=False),
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        return resp.json()


def _cleanup_expired() -> None:
    """Remove expired pending reviews."""
    now = time.time()
    expired = [k for k, v in _pending_reviews.items() if v.get("expires_at", 0) < now]
    for k in expired:
        _pending_reviews.pop(k, None)


def _save_to_kb(entry: dict) -> tuple[bool, str]:
    """Append an entry to curated.jsonl and rebuild index.

    Returns (success, message).
    """
    from app.kb.add_from_text import _save_entries

    # Ensure source starts with Doctor/Nurse to get proper boost
    src = entry.get("source", "")
    if not (src.startswith("Doctor") or src.startswith("Nurse")):
        return False, f"⚠️ source 必须以 Doctor 或 Nurse 开头（当前: {src[:30]}）"

    # Required: must have @医院名 and YYYY-MM-DD
    if "@" not in src:
        return False, "⚠️ source 必须包含 @医院名（如 'Doctor @三甲医院新生儿科'）"
    if not re.search(r"\d{4}-\d{2}-\d{2}", src):
        return False, "⚠️ source 必须包含日期（YYYY-MM-DD）"

    entry.setdefault("confidence", "high")
    entry.setdefault("tags", [])
    entry.setdefault("warning_signs", [])

    # Use _save_entries helper from add_from_text
    try:
        _save_entries([entry])
    except Exception as e:
        return False, f"❌ 写入失败: {e}"

    # Rebuild index in background
    project_root = Path(__file__).resolve().parent.parent.parent
    try:
        subprocess.Popen(
            [str(project_root / ".venv/bin/python"), "-m", "app.rag.build_index"],
            cwd=project_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.warning("[dingtalk] build_index spawn failed: %s", e)

    return True, "✅ 已写入 curated.jsonl（索引后台重建中）"


def _format_preview(entry: dict) -> str:
    """Format a KB entry preview for the user."""
    lines: list[str] = []
    lines.append("📋 医嘱已抽取（**未修改原话**）：\n")
    lines.append(f"**Question:** {entry.get('question', '')}\n")
    lines.append(f"**Content** ({len(entry.get('content', ''))} 字):")
    lines.append("> " + entry.get("content", "").replace("\n", "\n> "))
    lines.append("")
    lines.append(f"**Source:** {entry.get('source', '')}")
    lines.append(f"**Tags:** {', '.join(entry.get('tags', []))}")
    if entry.get("warning_signs"):
        lines.append(f"**Warning Signs:** {', '.join(entry['warning_signs'])}")
    lines.append(f"**Confidence:** {entry.get('confidence', 'high')}")
    lines.append("")
    lines.append("─" * 30)
    lines.append("回复 `ok` 入库 / `skip` 跳过 / `edit: 改后的内容`")
    return "\n".join(lines)


class MotherCareHandler(ChatbotHandler):
    async def process(self, message):  # type: ignore[override]
        try:
            data = message.data or {}
            text = (data.get("text") or {}).get("content", "").strip()
            sender_id = (
                data.get("senderStaffId")
                or data.get("senderId")
                or ""
            )
            if not text:
                return AckMessage.STATUS_OK, "OK"

            logger.info("[dingtalk] from=%s text=%r", sender_id, text[:80])

            # Get access token once
            loop = asyncio.get_event_loop()
            token = await loop.run_in_executor(
                None, self.dingtalk_client.get_access_token
            )
            app_key = self.dingtalk_client.credential.client_id

            # ─── Route 1: KB ingest mode (kb: prefix or pending review) ───
            lower = text.lower().strip()
            with _pending_lock:
                _cleanup_expired()
                pending = _pending_reviews.get(sender_id)

            if pending:
                # User is reviewing a pending entry
                if lower == "ok":
                    entry = pending["entry"]
                    ok, msg = _save_to_kb(entry)
                    with _pending_lock:
                        _pending_reviews.pop(sender_id, None)
                    reply_text = f"{msg}\n\n入条内容：{entry.get('question', '')[:60]}"
                elif lower == "skip":
                    with _pending_lock:
                        _pending_reviews.pop(sender_id, None)
                    reply_text = "🚫 已跳过，未入库。"
                elif lower.startswith("edit:"):
                    new_content = text[5:].strip()
                    entry = pending["entry"]
                    entry["content"] = new_content
                    with _pending_lock:
                        _pending_reviews[sender_id] = {
                            "entry": entry,
                            "expires_at": time.time() + _PENDING_TTL_SECONDS,
                        }
                    reply_text = _format_preview(entry)
                else:
                    reply_text = "请回复 `ok` / `skip` / `edit: 新内容`"
                resp = await send_oTo_message(app_key, sender_id, reply_text, token)
                logger.info("[dingtalk] KB reply: %s", resp)
                return AckMessage.STATUS_OK, "OK"

            # ─── Route 2: New KB ingest request ───
            if text.lower().startswith(KB_PREFIX):
                user_text = text[len(KB_PREFIX):].strip()
                if not user_text:
                    reply_text = (
                        "用法：\n"
                        "`kb: 医嘱正文...`\n\n"
                        "示例：\n"
                        "`kb: 今天带宝宝去三甲医院新生儿科复查，李医生说黄疸15.2...`\n\n"
                        "我会用保守模式抽取（不精简、不润色），给你预览后你回复 ok 入库。"
                    )
                    resp = await send_oTo_message(app_key, sender_id, reply_text, token)
                    return AckMessage.STATUS_OK, "OK"

                # Extract medical advice (conservative mode)
                from app.kb.doctor_extract import extract_medical_advice
                from app.llm import get_llm

                llm = get_llm()
                result = extract_medical_advice(llm, user_text)

                entries = result.get("entries", [])
                if not entries or result.get("verdict") != "include":
                    reply_text = f"❌ 抽取失败：{result.get('reason', '?')}\n请直接用 add_from_text 走交互模式。"
                    resp = await send_oTo_message(app_key, sender_id, reply_text, token)
                    return AckMessage.STATUS_OK, "OK"

                # Take first entry; if multiple, warn user
                entry = entries[0]
                if len(entries) > 1:
                    entry["_extra_count"] = len(entries) - 1

                with _pending_lock:
                    _pending_reviews[sender_id] = {
                        "entry": entry,
                        "expires_at": time.time() + _PENDING_TTL_SECONDS,
                    }

                reply_text = _format_preview(entry)
                if entry.get("_extra_count"):
                    reply_text += f"\n\n⚠️ LLM 还抽出了 {entry['_extra_count']} 条额外内容，本次先入库这条；如需要可以再发 `kb: ...`"

                resp = await send_oTo_message(app_key, sender_id, reply_text, token)
                logger.info("[dingtalk] KB preview sent: %s", resp)
                return AckMessage.STATUS_OK, "OK"

            # ─── Route 3: Normal Q&A ───
            from app.pipeline import handle_query

            result = handle_query(sender_id, text)
            reply_text = result.to_text()
            resp = await send_oTo_message(app_key, sender_id, reply_text, token)
            logger.info("[dingtalk] reply resp: %s", resp)
            return AckMessage.STATUS_OK, "OK"
        except Exception as e:
            logger.exception("[dingtalk] handler error: %s", e)
            return AckMessage.STATUS_OK, "OK"


def main() -> None:
    s = get_settings()
    if not (s.dingtalk_app_key and s.dingtalk_app_secret and s.dingtalk_agent_id):
        print("ERROR: DingTalk not configured.")
        sys.exit(1)

    credential = Credential(s.dingtalk_app_key, s.dingtalk_app_secret)
    client = DingTalkStreamClient(credential)
    client.register_callback_handler(CHATBOT_MESSAGE_TOPIC, MotherCareHandler())

    logger.info("Starting DingTalk bot (agent_id=%s)", s.dingtalk_agent_id)
    logger.info("KB ingest: send 'kb: 医嘱正文...' to add medical advice to KB")
    try:
        client.start_forever()
    except KeyboardInterrupt:
        logger.info("DingTalk bot stopped")


if __name__ == "__main__":
    main()