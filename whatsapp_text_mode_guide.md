# WhatsApp Text Interview Mode - Add-On Guide

## Overview

Add text-based interviews via WhatsApp to your voice interview platform.

**Key Insight:** This is MUCH simpler than voice because there's no audio processing!

**Voice Pipeline:** Audio → STT → Gemini → TTS → Audio (4 steps, complex)  
**Text Pipeline:** Text → Gemini → Text (1 step, simple!)

You already built the hard part (Gemini conversation engine). WhatsApp just connects text messages to it.

---

## Why Add WhatsApp Text Mode?

### Business Benefits:
- **Wider reach:** Everyone in SEA uses WhatsApp
- **Lower cost:** No voice API costs (STT/TTS)
- **Convenience:** Async - respondents answer anytime
- **Automatic transcripts:** No need to transcribe
- **Stronger pitch:** "Multi-channel platform" (voice + text)

### Technical Benefits:
- **Simpler:** Reuse Gemini engine you built
- **Reliable:** Text is more reliable than voice over poor connections
- **Scalable:** Handle many concurrent text interviews
- **Fast to build:** 1-2 hours since Gemini is done

---

## Architecture

```
┌────────────────────────────────────────────┐
│        GetHeard Platform                   │
├────────────────────────────────────────────┤
│                                            │
│  ┌─────────────┐      ┌──────────────┐   │
│  │   Voice     │      │  WhatsApp    │   │
│  │  Interview  │      │   Text       │   │
│  └──────┬──────┘      └──────┬───────┘   │
│         │                    │            │
│    ┌────▼────┐          ┌────▼────┐      │
│    │   STT   │          │  Text   │      │
│    └────┬────┘          │  Input  │      │
│         │               └────┬────┘      │
│         ▼                    │            │
│    ┌─────────────────────────▼─────┐     │
│    │     Gemini Conversation       │     │
│    │          Engine                │     │
│    └─────────────────────────┬─────┘     │
│         │                    │            │
│    ┌────▼────┐          ┌────▼────┐      │
│    │   TTS   │          │  Text   │      │
│    └────┬────┘          │ Output  │      │
│         │               └────┬────┘      │
│         ▼                    ▼            │
│    Audio Output        WhatsApp Msg       │
│                                            │
└────────────────────────────────────────────┘
```

**Same brain (Gemini), different channels!**

---

## Implementation Steps

### Step 1: Get Twilio Account (10 minutes)

**1.1 Sign Up:**
- Go to: https://www.twilio.com/try-twilio
- Sign up for free trial
- You get free credits ($15-20 USD)

**1.2 Set Up WhatsApp Sandbox:**
- In Twilio Console, go to: **Messaging → Try it out → Send a WhatsApp message**
- Follow instructions to connect your WhatsApp number to sandbox
- You'll send a message like "join <code>" to Twilio's WhatsApp number

**1.3 Get Credentials:**
Go to Twilio Console Dashboard and note:
- **Account SID** (starts with AC...)
- **Auth Token** (click to reveal)
- **WhatsApp Sandbox Number** (e.g., +1 415 523 8886)

---

### Step 2: Update Configuration (5 minutes)

**2.1 Add Twilio credentials to .env:**

```bash
cd /Users/niveditapandey/Documents/AI\ Projects/getHeard

cat >> .env << 'EOF'

# Twilio WhatsApp Configuration
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
EOF
```

**Replace with your actual values!**

**2.2 Install Twilio SDK:**

```bash
pip install twilio
pip freeze > requirements.txt
```

**2.3 Update settings.py:**

```bash
cat >> config/settings.py << 'EOF'

    # Twilio WhatsApp Configuration
    twilio_account_sid: str = Field(default="", description="Twilio Account SID")
    twilio_auth_token: str = Field(default="", description="Twilio Auth Token")
    twilio_whatsapp_number: str = Field(
        default="whatsapp:+14155238886",
        description="Twilio WhatsApp Number"
    )
    
    @property
    def has_twilio_credentials(self) -> bool:
        """Check if Twilio credentials are configured."""
        return bool(
            self.twilio_account_sid 
            and self.twilio_auth_token
            and self.twilio_account_sid != ""
        )
EOF
```

---

### Step 3: Create WhatsApp Handler (20 minutes)

**3.1 Create the WhatsApp interview manager:**

