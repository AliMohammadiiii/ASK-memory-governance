# گزارش جامع ارزیابی مقاله، مسیر انتشار، برنامه اصلاح و ممیزی نوآوری

**مقاله:** *Beyond Recall: A Layered Diagnostic for Write-Time Memory Governance in Language Agents*
**نسخه بررسی‌شده:** PDF چهل‌وسه‌صفحه‌ای به‌همراه منبع LaTeX، فایل منابع، ماتریس ادعا-شواهد، ممیزی سهم علمی و پاسخ شبیه‌سازی‌شده به داوران
**تاریخ ارزیابی:** ۲۸ ژوئیه ۲۰۲۶

---

## ۱. جمع‌بندی مدیریتی

این مقاله در وضعیت فعلی **یک پیش‌نویس پایان‌نامه‌ای قوی، صادقانه و از نظر مهندسی پژوهش بسیار جدی** است؛ اما هنوز نسخه‌ای نیست که بتوان با اطمینان به یک ژورنال Q1 سخت‌گیر یا Main Track یک کنفرانس سطح‌بالا فرستاد. مشکل اصلی کمبود متن، فرمول یا آزمایش نیست. مشکل اصلی این است که قدرت صورت‌بندی نظری و ممیزی مقاله از قدرت شواهد بیرونی آن جلوتر است.

ارزش اصلی کار این نیست که سه عمل `KEEP/SUPERSEDE/ABSTAIN` را اختراع کرده، یا اولین مقاله درباره update، supersession، lineage، abstention یا memory governance است؛ این ادعاها با ادبیات ۲۰۲۵–۲۰۲۶ قابل دفاع نیستند. ارزش متمایز و قابل دفاع مقاله عبارت است از:

> تبدیل «گذار نوشتن در حافظه» به واحد مستقل ارزیابی و ارائه یک قرارداد ارزیابی قابل‌بازپخش که تصمیم نوشتن، وضعیت پس از نوشتن، lineage/recoverability، بازیابی stale و اثر downstream را از یکدیگر جدا می‌کند و خطاها را بر اساس آسیب عملیاتی نامتقارن می‌سنجد.

این صورت‌بندی، در صورت اصلاح ادعاها و تقویت اعتبار تجربی، برای TMLR، AAMAS 2027–GAAI، NeurIPS Evaluations & Datasets و تا حدی TACL بسیار مناسب است.

### امتیاز وضعیت فعلی

| محور | امتیاز فعلی از ۱۰ | توضیح |
|---|---:|---|
| اهمیت مسئله | ۸.۵ | خطای write می‌تواند به state corruption پایدار تبدیل شود و فقط با QA نهایی دیده نشود. |
| قدرت framing | ۹.۰ | انتقال تمرکز از recall به state transition بسیار خوب و به‌یادماندنی است. |
| نوآوری قابل‌دفاع | ۶.۵ | ترکیب و قرارداد ارزیابی نو است؛ بسیاری از اجزای منفرد دیگر نو نیستند. |
| روش‌شناسی | ۷.۵ | طراحی لایه‌ای، replay، bootstrap و audit قوی است؛ ولی کنترلرها و شواهد به‌طور کامل یکپارچه نیستند. |
| اعتبار سازه | ۵.۵ | synthetic، owner-designed و owner-attested بودن annotation مهم‌ترین ضعف است. |
| اعتبار بیرونی | ۴.۵ | یک slice، یک answer model، یک judge، یک seed و فقدان gold write labels طبیعی. |
| بازتولیدپذیری طراحی | ۸.۰ | trace، manifest، per-item predictions و exact replay نقطه قوت جدی‌اند. |
| آمادگی artifact عمومی | ۵.۰ | نبود license عمومی و باقی‌بودن بخشی از gold/annotation در مرز خصوصی مانع است. |
| گستره تجربی | ۵.۵ | در برابر مقالات برتر جدید، تعداد benchmark/model/baseline کافی نیست. |
| ارائه و نگارش | ۷.۵ | دقیق و منظم، ولی ۴۳ صفحه، چند روایت هم‌زمان و تعداد زیاد جزئیات audit، پیام مرکزی را پنهان می‌کند. |
| آمادگی پایان‌نامه | ۸.۵ | با اصلاح ادعاها و ساختار، برای نسخه اولیه پایان‌نامه بسیار نزدیک است. |
| آمادگی ارسال سطح‌بالا | ۵.۵ | قبل از ارسال باید چند blocker واقعی برطرف شود. |

**حکم نهایی:** مقاله را نباید صرفاً «ویرایش زبانی» کرد. باید آن را از یک گزارش جامع پژوهش به یک paper با یک سؤال اصلی، یک contribution hierarchy و یک زنجیره شواهد یکپارچه تبدیل کرد.

---

## ۲. مقاله دقیقاً چه چیزی ارائه می‌کند؟

### ۲.۱ هسته نظری و سیستمی

مقاله سه عمل را بر روی یک حافظه typed و provenance-tracked تعریف می‌کند:

- `KEEP`: رکورد جاری invalidate نمی‌شود و در runtime ممکن است یک رکورد سازگار نیز افزوده شود.
- `SUPERSEDE`: رکورد پیشین حذف نمی‌شود؛ وضعیت آن تغییر کرده و pointer/lineage به جانشین حفظ می‌شود.
- `ABSTAIN`: در نبود شواهد کافی، state مدل‌شده باید byte-for-byte ثابت بماند و خود abstention قابل ممیزی باشد.

نکته مهم این است که مقاله `ABSTAIN` را از `NOOP`، `KEEP` را از «عدم بازیابی»، و supersession را از deletion جدا می‌کند. این تفکیک مفهومی ارزشمند است.

### ۲.۲ ابزارهای تجربی

مقاله سه خط شواهد را کنار هم قرار می‌دهد:

1. **MGP-6 v2:** پایلوت ۱۸۰تایی که نشان می‌دهد conflict type به‌تنهایی می‌تواند action را با دقت ۱.۰۰ پیش‌بینی کند؛ بنابراین split آیتمی ظاهراً تمیز می‌تواند construct failure داشته باشد.
2. **MGP-6 v4.3:** diagnostic synthetic کنترل‌شده با ۹۰۰ آیتم، ۱۰۰ semantic component، ۲۰ domain و hidden split برابر ۵۴۰؛ نتیجه hidden کنترلر frozen برابر ۰.۸۴۸۱ accuracy و ۰.۸۴۷۹ macro-F1 است.
3. **LongMemEval-M / V12:** یک slice همگن ۱۸۰تایی که governed writes را در ۷۶.۱٪ در برابر ۶۳.۳٪ naive overwrite قرار می‌دهد.

