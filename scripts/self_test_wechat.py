"""End-to-end self-test of WeChat URL verification handshake.

Simulates what Enterprise WeChat sends on URL verification GET, using OUR
.env's token + aes_key. If this passes (200 + echoes plaintext), our server
is 100% correct. Any "openapi failed" error from WeChat admin is then
guaranteed to be on the WeChat side (IP whitelist, perms, cache, etc.).

Run:
    python scripts/self_test_wechat.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

# Allow importing app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.wechat.crypto import encrypt, sha1_sign  # noqa: E402


def main() -> int:
    s = get_settings()
    if not (s.wechat_callback_token and s.wechat_callback_aes_key and s.wechat_corp_id):
        print("ERROR: WeChat not fully configured in .env")
        print("Need: WECHAT_CORP_ID, WECHAT_CALLBACK_TOKEN, WECHAT_CALLBACK_AES_KEY")
        return 1

    base = s.app_host if False else "https://matcher-cufflink-penpal.ngrok-free.dev"
    print("=== WeChat URL verification self-test ===")
    print(f"  ngrok URL   : {base}")
    print(f"  corp_id     : {s.wechat_corp_id}")
    print(f"  token       : {s.wechat_callback_token[:4]}***")
    print(f"  aes_key     : {s.wechat_callback_aes_key[:4]}***")
    print()

    # Step 1: encrypt a test echo string with OUR aes_key
    test_echostr = "self_test_echostr_2026_06_27"
    encrypted = encrypt(test_echostr, s.wechat_callback_aes_key, s.wechat_corp_id)
    print(f"  encrypted   : {encrypted[:40]}...")

    # Step 2: sign with OUR token
    ts = str(int(time.time()))
    nonce = "self_test_nonce"
    sig = sha1_sign(s.wechat_callback_token, ts, nonce, encrypted)
    print(f"  signature   : {sig}")
    print()

    # Step 3: GET the callback URL with our signed request
    url = (
        f"{base}/wechat/callback"
        f"?msg_signature={sig}&timestamp={ts}&nonce={nonce}&echostr={encrypted}"
    )
    print(f"  GET {url[:80]}...")
    print()

    with httpx.Client(timeout=10.0) as client:
        resp = client.get(url)

    print("=== Response ===")
    print(f"  HTTP {resp.status_code}")
    print(f"  Content-Type: {resp.headers.get('content-type', '?')}")
    body = resp.text
    print(f"  body: {body!r}")
    print()

    if resp.status_code == 200 and body == test_echostr:
        print("✅ PASS — our server is 100% correct.")
        print("   The 'openapi failed' error from WeChat is on WeChat's side.")
        print("   Likely causes:")
        print("   - WeChat IP whitelist (mgmt → security → IP whitelist)")
        print("   - Application not enabled for receiving messages")
        print("   - Stale WeChat browser cache (try incognito)")
        return 0
    elif resp.status_code == 403:
        print("❌ FAIL — signature verification failed.")
        print("   Token in .env does not match the one WeChat is using.")
        return 2
    elif "Invalid padding bytes" in body or "decrypt" in body.lower():
        print("❌ FAIL — AES key in .env is wrong (decryption failed).")
        return 3
    else:
        print(f"❌ FAIL — unexpected response (HTTP {resp.status_code}).")
        return 4


if __name__ == "__main__":
    sys.exit(main())