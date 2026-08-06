# راهنمای برچسب‌گذاری مستقل MGP-6 v3

نسخه قابل ارسال برای برچسب‌زن, پاسخ‌ها را مستقل، فقط بر اساس شواهد قابل مشاهده و بدون ابزار مولد ثبت کنید.

> هدف، حدس‌زدن سیاست پژوهشگر یا برچسب اکثریت نیست. باید اثر موجه رویداد جدید بر وضعیت حافظه را با action، target، state، lineage و evidence مشخص کنید.

## ۱. واحد برچسب‌گذاری

هر آیتم یک `transition_id` درون trajectory یک principal است. وضعیت فعال درست پیش از candidate مشخص می‌شود. شما باید فقط گذار خواسته‌شده را قضاوت کنید و پروفایل گسترده‌تری از کاربر نسازید.

شش خروجی اصلی را جدا ثبت کنید:

1. `action`: یکی از KEEP، SUPERSEDE یا ABSTAIN؛
2. `target_record_ids`: رکورد یا رکوردهای تحت اثر؛
3. `resulting_active_state`: رکوردهای فعال پس از گذار؛
4. `lineage_links`: ارتباط predecessor/successor یا invalidation؛
5. `evidence_spans`: شناسه turnهای ضروری؛
6. `rationale`: دلیل کوتاه و مبتنی بر شواهد.

درست‌بودن action لزوماً به‌معنای درست‌بودن state یا lineage نیست؛ همه را مستقل و دقیق تکمیل کنید.

## ۲. معنای سه action

### KEEP, حفظ وضعیت معتبر موجود

رکورد durable فعلی با همان status فعال باقی می‌ماند و successor durable برای ابطال آن ساخته نمی‌شود. این action زمانی مناسب است که شواهد روشن است اما رکورد قبلی را باطل نمی‌کند؛ برای نمونه تکرار همان معنا، elaboration سازگار، موضوع/slot متفاوت، یا override موقت روشن که در schema به‌صورت transient جدا ثبت می‌شود.

KEEP به معنی «هر متن جدید را ذخیره کن» نیست. duplicate durable نسازید و یک استثنای موقت را جایگزین ترجیح پایدار نکنید.

### SUPERSEDE, پایان اعتبار رکورد قبلی با حفظ تاریخچه

شواهد قابل‌اتکا نشان می‌دهد رکورد active مربوط به همان principal، همان slot و scope مرتبط دیگر current نیست. رکورد قبلی حذف یا overwrite نمی‌شود؛ status آن `superseded`/`invalidated` می‌شود و successor یا رویداد ابطال با lineage روشن ثبت می‌گردد.

برای correction دارای مقدار جدید، successor جدید active است و به predecessor پیوند می‌خورد. برای retraction معتبر بدون مقدار جایگزین، رکورد قبلی active نمی‌ماند و یک tombstone/invalidation طبق schema batch ثبت می‌شود؛ نبود مقدار تازه به‌تنهایی دلیل ABSTAIN نیست.

### ABSTAIN, خودداری از mutation به‌علت شواهد ناکافی

وقتی منبع، principal، slot، referent، زمان، دوام یا محتوای candidate به‌اندازه کافی روشن و قابل‌اتکا نیست، state را تغییر ندهید. quote شخص ثالث، پیشنهاد assistant، خروجی tool، استنباط ضعیف، pronoun حل‌نشده، منابع متعارض و bundle تجزیه‌نشده نمونه‌های رایج‌اند.

ABSTAIN با KEEP فرق دارد: در KEEP معنا و اثر policy روشن است و آگاهانه رکورد موجود حفظ می‌شود؛ در ABSTAIN عدم‌قطعیت یا ضعف شواهد اجازه هیچ write معتبری نمی‌دهد.

## ۳. درخت تصمیم

این مراحل را به‌ترتیب اجرا کنید؛ هیچ keyword یا metadata به‌تنهایی action را تعیین نمی‌کند.

