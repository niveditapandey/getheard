# GetHeard vs Listen Labs — Gap Analysis
*Last updated: 2026-03-28*

Reference: Listen Labs ($100M raised, $500M valuation, 1M+ interviews, 8-figure ARR)
Blueprint source: compass_artifact_wf-e2babb75 (internal research doc)

---

## What's Built ✅

### Core Interview Engine
- [x] Real-time voice pipeline: STT → Gemini → TTS (fully async)
- [x] 9 languages: EN, HI, ID, FIL, TH, VI, KO, JA, ZH
- [x] Provider routing: Sarvam AI (Indian languages) + Google Cloud (others)
- [x] Adaptive probing, follow-up logic, multi-question custom studies
- [x] Transcript storage in Firestore (survives Cloud Run restarts)
- [x] WhatsApp interview channel (Twilio)

### Research Workflow
- [x] AI question design — Gemini Pro generates study-specific questions
- [x] Project management (create, brief, manage, list)
- [x] Research report generation with: personas, emotional journey, opportunity matrix, key themes, pain points, positive highlights, quotes, recommendations, research gaps
- [x] Reports saved to Firestore + local JSON fallback
- [x] **Research Agent** — NL queries over reports + transcripts ("show quotes about trust", "what are quick wins?")
- [x] **PowerPoint export** — branded 12-slide deck auto-generated from report

### Platform
- [x] FastAPI backend (40+ endpoints)
- [x] Web UI for interviews (browser-based, no app download)
- [x] Client portal with session auth
- [x] Admin dashboard
- [x] Respondent panel: enrollment, points/rewards system
- [x] Multi-tenant: clients → projects → sessions
- [x] Landing page
- [x] Deployed on Cloud Run (`getheard.space` via Cloudflare)
- [x] Firestore persistence across all key data types

---

## Gap Analysis — Remaining Work ❌

### 🔴 High Priority (biggest revenue/product impact)

| Feature | Listen Labs | GetHeard Status | Notes |
|---------|-------------|-----------------|-------|
| **Screener questions** | Pre-interview qualification filters | Not built | Critical for panel quality; prevents waste |
| **Quality / fraud detection** | Real-time scoring: voice patterns, tab-switching, contradictions, copy-paste | Not built | Industry-typical ~20% invalid responses |
| **Mission Control** | Cross-study NL queries, trend tracking over time | Not built | Compounding knowledge base = retention moat |
| **Cultural prompting for Asia** | Handles indirect communication, face-saving cultures | Partial (language routing only) | The core Asian market differentiator |
| **Project status dashboard** | Live interview counts, response rate, real-time progress | Basic only | Clients need to track studies in flight |

### 🟡 Medium Priority

| Feature | Listen Labs | GetHeard Status | Notes |
|---------|-------------|-----------------|-------|
| **Stimuli presentation** | Show images, videos, Figma prototypes during interview | Not built | Needed for UX/concept testing studies |
| **Video/emotion analysis** | Facial micro-expressions + tone + word choice | Not built | Emotional Intelligence layer |
| **Video highlight reels** | Auto-clips most impactful interview moments | Not built | High-value deliverable for clients |
| **Quantitative from qualitative** | Auto-generates charts/stats from open-ended data | Partial (sentiment %) | Close the loop between qual and quant |
| **Screener + conditional logic** | Branching screener questions, URL parameters | Not built | Required for precise targeting |
| **Panel scale** | 30M+ pre-qualified participants globally | Empty panel | Need distribution/recruitment strategy |
| **Third-party panel integrations** | Qualtrics, Rally, Forsta/Decipher | Not built | Enterprise clients need this |
| **Always-on Pulse tracking** | Continuous research mode, auto-surface trend shifts | Not built | Subscription retention feature |
| **PDF export (proper)** | Full print-optimised PDF | Browser print only | python-pptx PDF export or headless Chrome |
| **Branded report templates** | Client logo + colours in reports | Not built | Important for agency/reseller use |

### 🟠 Later / Infrastructure

| Feature | Listen Labs | GetHeard Status | Notes |
|---------|-------------|-----------------|-------|
| **SOC2 Type II / ISO certifications** | SOC2 T2, GDPR, ISO 42001, 27001, 27701 | Not started | Required for enterprise procurement |
| **Data residency controls** | GDPR / PDPA / DPDP compliance | Not built | Critical for Asia (India DPDP, Thailand PDPA) |
| **API for client integrations** | Public REST API | Internal only | Enables ecosystem / resellers |
| **Proactive research agent** | Autonomously generates hypotheses + runs research | Roadmap item | Listen Labs' stated future |
| **Multi-modal (video webcam)** | Video recording mode | Audio + text only | Higher engagement, richer data |

---

## Asian Market Differentiation — What We Must Build

From the research doc, these are the structural advantages GetHeard can build that Listen Labs won't prioritise:

1. **Indirect communication probing** — Prompts that draw out opinions from respondents who say "it was fine" when they mean "I hated it" (face-saving cultures: JP, KR, TH, VN)
2. **Dialect support** — Hindi variants (Bhojpuri, Marathi), regional Indonesian, Cantonese vs Mandarin
3. **Culturally-appropriate incentive structures** — UPI, GoPay, GCash, True Money (not just PayPal/Stripe)
4. **Local pricing** — Per-interview pricing in INR, IDR, THB not just USD
5. **Regional compliance** — India DPDP Act, Thailand PDPA, Indonesia PDPs, Singapore PDPA

---

## Competitive Moat Priority Order

1. Screener + fraud detection → panel quality (table stakes)
2. Mission Control → compounding value per client (retention)
3. Cultural prompting → Asian market differentiation (uniqueness)
4. Stimuli presentation → UX research use case (TAM expansion)
5. Video + emotion analysis → premium tier (pricing power)
