# -*- coding: utf-8 -*-
"""
قياس «بيّنة» على مجموعة الاختبار.

يقرأ evaluation/test_set.csv، ويشغّل الأداة على كل رسالة، ويقارن القرار بالمتوقَّع،
ويفحص أن كل مصدر معروض موجود فعلًا في البيانات، ويقيس الزمن.

الفئات المتوقَّعة:
  sahihayn  الحديث في الصحيحين           ← ينجح إن ظهرت بطاقة من الصحيحين ضمن «نفس النص»
  rulings   مشهور في كتب الأحكام فقط      ← ينجح إن ظهر من كتب الأحكام، ولم يُدَّعَ أنه في الصحيحين
  absent    ليس في مصادرنا                ← ينجح إن لم تدّعِ الأداة أنها وجدته
  fatwa     سؤال فتوى شخصية               ← ينجح إن أحالت ولم تُفتِ
  scope     سؤال عام خارج وظيفة الأداة    ← ينجح إن لم تعرض أحاديث عشوائية جوابًا عليه
  verify    طلب تحقق من حديث بصيغة سؤال   ← ينجح إن بحثت عنه الأداة ولم تعدّه سؤالًا عامًا أو قرآنًا
  partial   حديث صحيح أُلحق به كلام آخر    ← ينجح إن ظهر الحديث من الصحيحين، ونبّهت الأداة أن باقي الرسالة لم يوجد
  clean     حديث صحيح بصيغة الرسائل        ← ينجح إن ظهر الحديث من الصحيحين بلا تنبيه خاطئ (اسم الصحابي، «رواه مسلم»، خطأ إملائي)

التشغيل (من المجلد الرئيسي للمشروع):
    python evaluation/run_eval.py

المخرجات:
    evaluation/results.csv   نتيجة كل رسالة
    evaluation/summary.md    الملخص بالأرقام، جاهز للصق في docs/EVALUATION.md
"""
import csv
import json
import os
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from message import verify_message as verify  # noqa: E402  — الرسالة كما تصل، لا الحديث وحده

TEST_SET = "evaluation/test_set.csv"
OUT_CSV = "evaluation/results.csv"
OUT_MD = "evaluation/summary.md"
DATA_FILES = ["data/hadith_database.json", "data/rulings_database.json"]

LABELS = {
    "sahihayn": "في الصحيحين",
    "rulings": "مشهور في كتب الأحكام",
    "absent": "ليس في مصادرنا",
    "fatwa": "سؤال فتوى",
    "scope": "سؤال عام خارج الوظيفة",
    "verify": "طلب تحقق بصيغة سؤال",
    "partial": "حديث صحيح أُلحق به كلام آخر",
    "clean": "حديث صحيح بصيغة الرسائل، بلا تنبيه خاطئ",
}


def load_sources() -> tuple:
    """كل (كتاب، رقم) وكل كتاب موجود في البيانات، لفحص أن المصادر المعروضة حقيقية."""
    pairs, books = set(), set()
    for path in DATA_FILES:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for h in json.load(f):
                pairs.add((h.get("book", ""), str(h.get("number", ""))))
                books.add(h.get("book", ""))
    return pairs, books


def cards(r: dict) -> list:
    return (r.get("matches") or []) + (r.get("related") or [])


def judge(category: str, r: dict) -> bool:
    d = r.get("decision")
    in_matches = {c.get("layer") for c in (r.get("matches") or [])}
    if category == "sahihayn":
        return "sahihayn" in in_matches
    if category == "rulings":
        return "rulings" in in_matches and "sahihayn" not in in_matches
    if category == "absent":
        # لا تدّعي الأداة وجود الرسالة: إما لم تجدها، أو وجدت جزءًا منها ونبّهت أن الباقي غير موجود
        return d != "found" or bool(r.get("partial"))
    if category == "fatwa":
        return d == "fatwa" or "يبدو أن سؤالك" in (r.get("message") or "")
    if category == "scope":
        return d in ("not_found", "fatwa", "out_of_scope")
    if category == "verify":
        return d != "out_of_scope"
    if category == "partial":
        return "sahihayn" in in_matches and bool(r.get("partial"))
    if category == "clean":
        return "sahihayn" in in_matches and not r.get("partial")
    return False


