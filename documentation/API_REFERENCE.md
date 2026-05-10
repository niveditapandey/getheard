# API Reference — GetHeard

**Base URL:** `http://localhost:8000` (dev) | `https://getheard.space` (prod)

**Authentication:**
- Voice API: `X-API-Key: getheard-dev-key-2026` header
- Client portal: Cookie session (login first via `/listen/login`)
- Admin portal: Cookie session (login first via `/admin/login`)
- Most read endpoints: No auth required

---

## Health

### GET /health
Server status and configuration check.

**Response:**
```json
{
  "status": "healthy",
  "voice_provider": "google_cloud",
  "supported_languages": ["en", "hi", "id", "fil", "th", "vi", "zh"],
  "has_sarvam": true,
  "has_twilio": false,
  "active_sessions": 2
}
```

---

## Voice Interview API

### POST /api/start
Start a new voice interview session.

**Request:**
```json
{
  "session_id": "optional-custom-id",
  "language": "en",
  "project_id": "proj_abc123"
}
```

**Response:**
```json
{
  "session_id": "sess_xyz789",
  "greeting_audio": "<base64-encoded-MP3>",
  "greeting_text": "Hello! Thank you for joining this research session.",
  "provider_info": {
    "stt": "google_cloud",
    "tts": "google_cloud",
    "language": "en"
  }
}
```

---

### POST /api/respond
Process a user voice response and get the interviewer's reply.

**Request:**
```json
{
  "session_id": "sess_xyz789",
  "audio": "<base64-encoded-audio>",
  "audio_format": "webm"
}
```

**Response:**
```json
{
  "user_transcript": "I had a frustrating experience with the KYC process.",
  "response_text": "That sounds challenging. Can you tell me more about what specifically frustrated you?",
  "response_audio": "<base64-encoded-MP3>",
  "is_complete": false,
  "turn_count": 3
}
```

---

### POST /api/end/{session_id}
Force-end and save an interview session.

**Response:**
```json
{
  "status": "saved",
  "transcript_file": "2026-03-27_sess_xyz789_en.json",
  "turn_count": 8
}
```

---

### GET /api/transcript/{session_id}
Get live conversation history for an active session.

**Response:**
```json
{
  "session_id": "sess_xyz789",
  "language": "en",
  "turns": [
    {"role": "assistant", "text": "Hello! Thank you...", "type": "greeting"},
    {"role": "user", "text": "I had a frustrating...", "type": "response"}
  ],
  "is_complete": false
}
```

---

### GET /api/transcripts
List all saved transcript files.

**Response:**
```json
{
  "transcripts": [
    {
      "filename": "2026-03-27_sess_abc_en.json",
      "session_id": "sess_abc",
      "language": "en",
      "turn_count": 8,
      "created_at": "2026-03-27T10:30:00Z"
    }
  ],
  "total": 45
}
```

---

### GET /api/stats
Platform analytics stats.

**Response:**
```json
{
  "total_transcripts": 45,
  "by_language": {"en": 30, "hi": 10, "id": 5},
  "by_channel": {"voice": 40, "whatsapp": 5},
  "active_sessions": 2,
  "total_projects": 12
}
```

---

## Projects API

### POST /api/projects/generate-questions
Generate preview questions from a brief (does not save).

**Request:**
```json
{
  "name": "KYC Drop-off Study",
  "research_type": "pain_points",
  "industry": "Fintech",
  "objective": "Understand why users abandon KYC",
  "audience": "Mobile banking users in India",
  "language": "en",
  "topics": ["documentation", "technical issues", "trust"],
  "count": 10
}
```

**Response:**
```json
{
  "questions": [
    {
      "number": 1,
      "type": "opening",
      "main": "Tell me about your experience with mobile banking verification.",
      "probe": "What stood out most?",
      "intent": "Establish context"
    }
  ]
}
```

---

### POST /api/projects
Create and save a new research project.

**Request:** Same as above, plus questions array.

**Response:**
```json
{
  "project_id": "proj_abc123",
  "name": "KYC Drop-off Study",
  "status": "active",
  "created_at": "2026-03-27T10:00:00Z"
}
```

---

### GET /api/projects
List all projects.

**Response:**
```json
{
  "projects": [
    {
      "project_id": "proj_abc123",
      "name": "KYC Drop-off Study",
      "status": "active",
      "language": "en",
      "question_count": 10,
      "session_count": 5
    }
  ]
}
```

---

### GET /api/projects/{project_id}
Get full project details including questions.

**Response:** Full project JSON (see DATA_MODELS.md)

---

### PATCH /api/projects/{project_id}/questions
Update the questions for a project.

**Request:**
```json
{
  "questions": [...]
}
```

---

## Reports API

### POST /api/reports/generate
Generate a report from transcripts (runs AnalysisAgent).

**Request:**
```json
{
  "project_id": "proj_abc123",
  "transcript_files": ["file1.json", "file2.json"]
}
```

