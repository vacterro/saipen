<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**بروتوكول الاستمرارية لوكلاء البرمجة بالذكاء الاصطناعي.** ذاكرة مشروع دائمة بنص بسيط (markdown)، بحيث يستطيع وكيل جديد بدون سجل محادثات تشغيل `/saipen continue` واستئناف العمل في أقل من دقيقة -- دون إعادة شرح، مع أي مزود، في أي يوم.

**أمر واحد. صفر فقدان للذاكرة.**

**مفاتيح سريعة:** `cc` يواصل تشغيل وضع الأهداف النشط، `sss` يعرض الحالة دون لمس الكود، و`ss` يحفظ نقطة تحقق ويتوقف. [انظر خريطة المفاتيح الكاملة 13](saipen/RFC.md#110-command-surface). التوائم السيريلية تعمل أيضًا: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**لغة الرد.** يرد الوكيل افتراضيًا **باللغة الإستونية** — هذه إعدادات، وليست نزوة، ولا شيء آخر في SAIPEN باللغة الإستونية. غيّرها في مكان واحد: سطر `reply_language:` في أعلى [`saipen/STYLE.md`](saipen/STYLE.md). `et` الإستونية، `en` الإنجليزية، `ru` الروسية، `auto` تختار حسب لغة رسالتك. يبقى البروتوكول والكود والالتزامات وكل الوثائق بالإنجليزية مهما كانت القيمة.

**v7.177.0** | [المواصفات](SPEC.md) | [الدليل](GUIDE.md) | [RFC](saipen/RFC.md) | [الأسلوب](saipen/STYLE.md) | [واجهة المستخدم](saipen/UI.md) | [التطابق](saipen/CONFORMANCE.md) | markdown بسيط | صفر تبعيات | MIT

```text
المستخدم ->  /saipen continue
الوكيل    ->  يقرأ STATE ("ما الذي عليّ فعله الآن؟")
الوكيل    ->  يقرأ BOARD ("ما هي المهمة التي سأبدأ بها؟")
الوكيل    ->  يقرأ next_action (ينفذ الأمر)
الوكيل    ->  يعمل.
```

### حالة المشروع > ذاكرة النموذج
الذاكرة تعيش في المشروع، وليس في رأس النموذج. تتحول `المشروع -> الذاكرة -> LLM` إلى `المشروع -> حالة SAIPEN -> LLM`.

### منطق البروتوكول الأساسي والضمانات
- **آلة الحالة الأساسية**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **استقلالية ذاتية بدون مطالبات**: لم تتبقَ مهام مفتوحة؟ ينتقل تلقائيًا إلى حلقة `HUNT` (فحص الأخطاء) ← `ADD` (تطوير الميزات) ← `HUNT`. بدون طرح أي أسئلة.
- **مشغلات صريحة**: `/saipen clean` (تنظيف المستودع)، `/saipen translate` (مصنع معزول في `.saipen/saitranslate/`)، `/saipen markhunt` (تدقيق شامل جاف للتسجيل فقط)، `/saipen prepare` (تجميع العمل للتسليم)، `/saipen validate` (فحص التطابق)، `/saipen goal` (تنفيذ موجة مستقلة). التحكم والبيانات: `/saipen status` (تقرير للقراءة فقط)، `/saipen stop` (حفظ نقطة التوقف والتوقف). القائمة الكاملة: RFC.md § 1.10.
- **موثوقية صارمة**: تحليل الإدخال على الدفعات (تذاكر دقيقة واحدة تلو الأخرى)، تبني شجرة العمل غير النظيفة (لا يمسح العمل غير الملتزم به أبداً)، حجب الأسرار (`sk-***`).

## مشاريع مدعومة بـ SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — أداة إدارة مطالبات عالية الأداء مدمجة أصليًا مع بروتوكول ذاكرة SAIPEN.

## طبقتان

| الطبقة | مطلوبة | الغرض |
|---|---|---|
| **الأساسية (Core)** | ✅ | استئناف العمل بأمان |
| **الصيانة (Maintenance)** | فوق الأساسية | تطوير البرمجيات دون توجيه مهام |

**التطور المؤتمت.** لا توجد مهام مفتوحة، اكتب `/saipen`: تقوم `HUNT` بتدقيق الأخطاء، الكود الميت، والاختبارات الفاشلة. المستودع نظيف؟ تقوم `ADD` ببناء الميزة التالية المفقودة، وتتحقق منها، ثم تعود لـ `HUNT`. المنتج ناضج -> يتوقف بسلاسة.

**وضع الهدف (GOAL Mode).** يقوم `/saipen goal <ما تريده>` بتغيير اتجاه اللوحة (تخفيض أولوية التذاكر القديمة، دون حذفها) والدفع بالهدف الجديد للأمام -- لا أسئلة "هل أستمر؟" بين التذاكر، ولا يتم تخطي VERIFY/REVIEW أبداً. ينفذ SHIP الدفع التلقائي للمستودع البعيد الموجود؛ والمستودع الجديد كليًا يسأل مرة واحدة فقط. شحن الهدف ليس نقطة النهاية أيضاً -- بل ينتقل مباشرة إلى صيانة HUNT/ADD المستقلة حتى ينضج المنتج أو يُحظر أو تصل الدورة إلى حدها الأقصى (3 موجات / 20 تذكرة، ثم يحفظ نقطة التوقف ويصدر تقريراً).

## البداية السريعة

**1. التثبيت مرة واحدة لكل جهاز** -- يعلّم Claude Code و Gemini و OpenCode و Aider و Antigravity? Codex ??? ???? ??? ?? ~/.agents/skills (FreeBuff? ???):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. بدء مشروع** -- افتح وكيلاً في مجلد مشروعك، واكتب:
> `saipen set`

بدون تثبيت؟ انسخ خطاً واحداً لأي وكيل:
> اقرأ <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md واتبعهما.

المنصة ليست في القائمة أعلاه (DeepSeek, Qwen, standalone OpenAI, إلخ)؟
توجد ملاحظات كل منصة في `extensions/adapters/`.

## روابط التوثيق والمواصفات
- **[SPEC.md](SPEC.md)** -- الهندسة المعمارية الرسمية، أهداف التصميم، واختبار الصلاحية.
- **[RFC.md](saipen/RFC.md)** -- المواصفات المعيارية التي ينفذها الوكلاء.
- **[GUIDE.md](GUIDE.md)** -- الدليل التعليمي البشري وإدلة المبسطة (ELI5):
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- أسلوب تواصل الوكيل وتحديد الصوت.
- **[UI.md](saipen/UI.md)** -- إرشادات تصميم واجهة المستخدم Win95 الذهبي الداكن.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- سيناريوهات اختبار السلوك وقواعد أداة التحقق.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

## ## لقطات الشاشة

<details>
<summary>انقر للتوسيع</summary>

<img src="assets/screenshot-freebuff.png" alt="إرشادات وكيل FreeBuff" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set في nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="لقطة شاشة saipen 2026-08-01" width="600"/>

</details>
