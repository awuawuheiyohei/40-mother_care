# Compliance Guide: XHS Topic Intelligence Bot

## 1. Purpose

This document defines the compliance boundaries for XHS Topic Intelligence Bot. The project must be designed and implemented in a way that respects platform rules, user privacy, copyright, and data security.

The core compliance principle is:

> The system organizes user-provided or publicly accessible information. It must not bypass access restrictions, extract private data, or reproduce original content at scale.

---

## 2. Compliance Principles

### 2.1 Manual Input First
The MVP must prioritize manually provided content.

Allowed:

- User provides a Xiaohongshu link.
- User manually copies title and content into input JSON.
- User optionally includes selected comments.
- System analyzes and summarizes the provided content.

Not allowed:

- Automatically logging into Xiaohongshu.
- Using cookies or tokens copied from a browser to access restricted content.
- Circumventing CAPTCHA or anti-bot controls.
- Using private APIs discovered through reverse engineering.

---

### 2.2 No Access Control Bypass
The system must not bypass:

- Login requirements.
- CAPTCHA.
- Rate limits.
- App-only technical restrictions.
- Paywalls.
- Private APIs.
- Anti-bot systems.

If a link cannot be accessed through normal public access, the system should return:

```text
This content cannot be accessed publicly. Please paste the title and content manually if you have the right to use it.
```

---

### 2.3 No Private Data Collection
The system must not collect or infer private personal data, including but not limited to:

- Phone numbers.
- Addresses.
- ID numbers.
- Private chat content.
- Account credentials.
- Private profiles.
- Precise personal location.
- Sensitive health identity information.

If such data appears in manually pasted input, the system should either:

1. Mask the data; or
2. Warn the user; or
3. Exclude it from the final report.

---

### 2.4 Summary Instead of Reproduction
The system should summarize and analyze content rather than reproduce full original text.

Allowed:

- Short evidence snippets.
- Topic names.
- Keywords.
- Summaries.
- Paraphrased insights.
- Source links.

Not allowed:

- Reposting full original Xiaohongshu notes.
- Generating a report that is mostly copied original text.
- Removing attribution or source links.
- Presenting original user content as the system's own content.

---

### 2.5 Source Traceability
Every topic or insight should retain source references.

Required:

- Source URL.
- Source title.
- Report creation time.
- Clear distinction between input content and generated analysis.

---

## 3. Data Classification

### 3.1 Allowed Data

Allowed in MVP:

- User-provided title.
- User-provided content.
- User-selected comments.
- Public source URL.
- Generated summary.
- Generated topics.
- Generated risk labels.

### 3.2 Restricted Data

Require caution or masking:

- Personal names.
- Usernames.
- Child names.
- Hospital information tied to a specific person.
- Personal timeline details.
- Health history.

### 3.3 Prohibited Data

Should not be collected or stored:

- Account passwords.
- Session cookies.
- Authentication tokens.
- Private messages.
- Phone numbers.
- Home addresses.
- Government ID numbers.
- Payment information.

---

## 4. Xiaohongshu Content Handling Rules

### 4.1 Link Handling
The system may store the provided link as a source reference.

### 4.2 Content Handling
The system should only process content that the user provides or content that is publicly accessible without bypass.

### 4.3 Comments Handling
Comments may contain personal information or unreliable claims. Therefore:

- Comments should be treated as weaker evidence than the main post.
- Comments should be deduplicated and summarized.
- Personal information in comments should be masked or excluded.
- Health-related comments should be flagged for professional verification.

### 4.4 Images and Videos
MVP should not process images or videos unless the user manually provides extracted text.

Future support may include OCR, but it must follow the same compliance requirements.

---

## 5. Health and Maternal/Infant Content Rules

Because this project may be used for maternal and infant knowledge organization, special caution is required.

### 5.1 Required Disclaimer
For reports involving pregnancy, postpartum recovery, newborn care, medication, feeding, disease symptoms, or health decisions, include:

```text
Disclaimer: This report is for information organization only and does not constitute medical advice. For diagnosis, treatment, medication, feeding problems, pregnancy, postpartum recovery, or newborn health issues, please consult qualified medical professionals.
```

### 5.2 Health Claims Must Be Flagged
Flag claims involving:

- Medication.
- Supplements.
- Baby feeding volume.
- Jaundice.
- Eczema.
- Fever.
- Allergies.
- Vaccines.
- Postpartum recovery.
- Breastfeeding problems.
- Emergency symptoms.

### 5.3 Avoid Definitive Medical Advice
The system must avoid statements like:

- “You should definitely use this medicine.”
- “This symptom is harmless.”
- “No need to see a doctor.”
- “This product cures the problem.”

Use safer wording:

- “This claim requires professional verification.”
- “Consider discussing this with a medical professional.”
- “The source presents this as personal experience, not medical evidence.”

---

## 6. Advertising and Commercial Bias

### 6.1 Promotional Pattern Detection
Flag content if it includes:

