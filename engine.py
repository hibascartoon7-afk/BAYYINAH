# -*- coding: utf-8 -*-
"""
محرك بيّنة: يبحث بالمعنى في طبقات مستقلة.

قاعدة أساسية (بعد مراجعة الربط الآلي):
  لا يُربط حكم من كتب الأحكام بحديث من الصحيحين آليًا.
  كل مصدر يُعرض في بطاقة مستقلة بنصه وكلام مؤلفه، والمستخدم يرى الفرق بنفسه.
  السبب: أي عتبة تشابه تخطئ، ونسبة حكم إلى حديث ليس له خطأ شرعي.

ولا يولّد النظام حكمًا ولا مصدرًا. كل شيء يُنقل من البيانات كما هو.
"""
import os
import re
import json
import hashlib
import difflib
from collections import Counter

import numpy as np
import chromadb
from chromadb.utils import embedding_functions
from normalize import normalize

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MAX_DISTANCE = {"verified": 0.35, "sahihayn": 0.35, "rulings": 0.35, "takhreej": 0.35}
DEFAULT_DISTANCE = 0.35
BATCH = 4000
SAME_TEXT = 0.8          # نسبة كلمات المستخدم الموجودة في النص

LAYERS = [
    ("verified",  "data/verified_hadiths.json", "مدقق من أ. فاطمة"),
    ("sahihayn", "data/hadith_database.json", "المصادر الأصلية"),
    ("rulings",  "data/rulings_database.json", "كتب الأحكام والمشتهرات"),
    ("takhreej", "data/taj_database.json",     "التخريج"),
]
_PATHS = {name: path for name, path, _ in LAYERS}
_LABELS = {name: label for name, _, label in LAYERS}
_ORDER = {"verified": 0, "sahihayn": 1, "rulings": 2, "takhreej": 3}

MATN = re.compile(r'[«"“](.+?)[»"”]', re.S)
_H = r'[ً-ْٰ]*'


def _loose(word: str) -> str:
    return _H.join(re.escape(c) for c in word) + _H


PROPHET = re.compile("|".join(_loose(w) for w in ["رسول الله", "النبي"]))
SAYS = re.compile(r'(?:' + "|".join(_loose(w) for w in ["قال", "يقول", "قالت"]) + r')\s*:?\s*')

# (2) الواو اختيارية: «وحدثنا» و«وأخبرنا» شائعة جدًا في مسلم
ISNAD_START = re.compile(r'^\s*(?:و' + _H + r')?(?:' + "|".join(
    _loose(w) for w in ["حدثنا", "أخبرنا", "حدثني", "أخبرني", "ثنا", "نا"]) + r')')

# (3) علامات تدل على أن النص ليس متنًا خالصًا
EXPLAIN = re.compile("|".join(_loose(w) for w in [
    "قال العلماء", "قال النووي", "قال القاضي", "قال أهل اللغة",
    "ومعنى ذلك", "معناه", "قال الشيخ", "قال المصنف"]))
# إسناد ثانٍ داخل نص الحديث: «ح وحدثنا…» أو «بمثل حديث…»
SECOND_ISNAD = re.compile(
    r'(?:^|[\s.»"؟])(?:'
    r'ح\s*(?:و' + _H + r')?(?:' + "|".join(_loose(w) for w in ["حدثنا", "أخبرنا", "حدثني"]) + r')'
    r'|و' + _H + r'(?:' + "|".join(_loose(w) for w in ["حدثنا", "أخبرنا", "حدثني"]) + r')'
    r'|(?:' + "|".join(_loose(w) for w in ["حدثنا", "أخبرنا"]) + r')'
    r')')

# سلسلة رواة بصيغة المفرد بعد «قال فلان»: يميّزها أن بعد الاسم «عن» أو «بن» أو «ابن»
NARRATOR_CHAIN = re.compile(
    r'(?:^|[\s.»"؟:])(?:' + _loose("حدثني") + "|" + _loose("أخبرني") + r')\s+'
    r'(?=[^.؟«»]{0,40}?[\s،,](?:' + _loose("عن") + "|" + _loose("بن") + "|" + _loose("ابن") + r')\s)')

