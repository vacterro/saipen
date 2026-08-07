<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# دليل SAIPEN (العربية)

[TRANSLATED AR]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

## البداية السريعة

## الأوامر

## من الجيد معرفته
- تغييرات غير مُلتزم بها عند العودة إلى المشروع؟ هذا طبيعي -- SAIPEN يلتزم فقط عند `ship`، وليس في كل خطوة. يتحقق الوكيل أولاً من صاحب هذه التغييرات قبل لمس أي شيء.
- تريده أن يتذكر قرارًا معماريًا حقيقيًا؟ ضعه في `.saipen/KNOWLEDGE/`، إما كملف `decisions.md` أو كملفات مرقمة `ADR-001.md`.
- لا يوجد git أو shell على هذا الجهاز؟ يقول الوكيل ذلك بوضوح (`mode`، `WAIT: <category> -- <سؤال>`) بدلاً من التخمين (الفئة هي واحدة من سبع: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`؛ وتوضح نوع الإجابة المطلوبة لإزالة التعليق)
- تريد شبكة أمان؟ `python <نسخة-saipen>/tools/install_hook.py` يثبّت فحصًا قبل كل التزام.