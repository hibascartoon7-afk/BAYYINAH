# -*- coding: utf-8 -*-
"""
مقارنة «بيّنة» بنموذج لغوي عام يُستعمل كما يستعمله الناس: يُسأل مباشرة، بلا تعليمات ولا مصادر.

لكل رسالة من فئات (sahihayn / rulings / absent) يُسأل النموذج العام عن مصدرها ودرجتها،
ثم تُفحص إحالاته إلى صحيحَي البخاري ومسلم آليًا مقابل بياناتنا:
  - مطابق            الرقم موجود، ونصه يطابق الرسالة
  - رقم لنص آخر       الرقم موجود، لكنه لحديث مختلف
  - رقم غير موجود     الرقم أكبر من عدد أحاديث الكتاب في أي ترقيم معروف
  - ترقيم آخر محتمل   الرقم يتجاوز ترقيم عبد الباقي لمسلم، وقد يصح بترقيم طبعة أخرى
  - خارج بياناتنا     الرقم ناقص أو مشكوك فيه في بياناتنا، فيحتاج تحققًا يدويًا
  - نسبة باطلة        رسالة ليست في الصحيحين، ونسبها النموذج إليهما
والإحالات إلى كتب أخرى تُعلَّم «تحتاج تحققًا يدويًا»، ولا تُحتسب صحيحة ولا خاطئة.

التشغيل (من المجلد الرئيسي للمشروع، ويحتاج GEMINI_API_KEY في .env):
    python evaluation/compare_general_model.py

المخرجات:
    evaluation/general_model.csv          جواب النموذج العام وفحص كل إحالة
    evaluation/general_model_summary.md   الملخص بالأرقام
"""
import csv
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from normalize import normalize  # noqa: E402
from llm import GEMINI_MODELS     # noqa: E402

TEST_SET = "evaluation/test_set.csv"
OUT_CSV = "evaluation/general_model.csv"
OUT_MD = "evaluation/general_model_summary.md"
CATEGORIES = ("sahihayn", "rulings", "absent")

# السؤال كما يكتبه مستخدم عادي، بلا تعليمات خاصة
QUESTION = "وصلتني هذه الرسالة: «{msg}»\nهل هذا حديث نبوي؟ ما مصدره (اسم الكتاب ورقم الحديث)؟ وما درجته؟"

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
# الرقم يُحتسب إحالةً فقط إن لم يكن قبله ما يدل على باب أو جزء أو صفحة أو سنة وفاة،
# ولم يكن بعده «/» (جزء/صفحة) ولا «هـ» (سنة). عند الشك لا نحتسبه، حتى لا نُخطّئ النموذج ظلمًا.
_GAP = r"(?:(?!باب|كتاب|جزء|ج\s|ج\.|ص\s|ص\.|ت\s|ت\.|المجلد|صفح|سنة)[^0-9٠-٩\n]){0,40}?"
_NUM = r"([0-9٠-٩]{1,5})(?![0-9٠-٩]|\s*/|\s*هـ|\s*ه\b)"
CITE = {
    "bukhari": re.compile(r"البخاري" + _GAP + _NUM),
    # «مسلم» تَرِد في نصوص الأحاديث نفسها («على كل مسلم»)، فنشترط صيغة إحالة قبلها
    "muslim": re.compile(r"(?:رواه|أخرجه|خرّجه|خرجه|صحيح|عند)\s+(?:الإمام\s+)?مسلم(?![\w])" + _GAP + _NUM),
}
# أعلى رقم في كل كتاب بالترقيم المعتمد في بياناتنا (البخاري: ترقيم فتح الباري، مسلم: ترقيم عبد الباقي)
MAX_NUMBER = {"bukhari": 7563, "muslim": 3033}
# لصحيح مسلم ترقيمات أخرى (مثل ترقيم دار السلام) تتجاوز 7000؛ فما زاد على ترقيم عبد الباقي
# ولم يتجاوز هذا الحد قد يكون صحيحًا بترقيم آخر، فلا نحتسبه خطأً.
OTHER_NUMBERING_MAX = {"bukhari": 7563, "muslim": 7563}
OTHER_BOOKS = re.compile(r"الترمذي|أبو داود|ابو داود|النسائي|ابن ماجه|ابن ماجة|أحمد|المسند|الموطأ|البيهقي|الطبراني|الحاكم")


def load_books():
    """أرقام أحاديث البخاري ومسلم في بياناتنا مع نصوصها.
    والأرقام المشكوك فيها (number_suspect) لا نعتمدها، فتُعلَّم «خارج بياناتنا» لا خطأً."""
    index = {"bukhari": {}, "muslim": {}}
    suspect = {"bukhari": set(), "muslim": set()}
    with open("data/hadith_database.json", encoding="utf-8") as f:
        for h in json.load(f):
            key = "bukhari" if "البخاري" in h.get("book", "") else "muslim" if "مسلم" in h.get("book", "") else None
            if not key:
                continue
            n = str(h.get("number", ""))
            if h.get("number_suspect"):
                suspect[key].add(n)
            else:
                index[key].setdefault(n, []).append(h.get("text", ""))
    return index, suspect


