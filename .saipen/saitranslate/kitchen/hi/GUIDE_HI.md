<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN गाइड (हिन्दी)

[TRANSLATED HI]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

**SAIPEN** आपके प्रोजेक्ट में `.saipen/` फ़ोल्डर के अंदर एक नोटबुक है।

## त्वरित शुरुआत

## कमांड

## जानना अच्छा है
- प्रोजेक्ट में वापस आने पर अनकमिटेड बदलाव मिले? सामान्य बात है -- SAIPEN केवल `ship` पर कमिट करता है, हर कदम पर नहीं। एजेंट कुछ भी छूने से पहले जांचता है कि ये बदलाव किसके हैं।
- चाहते हैं कि यह किसी वास्तविक आर्किटेक्चर निर्णय को याद रखे? इसे `.saipen/KNOWLEDGE/` में डालें, या तो एक `decisions.md` फ़ाइल के रूप में या क्रमांकित `ADR-001.md` फ़ाइलों के रूप में।
- इस मशीन पर git या shell नहीं है? एजेंट अनुमान लगाने के बजाय साफ़ बता देता है (`mode`, `WAIT: <category> -- <प्रश्न>`) (श्रेणी सात में से एक है: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; यह बताती है कि किस तरह का उत्तर इसे अनब्लॉक करता है)।
- सुरक्षा जाल चाहिए? `python <saipen-clone>/tools/install_hook.py` एक प्री-कमिट जांच स्थापित करता है।