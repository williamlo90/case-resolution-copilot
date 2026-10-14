# Phase 4 — uji sistem utuh dengan holdout terisolasi

## Tujuan pembelajaran

Membedakan hasil unit test dari hasil resolusi kasus nyata di dalam aplikasi.
Keputusan yang terlihat benar belum selesai sampai review manusia, efek target,
read-back, komunikasi pelanggan dan penutupan kasus tercatat serta terikat.

## Alur yang diuji

1. Input sumber membuat kasus dan kebijakan bertanggal di PostgreSQL disposable.
2. Mesin keputusan menghasilkan fakta, gap dan usulan. Kondisi yang belum aman
   diarahkan ke spesialis, diterima dan dikomunikasikan ke pelanggan.
3. Usulan yang memenuhi aturan ditinjau manusia, dijalankan sekali pada target
   sintetis, diverifikasi melalui read-back, lalu ditutup.
4. Adapter hanya membaca bukti produk. Observasi disegel sebelum proses scoring
   terpisah membuka label. Development harus lulus sebelum holdout dijalankan.

## Failure → fix → regression

Dataset awal tidak memuat nilai tujuan untuk lima perubahan, sehingga aksi
tidak mungkin diverifikasi. Input direvisi dengan nilai tujuan eksplisit,
target awal, fakta otorisasi dan holdout baru. Uji development juga menemukan
kebijakan kedua yang gagal dipublikasikan karena konflik belum membuat kasus
berstatus konflik. Pemeriksaan scope kini menahan tindakan selama konflik
publikasi belum selesai; journey PostgreSQL menguji status dan jalur eskalasi.
Gate development pertama juga menemukan retrieval dapat mengambil kebijakan
keluarga lain saat banyak kasus berbagi database. Scope dari input kasus kini
menyaring kandidat retrieval; tes berurutan dua kasus menguji isolasinya.

## Checkpoint

Satu commit Phase 4 memuat perluasan operasi bertipe, kontrak corpus,
adapter bukti, runner CI dan dokumentasi. Hasil acceptance ditentukan oleh
`phase4-gate.json` pada artifact workflow untuk SHA commit tersebut, bukan
oleh angka target atau hasil unit test. Baca [protokol dan batas klaim](../../evidence/case-resolution-v2/PHASE4_EVALUATION.md)
sebelum memakai angka dalam portfolio.

## Latihan membaca kode

- `backend/app/domain/controlled_operations.py`: nilai sumber mana yang
  membatasi operasi sebelum approval?
- `backend/app/evaluation/phase4_observation_adapter.py`: bukti apa yang
  membuktikan action, receipt dan read-back berasal dari satu target?
- `backend/scripts/capture_phase4_run.py`: mengapa runtime hanya menerima input?
- `backend/scripts/score_phase4_run.py`: kapan sebuah kegagalan menggagalkan gate?

Uji ini memakai target sintetis, label yang ditinjau agent, dan CI PostgreSQL;
hasilnya tidak membuktikan pembayaran produksi, independensi adjudikasi, atau
penghematan waktu operator. Pengukuran waktu berpasangan adalah Phase 5.
