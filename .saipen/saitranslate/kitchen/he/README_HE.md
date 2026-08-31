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

**פרוטוקול המשך עבור אגנטים של קוד א.י.**זיכרון פרויקט מחייה ב파ין
파ין קבצי markdown בתוך הפרויקט(`.saipen/`), לכן כל אגנט קריר תואם —
ללא היסטוריית שיח, ללא זיכרון של סשן — יכול לרוץ`/saipen continue`, לקרוא את
הנקייה`next_action`, ולcontinuation את העבודה ללא צורך לבקש מהמשתמש להסביר מחדש
כלום. מצב שייך לפרויקט, לא לזכרון של ספק מודל אחד.

**명령 אחד כדי להמשיך. מצב קובץ פלן. חוזרים על בדיקה של מכונה.**

הרепוזיטורי מאשש את עצמו בכל push; התקנה, מצב, בדיקות, ו
הסרה כוללת רק קבצים מקומיים — אין שירות ענן, אין ד몬, אין מסד נתונים.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.233.1** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [Core](saipen/CORE.md) | [Maintenance](saipen/MAINTENANCE.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) |MIT

**מקשים מהירים:** `cc` ממשיך את ההקשר של הפרויקט עד להתכנסות (מחדש יעד פעיל אם הוגדר), `sss` מציג סטטוס ללא נגיעה בקוד ו-`ss` שומר נקודת ביקורת ועוצר. [ראה את מפת 19 המקשים המלאה](saipen/RFC.md#110-command-surface). גם התאומים הקיריליים עובדים: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

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

## מה נשאר

זיכרון פרויקט חי נמצא ב-`.saipen/`— קבצים פשוטים שתוכלו לקרוא, להבדיל ולהשוות, ו
לעשות commit לציד הקוד. אגנט קר יענה לשאלות חמש מהקבצים
בשלב זה:

|קובץ / שדה|תשובות|
|---|---|
| `STATE.md` |מה קורה כרגע?(שלב, כרטיס פעיל, מצב הפעלה, חסימה) |
| `BOARD.md` |מה עבודה קיימת / מה פעילה?(גרף כרטיסים: DOING, TODO, DONE, BLOCKED) |
| `LOG.md` |למה הפרויקט הגיע למצב זה?(גרף sự kiện שרק מוסיפים לו) |
| `KNOWLEDGE/` |מה עובדות הפרויקט הנצברות חייבות לשרוד בין סשנים?|
| `next_action` (ב-`STATE.md`) |מה פעולה מדויקת צריך האגנט הבא לבצע?|

זה חוזה נקודת בדיקה, לא הצעת תכנון:`saipen stop`וגם כל
מעבר כרטיס – כתבו את הקבצים בترتيب קבוע, והผล נבדק על ידי
валиדטור. noting is stored in a hosted database, and nothing is lost when a
השגרה נגמרת.

## התחלה מהירה

**1. התקן פעם אחת למחשב**— מלמד את קלוד קוד, קדקס, ג'מייני, אופנקוד,
איידר, אנטי גרביטי, וכל קריאה כללית`~/.agents/skills`.reader(פריבופ, וכו'"):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`בלוק לפקודה של האגנט
파일들 שברשותคุณ(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— גיבוי כל אחד מהם ל-`.bak`ראשון —
ומעתיק את הפרוטוקול לflders של היכולות המתאימות. כלום מחוץ לאותם flders
مسارات, ללא ד몬, ללא קריאות רשת.</sub>

**2. התחילה פרויקט**— פתח אגנט בתיקייה שלך, הקלד:

> `saipen set`

**ללא התקנה?**הדבק שורה אחת לאגנט כלשהו:

> קרא&lt;клон&gt;/saipen/BOOT.md ראשית(גרעין התחלה קרירה), ואז&lt;клон&gt;/saipen/INDEX.md +&lt;клон&gt;/saipen/STYLE.md ותתאם לעדכון.

**измינה את דעתך?**פקודה אחת מחזירה אותו:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

היא מסירה בדיוק את בלוק המבוקש(ותставה את שארית הקובץ ללא שינוי), שומרת
a `.uninstalled.bak`עושה עתק ראשוני, ומוחקת את תיקיות היכולות.

## למה לא רק היסטוריית השיחה?

SAIPEN מכוון לתקלה ספציפית: אגנט תיכנות אינטלייגנטית שמשחזרת כלום
לאחר שהсеанс נגמר. כלים וعادة אחרים מכסים חלק מהבעיה הזו:

|גישה|למה הוא טוב|מה שהוא לא נושא|
|---|---|---|
|تاريخ השיחה / זיכרון המודל|נוח, ללא התקנה|תלוי ב세션 ובמוכר; לא מאוחסן עם הפרויקט, כך שסוכן קר לעולם לא יראה אותו|
|tĩnh`AGENTS.md`קובץ / פקודה|חוקים ומוסדות נאמנים|לא מייצג בעצמו את מצב המשימה האקטיבי`next_action`, או היסטוריה של שחזור|
|מעקב אחר בעיה / TODO|ניהול משימות ורשימת ציפיות|אינו מגדיר בעצמו את סמנטיקת המשך הפעולה של האגנט — מה שהагент הקרה חייב לקרוא ולהתבצע עליו בעת המשכה|
| **SAIPEN** |מצב ביצוע חי, קבוצת עבודה, היסטוריית אירועים, ידע נצחי, וחוקי המשך מותרים שנבדקים על ידי מכונה — בקבצים פשוטים לצידם של הקוד|א ничего; sự kết hợp đó là hợp đồng|

ההבדל אינו קובץ אחד. הוא בכך ש-SAIPEN מבצע את שלב המשכה
ניתן לבדוק על ידי מכונה: הפעולה הראשונה של אגנט קריר לאחר`/saipen continue`היא
מכתوبة על ידי`next_action`ומאושרט על ידי וריפיקטור, לא
מבוססת על זיכרון.

## הוכחות הנדסיות

SAIPEN משלב פרוטוקול פשוט-파일 נורמטיבי עם ביצוע, מכוון לفشل
בדיקות. הרепозיטורי ממחיש תכנון פרוטוקול/מchine-מchine, פיתון
أدوات, מצב מונחה-סכמה, חשיבה לשיקום, בדיקות רגרסיה,
גבולות זרימה רב-agenta, ותכלית תיאורית.

- **תת-הסכמה שנבנה.** [SPEC.md](SPEC.md)מגדיר את המודל המשותף-
המודל המשותף והתת-הסכמה היציבה על-הדיסק;[CORE.md](saipen/CORE.md)
ו-[MAINTENANCE.md](saipen/MAINTENANCE.md)מגדירים את ההתנהגות הנורמטיבית הנוכחית.
- **מצב שהודגם על-ידי מכונה.**התקן ה-stdlib בלבד
  [валиדטור](tools/validate.py)מקריא את הסכמת המצב האמיתית
  [מבחין במעבר של שלבים](extensions/schemas/state.schema.json)תלויות של כרטיסי תקציב
קישורים בגרף של אירועים
לאינvariants, יכולויות, וحالة השיקום
- **תغطية כשלונות** [CONFORMANCE.md](saipen/CONFORMANCE.md)מפת
דרישות ל[מצבים של סценריוס](tests/scenarios/); the
  [מפעיל סценריוס](tools/run_scenarios.py)מבצע מקרי בדיקה של הצלחה/실패 מבנית
הכוללים מצב שיקום פגום, מעבר לא חוקי, מעגלי תלות, ו
הגבלות קריאה בלבד.
- **kiểm soát רגרסיה.** [audit_checks.py](tools/audit_checks.py)משנה
עותקים ידועים-טובים ומדגים שבדיקות הווידאטור עדיין יכולות להראות אדומות, במקום
להתייחס לבדיקה תמיד אדומה כהוכחה.
- **שכבת ביצוע.** [saipen.py](tools/saipen.py)ממשיכת מצב יומני
פעולות;[bootstrap/](bootstrap/)מאחסן התקנה, הסרת התקנה, ויצוא
עזרות, עם אפשרות[ติดตั้ง hook של pre-commit](tools/install_hook.py).
- **הערכות מפורשות.**מצב פרוטוקול 핵심 הוא קבצים רגילים ללא תלויה ריצה
תלויה. אימות канוני וเครื่องมือ CLI דורשים פיתון, אך משתמשים רק
ב ספרייה הסטנדרטית שלו ואינם דורשים`pip`התקנה.

## 架構

שלש שכבות, תלויות אحادיות строго:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

הגרעין לא תלוי בתחזוקה: עם תחזוקה עצמית מוגבלת, SAIPEN
עדיין פרוטוקול המשך שלם — אגנט קר עדיין ממשיך.

- **מchine מצב גרעין** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **תחזוקה עצמית**— לוח מושבת(ללא כל מה ניתן לעבוד ב-`## TODO`,
ללא כל شيء ב-`## DOING`)ולא`BLOCKED`? מעבר אוטומטי`HUNT` (סריקת באגים)
  → `ADD` (развитие תכונות) → `HUNT`, שאלות אפס wurden. ישוש מושב ב
  `BLOCKED`לעולם לא מתחזק אוטומטית
  ([תחזוקה § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **מצב מטרה** — `/saipen goal <objective>`מחלף את הלוח ורץ את
המטרה קדימה דרך VERIFY/REVIEW, נופל לתחזוקה אוטומטית
עד שהחוק להשלמת תהליך יתבצע או שהריצה תגיע לקיבולת שלה(3 גלגלים / 20 כרטיסים,
ואז נקודות בדיקה ומדווח) ([תחזוקה § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **חיזוק**— קלט ב大批 הוא מפורס לכניסות כרטיסים אינדיבידואליים
  (CORE § 1.8); המשך העץ הלא נקי שומר על עבודה לא מmitted(CORE § 1.5);
ערכים דומים לسر נמחקים מהיומן(`sk-***`) (CORE § 1.2).

## פקודות נפוצות

כניסות נפוצות ליום; פנייה נוכחית מלאה נמצאת ב
[CORE § 1.10](saipen/CORE.md#110-command-surface).

|פקודה|מבצע|
|---|---|
| `/saipen set` |קבלת פרויקט: יוצר`.saipen/`מצב|
| `/saipen continue` |استمر מהحالة המותאמת של הפרויקט — ללא שיקום מחדש|
| `/saipen plan` |המר תביעה או רשימת מטלות ראשונית למסמכים|
| `/saipen goal <text>` |ביצוע גל אוטונומי נגד מטרה חדשה|
| `/saipen validate` |הרץ בדיקות התאמה|
| `/saipen status` |תقرיר לקריאה בלבד: שלב, מסמכים, מכשולים, קירירות|
| `/saipen stop` |จุด ביקורת ועצירה|

<details>
<summary><b>More commands</b></summary>

|명령|합니다|
|---|---|
| `/saipen hunt` |החל את סריקת הפגמים/ה향יקות כעת בכוח|
| `/saipen markhunt` |תчетה יבש ללא הגבלת גובה — מקליטה תוצאות, לא מתקן כלום|
| `/saipen ship` |שערי פלט; בצע התחייבות, תג ושלח כאשר מותר|
| `/saipen clean` |לוח וניקיון מצב|
| `/saipen translate` |מפעל תרגום מבודד|
| `/saipen prepare` / `/saipen collect` |עבודת חבילות למסירה / אינטגרציה של חבילת מוכנה|
| `/saipen test` |הרץ את סדרת הבדיקות המוצהרת, דיווח רק|
| `/saipen crew` |מעגל צוות בקביעות(הunted → תרבות → קבלה → בנייה → תרגום → מסמך → שילוח) |
| `/saipen improve` |תיעוד של ביקורת מטת של שיפורים בפרוטוקול|
| `/saipen sub ...` |יצירת/אימוץ של סוב-agenta לקריאה בלבד|

**מפתחות חבילות.** `ee`/`qq`הכנה של חבילות תרגום/ויקי שלמות ללא
אינטגרציה;`eee`/`qqq`קבלת רק חבילות מוכנות, ואז אינטגרציה, בדיקה,
תיעוד, והעלאה.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)מתקדם בכל
הצוות הפנימי בترتيب קבוע — חיישנים(saihunt, saitest, saipython, saiui),
מפיקים(saitranslate, saiwiki)ו-Core ככותב העץ הראשי היחיד —
עד שמעבר נוסף לא ימצא שום דבר אמיתי להשתנות. הוא מוסיף בדיוק אחד
กลไก שלו собственный: המטרה האורגניזציה המחזיקה(`execution_intent:
сходиться` with `converge_target: crew`)שעושה את המעגל ניתן להחזרה ו
ניתן להסיק ממנו מתוך ראיות.`saipen crew --dry-run --json`מפיק את
המעגל לקריאה בלבד;`bootstrap/saipen_crew.*`הוא עזרה ידנית חובה
לחלון מרובה חלונות, לעולם לא מה`saipen crew`озן. ראה
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## מה שאינן SAIPEN

- **LLM או מודל**— זהו פרוטוקול שסוכנים עוקבים אחריו, לא חוכמה.
- **IDE או מסד נתונים מארח**— המצב הוא קבצים רגילים בפרויקט שלך;
ללא hosting.
- **החלופה של Git**— Git עדיין מנהל את היסטוריית הגרסאות; בצע
  `.saipen/`כמו קוד רגיל.
- **קונסנסוס מפוזר**— ראה את גבול התאמה במקביל למטה.
- **הבטחה שהLLM יעשה החלטות הנדסיות נכונות**— הוא
למשל, מפחית את אובדן ההקשר והזזה התנהגותית; הוא לא גורם לagenta סטוכסטיים
ללא שגיאות.

המשימה של SAIPEN היא הוספת תקן/תנאי מצב ועוד אימות וเครื่י
handing the next agent a machine-checked starting point, not magic.

**גבול התאמה**עדכוני מצב מוערכים(SAIOPS)להשתמש ב
מנעול מערכת עם היקף פרויקט וเจอירלי לاسترجاع([OPS § 5](saipen/OPS.md#5-locks)).
chỉnh sửa פרויקט רגיל וכותבים מנותקים נמצאים מחוץ למנעול זה. SAIPEN
אינו הסכמה מפוזרת, לכן כותבים מנותקים דורשים
קואורדינציה חיצונית([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## אקוסיסטם

|פרויקט|קשר ל-SAIPEN|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |מרכז בקרה מקומי ל-Windows עבור פרויקטים SAIPEN — מגלם אוטומטית`.saipen/`חלונות עבודה, מציג מצב חי ותקנות התאמה, מנהל כרטיסי תקלה, ומביא forth CLIs חכמים. מלווה, לא הרשאה.|
| [SAIWORK](https://github.com/vacterro/saiwork) |שורש CodeNomad מורד שמתאמה SAIPEN: מזרימה`BOOT.md`/`STYLE.md`ל-Launches OpenCode, חושפת קיצורים SAIPEN ומציגות תצוגות מצב פרויקט, ומוסיפה קולת פקודות נצמד.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |סקetchpad נייד ל-Windows ומנהל קטעים שמתאים אוטומטית`.saipen/`תיקיות ומוסיף תצוגה לקריאה בלבד של STATE/BOARD/LOG.|

## מסמכים

|מסמך|מה זה|
|---|---|
| [SPEC.md](SPEC.md) |ארכיטקטורה רשמית, מטרות תכנון, בדיקת ליטמוס|
| [CORE.md](saipen/CORE.md) |המשך רשמי, מכונה מצבים, ותנאי פקודה|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |תחזוקה עצמית וوضع מטרה|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |דרישות ביצוע/התנהגות וחוקי וריפר|
| [GUIDE.md](GUIDE.md) |מדריך אנושי|
| [RFC.md](saipen/RFC.md) |הפניה לتوافق עם מסמכים נורמטיביים מפורקים|
| [STYLE.md](saipen/STYLE.md) |סגנון וקול של תקשורת האגנט|
| [UI.md](saipen/UI.md) |הנחיות לتصميم UI מודרני מבריק|
|броشور|броشور להצגת תוכן —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [אנגלית](guides/GUIDE_EN.md) · 🇪🇪 [אסטונית](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [ألماني](guides/GUIDE_DE.md) · 🇫🇷 [فرنسي](guides/GUIDE_FR.md) · 🇪🇸 [إسباني](guides/GUIDE_ES.md) · 🇮🇹 [איטלקי](guides/GUIDE_IT.md)

🇵🇹 [פורטוגלי](guides/GUIDE_PT.md) · 🇳🇱 [הולנדי](guides/GUIDE_NL.md) · 🇵🇱 [פולני](guides/GUIDE_PL.md) · 🇸🇪 [שוודי](guides/GUIDE_SV.md) · 🇩🇰 [דני](guides/GUIDE_DA.md)

🇫🇮 [סובי](guides/GUIDE_FI.md) · 🇳🇴 [נורווגית](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [ויệt נמי](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [טורקית](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [אינדונזית](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [צ'כית](guides/GUIDE_CS.md) · 🇷🇴 [רומנית](guides/GUIDE_RO.md) · 🇭🇺 [הונגרית](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [סלובקית](guides/GUIDE_SK.md) · 🇭🇷 [קרואטית](guides/GUIDE_HR.md)

</details>

## הערות על תצורה

**שפת תשובה.**הagenta עונה ב-**אסטוני**כברירת מחדל — זהו
הגדרה, לא דרישה פרוטוקול, וכל שאר הדברים ב-SAIPEN לא אסטוניים.
הפרוטוקול, הקוד, ה커מיטים וכל מסמך נשארים באנגלית בכל
ערך. תغيיר אותו במקום אחד: השורה`reply_language:`בחלק העליון של
[`saipen/STYLE.md`](saipen/STYLE.md). `et`אסטוני,`en`אנגלי,`ru`רוסי,
`auto`בוחר מתוך ההודעה ששלחת.

**אדרטרים.**פלטפורמה שאינה מכסה על ידי האינ젝טור(DeepSeek, Qwen, עצמאי
OpenAI, וכו')? הערות לפי פלטפורמה חיים ב-`extensions/adapters/`.

## 快照

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
