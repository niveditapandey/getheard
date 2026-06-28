"""
GetHeard — Full test suite (unit + functional).

Run against local server (default):
    pytest tests/test_suite.py -v

Run against production:
    TEST_BASE_URL=https://getheard-151428781052.asia-south1.run.app pytest tests/test_suite.py -v
"""

import io
import json
import os
import struct
import sys
import wave
from pathlib import Path

import pytest
import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 60  # seconds — generous for Gemini calls


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT, follow_redirects=True) as c:
        yield c


@pytest.fixture(scope="session")
def client_session(client):
    """Authenticated client-portal session (demo account)."""
    r = client.post("/listen/login", data={"email": "demo", "password": "demo123"})
    assert r.status_code == 200, f"Client login failed: {r.status_code}"
    return client


@pytest.fixture(scope="session")
def admin_session(client):
    """Authenticated admin session."""
    r = client.post("/admin/login", data={"username": "admin", "password": "getheard-admin-2026"})
    assert r.status_code == 200, f"Admin login failed: {r.status_code}"
    return client


@pytest.fixture(scope="session")
def sample_project(client):
    """Create a project once and share it across tests."""
    r = client.post("/api/projects", json={
        "name":          "Test Suite Project",
        "research_type": "cx",
        "industry":      "Technology / SaaS",
        "objective":     "Understand why users churn from the platform",
        "audience":      "SaaS users aged 25-40",
        "language":      "en",
        "question_count": 5,
    })
    assert r.status_code == 200, f"Project creation failed: {r.text[:200]}"
    return r.json()


def make_wav_bytes(duration_ms: int = 500, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    n = int(rate * duration_ms / 1000)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * n)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS — pure Python, no server needed
# ═══════════════════════════════════════════════════════════════════════════════

class TestSettings:
    def test_settings_load(self):
        from config.settings import settings
        assert settings.gemini_model.startswith("gemini")
        assert settings.gcp_project_id == "getheard-484014"

    def test_supported_languages(self):
        from config.settings import settings
        langs = settings.supported_languages
        assert "en" in langs
        assert "hi" in langs
        assert len(langs) >= 9

    def test_sarvam_routing_hindi(self):
        from config.settings import settings
        if settings.has_sarvam_credentials:
            assert settings.should_use_sarvam("hi") is True

    def test_google_routing_english(self):
        from config.settings import settings
        if settings.voice_provider in ("google_cloud", "auto"):
            assert settings.should_use_sarvam("en") is False

    def test_client_credentials_parsed(self):
        from config.settings import settings
        creds = settings.client_credentials_dict
        assert isinstance(creds, dict)
        assert "demo" in creds

    def test_admin_credentials_parsed(self):
        from config.settings import settings
        creds = settings.admin_credentials_dict
        assert isinstance(creds, dict)
        assert len(creds) >= 1


class TestPricingStore:
    def test_compute_quote_basic(self):
        from src.storage.pricing_store import compute_quote
        q = compute_quote(study_type="nps_csat", panel_size=10, panel_source="csv", market="IN")
        assert "total" in q
        assert q["total"] > 0
        assert "subtotal" in q
        assert "currency" in q

    def test_compute_quote_urgency(self):
        from src.storage.pricing_store import compute_quote
        normal = compute_quote(study_type="pain_points", panel_size=20, panel_source="csv", market="IN", urgency=False)
        urgent = compute_quote(study_type="pain_points", panel_size=20, panel_source="csv", market="IN", urgency=True)
        assert urgent["total"] > normal["total"]

    def test_compute_quote_large_panel(self):
        from src.storage.pricing_store import compute_quote
        small = compute_quote(study_type="custom", panel_size=5,  panel_source="csv", market="IN")
        large = compute_quote(study_type="custom", panel_size=100, panel_source="csv", market="IN")
        assert large["total"] > small["total"]

    def test_compute_quote_incentive(self):
        from src.storage.pricing_store import compute_quote
        without = compute_quote(study_type="nps_csat", panel_size=10, panel_source="csv", market="IN", respondent_incentive_per_head=0)
        with_inc = compute_quote(study_type="nps_csat", panel_size=10, panel_source="csv", market="IN", respondent_incentive_per_head=200)
        assert with_inc["total"] > without["total"]

    def test_compute_quote_panel_source(self):
        from src.storage.pricing_store import compute_quote
        csv     = compute_quote(study_type="nps_csat", panel_size=10, panel_source="csv",      market="IN")
        targeted = compute_quote(study_type="nps_csat", panel_size=10, panel_source="targeted", market="IN")
        assert targeted["total"] >= csv["total"]


