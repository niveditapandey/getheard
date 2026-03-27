"""
GetHeard FastAPI server.

Routes:
  GET  /                               → voice interview UI
  GET  /dashboard                      → analytics dashboard
  GET  /projects                       → projects listing page
  GET  /projects/{id}                  → project detail page
  GET  /report/{id}                    → research report page
  POST /api/start                      → start voice session
  POST /api/respond                    → submit audio, get AI response
  GET  /api/transcript/{id}            → live session transcript
  GET  /api/transcript-file/{name}     → saved transcript file
  GET  /api/transcripts                → list all saved transcripts
  GET  /api/stats                      → aggregate dashboard stats
  POST /api/projects/generate-questions → AI question preview (no save)
  POST /api/projects                   → create + save project
  GET  /api/projects                   → list all projects
  GET  /api/projects/{id}              → get project JSON
  PATCH /api/projects/{id}/questions   → update edited questions
  POST /api/reports/generate           → generate report from transcripts
  GET  /api/reports/{id}               → get report JSON
  GET  /api/reports                    → list all reports
  POST /webhook/whatsapp               → Twilio WhatsApp inbound
  GET  /api/whatsapp/stats             → active WhatsApp sessions
  GET  /health

  — Panel & Respondent (via app_panel router) —
  GET  /enroll                         → public respondent enrollment form
  POST /api/respondents/enroll         → enroll a respondent
  GET  /api/respondents                → list respondents
  GET  /api/respondents/stats          → aggregate panel counts
  GET  /api/respondents/{id}           → single respondent
  PATCH /api/respondents/{id}/status   → update status
  POST /panel/api/csv-upload           → Mode A: CSV → panel
  POST /panel/api/query                → Mode B: DB search → panel
  GET  /panel/api/{project_id}         → get panel for project
  POST /panel/api/{panel_id}/confirm   → client confirms panel

  — Client Portal —
  GET  /client/login                   → login page
  POST /client/login                   → authenticate
  GET  /client/logout                  → logout
  GET  /client                         → client dashboard
  GET  /api/client/projects            → projects visible to logged-in client
  GET  /api/client/stats               → stats for logged-in client

  — Respondent Portal (via app_respondent router) —
  GET  /join/profile/{phone}           → respondent profile page
  GET  /join/rewards/{respondent_id}   → rewards/points dashboard
  GET  /api/respondents/{id}/points    → points balance + history
  POST /api/respondents/{id}/points/add → add points (admin use)
  POST /api/respondents/{id}/redeem    → submit redemption request
  GET  /api/respondents/{id}/redemptions → redemption history
  GET  /api/points/rates               → exchange rates by country
  GET  /api/admin/redemptions          → all redemptions (admin)
  PATCH /api/admin/redemptions/{id}    → update redemption status (admin)
"""

import asyncio
import base64
import json
import logging
import sys
from pathlib import Path
from typing import Dict

import uvicorn
from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Request, Security, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings
from src.core.report_generator import generate_report, load_report, list_reports
from src.core.research_project import (
    create_project, generate_questions, get_project, list_projects,
    RESEARCH_TYPES, INDUSTRIES, LANGUAGE_NAMES, VALID_QUESTION_COUNTS,
)
from src.storage.transcript import TranscriptManager, TRANSCRIPTS_DIR
from src.voice.pipeline import VoiceInterviewPipeline
from src.web.app_agentic import router as agentic_router
from src.web.app_panel import router as panel_router
from src.web.app_client import router as client_router
from src.web.app_admin import router as admin_router
from src.web.app_study import router as study_router
from src.web.app_respondent import router as respondent_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="GetHeard Voice Interview Platform", version="1.0.0")
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

# ── Static files ──────────────────────────────────────────────────────────────
_static_dir = Path(__file__).parent / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(agentic_router)     # /agent/*
app.include_router(panel_router)       # /enroll, /api/respondents/*, /panel/api/*
app.include_router(client_router)      # /listen/*, /api/client/*
app.include_router(admin_router)       # /admin/*, /api/admin/*
app.include_router(study_router)       # /listen/study/*, /api/client/study/*, payment routes
app.include_router(respondent_router)  # /join/profile/*, /join/rewards/*, /api/respondents/*/points

# ── Sessions & storage ───────────────────────────────────────────────────────
sessions: Dict[str, VoiceInterviewPipeline] = {}
transcript_manager = TranscriptManager()
TEMPLATES = Path(__file__).parent / "templates"

