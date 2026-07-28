<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# دليل SAIPEN (العربية)

SAIPEN هو دفتر ملاحظات في مجلد `.saipen/` لوكلاء الذكاء الاصطناعي.

## البداية السريعة

1. **التثبيت مرة واحدة لكل جهاز:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **بدء المشروع:**
> `saipen set`

3. **العمل:**
> `saipen`

## الأوامر

| الأمر | الإجراء |
|---|---|
| `saipen set` | تهيئة مجلد الذاكرة `.saipen/` |
| `saipen continue` | استئناف العمل من الملاحظات |
| `saipen stop` | حفظ التقدم والتوقف |
| `saipen status` | قراءة اللوحة والحالة |
| `saipen goal <text>` | التحول إلى هدف جديد |
| `saipen clean` | تنظيف عميق للمستودع |
| `saipen translate` | بناء ترجمة معزول بـ 32 لغة |
| `saipen markhunt` | تدقيق عميق وغير محدود -- يسجل النتائج فقط دون إصلاح |
| `saipen prepare` | تجميع العمل لتسليمه إلى الوكيل التالي |
| `saipen ship` | بدء تدفق الإصدار |

## من الجيد معرفته
- تغييرات غير مُلتزم بها عند العودة إلى المشروع؟ هذا طبيعي -- SAIPEN يلتزم فقط عند `ship`، وليس في كل خطوة. يتحقق الوكيل أولاً من صاحب هذه التغييرات قبل لمس أي شيء.
- تريده أن يتذكر قرارًا معماريًا حقيقيًا؟ ضعه في `.saipen/KNOWLEDGE/`، إما كملف `decisions.md` أو كملفات مرقمة `ADR-001.md`.
- لا يوجد git أو shell على هذا الجهاز؟ يقول الوكيل ذلك بوضوح (`mode`، `WAIT: <category> -- <سؤال>`) بدلاً من التخمين.
- تريد شبكة أمان؟ `python <نسخة-saipen>/tools/install_hook.py` يثبّت فحصًا قبل كل التزام.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
