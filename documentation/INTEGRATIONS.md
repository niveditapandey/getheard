# Integrations — GetHeard

All external services GetHeard connects to, how they're configured, and how to set them up.

---

## 1. Google Gemini (LLM)

**Used for:** All AI agents (Brief, Designer, Panel, Analysis, Pricing, Timeline, Interview)

**SDK:** `google-genai` (modern SDK, not VertexAI SDK)

**Two auth options:**

### Option A: Gemini API Key (Recommended — Free Tier Available)
```env
GEMINI_API_KEY=AIzaSy...
```
Get from: https://aistudio.google.com/app/apikey

**Models used:**
- `gemini-2.5-flash` — Real-time voice + chat agents (fast, cheap)
- `gemini-2.5-pro` — DesignerAgent + AnalysisAgent (high quality)

### Option B: Vertex AI (Enterprise)
```env
GCP_PROJECT_ID=your-project
GCP_LOCATION=us-central1
# Leave GEMINI_API_KEY empty — uses application default credentials
```
Requires: `gcloud auth application-default login`

**Fallback logic in code:**
```python
if settings.gemini_api_key:
    client = genai.Client(api_key=settings.gemini_api_key)
else:
    client = genai.Client(vertexai=True, project=settings.gcp_project_id)
```

---

## 2. Google Cloud Speech (STT + TTS)

**Used for:** Voice interview transcription and text-to-speech synthesis

**Services:**
- `google-cloud-speech` — Speech-to-Text (STT)
- `google-cloud-texttospeech` — Text-to-Speech (TTS)

**Auth:** Application Default Credentials
```bash
gcloud auth application-default login
gcloud services enable speech.googleapis.com
gcloud services enable texttospeech.googleapis.com
```

**Languages supported:**
```python
LANGUAGE_CODES = {
    "en": "en-US",    "hi": "hi-IN",    "id": "id-ID",
    "fil": "fil-PH",  "th": "th-TH",    "vi": "vi-VN",
    "ko": "ko-KR",    "ja": "ja-JP",    "zh": "zh-CN",
    "ta": "ta-IN",    "te": "te-IN",    "ml": "ml-IN",
    # ... all Indian regional languages
}
```

**TTS voices used:** Neural2 female voices per language (e.g., `en-US-Neural2-F`)

---

## 3. Sarvam AI (Indian Language STT + TTS)

**Used for:** Hindi and all Indian language interviews (better fluency than Google Cloud)

**API:** REST API with httpx

```env
SARVAM_API_KEY=sk_hfcqy7pg_...
VOICE_PROVIDER=auto   # Automatically routes Indian langs to Sarvam
```

**Endpoints used:**
- STT: `https://api.sarvam.ai/speech-to-text` (model: `saarika:v2`)
- TTS: `https://api.sarvam.ai/text-to-speech` (model: `bulbul:v1`)

**Auto-routing logic:**
```python
# settings.py
def should_use_sarvam(self, language_code: str) -> bool:
    if self.voice_provider == "sarvam":
        return True
    elif self.voice_provider == "google_cloud":
        return False
    else:  # auto
        return (language_code in self.indian_language_codes
                and self.has_sarvam_credentials)
```

**Indian language codes:** `hi, en-IN, ta, te, ml, kn, bn, mr, gu, pa, or`

---

## 4. Razorpay (Indian & SEA Payments)

**Used for:** INR payment collection from clients

**SDK:** `razorpay` Python package

```env
RAZORPAY_KEY_ID=rzp_live_SG70K7NZsGvuj0
RAZORPAY_KEY_SECRET=ZtcVjIMQSYBCSZ5DU6kDOjTU
```

**Flow:**
1. `POST /api/client/payment/initiate` → Creates Razorpay order
2. Frontend opens Razorpay checkout modal (using `key_id` + `order_id`)
3. User completes payment in modal
4. Razorpay returns `payment_id` + `signature` to frontend
5. `POST /api/client/payment/razorpay/verify` → Verifies HMAC-SHA256 signature
6. On success → project advances to `panel_building`

**Signature verification:**
```python
import razorpay
client = razorpay.Client(auth=(key_id, key_secret))
client.utility.verify_payment_signature({
    "razorpay_order_id": order_id,
    "razorpay_payment_id": payment_id,
    "razorpay_signature": signature
})
```

**Webhook setup (Razorpay dashboard):**
- URL: `https://getheard.space/api/client/payment/razorpay/verify`
- Events: `payment.captured`

**Keys location:** razorpay.com → Settings → API Keys

---

## 5. Stripe (International Payments)

**Used for:** USD/SGD/other currency payments from international clients

**SDK:** `stripe` Python package

```env
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
```

**Flow:**
1. `POST /api/client/payment/initiate` with `payment_method: stripe`
2. Server creates Stripe Checkout Session
3. Returns `checkout_url` to frontend
4. Frontend redirects user to Stripe hosted page
5. Stripe handles payment + redirects back to `/listen/study/{id}/status`