### ۲.۳ ممیزی مکانیزم

کنترلر LongMemEval از پنج ویژگی ثبت‌شده استفاده می‌کند:

- extraction confidence؛
- evidence quality؛
- marker burden یا negation/hedge burden؛
- signed candidate–prior relation؛
- memory-type stability prior.

Exact replay هر ۱۲٬۶۵۴ write decision را بازتولید می‌کند. ولی leave-one-feature-out نشان می‌دهد evidence quality و stability prior در آن run هیچ actionی را تغییر نداده‌اند، و تقریباً تمام رفتار واقعی توسط marker burden، relation و relation guard حمل می‌شود. این نتیجه باید نه پنهان، بلکه به‌عنوان یک یافته صادقانه و مهم بازصورت‌بندی شود.

---

## ۳. مسئله ساختاری مهم: مقاله در حال حاضر سه کنترلر دارد

در متن فعلی سه مکانیزم متفاوت با interface مشترک وجود دارد:

1. scorecard پنج‌بعدیِ runtime در LongMemEval؛
2. lexical reference policy تاریخی در MGP-6 v2؛
3. composed model + rule controller در MGP-6 v4.3.

این سه کنترلر قابل‌جایگزینی نیستند. scorecard پنج‌بعدی منبع headline hidden نتیجه MGP-6 نیست و حتی adapter آن روی development v4.3 در حد chance گزارش شده است. این وضعیت برای داور این سؤال را ایجاد می‌کند:

> آیا مقاله یک benchmark/evaluation paper است، یک controller paper است، یا دو مقاله به‌هم دوخته‌شده است؟

### تصمیم پیشنهادی

مسیر قوی‌تر، **evaluation-first** است:

- contribution اصلی = evaluation contract + MGP-6 diagnostic؛
- کنترلرها = case studyهایی برای نشان دادن نحوه استفاده از قرارداد؛
- scorecard = auditable deployed policy، نه الگوریتم جدید؛
- LongMemEval = downstream validation محدود، نه اثبات تعمیم عمومی.

مسیر method-first فقط وقتی توصیه می‌شود که یک policy واحد، learned یا formally constrained، روی چند benchmark و چند model ارزیابی شود.

---

## ۴. اولویت‌بندی محل‌های انتشار

### ۴.۱ نکته مهم درباره Q1 و «سطح یک»

`Q1` ویژگی ژورنال در یک پایگاه، سال و category مشخص است. کنفرانس‌ها Q1 نیستند و معمولاً با رتبه‌هایی مانند CORE/CCF یا فهرست داخلی دانشگاه سنجیده می‌شوند. بنابراین دو مسیر باید جدا شوند:

- **مسیر بهترین تطابق علمی و دیده‌شدن پژوهشی؛**
- **مسیر الزام رسمی Q1 ژورنال.**

امتیازهای زیر احتمال پذیرش نیستند. آن‌ها ترکیبی از fit موضوعی، ارزش راهبردی، سازگاری با شواهد فعلی و امکان آماده‌سازی‌اند.

### ۴.۲ مسیر اول: بهترین تطابق علمی

| رتبه | مقصد | تطابق علمی | آمادگی فعلی | آمادگی پس از اصلاح | چرا مناسب است؟ | شرط اصلی پذیرش |
|---:|---|---:|---:|---:|---|---|
| ۱ | **TMLR** | ۹.۲ | ۶.۸ | ۸.۵ | formalization of new task، evaluation framework و diagnostic study دقیقاً در scope است؛ الزام به SOTA یا «novel enough» ندارد. | ادعاهای کاملاً پشتیبانی‌شده، artifact عمومی، اعتبار انسانی مستقل، روایت واحد و رفع تناقض license. |
| ۲ | **AAMAS 2027 – GAAI** | ۹.۱ | ۶.۳ | ۸.۱ | CFP صریحاً memory/state/context، long-lived interaction، failure recovery، debugging، safety و benchmarks را می‌خواهد. | تبدیل به paper هشت‌صفحه‌ای بسیار متمرکز، شواهد طبیعی و baselineهای قوی‌تر. |
| ۳ | **TACL** | ۸.۸ | ۵.۴ | ۷.۸ | memory agents، evaluation و NLP relevance مناسب است و مقاله ژورنالی می‌تواند در ACL-family ارائه شود. | فشرده‌سازی شدید به ده صفحه اصلی، natural gold، چند مدل/benchmark و state-of-the-art coverage. |
| ۴ | **NeurIPS 2027 Evaluations & Datasets** | ۸.۸ | ۴.۸ | ۸.۰ | evaluation را «موضوع علمی مستقل» می‌داند و audit/benchmark/negative result مناسب آن است. | dataset/code در submission قابل‌دسترسی، documentation، license، metadata و اعتبارسنجی بیرونی. |
| ۵ | **ACL/EMNLP 2027 via ARR** | ۸.۶ | ۵.۳ | ۷.۷ | در صورت برجسته‌کردن NLP/agent-memory و ارزیابی مستقیم با Memory-R1/HaluMem/STALE مناسب است. | novelty نسبت به موج ACL 2026، شواهد گسترده و paper هشت‌صفحه‌ای با یک پیام اصلی. |
| ۶ | **COLM 2027** | ۸.۴ | ۵.۸ | ۷.۶ | language-model systems و memory evaluation fit خوبی دارند. | تاریخ‌ها هنوز باید پس از اعلام رسمی بررسی شوند؛ broad empirical comparison لازم است. |
| ۷ | **AAAI-28** | ۸.۰ | ۵.۰ | ۷.۴ | AI systems/evaluation در scope است. | یک method یا formal contribution روشن‌تر و multi-benchmark evidence. |
| ۸ | **JAIR** | ۷.۸ | ۴.۷ | ۷.۲ | agents، reasoning، knowledge representation و evaluation را پوشش می‌دهد و طول ژورنالی مناسب است. | اهمیت برای AI community عمومی، novelty وسیع‌تر، grounding کامل در state of the art و reproducibility checklist. |

### نتیجه این مسیر

