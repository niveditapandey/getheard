"""
Google Cloud Speech-to-Text integration.
Supports all SEA languages + Indian languages.
"""

from google.cloud import speech_v1 as speech
from google.api_core.client_options import ClientOptions
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
            self.client = speech.SpeechClient(
                client_options=ClientOptions(quota_project_id=settings.gcp_project_id)
            )
            self.language_code = self._get_full_language_code(language_code)
            
            logger.info(f"Google Cloud STT initialized for: {self.language_code}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud STT: {e}")
            raise
    
    def _get_full_language_code(self, short_code: str) -> str:
        """Convert short code to full Google language code."""
        return self.LANGUAGE_CODES.get(short_code, 'en-US')
    
    def transcribe_audio(self, audio_content: bytes, audio_format: str = "webm") -> str:
        """
        Transcribe audio bytes to text.

        Args:
            audio_content: Audio data as bytes
            audio_format: Container format hint from the browser ("webm", "wav", "mp3", "ogg")

        Returns:
            Transcribed text
        """
        try:
            audio = speech.RecognitionAudio(content=audio_content)

            # Browser MediaRecorder produces WebM/OPUS at 48kHz.
            # Let Google auto-detect sample rate by omitting sample_rate_hertz for WEBM_OPUS.
            fmt = audio_format.lower()
            if fmt in ("webm", "ogg"):
                config = speech.RecognitionConfig(
                    encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
                    language_code=self.language_code,
                    enable_automatic_punctuation=True,
                )
            elif fmt == "mp3":
                config = speech.RecognitionConfig(
                    encoding=speech.RecognitionConfig.AudioEncoding.MP3,
                    language_code=self.language_code,
                    enable_automatic_punctuation=True,
                )
            else:  # wav / fallback
                config = speech.RecognitionConfig(
                    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                    sample_rate_hertz=16000,
                    language_code=self.language_code,
                    enable_automatic_punctuation=True,
                )
            
            try:
                response = self.client.recognize(config=config, audio=audio)
                transcripts = [r.alternatives[0].transcript for r in response.results]
            except Exception as sync_err:
                err_str = str(sync_err)
                if any(x in err_str for x in ("Sync input too long", "audio longer than 1 min",
                                               "Inline audio exceeds duration limit")):
                    logger.warning("Audio too long for sync — using streaming recognition")
                    transcripts = self._transcribe_streaming(audio_content, config)
                else:
                    raise

            full_transcript = " ".join(transcripts)
            logger.info(f"Transcribed: {full_transcript[:50]}...")
            return full_transcript

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise

    def _transcribe_streaming(self, audio_content: bytes, config) -> list:
        """Stream audio in chunks — no duration limit."""
        CHUNK = 16000  # bytes per chunk
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=False,
        )
        def _chunks():
            for i in range(0, len(audio_content), CHUNK):
                yield speech.StreamingRecognizeRequest(
                    audio_content=audio_content[i:i + CHUNK]
                )
        results = []
        try:
            for resp in self.client.streaming_recognize(streaming_config, _chunks()):
                for result in resp.results:
                    if result.is_final:
                        results.append(result.alternatives[0].transcript)
        except Exception as e:
            logger.error(f"Streaming STT error: {e}")
        return results
    
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