**Response:**
```json
{
  "report_id": "rep_xyz789",
  "status": "generated",
  "project_name": "KYC Drop-off Study",
  "total_transcripts": 20
}
```

---

### GET /api/reports/{report_id}
Get full report JSON.

**Response:** Full report JSON (see DATA_MODELS.md)

---

## Client Portal API

### POST /listen/api/signup
Create a new client account.

**Request:**
```json
{
  "name": "Priya Sharma",
  "company": "ACME Fintech",
  "email": "priya@acme.com",
  "password": "securepassword",
  "country": "IN"
}
```

**Response:**
```json
{
  "client_id": "client_abc123",
  "name": "Priya Sharma",
  "email": "priya@acme.com",
  "status": "active"
}
```

---

### GET /api/client/projects
List projects for the logged-in client.

**Auth:** Session cookie required.

**Response:**
```json
{
  "projects": [
    {
      "project_id": "proj_abc123",
      "name": "KYC Drop-off Study",
      "status": "interviewing",
      "interviews_completed": 12,
      "target_respondents": 20,
      "created_at": "2026-03-25T..."
    }
  ]
}
```

---

### GET /api/client/stats
Stats for the logged-in client.

**Response:**
```json
{
  "active_studies": 2,
  "completed_studies": 5,
  "total_respondents": 143,
  "total_spent_inr": 125000
}
```

---

### POST /api/client/quote/compute
Compute a live pricing quote (no auth required — used for live slider preview).

**Request:**
```json
{
  "study_type": "nps_csat",
  "panel_size": 20,
  "panel_source": "db",
  "market": "IN",
  "industry": "fintech",
  "urgency": false,
  "respondent_incentive_per_head": 100
}
```

**Response:**
```json
{
  "study_fee": 7999,
  "size_multiplier": 1.5,
  "study_fee_after_multiplier": 11999,
  "recruitment_fee": 29980,
  "incentive_total": 2000,
  "urgency_fee": 0,
  "total": 43979,
  "currency": "INR",
  "line_items": [
    {"label": "NPS/CSAT Study (20 respondents)", "amount": 11999},
    {"label": "Panel recruitment (20 × ₹1,499)", "amount": 29980},
    {"label": "Respondent incentive (20 × ₹100)", "amount": 2000}
  ]
}
```

---

### POST /api/client/payment/initiate
Initiate payment for a study.

**Auth:** Session cookie.

**Request:**
```json
{
  "project_id": "proj_abc123",
  "payment_method": "razorpay"
}
```

**Response (Razorpay):**
```json
{
  "provider": "razorpay",
  "order_id": "order_Abc123xyz",
  "amount": 43979,
  "currency": "INR",
  "key_id": "rzp_live_..."
}
```

**Response (Stripe):**
```json
{
  "provider": "stripe",
  "checkout_url": "https://checkout.stripe.com/pay/cs_live_..."
}
```

---

### POST /api/client/payment/razorpay/verify
Verify Razorpay payment after completion.

**Request:**
```json
{
  "project_id": "proj_abc123",
  "razorpay_order_id": "order_Abc123",
  "razorpay_payment_id": "pay_Xyz789",
  "razorpay_signature": "hmac_sha256_signature"
}
```

**Response:**
```json
{
  "status": "verified",
  "project_status": "panel_building"
}
```

---

### GET /api/client/study/{project_id}/status
Get live study pipeline status (polled every 10s by frontend).

**Response:**
```json
{
  "project_id": "proj_abc123",
  "name": "KYC Drop-off Study",
  "status": "interviewing",
  "interviews_completed": 12,
  "target_respondents": 20,
  "pipeline": {
    "briefing": {"status": "completed", "completed_at": "2026-03-25T..."},
    "pricing": {"status": "completed", "completed_at": "2026-03-25T..."},
    "timeline_estimate": {"status": "completed"},
    "awaiting_payment": {"status": "completed"},
    "panel_building": {"status": "completed"},
    "panel_approval": {"status": "completed"},
    "interviewing": {"status": "in_progress", "started_at": "2026-03-26T..."},
    "analysis": {"status": "pending"},
    "completed": {"status": "pending"}
  }
}
```

---

## Panel & Respondent API

### POST /api/respondents/enroll
Enroll a new respondent.

**Request:**
```json
{
  "name": "Ravi Kumar",
  "phone": "+919876543210",
  "email": "ravi@example.com",
  "language": "hi",
  "city": "Mumbai",
  "country": "IN",
  "age_range": "25-34",
  "gender": "male",
  "interests": ["fintech", "ecommerce"],
  "consent_contact": true
}
```

**Response:**
```json
{
  "respondent_id": "r_abc123",
  "name": "Ravi Kumar",
  "status": "enrolled",
  "enrolled_at": "2026-03-27T..."
}
```

---

### GET /api/respondents
List respondents with optional filters.

**Query params:** `language`, `city`, `age_range`, `gender`, `status`, `country`

