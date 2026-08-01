<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Kılavuzu (Türkçe)

Dinle, acemi. Sorun basit: yapay zeka ajanlarının hafızası bir japon balığı gibidir.

**SAIPEN** projenizdeki `.saipen/` klasöründe bulunan bir not defteridir.

**Kısayol tuşları:** `cc` aktif Goal Mode’u sürdürür, `sss` koda dokunmadan durumu bildirir ve `ss` kontrol noktası kaydedip durur. [11 tuşluk tam haritaya bakın](../saipen/RFC.md#110-command-surface). Kiril ikizleri de çalışır: `сс`, `ссс`, `аа`, `ее`, `рр`.

## Hızlı Başlangıç

1. **Makine başına bir kez kurun:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Projede başlat:**
> `saipen set`

3. **Çalış:**
> `saipen`

## Komutlar

| Komut | Eylem |
|---|---|
| `saipen set` | Bellek klasörünü başlat |
| `saipen continue` | Notlardan çalışmaya devam et |
| `saipen stop` | İlerlemeyi kaydet & dur |
| `saipen status` | Panoyu oku |
| `saipen goal <text>` | Yeni hedefe geç |
| `saipen clean` | Depoyu temizle |
| `saipen translate` | İzole 32 dilde çeviri derlemesi |
| `saipen markhunt` | Derin, sınırsız denetim -- sadece bulguları kaydeder |
| `saipen prepare` | İşi bir sonraki ajana devretmek için paketler |
| `saipen ship` | Yayın akışını tetikle |

## Bilmekte fayda var
- Projeye geri döndüğünde commit edilmemiş değişiklikler mi var? Normal -- SAIPEN yalnızca `ship` sırasında commit yapar, her adımda değil. Ajan bir şeye dokunmadan önce bu değişikliklerin kime ait olduğunu kontrol eder.
- Gerçek bir mimari kararı hatırlamasını mı istiyorsun? `.saipen/KNOWLEDGE/` klasörüne tek bir `decisions.md` dosyası veya numaralandırılmış `ADR-001.md` dosyaları olarak koy.
- Bu makinede git veya shell yok mu? Ajan tahmin etmek yerine bunu açıkça söyler (`mode`, `WAIT: <category> -- <soru>`). (kategori yediden biridir: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; ne tür bir cevabın durumu çözeceğini söyler)
- Bir güvenlik ağı mı istiyorsun? `python <saipen-klonu>/tools/install_hook.py` commit öncesi bir kontrol kurar.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