# صيغ تدل على رواية أخرى بالإسناد نفسه، تأتي بعد نص الحديث
SAME_CHAIN = re.compile(
    # صيغ مركّبة تكفي بذاتها (ويجوز أن تلحقها ضمائر: حديثهم، حديثه)
    "(?:" + "|".join(_loose(w) for w in [
        "بمثل حديث", "نحو حديث", "بمعنى حديث", "بهذا الإسناد", "بهذا الاسناد"]) + ")"
    # وكلمات مفردة تحتاج حدّ كلمة، كيلا تُلتقط داخل «بمثلها»
    + r"|(?:" + "|".join(_loose(w) for w in ["بمثله", "بنحوه"]) + r")(?![ً-ْٰ]*[ء-ي])")

_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
_client = chromadb.PersistentClient(path="./chroma_db")


def matn(record: dict) -> str:
    """نص الحديث بلا إسناد إن أمكن. قد يرجع النص كاملًا إن تعذّر الفصل."""
    if record.get("matn"):
        return record["matn"]
    text = record.get("text", "")
    parts = MATN.findall(text)
    joined = " ".join(parts).strip()
    if len(joined) >= 60:
        return joined
    first = min([i for i in (text.find('«'), text.find('"'), text.find('“')) if i != -1],
                default=-1)
    if first != -1:
        rest = re.sub(r'[«»"“”]', '', text[first:]).strip()
        if len(rest) > len(joined):
            return rest
    last = None
    for last in PROPHET.finditer(text):
        pass
    if last:
        says = SAYS.search(text, last.end(), last.end() + 60)
        if says:
            rest = text[says.end():].strip()
            if len(rest) > len(joined):
                return rest
    return joined or text


def isnad(record: dict) -> str:
    if record.get("isnad") is not None:
        return record["isnad"]
    text = record.get("text", "")
    if not ISNAD_START.search(text):
        return ""
    m_text = matn(record)
    pos = text.find(m_text[:40]) if m_text else -1
    return text[:pos].strip(' :،."«»') if pos > 0 else ""


def text_quality(record: dict) -> tuple:
    """
    هل النص المعروض متن خالص؟ يُرجع (موثوق؟، سبب التحفّظ).
    تُقرأ أولًا علامات التحفّظ التي وضعها التنظيف، ثم تُفحص العلل داخل النص.
    """
    if record.get("quality_flags"):                      # علامات وضعها التنظيف
        return False, record["quality_flags"][0]

    text, m_text = record.get("text", ""), matn(record)

    if m_text.strip() == text.strip() and ISNAD_START.search(text):
        return False, "تعذّر فصل المتن عن الإسناد"
    if EXPLAIN.search(m_text):
        return False, "النص يتضمن شرحًا من غير كلام النبي ﷺ"
    if SECOND_ISNAD.search(m_text):
        return False, "بعد نص الحديث رواية أو إسناد آخر"
    if NARRATOR_CHAIN.search(m_text):
        return False, "بعد نص الحديث رواية أو إسناد آخر"
    if SAME_CHAIN.search(m_text):
        return False, "بعد نص الحديث رواية أو إسناد آخر"
    if SAME_CHAIN.search(text) and len(normalize(m_text).split()) < 6:
        return False, "رواية متابعة: إسناد آخر للحديث نفسه، وليست حديثًا مستقلًا"
    return True, ""


FP_FILE = "./chroma_db/fingerprints.json"


def _saved_fps() -> dict:
    """البصمات المحفوظة. لا تُكتب إلا بعد اكتمال بناء الطبقة."""
    try:
        with open(FP_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_NORMALIZE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "normalize.py")


def _fingerprint(path: str) -> str:
    """بصمة محتوى الملف ومعه normalize.py: أي تغيير في البيانات أو في طريقة التوحيد
    يُعيد بناء الفهرس تلقائيًا، لأن الفهرس مبني على النص بعد توحيده."""
    h = hashlib.md5()
    for p in (path, _NORMALIZE_FILE):
        if os.path.exists(p):
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
    return h.hexdigest()


def index_ready() -> bool:
    """هل الفهارس مبنية ومطابقة لملفات البيانات؟"""
    for name, path, _ in LAYERS:
        if not os.path.exists(path):
            continue
        try:
            col = _client.get_collection(name, embedding_function=_ef)
        except Exception:
            return False
        if _saved_fps().get(name) != _fingerprint(path):
            return False
    return True


