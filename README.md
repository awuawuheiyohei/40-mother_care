# Mother & Baby AI Assistant — MVP Skeleton

一个**高可信、可控、可溯源**的母婴 AI 助手。基于 `Mother-care.md` 的设计文档搭建。

## 当前状态

✅ **MVP 骨架完成 + 50 条 KB**

- 企业微信 webhook 接入（URL 验证 + 消息回调 + 主动发送）
- FastAPI 后端 + 配置中心
- **50 条 KB**（30 新生儿 + 15 婴儿 + 5 孕期），每条带 source + source_url + confidence
- FAISS 向量索引 + embedding 客户端（缺 key 走 mock）
- Query Router + 高危关键词短路
- **强护栏**：医疗敏感 query 必须命中 source_url；自动 disclaimer
- Answer Composer（结论 / 建议 / 警示 / 来源 四段式）
- **Eval 回归框架**：150 条 labeled queries，覆盖每个 KB 条目的 3 种问法

⏳ **未做**
- 真实 embedding / LLM（需要填 API key）
- 多轮对话上下文管理
- 用户/宝宝档案（月龄、孕周、过敏史）
- 加密模式企业微信回调（仅留 stub）
- Admin Console（KB 上传 / 答案审核）

## 目录结构

```
mother_care/
├── Mother-care.md                 # 原始设计文档
├── README.md
├── pyproject.toml
├── .env.example
├── app/
│   ├── main.py                    # FastAPI 入口
│   ├── config.py                  # 配置加载
│   ├── pipeline.py                # 路由 → 检索 → 合成 → 护栏
│   ├── wechat/                    # 企业微信接入
│   ├── router/                    # 查询路由
│   ├── kb/
│   │   ├── schema.py              # KB 数据 schema
│   │   ├── loader.py              # JSONL loader
│   │   ├── data/
│   │   │   ├── neonate.jsonl      # 30 条新生儿期
│   │   │   ├── infant.jsonl       # 15 条婴儿期
│   │   │   └── prenatal.jsonl     # 5 条孕期
│   │   └── eval_data.jsonl        # 150 条评估 queries
│   ├── rag/                       # 检索（embedder + FAISS + retriever）
│   ├── llm/                       # LLM 客户端
│   ├── guardrails/                # 安全护栏
│   ├── composer/                  # 答案合成
│   ├── eval/run_eval.py           # 检索质量评估
│   └── prompts/system.txt         # LLM 系统 prompt
├── data/
│   ├── faiss.index                # 构建出来的向量索引
│   ├── faiss.meta.json            # 索引对应的 KB items
│   └── eval_report.md             # 最近一次 eval 报告
├── scripts/
│   ├── seed_kb.py                 # 灌 KB
│   └── run_dev.sh
└── tests/
    └── test_smoke.py
```

## 快速开始