# ── API key auth (optional — only enforces if header present) ────────────────
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def optional_api_key(api_key: str = Security(API_KEY_HEADER)):
    """
    Soft auth: if X-API-Key header is sent it must be valid.
    If omitted (browser requests), allows through for the MVP.
    """
    if api_key and api_key != settings.api_key:
        raise HTTPException(403, "Invalid API key")
    return api_key


# ── UI Routes ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_landing():
    """Public landing page — getheard.space"""
    f = TEMPLATES / "landing.html"
    if f.exists():
        return HTMLResponse(f.read_text(encoding="utf-8"))
    # Fallback to old interview UI if landing not built yet
    f = TEMPLATES / "index.html"
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else "<h1>GetHeard</h1>")


@app.get("/join", response_class=HTMLResponse)
async def serve_join():
    """Respondent panel landing page."""
    f = TEMPLATES / "respondent_home.html"
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else "<h1>Join page not found</h1>")


@app.get("/join/enroll", response_class=HTMLResponse)
async def serve_join_enroll():
    """Respondent enrollment form."""
    f = TEMPLATES / "enroll.html"
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else "<h1>Enroll form not found</h1>")


@app.get("/interview", response_class=HTMLResponse)
async def serve_ui():
    """Legacy voice interview UI — kept for direct interview access."""
    f = TEMPLATES / "index.html"
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else "<h1>UI not found</h1>")


@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    f = TEMPLATES / "dashboard.html"
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else "<h1>Dashboard not found</h1>")


@app.get("/projects", response_class=HTMLResponse)
async def serve_projects():
    f = TEMPLATES / "projects.html"
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else "<h1>Projects not found</h1>")


@app.get("/projects/new", response_class=HTMLResponse)
async def serve_new_project():
    f = TEMPLATES / "new_project.html"
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else "<h1>New project page not found</h1>")


@app.get("/projects/{project_id}", response_class=HTMLResponse)
async def serve_project_detail(project_id: str):
    f = TEMPLATES / "project_detail.html"
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else "<h1>Project detail page not found</h1>")


@app.get("/report/{report_id}", response_class=HTMLResponse)
async def serve_report(report_id: str):
    f = TEMPLATES / "report.html"
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else "<h1>Report not found</h1>")


# ── Voice interview API ──────────────────────────────────────────────────────

@app.post("/api/start")
async def start_interview(
    language: str = "en",
    project_id: str = "",
    _: str = Depends(optional_api_key),
):
    supported = settings.supported_languages + ["en"]
    if language not in supported:
        raise HTTPException(400, f"Language '{language}' not supported. Supported: {supported}")

    try:
        pipeline = VoiceInterviewPipeline(language_code=language, project_id=project_id or None)
        greeting_audio = await pipeline.start_interview()
        sessions[pipeline.session_id] = pipeline

        # Link session to project if applicable
        if project_id:
            proj = get_project(project_id)
            if proj:
                import asyncio
                await asyncio.to_thread(proj.add_session, pipeline.session_id)

        logger.info(f"Session {pipeline.session_id} started | lang={language} | project={project_id or 'none'}")
        return {
            "session_id": pipeline.session_id,
            "language": language,
            "greeting_audio_b64": base64.b64encode(greeting_audio).decode(),
            "provider_info": pipeline.get_provider_info(),
            "project_id": project_id or None,
        }
    except Exception as exc:
        logger.exception("Failed to start interview")
        raise HTTPException(500, str(exc))


@app.post("/api/respond")
async def respond(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    _: str = Depends(optional_api_key),
):
    if session_id not in sessions:
        raise HTTPException(404, "Session not found or expired")

    pipeline = sessions[session_id]

    ct = audio.content_type or ""
    fn = audio.filename or ""
    if "webm" in ct or fn.endswith(".webm"):
        audio_format = "webm"
    elif "wav" in ct or fn.endswith(".wav"):
        audio_format = "wav"
    elif "mp3" in ct or fn.endswith(".mp3"):
        audio_format = "mp3"
    elif "ogg" in ct or fn.endswith(".ogg"):
        audio_format = "ogg"
    else:
        audio_format = "webm"

    audio_bytes = await audio.read()

    try:
        transcript, response_audio, is_complete = await pipeline.process_audio(
            audio_bytes, audio_format=audio_format
        )
    except Exception as exc:
        logger.exception(f"[{session_id}] Error processing audio")
        raise HTTPException(500, str(exc))

    if is_complete:
        logger.info(f"Session {session_id} completed")

    return {
        "session_id": session_id,
        "transcript": transcript,
        "response_audio_b64": base64.b64encode(response_audio).decode(),
        "is_complete": is_complete,
    }


