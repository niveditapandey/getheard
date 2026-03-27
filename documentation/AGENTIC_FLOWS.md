# Agentic Flows — GetHeard AI Pipeline

## Overview

GetHeard uses a multi-agent pipeline powered by **Google Gemini** (function-calling mode). Each agent is a specialised AI that performs one stage of the research process. Agents communicate by passing structured data (Python dicts / JSON), not by talking to each other directly.

All agents extend `BaseAgent` which handles the Gemini function-calling loop.

---

## BaseAgent: How All Agents Work

```
┌─────────────────────────────────────────────────┐
│                   BaseAgent.run()                │
│                                                  │
│  1. Build system prompt + tool definitions       │
│  2. Send to Gemini (gemini-2.5-flash or pro)     │
│  3. Gemini returns:                              │
│     a. Final text → return AgentResult           │
│     b. Tool call → execute handler → loop back   │
│  4. Max iterations: 10 (prevents infinite loops) │
└─────────────────────────────────────────────────┘
```

**Tools** are registered as `ToolSpec` objects:
```python
ToolSpec(
    name="save_brief",
    description="Save the completed research brief",
    parameters={
        "type": "object",
        "properties": {
            "project_name": {"type": "string"},
            "research_type": {"type": "string"},
            ...
        }
    },
    handler=self._handle_save_brief   # Python function called when tool invoked
)
```

---

## Agent 1: BriefAgent — Conversational Brief Intake

### Purpose
Collects research brief from client through natural conversation. Asks one topic at a time, adapts based on answers, and saves a structured brief when complete.

### Flow

```
Client opens /agent/brief or /listen/study/new
         │
         ▼
POST /agent/api/brief/start
  → BriefAgent session created (session_id returned)
  → Agent sends opening message
         │
         ▼
[Multi-turn conversation loop]
POST /agent/api/brief/message {session_id, message}
  → Gemini processes conversation history
  → Agent asks clarifying questions about:
      1. What are you trying to learn? (objective)
      2. Who is your target audience?
      3. What industry/product?
      4. How many respondents? (panel size)
      5. Which language(s)?
      6. Any specific topics to cover?
      7. What study type fits best?
         │
         ▼
[When brief is complete]
  → Gemini decides to call save_brief() tool
  → Handler saves brief to projects/{id}.json
  → Response includes {brief_saved: true, brief: {...}}
         │
         ▼
Client redirected to /listen/study/{id}/pricing
```

### Brief Output Schema
```json
{
  "project_name": "KYC Drop-off Study",
  "research_type": "pain_points",
  "industry": "Fintech",
  "objective": "Understand why users abandon KYC verification",
  "target_audience": "Mobile banking users aged 25-45 in India",
  "language": "hi",
  "topics": ["documentation requirements", "technical issues", "trust concerns"],
  "question_count": 10
}
```

---

## Agent 2: DesignerAgent — Question Generation

### Purpose
Takes a research brief and generates a set of high-quality, open-ended interview questions. Self-reviews the questions for quality before returning.

### Flow

```
Brief dict (from BriefAgent or form)
         │
         ▼
POST /agent/api/design {brief}
  → DesignerAgent.run()
  → Pass 1: Generate initial questions from brief
  → Gemini calls set_questions() tool with question list
  → Pass 2: Self-review — assess each question for:
      - Openness (not leading)
      - Clarity (plain language)
      - Relevance (matches brief objective)
      - Language appropriateness
  → Revise questions if needed
  → Return final question set
```

### Question Output Schema
```json
[
  {
    "number": 1,
    "type": "opening",
    "main": "Tell me about your experience with mobile banking verification.",
    "probe": "What were the most frustrating parts?",
    "intent": "Establish context and emotional baseline"
  },
  {
    "number": 2,
    "type": "exploratory",
    "main": "Walk me through what happened when you tried to complete your KYC.",
    "probe": "What specifically made you stop?",
    "intent": "Map the drop-off moment"
  }
  // ... more questions
]
```

---

## Agent 3: PanelAgent — Respondent Recruitment

### Purpose
Builds a research panel from either a client-provided CSV or GetHeard's respondent database. Validates, deduplicates, and ranks respondents.

### Flow — Mode A: CSV Upload

```
Client uploads CSV file
         │
         ▼
POST /panel/api/csv-upload {project_id, csv_text}
  → PanelAgent.build_panel_from_csv()
  → Parse CSV rows
  → Gemini validates each respondent:
      - Check required fields present
      - Detect duplicates (by phone)
      - Flag invalid entries
  → Return validated panel JSON
  → Save to panels/{panel_id}.json
  → Update respondent status → "scheduled"
```

### Flow — Mode B: Database Query

