# Checkpoint pembelajaran — Phase 0

Tanggal: 13 Oktober 2026. Gate: **PASS — kontrak desain dan skema**, bukan gate kualitas produk.
Branch checkpoint: `case-resolution-v2`. Identitas SHA tersedia pada commit yang memuat file ini.

## Tujuan dan kondisi awal

Phase 0 menetapkan arti berhasil sebelum mengejar skor. Proyek sudah mempunyai Decision Brief,
policy berversi, review, action dan audit. Tetapi receipt masih dapat dianggap completed,
reopen belum tersedia, dan scorer belum memeriksa semua parameter tindakan atau hasil bisnis.
Bukti V1 berguna sebagai regression; angka historis belum menjawab klaim baru.

Baseline lokal main berada di `2a8175b`, dengan diff AWS yang belum selesai. Checkpoint dibuat
dari GitHub main `dab033c` dalam worktree `case-resolution-copilot-v2`, sehingga pekerjaan lama
tidak ikut dipublikasikan. Checkout `case-resolution-copilot-rebuild` dan perubahan existing
tetap dipertahankan. Worktree berbeda adalah direktori kerja dari repository Git yang sama.

## Yang berubah dan alasan desain

1. [Kontrak V2](../../evidence/case-resolution-v2/CONTRACT.md) membedakan policy correctness,
   correct completion, verified resolution, safe escalation, dan automation. Pemisahan ini
   mencegah keberhasilan satu kontrol dipakai sebagai bukti seluruh kasus selesai.
2. [Audit arsitektur](../../evidence/case-resolution-v2/BASELINE_AND_ARCHITECTURE.md) mencatat
   implemented/partial/missing dan titik kode yang perlu diperluas pada phase berikutnya.
3. [Claim ledger](../../evidence/case-resolution-v2/CLAIM_LEDGER.md) menghubungkan enam komponen
   klaim ke bukti dan phase pemilik. Tidak ada angka CV diisi.
4. Model kontrak di `backend/app/evaluation/case_resolution_v2/contracts.py` menolak contoh
   oracle yang kontradiktif, keluarga lintas split, seal tidak lengkap, dan denominator salah.
   JSON Schema mengekspor struktur; Python validators memeriksa hubungan antar-field.
5. Empat manifest berstatus planned memisahkan development, regression, holdout, dan time study.
   Target 40/12 keluarga belum berarti dataset tersebut sudah ada. Phase 2 akan membentuk dan
   menyegel dataset aktual; Phase 0 tidak memalsukan hash/label hasil final.
6. Measurement JSON memiliki SHA-256 (normalisasi LF/CRLF) untuk mendeteksi perubahan definisi secara tidak sengaja.
   Commit Git merupakan checkpoint desain. Perubahan sengaja membutuhkan kontrak versi baru
   dan alasan sebelum evaluasi; checksum bukan mekanisme anti-tamper terhadap pemilik repo.

## Verifikasi yang dijalankan

Semua dijalankan serial dari `case-resolution-copilot-v2/backend` dengan Python 3.12.13 melalui
environment `.venv` existing di checkout rebuild; tidak membuat environment atau mengubah dependency.

| Perintah | Hasil |
| --- | --- |
| `python -m pytest tests/unit/test_case_resolution_v2_contracts.py -q` | 43 passed, 0.19 s |
| `python -m scripts.validate_case_resolution_v2_contract --export-schemas` | PASS: schema export, design contract/hash, manifest isolation; tidak menjalankan produk |
| `python -m ruff check app/evaluation/case_resolution_v2 scripts/validate_case_resolution_v2_contract.py tests/unit/test_case_resolution_v2_contracts.py` | PASS |
| `python -m mypy app/evaluation/case_resolution_v2 scripts/validate_case_resolution_v2_contract.py tests/unit/test_case_resolution_v2_contracts.py` | PASS, 4 source files |
| Pemeriksaan tautan Markdown lokal, diff whitespace, V1 unchanged, dan baseline file hashes | PASS; enam dokumen bertautan valid, V1 tidak berubah, 11 file patch/untracked existing identik |

Masalah typing pada deklarasi threshold dan registry schema ditemukan pada pemeriksaan awal,
diperbaiki, lalu gate terarah diulang. Ini perbaikan kontrak, bukan failure trace keputusan bisnis
yang diperlukan Phase 3. Tes ini tidak membuktikan evaluator V2 atau workflow produk sudah benar.
Tidak ada provider call, deployment, database migration, browser E2E, atau load test.

## Cara mempelajari checkpoint

- Mulai dari baris `safe_automation` dan `eligible_automation_coverage`. Jelaskan mengapa satu
  kasus eligible yang sukses dari 40 kasus bukan otomatis berarti automation rate 100%.
- Bandingkan resolution dengan escalation: bukti apa yang dibutuhkan untuk menghitung masing-masing?
- Baca tes `test_same_outcome_timing_excludes_failed_manual_and_mismatched_terminal`. Mengapa
  manual yang cepat tetapi salah tidak boleh menghasilkan klaim speedup?
- Baca tes leakage: mengganti ID kasus tidak membuat variasi satu SOP menjadi holdout baru.
- Bedakan schema validation dari semantic validation: schema dapat mewajibkan parameter,
  tetapi scorer Phase 2 masih harus membuktikan parameter tersebut benar menurut oracle.

## Handoff

Phase 0 selesai pada cakupan audit dan kontrak. Phase 1 adalah lifecycle outcome, closure/reopen,
actual routing+acknowledgement, read-back tindakan, dan telemetry. Mulai phase berikutnya dengan
briefing serta desain migration/old-row handling; jangan memulai cloud atau studi waktu dulu.
Safety/resource policy dan aturan satu commit per phase tetap berlaku. Phase 1 belum dimulai.
