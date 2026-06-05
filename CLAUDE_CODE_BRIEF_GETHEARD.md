# GetHeard — Claude Code Sprint Brief
## "Finish the platform in 3-4 days"

---

## WHO YOU ARE AND WHAT THIS IS

You are Claude Code working on **getHeard** — an AI-powered qualitative research platform
built for Asian markets. Two-sided marketplace: brands commission research studies, 
respondents complete AI-moderated interviews via WhatsApp or voice call, AI generates 
boardroom-ready reports.

This is NOT a greenfield build. The platform is ~85% complete. Your job is to 
**finish, fix, and wire** — not rebuild.

**Owner:** Nivedita Pandey (nivedita@dendrons.ai)  
**GCP Project:** getheard-484014  
**Repo:** https://github.com/niveditapandey/getheard.git  
**Stack:** FastAPI + Jinja2 + vanilla JS. Python 3.13. Gemini 2.5 Flash via google-genai SDK (vertexai=True). Google Cloud STT/TTS + Sarvam AI. Twilio for WhatsApp + voice. Firestore for storage. JSON files for projects/transcripts/reports.

---

## CURRENT STATE (read this carefully before touching anything)

### What exists and works
- App starts clean: `bash run.sh` → uvicorn on port 8000, no errors
- Landing page renders at `/`
- Three portals: `/listen` (client/brand portal), `/join` (respondent portal), `/admin`
- All five agents are coded: BriefAgent, DesignerAgent, InterviewAgent, AnalysisAgent, PanelAgent
- Orchestrator is clean and well-structured (read `src/agents/orchestrator.py`)
- Voice pipeline: Google Cloud STT/TTS + Sarvam AI (Indian languages)
- WhatsApp handler exists: `src/web/whatsapp_handler.py`
- Report generation: PDF + PPTX generators exist in `src/core/`
- Firestore storage layer (migrated from JSON in earlier commits)
- Auth: session-based, client portal + admin dashboard

### Git state
- HEAD is on branch `fix/questions-and-link` (local, 2 commits ahead of origin/master)
- Last two commits fixed: brief chat link retry logic + collapsible questions on status page
- These fixes are NOT yet pushed to origin

### Key routes (from CLAUDE.md)
- POST `/agent/api/design` — DesignerAgent saves questions to project JSON
- POST `/api/client/studies/{project_id}/link` — links project to client session
- GET `/api/client/projects` — reads session["linked_studies"]
- GET `/agent/api/projects/{id}` — returns full project JSON including questions[]
- GET `/api/client/study/{id}/status` — pipeline status only

### Auth system
- Client: session cookie, `request.session["client_id"]`
- Simple/demo users: client_id starts with "simple:", studies stored in `session["linked_studies"]`
- Admin: `request.session["is_admin"]`
- **FIRST TASK:** find admin credentials in `.env` or `config/settings.py` and document them

---

## THE AGENT ARCHITECTURE (understand this before coding)

The orchestrator coordinates four stages. Each is independent:

```
Stage 1: Brief      → BriefAgent    → conversational chat, extracts research brief
Stage 2: Design     → DesignerAgent → generates + self-reviews interview questions  
Stage 3: Interview  → InterviewAgent → drives each respondent conversation
Stage 4: Analysis   → AnalysisAgent → 4-pass report generation
```

The orchestrator is a **thin coordinator** — it doesn't do the work itself, it creates
agents and passes state between them. The agents do the work via Gemini.

**InterviewAgent** is the key to both channels:
- WhatsApp: Twilio webhook → text in → InterviewAgent.process_message() → text out
- Voice: STT → InterviewAgent.process_message() → TTS → audio out

Same brain, different I/O channels.

---

## WHAT NEEDS TO BE BUILT/FIXED (in priority order)

### PRIORITY 1: Credentials and login (Day 1, first 30 mins)

1. Find admin password in `.env` or `config/settings.py`
2. Find/create a way to log into client portal as a test user
3. Document ALL credentials clearly in CLAUDE.md
4. Verify you can access all three portals: `/listen`, `/join`, `/admin`

### PRIORITY 2: Brief → Design pipeline (Day 1)

This is the client-facing flow. A brand comes in, chats with the BriefAgent,
gets a study designed. This MUST work end-to-end.

**Test it:** Log into `/listen` → commission research → chat interface → complete brief → 
see generated questions → project appears in dashboard.

**Find and fix any breaks in this flow.** Common failure points:
- BriefAgent Gemini call failing (check API key, model name)
- DesignerAgent not being triggered after brief completes
- Questions not being saved/displayed correctly
- The `fix/questions-and-link` branch fixes may not be fully applied

