<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Οδηγός SAIPEN (Ελληνικά)

Άκου, πρωτάρη. Το πρόβλημα είναι απλό: οι πράκτορες AI έχουν μνήμη χρυσόψαρου.

Το **SAIPEN** είναι ένα σημειωματάριο στον φάκελο `.saipen/` στο έργο σας.

**Συντομεύσεις:** το `cc` συνεχίζει ενεργό Goal Mode, το `sss` εμφανίζει την κατάσταση χωρίς να αγγίζει κώδικα και το `ss` αποθηκεύει σημείο ελέγχου και σταματάει. [Δες τον πλήρη χάρτη 11 πλήκτρων](../saipen/RFC.md#110-command-surface). Λειτουργούν και τα κυριλλικά δίδυμα: `сс`, `ссс`, `аа`, `ее`, `рр`.

## Γρήγορη Εκκίνηση

1. **Εγκατάσταση μία φορά ανά μηχάνημα:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Έναρξη έργου:**
> `saipen set`

3. **Εργασία:**
> `saipen`

## Εντολές

| Εντολή | Ενέργεια |
|---|---|
| `saipen set` | Αρχικοποίηση φακέλου μνήμης |
| `saipen continue` | Συνέχιση εργασίας από σημειώσεις |
| `saipen stop` | Αποθήκευση & διακοπή |
| `saipen status` | Ανάγνωση πίνακα |
| `saipen goal <text>` | Αλλαγή σε νέο στόχο |
| `saipen clean` | Καθαρισμός αποθετηρίου |
| `saipen translate` | Απομονωμένη δημιουργία μετάφρασης σε 32 γλώσσες |
| `saipen markhunt` | Βαθύς, απεριόριστος έλεγχος -- καταγράφει μόνο ευρήματα |
| `saipen prepare` | Πακετάρει την εργασία για παράδοση στον επόμενο πράκτορα |
| `saipen ship` | Εκκίνηση ροής έκδοσης |

## Καλό να ξέρεις
- Μη δεσμευμένες αλλαγές όταν επιστρέφεις στο έργο; Φυσιολογικό -- το SAIPEN κάνει commit μόνο στο `ship`, όχι σε κάθε βήμα. Ο πράκτορας ελέγχει πρώτα σε ποιον ανήκουν αυτές οι αλλαγές πριν αγγίξει οτιδήποτε.
- Θέλεις να θυμάται μια πραγματική απόφαση αρχιτεκτονικής; Βάλε την στο `.saipen/KNOWLEDGE/`, είτε ως ένα αρχείο `decisions.md` είτε ως αριθμημένα αρχεία `ADR-001.md`.
- Δεν υπάρχει git ή shell σε αυτό το μηχάνημα; Ο πράκτορας το λέει ξεκάθαρα (`mode`, `WAIT: <category> -- <ερώτηση>`) αντί να μαντεύει (η κατηγορία είναι μία από επτά: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; σας λέει τι είδους απάντηση ξεκλειδώνει την κατάσταση)
- Θέλεις δίχτυ ασφαλείας; Το `python <κλώνος-saipen>/tools/install_hook.py` εγκαθιστά έλεγχο πριν από κάθε commit.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
