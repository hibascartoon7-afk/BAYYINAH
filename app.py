# -*- coding: utf-8 -*-
"""
واجهة «بيّنة» (Streamlit).

الواجهة تعرض فقط؛ لا تحكم ولا تولّد. كل نص وحكم ومصدر يأتي من المحرك كما هو:
    verify_message (message.py)  ← النتيجة والبطاقات
    explain        (llm.py)      ← الجملة التمهيدية (نموذج بحمايات، أو جملة جاهزة)
    share_reply    (reply.py)    ← رد لطيف للمجموعة
    read_image     (ocr.py)      ← قراءة نص الصورة حرفيًا

الهوية البصرية: «من الرسالة إلى مصدرها».
  - السلسلة: مسار النتيجة من رسالة المستخدم إلى الكتاب والرقم، على هيئة سلسلة الإسناد.
  - الختم: حالة النتيجة في ختم واحد واضح.
  - الحاشية: أقوال العلماء تُعرض كحواشي المخطوطات، منسوبة لقائليها.

التشغيل:  streamlit run app.py
"""
# ChromaDB يحتاج sqlite3 أحدث مما في بعض خوادم Linux (مثل Streamlit Cloud)
try:
    __import__("pysqlite3")
    import sys
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

import os
from html import escape as esc

import streamlit as st

