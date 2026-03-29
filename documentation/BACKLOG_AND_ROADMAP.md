# Backlog & Roadmap — GetHeard

**Last Updated:** March 2026
**Owner:** Nivedita Pandey

---

## Legend
- ✅ Done
- 🔄 In Progress
- 🔜 Up Next (1–2 weeks)
- 📋 Backlog (planned)
- 💡 Ideas (not yet committed)

---

## ✅ Completed (What's Already Built)

### Core Platform
- [x] FastAPI web server with 6 routers (client, admin, study, panel, respondent, agentic)
- [x] Navy blue design system (CSS custom properties, all components)
- [x] Public landing page (`/`) — "Voice has Value" hero
- [x] Session-based authentication (itsdangerous, cookie sessions)

### Client Portal (`/listen`)
- [x] Client signup + login + logout
- [x] Client dashboard with studies + stats
- [x] BriefAgent conversational brief intake (chat UI)
- [x] PricingAgent — dynamic quote with 3 live-adjustable levers
- [x] TimelineAgent — delivery estimate with phase breakdown
- [x] Razorpay payment integration (order creation + HMAC signature verification)
- [x] Stripe payment integration (hosted checkout)
- [x] 9-stage study pipeline stepper (live status, polled every 10s)
- [x] Panel approval flow (client reviews + confirms)
- [x] Report download + shareable link

### Respondent Portal (`/join`)
- [x] Public enrollment form (`/join`)
- [x] 6-language multilingual form (EN, HI, ID, TH, VI, ZH — all labels switch)
- [x] Phone number deduplication
- [x] Points/rewards dashboard (`/join/rewards/{id}`)
- [x] Redemption flow (UPI + gift card)
- [x] Points: 20% on selection, 80% on completion
- [x] Gift card +10% bonus
- [x] Exchange rates for 12 countries
- [x] Respondent profile page

### Admin Portal (`/admin`)
- [x] Admin login (separate credentials)
- [x] Platform stats dashboard
- [x] Client + study management tables
- [x] Admin pricing editor (inline, live calculator)
- [x] Redemption queue management

### AI Agents
- [x] BaseAgent (Gemini function-calling loop)
- [x] BriefAgent (conversational brief intake)
- [x] DesignerAgent (question generation + self-review)
- [x] PanelAgent (CSV + DB panel building)
- [x] InterviewAgent (via GeminiInterviewer)
- [x] AnalysisAgent (4-pass: sentiment, themes, Q-by-Q, pain points)
- [x] PricingAgent (dynamic quote computation)
- [x] TimelineAgent (phase-based delivery estimate)
- [x] Orchestrator (coordinates full pipeline)

### Voice Pipeline
- [x] Browser-based voice interview (STT → Gemini → TTS)
- [x] Google Cloud STT (all 11+ languages)
- [x] Google Cloud TTS (neural voices)
- [x] Sarvam AI STT (Indian languages)
- [x] Sarvam AI TTS (Indian languages)
- [x] Auto-routing (Indian langs → Sarvam, others → Google Cloud)
- [x] WhatsApp text-based interview (Twilio webhook)

### Storage
- [x] Project store (JSON file CRUD)
- [x] Transcript manager (save/load/list)
- [x] Report store
- [x] Respondent store (with sensitive field separation)
- [x] Client store (SHA-256 password hashing)
- [x] Points store (12 currencies, gift card bonus)
- [x] Pricing store (admin-editable JSON config)

### Notifications
- [x] Resend email integration (domain: getheard.space, SPF+MX verified)
- [x] Meta WhatsApp Business API (outbound notifications)
- [x] Twilio WhatsApp inbound (interview webhook)
- [x] Graceful fallback (notifications fail silently if not configured)

### Config & Settings
- [x] Pydantic Settings (all env vars, feature flags, properties)
- [x] Dynamic pricing config (config/pricing.json, admin-editable)
- [x] All real credentials wired up (.env)

---

## 🔄 In Progress Right Now

| Task | Status | Notes |
|------|--------|-------|
| Resend DKIM verification | ⏳ DNS propagating | TXT record added to Namecheap 27 Mar; SPF+MX already verified |
| Twilio account setup | 🔄 User setting up | SID + Auth Token → add to .env; set sandbox webhook URL |
| Hindi + English interviews | 📌 User to do | Record interviews for existing 5 transcripts; rerun AnalysisAgent after |
| Documentation | ✅ Just completed | All 14 docs written |

---

## 🔜 Up Next (Week 1–2)

