"""
Google Cloud Speech-to-Text integration.
Supports all SEA languages + Indian languages.
"""

from google.cloud import speech_v1 as speech
from google.oauth2 import service_account
import logging
from typing import Optional
import io

from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GoogleCloudSTT:
    """Google Cloud Speech-to-Text handler."""
    
    # Language code mapping
    LANGUAGE_CODES = {
        'en': 'en-US',
        'id': 'id-ID',
        'fil': 'fil-PH',
        'th': 'th-TH',
        'vi': 'vi-VN',
        'ko': 'ko-KR',
        'ja': 'ja-JP',
        'zh': 'zh-CN',
        'hi': 'hi-IN',
        'ta': 'ta-IN',
        'te': 'te-IN',
        'ml': 'ml-IN',
        'kn': 'kn-IN',
        'bn': 'bn-IN',
        'mr': 'mr-IN',
        'gu': 'gu-IN',
        'pa': 'pa-IN',
    }
    
    def __init__(self, language_code: str = 'en'):
        """
        Initialize Google Cloud STT.
        
        Args:
            language_code: Language code (e.g., 'en', 'id', 'fil')
        """
        try:
            self.client = speech.SpeechClient()
            self.language_code = self._get_full_language_code(language_code)
            
            logger.info(f"Google Cloud STT initialized for: {self.language_code}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud STT: {e}")
            raise
    
    def _get_full_language_code(self, short_code: str) -> str:
        """Convert short code to full Google language code."""
        return self.LANGUAGE_CODES.get(short_code, 'en-US')
    
    def transcribe_audio(self, audio_content: bytes) -> str:
        """
        Transcribe audio bytes to text.
        
        Args:
            audio_content: Audio data as bytes (WAV format preferred)
            
        Returns:
            Transcribed text
        """
        try:
            audio = speech.RecognitionAudio(content=audio_content)
            
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=self.language_code,
                enable_automatic_punctuation=True,
            )
            
            response = self.client.recognize(config=config, audio=audio)
            
            # Combine all transcripts
            transcripts = []
            for result in response.results:
                transcripts.append(result.alternatives[0].transcript)
            
            full_transcript = " ".join(transcripts)
            
            logger.info(f"Transcribed: {full_transcript[:50]}...")
            return full_transcript
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise
    
    def transcribe_file(self, file_path: str) -> str:
        """
        Transcribe audio file to text.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Transcribed text
        """
        try:
            with open(file_path, 'rb') as audio_file:
                audio_content = audio_file.read()
            
            return self.transcribe_audio(audio_content)
            
        except Exception as e:
            logger.error(f"File transcription error: {e}")
            raise
    
    def transcribe_streaming(self, audio_stream):
        """
        Transcribe streaming audio.
        
        Args:
            audio_stream: Generator yielding audio chunks
            
        Yields:
            Transcribed text chunks
        """
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=self.language_code,
            enable_automatic_punctuation=True,
        )
        
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True
        )
        
        requests = (
            speech.StreamingRecognizeRequest(audio_content=chunk)
            for chunk in audio_stream
        )
        
        responses = self.client.streaming_recognize(
            config=streaming_config,
            requests=requests
        )
        
        for response in responses:
            for result in response.results:
                if result.is_final:
                    yield result.alternatives[0].transcript


if __name__ == "__main__":
    # Test Google Cloud STT
    print("Testing Google Cloud STT...")
    
    try:
        # Test initialization for different languages
        for lang, name in [('en', 'English'), ('id', 'Indonesian'), ('hi', 'Hindi')]:
            stt = GoogleCloudSTT(language_code=lang)
            print(f"✅ {name} ({lang}): {stt.language_code}")
        
        print("\n✅ Google Cloud STT test passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
