# -*- coding: utf-8 -*-
"""
قياس أثر كسر التعادل في ترتيب البطاقات، قبله وبعده، في تشغيل واحد.

يشغّل رسائل الاختبار الخمسين وأربع رسائل إضافية مرتين: مرة بترتيب المحرك كما هو (قبل)،
ومرة بكسر التعادل (بعد). ثم يقارن ما يعتمد على البطاقة الأولى:
  - قرار الأداة                 ← المتوقع: لا يتغير في أي رسالة
  - التنبيه على الكلام الزائد (partial)
  - البطاقة الأولى (top_source)
  - هل في البطاقة الأولى كلمات مستبدلة («اختلاف يسير» في llm.py)
  - نص الرد للمجموعة (reply.py)

لا يغيّر أي ملف في المشروع. التشغيل (من مجلد المشروع):
    python evaluation/compare_order.py
والنتيجة في evaluation/order_comparison.md (افتحيها في VS Code).
"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import message                      # noqa: E402
from reply import share_reply       # noqa: E402

EXTRA = [
    "صباح الخير 🌹 من قال «سبحان الله وبحمده» وأرسلها لعشرة أشخاص فتح الله له أبواب الرزق",
    "سبحان الله وبحمده",
    "إنما الأعمال بالنيات",
    "المؤمن للمؤمن كالبنيان يشد بعضه بعضا",
]
OUT = "evaluation/order_comparison.md"


def top(r: dict) -> str:
    cs = r.get("matches") or []
    if not cs:
        return "—"
    c = cs[0]
    return f"{c.get('book', '')} {c.get('number', '')}".strip()


def snapshot(text: str) -> dict:
    r = message.verify_message(text)
    first = (r.get("matches") or [{}])[0]
    return {"decision": r.get("decision"), "partial": bool(r.get("partial")), "top": top(r),
            "subs": message._subs(first) if r.get("matches") else 0, "reply": share_reply(r, text)}


def main():
    with open("evaluation/test_set.csv", encoding="utf-8-sig") as f:
        msgs = [row["message"] for row in csv.DictReader(f)]
    msgs += [m for m in EXTRA if m not in msgs]

    new_order = message._order
    rows = []
    for m in msgs:
        message._order = lambda r: r          # قبل: ترتيب المحرك كما هو
        before = snapshot(m)
        message._order = new_order            # بعد: كسر التعادل
        after = snapshot(m)
        rows.append((m, before, after))
        print("✓" if before["decision"] == after["decision"] else "✗", m[:45])
    message._order = new_order

    dec = [r for r in rows if r[1]["decision"] != r[2]["decision"]]
    par = [r for r in rows if r[1]["partial"] != r[2]["partial"]]
    tops = [r for r in rows if r[1]["top"] != r[2]["top"]]
    reps = [r for r in rows if r[1]["reply"] != r[2]["reply"]]

    L = ["# أثر كسر التعادل في ترتيب البطاقات", "",
         f"عدد الرسائل: **{len(rows)}** (50 من مجموعة الاختبار و{len(rows) - 50} إضافية).", "",
         "| المقارنة | تغيّر في |", "|---|---|",
         f"| قرار الأداة (المتوقع: صفر) | **{len(dec)}** |",
         f"| التنبيه على الكلام الزائد | {len(par)} |",
         f"| البطاقة الأولى | {len(tops)} |",
         f"| نص الرد للمجموعة | {len(reps)} |", ""]
    if dec:
        L += ["## ⚠️ رسائل تغيّر قرارها", ""] + [f"- {m}: {b['decision']} ← {a['decision']}" for m, b, a in dec] + [""]
    if tops or par:
        L += ["## البطاقة الأولى قبل وبعد", "", "| الرسالة | قبل | بعد | استبدال قبل ← بعد | التنبيه قبل ← بعد |", "|---|---|---|---|---|"]
        changed = [i for i, r in enumerate(rows) if r[1]["top"] != r[2]["top"] or r[1]["partial"] != r[2]["partial"]]
        for m, b, a in (rows[i] for i in changed):
            L.append(f"| {m} | {b['top']} | {a['top']} | {b['subs']} ← {a['subs']} | {b['partial']} ← {a['partial']} |")
        L.append("")
    for m in EXTRA + [r[0] for r in reps if r[0] not in EXTRA]:
        b, a = next((x[1], x[2]) for x in rows if x[0] == m)
        L += [f"## الرد للمجموعة: «{m}»", ""]
        if b["reply"] == a["reply"]:
            L += ["لم يتغيّر:", "", "```", a["reply"] or "(لا رد)", "```", ""]
        else:
            L += ["**قبل:**", "", "```", b["reply"] or "(لا رد)", "```", "", "**بعد:**", "", "```", a["reply"] or "(لا رد)", "```", ""]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"\nقرارات تغيّرت: {len(dec)} | بطاقات أولى تغيّرت: {len(tops)} | ردود تغيّرت: {len(reps)}")
    print(f"التفاصيل في {OUT}")


if __name__ == "__main__":
    main()
