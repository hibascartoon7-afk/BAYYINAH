# -*- coding: utf-8 -*-
"""
التحقق من الرسالة كما تصل، لا من الحديث وحده.

الرسالة المنتشرة تأتي عادةً هكذا:
    صباح الخير 🌹 قال رسول الله ﷺ: «اطلبوا العلم ولو في الصين» انشرها تؤجر ولا تجعلها تقف عندك
فتغرق الكلمات الزائدة معنى الحديث، فلا يجده البحث.

الطريقة (بلا نموذج لغوي، فلا يغادر نص المستخدم الجهاز):
  1) تُفحص الرسالة كاملة أولًا. فإن وُجد الحديث بلفظه، تُعاد النتيجة كما هي.
  2) وإلا تُستخرج منها مقاطع مرشّحة، ويُفحص كل مقطع:
       - ما بين علامات التنصيص « » " " “ ”
       - ما بعد «قال رسول الله ﷺ» أو «قال النبي ﷺ» أو «قال الله تعالى» ونحوها
       - الرسالة بعد حذف التحية وعبارات النشر وصيغ السؤال عن الصحة
  3) إن وُجد الحديث بلفظه في أحد المقاطع، تُعاد نتيجته، ومعه المقطع الذي فُحص (segment).
  4) وإلا تُعاد نتيجة الرسالة كاملة، فيبقى قرار الفتوى والسؤال العام والامتناع كما هو تمامًا.
  5) إن بقي في الرسالة كلام آخر غير المقطع الذي وُجد (مثل وعد «من نشرها فتح الله له أبواب الرزق»)،
     لا نقول «وجدنا ما كتبته»: نضع partial=True، ونُنبّه أن باقي الرسالة لم نجده في مصادرنا.
     وإلا صار حديث صحيح قصير، أو ذِكر مثل «سبحان الله وبحمده»، غطاءً لرسالة مختلقة.

الاستعمال في الواجهة:
    from message import verify_message
    r = verify_message(نص_الرسالة)
"""
import difflib
import re

from engine import verify, FATWA, FATWA_MSG
from normalize import normalize

_QUOTED = re.compile(r'[«"“]\s*([^«»"“”]{4,}?)\s*[»"”]')

# بعد normalize: ﷺ صارت «صلي الله عليه وسلم»، والألف والتاء والياء موحّدة، والترقيم محذوف
_ATTRIBUTION = re.compile(
    r"(?:قال|يقول|عن)\s+(?:رسول\s+الله|النبي|الرسول)(?:\s+صلي\s+الله\s+عليه\s+وسلم)?(?:\s+انه\s+قال|\s+قال)?\s+"
    r"|قال\s+الله\s+(?:تعالي|عز\s+وجل|تبارك\s+وتعالي)\s+"
)
_NOISE = [
    r"صباح\s+(?:الخير|النور)", r"مساء\s+(?:الخير|النور)",
    r"السلام\s+عليكم(?:\s+ورحمه\s+الله(?:\s+وبركاته)?)?", r"جمعه\s+مباركه",
    r"اسعد\s+الله\s+(?:صباحكم|مساءكم|اوقاتكم)(?:\s+بكل\s+خير)?",
    # الأنماط مكتوبة بصيغتها بعد normalize: «تؤجر» تصير «توجر»، و«أرسلها» تصير «ارسلها»
    r"انشرها\s+توجر", r"انشر\s+توجر", r"انشروها", r"شاركها", r"ساهم\s+في\s+نشرها",
    r"و?لا\s+تجعلها\s+تقف\s+عندك", r"و?لا\s+توقفها\s+عندك",
    r"ارسلها\s+(?:الي|ل)\s*\S+(?:\s+(?:اشخاص|شخص|اصدقاء))?",
    r"هل\s+(?:هذا\s+)?(?:الحديث|الكلام)\s+(?:صحيح|ثابت)", r"هل\s+حديث", r"هل\s+هذا\s+(?:الكلام\s+)?(?:للنبي|عن\s+النبي)",
    r"ما\s+(?:صحه|درجه)\s+(?:هذا\s+)?(?:الحديث)?", r"\bصحيح\s*$",
    # الراوي من الصحابة قبل الحديث: «عن أبي هريرة رضي الله عنه قال»، «عن أنس بن مالك عن النبي»
    r"\bعن\s+(?:\S+\s+){0,4}?رضي\s+الله\s+(?:عنهما|عنها|عنهم|عنه)(?:\s+(?:انه\s+)?(?:قال|قالت))?",
    r"رضي\s+الله\s+(?:عنهما|عنها|عنهم|عنه)",
    r"\bعن\s+(?:\S+\s+){1,4}?(?=عن\s+(?:رسول\s+الله|النبي|الرسول)\b)",
    # ذكر المصدر بعد الحديث: «رواه البخاري ومسلم»، «متفق عليه»، «صدق رسول الله ﷺ»
    r"\b(?:رواه|اخرجه|خرجه)(?:\s+(?:الامام|الامامان|الشيخان|و?البخاري|و?مسلم|و?الترمذي|و?ابو\s+داود|و?النسائي|و?ابن\s+ماجه|و?احمد|في\s+صحيحه|في\s+صحيحيهما))*",
    r"متفق\s+عليه", r"صدق\s+رسول\s+الله", r"حديث\s+(?:صحيح|شريف|نبوي)\s*$",
    r"صلي\s+الله\s+عليه\s+وسلم",
    r"(?:قال|يقول|عن)\s+(?:رسول\s+الله|النبي|الرسول)",
]
_NOISE_RE = re.compile("|".join(f"(?:{p})" for p in _NOISE))