```
Project requirements (language, market, age, interests)
         │
         ▼
POST /panel/api/query {criteria}
  → PanelAgent.query_panel()
  → Search respondents/ directory for matches
  → Filter by: language, status=enrolled, country, age_range
  → Gemini ranks best matches based on:
      - Profile completeness
      - Language fluency
      - Interest relevance
      - Interview history (prefer fresh respondents)
  → Return ranked panel
  → Save to panels/{panel_id}.json
```

### Panel Output Schema
```json
{
  "panel_id": "panel_abc123",
  "project_id": "proj_xyz789",
  "source": "db",
  "respondents": [
    {
      "respondent_id": "r12345",
      "name": "Anjali Sharma",
      "language": "hi",
      "city": "Mumbai",
      "age_range": "25-34",
      "status": "scheduled"
    }
  ],
  "total": 20,
  "created_at": "2026-03-27T..."
}
```

---

## Agent 4: InterviewAgent / GeminiInterviewer

### Purpose
Conducts the actual voice interview. Manages conversation flow, asks questions in order, probes for depth, and determines when interview is complete.

### Flow

```
Respondent opens interview link
         │
         ▼
POST /api/start {session_id, language, project_id}
  → VoiceInterviewPipeline.start_interview()
  → GeminiInterviewer initialised with:
      - System prompt (role: professional interviewer)
      - Custom questions (from project)
      - Language code
  → Generate greeting text
  → TTS.synthesize_speech(greeting)
  → Return base64 MP3 audio
         │
         ▼
[Interview loop — for each respondent turn]
         │
POST /api/respond {audio_base64, session_id}
  → Decode audio
  → STT.transcribe(audio) → text
  → GeminiInterviewer.send_user_response(text)
      → Gemini maintains conversation history
      → Decides: ask probe? → next question? → close?
      → Returns (response_text, is_complete)
  → TTS.synthesize_speech(response_text) → audio
  → Save turn to conversation history
  → Return {transcript, audio_base64, is_complete}
         │
         ▼
[When is_complete = True]
POST /api/end/{session_id}
  → TranscriptManager.save()
  → transcripts/{timestamp}_{session}_{lang}.json
  → Increment project.interviews_completed
  → Credit respondent 80% of points
```

### Interview Logic (Gemini System Prompt)
The interviewer is instructed to:
1. Start with a warm greeting and context-setting
2. Ask the main question from the question list
3. If response is brief → ask the probe question
4. When satisfied → advance to next question
5. After all questions → close warmly, save transcript
6. Never lead or suggest answers
7. Match respondent's language register (formal/informal)

---

## Agent 5: AnalysisAgent — 4-Pass Report Generation

### Purpose
Generates a structured research report from all interview transcripts. Uses 4 sequential analysis passes for comprehensive coverage.

### Flow

```
POST /agent/api/reports/generate {project_id}
  → Load all transcript files for project
  → AnalysisAgent.analyze(transcripts, brief)
         │
         ▼
[Pass 1: Sentiment Analysis]
  → For each transcript, classify: positive / neutral / negative
  → Aggregate sentiment percentages
  → Identify sentiment drivers per category
         │
         ▼
[Pass 2: Theme Extraction]
  → Identify recurring themes across all transcripts
  → Count frequency + representative quotes per theme
  → Group sub-themes
  → Sort by frequency
         │
         ▼
[Pass 3: Question-by-Question Breakdown]
  → For each interview question:
      → Summarise what respondents said
      → Top response patterns
      → Notable quotes
      → Sentiment for that question
         │
         ▼
[Pass 4: Pain Points + Recommendations]
  → Extract specific pain points with severity
  → Identify positive highlights
  → Generate 3-5 actionable recommendations
  → Write executive summary (2-3 paragraphs)
         │
         ▼
[Save report]
  → reports/{report_id}.json
  → Update project status → "completed"
  → Send email to client (Resend)
```

### Report Output Schema
```json
{
  "report_id": "rep_abc123",
  "project_id": "proj_xyz789",
  "executive_summary": "Based on 20 interviews...",
  "methodology": {
    "total_respondents": 20,
    "languages": ["hi", "en"],
    "completion_rate": "95%"
  },
  "sentiment_overview": {
    "positive_pct": 35,
    "neutral_pct": 40,
    "negative_pct": 25
  },
  "key_themes": [
    {
      "theme": "Documentation Complexity",
      "frequency": 16,
      "frequency_pct": 80,
      "sentiment": "negative",
      "quotes": ["The document list kept changing", "..."]
    }
  ],
  "question_insights": [...],
  "pain_points": [...],
  "positive_highlights": [...],
  "recommendations": [...]
}
```

---

## Agent 6: PricingAgent — Dynamic Quote

### Purpose
Computes and presents a dynamic price quote after the brief is complete. Allows live adjustment of 3 levers.

### Flow

