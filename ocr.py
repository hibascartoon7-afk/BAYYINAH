# -*- coding: utf-8 -*-
"""
قراءة النص من صور الرسائل المنتشرة (لقطات واتساب، بطاقات مزخرفة).

دور النموذج هنا: نسخ ما في الصورة حرفيًا فقط.
لا يصحّح الحديث ولا يكمله، لأن التحريف في اللفظ هو ما نريد أن نكشفه؛
فلو «صحّح» النموذج النص لأخفى الخطأ عن المحرك.

الصورة تُرسل إلى خدمة Google لقراءة النص فقط، ولا نحفظها نحن. والواجهة تُصرّح بذلك.

الاستعمال:
    from ocr import read_image
    text = read_image(image_bytes, "image/png")
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from llm import GEMINI_MODELS

OCR_PROMPT = (
    "انسخ نص الرسالة أو البطاقة الموجود في هذه الصورة حرفيًا كما هو مكتوب.\n"
    "- انسخ نص الرسالة نفسها فقط: ما في فقاعة الرسالة، أو ما في البطاقة.\n"
    "- تجاهل كل ما هو من واجهة التطبيق: اسم المحادثة أو المجموعة، وأسماء المشاركين والمرسلين، "
    "وعبارة «تمت إعادة توجيهها»، والوقت والتاريخ، وعلامات القراءة، وشريط الهاتف، والأزرار.\n"
    "- لا تصحّح أي كلمة ولا تُكمل أي نص ناقص، حتى لو بدا خطأً، وحتى لو بدا حديثًا تعرفه بلفظ آخر.\n"
    "- لا تُضف شرحًا ولا عنوانًا ولا تعليقًا ولا علامات تنصيص من عندك.\n"
    "- احتفظ بعلامات التنصيص والرموز الموجودة في الصورة (مثل « » و﴿ ﴾ وﷺ).\n"
    "- إن كانت في الصورة عدة رسائل، انسخها كلها بالترتيب، كل رسالة في سطر.\n"
    "- إن لم يوجد في الصورة نص عربي، أعد كلمة: لا_يوجد_نص"
)
# القراءة نسخٌ لا تفكير: نبدأ بالنموذج الخفيف لأنه أسرع بكثير، ثم الأقوى إن تعذّر
OCR_MODELS = ["gemini-3.5-flash-lite", "gemini-flash-lite-latest"]
NO_TEXT = "لا_يوجد_نص"


class OCRError(Exception):
    """خطأ يُعرض للمستخدم بلغة مفهومة."""


def read_image(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """تعيد النص المقروء من الصورة، أو نصًا فارغًا إن لم يوجد فيها نص عربي."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise OCRError("قراءة الصور غير متاحة حاليًا. يمكنك نسخ نص الرسالة ولصقه بدلًا من ذلك.")

    from google import genai
    from google.genai import types

    try:
        client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=30000))
        config = types.GenerateContentConfig(temperature=0)
        image = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    except Exception:
        raise OCRError("تعذّر فتح الصورة. جرّب صورة أخرى، أو الصق نص الرسالة بدلًا منها.")

    last_error = None
    for model in OCR_MODELS + [m for m in GEMINI_MODELS if m not in OCR_MODELS]:
        try:
            resp = client.models.generate_content(
                model=model, contents=[image, OCR_PROMPT], config=config)
            text = (resp.text or "").strip()
            if not text:
                continue                      # جواب فارغ: جرّب النموذج التالي
            return "" if NO_TEXT in text else text
        except Exception as e:      # ازدحام أو نموذج غير متاح: جرّب التالي
            last_error = e
            print(f"OCR {model}: {e}")        # للفريق في الطرفية فقط، لا يظهر للمستخدم
    raise OCRError("تعذّرت قراءة الصورة الآن. جرّب لصق نص الرسالة بدلًا منها.")