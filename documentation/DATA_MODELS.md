# Data Models — GetHeard

All data is stored as JSON files. This document describes the schema for every entity type.

---

## Project (`projects/{project_id}.json`)

Represents a commissioned research study.

```json
{
  "project_id": "proj_abc12345",
  "name": "KYC Drop-off Study Q1 2026",
  "research_type": "pain_points",
  "industry": "Fintech",
  "objective": "Understand why users abandon the KYC verification process",
  "audience": "Mobile banking users aged 25-45 in India",
  "language": "hi",
  "topics": ["documentation requirements", "technical issues", "trust concerns"],
  "question_count": 10,

  "questions": [
    {
      "number": 1,
      "type": "opening",
      "main": "Tell me about your experience with mobile banking KYC.",
      "probe": "What stands out most in that experience?",
      "intent": "Establish context and emotional baseline"
    },
    {
      "number": 2,
      "type": "exploratory",
      "main": "Walk me through what happened when you tried to complete your KYC.",
      "probe": "What specifically made you stop or struggle?",
      "intent": "Map the drop-off moment"
    }
  ],

  "sessions": ["sess_abc", "sess_def"],

  "status": "interviewing",

  "pipeline": {
    "briefing":          {"status": "completed", "started_at": "...", "completed_at": "..."},
    "pricing":           {"status": "completed", "completed_at": "..."},
    "timeline_estimate": {"status": "completed", "completed_at": "..."},
    "awaiting_payment":  {"status": "completed", "completed_at": "..."},
    "panel_building":    {"status": "completed", "completed_at": "..."},
    "panel_approval":    {"status": "completed", "completed_at": "..."},
    "interviewing":      {"status": "in_progress", "started_at": "..."},
    "analysis":          {"status": "pending"},
    "completed":         {"status": "pending"}
  },

  "client_id": "client_xyz789",
  "client_email": "priya@acme.com",

  "market": "IN",
  "target_respondents": 20,
  "interviews_completed": 12,
  "payment_received": true,

  "panel_source": "db",

  "quote_params": {
    "study_type": "pain_points",
    "panel_size": 20,
    "panel_source": "db",
    "market": "IN",
    "industry": "fintech",
    "urgency": false,
    "respondent_incentive_per_head": 0
  },

  "quote": {
    "study_fee": 14999,
    "size_multiplier": 1.5,
    "study_fee_after_multiplier": 22499,
    "recruitment_fee": 29980,
    "incentive_total": 0,
    "urgency_fee": 0,
    "total": 52479,
    "currency": "INR"
  },

  "payment_info": {
    "provider": "razorpay",
    "order_id": "order_Abc123",
    "payment_id": "pay_Xyz789",
    "paid_at": "2026-03-26T10:00:00Z",
    "amount_inr": 52479
  },

  "report_id": null,

  "created_at": "2026-03-25T09:00:00Z",
  "updated_at": "2026-03-27T14:30:00Z"
}
```

### Enums

**`research_type`:** `cx` | `ux` | `brand` | `product` | `nps` | `nps_csat` | `employee` | `market` | `pain_points` | `feature_feedback` | `custom`

**`status`:** `briefing` | `pricing` | `timeline_estimate` | `awaiting_payment` | `panel_building` | `panel_approval` | `interviewing` | `analysis` | `completed` | `cancelled`

**`panel_source`:** `csv` | `db` | `targeted`

**`pipeline[stage].status`:** `pending` | `in_progress` | `completed` | `failed`

---

## Transcript (`transcripts/{timestamp}_{session_id}_{lang}.json`)

Represents one completed interview session.

