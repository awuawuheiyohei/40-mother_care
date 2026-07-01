# PRD: XHS Topic Intelligence Bot

## 1. Product Overview

### 1.1 Product Name
**XHS Topic Intelligence Bot**

### 1.2 One-line Description
A compliance-first assistant that converts one or multiple Xiaohongshu links plus user-provided content into structured topic intelligence reports and pushes them to WeCom / Enterprise WeChat.

### 1.3 Background
Xiaohongshu content is often fragmented, experience-based, and mixed with personal opinions, product recommendations, and commercial promotion. Users may collect multiple posts around one scenario, such as maternal and infant care, product selection, hospital preparation, travel planning, or consumer research. However, manually extracting reusable topics, concerns, risks, and action items is time-consuming.

This project aims to turn those fragmented notes into standardized, reviewable, and traceable topic reports.

### 1.4 Product Vision
Build a lightweight personal / small-team intelligence assistant that can:

- Accept Xiaohongshu links and manually pasted content.
- Extract topics, subtopics, questions, keywords, and risks.
- Merge multiple links into one structured report.
- Push the final report to Enterprise WeChat.
- Gradually evolve into a domain-specific knowledge base.

---

## 2. Goals and Non-goals

### 2.1 Goals

#### MVP Goals
1. Accept a JSON input file containing multiple content items.
2. Support manual content input as the primary ingestion method.
3. Clean and normalize text.
4. Extract structured topics from each item.
5. Cluster similar topics across multiple items.
6. Identify potential risks, unsupported claims, medical/health-sensitive content, and advertising bias.
7. Generate:
   - Structured JSON result.
   - Markdown report.
8. Save generated outputs locally.
9. Prepare interfaces for future WeCom integration.

#### Long-term Goals
1. Add FastAPI service endpoints.
2. Add WeCom push capability.
3. Add report history and topic trend tracking.
4. Add knowledge base integration.
5. Add interactive query support through WeCom.
6. Support domain-specific templates, such as maternal and infant care, IT product research, consumer products, and travel planning.

### 2.2 Non-goals

The MVP will **not**:

1. Automatically scrape Xiaohongshu at scale.
2. Bypass login, anti-bot mechanisms, CAPTCHA, paywalls, private APIs, or access controls.
3. Collect private user data.
4. Reproduce full original posts in the final report.
5. Provide medical, legal, or financial advice as authoritative conclusions.
6. Replace professional judgment for health-related decisions.

---

## 3. Target Users

### 3.1 Primary User
A personal knowledge worker who collects Xiaohongshu links and wants structured insights, especially for practical decision-making scenarios.

Example scenarios:

- Preparing for childbirth and newborn care.
- Summarizing product reviews.
- Extracting consumer pain points.
- Building a personal knowledge base.
- Monitoring recurring questions in a topic area.

### 3.2 Secondary Users
- Small teams that need lightweight social content summaries.
- Product researchers.
- Content planners.
- Knowledge base maintainers.

---

## 4. User Scenarios

### Scenario 1: Single Link Analysis
The user provides one Xiaohongshu link and manually pasted content. The system extracts key topics, summary, keywords, and risks.

### Scenario 2: Multi-link Topic Consolidation
The user provides 5-20 links with pasted content. The system merges similar topics, removes duplicates, and generates a consolidated report.

### Scenario 3: Maternal and Infant Knowledge Preparation
The user collects posts about hospital bag preparation, newborn feeding, postpartum recovery, and baby skincare. The system converts them into a structured checklist and flags health-sensitive claims.

### Scenario 4: Enterprise WeChat Push
After generating a report, the system sends a Markdown summary to the user or a WeCom group.

### Scenario 5: Historical Knowledge Base
Reports are stored and can be queried later by topic, keyword, source link, or date.

---

## 5. Functional Requirements

## 5.1 Input Management

### FR-001: JSON Input Support
The system shall accept a JSON file containing multiple content items.

Required fields:

```json
{
  "items": [
    {
      "url": "https://www.xiaohongshu.com/explore/example",
      "title": "Example title",
      "content": "Manually pasted content",
      "comments": ["optional comment 1", "optional comment 2"]
    }
  ]
}
```

### FR-002: Required Field Validation
The system shall validate:

- `url` is not empty.
- `title` is not empty.
- `content` is not empty.
- `comments` is optional.

### FR-003: Manual Content First
The system shall treat manually provided content as the primary source in MVP.

### FR-004: Public Link Placeholder
The system may keep a placeholder module for public page reading, but it must not implement bypass or anti-bot circumvention in MVP.

---

## 5.2 Content Cleaning

### FR-010: Text Normalization
The system shall normalize:

- Extra spaces.
- Repeated line breaks.
- Duplicate hashtags.
- Common platform noise.
- Excessive emoji and decorative symbols.

### FR-011: Preserve Important Data
The system shall preserve:

- Product names.
- Brand names.
- Prices.
- Dates.
- Quantities.
- Locations.
- Medical terms.
- Source URLs.

### FR-012: Source Traceability
Each cleaned content item shall retain its original URL and title.

---

## 5.3 Topic Extraction

### FR-020: Per-item Summary
For each item, the system shall generate a concise summary.

### FR-021: Topic Extraction
For each item, the system shall extract:

- Topics.
- Subtopics.
- Keywords.
- User pain points.
- Frequently asked questions.
- Evidence snippets.
- Confidence score.

### FR-022: Evidence Requirement
Each extracted topic should include evidence from the input content, but evidence should be short and not reproduce large portions of original content.

### FR-023: Structured Output
Topic extraction output shall be saved as structured JSON.

---

## 5.4 Topic Clustering

### FR-030: Similar Topic Merge
The system shall merge semantically similar topics across multiple input items.

