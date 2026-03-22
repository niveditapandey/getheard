"""Quick test of configuration and Gemini setup."""

from config.settings import settings
from src.conversation.prompts import get_greeting, get_question
from src.conversation.gemini_engine import GeminiInterviewer

print("=" * 50)
print("CONFIGURATION TEST")
print("=" * 50)
print(f"GCP Project: {settings.gcp_project_id}")
print(f"Gemini Model: {settings.gemini_model}")
print(f"Voice Provider: {settings.voice_provider}")
print(f"Supported Languages: {settings.supported_languages}")
print(f"\nLanguage Routing:")
for lang in ['hi', 'en', 'id', 'fil', 'th']:
    provider = "Sarvam" if settings.should_use_sarvam(lang) else "Google Cloud"
    print(f"  {lang}: {provider}")

print("\n" + "=" * 50)
print("MULTI-LANGUAGE GREETINGS TEST")
print("=" * 50)
for lang, name in [('en', 'English'), ('id', 'Indonesian'), ('fil', 'Filipino'), ('hi', 'Hindi')]:
    print(f"\n{name} ({lang}):")
    print(get_greeting(lang)[:100] + "...")

print("\n" + "=" * 50)
print("GEMINI INTERVIEWER TEST")
print("=" * 50)

try:
    interviewer = GeminiInterviewer(language_code="en")
    greeting = interviewer.start_interview()
    print(f"✅ Interviewer started successfully!")
    print(f"Greeting: {greeting[:100]}...")
    print(f"State: {interviewer.state}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("ALL TESTS COMPLETE")
print("=" * 50)
