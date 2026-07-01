# Project Brief: XHS Topic Intelligence Bot

## 1. Context

I want to build a project with Claude Code called **XHS Topic Intelligence Bot**.

The product should help me process one or multiple Xiaohongshu links and manually provided post content, then generate detailed and standardized topic reports for review. The final report should be suitable for Enterprise WeChat / WeCom delivery.

The first target domain may be maternal and infant knowledge, but the architecture should be generic enough to support other topics later.

---

## 2. Product Goal

Given one or multiple Xiaohongshu links plus manually pasted content, the system should generate:

1. A structured topic JSON result.
2. A Markdown topic intelligence report.
3. Risk warnings for medical, infant-care, unsupported, or promotional claims.
4. Source link references.
5. Future WeCom push capability.

---

## 3. Important Compliance Constraints

This project must be compliance-first.

Do not implement:

- Xiaohongshu login automation.
- CAPTCHA bypass.
- Anti-bot bypass.
- Private API scraping.
- Cookie-based restricted access.
- Large-scale crawling.
- Private user data extraction.
- Full original content redistribution.

MVP should support manual content input first.

If a link is not publicly accessible, the system should ask the user to paste the content manually.

---

## 4. MVP Scope

### Milestone 1: Local Analysis Pipeline

Input:

- A JSON file containing multiple items.

Each item contains:

- `url`
- `title`
- `content`
- `comments` optional

Processing:

1. Validate input.
2. Clean content.
3. Extract topics from each item.
4. Cluster topics across items.
5. Analyze risks.
6. Generate Markdown report.
7. Save JSON and Markdown outputs locally.

Output:

```text
outputs/topic_result_YYYYMMDD_HHMMSS.json
outputs/report_YYYYMMDD_HHMMSS.md
```

---

## 5. Recommended Tech Stack

- Python 3.11+
- FastAPI for later API mode
- Pydantic for data models
- SQLite for later persistence
- Markdown for report output
- Modular LLM client
- WeCom sender module for future integration

LLM provider should be abstracted. Do not hardcode one vendor.

Possible providers:

- MiniMax
- Claude
- OpenAI-compatible APIs
- Local model in the future

---

## 6. Required Project Structure

Please generate the project skeleton as follows:

```text
xhs-topic-intelligence-bot/
│
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── api/
│   │   ├── routes_links.py
│   │   ├── routes_reports.py
│   │   └── routes_wecom.py
│   │
│   ├── services/
│   │   ├── content_loader.py
│   │   ├── content_cleaner.py
│   │   ├── topic_extractor.py
│   │   ├── topic_clusterer.py
│   │   ├── risk_analyzer.py
│   │   ├── report_generator.py
│   │   └── wecom_sender.py
│   │
│   ├── llm/
│   │   ├── client.py
│   │   ├── provider_base.py
│   │   └── prompts/
│   │       ├── summarize.md
│   │       ├── extract_topics.md
│   │       ├── cluster_topics.md
│   │       ├── analyze_risks.md
│   │       └── generate_report.md
│   │
│   ├── models/
│   │   ├── input.py
│   │   ├── topic.py
│   │   ├── risk.py
│   │   └── report.py
│   │
│   ├── storage/
│   │   ├── database.py
│   │   └── repository.py
│   │
│   └── utils/
│       ├── file_utils.py
│       ├── text_utils.py
│       └── validators.py
│
├── inputs/
│   └── sample_input.json
│
├── outputs/
│   └── .gitkeep
│
├── tests/
│   ├── test_content_cleaner.py
│   ├── test_topic_extractor.py
│   ├── test_topic_clusterer.py
│   ├── test_risk_analyzer.py
│   └── test_report_generator.py
│
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── COMPLIANCE.md
│   └── PROJECT_BRIEF.md
│
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── CLAUDE.md
```

---

## 7. Core Modules to Implement First

### 7.1 `content_loader.py`

Implement:

- Load input JSON.
- Validate required fields.
- Convert to Pydantic models.

### 7.2 `content_cleaner.py`

