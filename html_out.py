# -*- coding: utf-8 -*-
"""
معاينة نتائج «بيّنة» في صفحة HTML بعربية سليمة.
تُستعمل للتجربة ولأخذ لقطات للعرض، وليست الواجهة النهائية.

التشغيل:  python html_out.py
ثم افتحي result.html
"""
from engine import verify

QUERIES = [
    "المؤمن للمؤمن كالبنيان",
    "حب الوطن من الايمان",
    "كيف اطبخ المقلوبة",
]

CSS = """
:root{--dark:#12352f;--gold:#c8a24a;--ink:#1e2a27;--mut:#6b7280;--line:#e5e7eb}
*{box-sizing:border-box}
body{font-family:'Segoe UI',Tahoma,sans-serif;background:#f6f7f5;color:var(--ink);
     margin:0;padding:32px 20px;direction:rtl}
.wrap{max-width:880px;margin:auto}
h1{color:var(--dark);margin:0 0 4px}
.sub{color:var(--mut);margin:0 0 28px;font-size:14px}
.q{background:var(--dark);color:#fff;padding:14px 18px;border-radius:12px 12px 0 0;
   margin-top:28px;font-weight:600}
.msg{background:#fdf6e3;border-right:4px solid var(--gold);padding:12px 16px;
     font-size:14px;line-height:1.7}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;
      padding:18px 20px;margin:12px 0}
.tag{display:inline-block;background:#eef2f1;color:var(--dark);border-radius:20px;
     padding:3px 12px;font-size:12px;font-weight:600;margin-bottom:10px}
.tag.rul{background:#f3eaf8;color:#5b2a86}
.label{font-size:12px;color:var(--mut);margin-bottom:4px}
.matn{font-size:20px;line-height:1.9;font-weight:600;margin:0 0 10px}
.src{font-size:13px;color:var(--mut);border-top:1px solid var(--line);
     padding-top:10px;margin-top:10px}
.warn{background:#fff4e5;color:#8a5a12;padding:8px 12px;border-radius:8px;
      font-size:13px;margin:8px 0}
.ruling{background:#faf9f7;border-right:3px solid var(--gold);padding:10px 14px;
        border-radius:6px;margin:8px 0;font-size:14px;line-height:1.8}
.scholar{font-weight:700;color:var(--dark)}
.note{font-size:13px;color:var(--mut);margin-top:8px}
.diff{font-size:13px;color:#8a5a12;margin-top:6px}
details{margin-top:8px}
summary{cursor:pointer;font-size:13px;color:var(--mut)}
.isnad{font-size:13px;color:var(--mut);line-height:1.8;margin-top:6px}
"""


def esc(t):
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def card_html(m, related=False):
    cls = "tag rul" if "أحكام" in m["source_type"] else "tag"
    h = f'<div class="card"><span class="{cls}">{esc(m["source_type"])}'
    h += ' — قريب في المعنى</span>' if related else '</span>'
    h += f'<div class="label">{esc(m["display_label"])}</div>'
    h += f'<p class="matn">{esc(m["matn"])}</p>'

    if not m.get("matn_trusted", True) and m.get("matn_note"):
        h += f'<div class="warn">⚠️ {esc(m["matn_note"])}</div>'

    if m.get("isnad"):
        h += ('<details><summary>عرض السند</summary>'
              f'<div class="isnad">{esc(m["isnad"])}</div></details>')

    if m.get("diff"):
        h += f'<div class="diff">فروق اللفظ: {esc(m["diff"])}</div>'

    if m.get("agreement") == "مختلف فيه":
        h += ('<div class="note">اختلف العلماء في الحكم عليه، '
              'وهذه أبرز الأقوال الواردة في المصادر:</div>')

    for rl in m.get("rulings", []):
        quote = (rl.get("quote") or rl.get("ruling") or "").lstrip(". ")
        h += '<div class="ruling">'
        h += f'<span class="scholar">قال {esc(rl.get("scholar",""))}</span>'
        h += f' في {esc(rl.get("book",""))}'
        if rl.get("location"):
            h += f' ({esc(rl["location"])})'
        h += f': «{esc(quote)}»'
        if rl.get("quote_truncated"):
            h += '<div class="note">(النص مقتطع — انظر المصدر)</div>'
        if rl.get("quote_note"):
            h += f'<div class="note">({esc(rl["quote_note"])})</div>'
        h += '</div>'

    loc = " — ".join(x for x in [m.get("book", ""), m.get("chapter", "")] if x)
    if m.get("number"):
        loc += f" — رقم {m['number']}"
    if m.get("page"):
        loc += f" — ص {m['page']}"
    h += f'<div class="src">المصدر: {esc(loc)}</div>'

    if m.get("note"):
        h += f'<div class="note">{esc(m["note"])}</div>'
    return h + "</div>"


def main():
    parts = [f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">'
             f'<title>بيّنة — معاينة النتائج</title><style>{CSS}</style></head><body>'
             '<div class="wrap"><h1>بيِّنة</h1>'
             '<p class="sub">معاينة نتائج المحرك — أداة مدعومة بالذكاء الاصطناعي، '
             'وليست جهة إفتاء</p>']

    for q in QUERIES:
        r = verify(q)
        parts.append(f'<div class="q">المدخل: {esc(q)}</div>')
        if r.get("message"):
            parts.append(f'<div class="msg">{esc(r["message"])}</div>')
        for m in r["matches"]:
            parts.append(card_html(m))
        for m in r["related"][:2]:
            parts.append(card_html(m, related=True))

    parts.append("</div></body></html>")
    with open("result.html", "w", encoding="utf-8") as f:
        f.write("".join(parts))
    print("تم إنشاء result.html — افتحيه بالأمر:  start result.html")


if __name__ == "__main__":
    main()