def build_index(force: bool = False):
    """
    يبني الفهارس. تُشغَّل مرة واحدة فقط؛ بعدها تُقرأ من chroma_db المحفوظ.
    force=True لإعادة البناء بعد تغيير ملفات البيانات.
    """
    if not force and index_ready():
        print("الفهارس جاهزة (محفوظة من تشغيل سابق). لإعادة بنائها: python engine.py --rebuild")
        return

    for name, path, label in LAYERS:
        if not os.path.exists(path):
            print(f"  ⚠️ لا يوجد {path} — تم تخطي «{label}»")
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        ids = [f"{name}-{h.get('id', i)}" for i, h in enumerate(data)]
        dup = [x for x, n in Counter(ids).items() if n > 1]
        if dup:
            raise ValueError(f"أرقام مكررة في {path}: {dup[:5]}")

        fps = _saved_fps()          # تُمحى البصمة قبل الهدم، فلا يبدو الفهرس جاهزًا وهو ناقص
        fps.pop(name, None)
        with open(FP_FILE, "w", encoding="utf-8") as f:
            json.dump(fps, f)

        try:
            _client.delete_collection(name)
        except Exception:
            pass
        col = _client.create_collection(name, embedding_function=_ef,
                                        metadata={"hnsw:space": "cosine"})
        trusted_n = 0
        for i in range(0, len(data), BATCH):
            part = data[i:i + BATCH]
            for h in part:
                h["matn"] = matn(h)
                h["isnad"] = isnad(h)
                ok, why = text_quality(h)
                h["matn_trusted"], h["matn_note"] = ok, why
                trusted_n += ok
            col.add(
                ids=ids[i:i + BATCH],
                documents=[normalize(h["matn"]) for h in part],
                metadatas=[{"payload": json.dumps(h, ensure_ascii=False)} for h in part],
            )
        print(f"  {label}: {len(data)} مدخلًا | متن موثوق في {trusted_n} "
              f"({round(trusted_n * 100 / max(len(data), 1))}%)")
        fps = _saved_fps()                      # تُكتب البصمة بعد اكتمال الطبقة فقط
        fps[name] = _fingerprint(path)
        with open(FP_FILE, "w", encoding="utf-8") as f:
            json.dump(fps, f)
    print("تم بناء الفهارس.")


def _coverage(user_text: str, original: str) -> float:
    u, o = normalize(user_text).split(), normalize(original).split()
    if not u or not o:
        return 0.0
    found = sum(1 for w in u if any(difflib.SequenceMatcher(None, w, x).ratio() >= 0.8 for x in o))
    return found / len(u)


def _diff(user_text: str, original: str) -> str:
    a, b = normalize(user_text).split(), normalize(original).split()
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "replace":
            out.append(f"«{' '.join(a[i1:i2])}» بدل «{' '.join(b[j1:j2])}»")
        elif tag == "delete":
            out.append(f"زيادة: «{' '.join(a[i1:i2])}»")
        elif tag == "insert":
            out.append(f"نقص: «{' '.join(b[j1:j2])}»")
    return "، ".join(out)


def _agreement(rulings: list) -> str:
    if not rulings:
        return "لا حكم في مصادرنا"
    cats = {r.get("category") for r in rulings if r.get("category")}
    if not cats:
        return "غير مصنّف"
    return "متفق" if len(cats) == 1 else "مختلف فيه"


def _search(layer: str, query: str, k: int):
    if not os.path.exists(_PATHS.get(layer, "")):
        return []
    try:
        col = _client.get_collection(layer, embedding_function=_ef)
    except Exception:
        raise RuntimeError(f"ملف «{layer}» موجود لكن فهرسه غير مبني. شغّلي: python engine.py")
    q = normalize(query)
    found = {}
    # (1) البحث بالمعنى، مع تجاهل المقاطع القصيرة جدًا
    res = col.query(query_texts=[q], n_results=k)
    for _id, meta, dist in zip(res["ids"][0], res["metadatas"][0], res["distances"][0]):
        h = json.loads(meta["payload"])
        if dist <= MAX_DISTANCE.get(layer, DEFAULT_DISTANCE) and len(normalize(matn(h)).split()) >= 3:
            found[_id] = (h, dist)
    # (2) البحث باللفظ: كل نص يحتوي كلمات السؤال نفسها.
    #     نستعمل get لا query: البحث المقيّد بشرط داخل query قد يُرجع نتائج ناقصة أو فارغة.
    if len(q.split()) >= 2:
        try:
            lex = col.get(where_document={"$contains": q}, limit=50,
                          include=["metadatas", "embeddings"])
            if len(lex["ids"]):
                qv = np.asarray(_ef([q])[0], dtype=float)
                scored = []
                for _id, meta, emb in zip(lex["ids"], lex["metadatas"], lex["embeddings"]):
                    ev = np.asarray(emb, dtype=float)
                    dist = 1 - float(qv @ ev) / ((np.linalg.norm(qv) * np.linalg.norm(ev)) or 1)
                    scored.append((dist, _id, meta))
                for dist, _id, meta in sorted(scored, key=lambda x: x[0])[:k]:
                    found.setdefault(_id, (json.loads(meta["payload"]), dist))
        except Exception as e:
            print(f"  ⚠️ تعذّر البحث باللفظ في «{layer}»: {e}")
    out = []
    for h, dist in found.values():
        h["_distance"] = round(dist, 3)
        out.append(h)
    return out


