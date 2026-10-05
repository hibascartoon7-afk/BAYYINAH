import json, re, collections, copy
H=json.load(open('data/raw/hadith_database.json',encoding='utf-8'))
R=json.load(open('data/raw/rulings_database.json',encoding='utf-8'))
Dg=re.compile(r'[ً-ْٰ]'); nd=lambda t:Dg.sub('',t)
H_ = r'[ً-ْٰ]*'
def loose(w): return H_.join(re.escape(c) for c in w)+H_
ISN = r'(?:حدثن|أخبرن|اخبرن)'
log = collections.defaultdict(list)   # sheet -> rows

# ---------------- الصحيحان ----------------
outH=[]
for h in H:
    h=copy.deepcopy(h); t=h['text']; n=nd(t); flags=[]
    # 1) عنوان باب/كتاب أو بيانات ناشر بلا حديث → حذف
    if h['id']==7027 or re.search(r'المحقق\s*:|الناشر\s*:', n[:300]):
        log['H_del'].append([h['id'],h['book'],h['number'],'بيانات الكتاب والناشر، ليست حديثًا',t[:300]]); continue
    if re.match(r'\s*\(?\s*(?:باب|كتاب)',n):
        m=re.search(ISN+r'|«|عن النبي|قال رسول',n)
        if not m:
            log['H_del'].append([h['id'],h['book'],h['number'],'عنوان باب/كتاب فقط، لا حديث فيه',t[:300]]); continue
        # عنوان في أوله ثم حديث → نقص العنوان
        # نحدد الموضع في النص الأصلي المشكول بعدّ الحروف غير الحركات
        k=0; pos=0
        for i,ch in enumerate(t):
            if not Dg.match(ch):
                if k==m.start(): pos=i; break
                k+=1
        cut=t[:pos]; t=t[pos:]
        log['H_edit'].append([h['id'],h['book'],h['number'],'حُذف عنوان الباب من أول النص',cut.strip()[:200],t[:150]])
    # 1ب) بيانات الطبعة ملتصقة بنص الحديث (تظهر في بدايات المجلدات)
    pm_=re.search(r'\((?:البخاري|مسلم)\)\s*القسم\s*:', nd(t))
    if pm_:
        k=0; pos=None
        for i,ch in enumerate(t):
            if not Dg.match(ch):
                if k==pm_.start(): pos=i; break
                k+=1
        if pos is not None:
            rest=nd(t[pos:]); after_pub=re.search(r'(?:الهوامش|الأحاديث)[^.]{0,80}?\)?\s*'+ISN, rest)
            log['H_edit'].append([h['id'],h['book'],h['number'],'حُذفت بيانات الطبعة الملتصقة بالنص',t[pos:pos+200],t[:pos][-120:]])
            if re.search(ISN, rest[200:]):
                flags.append('بعد بيانات الطبعة نص آخر ملتصق')
            t=t[:pos].rstrip()
    # 2) أرقام زائدة في أول النص مثل «0412)» أو «م - (2121)» أو «5711 -»
    m=re.match(r'\s*(?:م\s*-\s*)?\(?\s*\d+\s*[)\-]\s*',t)
    if m:
        log['H_edit'].append([h['id'],h['book'],h['number'],'حُذف رقم زائد من أول النص',m.group(0).strip(),t[m.end():m.end()+120]])
        t=t[m.end():]
    # 3) عنوان الباب التالي ملتصق في آخر النص → نقصه إن لم يأتِ بعده إسناد
    m=re.search(r'([.»"!؟])\s*(?:[\*\-–]\s*)?('+loose('باب')+r'|'+loose('كتاب')+r')(?=[\s:])', t)
    if m:
        after=nd(t[m.end():])
        if re.search(ISN,after):
            flags.append('النص يضم أكثر من حديث (عنوان باب ثم إسناد جديد)')
        else:
            cut=t[m.start()+1:].strip(); t=t[:m.start()+1]
            log['H_edit'].append([h['id'],h['book'],h['number'],'حُذف عنوان الباب التالي من آخر النص',cut[:200],t[-120:]])
    # 3ب) كلمة «باب» وحدها في آخر النص بعد نهاية جملة (بقية عنوان)
    m2=re.search(r'(?<=[.»"])\s*(?:'+loose('باب')+r')\s*:?\s*$', t)
    if m2:
        log['H_edit'].append([h['id'],h['book'],h['number'],'حُذفت كلمة «باب» المتبقية في آخر النص',t[m2.start():].strip(),t[:m2.start()][-120:]])
        t=t[:m2.start()].rstrip()
    # 3ج) إحالات المحقق إلى الآيات مثل [81/التكوير/ الآية-17]
    refs=re.findall(r'\s*\[\s*\d+\s*/[^\]]{1,30}/[^\]]{0,20}\]', t)
    if refs:
        log['H_edit'].append([h['id'],h['book'],h['number'],'حُذفت إحالات المحقق إلى أرقام الآيات',' '.join(r.strip() for r in refs)[:200],''])
        t=re.sub(r'\s*\[\s*\d+\s*/[^\]]{1,30}/[^\]]{0,20}\]','',t)
    n=nd(t)
    # 4) علامات تحفّظ (لا تُحذف، تُعرض «نص الرواية كما في الكتاب»)
    if len(h['text'])>=4000: flags.append('النص مقطوع في الملف الأصلي (4000 حرف)')
    if re.search(r'قال العلماء|قال النووي|قال القاضي|قال الخطابي|قال أهل اللغة|قال ابن الصلاح|قال أبو عمرو|\[ش',n) or \
       re.search(r'\([^)]{1,40}\)\s+(?:\S+\s+)?(?:أي|هي|هو|يعني|معناه|يقال|روي|المراد|هكذا|ضبط|ضبطوا|اختلف|بكسر|بفتح|بضم|الصحيح|الأصح|في معناها?|هذا|قال|معنى|فيه)\s',n) or \
       re.search(r'المحققون|المحققين|نسخ بلادنا|في بعض الأصول|في بعض النسخ|قال أهل اللغة|محققوا',n):
        flags.append('يتضمن شرحًا أو تعليقًا من المحقق/الشارح')
    pm=re.search(r'رسول الله|النبي|«', n)
    if pm and (re.search(r'(?:^|[.»"؟]\s*)(?:ح\s*)?و?'+ISN, n[pm.end():]) or re.search(r'بمثله|بمثل حديث|بهذا الإسناد|بهذا الاسناد|بنحوه|نحو حديث', n)):
        flags.append('بعد نص الحديث روايات أو أسانيد أخرى')
    if re.search(r'(?<![\d/])\d{2,5}\s*(?:\((?:م|خ|ت|د|س|ق)\))?\s*-\s', n):
        flags.append('النص يضم أكثر من حديث (أرقام أحاديث داخل النص)')
    if re.search(r'في المفردات|بمعنى|قال الأزهري|قال المازري|وفي هذا الحديث|هذا الحديث مما|فيه دليل|فيه جواز', n) and h['book'].startswith('صحيح مسلم'):
        if 'يتضمن شرحًا أو تعليقًا من المحقق/الشارح' not in flags: flags.append('يتضمن شرحًا أو تعليقًا من المحقق/الشارح')
    if re.search(r'م\s*\d+\s*-\s*\(\d+\)', n):
        flags.append('النص يضم أكثر من حديث (أرقام أحاديث داخل النص)')
    if re.search(r'\(\d{2,5}\)\s*-', n) and 'النص يضم أكثر من حديث (أرقام أحاديث داخل النص)' not in flags:
        flags.append('النص يضم أكثر من حديث (أرقام أحاديث داخل النص)')
    GL=r'\((?!\d+\))(?!واللفظ|يعني|وهو |وهي |قال |وقال |قالا)[^)]{1,60}\)\s+[^\s(]'
    if h['book'].startswith('صحيح مسلم') and (re.search(r'"\.?\s*'+GL, n) or re.search(r'[.!؟]\s*'+GL, n)):
        if 'يتضمن شرحًا أو تعليقًا من المحقق/الشارح' not in flags: flags.append('يتضمن شرحًا أو تعليقًا من المحقق/الشارح')
    if '؟؟' in n:
        flags.append('في النص علامات شك في القراءة من المُدخِل')
    if re.search(r'[،:]\s*$', n.strip()):
        flags.append('النص ينتهي قبل تمامه')
    if re.search(r'\s(?:باب|بابٌ)\s+[^«»".،!؟]{3,120}$', n) and not re.search(r'باب\s+(?:الجنة|المسجد|النار|أبي بكر|السماء|البيت|الحجرة|عائشة)', n[-140:]):
        flags.append('في آخر النص عنوان باب ملتصق')
    if len(n.strip())<60 and not re.search(ISN+r'|عن |«', n):
        flags.append('نص ناقص (جزء من حديث سابق)')
    h['text']=t
    if flags:
        h['quality_flags']=flags
        log['H_flag'].append([h['id'],h['book'],h['number'],' | '.join(flags),t[:200]])
    outH.append(h)