@app.post("/api/end/{session_id}")
async def end_session(session_id: str):
    """Force-save transcript and clean up session — called when user clicks End."""
    if session_id not in sessions:
        return {"status": "not_found"}
    pipeline = sessions[session_id]
    try:
        await asyncio.to_thread(pipeline._save_transcript)
    except Exception as e:
        logger.warning(f"Force-save transcript failed for {session_id}: {e}")
    sessions.pop(session_id, None)
    return {"status": "saved", "session_id": session_id}


@app.get("/api/transcript/{session_id}")
async def get_live_transcript(session_id: str):
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")
    pipeline = sessions[session_id]
    return {
        "session_id": session_id,
        "language": pipeline.language_code,
        "is_complete": pipeline.is_interview_complete(),
        "provider_info": pipeline.get_provider_info(),
        "conversation": pipeline.get_conversation_history(),
    }


@app.get("/api/transcript-file/{filename}")
async def get_transcript_file(filename: str):
    """Load a saved transcript JSON file for the dashboard."""
    filepath = TRANSCRIPTS_DIR / filename
    if not filepath.exists():
        raise HTTPException(404, "Transcript file not found")
    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/transcripts")
async def list_transcripts():
    return {"transcripts": transcript_manager.list_transcripts()}


@app.get("/api/stats")
async def get_stats():
    """Aggregate stats for the dashboard."""
    transcripts = transcript_manager.list_transcripts()
    lang_counts: Dict[str, int] = {}
    channel_counts = {"voice": 0, "whatsapp": 0}

    for t in transcripts:
        lang = t.get("language_code", "en")
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
        if "whatsapp" in (t.get("file") or ""):
            channel_counts["whatsapp"] += 1
        else:
            channel_counts["voice"] += 1

    wa_active = 0
    try:
        from src.web.whatsapp_handler import get_whatsapp_manager
        wa_active = get_whatsapp_manager().active_count()
    except Exception:
        pass

    return {
        "total": len(transcripts),
        "by_language": lang_counts,
        "by_channel": channel_counts,
        "active_voice_sessions": len(sessions),
        "whatsapp_active": wa_active,
    }


# ── Research Projects API ────────────────────────────────────────────────────

@app.post("/api/projects/generate-questions")
async def api_generate_questions(payload: dict = Body(...), _: str = Depends(optional_api_key)):
    """Preview AI-generated questions without saving a project."""
    required = ["name", "research_type", "industry", "objective", "audience", "language", "question_count"]
    for field in required:
        if field not in payload:
            raise HTTPException(400, f"Missing field: {field}")
    try:
        questions = await asyncio.to_thread(
            generate_questions,
            name=payload["name"],
            research_type=payload["research_type"],
            industry=payload["industry"],
            objective=payload["objective"],
            audience=payload["audience"],
            language=payload["language"],
            topics=payload.get("topics", ""),
            count=int(payload["question_count"]),
        )
        return {"questions": questions}
    except Exception as exc:
        logger.exception("Question generation failed")
        raise HTTPException(500, str(exc))


@app.post("/api/projects")
async def api_create_project(payload: dict = Body(...), _: str = Depends(optional_api_key)):
    """Create and save a project with (optionally pre-edited) questions."""
    required = ["name", "research_type", "industry", "objective", "audience", "language", "question_count"]
    for field in required:
        if field not in payload:
            raise HTTPException(400, f"Missing field: {field}")
    try:
        project = await asyncio.to_thread(
            create_project,
            name=payload["name"],
            research_type=payload["research_type"],
            industry=payload["industry"],
            objective=payload["objective"],
            audience=payload["audience"],
            language=payload["language"],
            topics=payload.get("topics", ""),
            question_count=int(payload["question_count"]),
        )
        # If caller supplies edited questions, overwrite the AI-generated ones
        if "questions" in payload and payload["questions"]:
            await asyncio.to_thread(project.update_questions, payload["questions"])
        return project.to_dict()
    except Exception as exc:
        logger.exception("Project creation failed")
        raise HTTPException(500, str(exc))


@app.get("/api/projects")
async def api_list_projects():
    return {"projects": list_projects()}


