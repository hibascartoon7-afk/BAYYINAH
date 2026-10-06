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
import re
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
@import url('https://fonts.googleapis.com/css2?family=Readex+Pro:wght@400;500;600;700&family=Noto+Naskh+Arabic:wght@400;500;600&family=Amiri:wght@400;700&display=swap');

:root{{
  --ink:#161d4a;      /* حبر نيلي: الهوية، كما في العرض والفيديو */
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
  --sans:'Readex Pro',Tahoma,sans-serif;
  --kufi:'Readex Pro',Tahoma,sans-serif;
  --naskh:'Noto Naskh Arabic','Amiri','Traditional Arabic',serif;
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
.lang{{position:absolute;top:16px;inset-inline-end:20px;font-family:var(--sans);font-size:14px;
  color:#fff !important;text-decoration:none;border:1px solid rgba(255,255,255,.45);border-radius:999px;padding:4px 14px}}
.lang:hover{{background:rgba(255,255,255,.12)}}
.lang:focus-visible{{outline:3px solid #8f95e6;outline-offset:2px}}
.hero .word{{font-family:var(--naskh);font-size:88px;line-height:1.2;margin:0;font-weight:600;letter-spacing:0;color:#E8C768}}
.hero .motto{{font-family:var(--naskh);font-size:24px;color:#c9cdf2;margin:14px 0 0}}
.hero p, .hero .stMarkdown p{{text-align:center !important}}
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
.v-fatwa{{color:var(--fatwa)}} .v-alert{{color:var(--alert)}} .v-rul{{color:var(--fatwa)}}

.chain{{display:flex;flex-wrap:wrap;align-items:center;gap:0;margin:14px 0 6px;font-size:14px}}
.chain span{{background:#fff;border:1px solid var(--line);border-radius:999px;padding:5px 14px;color:var(--text)}}
.chain span.end{{background:var(--ink);color:#fff;border-color:var(--ink);font-weight:600}}
.chain span.miss{{background:transparent;border-style:dashed;color:var(--none)}}
.chain i{{width:22px;height:2px;background:repeating-linear-gradient(90deg,#b9bcd8 0 4px,transparent 4px 7px);display:inline-block}}

.alert{{background:#fdeeed;border-inline-start:4px solid var(--alert);color:#7a1b15;border-radius:10px;
  padding:12px 16px;margin:12px 0;line-height:1.9;font-size:15px}}
.intro{{font-size:15px;line-height:1.9;color:var(--text);margin:10px 0}}
.ai{{display:inline-block;font-size:12px;color:var(--near);border:1px solid #ecd3a8;background:#fff8ec;
  border-radius:999px;padding:1px 10px;margin-bottom:4px}}
.seg{{font-family:var(--naskh);font-size:18px;background:#fff;border:1px dashed #b9bcd8;border-radius:12px;
  padding:10px 14px;margin:8px 0;line-height:1.9}}
.seg small{{display:block;font-family:var(--sans);font-size:12px;color:var(--mut)}}

/* صفحة المصدر */
.page{{background:var(--sheet);border:1px solid var(--line);border-radius:14px;
  border-inline-start:6px solid var(--ink);padding:22px 24px 16px;margin:16px 0}}
.page.rul{{border-inline-start-color:var(--fatwa)}}
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
.hashiya{{margin:16px 0 0;padding-block:4px;padding-inline:18px 0;border-inline-start:1px solid #cfd2e6}}
.hashiya .h-title{{font-size:12px;color:var(--mut);margin:0 0 6px}}
.qawl{{margin:0 0 14px;direction:rtl;text-align:right}}
.qawl .who{{font-family:var(--kufi);font-size:14px;color:var(--fatwa)}}
.qawl .who small{{font-family:var(--sans);color:var(--mut);font-size:12px;margin-inline-start:6px}}
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
[data-testid="stCode"] pre, [data-testid="stCode"] code{{direction:rtl;text-align:right;white-space:pre-wrap !important;
  word-break:break-word;font-family:var(--sans) !important;font-size:15px;line-height:1.9}}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────── اللغة ───────────────────────────
# الواجهة تتحول إلى الإنجليزية؛ أما الأحاديث وأقوال العلماء فتبقى بالعربية كما هي،
# لأن ترجمتها آليًا تخالف مبدأ «النص يُنقل ولا يُولَّد». والمصطلحات من قاموس الحزمة العلمية.
LANG = "en" if st.query_params.get("lang") == "en" else "ar"
EN = LANG == "en"

if EN:
    st.markdown("""
<style>
[data-testid="stAppViewContainer"], [data-testid="stMain"]{direction:ltr}
.stMarkdown, .stMarkdown p, .stButton button, .stLinkButton a, label,
[data-testid="stExpander"] summary p, [data-testid="stFileUploader"] small,
[data-testid="stCaptionContainer"], [data-testid="stTabs"] button p, [data-testid="stAlert"] p{text-align:left}
.stTextArea textarea, .stMarkdown p.matn, .isnad, .seg, .stMarkdown .seg{direction:rtl;text-align:right !important}
.hero .motto{font-family:var(--sans);font-size:20px}
.stTextArea textarea::placeholder{unicode-bidi:plaintext;text-align:start;font-family:var(--sans);font-size:15px}
</style>""", unsafe_allow_html=True)

T = {
    "ar": {
        "switch": ("English", "?lang=en"), "motto": "لا حكم بلا بيّنة",
        "lead": "الصق الرسالة كما وصلتك، أو ارفع صورتها. نعيد الحديث إلى كتابه، "
                "وننقل كلام أهل العلم فيه بنصه، أو نخبرك بوضوح أننا لم نجده.",
        "tab_text": "نص الرسالة", "tab_img": "صورة الرسالة", "box": "الرسالة كما وصلتك", "placeholder": "قال رسول الله ﷺ: «…» انشرها تؤجر",
        "check": "تحقّق من الرسالة", "try": "أو جرّب مثالًا:",
        "ex": ["رسالة واتساب", "حديث مشهور", "سؤال شخصي"],
        "upload": "لقطة شاشة من واتساب، أو بطاقة فيها الحديث",
        "upload_note": "نرسل الصورة إلى خدمة Google لقراءة النص منها فقط، ولا نحفظها.",
        "read": "اقرأ الصورة وتحقّق",
        "trust": ["نبحث في <b>صحيحَي البخاري ومسلم</b> و<b>ثلاثة من كتب الأحاديث المشتهرة</b>",
                  "الأحكام <b>منقولة لا مولَّدة</b>", "أداة ذكاء اصطناعي، <b>وليست جهة إفتاء</b>",
                  "<b>لا نحفظ</b> رسائلك ولا صورك"],
        "empty": "الصق نص الرسالة في المربع أولًا، أو اختر مثالًا.",
        "searching": "نبحث في الكتب الخمسة…", "reading": "نقرأ النص من الصورة…",
        "no_text": "لم نجد نصًا عربيًا في الصورة. جرّب صورة أوضح، أو الصق النص في تبويب «نص الرسالة».",
        "found": ("في<br>الصحيحين", "وجدنا هذا النص في الصحيحين",
                  "كل مصدر معروض بنصه وكلام مؤلفه كما هو في الكتاب."),
        "found_rul": ("في كتب<br>المشتهرات", "وجدنا هذا النص في كتب الأحاديث المشتهرة",
                      "وهي كتب تجمع ما اشتهر على الألسنة، وفيها الصحيح وغيره؛ فاقرأ كلام العلماء فيه أدناه."),
        "partial": ("جزء<br>فقط", "وجدنا جزءًا من رسالتك فقط", "كل مصدر معروض بنصه وكلام مؤلفه كما هو في الكتاب."),
        "related": ("لم يوجد<br>بلفظه", "لم نجد هذا النص بلفظه",
                    "ما تحته أحاديث أخرى قريبة في المعنى، وليست حكمًا على ما كتبته."),
        "not_found": ("لم يُعثر<br>عليه", "لم نعثر على هذا النص في مصادرنا",
                      "وهذا لا يعني أنه مكذوب؛ فقد يكون في كتب لم نبحث فيها. فالأولى أن تسأل أهل العلم قبل نشره."),
        "fatwa": ("يُحال إلى<br>مفتٍ", "سؤالك يحتاج إلى فتوى", None),
        "scope": ("خارج<br>النطاق", "هذا خارج ما تتحقق منه «بيّنة»", None),
        "partial_msg": None,
        "you": "رسالتك", "five": "الكتب الخمسة", "no_match": "لا مطابق بلفظه", "no_result": "لا نتيجة",
        "no": "رقم", "p": "ص",
        "img_text": "النص الذي قرأناه من الصورة",
        "ocr_fail": "تعذّرت قراءة الصورة الآن. جرّب لصق نص الرسالة بدلًا منها.",
        "img_fix": "إن أخطأت القراءة، انسخ النص وصحّحه في تبويب «نص الرسالة».",
        "ai": "توضيح آلي، ليس من كلام أهل العلم", "segment": "الجزء الذي وجدناه من رسالتك",
        "matn": "المتن", "riwaya": "نص الرواية كما في الكتاب", "text_note": "تنبيه على النص:",
        "diff": "ما يختلف بين رسالتك ولفظ الكتاب:",
        "agree": "أقوال العلماء هنا متفقة", "differ": "اختلف أهل العلم فيه", "uncat": "أقوال غير مصنّفة",
        "h_differ": "أقوال أهل العلم كما وردت في كتبهم، دون ترجيح من الأداة",
        "h_same": "أقوال أهل العلم كما وردت في كتبهم",
        "cut": "الكلام مقتطع، فارجع إلى المصدر لقراءته كاملًا.", "isnad": "عرض السند",
        "more": "أحاديث أخرى قريبة في المعنى",
        "reply_h": "ردّ لطيف للمجموعة",
        "reply_note": "وصلتك الرسالة من مجموعة؟ هذا رد مكتوب من المصادر وحدها، تنسخه أو ترسله مباشرة.",
        "wa": "أرسل الرد على واتساب",
        "foot": "بيِّنة: تحدي الذكاء الاصطناعي في خدمة المحتوى الإسلامي، مؤسسة باذل 2026. "
                "المصادر والتراخيص ومنهجية العمل موثّقة في مستودع المشروع. "
                "للسؤال عن حالتك الخاصة، ارجع إلى جهة إفتاء معتمدة.",
        "spinner": "نجهّز فهرس المصادر لأول مرة… قد يستغرق بضع دقائق",
    },
    "en": {
        "switch": ("العربية", "?lang=ar"), "motto": "No ruling without evidence",
        "lead": "Paste a message as you received it, or upload a screenshot. We trace the hadith back to its book "
                "and show what scholars said about it in their own words, or tell you plainly that we couldn't find it.",
        "tab_text": "Message text", "tab_img": "Screenshot", "box": "The message as you received it (Arabic)", "placeholder": "Paste the Arabic message exactly as you received it\nقال رسول الله ﷺ: «…» انشرها تؤجر",
        "check": "Check this message", "try": "Or try an example:",
        "ex": ["WhatsApp message", "Well-known hadith", "Personal question"],
        "upload": "A WhatsApp screenshot, or an image card with the hadith",
        "upload_note": "We send the image to a Google service only to read its text. We don't store it.",
        "read": "Read image and check",
        "trust": ["We search <b>Sahih al-Bukhari</b>, <b>Sahih Muslim</b>, and <b>three books on popular sayings</b>",
                  "Rulings are <b>quoted, never generated</b>", "An AI tool, <b>not a fatwa authority</b>",
                  "We <b>don't store</b> your messages or images"],
        "empty": "Paste the message text first, or pick an example.",
        "searching": "Searching the five books…", "reading": "Reading the text in the image…",
        "no_text": "We couldn't find Arabic text in this image. Try a clearer one, or paste the text in the Message text tab.",
        "found": ("In the<br>Sahihayn", "We found this text in the Sahihayn",
                  "Each source is shown with its own text and its author's words, exactly as in the book."),
        "found_rul": ("Popular<br>sayings", "We found this text in books on popular sayings",
                      "These books collect sayings that spread widely, authentic and otherwise; read what the scholars said about it below."),
        "partial": ("Partly<br>found", "We found only part of your message",
                    "Each source is shown with its own text and its author's words, exactly as in the book."),
        "related": ("Not found<br>verbatim", "We didn't find this exact text",
                    "Below are other hadiths close in meaning. They are not a ruling on what you wrote."),
        "not_found": ("Not<br>found", "We couldn't find this text in our sources",
                      "That doesn't mean it is fabricated; it may be in books we didn't search. "
                      "It's best to ask a scholar before sharing it."),
        "fatwa": ("Ask a<br>mufti", "Your question needs a fatwa",
                  "It seems to concern a personal situation. Bayyinah only verifies hadith and doesn't issue "
                  "fatwas; please ask a recognized fatwa authority."),
        "scope": ("Out of<br>scope", "This is outside what Bayyinah checks",
                  "Bayyinah verifies Arabic hadith texts. General questions, Quranic verses, and non-Arabic "
                  "text are outside what it checks."),
        "partial_msg": "We found only the text shown below in our sources. The rest of your message isn't in them, "
                       "so please don't attribute it to the Prophet ﷺ before verifying it.",
        "you": "Your message", "five": "The five books", "no_match": "No exact match", "no_result": "No result",
        "no": "No.", "p": "p.",
        "img_text": "Text we read from the image",
        "ocr_fail": "We couldn't read the image right now. Try pasting the message text instead.",
        "img_fix": "If the reading is wrong, copy the text, fix it, and paste it in the Message text tab.",
        "ai": "", "segment": "The part of your message we found",
        "matn": "Hadith text", "riwaya": "Narration as it appears in the book", "text_note": "Note on this text:",
        "diff": "Differences between your message and the book's wording:",
        "agree": "Scholars' rulings agree", "differ": "Scholars differ on it", "uncat": "Uncategorized rulings",
        "h_differ": "What scholars said, quoted from their books, with no preference given by the tool",
        "h_same": "What scholars said, quoted from their books",
        "cut": "This quote is shortened; see the source to read it in full.", "isnad": "Show chain of narration",
        "more": "Other hadiths close in meaning",
        "reply_h": "A gentle reply for the group",
        "reply_note": "Got this from a group? Here's a reply in Arabic, written only from the sources. "
                      "Copy it or send it directly.",
        "wa": "Send reply on WhatsApp",
        "foot": "Bayyinah: AI Challenge Serving Islamic Content, Bathel Foundation 2026. Sources, licenses, and "
                "methodology are documented in the project repository. For your personal situation, please "
                "consult a recognized fatwa authority.",
        "spinner": "Preparing the source index for the first time… this may take a few minutes",
    },
}[LANG]

BOOKS_EN = {"صحيح البخاري": "Sahih al-Bukhari", "صحيح مسلم": "Sahih Muslim", "كشف الخفاء": "Kashf al-Khafa",
            "الدرر المنتثرة": "al-Durar al-Muntathira", "الفوائد الموضوعة": "al-Fawa'id al-Mawdu'a",
            "الدرر المنتثرة في الأحاديث المشتهرة": "al-Durar al-Muntathira",
            "الفوائد الموضوعة في الأحاديث الموضوعة": "al-Fawa'id al-Mawdu'a"}
SOURCE_EN = {"المصادر الأصلية": "Primary sources", "كتب الأحكام والمشتهرات": "Books on popular sayings",
             "مدقق من أ. فاطمة": "Verified by our reviewer", "التخريج": "Takhrij"}


BOOK_EDITION = r"\s*-\s*ت\s+عبد\s+الباقي|\s+ط\s+القدسي"     # «صحيح مسلم - ت عبد الباقي» ← «صحيح مسلم»


def book(name: str) -> str:
    name = re.sub(BOOK_EDITION, "", name or "").strip()
    return BOOKS_EN.get(name, name) if EN else name


def source_label(name: str) -> str:
    return SOURCE_EN.get(name, name) if EN else name


def engine_note(note: str, book_name: str) -> str:
    """ملاحظات المحرك الثابتة تُترجم؛ وغيرها يُعرض كما هو."""
    if not EN or not note:
        return note
    if note.startswith("هذا الحديث مروي في"):
        return f"This hadith is narrated in {book(book_name)}."
    if note.startswith("لم يتوفر حكم في مصادرنا"):
        return "No ruling on it is available in our sources; please consult a specialist."
    return note


# ─────────────────────────── المحرك ───────────────────────────
@st.cache_resource(show_spinner=False)
def load_engine():
    from engine import build_index
    build_index()
    return True


with st.spinner(T["spinner"]):
    load_engine()
from message import verify_message            # noqa: E402  (بعد بناء الفهرس)
from llm import explain                       # noqa: E402
from reply import share_reply, whatsapp_link  # noqa: E402

SEARCHED = ["صحيح البخاري", "صحيح مسلم", "كشف الخفاء", "الدرر المنتثرة", "الفوائد الموضوعة"]


# ─────────────────────────── مكوّنات العرض ───────────────────────────
def where(m: dict) -> str:
    parts = [m.get("chapter", "")]
    if m.get("number"):
        parts.append(f"{T['no']} {m['number']}")
    if m.get("page"):
        parts.append(f"{T['p']} {m['page']}")
    return "، ".join(esc(p) for p in parts if p) if not EN else ", ".join(esc(p) for p in parts if p)


def chain_html(steps: list, end_kind: str = "end") -> str:
    """السلسلة: من رسالتك إلى مصدرها."""
    out = []
    for i, s in enumerate(steps):
        cls = end_kind if i == len(steps) - 1 else ""
        out.append(f'<span class="{cls}">{esc(s)}</span>')
    return '<div class="chain" aria-label="path">' + "<i></i>".join(out) + "</div>"


def verdict_html(kind: str, seal: str, title: str, body: str) -> str:
    return (f'<div class="verdict"><div class="seal v-{kind}" aria-hidden="true">{seal}</div>'
            f'<div><h2>{esc(title)}</h2><p>{esc(body or "")}</p></div></div>')


FLAGS = {"متفق": ("f-agree", T["agree"]), "مختلف فيه": ("f-differ", T["differ"]),
         "غير مصنّف": ("f-none", T["uncat"])}


def page_html(m: dict) -> str:
    """صفحة مصدر كاملة لنتيجة مطابقة. النصوص الشرعية تبقى بالعربية دائمًا."""
    is_rul = m.get("layer") in ("rulings", "verified", "takhreej")
    h = f'<div class="page{" rul" if is_rul else ""}">'
    h += f'<p class="book">{esc(book(m.get("book", "")))}</p>'
    w = where(m)
    sep = ", " if EN else "، "
    h += f'<p class="where">{w + sep if w else ""}{esc(source_label(m.get("source_type", "")))}</p>'
    label = T["matn"] if m.get("matn_trusted", True) else T["riwaya"]
    h += f'<p class="matn-label">{esc(label)}</p>'
    h += f'<p class="matn">{esc(m.get("matn", ""))}</p>'

    if not m.get("matn_trusted", True) and m.get("matn_note"):
        h += f'<div class="warn">{T["text_note"]} <span dir="rtl">{esc(m["matn_note"])}</span></div>'
    if "» بدل «" in (m.get("diff") or ""):
        h += f'<p class="diff">{T["diff"]} <span dir="rtl">{esc(m["diff"])}</span></p>'

    if m.get("agreement") in FLAGS:
        cls, txt = FLAGS[m["agreement"]]
        h += f'<span class="flag {cls}">{txt}</span>'

    rulings = m.get("rulings", [])
    if rulings:
        title = T["h_differ"] if m.get("agreement") == "مختلف فيه" else T["h_same"]
        h += f'<div class="hashiya"><p class="h-title">{title}</p>'
        for rl in rulings:
            quote = (rl.get("quote") or rl.get("ruling") or "").lstrip(". ")
            ref = esc(book(rl.get("book", ""))) + (f"، {esc(rl['location'])}" if rl.get("location") else "")
            h += (f'<div class="qawl"><div class="who">{esc(rl.get("scholar", ""))}<small>{ref}</small></div>'
                  f'<blockquote>«{esc(quote)}»</blockquote>')
            if rl.get("quote_truncated"):
                h += f'<p class="note">{T["cut"]}</p>'
            if rl.get("quote_note"):
                h += f'<p class="note">{esc(rl["quote_note"])}</p>'
            h += "</div>"
        h += "</div>"

    if m.get("isnad"):
        h += f'<details><summary>{T["isnad"]}</summary><div class="isnad">{esc(m["isnad"])}</div></details>'
    note = re.sub(BOOK_EDITION, "", engine_note(m.get("note", ""), m.get("book", "")))
    if note:
        h += f'<p class="note">{esc(note)}</p>'
    return h + "</div>"


def near_html(m: dict) -> str:
    """نتيجة قريبة في المعنى: مختصرة، ولا تُعرض كأنها جواب."""
    w = where(m)
    sep = ", " if EN else "، "
    return (f'<div class="near"><p class="matn">{esc(m.get("matn", ""))}</p>'
            f'<p class="where">{esc(book(m.get("book", "")))}{sep + w if w else ""}</p></div>')


# ─────────────────────────── الرأس ───────────────────────────
switch_label, switch_href = T["switch"]
st.markdown(f"""
<div class="hero">
  <a class="lang" href="{switch_href}" target="_self">{switch_label}</a>
  <p class="word">بيِّنة</p>
  <p class="motto">{T["motto"]}</p>
  <p class="lead">{T["lead"]}</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────── الإدخال ───────────────────────────
# نصوص الأمثلة تبقى بالعربية، لأن الأداة تتحقق من النصوص العربية
EXAMPLES = [
    "صباح الخير 🌹 قال رسول الله ﷺ: «اطلبوا العلم ولو في الصين» انشرها تؤجر ولا تجعلها تقف عندك",
    "إنما الأعمال بالنيات",
    "زوجي حلف بالطلاق فما الحكم؟",
]


def use_example(text: str):
    st.session_state["msg"] = text
    st.session_state.pop("result", None)


tab_text, tab_img = st.tabs([T["tab_text"], T["tab_img"]])

with tab_text:
    st.text_area(T["box"], key="msg", height=130, placeholder=T["placeholder"])
    run_text = st.button(T["check"], type="primary", use_container_width=True)
    st.markdown(f'<p class="try">{T["try"]}</p>', unsafe_allow_html=True)
    cols = st.columns(len(EXAMPLES))
    for col, label, text in zip(cols, T["ex"], EXAMPLES):
        col.button(label, on_click=use_example, args=(text,), use_container_width=True)

with tab_img:
    img = st.file_uploader(T["upload"], type=["png", "jpg", "jpeg", "webp"])
    st.caption(T["upload_note"])
    if img:
        st.image(img, use_container_width=True)
    run_img = st.button(T["read"], type="primary", use_container_width=True, disabled=img is None)

st.markdown('<div class="trust">' + "".join(f"<span>{x}</span>" for x in T["trust"]) + "</div>",
            unsafe_allow_html=True)

# ─────────────────────────── التنفيذ ───────────────────────────
if run_text:
    st.session_state.pop("result", None)
    text = (st.session_state.get("msg") or "").strip()
    if not text:
        st.warning(T["empty"])
    else:
        with st.spinner(T["searching"]):
            r = verify_message(text)
            st.session_state["result"] = (text, r, explain(text, r))

if run_img and img:
    st.session_state.pop("result", None)
    from ocr import read_image, OCRError
    text = None
    try:
        with st.spinner(T["reading"]):
            text = read_image(img.getvalue(), img.type or "image/png")
    except OCRError as e:
        st.error(str(e))
    except Exception:
        st.error(T["ocr_fail"])
    if text == "":
        st.warning(T["no_text"])
    elif text:
        with st.spinner(T["searching"]):
            r = verify_message(text, input_type="image", extracted_text=text)
            st.session_state["result"] = (text, r, explain(text, r))

# ─────────────────────────── النتيجة ───────────────────────────
if "result" in st.session_state:
    text, r, ex = st.session_state["result"]
    decision = r.get("decision")
    matches, related = r.get("matches", []), r.get("related", [])[:3]
    sah_cards = [m for m in matches if m.get("layer") == "sahihayn"]
    top = (sah_cards or matches or [{}])[0]       # السلسلة توافق الختم: بطاقة الصحيحين أولًا إن وُجدت

    if decision == "found":
        in_sah = any(m.get("layer") == "sahihayn" for m in matches)
        kind, (seal, title, body) = (("alert", T["partial"]) if r.get("partial")
                                     else ("found", T["found"]) if in_sah
                                     else ("rul", T["found_rul"]))
        steps = [T["you"], book(top.get("book", "")), *([f"{T['no']} {top['number']}"] if top.get("number") else [])]
        st.markdown(verdict_html(kind, seal, title, body) + chain_html([s for s in steps if s]),
                    unsafe_allow_html=True)
    elif decision == "related_only":
        seal, title, body = T["related"]
        st.markdown(verdict_html("near", seal, title, body)
                    + chain_html([T["you"], T["five"], T["no_match"]], "miss"), unsafe_allow_html=True)
    elif decision == "not_found":
        seal, title, body = T["not_found"]
        st.markdown(verdict_html("none", seal, title, body)
                    + chain_html([T["you"], *[book(b) for b in SEARCHED], T["no_result"]], "miss"),
                    unsafe_allow_html=True)
    elif decision == "fatwa":
        seal, title, body = T["fatwa"]
        st.markdown(verdict_html("fatwa", seal, title, body or r.get("message", "")), unsafe_allow_html=True)
    elif decision == "out_of_scope":
        seal, title, body = T["scope"]
        st.markdown(verdict_html("none", seal, title, body or r.get("message", "")), unsafe_allow_html=True)

    if r.get("partial"):
        st.markdown(f'<div class="alert">{esc(T["partial_msg"] or r.get("message", ""))}</div>',
                    unsafe_allow_html=True)

    if r.get("input_type") == "image":
        with st.expander(T["img_text"], expanded=True):
            st.markdown(f'<div class="seg">{esc(r.get("extracted_text", ""))}</div>', unsafe_allow_html=True)
            st.caption(T["img_fix"])

    # الجملة التمهيدية تأتي من المحرك بالعربية؛ فتُعرض في الواجهة العربية فقط
    intro = (ex or {}).get("intro", "")
    if not EN and intro and decision in ("found", "related_only") and not r.get("partial"):
        label = f'<span class="ai">{T["ai"]}</span><br>' if ex.get("source") == "model" else ""
        st.markdown(f'<p class="intro">{label}{esc(intro)}</p>', unsafe_allow_html=True)

    if r.get("segment"):
        st.markdown(f'<div class="seg"><small>{T["segment"]}</small>{esc(r["segment"])}</div>',
                    unsafe_allow_html=True)

    for m in matches:
        st.markdown(page_html(m), unsafe_allow_html=True)

    if related and decision == "related_only":
        st.markdown("".join(near_html(m) for m in related), unsafe_allow_html=True)
    elif related and decision == "found":
        with st.expander(T["more"]):
            st.markdown("".join(near_html(m) for m in related), unsafe_allow_html=True)

    reply = share_reply(r, text)     # الرد بالعربية دائمًا: يُرسل إلى مجموعة وصلت منها رسالة عربية
    if reply:
        st.markdown(f'<p class="reply-h">{T["reply_h"]}</p>', unsafe_allow_html=True)
        st.caption(T["reply_note"])
        st.code(reply, language=None)
        st.link_button(T["wa"], whatsapp_link(reply), use_container_width=True)

st.markdown(f'<div class="foot">{T["foot"]}</div>', unsafe_allow_html=True)