- **بهترین انتخاب rolling و علمی:** TMLR.
- **بهترین فرصت نزدیک و agent-centric:** AAMAS 2027–GAAI.
- **بالاترین ارزش NLP journal:** TACL، ولی با سخت‌ترین compression و evidence bar.
- **بهترین خانه برای نسخه benchmark-centricِ کامل:** NeurIPS 2027 E&D.

### ۴.۳ مسیر دوم: ژورنال Q1 ترجیحی

| رتبه | ژورنال | fit | آمادگی فعلی | توصیه |
|---:|---|---:|---:|---|
| ۱ | **ACM Transactions on Intelligent Systems and Technology (TIST)** | ۸.۳ | ۶.۲ | بهترین گزینه Q1 محافظه‌کارانه در صورت ارائه یک intelligent-system architecture و ارزیابی وسیع. وضعیت Q1 باید در پایگاه مورد قبول دانشگاه و سال ارسال نهایی تأیید شود. |
| ۲ | **TACL** | ۸.۸ | ۵.۴ | از نظر علمی بسیار مناسب، اما Q1 بودن آن به database/category مورد قبول دانشگاه وابسته است؛ بدون تأیید کتبی دانشگاه «strict Q1» فرض نشود. |
| ۳ | **Knowledge-Based Systems** | ۷.۵ | ۶.۴ | مسیر عملی‌تر و کم‌ریسک‌تر از TACL/JAIR؛ باید paper را از «benchmark report» به knowledge-based decision system تبدیل کرد. |
| ۴ | **JAIR** | ۷.۸ | ۴.۷ | اعتبار علمی بالا و بدون APC؛ اما summary rejection برای کار narrow، incremental یا ضعیف در state of the art جدی است. |
| ۵ | **Artificial Intelligence Journal** | ۷.۳ | ۳.۸ | فقط پس از افزودن formal/general contribution قوی؛ نسخه فعلی برای AIJ بیش از حد domain-specific و synthetic است. |
| ۶ | **IEEE Transactions on Artificial Intelligence** | ۷.۵ | ۵.۵ | backup مناسب پس از بررسی دقیق رتبه جاری و scope در زمان ارسال. |
| ۷ | **Information Sciences / Engineering Applications of AI** | ۶.۸ | ۶.۰ | backup Q1؛ fit کمتر از گزینه‌های بالا و نیازمند emphasis روی system utility و روش الگوریتمی. |

### توصیه قطعی برای الزام Q1

اگر دانشگاه صریحاً «یک مقاله Q1 ژورنالی» می‌خواهد، پیشنهاد مسیر زیر است:

1. ابتدا وضعیت Q1 قابل‌قبول دانشگاه را برای TIST، KBS، TACL و JAIR از پایگاه رسمی همان دانشگاه تأیید کنید؛
2. نسخه را به شکل **evaluation-first intelligent system** بازنویسی کنید؛
3. P0 experimentها را کامل کنید؛
4. اولویت ارسال: **TIST → KBS** یا در صورت شواهد بسیار قوی‌تر **TACL**.

ارسال archival به AAMAS می‌تواند امکان ارسال همان کار به TMLR را از بین ببرد، زیرا TMLR expanded conference paper نمی‌پذیرد. JAIR برعکس، نسخه ژورنالی substantially extended از مقاله کنفرانسی را می‌پذیرد. این انتخاب باید قبل از اولین submission قطعی شود.

---

## ۵. شرایط و الگوی واقعی انتخاب در مقصدهای اصلی

### ۵.۱ TMLR

TMLR دو سؤال مرکزی دارد:

1. آیا ادعاها با شواهد دقیق، روشن و متقاعدکننده پشتیبانی شده‌اند؟
2. آیا حداقل بخشی از مخاطبان TMLR از یافته‌های مقاله چیزی یاد می‌گیرند؟

این ژورنال صرفاً به دلیل نداشتن SOTA یا «novel enough» بودن کار را رد نمی‌کند، ولی bold claim بدون evidence، novelty claim غلط و نگارش نامشخص را رد می‌کند. review عمومی، double-blind و تعاملی است؛ بنابراین ضعف provenance یا annotation بعداً پنهان نمی‌ماند.

**نمونه‌های پذیرفته‌شده بررسی‌شده:**

- CRMArena-Pro: نوزده task expert-validated، تعامل multi-turn، confidentiality و realism سازمانی؛
- LongICLBench: شش dataset و پانزده model؛
- CompWoB: پنجاه task ترکیبی و تحلیل generalization؛
- CORE-Bench: benchmark متصل به یک وظیفه واقعی و با artifact بازتولیدپذیر.

**الگوی انتخاب:** شکاف واحد، ارزیابی گسترده، artifact عمومی، human/expert validation، تحلیل failure و lesson قابل تعمیم.

### ۵.۲ AAMAS 2027–GAAI

موضوعات GAAI تقریباً مستقیم با مقاله هم‌پوشانی دارند: memory/state/context، long-lived interaction، runtime infrastructure، failure handling، debugging، assurance، safety، benchmarks و metrics. معیارهای رسمی شامل originality، significance، soundness، reproducibility، clarity، relevance، presentation و پوشش state of the art است.

**آنچه داور AAMAS می‌خواهد ببیند:**

- مسئله واقعاً agent-specific باشد، نه یک classifier عمومی روی متن؛
- contribution در رفتار/معماری/ارزیابی agent روشن باشد؛
- failure و recovery در trajectory نشان داده شود؛
- paper در هشت صفحه یک داستان واحد داشته باشد؛
- artifact و reproducibility عملی باشد.

### ۵.۳ TACL و ACL-family

TACL کار substantial، original، completed و NLP-relevant می‌خواهد. صفحه اصلی محدود است و appendix الزاماً مبنای داوری نیست. کارهای پذیرفته‌شده ACL 2026 در همین حوزه معمولاً یکی یا چند مورد زیر را دارند:

- چند benchmark و چند model scale؛
- یک learned mechanism یا معماری مشخص؛
- داده عمومی و human validation؛
- مقایسه مستقیم با frameworkهای حافظه؛
- downstream utility ملموس.

نمونه‌ها:

