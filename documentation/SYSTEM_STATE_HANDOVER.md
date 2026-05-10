# SYSTEM STATE & HANDOVER BRIEF
**Date:** 2026-03-29
**From:** Outgoing Lead Engineer
**To:** Incoming Lead Engineer
**Codebase:** `/Users/niveditapandey/Documents/AI Projects/getHeard`
**Live URL:** `https://getheard-648725089962.asia-south1.run.app`

> **Read this first, then the architecture docs.** This document captures what is actually running vs. what the architecture docs describe. It does not repeat what the docs already cover.
>
> Architecture reference: `ARCHITECTURE_HIGH_LEVEL.md`, `ARCHITECTURE_LOW_LEVEL.md`, `AGENTIC_FLOWS.md`, `DATA_MODELS.md`

---

## 1. CURRENT SYSTEM STATE

### Confirmed Working

| Component | Status | Notes |
|---|---|---|
| **Agent 1 — BriefAgent** | ✅ Working | Runs on Cloud Run, Gemini API live, `save_brief()` tool fires correctly |
| **Agent 2 — DesignerAgent** | ✅ Working | Triggered by "Design Study" button; saves `projects/{id}.json` with full questions |
| **Brief → Design full flow** | ✅ Working | End-to-end: brief chat → design → project JSON saved → redirect to pricing |
| **Project linking (simple users)** | ✅ Working | `POST /api/client/studies/{id}/link` stores project in session `linked_studies` |
| **`GET /api/client/projects`** | ✅ Working | Returns projects with full `questions` array for linked studies |
| **`GET /api/client/quote/{id}`** | ✅ Working | Computes quote from pricing config, no agent required |
| **`POST /api/client/quote/{id}/confirm`** | ✅ Working | Saves `quote` + `quote_params` to project JSON, advances pipeline to `pricing=completed` |
| **Admin dashboard** | ✅ Working | Overview stats load; all sidebar nav links present including Pipeline |
| **Admin pipeline page** | ✅ Working | `/admin/pipeline` — 5-stage CRM, stage reclassification, records table |
| **Respondent enroll** | ✅ Working | `/join/enroll` form submits correctly |
| **Landing page** | ✅ Working | Nav: "Order Research" + "Participate in Research" |
| **`/join/home`** | ✅ Working | Dedicated route; no longer caught by `/{project_id}` wildcard |

### Partially Working

| Component | What works | What doesn't |
|---|---|---|
| **Client dashboard** | Auth (simple + Firestore), stats, project list | "Revenue This Month" shows "—" — no revenue data in Firestore yet |
| **Pricing page (`/listen/study/{id}/pricing`)** | Quote loads from `compute_quote()` directly; UI renders correctly | PricingAgent (the conversational AI version) is **never triggered** — quote is computed deterministically from config, not via agent chat |
| **Timeline page** | Page renders | TimelineAgent is **never triggered** from the web UI — timeline section on page is placeholder only |
| **Project linking (Firestore users)** | Code path exists in `/api/client/studies/{id}/link` | `add_study_to_client()` writes to Firestore, but Firestore auth for the Cloud Run service account needs `roles/datastore.user` — verify this is still granted |
| **Payment** | Razorpay + Stripe routes exist in `app_study.py` | **Not tested end-to-end.** Webhook verification logic is present but payment gateway keys are not confirmed in `.env` |
| **WhatsApp intake** | `whatsapp_handler.py` exists | Not connected to any live Meta webhook; configuration is pending |

### Not Working / Not Built

| Component | State |
|---|---|
| **Agent 3 — PanelAgent (web-triggered)** | Agent class is complete and tested. No web UI or route triggers it post-payment. Panel building runs as a background async task after payment verification (`_trigger_panel_building()` in `app_study.py`), but payment is untested end-to-end |
| **Agent 4 — InterviewAgent (web-triggered)** | Agent class is complete. The voice pipeline (`src/voice/pipeline.py`) integrates it, but no client-facing web route exists to start an interview session from the portal |
| **Agent 5 — AnalysisAgent (web-triggered)** | Agent class is complete. `POST /agent/api/reports/generate` triggers it, but this route is not surfaced in the client portal UI — no button or page exists for a client to trigger report generation |
| **Study questions visible in client dashboard** | Questions are in the API response (`/api/client/projects` returns `questions[]`), but the `client_dashboard.html` JS does **not render them** — it only shows study name, type, and date |
| **Report visible to client** | `GET /report/{report_id}` route exists but its template was not confirmed working in testing |
| **`simple:` user session persistence on Cloud Run** | Session-stored `linked_studies` will be lost if Cloud Run scales to multiple instances (Starlette uses signed cookies — these survive, but verify `SESSION_SECRET` is set in Cloud Run env vars) |

