# How Listen Labs rebuilt qualitative research from scratch

Listen Labs is a San Francisco-based AI-first customer research platform that automates the entire qualitative research workflow — from study design through participant recruitment, AI-moderated interviews, and insight delivery — in hours rather than weeks. **Founded in 2023 by Alfred Wahlforss (CEO) and Florian Juengermann (CTO)** after pivoting from a viral AI avatar app called BeFake, the company has raised **$100M in total funding** at a $500M valuation, with Sequoia Capital and Ribbit Capital as lead investors. It is not YC-backed but was part of AI Grant (Nat Friedman / Daniel Gross). With over **1 million interviews conducted**, 8-figure ARR, and clients including Microsoft, Sweetgreen, Canva, Perplexity, and Robinhood, Listen Labs represents the clearest blueprint for how AI is reshaping the $140B market research industry — and the clearest model for what getHeard could adapt for Asian markets.

---

## The client experience: from brief to launch in minutes

Listen Labs structures the client journey around a **five-step workflow** designed to collapse the traditional 4–8 week research timeline into same-day execution.

**Step 1 — Co-design your approach.** A client clicks "New Study" from their dashboard. They provide project background, company context, study objectives, and hypotheses in free-text form. Alternatively, they can upload an existing discussion guide and the AI will parse it automatically. The platform then generates a draft discussion guide — a mix of open-ended and multiple-choice questions — in seconds. Built-in auto-QA flags methodological issues before launch. Expert-vetted templates are available for common use cases (concept testing, brand tracking, usability testing, creative testing, consumer journey mapping, churn analysis, diary studies, and multi-market segmentation).

**Step 2 — Define and recruit your audience.** Clients choose from four recruitment methods: Listen's built-in panel of **30M+ pre-qualified participants** spanning 200+ countries (B2B and B2C), a direct shareable link for their own customers, integration with external panel providers (Qualtrics, Rally, Forsta/Decipher), or a combination. Clients set targeting criteria — demographics, professional roles, behavioral attributes, usage patterns — along with quotas and response limits. Screener questions, conditional logic, and URL parameters are supported. The platform also supports CSV upload for analyzing existing open-ended survey responses.

**Step 3 — AI-moderated interviews run autonomously.** Once launched, the AI conducts interviews asynchronously — respondents participate whenever and wherever they want. Clients can provide the AI with extensive context so it behaves as a subject-matter expert on their product, brand, or category.

**Step 4 — Analyze with a Research Agent.** After interviews complete, a natural-language "Research Agent" (described internally as "Claude Code for research") generates custom deliverables on command. Clients can ask it to "create slides summarizing main findings," "build a breakdown by segment," or "show all quotes where users mentioned feeling confused."

**Step 5 — Compound knowledge across studies.** A feature called "Mission Control" enables cross-study queries, trend tracking over time, and cited answers from the client's entire research library. A continuous research mode called "Listen Pulse" supports always-on tracking, analyzing tens of thousands of responses and surfacing trend shifts automatically.

---

## What respondents actually experience

The respondent side of Listen Labs is designed to feel like a **natural one-on-one conversation** rather than a traditional survey, and runs entirely in the web browser with no app download required.

Respondents are either sourced from Listen's 30M+ panel (with detailed profile data enabling precise targeting), recruited via a direct link shared by the client, or routed from integrated third-party panels. A proprietary **Quality Guard / fraud detection system** analyzes voice patterns, response depth, tab-switching, copy-paste behavior, contradictions, and repeat respondents in real-time. Every response receives a quality score; low-quality ones are automatically removed and replaced at no extra cost. Listen claims this reduces invalid responses from the industry-typical **~20% down to near zero**.

The interview itself offers **three modalities**: video recording (webcam-on conversation), audio-only chat, or text-based exchange. The AI interviewer operates like a skilled human moderator — it asks personalized, adaptive questions from the discussion guide, then generates intelligent follow-up probes based on what the respondent actually says. During interviews, the AI can present **stimuli** including videos, images, landing pages, and interactive Figma prototypes. Screen-sharing sessions (mobile and desktop) are supported for usability testing, with the AI observing navigation behavior.