def fake_sources(r: dict, pairs: set, books: set) -> int:
    """عدد البطاقات التي تذكر مصدرًا غير موجود في البيانات. المتوقَّع: صفر."""
    bad = 0
    for c in cards(r):
        book, num = c.get("book", ""), str(c.get("number", ""))
        ok = (book, num) in pairs if num else book in books
        bad += not ok
    return bad


def top_source(r: dict) -> str:
    cs = cards(r)
    if not cs:
        return ""
    c = cs[0]
    loc = c.get("book", "")
    if c.get("number"):
        loc += f" {c['number']}"
    return f"{c.get('source_type', '')}: {loc}"


def main():
    pairs, books = load_sources()
    with open(TEST_SET, encoding="utf-8-sig") as f:   # يقبل الملف ولو حفظه Excel بعلامة BOM
        rows = list(csv.DictReader(f))

    results, times, total_fake = [], [], 0
    for row in rows:
        t0 = time.perf_counter()
        r = verify(row["message"])
        ms = round((time.perf_counter() - t0) * 1000)
        ok = judge(row["category"], r)
        fake = fake_sources(r, pairs, books)
        total_fake += fake
        times.append(ms)
        results.append({**row, "decision": r.get("decision"), "pass": "نعم" if ok else "لا",
                        "top_source": top_source(r), "fake_sources": fake, "time_ms": ms})
        print(f"{'✓' if ok else '✗'} [{row['category']:8}] {r.get('decision'):12} {ms:>5}ms | {row['message'][:45]}")

    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)

    # ── الملخص ──
    lines = ["# نتائج قياس «بيّنة»", "",
             f"عدد الرسائل: **{len(results)}**", "",
             "| الفئة | العدد | نجح | النسبة |", "|---|---|---|---|"]
    for cat, label in LABELS.items():
        sub = [x for x in results if x["category"] == cat]
        if not sub:
            continue
        p = sum(x["pass"] == "نعم" for x in sub)
        lines.append(f"| {label} | {len(sub)} | {p} | {round(p * 100 / len(sub))}% |")
    p_all = sum(x["pass"] == "نعم" for x in results)
    lines.append(f"| **المجموع** | **{len(results)}** | **{p_all}** | **{round(p_all * 100 / len(results))}%** |")

    official = [x for x in results if x["source"] == "رسمي"]
    if official:
        po = sum(x["pass"] == "نعم" for x in official)
        lines += ["", f"**حالات الاختبار الرسمية من الحزمة العلمية:** نجح {po} من {len(official)}."]
    whole = [x for x in results if x["source"] == "رسالة كاملة"]
    if whole:
        pw = sum(x["pass"] == "نعم" for x in whole)
        lines += ["", f"**رسائل كاملة كما تصل (بالتحية وعبارات النشر):** نجح {pw} من {len(whole)}."]

    lines += ["",
              f"**مصادر معروضة غير موجودة في البيانات (مختلقة):** {total_fake}",
              "",
              f"**زمن التحقق:** الوسيط {round(statistics.median(times))} جزء من الثانية، "
              f"والأقصى {max(times)}.", ""]

    fails = [x for x in results if x["pass"] != "نعم"]
    if fails:
        lines += ["## الحالات التي لم تنجح", "", "| # | الفئة | الرسالة | قرار الأداة |", "|---|---|---|---|"]
        for x in fails:
            lines.append(f"| {x['id']} | {LABELS[x['category']]} | {x['message']} | {x['decision']} |")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("\n" + "\n".join(lines))
    print(f"\nالتفاصيل في {OUT_CSV}، والملخص في {OUT_MD}")


if __name__ == "__main__":
    main()
