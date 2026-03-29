# GetHeard — Voice Research Platform

> **"Voice has Value."**
> Commission real market research — briefing to report, fully automated. Powered by AI agents across Asia.

---

## What Is GetHeard?

GetHeard is a two-sided AI-powered market research platform that connects **brands (clients)** who need consumer insights with **respondents** across Asia who share their opinions via voice interview.

- Clients commission research studies through a self-serve portal
- AI agents handle briefing, question design, panel recruitment, interviews, and report generation
- Respondents participate via browser voice or WhatsApp and earn points redeemable for cash or gift cards

**Live domain:** https://getheard.space

---

## Three Portals, One Platform

| Portal | URL | Who Uses It |
|--------|-----|-------------|
| Client Portal | `/listen` | Brands commissioning research |
| Respondent Portal | `/join` | People participating in interviews |
| Admin Dashboard | `/admin` | GetHeard team (Nivedita) |

---

## Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- Google Cloud account with Vertex AI or Gemini API key
- (Optional) Sarvam AI key for Indian languages

### 1. Clone & Install
```bash
git clone <repo>
cd getHeard
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install razorpay stripe httpx itsdangerous resend
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your credentials (see DEVELOPER_GUIDE.md)
```

Minimum required:
```env
GCP_PROJECT_ID=your-gcp-project
GEMINI_API_KEY=AIza...          # Free from aistudio.google.com
SECRET_KEY=any-random-string
```

### 3. Run the Server
```bash
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload
```

Or use the launch config in `.claude/launch.json` if using Claude Code.

### 4. Open in Browser
| Page | URL |
|------|-----|
| Landing | http://localhost:8000 |
| Client Login | http://localhost:8000/listen/login |
| Admin Login | http://localhost:8000/admin/login |
| Respondent Enroll | http://localhost:8000/join |
| Voice Interview (legacy) | http://localhost:8000/interview |
| Agent Dashboard | http://localhost:8000/agent |

**Default credentials:**
- Client: `demo` / `demo123`
- Admin: `admin` / `getheard-admin-2026`

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python) |
| AI / LLM | Google Gemini 2.5 Flash + Pro (via google-genai SDK) |
| Voice STT | Google Cloud Speech-to-Text + Sarvam AI (Indian langs) |
| Voice TTS | Google Cloud Text-to-Speech + Sarvam AI (Indian langs) |
| Frontend | Vanilla HTML/CSS/JS (no framework) — Jinja2 templates |
| Storage | JSON files (file-based, no database) |
| Payments | Razorpay (India/SEA) + Stripe (international) |
| Email | Resend (hello@getheard.space) |
| WhatsApp | Meta Business API + Twilio fallback |
| Auth | Starlette SessionMiddleware + itsdangerous |
| Hosting | (TBD — see BACKLOG_AND_ROADMAP.md) |

---

## Project Structure Overview

```
getHeard/
├── config/             # Settings + pricing config
├── src/
│   ├── agents/         # AI agents (Brief, Designer, Panel, Interview, Analysis, Pricing, Timeline)
│   ├── conversation/   # Gemini interview engine + prompts
│   ├── core/           # ResearchProject model + report generator
│   ├── voice/          # STT + TTS providers (Google Cloud + Sarvam)
│   ├── storage/        # File-based data stores
│   ├── notifications/  # Email (Resend) + WhatsApp (Meta) notifier
│   └── web/            # FastAPI app + 6 routers + 22 HTML templates
├── projects/           # Research project JSON files
├── transcripts/        # Interview transcript JSON files
├── reports/            # Generated report JSON files
├── respondents/        # Respondent panel database
├── clients/            # Client account database
├── redemptions/        # Payout request records
├── panels/             # Panel assignment records
└── documentation/      # ← You are here
```

---

## Key Documents in This Folder

| Document | What It Covers |
|----------|---------------|
| [PROJECT_SCOPE.md](PROJECT_SCOPE.md) | Vision, goals, target users, business model |
| [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) | Full PRD — features, user stories, acceptance criteria |
| [ARCHITECTURE_HIGH_LEVEL.md](ARCHITECTURE_HIGH_LEVEL.md) | System diagram, components, data flow |
| [ARCHITECTURE_LOW_LEVEL.md](ARCHITECTURE_LOW_LEVEL.md) | File structure, routes, classes |
| [AGENTIC_FLOWS.md](AGENTIC_FLOWS.md) | How AI agents work, pipeline diagrams |
| [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) | Setup, env vars, running locally, adding features |
| [API_REFERENCE.md](API_REFERENCE.md) | All API endpoints with request/response examples |
| [DATA_MODELS.md](DATA_MODELS.md) | JSON schemas for all data types |
| [PRICING_SYSTEM.md](PRICING_SYSTEM.md) | Pricing formula, admin config, compute logic |
| [INTEGRATIONS.md](INTEGRATIONS.md) | Razorpay, Stripe, Resend, WhatsApp, Twilio setup |
| [BACKLOG_AND_ROADMAP.md](BACKLOG_AND_ROADMAP.md) | Done, in-progress, todo, future roadmap |

---

## Supported Languages

| Code | Language | Voice Provider |
|------|----------|---------------|
| `en` | English | Google Cloud |
| `hi` | Hindi | Sarvam AI (preferred) |
| `id` | Indonesian | Google Cloud |
| `fil` | Filipino | Google Cloud |
| `th` | Thai | Google Cloud |
| `vi` | Vietnamese | Google Cloud |
| `zh` | Mandarin Chinese | Google Cloud |
| `ko` | Korean | Google Cloud |
| `ja` | Japanese | Google Cloud |
| `ta` | Tamil | Sarvam AI |
| `te` | Telugu | Sarvam AI |

---

## Contact / Owner

**Nivedita Pandey** — np@dendrons.ai
Platform: [getheard.space](https://getheard.space)