**Setup:** dashboard.stripe.com → Developers → API Keys

---

## 6. Resend (Transactional Email)

**Used for:** Study confirmation, report delivery, welcome emails

**API:** REST via `httpx`

```env
RESEND_API_KEY=re_bVAthYrA_FX6vyuxznbwqAQGsEW6J7mT4
RESEND_FROM_EMAIL=hello@getheard.space
```

**Domain verification status:** getheard.space
- SPF: ✅ Verified
- MX: ✅ Verified
- DKIM: ⏳ Propagating (added 27 Mar 2026)

**DNS records (Namecheap):**
| Type | Host | Value |
|------|------|-------|
| TXT | `resend._domainkey` | `p=MIGfMA0GCSqGSIb3DQEB...` |
| TXT | `send` | `v=spf1 include:amazonses.com ~all` |
| MX | `send` | `feedback-smtp.us-east-1.amazonses.com` |

**Usage:**
```python
from src.notifications.notifier import send_email

await send_email(
    to="client@company.com",
    subject="Your report is ready — GetHeard",
    html="<p>Your research report is ready. <a href='...'>View Report</a></p>"
)
```

**Domain verification check:**
```bash
curl https://api.resend.com/domains/44ace173-7e2c-4028-b25c-18022833d4b6 \
  -H "Authorization: Bearer re_bVAthYrA_..."
```

---

## 7. Meta WhatsApp Business API

**Used for:** Notifying respondents (selected, interview reminder, payout processed)

```env
WHATSAPP_PHONE_NUMBER_ID=985230514675305
WHATSAPP_BUSINESS_ID=2332652903923836
WHATSAPP_ACCESS_TOKEN=EAANDZA6ZCSSjoBRBu...   # 60-day token, refresh before expiry
```

**API:** `https://graph.facebook.com/v19.0/{phone_number_id}/messages`

**Usage:**
```python
from src.notifications.notifier import send_whatsapp

await send_whatsapp(
    to="+919876543210",
    message="You've been selected for a research panel! Reply YES to confirm."
)
```

**Template messages required for:**
- Panel selection notification
- Interview reminder
- Report ready (to client)
- Payout confirmation

**Create templates:** Meta Business Manager → WhatsApp → Message Templates

**Important:** The access token expires every 60 days. To get a permanent token:
1. Meta Business Manager → System Users → Create System User
2. Add WhatsApp Business account permissions
3. Generate permanent access token (never expires)

---

## 8. Twilio (WhatsApp Fallback + SMS)

**Used for:** WhatsApp text-based interview conversations (alternative to Meta API)

```env
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

**Setup:**
1. Console: [console.twilio.com](https://console.twilio.com)
2. Copy **Account SID** and **Auth Token** from Dashboard
3. Go to: **Messaging → Try it out → Send a WhatsApp message**
4. Sandbox: join code `join <word>-<word>` (send from your WhatsApp to activate)
5. Webhook URL: **Messaging → Settings → WhatsApp Sandbox Settings**
   - Set to: `https://getheard.space/webhook/whatsapp`

**Inbound webhook (`POST /webhook/whatsapp`):**
- Twilio sends form data: `From`, `Body`, `MessageSid`
- Handler routes to `WhatsAppHandler`
- `WhatsAppHandler` manages conversation sessions per phone number
- Response is TwiML XML with reply message

**Difference from Meta API:**
- Twilio = Sandbox (testing) + simpler API
- Meta = Production (template messages required for outbound)
- GetHeard supports both — Meta for outbound notifications, Twilio for inbound conversations

---

## 9. Google Cloud Platform (GCP)

**Project:** `getheard-484014`
**Region:** `us-central1`

**APIs enabled:**
- `speech.googleapis.com` (STT)
- `texttospeech.googleapis.com` (TTS)
- `aiplatform.googleapis.com` (Vertex AI — optional if using Gemini API key)

**Auth:** Application Default Credentials
```bash
gcloud auth application-default login
```

---

## Integration Health Check

Run this to verify all integrations:

```bash
curl http://localhost:8000/health
```

Expected response shows which services are configured:
```json
{
  "status": "healthy",
  "has_gemini": true,
  "has_sarvam": true,
  "has_razorpay": true,
  "has_stripe": false,
  "has_resend": true,
  "has_whatsapp_api": true,
  "has_twilio": true
}
```

---

## Credentials Summary

| Service | Where to Get | Expires? |
|---------|-------------|---------|
| Gemini API Key | aistudio.google.com | Never |
| Sarvam API Key | sarvam.ai dashboard | Never |
| Razorpay Key ID + Secret | razorpay.com/app/keys | Never |
| Stripe Keys | dashboard.stripe.com → API Keys | Never |
| Resend API Key | resend.com/api-keys | Never |
| Meta WhatsApp Token | Meta Business Manager → System User | 60 days (or permanent via system user) |
| Twilio SID + Token | console.twilio.com | Never |
| GCP Credentials | `gcloud auth application-default login` | 1 hour (auto-refreshes) |
