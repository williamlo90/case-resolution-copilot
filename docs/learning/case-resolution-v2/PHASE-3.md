# Phase 3 — SOP berubah, keputusan dan approval tetap terkendali

## Tujuan pembelajaran

Membuktikan perubahan aturan benar-benar mengubah keputusan, tanpa membuat approval lama berlaku
diam-diam atau mengulang tindakan yang hasilnya belum pasti.

## Yang berubah

1. SOP dapat memuat aturan terstruktur untuk batas hari refund, tingkat bukti kepemilikan, dan
   ambang nominal eskalasi. Aturan ini dibaca mesin keputusan; teks bebas bukan program otomatis.
2. Pemilihan versi konsisten pada retrieval, approval dan eksekusi. Draft tidak menggantikan versi
   aktif. Versi terjadwal berlaku mulai tanggalnya; approval versi lama kemudian menjadi stale.
3. Publish, approve dan persiapan dispatch memakai urutan transaksi per tenant. Tindakan yang sudah
   dikirim tetap harus ditelusuri, bukan dibatalkan secara fiktif ketika SOP berubah.
4. Rollback menyalin konten lama ke versi baru. Approval harus dibuat ulang. Tindakan lama dengan
   hasil unknown atau completed memblokir pengulangan lewat proposal baru.
5. Enam kasus replay terbuka diuji pada tiga tanggal: 18 observasi. Ada tiga perubahan bermakna,
   kontrol yang tidak berubah, serta rollback masing-masing keluarga.

## Contoh

Refund hari ke-10 ditahan oleh SOP tujuh hari, boleh diusulkan untuk review saat SOP menjadi 14 hari,
dan kembali ditahan setelah rollback ke tujuh hari. "Boleh diusulkan" belum berarti uang dikirim.
Kasus hari ke-5 menjadi kontrol: tetap memenuhi batas waktu di ketiga versi.

## Failure → fix → regression

Tes awal membuktikan mesin sebelumnya mengabaikan batas hari dalam sumber SOP dan masih mengusulkan
refund. Sekarang tes yang sama mengharuskan refund diblokir dengan alasan `refund_window`.
Detail reproduksi dan batas klaim ada di [evidence](../../evidence/case-resolution-v2/SOP_REVISIONS.md).

## Checkpoint

Pemeriksaan lokal: 172 unit tests terkait lulus; lint dan type check pada 17 file Python lulus.
Empat journey PostgreSQL lulus; race test sengaja tidak dijalankan lokal. Validator Phase 0/2
lulus, dengan 40 holdout tetap tersegel dan tanpa product run. Hasil CI untuk source final di bawah
melengkapi pemeriksaan ini, termasuk replay penuh dan race test.

Satu commit Phase 3 memuat implementasi, fixture/oracle, regression tests, workflow CI dan runbook.
Hasil replay lengkap dan race test diterbitkan sebagai artifact untuk **SHA commit tersebut** oleh
workflow `SOP revision gate`. Lihat numerator/denominator per revisi, bukan hanya indikator hijau.
Checkpoint ini tidak mengubah hasil V1, threshold Phase 0, atau sealed holdout Phase 2.

## Latihan membaca kode

- `backend/app/analysis/sop_rules.py`: mengapa aturan tidak valid harus menahan tindakan?
- `backend/app/persistence/policy_authority.py`: kapan versi terjadwal menjadi otoritas?
- `backend/app/persistence/actions/_base.py`: mengapa proposal baru tidak boleh melewati efek lama?
- `backend/app/evaluation/sop_replay.py`: mengapa observasi disimpan sebelum oracle dibuka?
- [Runbook](../../runbooks/sop-change-and-recovery.md): bagaimana operator mengevaluasi ulang dan
  memperoleh approval baru setelah rollback?

## Batas dan langkah berikutnya

Replay ini sintetis, terbuka untuk development, dan memakai snapshot retrieval serta mesin
deterministik. Label dibuat dan ditinjau agent, bukan reviewer manusia independen. Integrasi API
memakai PostgreSQL disposable dan target deterministik. Tidak ada klaim akurasi holdout, pembayaran
nyata, produksi, atau rollback deployment. Phase 4 masih memerlukan adapter runtime V2 yang tervalidasi
dan release candidate beku sebelum menjalankan evaluasi end-to-end.
