# Mother & Baby AI Assistant

> 一个**高可信、可控、可溯源**的母婴 AI 助手 —— 给自家宝宝用的，所以宁可漏答、不可错答。

[![Lint + Smoke](https://github.com/awuawuheiyohei/40-mother_care/actions/workflows/ci.yml/badge.svg)](https://github.com/awuawuheiyohei/40-mother_care/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![KB entries](https://img.shields.io/badge/KB-51-brightgreen.svg)](./app/kb/data)

通过钉钉 / 企业微信对话，给新生儿期、婴儿期、孕期的家长提供**有源可溯**的医学建议。

## 设计原则（Why this exists）

这是一个真实服务于自家新生命（EDD 2026-07）的项目，**人命关天**：

- **没有 source 的 KB 不写** —— 拒绝"绿便/攒肚/上火"等缺乏循证基础的概念
- **没有 source_url 的 KB 不能用于"多少度/几月/多少毫升/剂量"类问题** —— Lint 自动降级 confidence
- **LLM 不允许自由发挥** —— 必须基于检索证据回答；不允许编造数据
- **每个回答末尾自动 disclaimer** —— "本工具仅供参考，不替代医生面诊"
- **高危关键词短路** —— 抽搐/呼吸停止/大出血等场景直接返回 120 急救话术，跳过 KB

## 核心特性

| 模块 | 状态 | 说明 |
|---|---|---|
| **KB 知识库** | ✅ 51 条 | 30 新生儿 + 15 婴儿 + 5 孕期 + 1 verified |
| **三道关卡入库** | ✅ | 信息抽取 → 独立审核 → 人工确认（防编造） |
| **RAG 检索** | ✅ | FAISS 向量 + source-weighted cosine + 中文 BGE embedding |
| **LLM 合成** | ✅ | DeepSeek-V3（默认）/ MiniMax / OpenAI 兼容 |
| **答案护栏** | ✅ | 医疗敏感词强制 source_url / 自动 disclaimer / 高危词短路 |
| **Eval 回归** | ✅ | 150 条 labeled queries，Hit@1 ≥ 60% 目标 |
| **钉钉 Stream 接入** | ✅ | 推荐模式，WebSocket 出站，无需公网回调 |
| **企业微信回调** | ✅ | 明文模式，加密模式 stub |
| **launchd 开机自启** | ✅ | 4 个 plist（uvicorn / dingtalk / cloudflared / ngrok） |

## 架构（一句话）

```
钉钉/企微 → Webhook/Stream → FastAPI → Query Router
   → RAG Retriever (FAISS + BGE embedding)
   → Guardrails (medical-safety / high-risk-shortcircuit)
   → Answer Composer (LLM 合成)
   → DingTalk Stream 回推
```

完整架构见 [`ARCHITECTURE.md`](./ARCHITECTURE.md) · 产品设计见 [`PRD.md`](./PRD.md) · 合规约束见 [`COMPLIANCE.md`](./COMPLIANCE.md)。

## 目录结构

```
mother-care/
├── README.md                     # 你正在看的
├── ARCHITECTURE.md               # 架构细节
├── PRD.md                        # 产品需求
├── COMPLIANCE.md                 # 合规与安全约束
├── PROJECT_BRIEF.md              # 项目简报
├── Mother-care.md                # 原始设计文档
├── pyproject.toml
├── .env.example                  # 环境变量模板（带详细注释）
├── app/
│   ├── main.py                   # FastAPI 入口
│   ├── pipeline.py               # 路由 → 检索 → 合成 → 护栏
│   ├── config.py                 # 配置加载
│   ├── wechat/                   # 企业微信接入
│   ├── dingtalk/                 # 钉钉 Stream 接入（推荐）
│   ├── router/                   # 查询路由
│   ├── kb/
│   │   ├── schema.py             # KB 数据 schema
│   │   ├── loader.py             # JSONL loader
│   │   ├── lint.py               # KB 质量检查（confidence/URL/...）
│   │   ├── add_from_text.py      # 三道关卡入库工具
│   │   └── data/                 # 51 条 KB（jsonl）
│   ├── rag/                      # 检索（embedder + FAISS + retriever + build_index）
│   ├── llm/                      # LLM 客户端（mock fallback）
│   ├── guardrails/               # 安全护栏
│   ├── composer/                 # 答案合成
│   ├── eval/run_eval.py          # 检索质量评估
│   └── prompts/system.txt        # LLM 系统 prompt
├── data/                         # 构建产物（被 .gitignore）
│   ├── faiss.index
│   ├── faiss.meta.json
│   └── eval_report.md
├── deploy/                       # launchd plist
├── docs/                         # 平台接入指南
│   ├── DINGTALK_SETUP.md
│   └── WECHAT_SETUP.md
├── scripts/                      # 启动脚本 + KB 灌库
└── tests/                        # smoke + crypto
```

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，至少填：
#   LLM_API_KEY      — DeepSeek（推荐）/ MiniMax / OpenAI
#   EMBED_API_KEY    — SiliconFlow（推荐 BGE）/ OpenAI
#   DINGTALK_*       — 钉钉企业内部应用（推荐平台）
# 任何一项留空 = 该模块走 mock
```

`.env.example` 里每个变量都带注释说明用途、获取链接和替代方案。

### 3. 灌 KB + 构建索引

```bash
python -m app.kb.lint                    # 必须 0 errors
python scripts/seed_kb.py
python -m app.rag.build_index
```

### 4. 跑 eval 看命中率（**必做**）

```bash
python -m app.eval.run_eval --report md
# 输出 data/eval_report.md
```

**目标指标**（真实 embedding 模式）：
- Hit@1 ≥ 60%（最常用问法能命中正确 KB）
- Hit@3 ≥ 85%
- MRR ≥ 0.7

mock 模式下 Hit@1 ~ 1%（hash 向量无意义）—— **这是预期的，不是 KB 问题**。

### 5. 启动服务

```bash
bash scripts/run_dev.sh
# 或：uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

打开 http://localhost:8000/docs 看 API。

### 6. 接入钉钉（推荐）

详见 [`docs/DINGTALK_SETUP.md`](./docs/DINGTALK_SETUP.md)。5 分钟搞定：
1. https://open-dev.dingtalk.com → 企业内部应用 → 机器人能力
2. 把 AppKey / AppSecret / AgentID 填到 `.env`
3. `python -m app.dingtalk.bot`（已用 launchd 自启）

## KB 准确性保障（最重要的一节）

### 数据质量

1. **每条 KB 有 `source` 字段**（WHO / AAP / 中国国家卫健委 / UpToDate / XHS verified）
2. **关键条目有 `source_url`**（可点击的官方文档直链）
3. **不写没有把握的内容** —— 拒绝"绿便/攒肚/上火"等缺乏循证基础的概念
4. **不写具体药物剂量** —— 一律"请咨询儿科医生"
5. **`last_updated` 字段** —— 定期回访权威指南更新

### 工程保障

| 机制 | 实现 |
|---|---|
| **医疗敏感词强制 source_url** | `app/guardrails/` 检测"多少度/几月/剂量/能吃吗"等关键词，命中 KB 必须有 source_url，否则拒答 |
| **高危关键词短路** | 抽搐/呼吸停止/大出血等场景直接返回 120 急救话术，跳过 KB |
| **自动 disclaimer** | 每条回答末尾追加"本工具仅供参考" |
| **KB Lint** | `python -m app.kb.lint` —— high confidence 无 URL 自动报错 |
| **150 条 eval queries** | 每个 KB 条目配 3 种问法（canonical / 用户口语化 / 复述），回归测试 |
| **三道关卡入库** | Stage 1 信息抽取 → Stage 2 独立审核（独立 prompt + 独立角色）→ Stage 3 人工确认 |

### Confidence 规则

| confidence | source_url 必须 | 含义 |
|---|---|---|
| **high** | ✅ 非空 | 来源是 AAP / WHO / 中国国家卫健委指南等官方权威 |
| **medium** | ⚠️ 可空 | 条目质量可信但缺少可点击 URL；或来自个人分享（XHS verified）|
| **low** | ⚠️ 可空 | 仅作为参考；用户需自行核实 |

**为什么严格？** 用户看到 high confidence 会更信任 → 必须有可溯源 URL 否则就是误信。
Lint 强制检查：`high + 空 URL` 直接报错。

## 添加新 KB 条目

### 手动（来自权威指南）

1. 打开对应 jsonl（如 `neonate.jsonl`）
2. **复制一条类似的条目**作为模板
3. 改 `id` / `question` / `content` / `source` / `source_url` / `tags`
4. 跑 `python -m app.kb.lint` 确认 0 errors
5. 跑 `python -m app.rag.build_index` 重建索引

### 三道关卡（来自 XHS 等社交媒体）

**核心思想**：用户看帖后用文字总结 → 三道关卡处理 → 入库，全程防编造。

```bash
# 极简交互模式（推荐）
python -m app.kb.add_from_text
# 粘贴 → 看完 AI 提取 → y/n 决定 → 自动入库
```

或批量模式：
```bash
# 编辑 inputs/xhs_pending.json，然后：
python -m app.kb.add_from_text --input inputs/xhs_pending.json
# 审核 outputs/xhs_kb_review.md（Stage 2 独立审核报告）
python -m app.kb.add_from_text --commit outputs/xhs_kb_review.md
python -m app.kb.lint
python -m app.rag.build_index
```

**三道关卡流程**：
1. **Stage 1：信息抽取员**（LLM）—— 从原帖提取结构化条目，强制精简（≤250字）
2. **Stage 2：独立审核员**（LLM，独立 prompt + 独立角色）—— safety/accuracy 评分 + issues
3. **Stage 3：人工最终确认** —— 用户看 Stage 2 结果标 ✅/❌

**关键设计**：Stage 2 必须用**独立 prompt + 独立角色**（不能和 Stage 1 同一个 LLM 同一段对话），否则会出现"既当运动员又当裁判员"。

## 部署

### macOS launchd 开机自启（当前模式）

```bash
bash scripts/install_launchd.sh    # 安装 4 个 plist
bash scripts/uninstall_launchd.sh  # 卸载
bash scripts/status_services.sh    # 查看状态
```

plist 文件在 `deploy/`：
- `com.mothercare.uvicorn.plist` — FastAPI 服务
- `com.mothercare.dingtalk.plist` — 钉钉 Stream 客户端
- `com.mothercare.cloudflared.plist` — 备用：Cloudflare Tunnel（钉钉 Stream 不需要）
- `com.mothercare.ngrok.plist` — 备用：ngrok（仅企业微信回调模式需要）

### 为什么不用 WeChat？

- 企业微信回调需要公网 HTTPS + 验证 Token + 加密 AES —— 配 ngrok/cloudflared 很麻烦
- 钉钉 Stream 模式：WebSocket **出站连接**，无需公网回调，5 分钟搞定 —— **强烈推荐**

## 安全约束（再次强调）

这个项目直接关系到一个真实的新生命。**任何时候宁可漏答、不可错答**：

- 没有 source 的 KB 不写
- 没有 source_url 的 KB 不能用于"多少/多大/多少度/能吃吗"这类问题
- LLM 不允许自由发挥，必须基于检索证据
- 每个回答末尾自动追加 disclaimer
- 用户问诊外问题（如何酿酒、哲学问题）一律拒答

详细安全设计见 [`COMPLIANCE.md`](./COMPLIANCE.md)。

## 后续路线

- **多轮上下文**：用户追问"那发烧呢？" → 串联上下文
- **用户档案**：月龄/孕周/过敏史 → 检索时加权
- **Admin Console**：KB 上传 / 答案审核 / 反馈循环
- **Reranker**：cross-encoder 或 LLM-based（替换当前的 source-weighted cosine）
- **自动化评测**：每周拉真实 user query 跑回归
- **加密 WeChat 回调**：上线前必须

## License

Private — 仅供个人/家庭使用，不对外开放。