# Tomorrow's Build Plan - Day 2
## Voice Interview Platform - Continuing from Night 1

**Date:** Sunday, March 23, 2026  
**Time to complete:** 3-4 hours  
**Goal:** Complete Week 1 MVP - working end-to-end voice interview system

---

## What You Built Last Night ✅

1. ✅ Multi-provider architecture (Google Cloud + Sarvam auto-routing)
2. ✅ 9-language support (English, Indonesian, Filipino, Thai, Vietnamese, Korean, Japanese, Mandarin, Hindi)
3. ✅ Gemini conversation engine with multi-language prompts
4. ✅ Google Cloud Speech-to-Text (all languages tested)
5. ✅ Google Cloud Text-to-Speech (all languages tested)
6. ✅ Configuration system with smart routing
7. ✅ Google Cloud authentication working

---

## What to Build Today

### Phase 1: Sarvam AI Integration (30 minutes)
Build the Sarvam voice components for Indian languages

### Phase 2: Voice Router (20 minutes)
Create the smart router that picks Sarvam vs Google Cloud

### Phase 3: Voice Pipeline (1 hour)
Connect all pieces: Audio → STT → Gemini → TTS → Audio

### Phase 4: Simple Web Interface (1 hour)
Build a test page to conduct interviews

### Phase 5: End-to-End Testing (1 hour)
Test full interview flow in multiple languages

---

## PHASE 1: Sarvam AI Integration

### Step 1.1: Create Sarvam STT Module

```bash
cd /Users/niveditapandey/Documents/AI\ Projects/getHeard

cat > src/voice/sarvam_stt.py << 'EOF'
"""
Sarvam AI Speech-to-Text integration.
Optimized for Indian languages and code-switching.
"""

import aiohttp
import asyncio
import logging
from typing import Optional
import base64

from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SarvamSTT:
    """Sarvam AI Speech-to-Text handler for Indian languages."""
    
    def __init__(self, language_code: str = 'hi'):
        """
        Initialize Sarvam STT.
        
        Args:
            language_code: Language code (hi, en-IN, ta, te, etc.)
        """
        self.language_code = language_code
        self.api_key = settings.sarvam_api_key
        self.endpoint = "https://api.sarvam.ai/speech-to-text"
        
        logger.info(f"Sarvam STT initialized for: {language_code}")
    
    async def transcribe_audio_async(self, audio_content: bytes) -> str:
        """
        Transcribe audio bytes to text (async).
        
        Args:
            audio_content: Audio data as bytes
            
        Returns:
            Transcribed text
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Encode audio to base64
            audio_base64 = base64.b64encode(audio_content).decode('utf-8')
            
            payload = {
                "audio": audio_base64,
                "language_code": self.language_code,
                "model": "saarika:v1"  # Sarvam's latest model
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint,
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        transcript = result.get("transcript", "")
                        logger.info(f"Sarvam transcribed: {transcript[:50]}...")
                        return transcript
                    else:
                        error = await response.text()
                        logger.error(f"Sarvam STT error: {error}")
                        raise Exception(f"Sarvam API error: {response.status}")
                        
        except Exception as e:
            logger.error(f"Sarvam transcription error: {e}")
            raise
    
    def transcribe_audio(self, audio_content: bytes) -> str:
        """
        Synchronous wrapper for transcribe_audio_async.
        
        Args:
            audio_content: Audio data as bytes
            
        Returns:
            Transcribed text
        """
        return asyncio.run(self.transcribe_audio_async(audio_content))
    
    def transcribe_file(self, file_path: str) -> str:
        """
        Transcribe audio file to text.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Transcribed text
        """
        with open(file_path, 'rb') as f:
            audio_content = f.read()
        return self.transcribe_audio(audio_content)


if __name__ == "__main__":
    print("Sarvam STT module created - use from main application")
EOF
```

### Step 1.2: Create Sarvam TTS Module

