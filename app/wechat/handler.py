"""WeChat callback handler: URL verification + XML parsing + reply XML.

Supports two modes:
- Plaintext: when `WECHAT_CALLBACK_AES_KEY` is empty (legacy / dev only)
- Encrypted (AES-256-CBC): when `WECHAT_CALLBACK_AES_KEY` is set (production)
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

from app.config import get_settings


@dataclass
class WeChatMessage:
    user_id: str
    content: str
    raw: dict[str, Any]


def is_encrypted_mode() -> bool:
    """Whether to use AES-256-CBC encrypted callback mode."""
    s = get_settings()
    return bool(s.wechat_callback_aes_key)


def verify_callback_url_plain(
    msg_signature: str, timestamp: str, nonce: str, echostr: str
) -> str:
    """Plaintext mode: signature = sha1(token + timestamp + nonce + echostr)."""
    s = get_settings()
    if not s.wechat_callback_token:
        return echostr
    items = sorted([s.wechat_callback_token, timestamp, nonce, echostr])
    expected = hashlib.sha1("".join(items).encode("utf-8")).hexdigest()
    if expected != msg_signature:
        raise ValueError(f"signature mismatch: expected={expected}, got={msg_signature}")
    return echostr


def verify_callback_url(
    msg_signature: str, timestamp: str, nonce: str, echostr: str
) -> str:
    """URL verification handshake (handles both modes)."""
    s = get_settings()
    if not is_encrypted_mode():
        return verify_callback_url_plain(msg_signature, timestamp, nonce, echostr)

    # Encrypted mode
    from app.wechat.crypto import verify_and_decrypt_echo  # noqa: PLC0415

    return verify_and_decrypt_echo(
        msg_signature=msg_signature,
        timestamp=timestamp,
        nonce=nonce,
        echostr=echostr,
        token=s.wechat_callback_token,
        encoding_aes_key=s.wechat_callback_aes_key,
        corp_id=s.wechat_corp_id,
    )


def _extract_encrypted_from_xml(xml_body: bytes) -> str | None:
    """Extract the <Encrypt> field from incoming envelope XML. None if not present."""
    try:
        root = ET.fromstring(xml_body)
    except ET.ParseError:
        return None
    enc = root.findtext("Encrypt")
    return enc.strip() if enc else None


def parse_incoming_xml(xml_body: bytes) -> WeChatMessage:
    """Parse incoming XML/JSON message, handling both plaintext and encrypted modes."""
    s = get_settings()

    # Try encrypted mode first if configured
    if is_encrypted_mode():
        encrypted = _extract_encrypted_from_xml(xml_body)
        if encrypted is None:
            raise ValueError("encrypted mode configured but no <Encrypt> field in body")
        # Note: signature was already verified at the route handler level
        from app.wechat.crypto import decrypt  # noqa: PLC0415

        decrypted = decrypt(encrypted, s.wechat_callback_aes_key)
        if decrypted.receive_id != s.wechat_corp_id:
            raise ValueError(
                f"receive_id mismatch: expected={s.wechat_corp_id}, got={decrypted.receive_id}"
            )
        # Now parse the inner XML
        return _parse_plaintext_xml(decrypted.message.encode("utf-8"))

    # Plaintext mode
    return _parse_plaintext_xml(xml_body)


def _parse_plaintext_xml(xml_body: bytes) -> WeChatMessage:
    """Parse a plaintext XML message from WeChat."""
    root = ET.fromstring(xml_body)
    return WeChatMessage(
        user_id=root.findtext("FromUserName", ""),
        content=root.findtext("Content", ""),
        raw={child.tag: child.text for child in root},
    )


def build_text_reply_xml(to_user: str, from_user: str, content: str) -> str:
    """Build the XML reply body for a passive response (plaintext mode)."""
    ts = int(time.time())
    return (
        f"<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{ts}</CreateTime>"
        f"<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{content}]]></Content>"
        f"</xml>"
    )


def build_encrypted_reply_envelope(
    plaintext_xml: str, timestamp: str, nonce: str
) -> str:
    """Wrap a plaintext reply XML into the encrypted envelope for WeChat."""
    s = get_settings()
    from app.wechat.crypto import build_encrypted_reply_envelope as _build  # noqa: PLC0415

    return _build(
        plaintext_xml=plaintext_xml,
        timestamp=timestamp,
        nonce=nonce,
        token=s.wechat_callback_token,
        encoding_aes_key=s.wechat_callback_aes_key,
        corp_id=s.wechat_corp_id,
    )


def process_inbound(message: WeChatMessage) -> str:
    """Run the assistant pipeline and return the reply text.

    Imported lazily to avoid circular imports.
    """
    from app.pipeline import handle_query  # noqa: PLC0415

    result = handle_query(message.user_id, message.content)
    return result.to_text()


# Helper for the route handler to verify the msg_signature at the edge
def verify_incoming_signature(
    msg_signature: str, timestamp: str, nonce: str, encrypted: str
) -> bool:
    """Verify msg_signature at the edge, before parsing the body."""
    from app.wechat.crypto import verify_signature  # noqa: PLC0415

    return verify_signature(
        get_settings().wechat_callback_token,
        timestamp,
        nonce,
        encrypted,
        msg_signature,
    )