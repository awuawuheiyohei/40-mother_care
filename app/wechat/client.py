"""WeChat active send: access_token caching + message/send."""

from __future__ import annotations

import time

import httpx

from app.config import get_settings


_token_cache: dict[str, tuple[str, float]] = {}  # corp_id -> (token, expires_at)


async def get_access_token(force_refresh: bool = False) -> str:
    s = get_settings()
    if not s.wechat_configured:
        raise RuntimeError("WeChat not configured")

    now = time.time()
    cached = _token_cache.get(s.wechat_corp_id)
    if not force_refresh and cached and cached[1] > now + 60:
        return cached[0]

    url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
    params = {"corpid": s.wechat_corp_id, "corpsecret": s.wechat_corp_secret}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        data = resp.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"WeChat gettoken failed: {data}")
    token = data["access_token"]
    expires_in = data.get("expires_in", 7200)
    _token_cache[s.wechat_corp_id] = (token, now + expires_in)
    return token


async def send_text(to_user: str, content: str) -> dict:
    s = get_settings()
    if not s.wechat_configured:
        # Dev fallback: log to stdout
        print(f"[wechat:mock] -> {to_user}: {content[:200]}")
        return {"errcode": 0, "errmsg": "ok (mock)"}

    if s.wechat_allowed_users:
        allowed = {u.strip() for u in s.wechat_allowed_users.split(",")}
        if to_user not in allowed:
            return {"errcode": 0, "errmsg": "skipped (not in allowlist)"}

    token = await get_access_token()
    url = "https://qyapi.weixin.qq.com/cgi-bin/message/send"
    params = {"access_token": token}
    payload = {
        "touser": to_user,
        "msgtype": "text",
        "agentid": int(s.wechat_agent_id),
        "text": {"content": content},
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, params=params, json=payload)
        data = resp.json()
    if data.get("errcode") not in (0, None):
        # Retry once on token expiry
        if data.get("errcode") in (40014, 42001, 41001):
            token = await get_access_token(force_refresh=True)
            params = {"access_token": token}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, params=params, json=payload)
                data = resp.json()
    return data


async def reply(to_user: str, content: str) -> None:
    """Best-effort send. Logs but does not raise on failure."""
    try:
        await send_text(to_user, content)
    except Exception as e:  # noqa: BLE001
        print(f"[wechat] send_text failed for {to_user}: {e}")