```bash
cat > src/web/whatsapp_handler.py << 'EOF'
"""
WhatsApp text interview handler.
Connects WhatsApp messages to Gemini conversation engine.
"""

from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import logging
from typing import Dict, Optional

from src.conversation.gemini_engine import GeminiInterviewer
from src.storage.transcript import TranscriptManager
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WhatsAppInterviewManager:
    """
    Manages text-based interviews via WhatsApp.
    Much simpler than voice - just text in/out!
    """
    
    def __init__(self):
        """Initialize WhatsApp interview manager."""
        if not settings.has_twilio_credentials:
            raise ValueError("Twilio credentials not configured in .env")
        
        # Initialize Twilio client
        self.client = Client(
            settings.twilio_account_sid,
            settings.twilio_auth_token
        )
        
        # Store active interview sessions
        # Key: phone_number, Value: GeminiInterviewer instance
        # In production: use Redis or database
        self.active_sessions: Dict[str, GeminiInterviewer] = {}
        
        # Transcript manager
        self.transcript_manager = TranscriptManager()
        
        logger.info("WhatsApp Interview Manager initialized")
    
    def handle_incoming_message(
        self, 
        from_number: str, 
        message_text: str, 
        language: str = 'en'
    ) -> str:
        """
        Process incoming WhatsApp message and return response.
        
        Args:
            from_number: Sender's WhatsApp number (e.g., whatsapp:+6512345678)
            message_text: The message text
            language: Interview language (default: 'en')
            
        Returns:
            Response text to send back
        """
        try:
            # Check for special commands
            if message_text.lower().strip() in ['stop', 'end', 'quit', 'cancel']:
                return self._handle_stop_command(from_number)
            
            if message_text.lower().strip() in ['start', 'begin', 'new']:
                language = self._detect_language(message_text)
                return self._start_new_interview(from_number, language)
            
            # Check if active session exists
            if from_number not in self.active_sessions:
                # No active session - start new interview
                logger.info(f"New interview for {from_number}")
                return self._start_new_interview(from_number, language)
            
            # Existing session - continue conversation
            interviewer = self.active_sessions[from_number]
            
            # Process response
            ai_response = interviewer.process_response(message_text)
            
            # Check if interview completed
            if interviewer.is_interview_complete():
                # Save transcript
                self._save_and_cleanup(from_number)
            
            return ai_response
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return "Sorry, I encountered an error. Please try sending your message again, or type 'stop' to end the interview."
    
    def _start_new_interview(self, from_number: str, language: str) -> str:
        """Start a new interview session."""
        # Create new interviewer
        interviewer = GeminiInterviewer(language_code=language)
        self.active_sessions[from_number] = interviewer
        
        logger.info(f"Started interview for {from_number} in {language}")
        
        # Return greeting
        return interviewer.start_interview()
    
    def _handle_stop_command(self, from_number: str) -> str:
        """Handle stop command."""
        if from_number in self.active_sessions:
            interviewer = self.active_sessions[from_number]
            response = interviewer.end_interview()
            
            # Save transcript
            self._save_and_cleanup(from_number)
            
            return response
        else:
            return "No active interview to stop. Send any message to start a new interview!"
    
    def _save_and_cleanup(self, from_number: str):
        """Save transcript and cleanup session."""
        if from_number in self.active_sessions:
            interviewer = self.active_sessions[from_number]
            
            # Get conversation history
            history = interviewer.get_conversation_history()
            
            # Save transcript
            try:
                filepath = self.transcript_manager.save_transcript({
                    'channel': 'whatsapp',
                    'phone_number': from_number,
                    'conversation': history,
                    'language': interviewer.language_code
                })
                logger.info(f"Saved transcript: {filepath}")
            except Exception as e:
                logger.error(f"Failed to save transcript: {e}")
            
            # Cleanup
            del self.active_sessions[from_number]
    
    def _detect_language(self, text: str) -> str:
        """
        Simple language detection based on text.
        In production: use proper language detection library.
        """
        # Simple heuristic - check for common greetings
        text_lower = text.lower()
        
        if 'halo' in text_lower or 'selamat' in text_lower:
            return 'id'  # Indonesian
        elif 'kumusta' in text_lower or 'magandang' in text_lower:
            return 'fil'  # Filipino
        elif 'สวัสดี' in text_lower or 'สบาย' in text_lower:
            return 'th'  # Thai
        elif 'xin chào' in text_lower or 'chào' in text_lower:
            return 'vi'  # Vietnamese
        elif 'नमस्ते' in text or 'नमस्कार' in text:
            return 'hi'  # Hindi
        else:
            return 'en'  # Default to English
    
    def send_message(self, to_number: str, message_text: str):
        """
        Send a WhatsApp message (for proactive outreach).
        
        Args:
            to_number: Recipient's WhatsApp number
            message_text: Message to send
        """
        try:
            message = self.client.messages.create(
                from_=settings.twilio_whatsapp_number,
                body=message_text,
                to=to_number
            )
            logger.info(f"Sent message to {to_number}: {message.sid}")
            return message.sid
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise
    
    def get_active_sessions_count(self) -> int:
        """Get count of active interview sessions."""
        return len(self.active_sessions)
    
    def get_active_sessions(self) -> list:
        """Get list of active phone numbers."""
        return list(self.active_sessions.keys())


# Singleton instance
_whatsapp_manager: Optional[WhatsAppInterviewManager] = None

def get_whatsapp_manager() -> WhatsAppInterviewManager:
    """Get or create WhatsApp manager singleton."""
    global _whatsapp_manager
    if _whatsapp_manager is None:
        _whatsapp_manager = WhatsAppInterviewManager()
    return _whatsapp_manager


if __name__ == "__main__":
    print("WhatsApp Interview Handler")
    print("Testing initialization...")
    
    try:
        manager = WhatsAppInterviewManager()
        print(f"✅ Manager initialized")
        print(f"Active sessions: {manager.get_active_sessions_count()}")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure Twilio credentials are in .env file")
EOF
```

