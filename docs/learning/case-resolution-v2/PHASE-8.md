# Phase 8 — dokumentasi hasil dan handoff

Tanggal: 16 Oktober 2026. Gate: **PASS untuk dokumentasi dan keterlacakan klaim** setelah
pemeriksaan angka, provenance, tautan, dan diff. Satu commit phase pada `case-resolution-v2`
menjadi checkpoint; identitas SHA dilaporkan setelah push.

## Tujuan dan hasil

Menghubungkan kemampuan produk dengan hasil yang sudah diukur, tanpa mengulang benchmark,
holdout atau deployment cloud. README berfokus pada V2; case study menjelaskan masalah,
alur, keputusan desain dan hasil. Application pack menyediakan wording untuk task CV terpisah;
file CV aktual tidak diubah.

## Bukti yang dipertahankan

- Holdout sintetis 40/40 policy-correct dan correct completion, 19/19 aksi terverifikasi,
  21/21 eskalasi diterima; source dan run asli tercatat dalam aggregate publik.
- Replay SOP terbuka 18/18 pada enam kasus, tiga rule family dan tiga versi per family;
  bukan 18 kasus holdout tambahan.
- Benchmark waktu lama tetap 95 vs 582 detik, satu operator/tiga pasangan; tidak digabung
  dengan kualitas cohort V2 untuk membuat klaim waktu baru.
- Packaging Phase 6 tetap dikaitkan dengan kandidat container yang benar-benar diuji.
- Live AWS September tetap digunakan untuk klaim arsitektur. Audit Phase 7 tidak menemukan
  perubahan executable infra; 43 tes AWS/worker/config dan parsing delapan skrip lulus.
  Live cloud Phase 7 dilewati, bukan ditandai sebagai load test yang berhasil.

## File penting

[Evidence index](../../evidence/case-resolution-v2/README.md),
[hasil](../../evidence/case-resolution-v2/RESULTS.md),
[claim ledger](../../evidence/case-resolution-v2/CLAIM_LEDGER.md),
[case study](../../portfolio/CASE_STUDY.md), dan
[application pack](../../portfolio/APPLICATION_PACK.md).
Aggregate JSON menyimpan identitas source/run dan hash laporan asli agar angka tidak bergantung
semata pada masa retensi artifact CI. Raw trace dan engineering history tetap lokal.

## Verifikasi

Audit lokal membaca ulang hasil CI tersimpan dan metadata run GitHub, membandingkan semua angka
aggregate dengan sumber asli, memeriksa hash/provenance, denominator, link dokumen dan anchor,
serta menjalankan secret scan dan `git diff --check`. Kontrak/corpus beku dan runtime tidak
diubah. Pengujian runtime Phase 6 tidak diulang untuk perubahan dokumentasi ini.

## Integrasi dan handoff

Remote `main` adalah ancestor branch V2 pada audit awal, sehingga tidak ada commit main baru
yang perlu direkonsiliasi saat menyiapkan PR. Checkout main lokal menyimpan pekerjaan AWS lama
dan tidak disentuh. PR mengintegrasikan V2 ke main; gunakan merge yang mempertahankan commit
per phase untuk modul pembelajaran. Hasil CI PR tetap menjadi gate integrasi tersendiri.

Pembuatan PR tidak berarti merge atau deployment. Hosted Vercel/Neon/Clerk masih pada versi
sebelumnya; promosi V2 mengikuti runbook Phase 6. Bersihkan branch sementara setelah integrasi
dan retensi bukti dipastikan, bukan dengan menghapus pekerjaan lokal yang belum tersimpan.

## Latihan

1. Ikuti satu klaim README hingga numerator, denominator, source SHA dan evidence run.
2. Bedakan holdout, exposed regression, operator timing, container smoke dan AWS deployment.
3. Jelaskan mengapa mempertahankan commit phase berguna untuk pembelajaran, sementara main
   tetap menjadi tempat integrasi produk yang selesai.