```json
{
  "session_id": "sess_abc123",
  "language_code": "hi",
  "started_at": "2026-03-27T11:00:00Z",
  "ended_at": "2026-03-27T11:08:32Z",
  "duration_seconds": 512,
  "turn_count": 9,

  "conversation": [
    {
      "role": "assistant",
      "type": "greeting",
      "text": "नमस्ते! मैं GetHeard की ओर से हूँ।...",
      "timestamp": "2026-03-27T11:00:00Z"
    },
    {
      "role": "user",
      "type": "response",
      "text": "मैंने बैंकिंग KYC करने की कोशिश की लेकिन...",
      "timestamp": "2026-03-27T11:00:45Z"
    },
    {
      "role": "assistant",
      "type": "question",
      "text": "यह सुनकर बुरा लगा। आपने क्या विशेष रूप से पाया?",
      "timestamp": "2026-03-27T11:01:02Z"
    }
  ],

  "metadata": {
    "project_id": "proj_abc12345",
    "respondent_id": "r_xyz789",
    "provider_info": {
      "stt": "sarvam",
      "tts": "sarvam",
      "llm": "gemini-2.5-flash",
      "language": "hi"
    },
    "channel": "voice"
  }
}
```

---

## Report (`reports/{report_id}.json`)

AI-generated research report from AnalysisAgent.

```json
{
  "report_id": "rep_abc123",
  "project_id": "proj_xyz789",
  "project_name": "KYC Drop-off Study Q1 2026",
  "research_type": "pain_points",
  "objective": "Understand why users abandon KYC verification",
  "generated_at": "2026-03-28T09:00:00Z",
  "generated_by": "AnalysisAgent (gemini-2.5-pro, 4-pass)",

  "methodology": {
    "total_respondents": 20,
    "languages_represented": ["hi", "en"],
    "avg_turns_per_interview": 8.4,
    "completion_rate": "95%",
    "interview_window": "2026-03-26 to 2026-03-28"
  },

  "executive_summary": "Based on 20 in-depth voice interviews conducted in Hindi and English across Mumbai, Delhi, and Bangalore, three critical barriers to KYC completion emerged: documentation complexity, technical failures during upload, and trust deficits around data sharing. 80% of respondents cited the document list as 'confusing or unexpected', with PAN + Aadhaar requirements unclear upfront. One in three experienced at least one technical failure (camera, upload errors). This report presents detailed findings with verbatim quotes and 5 specific recommendations for product improvement.",

  "sentiment_overview": {
    "overall": "negative",
    "positive_pct": 20,
    "neutral_pct": 25,
    "negative_pct": 55,
    "sentiment_narrative": "Sentiment was predominantly negative, driven by friction and confusion rather than mistrust of the institution itself. Respondents expressed frustration with process design, not with the bank brand."
  },

  "key_themes": [
    {
      "theme": "Documentation Complexity",
      "frequency": 16,
      "frequency_pct": 80,
      "sentiment": "negative",
      "description": "Respondents were surprised by the number and type of documents required, often abandoning after discovering new requirements mid-process.",
      "quotes": [
        "I had my Aadhaar ready but then it asked for a selfie with PAN and I didn't know that.",
        "The list kept changing every time I came back to complete it."
      ],
      "sub_themes": ["Upfront disclosure gap", "Document type confusion", "Multiple trips to complete"]
    },
    {
      "theme": "Technical Failures",
      "frequency": 12,
      "frequency_pct": 60,
      "sentiment": "negative",
      "description": "Camera permissions, upload errors, and session timeouts were frequently mentioned as triggers for abandonment.",
      "quotes": [
        "My photo kept failing even in good light.",
        "The page just refreshed and I had to start over."
      ],
      "sub_themes": ["Camera issues", "Upload errors", "Session timeout"]
    }
  ],

  "question_insights": [
    {
      "question_number": 1,
      "question_text": "Tell me about your most recent KYC experience.",
      "summary": "Most respondents described the experience as 'confusing' or 'tedious'. Positive outliers had completed KYC at a branch with staff help.",
      "top_responses": ["Frustration with document list", "Technical issues", "Had to abandon and return later"],
      "sentiment": "negative",
      "notable_quote": "It felt like they were testing my patience more than verifying my identity."
    }
  ],

  "notable_quotes": [
    {
      "respondent_id": "r_abc123",
      "language": "hi",
      "quote": "Documents maangne ka koi end hi nahi tha — ek ke baad ek.",
      "translation": "There was no end to asking for documents — one after another.",
      "theme": "Documentation Complexity"
    }
  ],

  "pain_points": [
    {
      "pain_point": "No upfront document checklist",
      "severity": "high",
      "frequency_pct": 80,
      "description": "Users do not know what documents will be needed before starting.",
      "recommendation": "Show complete document checklist on the 'Get Started' screen before any other action."
    }
  ],

  "positive_highlights": [
    {
      "highlight": "Trust in brand",
      "frequency_pct": 70,
      "description": "Despite process frustration, most respondents trusted the institution and intended to complete eventually."
    }
  ],

  "recommendations": [
    "Show a complete document checklist before starting the KYC flow.",
    "Add a 'save progress' feature so users can return without restarting.",
    "Send a WhatsApp reminder with a direct resume link after abandonment.",
    "Improve camera error messages with specific troubleshooting steps.",
    "Add a live chat option during KYC for instant help."
  ]
}
```