A multi-modal **Emotional Intelligence** feature analyzes three signal layers simultaneously: tone of voice, facial micro-expressions, and word choice. Built on Ekman's six core emotions plus UX-specific ones (confusion, frustration), every detected emotion links to an exact timestamp and verbatim quote. The platform reports a **98% participant satisfaction rate** and responses that average **3x longer** than traditional survey methods — likely because the non-judgmental AI interface reduces social desirability bias and the conversational format encourages elaboration. All interviews support automatic translation and transcription in **100+ languages** (50+ for voice specifically), with the AI conducting interviews natively in the respondent's language.

---

## Deliverables: from transcripts to boardroom-ready slide decks

Listen Labs outputs a layered stack of deliverables, ranging from raw data to executive-ready presentations. This is arguably where the platform delivers the most differentiated value versus traditional research firms.

**Automated outputs include:** executive summaries with key takeaways, thematic analysis with automatically identified top themes, auto-generated user personas, quantitative metrics derived from qualitative conversations (charts from open-ended data), video highlight reels of the most impactful interview moments, full verbatim transcripts of every interview, notable quotes with contextual metadata, sentiment and emotional intelligence data, and interactive reports that clients can explore dynamically. The platform also auto-generates **PowerPoint slide decks** in branded templates — a capability the engineering team built by reverse-engineering PowerPoint's XML format because existing libraries were insufficient.

The **Research Agent** layer sits on top, allowing clients to issue natural-language commands to generate additional analysis on demand: segmented analysis with significance testing, custom CSV exports with thematic coding, chart creation, and quote retrieval. It can incorporate document uploads and web search to enrich findings. Every insight is traceable back to its source — the specific interview moment, verbatim quote, and timestamp. Reports are delivered through an interactive web dashboard, with export options for PowerPoint, PDF, and CSV.

The **Mission Control** feature transforms individual studies into a compounding knowledge base. Clients ask questions across their entire research library and get cited answers in seconds. This positions Listen not just as a project-based tool but as a persistent **"customer observability layer"** — a system of record for what customers think, want, and feel, updated continuously.

---

## Speed, pricing, and the unit economics of AI research

Listen Labs' core value proposition is speed: **results in hours, not weeks.** The homepage prominently displays a typical turnaround of **under 14 hours**. Responses begin arriving within minutes of launch. In the Microsoft case study, Romani Patel (Senior Research Manager) reported that traditional agency research taking 6–8 weeks was compressed to a single day. Emerald Research Group interviewed 60 participants in under a week versus the typical month needed for 20–30 with human moderators. Simple Modern went from zero to 120 nationwide interviews in 2.5 hours.

**Pricing is not publicly listed** — it's custom and enterprise-focused, requiring a demo booking. However, multiple data points suggest the model: competitor comparison sources estimate **$85–$150 per completed interview** depending on audience complexity and annual volume commitments. Another source indicates studies start from as low as $200 for small sample sizes, with typical customer research studies (30+ minute interviews with 200–300 customers, full analysis, and reporting) costing in the **low-to-mid thousands**. Enterprise packages likely run $15K+. Microsoft's Romani Patel stated Listen delivered at **"one-third the cost"** of traditional research. The model appears to be **usage-based per completed conversation** with tiered volume commitments. A free trial exists (via a "Try for Free" button on the homepage), though the depth of the free tier is unclear.

The company holds SOC 2 Type II, GDPR, ISO 42001, ISO 27001, and ISO 27701 certifications, and explicitly states it does not train AI models on customer data.

---

## The voice pipeline and technical architecture

Listen Labs' technical approach is built on a **multi-model architecture** — not locked to a single AI provider, allowing rapid adoption of the latest capabilities. The company was an early Azure OpenAI Service partner (through Microsoft for Startups) and its Research Agent is built on Claude (Anthropic).

Florian Juengermann described the real-time voice pipeline in detail on LinkedIn. The process works in five stages: **(1)** Voice recording is streamed and transcribed in real-time; **(2)** as soon as the respondent stops speaking, the transcript is sent to GPT-4; **(3)** GPT-4 streams the response back token by token; **(4)** once a somewhat complete sentence forms, the text chunk is sent to a text-to-speech server; **(5)** the server streams synthetic voice back and plays it as bytes arrive. Juengermann described this as "the fastest GPT-4 audio pipeline on the planet" at the time of development.