class TestQualityScorer:
    def _make_transcript(self, turns=8, avg_words=25, language="en"):
        conversation = []
        for i in range(turns):
            if i % 2 == 0:
                conversation.append({"speaker": "interviewer", "text": f"Question {i//2 + 1}?"})
            else:
                words = " ".join(["word"] * avg_words)
                conversation.append({"speaker": "respondent", "text": words})
        return {"session_id": "test_sess", "language_code": language, "conversation": conversation}

    def test_high_quality_score(self):
        from src.core.quality_scorer import score_transcript
        t = self._make_transcript(turns=12, avg_words=40)
        result = score_transcript(t, ai_evaluate=False)
        assert result["score"] >= 50
        assert result["label"] in ("high_quality", "medium_quality")
        assert "flags" in result
        assert "details" in result

    def test_low_quality_short_responses(self):
        from src.core.quality_scorer import score_transcript
        t = self._make_transcript(turns=4, avg_words=2)
        result = score_transcript(t, ai_evaluate=False)
        assert result["score"] < 75

    def test_score_has_required_keys(self):
        from src.core.quality_scorer import score_transcript
        t = self._make_transcript()
        result = score_transcript(t, ai_evaluate=False)
        for key in ("score", "label", "emoji", "flags", "details"):
            assert key in result, f"Missing key: {key}"

    def test_label_matches_score(self):
        from src.core.quality_scorer import score_transcript, QUALITY_LABELS
        t = self._make_transcript(turns=10, avg_words=30)
        result = score_transcript(t, ai_evaluate=False)
        score = result["score"]
        label = result["label"]
        thresholds = sorted(QUALITY_LABELS.items(), key=lambda x: x[1]["min"], reverse=True)
        expected = next(k for k, v in thresholds if score >= v["min"])
        assert label == expected


class TestResearchProject:
    def test_create_and_get_project(self):
        from src.core.research_project import create_project, get_project
        proj = create_project(
            name="Unit Test Project",
            research_type="ux",
            industry="Technology / SaaS",
            objective="Test objective",
            audience="Test users",
            language="en",
            topics="usability, navigation",
            question_count=5,
        )
        assert proj.project_id
        fetched = get_project(proj.project_id)
        assert fetched is not None
        assert fetched.name == "Unit Test Project"

    def test_project_has_questions(self):
        from src.core.research_project import create_project
        proj = create_project(
            name="Questions Test",
            research_type="cx",
            industry="Retail / E-commerce",
            objective="Understand purchase journey",
            audience="Online shoppers",
            language="en",
            topics="purchase, checkout, returns",
            question_count=5,
        )
        assert len(proj.questions) == 5
        for q in proj.questions:
            assert "main" in q or "text" in q

    def test_update_questions(self):
        from src.core.research_project import create_project, get_project
        proj = create_project(
            name="Update Test",
            research_type="brand",
            industry="Healthcare",
            objective="Brand perception",
            audience="Patients",
            language="en",
            topics="brand, trust, recommendation",
            question_count=5,
        )
        new_qs = [{"main": f"Updated Q{i+1}", "probe": "", "intent": ""} for i in range(3)]
        proj.update_questions(new_qs)
        fetched = get_project(proj.project_id)
        assert len(fetched.questions) == 3


