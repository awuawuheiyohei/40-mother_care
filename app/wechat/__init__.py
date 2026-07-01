"""WeChat (Enterprise) integration.

Submodules:
- handler: URL verification + XML parse + reply XML construction
- client: access_token + active send via /cgi-bin/message/send
- crypto: AES-256-CBC encryption (required for production WeChat callbacks)
"""

from app.wechat.client import get_access_token, reply, send_text
from app.wechat.crypto import (
    decrypt,
    encrypt,
    sha1_sign,
    verify_and_decrypt_echo,
    verify_and_decrypt_message,
    verify_signature,
)
from app.wechat.handler import (
    WeChatMessage,
    build_encrypted_reply_envelope,
    build_text_reply_xml,
    is_encrypted_mode,
    parse_incoming_xml,
    process_inbound,
    verify_callback_url,
    verify_incoming_signature,
)

__all__ = [
    # handler
    "WeChatMessage",
    "build_text_reply_xml",
    "build_encrypted_reply_envelope",
    "is_encrypted_mode",
    "parse_incoming_xml",
    "process_inbound",
    "verify_callback_url",
    "verify_incoming_signature",
    # client
    "get_access_token",
    "send_text",
    "reply",
    # crypto
    "decrypt",
    "encrypt",
    "sha1_sign",
    "verify_and_decrypt_echo",
    "verify_and_decrypt_message",
    "verify_signature",
]