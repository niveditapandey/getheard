# Product Requirements Document (PRD) — GetHeard

**Version:** 1.0
**Date:** March 2026
**Status:** In Development
**Owner:** Nivedita Pandey

---

## 1. Executive Summary

GetHeard is an AI-powered voice research platform for Asia. It enables brands to commission multilingual qualitative research studies with AI-moderated voice interviews, automated analysis, and structured reports — all self-served in days, not weeks.

---

## 2. User Personas

### Persona A: Priya — Product Manager at a Fintech Startup (Client)
- **Goal:** Understand why users drop off during KYC verification
- **Pain:** Can't afford a research agency; doesn't have time to run focus groups
- **Behaviour:** Books online tools, wants results in <1 week
- **Success:** Receives a 20-interview report with themes + quotes in 4 days

### Persona B: Ravi — Respondent in Mumbai (Panel Member)
- **Goal:** Earn ₹100–200 per interview via UPI
- **Pain:** Doesn't speak English well; survey apps don't work for him
- **Behaviour:** Uses WhatsApp daily; comfortable speaking Hindi
- **Success:** Joins panel in Hindi, completes interview on WhatsApp, receives UPI payout

### Persona C: Nivedita — Platform Admin
- **Goal:** Monitor all studies, manage pricing, process payouts, see revenue
- **Pain:** No central dashboard currently
- **Success:** Full visibility into clients, studies, respondents, revenue, redemptions

---

## 3. Feature Requirements

### 3.1 Public Landing Page (`/`)

| ID | Requirement | Priority |
|----|-------------|----------|
| L1 | Hero section with "Voice has Value" tagline | Must Have |
| L2 | Two CTAs: "Commission a Study" (→ /listen) and "Join as Respondent" (→ /join) | Must Have |
| L3 | Language switcher (EN, HI, ID, TH, VI, ZH) | Should Have |
| L4 | How-it-works section (3-step visual) | Should Have |
| L5 | Social proof / trust signals (markets served, interviews completed) | Nice to Have |
| L6 | SEO meta tags and OG image | Nice to Have |

---

### 3.2 Client Portal (`/listen`)

#### 3.2.1 Authentication

| ID | Requirement | Priority |
|----|-------------|----------|
| C1 | Self-serve signup with name, company, email, password | Must Have |
| C2 | Email + password login | Must Have |
| C3 | Session-based auth (cookie, server-side) | Must Have |
| C4 | Logout | Must Have |
| C5 | Password reset via email (Resend) | Should Have |
| C6 | Google OAuth login | Nice to Have |

#### 3.2.2 Client Dashboard

| ID | Requirement | Priority |
|----|-------------|----------|
| D1 | List all commissioned studies with status badges | Must Have |
| D2 | Stats cards: active studies, completed studies, total respondents | Must Have |
| D3 | Quick-action button: "Commission New Study" | Must Have |
| D4 | Click through to study detail page | Must Have |

#### 3.2.3 Study Commissioning Flow

**Step 1 — Brief (BriefAgent Chat)**

| ID | Requirement | Priority |
|----|-------------|----------|
| B1 | Conversational chat UI with BriefAgent | Must Have |
| B2 | Agent collects: project name, research type, industry, objective, target audience, language, topics, question count | Must Have |
| B3 | Agent saves brief when complete | Must Have |
| B4 | No pricing shown during briefing | Must Have |
| B5 | Client can select from study type presets (NPS, Feature Feedback, Pain Points, Custom) | Should Have |

**Step 2 — Pricing (PricingAgent)**

| ID | Requirement | Priority |
|----|-------------|----------|
| P1 | Itemised quote shown after brief is complete | Must Have |
| P2 | Three adjustable levers: panel size, panel source, study type | Must Have |
| P3 | Live price recompute as levers change (debounced API call) | Must Have |
| P4 | Optional: add respondent incentive (₹X per head) | Should Have |
| P5 | Optional: urgency toggle (+25%) | Should Have |
| P6 | Quote breakdown: study fee, recruitment fee, incentive total, urgency fee, total | Must Have |
| P7 | "Confirm Quote" CTA to advance to timeline | Must Have |

