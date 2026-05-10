"""
Google Cloud Text-to-Speech integration.
Supports all SEA languages + Indian languages.
"""

from google.cloud import texttospeech_v1 as texttospeech
from google.api_core.client_options import ClientOptions
import logging
from typing import Optional

from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GoogleCloudTTS:
    """Google Cloud Text-to-Speech handler."""
    
    # Voice configurations for different languages
    VOICE_CONFIGS = {
        'en': {'language_code': 'en-US', 'name': 'en-US-Neural2-F', 'gender': 'FEMALE'},
        'id': {'language_code': 'id-ID', 'name': 'id-ID-Standard-A', 'gender': 'FEMALE'},
        'fil': {'language_code': 'fil-PH', 'name': 'fil-PH-Standard-A', 'gender': 'FEMALE'},
        'th': {'language_code': 'th-TH', 'name': 'th-TH-Standard-A', 'gender': 'FEMALE'},
        'vi': {'language_code': 'vi-VN', 'name': 'vi-VN-Standard-A', 'gender': 'FEMALE'},
        'ko': {'language_code': 'ko-KR', 'name': 'ko-KR-Standard-A', 'gender': 'FEMALE'},
        'ja': {'language_code': 'ja-JP', 'name': 'ja-JP-Standard-A', 'gender': 'FEMALE'},
        'zh': {'language_code': 'cmn-CN', 'name': 'cmn-CN-Standard-A', 'gender': 'FEMALE'},
        'hi': {'language_code': 'hi-IN', 'name': 'hi-IN-Standard-A', 'gender': 'FEMALE'},
    }
    
    def __init__(self, language_code: str = 'en'):
        """
        Initialize Google Cloud TTS.
        
        Args:
            language_code: Language code (e.g., 'en', 'id', 'fil')
        """
        try:
            self.client = texttospeech.TextToSpeechClient(
                client_options=ClientOptions(quota_project_id=settings.gcp_project_id)
            )
            self.language_code = language_code
            self.voice_config = self.VOICE_CONFIGS.get(
                language_code, 
                self.VOICE_CONFIGS['en']
            )
            
            logger.info(f"Google Cloud TTS initialized for: {self.voice_config['language_code']}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud TTS: {e}")
            raise
    
    def synthesize_speech(self, text: str) -> bytes:
        """
        Convert text to speech audio.
        
        Args:
            text: Text to convert to speech
            
        Returns:
            Audio content as bytes (MP3 format)
        """
        try:
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            voice = texttospeech.VoiceSelectionParams(
                language_code=self.voice_config['language_code'],
                name=self.voice_config['name'],
            )
            
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.0,
                pitch=0.0,
            )
            
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            logger.info(f"Synthesized {len(text)} characters to audio")
            return response.audio_content
            
        except Exception as e:
            logger.error(f"Speech synthesis error: {e}")
            raise
    
    def save_to_file(self, text: str, output_path: str) -> None:
        """
        Synthesize speech and save to file.
        
        Args:
            text: Text to convert
            output_path: Path to save audio file
        """
        try:
            audio_content = self.synthesize_speech(text)
            
            with open(output_path, 'wb') as out:
                out.write(audio_content)
            
            logger.info(f"Audio saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"Save to file error: {e}")
            raise


if __name__ == "__main__":
    # Test Google Cloud TTS
    print("Testing Google Cloud TTS...")
    
    try:
        # Test different languages
        test_texts = {
            'en': 'Hello, how are you today?',
            'id': 'Halo, apa kabar?',
            'hi': 'नमस्ते, आप कैसे हैं?'
        }
        
        for lang, text in test_texts.items():
            tts = GoogleCloudTTS(language_code=lang)
            print(f"✅ {lang}: Voice {tts.voice_config['name']}")
        
        print("\n✅ Google Cloud TTS test passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