---

## Respondent (`respondents/{respondent_id}.json`)

A panel member enrolled on GetHeard.

```json
{
  "respondent_id": "r_abc123",
  "name": "Ravi Kumar",
  "phone": "+919876543210",
  "email": "ravi@example.com",
  "language": "hi",
  "city": "Mumbai",
  "country": "IN",
  "age_range": "25-34",
  "gender": "male",
  "interests": ["fintech", "ecommerce", "food"],
  "status": "enrolled",
  "consent_contact": true,
  "enrolled_at": "2026-03-01T...",
  "interviewed_at": "2026-03-27T...",
  "points_balance": 250,
  "points_lifetime": 500,
  "points_transactions": [
    {
      "type": "credit",
      "amount": 100,
      "reason": "Panel selection",
      "study_id": "proj_abc123",
      "timestamp": "2026-03-26T..."
    },
    {
      "type": "credit",
      "amount": 400,
      "reason": "Interview completed",
      "study_id": "proj_abc123",
      "timestamp": "2026-03-27T..."
    },
    {
      "type": "debit",
      "amount": 250,
      "reason": "UPI redemption",
      "request_id": "red_xyz789",
      "timestamp": "2026-03-28T..."
    }
  ],
  "sensitive": {
    "medical_conditions": "",
    "sexual_orientation": "prefer_not_to_say"
  }
}
```

### Enums

**`status`:** `enrolled` | `scheduled` | `interviewed` | `inactive` | `blocked`

**`age_range`:** `18-24` | `25-34` | `35-44` | `45-54` | `55+`

**`gender`:** `male` | `female` | `non_binary` | `prefer_not_to_say` | `other`

**`language`:** `en` | `hi` | `id` | `fil` | `th` | `vi` | `zh` | `ko` | `ja` | `ta` | `te` | `ml` | `kn` | `bn` | `mr` | `gu` | `pa` | `or`

**`interests`:** `fintech` | `ecommerce` | `food` | `travel` | `healthcare` | `education` | `gaming` | `fashion` | `automotive` | `real_estate`

---

## Client (`clients/{client_id}.json`)

A brand / company commissioning research.

```json
{
  "client_id": "client_abc123",
  "name": "Priya Sharma",
  "company": "ACME Fintech Pte Ltd",
  "email": "priya@acme.com",
  "country": "IN",
  "password_hash": "sha256_hex_string",
  "status": "active",
  "created_at": "2026-03-01T...",
  "last_login": "2026-03-27T...",
  "studies": ["proj_abc123", "proj_def456"]
}
```

**`status`:** `active` | `suspended` | `deleted`

---

## Panel (`panels/{panel_id}.json`)

A selected group of respondents for a specific project.

```json
{
  "panel_id": "panel_abc123",
  "project_id": "proj_xyz789",
  "source": "db",
  "created_at": "2026-03-26T...",
  "confirmed_at": "2026-03-26T...",
  "confirmed_by": "client_abc123",
  "respondents": [
    {
      "respondent_id": "r_abc123",
      "name": "Ravi Kumar",
      "language": "hi",
      "city": "Mumbai",
      "country": "IN",
      "age_range": "25-34",
      "gender": "male",
      "status": "scheduled",
      "interview_completed": true,
      "completed_at": "2026-03-27T..."
    }
  ],
  "total": 20,
  "completed": 15,
  "status": "active"
}
```