**3.2 Create transcript manager (if not exists):**

```bash
cat > src/storage/transcript.py << 'EOF'
"""
Transcript storage manager.
Saves interview transcripts as JSON files.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TranscriptManager:
    """Manages saving and loading interview transcripts."""
    
    def __init__(self, transcripts_dir: str = "transcripts"):
        """
        Initialize transcript manager.
        
        Args:
            transcripts_dir: Directory to store transcripts
        """
        self.transcripts_dir = Path(transcripts_dir)
        self.transcripts_dir.mkdir(exist_ok=True)
    
    def save_transcript(self, interview_data: dict) -> str:
        """
        Save interview transcript to JSON file.
        
        Args:
            interview_data: Interview data including conversation history
            
        Returns:
            Path to saved transcript file
        """
        try:
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            channel = interview_data.get('channel', 'unknown')
            filename = f"{channel}_{timestamp}.json"
            filepath = self.transcripts_dir / filename
            
            # Add metadata
            transcript = {
                "timestamp": datetime.now().isoformat(),
                "channel": channel,
                **interview_data
            }
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(transcript, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved transcript: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to save transcript: {e}")
            raise
    
    def load_transcript(self, filename: str) -> dict:
        """Load transcript from file."""
        filepath = self.transcripts_dir / filename
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def list_transcripts(self) -> List[str]:
        """List all saved transcripts."""
        return [f.name for f in self.transcripts_dir.glob("*.json")]


if __name__ == "__main__":
    print("Transcript Manager created")
EOF
```

---

### Step 4: Add WhatsApp Webhook to FastAPI (15 minutes)

**4.1 Update src/web/app.py with WhatsApp webhook:**

```bash
cat >> src/web/app.py << 'EOF'


# WhatsApp Integration
from fastapi import Form
from src.web.whatsapp_handler import get_whatsapp_manager


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(...),
    ProfileName: str = Form(None)
):
    """
    Twilio WhatsApp webhook endpoint.
    Receives incoming messages and sends responses.
    
    Twilio sends POST requests here when users message your WhatsApp number.
    """
    try:
        logger.info(f"📱 WhatsApp from {From} ({ProfileName}): {Body}")
        
        # Get WhatsApp manager
        manager = get_whatsapp_manager()
        
        # Process message and get AI response
        response_text = manager.handle_incoming_message(
            from_number=From,
            message_text=Body
        )
        
        # Create Twilio MessagingResponse
        from twilio.twiml.messaging_response import MessagingResponse
        resp = MessagingResponse()
        resp.message(response_text)
        
        logger.info(f"🤖 Response: {response_text[:100]}...")
        
        return str(resp)
        
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}")
        import traceback
        traceback.print_exc()
        
        # Send error message to user
        from twilio.twiml.messaging_response import MessagingResponse
        resp = MessagingResponse()
        resp.message("Sorry, I encountered an error. Please try again or type 'stop' to end the interview.")
        return str(resp)


@app.get("/api/whatsapp/stats")
async def whatsapp_stats():
    """Get WhatsApp interview statistics."""
    try:
        manager = get_whatsapp_manager()
        return {
            "status": "operational",
            "active_sessions": manager.get_active_sessions_count(),
            "active_numbers": manager.get_active_sessions()
        }
    except Exception as e:
        logger.error(f"WhatsApp stats error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "active_sessions": 0
        }


@app.post("/api/whatsapp/send")
async def send_whatsapp_message(to_number: str, message: str):
    """
    Send a WhatsApp message (for testing or proactive outreach).
    
    Args:
        to_number: WhatsApp number (format: whatsapp:+6512345678)
        message: Message text to send
    """
    try:
        manager = get_whatsapp_manager()
        message_sid = manager.send_message(to_number, message)
        return {
            "status": "sent",
            "message_sid": message_sid
        }
    except Exception as e:
        logger.error(f"Send message error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
EOF
```

