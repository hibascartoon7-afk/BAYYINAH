# -*- coding: utf-8 -*-
"""
ربط النموذج اللغوي بـ«بيّنة».

دور النموذج ضيّق عمدًا: يكتب جملة تمهيدية تشرح ما وجدته الأداة.
لا يكتب حكمًا ولا مصدرًا ولا رقمًا ولا نصّ حديث؛ هذه كلها تُعرض من البيانات مباشرة.

ثلاث حمايات:
  1) التعليمات الثابتة (system_prompt.py) تمنعه من ذلك.
  2) لا يُرسَل إليه نص المستخدم ولا نص الحديث؛ يُرسَل وصف النتيجة فقط.
     (يحمي الخصوصية، ويمنع أن يُدسّ له أمر داخل السؤال.)
  3) فحص بعد الجواب — بعد توحيد النص حتى لا يفلت شيء بالتشكيل:
     إن ذكر حكمًا أو مصدرًا أو رقمًا، أو اقتبس، أو نقل أربع كلمات متتالية
     من الحديث أو من كلام المستخدم، يُرفض جوابه وتُستعمل جملة جاهزة.

ولا تتعطل الأداة إن غاب المفتاح أو فشل الاتصال: تُستعمل الجملة الجاهزة.

التشغيل للتجربة:  python llm.py
"""
import os
import re

from normalize import normalize
from system_prompt import SYSTEM_PROMPT

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# النماذج تُجرَّب بالترتيب: إن ازدحم الأول أو تعذّر، يُجرَّب التالي.
# الأسماء مأخوذة من قائمة النماذج المتاحة للمفتاح. غيّريها هنا فقط إن تغيّرت.
GEMINI_MODELS = [
    "gemini-3.8-flash",          # الأساسي
    "gemini-3.5-flash-lite",     # أخفّ، وعادةً أقل ازدحامًا
    "gemini-flash-lite-latest",  # اسم ثابت يشير دائمًا إلى أحدث نسخة خفيفة
]


