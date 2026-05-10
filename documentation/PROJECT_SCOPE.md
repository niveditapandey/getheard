# Project Scope — GetHeard

## Vision

GetHeard makes consumer research as easy as ordering a product online. A brand in Mumbai, Singapore, or Jakarta should be able to commission a 20-person voice study, get AI-moderated interviews conducted in the local language, and receive a structured insight report — without hiring a research agency, without flying anyone out, and without weeks of waiting.

**Tagline:** *"Voice has Value."*

---

## The Problem Being Solved

Traditional market research in Asia is:
- **Slow** — 4–8 weeks from brief to report
- **Expensive** — ₹2–5 lakh for a basic qual study
- **Inaccessible** — requires research agencies, moderators, translators
- **English-biased** — insights from non-English speakers are lost
- **Unscalable** — human moderators can't run 50 interviews simultaneously

GetHeard removes every one of these friction points using AI agents + voice technology.

---

## Target Users

### Side A — Clients (Brands)

**Primary:** Mid-size companies in India and Southeast Asia doing consumer research
- Fintech startups (KYC drop-off studies, product feedback)
- E-commerce companies (CX, NPS)
- Healthcare brands (patient experience)
- FMCG (brand perception, new product testing)
- SaaS products (UX research, feature prioritisation)

**Budget:** ₹8,000 – ₹80,000 per study (equivalent to $100–$1,000 USD)

**Profile:** Product managers, CX leads, brand managers, startup founders who:
- Know what they want to learn but don't know how to run research
- Have limited budget for traditional agencies
- Need insights within days, not weeks

---

### Side B — Respondents (Panel)

**Who they are:** Adults across Asia willing to share opinions in exchange for small rewards

**Markets:** India, Singapore, Indonesia, Thailand, Vietnam, China, Japan, Korea, Philippines

**Profile:**
- Age 18–55
- Smartphone users (for WhatsApp or browser voice)
- Motivated by: small cash rewards (₹50–₹500 per interview), gift cards, brand engagement

**Languages:** English, Hindi, Indonesian, Thai, Vietnamese, Mandarin, Filipino, Korean, Japanese + all major Indian regional languages

---

## Business Model

### Revenue (Client Side)

| Study Type | Base Price (INR) |
|------------|-----------------|
| NPS / CSAT | ₹7,999 |
| Feature Feedback | ₹11,999 |
| Pain Points / UX | ₹14,999 |
| Custom / Bespoke | ₹16,999 |

Plus:
- Panel size multiplier (1x–6x based on respondent count)
- Recruitment fee (₹1,499/respondent from GetHeard panel; ₹2,499+ for targeted)
- Urgency premium: +25% for <72h turnaround
- Respondent incentive: client can optionally add ₹X per head (passed to respondents as points)

**Payment:** Razorpay (India/SEA) + Stripe (international)

### Cost (Respondent Side)

Respondents are rewarded with **points**:
- 20% of their points credited on panel **selection**
- 80% credited on interview **completion**
- Minimum 100 points to redeem
- Exchange: ~50 paise per point in India (varies by country)
- Redemption options: UPI cash transfer (IN/SG live), gift cards (+10% bonus), other markets "coming soon"

---

## What GetHeard Automates End-to-End

```
Client Brief → Question Design → Panel Recruitment → Interviews → Analysis → Report
     ↑               ↑                  ↑                ↑            ↑          ↑
  BriefAgent    DesignerAgent       PanelAgent     InterviewAgent  AnalysisAgent  (PDF/web)
```

Every step except payment review and final report approval is AI-automated.

---

## What GetHeard Does NOT Do (Scope Boundaries)

- **No video interviews** — audio/voice only (browser mic + WhatsApp)
- **No quantitative surveys** — qual voice interviews only (not Typeform/SurveyMonkey)
- **No participant recruitment outside Asia** — panel is Asia-focused
- **No real-time human moderation** — all interviews are AI-moderated
- **No raw data export** (yet) — reports are narrative + structured JSON
- **No native mobile app** — web-only (mobile-responsive)
- **No database** — currently file-based JSON storage (see backlog for migration)

---

## Markets & Geographic Scope

### Phase 1 (Current Build)
- 🇮🇳 India — Hindi + English + regional languages (Sarvam AI)
- 🇸🇬 Singapore — English
- 🇮🇩 Indonesia — Bahasa Indonesia

### Phase 2 (Planned)
- 🇹🇭 Thailand — Thai
- 🇻🇳 Vietnam — Vietnamese
- 🇨🇳 China — Mandarin

### Phase 3 (Future)
- 🇵🇭 Philippines — Filipino
- 🇰🇷 Korea — Korean
- 🇯🇵 Japan — Japanese

---

## Study Types

| Type | Code | Description |
|------|------|-------------|
| NPS / CSAT | `nps_csat` | Net Promoter Score, satisfaction drivers |
| Feature Feedback | `feature_feedback` | New/existing product feature evaluation |
| Pain Points | `pain_points` | UX research, drop-off analysis, friction mapping |
| Custom | `custom` | Fully bespoke research brief |

Pre-built templates are planned for common verticals (KYC drop-off, brand perception, etc.).

---

## Study Lifecycle (9 Stages)

```
1. briefing          → Client + BriefAgent chat to define research goals
2. pricing           → PricingAgent presents quote; client adjusts 3 levers
3. timeline_estimate → TimelineAgent estimates delivery with phase breakdown
4. awaiting_payment  → Client pays via Razorpay or Stripe
5. panel_building    → PanelAgent recruits respondents from DB or CSV
6. panel_approval    → Client reviews and approves panel list
7. interviewing      → Respondents complete voice interviews
8. analysis          → AnalysisAgent runs 4-pass analysis on transcripts
9. completed         → Report delivered; client downloads/shares
```

---

## Success Metrics (KPIs)

| Metric | Target (Year 1) |
|--------|----------------|
| Studies commissioned | 100 |
| Respondents enrolled | 5,000 |
| Average study turnaround | < 5 days |
| Client NPS | > 50 |
| Respondent completion rate | > 80% |
| Revenue | ₹25 lakh ARR |

---

## Competitive Positioning

| Competitor | Their Approach | GetHeard Advantage |
|------------|---------------|-------------------|
| Traditional research agencies | Human moderators, 4–8 weeks, expensive | 10x cheaper, 10x faster |
| SurveyMonkey / Typeform | Text surveys, no voice, no qual | Rich qual insights, voice, multilingual |
| UserTesting | English-only, Western markets | Asia-first, vernacular languages |
| Qualtrics | Enterprise, complex, expensive | Self-serve, SMB-friendly, Asia pricing |

---

## Founder

**Nivedita Pandey** — Solo founder, ex-[Dendrons.ai]
Building GetHeard as an AI-native research platform for Asia.