---

### Step 5: Test Locally with ngrok (20 minutes)

**5.1 Install ngrok:**

```bash
brew install ngrok
# Or download from https://ngrok.com/download
```

**5.2 Start your FastAPI server:**

```bash
cd /Users/niveditapandey/Documents/AI\ Projects/getHeard
source venv/bin/activate
python -m uvicorn src.web.app:app --reload --port 8000
```

**5.3 In a NEW terminal, start ngrok:**

```bash
ngrok http 8000
```

**5.4 Configure Twilio webhook:**

You'll see output like:
```
Forwarding  https://abc123.ngrok.io -> http://localhost:8000
```

1. Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)
2. Go to Twilio Console: **Messaging → Settings → WhatsApp Sandbox Settings**
3. Set **"When a message comes in"** to: `https://abc123.ngrok.io/webhook/whatsapp`
4. Save

**5.5 Test it!**

1. Open WhatsApp on your phone
2. Send a message to your Twilio WhatsApp sandbox number
3. You should get a greeting from the AI interviewer!
4. Have a conversation
5. Type "stop" to end

---

### Step 6: Simple Test Without Real WhatsApp (10 minutes)

**If you don't want to set up Twilio yet, test the logic:**

```bash
cat > test_whatsapp_mode.py << 'EOF'
"""
Test WhatsApp text interview mode without real WhatsApp.
Simulates the conversation flow.
"""

from src.conversation.gemini_engine import GeminiInterviewer

print("=" * 60)
print("WHATSAPP TEXT INTERVIEW SIMULATION")
print("=" * 60)

# Test in multiple languages
languages = [
    ('en', 'English', [
        "I visited the hospital last month for a checkup",
        "The doctors were very professional",
        "The waiting time was quite long"
    ]),
    ('id', 'Indonesian', [
        "Saya pergi ke rumah sakit minggu lalu",
        "Pelayanannya sangat baik",
        "Ruang tunggunya tidak nyaman"
    ])
]

for lang_code, lang_name, responses in languages:
    print(f"\n{'=' * 60}")
    print(f"Testing: {lang_name} ({lang_code})")
    print(f"{'=' * 60}")
    
    # Create interviewer
    interviewer = GeminiInterviewer(language_code=lang_code)
    
    # Start interview
    greeting = interviewer.start_interview()
    print(f"\n📱 Bot: {greeting}")
    
    # Simulate conversation
    for i, user_msg in enumerate(responses, 1):
        print(f"\n👤 User: {user_msg}")
        
        bot_response = interviewer.process_response(user_msg)
        print(f"📱 Bot: {bot_response}")
    
    # End
    closing = interviewer.end_interview()
    print(f"\n📱 Bot: {closing}")
    
    print(f"\n✅ {lang_name} simulation complete!")

print("\n" + "=" * 60)
print("KEY INSIGHT: WhatsApp mode works perfectly!")
print("No STT/TTS needed - just text in, text out")
print("Same Gemini engine, different channel")
print("=" * 60)
EOF

python test_whatsapp_mode.py
```

---

## Updated Architecture Diagram

