"""LLM client. OpenAI-compatible /chat/completions, with mock fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from app.config import get_settings


@dataclass
class LLMResponse:
    text: str
    mock: bool = False
    model: str = ""


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int, mock: bool):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.mock = mock

    def chat(self, system: str, user: str, temperature: float = 0.3) -> LLMResponse:
        if self.mock:
            return LLMResponse(text=_mock_complete(system, user), mock=True, model="mock")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return LLMResponse(text=text, mock=False, model=self.model)


def get_llm() -> LLMClient:
    s = get_settings()
    return LLMClient(
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        model=s.llm_model,
        timeout=s.llm_timeout,
        mock=not s.llm_configured,
    )


def _mock_complete(system: str, user: str) -> str:
    """Mock LLM: extract context snippets from the user prompt and echo them.

    The user prompt for our composer contains a "## 检索证据" section. In mock
    mode we just summarize that section in a fixed structure so the rest of
    the pipeline is exercisable.
    """
    # Try to extract evidence section
    evidence = ""
    if "## 检索证据" in user:
        evidence = user.split("## 检索证据", 1)[1].strip()
        # Cut at next section if any
        for marker in ("## 问题", "## 宝宝档案"):
            if marker in evidence:
                evidence = evidence.split(marker, 1)[0].strip()

    # Naively extract top 3 snippets
    snippets = [s.strip() for s in evidence.split("\n\n") if s.strip()][:3]

    if not snippets:
        return "（mock）知识库中没有找到匹配条目，建议咨询医生。"

    # Build a structured answer that approximates the composer's output
    answer = {
        "conclusion": "（mock 摘要）" + snippets[0][:120],
        "recommendations": [
            s[:80] + "..." for s in snippets[1:3]
        ] or ["参考知识库条目给出的具体建议。"],
        "warning_signs": [],
        "sources": ["见检索证据条目"],
    }
    return json.dumps(answer, ensure_ascii=False)


if __name__ == "__main__":
    c = get_llm()
    r = c.chat("你是一个助手", "新生儿黄疸怎么处理？")
    print(f"mock={r.mock}, model={r.model}")
    print(r.text[:200])