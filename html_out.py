from engine import verify

q = "النظافة من الإيمان"
r = verify(q)

h = """<html dir="rtl"><meta charset="utf-8">
<body style="font-family:Tahoma;background:#12352f;color:#fff;padding:40px">
<h1 style="color:#c8a24a">بيّنة</h1>
<p>المدخل: """ + q + "</p>"

for m in r["matches"]:
    h += f"""<div style="background:#fff;color:#1e2a27;padding:24px;border-radius:12px;margin-top:16px">
    <p style="font-size:26px;font-weight:bold">{m['text']}</p>
    <p>المصدر: {m['book']} — {m['chapter']} — رقم {m['number']}</p>
    <p>فروق اللفظ: {m['diff']}</p>
    <p style="color:#8a5a12">لم يتوفر حكم في مصادرنا، راجع مختصًا</p></div>"""

h += "</body></html>"
open("result.html", "w", encoding="utf-8").write(h)
print("تم إنشاء result.html")