- Memory-R1: سه benchmark، مدل‌های 3B تا 14B و policy learned برای ADD/UPDATE/DELETE/NOOP؛
- Inside Out: PersonaTree و MemListener آموزش‌دیده با RL؛
- Mem2ActBench: ۲۰۲۹ session، چهارصد task، هفت memory framework و human validation؛
- Hindsight: structured fact/belief/provenance/temporal graph و ارزیابی روی LongMemEval و LoCoMo.

**نتیجه برای مقاله شما:** framing و audit شما قوی‌تر از بسیاری از کارهاست، ولی breadth تجربی فعلی کمتر است.

### ۵.۴ NeurIPS Evaluations & Datasets

این track evaluation را نه یک مرحله فرعی، بلکه موضوع علمی مستقل می‌داند. paper باید توضیح دهد contribution دقیقاً چه ادعاهایی را، تحت چه فرض‌هایی، قابل ارزیابی می‌کند. dataset و code باید هنگام submission میزبانی، قابل‌دسترسی و مستند باشند؛ برای dataset submission، Croissant و Responsible-AI metadata نیز اهمیت دارد.

**مانع فعلی مستقیم:** جمله «We release» با «No public redistribution license has been selected» ناسازگار است.

### ۵.۵ JAIR

JAIR از نویسنده می‌خواهد روشن کند:

- چرا نتیجه برای جامعه AI مهم است و دیگران چگونه از آن استفاده می‌کنند؛
- یک تا سه paper نزدیک در JAIR چیست و تفاوت دقیق کجاست؛
- چه بخشی قبلاً منتشر شده است.

کار narrow، صرفاً application، کم‌اهمیت برای AI community عمومی، یا ضعیف در recent references احتمال summary rejection بالایی دارد. برای مقاله فعلی، اضافه‌کردن formal contract یا general theory و evidence گسترده لازم است.

---

## ۶. مقایسه دقیق با کارهای مشابه و مرز Novelty

### ۶.۱ نزدیک‌ترین کارها

| کار | contribution اصلی | هم‌پوشانی با مقاله شما | چیزی که هنوز می‌تواند متعلق به شما باشد |
|---|---|---|---|
| **HaluMem** | operation-level extraction/update/QA و hallucination benchmark | ادعای «اولین ارزیابی operation-level» را از بین می‌برد. | state-transition contract، lineage invariant، harm-aware decomposition و exact runtime replay. |
| **STALE** | implicit conflict، stale-state recognition و policy adaptation | تشخیص stale و update reasoning دیگر gap خالی نیست. | تفکیک write action از post-state و سنجش خطای destructive در لحظه commit. |
| **Supersede** | اندازه‌گیری و آموزش gap مربوط به supersession روی داده واقعی | supersession و LongMemEval update gap مستقیماً پوشش داده شده است. | سه‌راهی KEEP/SUPERSEDE/ABSTAIN، lineage preservation و evaluation contract چندلایه. |
| **TOKI** | bitemporal operator algebra، provenance، await-confirmation و soundness theorem | write-time correctness، audit trail و abstain-like operator را بسیار نزدیک می‌کند. | empirical diagnostic contract و error localization؛ فقط در صورت مقایسه مستقیم و مرزبندی روشن. |
| **Memory-R1** | learned ADD/UPDATE/DELETE/NOOP policy روی سه benchmark | discrete write action space و learned manager نو نیست. | uncertainty-driven abstention، state/lineage scoring و operational harm. |
| **Inside Out** | executable ADD/UPDATE/DELETE/NO_OP و RL-trained memory listener | structured operations و interpretable manager پوشش داده شده است. | replayable governance evaluation مستقل از یک معماری PersonaTree. |
| **TrustMem** | Memory Transition Verifier برای coverage/preservation/faithfulness | transition-level corruption و verifier به هسته شما نزدیک است. | صریح‌کردن action/state/lineage/retrieval/downstream layers و asymmetric cost. |
| **GateMem** | governance در shared memory: utility، access control و forgetting | واژه memory governance دیگر قابل انحصار نیست. | epistemic write correctness در single-principal setting؛ نه privacy/access governance. |
| **Hindsight** | fact/belief separation، provenance، temporal graph و production evidence | provenance و temporal update تنها نیستند. | benchmark contract، audit of decision mechanism و harm taxonomy. |
| **Mem2ActBench** | سنجش استفاده فعال از حافظه در tool execution | downstream utility از recall فراتر رفته است. | تمرکز شما بر write correctness قبل از retrieval/action است. |
| **Always-On Agents/AOEP** | lifecycle و invariants برای persistent agents | language مربوط به governance/invariants crowded شده است. | پیاده‌سازی دقیق و قابل‌بازپخش یک بخش مشخص از lifecycle. |
| **WorldMemArena** | write/maintain/retrieve/use در tasks multimodal | lifecycle-level evaluation به چهار مرحله توسعه یافته است. | deterministic post-state and lineage contract با labels دقیق؛ به شرط comparison. |

### ۶.۲ چیزهایی که نباید به‌عنوان Novelty ادعا شوند

- ابداع `ADD/UPDATE/DELETE/NOOP` یا write actions؛
- ابداع abstention یا reject option؛
- typed memory؛
- provenance و lineage؛
- stale-memory detection؛
- operation-level evaluation به‌طور کلی؛
- memory governance به‌طور کلی؛
- supersession benchmark یا knowledge-update benchmark؛
- نگه‌داشتن history به‌جای deletion؛
- این ادعا که LongMemEval فقط recall را می‌سنجد، بدون acknowledgment کارهای جدید update-focused.

### ۶.۳ Novelty قابل‌دفاع

Novelty شما **یک conjunction اجرایی** است، نه یک جزء منفرد:

1. **واحد ارزیابی:** گذار نوشتن به‌همراه post-state deterministic، نه فقط answer یا operation label؛
2. **تفکیک لایه‌ها:** action، state invariant، lineage/recoverability، stale retrieval و downstream answer جداگانه observable هستند؛
3. **طبقه‌بندی آسیب:** خطای missed abstention که state را حفظ می‌کند از false supersession که state را خراب می‌کند جدا می‌شود؛
4. **ممیزی مکانیزم:** exact replay و counterfactual dimension/guard omission نشان می‌دهد runtime واقعاً از چه ویژگی‌هایی استفاده کرده است؛
5. **ممیزی خود benchmark:** شکست v2 به‌عنوان یافته منفی حفظ شده و به release gate نسخه بعدی تبدیل شده است؛
6. **دو سطح شواهد:** controlled diagnostic با write labels در کنار downstream naturalistic evidence با محدودیت‌های صریح.