---

## 2. ACTUAL DATA FLOW (AS IMPLEMENTED)

### The working path

```
[Client: /listen/study/new]
    |
    | POST /agent/api/brief/start        → in-memory BriefAgent session created
    | POST /agent/api/brief/message (×N) → BriefAgent collects fields via tool call
    |                                       saves brief_saved=True, collected_brief={}
    |
    | [JS detects brief_saved=true → shows "Design Study" button]
    |
    | POST /agent/api/design             → Orchestrator.design_study(brief)
    |                                       DesignerAgent runs 4-tool loop
    |                                       saves projects/{project_id}.json
    |                                       IMPORTANT: no `status` or `pipeline` field written here
    |
    | POST /api/client/studies/{id}/link → stores project_id in session["linked_studies"]
    |
    | [JS redirects to /listen/study/{id}/pricing]
    |
    | GET /api/client/quote/{id}         → compute_quote() called directly (no agent)
    |                                       returns quote dict
    |
    | [Client adjusts panel size / source, clicks confirm]
    |
    | POST /api/client/quote/{id}/confirm → saves quote + quote_params to project JSON
    |                                        writes pipeline.briefing=completed
    |                                        writes pipeline.pricing=completed
    |                                        writes status=timeline_estimate
    |
    | [JS redirects to /listen/study/{id}/timeline]
    |
    | [FLOW STOPS HERE — no timeline, no payment, no panel building in a tested state]
```

### Where and why the flow stops

**After timeline page:** The timeline page (`study_timeline.html`) renders a static UI. `TimelineAgent.estimate()` is never called from any web route. The page has no API endpoint backing it with real timeline data. Clicking "Proceed to Payment" likely hits payment initiation, which is untested.

**After payment (hypothetically):** If payment were to succeed, `_mark_payment_received()` sets `status=panel_building` and calls `asyncio.create_task(_trigger_panel_building(project_id))` — a background task. This calls `PanelAgent.query_panel()`. No client-facing feedback loop exists for panel approval.

**Interview & Analysis:** Completely manual. There is no client-facing flow to start interviews or generate reports from the portal. These exist only as API endpoints accessible to internal/admin use.

---

## 3. AGENT STATUS

### Agent 1 — BriefAgent (`src/agents/brief_agent.py`)

| Check | Status |
|---|---|
| Runs | ✅ Yes — triggered via `/agent/api/brief/message` |
| Output saved | ⚠️ In-memory only — `_brief_sessions` dict on the server process. Not persisted to disk. If Cloud Run instance restarts mid-session, brief is lost |
| Output visible | ✅ Yes — `brief_saved` + `collected_brief` returned in API response; JS renders side panel |
| Downstream trigger | ✅ Manual — "Design Study" button in UI |

**Known quirk:** Alex will sometimes still ask redundant questions if brief context is thin. System prompt has a rule against this but Gemini doesn't always follow it. Improve with few-shot examples.

### Agent 2 — DesignerAgent (`src/agents/designer_agent.py`)

| Check | Status |
|---|---|
| Runs | ✅ Yes — triggered via `POST /agent/api/design` |
| Output saved | ✅ Yes — `projects/{project_id}.json` with full `questions[]` array |
| Output visible | ⚠️ Partially — questions are in `GET /api/client/projects` response, but client dashboard HTML does not render them. Pricing page shows study name only |
| Downstream trigger | ✅ Automatic — JS redirects to pricing after design completes |

**Note:** Project JSON saved by Orchestrator has no `status` or `pipeline` fields. The `_infer_pipeline()` function in `app_study.py` derives these on read. This is intentional and works correctly.

### Agent 3 — PricingAgent (`src/agents/pricing_agent.py`)

| Check | Status |
|---|---|
| Runs | ❌ Not triggered from web UI |
| Output saved | N/A |
| Output visible | N/A |

**What happens instead:** `GET /api/client/quote/{id}` calls `compute_quote()` (deterministic, from `config/pricing.json`) directly — no AI agent. This is fine for MVP. The PricingAgent is for conversational quote negotiation and is a later-stage feature.

### Agent 4 — TimelineAgent (`src/agents/timeline_agent.py`)