**Step 3 — Timeline (TimelineAgent)**

| ID | Requirement | Priority |
|----|-------------|----------|
| T1 | Estimated delivery date shown | Must Have |
| T2 | Phase breakdown: recruitment, scheduling, interviews, analysis, report | Must Have |
| T3 | Urgency option adjusts timeline + price | Should Have |
| T4 | Payment button (Razorpay for India/SEA, Stripe for international) | Must Have |

**Step 4 — Payment**

| ID | Requirement | Priority |
|----|-------------|----------|
| PAY1 | Razorpay modal for INR payments | Must Have |
| PAY2 | Stripe hosted checkout for international | Must Have |
| PAY3 | Payment verification (HMAC signature check for Razorpay) | Must Have |
| PAY4 | Post-payment: trigger panel building automatically | Must Have |
| PAY5 | Send payment confirmation email to client | Should Have |

#### 3.2.4 Panel Approval

| ID | Requirement | Priority |
|----|-------------|----------|
| PA1 | Client sees list of selected respondents (name, age, language, location) | Must Have |
| PA2 | Client can approve or request changes | Must Have |
| PA3 | On approval, respondents notified via WhatsApp | Should Have |

#### 3.2.5 Live Study Status

| ID | Requirement | Priority |
|----|-------------|----------|
| S1 | 9-step pipeline stepper showing current stage | Must Have |
| S2 | Auto-refresh every 10 seconds (polling) | Must Have |
| S3 | Interviews completed count vs target | Must Have |
| S4 | Link to download/share report when complete | Must Have |

---

### 3.3 Respondent Portal (`/join`)

#### 3.3.1 Enrollment

| ID | Requirement | Priority |
|----|-------------|----------|
| R1 | Public enroll form (no login required) | Must Have |
| R2 | Multilingual form (EN, HI, ID, TH, VI, ZH) — all labels switch | Must Have |
| R3 | Fields: name, phone (dedup key), email, language, city, country, age range, gender, interests | Must Have |
| R4 | Phone number deduplication (one account per phone) | Must Have |
| R5 | Consent checkbox (PDPA compliant) | Must Have |
| R6 | Optional sensitive fields: medical conditions, orientation (stored encrypted/separately) | Should Have |

#### 3.3.2 Rewards Dashboard

| ID | Requirement | Priority |
|----|-------------|----------|
| RW1 | Points balance display | Must Have |
| RW2 | Transaction history (credits + debits) | Must Have |
| RW3 | Redemption tab: cash (UPI) or gift card | Must Have |
| RW4 | UPI payout available for India + Singapore | Must Have |
| RW5 | Gift card redemption with +10% bonus | Must Have |
| RW6 | "Coming soon" for other markets | Must Have |
| RW7 | Min redemption: 100 points | Must Have |
| RW8 | Redemption request submitted → admin processes | Must Have |

#### 3.3.3 Profile Page

| ID | Requirement | Priority |
|----|-------------|----------|
| RP1 | View profile by phone number | Must Have |
| RP2 | Edit interests and preferences | Should Have |
| RP3 | Interview history | Should Have |

---

### 3.4 Admin Portal (`/admin`)

| ID | Requirement | Priority |
|----|-------------|----------|
| A1 | Admin login (separate credentials from client) | Must Have |
| A2 | Platform stats: total clients, active studies, respondents, revenue | Must Have |
| A3 | List all clients with study count | Must Have |
| A4 | List all studies with status | Must Have |
| A5 | Pricing admin panel — edit all pricing tiers inline | Must Have |
| A6 | Redemption queue — approve/reject payout requests | Must Have |
| A7 | Revenue dashboard (total collected, by study, by month) | Should Have |
| A8 | Respondent management (search, filter, status update) | Should Have |
| A9 | WhatsApp broadcast (send message to panel segment) | Nice to Have |

---

### 3.5 Voice Interview System