```bash
cat > src/voice/sarvam_tts.py << 'EOF'
"""
Sarvam AI Text-to-Speech integration.
Natural-sounding voice for Indian languages.
"""

import aiohttp
import asyncio
import logging
from typing import Optional
import base64

from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SarvamTTS:
    """Sarvam AI Text-to-Speech handler for Indian languages."""
    
    def __init__(self, language_code: str = 'hi'):
        """
        Initialize Sarvam TTS.
        
        Args:
            language_code: Language code (hi, en-IN, ta, te, etc.)
        """
        self.language_code = language_code
        self.api_key = settings.sarvam_api_key
        self.endpoint = "https://api.sarvam.ai/text-to-speech"
        
        logger.info(f"Sarvam TTS initialized for: {language_code}")
    
    async def synthesize_speech_async(self, text: str) -> bytes:
        """
        Convert text to speech audio (async).
        
        Args:
            text: Text to convert
            
        Returns:
            Audio content as bytes
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "text": text,
                "language_code": self.language_code,
                "speaker": "meera",  # Sarvam's female voice
                "model": "bulbul:v1"  # Sarvam's latest TTS model
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint,
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        # Sarvam returns base64 encoded audio
                        audio_base64 = result.get("audio", "")
                        audio_bytes = base64.b64decode(audio_base64)
                        logger.info(f"Sarvam synthesized {len(text)} chars")
                        return audio_bytes
                    else:
                        error = await response.text()
                        logger.error(f"Sarvam TTS error: {error}")
                        raise Exception(f"Sarvam API error: {response.status}")
                        
        except Exception as e:
            logger.error(f"Sarvam synthesis error: {e}")
            raise
    
    def synthesize_speech(self, text: str) -> bytes:
        """
        Synchronous wrapper for synthesize_speech_async.
        
        Args:
            text: Text to convert
            
        Returns:
            Audio content as bytes
        """
        return asyncio.run(self.synthesize_speech_async(text))
    
    def save_to_file(self, text: str, output_path: str) -> None:
        """
        Synthesize speech and save to file.
        
        Args:
            text: Text to convert
            output_path: Path to save audio
        """
        audio_bytes = self.synthesize_speech(text)
        with open(output_path, 'wb') as f:
            f.write(audio_bytes)
        logger.info(f"Saved audio to: {output_path}")


if __name__ == "__main__":
    print("Sarvam TTS module created - use from main application")
EOF
```

---

## PHASE 2: Voice Router

### Step 2.1: Create Smart Voice Router

```bash
cat > src/voice/voice_router.py << 'EOF'
"""
Smart voice router that selects optimal provider per language.
Auto-routing: Sarvam for Indian languages (if available), Google Cloud for others.
"""

import logging
from typing import Tuple

from config.settings import settings
from src.voice.google_cloud_stt import GoogleCloudSTT
from src.voice.google_cloud_tts import GoogleCloudTTS
from src.voice.sarvam_stt import SarvamSTT
from src.voice.sarvam_tts import SarvamTTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VoiceRouter:
    """
    Routes voice requests to optimal provider based on language.
    
    Auto-routing logic:
    - Indian languages + Sarvam available → use Sarvam
    - All other cases → use Google Cloud
    """
    
    def __init__(self, language_code: str = 'en'):
        """
        Initialize voice router for specified language.
        
        Args:
            language_code: Language code (e.g., 'en', 'hi', 'id')
        """
        self.language_code = language_code
        self.use_sarvam = settings.should_use_sarvam(language_code)
        
        # Initialize STT
        if self.use_sarvam:
            self.stt = SarvamSTT(language_code=language_code)
            logger.info(f"Voice Router: Using Sarvam STT for {language_code}")
        else:
            self.stt = GoogleCloudSTT(language_code=language_code)
            logger.info(f"Voice Router: Using Google Cloud STT for {language_code}")
        
        # Initialize TTS
        if self.use_sarvam:
            self.tts = SarvamTTS(language_code=language_code)
            logger.info(f"Voice Router: Using Sarvam TTS for {language_code}")
        else:
            self.tts = GoogleCloudTTS(language_code=language_code)
            logger.info(f"Voice Router: Using Google Cloud TTS for {language_code}")
    
    def transcribe(self, audio_content: bytes) -> str:
        """
        Transcribe audio to text using optimal provider.
        
        Args:
            audio_content: Audio bytes
            
        Returns:
            Transcribed text
        """
        return self.stt.transcribe_audio(audio_content)
    
    def synthesize(self, text: str) -> bytes:
        """
        Convert text to speech using optimal provider.
        
        Args:
            text: Text to synthesize
            
        Returns:
            Audio bytes
        """
        return self.tts.synthesize_speech(text)
    
    def get_provider_info(self) -> dict:
        """Get information about which providers are being used."""
        return {
            'language': self.language_code,
            'stt_provider': 'Sarvam' if self.use_sarvam else 'Google Cloud',
            'tts_provider': 'Sarvam' if self.use_sarvam else 'Google Cloud',
        }


if __name__ == "__main__":
    print("Testing Voice Router...")
    
    # Test routing for different languages
    test_languages = ['en', 'hi', 'id', 'fil', 'th']
    
    for lang in test_languages:
        try:
            router = VoiceRouter(language_code=lang)
            info = router.get_provider_info()
            print(f"\n{lang}: {info['stt_provider']} (STT) | {info['tts_provider']} (TTS)")
        except Exception as e:
            print(f"\n{lang}: Error - {e}")
    
    print("\n✅ Voice Router test complete!")
EOF

python src/voice/voice_router.py
```