class TestGeminiInterviewer:
    def test_interviewer_starts(self):
        from src.conversation.gemini_engine import GeminiInterviewer
        iv = GeminiInterviewer(language_code="en")
        greeting = iv.start_interview()
        assert isinstance(greeting, str)
        assert len(greeting) > 10
        assert iv.state == "greeting"

    def test_process_response_advances_state(self):
        from src.conversation.gemini_engine import GeminiInterviewer
        iv = GeminiInterviewer(language_code="en")
        iv.start_interview()
        response = iv.process_response("I've been using it for 3 months now and overall it's been pretty good.")
        assert isinstance(response, str)
        assert len(response) > 5

    def test_interview_completes(self):
        from src.conversation.gemini_engine import GeminiInterviewer
        iv = GeminiInterviewer(language_code="en")
        iv.start_interview()
        for _ in range(20):
            if iv.state == iv.COMPLETED:
                break
            iv.process_response("This is a detailed answer about my experience with the product.")
        assert iv.state == iv.COMPLETED

    def test_conversation_history_recorded(self):
        from src.conversation.gemini_engine import GeminiInterviewer
        iv = GeminiInterviewer(language_code="en")
        iv.start_interview()
        iv.process_response("I've been using it for 6 months.")
        history = iv.get_conversation_history()
        assert len(history) >= 2
        speakers = {h["speaker"] for h in history}
        assert "interviewer" in speakers
        assert "respondent" in speakers

    def test_custom_questions(self):
        from src.conversation.gemini_engine import GeminiInterviewer
        qs = [
            {"main": "Tell me about your onboarding experience.", "probe": "What was most confusing?", "intent": "onboarding"},
            {"main": "How do you use the product daily?", "probe": "What features do you rely on most?", "intent": "usage"},
        ]
        iv = GeminiInterviewer(language_code="en", custom_questions=qs, project_name="Test Study")
        greeting = iv.start_interview()
        assert isinstance(greeting, str)
        assert iv._use_custom is True


class TestVoicePipeline:
    def test_pipeline_initialises(self):
        from src.voice.pipeline import VoiceInterviewPipeline
        p = VoiceInterviewPipeline(language_code="en")
        assert p.session_id
        assert p.language_code == "en"
        assert p._stt_provider in ("google", "sarvam")
        assert p._tts_provider in ("google", "sarvam")

    def test_pipeline_hindi_uses_sarvam_when_configured(self):
        from src.voice.pipeline import VoiceInterviewPipeline
        from config.settings import settings
        p = VoiceInterviewPipeline(language_code="hi")
        if settings.has_sarvam_credentials:
            assert p._stt_provider == "sarvam"
            assert p._tts_provider == "sarvam"

    def test_provider_info(self):
        from src.voice.pipeline import VoiceInterviewPipeline
        p = VoiceInterviewPipeline(language_code="en")
        info = p.get_provider_info()
        assert "stt" in info
        assert "tts" in info
        assert "session_id" in info
        assert info["session_id"] == p.session_id

    def test_not_complete_initially(self):
        from src.voice.pipeline import VoiceInterviewPipeline
        p = VoiceInterviewPipeline(language_code="en")
        assert p.is_interview_complete() is False

    def test_history_initially_empty(self):
        from src.voice.pipeline import VoiceInterviewPipeline
        p = VoiceInterviewPipeline(language_code="en")
        assert p.get_conversation_history() == []