**The brief chat UI is at:** `src/web/templates/agent/brief_chat.html`  
**The agentic routes are in:** `src/web/app_agentic.py`  
**The orchestrator methods to use:** `start_brief_session()`, `send_brief_message()`, `design_study()`

After fixing, push the `fix/questions-and-link` branch to origin.

### PRIORITY 3: WhatsApp interview channel (Day 2)

This is the fastest channel to get working — pure text, no voice complexity.

**What needs to happen:**
1. Twilio sends incoming WhatsApp message to POST `/webhook/whatsapp`
2. `whatsapp_handler.py` receives it, looks up or creates respondent session
3. Finds the project the respondent is linked to (via their phone number or a join link)
4. Creates/retrieves InterviewAgent for that project
5. Passes message to `InterviewAgent.process_message()`
6. Returns response to Twilio → sends to respondent's WhatsApp

**Check whatsapp_handler.py first** — understand what's already built vs. what's missing.

**Twilio setup to verify:**
- Check `.env` for TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER
- Webhook URL needs to be publicly accessible — use ngrok for local testing:
  ```bash
  ngrok http 8000
  ```
  Then set Twilio WhatsApp sandbox webhook to: `https://YOUR_NGROK_URL/webhook/whatsapp`

**Session management for WhatsApp:**
- Key sessions by phone number (from Twilio's `From` field)
- Store active InterviewAgent instances in memory dict (same pattern as `_brief_sessions` in orchestrator)
- Persist transcript to Firestore when interview completes

**Test flow:**
1. Send "hi" to Twilio sandbox WhatsApp number
2. Receive greeting from InterviewAgent
3. Complete 3-5 question interview
4. Transcript saved
5. Confirm transcript appears in admin dashboard

### PRIORITY 4: Voice interview channel (Day 3)

Start with **web-based push-to-talk** (easier) before Twilio voice calls.

**Web push-to-talk flow:**
1. Respondent goes to `/join/{project_id}`
2. Clicks "Start Interview"  
3. Records audio chunk (MediaRecorder API)
4. Sends to POST `/interview/audio` with project_id + session_id
5. Backend: audio → Google Cloud STT → InterviewAgent.process_message() → Gemini → Google Cloud TTS → audio
6. Returns audio to browser, plays back
7. Loop until interview complete

**The voice pipeline is in:** `src/voice/pipeline.py`  
**STT:** `src/voice/google_cloud_stt.py` (use for English/SEA languages)  
**STT for Indian languages:** `src/voice/sarvam_stt.py`  
**TTS:** `src/voice/google_cloud_tts.py` and `src/voice/sarvam_tts.py`

**Language routing logic (smart router — implement this):**
```python
def get_stt_provider(language_code: str):
    SARVAM_LANGUAGES = {"hi-IN", "bn-IN", "ta-IN", "te-IN", "mr-IN", "gu-IN"}
    if language_code in SARVAM_LANGUAGES and sarvam_available():
        return SarvamSTT()
    return GoogleCloudSTT()
```

**Respondent join flow:**
- Client generates a shareable link: `getHeard.io/join/{project_id}?token=xxx`
- Respondent opens link, sees study description, clicks Start
- Interview runs (voice or WhatsApp depending on context)
- Completion screen with incentive info

### PRIORITY 5: Analysis → Report (Day 4)

After interviews complete, AnalysisAgent generates a report.

**Trigger:** Either manual (admin clicks "Generate Report") or automatic (N interviews complete).

**Flow:**
1. Admin goes to project in dashboard
2. Clicks "Generate Report"
3. POST `/admin/projects/{project_id}/report`
4. `orchestrator.generate_report(project_id)` runs AnalysisAgent
5. 4-pass analysis: themes → quotes → insights → recommendations
6. Report saved to Firestore + JSON
7. `src/core/pdf_generator.py` generates PDF
8. `src/core/pptx_generator.py` generates PPTX
9. Both downloadable from admin dashboard

**Check AnalysisAgent first** (`src/agents/analysis_agent.py`) — understand its 4-pass structure before wiring routes.

---

## GEMINI CONFIGURATION (critical — don't break this)

```python
# CORRECT way to initialize (already in codebase, don't change)
from google import genai
client = genai.Client(
    vertexai=True,
    project="getheard-484014",
    location="us-central1"
)

# CORRECT model
model = "gemini-2.5-flash"  # or "gemini-2.0-flash" if 2.5 not available

# Auth — if getting 401/403:
# Run: gcloud auth application-default login --no-launch-browser
# Follow the URL, paste the code back
```

---

## INTERVIEW AGENT SYSTEM PROMPT (the intelligence layer)

The InterviewAgent's Gemini system prompt is the most important thing in the product.
It must be an **adaptive qualitative researcher**, not a scripted Q&A bot.

The prompt must instruct Gemini to:
1. Ask the pre-designed questions in order, but naturally
2. PROBE when answers are vague — don't just move on
3. TRACK themes across the conversation — reference earlier answers
4. DECIDE when to move to next question vs. stay on current one
5. Maintain persona: warm, professional, curious, non-judgmental
6. Mirror the respondent's language (Hindi → respond Hindi, English → English, Hinglish → Hinglish)
7. Keep responses SHORT for voice (1-2 sentences max)
8. Signal completion cleanly so the pipeline knows to stop

**Prompt structure:**
```
You are an expert qualitative research interviewer named Alex, conducting a study 
on behalf of [client_name] about [objective].

QUESTIONS TO COVER:
[numbered list of questions from DesignerAgent]

YOUR BEHAVIOR:
- Ask questions conversationally, not mechanically
- After each answer, decide: probe deeper OR move to next question
- Probe when: answer is vague, uses jargon, contradicts earlier answer, 
  mentions something surprising
- Move on when: you have rich detail, 2+ minutes on topic, natural conclusion
- Track themes: if Q3 answer relates to Q1, say "You mentioned earlier that..."
- Mirror language: respond in same language/mix as respondent
- Keep voice responses to 1-2 sentences
- When all questions are covered, say: "Thank you so much for your time today. 
  This has been incredibly helpful." — this signals interview completion.

CURRENT CONVERSATION STATE:
Questions completed: {completed_questions}
Questions remaining: {remaining_questions}
Key themes so far: {themes_so_far}
```

---

## WHATSAPP INTERVIEW PROMPT VARIANT

For WhatsApp, responses can be slightly longer (3-4 sentences) since it's text.
Add to system prompt:
```
This is a text-based WhatsApp interview. You may write 2-4 sentences per response.
Use line breaks for readability. Do NOT use markdown formatting (no **, no #).
Emojis are fine and make the conversation feel warmer — use sparingly.
```

---

## TWILIO WHATSAPP WEBHOOK HANDLER SPEC

```python
@router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    form_data = await request.form()
    from_number = form_data.get("From")      # e.g. "whatsapp:+6512345678"
    body = form_data.get("Body", "").strip()
    
    # 1. Look up or create session for this phone number
    session = get_or_create_whatsapp_session(from_number)
    
    # 2. Get or create InterviewAgent for this session's project
    if not session.interview_agent:
        project_id = session.project_id  # set when respondent joins via link
        session.interview_agent = orchestrator.create_interview_agent(project_id)
        # First message — send greeting
        reply = session.interview_agent.get_greeting()
    else:
        reply = await session.interview_agent.process_message(body)
    
    # 3. Check if interview is complete
    if session.interview_agent.is_complete():
        save_transcript_to_firestore(session)
        reply = session.interview_agent.get_closing_message()
        cleanup_session(from_number)
    
    # 4. Return TwiML response
    return Response(
        content=f'<?xml version="1.0"?><Response><Message>{reply}</Message></Response>',
        media_type="application/xml"
    )
```

---

## RESPONDENT JOIN FLOW SPEC

When a client launches a study, they get a shareable link. Respondents click it.

**Link format:** `/join/{project_id}` or `/join/{project_id}?ref={panel_source}`

**Join page should:**
1. Show study title + estimated time (from project metadata)
2. Show incentive amount (from project settings)
3. Ask for: first name, WhatsApp number (for WhatsApp channel) OR just "Start" button (for web voice)
4. For WhatsApp: send them a WhatsApp message to start, OR show QR code to scan
5. For voice: go directly to the voice interview UI

**Session linking (WhatsApp path):**
- When respondent submits their number, store: `{phone_number: project_id}` in Firestore
- When Twilio webhook fires for that number, look up project_id from this mapping
- This is how the webhook knows WHICH project to interview for

---

## ADMIN DASHBOARD REQUIREMENTS

Admin at `/admin` should show:

1. **Projects list:** project name, client, # questions, # completed interviews, status
2. **Per-project view:** 
   - Questions list (collapsible — already partially built)
   - Respondents list with completion status
   - "Generate Report" button
   - Download links for PDF + PPTX once generated
3. **Transcripts viewer:** per respondent, full conversation
4. **Client list:** which clients, which studies linked

---

## QUALITY SCORING (already coded — just wire it)

`src/core/quality_scorer.py` exists. Wire it to run after each interview completes:
- Score: response length, relevance, completeness, fraud signals
- Store score in transcript metadata
- Flag low-quality responses in admin dashboard
- Don't count flagged responses toward analysis unless overridden

---

## ENV VARIABLES NEEDED

Check `.env` and ensure ALL of these are set:

```bash
# Google Cloud
GOOGLE_CLOUD_PROJECT=getheard-484014
GOOGLE_CLOUD_LOCATION=us-central1

# Sarvam AI
SARVAM_API_KEY=sk_hfcqy7pg_81AQuahucahYDGen5PN6hZOV

# Twilio
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886  # sandbox number

# Admin
ADMIN_PASSWORD=
ADMIN_USERNAME=

# Session
SECRET_KEY=  # for itsdangerous session signing

# Firestore (should work via gcloud auth, but check)
FIRESTORE_PROJECT_ID=getheard-484014
```

---

## TESTING CHECKPOINTS (verify each before moving on)

### After Priority 1 (credentials):
- [ ] Can log into `/admin`
- [ ] Can log into `/listen` as a test client
- [ ] Can reach `/join` page

### After Priority 2 (brief → design):
- [ ] Start brief chat → complete conversation → questions generated
- [ ] Questions visible in client dashboard
- [ ] Project appears in admin dashboard
- [ ] `fix/questions-and-link` branch pushed to origin

### After Priority 3 (WhatsApp):
- [ ] ngrok running, Twilio webhook configured
- [ ] Send "hi" to WhatsApp sandbox → receive greeting
- [ ] Complete 5-question interview via WhatsApp
- [ ] Transcript saved and visible in admin

### After Priority 4 (voice):
- [ ] Go to `/join/{project_id}` in browser
- [ ] Click Start → microphone activates
- [ ] Speak → transcription → AI response → TTS plays back
- [ ] Complete interview → transcript saved

### After Priority 5 (analysis):
- [ ] Click "Generate Report" in admin
- [ ] Report generates (may take 30-60 seconds)
- [ ] PDF downloads correctly
- [ ] PPTX downloads correctly

---

## DEBUGGING GUIDE

### If Gemini calls fail:
```bash
gcloud auth application-default login --no-launch-browser
# Copy URL → open in browser → sign in as nivedita@dendrons.ai → paste code back
```

### If Firestore fails:
- Check that `GOOGLE_CLOUD_PROJECT` is set in `.env`
- Run: `gcloud config set project getheard-484014`
- Check Firestore is enabled at console.cloud.google.com

### If Twilio webhook doesn't fire:
- Ensure ngrok is running: `ngrok http 8000`
- Copy the https URL from ngrok output
- Go to Twilio console → WhatsApp sandbox → set webhook to `https://XXX.ngrok.io/webhook/whatsapp`
- Send a message to the sandbox number to trigger it

### If audio doesn't work in voice interview:
- Check browser has microphone permission
- Check Google Cloud STT is enabled in GCP console
- Test STT directly: `python test_voice.py`
- Test Sarvam STT: `python tests/test_sarvam.py`

### Common import errors to watch for:
- `from src.agents.orchestrator import orchestrator` — use module-level singleton
- Firestore `db` import — use module-level `db` not `get_db()` (was fixed in commit 398fde9)

---

## CODE STYLE RULES

- No inline `#` comments in multi-line terminal commands (causes quote mode issues on Mac)
- Python 3.13 — use modern syntax
- Async everywhere for I/O (Gemini calls, Firestore, Twilio, STT/TTS)
- Log with `logger = logging.getLogger(__name__)` — not print statements
- Every agent method should have try/except with logger.error()
- Keep agent system prompts in the agent file itself, not in a separate prompts.py

---

## END GOAL (what "done" looks like)

A demo-able, investor-showable platform where:

1. A brand logs in → chats with AI → study is designed in <2 minutes
2. A shareable WhatsApp link goes out to respondents
3. Respondents complete AI-moderated interviews on WhatsApp (text) or voice (web)  
4. Admin sees completions in real-time
5. Click "Generate Report" → PDF + PPTX report downloads with themes, quotes, insights
6. The whole flow works without any manual intervention

That's the pitch. That's what you're building toward.

---

## FIRST THING TO DO WHEN YOU OPEN CLAUDE CODE

1. Read this entire brief
2. Read `CLAUDE.md` in project root
3. Read `src/agents/orchestrator.py` (clean, understand the flow)
4. Run `cat .env` and document what's configured vs. missing
5. Start the server: `bash run.sh`
6. Open `http://localhost:8000` in browser
7. Try to log in to all three portals
8. Report back: what works, what breaks, what's missing
9. Then start fixing in priority order above

Do NOT start rewriting things that already work. Read first, fix second.