Implement:

- Normalize whitespace.
- Remove obvious noise.
- Deduplicate hashtags.
- Preserve product names, numbers, prices, dates, medical terms, and source URLs.

### 7.3 `llm/client.py`

Implement:

- Abstract LLM client.
- Mock mode for testing.
- `generate_text()`.
- `generate_json()`.

### 7.4 `topic_extractor.py`

Implement:

- Per-item summary.
- Topic extraction.
- Keywords.
- Subtopics.
- Pain points.
- Questions.
- Evidence snippets.
- Source URL references.

### 7.5 `topic_clusterer.py`

Implement:

- Merge similar topics.
- Deduplicate keywords and questions.
- Keep all source URLs.
- Detect conflicting opinions.

### 7.6 `risk_analyzer.py`

Implement:

- Detect medical/infant-care content.
- Detect unsupported claims.
- Detect promotional bias.
- Detect private personal data patterns.
- Add disclaimers when needed.

### 7.7 `report_generator.py`

Implement Markdown sections:

```text
# Topic Intelligence Report

## 1. Input Summary
## 2. Executive Summary
## 3. Core Topics
## 4. High-frequency Keywords
## 5. User Pain Points
## 6. Frequently Asked Questions
## 7. Conflicting Opinions
## 8. Risk Warnings
## 9. Actionable Recommendations
## 10. Suggested Follow-up Questions
## 11. Source Links
```

### 7.8 `wecom_sender.py`

Implement as stub first:

- Function signature ready.
- Dry-run mode.
- Future support for webhook and self-built app.

---

## 8. Input Example

Create `inputs/sample_input.json`:

```json
{
  "project": "maternal-infant-research",
  "language": "zh-CN",
  "items": [
    {
      "url": "https://www.xiaohongshu.com/explore/example1",
      "title": "待产包避坑清单",
      "content": "这里是手动粘贴的小红书正文，内容包括待产包、产褥垫、尿不湿、奶瓶等建议。",
      "comments": [
        "医院有些东西会提供，不一定都要买。",
        "我觉得产褥垫可以多准备一点。"
      ]
    },
    {
      "url": "https://www.xiaohongshu.com/explore/example2",
      "title": "新生儿喂养经验",
      "content": "这里是手动粘贴的小红书正文，内容涉及母乳、奶粉、混合喂养和宝宝哭闹。",
      "comments": [
        "宝宝哭不一定就是没吃饱。",
        "喂养问题最好问医生或专业人士。"
      ]
    }
  ]
}
```

---

## 9. Expected JSON Output Example

```json
{
  "report_id": "20260627_235900",
  "language": "zh-CN",
  "input_summary": {
    "total_items": 2,
    "processed_items": 2,
    "failed_items": 0
  },
  "topics": [
    {
      "topic": "待产包准备",
      "confidence": 0.91,
      "summary": "内容主要讨论入院前需要准备的妈妈用品和宝宝用品。",
      "subtopics": ["妈妈用品", "宝宝用品", "医院清单"],
      "keywords": ["待产包", "产褥垫", "尿不湿", "奶瓶"],
      "pain_points": ["不知道哪些必须买", "担心买多浪费"],
      "questions": ["医院会提供哪些物品？", "哪些东西不用提前买？"],
      "source_urls": ["https://www.xiaohongshu.com/explore/example1"]
    }
  ],
  "risks": [
    {
      "risk_type": "medical",
      "severity": "medium",
      "description": "涉及新生儿喂养判断，需要专业验证。",
      "recommendation": "仅作为经验整理，不作为医疗建议。"
    }
  ]
}
```

---

## 10. Expected Markdown Report Example