# ─────────────────────────────────────────────────────────────
# المقبس: الدالة الوحيدة التي تعرف أي نموذج نستعمل.
# ─────────────────────────────────────────────────────────────
def ask_model(prompt: str, system: str = SYSTEM_PROMPT) -> str:
    """ترسل السؤال للنموذج وتعيد جوابه نصًا.
    تجرّب النماذج بالترتيب، وترفع آخر خطأ إن فشلت كلها."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("لا يوجد GEMINI_API_KEY في ملف .env")

    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=key,
        http_options=types.HttpOptions(timeout=10000),   # 8 ثوانٍ لكل محاولة، ثم ننتقل للتالي
    )
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.2,          # منخفضة: نريد صياغة ثابتة لا إبداعًا
        max_output_tokens=1024,   # يتسع لتفكير النموذج؛ وطول الجواب يضبطه _is_safe (400 حرف)
    )
    last_error = None
    for model in GEMINI_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt, config=config)
            text = (resp.text or "").strip()
            if text:
                return text
        except Exception as e:          # ازدحام أو نموذج غير متاح: ننتقل إلى التالي
            last_error = e
    raise RuntimeError(f"تعذّرت كل النماذج. آخر خطأ: {last_error}")


# ─────────────────────────────────────────────────────────────
# الفحص بعد الجواب: الخط الأحمر
# الكلمات مكتوبة بصيغتها بعد normalize (ة→ه، ى→ي، أ→ا، بلا تشكيل).
# يُقبل قبلها حرفان ملتصقان (و ف ب ل ك) و«ال»، فلا تفلت «وضعيف» ولا «الصحيحين» ولا «للبخاري».
# وتشمل صيغ الفعل: صححه، ضعّفه، حسّنه.
# ─────────────────────────────────────────────────────────────
_BANNED_WORDS = (
    r"صحيح\w*|صحاح|صحح\w*|ضعيف\w*|ضعف\w*|موضوع\w*|مكذوب|كذب|باطل|منكر|شاذ|مرسل|موقوف|مرفوع|"
    r"متواتر|متروك|واه|حسن|حسنه|ثابت|يثبت|ثبت|يصح|اسناد\w*|سند\w*|رواه|روي|روايه|اخرجه|خرجه|"
    r"متفق|الشيخان|الشيخين|البخاري|مسلم|الترمذي|النسائي|داود|ماجه|احمد|الالباني|السيوطي|"
    r"العجلوني|الكرمي|تيميه|الخفاء|الدرر|الفوائد|النبي|رسول|قال|يقول"
)
_BANNED = re.compile(r"\b[وفبلك]{0,2}(?:ال)?(?:" + _BANNED_WORDS + r")\b|لا اصل|صلي الله عليه وسلم")
_QUOTES = re.compile(r'[«»"“”]|ﷺ')
_DIGITS = re.compile(r"[0-9٠-٩]")


def _ngrams(text: str, n: int = 4) -> set:
    w = normalize(text).split()
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def _is_safe(text: str, *sources: str) -> bool:
    """يُقبل الجواب فقط إن خلا من الأحكام والمصادر والأرقام والاقتباس،
    ولم ينقل أربع كلمات متتالية من نص الحديث أو من كلام المستخدم."""
    if not text or len(text) > 400:
        return False
    if _QUOTES.search(text) or _DIGITS.search(text):
        return False
    t = normalize(text)
    t = re.sub(r"\b([وفبك]?)لل", r"\1لال", t)   # «للبخاري» ← «لالبخاري» حتى تُكشف
    if _BANNED.search(t):
        return False
    grams = _ngrams(text)
    return not any(grams & _ngrams(s) for s in sources if s)


# ─────────────────────────────────────────────────────────────
# الجمل الجاهزة: تُستعمل إن غاب النموذج أو رُفض جوابه
# ─────────────────────────────────────────────────────────────
def _template(result: dict) -> str:
    d = result.get("decision")
    if d == "found":
        n = len(result.get("matches", []))
        what = "المصدر كما ورد" if n == 1 else "المصادر كما وردت"
        return f"وجدنا ما كتبتَه في مصادرنا. نعرض لك {what}، مع أقوال العلماء منقولة من كتبهم."
    if d == "related_only":
        return ("لم نجد هذا النص بلفظه في مصادرنا. وهذه أحاديث قريبة منه في المعنى، "
                "وهي أحاديث أخرى وليست حكمًا على ما كتبتَه.")
    if d == "fatwa":
        return result.get("message", "")
    return "لم نجد هذا النص في مصادرنا المعتمدة. يُرجى مراجعة مختص."


def _fatwa_note(result: dict) -> str:
    """إن وُجد الحديث وكان السؤال شخصيًا، أضاف المحرك الإحالة إلى message؛ لا نُضيّعها."""
    msg = result.get("message", "")
    i = msg.find("يبدو أن سؤالك")
    return msg[i:] if i != -1 else ""


def explain(user_text: str, result: dict) -> dict:
    """
    تُرجع {"intro": الجملة التمهيدية, "source": "model" أو "template"}.
    الواجهة تعرض intro فوق البطاقات، والبطاقات كما هي من المحرك.
    إن كان source == "model" تكتب الواجهة بجانبه: «توضيح آلي — ليس من كلام أهل العلم».
    """
    if result.get("decision") in ("fatwa", "not_found", "related_only"):
        return {"intro": _template(result), "source": "template"}

    cards = result.get("matches") or result.get("related") or []
    found = result.get("decision") == "found"
    n_diff = len([x for x in (cards[0].get("diff", "") if cards else "").split("،") if x.strip()])
    prompt = (
        f"حالة البحث: {'وُجد النص بلفظه' if found else 'لم يوجد النص بلفظه، ووُجدت أحاديث أخرى قريبة في المعنى'}.\n"
        f"عدد المصادر المعروضة: {'واحد' if len(cards) == 1 else 'أكثر من واحد'}.\n"
        f"اختلاف ألفاظ المستخدم عن المصدر: {'يوجد اختلاف يسير' if n_diff else 'لا يوجد'}.\n"
        "اكتب جملة أو جملتين تشرح للمستخدم هذه النتيجة، دون أي حكم أو مصدر أو رقم أو اقتباس."
    )

    intro, source = _template(result), "template"
    try:
        text = ask_model(prompt)
        if _is_safe(text, user_text, *(c.get("matn", "") for c in cards)):
            intro, source = text, "model"
    except Exception as e:
        print(f"  (تعذّر الاتصال بالنموذج، استُعملت الجملة الجاهزة: {e})")

    note = _fatwa_note(result)
    if note:
        intro = f"{intro} {note}"
    return {"intro": intro, "source": source}


if __name__ == "__main__":
    from engine import verify
    for q in ["المؤمن للمؤمن كالبنيان", "خير الناس انفعهم للناس", "كيف اطبخ المقلوبة"]:
        r = verify(q)
        e = explain(q, r)
        print("\n" + "=" * 60)
        print("المدخل:", q)
        print(f"[{e['source']}]", e["intro"])