1. principal و source روشن است؟ اگر speaker، مالک گفته یا attribution نامعلوم است، معمولاً ABSTAIN.
2. محتوای candidate اتمیک و self-contained است؟ اگر چند ادعای تجزیه‌نشده یا referent مبهم دارد، ABSTAIN.
3. با رکورد فعال همان slot و scope معنایی را مقایسه می‌کند؟ اگر slot متفاوت است، رکورد قبلی را supersede نکنید؛ اثر جداگانه فقط طبق schema مجاز است.
4. reliability شواهد کافی است؟ confidence ابزار یا روانی متن جای provenance را نمی‌گیرد.
5. زمان را حل کنید: current، expired، retrospective، future یا ambiguous. temporal scope باید با validity رکوردها سازگار باشد.
6. دوام را حل کنید: stable profile، temporary state، preference، plan/commitment یا derived summary.
7. رابطه را معنایی تعیین کنید: duplicate، elaboration، contradiction، correction، retraction یا uncertain conflict.
8. اگر رکورد durable فعلی به‌طور قابل‌اتکا و در همان scope باطل شده، SUPERSEDE و lineage را بسازید.
9. اگر شواهد روشن است ولی ابطالی رخ نداده، KEEP و state نهایی را ثبت کنید.
10. اگر برای هر mutation معتبر تردید مادی باقی است، ABSTAIN و state را بدون تغییر نگه دارید.

## ۴. principal، provenance و reliability

گفته مستقیم first-party معمولاً قوی‌ترین evidence است، اما هنوز باید زمان، scope و referent روشن باشد. first-party unverified خودکار رد نمی‌شود؛ ادعای سلیقه شخصی نیاز به تأیید بیرونی ندارد، ولی ادعای factual حساس ممکن است نیازمند زمینه باشد.

delegated source فقط وقتی قابل استفاده است که اختیار، principal و موضوع delegation در متن روشن باشد. assistant، tool، extractor، quoted speaker یا shared-device log به‌صرف confidence بالا به حافظه شخص تبدیل نمی‌شود.

اگر دو منبع معتبر تعارض دارند و متن راه حل نمی‌دهد، ABSTAIN. تعداد تکرار، لحن قطعی یا score مدل، evidence مستقل ایجاد نمی‌کند.

## ۵. same-slot و atomicity

surface wordها را نه، معنای mutually exclusive slot را مقایسه کنید. زمان جلسه و قالب جلسه دو slot جدا هستند. نوشیدنی همیشگی و انتخاب فقط برای امشب موضوع مرتبط اما scope متفاوت دارند. یک رکورد durable باید به‌شکل یک ادعای واحد درباره principal/slot/value/validity قابل نمایش باشد.

اگر candidate چند ادعا دارد و schema batch اجازه decomposition نمی‌دهد، بخشی از bundle را حدس نزنید؛ ABSTAIN و علت را ثبت کنید. اگر decomposition از قبل در ورودی انجام شده، فقط transition مشخص‌شده را قضاوت کنید.

## ۶. زمان و دوام

- `current`: برای وضعیت فعلی قابل اعمال است.
- `explicitly expired`: بازه‌اش تمام شده؛ نباید current durable را بدون دلیل باطل کند.
- `retrospectively corrected`: factual history یا validity interval قبلی اصلاح می‌شود؛ تاریخ را در state/lineage حفظ کنید.
- `future-scoped`: تا زمان اثرگذاری، رکورد فعلی را current نگه دارید و فقط representation مجاز schema را استفاده کنید.
- `ambiguous`: اگر ambiguity روی mutation اثر دارد، ABSTAIN.

عبارت‌هایی مانند «از حالا»، «در واقع»، «فقط امروز» و «شاید» cue هستند، نه rule. نبود cue، correction روشن را بی‌اعتبار نمی‌کند؛ وجود cue نیز quote یا منبع ضعیف را معتبر نمی‌سازد.

temporary override روشن معمولاً رکورد durable را KEEP می‌کند و در صورت پشتیبانی schema یک transient جدا با expiration می‌سازد. override موقت مبهم یا hedged معمولاً ABSTAIN است.

## ۷. duplicate، elaboration و conflict

