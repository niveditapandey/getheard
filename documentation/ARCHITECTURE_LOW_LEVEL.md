# Low-Level Architecture — GetHeard

## Complete File & Module Reference

---

## Directory Tree

```
getHeard/
│
├── .env                          # All secrets and config (never commit)
├── .gitignore
├── requirements.txt
├── run.sh                        # Startup script
│
├── config/
│   ├── settings.py               # Pydantic Settings class (env var loader)
│   └── pricing.json              # Admin-editable pricing configuration
│
├── src/
│   ├── agents/
│   │   ├── base_agent.py         # BaseAgent + ToolSpec + AgentResult
│   │   ├── orchestrator.py       # Orchestrator (coordinates pipeline)
│   │   ├── brief_agent.py        # BriefAgent (conversational brief intake)
│   │   ├── designer_agent.py     # DesignerAgent (question generation)
│   │   ├── panel_agent.py        # PanelAgent (panel recruitment)
│   │   ├── interview_agent.py    # InterviewAgent (live interview logic)
│   │   ├── analysis_agent.py     # AnalysisAgent (4-pass report gen)
│   │   ├── pricing_agent.py      # PricingAgent (dynamic quote)
│   │   └── timeline_agent.py     # TimelineAgent (delivery estimate)
│   │
│   ├── conversation/
│   │   ├── gemini_engine.py      # GeminiInterviewer (LLM conversation)
│   │   └── prompts.py            # System prompts per language/type
│   │
│   ├── core/
│   │   ├── research_project.py   # ResearchProject model + CRUD helpers
│   │   └── report_generator.py   # Gemini-powered report analysis
│   │
│   ├── voice/
│   │   ├── pipeline.py           # VoiceInterviewPipeline (orchestrates STT→LLM→TTS)
│   │   ├── google_cloud_stt.py   # GoogleCloudSTT
│   │   ├── google_cloud_tts.py   # GoogleCloudTTS
│   │   ├── sarvam_stt.py         # SarvamSTT
│   │   └── sarvam_tts.py         # SarvamTTS
│   │
│   ├── storage/
│   │   ├── transcript.py         # TranscriptManager (save/load/list)
│   │   ├── respondent_store.py   # Respondent CRUD
│   │   ├── client_store.py       # Client account CRUD
│   │   ├── points_store.py       # Points + redemptions
│   │   └── pricing_store.py      # Pricing config + compute_quote()
│   │
│   ├── notifications/
│   │   ├── __init__.py
│   │   └── notifier.py           # send_email() + send_whatsapp()
│   │
│   └── web/
│       ├── app.py                # Main FastAPI app (entry point)
│       ├── app_agentic.py        # /agent/* router
│       ├── app_client.py         # /listen/* router
│       ├── app_admin.py          # /admin/* router
│       ├── app_panel.py          # /enroll, /panel/* router
│       ├── app_study.py          # /listen/study/*, payment router
│       ├── app_respondent.py     # /join/* router
│       ├── whatsapp_handler.py   # WhatsApp text interview handler
│       │
│       ├── static/
│       │   └── design_system.css # Global CSS design tokens + components
│       │
│       └── templates/
│           ├── landing.html
│           ├── index.html           # Voice interview UI (legacy)
│           ├── dashboard.html       # Analytics dashboard
│           ├── projects.html
│           ├── new_project.html
│           ├── project_detail.html
│           ├── report.html
│           ├── client_login.html
│           ├── client_signup.html
│           ├── client_dashboard.html
│           ├── study_new.html
│           ├── study_pricing.html
│           ├── study_timeline.html
│           ├── study_status.html
│           ├── admin_login.html
│           ├── admin_dashboard.html
│           ├── admin_pricing.html
│           ├── enroll.html          # Respondent enrollment (multilingual)
│           ├── respondent_home.html
│           ├── respondent_profile.html
│           ├── respondent_rewards.html
│           └── agent/
│               ├── index.html
│               └── brief_chat.html
│
├── projects/                    # Project JSON files
├── transcripts/                 # Interview transcript JSON files
├── reports/                     # Report JSON files
├── respondents/                 # Respondent JSON files
├── clients/                     # Client JSON files
├── panels/                      # Panel JSON files
├── redemptions/                 # Redemption request JSON files
│
└── documentation/               # ← All docs live here
```

---

## Route Map (All Endpoints)

