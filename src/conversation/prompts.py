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

GREETING_TEMPLATE_TH = """สวัสดีค่ะ! ขอบคุณมากที่สละเวลามาพูดคุยกับฉันในวันนี้ ฉันชื่ออเล็กซ์ และกำลังทำการวิจัยเพื่อทำความเข้าใจประสบการณ์ของผู้ป่วยในสถานพยาบาลให้ดียิ่งขึ้น ซึ่งจะช่วยให้ผู้ให้บริการด้านสุขภาพปรับปรุงการบริการของตน

ข้อมูลของคุณเป็นความลับอย่างสมบูรณ์ และไม่มีคำตอบที่ถูกหรือผิด การสนทนานี้จะใช้เวลาประมาณ 5-10 นาที กรุณาตอบในภาษาที่คุณสะดวกที่สุด

พร้อมจะเริ่มต้นกันได้เลยไหมคะ?"""

GREETING_TEMPLATE_VI = """Xin chào! Cảm ơn bạn rất nhiều vì đã dành thời gian để nói chuyện với tôi hôm nay. Tôi tên là Alex, và tôi đang thực hiện nghiên cứu để hiểu rõ hơn về trải nghiệm của bệnh nhân tại các cơ sở y tế. Điều này sẽ giúp các nhà cung cấp dịch vụ y tế cải thiện dịch vụ của họ.

Phản hồi của bạn hoàn toàn bảo mật, và không có câu trả lời đúng hay sai. Cuộc trò chuyện sẽ mất khoảng 5-10 phút. Vui lòng trả lời bằng ngôn ngữ nào bạn cảm thấy thoải mái nhất.

Chúng ta có thể bắt đầu không?"""

GREETING_TEMPLATE_KO = """안녕하세요! 오늘 저와 이야기해 주셔서 정말 감사합니다. 저는 Alex이고, 의료 시설에서의 환자 경험을 더 잘 이해하기 위한 연구를 진행하고 있습니다. 이는 의료 서비스 제공자들이 서비스를 개선하는 데 도움이 될 것입니다.

귀하의 피드백은 완전히 기밀이며, 정답이나 오답은 없습니다. 대화는 약 5-10분 정도 소요될 것입니다. 가장 편안한 언어로 답변해 주세요.

시작할 준비가 되셨나요?"""

GREETING_TEMPLATE_JA = """こんにちは！今日は時間を割いて話してくださり、本当にありがとうございます。私はアレックスと申します。医療施設における患者さんの体験をより深く理解するための調査を行っています。これは医療提供者がサービスを改善するのに役立ちます。

お話しいただく内容は完全に機密扱いです。正解も不正解もありません。会話は約5〜10分ほどかかります。最も快適な言語でお答えください。

始めてもよろしいでしょうか？"""

GREETING_TEMPLATE_ZH = """您好！非常感谢您今天抽出时间与我交流。我叫Alex，我正在进行研究，以更好地了解患者在医疗机构的就医体验。这将帮助医疗服务提供者改善其服务。

您的反馈完全保密，没有正确或错误的答案。这次谈话大约需要5-10分钟。请随意用您最舒适的语言回答。

我们可以开始了吗？"""

CLOSING_TEMPLATE_EN = """Thank you so much for sharing your experience with me today. Your honest feedback is incredibly valuable and will help improve healthcare services.

I really appreciate you taking the time to speak with me. Take care!"""

CLOSING_TEMPLATES = {
    "en": CLOSING_TEMPLATE_EN,
    "id": "Terima kasih banyak telah berbagi pengalaman Anda hari ini. Umpan balik Anda sangat berharga dan akan membantu meningkatkan layanan kesehatan. Terima kasih!",
    "fil": "Maraming salamat sa pagbabahagi ng inyong karanasan ngayon. Ang inyong feedback ay napakahalaga at makakatulong sa pagpapabuti ng serbisyong pangkalusugan. Salamat!",
    "hi": "आज अपना अनुभव साझा करने के लिए बहुत-बहुत धन्यवाद। आपकी प्रतिक्रिया बेहद मूल्यवान है। धन्यवाद!",
    "th": "ขอบคุณมากที่แบ่งปันประสบการณ์ของคุณในวันนี้ ข้อมูลของคุณมีค่ามากและจะช่วยปรับปรุงบริการด้านสุขภาพ ขอบคุณค่ะ!",
    "vi": "Cảm ơn bạn rất nhiều vì đã chia sẻ trải nghiệm của mình hôm nay. Phản hồi của bạn vô cùng quý giá. Cảm ơn bạn!",
    "ko": "오늘 경험을 공유해 주셔서 정말 감사합니다. 귀하의 피드백은 매우 소중합니다. 감사합니다!",
    "ja": "今日はご自身の体験を共有していただき、本当にありがとうございました。皆様のフィードバックは大変貴重です。ありがとうございました！",
    "zh": "非常感谢您今天分享您的体验。您的反馈非常宝贵，将有助于改善医疗服务。谢谢！",
}

