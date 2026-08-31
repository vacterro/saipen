<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
</p>

<div align="center">
  <h3><a href="README.ee.md">🇪🇪 LOE SEDA EESTI KEELES / ESTONIAN 🇪🇪</a></h3>
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp;
  <a href="README.ded.md">👴 Дед-Версия (Russian)</a> &nbsp;|&nbsp;
  <a href="README.ja.md">🇯🇵 日本語 (Japanese)</a>
</div>

# SAIPEN

**بروتوكول الاستمرار لagents الترميزية للذكاء الاصطناعي.**توجد ذاكرة المشروع في ملفات
Markdown داخل المشروع(`.saipen/`), لذا أي agent بارد متوافق —
بدون تاريخ المحادثة، بدون ذاكرة الجلسة — يمكن أن يعمل`/saipen continue`, يقرأ
المُخزَّن مسبقًا`next_action`, ويستأنف العمل دون الحاجة إلى طلب المستخدم إعادة التفسير
أي شيء. الحالة تعود للمشروع، وليس إلى ذاكرة مزود نموذج واحد.

**명령 واحد لاستئناف العمل. الحالة في ملفات بسيطة. عقود مُفَحَّصة بواسطة الآلة.**

يقوم المستودع بتأكيد نفسه عند كل دفع؛ تثبيت، حالة، فحوصات، و
التركيب غير مثبت محليًا — لا خدمة سحابية، ولا خادم، ولا قاعدة بيانات.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.234.0** | [المواصفات](SPEC.md) | [الدليل](GUIDE.md) | [النواة](saipen/CORE.md) | [الصيانة](saipen/MAINTENANCE.md) | [النمط](saipen/STYLE.md) | [واجهة المستخدم](saipen/UI.md) | [الامتثال](saipen/CONFORMANCE.md) |MIT