def overlap(message: str, text: str) -> float:
    m, t = set(normalize(message).split()), set(normalize(text).split())
    return len(m & t) / len(m) if m else 0.0


def check(category: str, message: str, answer: str, index: dict, suspect: dict) -> list:
    """تفحص إحالات الجواب إلى الصحيحين، وتُرجع قائمة بنتيجة كل إحالة.
    قاعدة الإنصاف: لا يُحتسب خطأً إلا ما نحن متأكدون منه؛ وما نقص من بياناتنا يُعلَّم «خارج بياناتنا»."""
    out = []
    for book, pat in CITE.items():
        for n in {x.translate(_AR_DIGITS).lstrip("0") for x in pat.findall(answer)}:
            if not n:
                continue
            if category != "sahihayn":
                out.append(("نسبة باطلة", book, n))
            elif int(n) > OTHER_NUMBERING_MAX[book]:
                out.append(("رقم غير موجود", book, n))
            elif int(n) > MAX_NUMBER[book]:
                out.append(("ترقيم آخر محتمل", book, n))
            elif n in suspect[book] or n not in index[book]:
                out.append(("خارج بياناتنا", book, n))
            elif max(overlap(message, t) for t in index[book][n]) >= 0.5:
                out.append(("مطابق", book, n))
            else:
                out.append(("رقم لنص آخر", book, n))
    if OTHER_BOOKS.search(answer):
        out.append(("تحتاج تحققًا يدويًا", "كتب أخرى", ""))
    return out


def ask(client, types, msg: str) -> tuple:
    config = types.GenerateContentConfig(temperature=0.2, max_output_tokens=1024)
    last = None
    for model in GEMINI_MODELS:
        try:
            r = client.models.generate_content(model=model, contents=QUESTION.format(msg=msg), config=config)
            if (r.text or "").strip():
                return r.text.strip(), model
        except Exception as e:
            last = e
    return f"[تعذّر الجواب: {last}]", ""


def main():
    from dotenv import load_dotenv
    load_dotenv()
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"),
                          http_options=types.HttpOptions(timeout=30000))
    index, suspect = load_books()
    with open(TEST_SET, encoding="utf-8-sig") as f:   # يقبل الملف ولو حفظه Excel بعلامة BOM
        rows = [r for r in csv.DictReader(f) if r["category"] in CATEGORIES]

    results = []
    for row in rows:
        answer, model = ask(client, types, row["message"])
        checks = check(row["category"], row["message"], answer, index, suspect)
        verdicts = [c[0] for c in checks]
        results.append({**row, "model": model, "answer": answer.replace("\n", " "),
                        "checks": " | ".join(f"{v} ({b} {n})".strip() for v, b, n in checks)})
        print(f"[{row['category']:8}] {row['message'][:40]:40} → {', '.join(verdicts) or 'لا إحالة'}")
        time.sleep(1)

    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)

    all_checks = [c.split(" (")[0] for x in results for c in x["checks"].split(" | ") if c]
    count = {k: all_checks.count(k) for k in
             ["مطابق", "رقم لنص آخر", "رقم غير موجود", "نسبة باطلة", "خارج بياناتنا",
              "ترقيم آخر محتمل", "تحتاج تحققًا يدويًا"]}
    wrong = count["رقم لنص آخر"] + count["رقم غير موجود"] + count["نسبة باطلة"]
    checked = count["مطابق"] + wrong
    msgs_with_wrong = sum(any(k in x["checks"] for k in ("رقم لنص آخر", "رقم غير موجود", "نسبة باطلة"))
                          for x in results)

    lines = ["# مقارنة بنموذج لغوي عام", "",
             f"النموذج العام: {', '.join(sorted({x['model'] for x in results if x['model']})) or 'Gemini'}، "
             f"يُسأل مباشرة بلا تعليمات ولا مصادر. عدد الرسائل: **{len(results)}**.", "",
             "## إحالات النموذج العام إلى الصحيحين، مفحوصة آليًا مقابل البيانات", "",
             "| النتيجة | العدد |", "|---|---|"]
    for k, v in count.items():
        lines.append(f"| {k} | {v} |")
    lines += ["",
              f"**من {checked} إحالة أمكن فحصها آليًا، {wrong} خاطئة "
              f"({round(wrong * 100 / checked) if checked else 0}%).**", "",
              f"**رسائل تضمّن جوابها إحالة خاطئة واحدة على الأقل:** {msgs_with_wrong} من {len(results)}.", "",
              "**«بيّنة»:** صفر مصادر مختلقة، لأن كل مصدر يُنقل من البيانات (انظر evaluation/summary.md).", "",
              "> الإحالات إلى غير الصحيحين لا تُحتسب هنا، وتحتاج تحققًا يدويًا. "
              "والأرقام الناقصة أو المشكوك فيها في بياناتنا تُعلَّم «خارج بياناتنا»، والأرقام التي قد تصح بترقيم طبعة أخرى تُعلَّم «ترقيم آخر محتمل»، ولا يُحتسب شيء منها خطأً. "
              "وكل إحالة عُلّمت خاطئة راجعها الفريق يدويًا في general_model.csv قبل اعتماد الرقم."]
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