| Check | Status |
|---|---|
| Runs | ✅ Yes — triggered via `GET /api/client/timeline/{project_id}` as a background task |
| Output saved | ✅ Yes — saves `timeline` dict into `projects/{id}.json` on completion |
| Output visible | ⚠️ Partially — `study_timeline.html` calls the endpoint and polls every 3s. First call returns `202 {"status": "computing"}`; subsequent calls return the timeline dict once saved. The issue: `renderTimeline()` in the template may not gracefully handle the `202` interim response — verify the JS doesn't crash on `{"status": "computing"}` before the timeline is ready |

**CORRECTION from earlier description:** The route and agent trigger already exist. Do NOT add a new route. The fix, if any, is in `renderTimeline()` in `study_timeline.html`.

**Dependency:** TimelineAgent requires `project.get("quote", {})` to be non-empty. It only gives meaningful output after `POST /api/client/quote/{id}/confirm` has been called and saved the quote to the project JSON. If quote is absent, agent runs but estimates may be off.

### Agent 5 — PanelAgent (`src/agents/panel_agent.py`)

| Check | Status |
|---|---|
| Runs | ⚠️ Only via background task after payment — untested end-to-end |
| Output saved | ✅ Yes (if triggered) — `panels/{panel_id}.json` |
| Output visible | ❌ No client-facing panel review UI |

### Agent 6 — InterviewAgent (`src/agents/interview_agent.py`)

| Check | Status |
|---|---|
| Runs | ✅ Yes — but only via the voice pipeline (`src/voice/pipeline.py`), not via web UI |
| Output saved | ✅ Yes — `transcripts/{session_id}.json` via voice pipeline |
| Output visible | ❌ No client-facing UI for interview sessions |

**Note:** The existing `feef0046` project has 8 completed sessions with transcripts — this is the only tested end-to-end path and was done via the older voice pipeline, not via the client portal.

### Agent 7 — AnalysisAgent (`src/agents/analysis_agent.py`)

| Check | Status |
|---|---|
| Runs | ✅ Yes — via `POST /agent/api/reports/generate` |
| Output saved | ✅ Yes — `reports/{report_id}.json` |
| Output visible | ⚠️ Report JSON exists. `GET /report/{report_id}` route exists. Client dashboard JS does not surface a "View Report" link unless `report_id` is present on the project |

### Orchestrator (`src/agents/orchestrator.py`)

The Orchestrator is **functional** for Stages 1 (Brief) and 2 (Design). Stages 3-4 (Interview, Analysis) are functional as isolated calls but are **not wired into the web UI pipeline**. There is no orchestrator-level state machine — stage transitions are managed by individual route handlers in `app_study.py`.

---

## 4. ROOT CAUSE OF FAILURE

### Why the flow stops after brief/design

**Primary cause: No agent chaining post-design in the web UI.**

The Orchestrator's `design_study()` saves the project and returns. The web layer (`app_agentic.py`) returns the project dict to the frontend. That's it. There is no automatic trigger for:
- TimelineAgent after pricing confirm
- PanelAgent after payment
- Anything to notify or route a client through panels → interviews → analysis

Each subsequent stage requires either a manual API call or a background task that has no client feedback loop.

### Why questions are not visible in the client dashboard

**The data exists. The UI doesn't render it.**

`GET /api/client/projects` returns the full project dict including `questions[]`. But `client_dashboard.html` JS only reads `project.name`, `project.research_type`, `project.created_at`, and `project.status`. It does not iterate or display `project.questions`. The study detail / question preview UI is not built in the dashboard.

### Why a newly designed study may not appear in the dashboard

For `simple:` users (demo login), the link from project → user relies on:
1. `brief_chat.html` calling `POST /api/client/studies/{id}/link` **after** design completes
2. That call storing `project_id` in `request.session["linked_studies"]`
3. Starlette cookie session persisting across page navigation

If step 1 fails (e.g., network error after design), the project exists on disk but is not linked to the user. The user will see an empty dashboard. There is **no recovery path** — the client cannot manually add a project to their account.

---

## 5. MINIMUM FIX REQUIRED

**Goal: Brief → Questions visible in client dashboard**

Three changes, all backend/template only:

### Fix 1: Render questions in client dashboard (1 file change)

**File:** `src/web/templates/client_dashboard.html`

In the JS that renders the project list, add a section under each study card that iterates `project.questions` and shows `q.main` + `q.type`. The data is already in the API response — it just needs to be rendered. Approximately 15 lines of HTML/JS.

### Fix 2: Make study link resilient (1 file change)

**File:** `src/web/app_agentic.py` (NOT app_study.py — the route lives here)

The route is `POST /agent/api/design` in `app_agentic.py`. Current signature:
```python
async def design_study(req: DesignRequest):
```

