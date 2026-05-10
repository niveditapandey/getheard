# Developer Guide — GetHeard

Welcome to the GetHeard codebase. This guide gets you from zero to running the full platform locally in under 15 minutes.

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.11+ | Required |
| pip | Latest | `pip install --upgrade pip` |
| Git | Any | |
| Google Cloud account | — | For STT/TTS APIs |
| Gemini API key | — | Free at [aistudio.google.com](https://aistudio.google.com) |

Optional (for full feature set):
- Sarvam AI API key (Indian language STT/TTS)
- Razorpay account (payments)
- Resend account (email)
- Meta Business account (WhatsApp)
- Twilio account (WhatsApp fallback)

---

## 1. Clone & Setup

```bash
# Clone the repo
git clone <repo-url> getHeard
cd getHeard

# Create virtual environment
python -m venv venv

# Activate
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

# Install core dependencies
pip install -r requirements.txt

# Install optional payment/email/session deps
pip install razorpay stripe httpx itsdangerous resend
```

---

## 2. Environment Configuration

Copy the template and fill in your values:

```bash
cp .env.example .env
```

**Minimum config to run (voice + chat):**
```env
GCP_PROJECT_ID=your-gcp-project-id
GEMINI_API_KEY=AIzaSy...            # From aistudio.google.com - FREE
SECRET_KEY=any-random-secret-string-change-me
```

**Full config (all features):**
```env
# ── Core ──────────────────────────────────────────────────────────
GCP_PROJECT_ID=getheard-484014
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.5-flash
GEMINI_MODEL_PRO=gemini-2.5-pro
GCP_LOCATION=us-central1

# ── Indian Languages (Sarvam) ─────────────────────────────────────
SARVAM_API_KEY=sk_...
VOICE_PROVIDER=auto               # auto | google_cloud | sarvam

# ── Auth ──────────────────────────────────────────────────────────
SECRET_KEY=change-this-to-a-long-random-string
CLIENT_CREDENTIALS=demo:demo123,acme:acme2026
ADMIN_CREDENTIALS=admin:strong-password-here
API_KEY=getheard-dev-key-2026

# ── Payments ──────────────────────────────────────────────────────
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...

# ── Email ─────────────────────────────────────────────────────────
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL=hello@getheard.space

# ── WhatsApp ──────────────────────────────────────────────────────
WHATSAPP_PHONE_NUMBER_ID=985230514675305
WHATSAPP_BUSINESS_ID=2332652903923836
WHATSAPP_ACCESS_TOKEN=EAAND...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# ── Interview Settings ────────────────────────────────────────────
INTERVIEW_LANGUAGE=en,hi,id,fil,th,vi,ko,ja,zh
DEFAULT_LANGUAGE=en
MAX_INTERVIEW_DURATION=600
QUESTIONS_COUNT=3
HOST=0.0.0.0
PORT=8000
```

---

## 3. Google Cloud Setup

GetHeard uses Google Cloud Speech APIs for STT and TTS. Two options:

### Option A: Gemini API Key Only (Easiest)
If you just set `GEMINI_API_KEY`, the LLM works. For STT/TTS, you still need Google Cloud credentials.

### Option B: Application Default Credentials (Recommended)
```bash
# Install Google Cloud CLI
brew install google-cloud-sdk        # macOS
# Or download from cloud.google.com/sdk

# Authenticate
gcloud auth application-default login

# Set project
gcloud config set project getheard-484014

# Enable APIs
gcloud services enable speech.googleapis.com
gcloud services enable texttospeech.googleapis.com
gcloud services enable aiplatform.googleapis.com
```

---

## 4. Run the Server

```bash
# Development (with auto-reload)
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload

# Production-like
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --workers 4
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

---

## 5. Verify Installation

Open these URLs to check each portal:

| URL | Expected |
|-----|---------|
| http://localhost:8000 | Landing page (navy hero) |
| http://localhost:8000/health | JSON with config info |
| http://localhost:8000/listen/login | Client login page |
| http://localhost:8000/admin/login | Admin login page |
| http://localhost:8000/join | Respondent home |
| http://localhost:8000/agent | Agent dashboard |

**Test client login:**
- Email: `demo` / Password: `demo123` (matches `CLIENT_CREDENTIALS=demo:demo123`)

**Test admin login:**
- Username: `admin` / Password: `getheard-admin-2026`

---

## 6. Project Structure & Where Things Live

### Adding a new API route

1. Decide which router it belongs to (client? admin? panel? respondent?)
2. Open the corresponding `src/web/app_*.py`
3. Add your route function
4. No registration needed — routers are auto-included in `app.py`

Example — adding a new client API:
```python
# src/web/app_client.py

@router.get("/api/client/my-new-endpoint")
async def my_new_endpoint(request: Request):
    client_id = request.session.get("client_id")
    if not client_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Your logic here
    return {"data": "something"}
```

### Adding a new HTML page

1. Create template in `src/web/templates/`
2. Use the base pattern:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <link rel="stylesheet" href="/static/design_system.css">
</head>
<body>
  <!-- Your content using CSS classes from design_system.css -->
</body>
</html>
```
3. Add a route that renders it:
```python
return templates.TemplateResponse("your_template.html", {"request": request})
```

### Adding a new agent

1. Create `src/agents/my_agent.py`
2. Extend `BaseAgent`:
```python
from src.agents.base_agent import BaseAgent, ToolSpec, AgentResult

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.register_tool(ToolSpec(
            name="my_tool",
            description="What this tool does",
            parameters={"type": "object", "properties": {...}},
            handler=self._handle_my_tool
        ))

    async def _handle_my_tool(self, params: dict) -> str:
        # Do something
        return "Tool completed successfully"

    async def run_my_workflow(self, input_data: dict) -> dict:
        result = await self.run(f"Do something with: {input_data}")
        return result.metadata
```

### Adding a new storage module

1. Create `src/storage/my_store.py`
2. Follow the pattern:
```python
import json
import os
from pathlib import Path

STORE_DIR = Path("my_entities")
STORE_DIR.mkdir(exist_ok=True)

def save_entity(data: dict) -> dict:
    entity_id = f"ent_{uuid4().hex[:8]}"
    data["entity_id"] = entity_id
    filepath = STORE_DIR / f"{entity_id}.json"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return data

def get_entity(entity_id: str) -> dict | None:
    filepath = STORE_DIR / f"{entity_id}.json"
    if not filepath.exists():
        return None
    with open(filepath) as f:
        return json.load(f)
```

---

## 7. Common Development Tasks

### Reset all data (start fresh)
```bash
rm -rf projects/* transcripts/* reports/* clients/* respondents/* panels/* redemptions/*
```

### Test the voice API manually
```bash
curl -X POST http://localhost:8000/api/start \
  -H "X-API-Key: getheard-dev-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"language": "en", "project_id": null}'
```

### Test the quote compute endpoint
```bash
curl -X POST http://localhost:8000/api/client/quote/compute \
  -H "Content-Type: application/json" \
  -d '{
    "study_type": "nps_csat",
    "panel_size": 15,
    "panel_source": "db",
    "market": "IN",
    "industry": "fintech",
    "urgency": false,
    "respondent_incentive_per_head": 0
  }'
```

### Check health
```bash
curl http://localhost:8000/health
```

### Manually trigger AnalysisAgent
```bash
curl -X POST http://localhost:8000/agent/api/reports/generate \
  -H "Content-Type: application/json" \
  -d '{"project_id": "your_project_id"}'
```

---

## 8. Code Conventions

### Python Style
- **Type hints** everywhere for function signatures
- **async/await** for all route handlers and I/O-bound work
- **Pydantic** for request/response validation
- **No magic strings** — use constants or config values
- Logging: `import logging; logger = logging.getLogger(__name__)`

### Error Handling
```python
# Route handlers: raise HTTPException
raise HTTPException(status_code=404, detail="Project not found")

# Storage functions: return None on not-found
def get_project(id) -> dict | None:
    ...

# Agents: return partial results, never crash
try:
    result = await self.run(message)
except Exception as e:
    logger.error(f"Agent error: {e}")
    return AgentResult(text="Analysis incomplete", tool_calls=[], metadata={})
```

### Template Variables
All templates receive `request` as a minimum:
```python
return templates.TemplateResponse("page.html", {
    "request": request,
    "client": client_data,
    "projects": projects_list
})
```

---

## 9. Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_gemini.py -v

# Run with output
pytest tests/ -v -s
```

**Manual testing checklist:**
- [ ] Landing page loads at `/`
- [ ] Client can sign up and log in at `/listen`
- [ ] Admin can log in at `/admin`
- [ ] Respondent can enroll at `/join`
- [ ] Voice interview starts at `/interview`
- [ ] BriefAgent chat works at `/agent/brief`
- [ ] Quote computes correctly at `/api/client/quote/compute`
- [ ] Health check returns 200 at `/health`

---

## 10. Debugging Tips

### Server won't start
```bash
# Check for syntax errors
python -c "from src.web.app import app; print('OK')"

# Check settings load
python config/settings.py
```

### Voice not working
- Check `GEMINI_API_KEY` is set
- Ensure Google Cloud credentials configured: `gcloud auth application-default login`
- Check browser has microphone permission

### Session not persisting (login fails)
- Ensure `SECRET_KEY` is set in `.env`
- Check `itsdangerous` is installed: `pip install itsdangerous`

### WhatsApp messages not sending
- Verify `WHATSAPP_ACCESS_TOKEN` is not expired (60-day token from Meta)
- Check `WHATSAPP_PHONE_NUMBER_ID` is correct
- Ensure phone number is registered in Meta Business Manager

### Payments not working
- Razorpay: check both `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` are set
- Stripe: ensure `stripe` package is installed (`pip install stripe`)
- Check server is accessible from internet for webhooks (use ngrok for local testing)

---

## 11. Key Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `pydantic-settings` | Config from .env |
| `google-genai` | Gemini LLM |
| `google-cloud-speech` | STT |
| `google-cloud-texttospeech` | TTS |
| `httpx` | Async HTTP (Sarvam, Resend, WhatsApp) |
| `itsdangerous` | Session signing |
| `python-multipart` | File upload handling |
| `razorpay` | Razorpay payments |
| `stripe` | Stripe payments |
| `twilio` | WhatsApp (Twilio) |
| `jinja2` | HTML templating |
| `websockets` | WebSocket support |

---

## 12. Ngrok for Local Webhook Testing

WhatsApp and Stripe/Razorpay need to reach your local server. Use ngrok:

```bash
# Install ngrok (brew install ngrok or download from ngrok.com)
ngrok http 8000

# Copy the HTTPS URL e.g. https://abc123.ngrok.io
# Set in Twilio: Messaging → Sandbox Settings → Webhook = https://abc123.ngrok.io/webhook/whatsapp
# Set in Razorpay: Settings → Webhooks → https://abc123.ngrok.io/api/client/payment/razorpay/verify
```

---

## 13. Deployment Checklist (Before Going Live)

- [ ] Change `SECRET_KEY` to a long random value
- [ ] Change `ADMIN_CREDENTIALS` to a strong password
- [ ] Set `RESEND_FROM_EMAIL=hello@getheard.space` (after domain verified)
- [ ] Use production Razorpay keys (live, not test)
- [ ] Enable HTTPS on the server
- [ ] Set up persistent volume for JSON files (or migrate to DB)
- [ ] Configure Razorpay webhook URL to production domain
- [ ] Configure WhatsApp webhook URL to production domain
- [ ] Set up error monitoring (Sentry or similar)
- [ ] Set up uptime monitoring
- [ ] Test all payment flows end-to-end in production