# (4) كاشف الفتوى — بصيغة النص بعد التوحيد (ى تصير ي، ة تصير ه)
FATWA = re.compile(
    r"(?:^|\s)(?:"
    r"هل\s+يجوز\s+(?:لي|لنا|ل?زوجت?ي|لزوجي)|"
    r"ما\s+حكم\s+(?:ما\s+فعلت|ما\s+فعلته|حالتي|وضعي|هذا\s+الامر)|"
    r"افتوني|افتني|(?:اريد|ابغي|ابغى|بدي|محتاج[هة]?)\s+فتو[يى]|فتو[يى]\s+في|"
    r"ماذا\s+افعل\s+في\s+حالتي|هل\s+علي\s+(?:اثم|كفار[هة]|قضاء)|"
    r"(?:زوجي|زوجتي|طلقت|طلقني|حلف)\s[^.]{0,40}?(?:فما\s+الحكم|ما\s+الحكم|ماذا\s+افعل|هل\s+يقع)|"
    r"حلف\s+بالطلاق|وقع\s+الطلاق"
    r")(?:\s|$)"
)
FATWA_MSG = ("يبدو أن سؤالك يحتاج إلى فتوى في حالة شخصية. «بيّنة» تتحقق من الأحاديث فقط ولا تُفتي؛ "
             "يُرجى سؤال جهة إفتاء معتمدة.")


def verify(user_text: str, k: int = 3, input_type: str = "text",
           extracted_text: str = "") -> dict:
    """
    (1) كل مصدر بطاقة مستقلة. لا ربط آلي بين حديث من الصحيحين وحكم من كتب الأحكام.
    """
    base = {"input_type": input_type, "extracted_text": extracted_text,
            "matches": [], "related": []}

    def make(h, layer):
        m_text = matn(h)
        trusted = h.get("matn_trusted", True)
        own = h.get("rulings", [])          # أحكام هذا المدخل وحده، من ملفه
        return {
            "matn": m_text,
            "isnad": isnad(h),
            "text": h.get("text", ""),
            "matn_trusted": trusted,
            "matn_note": h.get("matn_note", ""),
            # عنوان العرض: لا نسمّيه «متن» إلا إذا كان متنًا خالصًا
            "display_label": "المتن" if trusted else "نص الرواية كما في الكتاب",
            "book": h.get("book", ""),
            "chapter": h.get("chapter", ""),
            "number": "" if h.get("number_suspect") else h.get("number", ""),
            "page": h.get("page", ""),
            "layer": layer,
            "source_type": _LABELS[layer],
            "distance": h["_distance"],
            "similarity": round(_coverage(user_text, m_text), 2),
            "same_text": _coverage(user_text, m_text) >= SAME_TEXT,
            "diff": _diff(user_text, m_text),
            "agreement": _agreement(own),
            "rulings": own,
            "has_ruling": len(own) > 0,
        }

    candidates = []
    for layer in ("verified", "sahihayn", "rulings", "takhreej"):
        for h in _search(layer, user_text, k):
            candidates.append(make(h, layer))

    for c in candidates:
        if c["source_type"] == "المصادر الأصلية" and not c["has_ruling"]:
            c["note"] = f"هذا الحديث مروي في {c['book']}."
        elif not c["has_ruling"]:
            c["note"] = "لم يتوفر حكم في مصادرنا، راجع مختصًا."
        else:
            c["note"] = ""

    exact = sorted([c for c in candidates if c["same_text"]],
                   key=lambda c: (-c["similarity"], _ORDER.get(c["layer"], 9)))
    related = sorted([c for c in candidates if not c["same_text"]],
                     key=lambda c: (c["distance"], _ORDER.get(c["layer"], 9)))

    # الحديث الموجود بلفظه يُعرض ولو تضمّن ألفاظ فتوى (مثل «أفتني» داخل الحديث)
    if exact:
        msg = "كل مصدر معروض بنصه وكلام مؤلفه، ولم يُربط حكم بحديث آليًا."
        if FATWA.search(normalize(user_text)):
            msg += " " + FATWA_MSG          # سؤال شخصي وُجد له حديث: نعرضه ونُحيل أيضًا
        return {**base, "decision": "found", "matches": exact, "related": related,
                "message": msg}

    if FATWA.search(normalize(user_text)):
        return {**base, "decision": "fatwa", "message": FATWA_MSG}

    from scope import out_of_scope
    scope_msg = out_of_scope(user_text, related)
    if scope_msg:
        return {**base, "decision": "out_of_scope", "message": scope_msg}

    if related:
        return {**base, "decision": "related_only", "related": related,
                "message": "لم نجد هذا الحديث بلفظه في مصادرنا. وجدنا أحاديث قريبة في المعنى، "
                           "وهي أحاديث أخرى وليست حكمًا على ما كتبته."}
    return {**base, "decision": "not_found",
            "message": "لم يتم العثور على هذا الحديث في قاعدة بياناتنا المعتمدة. "
                       "يُرجى مراجعة مختص."}