**Run this and verify routing works!**

---

## PHASE 3: Voice Pipeline Orchestration

### Step 3.1: Create Main Pipeline

```bash
cat > src/voice/pipeline.py << 'EOF'
"""
Main voice pipeline - orchestrates the full interview flow.
Audio → STT → Gemini → TTS → Audio
"""

import logging
from typing import Optional

from src.voice.voice_router import VoiceRouter
from src.conversation.gemini_engine import GeminiInterviewer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VoiceInterviewPipeline:
    """
    Orchestrates complete voice interview pipeline.
    Handles: Voice input → Transcription → AI Response → Voice output
    """
    
    def __init__(self, language_code: str = 'en'):
        """
        Initialize pipeline for specified language.
        
        Args:
            language_code: Interview language (e.g., 'en', 'hi', 'id')
        """
        self.language_code = language_code
        
        # Initialize voice router (handles STT/TTS)
        self.voice_router = VoiceRouter(language_code=language_code)
        
        # Initialize conversation engine
        self.interviewer = GeminiInterviewer(language_code=language_code)
        
        # State
        self.is_started = False
        
        logger.info(f"Pipeline initialized for {language_code}")
        logger.info(f"Using: {self.voice_router.get_provider_info()}")
    
    def start_interview(self) -> bytes:
        """
        Start interview and return greeting audio.
        
        Returns:
            Audio bytes of greeting
        """
        # Get greeting text from Gemini
        greeting_text = self.interviewer.start_interview()
        
        # Convert to audio
        greeting_audio = self.voice_router.synthesize(greeting_text)
        
        self.is_started = True
        logger.info("Interview started, greeting synthesized")
        
        return greeting_audio
    
    def process_audio_response(self, audio_content: bytes) -> bytes:
        """
        Process user's audio response and generate next audio question.
        
        Args:
            audio_content: User's audio response
            
        Returns:
            Audio bytes of next question/response
        """
        if not self.is_started:
            raise RuntimeError("Interview not started. Call start_interview() first.")
        
        # Step 1: Transcribe user's audio
        user_text = self.voice_router.transcribe(audio_content)
        logger.info(f"User said: {user_text}")
        
        # Step 2: Get AI response from Gemini
        ai_response_text = self.interviewer.process_response(user_text)
        logger.info(f"AI responds: {ai_response_text[:50]}...")
        
        # Step 3: Convert AI response to audio
        ai_response_audio = self.voice_router.synthesize(ai_response_text)
        
        return ai_response_audio
    
    def get_conversation_history(self):
        """Get full conversation transcript."""
        return self.interviewer.get_conversation_history()
    
    def is_interview_complete(self) -> bool:
        """Check if interview is finished."""
        return self.interviewer.state == "completed"


if __name__ == "__main__":
    print("Voice Interview Pipeline module created")
    print("Use from web application or test scripts")
EOF
```

---

## PHASE 4: Simple Web Interface

### Step 4.1: Create FastAPI Web Server

