<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Πρωτόκολλο συνέχειας για πράκτορες κώδικα AI.** Μόνιμη μνήμη έργου σε
απλό markdown, ώστε ένας νέος πράκτορας χωρίς ιστορικό συνομιλίας να εκτελεί `/saipen continue`
και να συνεχίζει την εργασία σε λιγότερο από ένα λεπτό -- χωρίς νέα ενημέρωση, από οποιονδήποτε πάροχο, οποιαδήποτε ημέρα.

**Μία εντολή. Μηδενική αμνησία.**

**Συντομεύσεις:** το `cc` συνεχίζει ενεργό Goal Mode, το `sss` εμφανίζει την κατάσταση χωρίς να αγγίζει κώδικα και το `ss` αποθηκεύει σημείο ελέγχου και σταματάει. [Δες τον πλήρη χάρτη 13 πλήκτρων](saipen/RFC.md#110-command-surface). Λειτουργούν και τα κυριλλικά δίδυμα: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**v7.168.0** | [Προδιαγραφή](SPEC.md) | [Οδηγός](GUIDE.md) | [RFC](saipen/RFC.md) | [Στυλ](saipen/STYLE.md) | [UI](saipen/UI.md) | [Συμμόρφωση](saipen/CONFORMANCE.md) | απλό markdown | μηδενικές εξαρτήσεις | MIT

[![Ρωσικός Οδηγός](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![Αγγλικός Οδηγός](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Εσθονικός Οδηγός](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Ιαπωνικός Οδηγός](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Φωνή Ded](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
User  ->  /saipen continue
Agent ->  διαβάζει το STATE ("Τι κάνω αυτή τη στιγμή;")
Agent ->  διαβάζει το BOARD ("Ποια εργασία αναλαμβάνω;")
Agent ->  διαβάζει το next_action (εκτελεί την εντολή)
Agent ->  Εργάζεται.
```

### Κατάσταση Έργου > Μνήμη Μοντέλου
Η μνήμη ζει στο έργο, όχι στο κεφάλι ενός μοντέλου. Το `Έργο -> Μνήμη -> LLM` γίνεται `Έργο -> Κατάσταση SAIPEN -> LLM`.

### Βασική Λογική & Εγγυήσεις Πρωτοκόλλου
- **Μηχανή Κατάστασης Πυρήνα**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Αυτονομία χωρίς Prompts**: Δεν απομένουν εκκρεμότητες; Αυτόματη μετάβαση `HUNT` (σάρωση για bugs) → `ADD` (ανάπτυξη δυνατοτήτων) → `HUNT` βρόχος. Μηδενικές ερωτήσεις.
- **Ρητοί Ενεργοποιητές (Triggers)**: `/saipen clean` (καθαρισμός repo), `/saipen translate` (απομονωμένο εργαστήριο `.saipen/saitranslate/`), `/saipen markhunt` (έλεγχος χωρίς διορθώσεις, μόνο καταγραφή), `/saipen prepare` (προετοιμασία εργασίας για παράδοση), `/saipen validate` (έλεγχος συμμόρφωσης), `/saipen goal` (αυτόνομη εκτέλεση κύματος). Μετα-έλεγχος: `/saipen status` (αναφορά μόνο για ανάγνωση), `/saipen stop` (σημείο ελέγχου και παύση). Πλήρης λίστα: RFC.md § 1.10.
- **Αστηστη Αξιοπιστία**: Ανάλυση εισαγωγής σε πακέτα (χειρουργικά εισιτήρια 1 προς 1), υιοθέτηση ακάθαρτου δέντρου (ποτέ δεν διαγράφει μη καταγεγραμμένη εργασία), απόκρυψη μυστικών (`sk-***`).

## Έργα που Χρησιμοποιούν το SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Εργαλείο διαχείρισης prompts υψηλής απόδοσης με ενσωματωμένο πρωτόκολλο μνήμης SAIPEN.

## Δύο Επίπεδα

| Επίπεδο | Απαιτούμενο | Σκοπός |
|---|---|---|
| **Πυρήνας** | ✅ | Ασφαλής συνέχιση εργασίας |
| **Συντήρηση** | Πάνω από τον Πυρήνα | Εξέλιξη του λογισμικού χωρίς ανάθεση εργασιών |

**Αυτοματοποιημένη Εξέλιξη.** Δεν απομένουν ανοιχτές εκκρεμότητες, πληκτρολογήστε `/saipen`: Το `HUNT` ελέγχει για bugs, νεκρό κώδικα, αποτυχημένα τεστ. Καθαρό; Το `ADD` κατασκευάζει την επόμενη προφανή απαραίτητη δυνατότητα, την επαληθεύει, ελέγχει ξανά (HUNT). Το προϊόν ωριμάζει -> σταματά ομαλά.

**Λειτουργία GOAL.** Το `/saipen goal <αυτό που θέλετε>` αναδιοργανώνει τον πίνακα (παλιά εισιτήρια υποβιβάζονται, ποτέ δεν διαγράφονται) και προωθεί τον νέο στόχο -- χωρίς "να συνεχίσω;" ανάμεσα στα εισιτήρια, VERIFY/REVIEW ποτέ δεν παραλείπονται. Το SHIP κάνει auto-push σε υπάρχον remote. Ένα ολοκαίνουργιο repo θα ρωτήσει μία φορά. Η αποστολή του στόχου δεν είναι το σημείο σταματήματος -- περνάει κατευθείαν σε αυτόνομη συντήρηση HUNT/ADD μέχρι το προϊόν να ωριμάσει, να μπλοκαριστεί ή η εκτέλεση να φτάσει το όριό της (3 κύματα / 20 εισιτήρια, στη συνέχεια δημιουργεί σημείο ελέγχου και αναφέρει).

## Γρήγορη Εκκίνηση

**1. Εγκατάσταση μία φορά ανά μηχάνημα** -- διδάσκει τα Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex ??? ???????????? ?????? ????????? ~/.agents/skills (FreeBuff, ?.??.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Ξεκινήστε ένα έργο** -- ανοίξτε έναν πράκτορα στον φάκελό σας, πληκτρολογήστε:
> `saipen set`

Χωρίς εγκατάσταση; Επικολλήστε μία γραμμή σε οποιονδήποτε πράκτορα:
> Διαβάστε <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md και ακολουθήστε τα.

Η πλατφόρμα δεν είναι στην παραπάνω λίστα (DeepSeek, Qwen, αυτόνομο OpenAI, κ.λπ.);
Οι σημειώσεις ανά πλατφόρμα βρίσκονται στο `extensions/adapters/`.

## Σύνδεσμοι Τεκμηρίωσης & Προδιαγραφών
- **[SPEC.md](SPEC.md)** -- επίσημη αρχιτεκτονική, στόχοι σχεδιασμού, litmus test.
- **[RFC.md](saipen/RFC.md)** -- κανονιστική προδιαγραφή που εκτελείται από πράκτορες.
- **[GUIDE.md](GUIDE.md)** -- οδηγός για ανθρώπους & οδηγoί ELI5:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- στυλ επικοινωνίας πράκτορα & ορισμός φωνής.
- **[UI.md](saipen/UI.md)** -- οδηγίες σχεδίασης Vintage Golden UI.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- σενάρια δοκιμών συμπεριφοράς & κανόνες επικύρωσης.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>


