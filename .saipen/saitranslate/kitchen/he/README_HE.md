<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="לוגו SAIPEN"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="סטיקר SAIPEN" width="200"/>
</p>

# SAIPEN

**פרוטוקול המשכיות עבור סוכני קידוד AI.** זיכרון פרויקט מבוסס Markdown פשוט, כך שסוכן "קר" ללא היסטוריית צ'אט מריץ `/saipen continue` וממשיך בעבודה תוך פחות מדקה -- ללא תדרוך מחדש, כל ספק, כל יום.

**פקודה אחת. אפס אמנזיה.**

**v7.86.0** | [מפרט](SPEC.md) | [מדריך](GUIDE.md) | [RFC](saipen/RFC.md) | [סגנון](saipen/STYLE.md) | [ממשק משתמש](saipen/UI.md) | [תאימות](saipen/CONFORMANCE.md) | markdown פשוט | אפס תלויות | MIT

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Eesti Guide](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Japanese Guide](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Ded Voice](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
משתמש  ->  /saipen continue
סוכן    ->  קורא את STATE ("מה אני עושה כרגע?")
סוכן    ->  קורא את BOARD ("איזו משימה אני לוקח?")
סוכן    ->  קורא את next_action (מבצע פקודה)
סוכן    ->  עובד.
```

### מצב פרויקט > זיכרון מודל
הזיכרון שוכן בפרויקט, לא בראש של המודל. `פרויקט -> זיכרון -> LLM` הופך ל-`פרויקט -> מצב SAIPEN -> LLM`.

### לוגיקה מרכזית והבטחות הפרוטוקול
- **מכונת מצבים מרכזית**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **אוטונומיה ללא הנחיות (Zero-Prompt Autonomy)**: לא נותרו משימות פתוחות? מעבר אוטומטי למעגל `HUNT` (סריקת באגים) ← `ADD` (פיתוח תכונות) ← `HUNT`. אפס שאלות.
- **טריגרים מפורשים**: `/saipen clean` (ניקוי מאגר), `/saipen translate` (מפעל `.saipen/saitranslate/` מבודד), `/saipen markhunt` (ביקורת יבשה ללא הגבלה, רישום בלבד), `/saipen prepare` (אריזת עבודה להעברה), `/saipen validate` (בדיקת תאימות), `/saipen goal` (הרצת גל אוטונומית). מטא/שליטה: `/saipen status` (דוח לקריאה בלבד), `/saipen stop` (נקודת ביקורת ועצירה). רשימה מלאה: RFC.md § 1.10.
- **אמינות מחמירה**: ניתוח קלט באצ'ים (כרטיסים כירורגיים אחד-אחד), אימוץ עץ מלוכלך (לעולם לא מוחק עבודה שלא נשמרה ב-commit), הסתרת סודות (`sk-***`).

## פרויקטים המופעלים על ידי SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — כלי ניהול פרומפטים בביצועים גבוהים המשולב טבעית עם פרוטוקול הזיכרון של SAIPEN.

## שתי שכבות

| שכבה | חובה | מטרה |
|---|---|---|
| **Core** | ✅ | המשך עבודה בבטחה |
| **Maintenance** | מעל Core | פיתוח התוכנה ללא משימות מפורשות |

**אבולוציה אוטומטית.** לא נותרו משימות פתוחות, הקלד `/saipen`: `HUNT` מבצע ביקורת עבור באגים, קוד מת, ובדיקות שנכשלו. נקי? `ADD` בונה את היכולת החסרה הבאה, מאמת אותה, ומבצע ביקורת שוב. המוצר בוגר -> נעצר בצורה מסודרת.

**מצב GOAL.** `/saipen goal <מה שאתה רוצה>` משנה את לוח המשימות (כרטיסים ישנים מועברים לדירוג נמוך יותר, לעולם לא נמחקים) ומריץ את היעד החדש קדימה -- ללא "האם להמשיך?" בין כרטיסים, VERIFY/REVIEW לעולם לא מדולגים. SHIP מבצע auto-push ל-remote קיים; מאגר חדש לגמרי עדיין שואל פעם אחת. שילוח היעד אינו נקודת העצירה -- הוא עובר ישירות לתחזוקת HUNT/ADD אוטונומית עד שהמוצר בוגר, חסום, או שההרצה מגיעה למגבלה שלה (3 גלים / 20 כרטיסים, ואז שמירת נקודת ביקורת ודיווח).

## התחלה מהירה

**1. התקנה חד-פעמית למחשב** -- מלמד את Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex ??? ???? ???? ?? ~/.agents/skills (FreeBuff ???'):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. התחלת פרויקט** -- פתח סוכן בתיקייה שלך, הקלד:
> `saipen set`

אין התקנה? הדבק שורה אחת לכל סוכן:
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

הפלטפורמה שלך אינה ברשימה לעיל (DeepSeek, Qwen, OpenAI עצמאי וכו')?
הערות עבור כל פלטפורמה נמצאות ב-`extensions/adapters/`.

## קישורים לתיעוד ומפרטים
- **[SPEC.md](SPEC.md)** -- ארכיטקטורה רשמית, יעדי עיצוב, מבחן לקמוס.
- **[RFC.md](saipen/RFC.md)** -- מפרט נורמטיבי המבוצע על ידי סוכנים.
- **[GUIDE.md](GUIDE.md)** -- מדריך למשתמש ומדריכי ELI5:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- סגנון תקשורת והגדרת קול של הסוכן.
- **[UI.md](saipen/UI.md)** -- הנחיות עיצוב ממשק משתמש Dark Golden Win95.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- תרחישי בדיקת התנהגות וכללי מאמת.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="חותמת SAIPEN" width="120"/>
</p>


