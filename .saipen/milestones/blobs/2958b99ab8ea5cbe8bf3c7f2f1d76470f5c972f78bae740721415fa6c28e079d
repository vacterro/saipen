<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# מדריך SAIPEN (עברית)

SAIPEN הוא פנקס זיכרון בתיקייה .saipen/ עבור סוכני AI.

AI agents have one fatal flaw: they forget. Close the window and everything they learned about your project is gone — what you were building, what failed, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch. SAIPEN is the fix: a persistent notebook in the .saipen/ folder. The agent reads STATE and BOARD on startup, sees exactly where it left off, and gets back to work without a single repeated word.

**מקשים מהירים:** `cc` ממשיך את ההקשר של הפרויקט עד להתכנסות (מחדש יעד פעיל אם הוגדר), `sss` מציג סטטוס ללא נגיעה בקוד ו-`ss` שומר נקודת ביקורת ועוצר. [ראה את מפת 15 המקשים המלאה](../saipen/RFC.md#110-command-surface). גם התאומים הקיריליים עובדים: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

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


