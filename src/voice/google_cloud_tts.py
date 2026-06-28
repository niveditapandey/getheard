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

    # Baseline voice configs (BCP-47 locale + a guaranteed-available Standard voice).
    # The actual voice used is upgraded at init to the best tier available for the
    # language (Chirp3-HD → Neural2 → Wavenet → Standard), falling back to these.
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

    # Voice quality tiers, best → safest. Higher index = more natural sounding.
    _TIER_PRIORITY = ["Chirp3-HD", "Chirp-HD", "Studio", "Neural2", "Wavenet", "Standard"]

    # Cache of {locale: chosen_voice_name} so we only query the voice list once per locale.
    _voice_cache: dict = {}

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
            base = self.VOICE_CONFIGS.get(language_code, self.VOICE_CONFIGS['en'])
            self.voice_config = dict(base)  # copy so we can upgrade the name

            # Upgrade to the best available voice tier for this locale (once per locale)
            best = self._best_voice_for(base['language_code'], base['gender'])
            if best:
                self.voice_config['name'] = best
            self._is_premium = "Chirp" in self.voice_config['name'] or "Studio" in self.voice_config['name']

            logger.info(
                f"Google Cloud TTS initialized: {self.voice_config['language_code']} "
                f"→ {self.voice_config['name']}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud TTS: {e}")
            raise

    def _best_voice_for(self, locale: str, preferred_gender: str) -> Optional[str]:
        """Pick the highest-quality available voice for a locale. Cached per locale."""
        if locale in GoogleCloudTTS._voice_cache:
            return GoogleCloudTTS._voice_cache[locale]
        try:
            resp = self.client.list_voices(language_code=locale)
            gender_enum = texttospeech.SsmlVoiceGender[preferred_gender]
            # Group available voice names by tier
            def tier_of(name: str) -> int:
                for i, tier in enumerate(GoogleCloudTTS._TIER_PRIORITY):
                    if tier in name:
                        return i
                return len(GoogleCloudTTS._TIER_PRIORITY)  # unknown tier = lowest
            # Prefer matching gender, but accept any if none match
            voices = [v for v in resp.voices if locale in v.language_codes]
            preferred = [v for v in voices if v.ssml_gender == gender_enum] or voices
            if not preferred:
                return None
            best = min(preferred, key=lambda v: tier_of(v.name))
            GoogleCloudTTS._voice_cache[locale] = best.name
            logger.info(f"Selected best voice for {locale}: {best.name}")
            return best.name
        except Exception as e:
            logger.warning(f"Voice listing failed for {locale}, using baseline voice: {e}")
            GoogleCloudTTS._voice_cache[locale] = None
            return None
    
    def synthesize_speech(self, text: str) -> bytes:
        """
        Convert text to speech audio.
        
        Args:
            text: Text to convert to speech
            
        Returns:
            Audio content as bytes (MP3 format)
        """
        synthesis_input = texttospeech.SynthesisInput(text=text)

        def _synth(voice_name: str, premium: bool) -> bytes:
            voice = texttospeech.VoiceSelectionParams(
                language_code=self.voice_config['language_code'],
                name=voice_name,
            )
            # Chirp3-HD / Studio voices reject the `pitch` field — omit it for premium.
            if premium:
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3,
                )
            else:
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3,
                    speaking_rate=1.0,
                    pitch=0.0,
                )
            resp = self.client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            return resp.audio_content

        try:
            audio = _synth(self.voice_config['name'], self._is_premium)
            logger.info(f"Synthesized {len(text)} chars with {self.voice_config['name']}")
            return audio
        except Exception as e:
            # Premium voice failed — degrade to the guaranteed baseline so the
            # interview never breaks on a voice-availability issue.
            baseline = self.VOICE_CONFIGS.get(self.language_code, self.VOICE_CONFIGS['en'])['name']
            if self.voice_config['name'] != baseline:
                logger.warning(f"Voice {self.voice_config['name']} failed ({e}); falling back to {baseline}")
                try:
                    audio = _synth(baseline, premium=False)
                    # Stick with the baseline for the rest of this session
                    self.voice_config['name'] = baseline
                    self._is_premium = False
                    return audio
                except Exception as e2:
                    logger.error(f"Baseline voice {baseline} also failed: {e2}")
                    raise
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