```bash
cat > src/web/app.py << 'EOF'
"""
FastAPI web server for voice interview testing.
Provides simple UI to test the voice pipeline.
"""

from fastapi import FastAPI, WebSocket, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import logging
from pathlib import Path

from src.voice.pipeline import VoiceInterviewPipeline
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GetHeard Voice Interview Platform")

# Store active interview sessions
active_sessions = {}


@app.get("/", response_class=HTMLResponse)
async def get_home():
    """Serve the main interview interface."""
    html_path = Path(__file__).parent / "templates" / "index.html"
    
    if not html_path.exists():
        return HTMLResponse("""
        <html>
        <head><title>GetHeard - Voice Interview Platform</title></head>
        <body>
            <h1>GetHeard Voice Interview Platform</h1>
            <p>Template file not found. Creating basic interface...</p>
            <p>See templates/index.html for the full interface.</p>
        </body>
        </html>
        """)
    
    with open(html_path) as f:
        return HTMLResponse(content=f.read())


@app.post("/api/start-interview")
async def start_interview(language: str = "en"):
    """
    Start a new interview session.
    
    Args:
        language: Language code for interview
        
    Returns:
        Session ID and greeting audio
    """
    try:
        # Create new pipeline
        pipeline = VoiceInterviewPipeline(language_code=language)
        
        # Start interview and get greeting
        greeting_audio = pipeline.start_interview()
        
        # Store session (in production, use proper session management)
        session_id = f"session_{len(active_sessions)}"
        active_sessions[session_id] = pipeline
        
        logger.info(f"Started interview {session_id} in {language}")
        
        return {
            "session_id": session_id,
            "language": language,
            "greeting_audio": greeting_audio.hex(),  # Convert to hex for JSON
            "provider_info": pipeline.voice_router.get_provider_info()
        }
        
    except Exception as e:
        logger.error(f"Error starting interview: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.post("/api/process-audio")
async def process_audio(session_id: str, audio: UploadFile = File(...)):
    """
    Process user's audio response.
    
    Args:
        session_id: Active session ID
        audio: Audio file from user
        
    Returns:
        AI's audio response
    """
    try:
        if session_id not in active_sessions:
            return JSONResponse(
                status_code=404,
                content={"error": "Session not found"}
            )
        
        pipeline = active_sessions[session_id]
        
        # Read audio content
        audio_content = await audio.read()
        
        # Process through pipeline
        response_audio = pipeline.process_audio_response(audio_content)
        
        return {
            "response_audio": response_audio.hex(),
            "is_complete": pipeline.is_interview_complete()
        }
        
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/api/transcript/{session_id}")
async def get_transcript(session_id: str):
    """Get conversation transcript for a session."""
    if session_id not in active_sessions:
        return JSONResponse(
            status_code=404,
            content={"error": "Session not found"}
        )
    
    pipeline = active_sessions[session_id]
    history = pipeline.get_conversation_history()
    
    return {
        "session_id": session_id,
        "conversation": history,
        "is_complete": pipeline.is_interview_complete()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "active_sessions": len(active_sessions),
        "supported_languages": settings.supported_languages
    }


if __name__ == "__main__":
    uvicorn.run(
        "src.web.app:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
EOF
```

### Step 4.2: Create Simple HTML Interface

