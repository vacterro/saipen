<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**بروتوكول الاستمرارية لوكلاء البرمجة بالذكاء الاصطناعي.** ذاكرة مشروع دائمة بنص بسيط (markdown)، بحيث يستطيع وكيل جديد بدون سجل محادثات تشغيل `/saipen continue` واستئناف العمل في أقل من دقيقة -- دون إعادة شرح، مع أي مزود، في أي يوم.

**أمر واحد. صفر فقدان للذاكرة.**

**مفاتيح سريعة:** `cc` يواصل سياق المشروع إلى التقارب (يستأنف الهدف النشط إذا كان مضبوطًا)، `sss` يعرض الحالة دون لمس الكود، و`ss` يحفظ نقطة تحقق ويتوقف. [انظر خريطة المفاتيح الكاملة 15](saipen/RFC.md#110-command-surface). التوائم السيريلية تعمل أيضًا: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**لغة الرد.** يرد الوكيل افتراضيًا **باللغة الإستونية** — هذه إعدادات، وليست نزوة، ولا شيء آخر في SAIPEN باللغة الإستونية. غيّرها في مكان واحد: سطر `reply_language:` في أعلى [`saipen/STYLE.md`](saipen/STYLE.md). `et` الإستونية، `en` الإنجليزية، `ru` الروسية، `auto` تختار حسب لغة رسالتك. يبقى البروتوكول والكود والالتزامات وكل الوثائق بالإنجليزية مهما كانت القيمة.

**v7.223.16** | [المواصفات](SPEC.md) | [الدليل](GUIDE.md) | [RFC](saipen/RFC.md) | [الأسلوب](saipen/STYLE.md) | [واجهة المستخدم](saipen/UI.md) | [التطابق](saipen/CONFORMANCE.md) | markdown بسيط | صفر تبعيات | MIT

```text

### حالة المشروع > ذاكرة النموذج

الذاكرة تعيش في المشروع، وليس في رأس النموذج. تتحول `المشروع -> الذاكرة -> LLM` إلى `المشروع -> حالة SAIPEN -> LLM`.


## Commands

The full surface is 16 commands; complete details in [RFC § 1.10](saipen/RFC.md#110-command-surface).

| Command | What it does |
|---|---|
| `/saipen set` | Adopt a project |
| `/saipen continue` | Resume exactly where you left off |
| `/saipen plan` | Turn a request or raw queue into tickets |
| `/saipen goal <text>` | Autonomous wave assault on a new objective |
| `/saipen hunt` | Force an immediate defect/improvement scan |
| `/saipen ship` | Version bump, changelog, tag, push |
| `/saipen clean` | Repository cleanup |
| `/saipen validate` | Conformance check |
| `/saipen markhunt` | Dry uncapped audit, record only |
| `/saipen translate` | Isolated translation factory |
| `/saipen prepare` | Package work for handoff |
| `/saipen collect` | Integrate a ready package |
| `/saipen status` | Read-only report |
| `/saipen stop` | Checkpoint and halt |

<sub>`saipen init` and `saipen sub` complete the sixteen; both are called by the protocol, not typed daily.</sub>

**Package keys.** `ee`/`qq` prepare a complete translation or wiki package without integrating; `eee`/`qqq` accept only a ready package, then integrate, verify, review, and push.

**Experimental: saicrew.** Optional bonus layer (`extensions/subs/`, zero Core changes) for running a multi-agent crew — one Core writer plus read-only `saihunt`/`saipython` workers reporting through their own `OUTBOX.md`. Under active live testing, not finalised — see `extensions/subs/crew.md`.

## Two layers


| الطبقة | مطلوبة | الغرض |
|---|---|---|
| **الأساسية (Core)** | ✅ | استئناف العمل بأمان |
| **الصيانة (Maintenance)** | فوق الأساسية | تطوير البرمجيات دون توجيه مهام |

**التطور المؤتمت.** لا توجد مهام مفتوحة، اكتب `/saipen`: تقوم `HUNT` بتدقيق الأخطاء، الكود الميت، والاختبارات الفاشلة. المستودع نظيف؟ تقوم `ADD` ببناء الميزة التالية المفقودة، وتتحقق منها، ثم تعود لـ `HUNT`. المنتج ناضج -> يتوقف بسلاسة.

**وضع الهدف (GOAL Mode).** يقوم `/saipen goal <ما تريده>` بتغيير اتجاه اللوحة (تخفيض أولوية التذاكر القديمة، دون حذفها) والدفع بالهدف الجديد للأمام -- لا أسئلة "هل أستمر؟" بين التذاكر، ولا يتم تخطي VERIFY/REVIEW أبداً. ينفذ SHIP الدفع التلقائي للمستودع البعيد الموجود؛ والمستودع الجديد كليًا يسأل مرة واحدة فقط. شحن الهدف ليس نقطة النهاية أيضاً -- بل ينتقل مباشرة إلى صيانة HUNT/ADD المستقلة حتى ينضج المنتج أو يُحظر أو تصل الدورة إلى حدها الأقصى (3 موجات / 20 تذكرة، ثم يحفظ نقطة التوقف ويصدر تقريراً).


## Quick Start


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
> اقرأ <clone>/saipen/INDEX.md + <clone>/saipen/STYLE.md واتبعهما.

المنصة ليست في القائمة أعلاه (DeepSeek, Qwen, standalone OpenAI, إلخ)؟
توجد ملاحظات كل منصة في `extensions/adapters/`.


## Documentation

| Document | What it is |
|---|---|
| [SPEC.md](SPEC.md) | Formal architecture, design goals, litmus test |
| [RFC.md](saipen/RFC.md) | Normative specification agents execute |
| [GUIDE.md](GUIDE.md) | Human tutor and ELI5 guides |
| [STYLE.md](saipen/STYLE.md) | Agent communication style and voice definition |
| [UI.md](saipen/UI.md) | Vintage Golden UI design guidelines |
| [CONFORMANCE.md](saipen/CONFORMANCE.md) | Behavioural test scenarios and validator rules |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [English](guides/GUIDE_EN.md) · 🇪🇪 [Eesti](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Deutsch](guides/GUIDE_DE.md) · 🇫🇷 [Français](guides/GUIDE_FR.md) · 🇪🇸 [Español](guides/GUIDE_ES.md) · 🇮🇹 [Italiano](guides/GUIDE_IT.md)

🇵🇹 [Português](guides/GUIDE_PT.md) · 🇳🇱 [Nederlands](guides/GUIDE_NL.md) · 🇵🇱 [Polski](guides/GUIDE_PL.md) · 🇸🇪 [Svenska](guides/GUIDE_SV.md) · 🇩🇰 [Dansk](guides/GUIDE_DA.md)

🇫🇮 [Suomi](guides/GUIDE_FI.md) · 🇳🇴 [Norsk](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Türkçe](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Čeština](guides/GUIDE_CS.md) · 🇷🇴 [Română](guides/GUIDE_RO.md) · 🇭🇺 [Magyar](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) · 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)

</details>

## Built with SAIPEN

- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — High-performance prompt management tool built natively around the SAIPEN memory protocol.

## Screenshots

<details>
<summary>Click to expand</summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- source-digest: README.md sha256:7550073ecb7103b2b34a8a8214fb35b3daddfc5bddb641691f1355e40cf8cc7f -->


