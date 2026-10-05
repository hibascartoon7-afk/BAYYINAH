# -*- coding: utf-8 -*-
"""توحيد النص العربي قبل البحث والمقارنة في «بيّنة».
أي تعديل هنا يتطلب: python engine.py --rebuild
"""
import re

_TASHKEEL = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_TATWEEL = "\u0640"
_PUNCT = re.compile(r"[^\w\s]|_", re.UNICODE)
_SPACES = re.compile(r"\s+")
_SALAWAT = re.compile(r"ﷺ|صلى الله عليه وسلم|صلى الله عليه و سلم|صلي الله عليه وسلم")


def normalize(text: str) -> str:
    if not text:
        return ""
    t = str(text)
    t = _TASHKEEL.sub("", t)
    t = t.replace(_TATWEEL, "")
    t = _SALAWAT.sub(" صلى الله عليه وسلم ", t)
    t = _TASHKEEL.sub("", t)
    t = re.sub("[إأآٱ]", "ا", t)
    t = t.replace("ى", "ي")
    t = t.replace("ة", "ه")
    t = t.replace("ؤ", "و").replace("ئ", "ي")
    t = _PUNCT.sub(" ", t)
    return _SPACES.sub(" ", t).strip()