To access the session you must add `request: Request` as a second parameter:
```python
async def design_study(req: DesignRequest, request: Request):
```

FastAPI resolves this correctly — Pydantic body + Request can coexist. After `project = await orchestrator.design_study(req.brief)`, add the link logic reading from `request.session`. Import `Request` from `fastapi` (already imported in app_agentic.py — verify with grep).

**Impact:** Eliminates the race condition where design completes but the link call fails.

### Fix 3: Verify `SECRET_KEY` env var on Cloud Run

**File:** Cloud Run env config (not code)

The correct env var name is `SECRET_KEY` (not `SESSION_SECRET`). It maps to `settings.secret_key` in `config/settings.py`. The hardcoded default is `"getheard-secret-2026"` — same value currently in `.env`. Sessions will persist correctly as long as this value is stable across deploys.

Run: `gcloud run services describe getheard --region asia-south1 --format="yaml" | grep SECRET_KEY`

If not set on Cloud Run, the default `"getheard-secret-2026"` is used. This is acceptable short-term but should be set as a Cloud Run secret before production.

---

## 6. NEXT ACTION FOR NEW ENGINEER

**First task: Verify the end-to-end flow yourself before writing any code.**

Run this test sequence:

1. Go to `https://getheard-648725089962.asia-south1.run.app/listen/login`
2. Log in with `demo / demo123`
3. Click "New Study" → complete the brief chat with Alex
4. Click "Design Study" → wait for redirect to pricing
5. On pricing page: confirm the default quote
6. Check what the timeline page shows (is it blank or populated?)
7. Go back to `/listen` — does the new study appear in the dashboard?
8. If yes: click the study — do the questions render anywhere?

This will tell you immediately which of the above fixes are needed, in what order.

**Expected findings based on code audit:**
- Step 6: Timeline page will show a static UI with no real dates (TimelineAgent not called)
- Step 7: Study should appear IF the link call succeeded (check browser console for errors after step 4)
- Step 8: Questions will NOT be visible — Fix 1 above is confirmed needed

**Second task:** Once you can see the study in the dashboard with questions visible, the next meaningful milestone is enabling the client to see the study's pipeline progress (briefing → pricing → payment → delivery). The status page at `/listen/study/{id}/status` is built and `_infer_pipeline()` works — it just needs to be linked from the dashboard.

---

## ENVIRONMENT & DEPLOYMENT

| Item | Value |
|---|---|
| Cloud Run service | `getheard` in project **`leadconvert-platform`**, region `asia-south1` |
| Firestore database | In project **`getheard-484014`** (different GCP project — hardcoded in `src/storage/firestore_db.py` line 10) |
| Deploy command | `gcloud run deploy getheard --source . --region asia-south1 --quiet` |
| Service account | `151428781052-compute@developer.gserviceaccount.com` (belongs to `leadconvert-platform`) |
| IAM roles confirmed | `roles/datastore.user` and `roles/aiplatform.user` granted to service account **in `getheard-484014`** (cross-project) |
| Gemini auth | `GEMINI_API_KEY` is **blank in `.env`** — local dev uses Vertex AI ADC. Run `gcloud auth application-default login` before local dev. On Cloud Run, ADC is automatic via service account |
| Local dev | `source venv/bin/activate && uvicorn src.web.app:app --reload` from repo root |
| Admin login | `admin / getheard-admin-2026` at `/admin/login` |
| Demo client login | `demo / demo123` at `/listen/login` |
| Only one real project on disk | `projects/feef0046.json` (KYC Drop-off Study, 10 questions, 8 completed sessions via voice pipeline) |
| Existing reports on disk | `reports/27a4dde0.json`, `reports/39fb7a97.json` — NOT linked to `feef0046` project JSON (no `report_id` field on the project). To test AnalysisAgent output, load reports directly via `GET /agent/api/reports/{id}` |
| Razorpay keys | `RAZORPAY_KEY_ID=rzp_live_SG70K7NZsGvuj0` — these are **LIVE keys**, not test keys. Do NOT run payment tests without switching to `rzp_test_` keys first |
| Stripe | Keys are blank in `.env` — Stripe payment path is not functional |
| Two GCP projects explained | `leadconvert-platform` = Cloud Run host. `getheard-484014` = Firestore + Vertex AI. When granting IAM for Firestore, grant in `getheard-484014`, not `leadconvert-platform` |

---

*This document reflects system state as of 2026-03-29. Update this file — not ARCHITECTURE docs — as bugs are fixed and features are completed.*
