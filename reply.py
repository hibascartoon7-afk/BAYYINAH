# -*- coding: utf-8 -*-
"""
«ردّ للمجموعة»: نصٌّ لطيف موثّق، يرسله المستخدم إلى المجموعة التي وصلته منها الرسالة.

المبادئ نفسها التي تقوم عليها «بيّنة»:
  - يُكتب من البيانات وحدها، بلا نموذج لغوي، فلا يُختلق فيه حكم ولا مصدر.
  - لا يحكم على الحديث: ينقل موضعه في الصحيحين، أو كلام العلماء بنصه، أو يقول «لم أجده».
  - وجود النص في كتب الأحكام ليس حكمًا بوضعه، ففيها الصحيح أيضًا؛ فلا يقول الرد «موضوع».
  - لطيف مع المرسِل، فأكثر من ينشر هذه الرسائل ينشرها بنية طيبة.
  - لا يُقتطع كلام النبي ﷺ ولا كلام العالم أبدًا: إما أن يُنقل كاملًا، أو يُذكر موضعه فقط.
    (اقتطاع كلام العالم قد يحذف حكمه الذي يأتي غالبًا في آخره، أو يُبقي حديثًا آخر ساقه في كلامه.)

الاستعمال في الواجهة:
    from reply import share_reply, whatsapp_link
    text = share_reply(r, نص_الرسالة)     # r من verify_message
    if text:
        st.code(text, language=None)                       # فيه زر نسخ
        st.link_button("أرسل الرد على واتساب", whatsapp_link(text))
"""
import re
from urllib.parse import quote as _urlquote

from normalize import normalize

OPENING = "جزاك الله خيرًا على حرصك على نشر الخير 🌹"
CLOSING = "— تحققتُ منه عبر «بيّنة»، وهي تنقل المصادر كما هي ولا تُصدر أحكامًا."

MAX_MATN = 600      # حرفًا: الحديث الأطول من هذا لا يُقتطع، بل يُذكر موضعه فقط
MAX_QUOTE = 220     # حرفًا: كلام العالم الأطول من هذا لا يُقتطع، بل يُذكر موضعه فقط

# علامات أن الرسالة تنسب شيئًا إلى النبي ﷺ أو تنقل حديثًا (لا نرسل «لم أجده» لكلام عادي)
_CUE = re.compile(r"ﷺ|صلى الله عليه وسلم|صلي الله عليه وسلم|[«»\"“”]|حديث|النبي|رسول الله|قال الله")


def _one_line(text: str) -> str:
    return " ".join((text or "").split())


def _book_name(book: str) -> str:
    """«صحيح مسلم - ت عبد الباقي» ← «صحيح مسلم»؛ «كشف الخفاء ط القدسي» ← «كشف الخفاء»."""
    return re.sub(r"\s*-\s*ت\s+عبد\s+الباقي|\s+ط\s+القدسي", "", book or "").strip()


def _where(card: dict) -> str:
    """«صحيح البخاري (رقم 13)»، أو الكتاب وحده إن كان الرقم مخفيًّا لأنه مشكوك فيه."""
    book = _book_name(card.get("book", ""))
    num = card.get("number", "")
    return f"{book} (رقم {num})" if num else book


def _sahihayn_part(card: dict) -> list:
    matn = _one_line(card.get("matn", ""))
    # نقتبس اللفظ فقط إن كان متنًا خالصًا (بلا إسناد) وغير طويل؛ وإلا نذكر الموضع، ولا نقتطع كلام النبي ﷺ
    if card.get("matn_trusted", True) and matn and len(matn) <= MAX_MATN:
        lines = [f"هذا الحديث مرويٌّ في {_where(card)}، ولفظه:", f"«{matn}»"]
    else:
        lines = [f"هذا الحديث مرويٌّ في {_where(card)}، فالأولى أن نرجع إلى لفظه كاملًا هناك."]
    # «بدل» = كلمة تغيّرت فعلًا. أما «نقص» فمعناه أن المرسِل نقل جزءًا من الحديث، وهذا ليس خطأً في اللفظ.
    if "» بدل «" in (card.get("diff") or ""):
        lines.append("واللفظ المنتشر يختلف عن لفظ الكتاب في بعض الكلمات، فالأولى أن نرويه بلفظ الكتاب.")
    return lines


def _ruling_line(card: dict, r: dict) -> str:
    who = r.get("scholar") or "المؤلف"
    book = _book_name(r.get("book") or card.get("book", ""))
    loc = f" ({r['location']})" if r.get("location") else ""
    q = _one_line(r.get("quote", "")).lstrip(". ")
    complete = q and len(q) <= MAX_QUOTE and not r.get("quote_truncated") and not r.get("quote_note")
    if complete:
        return f"• قال {who} في «{book}»{loc}: «{q}»"
    return f"• ذكره {who} في «{book}»{loc}، فالأولى أن يُقرأ كلامه فيه كاملًا من الكتاب."


def _rulings_part(cards: list) -> list:
    lines = ["لم يظهر هذا النص في بحثي في الصحيحين، وهذا ما في كتب أهل العلم عنه:"]
    for card in cards[:2]:
        for r in (card.get("rulings") or [])[:1]:
            lines.append(_ruling_line(card, r))
    if len(lines) == 1:            # لا كلام منقول: نذكر الكتاب وحده
        lines.append(f"• ذُكر في {_where(cards[0])}.")
    lines.append("وهذه الكتب تجمع ما اشتهر على الألسنة، وفيها الصحيح وغيره، "
                 "فالأولى أن نقرأ كلام أهل العلم فيه قبل أن ننشره منسوبًا إلى النبي ﷺ.")
    return lines


def share_reply(result: dict, message: str = "") -> str:
    """نص الرد للمجموعة، أو نص فارغ حين لا يناسب الرد.
    message: نص الرسالة الأصلي (اختياري). إن أُعطي، لا يُكتب رد «لم أجده» لرسالة لا تنقل حديثًا أصلًا."""
    decision = result.get("decision")
    if decision in ("fatwa", "out_of_scope"):
        return ""

    lines = [OPENING, ""]

    if decision == "found":
        cards = result.get("matches") or []
        sah = [c for c in cards if c.get("layer") == "sahihayn"]
        rul = [c for c in cards if c.get("layer") in ("verified", "rulings")]   # المعتمد فيه أحكام، فيُعامل كالأحكام

        if sah:
            lines += _sahihayn_part(sah[0])
        elif rul:
            lines += _rulings_part(rul)
        else:
            return ""
        if result.get("partial"):
            lines.insert(2, "وجدتُ في المصادر ما يوافق جزءًا من الرسالة فقط:")
            lines.append("أما باقي الرسالة فلم أجده في المصادر، فالأولى ألا ننسبه إلى النبي ﷺ حتى نتثبّت منه.")
    else:  # related_only / not_found
        if message and not _CUE.search(message):
            return ""
        lines += ["بحثتُ عن هذا النص في صحيحَي البخاري ومسلم وفي ثلاثة من كتب الأحاديث المشتهرة، فلم أجده بلفظه.",
                  "وعدم وجوده فيها لا يعني أنه غير صحيح، فقد يكون في كتب أخرى؛ "
                  "فالأولى أن نسأل أهل العلم قبل أن ننشره منسوبًا إلى النبي ﷺ."]

    lines += ["", CLOSING]
    return "\n".join(lines)


def whatsapp_link(text: str) -> str:
    """رابط يفتح واتساب والرد مكتوب فيه، فيختار المستخدم المجموعة ويرسل."""
    return "https://wa.me/?text=" + _urlquote(text)
