# -*- coding: utf-8 -*-
"""
اختبارات سريعة لمبادئ الرد للمجموعة (reply.py). تعمل بلا فهرس ولا نموذج لغوي.

التشغيل (من مجلد المشروع):
    python tests/test_queries.py
أو:
    python -m pytest tests

أما قياس دقة الأداة على 50 رسالة فهو في: python evaluation/run_eval.py
"""
import os
import sys
from itertools import permutations

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reply import share_reply  # noqa: E402

DURAR = {"layer": "rulings", "book": "الدرر المنتثرة في الأحاديث المشتهرة", "number": "87",
         "rulings": [{"scholar": "السيوطي", "book": "الدرر المنتثرة في الأحاديث المشتهرة",
                      "quote": "ابن عدي والعقيلي والبيهقي في الشعب، وابن عبد البر في فصل العلم عن أنس رضي الله عنه."}]}
FAWAID = {"layer": "rulings", "book": "الفوائد الموضوعة في الأحاديث الموضوعة", "number": "154",
          "rulings": [{"scholar": "الكرمي", "book": "الفوائد الموضوعة في الأحاديث الموضوعة",
                       "quote": "قَالَ ابْنُ تَيْمِيَةَ: لَيْسَ هَذَا وَلا هَذَا مِنْ كَلامِ النَّبِيِّ صلى الله عليه وسلم."}]}
KASHF = {"layer": "rulings", "book": "كشف الخفاء ط القدسي", "number": "397",
         "rulings": [{"scholar": "العجلوني", "book": "كشف الخفاء ط القدسي", "quote": "رواه البيهقي وغيره " * 20}]}
SAH = {"layer": "sahihayn", "book": "صحيح مسلم - ت عبد الباقي", "number": "101",
       "matn": "مَنْ غَشَّنَا فَلَيْسَ مِنَّا", "matn_trusted": True, "diff": ""}


def test_no_reply_for_fatwa_or_out_of_scope():
    assert share_reply({"decision": "fatwa"}) == ""
    assert share_reply({"decision": "out_of_scope"}) == ""


def test_sahihayn_quoted_with_clean_book_name():
    t = share_reply({"decision": "found", "matches": [SAH]}, "«من غشنا فليس منا»")
    assert "صحيح مسلم (رقم 101)" in t and "عبد الباقي" not in t


def test_scholar_quote_survives_any_card_order():
    # قول ابن تيمية الصريح يبقى في الرد مهما كان ترتيب البطاقات، ولا يُقتطع أي قول
    for order in permutations([DURAR, FAWAID, KASHF]):
        t = share_reply({"decision": "found", "matches": list(order)}, "«اطلبوا العلم ولو بالصين»")
        assert "ابْنُ تَيْمِيَةَ" in t
        assert t.index("كشف الخفاء") > t.index("ابْنُ تَيْمِيَةَ")   # الإحالة إلى الكتاب بعد القول المنقول
        assert "…" not in t


def test_rulings_reply_never_says_fabricated():
    t = share_reply({"decision": "found", "matches": [DURAR, FAWAID]}, "«اطلبوا العلم ولو بالصين»")
    assert "موضوع" not in t.replace("الفوائد الموضوعة في الأحاديث الموضوعة", "")


def test_not_found_states_its_limits():
    t = share_reply({"decision": "related_only"}, "قال رسول الله ﷺ: «…»")
    assert "لا يعني أنه غير صحيح" in t


def test_no_reply_for_plain_text():
    assert share_reply({"decision": "related_only"}, "صباح الخير يا جماعة") == ""


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print("✓", t.__name__)
    print(f"نجحت {len(tests)} اختبارات")
