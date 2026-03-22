"""Test ALL SEA + Asian languages."""

from src.voice.google_cloud_stt import GoogleCloudSTT
from src.voice.google_cloud_tts import GoogleCloudTTS

print("=" * 50)
print("TESTING ALL LANGUAGES")
print("=" * 50)

all_languages = [
    ('en', 'English'),
    ('id', 'Indonesian'),
    ('fil', 'Filipino'),
    ('th', 'Thai'),
    ('vi', 'Vietnamese'),
    ('ko', 'Korean'),
    ('ja', 'Japanese'),
    ('zh', 'Mandarin Chinese'),
    ('hi', 'Hindi'),
]

print("\nSpeech-to-Text Support:")
for lang_code, lang_name in all_languages:
    try:
        stt = GoogleCloudSTT(language_code=lang_code)
        print(f"✅ {lang_name:20} ({lang_code:3}) → {stt.language_code}")
    except Exception as e:
        print(f"❌ {lang_name:20} ({lang_code:3}) → ERROR: {e}")

print("\nText-to-Speech Support:")
for lang_code, lang_name in all_languages:
    try:
        tts = GoogleCloudTTS(language_code=lang_code)
        print(f"✅ {lang_name:20} ({lang_code:3}) → {tts.voice_config['name']}")
    except Exception as e:
        print(f"❌ {lang_name:20} ({lang_code:3}) → ERROR: {e}")

print("\n" + "=" * 50)
