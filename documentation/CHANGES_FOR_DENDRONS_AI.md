# GetHeard — Public URLs for dendrons.ai & niveditapandey.com

> Use this file when doing a batch refresh of dendrons.ai and niveditapandey.com.
> Each section below maps to a user type / use case, with the exact link to embed.

---

## Product Overview

**GetHeard** — AI-powered qualitative research platform for Asia.
Tagline: *Voice has Value*
Live app base URL: `https://getheard-151428781052.asia-south1.run.app`
Custom domain (once Cloudflare Worker is set up): `https://getheard.space`

---

## Links by User Type

### 1. Research Clients (Brands / Corporates commissioning studies)

| What to show | URL |
|---|---|
| Client Login | `https://getheard-151428781052.asia-south1.run.app/listen/login` |
| Demo Dashboard (auto-login as demo) | `https://getheard-151428781052.asia-south1.run.app/listen` |
| Start a new study (AI Brief Agent) | `https://getheard-151428781052.asia-south1.run.app/agent/brief` |
| View a sample report | `https://getheard-151428781052.asia-south1.run.app/listen/reports` |

**Demo credentials for live demo on the site:**
- Username: `demo`
- Password: `demo123`

---

### 2. Respondents (People completing interviews)

| What to show | URL |
|---|---|
| Respondent Home / Panel signup | `https://getheard-151428781052.asia-south1.run.app/join/home` |
| Sample interview join page | `https://getheard-151428781052.asia-south1.run.app/join/<project_id>` |
| Rewards dashboard | `https://getheard-151428781052.asia-south1.run.app/join/rewards/<respondent_id>` |

> Note: Replace `<project_id>` with a real project ID once a demo project is created. Create one via the brief agent and paste the ID here.

---

### 3. Voice Interview (Live AI Interviewer — wow factor demo)

| What to show | URL |
|---|---|
| Voice interview booth | `https://getheard-151428781052.asia-south1.run.app/` |

> This is the most impressive demo — opens an in-browser voice AI interview.
> Best used as an embedded iframe or "Try it live" CTA on the landing page.

---

### 4. WhatsApp Interview (for portfolio / investor context)

Not a direct link — a phone demo. Document for reference:
- WhatsApp number: `+14788003250` (Twilio sandbox)
- Message to start: `START <project_id>`
- Works for numbers pre-registered in Twilio sandbox

---

### 5. Platform Landing Page

| What to show | URL |
|---|---|
| GetHeard landing page | `https://getheard-151428781052.asia-south1.run.app/landing` |

---

## For dendrons.ai — Suggested Card Format

```
Product: GetHeard
Tagline: AI-powered qualitative research for Asia. Voice has Value.
What it does: Commission research studies, conduct AI interviews via WhatsApp
              or voice, get instant reports with themes and quotes.
Status: Live demo
Audience: Market research agencies, CX teams, product teams in Asia

Links:
  → Try the platform (client login)   getheard-151428781052.asia-south1.run.app/listen/login
  → Try a voice interview (live AI)   getheard-151428781052.asia-south1.run.app/
  → Join as a respondent              getheard-151428781052.asia-south1.run.app/join/home

Demo credentials: demo / demo123
```

---

## For niveditapandey.com — Suggested Bio Blurb

```
GetHeard — AI Research Platform
Built an end-to-end qualitative research platform for the Asian market.
Brands commission studies, AI conducts interviews via WhatsApp and voice,
and the platform generates reports with themes, quotes and sentiment
analysis — in 9 languages. Currently in live demo.

[View Demo →] getheard-151428781052.asia-south1.run.app/listen/login
```

---

## URL Update Log

| Date | Change |
|---|---|
| 2026-03-28 | Initial deploy — Cloud Run URL active |
| TBD | Cloudflare Worker maps `getheard.space` → Cloud Run |
| TBD | Update all links above to use `getheard.space` once domain is live |

---

## Companion Project — LeadConvert

> If listing on the same page, GetHeard's sister project:
> LeadConvert (AI sales pipeline / lead qualification)
> Base URL: `https://leadconvert-client-[hash].asia-south1.run.app` (check GCP console for hash)
> User: document separately in `/leadconvert/docs/CHANGES_FOR_DENDRONS_AI.md`
