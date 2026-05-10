#!/usr/bin/env python3
"""Apply all sandbox code changes to the local repo."""
import base64
import re
from pathlib import Path

ROOT = Path(__file__).parent
ok = []
err = []

def patch(filepath, old, new, desc):
    p = ROOT / filepath
    content = p.read_text(encoding="utf-8")
    if old not in content:
        err.append(f"SKIP (not found): {desc}")
        return
    p.write_text(content.replace(old, new, 1), encoding="utf-8")
    ok.append(f"OK: {desc}")

patch("src/web/app_agentic.py",
    '        if "error" in result:\n            raise HTTPException(status_code=404, detail=result["error"])\n        return result',
    '        if "error" in result:\n            raise HTTPException(status_code=404, detail=result["error"])\n        result["is_complete"] = result.get("brief_saved", False)\n        return result',
    "app_agentic.py: is_complete alias")

patch("src/web/app_study.py",
    '    client_id = request.session.get("client_id")\n    if not client_id:\n        return None\n    return get_client(client_id)',
    '    client_id = request.session.get("client_id")\n    if not client_id:\n        return None\n    if client_id.startswith("simple:"):\n        username = client_id[len("simple:"):]\n        return {\n            "client_id": client_id,\n            "name": request.session.get("client_name", username.capitalize()),\n            "company": request.session.get("client_company", "GetHeard Demo"),\n            "email": username,\n            "studies": [],\n        }\n    return get_client(client_id)',
    "app_study.py: simple: user fix")

patch("src/web/app.py",
    '@app.get("/api/stats")',
    '''@app.post("/api/join/{project_id}/register-phone")
async def register_phone_for_project(project_id: str, request: Request):
    body = await request.json()
    phone = body.get("phone", "").strip()
    if not phone:
        raise HTTPException(400, "phone is required")
    if not phone.startswith("+"):
        phone = "+" + phone
    wa_number = f"whatsapp:{phone}"
    from src.web.whatsapp_handler import get_whatsapp_manager
    get_whatsapp_manager().register_phone(wa_number, project_id)
    return {"status": "registered", "phone": wa_number, "project_id": project_id}


@app.get("/api/stats")''',
    "app.py: register-phone endpoint")

patch("src/web/app.py",
    "reply = manager.handle_message(from_number=From, body=Body)",
    "reply = await manager.handle_message(from_number=From, body=Body)",
    "app.py: await Twilio handler")

patch("src/web/app.py",
    "reply = manager.handle_message(from_number=from_number, body=body)",
    "reply = await manager.handle_message(from_number=from_number, body=body)",
    "app.py: await Meta handler")

patch("src/web/app.py",
    '''    try:
        report = await asyncio.to_thread(
            generate_report,
            transcripts=transcripts,
            project_name=project_name,
            research_type=research_type,
            objective=objective,
            audience=audience,
            questions=questions,
            project_id=project_id,
        )
        return {"report_id": report["report_id"], "report": report}
    except Exception as exc:
        logger.exception("Report generation failed")
        raise HTTPException(500, str(exc))''',
    '''    try:
        if project_id:
            from src.agents.orchestrator import orchestrator as _orc
            raw_files = payload.get("transcript_files", [])
            clean_files = [f for f in (raw_files or []) if f] or None
            report = await _orc.generate_report(
                project_id=project_id,
                transcript_files=clean_files,
            )
        else:
            report = await asyncio.to_thread(
                generate_report,
                transcripts=transcripts,
                project_name=project_name,
                research_type=research_type,
                objective=objective,
                audience=audience,
                questions=questions,
                project_id=project_id,
            )
        return {"report_id": report["report_id"], "report": report}
    except Exception as exc:
        logger.exception("Report generation failed")
        raise HTTPException(500, str(exc))''',
    "app.py: route to AnalysisAgent")

patch("src/core/research_project.py",
    "    def add_session(self, session_id: str):\n        self._data.setdefault(\"sessions\", []).append(session_id)\n        self._data[\"updated_at\"] = datetime.now().isoformat()\n        _save_project(self._data)",
    "    def add_session(self, session_id: str):\n        sessions = self._data.setdefault(\"sessions\", [])\n        if session_id not in sessions:\n            sessions.append(session_id)\n            self._data[\"interviews_completed\"] = len(sessions)\n            self._data[\"updated_at\"] = datetime.now().isoformat()\n            _save_project(self._data)",
    "research_project.py: add_session dedup")

patch("src/agents/orchestrator.py",
    "        report_path = REPORTS_DIR / f\"{report_id}.json\"\n        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))\n\n        logger.info(f\"[Orchestrator] Report saved: {report_id}\")",
    '''        report_path = REPORTS_DIR / f"{report_id}.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

        try:
            project["report_id"] = report_id
            project["status"] = "completed"
            project["report_generated_at"] = report["generated_at"]
            proj_path.write_text(json.dumps(project, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"[Orchestrator] Could not update project status: {e}")

        logger.info(f"[Orchestrator] Report saved: {report_id}")''',
    "orchestrator.py: update project status after report")

patch("src/web/templates/project_detail.html",
    "transcript_files: relevant.map(t => t.file),",
    "transcript_files: relevant.map(t => t.session_id).filter(Boolean),",
    "project_detail.html: session_id fix")

patch("src/web/templates/report.html",
    "${(t.quotes||[]).slice(0,1).map(q=>`<div class=\"theme-quote\">${escHtml(q)}</div>`).join('')}",
    "${(t.example_quotes||t.quotes||[]).slice(0,1).map(q=>`<div class=\"theme-quote\">${escHtml(q)}</div>`).join('')}",
    "report.html: example_quotes fallback")