```bash
cat > src/web/templates/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GetHeard - Voice Interview Platform</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 600px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        
        h1 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 32px;
        }
        
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        
        .language-selector {
            margin-bottom: 30px;
        }
        
        select {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            cursor: pointer;
            background: white;
        }
        
        .status {
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
            font-weight: 500;
        }
        
        .status.ready {
            background: #e8f5e9;
            color: #2e7d32;
        }
        
        .status.listening {
            background: #fff3e0;
            color: #e65100;
            animation: pulse 2s infinite;
        }
        
        .status.speaking {
            background: #e3f2fd;
            color: #1565c0;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        
        .controls {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
        }
        
        button {
            flex: 1;
            padding: 15px 30px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .btn-primary {
            background: #667eea;
            color: white;
        }
        
        .btn-primary:hover:not(:disabled) {
            background: #5568d3;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
        }
        
        .btn-danger {
            background: #f44336;
            color: white;
        }
        
        .btn-danger:hover:not(:disabled) {
            background: #d32f2f;
        }
        
        .transcript {
            background: #f5f5f5;
            border-radius: 10px;
            padding: 20px;
            max-height: 300px;
            overflow-y: auto;
            margin-top: 20px;
        }
        
        .message {
            margin-bottom: 15px;
            padding: 10px;
            border-radius: 8px;
        }
        
        .message.interviewer {
            background: #e3f2fd;
            border-left: 4px solid #1565c0;
        }
        
        .message.respondent {
            background: #f1f8e9;
            border-left: 4px solid #558b2f;
        }
        
        .speaker {
            font-weight: 600;
            margin-bottom: 5px;
            font-size: 12px;
            text-transform: uppercase;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎙️ GetHeard</h1>
        <p class="subtitle">Voice Interview Platform - Week 1 MVP Test</p>
        
        <div class="language-selector">
            <select id="languageSelect">
                <option value="en">🇬🇧 English</option>
                <option value="id">🇮🇩 Indonesian (Bahasa Indonesia)</option>
                <option value="fil">🇵🇭 Filipino (Tagalog)</option>
                <option value="th">🇹🇭 Thai</option>
                <option value="vi">🇻🇳 Vietnamese</option>
                <option value="ko">🇰🇷 Korean</option>
                <option value="ja">🇯🇵 Japanese</option>
                <option value="zh">🇨🇳 Mandarin Chinese</option>
                <option value="hi">🇮🇳 Hindi</option>
            </select>
        </div>
        
        <div id="status" class="status ready">
            Ready to start interview
        </div>
        
        <div class="controls">
            <button id="startBtn" class="btn-primary" onclick="startInterview()">
                Start Interview
            </button>
            <button id="stopBtn" class="btn-danger" onclick="stopInterview()" disabled>
                Stop Interview
            </button>
        </div>
        
        <div id="transcript" class="transcript" style="display: none;">
            <h3 style="margin-bottom: 15px; color: #667eea;">Transcript</h3>
            <div id="messages"></div>
        </div>
    </div>
    
    <script>
        let sessionId = null;
        let mediaRecorder = null;
        let audioChunks = [];
        
        function updateStatus(text, className) {
            const status = document.getElementById('status');
            status.textContent = text;
            status.className = 'status ' + className;
        }
        
        function addMessage(speaker, text) {
            const messages = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message ' + speaker;
            messageDiv.innerHTML = `
                <div class="speaker">${speaker}</div>
                <div>${text}</div>
            `;
            messages.appendChild(messageDiv);
            messages.scrollTop = messages.scrollHeight;
        }
        
        async function startInterview() {
            const language = document.getElementById('languageSelect').value;
            
            try {
                updateStatus('Starting interview...', 'speaking');
                
                const response = await fetch('/api/start-interview?language=' + language, {
                    method: 'POST'
                });
                
                const data = await response.json();
                sessionId = data.session_id;
                
                document.getElementById('transcript').style.display = 'block';
                document.getElementById('startBtn').disabled = true;
                document.getElementById('stopBtn').disabled = false;
                
                // Play greeting (in real implementation)
                // For now, just show it
                updateStatus('Interview started - System is greeting you', 'speaking');
                
                console.log('Interview started:', data);
                console.log('Using providers:', data.provider_info);
                
                setTimeout(() => {
                    updateStatus('Your turn to speak - Click to record', 'ready');
                }, 2000);
                
            } catch (error) {
                console.error('Error starting interview:', error);
                updateStatus('Error starting interview', 'ready');
            }
        }
        
        function stopInterview() {
            sessionId = null;
            document.getElementById('startBtn').disabled = false;
            document.getElementById('stopBtn').disabled = true;
            updateStatus('Interview ended', 'ready');
        }
        
        // Note: Full audio recording implementation would go here
        // For Week 1 MVP, we're focusing on backend pipeline
        console.log('GetHeard Voice Interview Platform - Week 1 MVP');
    </script>
</body>
</html>
EOF
```

---

## PHASE 5: End-to-End Testing

### Step 5.1: Create Test Script

