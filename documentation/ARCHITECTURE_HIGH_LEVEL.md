# High-Level Architecture — GetHeard

## System Overview

GetHeard is a monolithic FastAPI web application with an embedded AI agent pipeline. It serves three user-facing portals (client, respondent, admin) and one AI-automated research pipeline — all from a single Python process.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        INTERNET / USERS                          │
└────────────┬──────────────────┬──────────────────┬──────────────┘
             │                  │                  │
      Clients (brands)    Respondents         Admin (Nivedita)
             │                  │                  │
             ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Web Application                        │
│                    (src/web/app.py + 6 routers)                  │
│                                                                   │
│  /listen/*      /join/*       /admin/*     /agent/*    /api/*    │
│  Client Portal  Respondent    Admin        Agentic     Voice API │
│  (app_client)   (app_panel    (app_admin)  (app_       (app.py)  │
│                 app_          app_study)   agentic)              │
│                 respondent)                                       │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ├─────────────────────────────────────────────┐
           ▼                                             ▼
┌──────────────────────┐                    ┌────────────────────┐
│   AI Agent Pipeline  │                    │  Voice Pipeline     │
│                      │                    │                     │
│  BriefAgent          │                    │  STT → Gemini → TTS │
│  DesignerAgent       │                    │                     │
│  PanelAgent          │                    │  Google Cloud STT   │
│  PricingAgent        │                    │  Sarvam AI STT      │
│  TimelineAgent       │                    │  GeminiInterviewer  │
│  AnalysisAgent       │                    │  Google Cloud TTS   │
│  Orchestrator        │                    │  Sarvam AI TTS      │
└──────────┬───────────┘                    └────────┬───────────┘
           │                                         │
           ▼                                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                    External AI APIs                               │
│                                                                   │
│  Google Gemini 2.5 Flash/Pro   Sarvam AI (Indian languages)      │
│  (via google-genai SDK)        (stt-scribe + bulbul TTS)         │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                    External Services                              │
│                                                                   │
│  Razorpay (payments)        Stripe (int'l payments)              │
│  Resend (email)             Meta WhatsApp Business API           │
│  Twilio (WhatsApp fallback) Google Cloud Speech APIs             │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                    File-Based Storage                             │
│                                                                   │
│  projects/      transcripts/    reports/      respondents/       │
│  clients/       panels/         redemptions/                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Web Layer (FastAPI)

The entire application runs as a single FastAPI process. Six APIRouter modules handle different feature areas:

| Router File | Prefix | Responsibility |
|-------------|--------|----------------|
| `app.py` | `/` | Core routes, voice API, WhatsApp webhook, reports |
| `app_client.py` | `/listen` | Client portal — auth, dashboard, signup |
| `app_study.py` | `/listen/study` | Study lifecycle, payment, timeline |
| `app_admin.py` | `/admin` | Admin dashboard, pricing management |
| `app_panel.py` | `/enroll`, `/panel` | Respondent enrollment, panel building |
| `app_respondent.py` | `/join` | Rewards dashboard, points, redemptions |
| `app_agentic.py` | `/agent` | Agentic UI, brief chat, report generation |

**Middleware:**
- `SessionMiddleware` (itsdangerous) — cookie-based sessions for client + admin auth
- `StaticFiles` — serves `/static/design_system.css` and other assets

---

### 2. AI Agent Layer

All agents extend `BaseAgent` which implements a Gemini function-calling loop:

```
BaseAgent.run(message)
  → Build Gemini request with tool definitions
  → Call Gemini API
  → If response has tool_calls → execute handlers → re-run
  → If final text → return AgentResult
```

**Agent Responsibilities:**

| Agent | Input | Output |
|-------|-------|--------|
| BriefAgent | Conversational turns | Structured brief dict |
| DesignerAgent | Brief dict | List of interview questions |
| PanelAgent | Criteria or CSV | Panel JSON + respondent status updates |
| PricingAgent | Project params | Quote breakdown dict |
| TimelineAgent | Project + urgency | Phase timeline dict |
| InterviewAgent | (via VoiceInterviewPipeline) | Conversation turns |
| AnalysisAgent | Transcript files | Full report JSON |

---

### 3. Voice Pipeline

Each browser interview session has its own `VoiceInterviewPipeline` instance:

```
User speaks → Browser captures audio (webm/wav)
  → POST /api/respond with audio bytes (base64)
  → VoiceInterviewPipeline.process_audio()
    → STT provider.transcribe(audio)        # Google Cloud or Sarvam
    → GeminiInterviewer.send_user_response()  # LLM generates reply
    → TTS provider.synthesize_speech()      # Google Cloud or Sarvam
  → Return {transcript, response_audio (base64 MP3), is_complete}
→ Browser plays audio + shows transcript
```

**Auto-routing logic:**
- Language is Indian (`hi`, `ta`, `te`, etc.) AND Sarvam API key configured → **Sarvam**
- Otherwise (or `voice_provider=google_cloud`) → **Google Cloud**
- Can force either with `VOICE_PROVIDER=sarvam` or `VOICE_PROVIDER=google_cloud`

---

### 4. Data Storage

GetHeard uses **JSON file storage** (no database). Each entity type has its own directory:

| Directory | Contents | Key |
|-----------|----------|-----|
| `projects/` | One JSON per study | `{project_id}.json` |
| `transcripts/` | One JSON per interview session | `{timestamp}_{session}_{lang}.json` |
| `reports/` | One JSON per analysis run | `{report_id}.json` |
| `respondents/` | One JSON per panel member | `{respondent_id}.json` |
| `clients/` | One JSON per client company | `{client_id}.json` |
| `panels/` | One JSON per panel build | `{panel_id}.json` |
| `redemptions/` | One JSON per payout request | `{request_id}.json` |

**Trade-off:** Simple to build, zero infrastructure — but not suitable for high concurrency or large datasets. Migration to PostgreSQL is in the backlog.

---

### 5. Authentication

**Client portal:** Cookie session via `itsdangerous.URLSafeTimedSerializer`
- Login → `request.session["client_id"] = client_id`
- Protected routes check `request.session.get("client_id")`
- Passwords hashed with SHA-256

**Admin portal:** Same mechanism, `request.session["is_admin"] = True`
- Admin credentials stored in `.env` as `ADMIN_CREDENTIALS=user:pass`

**Voice API:** API key auth header (`X-API-Key: getheard-dev-key-2026`)

---

### 6. Notification Layer

All notifications go through `src/notifications/notifier.py`:

```
send_email(to, subject, body)
  → POST https://api.resend.com/emails
  → From: hello@getheard.space (once domain verified)
  → Falls back gracefully if RESEND_API_KEY not set

send_whatsapp(to_phone, message)
  → POST https://graph.facebook.com/v19.0/{phone_number_id}/messages
  → Uses Meta WhatsApp Business API
  → Falls back gracefully if token not set
```

---

## Data Flow: Study Commission (Happy Path)

```
1. Client signs up → POST /listen/api/signup → clients/{id}.json created

2. Client starts new study → GET /listen/study/new → study_new.html

3. BriefAgent chat → POST /agent/api/brief/message (multiple turns)
   → Brief complete → projects/{id}.json created (status: briefing)

4. Auto-redirect to pricing → GET /listen/study/{id}/pricing
   PricingAgent.present_quote() → quote computed from pricing.json
   Client adjusts levers → POST /api/client/quote/compute (live preview)
   Client confirms → POST /api/client/quote/{id}/confirm
   → project status: pricing

5. TimelineAgent.estimate() → phases computed
   → GET /listen/study/{id}/timeline → shows phases + payment button
   → project status: timeline_estimate

6. Client pays:
   Razorpay: POST /api/client/payment/initiate → Razorpay order created
             POST /api/client/payment/razorpay/verify → signature verified
   Stripe: POST /api/client/payment/initiate → Stripe session created
           Stripe webhook → payment confirmed
   → project status: awaiting_payment → panel_building (async)

7. PanelAgent recruits respondents
   → panels/{panel_id}.json created
   → respondents/{id}.json status: scheduled
   → project status: panel_approval

8. Client approves panel → POST /panel/api/{panel_id}/confirm
   → WhatsApp sent to each respondent
   → project status: interviewing

9. Respondents complete interviews
   → transcripts/{file}.json created after each
   → project.interviews_completed incremented

10. All interviews done → AnalysisAgent runs (4 passes)
    → reports/{id}.json created
    → project status: completed
    → Email sent to client with report link
```

---

## Security Considerations

| Risk | Mitigation |
|------|-----------|
| Credential exposure | `.env` never committed to git; `.gitignore` covers it |
| Password storage | SHA-256 hashing (upgrade to bcrypt in roadmap) |
| Session hijacking | `itsdangerous` signed cookies; `SECRET_KEY` rotation needed |
| API key leakage | All keys in env vars, not hardcoded |
| Payment fraud | HMAC-SHA256 signature verification on Razorpay webhooks |
| Sensitive respondent data | Stored in `sensitive` sub-object; never returned in list APIs |
| Admin access | Separate credentials; no overlap with client auth |

---

## Performance Characteristics

| Operation | Typical Latency |
|-----------|----------------|
| Voice STT (Google Cloud) | 300–800ms |
| Gemini Flash response | 500–1500ms |
| Voice TTS (Google Cloud) | 200–500ms |
| Full voice round-trip | ~1.5–3s |
| BriefAgent turn | ~1–2s |
| AnalysisAgent full report | ~15–30s |
| Quote compute | <100ms |
| File-based read | <10ms |

---

## Deployment Architecture (Current + Target)

### Current (Development)
```
Local machine → uvicorn → localhost:8000
```

### Target (Production)
```
getheard.space DNS → [TBD hosting]
  Options: Railway, Render, Google Cloud Run, DigitalOcean App Platform

  Requirements:
  - Python 3.11+ runtime
  - Persistent disk (for JSON files) OR migration to PostgreSQL
  - Environment variables injection
  - Custom domain SSL (getheard.space)
  - Webhook reachability (WhatsApp, Stripe, Razorpay)
```

See `BACKLOG_AND_ROADMAP.md` for deployment tasks.