_MIN_WORDS = 3   # مقطع أقصر من هذا لا يُفحص وحده، حتى لا تُطابَق عبارة عابرة بحديث

# كلمات لا تُحتسب حين نقيس «هل بقي في الرسالة كلام آخر؟» (بصيغتها بعد normalize)
_FILLER = {"و", "من", "في", "علي", "عن", "الي", "ان", "او", "ما", "لا", "هذا", "هذه", "ذلك", "له", "لها",
           "هو", "هي", "قد", "ثم", "يا", "هل", "مع", "كل", "قال", "قالت", "انه", "الله"}
_EXTRA_MIN = 3   # ثلاث كلمات دالّة فأكثر خارج المقطع = كلام آخر يجب التنبيه عليه

PARTIAL_NOTE = ("وجدنا في مصادرنا النص المعروض أدناه فقط. أما باقي رسالتك فلم نجده فيها، "
                "فلا تنسبه إلى النبي ﷺ قبل التثبت منه.")


def _clean(norm_text: str) -> str:
    return re.sub(r"\s+", " ", _NOISE_RE.sub(" ", norm_text)).strip()


def candidates(text: str) -> list:
    """المقاطع المرشّحة لأن تكون نص الحديث داخل الرسالة، بلا تكرار، والأدق أولًا."""
    out = []

    def add(t: str):
        t = _clean(normalize(t)) if t else ""
        if len(t.split()) >= _MIN_WORDS and t not in out:
            out.append(t)

    for q in _QUOTED.findall(text or ""):            # 1) ما بين علامات التنصيص
        add(q)
    norm = normalize(text or "")
    for m in _ATTRIBUTION.finditer(norm):             # 2) ما بعد «قال رسول الله ﷺ»
        add(norm[m.end():])
    add(text)                                         # 3) الرسالة بعد حذف التحية وعبارات النشر
    return out


def _best_similarity(r: dict) -> float:
    return max((c.get("similarity", 0) for c in r.get("matches", [])), default=0)


def _in(word: str, words: set) -> bool:
    """الكلمة موجودة، أو قريبة جدًا (تحاسدو/تحاسدوا)، بالمقياس نفسه الذي يستعمله المحرك (0.8)."""
    return word in words or any(difflib.SequenceMatcher(None, word, x).ratio() >= 0.8 for x in words)


def _extra_words(text: str, seg: str) -> list:
    """الكلمات الدالّة في الرسالة (بعد حذف التحية وعبارات النشر واسم الصحابي والمصدر) التي ليست من المقطع الذي وُجد."""
    seg_words = set(seg.split())
    return [w for w in _clean(normalize(text or "")).split() if w not in _FILLER and not _in(w, seg_words)]