### Public Routes

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/` | `app.py` | Landing page |
| GET | `/health` | `app.py` | Health check + config info |
| GET | `/interview` | `app.py` | Legacy voice interview UI |
| GET | `/dashboard` | `app.py` | Analytics dashboard |
| GET | `/projects` | `app.py` | Projects list |
| GET | `/projects/new` | `app.py` | New project form |
| GET | `/projects/{id}` | `app.py` | Project detail |
| GET | `/report/{id}` | `app.py` | Report viewer |
| GET | `/join` | `app.py` | Respondent home |
| GET | `/join/enroll` | `app.py` | Respondent enroll form |

### Voice API

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/start` | API Key | Start interview session, get greeting audio |
| POST | `/api/respond` | API Key | Process audio, return response audio |
| POST | `/api/end/{session_id}` | API Key | Force-save transcript |
| GET | `/api/transcript/{session_id}` | API Key | Live conversation history |
| GET | `/api/transcript-file/{filename}` | — | Load saved transcript |
| GET | `/api/transcripts` | — | List all transcripts |
| GET | `/api/stats` | — | Dashboard stats |

### Projects & Reports API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/projects/generate-questions` | AI question preview (no save) |
| POST | `/api/projects` | Create and save project |
| GET | `/api/projects` | List all projects |
| GET | `/api/projects/{id}` | Get project |
| PATCH | `/api/projects/{id}/questions` | Update questions |
| POST | `/api/reports/generate` | Generate report from transcripts |
| GET | `/api/reports` | List reports |
| GET | `/api/reports/{id}` | Get report |