- duplicate معنایی: رکورد durable دوم نسازید؛ state قبلی حفظ می‌شود.
- elaboration سازگار: اگر slot جدا/جزئیات compatible و schema اجازه می‌دهد، رکورد مرتبط جدا ثبت می‌شود؛ predecessor بی‌دلیل supersede نمی‌شود.
- contradiction: فقط با source/scope/reliability کافی می‌تواند SUPERSEDE باشد؛ در غیر این صورت ABSTAIN یا KEEP بر حسب اثر روشن.
- correction: می‌تواند explicit یا implicit باشد. معیار، certainty معنایی در همان slot است نه وجود کلمه «اصلاح».
- retraction: اگر قابل‌اتکا و مشخص است، validity ادعای قبلی را پایان می‌دهد؛ اگر معلوم نیست کدام ادعا پس گرفته شده، ABSTAIN.
- uncertain conflict: اگر دو تفسیر materially different باقی است، state را تغییر ندهید.

## ۸. ساخت state و lineage

برای هر رکورد حداقل `record_id`, `principal`, `slot`, `value`, `status`, `valid_time` و provenance قابل استناد را رعایت کنید؛ فقط fieldهای schema batch را پر کنید.

در SUPERSEDE:

1. target درست را انتخاب کنید؛
2. predecessor را در تاریخچه نگه دارید و status آن را پایان دهید؛
3. successor یا invalidation مجاز را بسازید؛
4. پیوند `supersedes_id`/lineage معادل را ثبت کنید؛
5. دو رکورد durable ناسازگار را هم‌زمان active نگذارید.

در KEEP، duplicate durable نسازید. در ABSTAIN، هیچ field وضعیت را به‌خاطر candidate تغییر ندهید. اگر state ورودی از قبل ناسازگار است، آن را خودسرانه repair نکنید؛ `input_defect_flag` را ثبت کنید.

## ۹. evidence span و rationale

فقط turnهای لازم را در `evidence_spans` بیاورید: منشأ رکورد قبلی، candidate و هر turn لازم برای حل coreference/زمان/delegation. کل trajectory را به‌عنوان evidence انتخاب نکنید مگر واقعاً همه آن لازم باشد.

rationale باید کوتاه و در این قالب باشد:

`[منبع/انتساب] + [رابطه principal و slot] + [زمان/دوام] + [اثر بر state و lineage]`

نمونه: «T08 گفته مستقیم USER_A است؛ همان slot ترجیح پایدار را با scope جاری اصلاح می‌کند؛ R14 پایان می‌یابد و successor به آن پیوند می‌خورد.»

از عبارت‌های «حس می‌کنم»، «احتمالاً gold این است» یا اشاره به policy پژوهشگر استفاده نکنید.

## ۱۰. confidence و ambiguity

`annotator_confidence` را از ۱ تا ۵ ثبت کنید:

| امتیاز | معنا |
| --- | --- |
| ۵ | شواهد و schema روشن؛ تقریباً بدون تفسیر رقیب |
| ۴ | تصمیم روشن با یک نکته جزئی بی‌اثر |
| ۳ | تصمیم قابل دفاع ولی تفسیر رقیب واقعی وجود دارد |
| ۲ | ابهام مادی؛ نیاز جدی به داوری |
| ۱ | آیتم یا schema برای تصمیم کافی نیست |

confidence پایین action چهارم نیست. همچنان یکی از سه action را انتخاب کنید و `ambiguity_flag`/`input_defect_flag` را صادقانه پر کنید.

## ۱۱. مثال‌های آموزشی خارج از test

### مثال A, تغییر پایدار مستقیم

حافظه: `calendar_week_start = Sunday`. کاربر می‌گوید: «شروع ثابت هفته تقویم من دوشنبه است.» همان principal و slot، scope جاری و شواهد مستقیم است. action: SUPERSEDE؛ رکورد قدیمی در تاریخچه می‌ماند و successor Monday به آن لینک می‌شود.

### مثال B, استثنای موقت روشن

حافظه: `restaurant_noise = quiet`. کاربر می‌گوید: «فقط برای امشب جای شلوغ انتخاب کن.» action: KEEP؛ quiet durable می‌ماند و اگر schema دارد، transient تا پایان امشب ثبت می‌شود.

### مثال C, استثنای موقت مردد