---

## Redemption Request (`redemptions/{request_id}.json`)

A respondent's request to redeem points for cash or gift card.

```json
{
  "request_id": "red_abc123",
  "respondent_id": "r_xyz789",
  "respondent_name": "Ravi Kumar",
  "respondent_phone": "+919876543210",
  "country": "IN",

  "points": 200,
  "method": "upi",
  "cash_value": 100.0,
  "currency": "INR",
  "gift_card_bonus_applied": false,

  "details": {
    "upi_id": "ravi@okaxis"
  },

  "status": "completed",
  "admin_notes": "Transferred via HDFC UPI on 28 Mar 2026",

  "created_at": "2026-03-28T09:00:00Z",
  "updated_at": "2026-03-28T11:00:00Z"
}
```

**`method`:** `upi` | `gift_card` | `bank_transfer`

**`status`:** `pending` | `approved` | `completed` | `rejected`

---

## Pricing Config (`config/pricing.json`)

Admin-editable pricing configuration. Loaded at runtime by `pricing_store.py`.

```json
{
  "base_prices": {
    "nps_csat": 7999,
    "feature_feedback": 11999,
    "pain_points": 14999,
    "custom": 16999
  },

  "panel_size_multipliers": [
    {"min": 5,  "max": 10,  "multiplier": 1.0},
    {"min": 11, "max": 15,  "multiplier": 1.25},
    {"min": 16, "max": 20,  "multiplier": 1.5},
    {"min": 21, "max": 30,  "multiplier": 2.5},
    {"min": 31, "max": 40,  "multiplier": 3.5},
    {"min": 41, "max": 50,  "multiplier": 4.0},
    {"min": 51, "max": 60,  "multiplier": 5.0},
    {"min": 61, "max": 999, "multiplier": 6.0}
  ],

  "recruitment_fees": {
    "from_db_per_respondent": 1499,
    "targeted_base_per_respondent": 2499,
    "targeted_market_multipliers": {
      "IN": 1.0, "SG": 1.4, "ID": 1.1, "MY": 1.2,
      "TH": 1.2, "VN": 1.0, "JP": 1.8, "KR": 1.6,
      "CN": 1.5, "PH": 1.0
    },
    "industry_multipliers": {
      "healthcare": 1.5, "fintech": 1.2, "gaming": 0.9,
      "ecommerce": 1.0, "education": 1.0, "fmcg": 1.1,
      "automotive": 1.3, "real_estate": 1.4, "saas": 1.1,
      "other": 1.0
    }
  },

  "urgency_premium_percent": 25,
  "currency": "INR",
  "updated_at": "2026-03-27T..."
}
```

---

## In-Memory Session (Voice Interview)

Not persisted — stored in `active_sessions` dict in `app.py`.

```python
active_sessions = {
  "sess_abc123": {
    "pipeline": VoiceInterviewPipeline(...),
    "started_at": datetime,
    "language": "hi",
    "project_id": "proj_xyz789"
  }
}
```

Sessions are created on `POST /api/start` and cleaned up on `POST /api/end/{id}` or server restart.

---

## File Naming Conventions

| Entity | Pattern | Example |
|--------|---------|---------|
| Project | `{project_id}.json` | `proj_abc12345.json` |
| Transcript | `{YYYY-MM-DD}_{session_id}_{lang}.json` | `2026-03-27_sess_abc_hi.json` |
| Report | `{report_id}.json` | `rep_abc12345.json` |
| Respondent | `{respondent_id}.json` | `r_abc12345.json` |
| Client | `{client_id}.json` | `client_abc12345.json` |
| Panel | `{panel_id}.json` | `panel_abc12345.json` |
| Redemption | `{request_id}.json` | `red_abc12345.json` |

All IDs use prefix + 8-character hex: `proj_` | `sess_` | `rep_` | `r_` | `client_` | `panel_` | `red_`
