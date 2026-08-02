<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**AI कोडिंग एजेंट्स के लिए कंटीन्यूएशन प्रोटोकॉल (Continuation protocol)।** सादे मार्कडाउन में स्थायी प्रोजेक्ट मेमोरी, जिससे चैट हिस्ट्री के बिना कोई भी कोल्ड एजेंट `/saipen continue` चलाकर एक मिनट से भी कम समय में काम फिर से शुरू कर सकता है -- कोई रीब्रीफिंग (rebriefing) नहीं, किसी भी वेंडर, किसी भी दिन।

**एक कमांड। शून्य भूल (Zero amnesia)।**

**त्वरित कुंजियाँ:** `cc` सक्रिय Goal Mode जारी रखता है, `sss` कोड छुए बिना स्थिति दिखाता है और `ss` चेकपॉइंट सहेज कर रुक जाता है. [पूरा 13-कुंजी नक्शा देखें](saipen/RFC.md#110-command-surface). सिरिलिक जुड़वाँ भी काम करती हैं: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**v7.165.0** | [विशिष्टता (Spec)](SPEC_HI.md) | [गाइड (Guide)](GUIDE.md) | [RFC](RFC_HI.md) | [शैली (Style)](STYLE_HI.md) | [UI](saipen/UI.md) | [अनुरूपता (Conformance)](saipen/CONFORMANCE.md) | सादा मार्कडाउन | शून्य निर्भरता | MIT

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Hindi Guide](https://img.shields.io/badge/📖_ELI5_Guide-हिन्दी-orange?style=for-the-badge)](guides/GUIDE_HI.md)

```text
User  ->  /saipen continue
Agent ->  reads STATE ("मुझे अभी क्या करना है?")
Agent ->  reads BOARD ("मैं कौन सा कार्य उठा रहा हूँ?")
Agent ->  reads next_action (कमांड निष्पादित करता है)
Agent ->  काम करता है।
```

### प्रोजेक्ट स्टेट > मॉडल मेमोरी
मेमोरी प्रोजेक्ट में रहती है, मॉडल के दिमाग में नहीं। `Project -> Memory -> LLM` अब `Project -> SAIPEN State -> LLM` बन जाता है।

### प्रमुख प्रोटोकॉल लॉजिक और गारंटी
- **कोर स्टेट मशीन**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **जीरो-प्रॉम्प्ट ऑटोनॉमी**: बोर्ड खाली है? स्वतः-संक्रमण (auto-transitions) `HUNT` (बग स्कैन करें) → `ADD` (फीचर्स विकसित करें) → `HUNT` लूप। कोई सवाल नहीं पूछा जाएगा।
- **स्पष्ट ट्रिगर्स**: `/saipen clean` (रेपो स्क्रब), `/saipen translate` (पृथक `.saipen/saitranslate/` फैक्ट्री), `/saipen validate` (अनुरूपता जांच), `/saipen goal` (स्वायत्त निष्पादन)।
- **सख्त विश्वसनीयता**: बैच इनपुट पार्सिंग (सर्जिकल 1-दर-1 टिकट), डर्टी-ट्री अपनाना (कभी भी अनकमिटेड काम को मिटाता नहीं है), सीक्रेट रिडक्शन (`sk-***`)।

## त्वरित शुरुआत (Quick Start)

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


