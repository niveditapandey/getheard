cat > ~/documents/AI\ Projects/getheard/CLAUDE.md << 'EOF'
# GetHeard — Claude Code Context

## What this project is
AI-powered voice research platform. Two-sided: brands commission studies, respondents do voice interviews, AI handles everything in between.

## Repo
https://github.com/niveditapandey/getheard.git
Main branch: master

## Stack
FastAPI + Jinja2 templates + vanilla JS. No framework. JSON file storage. Gemini 2.5 Flash/Pro. Google Cloud STT/TTS + Sarvam AI for Indian languages.

## Three portals
- `/listen` — client portal (brands)
- `/join` — respondent portal
- `/admin` — admin dashboard

## Current task in progress
Branch: `fix/questions-and-link`
Commit: e7349b8

Two fixes:
1. `src/web/templates/agent/brief_chat.html` — link call retry logic (was silently swallowed), setTimeout 2500→3500
2. `src/web/templates/study_status.html` — collapsible questions section after pipeline card, one-time fetch to `/agent/api/projects/{projectId}`

Status: committed locally in Claude Code sandbox, needs pushing to `fix/questions-and-link` on GitHub via MCP tool.

## Key routes
- POST /agent/api/design — DesignerAgent saves questions to project JSON
- POST /api/client/studies/{project_id}/link — links project to client session
- GET /api/client/projects — reads session["linked_studies"]
- GET /agent/api/projects/{id} — returns full project JSON including questions[]
- GET /api/client/study/{id}/status — pipeline status only, no questions

## Auth
- Client: session cookie, request.session["client_id"]
- Simple/demo users: client_id starts with "simple:", studies stored in session["linked_studies"]
- Admin: request.session["is_admin"]

## .env location
In project root. Not on GitHub. All credentials already configured.
EOF