### ۶.۴ Gap دقیق پیشنهادی

صورت‌بندی پیشنهادی gap:

> Existing memory evaluations increasingly test extraction, updating, stale-state recognition, or downstream task success, but they generally do not provide a single replayable contract that separates the chosen write action from the deterministic post-write state, lineage preservation, later retrieval behavior, and downstream answer consequences. Consequently, two systems can obtain similar operation or QA scores while differing sharply in whether an error merely misses an audit event or irreversibly corrupts active state.

این gap باید با جدول comparison صریح و feature-by-feature اثبات شود، نه صرفاً با متن related work.

### ۶.۵ Claim اصلی پیشنهادی

> End-to-end memory QA cannot identify unsafe write failures. We introduce a layer-separated, replayable evaluation contract for write-time memory transitions and show, under explicitly bounded controlled and downstream settings, that it distinguishes state-preserving uncertainty errors from destructive updates that aggregate accuracy conceals.

### ۶.۶ سه contribution نهایی پیشنهادی

1. Formal write-transition contract with deterministic state and lineage invariants؛
2. MGP-6 controlled diagnostic with executable construct-validity and shortcut gates؛
3. Cross-layer runtime audit connecting evidence features, write decisions, state harms and downstream behavior.

بیش از سه contribution در Introduction نیاورید.

---

## ۷. ایرادهای محتمل داور و پاسخ واقعی لازم

| ایراد داور | چرا وارد است؟ | اقدام لازم |
|---|---|---|
| «داده و gold توسط همان پروژه طراحی شده‌اند.» | synthetic، author-designed و reviewer identity owner-attested است. | annotation مستقل، blinded و مستند؛ natural subset مستقل. |
| «دو human packet با agreement کامل construct validity نیست.» | دستورالعمل deterministic می‌تواند agreement مصنوعی ایجاد کند. | گزارش alpha/kappa، disagreement، adjudication و validation of wording. |
| «فقط یک سیستم روی hidden ارزیابی شده.» | baselineها و ablationها روی dev انتخابی‌اند. | hidden جدید یا evaluation server با pre-authorised systems. |
| «کنترلر پنج‌بعدی عملاً دو feature + guard است.» | e و rho هیچ actionی را تغییر نداده‌اند. | نام‌گذاری صادقانه یا policy learned/calibrated که همه dimensionها را واقعاً exercise کند. |
| «MGP-6 و LongMemEval از یک policy استفاده نمی‌کنند.» | دو headline از مکانیزم‌های متفاوت می‌آیند. | policy واحد یا evaluation-first framing روشن. |
| «LongMemEval فقط یک slice/model/judge دارد.» | external validity محدود است. | full/relevant subsets، سه یا بیشتر model، دو judge و human audit. |
| «نوآوری با TOKI/TrustMem/HaluMem/STALE overlap دارد.» | ادبیات ۲۰۲۶ بسیار نزدیک شده است. | direct comparison و claim محدود به executable conjunction. |
| «We release ولی license ندارید.» | تناقض حقوقی/علمی مستقیم است. | انتخاب license و data card قبل از submission. |
| «pre-registered اغراق‌آمیز است.» | اگر فقط manifest داخلی بوده، registration عمومی نیست. | عبارت `pre-specified and cryptographically frozen before hidden scoring`. |
| «dual human annotation قابل اثبات نیست.» | هویت/استقلال owner-attested است. | عبارت دقیق‌تر و evidence قابل‌ممیزی. |
| «selective accuracy از overall کمتر است.» | abstention calibrated نیست. | risk–coverage calibration، selective baselines و claim محدود. |
| «۴۳ صفحه داستان را پنهان کرده.» | audit history بر main claim غلبه کرده است. | v2 history و bookkeeping به appendix/artifact منتقل شود. |

---

## ۸. اصلاح فوری wording و claim hygiene

### مواردی که باید تغییر کنند

| متن/مفهوم فعلی | نسخه پیشنهادی |
|---|---|
| `900 human-authored ... dual human annotation covering every item` | `900 project-authored, controlled synthetic items with two independently completed, owner-attested annotation packets` تا زمانی که evidence مستقل وجود ندارد. |
| `one pre-registered configuration` | `one configuration pre-specified and cryptographically frozen before hidden scoring` مگر registration عمومی timestamped ارائه شود. |
| `We release ...` در حالی که license نیست | `We prepare and audit ...` تا زمان انتخاب license؛ بعد از انتشار واقعی به `We release` برگردد. |
| `five-dimensional controller` به‌عنوان مکانیزم مؤثر پنج‌بعدی | `five logged dimensions with two decision-active channels and a discrete safety guard on the observed run`. |
| «novel memory governance» | `novel replayable evaluation contract for epistemic write governance`. |
| `first` در هر claim وسیع | حذف شود مگر systematic search و comparison table آن را اثبات کند. |

---

## ۹. برنامه عملیاتی رسیدن به نسخه اولیه پایان‌نامه

### بازه پیشنهادی: ۱۰ تا ۱۴ روز کاری

#### روز ۱–۲: Freeze ادعاها

خروجی‌ها:

- claim ledger نهایی با سه وضعیت `supported / bounded / unsupported`؛
- حذف همه priority claimهای غیرقابل دفاع؛
- تطبیق تمام عددهای abstract/introduction/conclusion با artifact؛
- تصمیم رسمی evaluation-first.

Gate خروج:

- هیچ claim در abstract قوی‌تر از limitations یا evidence matrix نباشد؛
- عبارت human/pre-registration/release متناقض نباشد.

#### روز ۳: بازنویسی Abstract و Introduction

ساختار abstract:

1. یک جمله مشکل؛
2. یک جمله formal contract؛
3. یک headline controlled result؛
4. یک headline downstream result؛
5. یک جمله mechanism finding؛
6. یک جمله limitation/release.

حداکثر چهار تا شش عدد در abstract، نه دوازده عدد.

#### روز ۴–۵: Related Work 2026

حداقل این کارها باید اضافه و دسته‌بندی شوند:

- HaluMem؛
- STALE؛
- Supersede؛
- TOKI؛
- Memory-R1؛
- Inside Out؛
- TrustMem؛
- GateMem؛
- Hindsight؛
- Mem2ActBench؛
- WorldMemArena؛
- Always-On Agents/AOEP؛
- Fine-Mem/AgeMem در صورت ارتباط مستقیم.