### Critical for Launch

- [ ] **Add Twilio credentials to .env** — after user sets up account
  ```env
  TWILIO_ACCOUNT_SID=AC...
  TWILIO_AUTH_TOKEN=...
  ```

- [ ] **Confirm Resend DKIM verified** — check status, then update `.env`:
  ```env
  RESEND_FROM_EMAIL=hello@getheard.space
  ```
  Remove `RESEND_TEST_OVERRIDE_TO` line from `.env`

- [ ] **WhatsApp message templates** — Create 4 templates manually in Meta Business Manager:
  1. `panel_selected` — "You've been selected for a research panel..."
  2. `interview_reminder` — "Your interview is tomorrow..."
  3. `report_ready` — "Your research report is ready..."
  4. `payout_processed` — "Your payout of ₹{amount} has been processed..."

- [ ] **Get permanent WhatsApp token** — Current 60-day token expires ~May 2026
  - Meta Business Manager → System Users → Create System User → Generate permanent token

- [ ] **Change admin password** before going live:
  ```env
  ADMIN_CREDENTIALS=admin:your-strong-password-here
  SECRET_KEY=a-long-random-string-change-this
  ```

- [ ] **Complete Hindi + English interview recordings** — Do remaining interviews, re-run AnalysisAgent

### Tech Debt

- [ ] **Test full study lifecycle end-to-end** — Brief → Pay → Panel → Interview → Report
- [ ] **Error pages** — 404, 500 pages with navy design
- [ ] **Loading states** — Spinner/skeleton while BriefAgent/AnalysisAgent runs
- [ ] **Form validation** — Client-side validation on all forms (currently server-side only)

---

## 📋 Backlog (Planned — No Fixed Date)

### Deployment & Infrastructure

- [ ] **Deploy to production** — Choose hosting:
  - **Option A:** Railway.app (easiest, supports Python, ~$5/month)
  - **Option B:** Render.com (free tier, auto-deploy from git)
  - **Option C:** Google Cloud Run (serverless, scalable)
  - **Option D:** DigitalOcean App Platform
  - **Requirement:** Persistent disk volume for JSON files

- [ ] **Custom domain SSL** — getheard.space HTTPS (usually automatic with above options)
- [ ] **Set up automated backups** — Cron job to tar JSON directories daily
- [ ] **Error monitoring** — Sentry integration
- [ ] **Uptime monitoring** — UptimeRobot or Pingdom for getheard.space

### Database Migration

- [ ] **Migrate from JSON files to PostgreSQL**
  - Entities to migrate: projects, clients, respondents, panels, reports, redemptions
  - Transcripts can stay as files (too large for DB rows)
  - Use SQLAlchemy + Alembic for ORM + migrations
  - Will fix: concurrent write conflicts, large dataset queries, no indexing

### Client Portal Improvements

- [ ] **Password reset flow** — "Forgot password" → email link → reset
- [ ] **Study duplication** — "Run this study again" button
- [ ] **Report sharing with password protection** — Shareable link with optional password
- [ ] **PDF report download** — Server-rendered PDF (WeasyPrint or similar)
- [ ] **Email notifications to client** — Automated at each pipeline milestone
- [ ] **International pricing display** — Show USD/SGD equivalent in quote
- [ ] **Google OAuth login** — "Sign in with Google" for client portal
- [ ] **Study templates** — Pre-built briefs for common use cases (KYC drop-off, brand NPS, etc.)
- [ ] **Transcript access** — Client can view anonymised transcripts (toggle in dashboard)

### Respondent Portal Improvements

- [ ] **Phone OTP login** — Instead of link-based profile access
- [ ] **Interview scheduling** — Respondent picks time slot (calendar integration)
- [ ] **Automated UPI payouts** — Razorpay Payouts API for instant UPI (no manual admin step)
- [ ] **Automated gift card delivery** — API integration with Amazon/Flipkart gift cards
- [ ] **Respondent referral program** — Refer a friend → bonus points
- [ ] **Profile editing** — Update interests, contact details, city
- [ ] **Interview history** — List of all completed interviews

### Admin Portal Improvements

- [ ] **Revenue dashboard** — Total revenue, monthly chart, by study type
- [ ] **WhatsApp broadcast** — Send message to segment of panel (by language/country/interest)
- [ ] **Respondent import UI** — Upload CSV to bulk-import respondents (currently API-only)
- [ ] **Study management actions** — Manually advance/revert pipeline stages
- [ ] **Client management** — Suspend/activate clients, view payment history
- [ ] **Multi-admin support** — Add team members with admin access

