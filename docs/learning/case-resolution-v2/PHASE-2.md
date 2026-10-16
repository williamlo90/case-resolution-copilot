# Checkpoint pembelajaran — Phase 2

Tanggal: 13 Oktober 2026. Gate: **PASS — evaluator, mutation tests, dan corpus freeze**.
Branch: `case-resolution-v2`. SHA checkpoint adalah commit tunggal yang memuat file ini.

## Tujuan

Phase 1 membuktikan bahwa tindakan dapat diverifikasi. Phase 2 menilai apakah keputusan, parameter,
policy dan hasil akhirnya benar menurut oracle. Refund berhasil dikirim belum tentu keputusan benar:
nominal, penerima, eligibility atau batas persetujuannya bisa salah.

## Yang tersedia

1. Evaluator V2 terpisah di `backend/app/evaluation/case_resolution_v2/`. V1 tidak diubah.
   Score komponen membantu diagnosis, sedangkan `policy_correct` memakai syarat all-or-nothing.
   `correct_completion` juga mewajibkan outcome/receipt yang tepat. Kasus yang masih open bukan selesai.
2. Kontrak observasi untuk facts/citations, gaps, policy, semantic predicates, aksi dan semua parameter,
   approval, target read-back, closure dan acknowledgement eskalasi. JSON valid saja tidak cukup.
3. Corpus baru: 24 keluarga development, 3 regression V2, dan 40 holdout. Holdout terdiri dari
   14 billing, 13 refund, 13 account recovery, dengan empat kasus untuk setiap tag risiko wajib.
   Ada 36 kasus bertag critical. Cohort time study masih kosong dan menjadi pekerjaan Phase 5.
4. Manifest memisahkan split, mengunci input/label hashes, konfigurasi, seed, model/prompt, baseline
   produk dan identitas evaluator. Pemeriksaan keluarga dan policy text menghalangi duplikasi langsung.
5. Runner mengunci schedule/config sebelum eksekusi. Observasi harus disimpan dan disegel sebelum
   label dibaca. Perubahan input, label, konfigurasi, observasi atau evaluator ditolak. Kasus hilang,
   provider failure dan JSON rusak tetap masuk denominator.
6. Laporan JSON menyediakan counts, rates, Wilson interval, per-family failures dan terminal confusion
   matrix. Denominator nol adalah N/A. Hasil evaluator-only dipisahkan dari product/provider lane.

## Oracle dan batas provenance

Skenario/rule bersifat sintetis. Label dibuat dari source rule sebelum melihat output produk dan
memiliki rationale serta adjudication record. Penyusunan dan review dilakukan oleh Codex agent,
**bukan independent human review**. Nilai provenance baru `ai_authored_agent_adjudicated` membuat
hal ini eksplisit; threshold measurement Phase 0 tetap sama.

Holdout hanya menjalani authoring dan static validation, bukan product execution/debugging. Sealed
berarti identitasnya dikunci dan tidak dipakai tuning; bukan berarti tersembunyi secara kriptografis
dari penulisnya. Jika dipakai debugging produk, keluarga tersebut harus diturunkan menjadi development
atau regression dan diganti sebelum evaluasi final.

## Pengujian

Dijalankan lokal secara ringan dengan environment Python existing; tanpa database, browser, container,
provider call atau full product benchmark.

| Pemeriksaan | Hasil |
| --- | --- |
| `pytest tests/unit/test_case_resolution_v2_contracts.py tests/unit/test_case_resolution_v2_scoring.py tests/unit/test_case_resolution_v2_runner.py -q` | 105 passed |
| Contract/hash validator dan schema exports | PASS |
| Static corpus validation | 24 development / 3 regression / 40 holdout / 0 time study; product runs 0 |
| Ruff check dan format pada source/script/test terkait | PASS |
| Mypy pada 12 source files terkait | PASS |
| V1 code/data/evidence, frozen measurement contract, dan pekerjaan checkout lama | Tidak diubah |

Mutation suite membuktikan penolakan nominal/currency/recipient/account/target yang salah,
extra parameter/action, tenant berbeda, SOP/clause/tanggal salah, missing facts/gaps, citation tidak
mendukung, approval invalid, receipt mismatch, duplicate effect dan false closure. Tes eskalasi
membedakan rekomendasi dengan routing dan acknowledgement petugas yang benar.

Contoh observasi positif dalam unit test sengaja dibuat untuk menguji kontrak evaluator. Angka
kelulusannya bukan akurasi produk. Tidak ada laporan hasil holdout atau klaim CV baru.

## Cara mempelajari checkpoint

- Baca [panduan evaluator](../../evidence/case-resolution-v2/EVALUATOR.md), lalu ikuti satu input dan
  label development. Jelaskan sumber setiap expected value tanpa menggunakan output produk.
- Pada mutation parameter, nilai salah dibuat konsisten pada proposal, approval hash dan read-back.
  Mengapa evaluator tetap harus menolaknya? Karena konsistensi internal tidak membuktikan kesesuaian oracle.
- Baca `test_correct_decision_can_remain_incomplete`: apa bedanya policy correctness dan completion?
- Baca test malformed JSON/missing/provider failure: mengapa denominator tidak boleh mengecil?
- Ikuti declare → capture → observation seal → score. Di tahap mana label pertama boleh dibaca?
- Bedakan timestamp contoh oracle dari actual execution date: interval policy harus berlaku pada
  event nyata, bukan mengharuskan runtime selesai pada detik contoh yang dipilih penulis dataset.

## Handoff

Runtime adapter produk belum dibuat pada Phase 2. Adapter Phase 4 harus mengubah audit/approval/
read-back nyata menjadi observasi tanpa membaca label atau mengisi bukti yang hilang dari expected
answer. Beberapa business-rule/action families corpus lebih luas daripada engine saat ini; corpus
bukan bukti bahwa kapabilitas itu sudah didukung. Jangan menyamakan aksi berbeda atau menyaring kasus
sulit untuk mengejar skor. Bangun dan validasi kapabilitas hanya dengan development set sebelum ujian.

Phase 3 berikutnya menangani revisi SOP bertanggal, rollback dan product failure-to-regression trace.
Phase 3 belum dimulai. Phase 4 baru menghasilkan bukti end-to-end dari release candidate yang dibekukan.