patch("src/web/templates/report.html",
    "<span class=\"q-num\">${q.question_number}</span>",
    "<span class=\"q-num\">${q.question_number||''}</span>",
    "report.html: q.question_number fallback")

patch("src/web/templates/report.html",
    "<span class=\"q-text\">${escHtml(q.question_text||'')}</span>",
    "<span class=\"q-text\">${escHtml(q.question_text||q.question||'')}</span>",
    "report.html: q.question fallback")

patch("src/web/templates/report.html",
    "<p class=\"q-summary\">${escHtml(q.summary||'')}</p>",
    "<p class=\"q-summary\">${escHtml(q.summary||q.insight||'')}</p>",
    "report.html: q.insight fallback")

patch("src/web/templates/report.html",
    "${q.notable_quote ? `<div class=\"q-notable\">\"${escHtml(q.notable_quote)}\"</div>` : ''}",
    "${(q.notable_quote||q.top_quote) ? `<div class=\"q-notable\">\"${escHtml(q.notable_quote||q.top_quote)}\"</div>` : ''}",
    "report.html: top_quote fallback")

patch("src/web/templates/report.html",
    "<div class=\"rec-title\">${escHtml(rec.recommendation)}</div>",
    "<div class=\"rec-title\">${escHtml(rec.action||rec.recommendation||'')}</div>",
    "report.html: rec.action fallback")

patch("src/web/templates/study_new.html",
    "    // ── Handle completion ──\n    function handleCompletion(data) {\n      if (!data.brief_saved) return;",
    "    // ── Handle completion ──\n    async function handleCompletion(data) {\n      if (!data.is_complete && !data.brief_saved) return;",
    "study_new.html: async handleCompletion")

patch("src/web/templates/study_new.html",
    "    function handleCompletion(data) {",
    "    async function handleCompletion(data) {",
    "study_new.html: make handleCompletion async")

patch("src/web/templates/study_new.html",
    "        const greeting = data.reply || '';",
    "        const greeting = data.reply || data.message || data.response || 'Hello! I\\'m here to help you brief your study. What kind of research are you looking to do?';",
    "study_new.html: greeting fallback")

def write_file(filepath, b64_content, desc):
    p = ROOT / filepath
    try:
        decoded = base64.b64decode(b64_content)
        p.write_bytes(decoded)
        ok.append(f"OK: {desc}")
    except Exception as e:
        err.append(f"FAIL: {desc} — {e}")