QUESTION_TEMPLATES = [
    {
        "number": 1,
        "en":  "Can you tell me about your most recent healthcare visit? What was the reason, and what was that experience like?",
        "id":  "Bisakah Anda ceritakan tentang kunjungan kesehatan Anda yang paling baru? Apa alasannya, dan bagaimana pengalaman Anda?",
        "fil": "Maaari mo bang ikuwento ang iyong pinakabagong pagbisita sa healthcare facility? Ano ang dahilan, at paano ang karanasan?",
        "hi":  "क्या आप मुझे अपनी सबसे हाल की अस्पताल यात्रा के बारे में बता सकते हैं? क्या कारण था और अनुभव कैसा रहा?",
        "th":  "คุณช่วยเล่าให้ฟังเกี่ยวกับการไปพบแพทย์ครั้งล่าสุดของคุณได้ไหมคะ? เหตุผลคืออะไร และประสบการณ์นั้นเป็นอย่างไรบ้าง?",
        "vi":  "Bạn có thể kể cho tôi nghe về lần khám bệnh gần đây nhất của bạn không? Lý do là gì, và trải nghiệm đó như thế nào?",
        "ko":  "가장 최근에 의료 시설을 방문했던 경험에 대해 말씀해 주시겠어요? 어떤 이유였고, 그 경험은 어땠나요?",
        "ja":  "最近の医療機関への受診について教えていただけますか？受診の理由は何でしたか、そしてその体験はいかがでしたか？",
        "zh":  "您能告诉我您最近一次就医的经历吗？是什么原因去的，那次经历感觉如何？",
    },
    {
        "number": 2,
        "en":  "What aspects of your healthcare experience went well? What was positive?",
        "id":  "Aspek apa dari pengalaman kesehatan Anda yang berjalan dengan baik? Apa yang positif?",
        "fil": "Anong mga aspeto ng inyong healthcare experience ang naging mabuti? Ano ang positibo?",
        "hi":  "आपके स्वास्थ्य सेवा अनुभव के कौन से पहलू अच्छे रहे? क्या सकारात्मक था?",
        "th":  "ด้านใดของประสบการณ์ด้านสุขภาพของคุณที่ดำเนินไปด้วยดี? อะไรที่เป็นเรื่องบวก?",
        "vi":  "Những khía cạnh nào trong trải nghiệm chăm sóc sức khỏe của bạn diễn ra tốt? Điều gì là tích cực?",
        "ko":  "의료 경험에서 잘 된 부분은 무엇이었나요? 긍정적인 점은 무엇이었나요?",
        "ja":  "医療体験の中で、うまくいったのはどのような点でしたか？良かった点は何ですか？",
        "zh":  "您的就医体验中哪些方面做得很好？有哪些积极的地方？",
    },
    {
        "number": 3,
        "en":  "What could have been improved? What would have made the experience better?",
        "id":  "Apa yang bisa ditingkatkan? Apa yang akan membuat pengalaman lebih baik?",
        "fil": "Ano ang maaaring mapabuti? Ano ang makakagawang mas maganda ang karanasan?",
        "hi":  "क्या सुधार किया जा सकता था? अनुभव को बेहतर बनाने के लिए क्या किया जा सकता था?",
        "th":  "อะไรที่ควรจะปรับปรุง? อะไรจะทำให้ประสบการณ์นั้นดีขึ้น?",
        "vi":  "Điều gì có thể được cải thiện? Điều gì sẽ làm cho trải nghiệm tốt hơn?",
        "ko":  "어떤 점이 개선될 수 있었을까요? 어떤 것이 경험을 더 좋게 만들었을까요?",
        "ja":  "改善できた点はどこですか？何があれば体験がよりよくなりましたか？",
        "zh":  "哪些方面可以改进？什么会让这次体验更好？",
    },
]


def get_greeting(language_code: str = "en") -> str:
    """Get greeting in specified language."""
    greetings = {
        "en":  GREETING_TEMPLATE_EN,
        "id":  GREETING_TEMPLATE_ID,
        "fil": GREETING_TEMPLATE_FIL,
        "hi":  GREETING_TEMPLATE_HI,
        "th":  GREETING_TEMPLATE_TH,
        "vi":  GREETING_TEMPLATE_VI,
        "ko":  GREETING_TEMPLATE_KO,
        "ja":  GREETING_TEMPLATE_JA,
        "zh":  GREETING_TEMPLATE_ZH,
    }
    return greetings.get(language_code, GREETING_TEMPLATE_EN)


def get_closing(language_code: str = "en") -> str:
    """Get closing message in specified language."""
    return CLOSING_TEMPLATES.get(language_code, CLOSING_TEMPLATE_EN)


def get_question(number: int, language_code: str = "en") -> str:
    """Get question in specified language."""
    if number < 1 or number > 3:
        return ""
    q = QUESTION_TEMPLATES[number - 1]
    return q.get(language_code) or q.get("en", "")
