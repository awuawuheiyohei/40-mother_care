"""End-to-end test of the encrypted WeChat callback.

Simulates what the WeChat server sends:
1. URL verification GET (with encrypted echostr)
2. Incoming message POST (encrypted XML body)

Run:
    python scripts/test_wechat_e2e.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.wechat.crypto import (  # noqa: E402
    encrypt,
    sha1_sign,
)


def main() -> None:
    s = get_settings()
    if not s.wechat_callback_aes_key or not s.wechat_callback_token or not s.wechat_corp_id:
        print("ERROR: WeChat not fully configured (need aes_key, token, corp_id).")
        print("  Add to .env:")
        print("    WECHAT_CORP_ID=...")
        print("    WECHAT_CALLBACK_TOKEN=...")
        print("    WECHAT_CALLBACK_AES_KEY=...")
        return

    base = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:8000")
    print(f"Testing against {base}")
    print(f"  corp_id   = {s.wechat_corp_id}")
    print(f"  token     = {s.wechat_callback_token[:4]}...")
    print(f"  aes_key   = {s.wechat_callback_aes_key[:4]}...")
    print()

    # 1. URL verification
    print("=== Test 1: URL verification (encrypted) ===")
    echostr_plain = "test_echo_string_for_url_verification"
    encrypted = encrypt(echostr_plain, s.wechat_callback_aes_key, s.wechat_corp_id)
    ts = str(int(time.time()))
    nonce = "test_nonce_123"
    sig = sha1_sign(s.wechat_callback_token, ts, nonce, encrypted)

    with httpx.Client(timeout=10.0) as client:
        resp = client.get(
            f"{base}/wechat/callback",
            params={
                "msg_signature": sig,
                "timestamp": ts,
                "nonce": nonce,
                "echostr": encrypted,
            },
        )
        print(f"  HTTP {resp.status_code}")
        print(f"  body = {resp.text!r}")
        if resp.text == echostr_plain:
            print("  ✓ URL verification PASSED (decrypted echostr echoed back)")
        else:
            print(f"  ✗ URL verification FAILED (expected {echostr_plain!r})")
            return

    print()

    # 2. Message callback
    print("=== Test 2: Incoming encrypted message ===")
    # Build inner XML
    inner_xml = (
        f"<xml>"
        f"<ToUserName><![CDATA[{s.wechat_corp_id}]]></ToUserName>"
        f"<FromUserName><![CDATA[test_user_openid]]></FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        f"<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[新生儿黄疸多少算危险？]]></Content>"
        f"<MsgId>1234567890</MsgId>"
        f"<AgentID>1000002</AgentID>"
        f"</xml>"
    )
    encrypted_msg = encrypt(inner_xml, s.wechat_callback_aes_key, s.wechat_corp_id)
    envelope = (
        f"<xml>"
        f"<ToUserName><![CDATA[{s.wechat_corp_id}]]></ToUserName>"
        f"<Encrypt><![CDATA[{encrypted_msg}]]></Encrypt>"
        f"</xml>"
    )
    ts2 = str(int(time.time()))
    nonce2 = "another_nonce_456"
    sig2 = sha1_sign(s.wechat_callback_token, ts2, nonce2, encrypted_msg)

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{base}/wechat/callback",
            params={
                "msg_signature": sig2,
                "timestamp": ts2,
                "nonce": nonce2,
            },
            content=envelope,
            headers={"Content-Type": "application/xml"},
        )
        print(f"  HTTP {resp.status_code}")
        print(f"  body = {resp.text[:500]}")
        if resp.status_code == 200 and '"status": "ok"' in resp.text:
            print("  ✓ Message callback PASSED (pipeline ran)")
        else:
            print("  ✗ Message callback FAILED")
            return

    print()
    print("All encrypted-mode tests PASSED ✅")


if __name__ == "__main__":
    main()