```
Brief saved → project.status = "briefing"
         │
         ▼
GET /listen/study/{id}/pricing
  → PricingAgent.present_quote(project_id)
  → Reads project dict (study_type, market, target_respondents)
  → Calls compute_quote() from pricing_store.py
  → Tool: compute_price({params}) → itemised breakdown
  → Returns quote dict + explanation text
         │
         ▼
Client adjusts levers on pricing page:
  ● Panel size slider (5–60)
  ● Panel source (GetHeard DB / Client CSV / Targeted)
  ● Study type (NPS / Feature / Pain Points / Custom)
  ● Incentive (₹ per head add-on)
  ● Urgency toggle (+25%)
         │
         ▼
[Debounced API call on each lever change]
POST /api/client/quote/compute {params}
  → compute_quote(params) → new totals
  → Return itemised JSON → UI updates live
         │
         ▼
Client clicks "Confirm Quote"
POST /api/client/quote/{id}/confirm
  → Save quote params to project
  → Advance to timeline
```

---

## Agent 7: TimelineAgent — Delivery Estimate

### Purpose
Estimates project delivery timeline broken into phases. Accounts for market complexity, panel source, and urgency.

### Flow

```
GET /api/client/timeline/{id}
  → If timeline not cached → TimelineAgent.estimate(project)
  → Tool: set_timeline({phases}) invoked by Gemini
         │
         ▼
[Phase calculation logic]

Phase 1: Panel Recruitment
  - DB source: 1-2 days
  - CSV source: 0 days (client provides)
  - Targeted: 3-5 days

Phase 2: Scheduling
  - Standard: 1 day
  - Japan/Korea: +1 day (scheduling complexity)

Phase 3: Interviews
  - Base: ceil(target/10) days (assuming 10 interviews/day)
  - Min: 1 day

Phase 4: Analysis
  - Standard: 1 day (AnalysisAgent)
  - Large panel (30+): 2 days

Phase 5: Report Delivery
  - Always: 0 days (instant on analysis complete)

[Urgency: compress all phases by 40%, add 25% fee]

Market complexity adjustments:
  JP, KR: +1 day (scheduling)
  CN: +2 days (coordination)
  Other Asia: no adjustment
```

### Timeline Output Schema
```json
{
  "phases": [
    {"name": "Panel Recruitment", "days": 2, "start_day": 1, "end_day": 2},
    {"name": "Scheduling", "days": 1, "start_day": 3, "end_day": 3},
    {"name": "Interviews", "days": 2, "start_day": 4, "end_day": 5},
    {"name": "Analysis", "days": 1, "start_day": 6, "end_day": 6},
    {"name": "Report Delivery", "days": 0, "start_day": 6, "end_day": 6}
  ],
  "total_days": 6,
  "estimated_delivery": "2026-04-02",
  "urgency_available": true,
  "urgency_delivery": "2026-03-31"
}
```

---

## Full End-to-End Pipeline Diagram

```
CLIENT                    PLATFORM                   RESPONDENT
  │                           │                           │
  │── Start Study ──────────► │                           │
  │                           │ BriefAgent chat           │
  │◄── Quote ─────────────── │ PricingAgent              │
  │── Pay ──────────────────► │                           │
  │                           │ PanelAgent recruits ─────►│
  │◄── Panel list ─────────── │                           │
  │── Approve ─────────────► │                           │
  │                           │◄── WhatsApp accept ────── │
  │                           │                           │
  │         [Interview window]│                           │
  │                           │◄── Voice audio ─────────── │
  │                           │ STT → Gemini → TTS ───────►│
  │                           │◄── Voice audio ─────────── │
  │                           │ ... (loop until complete) │
  │                           │                           │
  │                           │ TranscriptManager.save()  │
  │                           │ Points: +80% credited ───►│
  │                           │                           │
  │                           │ AnalysisAgent (4 passes)  │
  │◄── Report email ───────── │                           │
  │── View report ─────────► │                           │
  │                           │                           │
                              │◄── Redeem points ──────── │
                              │ Admin approves payout ───►│
```

---

## Gemini Model Usage

| Agent | Model | Reason |
|-------|-------|--------|
| BriefAgent | `gemini-2.5-flash` | Real-time chat, speed matters |
| InterviewAgent | `gemini-2.5-flash` | Real-time voice, low latency |
| PricingAgent | `gemini-2.5-flash` | Simple computation |
| TimelineAgent | `gemini-2.5-flash` | Simple computation |
| DesignerAgent | `gemini-2.5-pro` | Quality matters for questions |
| AnalysisAgent | `gemini-2.5-pro` | Deep analysis, quality matters |
| PanelAgent | `gemini-2.5-flash` | Ranking, not deep reasoning |

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Gemini API timeout | Retry once with 2s delay, then return error |
| Tool call fails | Log error, return partial result |
| Audio too short/silent | STT returns empty → Gemini asks "Could you repeat that?" |
| Max iterations reached | Return whatever text accumulated so far |
| Payment verification fails | Return 400, do not advance pipeline |
| Panel DB empty | Return 0 results, suggest CSV upload |