### FR-031: Duplicate Removal
The system shall remove duplicate or near-duplicate keywords and questions.

### FR-032: Cross-link Topic Count
Each consolidated topic shall include the number of related source links.

### FR-033: Conflict Detection
The system shall identify potentially conflicting opinions, such as:

- Different product recommendations.
- Conflicting health claims.
- Contradictory preparation checklists.
- Overgeneralized personal experience.

---

## 5.5 Risk Analysis

### FR-040: Sensitive Domain Detection
The system shall flag content involving:

- Medical or health claims.
- Infant care.
- Pregnancy and postpartum recovery.
- Medication or supplement use.
- Financial claims.
- Safety-critical recommendations.

### FR-041: Advertising Bias Detection
The system shall identify possible commercial or promotional bias, such as:

- Strong brand claims without evidence.
- Repeated purchase links or coupon language.
- Absolute claims like “must buy” or “best”.

### FR-042: Unverified Claim Detection
The system shall mark claims that require further verification.

### FR-043: Professional Review Warning
For medical or baby-care related content, the system shall include a warning that the output is for information organization only and should not replace professional advice.

---

## 5.6 Report Generation

### FR-050: Markdown Report
The system shall generate a Markdown report with the following sections:

1. Input summary.
2. Executive summary.
3. Core topics.
4. Subtopics.
5. Keywords.
6. Pain points.
7. Frequently asked questions.
8. Conflicting opinions.
9. Risk warnings.
10. Actionable recommendations.
11. Suggested follow-up questions.
12. Source links.

### FR-051: JSON Result
The system shall generate a structured JSON result for machine processing.

### FR-052: Local File Output
The system shall save generated reports locally.

Suggested output files:

```text
outputs/topic_result_YYYYMMDD_HHMMSS.json
outputs/report_YYYYMMDD_HHMMSS.md
```

---

## 5.7 WeCom Integration

### FR-060: WeCom Sender Module
The system shall include a `wecom_sender.py` module for future integration.

### FR-061: MVP Behavior
In MVP 1, WeCom sending can be a stub or optional module.

### FR-062: Future WeCom Push
In later milestones, the system shall support:

- Send Markdown report to a WeCom group.
- Send summary to a specific user through self-built application.
- Send report file as attachment if needed.

---

## 6. Non-functional Requirements

### 6.1 Compliance
- No unauthorized scraping.
- No bypassing access controls.
- No private user data extraction.
- Keep source URLs for traceability.
- Do not reproduce full original content.

### 6.2 Security
- Store API keys in `.env`, not source code.
- Never commit secrets.
- Mask secrets in logs.
- Validate external input.

### 6.3 Reliability
- Invalid input should produce clear error messages.
- LLM failures should not crash the whole process.
- Partial results should be saved when possible.

### 6.4 Maintainability
- Modular architecture.
- Type hints required.
- Pydantic models required.
- Unit tests for core modules.
- Prompt templates stored separately.

### 6.5 Extensibility
The architecture should support:

- Multiple LLM providers.
- Future web UI.
- Future WeCom interaction.
- Future knowledge base.
- Future topic trend analysis.

---

## 7. Data Model

### 7.1 InputItem

```json
{
  "url": "string",
  "title": "string",
  "content": "string",
  "comments": ["string"]
}
```

### 7.2 ExtractedTopic

```json
{
  "topic": "string",
  "confidence": 0.0,
  "summary": "string",
  "subtopics": ["string"],
  "keywords": ["string"],
  "pain_points": ["string"],
  "questions": ["string"],
  "evidence": ["string"],
  "source_urls": ["string"]
}
```

### 7.3 RiskItem

```json
{
  "risk_type": "medical|advertising|unsupported_claim|privacy|other",
  "severity": "low|medium|high",
  "description": "string",
  "related_topic": "string",
  "recommendation": "string"
}
```

### 7.4 ReportResult

```json
{
  "report_id": "string",
  "created_at": "string",
  "input_count": 0,
  "topics": [],
  "risks": [],
  "markdown_report_path": "string",
  "json_result_path": "string"
}
```

---

## 8. Milestones

### Milestone 1: Local Pipeline
Deliverables:

- Project skeleton.
- JSON input parser.
- Content cleaner.
- LLM client abstraction.
- Prompt templates.
- Topic extractor.
- Topic clusterer.
- Risk analyzer.
- Markdown report generator.
- Local output files.
- Basic tests.

### Milestone 2: FastAPI Service
Deliverables:

- `POST /analyze`.
- `GET /reports/{report_id}`.
- `POST /reports/{report_id}/send-wecom`.
- API request validation.

### Milestone 3: WeCom Integration
Deliverables:

- WeCom webhook sender.
- WeCom self-built application sender.
- Access token cache.
- Error handling and retry.

### Milestone 4: Knowledge Base
Deliverables:

- SQLite report history.
- Topic search.
- Keyword search.
- Source link search.
- Trend summary.

### Milestone 5: Interactive Assistant
Deliverables:

- WeCom interaction.
- Ask follow-up questions.
- Generate checklist from selected topic.
- Generate domain-specific reports.

---

## 9. Acceptance Criteria

### MVP Acceptance Criteria
1. The system can process at least 3 manually provided Xiaohongshu content items.
2. The system outputs a valid JSON result.
3. The system outputs a readable Markdown report.
4. Each topic contains source link references.
5. Medical/infant-care claims are flagged when present.
6. No scraping or bypass logic is implemented.
7. Unit tests pass for core modules.
8. Secrets are not hardcoded.

---

## 10. Open Questions

1. Which LLM provider will be used first?
2. Should the report language be Chinese only or bilingual?
3. Should comments be treated equally with post content or as weaker evidence?
4. Should the system support multiple report templates by domain?
5. Should WeCom push be group-based first or personal app-based first?
