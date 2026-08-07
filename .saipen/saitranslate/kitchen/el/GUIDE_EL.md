<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Οδηγός SAIPEN (Ελληνικά)

[TRANSLATED EL]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

Το **SAIPEN** είναι ένα σημειωματάριο στον φάκελο `.saipen/` στο έργο σας.

## Γρήγορη Εκκίνηση

## Εντολές

## Καλό να ξέρεις
- Μη δεσμευμένες αλλαγές όταν επιστρέφεις στο έργο; Φυσιολογικό -- το SAIPEN κάνει commit μόνο στο `ship`, όχι σε κάθε βήμα. Ο πράκτορας ελέγχει πρώτα σε ποιον ανήκουν αυτές οι αλλαγές πριν αγγίξει οτιδήποτε.
- Θέλεις να θυμάται μια πραγματική απόφαση αρχιτεκτονικής; Βάλε την στο `.saipen/KNOWLEDGE/`, είτε ως ένα αρχείο `decisions.md` είτε ως αριθμημένα αρχεία `ADR-001.md`.
- Δεν υπάρχει git ή shell σε αυτό το μηχάνημα; Ο πράκτορας το λέει ξεκάθαρα (`mode`, `WAIT: <category> -- <ερώτηση>`) αντί να μαντεύει (η κατηγορία είναι μία από επτά: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; σας λέει τι είδους απάντηση ξεκλειδώνει την κατάσταση)
- Θέλεις δίχτυ ασφαλείας; Το `python <κλώνος-saipen>/tools/install_hook.py` εγκαθιστά έλεγχο πριν από κάθε commit.