class TestPrompts:
    def test_greetings_exist_for_all_languages(self):
        from src.conversation.prompts import get_greeting
        from config.settings import settings
        for lang in settings.supported_languages:
            greeting = get_greeting(lang)
            assert isinstance(greeting, str)
            assert len(greeting) > 10

    def test_questions_exist(self):
        from src.conversation.prompts import get_question
        for i in range(1, 4):
            q = get_question(i, "en")
            assert isinstance(q, str)
            assert len(q) > 5

    def test_closing_exists(self):
        from src.conversation.prompts import get_closing
        closing = get_closing("en")
        assert isinstance(closing, str)
        assert len(closing) > 10


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCTIONAL TESTS — require running server
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthAndPublicPages:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "gemini_model" in data
        assert "supported_languages" in data

    def test_landing_page(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "html" in r.headers.get("content-type", "").lower()

    def test_join_page(self, client):
        r = client.get("/join")
        assert r.status_code == 200

    def test_enroll_page(self, client):
        r = client.get("/join/enroll")
        assert r.status_code == 200

    def test_agent_page(self, client):
        r = client.get("/agent")
        assert r.status_code == 200

    def test_agent_brief_page(self, client):
        r = client.get("/agent/brief")
        assert r.status_code == 200

    def test_mission_control_page(self, client):
        r = client.get("/mission-control")
        assert r.status_code == 200

    def test_public_config(self, client):
        r = client.get("/api/config/public")
        assert r.status_code == 200
        data = r.json()
        assert "whatsapp_number" in data


class TestAuthRedirects:
    def test_client_portal_redirects_when_unauthenticated(self, client):
        r = client.get("/listen", follow_redirects=False)
        assert r.status_code in (302, 303)
        assert "login" in r.headers.get("location", "").lower()

    def test_admin_portal_redirects_when_unauthenticated(self, client):
        r = client.get("/admin", follow_redirects=False)
        assert r.status_code in (302, 303)
        assert "login" in r.headers.get("location", "").lower()

    def test_client_login_page_loads(self, client):
        r = client.get("/listen/login")
        assert r.status_code == 200

    def test_admin_login_page_loads(self, client):
        r = client.get("/admin/login")
        assert r.status_code == 200

    def test_client_login_success(self, client):
        r = client.post("/listen/login", data={"email": "demo", "password": "demo123"})
        assert r.status_code == 200

    def test_client_login_bad_credentials(self, client):
        r = client.post("/listen/login", data={"email": "demo", "password": "wrongpassword"}, follow_redirects=False)
        assert r.status_code in (302, 303)
        assert "error" in r.headers.get("location", "").lower()

    def test_admin_login_success(self, client):
        r = client.post("/admin/login", data={"username": "admin", "password": "getheard-admin-2026"})
        assert r.status_code == 200

    def test_admin_login_bad_credentials(self, client):
        r = client.post("/admin/login", data={"username": "admin", "password": "wrong"}, follow_redirects=False)
        assert r.status_code in (302, 303)
        assert "error" in r.headers.get("location", "").lower()


class TestVoiceAPI:
    def test_start_interview(self, client):
        r = client.post("/api/start?language=en")
        assert r.status_code == 200
        data = r.json()
        assert "session_id" in data
        assert "greeting_audio_b64" in data
        assert len(data["greeting_audio_b64"]) > 100  # non-empty audio
        assert "provider_info" in data

    def test_start_interview_invalid_language(self, client):
        r = client.post("/api/start?language=xx_invalid")
        assert r.status_code == 400

    def test_respond_with_audio(self, client):
        # Start session
        r = client.post("/api/start?language=en")
        assert r.status_code == 200
        session_id = r.json()["session_id"]

        # Send silence WAV
        wav = make_wav_bytes(500)
        r = client.post("/api/respond", files={"audio": ("audio.wav", wav, "audio/wav")},
                        data={"session_id": session_id})
        assert r.status_code == 200
        data = r.json()
        assert "transcript" in data
        assert "response_audio_b64" in data
        assert "is_complete" in data
        assert "current_question_idx" in data
        assert isinstance(data["is_complete"], bool)

    def test_respond_invalid_session(self, client):
        wav = make_wav_bytes(200)
        r = client.post("/api/respond", files={"audio": ("a.wav", wav, "audio/wav")},
                        data={"session_id": "definitely_fake_session_id"})
        assert r.status_code == 404

    def test_live_transcript(self, client):
        r = client.post("/api/start?language=en")
        session_id = r.json()["session_id"]
        r = client.get(f"/api/transcript/{session_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == session_id
        assert "is_complete" in data
        assert "conversation" in data

    def test_end_session(self, client):
        r = client.post("/api/start?language=en")
        session_id = r.json()["session_id"]
        r = client.post(f"/api/end/{session_id}")
        assert r.status_code == 200
        assert r.json()["status"] in ("saved", "not_found")

    def test_stats(self, client):
        r = client.get("/api/stats")
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "by_language" in data


class TestProjectsAPI:
    def test_list_projects(self, client):
        r = client.get("/api/projects")
        assert r.status_code == 200
        assert "projects" in r.json()

    def test_create_project_rejects_invalid_research_type(self, client):
        r = client.post("/api/projects", json={
            "name": "Bad Type", "research_type": "not_valid", "industry": "Healthcare",
            "objective": "x", "audience": "y", "language": "en", "question_count": 5,
        })
        assert r.status_code == 400

    def test_create_project_rejects_unsupported_language(self, client):
        r = client.post("/api/projects", json={
            "name": "Bad Lang", "research_type": "cx", "industry": "Healthcare",
            "objective": "x", "audience": "y", "language": "xx", "question_count": 5,
        })
        assert r.status_code == 400

    def test_create_project_rejects_bad_question_count(self, client):
        r = client.post("/api/projects", json={
            "name": "Bad Count", "research_type": "cx", "industry": "Healthcare",
            "objective": "x", "audience": "y", "language": "en", "question_count": 999,
        })
        assert r.status_code == 400

    def test_create_project(self, client):
        r = client.post("/api/projects", json={
            "name":          "Functional Test Project",
            "research_type": "brand",
            "industry":      "Retail / E-commerce",
            "objective":     "Understand brand perception",
            "audience":      "Online shoppers 18-35",
            "language":      "en",
            "question_count": 5,
        })
        assert r.status_code == 200
        data = r.json()
        assert "project_id" in data
        assert data["name"] == "Functional Test Project"
        assert len(data.get("questions", [])) == 5

    def test_get_project(self, client, sample_project):
        pid = sample_project["project_id"]
        r = client.get(f"/api/projects/{pid}")
        assert r.status_code == 200
        assert r.json()["project_id"] == pid

    def test_get_project_404(self, client):
        r = client.get("/api/projects/nonexistent_project_id")
        assert r.status_code == 404

    def test_update_questions(self, client, sample_project):
        pid = sample_project["project_id"]
        new_qs = [{"main": f"Updated Q{i+1}?", "probe": "Tell me more.", "intent": "general"} for i in range(3)]
        r = client.patch(f"/api/projects/{pid}/questions", json={"questions": new_qs})
        assert r.status_code == 200
        assert r.json()["question_count"] == 3

    def test_project_status(self, client, sample_project):
        pid = sample_project["project_id"]
        r = client.get(f"/api/projects/{pid}/status")
        assert r.status_code == 200
        data = r.json()
        assert data["project_id"] == pid
        assert "total_sessions" in data
        assert "quality_breakdown" in data

    def test_screener_get(self, client, sample_project):
        pid = sample_project["project_id"]
        r = client.get(f"/api/projects/{pid}/screener")
        assert r.status_code == 200

    def test_screener_submit_no_screener(self, client, sample_project):
        pid = sample_project["project_id"]
        r = client.post(f"/api/screener/{pid}/submit", json={"answers": {}, "lang": "en"})
        assert r.status_code == 200
        assert r.json()["qualified"] is True

    def test_screener_page(self, client, sample_project):
        pid = sample_project["project_id"]
        r = client.get(f"/screener/{pid}")
        assert r.status_code == 200

    def test_branding_update(self, client, sample_project):
        pid = sample_project["project_id"]
        r = client.patch(f"/api/projects/{pid}/branding", json={
            "brand_name": "TestBrand", "brand_color": "#ff0000", "logo_url": ""
        })
        assert r.status_code == 200


class TestReportsAPI:
    def test_list_reports(self, client):
        r = client.get("/api/reports")
        assert r.status_code == 200
        assert "reports" in r.json()

    def test_get_report_404(self, client):
        r = client.get("/api/reports/nonexistent_report_id")
        assert r.status_code == 404

    def test_export_endpoints_exist_for_real_report(self, client):
        r = client.get("/api/reports")
        reports = r.json().get("reports", [])
        if not reports:
            pytest.skip("No reports in system to test export")
        rid = reports[0]["report_id"]
        for fmt in ["pptx", "pdf"]:
            r = client.get(f"/api/reports/{rid}/export/{fmt}")
            assert r.status_code == 200
            assert len(r.content) > 1000


class TestPricingAPI:
    def test_quote_compute(self, client):
        r = client.post("/api/client/quote/compute", json={
            "study_type": "nps_csat",
            "panel_size": 20,
            "panel_source": "csv",
            "market": "IN",
            "industry": "banking",
            "urgency": False,
            "respondent_incentive_per_head": 200,
        })
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert data["total"] > 0
        assert "subtotal" in data

    def test_quote_with_urgency(self, client):
        payload = {"study_type": "pain_points", "panel_size": 15, "panel_source": "db",
                   "market": "SG", "industry": "tech", "urgency": False, "respondent_incentive_per_head": 0}
        normal = client.post("/api/client/quote/compute", json=payload).json()
        payload["urgency"] = True
        urgent = client.post("/api/client/quote/compute", json=payload).json()
        assert urgent["total"] > normal["total"]


class TestClientPortal:
    def test_dashboard_accessible_when_logged_in(self, client_session):
        r = client_session.get("/listen")
        assert r.status_code == 200

    def test_client_projects_api(self, client_session):
        r = client_session.get("/api/client/projects")
        assert r.status_code == 200
        assert "projects" in r.json()

    def test_client_stats_api(self, client_session):
        r = client_session.get("/api/client/stats")
        assert r.status_code == 200
        data = r.json()
        assert "active_studies" in data
        assert "completed_studies" in data

    def test_new_study_page(self, client_session):
        r = client_session.get("/listen/study/new")
        assert r.status_code == 200

    def test_study_status_page(self, client_session, sample_project):
        pid = sample_project["project_id"]
        r = client_session.get(f"/listen/study/{pid}/status")
        assert r.status_code == 200

    def test_study_pricing_page(self, client_session, sample_project):
        pid = sample_project["project_id"]
        r = client_session.get(f"/listen/study/{pid}/pricing")
        assert r.status_code == 200

    def test_study_timeline_page(self, client_session, sample_project):
        pid = sample_project["project_id"]
        r = client_session.get(f"/listen/study/{pid}/timeline")
        assert r.status_code == 200

    def test_client_study_status_api(self, client_session, sample_project):
        pid = sample_project["project_id"]
        r = client_session.get(f"/api/client/study/{pid}/status")
        assert r.status_code == 200
        data = r.json()
        assert "project_id" in data
        assert "status" in data

    def test_link_study_to_client(self, client_session, sample_project):
        pid = sample_project["project_id"]
        r = client_session.post(f"/api/client/studies/{pid}/link")
        assert r.status_code == 200
        assert r.json()["status"] == "linked"


class TestAdminPortal:
    def test_admin_dashboard(self, admin_session):
        r = admin_session.get("/admin")
        assert r.status_code == 200

    def test_admin_clients_page(self, admin_session):
        r = admin_session.get("/admin/clients")
        assert r.status_code == 200

    def test_admin_studies_page(self, admin_session):
        r = admin_session.get("/admin/studies")
        assert r.status_code == 200

    def test_admin_respondents_page(self, admin_session):
        r = admin_session.get("/admin/respondents")
        assert r.status_code == 200

    def test_admin_pricing_page(self, admin_session):
        r = admin_session.get("/admin/pricing")
        assert r.status_code == 200

    def test_admin_payouts_page(self, admin_session):
        r = admin_session.get("/admin/payouts")
        assert r.status_code == 200

    def test_admin_reports_page(self, admin_session):
        r = admin_session.get("/admin/reports")
        assert r.status_code == 200

    def test_admin_pipeline_page(self, admin_session):
        r = admin_session.get("/admin/pipeline")
        assert r.status_code == 200

    def test_admin_stats_api(self, admin_session):
        r = admin_session.get("/api/admin/stats")
        assert r.status_code == 200
        data = r.json()
        assert "total_clients" in data
        assert "active_studies" in data

    def test_admin_pricing_api_get(self, admin_session):
        r = admin_session.get("/api/admin/pricing")
        assert r.status_code == 200

    def test_admin_clients_api(self, admin_session):
        r = admin_session.get("/api/admin/clients")
        assert r.status_code == 200

    def test_admin_studies_api(self, admin_session):
        r = admin_session.get("/api/admin/studies")
        assert r.status_code == 200

    def test_admin_redemptions_api(self, admin_session):
        r = admin_session.get("/api/admin/redemptions")
        assert r.status_code == 200


class TestRespondentPanel:
    def test_enroll_page(self, client):
        r = client.get("/enroll")
        assert r.status_code == 200

    def test_respondent_home(self, client):
        r = client.get("/join")
        assert r.status_code == 200

    def test_enroll_respondent(self, client):
        import random
        phone = f"+91{random.randint(7000000000, 9999999999)}"
        r = client.post("/api/respondents/enroll", json={
            "name": "E2E Test Respondent",
            "phone": phone,
            "language": "en",
            "consent_contact": True,
            "country": "IN",
            "city": "Mumbai",
            "age_range": "25-34",
            "gender": "female",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "enrolled"
        assert "respondent_id" in data

    def test_enroll_missing_consent(self, client):
        import random
        phone = f"+91{random.randint(7000000000, 9999999999)}"
        r = client.post("/api/respondents/enroll", json={
            "name": "No Consent User",
            "phone": phone,
            "language": "en",
            "consent_contact": False,
        })
        assert r.status_code in (400, 422)

    def test_enroll_missing_required_field(self, client):
        r = client.post("/api/respondents/enroll", json={"name": "Incomplete"})
        assert r.status_code == 422

    def test_list_respondents(self, client):
        r = client.get("/api/respondents")
        assert r.status_code == 200
        assert "respondents" in r.json()

    def test_respondent_stats(self, client):
        r = client.get("/api/respondents/stats")
        assert r.status_code == 200
        assert "total" in r.json()

    def test_points_rates(self, client):
        r = client.get("/api/points/rates")
        assert r.status_code == 200
        data = r.json()
        assert "rates" in data
        assert "rate" in data["rates"]  # per-country rate info has a "rate" key


class TestAgenticPipeline:
    def test_list_agentic_projects(self, client):
        r = client.get("/agent/api/projects")
        assert r.status_code == 200
        assert "projects" in r.json()

    def test_list_agentic_reports(self, client):
        r = client.get("/agent/api/reports")
        assert r.status_code == 200
        assert "reports" in r.json()

    def test_brief_session_start(self, client):
        r = client.post("/agent/api/brief/start")
        assert r.status_code == 200
        data = r.json()
        assert "session_id" in data

    def test_brief_session_message(self, client):
        r = client.post("/agent/api/brief/start")
        sid = r.json()["session_id"]
        r = client.post("/agent/api/brief/message", json={
            "session_id": sid,
            "message": "I want to understand why our banking app users stop using it after 30 days",
        })
        assert r.status_code == 200
        data = r.json()
        assert "reply" in data
        assert len(data["reply"]) > 10
        assert "is_complete" in data

    def test_brief_session_state(self, client):
        r = client.post("/agent/api/brief/start")
        sid = r.json()["session_id"]
        r = client.get(f"/agent/api/brief/{sid}")
        assert r.status_code == 200
        data = r.json()
        assert "is_complete" in data

    def test_agentic_project_404(self, client):
        r = client.get("/agent/api/projects/nonexistent")
        assert r.status_code == 404


class TestMissionControl:
    def test_overview(self, client):
        r = client.get("/api/mission-control/overview")
        assert r.status_code == 200
        data = r.json()
        assert "headline" in data

    def test_starter_queries(self, client):
        r = client.get("/api/mission-control/starter-queries")
        assert r.status_code == 200
        assert "queries" in r.json()

    def test_query(self, client):
        r = client.post("/api/mission-control/query", json={
            "query": "What are the most common pain points across all studies?"
        })
        assert r.status_code == 200

    def test_query_empty_fails(self, client):
        r = client.post("/api/mission-control/query", json={"query": ""})
        assert r.status_code == 400


class TestWhatsApp:
    def test_whatsapp_stats(self, client):
        r = client.get("/api/whatsapp/stats")
        assert r.status_code == 200
        assert "active_sessions" in r.json()

    def test_meta_webhook_verify_bad_token(self, client):
        r = client.get("/webhook/meta-whatsapp?hub.mode=subscribe&hub.challenge=test&hub.verify_token=wrong")
        assert r.status_code == 403

    def test_register_phone(self, client, sample_project):
        pid = sample_project["project_id"]
        r = client.post(f"/api/join/{pid}/register-phone", json={"phone": "+919876543210"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "registered"
