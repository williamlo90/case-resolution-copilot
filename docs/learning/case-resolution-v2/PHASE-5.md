# Phase 5 — penggunaan kembali benchmark workflow

Tanggal: 16 Oktober 2026. Status: **selesai pada cakupan revisi pemilik proyek**.
Identitas checkpoint adalah commit tunggal yang memuat dokumen ini pada branch
`codex/case-resolution-v2`.

## Tujuan dan keputusan

Memakai bukti pengukuran yang sudah tersedia untuk menjelaskan manfaat workflow, sekaligus
mendokumentasikan pembaruan V2 sesuai bukti engineering masing-masing. Studi waktu baru
tidak menjadi syarat penutupan phase ini. Implementation plan lokal disesuaikan dengan
keputusan pemilik; tidak dipublikasikan karena tetap di-ignore.

## Hasil dan batas pengukuran

Benchmark 24 Agustus 2026 menggunakan satu operator dan tiga kasus sintetis per kondisi.
Median mentah 582 detik manual dan 95 detik Copilot; selisih 487 detik atau 83,7%.
Complete workflow adalah 0/3 manual dan 3/3 Copilot. Tugas berakhir pada keputusan yang
diterima aplikasi, sehingga hasil tersebut tidak mengukur speedup resolusi V2 yang sama-sama
benar selesai. Data dan laporan lama dipertahankan apa adanya.

## Perubahan dokumentasi

- README mempertahankan benchmark lama dan menjelaskan pembaruan V2 secara terpisah.
- [Evidence Phase 5](../../evidence/case-resolution-v2/PHASE5_BENCHMARK_REUSE.md) mencatat
  sumber, cakupan hasil, dan keputusan reuse.
- Claim ledger, handoff Phase 4, dan indeks dokumentasi mengikuti cakupan Phase 5 terbaru.
- Instrumen studi baru disimpan lokal untuk kemungkinan studi mendatang. Kontrak pengukuran,
  oracle, manifest beku, dan hasil benchmark historis tidak diubah oleh checkpoint ini.

## Verifikasi dan gate

Pemeriksaan ringan lokal: hitung ulang median, persentase dan completion dari raw results;
periksa tautan lokal dokumen checkpoint; jalankan `git diff --check`; periksa daftar staged
agar hanya dokumentasi Phase 5 yang ikut. Gate dokumentasi **PASS** setelah pemeriksaan ini.
Tidak ada pengukuran baru, provider call, browser, deployment, atau container yang dijalankan.
Satu commit dan push menjadi checkpoint pembelajaran; SHA serta verifikasi remote dilaporkan
setelah push, tanpa memasukkan SHA sendiri ke dokumen ini.

## Latihan dan handoff

1. Bedakan median elapsed mentah dengan speedup pada hasil akhir yang sama-sama benar.
2. Telusuri tiga durasi per kondisi di raw results hingga median dan selisih persentasenya.
3. Jelaskan mengapa skor holdout V2 tidak dapat digabung dengan cohort waktu historis.

Lanjutkan Phase 6 packaging dan release gate secara terpisah. Tidak ada tugas pengukuran
operator yang wajib untuk menutup Phase 5 pada cakupan ini.
