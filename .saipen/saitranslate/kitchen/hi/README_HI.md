<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**AI कोडिंग एजेंट्स के लिए कंटीन्यूएशन प्रोटोकॉल (Continuation protocol)।** सादे मार्कडाउन में स्थायी प्रोजेक्ट मेमोरी, जिससे चैट हिस्ट्री के बिना कोई भी कोल्ड एजेंट `/saipen continue` चलाकर एक मिनट से भी कम समय में काम फिर से शुरू कर सकता है -- कोई रीब्रीफिंग (rebriefing) नहीं, किसी भी वेंडर, किसी भी दिन।

**एक कमांड। शून्य भूल (Zero amnesia)।**

**त्वरित कुंजियाँ:** `cc` सक्रिय Goal Mode जारी रखता है, `sss` कोड छुए बिना स्थिति दिखाता है और `ss` चेकपॉइंट सहेज कर रुक जाता है. [पूरा 15-कुंजी नक्शा देखें](saipen/RFC.md#110-command-surface). सिरिलिक जुड़वाँ भी काम करती हैं: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**उत्तर की भाषा।** एजेंट डिफ़ॉल्ट रूप से **एस्टोनियाई** में उत्तर देता है — यह एक सेटिंग है, सनक नहीं, और SAIPEN में और कुछ भी एस्टोनियाई नहीं है। इसे एक ही जगह बदलें: [`saipen/STYLE.md`](saipen/STYLE.md) के शीर्ष पर `reply_language:` पंक्ति। `et` एस्टोनियाई, `en` अंग्रेज़ी, `ru` रूसी, `auto` आपके संदेश की भाषा से चुनता है। प्रोटोकॉल, कोड, कमिट और सभी दस्तावेज़ हर मान पर अंग्रेज़ी में रहते हैं।

**v7.206.8** | [विशिष्टता (Spec)](SPEC_HI.md) | [गाइड (Guide)](GUIDE.md) | [RFC](RFC_HI.md) | [शैली (Style)](STYLE_HI.md) | [UI](saipen/UI.md) | [अनुरूपता (Conformance)](saipen/CONFORMANCE.md) | सादा मार्कडाउन | शून्य निर्भरता | MIT

```text

### Project State > Model Memory

**Project state is stronger than model memory.** Memory lives in the project, not the model's head. `Project -> Memory -> LLM` becomes `Project -> SAIPEN state -> LLM`.

- **Core state machine** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Autonomy without prompting** — board stalled (no workable `TODO`, `DOING` empty) **and not `BLOCKED`**? Auto-transition to `HUNT` (bug scanning) → `ADD` (feature development) → `HUNT`, no questions asked. A `BLOCKED` session never launches autonomous hunting — it waits for a human to resolve the block (RFC § 2.1).
- **Strict reliability** — batch input parsing (surgical 1-at-a-time tickets), dirty tree adoption (never wipes uncommitted work), secret redaction (`sk-***`).

## Commands

The full surface is 16 commands; complete details in [RFC § 1.10](saipen/RFC.md#110-command-surface).

| Command | What it does |
|---|---|
| `/saipen set` | Adopt a project |
| `/saipen continue` | Resume exactly where you left off |
| `/saipen plan` | Turn a request or raw queue into tickets |
| `/saipen goal <text>` | Autonomous wave assault on a new objective |
| `/saipen hunt` | Force an immediate defect/improvement scan |
| `/saipen ship` | Version bump, changelog, tag, push |
| `/saipen clean` | Repository cleanup |
| `/saipen validate` | Conformance check |
| `/saipen markhunt` | Dry uncapped audit, record only |
| `/saipen translate` | Isolated translation factory |
| `/saipen prepare` | Package work for handoff |
| `/saipen collect` | Integrate a ready package |
| `/saipen status` | Read-only report |
| `/saipen stop` | Checkpoint and halt |

<sub>`saipen init` and `saipen sub` complete the sixteen; both are called by the protocol, not typed daily.</sub>

**Package keys.** `ee`/`qq` prepare a complete translation or wiki package without integrating; `eee`/`qqq` accept only a ready package, then integrate, verify, review, and push.

**Experimental: saicrew.** Optional bonus layer (`extensions/subs/`, zero Core changes) for running a multi-agent crew — one Core writer plus read-only `saihunt`/`saipython` workers reporting through their own `OUTBOX.md`. Under active live testing, not finalised — see `extensions/subs/crew.md`.

## Two layers

| Layer | Required | Purpose |
|---|---|---|
| **Core** | ✅ | Resume work safely |
| **Maintenance** | On top of Core | Evolve software without task direction |

**Automated evolution.** No open tasks remain, type `/saipen`: `HUNT` audits for bugs, dead code, and failing tests. Clean? `ADD` builds the next obvious missing capability, verifies it, and hunts again. Product mature -> stops gracefully.

**GOAL Mode.** `/saipen goal <what you want>` pivots the board (deprioritises old tickets, never deletes them) and drives the new objective forward — no "should I continue?" between tickets, VERIFY/REVIEW never skipped. SHIP auto-pushes to the existing remote; a brand-new repository still asks once. Shipping a goal is not the end point either — it transitions straight into autonomous HUNT/ADD maintenance until the product is mature, blocked, or the run hits its cap (3 waves / 20 tickets, then checkpoints and reports).

## Quick Start


**1. प्रति मशीन एक बार इंस्टॉल करें** -- Claude Code, Gemini, OpenCode, Aider, Antigravity को सिखाता है:
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. एक प्रोजेक्ट शुरू करें** -- अपने फ़ोल्डर में एक एजेंट खोलें, टाइप करें:
> `saipen set`

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>


## Documentation

| Document | What it is |
|---|---|
| [SPEC.md](SPEC.md) | Formal architecture, design goals, litmus test |
| [RFC.md](saipen/RFC.md) | Normative specification agents execute |
| [GUIDE.md](GUIDE.md) | Human tutor and ELI5 guides |
| [STYLE.md](saipen/STYLE.md) | Agent communication style and voice definition |
| [UI.md](saipen/UI.md) | Vintage Golden UI design guidelines |
| [CONFORMANCE.md](saipen/CONFORMANCE.md) | Behavioural test scenarios and validator rules |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [English](guides/GUIDE_EN.md) · 🇪🇪 [Eesti](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Deutsch](guides/GUIDE_DE.md) · 🇫🇷 [Français](guides/GUIDE_FR.md) · 🇪🇸 [Español](guides/GUIDE_ES.md) · 🇮🇹 [Italiano](guides/GUIDE_IT.md)

🇵🇹 [Português](guides/GUIDE_PT.md) · 🇳🇱 [Nederlands](guides/GUIDE_NL.md) · 🇵🇱 [Polski](guides/GUIDE_PL.md) · 🇸🇪 [Svenska](guides/GUIDE_SV.md) · 🇩🇰 [Dansk](guides/GUIDE_DA.md)

🇫🇮 [Suomi](guides/GUIDE_FI.md) · 🇳🇴 [Norsk](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Türkçe](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Čeština](guides/GUIDE_CS.md) · 🇷🇴 [Română](guides/GUIDE_RO.md) · 🇭🇺 [Magyar](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) · 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)

</details>

## Built with SAIPEN

- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — High-performance prompt management tool built natively around the SAIPEN memory protocol.

## Screenshots

<details>
<summary>Click to expand</summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- source-digest: README.md sha256:535e0088a9f9fcb5b9dc4d0a6e1072ac643101e0083789f57d4850be564931ce -->