_WA_B64 = (
    "IiIiCldoYXRzQXBwIGludGVydmlldyBoYW5kbGVyIOKAlCByb3V0ZXMgVHdpbGlv"
    "IG1lc3NhZ2VzIHRvIEludGVydmlld0FnZW50LgoKRmxvdzoKICBUd2lsaW8gd2Vi"
    "aG9vayDihpIgaGFuZGxlX21lc3NhZ2UoKSDihpIgSW50ZXJ2aWV3QWdlbnQucHJv"
    "Y2Vzc19yZXNwb25zZSgpIOKGkiBUd2lNTCByZXBseQoKU2Vzc2lvbnMgYXJlIGtl"
    "eWVkIGJ5IHBob25lIG51bWJlciAoZnJvbSBUd2lsaW8ncyBGcm9tIGZpZWxkKS4K"
    "UHJvamVjdCByb3V0aW5nOiAiU1RBUlQgPHByb2plY3RfaWQ+IiBvciBwcmUtbGlu"
    "a2VkIHZpYSAvam9pbiBwYWdlLgoi"
    "IiIKCmltcG9ydCBsb2dnaW5nCmZyb20gcGF0aGxpYiBpbXBvcnQgUGF0aApmcm9t"
    "IHR5cGluZyBpbXBvcnQgRGljdCwgT3B0aW9uYWwKCmxvZ2dlciA9IGxvZ2dpbmcu"
    "Z2V0TG9nZ2VyKF9fbmFtZV9fKQoKQkFTRV9ESVIgPSBQYXRoKF9fZmlsZV9fKS5w"
    "YXJlbnQucGFyZW50LnBhcmVudApQUk9KRUNUU19ESVIgPSBCQVNFX0RJUiAvICJw"
    "cm9qZWN0cyIKCgpjbGFzcyBXaGF0c0FwcFNlc3Npb246CiAgICAiIiJUcmFja3Mg"
    "YSBzaW5nbGUgV2hhdHNBcHAgaW50ZXJ2aWV3IHNlc3Npb24gYmFja2VkIGJ5IElu"
    "dGVydmlld0FnZW50LiIiIgoKICAgIGRlZiBfX2luaXRfXyhzZWxmLCBwaG9uZV9u"
    "dW1iZXI6IHN0ciwgcHJvamVjdF9pZDogc3RyKToKICAgICAgICBzZWxmLnBob25l"
    "X251bWJlciA9IHBob25lX251bWJlcgogICAgICAgIHNlbGYucHJvamVjdF9pZCA9"
    "IHByb2plY3RfaWQKICAgICAgICBzZWxmLmFnZW50ID0gTm9uZQogICAgICAgIHNl"
    "bGYuc3RhcnRlZCA9IEZhbHNlCgogICAgZGVmIF9sb2FkX2FnZW50KHNlbGYpOgog"
    "ICAgICAgIGZyb20gc3JjLmFnZW50cy5vcmNoZXN0cmF0b3IgaW1wb3J0IG9yY2hl"
    "c3RyYXRvcgogICAgICAgIHNlbGYuYWdlbnQgPSBvcmNoZXN0cmF0b3IuY3JlYXRl"
    "X2ludGVydmlld19hZ2VudChzZWxmLnByb2plY3RfaWQpCiAgICAgICAgaWYgc2Vs"
    "Zi5hZ2VudCBpcyBOb25lOgogICAgICAgICAgICByYWlzZSBWYWx1ZUVycm9yKGYi"
    "UHJvamVjdCBub3QgZm91bmQ6IHtzZWxmLnByb2plY3RfaWR9IikKCiAgICBkZWYg"
    "c3RhcnQoc2VsZikgLT4gc3RyOgogICAgICAgIHNlbGYuX2xvYWRfYWdlbnQoKQog"
    "ICAgICAgIHNlbGYuc3RhcnRlZCA9IFRydWUKICAgICAgICBvcGVuaW5nID0gc2Vs"
    "Zi5hZ2VudC5nZXRfb3BlbmluZygpCiAgICAgICAgbG9nZ2VyLmluZm8oZiJbV0Fd"
    "IFNlc3Npb24gc3RhcnRlZDoge3NlbGYucGhvbmVfbnVtYmVyfSBwcm9qZWN0PXtz"
    "ZWxmLnByb2plY3RfaWR9IikKICAgICAgICByZXR1cm4gb3BlbmluZwoKICAgIGFz"
    "eW5jIGRlZiByZXNwb25kKHNlbGYsIHRleHQ6IHN0cik6CiAgICAgICAgIiIiUmV0"
    "dXJucyAocmVwbHlfdGV4dCwgaXNfY29tcGxldGUpLiIiIgogICAgICAgIHJldHVy"
    "biBhd2FpdCBzZWxmLmFnZW50LnByb2Nlc3NfcmVzcG9uc2UodGV4dCkKCiAgICBk"
    "ZWYgaXNfY29tcGxldGUoc2VsZikgLT4gYm9vbDoKICAgICAgICByZXR1cm4gc2Vs"
    "Zi5hZ2VudC5pc19jb21wbGV0ZSBpZiBzZWxmLmFnZW50IGVsc2UgRmFsc2UKCiAg"
    "ICBkZWYgY29udmVyc2F0aW9uKHNlbGYpOgogICAgICAgIHJldHVybiBzZWxmLmFn"
    "ZW50LmNvbnZlcnNhdGlvbiBpZiBzZWxmLmFnZW50IGVsc2UgW10KCgpjbGFzcyBX"
    "aGF0c0FwcEludGVydmlld01hbmFnZXI6CiAgICAiIiIKICAgIEluLW1lbW9yeSBy"
    "ZWdpc3RyeSBvZiBhY3RpdmUgV2hhdHNBcHAgaW50ZXJ2aWV3IHNlc3Npb25zLgog"
    "ICAgRWFjaCBwaG9uZSBudW1iZXIgbWFwcyB0byBvbmUgYWN0aXZlIFdoYXRzQXBw"
    "U2Vzc2lvbi4KICAgICIiIgoKICAgIEhFTFBfVEVYVCA9ICgKICAgICAgICAi8J+R"
    "lyBXZWxjb21lIHRvIEdldEhlYXJkIVxuXG4iCiAgICAgICAgIlRvIHN0YXJ0IGFu"
    "IGludGVydmlldywgc2VuZDpcbiIKICAgICAgICAiICAqU1RBUlQgPHN0dWR5X2lk"
    "PipcXG5cbiIKICAgICAgICAiQ29tbWFuZHM6XG4iCiAgICAgICAgIiAgc3RvcCDi"
    "gJQgZW5kIGludGVydmlldyBlYXJseVxuIgogICAgICAgICIgIGhlbHAg4oCUIHNo"
    "b3cgdGhpcyBtZXNzYWdlIgogICAgKQoKICAgIGRlZiBfX2luaXRfXyhzZWxmKToK"
    "ICAgICAgICBzZWxmLnNlc3Npb25zOiBEaWN0W3N0ciwgV2hhdHNBcHBTZXNzaW9u"
    "XSA9IHt9CiAgICAgICAgIyBwaG9uZV9udW1iZXIg4oaSIHByb2plY3RfaWQgbWFw"
    "cGluZyAoc2V0IHdoZW4gcmVzcG9uZGVudCBqb2lucyB2aWEgL2pvaW4gbGluaykK"
    "ICAgICAgICBzZWxmLl9waG9uZV9wcm9qZWN0X21hcDogRGljdFtzdHIsIHN0cl0g"
    "PSB7fQogICAgICAgIGxvZ2dlci5pbmZvKCJbV0FdIFdoYXRzQXBwIEludGVydmll"
    "dyBNYW5hZ2VyIHJlYWR5IikKCiAgICBkZWYgcmVnaXN0ZXJfcGhvbmUoc2VsZiwg"
    "cGhvbmVfbnVtYmVyOiBzdHIsIHByb2plY3RfaWQ6IHN0cik6CiAgICAgICAgIiIi"
    "Q2FsbGVkIHdoZW4gYSByZXNwb25kZW50IHN1Ym1pdHMgdGhlaXIgbnVtYmVyIG9u"
    "IHRoZSAvam9pbiBwYWdlLiIiIgogICAgICAgIHNlbGYuX3Bob25lX3Byb2plY3Rf"
    "bWFwW3Bob25lX251bWJlcl0gPSBwcm9qZWN0X2lkCiAgICAgICAgbG9nZ2VyLmlu"
    "Zm8oZiJbV0FdIFJlZ2lzdGVyZWQge3Bob25lX251bWJlcn0g4oaSIHByb2plY3Qg"
    "e3Byb2plY3RfaWR9IikKCiAgICBhc3luYyBkZWYgaGFuZGxlX21lc3NhZ2Uoc2Vs"
    "ZiwgZnJvbV9udW1iZXI6IHN0ciwgYm9keTogc3RyKSAtPiBzdHI6CiAgICAgICAg"
    "dGV4dCA9IGJvZHkuc3RyaXAoKQogICAgICAgIGxvd2VyID0gdGV4dC5sb3dlcigp"
    "CgogICAgICAgIGlmIGxvd2VyIGluICgic3RvcCIsICJlbmQiLCAicXVpdCIsICJi"
    "eWUiKToKICAgICAgICAgICAgcmV0dXJuIGF3YWl0IHNlbGYuX3N0b3AoZnJvbV9u"
    "dW1iZXIpCgogICAgICAgIGlmIGxvd2VyIGluICgiaGVscCIsICI/IiwgIiIpOgog"
    "ICAgICAgICAgICByZXR1cm4gc2VsZi5IRUxQX1RFWFQKCiAgICAgICAgIyBTVEFS"
    "VCA8cHJvamVjdF9pZD4gY29tbWFuZAogICAgICAgIGlmIGxvd2VyLnN0YXJ0c3dp"
    "dGgoInN0YXJ0Iik6CiAgICAgICAgICAgIHBhcnRzID0gdGV4dC5zcGxpdChOb25l"
    "LCAxKQogICAgICAgICAgICBwcm9qZWN0X2lkID0gcGFydHNbMV0uc3RyaXAoKSBp"
    "ZiBsZW4ocGFydHMpID4gMSBlbHNlIE5vbmUKICAgICAgICAgICAgaWYgbm90IHBy"
    "b2plY3RfaWQ6CiAgICAgICAgICAgICAgICByZXR1cm4gIlBsZWFzZSBzZW5kOiAq"
    "U1RBUlQgPHN0dWR5X2lkPiogIChsb29rIGZvciBpdCBpbiB0aGUgaW52aXRhdGlv"
    "biBsaW5rKSIKICAgICAgICAgICAgcmV0dXJuIGF3YWl0IHNlbGYuX2JlZ2luX3Nl"
    "c3Npb24oZnJvbV9udW1iZXIsIHByb2plY3RfaWQpCgogICAgICAgICMgRXhpc3Rp"
    "bmcgc2Vzc2lvbgogICAgICAgIGlmIGZyb21fbnVtYmVyIGluIHNlbGYuc2Vzc2lv"
    "bnM6CiAgICAgICAgICAgIHJldHVybiBhd2FpdCBzZWxmLl9jb250aW51ZV9zZXNz"
    "aW9uKGZyb21fbnVtYmVyLCB0ZXh0KQoKICAgICAgICAjIENoZWNrIGlmIHBob25l"
    "IHdhcyBwcmUtcmVnaXN0ZXJlZCB2aWEgL2pvaW4gcGFnZQogICAgICAgIGlmIGZy"
    "b21fbnVtYmVyIGluIHNlbGYuX3Bob25lX3Byb2plY3RfbWFwOgogICAgICAgICAg"
    "ICBwcm9qZWN0X2lkID0gc2VsZi5fcGhvbmVfcHJvamVjdF9tYXBbZnJvbV9udW1i"
    "ZXJdCiAgICAgICAgICAgIHJldHVybiBhd2FpdCBzZWxmLl9iZWdpbl9zZXNzaW9u"
    "KGZyb21fbnVtYmVyLCBwcm9qZWN0X2lkKQoKICAgICAgICAjIFVua25vd24gdXNl"
    "ciDilJAgcHJvbXB0CiAgICAgICAgcmV0dXJuICgKICAgICAgICAgICAgIvCfkZcg"
    "SGkhIEknbSB0aGUgR2V0SGVhcmQgQUkgaW50ZXJ2aWV3ZXIuXG5cbiIKICAgICAg"
    "ICAgICAgIlRvIHN0YXJ0IHlvdXIgaW50ZXJ2aWV3LCBzZW5kOlxuIgogICAgICAg"
    "ICAgICAiICAqU1RBUlQgPHN0dWR5X2lkPipcXG5cbiIKICAgICAgICAgICAgIllv"
    "dSdsbCBmaW5kIHRoZSBzdHVkeSBJRCBpbiB0aGUgbGluayB5b3UgcmVjZWl2ZWQu"
    "IgogICAgICAgICkKCiAgICBhc3luYyBkZWYgX2JlZ2luX3Nlc3Npb24oc2VsZiwg"
    "ZnJvbV9udW1iZXI6IHN0ciwgcHJvamVjdF9pZDogc3RyKSAtPiBzdHI6CiAgICAg"
    "ICAgdHJ5OgogICAgICAgICAgICBzZXNzaW9uID0gV2hhdHNBcHBTZXNzaW9uKGZy"
    "b21fbnVtYmVyLCBwcm9qZWN0X2lkKQogICAgICAgICAgICBvcGVuaW5nID0gc2Vz"
    "c2lvbi5zdGFydCgpCiAgICAgICAgICAgIHNlbGYuc2Vzc2lvbnNbZnJvbV9udW1i"
    "ZXJdID0gc2Vzc2lvbgogICAgICAgICAgICByZXR1cm4gb3BlbmluZwogICAgICAg"
    "IGV4Y2VwdCBWYWx1ZUVycm9yIGFzIGU6CiAgICAgICAgICAgIGxvZ2dlci53YXJu"
    "aW5nKGYiW1dBXSBTZXNzaW9uIHN0YXJ0IGZhaWxlZCBmb3Ige2Zyb21fbnVtYmVy"
    "fToge2V9IikKICAgICAgICAgICAgcmV0dXJuIGYiU29ycnksIEkgY291bGRuJ3Qg"
    "ZmluZCB0aGF0IHN0dWR5LiBQbGVhc2UgY2hlY2sgdGhlIHN0dWR5IElEIGFuZCB0"
    "cnkgYWdhaW4uIgogICAgICAgIGV4Y2VwdCBFeGNlcHRpb24gYXMgZToKICAgICAg"
    "ICAgICAgbG9nZ2VyLmVycm9yKGYiW1dBXSBTZXNzaW9uIHN0YXJ0IGVycm9yOiB7"
    "ZX0iLCBleGNfaW5mbz1UcnVlKQogICAgICAgICAgICByZXR1cm4gIlNvcnJ5LCBz"
    "b21ldGhpbmcgd2VudCB3cm9uZyBzdGFydGluZyB5b3VyIGludGVydmlldy4gUGxl"
    "YXNlIHRyeSBhZ2Fpbi4iCgogICAgYXN5bmMgZGVmIF9jb250aW51ZV9zZXNzaW9u"
    "KHNlbGYsIGZyb21fbnVtYmVyOiBzdHIsIHRleHQ6IHN0cikgLT4gc3RyOgogICAg"
    "ICAgIHNlc3Npb24gPSBzZWxmLnNlc3Npb25zW2Zyb21fbnVtYmVyXQogICAgICAg"
    "IHRyeToKICAgICAgICAgICAgcmVwbHksIGlzX2RvbmUgPSBhd2FpdCBzZXNzaW9u"
    "LnJlc3BvbmQodGV4dCkKICAgICAgICAgICAgaWYgaXNfZG9uZToKICAgICAgICAg"
    "ICAgICAgIGF3YWl0IHNlbGYuX3NhdmVfYW5kX2NsZWFuKGZyb21fbnVtYmVyKQog"
    "ICAgICAgICAgICByZXR1cm4gcmVwbHkKICAgICAgICBleGNlcHQgRXhjZXB0aW9u"
    "IGFzIGU6CiAgICAgICAgICAgIGxvZ2dlci5lcnJvcihmIltXQV0gUmVzcG9uc2Ug"
    "ZXJyb3IgZm9yIHtmcm9tX251bWJlcn06IHtlfSIsIGV4Y19pbmZvPVRydWUpCiAg"
    "ICAgICAgICAgIHJldHVybiAiU29ycnksIEkgaGFkIHRyb3VibGUgd2l0aCB0aGF0"
    "LiBDb3VsZCB5b3Ugc2F5IHRoYXQgYWdhaW4/IgoKICAgIGFzeW5jIGRlZiBfc3Rv"
    "cChzZWxmLCBmcm9tX251bWJlcjogc3RyKSAtPiBzdHI6CiAgICAgICAgaWYgZnJv"
    "bV9udW1iZXIgbm90IGluIHNlbGYuc2Vzc2lvbnM6CiAgICAgICAgICAgIHJldHVy"
    "biAiTm8gYWN0aXZlIGludGVydmlldy4gU2VuZCAqU1RBUlQgPHN0dWR5X2lkPiog"
    "dG8gYmVnaW4uIgogICAgICAgIGF3YWl0IHNlbGYuX3NhdmVfYW5kX2NsZWFuKGZy"
    "b21fbnVtYmVyKQogICAgICAgIHJldHVybiAiVGhhbmsgeW91IGZvciB5b3VyIHRp"
    "bWUhIFlvdXIgcmVzcG9uc2VzIGhhdmUgYmVlbiBzYXZlZC4gSGF2ZSBhIGdyZWF0"
    "IGRheSEg8J+YiiIKCiAgICBhc3luYyBkZWYgX3NhdmVfYW5kX2NsZWFuKHNlbGYs"
    "IGZyb21fbnVtYmVyOiBzdHIpOgogICAgICAgIHNlc3Npb24gPSBzZWxmLnNlc3Np"
    "b25zLnBvcChmcm9tX251bWJlciwgTm9uZSkKICAgICAgICBzZWxmLl9waG9uZV9w"
    "cm9qZWN0X21hcC5wb3AoZnJvbV9udW1iZXIsIE5vbmUpCiAgICAgICAgaWYgbm90"
    "IHNlc3Npb246CiAgICAgICAgICAgIHJldHVybgoKICAgICAgICBjbGVhbl9waG9u"
    "ZSA9IGZyb21fbnVtYmVyLnJlcGxhY2UoIndoYXRzYXBwOiIsICIiKS5yZXBsYWNl"
    "KCIrIiwgIiIpCiAgICAgICAgY29udmVyc2F0aW9uID0gc2Vzc2lvbi5jb252ZXJz"
    "YXRpb24oKQoKICAgICAgICB0cnk6CiAgICAgICAgICAgIGZyb20gc3JjLnN0b3Jh"
    "Z2UudHJhbnNjcmlwdCBpbXBvcnQgVHJhbnNjcmlwdE1hbmFnZXIKICAgICAgICAg"
    "ICAgdG0gPSBUcmFuc2NyaXB0TWFuYWdlcigpCiAgICAgICAgICAgIHRtLnNhdmUo"
    "CiAgICAgICAgICAgICAgICBzZXNzaW9uX2lkPWNsZWFuX3Bob25lLAogICAgICAg"
    "ICAgICAgICAgbGFuZ3VhZ2VfY29kZT1zZXNzaW9uLmFnZW50Lmxhbmd1YWdlIGlm"
    "IHNlc3Npb24uYWdlbnQgZWxzZSAiZW4iLAogICAgICAgICAgICAgICAgY29udmVy"
    "c2F0aW9uPWNvbnZlcnNhdGlvbiwKICAgICAgICAgICAgICAgIG1ldGFkYXRhPXsK"
    "ICAgICAgICAgICAgICAgICAgICAiY2hhbm5lbCI6ICJ3aGF0c2FwcCIsCiAgICAg"
    "ICAgICAgICAgICAgICAgInBob25lX251bWJlciI6IGZyb21fbnVtYmVyLAogICAg"
    "ICAgICAgICAgICAgICAgICJwcm9qZWN0X2lkIjogc2Vzc2lvbi5wcm9qZWN0X2lk"
    "LAogICAgICAgICAgICAgICAgfSwKICAgICAgICAgICAgKQogICAgICAgICAgICBp"
    "ZiBzZXNzaW9uLnByb2plY3RfaWQ6CiAgICAgICAgICAgICAgICBmcm9tIHNyYy5j"
    "b3JlLnJlc2VhcmNoX3Byb2plY3QgaW1wb3J0IGdldF9wcm9qZWN0CiAgICAgICAg"
    "ICAgICAgICBwcm9qID0gZ2V0X3Byb2plY3Qoc2Vzc2lvbi5wcm9qZWN0X2lkKQog"
    "ICAgICAgICAgICAgICAgaWYgcHJvajoKICAgICAgICAgICAgICAgICAgICBwcm9q"
    "LmFkZF9zZXNzaW9uKGNsZWFuX3Bob25lKQogICAgICAgIGV4Y2VwdCBFeGNlcHRp"
    "b24gYXMgZToKICAgICAgICAgICAgbG9nZ2VyLmVycm9yKGYiW1dBXSBUcmFuc2Ny"
    "aXB0IHNhdmUgZmFpbGVkOiB7ZX0iLCBleGNfaW5mbz1UcnVlKQoKICAgICAgICAj"
    "IENyZWRpdCBwb2ludHMgaWYgcmVzcG9uZGVudCBpcyBpbiBwYW5lbAogICAgICAg"
    "IHRyeToKICAgICAgICAgICAgZnJvbSBzcmMuc3RvcmFnZS5yZXNwb25kZW50X3N0"
    "b3JlIGltcG9ydCBfZmluZF9ieV9waG9uZQogICAgICAgICAgICByZXNwb25kZW50"
    "ID0gX2ZpbmRfYnlfcGhvbmUoZnJvbV9udW1iZXIucmVwbGFjZSgid2hhdHNhcHA6"
    "IiwgIiIpKQogICAgICAgICAgICBpZiByZXNwb25kZW50OgogICAgICAgICAgICAg"
    "ICAgZnJvbSBzcmMuc3RvcmFnZS5wb2ludHNfc3RvcmUgaW1wb3J0IGFkZF9wb2lu"
    "dHMKICAgICAgICAgICAgICAgIGFkZF9wb2ludHMoCiAgICAgICAgICAgICAgICAg"
    "ICAgcmVzcG9uZGVudF9pZD1yZXNwb25kZW50WyJyZXNwb25kZW50X2lkIl0sCiAg"
    "ICAgICAgICAgICAgICAgICAgYW1vdW50PTUwLAogICAgICAgICAgICAgICAgICAg"
    "IHJlYXNvbj0iV2hhdHNBcHAgaW50ZXJ2aWV3IGNvbXBsZXRlZCIsCiAgICAgICAg"
    "ICAgICAgICAgICAgc3R1ZHlfaWQ9c2Vzc2lvbi5wcm9qZWN0X2lkIG9yICIiLAog"
    "ICAgICAgICAgICAgICAgKQogICAgICAgIGV4Y2VwdCBFeGNlcHRpb24gYXMgZToK"
    "ICAgICAgICAgICAgbG9nZ2VyLndhcm5pbmcoZiJbV0FdIFBvaW50cyBjcmVkaXQg"
    "ZmFpbGVkOiB7ZX0iKQoKICAgIGRlZiBhY3RpdmVfY291bnQoc2VsZikgLT4gaW50"
    "OgogICAgICAgIHJldHVybiBsZW4oc2VsZi5zZXNzaW9ucykKCiAgICBkZWYgYWN0"
    "aXZlX251bWJlcnMoc2VsZikgLT4gbGlzdDoKICAgICAgICByZXR1cm4gbGlzdChz"
    "ZWxmLnNlc3Npb25zLmtleXMoKSkKCgpfbWFuYWdlcjogT3B0aW9uYWxbV2hhdHNB"
    "cHBJbnRlcnZpZXdNYW5hZ2VyXSA9IE5vbmUKCgpkZWYgZ2V0X3doYXRzYXBwX21h"
    "bmFnZXIoKSAtPiBXaGF0c0FwcEludGVydmlld01hbmFnZXI6CiAgICBnbG9iYWwg"
    "X21hbmFnZXIKICAgIGlmIF9tYW5hZ2VyIGlzIE5vbmU6CiAgICAgICAgX21hbmFn"
    "ZXIgPSBXaGF0c0FwcEludGVydmlld01hbmFnZXIoKQogICAgcmV0dXJuIF9tYW5h"
    "Z2VyCg=="
)
write_file("src/web/whatsapp_handler.py", _WA_B64, "whatsapp_handler.py full rewrite")