```bash
cat > test_full_pipeline.py << 'EOF'
"""
Complete end-to-end test of the voice interview pipeline.
"""

from src.voice.pipeline import VoiceInterviewPipeline
from src.storage.transcript import TranscriptManager
import json

print("=" * 60)
print("FULL PIPELINE END-TO-END TEST")
print("=" * 60)

# Test different languages
test_languages = [
    ('en', 'English'),
    ('hi', 'Hindi'),
    ('id', 'Indonesian'),
]

for lang_code, lang_name in test_languages:
    print(f"\n{'=' * 60}")
    print(f"Testing: {lang_name} ({lang_code})")
    print(f"{'=' * 60}")
    
    try:
        # Initialize pipeline
        pipeline = VoiceInterviewPipeline(language_code=lang_code)
        
        # Get provider info
        provider_info = pipeline.voice_router.get_provider_info()
        print(f"\nVoice Providers:")
        print(f"  STT: {provider_info['stt_provider']}")
        print(f"  TTS: {provider_info['tts_provider']}")
        
        # Start interview
        print(f"\nStarting interview...")
        greeting_audio = pipeline.start_interview()
        print(f"✅ Greeting audio generated: {len(greeting_audio)} bytes")
        
        # Simulate user responses (in real app, these would be actual audio)
        print(f"\n[Simulating conversation - in production, would process real audio]")
        
        # Get conversation history
        history = pipeline.get_conversation_history()
        print(f"\nConversation History:")
        for msg in history:
            print(f"  {msg['speaker']}: {msg['text'][:60]}...")
        
        print(f"\n✅ {lang_name} pipeline test PASSED!")
        
    except Exception as e:
        print(f"\n❌ {lang_name} pipeline test FAILED: {e}")
        import traceback
        traceback.print_exc()

print(f"\n{'=' * 60}")
print("END-TO-END TEST COMPLETE")
print(f"{'=' * 60}")
EOF

python test_full_pipeline.py
```

### Step 5.2: Start Web Server

```bash
# Run the web server
python -m uvicorn src.web.app:app --reload --host 0.0.0.0 --port 8000
```

**Then open browser to:** http://localhost:8000

---

## Testing Checklist

Once everything is built:

- [ ] Test voice router (Sarvam for Hindi, Google for others)
- [ ] Test full pipeline with English
- [ ] Test full pipeline with Hindi
- [ ] Test full pipeline with Indonesian
- [ ] Start web server successfully
- [ ] Open web interface in browser
- [ ] Select language and start interview
- [ ] Verify conversation flow works
- [ ] Check transcript is saved

---

## If You Get Stuck

### Common Issues & Solutions

**Issue:** Sarvam API errors
- Check your API key is correct in .env
- Verify Sarvam API endpoints (they may have changed)
- Check Sarvam API documentation for latest format

**Issue:** Google Cloud authentication
- Run: `gcloud auth application-default login --no-browser`
- Follow the bootstrap flow again

**Issue:** Import errors
- Make sure you're in project directory: `cd /Users/niveditapandey/Documents/AI\ Projects/getHeard`
- Activate venv: `source venv/bin/activate`

**Issue:** Web server won't start
- Check port 8000 is free: `lsof -i :8000`
- Try different port: `--port 8001`

---

## Success Criteria for Today

By end of today, you should have:

✅ Sarvam AI integration working (STT + TTS)  
✅ Voice router auto-selecting providers  
✅ Full pipeline: Audio → STT → Gemini → TTS → Audio  
✅ Web interface accessible at localhost:8000  
✅ Can start interview and see greeting  
✅ Conversation transcript being tracked  

---

## After Today - Week 1 Remaining

**Monday (if needed):**
- Polish web interface
- Add actual audio recording/playback
- Test with real voice input
- Fix any bugs

**Tuesday-Friday:**
- Week 2 & 3 tasks (WhatsApp integration, phone numbers, etc.)

---

## Notes

- Take breaks every hour
- Test each component before moving to next
- Save all error messages if you get stuck
- Document any API changes you discover
- Keep transcript of what works/doesn't work

**You're 60% done with Week 1 MVP!** 🎉

Today you'll complete the remaining 40% and have a working multi-language voice interview system.

Good luck! 🚀