### WhatsApp

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhook/whatsapp` | Twilio inbound webhook |
| POST | `/api/whatsapp/send` | Send proactive message |
| GET | `/api/whatsapp/stats` | Active session count |

### Client Portal (`app_client.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/listen/login` | — | Login page |
| POST | `/listen/login` | — | Authenticate client |
| GET | `/listen/logout` | Session | Clear session |
| GET | `/listen` | Session | Redirect to dashboard |
| GET | `/listen/signup` | — | Signup page |
| POST | `/listen/api/signup` | — | Create client account |
| GET | `/api/client/projects` | Session | Client's projects |
| GET | `/api/client/stats` | Session | Client stats |
| GET | `/api/client/quote/{id}` | Session | Get project quote |
| POST | `/api/client/quote/{id}/confirm` | Session | Confirm quote, advance pipeline |

### Study Lifecycle (`app_study.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/listen/study/new` | Session | New study page |
| GET | `/listen/study/{id}/pricing` | Session | Pricing page |
| GET | `/listen/study/{id}/timeline` | Session | Timeline + payment page |
| GET | `/listen/study/{id}/status` | Session | Live status page |
| GET | `/api/client/study/{id}/status` | Session | Status JSON (polled) |
| GET | `/api/client/study/{id}/report-link` | Session | Shareable report URL |
| GET | `/api/client/timeline/{id}` | Session | Timeline JSON |
| POST | `/api/client/quote/compute` | — | Live quote compute |
| POST | `/api/client/payment/initiate` | Session | Create Razorpay/Stripe order |
| POST | `/api/client/payment/razorpay/verify` | — | Verify payment signature |

### Admin Portal (`app_admin.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/admin/login` | — | Admin login page |
| POST | `/admin/login` | — | Authenticate admin |
| GET | `/admin/logout` | Session | Clear admin session |
| GET | `/admin` | Admin | Admin dashboard |
| GET | `/admin/pricing` | Admin | Pricing editor |
| GET | `/api/admin/stats` | Admin | Platform stats |
| GET | `/api/admin/clients` | Admin | List all clients |
| GET | `/api/admin/studies` | Admin | List all studies |
| GET | `/api/admin/pricing` | Admin | Pricing config JSON |
| POST | `/api/admin/pricing` | Admin | Update pricing config |

### Panel Recruitment (`app_panel.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/enroll` | Respondent enrollment page |
| POST | `/api/respondents/enroll` | Enroll respondent |
| GET | `/api/respondents` | List respondents (filterable) |
| GET | `/api/respondents/stats` | Panel aggregate stats |
| GET | `/api/respondents/{id}` | Get respondent |
| PATCH | `/api/respondents/{id}/status` | Update status |
| POST | `/panel/api/csv-upload` | Build panel from CSV |
| POST | `/panel/api/query` | Build panel from DB query |
| GET | `/panel/api/{project_id}` | Get panel for project |
| POST | `/panel/api/{panel_id}/confirm` | Confirm panel |

### Respondent Portal (`app_respondent.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/join/profile/{phone}` | Respondent profile page |
| GET | `/join/rewards/{id}` | Rewards dashboard |
| GET | `/api/respondents/{id}/points` | Points balance + history |
| POST | `/api/respondents/{id}/points/add` | Add points (admin) |
| POST | `/api/respondents/{id}/redeem` | Submit redemption request |
| GET | `/api/respondents/{id}/redemptions` | Redemption history |
| GET | `/api/points/rates` | Exchange rates by country |
| GET | `/api/admin/redemptions` | All redemption requests |
| PATCH | `/api/admin/redemptions/{id}` | Update redemption status |

### Agentic Pipeline (`app_agentic.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/agent` | Agent dashboard |
| GET | `/agent/brief` | Brief chat UI |
| POST | `/agent/api/brief/start` | Start brief session |
| POST | `/agent/api/brief/message` | Send message, get reply |
| GET | `/agent/api/brief/{id}` | Get session state |
| POST | `/agent/api/design` | Run DesignerAgent |
| GET | `/agent/api/projects` | List agentic projects |
| GET | `/agent/api/projects/{id}` | Get project |
| POST | `/agent/api/reports/generate` | Run AnalysisAgent |
| GET | `/agent/api/reports` | List reports |
| GET | `/agent/api/reports/{id}` | Get report |

---

## Key Class Reference

### `config/settings.py` — Settings

```python
class Settings(BaseSettings):
    # GCP / Gemini
    gcp_project_id: str
    gemini_model: str = "gemini-2.5-flash"
    gemini_model_pro: str = "gemini-2.5-pro"
    gemini_api_key: str = ""
    gcp_location: str = "us-central1"

    # Voice
    sarvam_api_key: str = ""
    voice_provider: str = "google_cloud"  # google_cloud | sarvam | auto

    # Languages
    interview_language: str = "en,id,fil,th,vi,ko,ja,zh,hi"
    indian_languages: str = "hi,en-IN,ta,te,ml,kn,bn,mr,gu,pa,or"

    # Auth
    secret_key: str
    client_credentials: str = "demo:demo123"
    admin_credentials: str = "admin:getheard-admin-2026"
    api_key: str = "getheard-dev-key-2026"

    # Payments
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    stripe_publishable_key: str = ""
    stripe_secret_key: str = ""

    # Notifications
    resend_api_key: str = ""
    resend_from_email: str = "hello@getheard.space"
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""

    # Properties
    def client_credentials_dict → dict
    def admin_credentials_dict → dict
    def has_razorpay → bool
    def has_stripe → bool
    def has_resend → bool
    def has_sarvam_credentials → bool
    def should_use_sarvam(language_code) → bool
    def supported_languages → List[str]
```

---

### `src/agents/base_agent.py` — BaseAgent

```python
@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict      # JSON Schema
    handler: Callable

@dataclass
class AgentResult:
    text: str
    tool_calls: List[Dict]
    metadata: Dict

class BaseAgent:
    def register_tool(spec: ToolSpec)
    def run(message: str) → AgentResult
        # Gemini function-calling loop:
        # 1. Build request with tool definitions
        # 2. Call Gemini
        # 3. If tool_calls → execute → re-run with results
        # 4. Return final text
```

---

### `src/voice/pipeline.py` — VoiceInterviewPipeline

```python
class VoiceInterviewPipeline:
    def __init__(language_code: str, project_id: str = None):
        # Auto-routes to Sarvam or Google Cloud
        # Loads custom questions if project_id provided

    async def start_interview() → bytes  # MP3 greeting audio
    async def process_audio(audio_bytes, audio_format) → tuple:
        # Returns: (transcript_text, response_audio_bytes, is_complete)
    def get_conversation_history() → List[Dict]
    def get_provider_info() → Dict
    def is_interview_complete() → bool
```

---

### `src/storage/pricing_store.py` — Pricing

```python
def load_pricing_config() → Dict
def save_pricing_config(config: Dict)
def get_size_multiplier(panel_size: int) → float

