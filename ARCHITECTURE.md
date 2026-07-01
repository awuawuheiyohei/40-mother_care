# Architecture: XHS Topic Intelligence Bot

## 1. Architecture Principles

The system follows these principles:

1. **Compliance-first design**: manual content input is the default; no bypassing access control.
2. **Modular pipeline**: input, cleaning, extraction, clustering, risk analysis, and reporting are independent modules.
3. **LLM provider abstraction**: business logic should not depend on a specific LLM vendor.
4. **Traceability**: every extracted topic should preserve source URLs.
5. **Testability**: core modules should be testable without external APIs.
6. **Extensibility**: the system should support future WeCom integration, API service, and knowledge base.

---

## 2. High-level System Diagram

```text
+----------------------+        +----------------------+
| User JSON Input      |        | Future WeCom Input   |
| Manual content       |        | Message / Command    |
+----------+-----------+        +----------+-----------+
           |                               |
           v                               v
+-------------------------------------------------------+
| Input Layer                                           |
| - JSON parser                                         |
| - Input validator                                     |
| - Source URL tracker                                  |
+--------------------------+----------------------------+
                           |
                           v
+-------------------------------------------------------+
| Content Processing Layer                              |
| - Content loader                                      |
| - Content cleaner                                     |
| - Text normalizer                                     |
+--------------------------+----------------------------+
                           |
                           v
+-------------------------------------------------------+
| Intelligence Layer                                    |
| - LLM client abstraction                              |
| - Topic extractor                                     |
| - Topic clusterer                                     |
| - Risk analyzer                                       |
+--------------------------+----------------------------+
                           |
                           v
+-------------------------------------------------------+
| Output Layer                                          |
| - JSON result generator                               |
| - Markdown report generator                           |
| - Local file writer                                   |
| - Future WeCom sender                                 |
+-------------------------------------------------------+
```

---

## 3. Recommended Project Structure

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

## 4. Core Runtime Flow

### 4.1 MVP Local Pipeline

```text
1. User prepares input JSON.
2. main.py loads JSON file.
3. Input validator validates required fields.
4. content_cleaner.py normalizes text.
5. topic_extractor.py extracts per-item topics with LLM.
6. topic_clusterer.py merges similar topics across items.
7. risk_analyzer.py flags sensitive and unsupported claims.
8. report_generator.py creates Markdown report.
9. JSON result and Markdown report are saved locally.
```

### 4.2 Future API Flow

```text
1. User calls POST /analyze.
2. FastAPI validates request body.
3. Pipeline runs asynchronously or synchronously.
4. Report result is stored.
5. API returns report_id and output paths.
6. User calls GET /reports/{report_id}.
7. User optionally calls POST /reports/{report_id}/send-wecom.
```

### 4.3 Future WeCom Flow

```text
1. User sends a command or content to WeCom bot.
2. Backend receives message callback.
3. Backend parses links and manual content.
4. Analysis pipeline generates report.
5. WeCom sender pushes Markdown summary or report file.
```

---

## 5. Module Responsibilities

### 5.1 `content_loader.py`

Responsibilities:

- Load JSON input files.
- Convert raw JSON into Pydantic models.
- Preserve source URL, title, content, and comments.
- Reject invalid input.

MVP behavior:

- Manual content only.
- No automated Xiaohongshu scraping.

---

### 5.2 `content_cleaner.py`

Responsibilities:

- Normalize spaces and line breaks.
- Remove noisy decorative symbols.
- Deduplicate hashtags.
- Preserve important factual information.
- Merge post content and comments with clear labels.

Output example:

```json
{
  "url": "...",
  "title": "...",
  "cleaned_text": "...",
  "metadata": {
    "has_comments": true,
    "comment_count": 3
  }
}
```

---

### 5.3 `llm/client.py`

Responsibilities:

- Provide a unified interface for LLM calls.
- Hide provider-specific implementation.
- Load prompts from `app/llm/prompts/`.
- Handle retries and basic errors.

Suggested interface:

```python
class LLMClient:
    def generate_json(self, prompt: str, schema_name: str) -> dict:
        ...

    def generate_text(self, prompt: str) -> str:
        ...
```

Provider abstraction should allow future support for:

- MiniMax.
- Claude.
- OpenAI-compatible APIs.
- Local models.

---

### 5.4 `topic_extractor.py`

Responsibilities:

- Generate per-item summary.
- Extract topics, subtopics, keywords, pain points, questions, and evidence.
- Produce structured JSON.
- Validate LLM output.

Important rules:

- Do not quote large blocks from the original post.
- Evidence snippets should be short.
- Keep source URL.

---

### 5.5 `topic_clusterer.py`

Responsibilities:

- Merge similar topics across multiple items.
- Combine keywords and questions.
- Preserve all related source URLs.
- Detect possible duplicate topics.
- Prepare consolidated topic list for reporting.

Clustering options:

- MVP: LLM-based semantic clustering.
- Later: embedding-based clustering.

---

### 5.6 `risk_analyzer.py`

Responsibilities:

- Detect sensitive domains.
- Identify medical or infant-care claims.
- Identify advertising bias.
- Identify unsupported or absolute claims.
- Generate risk warnings.

Risk types:

```text
medical
infant_care
advertising
unsupported_claim
privacy
safety
other
```