@app.get("/api/projects/{project_id}")
async def api_get_project(project_id: str):
    proj = get_project(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    return proj.to_dict()


@app.patch("/api/projects/{project_id}/questions")
async def api_update_questions(project_id: str, payload: dict = Body(...), _: str = Depends(optional_api_key)):
    proj = get_project(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    questions = payload.get("questions")
    if not questions or not isinstance(questions, list):
        raise HTTPException(400, "Provide a 'questions' list")
    await asyncio.to_thread(proj.update_questions, questions)
    return {"status": "updated", "question_count": len(questions)}


# ── Reports API ───────────────────────────────────────────────────────────────

@app.post("/api/reports/generate")
async def api_generate_report(payload: dict = Body(...), _: str = Depends(optional_api_key)):
    """
    Generate a research report from saved transcripts.
    Body: { project_id (optional), transcript_files: [filename, ...],
            project_name, research_type, objective }
    """
    transcript_files = payload.get("transcript_files", [])
    if not transcript_files:
        raise HTTPException(400, "Provide 'transcript_files' list")

    transcripts = []
    for fname in transcript_files:
        fpath = TRANSCRIPTS_DIR / fname
        if fpath.exists():
            try:
                transcripts.append(json.loads(fpath.read_text(encoding="utf-8")))
            except Exception:
                pass

    if not transcripts:
        raise HTTPException(400, "No valid transcripts found")

    # Load project context if project_id supplied
    project_name = payload.get("project_name", "Research Study")
    research_type = payload.get("research_type", "cx")
    objective = payload.get("objective", "Understand customer experience")
    questions = None

    project_id = payload.get("project_id")
    if project_id:
        proj = get_project(project_id)
        if proj:
            project_name = proj.name
            research_type = proj._data.get("research_type", research_type)
            objective = proj._data.get("objective", objective)
            questions = proj.questions

    try:
        report = await asyncio.to_thread(
            generate_report,
            transcripts=transcripts,
            project_name=project_name,
            research_type=research_type,
            objective=objective,
            questions=questions,
        )
        return {"report_id": report["report_id"], "report": report}
    except Exception as exc:
        logger.exception("Report generation failed")
        raise HTTPException(500, str(exc))


@app.get("/api/reports")
async def api_list_reports():
    return {"reports": list_reports()}


@app.get("/api/reports/{report_id}")
async def api_get_report(report_id: str):
    report = load_report(report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    return report


# ── WhatsApp webhook ─────────────────────────────────────────────────────────

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    ProfileName: str = Form(default=""),
):
    """Twilio WhatsApp inbound webhook."""
    from src.web.whatsapp_handler import get_whatsapp_manager

    logger.info(f"[WA] {From} ({ProfileName}): {Body[:80]}")

    try:
        manager = get_whatsapp_manager()
        reply = manager.handle_message(from_number=From, body=Body)
    except Exception as exc:
        logger.exception("[WA] Handler error")
        reply = "Sorry, something went wrong. Please try again or type 'stop'."

    # Return TwiML
    from twilio.twiml.messaging_response import MessagingResponse
    resp = MessagingResponse()
    resp.message(reply)
    from fastapi.responses import Response
    return Response(content=str(resp), media_type="application/xml")


@app.get("/api/whatsapp/stats")
async def whatsapp_stats():
    try:
        from src.web.whatsapp_handler import get_whatsapp_manager
        m = get_whatsapp_manager()
        return {"active_sessions": m.active_count(), "active_numbers": m.active_numbers()}
    except Exception as e:
        return {"active_sessions": 0, "error": str(e)}


@app.post("/api/whatsapp/send")
async def send_whatsapp(to: str, message: str, _: str = Depends(optional_api_key)):
    """Send a proactive WhatsApp message to start an interview."""
    if not settings.has_twilio_credentials:
        raise HTTPException(503, "Twilio not configured — add TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN to .env")
    try:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        msg = client.messages.create(
            from_=settings.twilio_whatsapp_number,
            body=message,
            to=to if to.startswith("whatsapp:") else f"whatsapp:{to}",
        )
        return {"status": "sent", "sid": msg.sid}
    except Exception as exc:
        raise HTTPException(500, str(exc))


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "active_sessions": len(sessions),
        "supported_languages": settings.supported_languages,
        "gemini_model": settings.gemini_model,
        "has_sarvam": settings.has_sarvam_credentials,
        "has_twilio": settings.has_twilio_credentials,
    }


if __name__ == "__main__":
    uvicorn.run("src.web.app:app", host=settings.host, port=settings.port, reload=True)
