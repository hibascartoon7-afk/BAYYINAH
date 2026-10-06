# -*- coding: utf-8 -*-
"""
يشغّل أمثلة الفيديو الأربعة على «بيّنة»، ويحفظ نتائجها كما هي في video_data.json،
حتى تُرسم بطاقات الفيديو من مخرجات الأداة الحقيقية حرفيًا.

لا يغيّر أي ملف في المشروع. التشغيل (من مجلد المشروع):
    python video_data.py
"""
import json

from message import verify_message

EXAMPLES = [
    "صباح الخير 🌹 قال رسول الله ﷺ: «اطلبوا العلم ولو في الصين» انشرها تؤجر ولا تجعلها تقف عندك",
    "صباح الخير 🌹 من قال «سبحان الله وبحمده» وأرسلها لعشرة أشخاص فتح الله له أبواب الرزق",
    "عن أبي هريرة رضي الله عنه قال: قال رسول الله ﷺ: «من غشنا فليس منا»",
    "هل يجوز لي أن أصلي وأنا مسافر؟",
]


def card(c: dict) -> dict:
    return {
        "source_type": c.get("source_type", ""),
        "display_label": c.get("display_label", ""),
        "book": c.get("book", ""),
        "number": c.get("number", ""),
        "matn": c.get("matn", ""),
        "diff": c.get("diff", ""),
        "rulings": [{"scholar": r.get("scholar", ""), "book": r.get("book", ""),
                     "quote": r.get("quote") or r.get("ruling", "")} for r in c.get("rulings", [])[:2]],
    }


out = []
for text in EXAMPLES:
    r = verify_message(text)
    out.append({
        "input": text,
        "decision": r.get("decision"),
        "partial": r.get("partial", False),
        "segment": r.get("segment", ""),
        "message": r.get("message", ""),
        "matches": [card(c) for c in r.get("matches", [])[:3]],
    })
    print(f"✓ {r.get('decision')} | {text[:40]}")

with open("video_data.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("\nتمّ: أرسلي ملف video_data.json")