- Repeated brand promotion.
- Coupon or purchase link language.
- Absolute claims like “must buy”, “best”, “no alternative”.
- Lack of balanced comparison.
- Before/after claims without evidence.

### 6.2 Report Wording
When promotional bias is suspected, use neutral wording:

```text
This recommendation may contain commercial bias. Verify through additional independent sources before making a purchase decision.
```

---

## 7. Copyright and Attribution

### 7.1 Attribution
Always preserve source links.

### 7.2 No Full-text Redistribution
Do not generate reports that reproduce the full original post.

### 7.3 Short Evidence Snippets
Evidence snippets should be:

- Short.
- Necessary for traceability.
- Not a substitute for the original post.

Recommended limit:

```text
Each evidence snippet should generally be under 50 Chinese characters unless there is a strong reason.
```

---

## 8. Storage and Retention

### 8.1 MVP Storage
MVP stores local files only:

```text
outputs/*.json
outputs/*.md
```

### 8.2 Sensitive Data Handling
If sensitive data is detected:

- Mask it in reports.
- Avoid storing it in structured fields.
- Optionally warn the user.

### 8.3 Future Retention Policy
Future versions should support:

- Delete report.
- Delete all source content.
- Export report.
- Privacy mode.
- Retention period configuration.

---

## 9. Logging Rules

Logs must not include:

- API keys.
- WeCom secrets.
- Full raw content if privacy mode is enabled.
- Personal sensitive information.
- Authentication tokens.

Logs may include:

- Report ID.
- Processing status.
- Error type.
- Runtime duration.
- Number of input items.

---

## 10. WeCom Compliance

### 10.1 Webhook Mode
When using WeCom group robot webhook:

- Store webhook URL in `.env`.
- Do not commit webhook URL.
- Avoid sending sensitive personal data to group chats.
- Keep reports concise.

### 10.2 Self-built App Mode
When using WeCom self-built application:

- Store CorpID, AgentID, and Secret securely.
- Cache access token safely.
- Do not expose secrets in logs.
- Ensure the application visible range is properly configured.

### 10.3 Message Content
Before sending to WeCom:

- Mask sensitive personal data.
- Add medical disclaimer if needed.
- Avoid sending full original post text.

---

## 11. Risk Levels

### 11.1 Low Risk
Examples:

- General lifestyle tips.
- Product packing suggestions.
- Non-sensitive consumer opinions.

Action:

- Summarize normally.

### 11.2 Medium Risk
Examples:

- Baby skincare advice.
- Feeding experience.
- Postpartum recovery routines.
- Strong product recommendations.

Action:

- Add caution notes.
- Mark as experience-based.
- Recommend independent verification.

### 11.3 High Risk
Examples:

- Medication advice.
- Disease diagnosis.
- Emergency symptom judgment.
- Private personal data.
- Instructions to bypass platform restrictions.

Action:

- Do not provide definitive advice.
- Add professional consultation warning.
- Mask or exclude private data.
- Refuse to implement bypass-related logic.

---

## 12. Developer Do and Do Not List

### Do

- Use manual input for MVP.
- Preserve source links.
- Generate summaries and structured topics.
- Add risk warnings.
- Mask sensitive information.
- Keep prompts transparent and auditable.
- Write tests for compliance behavior.

### Do Not

- Implement login bypass.
- Implement CAPTCHA solving.
- Use stolen cookies or tokens.
- Reverse engineer private APIs.
- Collect private user information.
- Send sensitive information to WeCom groups.
- Reproduce full original posts.
- Present health claims as medical advice.

---

## 13. Compliance Test Cases

### Test Case 1: Empty Content
Input has URL and title but no content.

Expected:

- Validation error.
- No report generated.

### Test Case 2: Medical Claim
Input includes baby medication recommendation.

Expected:

- Medical risk flagged.
- Disclaimer included.
- No definitive medical recommendation.

### Test Case 3: Phone Number in Comment
Input comment includes phone number.

Expected:

- Phone number masked.
- Warning generated.

### Test Case 4: Promotional Claim
Input includes “this is the only brand worth buying”.

Expected:

- Advertising bias flagged.
- Recommendation to verify through independent sources.

### Test Case 5: Login-required Link
Input only contains a link without pasted content.

Expected:

- Ask user to manually paste content.
- No bypass attempt.

---

## 14. Standard Disclaimer Templates

### 14.1 General Disclaimer

```text
This report is generated from user-provided content and source links. It is intended for information organization and topic analysis only. Please verify important claims through reliable sources.
```

### 14.2 Medical Disclaimer

```text
This report is for information organization only and does not constitute medical advice. For pregnancy, postpartum recovery, newborn health, medication, feeding problems, symptoms, or treatment decisions, please consult qualified medical professionals.
```

### 14.3 Commercial Bias Disclaimer

```text
Some recommendations may reflect personal experience or commercial bias. Please compare multiple independent sources before making purchase decisions.
```

---

## 15. Implementation Requirement

Claude Code or any developer working on this project must follow this compliance guide. If a requested feature conflicts with this document, the implementation should refuse or provide a safe alternative.