_PIPELINE_B64 = (
    "IiIiClZvaWNlIGludGVydmlldyBwaXBlbGluZSAtIG9yY2hlc3RyYXRlcyBTVFQg"
    "4oaSIEdlbWluaSDihpIgVFRTIGZvciBhbnkgbGFuZ3VhZ2UuCkhhbmRsZXMgcHJv"
    "dmlkZXIgcm91dGluZzogU2FydmFtIGZvciBJbmRpYW4gbGFuZ3VhZ2VzLCBHb29n"
    "bGUgQ2xvdWQgZm9yIG90aGVycy4KCkFsbCBwdWJsaWMgbWV0aG9kcyBhcmUgYXN5"
    "bmMgc28gdGhleSBpbnRlZ3JhdGUgY2xlYW5seSB3aXRoIEZhc3RBUEkuCiIiIgoK"
    "aW1wb3J0IGFzeW5jaW8KaW1wb3J0IGxvZ2dpbmcKaW1wb3J0IHV1aWQKZnJvbSBk"
    "YXRldGltZSBpbXBvcnQgZGF0ZXRpbWUKZnJvbSB0eXBpbmcgaW1wb3J0IE9wdGlv"
    "bmFsLCBUdXBsZQoKZnJvbSBjb25maWcuc2V0dGluZ3MgaW1wb3J0IHNldHRpbmdz"
    "CmZyb20gc3JjLmNvbnZlcnNhdGlvbi5nZW1pbmlfZW5naW5lIGltcG9ydCBHZW1p"
    "bmlJbnRlcnZpZXdlcgpmcm9tIHNyYy5jb3JlLnJlc2VhcmNoX3Byb2plY3QgaW1w"
    "b3J0IGdldF9wcm9qZWN0CmZyb20gc3JjLnN0b3JhZ2UudHJhbnNjcmlwdCBpbXBv"
    "cnQgVHJhbnNjcmlwdE1hbmFnZXIKZnJvbSBzcmMudm9pY2UuZ29vZ2xlX2Nsb3Vk"
    "X3N0dCBpbXBvcnQgR29vZ2xlQ2xvdWRTVFQKZnJvbSBzcmMudm9pY2UuZ29vZ2xl"
    "X2Nsb3VkX3R0cyBpbXBvcnQgR29vZ2xlQ2xvdWRUVFMKCmxvZ2dlciA9IGxvZ2dp"
    "bmcuZ2V0TG9nZ2VyKF9fbmFtZV9fKQoKCmNsYXNzIFZvaWNlSW50ZXJ2aWV3UGlw"
    "ZWxpbmU6CiAgICAiIiIKICAgIE9yY2hlc3RyYXRlcyB0aGUgZnVsbCBpbnRlcnZp"
    "ZXcgcGlwZWxpbmUgZm9yIGEgc2luZ2xlIHNlc3Npb24uCiAgICBQcm92aWRlci1h"
    "d2FyZTogYXV0by1yb3V0ZXMgdG8gU2FydmFtIGZvciBJbmRpYW4gbGFuZ3VhZ2Vz"
    "LgogICAgQWxsIEkvTyBtZXRob2RzIGFyZSBhc3luYy4KICAgICIiIgoKICAgIGRl"
    "ZiBfX2luaXRfXyhzZWxmLCBsYW5ndWFnZV9jb2RlOiBzdHIgPSAiZW4iLCBwcm9q"
    "ZWN0X2lkOiBPcHRpb25hbFtzdHJdID0gTm9uZSk6CiAgICAgICAgc2VsZi5zZXNz"
    "aW9uX2lkID0gc3RyKHV1aWQudXVpZDQoKSlbOjhdCiAgICAgICAgc2VsZi5sYW5n"
    "dWFnZV9jb2RlID0gbGFuZ3VhZ2VfY29kZQogICAgICAgIHNlbGYucHJvamVjdF9p"
    "ZCA9IHByb2plY3RfaWQKICAgICAgICBzZWxmLnN0YXJ0ZWRfYXQgPSBkYXRldGlt"
    "ZS5ub3coKS5pc29mb3JtYXQoKQogICAgICAgIHNlbGYuaXNfc3RhcnRlZCA9IEZh"
    "bHNlCgogICAgICAgIHVzZV9zYXJ2YW0gPSBzZXR0aW5ncy5zaG91bGRfdXNlX3Nh"
    "cnZhbShsYW5ndWFnZV9jb2RlKQoKICAgICAgICAjIEluaXRpYWxpc2UgU1RUCiAg"
    "ICAgICAgaWYgdXNlX3NhcnZhbToKICAgICAgICAgICAgZnJvbSBzcmMudm9pY2Uu"
    "c2FydmFtX3N0dCBpbXBvcnQgU2FydmFtU1RUCiAgICAgICAgICAgIHNlbGYuc3R0"
    "ID0gU2FydmFtU1RUKGxhbmd1YWdlX2NvZGU9bGFuZ3VhZ2VfY29kZSwgYXBpX2tl"
    "eT1zZXR0aW5ncy5zYXJ2YW1fYXBpX2tleSkKICAgICAgICAgICAgc2VsZi5fc3R0"
    "X3Byb3ZpZGVyID0gInNhcnZhbSIKICAgICAgICBlbHNlOgogICAgICAgICAgICBz"
    "ZWxmLnN0dCA9IEdvb2dsZUNsb3VkU1RUKGxhbmd1YWdlX2NvZGU9bGFuZ3VhZ2Vf"
    "Y29kZSkKICAgICAgICAgICAgc2VsZi5fc3R0X3Byb3ZpZGVyID0gImdvb2dsZSIK"
    "CiAgICAgICAgIyBJbml0aWFsaXNlIFRUUwogICAgICAgIGlmIHVzZV9zYXJ2YW06"
    "CiAgICAgICAgICAgIGZyb20gc3JjLnZvaWNlLnNhcnZhbV90dHMgaW1wb3J0IFNh"
    "cnZhbVRUUwogICAgICAgICAgICBzZWxmLnR0cyA9IFNhcnZhbVRUUyhsYW5ndWFn"
    "ZV9jb2RlPWxhbmd1YWdlX2NvZGUsIGFwaV9rZXk9c2V0dGluZ3Muc2FydmFtX2Fw"
    "aV9rZXkpCiAgICAgICAgICAgIHNlbGYuX3R0c19wcm92aWRlciA9ICJzYXJ2YW0i"
    "CiAgICAgICAgZWxzZToKICAgICAgICAgICAgc2VsZi50dHMgPSBHb29nbGVDbG91"
    "ZFRUUyhsYW5ndWFnZV9jb2RlPWxhbmd1YWdlX2NvZGUpCiAgICAgICAgICAgIHNl"
    "bGYuX3R0c19wcm92aWRlciA9ICJnb29nbGUiCgogICAgICAgICMgQ29udmVyc2F0"
    "aW9uIGVuZ2luZSDigJQgdXNlIEludGVydmlld0FnZW50IHdoZW4gYSBwcm9qZWN0"
    "IGlzIGxpbmtlZAogICAgICAgIHNlbGYuYWdlbnQgPSBOb25lICAjIEludGVydmll"
    "d0FnZW50IChwcmVmZXJyZWQpCiAgICAgICAgc2VsZi5pbnRlcnZpZXdlciA9IE5v"
    "bmUgICMgR2VtaW5pSW50ZXJ2aWV3ZXIgKGZhbGxiYWNrKQoKICAgICAgICBpZiBw"
    "cm9qZWN0X2lkOgogICAgICAgICAgICB0cnk6CiAgICAgICAgICAgICAgICBmcm9t"
    "IHNyYy5hZ2VudHMub3JjaGVzdHJhdG9yIGltcG9ydCBvcmNoZXN0cmF0b3IgYXMg"
    "X29yYwogICAgICAgICAgICAgICAgc2VsZi5hZ2VudCA9IF9vcmMuY3JlYXRlX2lu"
    "dGVydmlld19hZ2VudChwcm9qZWN0X2lkKQogICAgICAgICAgICAgICAgaWYgc2Vs"
    "Zi5hZ2VudDoKICAgICAgICAgICAgICAgICAgICBsb2dnZXIuaW5mbyhmIlt7c2Vs"
    "Zi5zZXNzaW9uX2lkfV0gVXNpbmcgSW50ZXJ2aWV3QWdlbnQgZm9yIHByb2plY3Qg"
    "e3Byb2plY3RfaWR9IikKICAgICAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbiBhcyBl"
    "OgogICAgICAgICAgICAgICAgbG9nZ2VyLndhcm5pbmcoZiJbe3NlbGYuc2Vzc2lv"
    "bl9pZH1dIEludGVydmlld0FnZW50IGxvYWQgZmFpbGVkLCBmYWxsaW5nIGJhY2s6"
    "IHtlfSIpCgogICAgICAgIGlmIHNlbGYuYWdlbnQgaXMgTm9uZToKICAgICAgICAg"
    "ICAgIyBGYWxsYmFjazogbG9hZCBxdWVzdGlvbnMgbWFudWFsbHkgZm9yIEdlbWlu"
    "aUludGVydmlld2VyCiAgICAgICAgICAgIGN1c3RvbV9xdWVzdGlvbnMgPSBOb25l"
    "CiAgICAgICAgICAgIHByb2plY3RfbmFtZSA9IE5vbmUKICAgICAgICAgICAgaWYg"
    "cHJvamVjdF9pZDoKICAgICAgICAgICAgICAgIHByb2ogPSBnZXRfcHJvamVjdChw"
    "cm9qZWN0X2lkKQogICAgICAgICAgICAgICAgaWYgcHJvajoKICAgICAgICAgICAg"
    "ICAgICAgICBjdXN0b21fcXVlc3Rpb25zID0gcHJvai5xdWVzdGlvbnMKICAgICAw"
    "ICAgICAgICAgICAgICAgcHJvamVjdF9uYW1lID0gcHJvai5uYW1lCiAgICAgICAg"
    "ICAgIHNlbGYuaW50ZXJ2aWV3ZXIgPSBHZW1pbmlJbnRlcnZpZXdlcigKICAgICAg"
    "ICAgICAgICAgIGxhbmd1YWdlX2NvZGU9bGFuZ3VhZ2VfY29kZSwKICAgICAgICAg"
    "ICAgICAgIGN1c3RvbV9xdWVzdGlvbnM9Y3VzdG9tX3F1ZXN0aW9ucywKICAgICAw"
    "ICAgICAgICAgICAgcHJvamVjdF9uYW1lPXByb2plY3RfbmFtZSwKICAgICAgICAg"
    "ICAgKQoKICAgICAgICBzZWxmLnRyYW5zY3JpcHRfbWFuYWdlciA9IFRyYW5zY3Jp"
    "cHRNYW5hZ2VyKCkKCiAgICAgICAgbG9nZ2VyLmluZm8oCiAgICAgICAgICAgIGYi"
    "W3tzZWxmLnNlc3Npb25faWR9XSBQaXBlbGluZSByZWFkeSB8IGxhbmc9e2xhbmd1"
    "YWdlX2NvZGV9IHwgIgogICAgICAgICAgICBmIlNUVD17c2VsZi5fc3R0X3Byb3Zp"
    "ZGVyfSB8IFRUUz17c2VsZi5fdHRzX3Byb3ZpZGVyfSIKICAgICAgICApCg=="
)
write_file("src/voice/pipeline.py", _PIPELINE_B64, "pipeline.py rewrite (InterviewAgent support)")

print("\n".join(ok))
if err:
    print("\nNot applied (check manually):")
    print("\n".join(err))