همان حافظه؛ «این هفته شاید جای شلوغ، مطمئن نیستم.» action: ABSTAIN؛ به‌علت hedge، mutation معتبری ایجاد نمی‌شود.

### مثال D, quote شخص ثالث

کاربر می‌گوید: «دوستم گفت از حالا قهوه تلخ می‌خواهد.» این preference به دوست نسبت داده شده، نه principal مورد ارزیابی. برای حافظه principal: ABSTAIN.

### مثال E, duplicate

حافظه: `download_format = PDF`. کاربر بعداً همان ترجیح PDF را با paraphrase تکرار می‌کند. action: KEEP؛ duplicate durable جدید ساخته نمی‌شود.

### مثال F, retraction بدون مقدار جدید

حافظه: `allergy = peanuts`. کاربر به‌صورت روشن و معتبر می‌گوید ثبت قبلی درباره خودش اشتباه بوده و آن را پس می‌گیرد، بدون اعلام آلرژی دیگر. action: SUPERSEDE؛ رکورد قدیمی inactive/invalidated و lineage به رویداد retraction وصل می‌شود؛ مقدار جایگزین حدس زده نمی‌شود.

این متن‌ها فقط آموزش مفهوم‌اند و نباید در آیتم‌های اصلی تکرار یا paraphrase شوند.

## ۱۲. استقلال و رفتار مجاز

- به‌تنهایی کار کنید؛ درباره پاسخ آیتم با هیچ مشارکت‌کننده‌ای صحبت نکنید.
- از ChatGPT، مدل زبانی، موتور پیشنهاد پاسخ یا فایل annotation شخص دیگر استفاده نکنید.
- خروجی هیچ سیستم حافظه را جست‌وجو یا مشاهده نکنید.
- به distribution actionها نگاه نکنید و برای متوازن‌کردن پاسخ خود label را عوض نکنید.
- اشتباه ثبت‌شده را فقط پیش از تحویل نهایی و با log نسخه اصلاح کنید؛ پس از lock با هماهنگ‌کننده مکاتبه کنید، نه با ویرایش خاموش.
- سؤال schema را فقط با شناسه آیتم و بدون پیشنهاد label بپرسید.

## ۱۳. روال calibration و batch اصلی

ابتدا calibration جداگانه را تکمیل کنید. بازخورد calibration برای فهم manual است و آیتم‌هایش وارد confirmation نمی‌شوند. ورود به batch اصلی فقط پس از اعلام صلاحیت هماهنگ‌کننده مجاز است.

در batch اصلی هر ۳۰ تا ۴۵ دقیقه استراحت کوتاه داشته باشید. اگر خستگی، ابهام systematic یا مشکل فرم دیدید، توقف کنید و آخرین شناسه کامل‌شده را گزارش دهید. سرعت هدف نیست؛ کیفیت و استقلال مهم‌تر است.

## ۱۴. چک‌لیست هر آیتم

- [ ] principal و source را مشخص کرده‌ام.
- [ ] slot، referent، time و durability را حل کرده‌ام.
- [ ] reliability را از evidence سنجیده‌ام، نه confidence ابزار.
- [ ] action دقیقاً یکی از سه گزینه است.
- [ ] target، resulting state و lineage با action سازگارند.
- [ ] evidence span حداقلی و کافی است.
- [ ] rationale به متن قابل مشاهده متکی است.
- [ ] confidence و flagهای ابهام/خرابی صادقانه‌اند.
- [ ] از label دیگران، LLM یا system output استفاده نکرده‌ام.

## ۱۵. حریم خصوصی و گزارش مشکل

اگر نام واقعی، اطلاعات تماس، شناسه، داده سلامت/مالی/حساس یا محتوای قابل‌شناسایی دیدید، متن را کپی نکنید و annotation را ادامه ندهید. فقط `transition_id` را از مسیر خصوصی ثبت‌شده در برگهٔ توزیع به مسئول پاسخ‌گو گزارش کنید. فایل‌ها را فقط در فضای خصوصی پروژه که در همان برگه مشخص شده است قرار دهید و پس از تأیید دریافت، نسخه محلی را طبق دستور حذف کنید.