| ID | Requirement | Priority |
|----|-------------|----------|
| V1 | Browser-based voice interview (microphone → STT → Gemini → TTS) | Must Have |
| V2 | WhatsApp text-based interview (webhook → Gemini → WhatsApp reply) | Must Have |
| V3 | Multi-language support: EN, HI, ID, TH, VI, ZH, KO, JA, FIL | Must Have |
| V4 | Auto-route: Indian languages → Sarvam AI; others → Google Cloud | Must Have |
| V5 | Custom questions per project loaded into interview agent | Must Have |
| V6 | Conversation saved to transcript JSON after each session | Must Have |
| V7 | Interview marked complete after all questions answered | Must Have |
| V8 | Max interview duration: 10 minutes (configurable) | Must Have |
| V9 | Graceful fallback if audio fails (show transcript) | Should Have |
| V10 | Pre-translated questions for non-English interviews | Should Have |

---

### 3.6 AI Research Pipeline

| ID | Requirement | Priority |
|----|-------------|----------|
| AG1 | BriefAgent: conversational brief intake via chat | Must Have |
| AG2 | DesignerAgent: generate + self-review interview questions from brief | Must Have |
| AG3 | PanelAgent: recruit panel from DB or CSV upload | Must Have |
| AG4 | InterviewAgent: conduct voice interviews (via pipeline) | Must Have |
| AG5 | AnalysisAgent: 4-pass analysis (sentiment, themes, Q-by-Q, pain points) | Must Have |
| AG6 | PricingAgent: compute dynamic quotes post-brief | Must Have |
| AG7 | TimelineAgent: estimate delivery phases | Must Have |
| AG8 | Orchestrator: coordinate full pipeline end-to-end | Should Have |

---

### 3.7 Notifications

| ID | Requirement | Priority |
|----|-------------|----------|
| N1 | Email: study commissioned (to client) | Must Have |
| N2 | Email: panel approved (to client) | Must Have |
| N3 | Email: report ready (to client + link) | Must Have |
| N4 | WhatsApp: respondent selected for panel | Must Have |
| N5 | WhatsApp: interview reminder (day before) | Should Have |
| N6 | WhatsApp: payment/payout processed | Should Have |
| N7 | Email: signup welcome (to client) | Should Have |

---

## 4. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| Performance | Voice response latency < 2s (STT + Gemini + TTS combined) |
| Availability | 99% uptime during business hours (Asia time zones) |
| Security | No passwords stored in plaintext; SHA-256 hashing minimum |
| Privacy | Sensitive respondent fields stored separately; PDPA compliant |
| Scalability | Concurrent interviews: 50+ (stateless session design) |
| Mobile | Respondent pages fully mobile-responsive |
| Accessibility | WCAG AA minimum on client-facing pages |
| Browser | Chrome + Safari + Firefox (last 2 versions) |

---

## 5. Constraints

- **No database** — JSON file storage in current version (see roadmap for migration)
- **No real-time push** — polling used for live updates (every 10s)
- **No video** — audio only
- **No WhatsApp voice** — WhatsApp is text-only (voice = browser only)
- **Payments in INR only** — Stripe international TBD
- **Single-tenant admin** — one admin account, no multi-admin support yet

---

## 6. Acceptance Criteria (Definition of Done)

A study is considered end-to-end complete when:
1. Client can sign up, create a study via BriefAgent, and receive a quote
2. Client can pay via Razorpay and see study status update to "panel_building"
3. PanelAgent selects at least 5 respondents from the database
4. Client can approve the panel
5. At least 1 respondent can complete a voice interview in English
6. AnalysisAgent generates a report with executive summary + key themes
7. Client can view and share the report link
8. Admin can see the study and client in the admin dashboard

---

## 7. Out of Scope (v1)

- Video interviews
- Quantitative surveys / survey logic / branching
- Multi-admin / team accounts
- Native mobile app (iOS/Android)
- AI-generated survey links (Typeform-style)
- Automated UPI payouts (currently manual approval by admin)
- Real-time interview monitoring by client
- Transcript search / cross-study analytics