خروجی: یک جدول feature matrix با ستون‌های write labels، post-state، lineage، abstention، trajectory، natural data، human validation، exact replay، downstream evaluation.

#### روز ۶: یکپارچه‌سازی کنترلرها

در نسخه پایان‌نامه حداقل باید شفاف شود:

- کدام policy روی کدام instrument اجرا شده است؛
- چه چیزی shared interface است و چه چیزی implementation-specific؛
- کدام نتیجه «mechanism diagnosis» و کدام «accuracy» است؛
- چرا MGP-6 و LongMemEval complement هستند و validation متقابل کامل نیستند.

#### روز ۷–۸: اصلاح شکل‌ها و جداول

Main body فقط این visualها را نگه دارد:

1. معماری لایه‌ها و write-transition contract؛
2. data/evaluation flow؛
3. headline results + harm decomposition؛
4. mechanism audit یا risk–coverage plot.

جداول audit ریز، تاریخچه v2، bookkeeping و commandها به appendix منتقل شوند.

#### روز ۹: Limitations، Ethics و Artifact

- license status؛
- data card؛
- intended use/misuse؛
- owner-attested annotation؛
- contamination history؛
- exact scope of claims؛
- LLM-use disclosure مطابق مقصد.

#### روز ۱۰: نسخه دفاع‌پذیر پایان‌نامه

Gate نهایی:

- terminology ثابت؛
- همه headline numberها قابل trace؛
- ادعاهای novelty محدود؛
- هیچ تناقض بین abstract و limitations؛
- نسخه core حدود ۲۵–۳۵ صفحه و appendices جدا؛
- یک slide-ready summary شامل problem/gap/method/results/limitations.

روزهای ۱۱–۱۴ برای mock review و اصلاح رزرو شوند.

---

## ۱۰. برنامه P0 برای تبدیل به paper سطح‌بالا

### P0-1: license و artifact عمومی

باید قبل از submission تعیین شود:

- license داده؛
- license code؛
- public/private boundary؛
- checksum و immutable release؛
- dataset card و model/evaluation card؛
- anonymized hosting برای double-blind venue.

### P0-2: اعتبارسنجی انسانی مستقل

حداقل طراحی پیشنهادی:

- سه annotator مستقل خارج از تیم طراحی؛
- blinded نسبت به policy prediction و gold اولیه؛
- آموزش روی calibration set جدا؛
- annotation مستقل روی حداقل ۳۰۰–۵۰۰ item طبیعی یا independently rewritten؛
- گزارش raw agreement، Fleiss/weighted kappa یا Krippendorff’s alpha متناسب با طراحی؛
- adjudicator جدا؛
- evidence-turn citation و reason code؛
- تحلیل disagreement، نه فقط agreement نهایی؛
- ثبت زمان، version manual و conflict-of-interest.

### P0-3: hidden evaluation معتبر

نسخه بعدی باید:

- پس از freeze تمام policyها ساخته یا sealed شود؛
- controller، scorecard، no-guard، learned baseline، LLM judge و memory-system baseline را همگی قبل از access ثبت کند؛
- component-disjoint و template-disjoint باشد؛
- evaluation server یا third-party custodian داشته باشد؛
- فقط یک بار scoring اصلی انجام دهد؛
- per-system confidence interval و paired comparison گزارش کند.

### P0-4: policy واحد یا جداسازی صریح

دو گزینه:

**گزینه A – توصیه‌شده:** evaluation-first؛ همه policyها case study و baseline هستند.
**گزینه B:** policy واحد constrained/learned روی MGP-6 و LongMemEval و حداقل یک benchmark دیگر.

### P0-5: رفع اشکال scorecard

دو مسیر سالم:

1. صادقانه آن را `two active mechanisms plus logged metadata and safety guard` بنامید؛ یا
2. weights/thresholds را با calibration set، monotonic model یا constrained learner یاد بگیرید و سپس freeze کنید.

باید مقایسه شود:

- hand rule؛
- logistic/ordinal model؛
- monotonic GBM؛
- conformal/selective controller؛
- LLM policy؛
- oracle upper bounds.

---

## ۱۱. بسته آزمایش پیشنهادی برای Q1 یا Main Track

### ۱۱.۱ داده‌ها

حداقل:

- MGP-6 controlled diagnostic؛
- یک Natural Challenge subset با ۳۰۰–۵۰۰ مورد؛
- LongMemEval update/preference subsets یا full relevant slice؛
- LoCoMo یا یک benchmark trajectory-based؛
- STALE یا Supersede برای direct comparison؛
- در صورت امکان HaluMem برای operation-level comparison.

### ۱۱.۲ مدل‌ها

حداقل قابل دفاع:

- سه backbone از خانواده/اندازه متفاوت؛
- یک model باز کوچک؛
- یک model باز متوسط/بزرگ؛
- یک frontier API model؛
- برای top-tier بهتر است ۵–۸ configuration با مدل و seed مختلف داشته باشید.

### ۱۱.۳ baselineها

حداقل:

1. No-write/append-only؛
2. Last-write-wins/naive overwrite؛
3. structured LLM judge؛
4. learned classifier روی همان featureها؛
5. Memory-R1-like manager؛
6. STALE/CUPMem یا Supersede-style baseline؛
7. یک deployed memory system مانند Mem0/Zep/A-MEM/Hindsight؛
8. oracle action؛
9. oracle extraction با policy واقعی؛
10. no-guard و no-lineage ablation.

### ۱۱.۴ معیارها

نباید فقط action accuracy باشد:

- macro-F1؛
- destructive false-commit rate؛
- state invariant violation؛
- lineage integrity/recoverability؛
- stale retrieval rate؛
- downstream task accuracy؛
- risk–coverage/AURC؛
- calibration error/Brier یا NLL در صورت probability؛
- utility under multiple cost matrices؛
- latency، token و cost؛
- performance by memory type/domain/conflict family؛
- trajectory degradation در طول ۵/۱۰/۲۰ step.

### ۱۱.۵ آمار

- cluster bootstrap بر مبنای component/trajectory؛
- paired tests فقط با واحد مستقل درست؛
- correction برای multiple comparisons؛
- hierarchical logistic یا mixed-effects model برای چند model/dataset؛
- effect size و CI، نه فقط p-value؛
- primary outcomes از پیش مشخص؛
- sensitivity analysis برای cost matrices و thresholds.