The engineering team is exceptionally strong: **30% of engineers are International Olympiad in Informatics (IOI) medalists**, including founding engineer Tobias Schindler (previously Jane Street and Tesla Autopilot, IOI silver medalist, 3x ICPC world finalist). The company went from $10M to $20M+ ARR in about 4 months with just 33 team members — an indicator of extreme product leverage. The team now numbers roughly 57 and plans to reach 150 in 2026. Notably, Listen hires engineers for non-engineering roles (marketing, growth, operations), betting that technical fluency matters everywhere in the AI era.

---

## The competitive landscape and what it means for getHeard

Listen Labs' closest competitor is **Outset.ai** (YC-backed, $21M raised, similar end-to-end workflow with AI interviews in 40+ languages). Other direct competitors include **Conveo** (European-focused, backed by agencies like Unilever and Orange), **Quals AI** (UK-based, 24-hour turnaround), **Qualz.ai** (15 pre-built frameworks, voice-to-voice), **UserCall** (voice-first, PostHog integration for event-triggered research), and **Glaut** (white-label for agencies like IPSOS and Kantar). Analysis-only platforms like Dovetail, NVivo, and HeyMarvin compete on the back end but don't conduct interviews.

Listen differentiates through five key advantages: **(1)** sheer scale of funding ($100M vs. $21M for the next-largest competitor) enabling aggressive enterprise sales and product investment; **(2)** its 30M+ participant panel, which is larger than most competitors'; **(3)** a proprietary fraud detection system that addresses the industry's biggest quality problem; **(4)** the compounding knowledge base (Mission Control) that shifts the value proposition from project-based to persistent intelligence; and **(5)** a stated roadmap toward a fully **proactive AI research agent** that autonomously generates hypotheses, tests them, and runs research — essentially automating YC's "write code, talk to users" loop.

Versus traditional research firms (Nielsen, Kantar, focus group facilities), the disruption is stark. Traditional qualitative research typically involves 6–8 week timelines, five-figure budgets, and sample sizes of 20–30 participants. Listen delivers equivalent depth at 10x the scale in 1/10th the time at 1/3rd the cost. However, the industry isn't without skepticism: 419 experienced qualitative researchers from 32 countries published a paper in *Qualitative Inquiry* (2025) rejecting generative AI for "reflexive qualitative research," arguing it loses interpretive depth. Group dynamics from focus groups still hold value for certain research designs. The practical reality is that commercial adoption is accelerating regardless.

---

## The Asian market gap getHeard should exploit

The competitive analysis reveals a significant whitespace: **no AI-native qualitative research platform is purpose-built for Asian markets.** Listen Labs supports 100+ languages but is US/enterprise-focused. Outset covers 40+ languages with the same Western-centric orientation. Research from FUEL Asia confirms that commercial AI qual platforms "work better with some languages than others," and that **localized pricing along with culturally attuned development will be critical for APAC adoption**.

Several factors make Asia structurally different. Face-saving cultures and indirect communication styles require different probing strategies than Western directness. Hierarchical dynamics distort group-based research more severely in Asian contexts. The linguistic complexity is immense — Mandarin, Cantonese, Japanese, Korean, Thai, Vietnamese, Bahasa Indonesia/Malaysia, Hindi, Tamil, Tagalog, each with dialectal variations that off-the-shelf models handle unevenly. The APAC research industry remains largely traditional (firms like Kadence, Milieu, and Divergent still rely on human moderators and face-to-face IDIs), meaning the disruption opportunity parallels where the US market was 18–24 months ago.

For getHeard, the Listen Labs blueprint suggests prioritizing five things: an end-to-end workflow that collapses study setup to minutes; a real-time voice pipeline optimized for Asian languages; a fraud detection system (critical for panel quality in markets with high incentive-driven fraud); culturally-adapted AI interviewing styles that handle indirect communication; and a deliverables engine that produces boardroom-ready outputs automatically. The $140B global market research industry is being remade. Asia's share of that market — and the absence of a credible AI-native player — represents a clear opening.