### AI & Research Quality

- [ ] **Question templates** — Pre-built question sets for NPS, CX, UX, brand studies
- [ ] **Multi-language reports** — Report in Hindi/Indonesian if study was in that language
- [ ] **Cross-study analytics** — Compare themes across multiple studies (same client)
- [ ] **Transcript search** — Search across all transcripts by keyword/theme
- [ ] **Quote highlighting** — Auto-highlight the most impactful quotes in report
- [ ] **Confidence scores** — Add confidence % to each theme (how often mentioned)
- [ ] **Competitor mention detection** — Auto-flag when competitors mentioned in interviews
- [ ] **Sentiment timeline** — How sentiment changed during interview (positive start → negative about feature)

### Voice & Interview

- [ ] **WhatsApp voice notes** — Accept WhatsApp voice messages as interview input (currently text only)
- [ ] **Interview resume** — If respondent disconnects, continue where they left off
- [ ] **Interview quality score** — Flag interviews that were too short/low quality
- [ ] **Async interview via WhatsApp** — Full interview via WhatsApp text (no browser needed)
- [ ] **Interview link system** — Unique URL per respondent per study (currently open)
- [ ] **Korean + Japanese interviews** — Currently supported in code, needs testing

### Payments & Billing

- [ ] **Stripe webhook handler** — Currently Stripe payment isn't verified server-side
- [ ] **Invoice generation** — Auto-generate PDF invoice after payment
- [ ] **Subscription plans** — Monthly/annual plans for high-volume clients
- [ ] **Partial refunds** — If fewer respondents complete than promised
- [ ] **Credit system** — Prepaid credits that clients can draw down

### Market Expansion

- [ ] **Thailand launch** — Thai-language panel, local payment method (PromptPay)
- [ ] **Vietnam launch** — Vietnamese panel, local payment (VietQR)
- [ ] **Indonesia launch** — Bahasa Indonesia panel, GoPay/OVO
- [ ] **China launch** — Mandarin panel, WeChat Pay (complex regulatory)
- [ ] **Korea launch** — Korean panel, Kakao Pay
- [ ] **Japan launch** — Japanese panel (most expensive market)

---

## 💡 Future Ideas (Not Committed)

- **B2B API** — Sell GetHeard capabilities as an API (research-as-a-service)
- **White-label** — Research agencies use GetHeard under their own brand
- **Panel marketplace** — Respondents can browse open studies and self-apply
- **Longitudinal studies** — Same respondents over multiple waves (brand tracking)
- **Video interviews** — Optional webcam for facial expression analysis
- **GetHeard for HR** — Employee experience research (internal use case)
- **NPS benchmark database** — Industry NPS benchmarks by market
- **Research co-pilot** — AI suggests follow-up questions based on live analysis
- **Slack/Teams integration** — Report summary delivered to Slack channel
- **Zapier/Make connector** — Automate GetHeard with other tools

---

## Known Bugs & Issues

| Bug | Severity | Status |
|-----|----------|--------|
| WhatsApp token expires 60 days | High | ⚠️ Monitor — expiry ~May 2026 |
| Resend DKIM still propagating | Medium | ⏳ Auto-resolves |
| No error page for 404/500 | Low | In backlog |
| Stripe payment not server-verified | Medium | In backlog |
| SHA-256 password hashing (should be bcrypt) | Medium | In backlog |
| No rate limiting on API endpoints | Medium | In backlog |
| Sessions not invalidated on server restart | Low | Known limitation |
| JSON file storage has race conditions under concurrency | Medium | DB migration in backlog |

---

## Decisions Made (Architecture Log)

| Decision | Rationale |
|----------|-----------|
| JSON file storage (not PostgreSQL) | Ship fast; migrate later when needed |
| No WebSockets (polling for status) | Simpler; works fine at current scale |
| Single-process FastAPI (not microservices) | Solo founder, simpler to operate |
| Navy blue design (not purple) | Matches existing brand (elephantsdance.com, niveditapande.com) |
| `/listen` for clients, `/join` for respondents | Creative, memorable URL structure |
| Brief-first pricing (no price during briefing) | Client should focus on research goal, not cost |
| Sarvam AI for Indian languages | Better prosody/naturalness than Google Cloud for Indian languages |
| INR pricing for all markets | India-first launch; international conversion via Stripe |
| Points system (not direct cash) | Flexibility in payout method; gift card bonus drives engagement |
