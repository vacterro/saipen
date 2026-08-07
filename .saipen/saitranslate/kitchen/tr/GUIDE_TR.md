<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Kılavuzu (Türkçe)

[TRANSLATED TR]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

**SAIPEN** projenizdeki `.saipen/` klasöründe bulunan bir not defteridir.

## Hızlı Başlangıç

## Komutlar

## Bilmekte fayda var
- Projeye geri döndüğünde commit edilmemiş değişiklikler mi var? Normal -- SAIPEN yalnızca `ship` sırasında commit yapar, her adımda değil. Ajan bir şeye dokunmadan önce bu değişikliklerin kime ait olduğunu kontrol eder.
- Gerçek bir mimari kararı hatırlamasını mı istiyorsun? `.saipen/KNOWLEDGE/` klasörüne tek bir `decisions.md` dosyası veya numaralandırılmış `ADR-001.md` dosyaları olarak koy.
- Bu makinede git veya shell yok mu? Ajan tahmin etmek yerine bunu açıkça söyler (`mode`, `WAIT: <category> -- <soru>`). (kategori yediden biridir: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; ne tür bir cevabın durumu çözeceğini söyler)
- Bir güvenlik ağı mı istiyorsun? `python <saipen-klonu>/tools/install_hook.py` commit öncesi bir kontrol kurar.