```markdown
# Topic Intelligence Report

## 1. Input Summary
- Total items: 2
- Processed items: 2
- Failed items: 0

## 2. Executive Summary
This batch mainly discusses hospital bag preparation and newborn feeding. The most frequent concerns are what to buy, what not to overbuy, and which baby-care claims require professional verification.

## 3. Core Topics

### Topic 1: 待产包准备
- Confidence: 0.91
- Related sources: 1
- Keywords: 待产包, 产褥垫, 尿不湿, 奶瓶
- Pain points:
  - 不知道哪些必须买
  - 担心买多浪费
- Questions:
  - 医院会提供哪些物品？
  - 哪些东西不用提前买？

## 8. Risk Warnings
- Medical / infant-care warning: Some feeding-related claims require professional verification.

## 11. Source Links
- https://www.xiaohongshu.com/explore/example1
- https://www.xiaohongshu.com/explore/example2
```

---

## 11. Prompt Templates Required

Create these prompt files:

### `summarize.md`

Purpose:

- Summarize one content item faithfully.
- Do not add unsupported claims.
- Keep source title and URL.

### `extract_topics.md`

Purpose:

- Extract topics, subtopics, keywords, pain points, questions, and short evidence snippets.
- Return valid JSON.

### `cluster_topics.md`

Purpose:

- Merge similar topics across multiple items.
- Keep source URLs.
- Detect conflicts.

### `analyze_risks.md`

Purpose:

- Detect medical, infant-care, advertising, unsupported claims, privacy, and safety risks.
- Return valid JSON.

### `generate_report.md`

Purpose:

- Generate final Markdown report.
- Include disclaimers when needed.
- Do not reproduce full original content.

---

## 12. `.env.example` Required

```env
APP_ENV=development
APP_LANGUAGE=zh-CN
OUTPUT_DIR=outputs

LLM_PROVIDER=mock
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=

WECOM_MODE=dry_run
WECOM_WEBHOOK_URL=
WECOM_CORP_ID=
WECOM_AGENT_ID=
WECOM_SECRET=

LOG_LEVEL=INFO
```

---

## 13. CLAUDE.md Required

Create a `CLAUDE.md` file in the project root:

```markdown
# CLAUDE.md

## Project Name
XHS Topic Intelligence Bot

## Mission
Analyze Xiaohongshu links and user-provided content, then generate structured topic intelligence reports and send them to WeCom.

## Core Principles
1. Compliance first.
2. No bypassing login or anti-bot systems.
3. No private data extraction.
4. No large-scale scraping.
5. Prefer manual content input in MVP.
6. Preserve source links.
7. Summarize and analyze; do not reproduce full original content.

## Output Quality Requirements
Each report should include:
- Input summary
- Key topics
- Subtopics
- Keywords
- User pain points
- Frequently asked questions
- Conflicting opinions
- Risk warnings
- Actionable recommendations
- Source links

## Code Style
- Python 3.11+
- FastAPI-ready architecture
- Type hints required
- Pydantic models required
- Unit tests for core logic
- Clear module boundaries

## Milestone 1
Build local analysis pipeline:
Input JSON -> Clean content -> Extract topics -> Cluster topics -> Analyze risks -> Generate Markdown report.

## Milestone 2
Expose FastAPI endpoints.

## Milestone 3
Add WeCom integration.

## Milestone 4
Add knowledge base and topic trend tracking.
```

---

## 14. Developer Instructions for Claude Code

Please start by creating the repository structure and documentation files. Then implement Milestone 1.

Development order:

1. Create folder structure.
2. Create Pydantic models.
3. Create input loader and validator.
4. Create content cleaner.
5. Create LLM client mock mode.
6. Create prompt templates.
7. Create topic extractor using mock LLM first.
8. Create topic clusterer.
9. Create risk analyzer.
10. Create report generator.
11. Create CLI entry in `app/main.py`.
12. Create tests.
13. Run tests.
14. Update README with usage instructions.

Do not implement actual Xiaohongshu scraping in Milestone 1.

---

## 15. Success Criteria

Milestone 1 is complete when:

1. `python -m app.main --input inputs/sample_input.json` runs successfully.
2. A structured JSON file is generated under `outputs/`.
3. A Markdown report is generated under `outputs/`.
4. Tests pass.
5. There is no scraping or bypass logic.
6. The report includes source links and compliance disclaimers when needed.
