"""FastAPI application entry point."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel

from app import __version__
from app.config import get_settings
from app.pipeline import handle_query, reset_retriever
from app.wechat import (
    build_encrypted_reply_envelope,
    build_text_reply_xml,
    is_encrypted_mode,
    parse_incoming_xml,
    reply,
    verify_callback_url,
    verify_incoming_signature,
)
from app.wechat.handler import _extract_encrypted_from_xml


# ---- Logging ----
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.app_log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---- App ----
app = FastAPI(
    title="Mother & Baby AI Assistant",
    description="MVP skeleton — 高可信、可控、可溯源的母婴 AI 助手",
    version=__version__,
)


# ---- Schemas ----
class ChatRequest(BaseModel):
    user_id: str = "test_user"
    query: str


class ChatResponse(BaseModel):
    trace_id: str
    route: str
    answer: dict
    confidence: str
    hits: list[dict] = []
    warning: str | None = None


# ---- Routes ----
@app.get("/")
def root() -> dict:
    return {
        "name": "Mother & Baby AI Assistant",
        "version": __version__,
        "env": settings.app_env,
        "wechat_configured": settings.wechat_configured,
        "llm_configured": settings.llm_configured,
        "embed_configured": settings.embed_configured,
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict:
    s = get_settings()
    index_exists = Path(s.rag_index_path).exists()
    return {"status": "ok", "index_exists": index_exists}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> dict:
    """Direct chat endpoint — useful for testing without WeChat."""
    result = handle_query(req.user_id, req.query)
    return result.to_dict()


@app.post("/admin/rebuild-index")
def rebuild_index() -> dict:
    """Rebuild the FAISS index in-place. Useful after editing the KB."""
    from app.rag.build_index import main as build_main

    reset_retriever()
    build_main()
    reset_retriever()
    return {"status": "rebuilt"}


# ---- WeChat callback ----
@app.get("/wechat/callback")
def wechat_verify(
    msg_signature: str = Query(""),
    timestamp: str = Query(""),
    nonce: str = Query(""),
    echostr: str = Query(""),
) -> PlainTextResponse:
    """URL verification handshake."""
    try:
        verified = verify_callback_url(msg_signature, timestamp, nonce, echostr)
        return PlainTextResponse(verified)
    except Exception as e:
        logger.warning("[wechat:verify] failed: %s", e)
        raise HTTPException(status_code=403, detail=str(e)) from e


@app.post("/wechat/callback")
async def wechat_callback(request: Request, background_tasks: BackgroundTasks) -> Response:
    """Receive a text message from WeChat, run pipeline, send reply.

    Strategy to avoid WeChat's 5-second passive-reply timeout:
    1. Quickly parse + acknowledge (return empty success XML immediately)
    2. Run the LLM pipeline in a background task
    3. Use active send API to push the reply when ready
    """
    body = await request.body()
    timestamp = request.query_params.get("timestamp", "")
    nonce = request.query_params.get("nonce", "")
    msg_signature = request.query_params.get("msg_signature", "")

    # In encrypted mode: verify signature BEFORE parsing
    if is_encrypted_mode():
        encrypted = _extract_encrypted_from_xml(body)
        if not encrypted:
            raise HTTPException(status_code=400, detail="no <Encrypt> in body")
        if not verify_incoming_signature(msg_signature, timestamp, nonce, encrypted):
            raise HTTPException(status_code=403, detail="signature mismatch")

    try:
        msg = parse_incoming_xml(body)
    except Exception as e:
        logger.warning("[wechat:parse] failed: %s body=%r", e, body[:200])
        raise HTTPException(status_code=400, detail="invalid xml") from e

    if not msg.content or not msg.user_id:
        return Response(content=b"", media_type="application/xml")

    from_user = msg.raw.get("ToUserName", "") or settings.wechat_corp_id

    # Return success immediately so WeChat doesn't time out, then process in background.
    # The actual reply is delivered via the active send API (message/send) below.
    success_xml = build_text_reply_xml(msg.user_id, from_user, "")  # empty Content
    if is_encrypted_mode():
        success_xml = build_encrypted_reply_envelope(success_xml, timestamp, nonce)
    # Strip the empty Content so WeChat doesn't show blank bubble
    success_xml = success_xml.replace("<Content><![CDATA[]]></Content>", "")

    background_tasks.add_task(_process_and_reply, msg.user_id, msg.content)

    return Response(content=success_xml, media_type="application/xml")


def _process_and_reply(user_id: str, query: str) -> None:
    """Background task: run pipeline + actively send reply."""
    import asyncio

    try:
        result = handle_query(user_id, query)
        reply_text = result.to_text()
    except Exception as e:
        logger.exception("[wechat:bg] pipeline failed: %s", e)
        reply_text = "抱歉，处理你的问题时遇到了问题，请稍后再试。"

    # Fire-and-forget async send
    asyncio.run(reply(user_id, reply_text))


# ---- Chat Web UI (PWA) ----

CHAT_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#f5e6d3">
<title>母婴助手</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; background: #faf6f0; color: #2c2c2c; font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; }
  body { display: flex; flex-direction: column; max-width: 720px; margin: 0 auto; }
  header { background: #f5e6d3; padding: 14px 16px; text-align: center; font-size: 18px; font-weight: 600; color: #6b4423; box-shadow: 0 1px 3px rgba(0,0,0,0.06); position: sticky; top: 0; z-index: 10; }
  header small { display: block; font-size: 11px; font-weight: 400; color: #8b6f4e; margin-top: 2px; }
  #messages { flex: 1; overflow-y: auto; padding: 16px; padding-bottom: 8px; }
  .msg { margin-bottom: 14px; display: flex; }
  .msg.user { justify-content: flex-end; }
  .msg.assistant { justify-content: flex-start; }
  .bubble { max-width: 80%; padding: 10px 14px; border-radius: 14px; line-height: 1.55; word-wrap: break-word; font-size: 15px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
  .user .bubble { background: #4a90e2; color: white; border-bottom-right-radius: 4px; }
  .assistant .bubble { background: white; color: #2c2c2c; border-bottom-left-radius: 4px; }
  .meta { font-size: 11px; color: #8b6f4e; margin-top: 6px; padding: 0 4px; }
  .meta .source { display: inline-block; background: #f0e4d3; padding: 2px 6px; border-radius: 4px; margin-right: 4px; margin-top: 2px; }
  .meta .warning { color: #c0392b; }
  .meta .confidence { color: #888; margin-left: 4px; }
  .empty { text-align: center; color: #8b6f4e; padding: 30px 16px; font-size: 14px; }
  .empty .examples { margin-top: 20px; text-align: left; }
  .empty .example { background: white; border: 1px solid #e8d9c0; border-radius: 10px; padding: 10px 12px; margin-bottom: 8px; cursor: pointer; font-size: 14px; color: #6b4423; }
  .empty .example:active { background: #f5e6d3; }
  #form { display: flex; padding: 10px; background: white; border-top: 1px solid #e8d9c0; gap: 8px; }
  #input { flex: 1; border: 1px solid #d4c4ad; border-radius: 22px; padding: 10px 16px; font-size: 15px; outline: none; background: #fdfaf3; color: #2c2c2c; }
  #input:focus { border-color: #b08d5e; background: white; }
  #send { background: #6b4423; color: white; border: none; border-radius: 22px; padding: 0 18px; font-size: 15px; cursor: pointer; }
  #send:disabled { background: #c5b59a; }
  #send:active { background: #5a3818; }
  .thinking { display: inline-block; }
  .thinking span { display: inline-block; width: 6px; height: 6px; background: #8b6f4e; border-radius: 50%; margin: 0 2px; animation: bounce 1.4s infinite ease-in-out both; }
  .thinking span:nth-child(1) { animation-delay: -0.32s; }
  .thinking span:nth-child(2) { animation-delay: -0.16s; }
  @keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }
  .disclaimer { text-align: center; padding: 8px; font-size: 11px; color: #999; background: #faf6f0; }
</style>
</head>
<body>
<header>
  母婴助手
  <small>仅供参考 · 不构成医疗诊断</small>
</header>
<main id="messages">
  <div class="empty" id="welcome">
    <div style="font-size:32px;margin-bottom:8px;">👶</div>
    <div>问点什么试试？</div>
    <div class="examples">
      <div class="example" data-q="新生儿黄疸多少算危险？">新生儿黄疸多少算危险？</div>
      <div class="example" data-q="宝宝发烧38.5怎么办？">宝宝发烧38.5怎么办？</div>
      <div class="example" data-q="宝宝呛奶怎么处理？">宝宝呛奶怎么处理？</div>
      <div class="example" data-q="什么时候开始添加辅食？">什么时候开始添加辅食？</div>
    </div>
  </div>
</main>
<div class="disclaimer">仅供学习参考，遇紧急情况请就医或拨打 120 / 12320</div>
<form id="form">
  <input id="input" type="text" placeholder="问点什么…" autocomplete="off" required>
  <button id="send" type="submit">发送</button>
</form>
<script>
  const $ = (s) => document.querySelector(s);
  const messagesEl = $('#messages');
  const form = $('#form');
  const input = $('#input');
  const sendBtn = $('#send');
  const welcome = $('#welcome');

  function scrollBottom() { messagesEl.scrollTop = messagesEl.scrollHeight; }

  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function addUserMsg(text) {
    if (welcome) welcome.remove();
    const div = document.createElement('div');
    div.className = 'msg user';
    div.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
    messagesEl.appendChild(div);
    scrollBottom();
  }

  function addAssistantMsg(html) {
    const div = document.createElement('div');
    div.className = 'msg assistant';
    div.innerHTML = `<div class="bubble">${html}</div>`;
    messagesEl.appendChild(div);
    scrollBottom();
    return div;
  }

  function addThinking() {
    if (welcome) welcome.remove();
    const div = document.createElement('div');
    div.className = 'msg assistant';
    div.innerHTML = '<div class="bubble"><span class="thinking"><span></span><span></span><span></span></span></div>';
    messagesEl.appendChild(div);
    scrollBottom();
    return div;
  }

  function renderAnswer(data) {
    const a = data.answer || {};
    let html = '';
    if (a.conclusion) html += `<div><strong>结论：</strong>${escapeHtml(a.conclusion)}</div>`;
    if (a.recommendations && a.recommendations.length) {
      html += '<div style="margin-top:8px"><strong>建议：</strong><ol style="padding-left:20px;margin-top:4px">';
      a.recommendations.forEach(r => html += `<li>${escapeHtml(r)}</li>`);
      html += '</ol></div>';
    }
    if (a.warning_signs && a.warning_signs.length) {
      html += '<div style="margin-top:8px;color:#c0392b"><strong>警示信号：</strong><ul style="padding-left:20px;margin-top:4px">';
      a.warning_signs.forEach(w => html += `<li>${escapeHtml(w)}</li>`);
      html += '</ul></div>';
    }
    let meta = '';
    if (a.sources && a.sources.length) {
      a.sources.forEach(s => meta += `<span class="source">${escapeHtml(s)}</span>`);
    }
    if (a.confidence) meta += `<span class="confidence">· 置信度 ${escapeHtml(a.confidence)}</span>`;
    if (meta) html += `<div class="meta">${meta}</div>`;
    return html || '<em>（未生成回答）</em>';
  }

  async function sendQuery(q) {
    addUserMsg(q);
    input.value = '';
    sendBtn.disabled = true;
    const thinkingDiv = addThinking();
    try {
      const resp = await fetch('/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user_id: 'web', query: q}),
      });
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const data = await resp.json();
      thinkingDiv.innerHTML = `<div class="bubble">${renderAnswer(data)}</div>`;
    } catch (e) {
      thinkingDiv.innerHTML = `<div class="bubble">网络错误：${escapeHtml(String(e))}</div>`;
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    sendQuery(q);
  });

  document.querySelectorAll('.example').forEach(el => {
    el.addEventListener('click', () => sendQuery(el.dataset.q));
  });

  input.focus();
</script>
</body>
</html>
"""


@app.get("/chat-web", response_class=HTMLResponse)
def chat_web() -> str:
    """Mobile-friendly chat UI (PWA-style). Open in any browser on the same WiFi."""
    return CHAT_HTML


@app.get("/manifest.json")
def pwa_manifest() -> JSONResponse:
    return JSONResponse(
        {
            "name": "母婴助手",
            "short_name": "母婴助手",
            "start_url": "/chat-web",
            "display": "standalone",
            "background_color": "#faf6f0",
            "theme_color": "#f5e6d3",
            "icons": [],
        }
    )


# ---- CLI ----
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "dev",
    )