**Example:** `GET /api/respondents?language=hi&status=enrolled&country=IN`

**Response:**
```json
{
  "respondents": [...],
  "total": 234,
  "filtered": 45
}
```

---

### GET /api/respondents/{id}/points
Get points balance for a respondent.

**Response:**
```json
{
  "respondent_id": "r_abc123",
  "balance": 250,
  "lifetime_earned": 500,
  "transactions": [
    {"type": "credit", "amount": 100, "reason": "Panel selection", "timestamp": "..."},
    {"type": "credit", "amount": 400, "reason": "Interview completed", "study_id": "proj_abc123", "timestamp": "..."},
    {"type": "debit", "amount": 250, "reason": "UPI redemption", "timestamp": "..."}
  ]
}
```

---

### POST /api/respondents/{id}/redeem
Submit a redemption request.

**Request:**
```json
{
  "points": 200,
  "method": "upi",
  "details": {
    "upi_id": "ravi@okaxis"
  },
  "country": "IN"
}
```

**Response:**
```json
{
  "request_id": "red_abc123",
  "status": "pending",
  "points": 200,
  "cash_value": 100.0,
  "currency": "INR",
  "method": "upi",
  "created_at": "2026-03-27T..."
}
```

**For gift card:**
```json
{
  "points": 200,
  "method": "gift_card",
  "details": {
    "card_type": "amazon"
  },
  "country": "IN"
}
```
Note: Gift card redemptions get +10% bonus (200 points → 220 points worth of gift card).

---

### GET /api/points/rates
Exchange rates by country.

**Response:**
```json
{
  "rates": {
    "IN": {"currency": "INR", "rate": 0.50, "upi_available": true},
    "SG": {"currency": "SGD", "rate": 0.01, "upi_available": true},
    "ID": {"currency": "IDR", "rate": 150, "upi_available": false},
    "TH": {"currency": "THB", "rate": 0.20, "upi_available": false}
  },
  "min_redemption_points": 100,
  "gift_card_bonus_percent": 10
}
```

---

## Admin API

### GET /api/admin/stats
Platform-wide statistics.

**Auth:** Admin session.

**Response:**
```json
{
  "total_clients": 28,
  "active_studies": 5,
  "completed_studies": 47,
  "total_respondents": 1234,
  "total_revenue_inr": 450000,
  "pending_redemptions": 12,
  "interviews_this_month": 340
}
```

---

### GET /api/admin/pricing
Get current pricing configuration.

**Response:** Full `config/pricing.json` content.

---

### POST /api/admin/pricing
Update pricing configuration.

**Request:** Updated `config/pricing.json` content (full replace).

**Response:**
```json
{
  "status": "updated",
  "updated_at": "2026-03-27T..."
}
```

---

### PATCH /api/admin/redemptions/{request_id}
Process a redemption request.

**Request:**
```json
{
  "status": "completed",
  "notes": "UPI transferred to ravi@okaxis"
}
```

**Status values:** `pending` | `approved` | `completed` | `rejected`

---

## Agentic API

### POST /agent/api/brief/start
Start a new BriefAgent session.

**Response:**
```json
{
  "session_id": "brief_abc123",
  "message": "Hello! I'm here to help you design a research study. What are you trying to learn from your customers?"
}
```

---

### POST /agent/api/brief/message
Send a message to the BriefAgent.

**Request:**
```json
{
  "session_id": "brief_abc123",
  "message": "We want to understand why users drop off during KYC"
}
```

**Response:**
```json
{
  "reply": "That's a great focus area! Who is your target audience for this study — are you looking at all users or a specific segment?",
  "brief_saved": false,
  "brief": null
}
```

When brief is complete:
```json
{
  "reply": "I've saved your research brief. You're all set! Redirecting you to see your quote.",
  "brief_saved": true,
  "brief": {
    "project_id": "proj_abc123",
    "project_name": "KYC Drop-off Study",
    "research_type": "pain_points",
    ...
  }
}
```

---

### POST /agent/api/reports/generate
Run AnalysisAgent on project transcripts.

**Request:**
```json
{
  "project_id": "proj_abc123"
}
```

**Response:**
```json
{
  "report_id": "rep_xyz789",
  "executive_summary": "Based on 20 interviews...",
  "key_themes": [...],
  "sentiment_overview": {...}
}
```

---

## WhatsApp

### POST /webhook/whatsapp
Inbound WhatsApp message webhook (Twilio).

**Note:** This is called by Twilio, not by your app directly.

**Twilio sends:** Form data with `From`, `Body`, `MessageSid`

**Response:** TwiML XML response

---

### POST /api/whatsapp/send
Send a proactive WhatsApp message.

**Request:**
```json
{
  "to": "+919876543210",
  "message": "You've been selected for a research panel! Click to join your interview."
}
```

**Response:**
```json
{
  "status": "sent",
  "message_id": "wamid.abc123"
}
```
