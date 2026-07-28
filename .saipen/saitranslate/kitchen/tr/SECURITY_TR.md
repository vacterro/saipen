<!-- TRANSLATED TO TR -->
# Security Policy

## Kapsam

SAIPEN, bir spesifikasyon artı küçük bir yerel kurulum/dışa aktarma betikleri setidir (`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`, `export.ps1`/`.sh`). Bir sunucu çalıştırmaz, telemetri toplamaz ve hiçbir veriyi hiçbir yere iletmez. Betiklerin yaptığı tek şey, zaten kontrol ettiğiniz dosyalara (kendi `~/.claude`, `~/.gemini`, proje `.saipen/` vb.) yerel dosya sistemi yazmalarıdır.

Burada iki farklı dikkat düzeyi geçerlidir ve körü körüne güvenlik iddia etmektense kesin olmakta fayda var:

- **Kendi yapılandırma dosyalarınız** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.aider.conf.yml`) yalnızca sınırlandırılmış bir `SAIPEN:BEGIN`/`END` bloğu eklenerek veya kaldırılarak düzenlenir ve ilk değişiklikten önce orijinal `<file>.bak` dosyasına kopyalanır. Kaldırma işlemi, silme öncesinde ek olarak `<file>.uninstalled.bak` yazar.
- **Enjektörün oluşturduğu beceri (skill) dizinleri** (`~/.claude/skills/saipen` ve benzerleri), SAIPEN'e ait kopyalardır ve **yedeklenmezler**: kurulum onları toptan üzerine yazar ve kaldırma işlemi onları yinelemeli olarak siler. Bu kasıtlıdır -- bu deponun kendi dosyalarının kopyalarından başka bir şey içermezler -- ancak yerel bir beceri kopyasını elle düzenlerseniz, bu düzenlemeler bir sonraki `inject`/`uninstall`'da kaybolur. Özelleştirmeleri kendi yapılandırma bloğunuzda veya bir fork'ta tutun, kopyalanmış beceri klasöründe değil.

Güvenlik raporuna değer iki şey:
1. Kendi yorumlarının/README'inin tanımladığının ötesinde, dosya sisteminiz veya git geçmişinizle ilgili bir şey yapan bir bootstrap betiği.
2. Protokolün kendi sır-hijyen kuralı (RFC.md § 1.1 -- API anahtarlarını, token'ları, şifreleri asla `STATE.md`/`BOARD.md`/`LOG.md`/`KNOWLEDGE/`/`kitchen/`/`extensions/`/`saitranslate/kitchen/`/`recovery/`/`logs/` içine yazmayın) SAIPEN'i takip eden bir ajanın commit'lenmiş bir dosyaya sır sızdırmasına neden olacak gerçek bir boşluğa sahipse. Son ikisi sinsi olanlardır: Recovery, bozuk bir `STATE.md`'yi olduğu gibi `.saipen/recovery/`'ye kopyalar ve LOG mühürleme, satırları olduğu gibi `.saipen/logs/`'a taşır, bu nedenle orijinale ulaşan her şey, tüm işi içeriği değiştirmemek olan mekanizmalar tarafından arşivlenir.

## Supported Versions

Only the latest tagged release on `main` is supported. This is a
protocol specification, not a long-lived service -- there is no LTS
branch.

## Reporting a Vulnerability

Open a GitHub issue. If the report involves a real, currently-exploitable
problem (not a hypothetical), mark it as a private/security advisory via
this repository's **Security** tab ("Report a vulnerability") instead of
a public issue, so it isn't publicly visible before a fix ships.

Include: which script or RFC rule, the concrete scenario, and what
actually happens vs. what should happen. Same evidence standard as any
other bug report (see `CONTRIBUTING.md`).