**مفاتيح سريعة:** `cc` يواصل سياق المشروع إلى التقارب (يستأنف الهدف النشط إذا كان مضبوطًا)، `sss` يعرض الحالة دون لمس الكود، و`ss` يحفظ نقطة تحقق ويتوقف. [انظر خريطة المفاتيح الكاملة 19](saipen/RFC.md#110-command-surface). التوائم السيريلية تعمل أيضًا: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

```text
Project
  |
  +-- .saipen/STATE.md ------ what is happening right now (phase, ticket, mode, next_action)
  +-- .saipen/BOARD.md ------ what work exists (DOING / TODO / DONE / BLOCKED)
  +-- .saipen/LOG.md -------- why the project reached this state (event history)
  +-- .saipen/KNOWLEDGE/ ---- what durable facts must survive sessions
          |
          v
   /saipen continue
          |
          v
      cold agent
          |
          v
     next_action -> work -> checkpoint -> next ticket
```

## ما يبقى

توجد ذاكرة المشروع الحية في`.saipen/`— ملفات عادية يمكنك قراءتها، مقارنتها، و
تُقدّم التزامًا بجانب الكود. وكيل بارد يجيب عن خمسة أسئلة من الملفات
بشكل منفرد:

|الملف / الحقل|الإجابات|
|---|---|
| `STATE.md` |ما الذي يحدث الآن؟(المرحلة، التذكرة النشطة، وضع التشغيل، العائق) |
| `BOARD.md` |ما العمل الموجود / ما الذي نشط؟(مخطط التذاكر: DOING، TODO، DONE، BLOCKED) |
| `LOG.md` |لماذا وصل المشروع إلى هذا الحالة؟(مخطط الأحداث فقط إضافة) |
| `KNOWLEDGE/` |ما الحقائق الدائمة للمشروع التي يجب أن تبقى على قيد الحياة عبر الجلسات؟|
| `next_action` (في`STATE.md`) |ما هو الإجراء الدقيق الذي يجب أن ينفذه الوكيل التالي؟|

هذا عقد نقطة فحص، وليس اقتراح تصميم:`saipen stop`وكل
كتابة ملفات الانتقال في تسلسل ثابت، ويتم فحص النتيجة بواسطة
مُحقق. لا يتم تخزين أي شيء في قاعدة بيانات مُستضافة، ولا يُفقد أي شيء عندما
ينتهي الجلسة.

## البدء السريع

**1. قم بتثبيت مرة واحدة لكل جهاز**— يُعلّم Claude Code، Codex، Gemini، OpenCode،
Aider، Antigravity، وأي قارئ عام`~/.agents/skills`.reader(FreeBuff، إلخ.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`تمنع الكتلة إعطاء التعليمات للوكيل
الملفات التي تمتلكها بالفعل(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— إجراء نسخ احتياطي لها إلى`.bak`أولاً —
وتنسخ البروتوكول إلى مجلدات المهارات المناسبة. لا شيء خارج هذه المجلدات
المسارات، لا خادم، لا مكالمات الشبكة.</sub>

**2. ابدأ مشروعًا**— افتح وكيلًا في مجلدك، اكتب:

> `saipen set`

**لا تثبيت؟**لصق سطر واحد في أي وكيل:

> اقرأ&lt;клон&gt;/saipen/BOOT.md أولاً(نواة التشغيل البارد)، ثم&lt;клон&gt;/saipen/INDEX.md +&lt;клонировать&gt;/saipen/STYLE.md واتبعها.

**غيرت رأيك؟**أمر واحد يعيد ذلك:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

يُزيل بالضبط الكتلة المُشار إليها(مُحافظًا على بقية ملفك), يحفظ
a `.uninstalled.bak`قم بنسخه أولاً، ثم أزل مجلدات المهارات.

## لماذا لا نستخدم فقط تاريخ المحادثة؟

SAIPEN تستهدف فشلًا معينًا: وكيل ترميز ذكاء اصطناعي لا يتذكر شيئًا
بعد انتهاء الجلسة. الأدوات الأخرى والعادة تغطي جزءًا من هذه المشكلة:

|الطريقة|ما فائدته|ما لا يحمله|
|---|---|---|
|تاريخ المحادثة / ذاكرة النموذج|مريح، بدون إعدادات|يعتمد على الجلسة والمزود؛ لا يتم تخزينه مع المشروع، لذا لا يراه الوكيل البارد أبدًا|
|ثابت`AGENTS.md`ملف / تعليمات|قواعد ومبادئ ثابتة ومستمرة|لا يمثل من تلقاء نفسه حالة المهمة الحية،`next_action`, أو تاريخ الاستعادة|
|مُتبع / مُتبع TODO|إدارة المهام والمستودع|لا يحدد من تلقاء نفسه دلالات استمرار الوكيل — ما يجب على الوكيل البارد قراءته وإجراؤه عند استئنافه|
| **SAIPEN** |حالة التنفيذ الحية، قائمة المهام، تاريخ الأحداث، المعرف المتين، وقواعد الاستمرار المُدقَّقة بواسطة الآلة — في ملفات عادية بجانب الكود|لا شيء؛ تلك المجموعة هي العقدة|

الفرق ليس في أي ملف واحد. إنه أن SAIPEN هو الذي يجعل خطوة الاستئناف
قابلة للتحقق من قبل الآلة: الإجراء الأول الذي يجب على الوكيل البارد إجراؤه بعد`/saipen continue`هو
يتم تحديده بواسطة المُخزَّن`next_action`ويتم التحقق منه بواسطة مدقق، وليس
يتم إعادة بناؤه من الذاكرة.

## الدليل الهندسي

SAIPEN يقترن ببروتوكول عادي يُكتَب في ملفات عادية مع بروتوكول قابل للتنفيذ والمُوجَّه نحو الفشل
التحقق. يُظهر المستودع تصميم بروتوكول/آلة حالة، بايثون
أدوات، الحالة المُوجهة بواسطة المخطط، الاستدلال على الاستعادة، الاختبارات الرجعية،
حدود سلوك الوكلاء المتعددين، والانضباط في تحديد المعايير.

- **العقدة المُصممة.** [SPEC.md](SPEC.md)يحدد النموذج المدعوم بالملف
نموذج الاستمرارية والعقدة المستقرة على القرص؛[CORE.md](saipen/CORE.md)
و[MAINTENANCE.md](saipen/MAINTENANCE.md)يحدد السلوك الحالي المعياري.
- **الحالة المُدققة بواسطة الآلة.**النموذج القياسي الوحيد المخصص
  [التحقق من صحة البيانات](tools/validate.py)يقرأ النموذج الحي
  [للحالة](extensions/schemas/state.schema.json)ويتحقق من الانتقالات بين المراحل، والاعتماديات بين التذاكر، والروابط بين الأحداث، والروابط بين الوثائق المختلفة

الجوانب الثابتة، والقدرات، والوضعية الخاصة بالاستعادة.
- **تغطية الفشل.** [CONFORMANCE.md](saipen/CONFORMANCE.md)الخرائط
متطلبات إلى[مُعدات السيناريو](tests/scenarios/); الم
  [مُنفذ السيناريو](tools/run_scenarios.py)يُنفذ حالات الممرات الناجحة/المُستحيلة من الناحية الهيكلية
بما في ذلك حالات الاستعادة التالفة، الانتقالات غير الصالحة، الدورات التبعية، و
القيود المتعلقة بالقراءة فقط.
- **التحكم في التراجع.** [audit_checks.py](tools/audit_checks.py)يُغير
النسخ المعروفة بأنها جيدة ويُثبت أن فحوصات المُحقق يمكن أن تظل حمراء، بدلاً من
اعتبار الفحص الأخضر الدائم دليلاً.
- **الطبقة القابلة للتنفيذ.** [saipen.py](tools/saipen.py)يقدم حالة مسجلة
العمليات؛[bootstrap/](bootstrap/)يحتفظ بتثبيت، وإزالة تثبيت، وتصدير
المساعدات، مع خيار[مثيل ت钩 قبل التزام](tools/install_hook.py).
- **اختيارات واضحة.**الحالة الأساسية للبروتوكول هي ملفات عادية بدون وقت تشغيل
الاعتماد. التحقق القياسي والأدوات الطرفية تتطلب Python، ولكنها تستخدم فقط
مكتباتها القياسية ولا تحتاج إلى`pip`تثبيت.

## البنية

ثلاث طبقات، اعتماديات صارمة في الاتجاه الواحد:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

النواة لا تعتمد على الصيانة: مع تعطيل التطور المستقل، SAIPEN
ما زال بروتوكول استمرار كامل — وكيل بارد ما زال يعاود التشغيل.

- **آلة حالة النواة** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **الصيانة المستقلة**— اللوحة متوقفة(لا شيء قابل للتشغيل في`## TODO`,
لا شيء في`## DOING`)ولا`BLOCKED`? الانتقالات التلقائية`HUNT` (فحص الأخطاء)
  → `ADD` (تطوير الميزات) → `HUNT`, لم تطرح أي أسئلة. جلسة جلوس في
  `BLOCKED`لا تبحث تلقائيًا
  ([الصيانة § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **وضع الهدف** — `/saipen goal <objective>`تُقلب اللوحة وتُنفذ
الهدف إلى الأمام عبر VERIFY/REVIEW، مما يؤدي إلى الصيانة المستقلة
حتى تُنفَّذ قاعدة الإكمال أو تصل الجلسة إلى حدتها(3 موجات / 20 تذكرة،
ثم نقاط التفتيش والإبلاغ) ([الصيانة § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **تعزيز**— يتم تحليل المدخلات بالجملة إلى تذاكر فردية دقيقة
  (النواة § 1.8); يحتفظ استمرار شجرة الملفات الملوثة بالعمل غير المmitted(النواة § 1.5);
تُحذف القيم المتشابهة للسر من السجلات(`sk-***`) (النواة § 1.2).

## ال الأوامر الشائعة

نقاط الدخول اليومية؛ يعيش السطح الحالي الكامل في
[النواة § 1.10](saipen/CORE.md#110-command-surface).

|ال أمر|القيام|
|---|---|
| `/saipen set` |تبنى مشروعًا: إنشاء`.saipen/`الحالة|
| `/saipen continue` |استأنف من الحالة المحفوظة للمشروع — لا إعادة توجيه|
| `/saipen plan` |تحويل طلب أو قائمة مهام خام إلى تذاكر|
| `/saipen goal <text>` |تنفيذ موجة مستقلة ضد هدف جديد|
| `/saipen validate` |تشغيل فحوصات التوافق|
| `/saipen status` |تقرير فقط: المرحلة، التذاكر، العوائق، التقادم|
| `/saipen stop` |الاستراحة والتوقيف|

<details>
<summary><b>More commands</b></summary>

|ال명령|القيام|
|---|---|
| `/saipen hunt` |إجبار مسح العيوب/التحسينات الآن|
| `/saipen markhunt` |مراجعة جافة غير محدودة — تسجل النتائج، ولا تصلح شيئًا|
| `/saipen ship` |البوابات الخاصة بالإطلاق؛ التزام، تسمية، ودفع عندما يسمح بذلك|
| `/saipen clean` |اللوحة وتنظيف الحالة|
| `/saipen translate` |مصنع ترجمة معزول|
| `/saipen prepare` / `/saipen collect` |عمل الحزمة للتسليم / دمج حزمة جاهزة|
| `/saipen test` |تشغيل مجموعة الاختبارات المعلنة، وتقديم تقارير فقط|
| `/saipen crew` |دورة الطاقم بترتيب ثابت(الصيد → الإعادة → الاستيعاب → البناء → الترجمة → الوثيقة → الشحن) |
| `/saipen improve` |مراجعة ميتا-التحكم في تحسينات البروتوكول|
| `/saipen sub ...` |إطلاق / اعتماد وكلاء فرعيين قراءة فقط|

**مفاتيح الحزمة.** `ee`/`qq`تحضير حزم ترجمة/ويكي كاملة دون
دمج؛`eee`/`qqq`تقبل فقط الحزم الجاهزة، ثم دمجها، وتحقق منها،
وتمهلها، وابددها.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)يمرّ عبر كل
النظام الأساسي للطاقم بترتيب ثابت — المستشعرات(saihunt، saitest، saipython، saiui),
المُنتجين(saitranslate، saiwiki)و Core كالمُحرّك الوحيد للشجرة الرئيسية —
حتى تتم إجراء ممرّ جديد لا يترك أي شيء حقيقي ليتغير. فإنه يضيف بالضبط واحدًا
آلية خاصة به: الهدف المُنظم المستقر(`execution_intent:
يتوافق` with `converge_target: crew`)التي تجعل الدائرة قابلة للاستئناف و
قابلة للتحقيق من الأدلة.`saipen crew --dry-run --json`تستنتج
الدائرة قراءة فقط;`bootstrap/saipen_crew.*`هو مساعدة يدوية اختيارية
متعددة النوافذ، وليس ما`saipen crew`يعني. راجع
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## ما ليس SAIPEN

- **نموذج LLM أو نموذج**— إنه بروتوكول يتبعه الوكلاء، وليس ذكاءً.
- **IDE أو قاعدة بيانات ذاكرة مُستضافة**— الحالة هي ملفات عادية في مشروعك؛
لا شيء يتم استضافته.
- **استبدال لـ Git**— لا يزال Git يملك تاريخ الإصدار؛ احفظ التزامك
  `.saipen/`مثل أي كود آخر.
- **التوافق الموزع**— راجع الحد من التزامن أدناه.
- **ضمان أن نموذج لغة كبير سيتخذ قراراته الهندسية بشكل صحيح**— فإنه
يقلل من فقدان السياق والانحراف السلوكية؛ فإنه لا يجعل الوكلاء العشوائية
خالية من الأخطاء.

مهمة SAIPEN هي استمرار/عقد الحالة بالإضافة إلى التحقق من الصحة والأدوات —
تقديم نقطة البداية التي تم فحصها آليًا للوكيل التالي، وليس سحرًا.

**حدود التزامن.**تغييرات الحالة المُسجَّلة(SAIOPS)استخدم
قفل نظام التشغيل المخصص للمشروع ودفتر الأستاذ للتعافي([OPS § 5](saipen/OPS.md#5-locks)).
التعديلات العادية للمشروع والكتّاب غير المتصلين خارج هذا القفل. SAIPEN
ليست اتفاقية توزيعية، لذا يتطلب الكتّاب غير المتصلين تنسيقًا خارجيًا
تنسيق([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## البيئة

|المشروع|العلاقة مع SAIPEN|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |مركز تحكم محلي لنظام ويندوز لمشاريع SAIPEN — يكتشف تلقائيًا`.saipen/`المساحات، ويعرض الحالة الحية والنتائج المطابقة، ويدير التذاكر، ويطلق واجهات سطر الأوامر الذكية. مرفق، وليس الجهة المُقررة.|
| [SAIWORK](https://github.com/vacterro/saiwork) |فرع CodeNomad المُعدّل للاستخدام في المراحل اللاحقة والذي يدمج SAIPEN: يُحقّق`BOOT.md`/`STYLE.md`في بدء تشغيل OpenCode، ويعرض اختصارات SAIPEN وعرض حالة المشروع، ويضيف قائمة طوابير المطالبات المستمرة.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |لوحة مسحوق ويندوز قابلة الحمل التي تكتشف تلقائيًا`.saipen/`المجلدات وتضيف مُشاهد قراءة فقط لـ STATE/BOARD/LOG.|

## التوثيق

|وثيقة|ما هو|
|---|---|
| [SPEC.md](SPEC.md) |العمارة الرسمية، والأهداف التصميمية، والاختبار المبدئي|
| [CORE.md](saipen/CORE.md) |الاستمرارية التوجيهية، وآلة الحالة، وعقدة الأوامر|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |الصيانة المستقلة والوضع الهدف|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |المتطلبات القابلة للتنفيذ/السلوكية وقواعد المدقق|
| [GUIDE.md](GUIDE.md) |دليل بشري|
| [RFC.md](saipen/RFC.md) |تحويل التوافق إلى الوثائق المعيارية المفصولة|
| [STYLE.md](saipen/STYLE.md) |أسلوب وصوت اتصال الوكيل|
| [UI.md](saipen/UI.md) |موجز التصميم الموجز لواجهة المستخدم القديمة الذهبية|
|مجلة|مجلة عرض —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [الإنجليزية](guides/GUIDE_EN.md) · 🇪🇪 [الإستونية](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [الألمانية](guides/GUIDE_DE.md) · 🇫🇷 [الفرنسية](guides/GUIDE_FR.md) · 🇪🇸 [الإسبانية](guides/GUIDE_ES.md) · 🇮🇹 [الإيطالية](guides/GUIDE_IT.md)

🇵🇹 [البرتغالية](guides/GUIDE_PT.md) · 🇳🇱 [الهولندية](guides/GUIDE_NL.md) · 🇵🇱 [البولندية](guides/GUIDE_PL.md) · 🇸🇪 [السويدية](guides/GUIDE_SV.md) · 🇩🇰 [الدانماركية](guides/GUIDE_DA.md)

🇫🇮 [الفنلندية](guides/GUIDE_FI.md) · 🇳🇴 [النرويجية](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [الفيتنامية](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [التركية](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [الإندونيسية](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [التشيكية](guides/GUIDE_CS.md) · 🇷🇴 [الرومانية](guides/GUIDE_RO.md) · 🇭🇺 [المجرية](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [السلوفاكية](guides/GUIDE_SK.md) · 🇭🇷 [الكرواتية](guides/GUIDE_HR.md)

</details>

## ملاحظات التكوين

**لغة الرد.**يرد الوكيل باللغة**الإستونية**افتراضيًا — أي أن هذا هو
إعداد، وليس متطلبًا بروتوكوليًا، ولا شيء آخر في SAIPEN باللغة الإستونية.
البروتوكول، والكود، وال커밋ات وكل الوثائق تبقى باللغة الإنجليزية في كل
قيمة. قم بتغييرها في مكان واحد: السطر`reply_language:`في الأعلى من
[`saipen/STYLE.md`](saipen/STYLE.md). `et`الإستونية،`en`الإنجليزية،`ru`الروسية،
`auto`يختار من الرسالة التي أرسلتها.

**المحولات.**منصة غير مغطاة من قبل المحقن(DeepSeek، Qwen، مستقلة
OpenAI، وغيرها)? ملاحظات منصة محددة توجد في`extensions/adapters/`.

## 截屏

<details>
<summary><b>Click to expand</b></summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- translation-model: qwen3:14b contract:structured-markdown-v2 -->
<!-- source-digest: README.md sha256:bb47f7158db4a7a4fd99298427c1e4bc6859433c36435640e129cc6dad2a63b7 -->
