# AGENTS.md

给任何在本仓库工作的 AI agent 的硬约束与运维事实。产品背景见 `README.md`，
架构见 `ARCHITECTURE.md`，合规细则见 `COMPLIANCE.md`。

## 这是什么

母婴 AI 助手。RAG 检索 + LLM 合成，对家长（不是医生）给出**有源可溯**的育儿建议。

## 第一原则：宁可漏答，不可错答

服务对象是真实的新生命。任何改动都必须维持这几条不变量：

1. **KB 每条必须有 `source`**；`confidence=high` 的条目必须有非空 `source_url`
   （`python -m app.kb.lint` 会强制检查）
2. **医疗敏感 query 强制 source_url**：涉及"多少度/几月/多少毫升/剂量/能吃吗"时，
   命中条目没有 source_url 就必须拒答
3. **高危关键词短路**："抽搐/呼吸停止/大出血"等直接返回 120 急救话术，跳过检索
4. **LLM 不得脱离检索证据自由发挥**
5. **每条回答末尾自动追加 disclaimer**
6. **诊外问题一律拒答**（酿酒、哲学等）

改动 `app/guardrails/`、`app/kb/lint.py`、`app/pipeline.py` 时，先跑
`pytest tests/` 确认护栏没被削弱。

## 运行时拓扑

| 服务 | launchd Label | 说明 |
|---|---|---|
| FastAPI | `com.mothercare.uvicorn` | `0.0.0.0:8000` |
| 钉钉 Stream | `com.mothercare.dingtalk` | WebSocket 出站，无需公网回调 |
| ngrok | `com.mothercare.ngrok` | 备用，给企业微信回调用 |

- **三个服务都由 launchd 常驻托管（`RunAtLoad`）**。不要手动 `uvicorn` 或 `bash
  scripts/run_dev.sh`——会撞 8000 端口。
- 状态：`bash scripts/status_services.sh`；日志：`data/{uvicorn,dingtalk,ngrok}.log`
- 改 plist 后必须 `launchctl unload` → `load -w`，否则改动不生效。
- plist 里的绝对路径含 `NN-` 编号前缀，mass/ 每次重排序都要同步改。

## 密钥与配置

- **`.env` 含真实 API key，已 gitignore，永不提交**
- `.env.example` 是模板，**不允许出现任何真实值**（连示例 corp_id 都不能用
  `ww1234567890abcdef` 这种会被 GitHub secret scanner 命中的格式）
- 任一 key 留空 = 该模块走 mock。mock 下 LLM 返回伪总结，embedder 用哈希向量
  （**检索命中率会掉到 ~1%，这是预期的，不是 KB 有问题**）

## 构建产物：faiss.index

`data/faiss.index` 是**构建产物，被 gitignore**，仓库里没有。

- 首次 clone 后必须 `python -m app.rag.build_index` 重建
- **换了 embedding 供应商或模型，必须删掉旧 index 再重建**。维度不匹配时
  FAISS 直接抛 `assert d == self.d`，表现为 `/chat` 返回 500
- 真实 embedding 应显示 `embedder mode: REAL`；显示 `MOCK` 说明 key 没读到
- 重建后重启 uvicorn（retriever 在内存里持有旧 store）：
  `launchctl unload ~/Library/LaunchAgents/com.mothercare.uvicorn.plist && launchctl load -w <同一路径>`

## KB 维护

- 数据在 `app/kb/data/*.jsonl`，schema 与规则见该目录的 `README.md`
- 新增条目后**三步**：`python -m app.kb.lint`（须 0 errors）→ `python -m app.rag.build_index`
  → `python -m app.eval.run_eval --report md`
- 社交媒体内容走三道关卡工具 `python -m app.kb.add_from_text`：
  抽取 → **独立审核（必须独立 prompt + 独立角色）** → 人工确认
- 索引重建后核对 `Hit@1 ≥ 60% / Hit@3 ≥ 85% / MRR ≥ 0.7`。当前基线
  Hit@1 94% / Hit@3 100% / MRR 0.969，掉下来先查是不是 mock 模式

## 测试与 CI

```bash
.venv/bin/ruff check app tests scripts    # lint 必须 0 error
.venv/bin/python -m pytest tests/ -q      # 18 个测试
.venv/bin/python -m app.kb.lint           # 0 errors
```

CI（`.github/workflows/ci.yml`）在 push / PR 到 main 时跑 `ruff + KB lint`，
通过后跑 `pytest`。CI 走 mock 模式，不需要 API key。

> 注意：仓库里 30+ 个文件不符合 `ruff format`，因此 CI **只跑 `ruff check`，不跑
> `ruff format --check`**。新代码保持现有风格即可，不要顺手全量格式化。

## 路径约定（重要）

**禁止硬编码绝对路径**。用 `Path(__file__).resolve().parents[N]` 推导项目根。
mass/ 目录每轮整理都会加 `NN-` 前缀，写死路径的代码每次都要修——本项目就是因为
这么写，重命名后 plist 之外的部分零影响。

改 launchd plist 里的路径时，先确认当前目录名：
`mass/SORT-RECORD-<日期>.md` 里有完整改名映射表。

## 远端

- remote：`https://github.com/awuawuheiyohei/40-mother_care.git`
- **必须用 HTTPS，不要用 SSH。** 本机 TUN 代理（Clash/Surge 类 fake-IP）不透传
  SSH 流量：`github.com` 和 `ssh.github.com` 都解析到 `198.18.0.0/15` 的假 IP，
  22 和 443 端口都在 banner 阶段超时。HTTPS 走 `gh auth git-credential` 认证，
  实测正常。历史上的「HTTPS 在国内不稳」结论已失效——代理开着时正好相反。
- 仓库名是**干净的 `mother-care`**（2026-10-13 从 `40-mother_care` 改回）。
  本地目录仍带 `40-` 归档序号，这是两件事，不要混：
  - **GitHub 仓库名** `mother-care` —— 长期标识，不再跟 mass/ 排序变动
  - **本地目录名** `mass/40-mother_care` —— 每轮重排序会变，改名只动本地目录
  - `deploy/*.plist` 里的绝对路径含 `40-` 前缀，跟的是**本地目录**，保持不变
- 若将来再次重命名远端，三处要一起改：GitHub 仓库名 → `.git/config` 的 remote
  → README 第 5 行 badge URL。改完**逐个验证新值能访问**，不要只确认旧名消失