# مفتاح النموذج: من .env محليًا، أو من Secrets على Streamlit Cloud
try:
    if "GEMINI_API_KEY" in st.secrets and not os.getenv("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

st.set_page_config(page_title="بيّنة — لا حكم بلا بيّنة", page_icon="📜", layout="centered")

# نقش النجمة الثمانية، يُرسم بالكود (لا صورة خارجية)
STAR = ("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64' "
        "viewBox='0 0 64 64'><g fill='none' stroke='%23ffffff' stroke-opacity='0.07' stroke-width='1.2'>"
        "<rect x='18' y='18' width='28' height='28'/><rect x='18' y='18' width='28' height='28' "
        "transform='rotate(45 32 32)'/><circle cx='32' cy='32' r='5'/></g></svg>")

# ─────────────────────────── التنسيق ───────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Reem+Kufi:wght@500;700&family=Amiri:wght@400;700&family=IBM+Plex+Sans+Arabic:wght@400;500;600&display=swap');

:root{{
  --ink:#1b1f4b;      /* حبر نيلي: الهوية */
  --ink-2:#2b3170;
  --paper:#f5f6fb;    /* ورق بارد */
  --sheet:#ffffff;
  --text:#1f2333;
  --mut:#666b85;
  --line:#e3e5f0;
  --found:#0f8a6f;    /* ثابت في المصادر */
  --near:#b7791f;     /* قريب لا مطابق */
  --none:#5b6478;     /* لم يُعثر عليه */
  --fatwa:#6b3fa0;    /* إحالة */
  --alert:#b3261e;    /* جزء فقط */
  --sans:'IBM Plex Sans Arabic',Tahoma,sans-serif;
  --kufi:'Reem Kufi','IBM Plex Sans Arabic',sans-serif;
  --naskh:'Amiri','Traditional Arabic',serif;
}}

/* إطار Streamlit */
#MainMenu, footer, header[data-testid="stHeader"], [data-testid="stToolbar"],
[data-testid="stDecoration"]{{display:none !important}}
.stApp{{background:var(--paper);overflow-x:hidden}}
[data-testid="stAppViewContainer"], [data-testid="stMain"]{{direction:rtl}}
.block-container, [data-testid="stMainBlockContainer"]{{padding-top:0 !important;max-width:760px}}
.stMarkdown, .stMarkdown p, .stTextArea textarea, .stButton button, .stLinkButton a, label,
[data-testid="stExpander"] summary p, [data-testid="stFileUploader"] small,
[data-testid="stFileUploaderDropzoneInstructions"] span, [data-testid="stCaptionContainer"],
[data-testid="stTabs"] button p, [data-testid="stAlert"] p{{
  font-family:var(--sans) !important;text-align:right}}

/* الرأس: شريط حبر بعرض الشاشة */
.hero{{position:relative;margin-left:calc(50% - 50vw);margin-right:calc(50% - 50vw);
  background:var(--ink) url("{STAR}");background-size:64px;
  padding:56px 20px 92px;text-align:center;color:#fff}}
.hero .word{{font-family:var(--kufi);font-size:88px;line-height:1;margin:0;font-weight:700;letter-spacing:0}}
.hero .motto{{font-family:var(--naskh);font-size:24px;color:#c9cdf2;margin:14px 0 0}}
.hero .lead{{font-family:var(--sans);font-size:16px;color:#e6e8fb;max-width:520px;margin:18px auto 0;line-height:1.9}}

/* ورقة الإدخال تعلو الشريط */
.sheet-anchor{{height:0}}
[data-testid="stTabs"]{{background:var(--sheet);border-radius:18px;padding:8px 22px 22px;
  margin-top:-62px;position:relative;box-shadow:0 18px 40px -24px rgba(27,31,75,.45);border:1px solid var(--line)}}
[data-testid="stTabs"] [role="tablist"]{{gap:6px;border-bottom:1px solid var(--line)}}
[data-testid="stTabs"] [role="tab"]{{padding:12px 10px}}
[data-testid="stTabs"] [role="tab"] p{{font-size:15px;font-weight:600}}
[data-testid="stTabs"] [aria-selected="true"] p{{color:var(--ink)}}
[data-baseweb="tab-highlight"]{{background:var(--ink) !important}}
.stTextArea textarea{{direction:rtl;font-family:var(--naskh) !important;font-size:20px;line-height:1.9;
  background:var(--paper);border-radius:12px}}
.stTextArea label p, [data-testid="stFileUploader"] label p{{font-weight:600;color:var(--text)}}

/* الأزرار */
.stButton button, .stLinkButton a{{border-radius:12px;font-weight:600;min-height:46px}}
.stButton button[kind="primary"], [data-testid="stBaseButton-primary"]{{
  background:var(--ink) !important;border-color:var(--ink) !important;color:#fff !important;font-size:16px}}
.stButton button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover{{background:var(--ink-2) !important}}
.stButton button[kind="secondary"], [data-testid="stBaseButton-secondary"]{{
  background:transparent;border:1px dashed #b9bcd8;color:var(--ink);font-size:13px;min-height:38px}}
.stButton button:focus-visible, .stLinkButton a:focus-visible{{outline:3px solid #8f95e6;outline-offset:2px}}
.try{{font-size:13px;color:var(--mut);margin:6px 0 2px}}

/* الختم والسلسلة */
.verdict{{display:flex;gap:18px;align-items:center;margin:34px 0 10px}}
.seal{{flex:0 0 auto;width:92px;height:92px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  text-align:center;font-family:var(--kufi);font-size:15px;line-height:1.3;font-weight:700;
  border:3px double currentColor;transform:rotate(-8deg);background:#fff;padding:8px;
  animation:stamp .45s cubic-bezier(.2,.9,.3,1.3) both}}
@keyframes stamp{{from{{transform:rotate(-8deg) scale(1.6);opacity:0}}to{{transform:rotate(-8deg) scale(1);opacity:1}}}}
@media (prefers-reduced-motion:reduce){{.seal{{animation:none}}}}
.verdict h2{{font-family:var(--kufi);font-size:26px;margin:0;color:var(--text);font-weight:700}}
.verdict p{{margin:6px 0 0;color:var(--mut);font-size:15px;line-height:1.8}}
.v-found{{color:var(--found)}} .v-near{{color:var(--near)}} .v-none{{color:var(--none)}}
.v-fatwa{{color:var(--fatwa)}} .v-alert{{color:var(--alert)}}

.chain{{display:flex;flex-wrap:wrap;align-items:center;gap:0;margin:14px 0 6px;font-size:14px}}
.chain span{{background:#fff;border:1px solid var(--line);border-radius:999px;padding:5px 14px;color:var(--text)}}
.chain span.end{{background:var(--ink);color:#fff;border-color:var(--ink);font-weight:600}}
.chain span.miss{{background:transparent;border-style:dashed;color:var(--none)}}
.chain i{{width:22px;height:2px;background:repeating-linear-gradient(90deg,#b9bcd8 0 4px,transparent 4px 7px);display:inline-block}}

.alert{{background:#fdeeed;border-right:4px solid var(--alert);color:#7a1b15;border-radius:10px;
  padding:12px 16px;margin:12px 0;line-height:1.9;font-size:15px}}
.intro{{font-size:15px;line-height:1.9;color:var(--text);margin:10px 0}}
.ai{{display:inline-block;font-size:12px;color:var(--near);border:1px solid #ecd3a8;background:#fff8ec;
  border-radius:999px;padding:1px 10px;margin-bottom:4px}}
.seg{{font-family:var(--naskh);font-size:18px;background:#fff;border:1px dashed #b9bcd8;border-radius:12px;
  padding:10px 14px;margin:8px 0;line-height:1.9}}
.seg small{{display:block;font-family:var(--sans);font-size:12px;color:var(--mut)}}

/* صفحة المصدر */
.page{{background:var(--sheet);border:1px solid var(--line);border-radius:4px 16px 16px 4px;
  border-right:6px solid var(--ink);padding:22px 24px 16px;margin:16px 0}}
.page.rul{{border-right-color:var(--fatwa)}}
.page .book{{font-family:var(--kufi);font-size:15px;color:var(--ink);margin:0 0 2px}}
.page.rul .book{{color:var(--fatwa)}}
.page .where{{font-size:13px;color:var(--mut);margin:0 0 14px}}
.matn{{font-family:var(--naskh);font-size:26px;line-height:2.05;color:var(--text);margin:0}}
.matn-label{{font-size:12px;color:var(--mut);margin:0 0 2px}}
.flag{{display:inline-block;font-size:12px;border-radius:999px;padding:2px 10px;margin:10px 0 0 6px;font-weight:600}}
.f-agree{{background:#e7f4ef;color:var(--found)}} .f-differ{{background:#fff3e0;color:var(--near)}}
.f-none{{background:#eef0f5;color:var(--none)}}
.warn{{background:#fff8ec;color:#7c4a03;border-radius:8px;padding:8px 12px;font-size:13px;margin:10px 0}}
.diff{{font-size:13px;color:var(--near);margin:10px 0 0;line-height:1.8}}
.note{{font-size:13px;color:var(--mut);margin:10px 0 0;line-height:1.8}}

/* الحاشية: أقوال العلماء */
.hashiya{{margin:16px 0 0;padding:4px 18px 4px 0;border-right:1px solid #cfd2e6}}
.hashiya .h-title{{font-size:12px;color:var(--mut);margin:0 0 6px}}
.qawl{{margin:0 0 14px}}
.qawl .who{{font-family:var(--kufi);font-size:14px;color:var(--fatwa)}}
.qawl .who small{{font-family:var(--sans);color:var(--mut);font-size:12px;margin-right:6px}}
.qawl blockquote{{font-family:var(--naskh);font-size:19px;line-height:1.95;margin:2px 0 0;color:var(--text);border:0;padding:0}}
details{{margin-top:12px}}
details summary{{cursor:pointer;font-size:13px;color:var(--ink);font-family:var(--sans)}}
.isnad{{font-family:var(--naskh);font-size:16px;color:var(--mut);line-height:1.9;margin-top:6px}}

/* القريب في المعنى: أخف وأصغر */
.near{{background:transparent;border:1px dashed #d9c49c;border-radius:12px;padding:12px 16px;margin:10px 0}}
.near .matn{{font-size:19px;line-height:1.9}}
.near .where{{font-size:12px;color:var(--mut);margin:6px 0 0}}

.reply-h{{font-family:var(--kufi);font-size:20px;color:var(--text);margin:34px 0 2px}}
.trust{{display:flex;flex-wrap:wrap;gap:8px 20px;font-size:13px;color:var(--mut);margin:16px 2px 0}}
.trust b{{color:var(--ink);font-weight:600}}
.foot{{color:var(--mut);font-size:12px;line-height:1.9;margin:44px 0 10px;border-top:1px solid var(--line);padding-top:14px}}

@media (max-width:640px){{
  .hero{{padding:40px 16px 84px}} .hero .word{{font-size:64px}} .hero .motto{{font-size:20px}}
  [data-testid="stTabs"]{{padding:6px 14px 16px}}
  .verdict{{gap:12px}} .seal{{width:74px;height:74px;font-size:13px}} .verdict h2{{font-size:21px}}
  .matn{{font-size:22px}} .page{{padding:16px 16px 12px}} .chain i{{width:12px}}
}}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────── المحرك ───────────────────────────
@st.cache_resource(show_spinner="نجهّز فهرس المصادر لأول مرة… قد يستغرق بضع دقائق")
def load_engine():
    from engine import build_index
    build_index()
    return True


load_engine()
from message import verify_message            # noqa: E402  (بعد بناء الفهرس)
from llm import explain                       # noqa: E402
from reply import share_reply, whatsapp_link  # noqa: E402

SEARCHED = ["صحيح البخاري", "صحيح مسلم", "كشف الخفاء", "الدرر المنتثرة", "الفوائد الموضوعة"]


# ─────────────────────────── مكوّنات العرض ───────────────────────────
def where(m: dict) -> str:
    parts = [m.get("chapter", "")]
    if m.get("number"):
        parts.append(f"رقم {m['number']}")
    if m.get("page"):
        parts.append(f"ص {m['page']}")
    return "، ".join(esc(p) for p in parts if p)


def chain_html(steps: list, end_kind: str = "end") -> str:
    """السلسلة: من رسالتك إلى مصدرها."""
    out = []
    for i, s in enumerate(steps):
        cls = end_kind if i == len(steps) - 1 else ""
        out.append(f'<span class="{cls}">{esc(s)}</span>')
    return '<div class="chain" aria-label="مسار التحقق">' + "<i></i>".join(out) + "</div>"


def verdict_html(kind: str, seal: str, title: str, body: str) -> str:
    return (f'<div class="verdict"><div class="seal v-{kind}" aria-hidden="true">{seal}</div>'
            f'<div><h2>{esc(title)}</h2><p>{esc(body)}</p></div></div>')


FLAGS = {
    "متفق": ("f-agree", "أقوال العلماء هنا متفقة"),
    "مختلف فيه": ("f-differ", "اختلف أهل العلم فيه"),
    "غير مصنّف": ("f-none", "أقوال غير مصنّفة"),
}


def page_html(m: dict) -> str:
    """صفحة مصدر كاملة لنتيجة مطابقة."""
    is_rul = m.get("layer") in ("rulings", "verified", "takhreej")
    h = f'<div class="page{" rul" if is_rul else ""}">'
    h += f'<p class="book">{esc(m.get("book", ""))}</p>'
    w = where(m)
    h += f'<p class="where">{w + "، " if w else ""}{esc(m.get("source_type", ""))}</p>'
    h += f'<p class="matn-label">{esc(m.get("display_label", "المتن"))}</p>'
    h += f'<p class="matn">{esc(m.get("matn", ""))}</p>'

    if not m.get("matn_trusted", True) and m.get("matn_note"):
        h += f'<div class="warn">تنبيه على النص: {esc(m["matn_note"])}</div>'
    if m.get("diff"):
        h += f'<p class="diff">ما يختلف بين رسالتك ولفظ الكتاب: {esc(m["diff"])}</p>'

    if m.get("agreement") in FLAGS:
        cls, txt = FLAGS[m["agreement"]]
        h += f'<span class="flag {cls}">{txt}</span>'

    rulings = m.get("rulings", [])
    if rulings:
        title = ("أقوال أهل العلم كما وردت في كتبهم، دون ترجيح من الأداة"
                 if m.get("agreement") == "مختلف فيه" else "أقوال أهل العلم كما وردت في كتبهم")
        h += f'<div class="hashiya"><p class="h-title">{title}</p>'
        for rl in rulings:
            quote = (rl.get("quote") or rl.get("ruling") or "").lstrip(". ")
            ref = esc(rl.get("book", "")) + (f"، {esc(rl['location'])}" if rl.get("location") else "")
            h += (f'<div class="qawl"><div class="who">{esc(rl.get("scholar", ""))}<small>{ref}</small></div>'
                  f'<blockquote>«{esc(quote)}»</blockquote>')
            if rl.get("quote_truncated"):
                h += '<p class="note">الكلام مقتطع، فارجع إلى المصدر لقراءته كاملًا.</p>'
            if rl.get("quote_note"):
                h += f'<p class="note">{esc(rl["quote_note"])}</p>'
            h += "</div>"
        h += "</div>"

    if m.get("isnad"):
        h += f'<details><summary>عرض السند</summary><div class="isnad">{esc(m["isnad"])}</div></details>'
    if m.get("note"):
        h += f'<p class="note">{esc(m["note"])}</p>'
    return h + "</div>"


def near_html(m: dict) -> str:
    """نتيجة قريبة في المعنى: مختصرة، ولا تُعرض كأنها جواب."""
    w = where(m)
    return (f'<div class="near"><p class="matn">{esc(m.get("matn", ""))}</p>'
            f'<p class="where">{esc(m.get("book", ""))}{"، " + w if w else ""}</p></div>')


# ─────────────────────────── الرأس ───────────────────────────
st.markdown("""
<div class="hero">
  <p class="word">بيِّنة</p>
  <p class="motto">لا حكم بلا بيّنة</p>
  <p class="lead">الصق الرسالة كما وصلتك، أو ارفع صورتها. نعيد الحديث إلى كتابه،
  وننقل كلام أهل العلم فيه بنصه، أو نخبرك بوضوح أننا لم نجده.</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────── الإدخال ───────────────────────────
EXAMPLES = {
    "رسالة واتساب": "صباح الخير 🌹 قال رسول الله ﷺ: «اطلبوا العلم ولو في الصين» انشرها تؤجر ولا تجعلها تقف عندك",
    "حديث مشهور": "إنما الأعمال بالنيات",
    "سؤال شخصي": "زوجي حلف بالطلاق فما الحكم؟",
}


def use_example(text: str):
    st.session_state["msg"] = text
    st.session_state.pop("result", None)


tab_text, tab_img = st.tabs(["نص الرسالة", "صورة الرسالة"])

with tab_text:
    st.text_area("الرسالة كما وصلتك", key="msg", height=130,
                 placeholder="قال رسول الله ﷺ: «…» انشرها تؤجر")
    run_text = st.button("تحقّق من الرسالة", type="primary", use_container_width=True)
    st.markdown('<p class="try">أو جرّب مثالًا:</p>', unsafe_allow_html=True)
    cols = st.columns(len(EXAMPLES))
    for col, (label, text) in zip(cols, EXAMPLES.items()):
        col.button(label, on_click=use_example, args=(text,), use_container_width=True)

with tab_img:
    img = st.file_uploader("لقطة شاشة من واتساب، أو بطاقة فيها الحديث", type=["png", "jpg", "jpeg", "webp"])
    st.caption("نرسل الصورة إلى خدمة Google لقراءة النص منها فقط، ولا نحفظها.")
    if img:
        st.image(img, use_container_width=True)
    run_img = st.button("اقرأ الصورة وتحقّق", type="primary", use_container_width=True, disabled=img is None)

st.markdown(
    '<div class="trust"><span>نبحث في <b>صحيحَي البخاري ومسلم</b> و<b>ثلاثة من كتب الأحاديث المشتهرة</b></span>'
    '<span>الأحكام <b>منقولة لا مولَّدة</b></span><span>أداة ذكاء اصطناعي، <b>وليست جهة إفتاء</b></span>'
    '<span><b>لا نحفظ</b> رسائلك ولا صورك</span></div>', unsafe_allow_html=True)

# ─────────────────────────── التنفيذ ───────────────────────────
if run_text:
    text = (st.session_state.get("msg") or "").strip()
    if not text:
        st.warning("الصق نص الرسالة في المربع أولًا، أو اختر مثالًا.")
    else:
        with st.spinner("نبحث في الكتب الخمسة…"):
            r = verify_message(text)
            st.session_state["result"] = (text, r, explain(text, r))

if run_img and img:
    from ocr import read_image, OCRError
    text = None
    try:
        with st.spinner("نقرأ النص من الصورة…"):
            text = read_image(img.getvalue(), img.type or "image/png")
    except OCRError as e:
        st.error(str(e))
    if text == "":
        st.warning("لم نجد نصًا عربيًا في الصورة. جرّب صورة أوضح، أو الصق النص في تبويب «نص الرسالة».")
    elif text:
        with st.spinner("نبحث في الكتب الخمسة…"):
            r = verify_message(text, input_type="image", extracted_text=text)
            st.session_state["result"] = (text, r, explain(text, r))

# ─────────────────────────── النتيجة ───────────────────────────
if "result" in st.session_state:
    text, r, ex = st.session_state["result"]
    decision = r.get("decision")
    matches, related = r.get("matches", []), r.get("related", [])[:3]
    top = matches[0] if matches else {}

    if decision == "found":
        kind, seal, title = ("alert", "جزء<br>فقط", "وجدنا جزءًا من رسالتك فقط") if r.get("partial") \
            else ("found", "ثابت في<br>المصادر", "وجدنا هذا النص في مصادرنا")
        body = "كل مصدر معروض بنصه وكلام مؤلفه كما هو في الكتاب."
        steps = ["رسالتك", top.get("book", ""), *([f"رقم {top['number']}"] if top.get("number") else [])]
        st.markdown(verdict_html(kind, seal, title, body) + chain_html([s for s in steps if s]),
                    unsafe_allow_html=True)
    elif decision == "related_only":
        st.markdown(verdict_html("near", "لم يوجد<br>بلفظه", "لم نجد هذا النص بلفظه",
                                 "ما تحته أحاديث أخرى قريبة في المعنى، وليست حكمًا على ما كتبته.")
                    + chain_html(["رسالتك", "الكتب الخمسة", "لا مطابق بلفظه"], "miss"), unsafe_allow_html=True)
    elif decision == "not_found":
        st.markdown(verdict_html("none", "لم يُعثر<br>عليه", "لم نعثر على هذا النص في مصادرنا",
                                 "وهذا لا يعني أنه مكذوب؛ فقد يكون في كتب لم نبحث فيها. "
                                 "فالأولى أن تسأل أهل العلم قبل نشره.")
                    + chain_html(["رسالتك", *SEARCHED, "لا نتيجة"], "miss"), unsafe_allow_html=True)
    elif decision == "fatwa":
        st.markdown(verdict_html("fatwa", "يُحال إلى<br>مفتٍ", "سؤالك يحتاج إلى فتوى",
                                 r.get("message", "")), unsafe_allow_html=True)
    elif decision == "out_of_scope":
        st.markdown(verdict_html("none", "خارج<br>النطاق", "هذا خارج ما تتحقق منه «بيّنة»",
                                 r.get("message", "")), unsafe_allow_html=True)

    if r.get("partial"):
        st.markdown(f'<div class="alert">{esc(r.get("message", ""))}</div>', unsafe_allow_html=True)

    if r.get("input_type") == "image":
        with st.expander("النص الذي قرأناه من الصورة"):
            st.markdown(f'<div class="seg">{esc(r.get("extracted_text", ""))}</div>', unsafe_allow_html=True)
            st.caption("إن أخطأت القراءة، انسخ النص وصحّحه في تبويب «نص الرسالة».")

    intro = (ex or {}).get("intro", "")
    if intro and decision in ("found", "related_only") and not r.get("partial"):
        label = '<span class="ai">توضيح آلي، ليس من كلام أهل العلم</span><br>' if ex.get("source") == "model" else ""
        st.markdown(f'<p class="intro">{label}{esc(intro)}</p>', unsafe_allow_html=True)

    if r.get("segment"):
        st.markdown(f'<div class="seg"><small>الجزء الذي وجدناه من رسالتك</small>{esc(r["segment"])}</div>',
                    unsafe_allow_html=True)

    for m in matches:
        st.markdown(page_html(m), unsafe_allow_html=True)

    if related and decision == "related_only":
        st.markdown("".join(near_html(m) for m in related), unsafe_allow_html=True)
    elif related and decision == "found":
        with st.expander("أحاديث أخرى قريبة في المعنى"):
            st.markdown("".join(near_html(m) for m in related), unsafe_allow_html=True)

    reply = share_reply(r, text)
    if reply:
        st.markdown('<p class="reply-h">ردّ لطيف للمجموعة</p>', unsafe_allow_html=True)
        st.caption("وصلتك الرسالة من مجموعة؟ هذا رد مكتوب من المصادر وحدها، تنسخه أو ترسله مباشرة.")
        st.code(reply, language=None)
        st.link_button("أرسل الرد على واتساب", whatsapp_link(reply), use_container_width=True)

st.markdown("""
<div class="foot">
بيِّنة: تحدي الذكاء الاصطناعي في خدمة المحتوى الإسلامي، مؤسسة باذل 2026.
المصادر والتراخيص ومنهجية العمل موثّقة في مستودع المشروع. للسؤال عن حالتك الخاصة، ارجع إلى جهة إفتاء معتمدة.
</div>
""", unsafe_allow_html=True)