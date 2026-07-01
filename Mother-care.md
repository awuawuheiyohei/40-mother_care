***

# 🍼 Mother & Baby AI Assistant Architecture (Enterprise-grade MVP Design)

## 1. Project Positioning

### ✅ Core Definition

This is **NOT** a general chatbot.

> ✅ It is a **High-Confidence, Controlled Knowledge Decision Assistant**

***

### 🎯 Design Priorities

* ✅ Accuracy > Fluency
* ✅ Traceability > Speed
* ✅ Structured Output > Free-form Generation

***

## 2. System Architecture

```
[WeChat Entry]
        ↓
[Bot Service / Webhook]
        ↓
[Query Router]
        ↓
 ┌───────────────┬────────────────┬───────────────┐
 │               │                │               │
[KB Retrieval] [Rule Engine]    [LLM Direct]   (Fallback)
 │               │                │
 └──────────────→[Answer Composer]←──────────────┘
                        ↓
              [Confidence Evaluation]
                        ↓
                 [Final Response]
```

***

## 3. Core Modules Breakdown

***

### 3.1 WeChat Integration Layer

#### Recommended Options

**Option A (Preferred):**

* Enterprise WeChat Bot (稳定 + 合规)

**Option B:**

* Personal WeChat bridge (itchat / wxhook)

#### Flow

```
User → WeChat → Webhook → Backend Service
```

***

### 3.2 Query Router (核心智能层)

Do NOT send everything directly to LLM.

#### Classification Types

| Type      | Example     | Handling      |
| --------- | ----------- | ------------- |
| Knowledge | 新生儿黄疸多少算危险  | KB priority   |
| Action    | 宝宝发烧38.5怎么办 | KB + Rules    |
| Ambiguous | 宝宝不太对劲      | LLM clarifies |

***

### 3.3 Knowledge Base (核心资产)

### ✅ Multi-layer Knowledge Design

***

#### Layer 1: Authoritative Sources (Highest Priority)

Sources:

* WHO
* CDC
* Chinese Pediatric Guidelines

Features:

* Structured
* High confidence

***

#### Layer 2: Curated Knowledge (你的护城河)

* Doctor advice notes
* Personal checklists
* Real-world experience

***

#### Layer 3: Dynamic Additions

* FAQ accumulation
* Temporary research

***

### 📁 Suggested Structure

```
documents/
  pregnancy/
  newborn/
  emergency/
  feeding/

metadata:
  source
  confidence_level
  last_reviewed
```

***

### 3.4 Retrieval System (RAG)

#### Tech Choices

* Embedding: MiniMax / OpenAI / Local
* Vector DB:
  * MVP: FAISS / Chroma
  * Scalable: Milvus / Weaviate

***

#### Retrieval Strategy (VERY IMPORTANT)

```
Step 1: Semantic Search
Step 2: Keyword Filtering
Step 3: Source-based Ranking
```

Priority rule:

```
WHO > Hospital > Curated > Internet
```

***

### 3.5 Guardrails (防止胡说八道)

***

#### ✅ A. No Unsupported Answers

Prompt rule:

```
If no evidence found:
→ Say "Knowledge base does not cover this"
→ Suggest consulting doctor
```

***

#### ✅ B. Mandatory Source Citation

All responses must include:

```
Sources:
- WHO guideline 2023
- XXX hospital
```

***

#### ✅ C. High-Risk Detection

Trigger keywords:

* 发烧
* 呼吸异常
* 抽搐
* 出血

Output:

```
⚠️ Potential emergency
Please contact hospital immediately
```

***

### 3.6 Answer Composer

#### Standard Output Format

```
【Conclusion】
...

【Recommendations】
1.
2.

【Warning Signs】
...

【Sources】
...
```

***

## 4. Accuracy Assurance System

***

### ✅ 4.1 Three-step Generation

```
Step 1: Retrieve evidence
Step 2: LLM summarizes (ONLY based on evidence)
Step 3: Validation prompt check
```

***

### ✅ 4.2 Evidence Binding

Prompt constraint:

```
You MUST only answer based on provided context.
Do NOT use external knowledge.
```

***

### ✅ 4.3 Confidence Score

Example:

```
Confidence: High
Reason: Based on WHO guideline
```

***

### ✅ 4.4 Human Review Loop

You should:

* Log all Q\&A
* Mark:
  * ✅ Correct
  * ❌ Needs fix
* Feed back into KB

👉 This makes system stronger over time

***

## 5. Data Structure Design

### Example Knowledge Item

```json
{
  "id": "NB-001",
  "question": "新生儿发烧定义",
  "content": "新生儿体温超过38°C属于发热...",
  "source": "WHO",
  "confidence": "high",
  "tags": ["发烧", "新生儿"],
  "last_updated": "2026-06-01"
}
```

***

## 6. Product Form & Deployment

***

### Phase 1 (MVP)

✅ WeChat Bot + Backend

Stack:

* FastAPI / Node.js
* Vector DB (local)
* MiniMax API

***

### Phase 2

✅ Admin Console

Features:

* KB upload
* Review answers
* Edit knowledge

***

### Phase 3

✅ Smart Parenting Assistant

* Timeline tracking (孕周 / 月龄)
* Reminders:
  * Vaccination
  * Health checkups
  * Milestones

***

## 7. Compliance & Risk Control

***

### ⚠️ Mandatory Disclaimer

```
This tool is for reference only and does not replace medical advice.
```

***

### ⚠️ Medical Safety Rules

* No diagnosis
* No drug dosage (unless authoritative source)

***

### ⚠️ Data Privacy

* Baby data = sensitive
* Recommendation:
  * Store locally or anonymized
  * Avoid third-party exposure

***

## 8. Development Responsibility Split

***

### 👤 You

* Knowledge Base design ⭐
* Prompt strategy
* Data curation

***

### 🤖 MiniMax Code

* API integration
* Retrieval system
* WeChat connection
* Answer pipeline

***

## 9. Execution Plan

***

### ✅ Day 1–2

* Setup:

```
WeChat → Webhook → API
```

***

### ✅ Day 3–5

* Build KB (50–100 entries)

Categories:

* Fever
* Feeding
* Jaundice

***

### ✅ Day 6–7

* Integrate RAG
* Structured response

***

### ✅ Week 2

* Add Guardrails
* Add citation system
* Add risk detection

***

## 10. One-line Summary

> ✅ A **Controlled, Explainable, High-Safety AI Assistant for Maternal & Infant Care**

***

## ✅ Optional Next Steps

You can extend this project with:

* Prompt Engineering Pack
* APAC maternal keyword dictionary
* Structured review templates
* Multi-language support (CN/EN)

***