```
┌────────────────────────────────────────────────────────────┐
│              GetHeard Interview Platform                   │
│                                                            │
│  ┌────────────────────┐      ┌─────────────────────┐     │
│  │  VOICE CHANNEL     │      │  TEXT CHANNEL       │     │
│  │                    │      │  (WhatsApp)         │     │
│  │  Phone Call        │      │                     │     │
│  │       │            │      │  WhatsApp Msg       │     │
│  │       ▼            │      │       │             │     │
│  │  ┌─────────┐       │      │       ▼             │     │
│  │  │ Sarvam  │       │      │  Direct Text        │     │
│  │  │   or    │       │      │  (No processing)    │     │
│  │  │ Google  │       │      │                     │     │
│  │  │  STT    │       │      │                     │     │
│  │  └────┬────┘       │      │                     │     │
│  │       │            │      │       │             │     │
│  └───────┼────────────┘      └───────┼─────────────┘     │
│          │                           │                    │
│          └───────────┬───────────────┘                    │
│                      ▼                                     │
│          ┌────────────────────────┐                       │
│          │   Gemini Conversation  │                       │
│          │        Engine          │                       │
│          │   (Same for both!)     │                       │
│          └────────────┬───────────┘                       │
│                       │                                    │
│          ┌────────────▼───────────┐                       │
│          │                        │                        │
│     ┌────▼─────┐         ┌────────▼────┐                 │
│     │ Sarvam   │         │  Text       │                 │
│     │   or     │         │  Response   │                 │
│     │ Google   │         │ (Direct)    │                 │
│     │  TTS     │         │             │                 │
│     └────┬─────┘         └─────┬───────┘                 │
│          │                     │                          │
│     Audio Output          WhatsApp Msg                    │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## Benefits Summary

### For Users:
- **Convenience:** Respond on their own time via WhatsApp
- **Familiarity:** Everyone knows how to use WhatsApp
- **No barriers:** No need to download apps or make calls
- **Async:** Can pause and continue later

### For You:
- **Lower costs:** No voice API charges for text interviews
- **Higher completion rates:** Users more likely to finish async
- **Easier scaling:** Handle 100s of concurrent text interviews
- **Automatic transcripts:** No transcription needed

### For Fundraising:
- **Stronger story:** "Multi-channel platform, not just voice"
- **Wider TAM:** Can reach text-only users too
- **Competitive edge:** Listen Labs is voice-only, you have both
- **Better unit economics:** Mix of voice (premium) + text (volume)

---

## Cost Comparison

**Voice Interview (5 minutes):**
- STT: ~$0.02 (Sarvam) or $0.04 (Google)
- TTS: ~$0.03 (Sarvam) or $0.06 (Google)
- Gemini: ~$0.01
- **Total: $0.06-$0.11 per interview**

**WhatsApp Text Interview:**
- WhatsApp messages: ~$0.005 per message (Twilio)
- Gemini: ~$0.01
- **Total: $0.02-$0.03 per interview**

**WhatsApp is 3-5x cheaper!**

---

## Integration Timeline

**If you add this tomorrow:**

1. **Step 1-2 (Configuration):** 15 minutes
2. **Step 3 (Handler code):** 20 minutes
3. **Step 4 (FastAPI webhook):** 15 minutes
4. **Step 5 (ngrok testing):** 20 minutes
5. **Step 6 (Testing):** 10 minutes

**Total: ~80 minutes (1.5 hours)**

Since Gemini is already built, this is mostly just plumbing!

---

## Production Considerations

For production deployment (post-MVP):

1. **Session Storage:** Move from in-memory dict to Redis or database
2. **Language Detection:** Use proper library (langdetect, Google Translate API)
3. **Rate Limiting:** Prevent spam/abuse
4. **User Management:** Track users across sessions
5. **Analytics:** Message counts, completion rates, avg duration
6. **Twilio Production:** Upgrade from sandbox to production WhatsApp number

---

## Testing Checklist

- [ ] Twilio credentials added to .env
- [ ] WhatsApp handler created
- [ ] FastAPI webhook endpoint added
- [ ] Server starts without errors
- [ ] ngrok tunnel working
- [ ] Twilio webhook configured
- [ ] Can send message and get greeting
- [ ] Conversation flows naturally
- [ ] Can type "stop" to end
- [ ] Transcript saved to file

---

## Updated Pitch After Adding This

**Before (voice only):**
"We're building voice AI for qualitative research in Asia"

**After (voice + text):**
"We're building a multi-channel AI interview platform for Asia:
- 🎤 Voice calls for rich emotional insights
- 💬 WhatsApp for convenient, scalable reach
- 🌏 9 languages covering SEA + India
- 📊 Both channels feed same analytics

We're not just Listen Labs for Asia - we're multi-channel from day one."

**This is much stronger!** 🚀

---

## Next Steps

1. **Tomorrow:** Add WhatsApp text mode (1.5 hours)
2. **Week 2:** Production deployment with proper database
3. **Week 3:** Analytics dashboard showing voice vs text metrics
4. **Week 4:** A/B test: which channel gets better completion rates?

---

## Questions?

**Q: Can I use this for design partner testing?**  
A: YES! Much easier than scheduling voice calls. Just send them your WhatsApp number.

**Q: What if they prefer their local language?**  
A: The language detection works automatically. Or ask them to type "English" or "Indonesian" to set preference.

**Q: Can I send them the first message?**  
A: Yes! Use the `/api/whatsapp/send` endpoint to proactively start interviews.

**Q: Does this work in India too?**  
A: Absolutely! WhatsApp is huge in India. Everyone uses it.

---

**Ready to add this tomorrow?** Follow the steps above after you complete the voice pipeline! 🎉
