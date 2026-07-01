"""Print current config without exposing secret values.

Usage:
    python scripts/show_config.py

Replaces values for any var matching *KEY*, *TOKEN*, *SECRET*, *PASSWORD*
with ***masked***. Useful for confirming config without leaking secrets to
chat transcripts / logs / screenshots.
"""

from __future__ import annotations

import re

from app.config import get_settings


SECRET_PATTERN = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASS|CREDENTIAL|AUTH|CERT)", re.IGNORECASE)


def is_secret(field_name: str) -> bool:
    return bool(SECRET_PATTERN.search(field_name))


def main() -> None:
    s = get_settings()
    print(f"app_env          = {s.app_env}")
    print(f"app_host:port    = {s.app_host}:{s.app_port}")
    print()
    print("--- WeChat ---")
    print(f"wechat_corp_id      = {s.wechat_corp_id or '(empty)'}")
    print(f"wechat_agent_id     = {s.wechat_agent_id or '(empty)'}")
    print(f"wechat_configured   = {s.wechat_configured}")
    print()
    print("--- LLM ---")
    print(f"llm_base_url        = {s.llm_base_url}")
    print(f"llm_api_key         = {'***masked***' if s.llm_api_key else '(empty)'}")
    print(f"llm_model           = {s.llm_model}")
    print(f"llm_configured      = {s.llm_configured}")
    print()
    print("--- Embedding ---")
    print(f"embed_base_url      = {s.embed_base_url}")
    print(f"embed_api_key       = {'***masked***' if s.embed_api_key else '(empty)'}")
    print(f"embed_model         = {s.embed_model}")
    print(f"embed_dim           = {s.embed_dim}")
    print(f"embed_configured    = {s.embed_configured}")
    print()
    print("--- RAG ---")
    print(f"rag_top_k           = {s.rag_top_k}")
    print(f"rag_min_score       = {s.rag_min_score}")
    print(f"rag_index_path      = {s.rag_index_path}")
    print(f"rag_kb_path         = {s.rag_kb_path}")
    print()
    print("--- DingTalk ---")
    print(f"dingtalk_app_key    = {'***masked***' if s.dingtalk_app_key else '(empty)'}")
    print(f"dingtalk_app_secret = {'***masked***' if s.dingtalk_app_secret else '(empty)'}")
    print(f"dingtalk_agent_id   = {s.dingtalk_agent_id or '(empty)'}")
    print(f"dingtalk_configured = {bool(s.dingtalk_app_key and s.dingtalk_app_secret and s.dingtalk_agent_id)}")


if __name__ == "__main__":
    main()