# كسر التعادل في ترتيب البطاقات، ولا شيء غيره.
# المحرك يعدّ الكلمة القريبة جدًا مطابقة («سبحانك» ≈ «سبحان»)، فقد تأخذ بطاقةٌ فيها كلمات مستبدلة
# نسبةَ التطابق نفسها التي تأخذها البطاقة المطابقة حرفيًا، فتظهر قبلها. مثال: «سبحان الله وبحمده»
# كانت أول بطاقته «سبحانك ربي وبحمدك» (مسلم 484)، وهو ذِكر آخر، قبل «… سبحان الله وبحمده» (مسلم 2731).
#
# القاعدة: يبقى ترتيب المحرك كما هو بين البطاقات المختلفة في نسبة التطابق. وبين البطاقات المتساوية فيها
# (المتجاورة في ترتيب المحرك) يُقدَّم الأقل كلماتٍ مستبدلة، ثم المصدر حسب طبقته، ثم ترتيب المحرك.
# والكلمات المستبدلة تُعدّ من حقل diff بعدد مرات «» بدل «»؛ أما الناقصة فلا تُعدّ، فنقلُ جزءٍ من الحديث ليس خطأً في اللفظ.
_LAYER_ORDER = {"verified": 0, "sahihayn": 1, "rulings": 2, "takhreej": 3}


def _subs(card: dict) -> int:
    return (card.get("diff") or "").count("» بدل «")


def _order(result: dict) -> dict:
    cards = result.get("matches") or []
    if len(cards) < 2:
        return result
    out, i = [], 0
    while i < len(cards):
        sim = round(cards[i].get("similarity", 0), 4)
        j = i
        while j + 1 < len(cards) and round(cards[j + 1].get("similarity", 0), 4) == sim:
            j += 1
        tied = sorted(enumerate(cards[i:j + 1]),
                      key=lambda ic: (_subs(ic[1]), _LAYER_ORDER.get(ic[1].get("layer"), 9), ic[0]))
        out += [c for _, c in tied]
        i = j + 1
    return {**result, "matches": out}


def verify_message(text: str, **kwargs) -> dict:
    """مثل verify، لكن للرسالة المنتشرة كما تصل. تضيف حقلين:
    segment: المقطع الذي وُجد فيه الحديث (فارغ إن فُحصت الرسالة كاملة).
    partial: True إن بقي في الرسالة كلام آخر لم نجده؛ والواجهة تعرض message تنبيهًا ظاهرًا."""
    whole = _order(verify(text, **kwargs))
    if whole.get("decision") == "found":
        # الرسالة كلها وُجدت؛ لكن قد يُلحَق بحديث طويل وعدٌ مختلق قصير لا يكفي لإسقاط نسبة التطابق.
        # فنقارن كلمات الرسالة بنص الحديث الذي وُجد نفسه.
        top = (whole.get("matches") or [{}])[0]
        extra = _extra_words(text, normalize(top.get("matn", "")))
        result = {**whole, "segment": "", "partial": len(extra) >= _EXTRA_MIN}
        if result["partial"]:
            result["message"] = (PARTIAL_NOTE + " " + (whole.get("message") or "")).strip()
        return result

    found = []
    for seg in candidates(text):
        if seg == normalize(text):
            continue                                  # فُحص كاملًا من قبل
        r = _order(verify(seg, **kwargs))
        if r.get("decision") == "found":
            found.append((seg, r))

    if not found:
        return {**whole, "segment": "", "partial": False}

    # الأدق تطابقًا، ثم الأطول (حتى يبقى خارجه أقل ما يمكن)
    seg, best = max(found, key=lambda x: (_best_similarity(x[1]), len(x[0].split())))
    extra = _extra_words(text, seg)
    result = {**best, "segment": seg, "partial": len(extra) >= _EXTRA_MIN}
    if result["partial"]:
        result["message"] = (PARTIAL_NOTE + " " + (best.get("message") or "")).strip()
    if FATWA.search(normalize(text)) and FATWA_MSG not in (result.get("message") or ""):
        result["message"] = ((result.get("message") or "") + " " + FATWA_MSG).strip()
    return result