---

## ۱۲. ایده‌های خلاقانه برای افزایش جذابیت علمی

### رتبه‌بندی بر اساس ارزش انتشار

| ایده | ارزش علمی | هزینه | توصیه |
|---|---:|---:|---|
| **Natural Write Gold** با annotation مستقل | ۱۰ | ۸ | بالاترین اولویت؛ بزرگ‌ترین ضعف فعلی را مستقیم می‌بندد. |
| **یک policy واحد روی controlled + natural** | ۱۰ | ۸ | داستان مقاله را یکپارچه می‌کند. |
| **Formal Epistemic Write Contract** | ۹ | ۷ | novelty را در برابر TOKI/TrustMem دقیق و نظری می‌کند. |
| **Constrained learned controller** | ۹ | ۸ | برای TACL/ACL/AAAI بسیار ارزشمند است. |
| **Counterfactual Governance Suite** | ۹ | ۶ | minimal pairهایی که فقط authority/time/provenance/scope را تغییر می‌دهند. |
| **OOD abstention و conformal risk control** | ۸.۵ | ۷ | ABSTAIN را از rule heuristic به selective safety mechanism ارتقا می‌دهد. |
| **Causal feature intervention audit** | ۸.۵ | ۶ | به‌جای correlation، اثر causal marker/relation/provenance را می‌سنجد. |
| **Dynamic hidden evaluation server** | ۸ | ۸ | contamination و overfitting benchmark را کاهش می‌دهد. |
| **Multi-step/cross-slot trajectories** | ۸ | ۷ | external validity را بالا می‌برد. |
| **Poisoning/source-laundering stress tests** | ۸ | ۶ | write-time safety را به threat model واقعی نزدیک می‌کند. |
| **Multilingual subset** | ۷ | ۶ | ارزش افزوده خوب، ولی بعد از natural validation. |
| **Multi-principal governance** | ۶ | ۸ | به GateMem نزدیک است؛ فقط با تفاوت روشن انجام شود. |

### ۱۲.۱ Counterfactual Governance Suite

برای هر semantic content، minimal pairهایی بسازید که فقط یکی از عوامل زیر تغییر کند:

- منبع authoritative در برابر hearsay؛
- statement قطعی در برابر hedge؛
- scope موقت در برابر پایدار؛
- explicit correction در برابر implicit conflict؛
- self-report در برابر third-party report؛
- timestamp قدیمی در برابر جدید؛
- permission/ownership متفاوت.

این suite نشان می‌دهد policy به semantics یا shortcutهای سطحی واکنش نشان می‌دهد.

### ۱۲.۲ Formal Epistemic Write Contract

می‌توان قرارداد را به شکل predicates و guarantees نوشت:

- state preservation under abstention؛
- lineage preservation under supersession؛
- no destructive update below evidence threshold؛
- replay consistency؛
- provenance non-erasure؛
- bounded destructive risk under calibrated confidence.

با TOKI باید صریحاً تفاوت بگذارید: TOKI روی concurrency/isolation/operator soundness است؛ مقاله شما باید روی evaluation observability و epistemic decision risk متمرکز بماند.

### ۱۲.۳ Learned but Auditable Policy

یک monotonic constrained model بسازید که:

- با افزایش ambiguity، احتمال ABSTAIN کاهش پیدا نکند؛
- SUPERSEDE فقط با relation منفی و evidence کافی فعال شود؛
- stability prior فقط margin را در جهت مشخص تغییر دهد؛
- rule guard به‌صورت hard constraint باقی بماند؛
- calibration و risk guarantee گزارش شود.

این ترکیب «learned + auditable + safety-constrained» جذاب‌تر از scorecard دستی فعلی است.

---

## ۱۳. ساختار پیشنهادی paper جدید

### عنوان‌های بهتر

1. **From Recall to State Change: Auditable Evaluation of Write-Time Memory Governance in Language Agents**
2. **When Should an Agent Rewrite Memory? Layered Evaluation of Write-Time State Transitions**
3. **WriteBench: Auditable Evaluation of Memory Updates in Language Agents**

عنوان فعلی خوب است، ولی `Beyond Recall` عمومی است و object of evaluation را به‌اندازه کافی سریع نشان نمی‌دهد.

### ساختار evaluation-first

1. Introduction: gap، one-sentence claim، سه contribution؛
2. Related Work: feature matrix؛
3. Write-Transition Contract؛
4. MGP-6 Design and Validity Gates؛
5. Systems/Baselines؛
6. Controlled Results؛
7. Natural Downstream Validation؛
8. Mechanism and Cost Audit؛
9. Limitations/Ethics؛
10. Conclusion.

### بودجه صفحه برای AAMAS/ACL

- Introduction: ۰.۷۵ صفحه؛
- Related work: ۰.۶؛
- Formalism: ۱.۰؛
- Dataset/evaluation: ۱.۲؛
- Methods/baselines: ۰.۸؛
- Results: ۲.۲؛
- analysis/limitations: ۱.۰؛
- conclusion: ۰.۲۵؛
- references خارج از محدودیت در صورت مجاز بودن.

تاریخچه کامل v2، commandها، failed runs، cost tables و response-to-reviewers در artifact/appendix بمانند.

---

## ۱۴. برنامه ارسال نزدیک: AAMAS 2027

تاریخ‌های رسمی:

- author registration: ۱۷ سپتامبر ۲۰۲۶؛
- abstract: ۱ اکتبر ۲۰۲۶؛
- full paper: ۸ اکتبر ۲۰۲۶؛
- notification: ۲۱ دسامبر ۲۰۲۶.

از ۲۸ ژوئیه تا deadline کامل حدود ۷۲ روز وجود دارد.

### برنامه ده‌هفته‌ای

#### هفته ۱

- انتخاب evaluation-first؛
- اصلاح claims و related-work matrix؛
- حل license؛
- preregister/pre-specify experiment plan.

#### هفته ۲

- نهایی‌کردن annotation protocol؛
- انتخاب annotatorهای مستقل؛
- freeze baseline list و hidden protocol.

#### هفته ۲–۴

- annotation طبیعی؛
- ساخت hidden جدید؛
- اجرای calibration؛
- آماده‌سازی adapters.

#### هفته ۳–۶