def calibrate(pairs):
    for q, should in pairs:
        r = verify(q)
        ok = (r["decision"] == "found") == should
        best = (r["matches"] or r["related"] or [{}])[0]
        print(("✓" if ok else "✗"), r["decision"], best.get("distance"),
              best.get("similarity"), "|", q)


def distances(query: str, k: int = 3):
    """تطبع أقرب النتائج في كل طبقة مع مسافتها، لاختيار الحد بالأرقام."""
    for name, path, label in LAYERS:
        if not os.path.exists(path):
            continue
        col = _client.get_collection(name, embedding_function=_ef)
        res = col.query(query_texts=[normalize(query)], n_results=k)
        print(f"\n[{label}]  الحد الحالي: {MAX_DISTANCE.get(name, DEFAULT_DISTANCE)}")
        for meta, dist in zip(res["metadatas"][0], res["distances"][0]):
            h = json.loads(meta["payload"])
            print(f"   {round(dist, 3)}  | {h.get('book','')} {h.get('number','')} | {matn(h)[:70]}")


if __name__ == "__main__":
    import sys
    build_index(force="--rebuild" in sys.argv)
    tests = [
        "انما الاعمال بالنيات",
        "النظافة من الإيمان",
        "اطلبوا العلم ولو في الصين",
        "كيف اطبخ المقلوبة",
        "هل يجوز لي أن أصلي وأنا مسافر؟",
        "أريد فتوى في مسألة",
        "زوجي حلف بالطلاق فما الحكم؟",
    ]
    for q in tests:
        r = verify(q)
        print("\n" + "=" * 62)
        print("المدخل:", q)
        if r["decision"] in ("not_found", "fatwa"):
            print(" ", r["message"])
            continue
        if r["decision"] == "related_only":
            print(" ", r["message"])
        for m in (r["matches"] or r["related"])[:3]:
            print(f"\n  ── بطاقة: [{m['source_type']}]")
            print(f"  {m['display_label']}: {m['matn'][:170]}")
            if not m["matn_trusted"]:
                print(f"  ⚠️ {m['matn_note']}")
            loc = " — ".join(x for x in [m['book'], m['chapter'][:30]] if x)
            loc += f" — رقم {m['number']}" if m["number"] else ""
            loc += f" — ص {m['page']}" if m["page"] else ""
            print(f"  المصدر: {loc} | قرب: {m['distance']}")
            if m["agreement"] == "مختلف فيه":
                print("  اختلف العلماء في الحكم عليه، وهذه أبرز الأقوال:")
            # (5) نعرض كلام المؤلف كما هو، لا حكمًا مختصرًا مستخرجًا آليًا
            for rl in m["rulings"][:3]:
                quote = (rl.get("quote") or rl.get("ruling", "")).lstrip(". ")
                print(f"   قال {rl.get('scholar','')} في {rl.get('book','')}: «{quote[:200]}…»")
                if rl.get("quote_truncated"):
                    print("   (النص مقتطع — انظري المصدر)")
                if rl.get("quote_note"):
                    print(f"   ({rl['quote_note']})")
                if rl.get("url") and rl["url"] != "https://shamela.ws":
                    print(f"   المصدر: {rl['url']}")
            if m["note"]:
                print("  " + m["note"])