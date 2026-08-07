<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Panduan SAIPEN (Bahasa Indonesia)

[TRANSLATED ID]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

**SAIPEN** adalah buku catatan di folder `.saipen/` di proyek Anda.

## Mulai Cepat

## Perintah

## Baik untuk diketahui
- Ada perubahan yang belum di-commit saat kembali ke proyek? Normal -- SAIPEN hanya commit saat `ship`, bukan setiap langkah. Agen memeriksa dulu perubahan itu milik siapa sebelum menyentuh apa pun.
- Ingin agar ia mengingat keputusan arsitektur yang sebenarnya? Taruh di `.saipen/KNOWLEDGE/`, sebagai satu file `decisions.md` atau file bernomor `ADR-001.md`.
- Tidak ada git atau shell di mesin ini? Agen akan mengatakannya dengan jelas (`mode`, `WAIT: <category> -- <pertanyaan>`) alih-alih menebak (kategori adalah salah satu dari tujuh: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; ini memberi tahu jenis jawaban apa yang membuka blokir)
- Ingin jaring pengaman? `python <klon-saipen>/tools/install_hook.py` memasang pemeriksaan pra-commit.