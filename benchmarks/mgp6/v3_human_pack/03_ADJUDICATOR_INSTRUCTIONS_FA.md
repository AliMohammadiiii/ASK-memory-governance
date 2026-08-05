# دستورالعمل داور اختلاف‌های MGP-6 v3

نسخه قابل ارسال برای داور چهارم, داوری فقط پس از قفل سه annotation مستقل آغاز می‌شود.

> نقش شما انتخاب رأی اکثریت نیست. ابتدا judgment مستقل خود را قفل می‌کنید؛ سپس منشأ اختلاف را بررسی و یک تصمیم مستدل و قابل ممیزی ثبت می‌کنید.

## ۱. شرط استقلال

داور نباید در طراحی کنترل‌گر، ساخت آیتم confirmation یا annotation سه‌نفره همان آیتم‌ها نقش داشته باشد. تعارض منافع، مشاهده قبلی gold یا دسترسی به system output باید پیش از شروع اعلام شود.

شما نباید نام annotatorها، هویت نویسنده، نتیجه سیستم‌ها، author gold، توزیع کل actionها یا splitهای محرمانه را ببینید. برچسب‌ها با A/B/C نمایش داده می‌شوند و ترتیب آن‌ها برای هر آیتم می‌تواند random باشد.

## ۲. ورودی و خروجی

برای هر `adjudication_id` دو مرحله دارید:

1. مرحله مستقل: trajectory، state قبل و candidate را می‌بینید؛ `independent_action`, target, state, lineage, evidence و rationale را ثبت و قفل می‌کنید.
2. مرحله حل اختلاف: action و rationaleهای بی‌نام A/B/C را می‌بینید؛ `final_action` و artifact نهایی، نوع اختلاف و دلیل تصمیم را ثبت می‌کنید.

خروجی باید raw labelهای A/B/C و judgment مستقل شما را حفظ کند. هیچ مقدار قبلی overwrite نمی‌شود.

## ۳. قاعده ازپیش‌ثبت‌شده پیشنهادی

- توافق کامل A/B/C: بدون داوری موردی، همان artifact فقط پس از validation شکلی پذیرفته می‌شود.
- اختلاف در هر field اصلی: آیتم به داور چهارم می‌رود، حتی اگر action یکسان ولی state/lineage متفاوت باشد.
- داور ابتدا بدون مشاهده رأی‌ها judgment مستقل می‌دهد.
- سپس دلایل A/B/C باز می‌شوند؛ داور می‌تواند judgment را حفظ یا تغییر دهد، اما هر تغییر باید دلیل شواهدی داشته باشد.
- اکثریت ۲–۱ tie-break خودکار نیست.
- اگر اختلاف ناشی از نقص واقعی آیتم/schema است، `ITEM_DEFECT` ثبت می‌شود؛ آیتم silent edit یا به‌علت سختی حذف نمی‌شود.

اگر پروژه قاعده دیگری دارد، باید قبل از بازشدن labelها freeze و جایگزین این بخش شده باشد.

## ۴. معیار تصمیم

همان manual برچسب‌زن را اعمال کنید:

- KEEP: رکورد durable موجود باطل نمی‌شود؛ duplicate، elaboration سازگار یا transient روشن ممکن است بدون successor durable مدیریت شود.
- SUPERSEDE: شواهد قابل‌اتکا همان principal/slot/scope را اصلاح یا retract می‌کند؛ predecessor حفظ و validity آن پایان می‌یابد، successor یا invalidation دارای lineage ثبت می‌شود.
- ABSTAIN: source، slot، referent، زمان، دوام یا محتوا برای mutation معتبر کافی نیست؛ state تغییر نمی‌کند.

هرگز بر اساس اینکه «سیستم احتمالاً چه می‌کند» یا «کدام action کمتر/بیشتر شده» تصمیم نگیرید.

## ۵. طبقه‌بندی منشأ اختلاف

یک یا چند کد ثبت کنید:

