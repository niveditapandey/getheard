# GetHeard — Architecture Document

> **Audience:** New developers, product managers, and anyone taking over this project.  
> This document describes what the system is, how the pieces fit together, and where everything lives in code.

---

## Table of Contents

1. [What is GetHeard?](#1-what-is-getheard)
2. [High-Level Architecture](#2-high-level-architecture)
3. [The Three Portals](#3-the-three-portals)
4. [The AI Pipeline](#4-the-ai-pipeline)
5. [The Voice Interview System](#5-the-voice-interview-system)
6. [Data Storage](#6-data-storage)
7. [Authentication & Auth Model](#7-authentication--auth-model)
8. [External Services & Integrations](#8-external-services--integrations)
9. [Low-Level: File & Module Map](#9-low-level-file--module-map)
10. [Low-Level: Route Reference](#10-low-level-route-reference)
11. [Low-Level: Key Data Models](#11-low-level-key-data-models)
12. [Low-Level: Environment Variables](#12-low-level-environment-variables)
13. [How to Run Locally](#13-how-to-run-locally)
14. [Deployment](#14-deployment)
15. [Testing](#15-testing)

---

## 1. What is GetHeard?

GetHeard is an **AI-powered qualitative research platform** targeted at brands in Asian markets. It replaces traditional research agencies by automating the entire research pipeline end-to-end:

```
Brand commissions study → AI designs questions → Respondents do voice interviews → AI produces report
```

**Two sides:**
- **Brands (clients)** pay to commission research studies. They go through `/listen`.
- **Respondents** complete AI-led voice or WhatsApp interviews and earn rewards. They go through `/join`.
- **Admin (Nivedita)** manages everything through `/admin`.

**Key differentiators:**
- Interviews are conducted by an AI voice agent (not a human moderator)
- Supports 9+ languages including Indian languages (Hindi, Tamil, etc.) via Sarvam AI
- AI auto-generates the research questions from a plain-English brief
- AI produces the full analysis report (4-pass reasoning, not a one-shot summary)

---

## 2. High-Level Architecture

The entire platform is a **single Python process** — a FastAPI monolith with an embedded AI agent pipeline. There is no microservices split.

```
┌────────────────────────────────────────────────────────────────────┐
│                          INTERNET / USERS                           │
└──────────────┬─────────────────────┬──────────────────┬────────────┘
               │                     │                  │
        Clients (brands)       Respondents         Admin (Nivedita)
               │                     │                  │
               ▼                     ▼                  ▼
┌────────────────────────────────────────────────────────────────────┐
│                      FastAPI Web Application                        │
│                   (src/web/app.py — entry point)                    │
│                                                                     │
│  /listen/*        /join/*      /admin/*    /agent/*    /api/*       │
│  Client Portal    Respondent   Admin       Agentic     Voice &      │
│  app_client.py    app_panel    app_admin   app_        Report API   │
│  app_study.py     app_         app_study   agentic     app.py       │
│                   respondent                                        │
└──────────────┬───────────────────────────────────────────┬─────────┘
               │                                           │
               ▼                                           ▼
┌──────────────────────────┐               ┌───────────────────────────┐
│     AI Agent Pipeline     │               │     Voice Pipeline         │
│                           │               │                           │
│  Orchestrator             │               │  VoiceInterviewPipeline   │
│  ├─ BriefAgent            │               │  ├─ STT (speech → text)   │
│  ├─ DesignerAgent         │               │  ├─ GeminiInterviewer     │
│  ├─ PanelAgent            │               │  └─ TTS (text → speech)   │
│  ├─ PricingAgent          │               │                           │
│  ├─ TimelineAgent         │               │  Provider auto-routing:   │
│  ├─ InterviewAgent        │               │  Indian lang → Sarvam AI  │
│  └─ AnalysisAgent         │               │  Other lang → Google Cloud│
└──────────────┬────────────┘               └───────────────┬───────────┘
               │                                            │
               └──────────────────┬─────────────────────────┘
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│                         External AI APIs                            │
│                                                                     │
│   Google Gemini 2.5 Flash (real-time)    Gemini 2.5 Pro (analysis) │
│   Sarvam AI: stt-scribe + bulbul-v2 TTS  (Indian languages)        │
│   Google Cloud Speech-to-Text            Google Cloud TTS           │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                        External Services                            │
│                                                                     │
│   Razorpay (India payments)     Stripe (international payments)     │
│   Resend (email notifications)  Meta WhatsApp Business API          │
│   Twilio (WhatsApp fallback)    Google Cloud Firestore (database)   │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                      Google Cloud Firestore                         │
│                                                                     │
│   transcripts/   projects/   clients/   respondents/               │
│   panels/        reports/    redemptions/  points/                  │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. The Three Portals

### 3.1 Client Portal (`/listen`)

**Who uses it:** Brand managers, researchers at companies commissioning studies.

**The study commissioning flow (happy path):**

```
Step 1 → Sign up / log in at /listen/login
Step 2 → Start new study at /listen/study/new
         → Chat with BriefAgent (Alex, our AI consultant)
         → Brief is saved: project name, objective, audience, language, topics
Step 3 → Review + adjust pricing at /listen/study/{id}/pricing
         → PricingAgent computes itemised quote (study fee + recruitment + incentives)
         → Confirm quote
Step 4 → Review timeline at /listen/study/{id}/timeline
         → TimelineAgent estimates delivery phases
         → Pay via Razorpay (India) or Stripe (international)
Step 5 → Panel building (admin-driven)
         → Admin recruits respondents, client approves the panel
Step 6 → Interviewing
         → Respondents complete voice/WhatsApp interviews
Step 7 → Report delivered at /listen/study/{id}/status
         → Download as PDF or PPTX
```

**Key pages:**
| URL | Purpose |
|-----|---------|
| `/listen` | Dashboard — all studies, stats |
| `/listen/study/new` | Start a new study (brief chat) |
| `/listen/study/{id}/pricing` | Adjust and confirm quote |
| `/listen/study/{id}/timeline` | View phases + pay |
| `/listen/study/{id}/status` | Live study progress tracker |
| `/listen/reports` | All reports |

---

### 3.2 Respondent Portal (`/join`)

**Who uses it:** Panel members who complete interviews.

**The respondent flow:**
```
Enroll at /join/enroll → Screener (if enabled) → Interview invite via WhatsApp
→ Complete voice or WhatsApp interview → Earn points → Redeem at /join/rewards/{id}
```

**Key pages:**
| URL | Purpose |
|-----|---------|
| `/join` | Landing / signup |
| `/join/enroll` | Enrollment form (name, phone, demographics) |
| `/join/profile/{phone}` | Personal profile |
| `/join/rewards/{id}` | Points balance + redemption |
| `/screener/{project_id}` | Screener quiz before interview |

---

### 3.3 Admin Portal (`/admin`)

**Who uses it:** Nivedita (platform operator).

**What you can do:**
- Monitor all clients, studies, and respondents
- Manage the respondent panel (approve, reject, schedule)
- Review and approve panels before outreach starts
- Manage respondent payouts (points → cash)
- Edit pricing configuration live (no code change needed)
- View analytics across all studies

**Key pages:**
| URL | Purpose |
|-----|---------|
| `/admin` | Dashboard overview |
| `/admin/clients` | All client accounts |
| `/admin/studies` | All studies with pipeline status |
| `/admin/respondents` | Panel management |
| `/admin/pricing` | Edit pricing config live |
| `/admin/payouts` | Respondent redemption requests |
| `/admin/reports` | All generated reports |
| `/admin/pipeline` | Pipeline status across studies |

---

## 4. The AI Pipeline

### 4.1 The Agents

All agents extend `BaseAgent` in `src/agents/base_agent.py`. The base class implements a **Gemini function-calling loop**: it sends a message to Gemini along with tool definitions, Gemini calls a tool, the result is sent back, and this repeats until Gemini produces a final text response.

**The Orchestrator** (`src/agents/orchestrator.py`) is the central coordinator. It owns a module-level singleton instance and wires the agents together:

```
Orchestrator
  ├── Stage 1: BriefAgent      — collects brief via chat
  ├── Stage 2: DesignerAgent   — generates interview questions
  ├── Stage 3: InterviewAgent  — (per session, via VoiceInterviewPipeline)
  └── Stage 4: AnalysisAgent   — produces the report
```

---

### 4.2 Agent Responsibilities

| Agent | File | Input | Output | Model |
|-------|------|-------|--------|-------|
| BriefAgent | `brief_agent.py` | Chat messages from client | Structured brief dict | Flash |
| DesignerAgent | `designer_agent.py` | Brief dict | Interview questions list | Pro |
| PanelAgent | `panel_agent.py` | Project criteria or CSV | Panel JSON | Flash |
| PricingAgent | `pricing_agent.py` | Project params | Quote breakdown | Flash |
| TimelineAgent | `timeline_agent.py` | Project + urgency flag | Phase timeline | Flash |
| InterviewAgent | `interview_agent.py` | Questions, language | Conversation turns | Flash |
| AnalysisAgent | `analysis_agent.py` | Transcript files | Full report JSON | Pro |

---

### 4.3 AnalysisAgent — The 4-Pass Report

The report generation is the most sophisticated agent. It reasons in 4 passes:

```
Pass 1 — EXTRACT:     Analyse each transcript individually (themes, sentiment, quotes)
Pass 2 — SYNTHESIZE:  Find patterns across ALL transcripts (frequency, contradictions)
Pass 3 — WRITE:       Draft each section (exec summary, findings, pain points, recs)
Pass 4 — CRITIQUE:    Self-review — find gaps, patch weak claims, finalize
```

This mimics how a senior analyst actually works, rather than doing a one-shot summarisation.

---

### 4.4 Other AI Features

| Feature | Where | Description |
|---------|-------|-------------|
| Screener generation | `src/core/screener.py` | AI generates qualifying questions from brief |
| Quality scoring | `src/core/quality_scorer.py` | Scores each transcript 0–100, detects fraud |
| Mission Control | `src/core/mission_control.py` | Cross-study NL query ("What are customers saying about X across all studies?") |
| Research Agent | `src/core/research_agent.py` | Ask natural-language questions about a single report |
| Report export | `src/core/pptx_generator.py`, `pdf_generator.py` | Download reports as PPTX or PDF |

---

## 5. The Voice Interview System

Each browser interview session is managed by a `VoiceInterviewPipeline` instance (one per session, in-memory, keyed in the `sessions` dict in `app.py`).

**Session lifetime:** A background task (started at app startup) runs every 10 minutes and evicts sessions that have been idle for more than 45 minutes, auto-saving the transcript to Firestore before removal. Explicit `/api/end/{session_id}` calls also clean up immediately.

### How a voice turn works:

```
User speaks into browser microphone
  → Browser records audio (WebM format)
  → POST /api/respond  { session_id, audio (file) }
  → VoiceInterviewPipeline.process_audio(audio_bytes)
      → STT provider.transcribe()         # Speech → text
      → InterviewAgent.next_response()    # Text → next question (Gemini)
      → TTS provider.synthesize_speech()  # Text → audio (MP3)
  → Response: { transcript, response_audio_b64, is_complete }
  → Browser decodes base64 MP3 and plays it
  → Repeat until is_complete = True
  → Transcript auto-saved to Firestore
```

### Provider routing for languages:

| Language | STT Provider | TTS Provider |
|----------|-------------|-------------|
| Hindi (`hi`), Tamil, Telugu, etc. | Sarvam AI (stt-scribe) | Sarvam AI (bulbul-v2) |
| English, Indonesian, Filipino, Thai, Vietnamese, Korean, Japanese, Mandarin | Google Cloud Speech | Google Cloud TTS |

Override with `VOICE_PROVIDER=google_cloud` or `VOICE_PROVIDER=sarvam` in `.env`.

### WhatsApp interviews

Alternatively, interviews can run over WhatsApp. `src/web/whatsapp_handler.py` handles inbound messages from:
- **Twilio** (`POST /webhook/whatsapp`)
- **Meta WhatsApp Business API** (`POST /webhook/meta-whatsapp`)

The handler maps phone numbers to project IDs, maintains per-number conversation state, and returns TwiML or posts replies via the Meta Graph API.

---

## 6. Data Storage

**The database is Google Cloud Firestore.** There is also residual local JSON file storage for projects, reports, and panels (the Firestore migration was incremental).

### Firestore Collections

| Collection | Document Key | What it stores |
|-----------|-------------|---------------|
| `transcripts` | `session_id` | Full interview conversation, quality score |
| `projects` | `project_id` | Study brief, questions, pipeline status, sessions |
| `clients` | `client_id` | Client account, company, studies list |
| `respondents` | `respondent_id` | Profile, demographics, status, points |
| `panels` | `panel_id` | Panel composition for a project |
| `reports` | `report_id` | Generated analysis report |
| `redemptions` | `request_id` | Respondent payout requests |
| `points` | `respondent_id` | Points balance + transaction history |

### Local JSON (projects, reports, panels)

Some data still writes to local directories. This is the legacy path — new features use Firestore.

| Directory | Contents |
|-----------|----------|
| `projects/` | `{project_id}.json` — project data |
| `reports/` | `{report_id}.json` — report data |
| `panels/` | `{panel_id}.json` — panel data |
| `transcripts/` | Legacy local transcripts (now Firestore) |
| `clients/` | Legacy local client files (now Firestore) |
| `respondents/` | Legacy local respondent files (now Firestore) |

> **Important for new devs:** The `TranscriptManager` class writes to Firestore. The `ResearchProject` class reads/writes JSON files. This dual-persistence is technical debt — see the roadmap.

---

## 7. Authentication & Auth Model

There are three separate auth contexts:

| Portal | Mechanism | Session Key | How to log in |
|--------|----------|------------|--------------|
| Client | Cookie session (`itsdangerous`) | `client_id` | `/listen/login` (email + password) |
| Admin | Cookie session | `is_admin = True` | `/admin/login` (username + password) |
| Voice API | API key header | `X-API-Key` | Header on every request |

**Client auth detail:**
- Passwords hashed with SHA-256 (upgrade to bcrypt is in roadmap)
- Two tiers of client accounts:
  - **Simple/demo accounts** — stored in `.env` as `CLIENT_CREDENTIALS=user:pass`. `client_id` is `simple:{username}`. Linked studies are stored in the session cookie (not persisted).
  - **Firestore accounts** — full accounts created via `/listen/api/signup`. Stored in Firestore `clients` collection. Linked studies persist.

**Admin auth detail:**
- Credentials in `.env` as `ADMIN_CREDENTIALS=admin:password`
- No Firestore involved — just session cookie check

---

## 8. External Services & Integrations

| Service | Purpose | Env Variables |
|---------|---------|--------------|
| **Google Gemini** (via AI Studio) | All AI reasoning | `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_MODEL_PRO` |
| **Google Cloud Firestore** | Primary database | `GCP_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS` |
| **Google Cloud Speech** | STT for non-Indian languages | (uses same GCP credentials) |
| **Google Cloud TTS** | TTS for non-Indian languages | (uses same GCP credentials) |
| **Sarvam AI** | STT + TTS for Indian languages | `SARVAM_API_KEY` |
| **Meta WhatsApp Business** | WhatsApp interviews (inbound + outbound) | `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_VERIFY_TOKEN` |
| **Twilio** | WhatsApp fallback (sandbox) | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER` |
| **Razorpay** | Payments for India | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` |
| **Stripe** | International payments | `STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY` |
| **Resend** | Email notifications | `RESEND_API_KEY`, `RESEND_FROM_EMAIL` |

All are optional at startup — the app detects which services are configured and enables/disables features accordingly. Check `config/settings.py` for the `.has_*` properties.

---

## 9. Low-Level: File & Module Map

```
getHeard/
│
├── ARCHITECTURE.md               ← You are here
├── CLAUDE.md                     # Context for Claude Code (AI assistant)
├── .env                          # All secrets (never commit)
├── .gitignore
├── requirements.txt
├── run.sh                        # Local startup script
├── Dockerfile                    # Cloud Run / Docker deployment
├── Procfile                      # Railway deployment
│
├── config/
│   ├── settings.py               # Pydantic Settings — loads all env vars
│   └── pricing.json              # Admin-editable pricing tiers (edited via /admin/pricing)
│
├── src/
│   │
│   ├── agents/                   # AI Agent layer
│   │   ├── base_agent.py         # BaseAgent: Gemini function-calling loop + ToolSpec
│   │   ├── orchestrator.py       # Orchestrator: coordinates all 4 pipeline stages
│   │   ├── brief_agent.py        # BriefAgent: conversational brief intake (Alex persona)
│   │   ├── designer_agent.py     # DesignerAgent: generates + self-reviews questions
│   │   ├── interview_agent.py    # InterviewAgent: drives live interview conversation
│   │   ├── analysis_agent.py     # AnalysisAgent: 4-pass report generation
│   │   ├── panel_agent.py        # PanelAgent: builds respondent panels
│   │   ├── pricing_agent.py      # PricingAgent: computes study quote
│   │   └── timeline_agent.py     # TimelineAgent: estimates delivery timeline
│   │
│   ├── conversation/             # Lower-level LLM conversation wrappers
│   │   ├── gemini_engine.py      # GeminiInterviewer: manages conversation turns for voice
│   │   └── prompts.py            # System prompts per language and research type
│   │
│   ├── core/                     # Domain logic (not agent-specific)
│   │   ├── research_project.py   # ResearchProject model + create/get/list/update helpers
│   │   ├── report_generator.py   # One-shot Gemini report generation (legacy fallback)
│   │   ├── research_agent.py     # NL Q&A over a single report
│   │   ├── mission_control.py    # Cross-study NL Q&A + strategic overview
│   │   ├── quality_scorer.py     # Transcript quality scoring (0–100) + fraud detection
│   │   ├── screener.py           # AI-generate screener questions + evaluate answers
│   │   ├── pptx_generator.py     # Export report as branded PowerPoint (.pptx)
│   │   └── pdf_generator.py      # Export report as branded PDF
│   │
│   ├── voice/                    # Voice pipeline
│   │   ├── pipeline.py           # VoiceInterviewPipeline: routes STT → LLM → TTS
│   │   ├── google_cloud_stt.py   # GoogleCloudSTT wrapper
│   │   ├── google_cloud_tts.py   # GoogleCloudTTS wrapper
│   │   ├── sarvam_stt.py         # SarvamSTT wrapper (Indian languages)
│   │   └── sarvam_tts.py         # SarvamTTS wrapper (Indian languages)
│   │
│   ├── storage/                  # Persistence layer (Firestore + JSON)
│   │   ├── firestore_db.py       # Shared Firestore client (lazy-init singleton)
│   │   ├── transcript.py         # TranscriptManager → Firestore transcripts collection
│   │   ├── client_store.py       # Client CRUD → Firestore clients collection
│   │   ├── respondent_store.py   # Respondent CRUD → Firestore respondents collection
│   │   ├── points_store.py       # Points + redemptions → Firestore
│   │   └── pricing_store.py      # Pricing config + compute_quote() from config/pricing.json
│   │
│   ├── notifications/
│   │   └── notifier.py           # send_email() via Resend, send_whatsapp() via Meta API
│   │
│   └── web/                      # FastAPI routers + templates
│       ├── app.py                # Main app: router assembly, voice API, reports, WhatsApp
│       ├── app_agentic.py        # /agent/* — brief chat, design, agentic reports
│       ├── app_client.py         # /listen/* — client auth, dashboard, study linking
│       ├── app_study.py          # /listen/study/* — lifecycle, payment, timeline
│       ├── app_admin.py          # /admin/* — admin dashboard, pricing, clients
│       ├── app_panel.py          # /enroll, /panel/* — respondent enrollment + panel build
│       ├── app_respondent.py     # /join/* — rewards, points, redemptions
│       ├── whatsapp_handler.py   # WhatsApp text interview state machine
│       │
│       ├── static/
│       │   └── design_system.css # CSS design tokens (navy palette, components)
│       │
│       └── templates/            # Jinja2 HTML templates (rendered server-side)
│           ├── landing.html      # Public landing page
│           ├── client_login.html / client_signup.html / client_dashboard.html
│           ├── study_new.html    # New study — brief chat UI
│           ├── study_pricing.html
│           ├── study_timeline.html
│           ├── study_status.html # Live study tracker
│           ├── client_reports.html
│           ├── admin_login.html / admin_dashboard.html / admin_pricing.html
│           ├── admin_clients.html / admin_studies.html / admin_respondents.html
│           ├── admin_payouts.html / admin_reports.html / admin_pipeline.html
│           ├── enroll.html       # Respondent enrollment form
│           ├── respondent_home.html / respondent_profile.html / respondent_rewards.html
│           ├── screener.html     # Respondent screening quiz
│           ├── report.html       # Report viewer (with PPTX/PDF export)
│           ├── mission_control.html
│           └── agent/
│               ├── index.html    # Agentic pipeline dashboard
│               └── brief_chat.html
│
├── tests/
│   └── test_suite.py             # Full test suite — 115 tests (unit + functional)
│
├── projects/                     # Project JSON files (local, being migrated to Firestore)
├── reports/                      # Report JSON files (local)
├── panels/                       # Panel JSON files (local)
├── transcripts/                  # Legacy local transcripts (now Firestore)
├── respondents/                  # Legacy local respondent data (now Firestore)
├── clients/                      # Legacy local client data (now Firestore)
└── documentation/                # Additional docs (API reference, user guides, etc.)
```

---

## 10. Low-Level: Route Reference

### Voice API (app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/start` | API Key (optional) | Start interview session; returns greeting audio |
| POST | `/api/respond` | API Key (optional) | Process audio turn; returns response audio |
| POST | `/api/end/{session_id}` | — | Force-save transcript and close session |
| GET | `/api/transcript/{session_id}` | — | Live conversation history |
| GET | `/api/transcript-file/{filename}` | — | Load saved transcript |
| GET | `/api/transcripts` | — | List all transcripts |
| GET | `/api/stats` | — | Aggregate dashboard stats |

### Projects & Reports (app.py)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/projects/generate-questions` | AI question preview (no save) |
| POST | `/api/projects` | Create and save project (validates research_type, language, question_count 1–30) |
| GET | `/api/projects` | List all projects |
| GET | `/api/projects/{id}` | Get project JSON |
| PATCH | `/api/projects/{id}/questions` | Update questions |
| PATCH | `/api/projects/{id}/branding` | Update brand_name, brand_color, logo_url |
| GET | `/api/projects/{id}/status` | Live project stats (session counts, quality) |
| POST | `/api/projects/{id}/score-all` | Score all transcripts for fraud/quality |
| GET | `/api/projects/{id}/screener` | Get screener config |
| PATCH | `/api/projects/{id}/screener` | Save screener config |
| POST | `/api/projects/{id}/screener/generate` | AI-generate screener questions |
| POST | `/api/sessions/{session_id}/score` | Score one transcript |
| POST | `/api/reports/generate` | Generate report from transcripts |
| POST | `/api/reports/generate-multi` | Cross-project report |
| GET | `/api/reports` | List reports |
| GET | `/api/reports/{id}` | Get report JSON |
| POST | `/api/reports/{id}/query` | NL query against report (Research Agent) |
| GET | `/api/reports/{id}/export/pptx` | Download report as PowerPoint |
| GET | `/api/reports/{id}/export/pdf` | Download report as PDF |

### WhatsApp (app.py)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhook/whatsapp` | Twilio inbound webhook |
| GET | `/webhook/meta-whatsapp` | Meta webhook verification |
| POST | `/webhook/meta-whatsapp` | Meta inbound messages |
| POST | `/api/whatsapp/send` | Send proactive message via Twilio |
| GET | `/api/whatsapp/stats` | Active WhatsApp session count |

### Mission Control (app.py)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/mission-control` | Mission Control UI |
| GET | `/api/mission-control/overview` | AI strategic overview across all studies |
| POST | `/api/mission-control/query` | NL query across all reports + transcripts |

### Screener (app.py)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/screener/{project_id}` | Respondent screener page |
| POST | `/api/screener/{project_id}/submit` | Evaluate screener answers |

### Client Portal (app_client.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/listen/login` | — | Login page |
| POST | `/listen/login` | — | Authenticate |
| GET | `/listen/logout` | Session | Clear session |
| GET | `/listen` | Session | Client dashboard |
| GET | `/listen/signup` | — | Signup page |
| POST | `/listen/api/signup` | — | Create account |
| GET | `/api/client/projects` | Session | Client's projects |
| GET | `/api/client/stats` | Session | Client stats |
| GET | `/api/client/reports` | Session | Client's reports |
| POST | `/api/client/studies/{id}/link` | Session | Link project to client account |
| GET | `/api/client/quote/{id}` | Session | Get project quote |
| POST | `/api/client/quote/{id}/confirm` | Session | Confirm quote, advance pipeline |

### Study Lifecycle (app_study.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/listen/study/new` | Session | New study page |
| GET | `/listen/study/{id}/pricing` | Session | Pricing page |
| GET | `/listen/study/{id}/timeline` | Session | Timeline + payment |
| GET | `/listen/study/{id}/status` | Session | Live status page |
| GET | `/api/client/study/{id}/status` | Session | Status JSON (polled every 10s) |
| GET | `/api/client/study/{id}/report-link` | Session | Shareable report URL |
| GET | `/api/client/timeline/{id}` | Session | Timeline JSON |
| POST | `/api/client/quote/compute` | — | Live quote compute |
| POST | `/api/client/payment/initiate` | Session | Create Razorpay or Stripe order |
| POST | `/api/client/payment/razorpay/verify` | — | Verify Razorpay HMAC signature |

### Admin Portal (app_admin.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/admin/login` | — | Login page |
| POST | `/admin/login` | — | Authenticate |
| GET | `/admin/logout` | Admin | Clear session |
| GET | `/admin` | Admin | Dashboard |
| GET | `/admin/clients` | Admin | Client list |
| GET | `/admin/studies` | Admin | All studies |
| GET | `/admin/respondents` | Admin | Respondent panel |
| GET | `/admin/pricing` | Admin | Pricing editor |
| GET | `/admin/payouts` | Admin | Payout requests |
| GET | `/admin/reports` | Admin | All reports |
| GET | `/admin/pipeline` | Admin | Pipeline status |
| GET | `/api/admin/stats` | Admin | Platform-wide stats |
| GET | `/api/admin/pricing` | Admin | Pricing config JSON |
| POST | `/api/admin/pricing` | Admin | Update pricing config |
| GET | `/api/admin/clients` | Admin | All clients list |
| GET | `/api/admin/studies` | Admin | All studies list |
| GET | `/api/admin/redemptions` | Admin | All redemption requests |
| PATCH | `/api/admin/redemptions/{id}` | Admin | Update redemption status |

### Panel & Respondent (app_panel.py + app_respondent.py)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/enroll` | Public respondent enrollment page |
| POST | `/api/respondents/enroll` | Enroll respondent |
| GET | `/api/respondents` | List respondents (filterable) |
| GET | `/api/respondents/stats` | Aggregate panel counts |
| GET | `/api/respondents/{id}` | Get respondent |
| PATCH | `/api/respondents/{id}/status` | Update status |
| POST | `/panel/api/csv-upload` | Build panel from uploaded CSV |
| POST | `/panel/api/query` | Build panel from DB query |
| GET | `/panel/api/{project_id}` | Get panel for project |
| POST | `/panel/api/{panel_id}/confirm` | Confirm panel (triggers respondent outreach) |
| GET | `/join/profile/{phone}` | Respondent profile page |
| GET | `/join/rewards/{id}` | Rewards dashboard |
| GET | `/api/respondents/{id}/points` | Points balance + history |
| POST | `/api/respondents/{id}/points/add` | Add points (admin only) |
| POST | `/api/respondents/{id}/redeem` | Submit redemption request |
| GET | `/api/respondents/{id}/redemptions` | Redemption history |
| GET | `/api/points/rates` | Exchange rates by country |

### Agentic Pipeline (app_agentic.py)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/agent` | Agentic home page |
| GET | `/agent/brief` | Brief chat UI |
| POST | `/agent/api/brief/start` | Create BriefAgent session |
| POST | `/agent/api/brief/message` | Send message, get reply |
| GET | `/agent/api/brief/{id}` | Get session state |
| POST | `/agent/api/design` | Run DesignerAgent on a brief |
| GET | `/agent/api/projects` | List projects |
| GET | `/agent/api/projects/{id}` | Get project (includes questions[]) |
| POST | `/agent/api/reports/generate` | Run AnalysisAgent |
| GET | `/agent/api/reports` | List reports |
| GET | `/agent/api/reports/{id}` | Get full report JSON |

---

## 11. Low-Level: Key Data Models

### Project JSON (stored in Firestore `projects` + local `projects/`)

```json
{
  "project_id":    "abc12345",
  "name":          "HDFC Credit Card CX Study",
  "research_type": "cx",
  "industry":      "Banking / Finance",
  "objective":     "Why do customers churn within 90 days?",
  "audience":      "Active credit card holders, 25-40, metro cities",
  "language":      "en",
  "topics":        ["onboarding", "rewards", "app experience", "support"],
  "question_count": 10,
  "questions": [
    {
      "id": "q1",
      "text": "Walk me through when you first got your card — what happened?",
      "type": "open",
      "order": 1
    }
  ],
  "sessions":      ["sess_abc123", "sess_def456"],
  "status":        "interviewing",
  "pipeline": {
    "briefing":          { "status": "completed", "completed_at": "2026-06-15T10:00:00Z" },
    "pricing":           { "status": "completed", "completed_at": "2026-06-15T11:00:00Z" },
    "timeline_estimate": { "status": "completed" },
    "payment":           { "status": "completed" },
    "panel_building":    { "status": "in_progress" },
    "panel_approval":    { "status": "pending" },
    "interviewing":      { "status": "pending" },
    "analysis":          { "status": "pending" },
    "report":            { "status": "pending" }
  },
  "quote":         { "total": 45000, "currency": "INR", ... },
  "quote_params":  { "panel_size": 20, "market": "IN", ... },
  "target_respondents": 20,
  "report_id":     null,
  "created_at":    "2026-06-15T10:00:00Z",
  "created_by":    "BriefAgent"
}
```

### Transcript JSON (stored in Firestore `transcripts`)

```json
{
  "session_id":    "sess_abc123",
  "language_code": "en",
  "project_id":    "abc12345",
  "started_at":    "2026-06-15T14:00:00Z",
  "ended_at":      "2026-06-15T14:22:00Z",
  "saved_at":      "2026-06-15T14:22:01Z",
  "turn_count":    12,
  "quality_score": 84,
  "quality_label": "high_quality",
  "quality_flags": [],
  "conversation": [
    { "speaker": "interviewer", "text": "Hi! Tell me about your experience..." },
    { "speaker": "respondent",  "text": "I've been using the card for 3 months..." }
  ],
  "metadata": {
    "project_id":    "abc12345",
    "stt_provider":  "google",
    "tts_provider":  "google",
    "engine":        "InterviewAgent"
  }
}
```

> **Note:** `project_id` is stored at the top level (not only in `metadata`) to enable efficient Firestore queries by project. Use `TranscriptManager.load_summaries(session_ids)` to load only the transcripts you need — it takes a list of session IDs and does targeted reads, avoiding a full collection scan.

### Respondent JSON (Firestore `respondents`)

```json
{
  "respondent_id": "resp_xyz789",
  "name":          "Priya S",
  "phone":         "+919876543210",
  "country":       "IN",
  "language":      "hi",
  "status":        "available",
  "demographics":  { "age_range": "25-34", "city": "Mumbai", "gender": "Female" },
  "points":        350,
  "enrolled_at":   "2026-05-01T09:00:00Z"
}
```

### Pricing config (`config/pricing.json`)

```json
{
  "base_fee": {
    "nps_csat":         15000,
    "feature_feedback": 20000,
    "pain_points":      25000,
    "custom":           30000
  },
  "panel_source_multiplier": {
    "csv": 1.0,
    "db":  1.2,
    "targeted": 1.5
  },
  "size_tiers": [
    { "max": 10,  "multiplier": 1.0 },
    { "max": 25,  "multiplier": 1.3 },
    { "max": 50,  "multiplier": 1.6 },
    { "max": 100, "multiplier": 2.0 }
  ],
  "urgency_fee_pct": 0.2,
  "incentive_markup_pct": 0.15
}
```

---

## 12. Low-Level: Environment Variables

Copy `.env.example` to `.env` and fill in the values. Required fields must be set before the app will function.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GCP_PROJECT_ID` | Yes | `getheard-484014` | Google Cloud project ID |
| `GEMINI_API_KEY` | Yes | — | Google AI Studio API key (get free at aistudio.google.com) |
| `GEMINI_MODEL` | No | `gemini-2.5-flash` | Model for voice/chat (fast, low latency) |
| `GEMINI_MODEL_PRO` | No | `gemini-2.5-pro` | Model for design + analysis (deeper reasoning) |
| `GCP_LOCATION` | No | `us-central1` | Vertex AI region |
| `GOOGLE_APPLICATION_CREDENTIALS` | Yes* | — | Path to GCP service account JSON |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | Yes* | — | Inline JSON (alternative to file, for Railway/Cloud Run) |
| `SARVAM_API_KEY` | No | — | Sarvam AI key (enables Indian language STT/TTS) |
| `VOICE_PROVIDER` | No | `google_cloud` | `google_cloud` / `sarvam` / `auto` |
| `SECRET_KEY` | Yes | — | Signs session cookies (change in production!) |
| `CLIENT_CREDENTIALS` | No | `demo:demo123` | Simple client logins: `user1:pass1,user2:pass2` |
| `ADMIN_CREDENTIALS` | No | `admin:getheard-admin-2026` | Admin login: `user:pass` |
| `API_KEY` | No | `getheard-dev-key-2026` | Voice API authentication key |
| `RAZORPAY_KEY_ID` | No | — | Razorpay public key |
| `RAZORPAY_KEY_SECRET` | No | — | Razorpay secret key |
| `STRIPE_PUBLISHABLE_KEY` | No | — | Stripe public key |
| `STRIPE_SECRET_KEY` | No | — | Stripe secret key |
| `RESEND_API_KEY` | No | — | Resend email API key |
| `RESEND_FROM_EMAIL` | No | `hello@getheard.space` | Sender email |
| `WHATSAPP_PHONE_NUMBER_ID` | No | — | Meta WhatsApp phone number ID |
| `WHATSAPP_BUSINESS_ID` | No | — | Meta WhatsApp Business account ID |
| `WHATSAPP_ACCESS_TOKEN` | No | — | Meta WhatsApp access token |
| `WHATSAPP_VERIFY_TOKEN` | No | `getheard-verify-2026` | Meta webhook verify token |
| `TWILIO_ACCOUNT_SID` | No | — | Twilio Account SID (WhatsApp sandbox) |
| `TWILIO_AUTH_TOKEN` | No | — | Twilio Auth Token |
| `TWILIO_WHATSAPP_NUMBER` | No | `whatsapp:+14155238886` | Twilio sandbox number |
| `INTERVIEW_LANGUAGE` | No | `en,id,fil,th,vi,ko,ja,zh,hi` | Supported languages |
| `INDIAN_LANGUAGES` | No | `hi,en-IN,ta,te,ml,...` | Languages routed to Sarvam |
| `MAX_INTERVIEW_DURATION` | No | `600` | Max seconds per interview |
| `HOST` | No | `0.0.0.0` | Server bind host |
| `PORT` | No | `8000` | Server port |

*Either `GOOGLE_APPLICATION_CREDENTIALS` (file path) or `GOOGLE_APPLICATION_CREDENTIALS_JSON` (inline JSON) is required for Firestore and Google Cloud Speech/TTS.

---

## 13. How to Run Locally

```bash
# 1. Clone and set up venv
git clone https://github.com/niveditapandey/getheard.git
cd getHeard
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up credentials
cp .env.example .env
# Edit .env — at minimum set GEMINI_API_KEY and GCP credentials

# 4. Run
./run.sh
# Or directly:
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload
```

The app starts at `http://localhost:8000`. Key URLs to verify:
- `/health` — health check (shows configured providers)
- `/listen/login` — client portal
- `/admin/login` — admin (credentials from `ADMIN_CREDENTIALS` in `.env`)
- `/join` — respondent portal

---

## 14. Deployment

### Current Deployment Target

The app is containerised with Docker for deployment to Google Cloud Run or Railway.

```dockerfile
# Dockerfile at project root
# Python 3.11, installs requirements, runs uvicorn
```

### Environment Setup on Cloud Platforms

**Railway:**
- Set all env vars in the Railway dashboard
- Use `GOOGLE_APPLICATION_CREDENTIALS_JSON` (paste entire JSON as one env var value)
- `railway.toml` is pre-configured

**Google Cloud Run:**
- `Dockerfile` is pre-configured
- Set env vars in Cloud Run service configuration
- Mount GCP service account credentials (or use Workload Identity)

### Performance Characteristics

| Operation | Typical Latency |
|-----------|----------------|
| Voice STT (Google Cloud) | 300–800ms |
| Gemini Flash response | 500–1500ms |
| Voice TTS (Google Cloud) | 200–500ms |
| Full voice round-trip | 1.5–3s total |
| BriefAgent turn | 1–2s |
| DesignerAgent (question design) | 5–15s |
| AnalysisAgent (full 4-pass report) | 20–60s |
| Quote compute | <100ms |
| Firestore read | 10–50ms |

### Known Limitations & Technical Debt

| Issue | Impact | Status |
|-------|--------|--------|
| Dual storage (JSON files + Firestore) | Data inconsistency risk | Open — migrate project/panel/report writes to Firestore |
| SHA-256 password hashing | Weak for production | Open — upgrade to bcrypt |
| In-memory voice sessions (`sessions: Dict`) lost on restart | Sessions drop if process restarts | Partially mitigated — 45-min TTL auto-saves and evicts idle sessions |
| `config/pricing.json` on local disk | Lost on redeploy without persistent volume | Open — move to Firestore |
| No rate limiting | API abuse risk | Open — add slowapi middleware |
| Simple/demo users in session only | Studies lost when session cookie expires | Open — require Firestore account for production |
| Screener quota race condition (read-modify-write) | Two simultaneous submits could both qualify | Partially mitigated — re-reads count immediately before write; full fix requires Firestore transactions |

---

## 15. Testing

The test suite lives in `tests/test_suite.py` and covers 115 tests across two categories.

### Running tests

```bash
# Against local server (start server first)
source venv/bin/activate
python -m uvicorn src.web.app:app --port 8000

# In another terminal:
pytest tests/test_suite.py -v

# Against production
TEST_BASE_URL=https://getheard-151428781052.asia-south1.run.app pytest tests/test_suite.py -v

# Run a single class
pytest tests/test_suite.py::TestVoiceAPI -v
```

### Unit tests (no server required)

These test Python modules directly — no HTTP involved.

| Class | What it covers |
|-------|---------------|
| `TestSettings` | Env var loading, language routing, Sarvam detection |
| `TestPricingStore` | `compute_quote()` — urgency multiplier, panel size tiers, incentive markup |
| `TestQualityScorer` | 0–100 scoring, label thresholds, fraud detection rules |
| `TestPrompts` | Multi-language greeting/question/closing strings |
| `TestResearchProject` | `create_project()` with live Gemini, `update_questions()`, persistence |
| `TestGeminiInterviewer` | State machine (not_started → greeting → questioning → completed), history |
| `TestVoicePipeline` | Pipeline init, provider routing (Hindi → Sarvam), provider info |

### Functional tests (require running server)

These make real HTTP calls to `http://localhost:8000` (or `TEST_BASE_URL`).

| Class | What it covers |
|-------|---------------|
| `TestHealthAndPublicPages` | `/health`, landing page, join/enroll, agent, mission control |
| `TestAuthRedirects` | Unauthenticated redirects, login success/failure for both client + admin |
| `TestVoiceAPI` | Full STT→LLM→TTS round-trip: start, respond (with WAV), transcript, end |
| `TestProjectsAPI` | CRUD, question update, project status, screener, branding; validation rejects invalid research_type/language/count |
| `TestReportsAPI` | List, 404, PPTX/PDF export |
| `TestPricingAPI` | Quote compute, urgency multiplier |
| `TestClientPortal` | Dashboard, study pages, status API, study linking |
| `TestAdminPortal` | All admin pages, stats API, pricing API, redemptions |
| `TestRespondentPanel` | Enrollment (valid + missing consent + missing field), stats, points rates |
| `TestAgenticPipeline` | Brief session start/message/state, project list |
| `TestMissionControl` | Overview, starter queries, NL query, empty query rejection |
| `TestWhatsApp` | Stats, Meta webhook token rejection, phone registration |

### What is NOT tested

- Payment flows (Razorpay/Stripe require real card or sandbox setup)
- WhatsApp inbound message handling (requires webhook tunnel)
- AI report generation end-to-end (covered by production smoke tests instead)
- Admin write operations (pricing update, redemption status) — read paths are covered

---

*Last updated: June 2026*
