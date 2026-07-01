"""Smoke tests — verify the full pipeline runs end-to-end with mock backends."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# Force mock mode for all tests
os.environ.setdefault("LLM_API_KEY", "")
os.environ.setdefault("EMBED_API_KEY", "")

# Use a tmp directory for KB + index
TMP = Path(__file__).resolve().parent.parent / "data_test"
TMP.mkdir(parents=True, exist_ok=True)
os.environ["RAG_KB_PATH"] = str(TMP / "kb")
os.environ["RAG_INDEX_PATH"] = str(TMP / "faiss.index")


@pytest.fixture(scope="module", autouse=True)
def build_test_index():
    """Build a tiny index for tests using bundled KB (neonate + infant + prenatal)."""
    import shutil

    from app.config import get_settings
    from app.rag.build_index import main as build_main

    s = get_settings()
    src_dir = Path(__file__).resolve().parent.parent / "app" / "kb" / "data"
    dst_dir = Path(s.rag_kb_path)
    dst_dir.mkdir(parents=True, exist_ok=True)
    for name in ("neonate.jsonl", "infant.jsonl", "prenatal.jsonl"):
        src = src_dir / name
        dst = dst_dir / name
        if not dst.exists() and src.exists():
            shutil.copy(src, dst)
    build_main()

    from app.rag.retriever import reset_retriever
    reset_retriever()
    yield


def test_root():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data
    assert data["wechat_configured"] is False
    assert data["llm_configured"] is False
    assert data["embed_configured"] is False


def test_knowledge_query_returns_structured_answer():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post("/chat", json={"user_id": "t1", "query": "新生儿黄疸多少算危险？"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["route"] in {"knowledge", "ambiguous"}
    assert "conclusion" in data["answer"]
    assert "recommendations" in data["answer"]
    assert "sources" in data["answer"]
    assert data["confidence"] in {"high", "medium", "low"}


def test_emergency_query_short_circuits():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post("/chat", json={"user_id": "t1", "query": "宝宝抽搐怎么办？"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["route"] == "emergency"
    assert "120" in data["answer"]["conclusion"]


def test_off_topic_query_returns_low_confidence():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/chat",
        json={"user_id": "t1", "query": "如何在家酿造葡萄酒？"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["confidence"] == "low"


def test_wechat_url_verification_passthrough():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.get(
        "/wechat/callback",
        params={
            "msg_signature": "",
            "timestamp": "1",
            "nonce": "2",
            "echostr": "test_echo",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "test_echo"


def test_kb_loader_parses_sample():
    from app.config import get_settings
    from app.kb.loader import load_kb

    s = get_settings()
    items = load_kb(s.rag_kb_path)
    assert len(items) >= 10
    assert all(item.id for item in items)
    assert all(item.source for item in items)


def test_guardrails_emergency_keywords():
    from app.guardrails import check_emergency

    r = check_emergency("宝宝抽搐了")
    assert not r.ok
    assert "120" in (r.response or "")

    r2 = check_emergency("宝宝黄疸")
    assert r2.ok