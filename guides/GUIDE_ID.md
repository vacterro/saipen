<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Panduan SAIPEN (Bahasa Indonesia)

Dengar, pemula. Masalahnya sederhana: agen AI Anda memiliki ingatan ikan mas.

**SAIPEN** adalah buku catatan di folder `.saipen/` di proyek Anda.

## Mulai Cepat

1. **Instal sekali per mesin:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Mulai proyek:**
> `saipen set`

3. **Bekerja:**
> `saipen`

## Perintah

| Perintah | Aksi |
|---|---|
| `saipen set` | Inisialisasi folder memori |
| `saipen continue` | Lanjutkan pekerjaan dari catatan |
| `saipen stop` | Simpan kemajuan & berhenti |
| `saipen status` | Baca papan |
| `saipen goal <text>` | Beralih ke tujuan baru |
| `saipen clean` | Bersihkan repositori |
| `saipen translate` | Bangun terjemahan terisolasi dalam 32 bahasa |
| `saipen markhunt` | Audit mendalam tanpa batas -- hanya mencatat temuan |
| `saipen prepare` | Mengemas pekerjaan untuk diserahkan ke agen berikutnya |
| `saipen ship` | Picu aliran rilis |

## Baik untuk diketahui
- Ada perubahan yang belum di-commit saat kembali ke proyek? Normal -- SAIPEN hanya commit saat `ship`, bukan setiap langkah. Agen memeriksa dulu perubahan itu milik siapa sebelum menyentuh apa pun.
- Ingin agar ia mengingat keputusan arsitektur yang sebenarnya? Taruh di `.saipen/KNOWLEDGE/`, sebagai satu file `decisions.md` atau file bernomor `ADR-001.md`.
- Tidak ada git atau shell di mesin ini? Agen akan mengatakannya dengan jelas (`mode`, `WAIT: <category> -- <pertanyaan>`) alih-alih menebak (kategori adalah salah satu dari tujuh: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; ini memberi tahu jenis jawaban apa yang membuka blokir)
- Ingin jaring pengaman? `python <klon-saipen>/tools/install_hook.py` memasang pemeriksaan pra-commit.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