- چند model و baseline؛
- LongMemEval/STALE/Supersede/LoCoMo؛
- judge robustness و human audit؛
- policy unification یا constrained baseline.

#### هفته ۶

- آمار cluster-aware؛
- harm decomposition؛
- cost/latency؛
- robustness.

#### هفته ۷

- تبدیل به هشت صفحه؛
- یک figure اصلی و دو جدول اصلی؛
- appendix/artifact جدا.

#### هفته ۸

- سه mock review مستقل: agent systems، NLP، statistics/evaluation؛
- ساخت rebuttal risk log.

#### هفته ۹

- anonymity audit؛
- artifact dry run؛
- bibliography status audit؛
- claims-to-evidence audit.

#### هفته ۱۰

- final compile؛
- metadata؛
- reproducibility checklist؛
- submission.

### حداقل قابل‌قبول برای ارسال AAMAS

- license و artifact عمومی؛
- external human validation؛
- hidden comparison معتبر؛
- حداقل سه model؛
- حداقل پنج baseline قوی؛
- حداقل یک benchmark طبیعی مستقل؛
- روایت واحد در هشت صفحه.

اگر این حداقل‌ها تا پایان هفته ششم کامل نشوند، ارسال زودهنگام به AAMAS ریسک از دست‌دادن novelty window و ایجاد محدودیت برای مسیر ژورنالی را بالا می‌برد.

---

## ۱۵. برنامه ارسال TMLR

TMLR rolling است و اجازه revision در طول review می‌دهد، اما review عمومی است. زمان مناسب submission زمانی است که:

- license حل شده باشد؛
- independent annotation واقعی وجود داشته باشد؛
- novelty table به‌روز باشد؛
- paper حدود ۱۲–۱۶ صفحه main و متمرکز باشد؛
- baselineهای کلیدی حاضر باشند؛
- hidden comparison جدید تکمیل شده باشد.

مزیت TMLR برای این کار این است که negative result، audit و evaluation formalization را جدی می‌گیرد و نیاز ندارد paper حتماً SOTA algorithm باشد. عیب آن این است که نمی‌توان نسخه expanded یک conference paper archival را بعداً به آن فرستاد.

---

## ۱۶. برنامه Q1 ژورنالی ۱۲–۱۶ هفته‌ای

### هفته ۱–۳

- claim rewrite؛
- license؛
- independent validation؛
- literature update.

### هفته ۲–۷

- multi-benchmark؛
- multi-model؛
- baseline suite؛
- hidden evaluation.

### هفته ۵–۸

- constrained/learned policy یا formal contract؛
- trajectory experiment؛
- calibration.

### هفته ۸–۱۰

- statistics؛
- ablations؛
- error taxonomy؛
- artifact release.

### هفته ۱۰–۱۲

- journal rewrite؛
- figures؛
- data/reproducibility statements؛
- supplementary package.

### هفته ۱۳–۱۴

- سه mock reviewer؛
- plagiarism/self-overlap check؛
- reference verification؛
- cover letter.

### هفته ۱۵–۱۶

- final venue-specific formatting و submission.

---

## ۱۷. تصمیم نهایی پیشنهادی

### برای پایان‌نامه

نسخه اولیه را سریعاً با مسیر ده‌روزه بسازید. این نسخه لازم نیست منتظر همه آزمایش‌های journal-grade بماند، ولی باید claimهای صحیح، related work کامل، کنترلرهای شفاف و limitations بدون تناقض داشته باشد.

### برای انتشار

**گزینه پیشنهادی اصلی:**

- paper را evaluation-first کنید؛
- P0ها را کامل کنید؛
- در صورت موفقیت سریع آزمایش‌ها، AAMAS 2027–GAAI را هدف بگیرید؛
- در غیر این صورت نسخه قوی‌تر را بدون عجله به TMLR یا مسیر Q1 یعنی TIST/KBS بفرستید.

**گزینه با بیشترین شانس علمی برای کار فعلی پس از اصلاح:** TMLR.
**گزینه با بهترین تطابق و deadline نزدیک:** AAMAS 2027–GAAI.
**گزینه Q1 محافظه‌کارانه:** ACM TIST، سپس Knowledge-Based Systems.
**گزینه پرارزش ولی پرریسک:** TACL یا NeurIPS 2027 E&D.

### شرط ارسال واقعی

مقاله زمانی آماده submission جدی است که تمام موارد زیر پاس شوند:

- [ ] public license و artifact قابل‌دسترسی؛
- [ ] سه annotator مستقل + adjudication؛
- [ ] natural gold subset؛
- [ ] hidden comparison برای چند سیستم؛
- [ ] policy story یکپارچه؛
- [ ] direct comparison با نزدیک‌ترین کارهای ۲۰۲۶؛
- [ ] حداقل سه model و پنج baseline؛
- [ ] calibration/risk–coverage؛
- [ ] ادعاهای human/pre-registration/release اصلاح‌شده؛
- [ ] main paper متمرکز و venue-length؛
- [ ] هیچ عدد یا claim بدون trace/evidence.

تا قبل از عبور از این gateها، مقاله برای پایان‌نامه مناسب است، اما ارسال Q1/top-tier بیش از آن‌که از کیفیت framing ضربه بخورد، از validity و breadth ناکافی ضربه خواهد خورد.

---

## ۱۸. منابع و صفحات رسمی بررسی‌شده

در تهیه این گزارش، علاوه بر فایل مقاله و artifactهای داخلی، صفحات رسمی یا اولیه مربوط به موارد زیر بررسی شد:

- TMLR editorial policies، acceptance criteria، author/reviewer guide و نمونه paperهای پذیرفته‌شده؛
- AAMAS 2027 Call for Papers و حوزه Generative and Agentic AI؛
- TACL submission policies؛
- NeurIPS 2026 Evaluations & Datasets scope و artifact requirements؛
- JAIR submission requirements و editorial charter؛
- Knowledge-Based Systems و Artificial Intelligence journal insights؛
- ACL Anthology برای Memory-R1، Inside Out، Mem2ActBench و Hindsight؛
- نسخه‌های اولیه HaluMem، STALE، Supersede، TOKI، TrustMem، GateMem، WorldMemArena و Always-On Agents.

تمام رتبه‌های Q1 باید درست پیش از submission در پایگاه دقیق مورد قبول دانشگاه، با year/category مشخص، دوباره تأیید شوند.
