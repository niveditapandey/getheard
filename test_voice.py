"""Test Google Cloud voice components."""

from src.voice.google_cloud_stt import GoogleCloudSTT
from src.voice.google_cloud_tts import GoogleCloudTTS

print("=" * 50)
print("GOOGLE CLOUD VOICE TEST")
print("=" * 50)

# Test STT initialization
print("\nTesting Speech-to-Text:")
try:
    for lang, name in [('en', 'English'), ('id', 'Indonesian'), ('fil', 'Filipino'), ('hi', 'Hindi')]:
        stt = GoogleCloudSTT(language_code=lang)
        print(f"✅ {name} ({lang}): {stt.language_code}")
except Exception as e:
    print(f"❌ STT Error: {e}")
    import traceback
    traceback.print_exc()

# Test TTS initialization
print("\nTesting Text-to-Speech:")
try:
    test_texts = {
        'en': 'Hello, how are you today?',
        'id': 'Halo, apa kabar?',
        'fil': 'Kumusta ka?',
        'hi': 'नमस्ते, आप कैसे हैं?'
    }
    
    for lang, text in test_texts.items():
        tts = GoogleCloudTTS(language_code=lang)
        print(f"✅ {lang}: Voice {tts.voice_config['name']}")
        
    print("\n✅ All voice components initialized successfully!")
    
except Exception as e:
    print(f"❌ TTS Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("VOICE TEST COMPLETE")
print("=" * 50)