Severity levels:

```text
low
medium
high
```

---

### 5.7 `report_generator.py`

Responsibilities:

- Generate Markdown report.
- Generate structured JSON output.
- Ensure report format is stable.
- Include source links.
- Include disclaimers where necessary.

Markdown report sections:

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

---

### 5.8 `wecom_sender.py`

Responsibilities:

- Send Markdown report to WeCom.
- Support webhook mode first.
- Later support self-built application mode.
- Handle errors, timeout, and retry.

MVP status:

- Stub or optional implementation.

Future configuration:

```env
WECOM_WEBHOOK_URL=
WECOM_CORP_ID=
WECOM_AGENT_ID=
WECOM_SECRET=
```

---

## 6. Data Flow Details

### 6.1 Input JSON

```json
{
  "project": "maternal-infant-research",
  "language": "zh-CN",
  "items": [
    {
      "url": "https://www.xiaohongshu.com/explore/example1",
      "title": "待产包避坑清单",
      "content": "这里是手动粘贴的小红书正文。",
      "comments": [
        "评论1",
        "评论2"
      ]
    }
  ]
}
```

### 6.2 Topic JSON Output

```json
{
  "report_id": "20260627_235900",
  "input_summary": {
    "total_items": 3,
    "processed_items": 3,
    "failed_items": 0
  },
  "topics": [
    {
      "topic": "待产包准备",
      "summary": "多篇内容围绕入院准备、妈妈用品和宝宝用品展开。",
      "confidence": 0.91,
      "subtopics": ["妈妈用品", "宝宝用品", "医院清单"],
      "keywords": ["待产包", "产褥垫", "尿不湿"],
      "pain_points": ["不知道哪些必须买", "担心买多浪费"],
      "questions": ["医院会提供哪些物品？"],
      "source_urls": ["https://www.xiaohongshu.com/explore/example1"]
    }
  ],
  "risks": [
    {
      "risk_type": "medical",
      "severity": "medium",
      "description": "涉及产后恢复建议，需要结合医生意见。",
      "recommendation": "仅作为信息整理，不作为医疗建议。"
    }
  ]
}
```

---

## 7. Persistence Design

### 7.1 MVP Storage

MVP uses local files:

```text
outputs/
├── topic_result_20260627_235900.json
└── report_20260627_235900.md
```

### 7.2 Future SQLite Schema

Suggested tables:

```text
reports
- id
- report_id
- title
- created_at
- language
- markdown_path
- json_path

source_items
- id
- report_id
- url
- title
- content_hash
- created_at

topics
- id
- report_id
- topic
- summary
- confidence
- source_urls_json

risks
- id
- report_id
- risk_type
- severity
- description
- recommendation
```

---

## 8. Error Handling

### 8.1 Input Errors

Examples:

- Missing URL.
- Missing title.
- Empty content.
- Invalid JSON.

Behavior:

- Return clear validation error.
- Do not run LLM pipeline.

### 8.2 LLM Errors

Examples:

- Timeout.
- Invalid JSON output.
- Provider unavailable.

Behavior:

- Retry configurable times.
- Save partial results if possible.
- Return actionable error message.

### 8.3 WeCom Errors

Examples:

- Invalid webhook URL.
- Token expired.
- Message too long.
- API rate limit.

Behavior:

- Log sanitized error.
- Retry if safe.
- Fall back to local report file.

---

## 9. Configuration

### 9.1 `.env.example`

```env
APP_ENV=development
APP_LANGUAGE=zh-CN
OUTPUT_DIR=outputs

LLM_PROVIDER=minimax
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=

WECOM_MODE=webhook
WECOM_WEBHOOK_URL=
WECOM_CORP_ID=
WECOM_AGENT_ID=
WECOM_SECRET=

LOG_LEVEL=INFO
```

---

## 10. Testing Strategy

### 10.1 Unit Tests

Required tests:

- Content cleaning.
- Input validation.
- Topic model validation.
- Report generation.
- Risk detection rules.

### 10.2 Mock LLM Tests

Use mocked LLM responses to test:

- Valid JSON parsing.
- Invalid JSON handling.
- Missing field recovery.

### 10.3 Integration Tests

Later milestones:

- End-to-end JSON input to Markdown output.
- FastAPI endpoint test.
- WeCom sender dry-run.

---

## 11. Security Considerations

1. Do not log API keys.
2. Do not commit `.env`.
3. Mask URLs if they contain sensitive tokens.
4. Do not store private user data unless explicitly needed.
5. Do not store raw content longer than necessary if privacy mode is enabled.
6. Provide a delete function for reports in future versions.

---

## 12. Deployment Options

### 12.1 Local CLI
Best for MVP.

```text
python -m app.main --input inputs/sample_input.json
```

### 12.2 Local FastAPI
Best for testing API mode.

```text
uvicorn app.main:app --reload
```

### 12.3 Docker
Future deployment option.

### 12.4 Cloud VM
Future deployment for WeCom callback and scheduled tasks.

---

## 13. Future Enhancements

1. Embedding-based topic clustering.
2. Domain-specific report templates.
3. Maternal and infant checklist generation.
4. Knowledge base retrieval.
5. WeCom interactive commands.
6. Scheduled topic digest.
7. Multi-language report generation.
8. Report comparison across time periods.