def compute_quote(
    study_type: str,          # nps_csat | feature_feedback | pain_points | custom
    panel_size: int,
    panel_source: str,        # csv | db | targeted
    market: str = "IN",       # Country code
    industry: str = "other",
    urgency: bool = False,
    respondent_incentive_per_head: int = 0,
    config: Dict = None       # Pass pre-loaded config for efficiency
) → Dict:
    # Returns itemised breakdown:
    # {study_fee, recruitment_fee, incentive_total, urgency_fee, total,
    #  line_items: [...], params: {...}}
```

---

### `src/storage/points_store.py` — Points

```python
EXCHANGE_RATES = {
    "IN": {"currency": "INR", "rate": 0.50},
    "SG": {"currency": "SGD", "rate": 0.01},
    "ID": {"currency": "IDR", "rate": 150},
    # ... 12 countries
}
MIN_REDEMPTION_POINTS = 100
GIFT_CARD_BONUS_PERCENT = 10

def get_points_balance(respondent_id) → Dict
def add_points(respondent_id, amount, reason, study_id=None) → bool
def deduct_points(respondent_id, amount, reason) → bool
def create_redemption_request(respondent_id, points, method, details, country) → Dict
def list_redemption_requests(status=None) → List[Dict]
def update_redemption_status(request_id, status, notes=None) → bool
```

---

## CSS Design System

All UI uses the navy colour palette defined in `src/web/static/design_system.css`:

```css
:root {
    --navy:        #1e3c72;   /* Primary buttons, borders, active nav */
    --navy-dark:   #152d56;   /* Hover states, sidebar background */
    --blue:        #2a5298;   /* Secondary buttons, links */
    --blue-light:  #4facfe;   /* Accents, highlights */
    --accent:      #60a5fa;   /* Icons, tags, active states */
    --off-white:   #e8edf5;   /* Panel backgrounds */
    --muted:       #8fa3c8;   /* Placeholder text */
    --white:       #ffffff;
}
```

**Component classes available:** `.btn-primary`, `.btn-secondary`, `.btn-outline`, `.btn-ghost`, `.card`, `.badge`, `.badge-active`, `.badge-pending`, `.badge-inprogress`, `.tag`, `.tag-active`, `.nav-item`, `.nav-item.active`, `.stat-card`, `.info-box`, `.hero`, `.pipeline-step`

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GCP_PROJECT_ID` | Yes | — | Google Cloud project ID |
| `GEMINI_API_KEY` | Yes* | — | Gemini API key (*or use Vertex AI) |
| `GEMINI_MODEL` | No | `gemini-2.5-flash` | Model for voice/chat |
| `GEMINI_MODEL_PRO` | No | `gemini-2.5-pro` | Model for analysis/design |
| `GCP_LOCATION` | No | `us-central1` | Vertex AI region |
| `SARVAM_API_KEY` | No | — | Sarvam AI (Indian languages) |
| `VOICE_PROVIDER` | No | `google_cloud` | `google_cloud` / `sarvam` / `auto` |
| `SECRET_KEY` | Yes | — | Session cookie signing key |
| `CLIENT_CREDENTIALS` | No | `demo:demo123` | Client portal logins |
| `ADMIN_CREDENTIALS` | No | `admin:getheard-admin-2026` | Admin portal login |
| `API_KEY` | No | `getheard-dev-key-2026` | Voice API authentication |
| `RAZORPAY_KEY_ID` | No | — | Razorpay public key |
| `RAZORPAY_KEY_SECRET` | No | — | Razorpay secret key |
| `STRIPE_PUBLISHABLE_KEY` | No | — | Stripe public key |
| `STRIPE_SECRET_KEY` | No | — | Stripe secret key |
| `RESEND_API_KEY` | No | — | Resend email API key |
| `RESEND_FROM_EMAIL` | No | `hello@getheard.space` | Sender email address |
| `WHATSAPP_PHONE_NUMBER_ID` | No | — | Meta WhatsApp phone ID |
| `WHATSAPP_ACCESS_TOKEN` | No | — | Meta WhatsApp token |
| `TWILIO_ACCOUNT_SID` | No | — | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | No | — | Twilio Auth Token |
| `INTERVIEW_LANGUAGE` | No | `en,id,fil,...` | Supported language codes |
| `MAX_INTERVIEW_DURATION` | No | `600` | Max seconds per interview |
| `QUESTIONS_COUNT` | No | `3` | Default question count |
| `HOST` | No | `0.0.0.0` | Server bind address |
| `PORT` | No | `8000` | Server port |
