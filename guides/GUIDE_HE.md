<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# מדריך SAIPEN (עברית)

SAIPEN הוא פנקס זיכרון בתיקייה `.saipen/` עבור סוכני AI.

**מקשים מהירים:** `cc` ממשיך Goal Mode פעיל, `sss` מציג סטטוס ללא נגיעה בקוד ו-`ss` שומר נקודת ביקורת ועוצר. [ראה את מפת 14 המקשים המלאה](../saipen/RFC.md#110-command-surface). גם התאומים הקיריליים עובדים: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

## התחלה מהירה

1. **התקן פעם אחת לכל מחשב:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **הפעל פרויקט:**
> `saipen set`

3. **עבודה:**
> `saipen`

## פקודות

| פקודה | פעולה |
|---|---|
| `saipen set` | אתחל תיקיית זיכרון `.saipen/` |
| `saipen continue` | חדש עבודה מההערות |
| `saipen stop` | שמור התקדמות ועצור |
| `saipen status` | קרא את הלוח והמצב |
| `saipen goal <text>` | עבור ליעד חדש |
| `saipen clean` | ניקוי עמוק של המאגר |
| `saipen translate` | בניית תרגום מבודדת ל-32 שפות |
| `saipen markhunt` | ביקורת עמוקה וללא הגבלה -- רק מתעד ממצאים |
| `saipen prepare` | אורז את העבודה למסירה לסוכן הבא |
| `saipen ship` | הפעל תהליך שחרור |

## טוב לדעת
- שינויים לא מחויבים כשחוזרים לפרויקט? נורמלי -- SAIPEN מבצע commit רק ב-`ship`, לא בכל שלב. הסוכן בודק קודם למי שייכים השינויים לפני שהוא נוגע במשהו.
- רוצה שהוא יזכור החלטת ארכיטקטורה אמיתית? שים אותה ב-`.saipen/KNOWLEDGE/`, כקובץ `decisions.md` אחד או כקבצים ממוספרים `ADR-001.md`.
- אין git או shell במחשב הזה? הסוכן אומר את זה בפירוש (`mode`, `WAIT: <category> -- <שאלה>`) במקום לנחש (הקטגוריה היא אחת משבע: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; היא אומרת איזו תשובה פותרת את החסימה)
- רוצה רשת ביטחון? `python <שכפול-saipen>/tools/install_hook.py` מתקין בדיקה לפני כל commit.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