| کد | توضیح |
| --- | --- |
| `SOURCE_ATTRIBUTION` | اختلاف درباره speaker، principal یا delegated authority |
| `SLOT_IDENTITY` | اختلاف درباره یکسان‌بودن slot یا scope معنایی |
| `TEMPORAL_SCOPE` | current/expired/retrospective/future/ambiguous |
| `DURABILITY` | پایدار در برابر موقت/plan/summary |
| `RELIABILITY` | کفایت provenance یا تعارض منبع |
| `RELATION` | duplicate/elaboration/contradiction/correction/retraction |
| `TARGET` | action مشترک ولی target متفاوت |
| `STATE_CONSTRUCTION` | resulting active state متفاوت |
| `LINEAGE` | predecessor/successor یا validity متفاوت |
| `SCHEMA_GAP` | manual/schema representation کافی ندارد |
| `ITEM_DEFECT` | متن ناقص، ناسازگار یا واقعاً حل‌ناپذیر است |
| `ANNOTATION_ERROR` | خطای خواندن یا ورود داده بدون ابهام مفهومی |

## ۶. فرایند هر اختلاف

1. نسخه manual و schema را ثبت کنید.
2. آیتم خام را بدون رأی‌های A/B/C بخوانید.
3. principal، source، slot، time، durability و relation را یادداشت کنید.
4. judgment مستقل کامل را ثبت و submit/lock کنید.
5. بسته دلایل A/B/C را باز کنید؛ نام یا الگوی هویتی نباید موجود باشد.
6. هر دلیل را فقط با evidence آیتم مقایسه کنید، نه با تعداد رأی.
7. final action، target، resulting state، lineage و evidence span را ثبت کنید.
8. disagreement code و rationale نهایی را بنویسید.
9. `changed_after_review` و دلیل تغییر از judgment مستقل را پر کنید.
10. اگر defect وجود دارد، آن را flag کنید و آیتم را خودسرانه بازنویسی/حذف نکنید.

## ۷. قالب rationale داوری

`اختلاف بر سر [کد] بود. turnهای [شناسه] نشان می‌دهند [تحلیل source/slot/time]. بنابراین [action] و state/lineage [خلاصه artifact] انتخاب شد. دلیل رد تفسیر رقیب: [دلیل کوتاه].`

rationale باید برای بازتولید تصمیم کافی باشد، اما اطلاعات هویتی یا اشاره به system performance نداشته باشد.

## ۸. آیتم معیوب یا حل‌ناپذیر

اگر دو تفسیر با manual سازگار و از نظر شواهد هم‌وزن‌اند، action را با حدس شخصی قطعی نکنید. `ITEM_DEFECT` یا `SCHEMA_GAP` و confidence پایین ثبت کنید. هماهنگ‌کننده فقط قانون exclusion ازپیش‌ثبت‌شده را اعمال می‌کند.

پس از دسترسی تیم کنترل‌گر به predictionها، defect دلیل حذف پسینی نیست. آیتم و همه labelها حفظ می‌شوند و نتیجه با rule اصلی و sensitivity analysis گزارش می‌شود. wording test هرگز پس از مشاهده output سیستم برای «روشن‌ترشدن» اصلاح نمی‌شود.

## ۹. ممنوعیت‌ها

- رأی‌گیری ساده یا انتخاب خودکار اکثریت؛
- تماس با annotator برای دفاع از پاسخ؛
- استفاده از LLM، جست‌وجوی system output یا author notes؛
- تغییر raw annotationها؛
- حذف آیتم سخت یا ناموافق با انتظار؛
- بازکردن gold یا prediction پیش از پایان و hash داوری؛
- درج نام یا اطلاعات فردی در rationale.

## ۱۰. چک‌لیست پایان round

- [ ] judgment مستقل پیش از رأی‌های A/B/C قفل شده است.
- [ ] همه fieldهای action/state/lineage بررسی شده‌اند.
- [ ] evidence span و کد اختلاف ثبت شده است.
- [ ] تغییر پس از مشاهده دلایل، در صورت وجود، توضیح دارد.
- [ ] raw labelها و rationaleهای سه نفر دست‌نخورده‌اند.
- [ ] defectها flag شده‌اند، نه silent edit یا حذف.
- [ ] هیچ system output، gold مؤلف یا هویت فردی دیده/استفاده نشده است.
- [ ] فایل نهایی timestamp و hash شده و از مسیر امن تحویل شده است.

## ۱۱. گزارش حادثه

اگر فایل شامل نام annotator، author gold، prediction سیستم یا PII بود، آن را ببندید و ادامه ندهید؛ فقط `adjudication_id` و نوع نشت را از مسیر خصوصی ثبت‌شده در برگهٔ توزیع به مسئول پاسخ‌گو گزارش کنید. تا دریافت بسته پاک‌سازی‌شده داوری متوقف می‌ماند.
