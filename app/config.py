"""Application configuration loaded from environment variables.

All "empty value = mock mode" rules live here so individual components
don't need to know about env parsing.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- App ----
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_log_level: str = "INFO"

    # ---- WeChat ----
    wechat_corp_id: str = ""
    wechat_agent_id: str = ""
    wechat_corp_secret: str = ""
    wechat_callback_token: str = ""
    wechat_callback_aes_key: str = ""
    wechat_allowed_users: str = ""

    # ---- LLM ----
    llm_base_url: str = "https://api.MiniMax.chat/v1"
    llm_api_key: str = ""
    llm_model: str = "MiniMax-Text-01"
    llm_timeout: int = 30

    # ---- Embedding ----
    embed_base_url: str = "https://api.openai.com/v1"
    embed_api_key: str = ""
    embed_model: str = "text-embedding-3-small"
    embed_dim: int = 1536

    # ---- DingTalk ----
    dingtalk_app_key: str = ""
    dingtalk_app_secret: str = ""
    dingtalk_agent_id: str = ""

    # ---- RAG ----
    rag_top_k: int = 5
    rag_min_score: float = 0.35
    rag_index_path: str = "./data/faiss.index"
    rag_kb_path: str = "./app/kb/data"

    # ---- Source priority (JSON string) ----
    source_weights_json: str = Field(
        default='{"WHO": 1.0, "CDC": 1.0, "Chinese Pediatric Guideline": 0.95, "Hospital": 0.85, "Doctor": 0.9, "Nurse": 0.85, "Curated": 0.7, "XHS (verified)": 0.55, "Internet": 0.4}'
    )

    # ---- Derived helpers ----
    @property
    def source_weights(self) -> dict[str, float]:
        try:
            return json.loads(self.source_weights_json)
        except json.JSONDecodeError:
            return {"Curated": 0.7}

    @property
    def wechat_configured(self) -> bool:
        return bool(
            self.wechat_corp_id
            and self.wechat_agent_id
            and self.wechat_corp_secret
        )

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def embed_configured(self) -> bool:
        return bool(self.embed_api_key)

    def ensure_dirs(self) -> None:
        Path(self.rag_index_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.rag_kb_path).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s


# Quick CLI check: `python -m app.config`
if __name__ == "__main__":
    s = get_settings()
    print(f"app_env        = {s.app_env}")
    print(f"wechat         = {'configured' if s.wechat_configured else 'MOCK'}")
    print(f"llm            = {'configured' if s.llm_configured else 'MOCK'} ({s.llm_model})")
    print(f"embed          = {'configured' if s.embed_configured else 'MOCK'} ({s.embed_model}, dim={s.embed_dim})")
    print(f"rag index path = {s.rag_index_path}")
    print(f"source weights = {s.source_weights}")