# أرقام مسلم الشاذة: رقم بعيد عن جاريه
M=[h for h in outH if h['book'].startswith('صحيح مسلم')]
for a,b,c in zip(M,M[1:],M[2:]):
    x,y,z=int(a['number']),int(b['number']),int(c['number'])
    if abs(y-x)>5 and abs(z-y)>5:
        b['number_suspect']=True
        log['H_num'].append([b['id'],y,f'قبله {x} وبعده {z}',b['text'][:120]])

# أرقام البخاري المفقودة
nums={int(h['number']) for h in outH if h['book']=='صحيح البخاري'}
for n_ in range(1,7564):
    if n_ not in nums: log['H_missing'].append([n_])

# ---------------- الأحكام ----------------
outR=[]
for h in R:
    h=copy.deepcopy(h); r=h['rulings'][0]; q=(r.get('quote') or '').strip()
    if q.startswith('…'):
        log['R_del'].append([h['id'],h['book'],h['number'],h['text'],'الشرح يبدأ من منتصف كلام المؤلف ولا يطابق هذا النص',r['ruling'],q[:300]]); continue
    if len(q)<=3:
        log['R_del'].append([h['id'],h['book'],h['number'],h['text'],'لا يوجد كلام منقول للمؤلف',r['ruling'],q]); continue
    if re.match(r'\s*\d+\s*\)', h['text']):
        log['R_del'].append([h['id'],h['book'],h['number'],h['text'],'حاشية من المحقق التُقطت كأنها مدخل',r['ruling'],q[:300]]); continue
    qq=nd(q).strip()
    if (len(qq.split())<=2 and not re.search(r'[.!؟»"]\s*$', qq)) or qq.strip(' .')=='والله أعلم':
        log['R_del'].append([h['id'],h['book'],h['number'],h['text'],'كلام المؤلف ناقص لا يفيد شيئًا',r['ruling'],q]); continue
    if re.match(r'\s*(?:ولذا|ولهذا|ولذلك|وهذا|وهو|وهي|فهو|فهذا|لكن|ولكن|انتهى|أي\s|بل\s|ثم\s|وقد\s|وأما|فإن|فقد|وكذا|وكذلك|إلا\s|حتى|وإن|والله|ويؤيده|ويشهد|وعلى|ومنه|وقوله|ومعناه|يعني)', nd(q)):
        log['R_suspect'].append([h['id'],h['book'],h['text'],q[:250]])
    if re.search(r'\(\d+\)', q):
        r['quote_note']='في كلام المؤلف إحالات إلى حواشي المحقق'
    if r['ruling']!='انظر كلام المؤلف':
        log['R_label'].append([h['id'],h['book'],h['text'],r['scholar'],r['ruling'],q[:400],''])
    r['ruling']=''                      # لا حكم مختصر آلي؛ يُعرض كلام المؤلف فقط
    if len(r.get('quote',''))>=600 or not re.search(r'[.»"!؟)\]]\s*$', r.get('quote','').strip()): r['quote_truncated']=True
    outR.append(h)
g=collections.defaultdict(list)
for h in outR: g[(h['book'],nd(h['text']).strip())].append(h)
for k,v in g.items():
    if len(v)>1:
        for h in v: log['R_dup'].append([h['id'],h['book'],h['number'],h['text'],h['rulings'][0]['quote'][:200]])

json.dump(outH,open('data/hadith_database.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
json.dump(outR,open('data/rulings_database.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
json.dump({k:v for k,v in log.items()},open('data/log.json','w',encoding='utf-8'),ensure_ascii=False)
print("الصحيحان:",len(H),"→",len(outH)); print("الأحكام:",len(R),"→",len(outR))
for k,v in log.items(): print(k,len(v))
fc=collections.Counter(f for h in outH for f in h.get('quality_flags',[])); print(fc)
