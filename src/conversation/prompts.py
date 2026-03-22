"""
Multi-language system prompts for market research interviewer.
Supports SEA languages + Indian languages.
"""

INTERVIEWER_SYSTEM_PROMPT = """You are Alex, a warm and empathetic market research interviewer conducting studies on healthcare experiences across Southeast Asia and India. You speak with participants in their native language.

Your role:
1. Create a comfortable, conversational atmosphere
2. Ask clear, open-ended questions about healthcare experiences
3. Listen actively and ask thoughtful follow-up questions
4. Be genuinely curious without being intrusive
5. Show empathy, especially for difficult experiences
6. Keep conversations natural, not scripted
7. Guide through 3 main topics about their healthcare visit

Interview structure:
- Warm greeting and brief explanation
- Question 1: Tell me about your most recent healthcare visit
- Question 2: What went well during your experience?
- Question 3: What could have been improved?
- 1-2 natural follow-ups per main question
- Sincere thank you at the end

CRITICAL LANGUAGE RULE:
- ALWAYS respond in the SAME language the participant uses
- If they speak Indonesian, respond in Indonesian
- If they speak Filipino/Tagalog, respond in Filipino
- If they speak Thai, respond in Thai
- If they speak Vietnamese, respond in Vietnamese
- If they speak Hindi, respond in Hindi
- If they speak English, respond in English
- Mirror any code-switching they do naturally

Supported languages: English, Indonesian (Bahasa Indonesia), Filipino (Tagalog), Thai, Vietnamese, Korean, Japanese, Mandarin Chinese, Hindi, and other Indian languages.

Tone: Friendly, professional, culturally sensitive, patient, non-judgmental.

Keep interviews 5-10 minutes. You're collecting qualitative insights, not medical assessments.
"""

GREETING_TEMPLATE_EN = """Hello! Thank you so much for taking the time to speak with me today. My name is Alex, and I'm conducting research to better understand patient experiences in healthcare facilities. This will help healthcare providers improve their services.

Your feedback is completely confidential, and there are no right or wrong answers. The conversation will take about 5-10 minutes. Please feel free to answer in whichever language is most comfortable for you.

Shall we begin?"""

GREETING_TEMPLATE_ID = """Halo! Terima kasih banyak telah meluangkan waktu untuk berbicara dengan saya hari ini. Nama saya Alex, dan saya sedang melakukan penelitian untuk lebih memahami pengalaman pasien di fasilitas kesehatan. Ini akan membantu penyedia layanan kesehatan meningkatkan layanan mereka.

Umpan balik Anda sepenuhnya rahasia, dan tidak ada jawaban yang benar atau salah. Percakapan ini akan memakan waktu sekitar 5-10 menit. Silakan menjawab dalam bahasa apa pun yang paling nyaman untuk Anda.

Bolehkah kita mulai?"""

GREETING_TEMPLATE_FIL = """Kumusta! Maraming salamat sa paglalaan ng oras para makausap ako ngayong araw. Ako si Alex, at nagsasagawa ako ng pananaliksik upang mas maunawaan ang karanasan ng mga pasyente sa mga healthcare facility. Makakatulong ito sa mga healthcare provider na mapabuti ang kanilang mga serbisyo.

Ang inyong feedback ay ganap na kumpidensyal, at walang tama o maling sagot. Ang usapan ay tatagal ng humigit-kumulang 5-10 minuto. Mangyaring sumagot sa wikang pinaka-komportable para sa inyo.

Maaari na ba tayong magsimula?"""

GREETING_TEMPLATE_HI = """नमस्ते! आज मेरे साथ बात करने के लिए समय निकालने के लिए बहुत-बहुत धन्यवाद। मेरा नाम एलेक्स है, और मैं स्वास्थ्य सुविधाओं में रोगियों के अनुभवों को बेहतर ढंग से समझने के लिए शोध कर रहा हूं। इससे स्वास्थ्य सेवा प्रदाताओं को अपनी सेवाओं में सुधार करने में मदद मिलेगी।

आपकी प्रतिक्रिया पूरी तरह से गोपनीय है, और कोई सही या गलत उत्तर नहीं है। बातचीत में लगभग 5-10 मिनट लगेंगे। कृपया जिस भी भाषा में आप सहज हों, उसमें उत्तर दें।

क्या हम शुरू कर सकते हैं?"""

CLOSING_TEMPLATE_EN = """Thank you so much for sharing your experience with me today. Your honest feedback is incredibly valuable and will help improve healthcare services.

I really appreciate you taking the time to speak with me. Take care!"""

QUESTION_TEMPLATES = [
    {
        "number": 1,
        "main_question_en": "Can you tell me about your most recent healthcare visit? What was the reason, and what was that experience like?",
        "main_question_id": "Bisakah Anda ceritakan tentang kunjungan kesehatan Anda yang paling baru? Apa alasannya, dan bagaimana pengalaman Anda?",
        "main_question_fil": "Maaari mo bang ikuwento ang iyong pinakabagong pagbisita sa healthcare facility? Ano ang dahilan, at paano ang karanasan?",
        "main_question_hi": "क्या आप मुझे अपनी सबसे हाल की अस्पताल यात्रा के बारे में बता सकते हैं? क्या कारण था और अनुभव कैसा रहा?"
    },
    {
        "number": 2,
        "main_question_en": "What aspects of your healthcare experience went well? What was positive?",
        "main_question_id": "Aspek apa dari pengalaman kesehatan Anda yang berjalan dengan baik? Apa yang positif?",
        "main_question_fil": "Anong mga aspeto ng inyong healthcare experience ang naging mabuti? Ano ang positibo?",
        "main_question_hi": "आपके स्वास्थ्य सेवा अनुभव के कौन से पहलू अच्छे रहे? क्या सकारात्मक था?"
    },
    {
        "number": 3,
        "main_question_en": "What could have been improved? What would have made the experience better?",
        "main_question_id": "Apa yang bisa ditingkatkan? Apa yang akan membuat pengalaman lebih baik?",
        "main_question_fil": "Ano ang maaaring mapabuti? Ano ang makakagawang mas maganda ang karanasan?",
        "main_question_hi": "क्या सुधार किया जा सकता था? अनुभव को बेहतर बनाने के लिए क्या किया जा सकता था?"
    }
]

def get_greeting(language_code: str = "en") -> str:
    """Get greeting in specified language."""
    greetings = {
        "en": GREETING_TEMPLATE_EN,
        "id": GREETING_TEMPLATE_ID,
        "fil": GREETING_TEMPLATE_FIL,
        "hi": GREETING_TEMPLATE_HI
    }
    return greetings.get(language_code, GREETING_TEMPLATE_EN)

def get_question(number: int, language_code: str = "en") -> str:
    """Get question in specified language."""
    if number < 1 or number > 3:
        return ""
    
    q = QUESTION_TEMPLATES[number - 1]
    key = f"main_question_{language_code}"
    
    if key in q:
        return q[key]
    return q.get("main_question_en", "")
