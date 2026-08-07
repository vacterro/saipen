<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# מדריך SAIPEN (עברית)

[TRANSLATED HE]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

## התחלה מהירה

## פקודות

## טוב לדעת
- שינויים לא מחויבים כשחוזרים לפרויקט? נורמלי -- SAIPEN מבצע commit רק ב-`ship`, לא בכל שלב. הסוכן בודק קודם למי שייכים השינויים לפני שהוא נוגע במשהו.
- רוצה שהוא יזכור החלטת ארכיטקטורה אמיתית? שים אותה ב-`.saipen/KNOWLEDGE/`, כקובץ `decisions.md` אחד או כקבצים ממוספרים `ADR-001.md`.
- אין git או shell במחשב הזה? הסוכן אומר את זה בפירוש (`mode`, `WAIT: <category> -- <שאלה>`) במקום לנחש (הקטגוריה היא אחת משבע: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; היא אומרת איזו תשובה פותרת את החסימה)
- רוצה רשת ביטחון? `python <שכפול-saipen>/tools/install_hook.py` מתקין בדיקה לפני כל commit.