```bash
# 1. 安装依赖
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填 WECHAT_* / LLM_API_KEY / EMBED_API_KEY（任一留空 = 该模块走 mock）

# 3. 灌 KB + 构建索引
python scripts/seed_kb.py
python -m app.rag.build_index

# 4. 跑 eval 看命中率（重要！）
python -m app.eval.run_eval --report md

# 5. 启动服务
bash scripts/run_dev.sh
# 或: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

打开 http://localhost:8000/docs 看 API。

## Mock 模式

所有外部依赖都可以不配 key 直接跑：

- **没填 LLM_API_KEY**：LLM 返回基于检索片段的伪总结（看 `app/llm/__init__.py:_mock_complete`）
- **没填 EMBED_API_KEY**：embedder 用确定性哈希向量 — **检索质量会很差（Hit@1 ≈ 1%）**，必须换真 key
- **没填 WECHAT_**：手动调 `/chat` 端点测试对话逻辑

> ⚠️ **MOCK 模式仅供流程联调，不能上线**。

## KB 准确性保障（最重要）

### 数据质量

1. **每条 KB 有 source 字段**（WHO / AAP / 中国国家卫健委 / UpToDate / 复旦儿科公开课等）
2. **关键条目有 source_url**（可点击的官方文档直链）
3. **不写没有把握的内容**：拒绝"绿便/攒肚/上火"等缺乏循证基础的概念；不写具体药物剂量
4. **last_updated 字段**：定期回访权威指南更新

### 工程保障

1. **医疗敏感 query 强制 source_url** — 涉及"多少度/多少毫升/几月/剂量"等关键词的 query，命中 KB 必须有 source_url，否则拒答
2. **高危关键词短路** — 抽搐/呼吸停止/大出血等场景直接返回 120 急救话术，跳过 KB
3. **自动 disclaimer** — 每条回答末尾追加"本工具仅供参考"
4. **150 条 eval queries** — 每个 KB 条目配 3 种问法（canonical / 用户口语化 / 复述），回归测试检索质量

### 评估方法

```bash
python -m app.eval.run_eval --report md
# 输出 data/eval_report.md
```

**目标指标**（真实 embedding 模式下）：
- Hit@1 ≥ 60%（最常用的问法能命中正确 KB）
- Hit@3 ≥ 85%
- MRR ≥ 0.7

mock 模式下 Hit@1 ~ 1%（hash 向量无意义），这是预期 — 看到 1% 说明 eval 框架在工作，不是 KB 问题。

## 真实 key 接入

**1. LLM（MiniMax / OpenAI）**

`.env`:
```bash
LLM_BASE_URL=https://api.MiniMax.chat/v1   # 或 https://api.openai.com/v1
LLM_API_KEY=sk-xxxxxxxxxxxx
LLM_MODEL=MiniMax-Text-01                   # 或 gpt-4o-mini / gpt-4o
```

测试：
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u1","query":"新生儿黄疸多少算危险？"}'
```
看 `app/pipeline.py` 日志，确认 LLM 调用成功。

**2. Embedding（OpenAI 兼容）**

`.env`:
```bash
EMBED_BASE_URL=https://api.openai.com/v1
EMBED_API_KEY=sk-xxxxxxxxxxxx
EMBED_MODEL=text-embedding-3-small
EMBED_DIM=1536
```

**重要**：换 embedding 后必须重新 build index！
```bash
mavis-trash data/faiss.index data/faiss.meta.json  # 或 rm
python -m app.rag.build_index
python -m app.eval.run_eval --report md   # 跑一遍 eval 看真实命中率
```

如果 Hit@1 < 60%，调 `RAG_TOP_K` / `RAG_MIN_SCORE` / `SOURCE_WEIGHTS`（在 `.env`）。

**3. 企业微信（可选）**

`.env`:
```bash
WECHAT_CORP_ID=ww...
WECHAT_AGENT_ID=1000002
WECHAT_CORP_SECRET=...
WECHAT_CALLBACK_TOKEN=...
WECHAT_CALLBACK_AES_KEY=...        # 加密模式需要，明文模式可空
WECHAT_ALLOWED_USERS=userid1,userid2  # 留空 = 全部接受
```

回调 URL 配成 `https://<your-domain>/wechat/callback`。当前实现是**明文回调**模式（加密模式 TODO 见 `app/wechat/crypto.py`）。

## 配置企业微信回调

1. 企业微信管理后台 → 应用 → 接收消息 → 设置 API 接收
2. URL 填 `https://<your-domain>/wechat/callback`
3. Token / EncodingAESKey 填到 `.env`
4. 当前默认明文模式，加密模式需要实现 `app/wechat/crypto.py`

## 后续路线

按 `Mother-care.md` 的 Phase 2/3：

- **多轮上下文**：用户追问"那发烧呢？" → 串联上下文
- **用户档案**：月龄/孕周/过敏史 → 检索时加权
- **Admin Console**：KB 上传 / 答案审核 / 反馈循环
- **Reranker**：cross-encoder 或 LLM-based（替换当前的 source-weighted cosine）
- **自动化评测**：每周拉真实 user query 跑回归
- **加密 WeChat 回调**：上线前必须

## 安全约束（再次强调）

这个项目直接关系到一个真实的新生命。**任何时候宁可漏答、不可错答**：

- 没有 source 的 KB 不写
- 没有 source_url 的 KB 不能用于"多少/多大/多少度/能吃吗"这类问题
- LLM 不允许自由发挥，必须基于检索证据
- 每个回答末尾自动追加 disclaimer
- 用户问诊外问题（如何酿酒、哲学问题）一律拒答